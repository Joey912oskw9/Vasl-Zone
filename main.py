import os
import json
import sqlite3
import secrets
import hashlib
import base64
import urllib.parse
import logging
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LuffyPanel")

app = FastAPI(title="Luffy Panel v2", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ─── دیتابیس ───────────────────────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "panel.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    uuid TEXT NOT NULL,
    protocol TEXT DEFAULT 'vless-ws',
    host TEXT DEFAULT '',
    port INTEGER DEFAULT 443,
    total_bytes INTEGER DEFAULT 0,
    used_bytes INTEGER DEFAULT 0,
    expiry_date TEXT,
    enabled INTEGER DEFAULT 1,
    config_type TEXT DEFAULT 'normal',
    last_reset TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    sub_id TEXT UNIQUE
)""")

c.execute("""CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""")

c.execute("INSERT OR IGNORE INTO settings VALUES ('password','admin')")
c.execute("INSERT OR IGNORE INTO settings VALUES ('domain','')")
c.execute("INSERT OR IGNORE INTO settings VALUES ('port','443')")
c.execute("INSERT OR IGNORE INTO settings VALUES ('session_token','')")
conn.commit()

# ─── توابع کمکی ────────────────────────────────────────────────────────────
def gen_uuid():
    h = secrets.token_hex(16)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fmt_bytes(b):
    if not b: return "0 B"
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    if b < 1024**3: return f"{b/1024**2:.2f} MB"
    return f"{b/1024**3:.2f} GB"

def get_setting(key, default=""):
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else default

def set_setting(key, value):
    c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
    conn.commit()

# ─── ساخت لینک کانفیگ ──────────────────────────────────────────────────────
def build_config(user):
    host = user["host"] or get_setting("domain", "localhost")
    port = user["port"] or int(get_setting("port", "443"))
    uuid = user["uuid"]
    email = user["email"]
    protos = user["protocol"].split(",")
    links = []
    
    for p in protos:
        p = p.strip()
        if p == "vless-ws":
            params = {"encryption":"none","security":"tls","type":"ws","host":host,
                      "path":f"/{uuid[:8]}","sni":host,"fp":"chrome","alpn":"http/1.1"}
            q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
            links.append(f"vless://{uuid}@{host}:{port}?{q}#{urllib.parse.quote(f'{email}-VLESS')}")
            
        elif p == "xhttp-packet":
            params = {"encryption":"none","security":"tls","type":"xhttp","mode":"packet-up",
                      "host":host,"path":f"/xp-{uuid[:8]}","sni":host,"fp":"chrome","alpn":"h2,http/1.1"}
            q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
            links.append(f"vless://{uuid}@{host}:{port}?{q}#{urllib.parse.quote(f'{email}-XHTTP-P')}")
            
        elif p == "xhttp-stream":
            params = {"encryption":"none","security":"tls","type":"xhttp","mode":"stream-up",
                      "host":host,"path":f"/xs-{uuid[:8]}","sni":host,"fp":"chrome","alpn":"h2,http/1.1"}
            q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
            links.append(f"vless://{uuid}@{host}:{port}?{q}#{urllib.parse.quote(f'{email}-XHTTP-S')}")
    
    sub = base64.b64encode("\n".join(links).encode()).decode()
    sub_url = f"/sub/{user['sub_id']}"
    
    return {"links": links, "subscription": sub, "sub_url": sub_url}

# ─── احراز هویت ────────────────────────────────────────────────────────────
def check_auth(session_token=""):
    return session_token == get_setting("session_token", "")

@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    pw = body.get("password", "")
    if pw == get_setting("password", "admin"):
        token = secrets.token_urlsafe(32)
        set_setting("session_token", token)
        resp = JSONResponse({"ok": True, "token": token})
        resp.set_cookie(key="session", value=token, max_age=86400*7)
        return resp
    return JSONResponse({"ok": False}, status_code=401)

@app.post("/api/logout")
async def logout():
    set_setting("session_token", "")
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp

@app.get("/api/me")
async def me(session: str = Cookie("")):
    return {"ok": check_auth(session)}

# ─── API: کانفیگ‌ها ────────────────────────────────────────────────────────
@app.get("/api/links")
async def get_links(session: str = Cookie("")):
    if not check_auth(session):
        raise HTTPException(401, "unauthorized")
    
    rows = c.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    cols = ["id","email","uuid","protocol","host","port","total_bytes","used_bytes",
            "expiry_date","enabled","config_type","last_reset","created_at","sub_id"]
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        configs = build_config(d)
        d["link"] = configs["links"][0] if configs["links"] else ""
        d["links"] = configs["links"]
        d["subscription"] = configs["subscription"]
        d["sub_url"] = configs["sub_url"]
        d["used_fmt"] = fmt_bytes(d["used_bytes"])
        d["total_fmt"] = fmt_bytes(d["total_bytes"]) if d["total_bytes"] else "♾"
        result.append(d)
    return {"links": result, "total": len(result)}

@app.post("/api/links")
async def create_link(request: Request, session: str = Cookie("")):
    if not check_auth(session):
        raise HTTPException(401, "unauthorized")
    
    body = await request.json()
    email = body.get("email", f"user_{secrets.token_hex(4)}")
    protocol = body.get("protocol", "vless-ws")
    volume_gb = body.get("volume_gb", 0)
    expiry_days = body.get("expiry_days", 0)
    host = body.get("host", "")
    port = body.get("port", 0)
    
    existing = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        return {"ok": False, "msg": "این ایمیل قبلاً ثبت شده"}
    
    uid = gen_uuid()
    user_uuid = gen_uuid()
    sub_id = secrets.token_hex(8)
    total_bytes = int(volume_gb * 1024**3) if volume_gb > 0 else 0
    expiry = None
    if expiry_days > 0:
        expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("""INSERT INTO users (id,email,uuid,protocol,host,port,total_bytes,expiry_date,sub_id)
                 VALUES (?,?,?,?,?,?,?,?,?)""",
              (uid, email, user_uuid, protocol, host, port, total_bytes, expiry, sub_id))
    conn.commit()
    
    user = {"email":email,"uuid":user_uuid,"protocol":protocol,"host":host,"port":port,"sub_id":sub_id}
    configs = build_config(user)
    
    return {"ok": True, "id": uid, "email": email, "link": configs["links"][0] if configs["links"] else "",
            "subscription": configs["subscription"], "sub_url": configs["sub_url"]}

@app.delete("/api/links/{uid}")
async def delete_link(uid: str, session: str = Cookie("")):
    if not check_auth(session):
        raise HTTPException(401, "unauthorized")
    c.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    return {"ok": True}

@app.put("/api/links/{uid}")
async def update_link(uid: str, request: Request, session: str = Cookie("")):
    if not check_auth(session):
        raise HTTPException(401, "unauthorized")
    
    existing = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not existing:
        raise HTTPException(404, "not found")
    
    body = await request.json()
    email = body.get("email", existing[1])
    protocol = body.get("protocol", existing[3])
    volume_gb = body.get("volume_gb", existing[6]/1024**3 if existing[6] > 0 else 0)
    expiry_days = body.get("expiry_days", 0)
    host = body.get("host", existing[4])
    port = body.get("port", existing[5])
    
    total_bytes = int(volume_gb * 1024**3) if volume_gb > 0 else 0
    expiry = existing[8]
    if expiry_days > 0:
        expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("""UPDATE users SET email=?,protocol=?,host=?,port=?,total_bytes=?,expiry_date=?
                 WHERE id=?""", (email, protocol, host, port, total_bytes, expiry, uid))
    conn.commit()
    return {"ok": True}

@app.post("/api/links/{uid}/toggle")
async def toggle_link(uid: str, session: str = Cookie("")):
    if not check_auth(session):
        raise HTTPException(401, "unauthorized")
    u = c.execute("SELECT enabled FROM users WHERE id=?", (uid,)).fetchone()
    if not u: raise HTTPException(404)
    new = 0 if u[0] else 1
    c.execute("UPDATE users SET enabled=? WHERE id=?", (new, uid))
    conn.commit()
    return {"ok": True, "enabled": bool(new)}

@app.post("/api/links/{uid}/reset-traffic")
async def reset_traffic(uid: str, session: str = Cookie("")):
    if not check_auth(session):
        raise HTTPException(401, "unauthorized")
    c.execute("UPDATE users SET used_bytes=0, last_reset=? WHERE id=?", (now_str(), uid))
    conn.commit()
    return {"ok": True}

# ─── سابسکریپشن ────────────────────────────────────────────────────────────
@app.get("/sub/{sub_id}")
async def get_sub(sub_id: str):
    u = c.execute("SELECT * FROM users WHERE sub_id=?", (sub_id,)).fetchone()
    if not u:
        return HTMLResponse("Not Found", status_code=404)
    
    cols = ["id","email","uuid","protocol","host","port","total_bytes","used_bytes",
            "expiry_date","enabled","config_type","last_reset","created_at","sub_id"]
    d = dict(zip(cols, u))
    
    if not d["enabled"]:
        return HTMLResponse("Disabled", status_code=403)
    
    # بررسی انقضا
    if d["expiry_date"] and d["expiry_date"] < now_str():
        return HTMLResponse("Expired", status_code=403)
    
    # بررسی حجم
    if d["total_bytes"] > 0 and d["used_bytes"] >= d["total_bytes"]:
        return HTMLResponse("Quota Exceeded", status_code=403)
    
    # افزایش مصرف (ردیابی)
    c.execute("UPDATE users SET used_bytes=used_bytes+1 WHERE id=?", (d["id"],))
    conn.commit()
    
    configs = build_config(d)
    return configs["subscription"]

# ─── آمار ───────────────────────────────────────────────────────────────────
@app.get("/stats")
async def stats(session: str = Cookie("")):
    if not check_auth(session):
        raise HTTPException(401, "unauthorized")
    
    rows = c.execute("SELECT * FROM users").fetchall()
    total = len(rows)
    active = sum(1 for r in rows if r[9] and (not r[8] or r[8] > now_str()))
    total_traffic = sum(r[7] for r in rows)
    
    return {
        "total_users": total,
        "active_users": active,
        "total_traffic": total_traffic,
        "total_traffic_fmt": fmt_bytes(total_traffic),
        "uptime": "running"
    }

# ─── صفحه اصلی (داشبورد) ───────────────────────────────────────────────────
@app.get("/")
async def root():
    return RedirectResponse("/dashboard")

@app.get("/dashboard")
async def dashboard():
    rows = c.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    cols = ["id","email","uuid","protocol","host","port","total_bytes","used_bytes",
            "expiry_date","enabled","config_type","last_reset","created_at","sub_id"]
    users = [dict(zip(cols, r)) for r in rows]
    
    total = len(users)
    active = sum(1 for u in users if u["enabled"] and (not u["expiry_date"] or u["expiry_date"] > now_str()))
    traffic = sum(u["used_bytes"] for u in users)
    
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fa" dir="rtl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Luffy Panel</title>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Vazirmatn',sans-serif;background:#0a0e17;color:#e8edf5;padding:20px;min-height:100vh}}
.container{{max-width:1200px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:25px;padding:15px 20px;background:#111827;border-radius:12px;border:1px solid #1f2937}}
h1{{font-size:20px;color:#f59e0b;display:flex;align-items:center;gap:8px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}}
.stat-card{{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:15px}}
.stat-title{{font-size:11px;color:#6b7280;margin-bottom:4px}}
.stat-value{{font-size:20px;font-weight:700}}
.stat-value.green{{color:#10b981}}
.stat-value.blue{{color:#3b82f6}}
.stat-value.yellow{{color:#f59e0b}}
.btn{{padding:8px 16px;border-radius:8px;border:none;cursor:pointer;font-family:inherit;font-size:12px;font-weight:600;transition:.2s;display:inline-flex;align-items:center;gap:5px}}
.btn:hover{{transform:translateY(-1px);opacity:.9}}
.btn-primary{{background:#3b82f6;color:#fff}}
.btn-success{{background:#10b981;color:#fff}}
.btn-danger{{background:#ef4444;color:#fff}}
.btn-warning{{background:#f59e0b;color:#000}}
.btn-sm{{padding:4px 10px;font-size:10px}}
table{{width:100%;border-collapse:collapse;font-size:12px;background:#111827;border-radius:10px;overflow:hidden}}
th{{background:#1f2937;color:#9ca3af;padding:10px 12px;text-align:right;font-weight:600;font-size:11px}}
td{{padding:10px 12px;border-top:1px solid #1f2937;color:#d1d5db}}
tr:hover{{background:rgba(255,255,255,0.02)}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600}}
.badge-green{{background:rgba(16,185,129,0.15);color:#10b981}}
.badge-red{{background:rgba(239,68,68,0.15);color:#ef4444}}
.badge-yellow{{background:rgba(245,158,11,0.15);color:#f59e0b}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center}}
.modal.show{{display:flex}}
.modal-content{{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:25px;width:90%;max-width:500px;max-height:80vh;overflow-y:auto}}
.modal-title{{font-size:15px;font-weight:700;color:#f59e0b;margin-bottom:15px}}
.form-group{{margin-bottom:12px}}
.form-group label{{display:block;font-size:11px;color:#9ca3af;margin-bottom:4px;font-weight:600}}
.form-control{{width:100%;padding:8px 12px;border-radius:8px;border:1px solid #1f2937;background:#0d1117;color:#e8edf5;font-family:inherit;font-size:12px;outline:none}}
.form-control:focus{{border-color:#3b82f6}}
select.form-control option{{background:#0d1117;color:#e8edf5}}
.form-row{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.proto-checks{{display:flex;gap:8px;flex-wrap:wrap}}
.proto-check{{display:flex;align-items:center;gap:5px;font-size:11px;padding:5px 10px;border-radius:14px;border:1px solid #1f2937;cursor:pointer;transition:.2s;background:#0d1117;color:#9ca3af}}
.proto-check.active{{border-color:#f59e0b;color:#f59e0b;background:rgba(245,158,11,0.1)}}
.proto-check input{{accent-color:#f59e0b}}
.link-cell{{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:ltr;font-family:monospace;font-size:10px;color:#6b7280}}
.copy-btn{{background:rgba(59,130,246,0.15);color:#60a5fa;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:10px;border:none}}
.copy-btn:hover{{background:rgba(59,130,246,0.3)}}
.login-container{{display:flex;align-items:center;justify-content:center;min-height:100vh}}
.login-card{{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:30px;width:100%;max-width:350px}}
.login-card h1{{font-size:18px;margin-bottom:5px}}
.login-card p{{color:#6b7280;font-size:12px;margin-bottom:20px}}
@media(max-width:768px){{.form-row{{grid-template-columns:1fr}}}}
</style>
</head><body>
<div class="container" id="app">
    <div id="login-screen" style="display:none">
        <div class="login-container">
            <div class="login-card">
                <h1>🔐 Luffy Panel</h1>
                <p>ورود به پنل مدیریت</p>
                <div class="form-group"><label>رمز عبور</label><input class="form-control" id="login-pass" type="password" placeholder="admin" onkeydown="if(event.key=='Enter')doLogin()"></div>
                <button class="btn btn-primary" onclick="doLogin()" style="width:100%">ورود</button>
                <div id="login-error" style="color:#ef4444;font-size:12px;margin-top:10px;display:none"></div>
            </div>
        </div>
    </div>

    <div id="panel-screen">
        <div class="header">
            <h1>🏴‍☠️ Luffy Panel</h1>
            <div style="display:flex;gap:8px">
                <button class="btn btn-primary" onclick="openCreateModal()">➕ جدید</button>
                <button class="btn btn-sm btn-warning" onclick="doLogout()">🚪 خروج</button>
            </div>
        </div>
        
        <div class="stats">
            <div class="stat-card"><div class="stat-title">👥 کل کاربران</div><div class="stat-value blue" id="stat-total">{total}</div></div>
            <div class="stat-card"><div class="stat-title">✅ فعال</div><div class="stat-value green" id="stat-active">{active}</div></div>
            <div class="stat-card"><div class="stat-title">📊 مصرف کل</div><div class="stat-value yellow" id="stat-traffic">{fmt_bytes(traffic)}</div></div>
        </div>

        <div style="margin-bottom:12px">
            <input class="form-control" id="search" placeholder="🔍 جستجو..." style="width:250px;display:inline-block" oninput="filterTable()">
        </div>

        <table>
        <thead><tr>
            <th>ایمیل</th><th>پروتکل</th><th>حجم</th><th>مصرف</th><th>انقضا</th><th>وضعیت</th><th>لینک</th><th>عملیات</th>
        </tr></thead>
        <tbody id="users-tbody">
        {"".join(f'''<tr>
            <td><strong>{u['email']}</strong></td>
            <td><span class="badge badge-green">{u['protocol'][:15]}</span></td>
            <td>{fmt_bytes(u['total_bytes']) if u['total_bytes'] else '♾'}</td>
            <td>{fmt_bytes(u['used_bytes'])}</td>
            <td>{u['expiry_date'][:10] if u['expiry_date'] else '♾'}</td>
            <td><span class="badge {"badge-green" if u['enabled'] and (not u['expiry_date'] or u['expiry_date']>now_str()) else "badge-red"}">{"فعال" if u['enabled'] and (not u['expiry_date'] or u['expiry_date']>now_str()) else "غیرفعال"}</span></td>
            <td><div class="link-cell">{"...".join([u['id'][:8],u['sub_id'][:4]])}</div><button class="copy-btn" onclick="copySub('{u['sub_id']}')">📋</button></td>
            <td>
                <button class="btn btn-sm btn-warning" onclick="editUser('{u['id']}')">✏️</button>
                <button class="btn btn-sm btn-danger" onclick="deleteUser('{u['id']}')">🗑</button>
                <button class="btn btn-sm {'btn-success' if u['enabled'] else 'btn-danger'}" onclick="toggleUser('{u['id']}')">{'🔓' if u['enabled'] else '🔒'}</button>
            </td>
        </tr>''' for u in users)}
        </tbody></table>
    </div>
</div>

<div class="modal" id="userModal">
<div class="modal-content">
    <div class="modal-title" id="modalTitle">➕ کاربر جدید</div>
    <input type="hidden" id="edit-id">
    <div class="form-group"><label>ایمیل</label><input class="form-control" id="email" placeholder="user@example.com"></div>
    <div class="form-group">
        <label>پروتکل‌ها</label>
        <div class="proto-checks">
            <div class="proto-check active" onclick="toggleProto(this,'vless-ws')">VLESS+WS</div>
            <div class="proto-check" onclick="toggleProto(this,'xhttp-packet')">XHTTP-P</div>
            <div class="proto-check" onclick="toggleProto(this,'xhttp-stream')">XHTTP-S</div>
        </div>
    </div>
    <div class="form-row">
        <div class="form-group"><label>هاست</label><input class="form-control" id="host" placeholder="auto"></div>
        <div class="form-group"><label>پورت</label><input class="form-control" id="port" type="number" value="443"></div>
    </div>
    <div class="form-row">
        <div class="form-group"><label>حجم (GB)</label><input class="form-control" id="volume" type="number" value="0" placeholder="0=∞"></div>
        <div class="form-group"><label>روز انقضا</label><input class="form-control" id="expiry" type="number" value="0" placeholder="0=∞"></div>
    </div>
    <div style="display:flex;gap:10px;margin-top:15px">
        <button class="btn btn-success" onclick="saveUser()" style="flex:1">💾 ذخیره</button>
        <button class="btn btn-danger" onclick="closeModal()" style="flex:0.5">❌</button>
    </div>
</div></div>

<script>
let selectedProtos = ['vless-ws'];
let loggedIn = false;

async function doLogin(){{
    const pass = document.getElementById('login-pass').value;
    const r = await fetch('/api/login', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{password:pass}})}});
    if(r.ok){{location.reload()}}
    else{{document.getElementById('login-error').textContent='❌ رمز اشتباه';document.getElementById('login-error').style.display='block'}}
}}

async function doLogout(){{await fetch('/api/logout',{{method:'POST'}});location.reload()}}

async function checkAuth(){{
    const r = await fetch('/api/me');
    const d = await r.json();
    if(!d.ok){{document.getElementById('login-screen').style.display='flex';document.getElementById('panel-screen').style.display='none'}}
}}
checkAuth();

function toggleProto(el,val){{
    el.classList.toggle('active');
    if(selectedProtos.includes(val)) selectedProtos = selectedProtos.filter(v=>v!=val);
    else selectedProtos.push(val);
    if(!selectedProtos.length){{el.classList.add('active');selectedProtos=[val]}}
}}

function openCreateModal(){{
    document.getElementById('modalTitle').textContent = '➕ کاربر جدید';
    document.getElementById('edit-id').value = '';
    document.getElementById('email').value = '';
    document.getElementById('host').value = '';
    document.getElementById('port').value = '443';
    document.getElementById('volume').value = '0';
    document.getElementById('expiry').value = '0';
    selectedProtos = ['vless-ws'];
    document.querySelectorAll('.proto-check').forEach(c=>c.classList.toggle('active',c.textContent.includes('VLESS')));
    document.getElementById('userModal').classList.add('show');
}}

function closeModal(){{document.getElementById('userModal').classList.remove('show')}}

async function saveUser(){{
    const editId = document.getElementById('edit-id').value;
    const body = {{
        email: document.getElementById('email').value || 'user_'+Math.random().toString(36).slice(2,8),
        protocol: selectedProtos.join(','),
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value) || 443,
        volume_gb: parseFloat(document.getElementById('volume').value) || 0,
        expiry_days: parseInt(document.getElementById('expiry').value) || 0
    }};
    const url = editId ? '/api/links/'+editId : '/api/links';
    const method = editId ? 'PUT' : 'POST';
    try{{
        const r = await fetch(url,{{method,headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
        if(r.ok){{closeModal();location.reload()}}
        else{{const d=await r.json();alert(d.msg||'خطا')}}
    }}catch(e){{alert(e.message)}}
}}

async function editUser(id){{
    document.getElementById('modalTitle').textContent = '✏️ ویرایش';
    document.getElementById('edit-id').value = id;
    const r = await fetch('/api/links');
    const d = await r.json();
    const u = d.links.find(l=>l.id==id);
    if(!u) return;
    document.getElementById('email').value = u.email;
    document.getElementById('host').value = u.host;
    document.getElementById('port').value = u.port;
    document.getElementById('volume').value = u.total_bytes > 0 ? (u.total_bytes/1073741824).toFixed(1) : 0;
    document.getElementById('expiry').value = u.expiry_date ? 30 : 0;
    selectedProtos = u.protocol.split(',');
    document.querySelectorAll('.proto-check').forEach(c=>{{
        const v = {'VLESS+WS':'vless-ws','XHTTP-P':'xhttp-packet','XHTTP-S':'xhttp-stream'}[c.textContent.trim()];
        c.classList.toggle('active',selectedProtos.includes(v));
    }});
    document.getElementById('userModal').classList.add('show');
}}

async function deleteUser(id){{if(!confirm('حذف?'))return;await fetch('/api/links/'+id,{{method:'DELETE'}});location.reload()}}

async function toggleUser(id){{await fetch('/api/links/'+id+'/toggle',{{method:'POST'}});location.reload()}}

async function copySub(subId){{navigator.clipboard.writeText(window.location.origin+'/sub/'+subId)}}

function filterTable(){{
    const q = document.getElementById('search').value.toLowerCase();
    document.querySelectorAll('#users-tbody tr').forEach(r=>{{
        r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
}}
</script>
</body></html>""")

# ─── استارت ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
