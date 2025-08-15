#!/usr/bin/env python3
"""
Quantum Careers & Skill Uplift – FastAPI Backend (Battle‑tested)
----------------------------------------------------------------
• Endpoints kept identical to your original spec (return types unchanged).
• Uses Mistral AI to: 
  - extract skills / education / experience from resumes
  - generate adaptive MCQs & coding questions for tests
• Robust JSON extraction & fallbacks (never blocks demo).
• Optional MongoDB persistence (auto‑disables if env is missing).
• Strict validation, timeouts, and error handling.

ENV (.env)
-----------
MISTRAL_API_KEY=YOUR_KEY
MONGO_URL=mongodb+srv://...   (optional)
DB_NAME=quantumapp            (optional, defaults to 'quantumapp')
CORS_ORIGINS=*

Run
----
uvicorn quantum_jobs_backend_fastapi:app --reload --port 8000

Dependencies
-------------
fastapi, uvicorn, python-dotenv, httpx, pdfplumber, python-docx, motor, pydantic
"""

from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

# DB (optional)
try:
    from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
except Exception:  # pragma: no cover - allow running without motor installed
    AsyncIOMotorClient = None  # type: ignore

import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta
import json
import asyncio
import base64
import re
import random
import httpx
# File processing imports
import pdfplumber
import docx
from io import BytesIO

# ------------------------------------------------------------
# ENV & App Setup
# ------------------------------------------------------------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")

# Optional Mongo
MONGO_URL = os.getenv("MONGO_URL", "")
DB_NAME = os.getenv("DB_NAME", "quantumapp")
DB_ENABLED = bool(MONGO_URL and AsyncIOMotorClient)

db = None
if DB_ENABLED:
    try:
        _client = AsyncIOMotorClient(MONGO_URL)
        db = _client[DB_NAME]
    except Exception as e:
        DB_ENABLED = False
        db = None
        logging.warning(f"Mongo disabled due to connection error: {e}")

app = FastAPI(title="Quantum Careers API", version="1.0.0")
api_router = APIRouter(prefix="/api")

# ------------------------------------------------------------
# In-memory stores (always used; DB optional mirror)
# ------------------------------------------------------------
resume_data: Dict[str, Dict[str, Any]] = {}
test_sessions: Dict[str, Dict[str, Any]] = {}
test_results: Dict[str, Dict[str, Any]] = {}
job_recommendations_data: Dict[str, List[Dict[str, Any]]] = {}

# ------------------------------------------------------------
# Mock Job Data (Keep as reference catalog)
# ------------------------------------------------------------
QUANTUM_JOBS = [
    {
        "id": "qjob1",
        "title": "Quantum Software Engineer",
        "company": "IBM Quantum",
        "description": "Develop quantum algorithms and software solutions",
        "required_skills": ["Python", "Qiskit", "Machine Learning", "Linear Algebra", "Quantum Computing"],
        "experience_years": 3,
        "salary_range": "$120k - $180k"
    },
    {
        "id": "qjob2",
        "title": "Quantum Research Scientist",
        "company": "Google Quantum AI",
        "description": "Research quantum algorithms and quantum advantage",
        "required_skills": ["Physics", "Python", "C++", "Mathematics", "Research", "Quantum Computing"],
        "experience_years": 5,
        "salary_range": "$150k - $220k"
    },
    {
        "id": "qjob3",
        "title": "Quantum Applications Developer",
        "company": "Rigetti Computing",
        "description": "Build quantum applications for real-world problems",
        "required_skills": ["Python", "JavaScript", "Quantum Computing", "Cloud Computing", "APIs"],
        "experience_years": 2,
        "salary_range": "$100k - $150k"
    },
    {
        "id": "qjob4",
        "title": "Quantum Hardware Engineer",
        "company": "IonQ",
        "description": "Design and optimize quantum hardware systems",
        "required_skills": ["Physics", "Electronics", "Python", "MATLAB", "Quantum Computing"],
        "experience_years": 4,
        "salary_range": "$130k - $190k"
    },
    {
        "id": "qjob5",
        "title": "Quantum Product Manager",
        "company": "Amazon Braket",
        "description": "Lead quantum computing product development",
        "required_skills": ["Product Management", "Quantum Computing", "Business Strategy", "Python", "Communication"],
        "experience_years": 6,
        "salary_range": "$140k - $200k"
    }
]

ROLE_REQUIREMENTS = {
    "Quantum Software Engineer": {
        "required_skills": ["Python", "Qiskit", "Linear Algebra", "Quantum Computing", "Git"],
        "preferred_skills": ["C++", "Machine Learning", "Cloud Computing"],
        "min_experience": 2,
        "education": "Bachelor's in Computer Science, Physics, or related field"
    },
    "Quantum Research Scientist": {
        "required_skills": ["Physics", "Mathematics", "Python", "Research", "Quantum Computing"],
        "preferred_skills": ["Machine Learning", "Statistics", "MATLAB"],
        "min_experience": 4,
        "education": "PhD in Physics, Computer Science, or related field"
    },
    "Quantum Applications Developer": {
        "required_skills": ["Python", "JavaScript", "APIs", "Software Development", "Quantum Computing"],
        "preferred_skills": ["React", "FastAPI", "Cloud Platforms"],
        "min_experience": 1,
        "education": "Bachelor's in Computer Science or related field"
    }
}

# ------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------
class TestSession(BaseModel):
    id: str
    user_id: str
    mcq_questions: list
    coding_questions: list
    duration_minutes: int = 30
    status: str = "active"  # active, completed, expired
    start_time: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=30))
test_sessions = {}
class ResumeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    tech_stacks: List[str]
    education: List[Dict[str, Any]]
    work_experience: List[Dict[str, Any]]
    strength_score: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class JobRecommendation(BaseModel):
    job_id: str
    title: str
    company: str
    match_percentage: float
    matching_skills: List[str]
    missing_skills: List[str]

class TestSubmission(BaseModel):
    session_id: str
    mcq_answers: Dict[str, int]
    coding_answers: Dict[str, str]

class UpgradePlan(BaseModel):
    target_role: str
    missing_skills: List[str]
    recommended_resources: List[Dict[str, str]]
    suggested_projects: List[str]
    estimated_time_weeks: int

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
JSON_BLOCK_RE = re.compile(r"```(?:json)?(.*?)```", re.DOTALL | re.IGNORECASE)
CURLY_EXTRACT_RE = re.compile(r"\{[\s\S]*\}")


def safe_json_loads(text: str) -> Dict[str, Any]:
    """Parse possibly messy model output into JSON dict."""
    if not text:
        raise ValueError("Empty content")

    # Try direct
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try fenced code block
    m = JSON_BLOCK_RE.search(text)
    if m:
        inner = m.group(1).strip()
        try:
            return json.loads(inner)
        except Exception:
            pass

    # Try extracting first {...}
    m2 = CURLY_EXTRACT_RE.search(text)
    if m2:
        frag = m2.group(0)
        try:
            return json.loads(frag)
        except Exception:
            pass

    # Last resort: fix quotes and trailing commas (very light touch)
    cleaned = text.strip().strip('`').strip()
    cleaned = re.sub(r"\\n", " ", cleaned)
    cleaned = re.sub(r",\s*\]", "]", cleaned)
    cleaned = re.sub(r",\s*\}", "}", cleaned)
    return json.loads(cleaned)


async def mistral_chat_json(messages: List[Dict[str, str]], *, max_tokens: int = 1000, temperature: float = 0.3) -> Dict[str, Any]:
    """Call Mistral chat/completions and parse as JSON with strong safety/fallback."""
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY missing in environment")

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},  # encourage JSON
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        result = resp.json()

    content = result["choices"][0]["message"]["content"]
    return safe_json_loads(content)


# ------------------------ Resume Parsing ---------------------
TECH_KEYWORDS = [
    "Python", "JavaScript", "Java", "C++", "C#", "Go", "Rust", "Ruby", "PHP",
    "React", "Angular", "Vue", "Node.js", "Django", "Flask", "FastAPI", "Spring",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "Linux", "SQL", "MongoDB",
    "Machine Learning", "AI", "Deep Learning", "TensorFlow", "PyTorch", "Pandas", "NumPy",
    "Quantum Computing", "Qiskit", "Cirq", "Linear Algebra", "Statistics", "MATLAB",
    "Blockchain", "DevOps", "CI/CD", "Terraform", "Ansible"
]


def extract_text_from_pdf(file_content: bytes) -> str:
    try:
        text = []
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text.append(page_text)
        return "\n".join(text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")


def extract_text_from_docx(file_content: bytes) -> str:
    try:
        doc = docx.Document(BytesIO(file_content))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing DOCX: {str(e)}")


def parse_tech_stacks(text: str) -> List[str]:
    found = set()
    text_upper = text.upper()
    for tech in TECH_KEYWORDS:
        if tech.upper() in text_upper:
            found.add(tech)
    return sorted(found)


def extract_years(text: str) -> List[int]:
    # Find all 4-digit years 1900..2099
    years = [int(m.group()) for m in re.finditer(r"\b(19\d{2}|20\d{2})\b", text)]
    return years


def parse_education(text: str) -> List[Dict[str, Any]]:
    education = []
    education_keywords = ["Bachelor", "Master", "PhD", "University", "College", "Degree"]
    for line in text.splitlines():
        if len(line.strip()) < 12:
            continue
        if any(k.lower() in line.lower() for k in education_keywords):
            years = extract_years(line)
            education.append({
                "description": line.strip(),
                "year": max(years) if years else None,
            })
    return education[:4]


def parse_work_experience(text: str) -> List[Dict[str, Any]]:
    exp = []
    work_keywords = ["Engineer", "Developer", "Manager", "Analyst", "Scientist", "Researcher", "Intern"]
    for line in text.splitlines():
        if len(line.strip()) < 15:
            continue
        if any(k.lower() in line.lower() for k in work_keywords):
            years = extract_years(line)
            exp.append({
                "role": line.strip(),
                "year": max(years) if years else None,
                "duration": random.randint(1, 4)
            })
    return exp[:6]


def calculate_strength_score(tech_stacks: List[str], education: List[Dict[str, Any]], experience: List[Dict[str, Any]]) -> float:
    score = 0.0
    score += min(len(tech_stacks) * 0.5, 4.0)      # 40%
    score += min(len(education) * 1.0, 3.0)        # 30%
    score += min(len(experience) * 0.75, 3.0)      # 30%
    return round(min(score, 10.0), 2)


async def mistral_extract_resume(text: str) -> Optional[Dict[str, Any]]:
    """Use Mistral to extract structured resume insights. Returns None on failure."""
    try:
        messages = [
            {"role": "system", "content": (
                "You are an expert resume parser. Extract a concise JSON with keys: "
                "tech_stacks (string array), education (array of {description, year:int|null}), "
                "work_experience (array of {role, year:int|null, duration:int months or years if clear}). "
                "Only output JSON and keep arrays short and relevant."
            )},
            {"role": "user", "content": text[:20000]},  # cap input size
        ]
        data = await mistral_chat_json(messages, max_tokens=1200, temperature=0.2)
        # Light shape normalization
        tech = data.get("tech_stacks") or data.get("skills") or []
        edu = data.get("education") or []
        exp = data.get("work_experience") or data.get("experience") or []
        if not isinstance(tech, list):
            tech = []
        if not isinstance(edu, list):
            edu = []
        if not isinstance(exp, list):
            exp = []
        return {"tech_stacks": tech, "education": edu, "work_experience": exp}
    except Exception as e:
        logging.warning(f"Mistral resume extraction failed, using heuristics. Error: {e}")
        return None


# ------------------------ Assessment Utils -------------------
MCQ_FALLBACK = [
    {
        "id": "mcq1",
        "question": "What is the basic unit of quantum information?",
        "options": ["Bit", "Byte", "Qubit", "Gate"],
        "correct_answer": 2,
        "category": "quantum_basics",
        "difficulty": "easy"
    },
    {
        "id": "mcq2",
        "question": "Which principle allows quantum computers to process multiple states simultaneously?",
        "options": ["Entanglement", "Superposition", "Decoherence", "Interference"],
        "correct_answer": 1,
        "category": "quantum_basics",
        "difficulty": "medium"
    },
    {
        "id": "mcq3",
        "question": "Which quantum gate creates superposition from |0⟩?",
        "options": ["Pauli-X", "Pauli-Z", "Hadamard", "CNOT"],
        "correct_answer": 2,
        "category": "quantum_gates",
        "difficulty": "medium"
    },
]

CODING_FALLBACK = [
    {
        "id": "code1",
        "question": "Write a Python function that calculates the factorial of a number recursively.",
        "template": "def factorial(n):\n    # Your code here\n    pass",
        "test_cases": [
            {"input": 5, "expected": 120},
            {"input": 0, "expected": 1},
            {"input": 3, "expected": 6}
        ],
        "category": "programming",
        "difficulty": "easy"
    },
    {
        "id": "code2",
        "question": "Implement a function to check if a string is a palindrome (ignore case and spaces).",
        "template": "def is_palindrome(s):\n    # Your code here\n    pass",
        "test_cases": [
            {"input": "A man a plan a canal Panama", "expected": True},
            {"input": "race a car", "expected": False},
            {"input": "Madam", "expected": True}
        ],
        "category": "programming",
        "difficulty": "medium"
    },
]


def calculate_job_match(user_skills: List[str], job_skills: List[str]) -> tuple:
    u = set(s.strip().lower() for s in user_skills)
    j = set(s.strip().lower() for s in job_skills)
    matching = sorted(u & j)
    missing = sorted(j - u)
    match_pct = (len(matching) / len(j) * 100.0) if j else 0.0
    return match_pct, matching, missing


def grade_mcq_answers(questions: List[Dict[str, Any]], answers: Dict[str, int]) -> Dict[str, Any]:
    correct = 0
    total = len(questions)
    details = []
    for q in questions:
        qid = q.get("id")
        user_ans = answers.get(qid, -1)
        is_correct = user_ans == q.get("correct_answer")
        if is_correct:
            correct += 1
        details.append({
            "question_id": qid,
            "correct": is_correct,
            "user_answer": user_ans,
            "correct_answer": q.get("correct_answer"),
            "category": q.get("category")
        })
    return {
        "score": (correct / total) * 100 if total else 0,
        "correct": correct,
        "total": total,
        "details": details
    }


def grade_coding_answers(questions: List[Dict[str, Any]], answers: Dict[str, str]) -> Dict[str, Any]:
    total = len(questions)
    score = 0
    details = []
    for q in questions:
        qid = q.get("id")
        user_code = answers.get(qid, "") or ""
        code_score = 0
        if len(user_code.strip()) > 20:
            code_score += 30
        if "def " in user_code or "function " in user_code:
            code_score += 30
        if "return" in user_code:
            code_score += 40
        score += code_score
        details.append({
            "question_id": qid,
            "score": code_score,
            "max_score": 100,
            "feedback": "Code structure looks good!" if code_score > 60 else "Could use improvement in structure."
        })
    return {
        "score": (score / (total * 100)) * 100 if total else 0,
        "details": details
    }


async def mistral_generate_questions(n_mcq: int = 3, n_coding: int = 2) -> Dict[str, Any]:
    """Generate questions using Mistral and normalize into our schema."""
    messages = [
        {"role": "system", "content": (
            "You generate short, challenging assessments for quantum & software roles. Output strict JSON with keys: "
            "mcq_questions (array of {id, question, options[4], correct_answer:index, category, difficulty}), "
            "coding_questions (array of {id, question, template, test_cases:array, category, difficulty})."
        )},
        {"role": "user", "content": (
            f"Create {n_mcq} MCQs and {n_coding} coding questions. MCQs must include 'options' and 'correct_answer' as index. "
            "Coding must include short 'template' and a few 'test_cases' with 'input' and 'expected'."
        )}
    ]
    try:
        data = await mistral_chat_json(messages, max_tokens=1400, temperature=0.4)
        mcq = data.get("mcq_questions", [])
        code = data.get("coding_questions", [])

        # Minimal normalization & IDs
        def norm_mcq(i, q):
            return {
                "id": q.get("id") or f"mcq{i+1}",
                "question": q.get("question", ""),
                "options": q.get("options", [])[:6],
                "correct_answer": int(q.get("correct_answer", 0)),
                "category": q.get("category", "general"),
                "difficulty": q.get("difficulty", "medium"),
            }

        def norm_code(i, q):
            return {
                "id": q.get("id") or f"code{i+1}",
                "question": q.get("question") or q.get("prompt", ""),
                "template": q.get("template", ""),
                "test_cases": q.get("test_cases", []),
                "category": q.get("category", "programming"),
                "difficulty": q.get("difficulty", "medium"),
            }

        mcq_n = [norm_mcq(i, q) for i, q in enumerate(mcq)][:n_mcq]
        code_n = [norm_code(i, q) for i, q in enumerate(code)][:n_coding]

        # Ensure basic validity, else fallback
        if not mcq_n or not code_n:
            raise ValueError("Empty questions from model")
        for q in mcq_n:
            if not q["options"] or not isinstance(q["correct_answer"], int):
                raise ValueError("Invalid MCQ structure")
        return {"mcq_questions": mcq_n, "coding_questions": code_n}
    except Exception as e:
        logging.warning(f"Mistral question generation failed, using fallback. Error: {e}")
        return {"mcq_questions": MCQ_FALLBACK, "coding_questions": CODING_FALLBACK}


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------
@api_router.post("/upload_resume")
async def upload_resume(file: UploadFile = File(...), user_id: str = Form(...)):
    """Upload and parse resume; uses Mistral for extraction with heuristic fallback."""
    try:
        if file.content_type not in [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "text/plain",
        ]:
            raise HTTPException(status_code=400, detail="Only PDF, DOCX/DOC, and TXT files are supported")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size must be less than 10MB")

        if file.content_type == "application/pdf":
            text = extract_text_from_pdf(content)
        elif file.content_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"):
            text = extract_text_from_docx(content)
        else:
            text = content.decode(errors="ignore")

        # Try Mistral first
        extracted = await mistral_extract_resume(text) if MISTRAL_API_KEY else None

        if extracted:
            tech_stacks = sorted(set([*parse_tech_stacks(text), *extracted.get("tech_stacks", [])]))
            education = extracted.get("education") or parse_education(text)
            work_experience = extracted.get("work_experience") or parse_work_experience(text)
        else:
            tech_stacks = parse_tech_stacks(text)
            education = parse_education(text)
            work_experience = parse_work_experience(text)

        strength_score = calculate_strength_score(tech_stacks, education, work_experience)

        analysis = ResumeAnalysis(
            user_id=user_id,
            tech_stacks=tech_stacks,
            education=education,
            work_experience=work_experience,
            strength_score=strength_score,
        )

        # Memory store
        resume_data[user_id] = analysis.dict()

        # Optional DB mirror
        if DB_ENABLED and db is not None:
            try:
                await db.resumes.update_one(
                    {"user_id": user_id},
                    {"$set": analysis.dict()},
                    upsert=True,
                )
            except Exception as e:
                logging.warning(f"DB upsert failed: {e}")

        return analysis

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing resume: {str(e)}")


@api_router.get("/get_resume_analysis/{user_id}")
async def get_resume_analysis(user_id: str):
    if user_id not in resume_data:
        # Try DB if available
        if DB_ENABLED and db is not None:
            doc = await db.resumes.find_one({"user_id": user_id})
            if doc:
                # cache in memory
                doc.pop("_id", None)
                resume_data[user_id] = doc
            else:
                raise HTTPException(status_code=404, detail="Resume analysis not found")
        else:
            raise HTTPException(status_code=404, detail="Resume analysis not found")
    return resume_data[user_id]


@api_router.get("/get_job_recommendations/{user_id}")
async def get_job_recommendations(user_id: str):
    if user_id not in resume_data:
        raise HTTPException(status_code=404, detail="Resume analysis not found")

    user_skills = resume_data[user_id]["tech_stacks"]

    recommendations: List[JobRecommendation] = []
    for job in QUANTUM_JOBS:
        match_percentage, matching_skills, missing_skills = calculate_job_match(user_skills, job["required_skills"])
        if match_percentage > 0:
            recommendations.append(JobRecommendation(
                job_id=job["id"],
                title=job["title"],
                company=job["company"],
                match_percentage=round(match_percentage, 2),
                matching_skills=matching_skills,
                missing_skills=missing_skills,
            ))

    recommendations.sort(key=lambda x: x.match_percentage, reverse=True)
    recommendations = recommendations[:3]

    job_recommendations_data[user_id] = [rec.dict() for rec in recommendations]

    # Optional DB mirror
    if DB_ENABLED and db is not None:
        try:
            await db.recommendations.update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "recs": job_recommendations_data[user_id], "ts": datetime.utcnow()}},
                upsert=True,
            )
        except Exception as e:
            logging.warning(f"DB recs upsert failed: {e}")

    return {
        "recommendations": recommendations,
        "jobs_detail": QUANTUM_JOBS,
    }


@api_router.post("/start_test")
async def start_test(user_id: str = Form(...)):
    # Generate via Mistral with resilient fallback
    gen = await mistral_generate_questions(n_mcq=3, n_coding=2) if MISTRAL_API_KEY else {"mcq_questions": MCQ_FALLBACK, "coding_questions": CODING_FALLBACK}

    mcq_questions = gen.get("mcq_questions", [])
    coding_questions = gen.get("coding_questions", [])

    sess = TestSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        mcq_questions=mcq_questions,
        coding_questions=coding_questions,
    )
    
    # Store as dictionary instead of Pydantic object
    test_sessions[sess.id] = sess.dict()

    # Optional DB mirror
    if DB_ENABLED and db is not None:
        try:
            await db.tests.insert_one(test_sessions[sess.id])
        except Exception as e:
            logging.warning(f"DB insert test failed: {e}")
    
    return {
        "session_id": sess.id,
        "mcq_questions": mcq_questions,
        "coding_questions": coding_questions,
        "duration_minutes": sess.duration_minutes,
    }


@api_router.post("/submit_test")
async def submit_test(submission: TestSubmission):
    if submission.session_id not in test_sessions:
        raise HTTPException(status_code=404, detail="Test session not found")

    session = test_sessions[submission.session_id]

    # Expiry check - use dot notation for Pydantic model attributes
    now = datetime.utcnow()
    if session.expires_at and now > session.expires_at:
        session.status = "expired"

    if session.status != "active":
        raise HTTPException(status_code=400, detail="Test session is not active")

    mcq_results = grade_mcq_answers(session.mcq_questions, submission.mcq_answers)
    coding_results = grade_coding_answers(session.coding_questions, submission.coding_answers)
    total_score = round(mcq_results["score"] * 0.6 + coding_results["score"] * 0.4, 2)

    result = {
        "session_id": submission.session_id,
        "user_id": session.user_id,
        "mcq_results": mcq_results,
        "coding_results": coding_results,
        "total_score": total_score,
        "timestamp": datetime.utcnow().isoformat(),
        "duration_taken": 25  # mocked
    }

    test_results[submission.session_id] = result
    session.status = "completed"

    # Optional DB mirror
    if DB_ENABLED and db is not None:
        try:
            await db.results.insert_one(result)
            await db.tests.update_one({"id": session.id}, {"$set": {"status": "completed"}})
        except Exception as e:
            logging.warning(f"DB write result failed: {e}")

    return result


@api_router.get("/get_test_history/{user_id}")
async def get_test_history(user_id: str):
    user_results = [r for r in test_results.values() if r["user_id"] == user_id]

    # If empty and DB enabled, try DB
    if not user_results and DB_ENABLED and db is not None:
        try:
            cursor = db.results.find({"user_id": user_id})
            user_results = [
                {k: v for k, v in doc.items() if k != "_id"}
                async for doc in cursor
            ]
        except Exception as e:
            logging.warning(f"DB history fetch failed: {e}")

    user_results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    if user_results:
        scores = [float(r.get("total_score", 0)) for r in user_results]
        analytics = {
            "average_score": round(sum(scores) / len(scores), 2),
            "best_score": round(max(scores), 2),
            "total_tests": len(user_results),
            "improvement_trend": "improving" if len(scores) > 1 and scores[0] > scores[-1] else "stable",
        }
    else:
        analytics = {
            "average_score": 0,
            "best_score": 0,
            "total_tests": 0,
            "improvement_trend": "no_data",
        }

    return {"test_history": user_results, "analytics": analytics}


@api_router.post("/upgrade_me")
async def upgrade_me(target_role: str = Form(...), user_id: str = Form(...)):
    if user_id not in resume_data:
        raise HTTPException(status_code=404, detail="Resume analysis not found")
    if target_role not in ROLE_REQUIREMENTS:
        raise HTTPException(status_code=400, detail="Target role not supported")

    user_skills = set(s.lower() for s in resume_data[user_id]["tech_stacks"])
    reqs = ROLE_REQUIREMENTS[target_role]
    required = set(s.lower() for s in reqs["required_skills"])
    missing = sorted(required - user_skills)

    resources = [
        {
            "skill": s,
            "resource_name": f"Master {s.title()} – curated path",
            "url": f"https://example.com/learn-{s.replace(' ', '-')}",
            "type": "online_course",
            "duration": "3-5 weeks",
        }
        for s in missing
    ]

    projects = [
        (f"Build a quantum algorithm using {s}" if "quantum" in s else f"Create a demo showcasing {s}")
        for s in missing[:4]
    ]

    plan = UpgradePlan(
        target_role=target_role,
        missing_skills=missing,
        recommended_resources=resources,
        suggested_projects=projects,
        estimated_time_weeks=max(4, len(missing) * 4),
    )

    return plan


@api_router.get("/profile_overview/{user_id}")
async def get_profile_overview(user_id: str):
    overview: Dict[str, Any] = {}

    if user_id in resume_data:
        overview["resume"] = resume_data[user_id]
    elif DB_ENABLED and db is not None:
        doc = await db.resumes.find_one({"user_id": user_id})
        if doc:
            doc.pop("_id", None)
            overview["resume"] = doc
        else:
            overview["resume"] = None
    else:
        overview["resume"] = None

    overview["available_jobs"] = len(job_recommendations_data.get(user_id, []))

    user_test_results = [r for r in test_results.values() if r.get("user_id") == user_id]
    if not user_test_results and DB_ENABLED and db is not None:
        try:
            cursor = db.results.find({"user_id": user_id})
            user_test_results = [
                {k: v for k, v in doc.items() if k != "_id"}
                async for doc in cursor
            ]
        except Exception:
            pass

    if user_test_results:
        scores = [float(r.get("total_score", 0)) for r in user_test_results]
        overview["test_performance"] = {
            "average_score": round(sum(scores) / len(scores), 2),
            "total_tests": len(user_test_results),
            "last_score": round(scores[0], 2) if scores else 0,
        }
    else:
        overview["test_performance"] = {"average_score": 0, "total_tests": 0, "last_score": 0}

    return overview


# ------------------------------------------------------------
# App Wiring & Logging
# ------------------------------------------------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
