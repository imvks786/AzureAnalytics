from fastapi import FastAPI, Request, HTTPException, Form, Body, Depends
from fastapi.responses import HTMLResponse, Response, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
import uuid
import pymysql
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
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),      # user@servername
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
        port=3306,
        connect_timeout=5,
        autocommit=True,
        ssl={"ssl": {}}   # 🔐 SSL ENABLED
    )

# ---------------- INIT DB ----------------
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    try:
        # create users first so FK in sites can reference it
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(200) UNIQUE,
            name VARCHAR(200),
            picture VARCHAR(500),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(100) UNIQUE,
            site_name VARCHAR(200),
            domain VARCHAR(200),
            PropertyName VARCHAR(200),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id INT,
            INDEX (user_id),
            CONSTRAINT FK_sites_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            visitor_id VARCHAR(100),
            site_id VARCHAR(100),
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_visitor_site (visitor_id, site_id)
        ) ENGINE=InnoDB
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(100),
            visitor_id VARCHAR(100),
            event_type VARCHAR(50),
            page_url TEXT,
            referrer TEXT,
            user_agent TEXT,
            ip_address VARCHAR(50),
            language VARCHAR(20),
            platform VARCHAR(50),
            screen_size VARCHAR(20),
            timezone VARCHAR(50),
            clicked_url TEXT,
            is_external TINYINT(1),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX (site_id),
            INDEX (visitor_id),
            INDEX (created_at)
        ) ENGINE=InnoDB
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS TechStack (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(100),
            Browser VARCHAR(100),
            BrowserVersion VARCHAR(50),
            DeviceCat VARCHAR(50),
            ScreenRes VARCHAR(50),
            Platform VARCHAR(50),
            OS VARCHAR(50),
            OSVersion VARCHAR(50),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX (site_id)
        ) ENGINE=InnoDB
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS site_access (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(100),
            user_id INT,
            role VARCHAR(50) DEFAULT 'admin',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_access (site_id, user_id),
            CONSTRAINT FK_access_site FOREIGN KEY (site_id) REFERENCES sites(site_id) ON DELETE CASCADE,
            CONSTRAINT FK_access_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
        """)

        conn.commit()
    finally:
        conn.close()

init_db()

# ---------------- HELPERS ----------------
def get_user_sites_sql():
    # Helper SQL clause to find sites user owns OR has access to
    # returns clause and params must be handled by caller
    pass

def get_authorized_site_ids(user_id):
    """Returns a list of site_ids that the user owns or has access to."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Sites owned
        cur.execute("SELECT site_id FROM sites WHERE user_id=%s", (user_id,))
        owned = [r[0] for r in cur.fetchall()]
        
        # Sites shared
        cur.execute("SELECT site_id FROM site_access WHERE user_id=%s", (user_id,))
        shared = [r[0] for r in cur.fetchall()]
        
        return list(set(owned + shared))
    finally:
        conn.close()

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
    user = request.session.get("user")
    # Render index.html
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

#---------------- OAUTH ROUTES ----------------
@app.get("/login/google")
async def login_google(request: Request):
    redirect_uri = request.url_for("auth_google")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
    if GOOGLE_REDIRECT_URI:
        redirect_uri = GOOGLE_REDIRECT_URI
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
    if not user:
         return RedirectResponse(url="/")

    # Check if user already has sites
    user_id = request.session.get("user_id")
    if user_id:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM sites WHERE user_id=%s LIMIT 1", (user_id,))
            if cur.fetchone():
                return RedirectResponse(url="/dashboard")
        finally:
            conn.close()

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
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_connection()
    cur = conn.cursor()

    # Fetch all sites for this user
    # Fetch sites user owns OR has access to
    # We can do a UNION or join.
    sql = """
    SELECT s.site_name, s.domain, s.site_id, s.user_id, 'owner' as role 
    FROM sites s WHERE s.user_id=%s
    UNION
    SELECT s.site_name, s.domain, s.site_id, sa.site_id as owner_id, 'shared' as role
    FROM sites s 
    JOIN site_access sa ON s.site_id = sa.site_id 
    WHERE sa.user_id=%s
    """
    cur.execute(sql, (user_id, user_id))
    fetched = cur.fetchall()

    # Convert to list of dicts for template
    data = [{"site_name": row[0], "domain": row[1], "site_id": row[2]} for row in fetched] if fetched else []

    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request,
            "user": user,
            "data": data
        }
    )


# ---------------- Reports UI ----------------
@app.get("/reports/referrers", response_class=HTMLResponse)
def report_referrers(request: Request):
    user = request.session.get("user")
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # fetch sites for selector
    conn = get_connection()
    cur = conn.cursor()
    try:
        # REFACTOR: Fetch owned + shared sites
        sql_sites = """
        SELECT s.site_name, s.domain, s.site_id 
        FROM sites s WHERE s.user_id=%s
        UNION
        SELECT s.site_name, s.domain, s.site_id
        FROM sites s 
        JOIN site_access sa ON s.site_id = sa.site_id 
        WHERE sa.user_id=%s
        """
        cur.execute(sql_sites, (user_id, user_id))
        rows = cur.fetchall()
        sites = [{"site_name": r[0], "domain": r[1], "site_id": r[2]} for r in rows] if rows else []

        # optional site_id param (required to view referrers for a particular site)
        site_id = request.query_params.get("site_id")
        if not site_id:
            # render template with empty data and site list
            return templates.TemplateResponse("report.html", {"request": request, "user": user, "sites": sites, "selected_site": None, "referrers": [], "bounce_rate": None})

        # validate ownership
        if sites and site_id not in [s["site_id"] for s in sites]:
            raise HTTPException(status_code=400, detail="Invalid site_id")

        # optional date range filters: ?start=YYYY-MM-DD&end=YYYY-MM-DD
        start_q = request.query_params.get("start")
        end_q = request.query_params.get("end")

        where_clauses = ["site_id=%s"]
        params = [site_id]

        try:
            if start_q:
                # treat start as inclusive beginning of day
                start_dt = datetime.fromisoformat(start_q)
                where_clauses.append("created_at >= %s")
                params.append(start_dt)
            if end_q:
                # treat end as inclusive -> add one day and use < end_dt
                end_dt = datetime.fromisoformat(end_q) + timedelta(days=1)
                where_clauses.append("created_at < %s")
                params.append(end_dt)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        where_sql = " AND ".join(where_clauses)

        # fetch referrers grouped by referrer: total events and distinct visitors
        sql = f"SELECT referrer, COUNT(*) as ref_count, COUNT(DISTINCT visitor_id) as visitors FROM events WHERE {where_sql} GROUP BY referrer ORDER BY ref_count DESC"
        cur.execute(sql, tuple(params))
        ref_rows = cur.fetchall()
        referrers = []
        for r in ref_rows:
            ref = r[0] or ''
            label = ref if ref.strip() else 'Direct'
            referrers.append({"referrer": label, "count": int(r[1]), "visitors": int(r[2])})

        # compute bounce rate for the same range: visitors with only 1 event
        sql_vis = f"SELECT visitor_id, COUNT(*) as cnt FROM events WHERE {where_sql} GROUP BY visitor_id"
        cur.execute(sql_vis, tuple(params))
        visitor_counts = cur.fetchall()
        total_visitors = len(visitor_counts)
        bounce_visitors = sum(1 for v in visitor_counts if v[1] == 1)
        bounce_rate = round((bounce_visitors / total_visitors) * 100, 1) if total_visitors else 0

        return templates.TemplateResponse("report.html", {"request": request, "user": user, "sites": sites, "selected_site": site_id, "referrers": referrers, "bounce_rate": bounce_rate})
    finally:
        conn.close()

@app.get("/reports/tech", response_class=HTMLResponse)
def report_tech(request: Request):
    user = request.session.get("user")
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Fetch sites owned + shared
        cur.execute("SELECT site_id FROM sites WHERE user_id=%s UNION SELECT site_id FROM site_access WHERE user_id=%s", (user_id, user_id))
        rows = cur.fetchall()
        authorized_site_ids = [r[0] for r in rows]

        # Site Selection
        cur.execute("SELECT site_name, domain, site_id FROM sites WHERE user_id=%s UNION SELECT s.site_name, s.domain, s.site_id FROM sites s JOIN site_access sa ON s.site_id=sa.site_id WHERE sa.user_id=%s", (user_id, user_id))
        all_sites_rows = cur.fetchall()
        sites = [{"site_name": r[0], "domain": r[1], "site_id": r[2]} for r in all_sites_rows]

        site_id = request.query_params.get("site_id")
        if not site_id:
             # Default to first site if available, or just render empty
             if sites:
                 site_id = sites[0]["site_id"]
             else:
                 return templates.TemplateResponse("tech_details.html", {"request": request, "user": user, "sites": [], "selected_site": None})

        if site_id not in authorized_site_ids:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Filters
        start_q = request.query_params.get("start")
        end_q = request.query_params.get("end")
        
        where_clauses = ["site_id=%s"]
        params = [site_id]

        if start_q:
            start_dt = datetime.fromisoformat(start_q)
            where_clauses.append("created_at >= %s")
            params.append(start_dt)
        if end_q:
            end_dt = datetime.fromisoformat(end_q) + timedelta(days=1)
            where_clauses.append("created_at < %s")
            params.append(end_dt)
        
        where_sql = " AND ".join(where_clauses)
        
        # Aggregations
        data = {}
        
        # Browser
        cur.execute(f"SELECT Browser, COUNT(*) as cnt FROM TechStack WHERE {where_sql} GROUP BY Browser ORDER BY cnt DESC", tuple(params))
        data["browsers"] = [{"label": r[0], "count": r[1]} for r in cur.fetchall()]

        # OS
        cur.execute(f"SELECT OS, COUNT(*) as cnt FROM TechStack WHERE {where_sql} GROUP BY OS ORDER BY cnt DESC", tuple(params))
        data["os"] = [{"label": r[0], "count": r[1]} for r in cur.fetchall()]

        # Device Category
        cur.execute(f"SELECT DeviceCat, COUNT(*) as cnt FROM TechStack WHERE {where_sql} GROUP BY DeviceCat ORDER BY cnt DESC", tuple(params))
        data["devices"] = [{"label": r[0], "count": r[1]} for r in cur.fetchall()]

        # Screen Resolution
        cur.execute(f"SELECT ScreenRes, COUNT(*) as cnt FROM TechStack WHERE {where_sql} GROUP BY ScreenRes ORDER BY cnt DESC", tuple(params))
        data["screens"] = [{"label": r[0], "count": r[1]} for r in cur.fetchall()]

        return templates.TemplateResponse("tech_details.html", {"request": request, "user": user, "sites": sites, "selected_site": site_id, "data": data})

    finally:
        conn.close()
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

        # visitor upsert - use MySQL ON DUPLICATE KEY UPDATE
        cur.execute(
            """
            INSERT INTO visitors (visitor_id, site_id, last_seen)
            VALUES (%s, %s, NOW())
            ON DUPLICATE KEY UPDATE last_seen = NOW()
            """,
            (visitor_id, site_id)
        )

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
        # get authorized site ids
        cur.execute("SELECT site_id FROM sites WHERE user_id=%s UNION SELECT site_id FROM site_access WHERE user_id=%s", (user_id, user_id))
        rows = cur.fetchall()
        site_ids = [r[0] for r in rows]

        # allow optional site_id filter (validate it belongs to this user)
        site_param = request.query_params.get("site_id")
        if site_param:
            if site_param not in site_ids:
                raise HTTPException(status_code=400, detail="Invalid site_id")
            site_ids = [site_param]

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

        # compute time windows
        threshold_5 = datetime.utcnow() - timedelta(minutes=5)
        threshold_30 = datetime.utcnow() - timedelta(minutes=30)

        # active users right now (last 5 minutes)
        sql = f"SELECT COUNT(DISTINCT visitor_id) FROM events WHERE site_id IN ({placeholders}) AND created_at >= %s"
        cur.execute(sql, tuple(site_ids) + (threshold_5,))
        active_users = cur.fetchone()[0] or 0

        # page views last 30 minutes
        sql = f"SELECT COUNT(*) FROM events WHERE site_id IN ({placeholders}) AND event_type=%s AND created_at >= %s"
        params = tuple(site_ids) + ("page_view", threshold_30)
        cur.execute(sql, params)
        page_views = cur.fetchone()[0] or 0

        # average session duration in seconds (approx) over last 30 minutes
        sql = f"SELECT visitor_id, MIN(created_at) as min_ts, MAX(created_at) as max_ts FROM events WHERE site_id IN ({placeholders}) AND created_at >= %s GROUP BY visitor_id"
        cur.execute(sql, tuple(site_ids) + (threshold_30,))
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
            sql = f"SELECT COUNT(DISTINCT visitor_id) FROM events WHERE site_id IN ({placeholders}) AND created_at >= %s AND created_at < %s"
            params = tuple(site_ids) + (start, end)
            cur.execute(sql, params)
            val = cur.fetchone()[0] or 0
            labels.append(start.strftime('%H:%M'))
            values.append(val)

        # traffic sources (simple classification based on referrer, last 30 minutes)
        sql = f"SELECT referrer, COUNT(*) as cnt FROM events WHERE site_id IN ({placeholders}) AND created_at >= %s GROUP BY referrer"
        cur.execute(sql, tuple(site_ids) + (threshold_30,))
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

        # top pages (last 30 minutes)
        sql = f"SELECT page_url, COUNT(*) as views, COUNT(DISTINCT visitor_id) as users FROM events WHERE site_id IN ({placeholders}) AND created_at >= %s GROUP BY page_url ORDER BY views DESC"
        cur.execute(sql, tuple(site_ids) + (threshold_30,))
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
        cur.execute("SELECT site_id FROM sites WHERE user_id=%s UNION SELECT site_id FROM site_access WHERE user_id=%s", (user_id, user_id))
        rows = cur.fetchall()
        site_ids = [r[0] for r in rows]
        if not site_ids:
            return {"counts": []}

        # allow optional site filter via query param
        site_param = request.query_params.get("site_id")
        if site_param:
            if site_param not in site_ids:
                raise HTTPException(status_code=400, detail="Invalid site_id")
            site_ids = [site_param]

        placeholders = ",".join(["%s"] * len(site_ids))
        threshold_dt = datetime.utcnow() - timedelta(minutes=minutes)
        sql = f"SELECT event_type, COUNT(*) as cnt FROM events WHERE site_id IN ({placeholders}) AND created_at >= %s GROUP BY event_type ORDER BY cnt DESC"
        params = tuple(site_ids) + (threshold_dt,)
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
    return RedirectResponse(url="/")

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

# ---------------- Settings UI ----------------
@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    user = request.session.get("user")
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Fetch sites owned by user (they can rename these)
        cur.execute("SELECT site_name, domain, site_id, PropertyName FROM sites WHERE user_id=%s", (user_id,))
        owned_rows = cur.fetchall()
        owned_sites = [{"site_name": r[0], "domain": r[1], "site_id": r[2], "PropertyName": r[3]} for r in owned_rows]

        # Fetch authorized users for each owned site
        for site in owned_sites:
             cur.execute("""
                SELECT u.email, u.name, sa.role, u.id 
                FROM site_access sa 
                JOIN users u ON sa.user_id = u.id 
                WHERE sa.site_id=%s
             """, (site["site_id"],))
             site["admins"] = [{"email": r[0], "name": r[1], "role": r[2], "user_id": r[3]} for r in cur.fetchall()]

        return templates.TemplateResponse("settings.html", {"request": request, "user": user, "sites": owned_sites})
    finally:
        conn.close()

@app.post("/settings/update")
async def update_site_settings(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    form = await request.form()
    site_id = form.get("site_id")
    site_name = form.get("site_name")
    property_name = form.get("property_name")

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Verify ownership
        cur.execute("SELECT 1 FROM sites WHERE site_id=%s AND user_id=%s", (site_id, user_id))
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="Not authorized to edit this site")
        
        cur.execute("UPDATE sites SET site_name=%s, PropertyName=%s WHERE site_id=%s", (site_name, property_name, site_id))
        conn.commit()
    finally:
        conn.close()
    
    return RedirectResponse(url="/settings", status_code=303)

@app.post("/settings/access/add")
async def add_site_access(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    form = await request.form()
    site_id = form.get("site_id")
    email = form.get("email")

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Verify ownership
        cur.execute("SELECT 1 FROM sites WHERE site_id=%s AND user_id=%s", (site_id, user_id))
        if not cur.fetchone():
             raise HTTPException(status_code=403, detail="Not authorized")

        # Find or create user
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        row = cur.fetchone()
        if row:
            target_user_id = row[0]
        else:
            # Create shadow user
            cur.execute("INSERT INTO users (email, name, picture) VALUES (%s, %s, %s)", (email, email.split('@')[0], None))
            conn.commit()
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            target_user_id = cur.fetchone()[0]

        # Prevent adding self
        if target_user_id == user_id:
             return RedirectResponse(url="/settings", status_code=303)

        # Add access
        try:
            cur.execute("INSERT INTO site_access (site_id, user_id) VALUES (%s, %s)", (site_id, target_user_id))
            conn.commit()
        except pymysql.err.IntegrityError:
            pass # Already exists

    finally:
        conn.close()

    return RedirectResponse(url="/settings", status_code=303)

@app.post("/settings/access/remove")
async def remove_site_access(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    form = await request.form()
    site_id = form.get("site_id")
    target_user_id = form.get("user_id")

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Verify ownership
        cur.execute("SELECT 1 FROM sites WHERE site_id=%s AND user_id=%s", (site_id, user_id))
        if not cur.fetchone():
             raise HTTPException(status_code=403, detail="Not authorized")
        
        cur.execute("DELETE FROM site_access WHERE site_id=%s AND user_id=%s", (site_id, target_user_id))
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url="/settings", status_code=303)
