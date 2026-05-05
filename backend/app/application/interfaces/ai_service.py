from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IAIService(ABC):
    """Port for AI operations (Gemini / OpenAI / OAuth-compatible)."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        *,
        expect_list: bool = False,
    ) -> Any:
        """Generic JSON-mode generation used by Phase 0 shared services.

        Returns a parsed ``dict`` (or ``list`` when ``expect_list=True``).
        On parse failure providers return ``{}`` / ``[]`` rather than
        raising — callers detect that as an extraction failure and fall
        back to ``Schema.empty(reason=...)``.
        """
        ...

    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """Generic plaintext/markdown generation.

        Used by Phase 3's reviser (and any other service that needs raw
        text output). Returns the trimmed body. Implementations should
        return an empty string on provider errors rather than raising —
        callers branch on emptiness.
        """
        ...

    @abstractmethod
    async def extract_cv_info(self, cv_text: str) -> Dict:
        """Extract structured info from CV text.

        Returns dict with keys: skills, experience, tools, education, summary
        """
        ...

    @abstractmethod
    async def extract_jd_info(self, jd_text: str) -> Dict:
        """Extract structured requirements from JD text.

        Returns dict with keys: required_skills, preferred_skills,
        experience_requirements, tools, responsibilities
        """
        ...

    @abstractmethod
    async def classify_document(self, document_text: str, filename: str | None = None) -> Dict:
        """Classify an uploaded document as CV, job description, or other."""
        ...

    @abstractmethod
    async def rewrite_cv(self, cv_text: str, jd_text: str, cv_extracted: Dict, jd_extracted: Dict) -> str:
        """Rewrite CV to better match JD while preserving truthful content."""
        ...

    @abstractmethod
    async def check_hallucination(
        self, original_cv: str, rewritten_cv: str, cv_extracted: Dict
    ) -> List[Dict]:
        """Compare rewritten CV against original to detect hallucinations.

        Returns list of warning dicts with keys:
        section, original_text, rewritten_text, issue_type, explanation, level
        """
        ...

    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embedding vectors for a list of texts."""
        ...

    @abstractmethod
    async def evaluate_jd(self, jd_text: str, jd_extracted: Dict) -> Dict:
        """Evaluate JD detail level, requirements, and years of experience.
        
        Returns dict with keys: level, years_of_experience, difficulty, missing_info, summary
        """
        ...

    @abstractmethod
    async def suggest_interview_questions(self, cv_extracted: Dict, jd_extracted: Dict) -> List[Dict]:
        """Suggest interview questions based on the gap between CV and JD.
        
        Returns list of dicts with keys: question, purpose, suggested_answer_strategy, category
        """
        ...

    @abstractmethod
    async def negotiate_salary(self, cv_extracted: Dict, jd_extracted: Dict) -> Dict:
        """Analyze expected salary and provide negotiation strategies based on CV/JD fit.
        
        Returns dict with keys: expected_salary_range, negotiation_strategy, cv_strengths, cv_weaknesses
        """
        ...

    @abstractmethod
    async def generate_cv_template(
        self,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
        user_profile: Dict | None = None,
    ) -> str:
        """Generate a basic Markdown CV template for a given job.

        ``user_profile`` is the optional candidate-facts payload (Phase 2
        fallback). When supplied with at least one of ``full_name`` /
        ``email`` / ``phone_number``, the prompt biases the generator
        toward inserting those values instead of placeholders.

        Returns a Markdown string representing the CV template.
        """
        ...

    @abstractmethod
    async def chat_interaction(self, messages: List[Dict[str, str]]) -> str:
        """Interact conversationally using a list of messages.
        
        Returns the AI's response text.
        """
        ...

    @abstractmethod
    async def chat_interaction_stream(self, messages: List[Dict[str, str]]):
        """Interact conversationally using a streaming response.
        
        Yields the AI's response text chunks.
        """
        ...

    @abstractmethod
    async def plan_cv_edits(
        self,
        messages: List[Dict[str, str]],
        current_cv: str,
        output_format: str = "markdown",
    ) -> Dict:
        """Return structured edit operations for an existing CV.

        Expected response shape:
        {
          "assistant_reply": "...",
          "operations": [{...}]
        }
        """
        ...
