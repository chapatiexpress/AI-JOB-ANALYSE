from __future__ import annotations

import io
import os
import re
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

import requests
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
from pypdf import PdfReader

app = FastAPI(title="JD Match AI API", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PROFILE_FILE = DATA_DIR / "profile.json"

SKILL_PATTERNS = {
    "Java": r"\bjava\b",
    "Spring Boot": r"\bspring boot\b",
    "Spring Cloud": r"\bspring cloud\b",
    "Spring Security": r"\bspring security\b",
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
    "OpenShift": r"\bopen\s*shift\b|\bopenshift\b",
    "Apigee": r"\bapigee\b",
    "RAG": r"\brag\b",
    "GenAI": r"\bgen\s*ai\b|\bgenerative ai\b",
    "LLM": r"\bllm\b",
    "Spark": r"\bspark\b"
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
        if clean and len(clean.split()) <= 5 and not re.search(r"phone|email|summary|experience|education|resume", clean, re.I):
            name = clean
            break

    skills = [skill for skill, pattern in SKILL_PATTERNS.items() if re.search(pattern, text, re.I)]
    primary_role = "Java Full Stack Developer" if "Java" in skills else "Software Engineer"
    return {"name": name, "years": years, "primary_role": primary_role, "skills": skills}

def load_profile() -> Dict[str, Any]:
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    return {"name": "Candidate", "years": 0, "primary_role": "Software Engineer", "skills": []}

def detect_types(text: str) -> List[str]:
    vals = []
    if re.search(r"\bC2C\b|corp[- ]?to[- ]?corp|corp\s*2\s*corp", text, re.I): vals.append("C2C")
    if re.search(r"\bW2\b", text, re.I): vals.append("W2")
    if re.search(r"\b1099\b", text, re.I): vals.append("1099")
    return vals

def detect_visas(text: str) -> List[str]:
    vals = []
    for label, pat in [
        ("H1B", r"\bH1B\b|\bH-1B\b"),
        ("USC", r"\bUSC\b|US Citizen"),
        ("H4-EAD", r"\bH4[- ]?EAD\b"),
        ("OPT", r"\bOPT\b"),
        ("GC", r"\bGC\b|Green Card"),
        ("TN", r"\bTN\b"),
    ]:
        if re.search(pat, text, re.I): vals.append(label)
    if re.search(r"any visa", text, re.I): vals.append("Any")
    return vals

def detect_work_model(text: str) -> str:
    if re.search(r"\bremote\b", text, re.I): return "Remote"
    if re.search(r"\bhybrid\b", text, re.I): return "Hybrid"
    if re.search(r"\bonsite\b|on-site", text, re.I): return "Onsite"
    return "Not stated"

def detect_email(text: str) -> str | None:
    m = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    return m.group(0) if m else None

def infer_location(text: str) -> str:
    m = re.search(r"\b(?:Location|Loc)\s*[:\-]\s*([A-Za-z .,/]+(?:,\s*[A-Z]{2})?)", text, re.I)
    return m.group(1).strip()[:80] if m else "Not stated"

def infer_age(date_text: str | None) -> tuple[float, str]:
    if not date_text:
        return 24.0, "Recent / time not indexed"
    t = str(date_text).strip().lower()

    m = re.search(r"(\d+)\s*(?:minute|minutes|min|mins)\b", t)
    if m:
        mins = int(m.group(1))
        return mins / 60.0, f"{mins} min ago"

    m = re.search(r"(\d+)\s*(?:hour|hours|hr|hrs)\b", t)
    if m:
        h = int(m.group(1))
        return float(h), f"{h} hr{'s' if h != 1 else ''} ago"

    m = re.search(r"(\d+)\s*(?:day|days)\b", t)
    if m:
        d = int(m.group(1))
        return float(d * 24), f"{d} day{'s' if d != 1 else ''} ago"

    if "today" in t:
        return 12.0, "Today"
    if "yesterday" in t:
        return 24.0, "Yesterday"
    return 24.0, str(date_text)[:40]

def extract_skills(text: str) -> List[str]:
    return [skill for skill, pattern in SKILL_PATTERNS.items() if re.search(pattern, text, re.I)]

def parse_experience_requirement(text: str) -> tuple[int | None, int | None]:
    """Return (minimum_years, maximum_years) when visible in the public snippet."""
    # Examples: 6-8 years, 10–15 yrs, 10+ years, minimum 8 years.
    m = re.search(r"\b(\d+)\s*[-–]\s*(\d+)\s*(?:years|yrs)\b", text, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = re.search(r"\b(?:minimum|min\.?|at least)\s*(\d+)\+?\s*(?:years|yrs)\b", text, re.I)
    if m:
        return int(m.group(1)), None

    m = re.search(r"\b(\d+)\+\s*(?:years|yrs)\b", text, re.I)
    if m:
        return int(m.group(1)), None

    m = re.search(r"\b(\d+)\s*(?:years|yrs)\s+(?:of\s+)?(?:overall\s+)?experience\b", text, re.I)
    if m:
        return int(m.group(1)), None

    return None, None


def role_relevance(profile: Dict[str, Any], jd_text: str) -> tuple[int, List[str]]:
    """Small role/title adjustment so unrelated roles do not score 100% from shared buzzwords."""
    lower = jd_text.lower()
    title_lower = jd_text.split("\n", 1)[0].lower()
    profile_skills = set(profile.get("skills", []))
    adjustments = 0
    notes: List[str] = []

    if "Java" in profile_skills:
        if re.search(r"\bjava\b", lower):
            adjustments += 4
        elif re.search(r"\b(?:salesforce|\.net|c#|snowflake|neo4j|sap|maximo)\b", lower):
            adjustments -= 18
            notes.append("role stack differs from resume")

    if re.search(r"\b(?:intern|internship|graduate|entry[- ]level|junior)\b", title_lower):
        if (profile.get("years") or 0) >= 7:
            adjustments -= 18
            notes.append("junior/intern role")

    if re.search(r"\b(?:lead|architect|principal)\b", title_lower):
        if (profile.get("years") or 0) < 8:
            adjustments -= 8
            notes.append("lead/architect seniority")

    return adjustments, notes


def score(profile: Dict[str, Any], jd_text: str) -> tuple[int, List[str], List[str], bool, bool, str]:
    profile_skills = set(profile.get("skills", []))
    jd_skills = extract_skills(jd_text)
    if not jd_skills:
        return 0, [], [], False, True, "Not enough JD text in the public search snippet"

    matched = [s for s in jd_skills if s in profile_skills]
    missing = [s for s in jd_skills if s not in profile_skills]

    # Weight the skills most important for Java full-stack/backend roles more heavily.
    weights = {
        "Java": 4.0,
        "Spring Boot": 4.0,
        "Spring Cloud": 2.5,
        "Spring Security": 2.5,
        "Microservices": 3.0,
        "REST": 2.0,
        "Angular": 3.0,
        "React": 3.0,
        "TypeScript": 1.5,
        "JavaScript": 1.5,
        "AWS": 3.0,
        "Azure": 2.5,
        "GCP": 2.5,
        "Kafka": 2.5,
        "Redis": 1.5,
        "Docker": 2.0,
        "Kubernetes": 2.5,
        "Jenkins": 1.5,
        "Terraform": 1.5,
        "Oracle": 1.5,
        "PostgreSQL": 1.5,
        "MongoDB": 1.5,
        "Cassandra": 1.5,
        "Python": 1.0,
        "Go": 1.0,
        "Spark": 1.0,
    }
    total_weight = sum(weights.get(s, 1.0) for s in jd_skills)
    matched_weight = sum(weights.get(s, 1.0) for s in matched)
    coverage = (matched_weight / total_weight) if total_weight else 0.0

    # Begin with weighted technical coverage, not a raw visible-keyword percentage.
    raw = round(coverage * 94)

    relevance_adjustment, relevance_notes = role_relevance(profile, jd_text)
    raw += relevance_adjustment

    # Penalize known specialist stacks that are not represented in this resume profile.
    hard_terms = {
        "neo4j": "Neo4j",
        "cypher": "Cypher",
        "snowflake": "Snowflake",
        "salesforce": "Salesforce",
        "oracle brm": "Oracle BRM",
        ".net": ".NET",
        "c#": "C#",
        "camunda": "Camunda",
        "webmethods": "WebMethods",
        "maximo": "Maximo",
        "sap s/4": "SAP S/4",
    }
    blocked_terms = [
        label for term, label in hard_terms.items()
        if term in jd_text.lower() and label not in profile_skills
    ]
    blocked = bool(blocked_terms)
    warning = False

    # Experience requirements: strict minimums are blockers; narrow ranges also flag overqualification.
    min_years, max_years = parse_experience_requirement(jd_text)
    profile_years = profile.get("years") or 0
    if min_years and profile_years:
        if profile_years < min_years:
            blocked = True
            blocked_terms.append(f"{min_years}+ years required")
        elif max_years and profile_years > max_years + 1:
            warning = True
            raw -= 10
            relevance_notes.append(f"experience range {min_years}-{max_years} years")

    # Location/visa conditions cannot be verified from the resume alone.
    confirm_terms = []
    if re.search(r"\b(?:only locals|locals only|local candidates only|must be local|local only)\b", jd_text, re.I):
        warning = True
        confirm_terms.append("local-only requirement")
    if re.search(r"\b(?:F2F|face[- ]to[- ]face|in[- ]person interview)\b", jd_text, re.I):
        warning = True
        confirm_terms.append("in-person/F2F interview")
    if re.search(r"\b(?:no h1b|no h-1b|usc\s*/\s*gc only|usc and gc only)\b", jd_text, re.I):
        warning = True
        confirm_terms.append("visa restriction")

    # Search snippets are incomplete. Prevent a tiny snippet from appearing as a perfect 100% match.
    visible_skill_count = len(jd_skills)
    if visible_skill_count <= 2:
        evidence_cap = 86
    elif visible_skill_count == 3:
        evidence_cap = 90
    elif visible_skill_count == 4:
        evidence_cap = 94
    elif visible_skill_count == 5:
        evidence_cap = 96
    elif visible_skill_count <= 7:
        evidence_cap = 98
    else:
        evidence_cap = 99

    # Missing a core visible skill should matter materially.
    core_skills = {"Java", "Spring Boot", "Microservices", "Angular", "React", "AWS", "Kafka", "Kubernetes"}
    missing_core = [s for s in missing if s in core_skills]
    if missing_core:
        raw -= min(18, 5 * len(missing_core))

    match_score = max(0, min(evidence_cap, raw))

    if blocked_terms:
        reason = "Hard gap: " + ", ".join(dict.fromkeys(blocked_terms))
    else:
        parts = [f"{len(matched)}/{len(jd_skills)} visible JD skills matched"]
        if missing_core:
            parts.append("missing core: " + ", ".join(missing_core))
        if relevance_notes:
            parts.extend(relevance_notes)
        if confirm_terms:
            parts.append("confirm: " + ", ".join(confirm_terms))
        if visible_skill_count < 5:
            parts.append("score capped because LinkedIn search snippet is limited")
        reason = "; ".join(parts)

    return match_score, matched, missing, blocked, warning, reason

def build_queries(profile: Dict[str, Any]) -> List[str]:
    skills = set(profile.get("skills", []))

    # Keep Serper queries simple. Free Serper accounts can reject
    # complex Google operator patterns with nested quotes / OR groups.
    if "Java" in skills:
        return [
            "site:linkedin.com/posts C2C Java Full Stack hiring",
            "site:linkedin.com/posts C2C Java Spring Boot hiring",
            "site:linkedin.com/posts C2C Java Microservices hiring",
            "site:linkedin.com/posts C2C Java Angular hiring",
            "site:linkedin.com/posts C2C Java React hiring",
            "site:linkedin.com/posts C2C Java AWS Kafka hiring",
            "site:linkedin.com/posts C2C Java Platform Engineer hiring",
            "site:linkedin.com/posts H1B C2C Senior Java hiring",
        ]

    top = list(skills)[:3]
    query = "site:linkedin.com/posts C2C hiring"
    if top:
        query += " " + " ".join(top)
    return [query]

def serper_search(query: str, hours: int) -> List[Dict[str, Any]]:
    key = (os.getenv("SERPER_API_KEY") or "").strip()
    if not key:
        return []

    payload = {
        "q": query,
        "num": 10,
        "gl": "us",
        "hl": "en",
        "tbs": "qdr:h" if hours <= 1 else "qdr:d",
    }

    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json=payload,
            timeout=25,
        )

        # If Serper rejects a time-filtered request, retry once without tbs.
        if resp.status_code == 400:
            print(f"Serper 400 for query {query!r}: {resp.text[:500]}")
            payload.pop("tbs", None)
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                json=payload,
                timeout=25,
            )

        if not resp.ok:
            print(f"Serper error {resp.status_code}: {resp.text[:500]}")
            return []

        data = resp.json()
        return data.get("organic", []) or []

    except requests.RequestException as exc:
        print(f"Serper request failed: {exc}")
        return []

def fetch_linkedin_post_results(profile: Dict[str, Any], hours: int) -> List[Dict[str, Any]]:
    seen = set()
    out = []

    for query in build_queries(profile):
        for item in serper_search(query, hours):
            url = item.get("link", "")
            if "linkedin.com" not in url:
                continue
            if "/posts/" not in url and "/feed/update/" not in url:
                continue
            if url in seen:
                continue
            seen.add(url)

            title = item.get("title") or "LinkedIn recruiter JD"
            snippet = item.get("snippet") or ""
            date_text = item.get("date")
            combined = f"{title}\n{snippet}"
            age_hours, posted_label = infer_age(date_text)
            if age_hours > float(hours):
                continue
            match, matched, missing, blocked, warning, reason = score(profile, combined)

            out.append({
                "id": url,
                "source": "LinkedIn Post",
                "title": title,
                "company": "LinkedIn recruiter post",
                "location": infer_location(combined),
                "work_model": detect_work_model(combined),
                "types": detect_types(combined),
                "visas": detect_visas(combined),
                "age_hours": age_hours,
                "posted_label": posted_label,
                "url": url,
                "snippet": snippet,
                "email": detect_email(combined),
                "match": match,
                "matched_skills": matched,
                "missing_skills": missing,
                "blocked": blocked,
                "warning": warning,
                "reason": reason
            })

    out.sort(key=lambda x: (-x["match"], x["age_hours"]))
    return out

@app.get("/health")
def health():
    return {"ok": True, "version": "2.2.0", "serper_configured": bool((os.getenv("SERPER_API_KEY") or "").strip())}

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    raw = await file.read()
    text = extract_text(file.filename or "resume", raw)
    profile = build_profile(text)
    PROFILE_FILE.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile

@app.get("/api/jds")
def get_jds(
    hours: int = Query(24, ge=1, le=24),
    min_match: int = Query(70, ge=0, le=100)
):
    profile = load_profile()
    if not profile.get("skills"):
        return {"jds": [], "message": "Upload a resume first."}
    if not os.getenv("SERPER_API_KEY"):
        return {"jds": [], "message": "SERPER_API_KEY is not configured on Render."}

    jds = fetch_linkedin_post_results(profile, hours)
    jds = [j for j in jds if j["match"] >= min_match and not j["blocked"]]
    return {"jds": jds}
