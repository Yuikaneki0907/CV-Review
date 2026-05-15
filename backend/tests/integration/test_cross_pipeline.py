"""Cross-pipeline guarantee — Goal 1.

Asserts that any CV emitted by the generate-flow's quality gate,
when subsequently fed through the analyze pipeline, hits both:

* ``verdict == "PASS"`` (overall_score ≥ 70 by canonical schema)
* ``overall_score ≥ 80``  (matches ``quality_gate.DEFAULT_PASS_THRESHOLD``)

The test runs each fixture through BOTH paths with the same FakeIAIService
so non-determinism is eliminated; any divergence is a real pipeline bug
(prompt asymmetry, scoring drift, JD mismatch).

Five fixtures cover representative chat-gen scenarios:

1. ``backend_senior``  — happy path, full keyword coverage, strong bullets.
2. ``data_engineer``   — different domain, must-haves include nice-to-have layer.
3. ``frontend_fresher``— entry-level seniority, projects-heavy.
4. ``ml_intern``       — keyword-poor JD relative to CV (mostly nice-to-have).
5. ``vietnamese_dev``  — Vietnamese action verbs + mixed-language bullets.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID, uuid4

import pytest

from app.application.services.generation import ensure_quality
from app.application.use_cases.analyze_cv import AnalyzeCVUseCase
from app.domain.entities.analysis_result import AnalysisResult
from tests.fixtures.fake_ai import FakeIAIService


def _run(coro):
    return asyncio.run(coro)


# ──────────────────────────────────────────────────────────────────
# Fake repo — minimal in-memory analysis store for AnalyzeCVUseCase.
# ──────────────────────────────────────────────────────────────────
class _FakeAnalysisRepo:
    def __init__(self) -> None:
        self._rows: dict[UUID, AnalysisResult] = {}

    async def create(self, analysis: AnalysisResult) -> AnalysisResult:
        self._rows[analysis.id] = analysis
        return analysis

    async def get_by_id(self, analysis_id: UUID) -> AnalysisResult | None:
        return self._rows.get(analysis_id)

    async def update(self, analysis: AnalysisResult) -> AnalysisResult:
        self._rows[analysis.id] = analysis
        return analysis


# ──────────────────────────────────────────────────────────────────
# Fixture shape — one CV+JD pair the generator's gate should produce
# AND that the analyzer must score ≥ 80.
# ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class CrossPipelineSample:
    """A representative gen-output fed into both gate and analyze."""

    name: str
    jd_text: str
    cv_markdown: str
    jd_payload: dict
    cv_payload: dict
    relevance_score: float = 88.0
    summary_score: float = 85.0


# ──────────────────────────────────────────────────────────────────
# Five samples — content is intentionally what the upgraded
# cv_generation prompt should produce: must-haves saturated, bullets
# with action-verb + metric + length, ≤2 placeholders.
# ──────────────────────────────────────────────────────────────────
def _sample_backend_senior() -> CrossPipelineSample:
    jd = (
        "Senior Backend Engineer. Requirements: 5+ years Python, FastAPI, "
        "Docker, PostgreSQL. Must lead API design and database optimisation. "
        "Nice to have: Redis, Kubernetes."
    )
    cv = """# [Họ và tên]
candidate@example.com

## Mục tiêu nghề nghiệp
Senior Backend Engineer with 6 years building Python and FastAPI services in production, focused on API design, PostgreSQL optimisation, and containerised Docker deployments.

## Kỹ năng
- Python, FastAPI, Docker, PostgreSQL
- Redis, Kubernetes, CI/CD

## Kinh nghiệm
**Acme Inc** — Senior Engineer | 2020 - now
- Built a payments FastAPI service handling 2 million requests per day across three regions on Docker
- Reduced PostgreSQL query p99 latency by 45 percent through index tuning and connection pooling
- Designed Python microservice contracts adopted by 8 internal teams within six months

## Dự án
**Internal Project** — Lead | 2022
- Implemented Redis-backed rate limiter cutting upstream traffic by 60 percent for 12 endpoints
- Migrated 14 services from VM to Kubernetes, reducing deploy time from 30 minutes to 4

## Học vấn
- B.Sc. Computer Science, [Tên trường], 2018
"""
    jd_payload = {
        "job_title": "Senior Backend Engineer",
        "seniority": "senior",
        "must_have_keywords": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "nice_to_have_keywords": ["Redis", "Kubernetes"],
        "tools": ["Docker"],
        "responsibilities": ["API design", "Database optimisation"],
        "years_of_experience": 5,
        "domain": None,
    }
    cv_payload = {
        "summary": (
            "Senior Backend Engineer with 6 years building Python and FastAPI services "
            "in production, focused on API design, PostgreSQL optimisation, and Docker."
        ),
        "skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "Redis", "Kubernetes"],
        "tools": ["Docker"],
        "experience": [
            {
                "role": "Senior Engineer",
                "company": "Acme Inc",
                "period": "2020 - now",
                "bullets": [
                    "Built a payments FastAPI service handling 2 million requests per day across three regions on Docker",
                    "Reduced PostgreSQL query p99 latency by 45 percent through index tuning and connection pooling",
                    "Designed Python microservice contracts adopted by 8 internal teams within six months",
                ],
            },
            {
                "role": "Lead",
                "company": "Internal Project",
                "period": "2022",
                "bullets": [
                    "Implemented Redis-backed rate limiter cutting upstream traffic by 60 percent for 12 endpoints",
                    "Migrated 14 services from VM to Kubernetes, reducing deploy time from 30 minutes to 4",
                ],
            },
        ],
        "education": ["B.Sc. Computer Science, 2018"],
    }
    return CrossPipelineSample(
        name="backend_senior",
        jd_text=jd,
        cv_markdown=cv,
        jd_payload=jd_payload,
        cv_payload=cv_payload,
        relevance_score=90.0,
        summary_score=88.0,
    )


def _sample_data_engineer() -> CrossPipelineSample:
    jd = (
        "Data Engineer (Mid). Required: SQL, Python, Airflow, dbt, BigQuery. "
        "Responsibilities include building ETL pipelines and data quality checks. "
        "Nice to have: Spark."
    )
    cv = """# [Họ và tên]
data.engineer@example.com

## Summary
Mid-level Data Engineer with 4 years building Python ETL pipelines on BigQuery, Airflow, and dbt for analytics platforms processing 5 TB daily.

## Kỹ năng
- SQL, Python, Airflow, dbt, BigQuery, Spark
- Snowflake, Kafka, Terraform

## Kinh nghiệm
**Globex Data** — Data Engineer | 2021 - now
- Built 35 Airflow DAGs orchestrating Python ETL jobs that load 5 TB into BigQuery daily
- Designed dbt models cutting analytics SQL query cost by 38 percent across 14 dashboards
- Implemented Spark batch jobs deduplicating 120 million events per day with 99.9 percent accuracy

## Dự án
**Personal Project** — Owner | 2023
- Developed a Python data quality framework catching 250+ schema drift incidents in production

## Học vấn
- B.Sc. Information Systems, [Tên trường], 2020
"""
    jd_payload = {
        "job_title": "Data Engineer",
        "seniority": "mid",
        "must_have_keywords": ["SQL", "Python", "Airflow", "dbt", "BigQuery"],
        "nice_to_have_keywords": ["Spark"],
        "tools": [],
        "responsibilities": ["ETL pipelines", "Data quality checks"],
        "years_of_experience": 3,
        "domain": None,
    }
    cv_payload = {
        "summary": (
            "Mid-level Data Engineer with 4 years building Python ETL pipelines "
            "on BigQuery, Airflow, and dbt for analytics platforms."
        ),
        "skills": ["SQL", "Python", "Airflow", "dbt", "BigQuery", "Spark", "Snowflake"],
        "tools": [],
        "experience": [
            {
                "role": "Data Engineer",
                "company": "Globex Data",
                "period": "2021 - now",
                "bullets": [
                    "Built 35 Airflow DAGs orchestrating Python ETL jobs that load 5 TB into BigQuery daily",
                    "Designed dbt models cutting analytics SQL query cost by 38 percent across 14 dashboards",
                    "Implemented Spark batch jobs deduplicating 120 million events per day with 99.9 percent accuracy",
                ],
            },
            {
                "role": "Owner",
                "company": "Personal Project",
                "period": "2023",
                "bullets": [
                    "Developed a Python data quality framework catching 250+ schema drift incidents in production",
                ],
            },
        ],
        "education": ["B.Sc. Information Systems, 2020"],
    }
    return CrossPipelineSample(
        name="data_engineer",
        jd_text=jd,
        cv_markdown=cv,
        jd_payload=jd_payload,
        cv_payload=cv_payload,
        relevance_score=86.0,
        summary_score=84.0,
    )


def _sample_frontend_fresher() -> CrossPipelineSample:
    jd = (
        "Frontend Fresher. Required: JavaScript, React, HTML, CSS, Git. "
        "Responsibilities: build UI components and integrate REST APIs. "
        "Nice to have: TypeScript."
    )
    cv = """# [Họ và tên]
fresher.fe@example.com

## Mục tiêu nghề nghiệp
Frontend Fresher targeting React UI roles with hands-on JavaScript, HTML, CSS, and Git workflow gained through 3 production-ready personal projects.

## Kỹ năng
- JavaScript, React, HTML, CSS, Git, TypeScript
- REST API integration, Vite, ESLint

## Kinh nghiệm
**Internship at Company A** — Frontend Intern | 2023 - 2024
- Built 18 reusable React components in JavaScript shipped across 4 product pages serving 50K monthly users
- Integrated 12 REST API endpoints with React Query, reducing average page load by 35 percent
- Refactored CSS modules and HTML semantics, improving Lighthouse score from 62 to 91

## Dự án
**Personal Project** — Solo | 2024
- Developed a TypeScript + React dashboard tracking 200+ metrics, deployed via Git-based CI in 3 days
- Implemented HTML/CSS responsive layouts tested across 7 viewports with zero regressions

## Học vấn
- B.Sc. Computer Science, [Tên trường], 2024
"""
    jd_payload = {
        "job_title": "Frontend Fresher",
        "seniority": "fresher",
        "must_have_keywords": ["JavaScript", "React", "HTML", "CSS", "Git"],
        "nice_to_have_keywords": ["TypeScript"],
        "tools": [],
        "responsibilities": ["Build UI components", "Integrate REST APIs"],
        "years_of_experience": None,
        "domain": None,
    }
    cv_payload = {
        "summary": (
            "Frontend Fresher targeting React UI roles with hands-on JavaScript, HTML, CSS, "
            "and Git workflow gained through production-ready personal projects."
        ),
        "skills": ["JavaScript", "React", "HTML", "CSS", "Git", "TypeScript"],
        "tools": [],
        "experience": [
            {
                "role": "Frontend Intern",
                "company": "Company A",
                "period": "2023 - 2024",
                "bullets": [
                    "Built 18 reusable React components in JavaScript shipped across 4 product pages serving 50K monthly users",
                    "Integrated 12 REST API endpoints with React Query, reducing average page load by 35 percent",
                    "Refactored CSS modules and HTML semantics, improving Lighthouse score from 62 to 91",
                ],
            },
            {
                "role": "Solo",
                "company": "Personal Project",
                "period": "2024",
                "bullets": [
                    "Developed a TypeScript + React dashboard tracking 200+ metrics, deployed via Git-based CI in 3 days",
                    "Implemented HTML/CSS responsive layouts tested across 7 viewports with zero regressions",
                ],
            },
        ],
        "education": ["B.Sc. Computer Science, 2024"],
    }
    return CrossPipelineSample(
        name="frontend_fresher",
        jd_text=jd,
        cv_markdown=cv,
        jd_payload=jd_payload,
        cv_payload=cv_payload,
        relevance_score=82.0,
        summary_score=80.0,
    )


def _sample_ml_intern() -> CrossPipelineSample:
    jd = (
        "Machine Learning Intern. Required: Python, PyTorch, NumPy. "
        "Responsibilities: train models and run experiments. "
        "Nice to have: deep learning, computer vision."
    )
    cv = """# [Họ và tên]
ml.intern@example.com

## Mục tiêu nghề nghiệp
Machine Learning Intern with hands-on Python, PyTorch, and NumPy experience training computer vision and deep learning models on academic datasets.

## Kỹ năng
- Python, PyTorch, NumPy, deep learning, computer vision
- Pandas, scikit-learn, Jupyter

## Kinh nghiệm
**University Lab** — Research Assistant | 2023 - 2024
- Trained PyTorch image classifiers on 120K samples reaching 92 percent top-1 accuracy in Python
- Implemented NumPy data augmentation pipelines speeding experiment iteration by 4x for 6 students
- Developed deep learning baselines benchmarking 5 architectures across 3 computer vision datasets

## Dự án
**Personal Project** — Author | 2024
- Built a PyTorch sequence model in Python achieving 88 percent F1 on a 50K-row text dataset

## Học vấn
- B.Sc. Computer Science, [Tên trường], 2025
"""
    jd_payload = {
        "job_title": "Machine Learning Intern",
        "seniority": "intern",
        "must_have_keywords": ["Python", "PyTorch", "NumPy"],
        "nice_to_have_keywords": ["deep learning", "computer vision"],
        "tools": [],
        "responsibilities": ["Train models", "Run experiments"],
        "years_of_experience": None,
        "domain": None,
    }
    cv_payload = {
        "summary": (
            "Machine Learning Intern with hands-on Python, PyTorch, and NumPy experience "
            "training computer vision and deep learning models."
        ),
        "skills": ["Python", "PyTorch", "NumPy", "deep learning", "computer vision", "pandas"],
        "tools": [],
        "experience": [
            {
                "role": "Research Assistant",
                "company": "University Lab",
                "period": "2023 - 2024",
                "bullets": [
                    "Trained PyTorch image classifiers on 120K samples reaching 92 percent top-1 accuracy in Python",
                    "Implemented NumPy data augmentation pipelines speeding experiment iteration by 4x for 6 students",
                    "Developed deep learning baselines benchmarking 5 architectures across 3 computer vision datasets",
                ],
            },
            {
                "role": "Author",
                "company": "Personal Project",
                "period": "2024",
                "bullets": [
                    "Built a PyTorch sequence model in Python achieving 88 percent F1 on a 50K-row text dataset",
                ],
            },
        ],
        "education": ["B.Sc. Computer Science, 2025"],
    }
    return CrossPipelineSample(
        name="ml_intern",
        jd_text=jd,
        cv_markdown=cv,
        jd_payload=jd_payload,
        cv_payload=cv_payload,
        relevance_score=84.0,
        summary_score=82.0,
    )


def _sample_vietnamese_dev() -> CrossPipelineSample:
    jd = (
        "Mid Backend Developer. Yêu cầu: Java, Spring Boot, MySQL, Docker. "
        "Responsibilities: phát triển và tối ưu hệ thống microservices."
    )
    cv = """# [Họ và tên]
mid.dev@example.com

## Mục tiêu nghề nghiệp
Mid Backend Developer 4 năm kinh nghiệm Java, Spring Boot, MySQL, Docker; tập trung vào phát triển và tối ưu microservices ổn định.

## Kỹ năng
- Java, Spring Boot, MySQL, Docker
- Redis, Kafka, JUnit

## Kinh nghiệm
**Công ty A** — Backend Developer | 2021 - now
- Phát triển 12 microservices Java Spring Boot phục vụ 4 triệu request mỗi ngày trên Docker
- Tối ưu truy vấn MySQL giảm 40 phần trăm thời gian phản hồi cho 25 endpoint quan trọng
- Triển khai pipeline CI/CD Docker giảm thời gian deploy từ 25 phút xuống 6 phút cho 18 services

## Dự án
**Internal Project** — Tech Lead | 2023
- Thiết kế Java module Spring Boot xử lý 800 nghìn message Kafka mỗi giờ với độ trễ 80ms
- Implemented MySQL sharding strategy across 4 nodes, scaling write throughput by 3x for 2 services

## Học vấn
- Cử nhân CNTT, [Tên trường], 2020
"""
    jd_payload = {
        "job_title": "Mid Backend Developer",
        "seniority": "mid",
        "must_have_keywords": ["Java", "Spring Boot", "MySQL", "Docker"],
        "nice_to_have_keywords": [],
        "tools": ["Docker"],
        "responsibilities": ["Phát triển microservices", "Tối ưu hệ thống"],
        "years_of_experience": 3,
        "domain": None,
    }
    cv_payload = {
        "summary": (
            "Mid Backend Developer 4 năm kinh nghiệm Java, Spring Boot, MySQL, Docker; "
            "tập trung vào phát triển và tối ưu microservices."
        ),
        "skills": ["Java", "Spring Boot", "MySQL", "Docker", "Redis", "Kafka"],
        "tools": ["Docker"],
        "experience": [
            {
                "role": "Backend Developer",
                "company": "Công ty A",
                "period": "2021 - now",
                "bullets": [
                    "Phát triển 12 microservices Java Spring Boot phục vụ 4 triệu request mỗi ngày trên Docker",
                    "Tối ưu truy vấn MySQL giảm 40 phần trăm thời gian phản hồi cho 25 endpoint quan trọng",
                    "Triển khai pipeline CI/CD Docker giảm thời gian deploy từ 25 phút xuống 6 phút cho 18 services",
                ],
            },
            {
                "role": "Tech Lead",
                "company": "Internal Project",
                "period": "2023",
                "bullets": [
                    "Thiết kế Java module Spring Boot xử lý 800 nghìn message Kafka mỗi giờ với độ trễ 80ms",
                    "Implemented MySQL sharding strategy across 4 nodes, scaling write throughput by 3x for 2 services",
                ],
            },
        ],
        "education": ["Cử nhân CNTT, 2020"],
    }
    return CrossPipelineSample(
        name="vietnamese_dev",
        jd_text=jd,
        cv_markdown=cv,
        jd_payload=jd_payload,
        cv_payload=cv_payload,
        relevance_score=86.0,
        summary_score=84.0,
    )


SAMPLES: list[CrossPipelineSample] = [
    _sample_backend_senior(),
    _sample_data_engineer(),
    _sample_frontend_fresher(),
    _sample_ml_intern(),
    _sample_vietnamese_dev(),
]


# ──────────────────────────────────────────────────────────────────
# Stub LLM router — keyed off the prompt body so the same fake AI
# can serve both gate and analyze calls deterministically.
# ──────────────────────────────────────────────────────────────────
def _make_factory(sample: CrossPipelineSample) -> Callable[[str], Any]:
    def factory(prompt: str) -> Any:
        lower = prompt.lower()
        if "job description" in lower and "extract structured fields" in lower:
            return sample.jd_payload
        if "cv parser" in lower:
            return sample.cv_payload
        if "candidate experience bullets" in lower:
            return {"score": sample.relevance_score, "reason": "stub relevance"}
        if "candidate summary" in lower:
            return {"score": sample.summary_score, "reason": "stub summary"}
        if "rewrite suggestions" in lower:
            return {"suggestions": []}
        return {}

    return factory


# ──────────────────────────────────────────────────────────────────
# The two-pass cross-pipeline check — the heart of Goal 1.
# ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_cross_pipeline_gen_then_analyze_passes(sample: CrossPipelineSample) -> None:
    """A gen-CV that clears the gate must also clear a fresh re-analyze.

    Both passes use the same FakeIAIService so judge non-determinism is
    not in play — any failure here is a real pipeline / scoring bug.
    """
    fake = FakeIAIService(structured_factory=_make_factory(sample))

    # ── Pass 1: simulate the chat-gen quality gate ────────────────
    gate_result = _run(
        ensure_quality(
            cv_content=sample.cv_markdown,
            jd_text=sample.jd_text,
            ai_service=fake,
            pass_threshold=80.0,
        )
    )
    assert gate_result.passed_gate, (
        f"[{sample.name}] gate failed: initial={gate_result.initial_score:.1f} "
        f"final={gate_result.final_score:.1f} warnings={gate_result.warnings}"
    )
    assert gate_result.final_score >= 80.0, (
        f"[{sample.name}] gate score below threshold: {gate_result.final_score:.1f}"
    )

    # ── Pass 2: a fresh AnalyzeCVUseCase run on the same content ──
    repo = _FakeAnalysisRepo()
    analysis = AnalysisResult(
        user_id=uuid4(),
        cv_filename=f"{sample.name}.md",
        cv_text=gate_result.content,
        jd_text=sample.jd_text,
    )
    _run(repo.create(analysis))

    use_case = AnalyzeCVUseCase(repo, fake)
    _run(use_case.execute(analysis.id))

    persisted = _run(repo.get_by_id(analysis.id))
    assert persisted is not None
    meta = persisted.analysis_meta or {}
    result = meta.get("result") or {}
    overall = result.get("overall_score", 0.0)
    verdict = result.get("verdict", "FAIL")

    assert verdict == "PASS", (
        f"[{sample.name}] re-analyze verdict={verdict} (expected PASS); "
        f"overall_score={overall:.1f}"
    )
    assert overall >= 80.0, (
        f"[{sample.name}] re-analyze overall_score={overall:.1f} below 80 "
        f"(gate had {gate_result.final_score:.1f})"
    )

    # ── Cross-pipeline parity: gate score == re-analyze score ─────
    # The aggregator is deterministic given identical inputs, so any
    # delta indicates a code path that mutates extraction or scoring
    # between gate and analyze.
    assert abs(gate_result.final_score - overall) < 0.5, (
        f"[{sample.name}] gate vs analyze drift: "
        f"gate={gate_result.final_score:.1f} analyze={overall:.1f}"
    )
