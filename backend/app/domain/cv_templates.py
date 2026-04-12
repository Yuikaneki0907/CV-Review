"""
Built-in CV templates.
Each template has: id, name, description, and a markdown skeleton
that the AI will use as a structural guide when generating CV content.
"""

TEMPLATES = {
    "ats_clean": {
        "id": "ats_clean",
        "name": "ATS-Friendly (Clean)",
        "description": "Bố cục tối giản, tương thích hệ thống ATS. Heading rõ ràng, không bảng/cột.",
        "skeleton": """# [HỌ VÀ TÊN]
[Chức danh] | [Email] | [Số điện thoại] | [LinkedIn]

## PROFESSIONAL SUMMARY
[2-3 câu tóm tắt kinh nghiệm, thế mạnh, và giá trị bạn mang lại]

## CORE COMPETENCIES
- [Kỹ năng 1]
- [Kỹ năng 2]
- [Kỹ năng 3]

## PROFESSIONAL EXPERIENCE

**[Company Name]** | [Job Title]
*[City, Country] | [Month, Year] – [Month, Year]*

- [Achievement/responsibility with measurable results]
- [Achievement/responsibility with measurable results]

**[Previous Company]** | [Previous Title]
*[City, Country] | [Month, Year] – [Month, Year]*

- [Achievement/responsibility with measurable results]

## EDUCATION

**[University Name]** | [Degree]
*[City, Country] | [Year]*

## CERTIFICATIONS
- [Certification Name] – [Issuing Organization] ([Year])

## LANGUAGES
- [Language]: [Proficiency level]
""",
    },
    "executive": {
        "id": "executive",
        "name": "Executive / Senior",
        "description": "Dành cho cấp quản lý. Nhấn mạnh thành tựu, chỉ số KPI, năng lực lãnh đạo.",
        "skeleton": """# [HỌ VÀ TÊN]
[Title] | [Email] | [Phone] | [LinkedIn]

## EXECUTIVE SUMMARY
[3-4 câu thể hiện tầm nhìn chiến lược, kết quả định lượng, năng lực lãnh đạo]

## KEY ACHIEVEMENTS
- [Achievement 1 with measurable impact: revenue, team size, cost reduction]
- [Achievement 2 with measurable impact]
- [Achievement 3 with measurable impact]

## CORE COMPETENCIES
[Strategic Planning] | [Team Leadership] | [P&L Management] | [Stakeholder Management]

## PROFESSIONAL EXPERIENCE

**[Company Name]** | [C-Level / Director / VP Title]
*[City, Country] | [Month, Year] – Present*

Strategic Impact:
- [Led initiative resulting in X% improvement]
- [Managed team of X people across Y departments]
- [Delivered $X revenue / savings]

**[Previous Company]** | [Previous Senior Title]
*[City, Country] | [Month, Year] – [Month, Year]*

- [Leadership achievement]
- [Business outcome]

## EDUCATION
**[University]** | [MBA / Advanced Degree]

## BOARD & ADVISORY ROLES
- [Role] at [Organization]
""",
    },
    "tech_engineer": {
        "id": "tech_engineer",
        "name": "Tech / Engineer",
        "description": "Dành cho developer, engineer. Tập trung vào tech stack, projects, open source.",
        "skeleton": """# [HỌ VÀ TÊN]
[Title, e.g. Software Engineer] | [Email] | [Phone] | [GitHub] | [LinkedIn]

## SUMMARY
[2-3 câu: years of experience, chuyên môn chính, thành tựu nổi bật]

## TECHNICAL SKILLS

- Languages: [Python, JavaScript, Go, ...]
- Frameworks: [React, FastAPI, Spring Boot, ...]
- Databases: [PostgreSQL, MongoDB, Redis, ...]
- DevOps: [Docker, Kubernetes, CI/CD, AWS/GCP, ...]
- Tools: [Git, Jira, Figma, ...]

## PROFESSIONAL EXPERIENCE

**[Company Name]** | [Job Title]
*[City, Country] | [Month, Year] – Present*

- [Built/designed/implemented X using Y, resulting in Z]
- [Improved performance by X% through optimization of Y]
- [Led migration from X to Y serving Z users]

**[Previous Company]** | [Previous Title]
*[City, Country] | [Month, Year] – [Month, Year]*

- [Technical achievement with impact]

## PROJECTS
**[Project Name]** – [Brief description]
- Tech: [Stack used]
- Impact: [Metrics / users]

## EDUCATION
**[University]** | [Degree in Computer Science / Engineering]
*[Year]*

## CERTIFICATIONS
- [AWS / GCP / Azure certification]
""",
    },
    "fresh_graduate": {
        "id": "fresh_graduate",
        "name": "Fresh Graduate",
        "description": "Dành cho sinh viên mới ra trường. Nhấn mạnh học vấn, dự án, kỹ năng.",
        "skeleton": """# [HỌ VÀ TÊN]
[Vị trí ứng tuyển] | [Email] | [Số điện thoại] | [LinkedIn/Portfolio]

## OBJECTIVE
[2 câu: mục tiêu nghề nghiệp, điều bạn muốn đóng góp cho công ty]

## EDUCATION
**[University Name]** | [Degree, Major]
*[City] | [Expected Graduation / Graduated: Month Year]*
- GPA: [X.X/4.0]
- Relevant Coursework: [Course 1, Course 2, Course 3]
- Awards: [Dean's List, Scholarship, etc.]

## SKILLS
- [Skill Category 1]: [Skill 1, Skill 2, Skill 3]
- [Skill Category 2]: [Skill 4, Skill 5]
- Languages: [Vietnamese (Native), English (IELTS X.X / TOEIC XXX)]

## PROJECTS

**[Project Name]** | [Course / Personal / Hackathon]
*[Month Year]*
- [What you built, what technology used]
- [Result / impact / demo link]

## INTERNSHIP / PART-TIME EXPERIENCE

**[Company Name]** | [Intern / Part-time Title]
*[City] | [Month Year – Month Year]*
- [What you did, what you learned]

## ACTIVITIES & LEADERSHIP
- [Club/Organization]: [Role] – [Achievement]
- [Volunteer work]: [Description]
""",
    },
}

def get_template(template_id: str) -> dict | None:
    return TEMPLATES.get(template_id)

def list_templates() -> list[dict]:
    return [
        {"id": t["id"], "name": t["name"], "description": t["description"]}
        for t in TEMPLATES.values()
    ]
