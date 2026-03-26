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
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
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
