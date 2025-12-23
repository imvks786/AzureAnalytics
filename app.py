from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
import pyodbc
from dotenv import load_dotenv
import uuid

load_dotenv()

app = FastAPI(title="Analytics API")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# --- DB Connection ---
def get_connection():
    driver = os.getenv("AZURE_SQL_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("AZURE_SQL_SERVER")
    database = os.getenv("AZURE_SQL_DB")
    uid = os.getenv("AZURE_SQL_USER")
    pwd = os.getenv("AZURE_SQL_PASSWORD")
    encrypt = os.getenv("AZURE_SQL_ENCRYPT", "yes")
    trust_server_cert = os.getenv("AZURE_SQL_TRUST_SERVER_CERT", "no")

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};DATABASE={database};UID={uid};PWD={pwd};"
        f"Encrypt={encrypt};TrustServerCertificate={trust_server_cert};"
    )
    return pyodbc.connect(conn_str)

# --- Initialize DB ---
def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Sites
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
        # Visitors
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
        # Events
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

# --- Pydantic model ---
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

# --- Health check ---
@app.get("/health")
def health():
    return {"status": "ok"}

# --- Admin HTML page to add sites ---
@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    html_content = """
    <html>
        <head><title>Add Site</title></head>
        <body>
            <h2>Add New Website</h2>
            <form action="/admin" method="post">
                <label>Site Name:</label><br>
                <input type="text" name="site_name" required><br><br>
                <label>Domain:</label><br>
                <input type="text" name="domain" required><br><br>
                <input type="submit" value="Add Site">
            </form>
        </body>
    </html>
    """
    return html_content

@app.post("/admin", response_class=HTMLResponse)
def add_site(site_name: str = Form(...), domain: str = Form(...)):
    site_id = uuid.uuid4().hex[:8]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sites (site_id, site_name, domain)
            VALUES (?, ?, ?)
        """, (site_id, site_name, domain))
        conn.commit()
    finally:
        conn.close()
    return f"""
    <html>
        <body>
            <h2>✅ Site added successfully!</h2>
            <p>Site Name: {site_name}</p>
            <p>Domain: {domain}</p>
            <p>Site ID: <b>{site_id}</b></p>
            <p>Include in your JS tracker:</p>
            <code>&lt;script src='https://yourdomain.com/track.js' data-site-id='{site_id}'&gt;&lt;/script&gt;</code>
            <br><br>
            <a href="/admin">Add another site</a>
        </body>
    </html>
    """

# --- Collect endpoint ---
@app.post("/collect")
def collect(event: CollectEvent, request: Request):
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Validate site
        cur.execute("SELECT 1 FROM sites WHERE site_id = ?", (event.siteId,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Invalid site_id")

        # Upsert visitor
        cur.execute("""
        MERGE visitors AS target
        USING (SELECT ? AS visitor_id, ? AS site_id) AS src
        ON target.visitor_id = src.visitor_id AND target.site_id = src.site_id
        WHEN MATCHED THEN
            UPDATE SET last_seen = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (visitor_id, site_id, first_seen)
            VALUES (src.visitor_id, src.site_id, SYSUTCDATETIME());
        """, (event.visitorId, event.siteId))

        # Insert event
        cur.execute("""
        INSERT INTO events (
            site_id, visitor_id, event_type,
            page_url, referrer, user_agent, ip_address,
            language, platform, screen_size, timezone
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

# --- Serve track.js ---
@app.get("/track.js")
def track_js():
    js_content = """
(function () {
  const SCRIPT = document.currentScript;
  const SITE_ID = SCRIPT.getAttribute("data-site-id");
  if (!SITE_ID || navigator.doNotTrack === "1") return;
  let vid = localStorage.getItem("_va_vid");
  if (!vid) {
    vid = crypto.randomUUID();
    localStorage.setItem("_va_vid", vid);
  }
  const payload = {
    siteId: SITE_ID,
    visitorId: vid,
    pageUrl: location.href,
    referrer: document.referrer,
    userAgent: navigator.userAgent,
    language: navigator.language,
    platform: navigator.platform,
    screenSize: `${screen.width}x${screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    timestamp: new Date().toISOString()
  };
  navigator.sendBeacon("/collect", JSON.stringify(payload));
})();
    """
    return Response(content=js_content, media_type="application/javascript")
