from dataclasses import dataclass


@dataclass
class JobDescription:
    """Job Description domain entity."""

    text: str = ""
    title: str = ""
    company: str = ""
