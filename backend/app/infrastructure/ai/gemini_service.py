import json
import time
from typing import Dict, List

from google import genai

from app.config import get_settings
from app.application.interfaces.ai_service import IAIService
from app.logger import get_logger

logger = get_logger("app.infrastructure.ai.gemini")


class GeminiService(IAIService):
    """Concrete AI service using Google Gemini API."""

    def __init__(self):
        settings = get_settings()
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._gen_model = settings.GEMINI_GEN_MODEL
        self._embed_model = settings.GEMINI_EMBED_MODEL
        logger.info("GeminiService initialized (gen=%s, embed=%s)", self._gen_model, self._embed_model)

    async def extract_cv_info(self, cv_text: str) -> Dict:
        prompt = f"""Analyze this CV/Resume and extract structured information in JSON format.

CV TEXT:
{cv_text}

Return ONLY a valid JSON object with this exact structure:
{{
  "skills": ["skill1", "skill2", ...],
  "experience": ["description of experience 1", "description of experience 2", ...],
  "tools": ["tool1", "tool2", ...],
  "education": ["degree/certification 1", ...],
  "summary": "brief professional summary"
}}
"""
        logger.info("extract_cv_info: prompt_len=%d chars", len(prompt))
        result = await self._generate_json(prompt)
        logger.info("extract_cv_info: extracted %d skills, %d experiences",
                     len(result.get("skills", [])), len(result.get("experience", [])))
        return result

    async def extract_jd_info(self, jd_text: str) -> Dict:
        prompt = f"""Analyze this Job Description and extract structured requirements in JSON format.

JOB DESCRIPTION:
{jd_text}

Return ONLY a valid JSON object with this exact structure:
{{
  "required_skills": ["skill1", "skill2", ...],
  "preferred_skills": ["skill1", "skill2", ...],
  "experience_requirements": ["requirement 1", "requirement 2", ...],
  "tools": ["tool1", "tool2", ...],
  "responsibilities": ["responsibility 1", ...]
}}
"""
        logger.info("extract_jd_info: prompt_len=%d chars", len(prompt))
        result = await self._generate_json(prompt)
        logger.info("extract_jd_info: extracted %d required, %d preferred skills",
                     len(result.get("required_skills", [])), len(result.get("preferred_skills", [])))
        return result

    async def rewrite_cv(
        self, cv_text: str, jd_text: str, cv_extracted: Dict, jd_extracted: Dict
    ) -> str:
        missing = []
        jd_required = set(s.lower() for s in jd_extracted.get("required_skills", []))
        cv_skills = set(s.lower() for s in cv_extracted.get("skills", []))
        missing = list(jd_required - cv_skills)

        prompt = f"""You are an expert CV rewriter. Rewrite the following CV to better match
the Job Description. Follow these CRITICAL rules:

1. ONLY use information that exists in the original CV
2. DO NOT invent new skills, experiences, or qualifications
3. DO rephrase existing content to emphasize skills relevant to the JD
4. DO reorder sections to highlight matching qualifications first
5. DO use action verbs and quantifiable achievements from the original CV
6. Keep the same overall structure but optimize wording

The candidate is missing these skills from the JD: {missing}
- For missing skills: DO NOT add them. Instead, highlight transferable skills
  from the CV that partially overlap.

ORIGINAL CV:
{cv_text}

JOB DESCRIPTION:
{jd_text}

Return the rewritten CV as plain text, maintaining the original format."""

        logger.info("rewrite_cv: prompt_len=%d, missing_skills=%d", len(prompt), len(missing))
        start = time.perf_counter()

        response = self._client.models.generate_content(
            model=self._gen_model,
            contents=prompt,
        )

        duration = (time.perf_counter() - start) * 1000
        logger.info("rewrite_cv: response_len=%d chars, duration=%.0fms",
                     len(response.text), duration)
        return response.text

    async def check_hallucination(
        self, original_cv: str, rewritten_cv: str, cv_extracted: Dict
    ) -> List[Dict]:
        prompt = f"""You are a Truth-Anchoring Auditor. Compare the REWRITTEN CV against the ORIGINAL CV
and identify any hallucinations or over-claims.

ORIGINAL CV:
{original_cv}

REWRITTEN CV:
{rewritten_cv}

EXTRACTED CV DATA:
{json.dumps(cv_extracted, indent=2)}

For each issue found, return a JSON array of objects:
[
  {{
    "section": "which section of the rewritten CV",
    "original_text": "what the original said",
    "rewritten_text": "what the rewritten version says",
    "issue_type": "hallucination" or "over_claiming",
    "explanation": "why this is flagged",
    "level": "low" or "medium" or "high"
  }}
]

If no issues found, return an empty array: []
Return ONLY valid JSON."""

        logger.info("check_hallucination: prompt_len=%d chars", len(prompt))
        result = await self._generate_json(prompt, expect_list=True)
        logger.info("check_hallucination: found %d warnings", len(result))
        return result

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        logger.debug("get_embeddings: %d texts, total_len=%d chars",
                      len(texts), sum(len(t) for t in texts))
        start = time.perf_counter()

        result = self._client.models.embed_content(
            model=self._embed_model,
            contents=texts,
        )

        duration = (time.perf_counter() - start) * 1000
        logger.debug("get_embeddings: returned %d embeddings in %.0fms",
                      len(result.embeddings), duration)
        return [emb.values for emb in result.embeddings]

    async def _generate_json(self, prompt: str, expect_list: bool = False):
        start = time.perf_counter()

        response = self._client.models.generate_content(
            model=self._gen_model,
            contents=prompt,
        )

        duration = (time.perf_counter() - start) * 1000
        text = response.text.strip()
        logger.debug("_generate_json: raw_len=%d, duration=%.0fms", len(text), duration)

        # Clean markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        try:
            parsed = json.loads(text)
            logger.debug("_generate_json: JSON parsed OK")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(
                "_generate_json: JSON parse FAILED — %s\nRaw response (first 500 chars):\n%s",
                str(e), text[:500],
            )
            return [] if expect_list else {}

    async def evaluate_jd(self, jd_text: str, jd_extracted: Dict) -> Dict:
        prompt = f"""
        Bạn là một chuyên gia tuyển dụng. Hãy đánh giá độ khó và yêu cầu của mô tả công việc (Job Description) sau đây:

        JD Text:
        ---
        {jd_text}
        ---

        Dữ liệu đã trích xuất: {json.dumps(jd_extracted, ensure_ascii=False)}

        Hãy trả về kết quả dưới định dạng JSON bao gồm:
        {{
            "level": "Fresher" | "Junior" | "Middle" | "Senior" | "Manager",
            "years_of_experience": "Ghi rõ số năm kinh nghiệm yêu cầu hoặc 'Không yêu cầu'",
            "difficulty": "Easy" | "Medium" | "Hard",
            "missing_info": ["Danh sách các thông tin quan trọng bị thiếu trong JD, ví dụ: mức lương, địa điểm..."],
            "summary": "Tóm tắt ngắn gọn yêu cầu chính yếu của JD này"
        }}
        Chỉ trả về JSON.
        """
        result = await self._generate_json(prompt)
        return result if isinstance(result, dict) else {}

    async def suggest_interview_questions(self, cv_extracted: Dict, jd_extracted: Dict) -> List[Dict]:
        prompt = f"""
        Bạn là một chuyên gia phỏng vấn nhân sự. Dựa trên thông tin CV của ứng viên và JD của công ty, hãy gợi ý bộ câu hỏi phỏng vấn phù hợp nhất.
        Đặc biệt chú trọng đến những kỹ năng ứng viên còn thiếu so với JD, hoặc những kinh nghiệm ấn tượng trong CV.

        CV Extracted: {json.dumps(cv_extracted, ensure_ascii=False)}
        JD Extracted: {json.dumps(jd_extracted, ensure_ascii=False)}

        Hãy trả về MỘT MẢNG JSON, mỗi phần tử có cấu trúc như sau:
        [{{
            "question": "Câu hỏi phỏng vấn",
            "purpose": "Mục đích của câu hỏi này (kiểm tra kỹ năng gì?)",
            "suggested_answer_strategy": "Gợi ý chiến lược trả lời dành cho ứng viên",
            "category": "Technical" | "Soft Skill" | "Behavioral" | "Experience"
        }}]
        Chỉ trả về danh sách JSON. Đưa ra 3-5 câu hỏi trọng tâm nhất.
        """
        result = await self._generate_json(prompt, expect_list=True)
        return result if isinstance(result, list) else []

    async def negotiate_salary(self, cv_extracted: Dict, jd_extracted: Dict) -> Dict:
        prompt = f"""
        Bạn là chuyên gia tư vấn tuyển dụng và đàm phán lương. Hãy đánh giá khả năng deal lương của ứng viên dựa trên CV và JD.

        CV Extracted: {json.dumps(cv_extracted, ensure_ascii=False)}
        JD Extracted: {json.dumps(jd_extracted, ensure_ascii=False)}

        Hãy trả về kết quả dưới định dạng JSON bao gồm:
        {{
            "expected_salary_range": "Dự đoán khoảng lương hoặc ghi 'Cần thêm thông tin thị trường'",
            "negotiation_strategy": "Chiến lược cụ thể để ứng viên có thể deal được mức lương tốt nhất (VD: nhấn mạnh vào kỹ năng A)",
            "cv_strengths": ["Các điểm mạnh trong CV làm lợi thế đàm phán"],
            "cv_weaknesses": ["Các điểm yếu ứng viên cần chuẩn bị để nhà tuyển dụng không ép lương"]
        }}
        Chỉ trả về định dạng JSON.
        """
        result = await self._generate_json(prompt)
        return result if isinstance(result, dict) else {}

    async def generate_cv_template(
        self,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
    ) -> str:
        format_guide = {
            "markdown": "tuân thủ markdown chuẩn, có heading và bullet list rõ ràng.",
            "docx": "tuân thủ markdown sạch để có thể export DOCX chính xác (heading/bullet rõ ràng).",
        }.get(output_format, "tuân thủ markdown chuẩn.")

        prompt = f"""
        Bạn là chuyên gia viết CV. Hãy tạo một mẫu CV chuyên nghiệp dựa trên:
        - Vị trí ứng tuyển: {job_title}
        - Cấp độ: {level}
        - JD tham chiếu:
        ---
        {jd_text}
        ---

        Yêu cầu:
        - Định dạng đầu ra: {output_format}. Nội dung phải {format_guide}
        - Dùng placeholder như [Họ và tên], [Email], [Tên công ty], [Năm].
        - Bố cục nên có: Thông tin cá nhân, Mục tiêu nghề nghiệp, Kỹ năng, Kinh nghiệm, Dự án, Học vấn.
        - Chỉ trả về nội dung CV, không thêm giải thích.
        """

        response = self._client.models.generate_content(
            model=self._gen_model,
            contents=prompt,
        )
        return (response.text or "").strip()

    async def chat_interaction(self, messages: List[Dict[str, str]]) -> str:
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            prompt_parts.append(f"{role}:\n{content}")
        
        prompt = "\n\n".join(prompt_parts)
        
        start = time.perf_counter()
        response = self._client.models.generate_content(
            model=self._gen_model,
            contents=prompt,
        )
        duration = (time.perf_counter() - start) * 1000
        logger.info("chat_interaction: response_len=%d chars, duration=%.0fms", len(response.text), duration)
        return response.text

    async def chat_interaction_stream(self, messages: List[Dict[str, str]]):
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            prompt_parts.append(f"{role}:\n{content}")
        
        prompt = "\n\n".join(prompt_parts)
        
        logger.info("chat_interaction_stream: streaming response")
        response_stream = self._client.models.generate_content_stream(
            model=self._gen_model,
            contents=prompt,
        )
        for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    async def plan_cv_edits(
        self,
        messages: List[Dict[str, str]],
        current_cv: str,
        output_format: str = "markdown",
    ) -> Dict:
        prompt = f"""
        Bạn là trợ lý chỉnh sửa CV theo yêu cầu hội thoại.
        Nhiệm vụ: KHÔNG viết lại toàn bộ CV. Chỉ trả về các thao tác chỉnh sửa cục bộ nhỏ nhất cần thiết.

        Conversation:
        {json.dumps(messages, ensure_ascii=False, indent=2)}

        Current CV ({output_format}, lưu dưới markdown):
        ---
        {current_cv}
        ---

        Chỉ được dùng các loại operation sau:
        1. replace_section_body: {{"type":"replace_section_body","heading":"SUMMARY","content":"...nội dung mới của section, KHÔNG lặp lại heading"}}
        2. append_to_section: {{"type":"append_to_section","heading":"EXPERIENCE","content":"- bullet mới\\n- bullet mới 2"}}
        3. replace_text: {{"type":"replace_text","target":"đoạn cũ","content":"đoạn mới"}}
        4. insert_after_text: {{"type":"insert_after_text","target":"đoạn mốc","content":"\\n- thêm ngay sau"}}
        5. remove_text: {{"type":"remove_text","target":"đoạn cần xoá"}}

        Quy tắc:
        - Không phát minh dữ kiện mới ngoài hội thoại và CV hiện tại.
        - Nếu yêu cầu chưa đủ rõ hoặc thiếu dữ kiện, KHÔNG tạo operation. Hãy hỏi lại ở assistant_reply.
        - Không trả về full CV.
        - Ưu tiên chỉnh rất cục bộ, giữ nguyên phần không liên quan.

        Trả về JSON duy nhất đúng schema:
        {{
          "assistant_reply": "Tin nhắn ngắn gọn cho user bằng tiếng Việt",
          "operations": [{{...}}]
        }}
        """
        result = await self._generate_json(prompt)
        return result if isinstance(result, dict) else {"assistant_reply": "", "operations": []}
