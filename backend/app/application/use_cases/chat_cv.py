import re
from typing import List, Dict, Optional, Tuple
from uuid import UUID, uuid4

from app.application.exceptions import AIProviderEmptyResponseError
from app.application.services.generation import ensure_quality
from app.domain.entities.generated_cv import GeneratedCV
from app.domain.schemas.cv_schema import PLACEHOLDER_PATTERN
from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.repositories import IGeneratedCVRepository
from app.domain.cv_templates import get_template
from app.logger import get_logger

MIN_JD_CHARS_FOR_GATE = 120  # mirrors _extract_target_jd_from_messages threshold

logger = get_logger("app.application.use_cases.chat_cv")
MIN_GENERATED_CV_CHARS = 80
SAFE_EMPTY_AI_MESSAGE = "Mình chưa tạo được CV vì AI không trả về nội dung. Vui lòng thử lại."
SAFE_INVALID_CV_MESSAGE = "Mình chưa tạo được CV vì nội dung AI trả về chưa đủ hợp lệ. Vui lòng thử lại."
ERROR_LIKE_CV_MARKERS = [
    "ai provider returned",
    "không trả về nội dung",
    "khong tra ve noi dung",
    "vui lòng thử lại",
    "vui long thu lai",
    "error",
    "exception",
    "traceback",
]

class ChatCVUseCase:
    def __init__(self, repo: IGeneratedCVRepository, ai_service: IAIService):
        self.repo = repo
        self.ai = ai_service

    def _build_format_instruction(self, output_format: str) -> str:
        if output_format == "docx":
            return (
                "Đầu ra CV phải là MARKDOWN sạch để hệ thống export DOCX. "
                "Dùng heading rõ ràng, bullet chuẩn, không chèn ký tự lạ."
            )
        return (
            "Đầu ra CV bắt buộc ở định dạng MARKDOWN. "
            "Dùng heading, bullet list, bố cục rõ ràng."
        )

    def _build_template_instruction(self, template_id: Optional[str]) -> str:
        if not template_id:
            return ""
        tpl = get_template(template_id)
        if not tpl:
            return ""
        return (
            f"\n\nUser đã chọn template '{tpl['name']}'. "
            f"BẮT BUỘC viết CV theo ĐÚNG cấu trúc heading/section của template dưới đây. "
            f"Giữ nguyên thứ tự các section, chỉ điền nội dung thực tế thay cho placeholder:\n\n"
            f"--- TEMPLATE ---\n{tpl['skeleton']}\n--- END TEMPLATE ---\n"
        )

    def _clean_cv_markdown(self, value: str) -> str:
        cv_content = (value or "").strip()
        if cv_content.startswith("```markdown"):
            cv_content = cv_content.replace("```markdown", "", 1)
            if cv_content.endswith("```"):
                cv_content = cv_content[:-3]
        elif cv_content.startswith("```"):
            cv_content = cv_content.replace("```", "", 1)
            if cv_content.endswith("```"):
                cv_content = cv_content[:-3]
        return self._remove_repeated_cv_document(cv_content.strip())

    def _count_placeholders(self, value: str) -> int:
        return len(PLACEHOLDER_PATTERN.findall(value or ""))

    def _infer_generation_mode(self, cv_content: str, messages: List[Dict[str, str]]) -> str:
        if self._count_placeholders(cv_content) > 0:
            return "template_only"
        user_text = " ".join(
            str(message.get("content") or "")
            for message in messages or []
            if message.get("role") == "user"
        ).lower()
        has_personal_facts = any(
            token in user_text
            for token in [
                "tôi tên",
                "anh tên",
                "em tên",
                "email",
                "số điện thoại",
                "github",
                "linkedin",
                "học trường",
                "chuyên ngành",
                "kinh nghiệm",
                "dự án",
            ]
        )
        return "personalized" if has_personal_facts else "template_only"

    def _extract_candidate_facts(self, messages: List[Dict[str, str]]) -> dict:
        user_messages = [
            str(message.get("content") or "").strip()
            for message in messages or []
            if message.get("role") == "user" and str(message.get("content") or "").strip()
        ]
        combined = "\n".join(user_messages)
        facts = {}
        email = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", combined)
        if email:
            facts["email"] = email.group(0)
        phone = re.search(r"(?:\+?84|0)\d[\d\s.-]{7,12}\d", combined)
        if phone:
            facts["phone"] = phone.group(0)
        if re.search(r"(?i)\bgithub\.com/[^\s]+", combined):
            facts["github"] = True
        if re.search(r"(?i)\blinkedin\.com/[^\s]+", combined):
            facts["linkedin"] = True
        education_terms = ["học trường", "đại học", "university", "chuyên ngành", "khoa học máy tính", "haui"]
        if any(term in combined.lower() for term in education_terms):
            facts["education"] = True
        if any(term in combined.lower() for term in ["dự án", "project", "kinh nghiệm", "thực tập", "intern"]):
            facts["experience_or_projects"] = True
        return facts

    def _extract_target_jd_from_messages(self, messages: List[Dict[str, str]]) -> str:
        jd_markers = ["jd", "job description", "mô tả công việc", "yêu cầu công việc", "requirements"]
        for message in reversed(messages or []):
            if message.get("role") != "user":
                continue
            content = str(message.get("content") or "").strip()
            if len(content) >= 120 and any(marker in content.lower() for marker in jd_markers):
                return content
        return ""

    def _remove_repeated_cv_document(self, markdown: str) -> str:
        """Drop accidental repeated full-CV blocks emitted by the model in one response."""
        text = (markdown or "").strip()
        if not text:
            return text

        h1_matches = list(re.finditer(r"(?m)^#\s+(.+?)\s*$", text))
        if len(h1_matches) >= 2:
            first_title = re.sub(r"\s+", " ", h1_matches[0].group(1).strip().lower())
            for match in h1_matches[1:]:
                title = re.sub(r"\s+", " ", match.group(1).strip().lower())
                if title == first_title:
                    return text[:match.start()].rstrip()

        first_contact = re.search(
            r"(?mi)^##\s+(thông tin liên hệ|contact|personal information)\s*$",
            text,
        )
        if first_contact:
            second_contact = re.search(
                r"(?mi)^##\s+(thông tin liên hệ|contact|personal information)\s*$",
                text[first_contact.end():],
            )
            if second_contact:
                cut_at = first_contact.end() + second_contact.start()
                prefix = text[:cut_at].rstrip()
                if self._looks_like_markdown_cv(prefix):
                    return prefix

        return text

    def _get_last_user_message(self, messages: List[Dict[str, str]]) -> str:
        for message in reversed(messages or []):
            if message.get("role") == "user":
                return str(message.get("content") or "").strip()
        return ""

    def _is_template_catalog_request(self, message: str) -> bool:
        normalized = (message or "").lower()
        asks_templates = any(
            phrase in normalized
            for phrase in [
                "mẫu cv",
                "mau cv",
                "template cv",
                "các mẫu",
                "những mẫu",
                "mẫu nào",
            ]
        )
        chooses_template = any(
            phrase in normalized
            for phrase in [
                "chọn mẫu",
                "chon mau",
                "dùng mẫu",
                "dung mau",
                "lấy mẫu",
                "lay mau",
                "sử dụng mẫu",
                "su dung mau",
            ]
        )
        return asks_templates and not chooses_template

    def _build_template_catalog_reply(self, messages: List[Dict[str, str]]) -> str:
        context = " ".join(str(m.get("content") or "") for m in messages[-6:]).lower()
        has_cs_context = any(
            token in context
            for token in ["khoa học máy tính", "computer science", "cntt", "ai", "data", "lập trình", "software"]
        )
        recommendation = (
            "Với thông tin hiện tại của bạn, mình đề xuất bắt đầu bằng **AI/ML Intern** hoặc **Software Engineer Intern**."
            if has_cs_context
            else "Nếu bạn chưa chắc hướng ứng tuyển, mình đề xuất bắt đầu bằng **Software Engineer Intern** hoặc **CV theo dự án cá nhân**."
        )
        return (
            "Mình có các hướng mẫu CV sau:\n\n"
            "1. **AI/ML Intern** - phù hợp nếu muốn đi theo Machine Learning, Computer Vision, NLP.\n"
            "2. **Data Analyst Intern** - nhấn mạnh SQL, Python, Excel/BI, phân tích dữ liệu.\n"
            "3. **Backend Intern** - nhấn mạnh API, database, server, hệ thống.\n"
            "4. **Frontend Intern** - nhấn mạnh React, UI, sản phẩm web.\n"
            "5. **Software Engineer Fresher** - cân bằng thuật toán, dự án, kỹ năng lập trình.\n"
            "6. **CV theo dự án cá nhân** - phù hợp khi chưa có kinh nghiệm làm việc nhưng có project.\n"
            "7. **CV học thuật/nghiên cứu** - phù hợp nếu có paper, lab, đề tài nghiên cứu.\n\n"
            f"{recommendation} Bạn muốn dùng mẫu nào?"
        )

    def _looks_like_markdown_cv(self, value: str) -> bool:
        text = (value or "").strip()
        if not text:
            return False

        lower_text = text.lower()
        heading_count = len(re.findall(r"(?m)^#{1,3}\s+\S+", text))
        cv_section_keywords = [
            "kinh nghiệm",
            "experience",
            "kỹ năng",
            "skills",
            "học vấn",
            "education",
            "dự án",
            "projects",
            "summary",
            "mục tiêu",
        ]
        keyword_hits = sum(1 for keyword in cv_section_keywords if keyword in lower_text)
        return heading_count >= 2 and keyword_hits >= 2

    def _is_valid_generated_cv_content(self, value: str) -> bool:
        text = self._clean_cv_markdown(value)
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) < MIN_GENERATED_CV_CHARS:
            return False

        lower_text = normalized.lower()
        if any(marker in lower_text for marker in ERROR_LIKE_CV_MARKERS):
            return False

        placeholder_only_text = PLACEHOLDER_PATTERN.sub("", normalized)
        placeholder_only_text = re.sub(r"[\s#*\-_|:.,;/()]+", "", placeholder_only_text)
        if not placeholder_only_text:
            return False

        return self._looks_like_markdown_cv(text)

    async def _save_safe_failure_reply(
        self,
        *,
        conversation_id: UUID,
        user_id: UUID,
        messages: List[Dict[str, str]],
        reply: str,
    ) -> None:
        await self.repo.save_chat_messages(
            conversation_id,
            user_id,
            messages + [{"role": "assistant", "content": reply}],
        )

    def _extract_final_cv(self, ai_reply: str) -> tuple[str, Optional[str]]:
        match = re.search(r"<FINAL_CV>(.*?)</FINAL_CV>", ai_reply, flags=re.DOTALL | re.IGNORECASE)
        if match:
            cv_content = self._clean_cv_markdown(match.group(1))
            clean_reply = re.sub(
                r"<FINAL_CV>.*?</FINAL_CV>",
                "\n\n*(Đã tạo CV thành công)*",
                ai_reply,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip()
            clean_reply = re.sub(r"\n{3,}", "\n\n", clean_reply)
            return clean_reply or "*(Đã tạo CV thành công)*", cv_content

        tag_match = re.search(r"<FINAL_CV>(.*)$", ai_reply, flags=re.DOTALL | re.IGNORECASE)
        if tag_match:
            cv_content = self._clean_cv_markdown(tag_match.group(1))
            clean_reply = ai_reply[:tag_match.start()].strip() or "*(Đã tạo CV thành công)*"
            return clean_reply, cv_content

        first_heading = re.search(r"(?m)^#\s+\S+", ai_reply)
        if first_heading:
            candidate = self._clean_cv_markdown(ai_reply[first_heading.start():])
            if self._looks_like_markdown_cv(candidate):
                clean_reply = ai_reply[:first_heading.start()].strip() or "*(Đã tạo CV thành công)*"
                return clean_reply, candidate

        stripped = self._clean_cv_markdown(ai_reply)
        if self._looks_like_markdown_cv(stripped):
            return "*(Đã tạo CV thành công)*", stripped

        return ai_reply, None

    async def _apply_quality_gate(
        self,
        cv_content: str,
        messages: List[Dict[str, str]],
        current_cv: Optional[GeneratedCV],
        output_format: str,
    ) -> tuple[str, Optional[str]]:
        """Run the analyze-and-revise quality gate when a JD is available.

        Returns ``(content, resolved_jd_text)``. ``resolved_jd_text`` is the
        full JD body the gate actually scored against (or ``None`` when the
        gate was skipped). Caller uses it to persist a real ``target_jd_text``
        on the saved CV instead of the legacy "Được cung cấp qua chat"
        sentinel — so a later re-analyze runs on the SAME JD as the gate did.

        Skips silently when no JD signal is present in the conversation —
        and never raises: if the gate itself errors out we keep the original
        CV so the user still gets a saved draft.
        """
        jd_text = self._extract_target_jd_from_messages(messages)
        if not jd_text and current_cv:
            stored_jd = (current_cv.target_jd_text or "").strip()
            if (
                len(stored_jd) >= MIN_JD_CHARS_FOR_GATE
                and stored_jd != "Được cung cấp qua chat"
            ):
                jd_text = stored_jd

        if not jd_text or len(jd_text) < MIN_JD_CHARS_FOR_GATE:
            logger.info("Quality gate skipped: no JD in chat context")
            return cv_content, None

        try:
            result = await ensure_quality(
                cv_content=cv_content,
                jd_text=jd_text,
                ai_service=self.ai,
                output_format=output_format,
            )
        except Exception as exc:
            logger.warning("Quality gate errored, keeping original CV: %s", exc, exc_info=True)
            return cv_content, jd_text

        logger.info(
            "Quality gate: passed=%s initial=%.1f final=%.1f revisions=%d warnings=%s",
            result.passed_gate,
            result.initial_score,
            result.final_score,
            result.revisions_used,
            result.warnings,
        )
        return result.content, jd_text

    async def _build_generated_cv(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
        messages: List[Dict[str, str]],
        reply_text: str,
        cv_content: str,
        output_format: str,
        current_cv: Optional[GeneratedCV] = None,
        resolved_jd_text: Optional[str] = None,
    ) -> GeneratedCV | dict:
        if not self._is_valid_generated_cv_content(cv_content):
            logger.warning(
                "Rejected generated CV before save: content_len=%d, conversation_id=%s",
                len(cv_content or ""),
                conversation_id,
            )
            raise ValueError("AI returned invalid generated CV content")

        clean_reply = reply_text.strip() or "*(Đã tạo CV thành công)*"
        generated_payload = {
            "format": output_format,
            "content": cv_content,
            "markdown": cv_content,
            "generation_mode": self._infer_generation_mode(cv_content, messages),
            "placeholder_count": self._count_placeholders(cv_content),
            "candidate_facts": self._extract_candidate_facts(messages),
        }
        if current_cv:
            base_profile = dict(current_cv.base_profile_data or {})
            base_profile["generation_mode"] = generated_payload["generation_mode"]
            base_profile["candidate_facts"] = generated_payload["candidate_facts"]
            # Prefer the JD the gate actually scored against; fall back to
            # whatever the parent version had so we never lose JD signal.
            if resolved_jd_text and len(resolved_jd_text.strip()) >= MIN_JD_CHARS_FOR_GATE:
                target_jd_text = resolved_jd_text.strip()
            else:
                target_jd_text = current_cv.target_jd_text
            return {
                "target_jd_text": target_jd_text,
                "base_profile_data": base_profile,
                "generated_content": generated_payload,
                "status": "completed",
            }

        # New conversation: prefer the JD resolved by the quality gate
        # (full body) over the marker-based extractor; fall back to sentinel.
        if resolved_jd_text and len(resolved_jd_text.strip()) >= MIN_JD_CHARS_FOR_GATE:
            target_jd_text = resolved_jd_text.strip()
        else:
            target_jd_text = (
                self._extract_target_jd_from_messages(messages)
                or "Được cung cấp qua chat"
            )
        return GeneratedCV(
            user_id=user_id,
            conversation_id=conversation_id,
            version=1,
            target_jd_text=target_jd_text,
            base_profile_data={
                "level": "Unknown",
                "job_title": "CV Từ Chatbot",
                "generation_mode": generated_payload["generation_mode"],
                "candidate_facts": generated_payload["candidate_facts"],
            },
            generated_content=generated_payload,
            status="completed",
        )

    async def execute(
        self,
        user_id: UUID,
        messages: List[Dict[str, str]],
        output_format: str = "markdown",
        template_id: Optional[str] = None,
        current_cv: Optional[GeneratedCV] = None,
        conversation_id: Optional[UUID] = None,
    ) -> Tuple[str, Optional[UUID], UUID]:
        """
        Process the chat message. If AI outputs <FINAL_CV>, extract it and save.
        Returns (reply_text, generated_cv_id).
        """
        if output_format not in {"markdown", "docx"}:
            output_format = "markdown"

        active_conversation_id = current_cv.conversation_id if current_cv else (conversation_id or uuid4())

        if self._is_template_catalog_request(self._get_last_user_message(messages)):
            reply = self._build_template_catalog_reply(messages)
            await self.repo.save_chat_messages(
                active_conversation_id,
                user_id,
                messages + [{"role": "assistant", "content": reply}],
            )
            return reply, None, active_conversation_id


        system_prompt = {
            "role": "system",
            "content": (
                "Bạn là một chuyên gia tư vấn tạo CV (Resumé). Nhiệm vụ của bạn là thu thập thông tin từ user: "
                "1. Vị trí ứng tuyển (Job Title). "
                "2. Cấp độ (Level: Fresher, Junior, Middle, Senior, Manager, etc). "
                "3. Mô tả công việc (Job Description / JD). "
                "Nếu user chưa cung cấp đủ các thông tin trên, hãy hỏi lại user một cách thân thiện, tự nhiên. "
                "Nếu user cung cấp thông tin cá nhân rõ ràng như năm học, chuyên ngành, trường, kỹ năng, dự án, hãy đưa thông tin đó vào bản CV nháp ngay; không để placeholder cho dữ kiện user đã nói. "
                "Nếu user hỏi bạn có những mẫu CV nào, chỉ liệt kê các mẫu phù hợp và hỏi user chọn mẫu; TUYỆT ĐỐI không xuất <FINAL_CV> khi user chưa chọn mẫu. "
                "Nếu user ĐÃ CUNG CẤP ĐỦ thông tin, hãy tiến hành viết CV ngay lập tức. "
                f"Định dạng user yêu cầu: {output_format}. {self._build_format_instruction(output_format)} "
                "QUAN TRỌNG NHẤT: Toàn bộ nội dung CV PHẢI được đặt bên trong thẻ <FINAL_CV> và </FINAL_CV>. "
                "Tuyệt đối không được quên hai thẻ này khi bạn xuất ra CV. Các chữ bên ngoài thẻ này là lời nói với user. "
                "QUY TẮC DỮ LIỆU: Không tự bịa thông tin cá nhân, trường học, ngành học, GPA, thành phố/quốc gia, tháng bắt đầu/kết thúc, tên công ty hoặc chức danh nếu user chưa cung cấp. "
                "Nếu thiếu dữ liệu cá nhân, hãy dùng placeholder rõ ràng như [Ngành học], [Email], [Số điện thoại], [Tên công ty]. "
                "QUY TẮC TUYỆT ĐỐI VỀ HÌNH THỨC CV: KHÔNG BAO GIỜ dùng emoji, icon, biểu tượng cảm xúc (📍🏠📱📧✉️📎🌟⭐💼 v.v.) trong nội dung CV. "
                "CV chuyên nghiệp chỉ dùng văn bản thuần, heading, bullet point chuẩn. Tuyệt đối tối giản, không trang trí."
                + self._build_template_instruction(template_id)
            )
        }
        
        # Optimization: LLM Context Memory (Sliding Window)
        # Only keep the last 6 messages (3 turns) to prevent token explosion.
        recent_messages = messages[-6:] if len(messages) > 6 else messages
        chat_messages = [system_prompt] + recent_messages
        
        try:
            ai_reply = await self.ai.chat_interaction(chat_messages)
        except AIProviderEmptyResponseError:
            logger.warning(
                "AI chat generation returned empty response: user_id=%s, conversation_id=%s, messages_count=%d",
                user_id,
                active_conversation_id,
                len(messages),
            )
            await self._save_safe_failure_reply(
                conversation_id=active_conversation_id,
                user_id=user_id,
                messages=messages,
                reply=SAFE_EMPTY_AI_MESSAGE,
            )
            return SAFE_EMPTY_AI_MESSAGE, None, active_conversation_id

        if not (ai_reply or "").strip():
            logger.warning(
                "AI chat generation returned blank text: user_id=%s, conversation_id=%s, messages_count=%d",
                user_id,
                active_conversation_id,
                len(messages),
            )
            await self._save_safe_failure_reply(
                conversation_id=active_conversation_id,
                user_id=user_id,
                messages=messages,
                reply=SAFE_EMPTY_AI_MESSAGE,
            )
            return SAFE_EMPTY_AI_MESSAGE, None, active_conversation_id
        
        cv_id = None
        clean_reply, cv_content = self._extract_final_cv(ai_reply)

        if cv_content:
            if not self._is_valid_generated_cv_content(cv_content):
                logger.warning(
                    "AI chat generation returned invalid CV content: user_id=%s, conversation_id=%s, content_len=%d",
                    user_id,
                    active_conversation_id,
                    len(cv_content),
                )
                await self._save_safe_failure_reply(
                    conversation_id=active_conversation_id,
                    user_id=user_id,
                    messages=messages,
                    reply=SAFE_INVALID_CV_MESSAGE,
                )
                return SAFE_INVALID_CV_MESSAGE, None, active_conversation_id

            cv_content, resolved_jd_text = await self._apply_quality_gate(
                cv_content=cv_content,
                messages=messages,
                current_cv=current_cv,
                output_format=output_format,
            )

            built_payload = await self._build_generated_cv(
                user_id=user_id,
                conversation_id=active_conversation_id,
                messages=messages,
                reply_text=clean_reply.strip(),
                cv_content=cv_content,
                output_format=output_format,
                current_cv=current_cv,
                resolved_jd_text=resolved_jd_text,
            )
            if current_cv:
                cv_entity = await self.repo.create_versioned(
                    user_id=user_id,
                    conversation_id=current_cv.conversation_id,
                    parent_version_id=current_cv.id,
                    target_jd_text=built_payload["target_jd_text"],
                    base_profile_data=built_payload["base_profile_data"],
                    generated_content=built_payload["generated_content"],
                    status=built_payload["status"],
                )
            else:
                cv_entity = built_payload
                await self.repo.create(cv_entity)
            cv_id = cv_entity.id
            
            ai_reply = clean_reply
            full_chat = messages + [{"role": "assistant", "content": ai_reply}]
            await self.repo.save_chat_messages(cv_entity.conversation_id, user_id, full_chat)
        else:
            await self.repo.save_chat_messages(
                active_conversation_id,
                user_id,
                messages + [{"role": "assistant", "content": ai_reply}],
            )
            
        return ai_reply, cv_id, active_conversation_id

    async def execute_stream(
        self,
        user_id: UUID,
        messages: List[Dict[str, str]],
        output_format: str = "markdown",
        template_id: Optional[str] = None,
        current_cv: Optional[GeneratedCV] = None,
        conversation_id: Optional[UUID] = None,
    ):
        import json
        if output_format not in {"markdown", "docx"}:
            output_format = "markdown"

        active_conversation_id = current_cv.conversation_id if current_cv else (conversation_id or uuid4())
        yield f"event: conversation_id\ndata: {json.dumps(str(active_conversation_id))}\n\n"

        if self._is_template_catalog_request(self._get_last_user_message(messages)):
            reply = self._build_template_catalog_reply(messages)
            await self.repo.save_chat_messages(
                active_conversation_id,
                user_id,
                messages + [{"role": "assistant", "content": reply}],
            )
            yield f"event: chat_chunk\ndata: {json.dumps(reply)}\n\n"
            yield f"event: status\ndata: {json.dumps({'state': 'waiting_input', 'label': 'Đang chờ bạn chọn mẫu CV.'})}\n\n"
            return

        system_prompt = {
            "role": "system",
            "content": (
                "Bạn là một chuyên gia tư vấn tạo CV (Resumé). Nhiệm vụ của bạn là thu thập thông tin từ user: "
                "1. Vị trí ứng tuyển (Job Title). "
                "2. Cấp độ (Level: Fresher, Junior, Middle, Senior, Manager, etc). "
                "3. Mô tả công việc (Job Description / JD). "
                "Nếu user chưa cung cấp đủ các thông tin trên, hãy hỏi lại user một cách thân thiện tự nhiên, ĐỒNG THỜI có thể đưa ra một bản CV mẫu (template) sơ bộ để họ gợi nhớ thông tin. "
                "Nếu user cung cấp thông tin cá nhân rõ ràng như năm học, chuyên ngành, trường, kỹ năng, dự án, hãy đưa thông tin đó vào bản CV nháp ngay; không để placeholder cho dữ kiện user đã nói. "
                "Nếu user hỏi bạn có những mẫu CV nào, chỉ liệt kê các mẫu phù hợp và hỏi user chọn mẫu; TUYỆT ĐỐI không xuất <FINAL_CV> khi user chưa chọn mẫu. "
                "Nếu user ĐÃ CUNG CẤP ĐỦ thông tin, hãy tiến hành viết CV chi tiết cho họ. "
                f"Định dạng yêu cầu: {output_format}. {self._build_format_instruction(output_format)} "
                "CỰC KỲ QUAN TRỌNG (ĐIỀU KIỆN TIÊN QUYẾT): "
                "BẤT KỲ KHI NÀO BẠN VIẾT NỘI DUNG CV (DÙ CHỈ LÀ BẢN DÀN Ý, BẢN NHÁP (TEMPLATE) HAY BẢN HOÀN CHỈNH), BẠN BẮT BUỘC PHẢI ĐẶT TOÀN BỘ NỘI DUNG CV ĐÓ VÀO BÊN TRONG CẶP THẺ `<FINAL_CV>` VÀ `</FINAL_CV>`. "
                "Ví dụ:\n"
                "Tôi đã làm cho bạn một bản mẫu đây:\n"
                "<FINAL_CV>\n"
                "# Tên của bạn\n"
                "## Kỹ năng\n"
                "...nội dung...\n"
                "</FINAL_CV>\n"
                "Hãy bổ sung thêm các phần còn thiếu nhé!\n\n"
                "Hệ thống SẼ CHỈ trích xuất văn bản nằm trong thẻ `<FINAL_CV>` để hiển thị lên màn hình Document Preview của user. NẾU BẠN QUÊN THẺ NÀY, MÀN HÌNH PREVIEW SẼ BỊ TRỐNG! "
                "Danh sách hoặc các gạch đầu dòng thuộc về CV PHẢI nằm trong thẻ này. Mọi chữ nằm ngoài thẻ sẽ chỉ là tin nhắn giao tiếp bình thường. "
                "QUY TẮC DỮ LIỆU: Không tự bịa thông tin cá nhân, trường học, ngành học, GPA, thành phố/quốc gia, tháng bắt đầu/kết thúc, tên công ty hoặc chức danh nếu user chưa cung cấp. "
                "Nếu thiếu dữ liệu cá nhân, hãy dùng placeholder rõ ràng như [Ngành học], [Email], [Số điện thoại], [Tên công ty]. "
                "QUY TẮC TUYỆT ĐỐI VỀ HÌNH THỨC CV: KHÔNG BAO GIỜ dùng emoji, icon, biểu tượng cảm xúc (📍🏠📱📧✉️📎🌟⭐💼 v.v.) trong nội dung CV. "
                "CV chuyên nghiệp chỉ dùng văn bản thuần, heading, bullet point chuẩn. Tuyệt đối tối giản, không trang trí."
                + self._build_template_instruction(template_id)
            )
        }
        
        # Optimization: LLM Context Memory (Sliding Window)
        # Only keep the last 6 messages (3 turns) to prevent token explosion.
        recent_messages = messages[-6:] if len(messages) > 6 else messages
        chat_messages = [system_prompt] + recent_messages
        
        buffer = ""
        in_cv = False
        cv_text = ""
        ai_reply = ""
        saved_cv_id = None
        
        async def save_cv_entity(cv_raw_text: str, reply_text: str) -> tuple[UUID, str]:
            cv_content = self._clean_cv_markdown(cv_raw_text)

            cv_content, resolved_jd_text = await self._apply_quality_gate(
                cv_content=cv_content,
                messages=messages,
                current_cv=current_cv,
                output_format=output_format,
            )

            clean_reply = (reply_text or "").strip()
            if not clean_reply:
                clean_reply = "*(Đã tạo CV thành công)*"

            built_payload = await self._build_generated_cv(
                user_id=user_id,
                conversation_id=active_conversation_id,
                messages=messages,
                reply_text=clean_reply,
                cv_content=cv_content,
                output_format=output_format,
                current_cv=current_cv,
                resolved_jd_text=resolved_jd_text,
            )
            if current_cv:
                cv_entity = await self.repo.create_versioned(
                    user_id=user_id,
                    conversation_id=current_cv.conversation_id,
                    parent_version_id=current_cv.id,
                    target_jd_text=built_payload["target_jd_text"],
                    base_profile_data=built_payload["base_profile_data"],
                    generated_content=built_payload["generated_content"],
                    status=built_payload["status"],
                )
            else:
                cv_entity = built_payload
                await self.repo.create(cv_entity)
            
            full_chat = messages + [{"role": "assistant", "content": clean_reply}]
            await self.repo.save_chat_messages(cv_entity.conversation_id, user_id, full_chat)
            return cv_entity.id, cv_content

        stream = self.ai.chat_interaction_stream(chat_messages)
        
        try:
            yield f"event: status\ndata: {json.dumps({'state': 'reasoning', 'label': 'AI đang phân tích yêu cầu và lên nội dung CV...'})}\n\n"
            # We must use proper async for loop when using async generators
            async for chunk in stream:
                buffer += chunk
                
                while True:
                    if not in_cv:
                        tag_idx = buffer.find("<FINAL_CV>")
                        if tag_idx != -1:
                            out = buffer[:tag_idx]
                            buffer = buffer[tag_idx + len("<FINAL_CV>"):]
                            if out:
                                ai_reply += out
                                yield f"event: chat_chunk\ndata: {json.dumps(out)}\n\n"
                            in_cv = True
                            yield f"event: status\ndata: {json.dumps({'state': 'drafting', 'label': 'AI đang soạn CV và đổ nội dung vào tài liệu...'})}\n\n"
                            yield f"event: signal\ndata: {json.dumps('START_CV')}\n\n"
                            continue
                        else:
                            if len(buffer) > 20: # keep 20 chars buffer in case pattern matches partially
                                out = buffer[:-20]
                                buffer = buffer[-20:]
                                ai_reply += out
                                yield f"event: chat_chunk\ndata: {json.dumps(out)}\n\n"
                            break
                    else:
                        tag_idx = buffer.find("</FINAL_CV>")
                        if tag_idx != -1:
                            out = buffer[:tag_idx]
                            buffer = buffer[tag_idx + len("</FINAL_CV>"):]
                            if out:
                                cv_text += out
                            in_cv = False
                            
                            yield f"event: status\ndata: {json.dumps({'state': 'saving_version', 'label': 'Đang chấm điểm + lưu phiên bản CV...'})}\n\n"
                            saved_cv_id, saved_cv_content = await save_cv_entity(cv_text, ai_reply)
                            yield f"event: cv_chunk\ndata: {json.dumps(saved_cv_content)}\n\n"
                            yield f"event: cv_id\ndata: {json.dumps(str(saved_cv_id))}\n\n"
                            yield f"event: status\ndata: {json.dumps({'state': 'done', 'label': 'Đã tạo xong phiên bản CV mới.'})}\n\n"
                            continue
                        else:
                            if len(buffer) > 20:
                                out = buffer[:-20]
                                buffer = buffer[-20:]
                                cv_text += out
                            break

            if buffer:
                if not in_cv:
                    ai_reply += buffer
                    yield f"event: chat_chunk\ndata: {json.dumps(buffer)}\n\n"
                else:
                    cv_text += buffer

            if cv_text and not saved_cv_id:
                yield f"event: status\ndata: {json.dumps({'state': 'saving_version', 'label': 'Đang chấm điểm + lưu phiên bản CV...'})}\n\n"
                saved_cv_id, saved_cv_content = await save_cv_entity(cv_text, ai_reply)
                yield f"event: cv_chunk\ndata: {json.dumps(saved_cv_content)}\n\n"
                yield f"event: cv_id\ndata: {json.dumps(str(saved_cv_id))}\n\n"
                yield f"event: status\ndata: {json.dumps({'state': 'done', 'label': 'Đã tạo xong phiên bản CV mới.'})}\n\n"

            if not cv_text and not saved_cv_id:
                if not ai_reply.strip():
                    logger.warning(
                        "AI chat generation stream returned no text: user_id=%s, conversation_id=%s, messages_count=%d",
                        user_id,
                        active_conversation_id,
                        len(messages),
                    )
                    await self._save_safe_failure_reply(
                        conversation_id=active_conversation_id,
                        user_id=user_id,
                        messages=messages,
                        reply=SAFE_EMPTY_AI_MESSAGE,
                    )
                    yield f"event: chat_chunk\ndata: {json.dumps(SAFE_EMPTY_AI_MESSAGE)}\n\n"
                    yield f"event: status\ndata: {json.dumps({'state': 'failed', 'label': 'AI không trả về nội dung.'})}\n\n"
                    return

                clean_reply, fallback_cv = self._extract_final_cv(ai_reply)
                if fallback_cv:
                    yield f"event: status\ndata: {json.dumps({'state': 'saving_version', 'label': 'Đang chấm điểm + lưu phiên bản CV...'})}\n\n"
                    saved_cv_id, saved_cv_content = await save_cv_entity(fallback_cv, clean_reply)
                    yield f"event: cv_chunk\ndata: {json.dumps(saved_cv_content)}\n\n"
                    yield f"event: cv_id\ndata: {json.dumps(str(saved_cv_id))}\n\n"
                    yield f"event: status\ndata: {json.dumps({'state': 'done', 'label': 'Đã tạo xong phiên bản CV mới.'})}\n\n"
                else:
                    await self.repo.save_chat_messages(
                        active_conversation_id,
                        user_id,
                        messages + [{"role": "assistant", "content": ai_reply}],
                    )
        except AIProviderEmptyResponseError:
            logger.warning(
                "AI chat generation stream returned empty provider response: user_id=%s, conversation_id=%s, messages_count=%d",
                user_id,
                active_conversation_id,
                len(messages),
            )
            await self._save_safe_failure_reply(
                conversation_id=active_conversation_id,
                user_id=user_id,
                messages=messages,
                reply=SAFE_EMPTY_AI_MESSAGE,
            )
            yield f"event: chat_chunk\ndata: {json.dumps(SAFE_EMPTY_AI_MESSAGE)}\n\n"
            yield f"event: status\ndata: {json.dumps({'state': 'failed', 'label': 'AI không trả về nội dung.'})}\n\n"
            yield f"event: error\ndata: {json.dumps('AI provider returned an empty response')}\n\n"
        except ValueError:
            logger.warning(
                "Rejected invalid generated CV from AI stream: user_id=%s, conversation_id=%s, content_len=%d",
                user_id,
                active_conversation_id,
                len(cv_text or ""),
            )
            await self._save_safe_failure_reply(
                conversation_id=active_conversation_id,
                user_id=user_id,
                messages=messages,
                reply=SAFE_INVALID_CV_MESSAGE,
            )
            yield f"event: chat_chunk\ndata: {json.dumps(SAFE_INVALID_CV_MESSAGE)}\n\n"
            yield f"event: status\ndata: {json.dumps({'state': 'failed', 'label': 'AI trả về nội dung CV chưa hợp lệ.'})}\n\n"
            yield f"event: error\ndata: {json.dumps('AI returned invalid generated CV content')}\n\n"
        except Exception as e:
            logger.error(
                "Error in AI stream: %s, user_id=%s, conversation_id=%s, messages_count=%d",
                type(e).__name__,
                user_id,
                active_conversation_id,
                len(messages),
                exc_info=True,
            )
            await self._save_safe_failure_reply(
                conversation_id=active_conversation_id,
                user_id=user_id,
                messages=messages,
                reply=SAFE_EMPTY_AI_MESSAGE,
            )
            yield f"event: chat_chunk\ndata: {json.dumps(SAFE_EMPTY_AI_MESSAGE)}\n\n"
            yield f"event: status\ndata: {json.dumps({'state': 'failed', 'label': 'Không thể tạo CV lúc này.'})}\n\n"
            yield f"event: error\ndata: {json.dumps('AI generation failed')}\n\n"
