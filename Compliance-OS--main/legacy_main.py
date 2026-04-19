from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import json
import sqlite3
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialise Groq client (gracefully degrades if key is absent)
try:
    from groq import Groq
    _groq_key = os.getenv("GROQ_API_KEY", "")
    groq_client = Groq(api_key=_groq_key) if _groq_key else None
except Exception:
    groq_client = None

app = FastAPI(title="Multi-Agent Compliance Intelligence System", version="3.0.0")

# Database Initialization
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compliance.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")  # Enables concurrent reads + reduces locking
        conn.execute('''CREATE TABLE IF NOT EXISTS compliance_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      doc_name TEXT,
                      date TEXT,
                      industry TEXT,
                      risk_level TEXT,
                      full_report TEXT)''')
        conn.commit()

init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INDUSTRY_PROMPTS = {
    "banking": {
        "focus": ["KYC", "AML", "loan compliance", "RBI guidelines", "BASEL norms", "AI Governance"],
        "output_type": "internal policy + documentation updates",
        "policies": ["KYC Policy", "AML/CFT Policy", "Loan Sanctioning Policy", "Credit Risk Policy", "Data Governance Policy", "AI Ethics Framework"],
    },
    "fintech": {
        "focus": ["app features", "backend logic", "onboarding flows", "API compliance", "data security"],
        "output_type": "product + system changes",
        "policies": ["User Onboarding Policy", "Data Privacy Policy", "API Security Policy", "Fraud Detection Policy", "PCI-DSS Compliance Policy"],
    },
    "insurance": {
        "focus": ["claims processing", "fraud detection", "policy issuance", "IRDAI regulations", "risk underwriting"],
        "output_type": "workflow + risk controls",
        "policies": ["Claims Processing Policy", "Fraud Prevention Policy", "Underwriting Guidelines", "Customer Disclosure Policy", "Reinsurance Policy"],
    },
    "nbfc": {
        "focus": ["credit scoring", "repayment tracking", "NPA norms", "RBI NBFC guidelines", "co-lending"],
        "output_type": "risk engine + loan system",
        "policies": ["Credit Appraisal Policy", "NPA Recognition Policy", "Fair Practices Code", "Co-Lending Policy", "Recovery & Collections Policy"],
    },
    "corporate": {
        "focus": ["legal compliance", "HR policies", "ESG governance", "SEBI regulations", "board reporting"],
        "output_type": "compliance checklist + policies",
        "policies": ["Board Governance Policy", "Whistleblower Policy", "Code of Conduct", "ESG Reporting Policy", "Insider Trading Compliance Policy"],
    },
}

def parse_regulation(regulation_text: str) -> dict:
    """Agent 1: Monitoring / Parser Agent"""
    keywords = []
    obligations = []
    kw_map = {
        "kyc": "KYC verification mandate",
        "aml": "Anti-Money Laundering controls",
        "data": "Data protection obligations",
        "capital": "Capital adequacy requirements",
        "risk": "Risk management framework",
        "report": "Regulatory reporting requirements",
        "audit": "Audit and inspection obligations",
        "ai": "AI Governance",
        "crypto": "Digital Asset Reporting"
    }
    text_lower = regulation_text.lower()
    for kw, obligation in kw_map.items():
        if kw in text_lower:
            keywords.append(kw.upper())
            obligations.append(obligation)
    return {
        "extracted_keywords": keywords or ["GENERAL"],
        "obligations": obligations or ["Standard regulatory compliance"],
        "authority": _detect_authority(regulation_text)
    }

def _detect_authority(text: str) -> str:
    t = text.lower()
    if "rbi" in t: return "RBI"
    if "sebi" in t: return "SEBI"
    if "irdai" in t: return "IRDAI"
    if "mca" in t: return "MCA"
    return "Global Regulator"

def industry_agent(industry: str, parsed: dict) -> dict:
    """Agent 3: Industry Agent"""
    return {"industry": industry.title(), "focus": INDUSTRY_PROMPTS.get(industry.lower(), {}).get("focus", [])}

def risk_agent(text: str) -> dict:
    """Agent 4: Risk Agent"""
    level = "HIGH" if any(x in text.lower() for x in ["penalty", "must", "immediate"]) else "MEDIUM"
    return {"level": level, "urgency": "HIGH" if level == "HIGH" else "MEDIUM"}

def impact_agent(industry: str) -> dict:
    """Agent 5: Impact Agent"""
    # Logic extracted from previous implementation for consistency
    return {
        "financial": ["Potential ₹50–120 Cr investment", "15–25% increase in ops cost"],
        "operational": ["Core system upgrades", "20% headcount increase"],
        "market": ["Competitive differentiation", "Trust advantage"]
    }

def policy_agent(industry: str) -> list:
    """Agent 6: Policy Agent"""
    return INDUSTRY_PROMPTS.get(industry.lower(), {}).get("policies", [])[:3]

def action_agent(risk_level: str) -> list:
    """Agent 7: Action Agent"""
    return [
        {"priority": "HIGH", "action": "Establish Board-level Ethics & Compliance Committee"},
        {"priority": risk_level, "action": "Initiate cross-functional gap analysis sprint"}
    ]

def report_agent(data: dict) -> dict:
    """Agent 8: Report Agent - Builds final structured JSON"""
    import datetime
    return {
        "report_metadata": {
            "generated_at": datetime.datetime.now().isoformat(),
            "system": "Real-Time AI Compliance Engine",
            "industry": data["industry"]
        },
        "executive_summary": f"Autonomous analysis of {data['authority']} mandate for the {data['industry']} sector. Risk profile {data['risk']['level']}.",
        "regulatory_update": f"{data['authority']} mandate regarding {', '.join(data['parsed']['obligations'])}.",
        "risk_analysis": {
            "risk_level": data["risk"]["level"],
            "urgency": data["risk"]["urgency"],
            "reason": f"Regulation imposes significant {data['risk']['level']} risk obligations with immediate impact."
        },
        "business_impact": data["impact"],
        "affected_policies": data["policies"],
        "action_plan": data["actions"],
        "compliance_risks": ["Reporting latency", "Data integrity audit failure"],
        "recommendations": ["Automate telemetry pipeline", "Update Ethics Framework"],
        "final_conclusion": "Immediate compliance mobilization required to prevent regulatory friction."
    }

def adapt_to_industry(industry: str, parsed: dict) -> dict:
    """Agent 2: Industry Adapter Agent"""
    industry_config = INDUSTRY_PROMPTS.get(industry.lower(), INDUSTRY_PROMPTS["corporate"])
    return {
        "industry_focus": industry_config["focus"],
        "output_type": industry_config["output_type"],
        "base_policies": industry_config["policies"],
        "adapted_obligations": parsed["obligations"],
    }

def analyze_risk(regulation_text: str, industry: str, parsed: dict) -> dict:
    """Agent 3: Risk Analysis Agent"""
    high_risk_terms = ["penalty", "suspension", "criminal", "mandatory", "zero-tolerance", "restriction"]
    
    text_lower = regulation_text.lower()
    high_count = sum(1 for t in high_risk_terms if t in text_lower)
    
    if high_count >= 2 or len(parsed["obligations"]) >= 4:
        level = "HIGH"
        reason = f"Regulation imposes concurrent obligations with potential punitive measures including operational restriction. Immediate compliance action required across {industry.upper()} operations."
    elif high_count == 1 or len(parsed["obligations"]) >= 2:
        level = "MEDIUM"
        reason = f"Regulation introduces structural compliance obligations requiring remediation. Moderate operational disruption expected in {industry.upper()} workflows."
    else:
        level = "LOW"
        reason = "Regulation represents incremental policy refinement."
    
    return {"risk_level": level, "reason": reason}

def analyze_business_impact(industry: str, parsed: dict, risk: dict) -> dict:
    """Agent 4: Business Impact Agent"""
    ind = industry.lower()
    
    impacts = {
        "banking": {
            "financial": [
                "Estimated ₹50–120 Cr investment required for new infrastructure/oversight",
                "Potential 15–25% increase in compliance operational unit costs",
                "Revenue deferral risk due to restriction on new product launches",
            ],
            "operational": [
                "Integration of internal validation teams with product engineering workflows",
                "Core banking system upgrades for enhanced auditing and logging",
                "Compliance officer and model risk management headcount increase by 20%",
            ],
            "market": [
                "Slower time-to-market for new algorithmic models / digital products",
                "Competitive differentiation via compliant 'Trusted' digital systems",
                "Regulatory confidence boosts institutional investor sentiment",
            ],
        },
        "fintech": {
            "financial": [
                "Product development budget reallocation: ₹10–40 Cr for compliance engines",
                "Infrastructure cost increase of ~20% for continuous monitoring systems",
            ],
            "operational": [
                "Backend API overhaul to integrate human-in-the-loop fallback mechanisms",
                "Cross-functional sprint teams needed for rapid compliance adoption",
            ],
            "market": [
                "Compliant fintechs gain trust advantage with enterprise B2B banking clients",
                "Non-compliant fintechs face total app store/onboarding freeze",
            ],
        }
    }
    
    default_impact = impacts["banking"]
    base = impacts.get(ind, default_impact)
    return {
        "financial": base["financial"],
        "operational": base["operational"],
        "market": base["market"],
    }

def map_policies(industry: str, parsed: dict, adapted: dict) -> list:
    """Agent 5: Policy Mapping Agent"""
    base_policies = adapted["base_policies"]
    obligation_policies = []
    
    for obl in parsed["obligations"]:
        if "KYC" in obl: obligation_policies.append("KYC Policy")
        if "AML" in obl: obligation_policies.append("AML/CFT Policy")
        if "Data" in obl: obligation_policies.append("Data Governance Policy")
        if "AI" in obl or "Algorithmic" in obl: 
            obligation_policies.append("AI Ethics & Governance Framework")
            obligation_policies.append("Model Risk Management Policy")
    
    all_policies = list(dict.fromkeys(obligation_policies + base_policies))
    return all_policies[:6]

def generate_actions(industry: str, parsed: dict, risk: dict) -> list:
    """Agent 6: Action Generator Agent"""
    ind = industry.lower()
    
    actions = {
        "banking": [
            {"type": "process_change", "description": "Form a dedicated Ethics & Compliance Committee at the Board Level to oversee all algorithm/LLM deployments."},
            {"type": "system_change", "description": "Implement 'Human-in-the-Loop' (HITL) manual overrides for all high-value flagged transactions."},
            {"type": "policy_update", "description": "Draft and adopt an AI Governance Framework mapping to RBI mandates within 45 days."},
            {"type": "system_change", "description": "Deploy continuous monitoring dashboards to detect bias and drift in decision engines."},
            {"type": "product_change", "description": "Halt all unsupervised autonomous product launches until internal compliance sign-off is achieved."}
        ],
        "fintech": [
            {"type": "product_change", "description": "Redesign algorithmic flows to include manual review queues for edge-case approvals."},
            {"type": "policy_update", "description": "Publish updated algorithmic transparency guides to users."},
            {"type": "process_change", "description": "Establish weekly bias-testing sprints alongside standard QA."}
        ]
    }
    
    base_actions = actions.get(ind, actions.get("banking"))
    
    if risk["risk_level"] == "HIGH":
        base_actions.insert(0, {
            "type": "process_change",
            "description": "⚠️ URGENT: Establish cross-functional war room with CRO/CTO to address HIGH-RISK regulatory exposure — target 15-day response."
        })
    
    return base_actions[:6]

def generate_insights(industry: str, risk: dict, parsed: dict) -> dict:
    """Agent 7: Reporter Agent"""
    return {
        "key_statistics": [
            "Industry studies suggest 67% of institutions underestimate initial oversight compliance costs by 2–3x.",
            "Reports indicate that automated drift monitoring reduces regulatory breach incidents by 45%.",
            f"Regulatory data shows 1 in 5 {industry} firms face restrictions due to unvalidated system deployments."
        ],
        "non_compliance_risks": [
            "Immediate suspension of new product pipeline and service launches.",
            "Class-action liabilities stemming from algorithmic bias.",
            "Fines scaling up to multi-crore penalities depending on business impact."
        ],
        "industry_specific_effect": [
            f"Accelerates {industry} transformation toward robust 'Trusted' autonomous systems.",
            "Creates competitive moat for large entities that can absorb validation overhead."
        ],
    }

class ComplianceRequest(BaseModel):
    regulation_text: str
    industry: str
    company_name: Optional[str] = "Your Organization"

class ChatRequest(BaseModel):
    message: str
    industry: Optional[str] = "corporate"

@app.post("/analyze")
async def analyze_compliance(req: ComplianceRequest):
    industry = req.industry.lower().strip()
    
    # 8-Agent Execution Flow
    # 1 & 2: Parser
    parsed = parse_regulation(req.regulation_text)
    # 3: Industry
    industry_data = industry_agent(industry, parsed)
    # 4: Risk
    risk = risk_agent(req.regulation_text)
    # 5: Impact
    impact = impact_agent(industry)
    # 6: Policy
    policies = policy_agent(industry)
    # 7: Action
    actions = action_agent(risk["level"])
    # 8: Report Build
    report = report_agent({
        "industry": industry.upper(),
        "authority": parsed["authority"],
        "parsed": parsed,
        "risk": risk,
        "impact": impact,
        "policies": policies,
        "actions": actions
    })

    # Compatibility shim for existing frontend
    shim = {
        "risk_analysis": {
            "risk_level": report["risk_analysis"]["risk_level"],
            "reason": report["risk_analysis"]["reason"]
        },
        "impact_analysis": report["business_impact"],
        "policies_affected": report["affected_policies"],
        "action_items": [{"type": "system_change", "description": a["action"]} for a in report["action_plan"]],
        "compliance_insights": {
            "key_statistics": ["67% institutions underestimate cost", "Process automation reduces risk by 45%"],
            "non_compliance_risks": report["compliance_risks"]
        },
        "industry": industry,
        "full_report": report # The new strict JSON
    }
    
    # Persistence: Save to SQLite using context manager (auto-closes, prevents leaks)
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "INSERT INTO compliance_history (doc_name, date, industry, risk_level, full_report) VALUES (?, ?, ?, ?, ?)",
                (f"{parsed['authority']} circular",
                 datetime.datetime.now().strftime("%Y-%m-%d"),
                 industry.upper(),
                 report["risk_analysis"]["risk_level"],
                 json.dumps(report))
            )
            conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")

    return shim

@app.get("/history")
async def get_history():
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()
            c.execute("SELECT doc_name, date, industry, risk_level, full_report FROM compliance_history ORDER BY id DESC LIMIT 10")
            rows = c.fetchall()
        history = []
        for r in rows:
            history.append({
                "doc_name": r[0],
                "date": r[1],
                "industry": r[2],
                "risk_level": r[3],
                "full_report": json.loads(r[4])
            })
        return history
    except Exception as e:
        print(f"History fetch error: {e}")
        return []

@app.get("/stats")
async def get_stats():
    """Real analytics endpoint — feeds the analytics.html dashboard from live DB data."""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()

            # Industry breakdown (orders pie chart)
            c.execute("SELECT industry, COUNT(*) FROM compliance_history GROUP BY industry ORDER BY COUNT(*) DESC LIMIT 7")
            ind_rows = c.fetchall()
            industry_labels = [r[0] for r in ind_rows]
            industry_counts  = [r[1] for r in ind_rows]
            # Normalise to percentages for doughnut chart
            total_ind = sum(industry_counts) or 1
            industry_pct = [round(v / total_ind * 100, 2) for v in industry_counts]

            # Risk level breakdown (annual bar chart reused as risk bar)
            c.execute("SELECT risk_level, COUNT(*) FROM compliance_history GROUP BY risk_level ORDER BY risk_level")
            risk_rows = c.fetchall()
            risk_labels = [r[0] for r in risk_rows]
            risk_counts  = [r[1] for r in risk_rows]

            # Monthly analysis count for the last 7 recorded months (line chart)
            c.execute("""
                SELECT substr(date,1,7) AS month, COUNT(*)
                FROM compliance_history
                GROUP BY month
                ORDER BY month DESC
                LIMIT 7
            """)
            monthly_rows = list(reversed(c.fetchall()))
            monthly_labels = [r[0] for r in monthly_rows]
            monthly_counts  = [r[1] for r in monthly_rows]

            # Top industries by analysis count (ranking bar)
            c.execute("""
                SELECT industry, COUNT(*) as cnt
                FROM compliance_history
                GROUP BY industry
                ORDER BY cnt DESC
                LIMIT 24
            """)
            rank_rows = c.fetchall()
            rank_labels = [r[0] for r in rank_rows]
            rank_counts  = [r[1] for r in rank_rows]

        return {
            "annualSales":   {"labels": risk_labels,    "data": risk_counts},
            "monthlyReturn": {"labels": monthly_labels, "data": monthly_counts},
            "orders":        {"labels": industry_labels, "data": industry_pct},
            "ranking":       {"labels": rank_labels,    "data": rank_counts}
        }
    except Exception as e:
        print(f"Stats error: {e}")
        # Graceful fallback so the page still renders
        return {
            "annualSales":   {"labels": ["No Data"], "data": [0]},
            "monthlyReturn": {"labels": ["No Data"], "data": [0]},
            "orders":        {"labels": ["No Data"], "data": [100]},
            "ranking":       {"labels": ["No Data"], "data": [0]}
        }

@app.post("/chat")
async def chat_interaction(req: ChatRequest):
    msg = req.message
    ind = req.industry.lower()

    # --- Groq LLM path (active when GROQ_API_KEY is set) ---
    if groq_client:
        try:
            system_prompt = (
                f"You are ComplianceOS Copilot, an expert AI assistant specialised in regulatory compliance "
                f"for the {ind.upper()} sector in India. You help teams understand RBI, SEBI, IRDAI, MCA, and "
                f"other mandates. Be concise (3-5 sentences), professional, and actionable."
            )
            completion = groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": msg}
                ],
                max_tokens=300,
                temperature=0.4
            )
            return {"reply": completion.choices[0].message.content.strip()}
        except Exception as e:
            print(f"Groq chat error: {e}")
            # Fall through to rule-based fallback

    # --- Rule-based fallback (no API key or Groq timeout) ---
    msg_lower = msg.lower()
    if "penalty" in msg_lower or "fine" in msg_lower or "risk" in msg_lower:
        response = f"Based on {ind.upper()} mandates, non-compliance carries severe operational risk. Priority is usually given to halting unauthorized deployments immediately."
    elif "how" in msg_lower and "implement" in msg_lower:
        response = f"Implementation in {ind} typically requires cross-functional coordination. Start by forming a dedicated Ethics/Compliance review board and schedule Phase 1 audits."
    elif "policy" in msg_lower or "document" in msg_lower:
        response = "Affected policies generally include your internal API Governance, Data Privacy, and AI Ethics schemas. I recommend mapping current workflows before rewriting rules."
    elif "cost" in msg_lower or "budget" in msg_lower or "financ" in msg_lower:
        response = "Historically, unexpected compliance mandates incur 15-20% baseline operational overhead. Tech integrations typically consume the largest budget share."
    elif "hello" in msg_lower or "hi" in msg_lower:
        response = f"Hello! How can I assist you with your {ind.upper()} compliance implementation today?"
    else:
        response = "I understand you're navigating complex regulatory shifts. Could you clarify your specific technical or legal concern? For example, ask me 'how to implement policy' or 'what is the penalty risk'."

    return {"reply": response}

@app.get("/")
async def root():
    html_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    return {"message": "System Operational"}

@app.get("/analytics")
async def analytics_dashboard():
    analytics_path = os.path.join(BASE_DIR, "analytics.html")
    return FileResponse(analytics_path, media_type="text/html")

@app.get("/mock_api.js")
async def serve_mock_api():
    mock_path = os.path.join(BASE_DIR, "mock_api.js")
    return FileResponse(mock_path, media_type="application/javascript")

@app.get("/feed")
async def realtime_feed():
    feed_path = os.path.join(BASE_DIR, "realtime_feed.html")
    return FileResponse(feed_path, media_type="text/html")
