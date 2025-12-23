from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
import uuid
import pymssql
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Analytics API")

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

@app.post("/admin", response_class=HTMLResponse)
def add_site(site_name: str = Form(...), domain: str = Form(...)):
    site_id = uuid.uuid4().hex[:8]
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO sites (site_id, site_name, domain) VALUES (%s, %s, %s)",
            (site_id, site_name, domain)
        )
        conn.commit()
    finally:
        conn.close()

    return f"""
    <h3>✅ Site Added</h3>
    <p>Site ID: <b>{site_id}</b></p>
    <code>
    &lt;script src="https://YOURDOMAIN/track.js" data-site-id="{site_id}"&gt;&lt;/script&gt;
    </code>
    """

# ---------------- COLLECT ----------------
@app.post("/collect")
def collect(event: CollectEvent, request: Request):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM sites WHERE site_id=%s", (event.siteId,))
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
            event.visitorId, event.siteId,
            event.visitorId, event.siteId,
            event.visitorId, event.siteId
        ))

        # event insert
        cur.execute("""
        INSERT INTO events (
            site_id, visitor_id, event_type,
            page_url, referrer, user_agent, ip_address,
            language, platform, screen_size, timezone
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            event.siteId,
            event.visitorId,
            "page_view",
            event.pageUrl,
            event.referrer,
            event.userAgent,
            request.client.host,
            event.language,
            event.platform,
            event.screenSize,
            event.timezone
        ))

        conn.commit()
    finally:
        conn.close()

    return {"status": "ok"}

# ---------------- TRACK.JS ----------------
@app.get("/track.js")
def track_js():
    return Response("""
(function () {
  const s = document.currentScript;
  const siteId = s.getAttribute("data-site-id");
  if (!siteId) return;

  let vid = localStorage.getItem("_va_vid");
  if (!vid) {
    vid = crypto.randomUUID();
    localStorage.setItem("_va_vid", vid);
  }

  navigator.sendBeacon("/collect", JSON.stringify({
    siteId,
    visitorId: vid,
    pageUrl: location.href,
    referrer: document.referrer,
    userAgent: navigator.userAgent,
    language: navigator.language,
    platform: navigator.platform,
    screenSize: screen.width + "x" + screen.height,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    timestamp: new Date().toISOString()
  }));
})();
""", media_type="application/javascript")
