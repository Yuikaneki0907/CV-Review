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
