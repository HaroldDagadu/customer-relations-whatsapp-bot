"""
WhatsApp Bot + Admin Dashboard API
FastAPI server handling WhatsApp webhooks, admin dashboard, and CRUD operations.
"""
from fastapi import FastAPI, Request, HTTPException, Depends, Cookie, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import logging
import asyncio
import hmac
import hashlib
import httpx
import os
import shutil
import secrets
from typing import Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from pydantic import BaseModel

from config import settings
from session_manager import session_manager
from repository import Repository
from database import get_db_connection, verify_password, hash_password
from workers import cleanup_sessions_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(cleanup_sessions_worker())
    yield

app = FastAPI(title="WhatsApp API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
@app.get("/admin")
@app.get("/admin/")
async def serve_admin_root():
    return RedirectResponse(url="/static/index.html")


# ==========================================
# Pydantic Schema Definitions
# ==========================================
class LoginRequest(BaseModel):
    username: str
    password: str

class PackagePayload(BaseModel):
    name: str
    category: str
    description: Optional[str] = ""
    schedule_type: str
    duration_weeks: str
    price: float

class ClientPayload(BaseModel):
    name: str
    region: str
    contact_numbers: Optional[str] = ""
    address: Optional[str] = ""
    google_maps_link: Optional[str] = ""

class FeePayload(BaseModel):
    name: str
    description: Optional[str] = ""
    amount: float
    mandatory: bool
    pass_through: bool

class KnowledgePayload(BaseModel):
    topic: str
    content: str

class ChatMessagePayload(BaseModel):
    message: str

class BroadcastRequest(BaseModel):
    target: str  # "all", "branch", "package", or "package_branch"
    message: str
    location: Optional[str] = None   # branch name when target is "branch" or "package_branch"
    locations: Optional[list[str]] = None  # multiple branch names
    package_id: Optional[int] = None  # package ID when target is "package" or "package_branch"
    package_ids: Optional[list[int]] = None  # multiple package IDs

class AdminPayload(BaseModel):
    username: str
    role: str
    location: Optional[str] = None
    password: Optional[str] = None

class SendToRegistrantsPayload(BaseModel):
    registration_ids: list[int]
    message: str

class UpdateRegistrationPayload(BaseModel):
    package_id: int
    status: str
    name: Optional[str] = ""
    dob: Optional[str] = ""
    ghana_card: Optional[str] = ""
    place_of_birth: Optional[str] = ""
    witness_name: Optional[str] = ""
    witness_phone: Optional[str] = ""
    marital_status: Optional[str] = ""
    location: Optional[str] = ""

class UpdateTicketPayload(BaseModel):
    subject: str
    description: Optional[str] = ""
    status: str
    location: Optional[str] = ""

class LeadStatusPayload(BaseModel):
    status: str


# ==========================================
# Auth Dependencies
# ==========================================
async def get_current_admin(admin_token: str = Cookie(None)):
    if not admin_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    admin = Repository.get_admin_by_session_token(admin_token)
    if not admin:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return admin

def require_role(allowed_roles: list):
    async def role_dependency(admin=Depends(get_current_admin)):
        if admin["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        return admin
    return role_dependency


# ==========================================
# Auth API Routes
# ==========================================
class ResetPasswordRequest(BaseModel):
    temp_token: str
    new_password: str
@app.post("/api/admin/auth/login")
async def admin_login(payload: LoginRequest):
    admin = Repository.get_admin_by_username(payload.username)
    if not admin or not verify_password(payload.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = secrets.token_hex(32)
    expires_at = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    Repository.create_admin_session(admin["id"], token, expires_at)
    
    if admin.get("must_reset_password") == 1:
        return {"require_password_reset": True, "temp_token": token, "username": admin["username"]}

    response = JSONResponse(content={
        "id": admin["id"], "username": admin["username"],
        "role": admin["role"], "location": admin["location"]
    })
    response.set_cookie(key="admin_token", value=token, httponly=True, samesite="lax", max_age=28800, secure=False)
    return response

@app.post("/api/admin/auth/reset-password")
async def admin_reset_password(payload: ResetPasswordRequest):
    admin = Repository.get_admin_by_session_token(payload.temp_token)
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid or expired reset token")
    
    if admin.get("must_reset_password") != 1:
        raise HTTPException(status_code=400, detail="Password reset not required")
        
    hashed = hash_password(payload.new_password)
    Repository.update_admin_password(admin["id"], hashed)
    
    response = JSONResponse(content={
        "id": admin["id"], "username": admin["username"],
        "role": admin["role"], "location": admin["location"]
    })
    response.set_cookie(key="admin_token", value=payload.temp_token, httponly=True, samesite="lax", max_age=28800, secure=False)
    return response

@app.post("/api/admin/auth/logout")
async def admin_logout(admin_token: str = Cookie(None)):
    if admin_token:
        Repository.delete_admin_session(admin_token)
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie("admin_token")
    return response

@app.get("/api/admin/auth/me")
async def admin_me(admin=Depends(get_current_admin)):
    return {"id": admin["id"], "username": admin["username"], "role": admin["role"], "location": admin["location"]}


# ==========================================
# Overview & Metrics
# ==========================================
@app.get("/api/admin/overview")
async def get_overview(location: Optional[str] = None, admin=Depends(get_current_admin)):
    if admin["role"] == "branch_admin":
        location = admin["location"]
    return Repository.get_overview_metrics(location)

@app.get("/api/admin/overview/trends")
async def get_trends(days: int = 7, admin=Depends(get_current_admin)):
    return {
        "messages": Repository.get_message_trend(days),
        "registrations": Repository.get_registration_trend(days),
    }

@app.get("/api/admin/overview/message-analytics")
async def get_message_analytics(start_date: str, end_date: str, direction: str = 'both', admin=Depends(get_current_admin)):
    try:
        return Repository.get_message_analytics(start_date, end_date, direction)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/overview/registration-analytics")
async def get_registration_analytics(start_date: str, end_date: str, status: str = 'all', admin=Depends(get_current_admin)):
    try:
        return Repository.get_registration_analytics(start_date, end_date, status)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/overview/ticket-analytics")
async def get_ticket_analytics(start_date: str, end_date: str, status: str = 'all', admin=Depends(get_current_admin)):
    try:
        return Repository.get_ticket_analytics(start_date, end_date, status)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




# ==========================================
# AI Insights
# ==========================================
@app.get("/api/admin/insights/generate")
async def generate_insights(admin=Depends(get_current_admin)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM messages WHERE role = 'user' ORDER BY created_at DESC LIMIT 200")
        rows = cursor.fetchall()
    if not rows:
        return "Not enough message logs to compile insights."
    messages_digest = "\n".join([f"- {row['content']}" for row in rows])
    try:
        from agent import get_chat_llm
        llm = get_chat_llm(temperature=0.7)
        prompt = f"""You are a senior marketing strategist for the business.
Below is a digest of the last 200 user messages from our WhatsApp Bot.
Analyze and compile a plain-text marketing insights report.

Include:
1. Popular Topics: What users ask about most (Pricing, timings, registration, complaints?)
2. Intent Ratios: Approximate breakdown of user intents (Buying vs Browsing vs Support)
3. Recommendations: Actionable steps for management to improve conversions.

Keep it professional, structured, and concise.

User Messages Digest:
{messages_digest}"""
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
        from agent import extract_text_response
        return extract_text_response(response.content) or "Failed to compile AI insights."
    except Exception as e:
        logger.error(f"Failed to generate insights: {e}")
        return f"Error connecting to AI Provider: {e}"


@app.get("/api/admin/insights/chart-data")
async def get_chart_data(admin=Depends(get_current_admin)):
    """Return real intent and sentiment breakdowns from the messages table."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM messages WHERE role = 'user' ORDER BY created_at DESC LIMIT 500")
        rows = cursor.fetchall()

    if not rows:
        return {"intent": {"labels": [], "data": []}, "sentiment": {"labels": [], "data": []}}

    # --- intent classification (keyword-based) ---
    intent_keywords = {
        "Pricing & Fees":        ["price", "cost", "fee", "ghs", "how much", "amount", "cedis", "rate", "pricing"],
        "Registration":          ["register", "sign up", "enroll", "registration", "join", "book"],
        "Branch & Location":     ["branch", "location", "where", "address", "direction", "closest", "near", "map", "central", "east", "west", "north"],
        "Fees & License":        ["fee", "license", "documentation", "printing", "card", "permit"],
        "Course / Schedule":     ["course", "schedule", "week", "duration", "express", "refresher", "regular", "student", "nss"],
        "Support / Complaint":   ["complaint", "ticket", "issue", "problem", "help", "support", "refund", "cancel"],
    }
    intent_counts = {k: 0 for k in intent_keywords}
    for row in rows:
        text = (row["content"] or "").lower()
        for intent, keywords in intent_keywords.items():
            if any(kw in text for kw in keywords):
                intent_counts[intent] += 1
                break  # assign to first matching category

    # Remove zero-count categories and sort by count desc
    sorted_intents = sorted(
        [(k, v) for k, v in intent_counts.items() if v > 0],
        key=lambda x: x[1], reverse=True
    )
    intent_labels = [x[0] for x in sorted_intents]
    intent_data = [x[1] for x in sorted_intents]

    # --- sentiment classification (keyword-based) ---
    positive_words = ["thank", "great", "good", "excellent", "perfect", "wonderful", "happy",
                      "thanks", "awesome", "nice", "love", "best", "helpful", "appreciate",
                      "ok", "yes", "fine", "cool", "glad", "quick", "fast", "easy"]
    frustrated_words = ["bad", "wrong", "complaint", "issue", "problem", "refund", "cancel",
                        "angry", "upset", "disappointed", "terrible", "poor", "slow", "delay",
                        "not working", "fix", "error", "failed"]
    hesitant_words = ["maybe", "not sure", "thinking", "consider", "later", "might", "perhaps",
                      "probably", "could", "would", "should", "check", "confirm"]

    pos = neu = hes = frus = 0
    for row in rows:
        text = (row["content"] or "").lower()
        if any(w in text for w in frustrated_words):
            frus += 1
        elif any(w in text for w in hesitant_words):
            hes += 1
        elif any(w in text for w in positive_words):
            pos += 1
        else:
            neu += 1

    total = len(rows)
    sentiment_pct = {
        "Positive":    round(pos * 100 / total, 1) if total else 0,
        "Neutral":     round(neu * 100 / total, 1) if total else 0,
        "Hesitant":    round(hes * 100 / total, 1) if total else 0,
        "Frustrated":  round(frus * 100 / total, 1) if total else 0,
    }

    chart_colors = {
        "Pricing & Fees": "#c62828",
        "Registration": "#1a237e",
        "Branch & Location": "#f59e0b",
        "Fees & License": "#10b981",
        "Course / Schedule": "#8b5cf6",
        "Support / Complaint": "#a855f7",
    }
    sentiment_colors = {"Positive": "#10b981", "Neutral": "#1a237e", "Hesitant": "#f59e0b", "Frustrated": "#c62828"}

    return {
        "intent": {
            "labels": intent_labels,
            "data": intent_data,
            "colors": [chart_colors.get(l, "#6b7280") for l in intent_labels],
        },
        "sentiment": {
            "labels": list(sentiment_pct.keys()),
            "data": list(sentiment_pct.values()),
            "colors": [sentiment_colors[k] for k in sentiment_pct],
        },
    }


# ==========================================
# Live Chat Endpoints
# ==========================================
@app.get("/api/admin/chats")
async def list_chats(location: Optional[str] = None, admin=Depends(get_current_admin)):
    if admin["role"] == "branch_admin":
        location = admin["location"]
    return Repository.get_chats_list(location)

@app.get("/api/admin/chats/{phone}/messages")
async def get_chat_history(phone: str, limit: int = 50, since: Optional[str] = None, admin=Depends(get_current_admin)):
    user = Repository.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin["role"] == "branch_admin" and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    messages = Repository.get_user_messages(user["id"], limit=limit, since=since)
    return {"user": user, "messages": messages}

@app.post("/api/admin/chats/{phone}/send")
async def send_manual_chat(phone: str, payload: ChatMessagePayload, admin=Depends(get_current_admin)):
    user = Repository.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin["role"] == "branch_admin" and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    await send_whatsapp_message(user["phone_number"], payload.message)
    Repository.log_message(user["id"], "admin", payload.message)
    return {"status": "ok"}

@app.post("/api/admin/chats/{phone}/toggle-human")
async def toggle_human_mode(phone: str, admin=Depends(get_current_admin)):
    user = Repository.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin["role"] == "branch_admin" and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    new_status = 0 if user.get("is_human_chat") == 1 else 1
    Repository.update_user_human_chat(user["id"], new_status)
    return {"is_human_chat": new_status}

@app.post("/api/admin/chats/{phone}/reset-session")
async def reset_ai_session(phone: str, admin=Depends(get_current_admin)):
    user = Repository.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin["role"] == "branch_admin" and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    session_manager.reset_session(user["phone_number"])
    return {"status": "ok"}

@app.patch("/api/admin/leads/{phone}/status")
async def update_lead_status(phone: str, payload: LeadStatusPayload, admin=Depends(get_current_admin)):
    user = Repository.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin["role"] == "branch_admin" and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    Repository.update_lead_status(phone, payload.status)
    return {"status": "ok", "lead_status": payload.status}

async def _internal_analyze_lead(phone: str):
    user = Repository.get_user_by_phone(phone)
    if not user:
        return None
    messages = Repository.get_user_messages(user["id"])
    if not messages:
        return None
    
    log_text = "\n".join([f"{'Customer' if m['role']=='user' else 'Bot/Admin'}: {m['content']}" for m in messages])
    
    try:
        from agent import get_chat_llm
        llm = get_chat_llm(temperature=0.0)
        prompt = f"""You are a Lead Scoring AI for the business.
Analyze this chat history and classify the customer as a 'hot', 'warm', or 'cold' lead based on their engagement and purchase signals.
Output MUST be in the following exact JSON format without markdown code blocks:
{{
  "lead_status": "hot",
  "analysis": "A brief 2 sentence summary of their intent",
  "next_steps": "A bulleted list (using -, no markdown asterisks) of recommended actions for the agent"
}}

Chat Log:
{log_text}"""
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
        from agent import extract_text_response
        response_text = extract_text_response(response.content).strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
            
        import json
        data = json.loads(response_text)
        
        lead_status = data.get("lead_status", "unassigned").lower()
        if lead_status not in ["hot", "warm", "cold"]:
            lead_status = "unassigned"
            
        analysis = data.get("analysis", "")
        next_steps = data.get("next_steps", "")
        if isinstance(next_steps, list):
            next_steps = "\n- ".join(str(s) for s in next_steps)
            if next_steps:
                next_steps = "- " + next_steps
        Repository.update_lead_analysis(phone, lead_status, analysis, next_steps)
        return {"status": "ok", "lead_status": lead_status, "analysis": analysis, "next_steps": next_steps}
    except Exception as e:
        logger.error(f"Lead analysis failed: {e}")
        return None

@app.post("/api/admin/leads/{phone}/analyze")
async def analyze_lead(phone: str, admin=Depends(get_current_admin)):
    user = Repository.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin["role"] == "branch_admin" and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    result = await _internal_analyze_lead(phone)
    if not result:
        raise HTTPException(status_code=500, detail="Analysis failed or no messages found")
    return result

@app.get("/api/admin/chats/{phone}/analyze")
async def analyze_user_chat(phone: str, admin=Depends(get_current_admin)):
    user = Repository.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin["role"] == "branch_admin" and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    messages = Repository.get_user_messages(user["id"])
    if not messages:
        return "No conversation history to analyze."
    log_text = "\n".join([f"{'Customer' if m['role']=='user' else 'Bot/Admin'}: {m['content']}" for m in messages])
    try:
        from agent import get_chat_llm
        llm = get_chat_llm(temperature=0.0)
        prompt = f"""You are a senior marketing and support analyst for the business.
Analyze this chat between a customer and the bot/admin.
Provide a concise, high-value summary of exactly three sections.
DO NOT use markdown formatting (no asterisks).
Format exactly like this:

Customer Intent: <one sentence summarizing what the customer wants>
Sentiment & Obstacles: <one sentence summarizing how the customer feels and what went wrong>
Agent Action Advice:
- <concrete action advice 1>
- <concrete action advice 2>

Chat Log:
{log_text}"""
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
        from agent import extract_text_response
        return extract_text_response(response.content) or "Failed to summarize chat."
    except Exception as e:
        logger.error(f"Failed to analyze chat: {e}")
        return f"Error: {e}"

@app.get("/api/admin/chats/{phone}/export")
async def export_chat_history(phone: str, admin=Depends(get_current_admin)):
    user = Repository.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin["role"] == "branch_admin" and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    messages = Repository.get_user_messages(user["id"])
    csv_header = "ID,Timestamp,Role,Content\n"
    csv_rows = []
    for m in messages:
        content_escaped = m["content"].replace('"', '""')
        csv_rows.append(f'{m["id"]},"{m["created_at"]}","{m["role"]}","{content_escaped}"')
    csv_data = csv_header + "\n".join(csv_rows)
    return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=chat_{phone}.csv"})


# ==========================================
# Broadcast
# ==========================================
@app.post("/api/admin/broadcast")
async def send_broadcast(payload: BroadcastRequest, admin=Depends(get_current_admin)):
    if admin["role"] == "branch_admin":
        payload.location = admin["location"]
        payload.locations = [admin["location"]] if admin["location"] else []
        if payload.target == "all":
            payload.target = "branch"
        elif payload.target == "package":
            payload.target = "package_branch"
        elif payload.target == "branch":
            payload.locations = [admin["location"]]
        elif payload.target == "package_branch":
            payload.locations = [admin["location"]]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if payload.target == "package":
            pkgs = payload.package_ids if payload.package_ids else ([payload.package_id] if payload.package_id is not None else [])
            if pkgs:
                placeholders = ",".join("?" * len(pkgs))
                cursor.execute(f"""
                    SELECT DISTINCT u.phone_number FROM users u
                    JOIN registrations r ON u.id = r.user_id
                    WHERE r.package_id IN ({placeholders})
                """, tuple(pkgs))
            else:
                cursor.execute("SELECT phone_number FROM users WHERE 1=0")
        elif payload.target == "package_branch":
            conds = []
            params = []
            
            pkgs = payload.package_ids if payload.package_ids else ([payload.package_id] if payload.package_id is not None else [])
            if pkgs:
                placeholders = ",".join("?" * len(pkgs))
                conds.append(f"r.package_id IN ({placeholders})")
                params.extend(pkgs)
                
            locs = payload.locations if payload.locations else ([payload.location] if payload.location else [])
            if locs:
                placeholders = ",".join("?" * len(locs))
                conds.append(f"r.location IN ({placeholders})")
                params.extend(locs)
                
            if conds:
                where_clause = " AND ".join(conds)
                cursor.execute(f"""
                    SELECT DISTINCT u.phone_number FROM users u
                    JOIN registrations r ON u.id = r.user_id
                    WHERE {where_clause}
                """, tuple(params))
            else:
                cursor.execute("SELECT phone_number FROM users WHERE 1=0")
        elif payload.target == "branch":
            locs = payload.locations if payload.locations else ([payload.location] if payload.location else [])
            if locs:
                placeholders = ",".join("?" * len(locs))
                cursor.execute(f"""
                    SELECT phone_number FROM users WHERE location IN ({placeholders})
                """, tuple(locs))
            else:
                cursor.execute("SELECT phone_number FROM users WHERE 1=0")
        else:
            cursor.execute("SELECT phone_number FROM users")

        recipients = [row["phone_number"] for row in cursor.fetchall()]

    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients found.")

    async def dispatch():
        for phone in recipients:
            try:
                await send_whatsapp_message(phone, payload.message)
                user = Repository.get_user_by_phone(phone)
                if user:
                    Repository.log_message(user["id"], "assistant", f"[BROADCAST] {payload.message}")
            except Exception as e:
                logger.error(f"Broadcast failed for {phone}: {e}")
    asyncio.create_task(dispatch())
    Repository.create_broadcast(payload.message, admin["id"], len(recipients))
    return {"status": "ok", "recipient_count": len(recipients)}

@app.get("/api/admin/broadcast")
async def get_broadcast_logs(admin=Depends(get_current_admin)):
    return Repository.get_broadcasts()


# ==========================================
# CRUD: Packages
# ==========================================
@app.get("/api/admin/packages")
async def get_packages(admin=Depends(get_current_admin)):
    return Repository.get_packages()

@app.get("/api/admin/packages/{id}")
async def get_package(id: int, admin=Depends(get_current_admin)):
    p = Repository.get_package_by_id(id)
    if not p: raise HTTPException(status_code=404, detail="Package not found")
    return p

@app.post("/api/admin/packages")
async def create_package(payload: PackagePayload, admin=Depends(require_role(["super_admin"]))):
    return {"id": Repository.create_package(payload.name, payload.category, payload.description, payload.schedule_type, payload.duration_weeks, payload.price)}

@app.put("/api/admin/packages/{id}")
async def update_package(id: int, payload: PackagePayload, admin=Depends(require_role(["super_admin"]))):
    if not Repository.get_package_by_id(id): raise HTTPException(status_code=404, detail="Package not found")
    Repository.update_package(id, payload.name, payload.category, payload.description, payload.schedule_type, payload.duration_weeks, payload.price)
    return {"status": "ok"}

@app.delete("/api/admin/packages/{id}")
async def delete_package(id: int, admin=Depends(require_role(["super_admin"]))):
    if not Repository.get_package_by_id(id): raise HTTPException(status_code=404, detail="Package not found")
    Repository.delete_package(id)
    return {"status": "ok"}


# ==========================================
# CRUD: Branches
# ==========================================
@app.get("/api/admin/clients")
async def get_clients(admin=Depends(get_current_admin)):
    return Repository.get_clients()

@app.get("/api/admin/clients/{id}")
async def get_client(id: int, admin=Depends(get_current_admin)):
    c = Repository.get_client_by_id(id)
    if not c: raise HTTPException(status_code=404, detail="Branch not found")
    return c

@app.post("/api/admin/clients")
async def create_client(payload: ClientPayload, admin=Depends(require_role(["super_admin"]))):
    return {"id": Repository.create_client(payload.name, payload.region, payload.contact_numbers, payload.address, payload.google_maps_link)}

@app.put("/api/admin/clients/{id}")
async def update_client(id: int, payload: ClientPayload, admin=Depends(require_role(["super_admin"]))):
    if not Repository.get_client_by_id(id): raise HTTPException(status_code=404, detail="Branch not found")
    Repository.update_client(id, payload.name, payload.region, payload.contact_numbers, payload.address, payload.google_maps_link)
    return {"status": "ok"}

@app.delete("/api/admin/clients/{id}")
async def delete_client(id: int, admin=Depends(require_role(["super_admin"]))):
    if not Repository.get_client_by_id(id): raise HTTPException(status_code=404, detail="Branch not found")
    Repository.delete_client(id)
    return {"status": "ok"}


# ==========================================
# CRUD: Add-On Fees
# ==========================================
@app.get("/api/admin/fees")
async def get_fees(admin=Depends(get_current_admin)):
    return Repository.get_fees()

@app.get("/api/admin/fees/{id}")
async def get_fee(id: int, admin=Depends(get_current_admin)):
    f = Repository.get_fee_by_id(id)
    if not f: raise HTTPException(status_code=404, detail="Fee not found")
    return f

@app.post("/api/admin/fees")
async def create_fee(payload: FeePayload, admin=Depends(require_role(["super_admin"]))):
    return {"id": Repository.create_fee(payload.name, payload.description, payload.amount, payload.mandatory, payload.pass_through)}

@app.put("/api/admin/fees/{id}")
async def update_fee(id: int, payload: FeePayload, admin=Depends(require_role(["super_admin"]))):
    if not Repository.get_fee_by_id(id): raise HTTPException(status_code=404, detail="Fee not found")
    Repository.update_fee(id, payload.name, payload.description, payload.amount, payload.mandatory, payload.pass_through)
    return {"status": "ok"}

@app.delete("/api/admin/fees/{id}")
async def delete_fee(id: int, admin=Depends(require_role(["super_admin"]))):
    if not Repository.get_fee_by_id(id): raise HTTPException(status_code=404, detail="Fee not found")
    Repository.delete_fee(id)
    return {"status": "ok"}


# ==========================================
# CRUD: Knowledge Base & Document Upload
# ==========================================
@app.get("/api/admin/knowledge")
async def list_knowledge(admin=Depends(get_current_admin)):
    return Repository.get_knowledge_base()

@app.get("/api/admin/knowledge/{id}")
async def get_knowledge(id: int, admin=Depends(get_current_admin)):
    k = Repository.get_knowledge_by_id(id)
    if not k: raise HTTPException(status_code=404, detail="Record not found")
    return k

@app.post("/api/admin/knowledge")
async def create_knowledge(payload: KnowledgePayload, admin=Depends(require_role(["super_admin"]))):
    kb_id = Repository.create_knowledge(payload.topic, payload.content)
    try:
        from rag_engine import ingest_knowledge
        ingest_knowledge(kb_id, payload.topic, payload.content)
    except Exception as e:
        logger.error(f"Failed to index knowledge entry {kb_id} to ChromaDB: {e}")
    return {"id": kb_id}

@app.put("/api/admin/knowledge/{id}")
async def update_knowledge(id: int, payload: KnowledgePayload, admin=Depends(require_role(["super_admin"]))):
    Repository.update_knowledge(id, payload.topic, payload.content)
    try:
        from rag_engine import delete_knowledge_entry, ingest_knowledge
        delete_knowledge_entry(id)
        ingest_knowledge(id, payload.topic, payload.content)
    except Exception as e:
        logger.error(f"Failed to update knowledge entry {id} in ChromaDB: {e}")
    return {"status": "ok"}

@app.delete("/api/admin/knowledge/{id}")
async def delete_knowledge(id: int, admin=Depends(require_role(["super_admin"]))):
    Repository.delete_knowledge(id)
    try:
        from rag_engine import delete_knowledge_entry
        delete_knowledge_entry(id)
    except Exception as e:
        logger.error(f"Failed to delete knowledge entry {id} from ChromaDB: {e}")
    return {"status": "ok"}

@app.post("/api/admin/documents/upload")
async def upload_document(file: UploadFile = File(...), admin=Depends(require_role(["super_admin"]))):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    file_name = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, file_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        from rag_engine import ingest_pdf
        result = ingest_pdf(file_path)
        return {"status": "ok", "filename": file.filename, **result}
    except Exception as e:
        try: os.remove(file_path)
        except: pass
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {e}")

@app.get("/api/admin/documents")
async def list_documents(admin=Depends(get_current_admin)):
    try:
        from rag_engine import list_documents
        return list_documents()
    except Exception as e:
        return []

@app.delete("/api/admin/documents/{filename}")
async def delete_document(filename: str, admin=Depends(require_role(["super_admin"]))):
    try:
        from rag_engine import delete_document
        count = delete_document(filename)
        # Clean up file from disk
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as fe:
                logger.error(f"Failed to remove file {filename} from disk: {fe}")
        return {"status": "ok", "chunks_deleted": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/documents/status")
async def document_status(admin=Depends(get_current_admin)):
    try:
        from rag_engine import get_stats
        return get_stats()
    except Exception as e:
        return {"total_chunks": 0, "total_documents": 0, "error": str(e)}


# ==========================================
# Registrations
# ==========================================
@app.get("/api/admin/registrations")
async def list_registrations(location: Optional[str] = None, status: Optional[str] = None, package_id: Optional[int] = None, search: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, admin=Depends(get_current_admin)):
    return Repository.get_registrations_filtered(location, status, package_id, search, start_date, end_date)

@app.get("/api/admin/registrations/{id}")
async def get_registration_by_id(id: int, admin=Depends(get_current_admin)):
    r = Repository.get_registration_by_id(id)
    if not r: raise HTTPException(status_code=404, detail="Registration not found")
    if admin["role"] == "branch_admin" and r.get("user_location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    return r

@app.put("/api/admin/registrations/{id}")
async def update_registration(id: int, payload: UpdateRegistrationPayload, admin=Depends(get_current_admin)):
    if not Repository.get_registration_by_id(id):
        raise HTTPException(status_code=404, detail="Registration not found")
    Repository.update_registration_full(
        id, 
        payload.package_id, 
        payload.status, 
        payload.name, 
        payload.dob, 
        payload.ghana_card, 
        payload.place_of_birth, 
        payload.witness_name, 
        payload.witness_phone, 
        payload.marital_status, 
        payload.location
    )
    return {"status": "ok"}

@app.delete("/api/admin/registrations/{id}")
async def delete_registration(id: int, admin=Depends(get_current_admin)):
    if not Repository.get_registration_by_id(id):
        raise HTTPException(status_code=404, detail="Registration not found")
    Repository.delete_registration(id)
    return {"status": "ok"}


@app.post("/api/admin/registrations/{id}/check-payment")
async def check_registration_payment(id: int, admin=Depends(get_current_admin)):
    registration = Repository.get_registration_by_id(id)
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    
    # Permission check for branch admins
    if admin["role"] == "branch_admin" and registration.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    ref = registration.get("payment_reference")
    if not ref:
        return {"status": "error", "message": "No payment reference has been generated for this registration."}
        
    # If already confirmed, just return it
    if registration["status"] == "confirmed":
        return {"status": "success", "message": "Payment was already confirmed."}
        
    # Query Paystack API
    headers = {
        "Authorization": f"Bearer {settings.paystack_secret_key}",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"https://api.paystack.co/transaction/verify/{ref}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") and data.get("data", {}).get("status") == "success":
                    # Update DB status
                    Repository.update_registration_status(id, "confirmed", ref)
                    
                    # Send WhatsApp confirmation to user
                    user = Repository.get_user_by_id(registration["user_id"])
                    if user:
                        package = Repository.get_package_by_id(registration["package_id"])
                        package_name = package["name"] if package else "selected package"
                        amount_paid = data["data"]["amount"] / 100
                        msg = (f"*Payment Confirmed*\n\n"
                               f"Thank you for your payment of GHS {amount_paid:.2f}.\n"
                               f"Program: {package_name}\nReference: {ref}\n\n"
                               f"Your spot is now reserved. Our team will contact you with your schedule.\n"
                               f"For questions, reply to this chat.")
                        await send_whatsapp_message(user["phone_number"], msg)
                    return {"status": "success", "message": "Payment verified successfully. Registration status updated."}
                else:
                    paystack_status = data.get("data", {}).get("status", "unknown")
                    return {"status": "pending", "message": f"Payment is not completed. Paystack status: {paystack_status}"}
            else:
                return {"status": "error", "message": f"Paystack returned status code {response.status_code}"}
    except Exception as e:
        logger.error(f"Error verifying payment with Paystack: {e}")
        return {"status": "error", "message": f"Failed to verify payment: {str(e)}"}


@app.get("/api/admin/clients-list")
async def list_unique_clients(location: Optional[str] = None, search: Optional[str] = None, admin=Depends(get_current_admin)):
    return Repository.get_unique_registered_users(location, search)

@app.post("/api/admin/registrations/send")
async def send_to_registrants(payload: SendToRegistrantsPayload, admin=Depends(get_current_admin)):
    if not payload.registration_ids:
        raise HTTPException(status_code=400, detail="No recipients selected")
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(payload.registration_ids))
        cursor.execute(f"""
            SELECT DISTINCT u.phone_number, u.id as user_id FROM registrations r
            JOIN users u ON r.user_id = u.id WHERE r.id IN ({placeholders})
        """, payload.registration_ids)
        recipients = [dict(row) for row in cursor.fetchall()]
    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients found")

    async def dispatch():
        for r in recipients:
            try:
                await send_whatsapp_message(r["phone_number"], payload.message)
                Repository.log_message(r["user_id"], "admin", f"[DIRECT] {payload.message}")
            except Exception as e:
                logger.error(f"Failed to send to {r['phone_number']}: {e}")
    asyncio.create_task(dispatch())
    Repository.create_broadcast(payload.message, admin["id"], len(recipients))
    return {"status": "ok", "recipient_count": len(recipients)}


# ==========================================
# Support Tickets
# ==========================================
@app.get("/api/admin/tickets")
async def list_tickets(location: Optional[str] = None, admin=Depends(get_current_admin)):
    if admin["role"] == "branch_admin":
        location = admin["location"]
    return Repository.get_tickets(location)

@app.get("/api/admin/tickets/{id}")
async def get_ticket_by_id(id: int, admin=Depends(get_current_admin)):
    t = Repository.get_ticket_by_id(id)
    if not t: raise HTTPException(status_code=404, detail="Ticket not found")
    user = Repository.get_user_by_id(t["user_id"])
    if admin["role"] == "branch_admin" and user and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    return t

@app.post("/api/admin/tickets/{id}/resolve")
async def resolve_ticket(id: int, admin=Depends(get_current_admin)):
    t = Repository.get_ticket_by_id(id)
    if not t: raise HTTPException(status_code=404, detail="Ticket not found")
    user = Repository.get_user_by_id(t["user_id"])
    if admin["role"] == "branch_admin" and user and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    Repository.update_ticket_status(id, "resolved")
    return {"status": "ok"}

@app.put("/api/admin/tickets/{id}")
async def update_ticket(id: int, payload: UpdateTicketPayload, admin=Depends(get_current_admin)):
    t = Repository.get_ticket_by_id(id)
    if not t: raise HTTPException(status_code=404, detail="Ticket not found")
    user = Repository.get_user_by_id(t["user_id"])
    if admin["role"] == "branch_admin" and user and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    Repository.update_ticket_full(id, payload.subject, payload.description, payload.status, payload.location)
    return {"status": "ok"}

@app.delete("/api/admin/tickets/{id}")
async def delete_ticket(id: int, admin=Depends(get_current_admin)):
    t = Repository.get_ticket_by_id(id)
    if not t: raise HTTPException(status_code=404, detail="Ticket not found")
    user = Repository.get_user_by_id(t["user_id"])
    if admin["role"] == "branch_admin" and user and user.get("location") != admin["location"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    Repository.delete_ticket(id)
    return {"status": "ok"}


# ==========================================
# Admin Users (Super Admin Only)
# ==========================================
@app.get("/api/admin/users")
async def list_admins(admin=Depends(require_role(["super_admin"]))):
    return Repository.get_admins()

@app.get("/api/admin/users/{id}")
async def get_admin(id: int, admin=Depends(require_role(["super_admin"]))):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, location, created_at FROM admin_users WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row: raise HTTPException(status_code=404, detail="Admin not found")
        return dict(row)

@app.post("/api/admin/users")
async def create_admin(payload: AdminPayload, admin=Depends(require_role(["super_admin"]))):
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required")
    return {"id": Repository.create_admin(payload.username, hash_password(payload.password), payload.role, payload.location)}

@app.put("/api/admin/users/{id}")
async def update_admin(id: int, payload: AdminPayload, admin=Depends(require_role(["super_admin"]))):
    pw_hash = hash_password(payload.password) if payload.password else None
    Repository.update_admin(id, payload.username, payload.role, payload.location, pw_hash)
    return {"status": "ok"}

@app.delete("/api/admin/users/{id}")
async def delete_admin(id: int, admin=Depends(require_role(["super_admin"]))):
    Repository.delete_admin(id)
    return {"status": "ok"}

@app.post("/api/admin/users/{id}/force-reset")
async def force_admin_password_reset(id: int, admin=Depends(require_role(["super_admin"]))):
    import random
    import string
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    pw_hash = hash_password(temp_password)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE admin_users SET password_hash=?, must_reset_password=1 WHERE id=?", (pw_hash, id))
        conn.commit()
    return {"temp_password": temp_password}


# ==========================================
# Metrics & RAG & AI Agent Tools (Dashboard Integration)
# ==========================================
@app.get("/api/admin/metrics")
async def get_metrics(location: Optional[str] = None, admin=Depends(get_current_admin)):
    if admin["role"] == "branch_admin":
        location = admin["location"]
    return Repository.get_overview_metrics(location)

@app.get("/api/admin/rag/status")
async def get_rag_status(admin=Depends(get_current_admin)):
    try:
        from rag_engine import get_stats
        stats = get_stats()
        embeddings_active = bool(settings.google_api_key)
        return {
            "count": stats.get("total_chunks", 0),
            "embeddings_active": embeddings_active
        }
    except Exception as e:
        logger.error(f"Error getting RAG status: {e}")
        return {"count": 0, "embeddings_active": False, "error": str(e)}

@app.post("/api/admin/rag/rebuild")
async def rebuild_rag_index(admin=Depends(require_role(["super_admin"]))):
    try:
        from rag_engine import clear_all, ingest_knowledge, get_stats
        clear_all()
        
        # Load all knowledge entries from SQLite
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, topic, content FROM knowledge_base")
            rows = cursor.fetchall()
            
        chunks_total = 0
        for row in rows:
            try:
                ingest_knowledge(row["id"], row["topic"], row["content"])
                chunks_total += 1
            except Exception as fe:
                logger.error(f"Failed to index knowledge entry {row['id']} during rebuild: {fe}")
                
        stats = get_stats()
        return {"status": "ok", "count": stats.get("total_chunks", 0)}
    except Exception as e:
        logger.error(f"Error rebuilding vector store: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class RAGQueryPayload(BaseModel):
    query: str

@app.post("/api/admin/rag/query")
async def query_rag(payload: RAGQueryPayload, admin=Depends(get_current_admin)):
    try:
        from rag_engine import search_documents
        results = search_documents(payload.query)
        if not results:
            return {"context": ""}
        context_parts = []
        for r in results:
            context_parts.append(f"[Source: {r['source']}, Page: {r['page']}]\n{r['content']}")
        context = "\n\n".join(context_parts)
        return {"context": context}
    except Exception as e:
        logger.error(f"Error query RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/tools")
async def get_tools_list(admin=Depends(get_current_admin)):
    try:
        from tools import ALL_TOOLS
        serialized = []
        for tool in ALL_TOOLS:
            properties = {}
            required = []
            if hasattr(tool, "args_schema") and tool.args_schema:
                try:
                    if hasattr(tool.args_schema, "model_json_schema"):
                        schema = tool.args_schema.model_json_schema()
                    else:
                        schema = tool.args_schema.schema()
                    properties = schema.get("properties", {})
                    required = schema.get("required", [])
                except Exception:
                    properties = tool.args
            else:
                properties = tool.args
            
            serialized.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })
        return serialized
    except Exception as e:
        logger.error(f"Error getting tools list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ToolCallPayload(BaseModel):
    name: str
    arguments: dict

@app.post("/api/admin/tools/call")
async def call_registered_tool(payload: ToolCallPayload, admin=Depends(get_current_admin)):
    try:
        from tools import ALL_TOOLS
        target_tool = None
        for tool in ALL_TOOLS:
            if tool.name == payload.name:
                target_tool = tool
                break
        if not target_tool:
            raise HTTPException(status_code=404, detail=f"Tool '{payload.name}' not found.")
        
        result = target_tool.invoke(payload.arguments)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error calling tool {payload.name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# WhatsApp Webhook
# ==========================================
async def send_typing_indicator(message_id: str):
    phone_number_id = settings.whatsapp_phone_number_id.strip() if settings.whatsapp_phone_number_id else ""
    api_token = settings.whatsapp_api_token.strip() if settings.whatsapp_api_token else ""
    if not api_token or not phone_number_id or not message_id:
        return
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id, "typing_indicator": {"type": "text"}}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except Exception as e:
            logger.debug(f"Typing indicator failed: {e}")


async def send_whatsapp_message(to_phone_number: str, message: str):
    if not message or not message.strip():
        logger.warning(f"Attempted to send empty WhatsApp message to {to_phone_number}. Skipping.")
        return
    phone_number_id = settings.whatsapp_phone_number_id.strip() if settings.whatsapp_phone_number_id else ""
    api_token = settings.whatsapp_api_token.strip() if settings.whatsapp_api_token else ""
    if not api_token or not phone_number_id:
        logger.warning(f"WhatsApp API keys missing. Would have sent: {message} to {to_phone_number}")
        return
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to_phone_number, "type": "text", "text": {"body": message}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Sent message to {to_phone_number}")
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error: {e.response.text}")
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {type(e).__name__}: {e}", exc_info=True)


@app.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode and token:
        if mode == "subscribe" and token == settings.whatsapp_webhook_verify_token:
            logger.info("WEBHOOK_VERIFIED")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Forbidden")
    raise HTTPException(status_code=400, detail="Bad Request")


_PROCESSED_MESSAGE_IDS: set[str] = set()
_MAX_DEDUP_CACHE = 5000

def _trim_dedup_cache() -> None:
    global _PROCESSED_MESSAGE_IDS
    if len(_PROCESSED_MESSAGE_IDS) > _MAX_DEDUP_CACHE:
        excess = len(_PROCESSED_MESSAGE_IDS) - int(_MAX_DEDUP_CACHE * 0.8)
        remove = set(list(_PROCESSED_MESSAGE_IDS)[:excess])
        _PROCESSED_MESSAGE_IDS -= remove

async def handle_flow_submission(phone_number: str, user_id: int, flow_token: str, flow_data: dict):
    from database import get_db_connection
    from config import settings
    
    # 1. Ticket Submission
    if flow_token.startswith("ticket_token_"):
        subject = flow_data.get("subject", "General Support Request")
        description = flow_data.get("description", "")
        
        # Save to DB
        user_row = Repository.get_user_by_id(user_id)
        user_location = user_row.get("location") if user_row else None
        Repository.create_ticket(user_id, subject, description, location=user_location)
        
        # Log message activity
        Repository.log_message(user_id, "user", f"[Flow Ticket]: {subject} - {description}")
        
        # Send confirmation
        confirm_msg = (
            f"*Support Ticket Created Successfully!*\n\n"
            f"Subject: {subject}\n"
            f"Status: Open\n\n"
            f"Our customer service representatives will contact you shortly."
        )
        Repository.log_message(user_id, "assistant", confirm_msg)
        await send_whatsapp_message(phone_number, confirm_msg)
        
    # 2. Registration Submission
    elif flow_token.startswith("registration_token_"):
        parts = flow_token.split("_")
        user_id = int(parts[-2])
        package_id = int(parts[-1])
        name = flow_data.get("name", "")
        dob = flow_data.get("dob", "")
        ghana_card = flow_data.get("ghana_card", "")
        place_of_birth = flow_data.get("place_of_birth", "")
        witness_name = flow_data.get("witness_name", "")
        witness_phone = flow_data.get("witness_phone", "")
        marital_status = flow_data.get("marital_status", "")
        location = flow_data.get("location", "")
        
        # Save custom registration details to SQLite
        reg_id = Repository.create_registration(
            user_id=user_id,
            package_id=package_id,
            status='pending',
            name=name,
            dob=dob,
            ghana_card=ghana_card,
            place_of_birth=place_of_birth,
            witness_name=witness_name,
            witness_phone=witness_phone,
            marital_status=marital_status,
            location=location
        )
            
        # Log message activity
        Repository.log_message(user_id, "user", f"[Flow Registration] Name: {name}, DOB: {dob}, Ghana Card: {ghana_card}, POB: {place_of_birth}, Witness: {witness_name} ({witness_phone}), Marital: {marital_status}, Location: {location}")
        
        # Update the user's location in the users table to the chosen branch
        if location:
            Repository.update_user_location(user_id, location)
        
        # Look up branch details for confirmation message
        branch_footer = ""
        if location:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, address, contact_numbers, google_maps_link FROM clients")
                branch_rows = cursor.fetchall()
            matched_branch = None
            loc_lower = location.strip().lower()
            for br in branch_rows:
                if loc_lower in br['name'].lower() or br['name'].lower() in loc_lower:
                    matched_branch = dict(br)
                    break
            if not matched_branch:
                for br in branch_rows:
                    for word in loc_lower.split():
                        if len(word) > 2 and word in br['name'].lower():
                            matched_branch = dict(br)
                            break
                    if matched_branch:
                        break
            if matched_branch:
                branch_footer = (
                    f"\n*Branch Details:*\n"
                    f"Branch: {matched_branch['name']} (Branch #{matched_branch['id']})\n"
                    f"Address: {matched_branch.get('address', 'N/A')}\n"
                    f"Contact: {matched_branch.get('contact_numbers', 'N/A')}\n"
                    f"Google Maps: {matched_branch.get('google_maps_link', 'N/A')}"
                )
            else:
                branch_footer = f"\nBranch: {location}"
        
        # Pull package info for payment response
        package = Repository.get_package_by_id(package_id)
        if not package:
            logger.error(f"Package {package_id} not found for registration {reg_id}")
            return
            
        # Re-use our conditional Paystack payment link logic
        if settings.use_paystack:
            # Initialize Paystack transaction (amount in pesewas)
            amount_in_pesewas = int(package["price"] * 100)
            headers = {
                "Authorization": f"Bearer {settings.paystack_secret_key}",
                "Content-Type": "application/json"
            }
            # Prepare email for Paystack requirement
            email = f"{phone_number.replace('+', '')}@example.com"

            payload = {
                "email": email,
                "amount": amount_in_pesewas,
                "reference": f"wa_reg_{reg_id}",
                "metadata": {
                    "registration_id": reg_id,
                    "package_name": package["name"],
                    "user_id": user_id
                }
            }
            
            payment_link = ""
            try:
                response = httpx.post(
                    "https://api.paystack.co/transaction/initialize",
                    json=payload,
                    headers=headers,
                    timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("status"):
                    payment_link = data["data"]["authorization_url"]
                    reference = data["data"]["reference"]
                    
                    # Store the payment reference on the registration
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE registrations SET payment_reference = ? WHERE id = ?",
                            (reference, reg_id)
                        )
                        conn.commit()
            except Exception as pe:
                logger.error(f"Failed to initialize Paystack transaction in Flow submission: {pe}")
                
            if payment_link:
                confirm_msg = (
                    f"Registration successful!\n"
                    f"Package: {package['name']}\n"
                    f"Registration ID: {reg_id}\n"
                    f"Amount Due: {package['price']} GHS\n"
                    f"Status: Pending Payment\n"
                    f"{branch_footer}\n\n"
                    f"Please complete payment using this secure link: {payment_link}"
                )
            else:
                confirm_msg = (
                    f"Registration successful!\n"
                    f"Package: {package['name']}\n"
                    f"Registration ID: {reg_id}\n"
                    f"Amount Due: {package['price']} GHS\n"
                    f"Status: Pending payment\n"
                    f"{branch_footer}\n\n"
                    f"Our team will send you payment instructions shortly."
                )
        else:
            visit_text = f"our {matched_branch['name']}" if location and matched_branch else "your chosen branch"
            
            confirm_msg = (
                f"Registration successful!\n"
                f"Package: {package['name']}\n"
                f"Registration ID: {reg_id}\n"
                f"Amount Due: {package['price']} GHS\n"
                f"Status: Pending Payment\n"
                f"{branch_footer}\n\n"
                f"Please visit {visit_text} to make payment."
            )
            
        Repository.log_message(user_id, "assistant", confirm_msg)
        await send_whatsapp_message(phone_number, confirm_msg)


async def process_user_message_task(phone_number: str, user_id: int, user_name: str, text: str, message_id: str):
    try:
        # Truncate long messages for readable terminal logging.
        preview = text if len(text) <= 120 else text[:117] + "..."
        logger.info("[MSG RECV] %s | %s | %s", phone_number, user_name or "?", preview)

        await send_typing_indicator(message_id)
        session = session_manager.get_or_create_session(phone_number, user_id, user_name)
        response_text = await session.send_message(text)

        if not response_text or not response_text.strip():
            logger.warning(f"Empty AI response generated for user {phone_number}. Using fallback text.")
            response_text = "I'm sorry, I could not process that request. How can I help you today?"

        Repository.log_message(user_id, "assistant", response_text)

        response_preview = response_text if len(response_text) <= 150 else response_text[:147] + "..."
        logger.info("[MSG SEND] %s | %s", phone_number, response_preview)

        await send_whatsapp_message(phone_number, response_text)

        # Trigger auto lead analysis in the background
        import asyncio
        asyncio.create_task(_internal_analyze_lead(phone_number))
    except Exception as ex:
        logger.error(f"Error in background message processing: {ex}")


async def handle_flow_submission_task(phone_number: str, user_id: int, flow_token: str, flow_data: dict):
    try:
        await handle_flow_submission(phone_number, user_id, flow_token, flow_data)
    except Exception as ex:
        logger.error(f"Error in background flow processing: {ex}")


@app.post("/webhook/whatsapp")
async def handle_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])

        if messages:
            msg = messages[0]
            phone_number = msg.get("from")
            message_id = msg.get("id", "")

            if message_id and message_id in _PROCESSED_MESSAGE_IDS:
                return {"status": "ok"}

            if message_id:
                _PROCESSED_MESSAGE_IDS.add(message_id)
                _trim_dedup_cache()

            contact_name = None
            if contacts:
                contact_name = contacts[0].get("profile", {}).get("name")

            user = Repository.get_or_create_user(phone_number, contact_name)
            user_id = user["id"]

            msg_type = msg.get("type")
            
            # Handle WhatsApp Flow submissions (interactive nfm_reply)
            if msg_type == "interactive":
                interactive_data = msg.get("interactive", {})
                if interactive_data.get("type") == "nfm_reply":
                    nfm_reply = interactive_data.get("nfm_reply", {})
                    response_json_str = nfm_reply.get("response_json", "{}")
                    
                    import json
                    try:
                        flow_data = json.loads(response_json_str)
                    except Exception:
                        flow_data = {}
                        
                    flow_token = flow_data.get("flow_token", "")
                    
                    background_tasks.add_task(
                        handle_flow_submission_task,
                        phone_number,
                        user_id,
                        flow_token,
                        flow_data
                    )
                    return {"status": "ok"}

            text = ""
            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
            else:
                text = f"[{msg_type.upper()} Message]"

            Repository.log_message(user_id, "user", text)

            if user.get("is_human_chat") == 1:
                logger.info(f"User {phone_number} is in human takeover mode.")
                return {"status": "ok"}

            background_tasks.add_task(
                process_user_message_task,
                phone_number,
                user_id,
                user.get("name"),
                text,
                message_id
            )

    except Exception as e:
        logger.error(f"Error processing message: {e}")

    return {"status": "ok"}


# ==========================================
# Paystack Webhook
# ==========================================
@app.post("/webhook/paystack")
async def handle_paystack_webhook(request: Request):
    payload_bytes = await request.body()
    signature = request.headers.get("x-paystack-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    expected = hmac.new(settings.paystack_secret_key.encode('utf-8'), payload_bytes, hashlib.sha512).hexdigest()
    if signature != expected:
        raise HTTPException(status_code=400, detail="Invalid signature")
    import json
    body = json.loads(payload_bytes)
    event_type = body.get("event")
    data = body.get("data", {})
    logger.info(f"Paystack: event={event_type}, ref={data.get('reference')}")

    if event_type == "charge.success":
        reference = data.get("reference")
        amount_paid = int(data.get("amount", 0)) / 100
        if data.get("status") != "success":
            return {"status": "ok"}
        registration = Repository.get_registration_by_reference(reference)
        if not registration:
            return {"status": "ok"}
        Repository.update_registration_status(registration["id"], "confirmed", reference)
        package = Repository.get_package_by_id(registration["package_id"])
        package_name = package["name"] if package else "your selected package"
        user = Repository.get_user_by_id(registration["user_id"])
        if user:
            msg = (f"*Payment Confirmed*\n\n"
                   f"Thank you for your payment of GHS {amount_paid:.2f}.\n"
                   f"Program: {package_name}\nReference: {reference}\n\n"
                   f"Your spot is now reserved. Our team will contact you with your schedule.\n"
                   f"For questions, reply to this chat.")
            await send_whatsapp_message(user["phone_number"], msg)

    elif event_type == "charge.failed":
        reference = data.get("reference")
        registration = Repository.get_registration_by_reference(reference)
        if registration:
            user = Repository.get_user_by_id(registration["user_id"])
            if user:
                await send_whatsapp_message(user["phone_number"], "Your payment could not be processed. Please try again or contact our office.")

    return {"status": "ok"}
