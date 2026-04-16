from abc import ABC, abstractmethod
from typing import Dict, List


class IAIService(ABC):
    """Port for AI operations (Gemini)."""

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
    ) -> str:
        """Generate a basic Markdown CV template for a given job.
        
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
