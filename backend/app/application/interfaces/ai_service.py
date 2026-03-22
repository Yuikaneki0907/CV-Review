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
