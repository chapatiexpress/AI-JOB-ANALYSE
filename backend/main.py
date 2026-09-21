
from __future__ import annotations

import io
import os
import re
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docx import Document
from pypdf import PdfReader

app = FastAPI(title="JobMatch AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PROFILE_FILE = DATA_DIR / "profile.json"

# IMPORTANT:
# This starter does NOT scrape LinkedIn.
# Replace load_jobs() with an authorized job source / ATS feed / permitted API.
SAMPLE_JOBS = [
    {
        "id": "sample-1",
        "source": "Authorized Feed",
        "title": "Senior Java Full Stack Developer",
        "company": "Example Client",
        "location": "Dallas, TX",
        "work_model": "Hybrid",
        "types": ["C2C"],
        "visas": ["H1B", "USC", "H4-EAD"],
        "age_hours": 0.45,
        "required_skills": ["Java", "Spring Boot", "Microservices", "Kafka", "AWS", "Angular"],
        "years_required": 10,
        "url": "https://example.com/job/sample-1"
    },
    {
        "id": "sample-2",
        "source": "Authorized Feed",
        "title": "Java Angular Developer",
        "company": "Example Staffing",
        "location": "Remote, USA",
        "work_model": "Remote",
        "types": ["C2C", "W2"],
        "visas": ["Any"],
        "age_hours": 1.2,
        "required_skills": ["Java", "Spring Boot", "Angular", "REST", "Kafka", "Docker", "Kubernetes"],
        "years_required": 8,
        "url": "https://example.com/job/sample-2"
    },
    {
        "id": "sample-3",
        "source": "Authorized Feed",
        "title": "Neo4j Graph Database SME",
        "company": "Example Vendor",
        "location": "Chicago, IL",
        "work_model": "Hybrid",
        "types": ["C2C"],
        "visas": ["H1B", "USC"],
        "age_hours": 0.8,
        "required_skills": ["Neo4j", "Cypher", "Graph Database", "Java"],
        "years_required": 10,
        "url": "https://example.com/job/sample-3"
    }
]

SKILL_PATTERNS = {
    "Java": r"\bjava\b",
    "Spring Boot": r"\bspring boot\b",
    "Spring Cloud": r"\bspring cloud\b",
    "Microservices": r"\bmicroservices?\b",
    "REST": r"\brest(?:ful)?\b",
    "GraphQL": r"\bgraphql\b",
    "Angular": r"\bangular\b",
    "React": r"\breact(?:js)?\b",
    "TypeScript": r"\btypescript\b|\btype script\b",
    "JavaScript": r"\bjavascript\b",
    "Node.js": r"\bnode\.?js\b",
    "AWS": r"\baws\b|amazon web services",
    "Azure": r"\bazure\b",
    "GCP": r"\bgcp\b|google cloud",
    "Kafka": r"\bkafka\b",
    "Redis": r"\bredis\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\bkubernetes\b|\beks\b",
    "Jenkins": r"\bjenkins\b",
    "Terraform": r"\bterraform\b",
    "Oracle": r"\boracle\b",
    "PostgreSQL": r"\bpostgres(?:ql)?\b",
    "SQL Server": r"\bsql server\b",
    "MongoDB": r"\bmongodb\b",
    "Cassandra": r"\bcassandra\b",
    "DynamoDB": r"\bdynamodb\b",
    "Python": r"\bpython\b",
    "Go": r"\bgolang\b|\bgo language\b",
    "C++": r"\bc\+\+\b",
    "Selenium": r"\bselenium\b",
    "GitHub Actions": r"\bgithub actions\b",
    "OpenShift": r"\bopen\s*shift\b|\bopenshift\b",
    "Apigee": r"\bapigee\b",
    "RAG": r"\brag\b",
    "GenAI": r"\bgen\s*ai\b|\bgenerative ai\b",
    "LLM": r"\bllm\b"
}

def extract_text(filename: str, raw: bytes) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    if suffix == ".docx":
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)

    raise ValueError("Only PDF and DOCX files are supported.")

def build_profile(text: str) -> Dict[str, Any]:
    years = None
    m = re.search(r"(\d+)\+?\s+years", text, re.I)
    if m:
        years = int(m.group(1))

    name = "Candidate"
    for line in text.splitlines():
        clean = line.strip()
        if clean and len(clean.split()) <= 5 and "resume" not in clean.lower():
            if not re.search(r"phone|email|summary|experience|education", clean, re.I):
                name = clean
                break

    skills = []
    for skill, pattern in SKILL_PATTERNS.items():
        if re.search(pattern, text, re.I):
            skills.append(skill)

    primary_role = "Java Full Stack Developer"
    if "Spring Boot" in skills and "Java" in skills and not ({"React", "Angular"} & set(skills)):
        primary_role = "Java Backend Developer"

    return {
        "name": name,
        "years": years,
        "primary_role": primary_role,
        "skills": skills
    }

def normalize(skill: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", skill.lower())

def score_job(profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    profile_skills = {normalize(s): s for s in profile.get("skills", [])}
    required = job.get("required_skills", [])

    matched = []
    missing = []

    aliases = {
        normalize("REST APIs"): normalize("REST"),
        normalize("REST"): normalize("REST"),
        normalize("ReactJS"): normalize("React"),
        normalize("AngularJS"): normalize("Angular"),
        normalize("K8s"): normalize("Kubernetes")
    }

    for skill in required:
        key = normalize(skill)
        key = aliases.get(key, key)
        if key in profile_skills:
            matched.append(skill)
        else:
            missing.append(skill)

    skill_score = int(round((len(matched) / max(1, len(required))) * 100))

    blocked = False
    warning = False
    reasons = []

    years_required = job.get("years_required")
    years = profile.get("years")
    if years_required and years:
        if years < years_required:
            blocked = True
            reasons.append(f"Experience gap: requires {years_required}+ years")
        elif years > years_required + 5:
            warning = True
            reasons.append("Possible seniority mismatch")

    hard_skills = {"neo4j", "cypher", "snowflake", "c#", ".net", "salesforce", "oraclebrm"}
    hard_missing = [s for s in missing if normalize(s) in {normalize(x) for x in hard_skills}]
    if hard_missing:
        blocked = True
        reasons.append("Hard skill gap: " + ", ".join(hard_missing))

    reason = "Strong technical match" if not reasons else " • ".join(reasons)

    result = dict(job)
    result.update({
        "match": skill_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "blocked": blocked,
        "warning": warning,
        "reason": reason
    })
    return result

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    raw = await file.read()
    text = extract_text(file.filename or "resume", raw)
    profile = build_profile(text)

    PROFILE_FILE.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile

def load_profile() -> Dict[str, Any]:
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))

    # sensible demo profile so the UI works before first upload
    return {
        "name": "Demo Candidate",
        "years": 10,
        "primary_role": "Java Full Stack Developer",
        "skills": [
            "Java", "Spring Boot", "Microservices", "REST", "Angular", "React",
            "AWS", "Kafka", "Docker", "Kubernetes", "Jenkins", "Oracle",
            "PostgreSQL", "MongoDB", "Cassandra", "Redis"
        ]
    }

def load_jobs() -> List[Dict[str, Any]]:
    # Replace this with a permitted/authorized job data connector.
    # Example options:
    # - ATS feeds
    # - employer career-site APIs
    # - approved partner APIs
    # - user's own inbox/job alerts
    return SAMPLE_JOBS

@app.get("/api/jobs")
def get_jobs(
    hours: float = Query(24, ge=0.1, le=168),
    min_match: int = Query(70, ge=0, le=100)
):
    profile = load_profile()
    jobs = [score_job(profile, job) for job in load_jobs()]
    jobs = [
        job for job in jobs
        if job.get("age_hours", 999) <= hours and job.get("match", 0) >= min_match
    ]
    jobs.sort(key=lambda j: (-j["match"], j["age_hours"]))
    return {"jobs": jobs}
