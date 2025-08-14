from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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

# File processing imports
import pdfplumber
import docx
from io import BytesIO

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# In-memory storage for hackathon demo
resume_data = {}
test_sessions = {}
test_results = {}
job_recommendations_data = {}

# Mock Data
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

MCQ_QUESTIONS = [
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
        "question": "What is the time complexity of Shor's algorithm for integer factorization?",
        "options": ["O(n³)", "O(n² log n)", "O(n³ log n)", "O(2ⁿ)"], 
        "correct_answer": 0,
        "category": "algorithms",
        "difficulty": "hard"
    },
    {
        "id": "mcq4",
        "question": "Which quantum gate creates superposition from |0⟩ state?",
        "options": ["Pauli-X", "Pauli-Z", "Hadamard", "CNOT"],
        "correct_answer": 2,
        "category": "quantum_gates",
        "difficulty": "medium"
    },
    {
        "id": "mcq5",
        "question": "What does NISQ stand for in quantum computing?", 
        "options": ["Near-term Intermediate-Scale Quantum", "Nuclear Intermediate Standard Quantum", "Next-gen Intelligent Super Quantum", "Natural Information State Quantum"],
        "correct_answer": 0,
        "category": "quantum_basics", 
        "difficulty": "easy"
    }
]

CODING_QUESTIONS = [
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
    {
        "id": "code3",
        "question": "Create a simple quantum circuit using Qiskit that puts a qubit in superposition.",
        "template": "from qiskit import QuantumCircuit\n\ndef create_superposition():\n    # Your code here\n    pass",
        "test_cases": [
            {"description": "Should create a circuit with Hadamard gate"}
        ],
        "category": "quantum",
        "difficulty": "medium"
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

# Models
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

class TestSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    mcq_questions: List[Dict[str, Any]]
    coding_questions: List[Dict[str, Any]]
    start_time: datetime = Field(default_factory=datetime.utcnow)
    duration_minutes: int = 30
    status: str = "active"  # active, completed, expired

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

# Helper Functions
def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file"""
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(BytesIO(file_content))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing DOCX: {str(e)}")

def parse_tech_stacks(text: str) -> List[str]:
    """Extract technology stacks from resume text"""
    tech_keywords = [
        "Python", "JavaScript", "Java", "C++", "C#", "Go", "Rust", "Ruby", "PHP",
        "React", "Angular", "Vue", "Node.js", "Django", "Flask", "FastAPI", "Spring",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "Linux", "SQL", "MongoDB",
        "Machine Learning", "AI", "Deep Learning", "TensorFlow", "PyTorch", "Pandas", "NumPy",
        "Quantum Computing", "Qiskit", "Cirq", "Linear Algebra", "Statistics", "MATLAB",
        "Blockchain", "DevOps", "CI/CD", "Terraform", "Ansible"
    ]
    
    found_techs = []
    text_upper = text.upper()
    
    for tech in tech_keywords:
        if tech.upper() in text_upper:
            found_techs.append(tech)
    
    return list(set(found_techs))

def parse_education(text: str) -> List[Dict[str, Any]]:
    """Extract education information from resume text"""
    education = []
    
    # Simple pattern matching for common education keywords
    education_keywords = ["Bachelor", "Master", "PhD", "University", "College", "Degree"]
    lines = text.split('\n')
    
    for line in lines:
        line_upper = line.upper()
        if any(keyword.upper() in line_upper for keyword in education_keywords):
            if len(line.strip()) > 10:  # Avoid very short lines
                education.append({
                    "description": line.strip(),
                    "year": extract_year_from_text(line)
                })
    
    return education[:3]  # Limit to 3 entries

def parse_work_experience(text: str) -> List[Dict[str, Any]]:
    """Extract work experience from resume text"""
    experience = []
    
    # Look for common work-related keywords
    work_keywords = ["Engineer", "Developer", "Manager", "Analyst", "Scientist", "Researcher", "Intern"]
    lines = text.split('\n')
    
    for line in lines:
        line_upper = line.upper()
        if any(keyword.upper() in line_upper for keyword in work_keywords):
            if len(line.strip()) > 15:  # Avoid very short lines
                experience.append({
                    "role": line.strip(),
                    "year": extract_year_from_text(line),
                    "duration": random.randint(1, 4)  # Mock duration
                })
    
    return experience[:4]  # Limit to 4 entries

def extract_year_from_text(text: str) -> Optional[int]:
    """Extract year from text"""
    year_pattern = r'\b(19|20)\d{2}\b'
    matches = re.findall(year_pattern, text)
    if matches:
        years = [int(match + text[text.find(match):text.find(match)+4]) for match in matches]
        return max(years) if years else None
    return None

def calculate_strength_score(tech_stacks: List[str], education: List[Dict], experience: List[Dict]) -> float:
    """Calculate resume strength score out of 10"""
    score = 0.0
    
    # Tech stack score (40% weight)
    tech_score = min(len(tech_stacks) * 0.5, 4.0)
    score += tech_score
    
    # Education score (30% weight)
    edu_score = min(len(education) * 1.0, 3.0)
    score += edu_score
    
    # Experience score (30% weight)
    exp_score = min(len(experience) * 0.75, 3.0)
    score += exp_score
    
    return min(score, 10.0)

def calculate_job_match(user_skills: List[str], job_skills: List[str]) -> tuple:
    """Calculate job match percentage and skills analysis"""
    user_skills_set = set([skill.lower() for skill in user_skills])
    job_skills_set = set([skill.lower() for skill in job_skills])
    
    matching_skills = list(user_skills_set.intersection(job_skills_set))
    missing_skills = list(job_skills_set - user_skills_set)
    
    if len(job_skills) == 0:
        match_percentage = 0.0
    else:
        match_percentage = (len(matching_skills) / len(job_skills)) * 100
    
    return match_percentage, matching_skills, missing_skills

def grade_mcq_answers(questions: List[Dict], answers: Dict[str, int]) -> Dict[str, Any]:
    """Grade MCQ answers"""
    correct = 0
    total = len(questions)
    details = []
    
    for question in questions:
        qid = question["id"]
        user_answer = answers.get(qid, -1)
        is_correct = user_answer == question["correct_answer"]
        
        if is_correct:
            correct += 1
            
        details.append({
            "question_id": qid,
            "correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": question["correct_answer"],
            "category": question["category"]
        })
    
    return {
        "score": (correct / total) * 100 if total > 0 else 0,
        "correct": correct,
        "total": total,
        "details": details
    }

def grade_coding_answers(questions: List[Dict], answers: Dict[str, str]) -> Dict[str, Any]:
    """Grade coding answers (simplified for demo)"""
    total = len(questions)
    score = 0
    details = []
    
    for question in questions:
        qid = question["id"]
        user_code = answers.get(qid, "")
        
        # Simple grading based on keywords and length
        code_score = 0
        if len(user_code.strip()) > 20:  # Has substantial code
            code_score += 30
        if "def " in user_code or "function " in user_code:  # Has function definition
            code_score += 30
        if "return" in user_code:  # Has return statement
            code_score += 40
            
        score += code_score
        details.append({
            "question_id": qid,
            "score": code_score,
            "max_score": 100,
            "feedback": "Code structure looks good!" if code_score > 60 else "Could use improvement in structure."
        })
    
    return {
        "score": (score / (total * 100)) * 100 if total > 0 else 0,
        "details": details
    }

# Routes
@api_router.post("/upload_resume")
async def upload_resume(file: UploadFile = File(...), user_id: str = Form(...)):
    """Upload and parse resume"""
    try:
        # Validate file type
        if file.content_type not in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")
        
        # Validate file size (10MB limit)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size must be less than 10MB")
        
        # Extract text based on file type
        if file.content_type == "application/pdf":
            text = extract_text_from_pdf(content)
        else:
            text = extract_text_from_docx(content)
        
        # Parse resume data
        tech_stacks = parse_tech_stacks(text)
        education = parse_education(text)
        work_experience = parse_work_experience(text)
        strength_score = calculate_strength_score(tech_stacks, education, work_experience)
        
        # Store in memory
        analysis = ResumeAnalysis(
            user_id=user_id,
            tech_stacks=tech_stacks,
            education=education,
            work_experience=work_experience,
            strength_score=strength_score
        )
        
        resume_data[user_id] = analysis.dict()
        
        return analysis
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing resume: {str(e)}")

@api_router.get("/get_resume_analysis/{user_id}")
async def get_resume_analysis(user_id: str):
    """Get resume analysis for user"""
    if user_id not in resume_data:
        raise HTTPException(status_code=404, detail="Resume analysis not found")
    
    return resume_data[user_id]

@api_router.get("/get_job_recommendations/{user_id}")
async def get_job_recommendations(user_id: str):
    """Get job recommendations based on user's resume"""
    if user_id not in resume_data:
        raise HTTPException(status_code=404, detail="Resume analysis not found")
    
    user_data = resume_data[user_id]
    user_skills = user_data["tech_stacks"]
    
    recommendations = []
    
    for job in QUANTUM_JOBS:
        match_percentage, matching_skills, missing_skills = calculate_job_match(
            user_skills, job["required_skills"]
        )
        
        if match_percentage > 0:  # Only recommend if there's some match
            recommendations.append(JobRecommendation(
                job_id=job["id"],
                title=job["title"],
                company=job["company"],
                match_percentage=match_percentage,
                matching_skills=matching_skills,
                missing_skills=missing_skills
            ))
    
    # Sort by match percentage and take top 3
    recommendations.sort(key=lambda x: x.match_percentage, reverse=True)
    recommendations = recommendations[:3]
    
    # Store recommendations
    job_recommendations_data[user_id] = [rec.dict() for rec in recommendations]
    
    return {
        "recommendations": recommendations,
        "jobs_detail": QUANTUM_JOBS
    }

@api_router.post("/start_test")
async def start_test(user_id: str = Form(...)):
    """Start a new test session"""
    # Select random questions
    selected_mcq = random.sample(MCQ_QUESTIONS, min(3, len(MCQ_QUESTIONS)))
    selected_coding = random.sample(CODING_QUESTIONS, min(2, len(CODING_QUESTIONS)))
    
    test_session = TestSession(
        user_id=user_id,
        mcq_questions=selected_mcq,
        coding_questions=selected_coding
    )
    
    test_sessions[test_session.id] = test_session.dict()
    
    return {
        "session_id": test_session.id,
        "mcq_questions": selected_mcq,
        "coding_questions": selected_coding,
        "duration_minutes": test_session.duration_minutes
    }

@api_router.post("/submit_test")
async def submit_test(submission: TestSubmission):
    """Submit test answers and get results"""
    if submission.session_id not in test_sessions:
        raise HTTPException(status_code=404, detail="Test session not found")
    
    session = test_sessions[submission.session_id]
    
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Test session is not active")
    
    # Grade answers
    mcq_results = grade_mcq_answers(session["mcq_questions"], submission.mcq_answers)
    coding_results = grade_coding_answers(session["coding_questions"], submission.coding_answers)
    
    # Calculate total score
    total_score = (mcq_results["score"] * 0.6) + (coding_results["score"] * 0.4)
    
    # Store results
    result = {
        "session_id": submission.session_id,
        "user_id": session["user_id"],
        "mcq_results": mcq_results,
        "coding_results": coding_results,
        "total_score": total_score,
        "timestamp": datetime.utcnow().isoformat(),
        "duration_taken": 25  # Mock duration
    }
    
    test_results[submission.session_id] = result
    test_sessions[submission.session_id]["status"] = "completed"
    
    return result

@api_router.get("/get_test_history/{user_id}")
async def get_test_history(user_id: str):
    """Get test history for user"""
    user_results = []
    
    for result in test_results.values():
        if result["user_id"] == user_id:
            user_results.append(result)
    
    # Sort by timestamp
    user_results.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Calculate analytics
    if user_results:
        scores = [r["total_score"] for r in user_results]
        analytics = {
            "average_score": sum(scores) / len(scores),
            "best_score": max(scores),
            "total_tests": len(user_results),
            "improvement_trend": "improving" if len(scores) > 1 and scores[0] > scores[-1] else "stable"
        }
    else:
        analytics = {
            "average_score": 0,
            "best_score": 0,
            "total_tests": 0,
            "improvement_trend": "no_data"
        }
    
    return {
        "test_history": user_results,
        "analytics": analytics
    }

@api_router.post("/upgrade_me")
async def upgrade_me(target_role: str = Form(...), user_id: str = Form(...)):
    """Get upgrade plan for target role"""
    if user_id not in resume_data:
        raise HTTPException(status_code=404, detail="Resume analysis not found")
    
    if target_role not in ROLE_REQUIREMENTS:
        raise HTTPException(status_code=400, detail="Target role not supported")
    
    user_data = resume_data[user_id]
    user_skills = set([skill.lower() for skill in user_data["tech_stacks"]])
    
    role_reqs = ROLE_REQUIREMENTS[target_role]
    required_skills = set([skill.lower() for skill in role_reqs["required_skills"]])
    
    missing_skills = list(required_skills - user_skills)
    
    # Generate learning resources
    resources = []
    for skill in missing_skills:
        resources.append({
            "skill": skill,
            "resource_name": f"Learn {skill.title()}",
            "url": f"https://example.com/learn-{skill.lower().replace(' ', '-')}",
            "type": "online_course",
            "duration": "4-6 weeks"
        })
    
    # Generate project suggestions
    projects = [
        f"Build a quantum algorithm using {skill}" if "quantum" in skill.lower() else f"Create a project demonstrating {skill}"
        for skill in missing_skills[:3]
    ]
    
    estimated_weeks = len(missing_skills) * 4  # 4 weeks per skill
    
    upgrade_plan = UpgradePlan(
        target_role=target_role,
        missing_skills=missing_skills,
        recommended_resources=resources,
        suggested_projects=projects,
        estimated_time_weeks=estimated_weeks
    )
    
    return upgrade_plan

@api_router.get("/profile_overview/{user_id}")
async def get_profile_overview(user_id: str):
    """Get complete profile overview"""
    overview = {}
    
    # Resume data
    if user_id in resume_data:
        overview["resume"] = resume_data[user_id]
    else:
        overview["resume"] = None
    
    # Job recommendations count
    if user_id in job_recommendations_data:
        overview["available_jobs"] = len(job_recommendations_data[user_id])
    else:
        overview["available_jobs"] = 0
    
    # Test performance
    user_test_results = [r for r in test_results.values() if r["user_id"] == user_id]
    if user_test_results:
        scores = [r["total_score"] for r in user_test_results]
        overview["test_performance"] = {
            "average_score": sum(scores) / len(scores),
            "total_tests": len(user_test_results),
            "last_score": scores[0] if scores else 0
        }
    else:
        overview["test_performance"] = {
            "average_score": 0,
            "total_tests": 0,
            "last_score": 0
        }
    
    return overview

# Include router
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()