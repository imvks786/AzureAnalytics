from fastapi import FastAPI, Request, HTTPException, Form, Body
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
import os
import uuid
import pymssql
import json
from dotenv import load_dotenv

load_dotenv()

templates = Jinja2Templates(directory="templates")

app = FastAPI(title="Analytics API")
app.mount("/static", StaticFiles(directory="static"), name="static")
# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- DB CONNECTION ----------------
def get_connection():
    return pymssql.connect(
        server=os.getenv("AZURE_SQL_SERVER"),   
        user=os.getenv("AZURE_SQL_USER"),     
        password=os.getenv("AZURE_SQL_PASSWORD"),
        database=os.getenv("AZURE_SQL_DB"),
        port=1433,
        timeout=5
    )

# ---------------- INIT DB ----------------
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='sites' and xtype='U')
        CREATE TABLE sites (
            id INT IDENTITY PRIMARY KEY,
            site_id NVARCHAR(100) UNIQUE,
            site_name NVARCHAR(200),
            domain NVARCHAR(200),
            created_at DATETIME2 DEFAULT SYSUTCDATETIME()
        )
        """)

        cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='visitors' and xtype='U')
        CREATE TABLE visitors (
            id BIGINT IDENTITY PRIMARY KEY,
            visitor_id NVARCHAR(100),
            site_id NVARCHAR(100),
            first_seen DATETIME2 DEFAULT SYSUTCDATETIME(),
            last_seen DATETIME2,
            UNIQUE(visitor_id, site_id)
        )
        """)

        cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='events' and xtype='U')
        CREATE TABLE events (
            id BIGINT IDENTITY PRIMARY KEY,
            site_id NVARCHAR(100),
            visitor_id NVARCHAR(100),
            event_type NVARCHAR(50),
            page_url NVARCHAR(MAX),
            referrer NVARCHAR(MAX),
            user_agent NVARCHAR(MAX),
            ip_address NVARCHAR(50),
            language NVARCHAR(20),
            platform NVARCHAR(50),
            screen_size NVARCHAR(20),
            timezone NVARCHAR(50),
            created_at DATETIME2 DEFAULT SYSUTCDATETIME()
        )
        """)

        conn.commit()
    finally:
        conn.close()

init_db()

# ---------------- MODELS ----------------
class CollectEvent(BaseModel):
    siteId: str
    visitorId: str
    pageUrl: str
    referrer: str | None = None
    userAgent: str
    language: str | None = None
    platform: str | None = None
    screenSize: str | None = None
    timezone: str | None = None
    timestamp: str

# ---------------- HEALTH ----------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    # Render index.html
    return templates.TemplateResponse("index.html", {"request": request})

# ---------------- ADMIN UI ----------------
@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return """
    <h2>Add Website</h2>
    <form method="post">
      <input name="site_name" placeholder="Site Name" required><br><br>
      <input name="domain" placeholder="example.com" required><br><br>
      <button>Add</button>
    </form>
    """

@app.post("/getCode")
def add_site(site_name: str = Form(...), domain: str = Form(...), propertyName: str = Form(...)):
    site_id = uuid.uuid4().hex[:8]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO sites (site_id, site_name, domain, PropertyName) VALUES (%s, %s, %s, %s)",
            (site_id, site_name, domain, propertyName)
        )
        conn.commit()
    finally:
        conn.close()

    return {"site_id": site_id}

@app.post("/collect")
async def collect(request: Request):
    data = await request.json()

    site_id = data.get("siteId")
    visitor_id = data.get("visitorId")

    if not site_id or not visitor_id:
        raise HTTPException(status_code=400, detail="Invalid payload")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # validate site
        cur.execute("SELECT 1 FROM sites WHERE site_id=%s", (site_id,))
        if not cur.fetchone():
            raise HTTPException(400, "Invalid site_id")

        # visitor upsert
        cur.execute("""
        IF EXISTS (SELECT 1 FROM visitors WHERE visitor_id=%s AND site_id=%s)
            UPDATE visitors SET last_seen=SYSUTCDATETIME()
            WHERE visitor_id=%s AND site_id=%s
        ELSE
            INSERT INTO visitors (visitor_id, site_id)
            VALUES (%s, %s)
        """, (
            visitor_id, site_id,
            visitor_id, site_id,
            visitor_id, site_id
        ))

        # insert event
        cur.execute("""
        INSERT INTO events (
            site_id, visitor_id, event_type,
            page_url, referrer, user_agent, ip_address,
            language, platform, screen_size, timezone,
            clicked_url, is_external
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            site_id,
            visitor_id,
            data.get("eventType", "page_view"),
            data.get("pageUrl"),
            data.get("referrer"),
            data.get("userAgent"),
            request.client.host,
            data.get("language"),
            data.get("platform"),
            data.get("screenSize"),
            data.get("timezone"),
            data.get("clicked_url"),      # <-- must exist
            data.get("is_external")       # <-- must exist
        ))
        conn.commit()

    finally:
        conn.close()

    return {"status": "ok"}


@app.get("/track.js")
def track_js():
    return FileResponse(
        path="static/track.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )








