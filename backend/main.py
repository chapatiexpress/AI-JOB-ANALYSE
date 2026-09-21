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

app = FastAPI(title="JD Match AI API", version="2.0.0")

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
    if re.search(r"\bC2C\b|corp[- ]?to[- ]?corp", text, re.I): vals.append("C2C")
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
        return 24.0, "Recent"
    t = date_text.strip().lower()
    m = re.search(r"(\d+)\s*(minute|min)", t)
    if m: 
        mins = int(m.group(1))
        return mins/60.0, f"{mins} min ago"
    m = re.search(r"(\d+)\s*(hour|hr)", t)
    if m:
        h = int(m.group(1))
        return float(h), f"{h} hr{'s' if h != 1 else ''} ago"
    if "today" in t:
        return 12.0, "Today"
    return 24.0, date_text[:40]

def extract_skills(text: str) -> List[str]:
    return [skill for skill, pattern in SKILL_PATTERNS.items() if re.search(pattern, text, re.I)]

def score(profile: Dict[str, Any], jd_text: str) -> tuple[int, List[str], List[str], bool, bool, str]:
    profile_skills = set(profile.get("skills", []))
    jd_skills = extract_skills(jd_text)
    if not jd_skills:
        return 0, [], [], False, True, "Not enough JD text in the public search snippet"

    matched = [s for s in jd_skills if s in profile_skills]
    missing = [s for s in jd_skills if s not in profile_skills]
    raw = round(len(matched) / len(jd_skills) * 100)

    # Penalize known specialist stacks when the profile does not contain them.
    hard_terms = {
        "neo4j": "Neo4j", "cypher": "Cypher", "snowflake": "Snowflake",
        "salesforce": "Salesforce", "oracle brm": "Oracle BRM",
        ".net": ".NET", "c#": "C#"
    }
    blocked_terms = [label for term, label in hard_terms.items() if term in jd_text.lower() and label not in profile_skills]
    blocked = bool(blocked_terms)
    warning = False

    years_req = None
    m = re.search(r"(\d+)\+?\s*(?:years|yrs)", jd_text, re.I)
    if m: years_req = int(m.group(1))
    if years_req and profile.get("years"):
        if years_req > profile["years"] + 1:
            blocked = True
            blocked_terms.append(f"{years_req}+ years")

    reason = "Preliminary strong match from public LinkedIn post snippet"
    if blocked_terms:
        reason = "Hard gap: " + ", ".join(blocked_terms)

    return raw, matched, missing, blocked, warning, reason

def build_queries(profile: Dict[str, Any]) -> List[str]:
    skills = set(profile.get("skills", []))
    queries = []
    base = 'site:linkedin.com/posts ("C2C" OR "corp to corp")'
    if "Java" in skills:
        queries += [
            f'{base} ("Java Full Stack" OR "Java Fullstack") hiring',
            f'{base} ("Java Spring Boot" OR "Java Microservices") hiring',
            f'{base} ("Java Angular" OR "Java React") hiring',
            f'{base} ("Java AWS" OR "Java Kafka") hiring',
            f'{base} ("Senior Java" OR "Lead Java") hiring'
        ]
    else:
        top = " ".join(list(skills)[:4])
        queries.append(f'{base} "{top}" hiring')
    return queries[:6]

def serper_search(query: str, hours: int) -> List[Dict[str, Any]]:
    """
    Search Google through Serper for public LinkedIn recruiter posts.

    This version is intentionally fault-tolerant:
    - strips accidental whitespace from the API key
    - first tries a freshness-filtered request
    - retries with the smallest valid payload if Serper returns HTTP 400
    - returns an empty result instead of crashing the /api/jds endpoint
    """
    key = (os.getenv("SERPER_API_KEY") or "").strip()
    if not key:
        return []

    headers = {
        "X-API-KEY": key,
        "Content-Type": "application/json",
    }

    # First request: include freshness and US/English targeting.
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
            headers=headers,
            json=payload,
            timeout=25,
        )

        # Some Serper accounts/queries can reject optional parameters with 400.
        # Retry with the smallest supported payload.
        if resp.status_code == 400:
            fallback_payload = {
                "q": query,
                "num": 10,
            }
            resp = requests.post(
                "https://google.serper.dev/search",
                headers=headers,
                json=fallback_payload,
                timeout=25,
            )

        if not resp.ok:
            print(
                "SERPER_ERROR",
                "status=", resp.status_code,
                "body=", resp.text[:500],
                "query=", query[:250],
            )
            return []

        data = resp.json()
        return data.get("organic", [])

    except requests.RequestException as exc:
        print("SERPER_REQUEST_EXCEPTION", repr(exc), "query=", query[:250])
        return []
    except ValueError as exc:
        print("SERPER_JSON_EXCEPTION", repr(exc), "query=", query[:250])
        return []


def fetch_linkedin_post_results(profile: Dict[str, Any], hours: int) -> List[Dict[str, Any]]:
    seen = set()
    out = []

    for query in build_queries(profile):
        try:
            search_results = serper_search(query, hours)
        except Exception as exc:
            print("LINKEDIN_SEARCH_EXCEPTION", repr(exc), "query=", query[:250])
            search_results = []

        for item in search_results:
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
    return {"ok": True, "version": 2}

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

    try:
        jds = fetch_linkedin_post_results(profile, hours)
    except Exception as exc:
        print("JD_FETCH_EXCEPTION", repr(exc))
        return {
            "jds": [],
            "message": "Live JD search failed temporarily. Check Render logs for SERPER_ERROR details."
        }

    jds = [j for j in jds if j["match"] >= min_match and not j["blocked"]]
    return {"jds": jds}
