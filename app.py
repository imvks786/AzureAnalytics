from fastapi import FastAPI, Request, HTTPException, Form, Body, Depends
from fastapi.responses import HTMLResponse, Response, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
import uuid
import pymssql
import json
from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

templates = Jinja2Templates(directory="templates")

app = FastAPI(title="Analytics API")
app.mount("/static", StaticFiles(directory="static"), name="static")
# ---------------- CORS ----------------
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Session
app.add_middleware(
    SessionMiddleware,
    secret_key="SUPER_SECRET_SESSION_KEY"
)

#---------------- OAUTH ----------------
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
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
            PropertyName NVARCHAR(200),
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

        cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' and xtype='U')
        CREATE TABLE users (
            id INT IDENTITY PRIMARY KEY,
            email NVARCHAR(200) UNIQUE,
            name NVARCHAR(200),
            picture NVARCHAR(500),
            created_at DATETIME2 DEFAULT SYSUTCDATETIME()
        )
        """)
        cur.execute("""
        IF COL_LENGTH('sites', 'user_id') IS NULL
            ALTER TABLE sites ADD user_id INT
        """)
        cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.foreign_keys fk
            JOIN sys.tables t ON fk.parent_object_id = t.object_id
            WHERE t.name = 'sites' AND fk.name = 'FK_sites_users'
        )
        BEGIN
            IF COL_LENGTH('sites', 'user_id') IS NOT NULL AND OBJECT_ID('users') IS NOT NULL
                ALTER TABLE sites ADD CONSTRAINT FK_sites_users FOREIGN KEY (user_id) REFERENCES users(id)
        END
        """)

        conn.commit()
    finally:
        conn.close()

init_db()

def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

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

# ---------------- INDEX UI ----------------
@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    # Render index.html
    return templates.TemplateResponse("index.html", {"request": request})

#---------------- OAUTH ROUTES ----------------
@app.get("/login/google")
async def login_google(request: Request):
    redirect_uri = request.url_for("auth_google")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def auth_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = token.get("userinfo")

    # Insert user into DB if not already present and capture the user id
    user_id = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (user["email"],))
        row = cur.fetchone()
        if row:
            user_id = row[0]
        else:
            cur.execute(
                "INSERT INTO users (email, name, picture) VALUES (%s, %s, %s)",
                (user["email"], user["name"], user["picture"])
            )
            conn.commit()
            cur.execute("SELECT id FROM users WHERE email=%s", (user["email"],))
            fetched = cur.fetchone()
            user_id = fetched[0] if fetched else None
    except Exception as e:
        # Don't block the auth flow if DB insert fails
        print("Warning: failed to upsert user:", e)
    finally:
        try:
            conn.close()
        except:
            pass

    # Save user info in session and include user_id inside the user object
    request.session["user"] = {
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture"]
    }
    if user_id:
        request.session["user"]["user_id"] = user_id
        request.session["user_id"] = user_id

    return RedirectResponse(url="/CreateSite")

#---------------- Create Site UI ----------------
@app.get("/CreateSite", response_class=HTMLResponse)
async def read_index(request: Request):
    # Check session
    user = request.session.get("user")  
    # user saved in session after Google login
    return templates.TemplateResponse(
        "create_site.html",
        {
            "request": request,
            "user": user  # pass user info to template
        }
    )

#---------------- API ENDPOINTS ----------------
@app.post("/getCode")
def add_site(request: Request, site_name: str = Form(...), domain: str = Form(...), propertyName: str = Form(...)):
    site_id = uuid.uuid4().hex[:8]
    user_id = request.session["user"]["user_id"]
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        if not user_id:
            # not authenticated — instruct client to re-login
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Debug print
        print("Inserting site with user_id:", user_id)
        
        cur.execute(
            "INSERT INTO sites (site_id, site_name, domain, PropertyName, user_id) VALUES (%s, %s, %s, %s, %s)",
            (site_id, site_name, domain, propertyName, user_id)
        )
        conn.commit()
    finally:
        conn.close()

    return {"site_id": site_id,"user_id": user_id}

# ---------------- Dashboard UI ----------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = request.session.get("user")

    conn = get_connection()
    cur = conn.cursor()

    # Fetch all sites for this user
    cur.execute("SELECT site_name, domain FROM sites WHERE user_id=%s", (user["user_id"],))
    fetched = cur.fetchall()  # returns list of tuples

    # Convert to list of dicts for template
    data = [{"site_name": row[0], "domain": row[1]} for row in fetched] if fetched else []

    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request,
            "user": user,
            "data": data
        }
    )
#---------------- Event Collection ----------------
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

#---------------- Realtime metrics ----------------
@app.get("/api/realtime")
def realtime_metrics(request: Request):
    """Return aggregated realtime metrics for the current user's sites."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # get site ids owned by this user
        cur.execute("SELECT site_id FROM sites WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        site_ids = [r[0] for r in rows]

        if not site_ids:
            return {
                "activeUsers": 0,
                "pageViews": 0,
                "avgDuration": 0,
                "bounceRate": 0,
                "timeseries": {"labels": [], "values": []},
                "trafficSources": {},
                "topPages": []
            }

        placeholders = ",".join(["%s"] * len(site_ids))

        # active users right now (last 5 minutes)
        # sql = f"SELECT COUNT(DISTINCT visitor_id) FROM events WHERE site_id IN ({placeholders}) AND created_at >= DATEADD(minute, -5, SYSUTCDATETIME())"
        sql = f"SELECT COUNT(DISTINCT visitor_id) FROM events WHERE site_id IN ({placeholders})"
        cur.execute(sql, tuple(site_ids))
        active_users = cur.fetchone()[0] or 0

        # page views last 30 minutes
        # sql = f"SELECT COUNT(*) FROM events WHERE site_id IN ({placeholders}) AND event_type=%s AND created_at >= DATEADD(minute, -30, SYSUTCDATETIME())"
        sql = f"SELECT COUNT(*) FROM events WHERE site_id IN ({placeholders}) AND event_type=%s"
        params = tuple(site_ids) + ("page_view",)
        cur.execute(sql, params)
        page_views = cur.fetchone()[0] or 0

        # average session duration in seconds (approx) over last 30 minutes
        # sql = f"SELECT visitor_id, MIN(created_at) as min_ts, MAX(created_at) as max_ts FROM events WHERE site_id IN ({placeholders}) AND created_at >= DATEADD(minute, -30, SYSUTCDATETIME()) GROUP BY visitor_id"
        sql = f"SELECT visitor_id, MIN(created_at) as min_ts, MAX(created_at) as max_ts FROM events WHERE site_id IN ({placeholders}) GROUP BY visitor_id"
        cur.execute(sql, tuple(site_ids))
        sessions = cur.fetchall()
        durations = []
        for v in sessions:
            min_ts = v[1]
            max_ts = v[2]
            if min_ts and max_ts:
                diff = (max_ts - min_ts).total_seconds()
                durations.append(diff)
        avg_duration = int(sum(durations) / len(durations)) if durations else 0

        # bounce rate (visitors with only 1 event in window)
        total_visitors = len(sessions)
        bounce_visitors = sum(1 for v in sessions if v and v[1] == v[2])
        bounce_rate = round((bounce_visitors / total_visitors) * 100, 1) if total_visitors else 0

        # timeseries - active users per minute for last 30 minutes
        labels = []
        values = []
        now = datetime.utcnow()
        for i in range(30, -1, -1):
            start = now - timedelta(minutes=i)
            end = start + timedelta(minutes=1)
            # sql = f"SELECT COUNT(DISTINCT visitor_id) FROM events WHERE site_id IN ({placeholders}) AND created_at >= %s AND created_at < %s"
            sql = f"SELECT COUNT(DISTINCT visitor_id) FROM events WHERE site_id IN ({placeholders})"
            params = tuple(site_ids) + (start, end)
            cur.execute(sql, params)
            val = cur.fetchone()[0] or 0
            labels.append(start.strftime('%H:%M'))
            values.append(val)

        # traffic sources (simple classification based on referrer)
        sql = f"SELECT referrer, COUNT(*) as cnt FROM events WHERE site_id IN ({placeholders}) GROUP BY referrer"
        cur.execute(sql, tuple(site_ids))
        ref_rows = cur.fetchall()
        sources = {"Direct": 0, "Organic": 0, "Social": 0, "Referral": 0, "Email": 0}
        for r in ref_rows:
            ref = r[0] or ''
            cnt = r[1]
            ref_low = ref.lower()
            if not ref:
                sources["Direct"] += cnt
            elif any(k in ref_low for k in ["google", "bing", "yahoo"]):
                sources["Organic"] += cnt
            elif any(k in ref_low for k in ["facebook", "twitter", "instagram", "linkedin", "t.co"]):
                sources["Social"] += cnt
            elif "mailto:" in ref_low or "email" in ref_low:
                sources["Email"] += cnt
            else:
                sources["Referral"] += cnt

        # top pages
        # sql = f"SELECT page_url, COUNT(*) as views, COUNT(DISTINCT visitor_id) as users FROM events WHERE site_id IN ({placeholders}) AND created_at >= DATEADD(minute, -30, SYSUTCDATETIME()) GROUP BY page_url ORDER BY views DESC"
        sql = f"SELECT page_url, COUNT(*) as views, COUNT(DISTINCT visitor_id) as users FROM events WHERE site_id IN ({placeholders}) GROUP BY page_url ORDER BY views DESC"
        cur.execute(sql, tuple(site_ids))
        pages = cur.fetchall()
        top_pages = []
        for p in pages[:10]:
            top_pages.append({"url": p[0], "views": p[1], "users": p[2]})

        return {
            "activeUsers": active_users,
            "pageViews": page_views,
            "avgDuration": avg_duration,
            "bounceRate": bounce_rate,
            "timeseries": {"labels": labels, "values": values},
            "trafficSources": sources,
            "topPages": top_pages
        }

    finally:
        conn.close()


#---------------- Event counts by name ----------------
@app.get("/api/event_counts")
def event_counts(request: Request):
    """Return counts of events grouped by event_type for user's sites. Accepts optional ?minutes=<n> (default 30)."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    minutes = 30
    try:
        if "minutes" in request.query_params:
            minutes = int(request.query_params.get("minutes", 30))
    except Exception:
        minutes = 30

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT site_id FROM sites WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        site_ids = [r[0] for r in rows]
        if not site_ids:
            return {"counts": []}

        placeholders = ",".join(["%s"] * len(site_ids))
        # sql = f"SELECT event_type, COUNT(*) as cnt FROM events WHERE site_id IN ({placeholders}) AND created_at >= DATEADD(minute, -%s, SYSUTCDATETIME()) GROUP BY event_type ORDER BY cnt DESC"
        sql = f"SELECT event_type, COUNT(*) as cnt FROM events WHERE site_id IN ({placeholders}) GROUP BY event_type ORDER BY cnt DESC"
        params = tuple(site_ids) + (minutes,)
        cur.execute(sql, params)
        rows = cur.fetchall()

        # ensure common event types are present with zero count if missing
        common = ["page_view", "click", "form_start", "scroll", "session_start", "user_engagement"]
        counts = {r[0]: r[1] for r in rows}
        result = []
        # add existing counts first (ordered by count desc)
        ordered = sorted(counts.items(), key=lambda x: -x[1])
        for k, v in ordered:
            result.append({"event": k, "count": v})
        # then ensure common types exist in result
        for c in common:
            if c not in counts:
                result.append({"event": c, "count": 0})

        return {"counts": result}
    finally:
        conn.close()
#---------------- Logout ----------------
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}

#---------------- Session debug ----------------
@app.get("/session")
def session_info(request: Request):
    """Return all session data as JSON for debugging."""
    try:
        session_data = dict(request.session)
    except Exception:
        # request.session may not be serializable directly in some cases
        session_data = {k: str(v) for k, v in request.session.items()}

    # print to server console for quick debugging
    print("Session dump:", session_data)

    return {"session": session_data}

#---------------- Serve track.js ----------------
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

#---------------- Run the app ----------------