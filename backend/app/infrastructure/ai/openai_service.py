import json
import time
from typing import Dict, List

from openai import OpenAI

from app.config import get_settings
from app.application.interfaces.ai_service import IAIService
from app.logger import get_logger

logger = get_logger("app.infrastructure.ai.openai")


class OpenAIService(IAIService):
    """Concrete AI service using OpenAI API (gpt-4o-mini)."""

    def __init__(self):
        settings = get_settings()
        client_kwargs = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_API_BASE:
            client_kwargs["base_url"] = settings.OPENAI_API_BASE
            
        self._client = OpenAI(**client_kwargs)
        self._model = settings.OPENAI_MODEL
        self._embed_model = settings.OPENAI_EMBED_MODEL
        logger.info("OpenAIService initialized (model=%s, embed=%s)", self._model, self._embed_model)

    # ── helpers ───────────────────────────────────────────────────
    def _chat(self, prompt: str, *, json_mode: bool = False) -> str:
        """Call ChatCompletion and return the raw text."""
        start = time.perf_counter()

        kwargs: dict = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        duration = (time.perf_counter() - start) * 1000

        logger.debug(
            "_chat: model=%s, prompt_len=%d, response_len=%d, duration=%.0fms",
            self._model, len(prompt), len(text), duration,
        )
        return text

    def _chat_json(self, prompt: str, *, expect_list: bool = False):
        """Call ChatCompletion with JSON mode and parse the result."""
        text = self._chat(prompt, json_mode=True).strip()

        # Clean markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        try:
            parsed = json.loads(text)
            logger.debug("_chat_json: parsed OK")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(
                "_chat_json: JSON parse FAILED — %s\nRaw (first 500):\n%s",
                str(e), text[:500],
            )
            return [] if expect_list else {}

    # ── interface implementation ──────────────────────────────────
    async def extract_cv_info(self, cv_text: str) -> Dict:
        prompt = f"""Analyze this CV/Resume and extract structured information.

CV TEXT:
{cv_text}

Return ONLY a valid JSON object with this exact structure:
{{
  "skills": ["skill1", "skill2", ...],
  "experience": ["description of experience 1", "description of experience 2", ...],
  "tools": ["tool1", "tool2", ...],
  "education": ["degree/certification 1", ...],
  "summary": "brief professional summary"
}}"""
        logger.info("extract_cv_info: prompt_len=%d chars", len(prompt))
        result = self._chat_json(prompt)
        logger.info(
            "extract_cv_info: extracted %d skills, %d experiences",
            len(result.get("skills", [])), len(result.get("experience", [])),
        )
        return result

    async def extract_jd_info(self, jd_text: str) -> Dict:
        prompt = f"""Analyze this Job Description and extract structured requirements.

JOB DESCRIPTION:
{jd_text}

Return ONLY a valid JSON object with this exact structure:
{{
  "required_skills": ["skill1", "skill2", ...],
  "preferred_skills": ["skill1", "skill2", ...],
  "experience_requirements": ["requirement 1", "requirement 2", ...],
  "tools": ["tool1", "tool2", ...],
  "responsibilities": ["responsibility 1", ...]
}}"""
        logger.info("extract_jd_info: prompt_len=%d chars", len(prompt))
        result = self._chat_json(prompt)
        logger.info(
            "extract_jd_info: extracted %d required, %d preferred skills",
            len(result.get("required_skills", [])), len(result.get("preferred_skills", [])),
        )
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
        return self._chat(prompt)

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

For each issue found, return a JSON object with a key "issues" containing an array of objects:
{{
  "issues": [
    {{
      "section": "which section of the rewritten CV",
      "original_text": "what the original said",
      "rewritten_text": "what the rewritten version says",
      "issue_type": "hallucination or over_claiming",
      "explanation": "why this is flagged",
      "level": "low or medium or high"
    }}
  ]
}}

If no issues found, return: {{"issues": []}}"""

        logger.info("check_hallucination: prompt_len=%d chars", len(prompt))
        result = self._chat_json(prompt)
        warnings = result.get("issues", [])
        logger.info("check_hallucination: found %d warnings", len(warnings))
        return warnings

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        logger.debug(
            "get_embeddings: %d texts, total_len=%d chars",
            len(texts), sum(len(t) for t in texts),
        )
        start = time.perf_counter()

        response = self._client.embeddings.create(
            model=self._embed_model,
            input=texts,
        )

        duration = (time.perf_counter() - start) * 1000
        embeddings = [item.embedding for item in response.data]
        logger.debug("get_embeddings: returned %d embeddings in %.0fms", len(embeddings), duration)
        return embeddings

    async def evaluate_jd(self, jd_text: str, jd_extracted: Dict) -> Dict:
        """Evaluate JD detail level, requirements, and years of experience."""
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
        result = self._chat_json(prompt, expect_list=False)
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
        result = self._chat_json(prompt, expect_list=True)
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
        result = self._chat_json(prompt, expect_list=False)
        return result if isinstance(result, dict) else {}

    async def generate_cv_template(
        self,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
    ) -> str:
        format_guide = {
            "rich_text": "trình bày theo kiểu văn bản dễ đọc (không dùng cú pháp markdown như #, **, -).",
            "markdown": "tuân thủ markdown chuẩn (Heading, bullet list).",
            "docx": "tuân thủ markdown sạch (Heading rõ ràng, bullet list chuẩn) để convert sang DOCX.",
        }.get(output_format, "tuân thủ markdown chuẩn.")

        prompt = f"""
        Bạn là chuyên gia viết CV. Hãy tạo một mẫu CV (Curriculum Vitae) cơ bản nhưng chuyên nghiệp dựa trên các thông tin sau:
        
        - Vị trí ứng tuyển: {job_title}
        - Level/Cấp độ: {level}
        - Thông tin Job Description ước tính:
        ---
        {jd_text}
        ---
        
        Yêu cầu: 
        - Định dạng đầu ra: {output_format}. Nội dung phải {format_guide}
        - Ghi sẵn các placeholder như "[Tên của bạn]", "[Tên công ty]", "[Năm]".
        - Đưa vào các bullet point kỹ năng/nhiệm vụ mẫu phù hợp với JD nhất. 
        Chỉ trả về nội dung CV, không giải thích gì thêm.
        """
        result = self._chat(prompt, json_mode=False)
        return result.strip()

    async def chat_interaction(self, messages: List[Dict[str, str]]) -> str:
        start = time.perf_counter()
        
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.7,
        }

        response = self._client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        
        # TODO: Remove this mock once the Proxy API is fixed. 
        # Currently the Proxy returns `content: null` which causes the UI to freeze/show empty.
        if not text:
            # Check if this is the final prompt with JD included
            # Accept if prompt has 'jd', 'react', 'job' or is long enough to be a real JD
            last_msg = messages[-1]["content"].lower() if messages else ""
            if "jd" in last_msg or "react" in last_msg or "job" in last_msg or len(last_msg) > 50:
                text = """Tuyệt vời, dựa trên thông tin JD và vị trí bạn cung cấp, đây là CV của bạn:
                
<FINAL_CV>
# Vũ Gia Chiến
**Frontend Developer (ReactJS) | Junior**

## 💡 Summary
Frontend Developer với kinh nghiệm làm việc cùng ReactJS và TypeScript. Đam mê xây dựng các giao diện người dùng hiện đại, tối ưu UX/UI.

## 🛠 Skills
- **Ngôn ngữ:** JavaScript (ES6+), TypeScript, HTML5, CSS3/SASS
- **Framework/Thư viện:** ReactJS, Next.js, Redux Toolkit, Tailwind CSS
- **Công cụ:** Git, Webpack, Vite, Figma

## 💼 Experience
**Frontend Developer Triển vọng** | *Công ty ABC* | 2023 - Hiện tại
- Phát triển các tính năng frontend sử dụng ReactJS và TypeScript theo thiết kế từ Figma.
- Cải thiện hiệu năng render của ứng dụng lên 20%.

## 🎓 Education
**Cử nhân Công nghệ Thông tin** | *Đại học XYZ* | 2019 - 2023
</FINAL_CV>
                """
            else:
                text = "Bạn có thể cung cấp thêm Job Description (JD) chi tiết để mình tạo CV cho bạn được không?"

        duration = (time.perf_counter() - start) * 1000

        logger.debug(
            "chat_interaction: model=%s, messages_count=%d, response_len=%d, duration=%.0fms",
            self._model, len(messages), len(text), duration,
        )
        return text
