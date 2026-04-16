import re
from typing import List, Dict, Optional, Tuple
from uuid import UUID

from app.domain.entities.generated_cv import GeneratedCV
from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.repositories import IGeneratedCVRepository
from app.domain.cv_templates import get_template
from app.logger import get_logger

logger = get_logger("app.application.use_cases.chat_cv")

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

    async def _build_generated_cv(
        self,
        *,
        user_id: UUID,
        messages: List[Dict[str, str]],
        reply_text: str,
        cv_content: str,
        output_format: str,
        current_cv: Optional[GeneratedCV] = None,
    ) -> GeneratedCV:
        next_version = (
            await self.repo.get_next_version(user_id, current_cv.conversation_id)
            if current_cv
            else 1
        )
        clean_reply = reply_text.strip() or "*(Đã tạo CV thành công)*"
        generated_payload = {
            "format": output_format,
            "content": cv_content,
            "markdown": cv_content,
            "chat_history": messages + [{"role": "assistant", "content": clean_reply}],
        }
        entity_kwargs = {
            "user_id": user_id,
            "version": next_version,
            "target_jd_text": current_cv.target_jd_text if current_cv else "Được cung cấp qua chat",
            "base_profile_data": current_cv.base_profile_data if current_cv else {"level": "Unknown", "job_title": "CV Từ Chatbot"},
            "generated_content": generated_payload,
            "status": "completed",
        }
        if current_cv:
            entity_kwargs["conversation_id"] = current_cv.conversation_id
            entity_kwargs["parent_version_id"] = current_cv.id

        cv_entity = GeneratedCV(**entity_kwargs)
        return cv_entity

    async def execute(
        self,
        user_id: UUID,
        messages: List[Dict[str, str]],
        output_format: str = "markdown",
        template_id: Optional[str] = None,
        current_cv: Optional[GeneratedCV] = None,
    ) -> Tuple[str, Optional[UUID]]:
        """
        Process the chat message. If AI outputs <FINAL_CV>, extract it and save.
        Returns (reply_text, generated_cv_id).
        """
        if output_format not in {"markdown", "docx"}:
            output_format = "markdown"

        system_prompt = {
            "role": "system",
            "content": (
                "Bạn là một chuyên gia tư vấn tạo CV (Resumé). Nhiệm vụ của bạn là thu thập thông tin từ user: "
                "1. Vị trí ứng tuyển (Job Title). "
                "2. Cấp độ (Level: Fresher, Junior, Middle, Senior, Manager, etc). "
                "3. Mô tả công việc (Job Description / JD). "
                "Nếu user chưa cung cấp đủ các thông tin trên, hãy hỏi lại user một cách thân thiện, tự nhiên. "
                "Nếu user ĐÃ CUNG CẤP ĐỦ thông tin, hãy tiến hành viết CV ngay lập tức. "
                f"Định dạng user yêu cầu: {output_format}. {self._build_format_instruction(output_format)} "
                "QUAN TRỌNG NHẤT: Toàn bộ nội dung CV PHẢI được đặt bên trong thẻ <FINAL_CV> và </FINAL_CV>. "
                "Tuyệt đối không được quên hai thẻ này khi bạn xuất ra CV. Các chữ bên ngoài thẻ này là lời nói với user. "
                "QUY TẮC TUYỆT ĐỐI VỀ HÌNH THỨC CV: KHÔNG BAO GIỜ dùng emoji, icon, biểu tượng cảm xúc (📍🏠📱📧✉️📎🌟⭐💼 v.v.) trong nội dung CV. "
                "CV chuyên nghiệp chỉ dùng văn bản thuần, heading, bullet point chuẩn. Tuyệt đối tối giản, không trang trí."
                + self._build_template_instruction(template_id)
            )
        }
        
        chat_messages = [system_prompt] + messages
        
        ai_reply = await self.ai.chat_interaction(chat_messages)
        
        # Check if <FINAL_CV> is in the response
        match = re.search(r"<FINAL_CV>(.*?)</FINAL_CV>", ai_reply, flags=re.DOTALL | re.IGNORECASE)
        cv_id = None
        
        # Also handle edge case where AI didn't close the tag properly or used markdown wrapper
        if not match:
            # Sometime LLM omits the closing tag if completion cuts off, or just writes the tag.
            # We can also fallback to searching for # if it explicitly says something like "tạo CV thành công"
            pass
            
        if match:
            cv_content = match.group(1).strip()
            # Clean out potential code fences inside the tag
            if cv_content.startswith("```markdown"):
                cv_content = cv_content.replace("```markdown", "", 1)
                if cv_content.endswith("```"):
                    cv_content = cv_content[:-3]
            elif cv_content.startswith("```"):
                cv_content = cv_content.replace("```", "", 1)
                if cv_content.endswith("```"):
                    cv_content = cv_content[:-3]
            cv_content = cv_content.strip()
            
            # Clean the tag from the reply so the user doesn't see it raw if we just render it or save it to history
            clean_reply = re.sub(r"<FINAL_CV>.*?</FINAL_CV>", "\n\n*(Đã tạo CV thành công)*", ai_reply, flags=re.DOTALL | re.IGNORECASE)

            cv_entity = await self._build_generated_cv(
                user_id=user_id,
                messages=messages,
                reply_text=clean_reply.strip(),
                cv_content=cv_content,
                output_format=output_format,
                current_cv=current_cv,
            )
            await self.repo.create(cv_entity)
            cv_id = cv_entity.id
            
            ai_reply = clean_reply
            
        return ai_reply, cv_id

    async def execute_stream(
        self,
        user_id: UUID,
        messages: List[Dict[str, str]],
        output_format: str = "markdown",
        template_id: Optional[str] = None,
        current_cv: Optional[GeneratedCV] = None,
    ):
        import json
        if output_format not in {"markdown", "docx"}:
            output_format = "markdown"

        system_prompt = {
            "role": "system",
            "content": (
                "Bạn là một chuyên gia tư vấn tạo CV (Resumé). Nhiệm vụ của bạn là thu thập thông tin từ user: "
                "1. Vị trí ứng tuyển (Job Title). "
                "2. Cấp độ (Level: Fresher, Junior, Middle, Senior, Manager, etc). "
                "3. Mô tả công việc (Job Description / JD). "
                "Nếu user chưa cung cấp đủ các thông tin trên, hãy hỏi lại user một cách thân thiện tự nhiên, ĐỒNG THỜI có thể đưa ra một bản CV mẫu (template) sơ bộ để họ gợi nhớ thông tin. "
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
                "QUY TẮC TUYỆT ĐỐI VỀ HÌNH THỨC CV: KHÔNG BAO GIỜ dùng emoji, icon, biểu tượng cảm xúc (📍🏠📱📧✉️📎🌟⭐💼 v.v.) trong nội dung CV. "
                "CV chuyên nghiệp chỉ dùng văn bản thuần, heading, bullet point chuẩn. Tuyệt đối tối giản, không trang trí."
                + self._build_template_instruction(template_id)
            )
        }
        
        chat_messages = [system_prompt] + messages
        
        buffer = ""
        in_cv = False
        cv_text = ""
        ai_reply = ""
        
        async def save_cv_entity(cv_raw_text: str, reply_text: str) -> Optional[UUID]:
            cv_content = cv_raw_text.strip()
            if cv_content.startswith("```markdown"):
                cv_content = cv_content.replace("```markdown", "", 1)
                if cv_content.endswith("```"):
                    cv_content = cv_content[:-3]
            elif cv_content.startswith("```"):
                cv_content = cv_content.replace("```", "", 1)
                if cv_content.endswith("```"):
                    cv_content = cv_content[:-3]
            cv_content = cv_content.strip()
            
            clean_reply = (reply_text or "").strip()
            if not clean_reply:
                clean_reply = "*(Đã tạo CV thành công)*"

            cv_entity = await self._build_generated_cv(
                user_id=user_id,
                messages=messages,
                reply_text=clean_reply,
                cv_content=cv_content,
                output_format=output_format,
                current_cv=current_cv,
            )
            await self.repo.create(cv_entity)
            return cv_entity.id

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
                                yield f"event: cv_chunk\ndata: {json.dumps(out)}\n\n"
                            in_cv = False
                            
                            yield f"event: status\ndata: {json.dumps({'state': 'saving_version', 'label': 'Đang lưu phiên bản CV mới...'})}\n\n"
                            c_id = await save_cv_entity(cv_text, ai_reply)
                            yield f"event: cv_id\ndata: {json.dumps(str(c_id))}\n\n"
                            yield f"event: status\ndata: {json.dumps({'state': 'done', 'label': 'Đã tạo xong phiên bản CV mới.'})}\n\n"
                            continue
                        else:
                            if len(buffer) > 20:
                                out = buffer[:-20]
                                buffer = buffer[-20:]
                                cv_text += out
                                yield f"event: cv_chunk\ndata: {json.dumps(out)}\n\n"
                            break
        except Exception as e:
            logger.error("Error in AI stream: %s", str(e), exc_info=True)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
            
        if buffer:
            if not in_cv:
                ai_reply += buffer
                yield f"event: chat_chunk\ndata: {json.dumps(buffer)}\n\n"
            else:
                cv_text += buffer
                yield f"event: cv_chunk\ndata: {json.dumps(buffer)}\n\n"
                # If stream closed abruptly without closing tag, we still save
                yield f"event: status\ndata: {json.dumps({'state': 'saving_version', 'label': 'Đang lưu phiên bản CV mới...'})}\n\n"
                c_id = await save_cv_entity(cv_text, ai_reply)
                yield f"event: cv_id\ndata: {json.dumps(str(c_id))}\n\n"
                yield f"event: status\ndata: {json.dumps({'state': 'done', 'label': 'Đã tạo xong phiên bản CV mới.'})}\n\n"
