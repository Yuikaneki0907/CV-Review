from abc import ABC, abstractmethod


class IFileParser(ABC):
    """Port for file parsing operations."""

    @abstractmethod
    async def parse(self, file_path: str) -> str:
        """Parse a file and return its text content."""
        ...

    @abstractmethod
    def supports(self, filename: str) -> bool:
        """Check if this parser supports the given file type."""
        ...
