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
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException, Query, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VaslZone-v3")

app = FastAPI(title="VaslZone Panel v3", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ─── دیتابیس ───────────────────────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "/data/panel.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if "/" in DB_PATH else None

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
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    sub_id TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS traffic_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    date TEXT,
    bytes INTEGER DEFAULT 0
)""")

c.execute("""CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""")

c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('default_host','')")
c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('default_port','443')")
c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('admin_password','admin')")
c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('panel_title','VaslZone Panel')")
conn.commit()

# ─── توابع کمکی ────────────────────────────────────────────────────────────
def gen_uuid():
    h = secrets.token_hex(16)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fmt_bytes(b):
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    if b < 1024**3: return f"{b/1024**2:.2f} MB"
    return f"{b/1024**3:.2f} GB"

def get_setting(key, default=""):
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else default

# ─── ساخت کانفیگ ──────────────────────────────────────────────────────────
def build_vless_ws(uuid, host, port=443, remark=""):
    params = {"encryption":"none","security":"tls","type":"ws","host":host,"path":f"/ws/{uuid[:8]}","sni":host,"fp":"chrome","alpn":"http/1.1"}
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    return f"vless://{uuid}@{host}:{port}?{q}#{urllib.parse.quote(remark)}"

def build_xhttp_packet(uuid, host, port=443, remark=""):
    params = {"encryption":"none","security":"tls","type":"xhttp","mode":"packet-up","host":host,"path":f"/xhttp-p/{uuid[:8]}","sni":host,"fp":"chrome","alpn":"h2,http/1.1"}
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    return f"vless://{uuid}@{host}:{port}?{q}#{urllib.parse.quote(remark)}"

def build_xhttp_stream(uuid, host, port=443, remark=""):
    params = {"encryption":"none","security":"tls","type":"xhttp","mode":"stream-up","host":host,"path":f"/xhttp-s/{uuid[:8]}","sni":host,"fp":"chrome","alpn":"h2,http/1.1"}
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    return f"vless://{uuid}@{host}:{port}?{q}#{urllib.parse.quote(remark)}"

def build_user_configs(user):
    """ساخت کانفیگ برای کاربر با پروتکل‌های انتخابی"""
    host = user["host"] or get_setting("default_host", "localhost")
    port = user["port"] or int(get_setting("default_port", "443"))
    uuid = user["uuid"]
    remark = user["email"]
    
    protos = user["protocol"].split(",")
    builders = {
        "vless-ws": build_vless_ws,
        "xhttp-packet": build_xhttp_packet,
        "xhttp-stream": build_xhttp_stream
    }
    
    links = []
    for p in protos:
        p = p.strip()
        if p in builders:
            links.append(builders[p](uuid, host, port, f"{remark}-{p}"))
    
    # سابسکریپشن
    sub = base64.b64encode("\n".join(links).encode()).decode()
    sub_url = f"/sub/{user['sub_id'] or user['id']}"
    
    return {"links": links, "subscription": sub, "sub_url": sub_url}

# ─── صفحه اصلی ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return RedirectResponse("/dashboard")

# ─── داشبورد ──────────────────────────────────────────────────────────────
@app.get("/dashboard")
async def dashboard():
    users = c.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    cols = ["id","email","uuid","protocol","host","port","total_bytes","used_bytes","expiry_date","enabled","note","created_at","sub_id"]
    user_list = [dict(zip(cols, u)) for u in users]
    
    total_users = len(user_list)
    active_users = sum(1 for u in user_list if u["enabled"] and (not u["expiry_date"] or u["expiry_date"] > now_str()))
    total_traffic = sum(u["used_bytes"] for u in user_list)
    
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fa" dir="rtl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{get_setting('panel_title')}</title>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Vazirmatn',sans-serif;background:#060f1d;color:#E8F4FF;padding:20px}}
.container{{max-width:1200px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:25px}}
h1{{font-size:22px;color:#D97706;display:flex;align-items:center;gap:10px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:25px}}
.stat-card{{background:rgba(10,22,40,0.9);border:1px solid rgba(239,68,68,0.15);border-radius:14px;padding:18px}}
.stat-title{{font-size:12px;color:#7BAED4;margin-bottom:5px}}
.stat-value{{font-size:22px;font-weight:700}}
.stat-desc{{font-size:11px;color:#3D6B8E;margin-top:3px}}
.section-title{{font-size:16px;font-weight:700;color:#D97706;margin-bottom:15px;display:flex;align-items:center;gap:8px}}
.toolbar{{display:flex;gap:10px;margin-bottom:15px;flex-wrap:wrap}}
.btn{{padding:8px 18px;border-radius:9px;border:none;cursor:pointer;font-family:inherit;font-size:12px;font-weight:600;transition:.2s;display:inline-flex;align-items:center;gap:5px}}
.btn:hover{{transform:translateY(-1px);opacity:.9}}
.btn-primary{{background:linear-gradient(135deg,#2563EB,#1D4ED8);color:#fff}}
.btn-success{{background:linear-gradient(135deg,#059669,#065F46);color:#fff}}
.btn-danger{{background:linear-gradient(135deg,#DC2626,#991B1B);color:#fff}}
.btn-warning{{background:linear-gradient(135deg,#D97706,#92400E);color:#fff}}
.btn-info{{background:linear-gradient(135deg,#7C3AED,#6D28D9);color:#fff}}
.btn-sm{{padding:5px 12px;font-size:11px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:rgba(217,119,6,0.08);color:#7BAED4;padding:10px 12px;text-align:right;font-weight:600;border-bottom:1px solid rgba(239,68,68,0.1)}}
td{{padding:10px 12px;border-bottom:1px solid rgba(239,68,68,0.05)}}
tr:hover{{background:rgba(239,68,68,0.03)}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:10px;font-weight:600}}
.badge-green{{background:rgba(16,185,129,0.15);color:#34D399}}
.badge-red{{background:rgba(239,68,68,0.15);color:#F87171}}
.badge-yellow{{background:rgba(245,158,11,0.15);color:#FBBF24}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center}}
.modal.show{{display:flex}}
.modal-content{{background:#0d1b2e;border:1px solid rgba(239,68,68,0.2);border-radius:16px;padding:25px;width:90%;max-width:500px;max-height:90vh;overflow-y:auto}}
.modal-title{{font-size:16px;font-weight:700;color:#D97706;margin-bottom:15px}}
.form-group{{margin-bottom:12px}}
.form-group label{{display:block;font-size:11px;color:#7BAED4;margin-bottom:4px;font-weight:600}}
.form-control{{width:100%;padding:9px 12px;border-radius:8px;border:1px solid rgba(239,68,68,0.2);background:rgba(0,0,0,0.3);color:#E8F4FF;font-family:inherit;font-size:12px;outline:none;transition:.2s}}
.form-control:focus{{border-color:rgba(217,119,6,0.5)}}
select.form-control option{{background:#0a1628;color:#E8F4FF}}
.form-row{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.proto-checks{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:5px}}
.proto-check{{display:flex;align-items:center;gap:5px;font-size:12px;padding:5px 12px;border-radius:20px;border:1px solid rgba(239,68,68,0.15);cursor:pointer;transition:.2s}}
.proto-check:hover{{border-color:rgba(217,119,6,0.4)}}
.proto-check input{{accent-color:#D97706}}
.copy-btn{{background:rgba(37,99,235,0.2);color:#60A5FA;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:10px;border:none}}
.copy-btn:hover{{background:rgba(37,99,235,0.4)}}
.link-cell{{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:ltr;font-family:monospace;font-size:10px}}
@media(max-width:768px){{.form-row{{grid-template-columns:1fr}}table{{font-size:10px}}}}
</style>
</head><body>
<div class="container">
<div class="header">
    <h1><i class="ti ti-brand-vue"></i> {get_setting('panel_title')}</h1>
    <div>
        <button class="btn btn-primary" onclick="openModal('add')">➕ کاربر جدید</button>
        <button class="btn btn-info" onclick="openSettings()">⚙️ تنظیمات</button>
    </div>
</div>

<div class="stats">
    <div class="stat-card"><div class="stat-title">👥 کل کاربران</div><div class="stat-value">{total_users}</div></div>
    <div class="stat-card"><div class="stat-title">✅ فعال</div><div class="stat-value" style="color:#34D399">{active_users}</div></div>
    <div class="stat-card"><div class="stat-title">📊 مصرف کل</div><div class="stat-value" style="color:#60A5FA">{fmt_bytes(total_traffic)}</div></div>
</div>

<div class="section-title"><i class="ti ti-users"></i> لیست کاربران</div>
<div class="toolbar">
    <input class="form-control" id="search" placeholder="🔍 جستجو..." style="width:200px;padding:7px 12px" oninput="filterTable()">
</div>

<table id="users-table">
<thead><tr>
    <th>ایمیل</th><th>پروتکل</th><th>حجم کل</th><th>مصرف</th><th>انقضا</th><th>وضعیت</th><th>لینک</th><th>عملیات</th>
</tr></thead>
<tbody>
{"".join(f'''<tr>
    <td><strong>{u['email']}</strong></td>
    <td><span class="badge badge-green">{u['protocol'][:20]}</span></td>
    <td>{fmt_bytes(u['total_bytes']) if u['total_bytes'] else '♾'}</td>
    <td>{fmt_bytes(u['used_bytes'])}</td>
    <td>{u['expiry_date'][:10] if u['expiry_date'] else '♾'}</td>
    <td><span class="badge {"badge-green" if u['enabled'] and (not u['expiry_date'] or u['expiry_date']>now_str()) else "badge-red"}'>{'🟢 فعال' if u['enabled'] and (not u['expiry_date'] or u['expiry_date']>now_str()) else '🔴 غیرفعال'}</span></td>
    <td><div class="link-cell" id="link-{u['id']}">{build_user_configs(u)['links'][0] if build_user_configs(u)['links'] else ''}</div>
        <button class="copy-btn" onclick="copyLink('{u['id']}')">📋</button></td>
    <td>
        <button class="btn btn-sm btn-warning" onclick="editUser('{u['id']}')">✏️</button>
        <button class="btn btn-sm btn-danger" onclick="deleteUser('{u['id']}')">🗑</button>
    </td>
</tr>''' for u in user_list)}
</tbody></table>
</div>

<div class="modal" id="userModal">
<div class="modal-content">
    <div class="modal-title" id="modalTitle">➕ کاربر جدید</div>
    <input type="hidden" id="edit-id">
    <div class="form-group"><label>ایمیل / نام کاربری</label><input class="form-control" id="email" placeholder="example@mail.com"></div>
    <div class="form-group">
        <label>پروتکل‌ها (چندتایی انتخاب کن)</label>
        <div class="proto-checks">
            <label class="proto-check"><input type="checkbox" value="vless-ws" checked> VLESS+WS</label>
            <label class="proto-check"><input type="checkbox" value="xhttp-packet"> XHTTP packet-up</label>
            <label class="proto-check"><input type="checkbox" value="xhttp-stream"> XHTTP stream-up</label>
        </div>
    </div>
    <div class="form-row">
        <div class="form-group"><label>هاست</label><input class="form-control" id="host" placeholder="{get_setting('default_host','localhost')}"></div>
        <div class="form-group"><label>پورت</label><input class="form-control" id="port" type="number" value="{get_setting('default_port','443')}"></div>
    </div>
    <div class="form-row">
        <div class="form-group"><label>حجم (GB) — 0 = نامحدود</label><input class="form-control" id="volume" type="number" value="0"></div>
        <div class="form-group"><label>روز انقضا — 0 = نامحدود</label><input class="form-control" id="expiry" type="number" value="0"></div>
    </div>
    <div class="form-group"><label>یادداشت</label><input class="form-control" id="note" placeholder="اختیاری"></div>
    <div style="display:flex;gap:10px;margin-top:15px">
        <button class="btn btn-success" onclick="saveUser()" style="flex:1">💾 ذخیره</button>
        <button class="btn btn-danger" onclick="closeModal('userModal')" style="flex:0.5">❌</button>
    </div>
</div></div>

<div class="modal" id="settingsModal">
<div class="modal-content">
    <div class="modal-title">⚙️ تنظیمات پنل</div>
    <div class="form-group"><label>عنوان پنل</label><input class="form-control" id="s-title" value="{get_setting('panel_title')}"></div>
    <div class="form-row">
        <div class="form-group"><label>هاست پیش‌فرض</label><input class="form-control" id="s-host" value="{get_setting('default_host')}"></div>
        <div class="form-group"><label>پورت پیش‌فرض</label><input class="form-control" id="s-port" value="{get_setting('default_port')}"></div>
    </div>
    <div class="form-group"><label>رمز ادمین</label><input class="form-control" id="s-pass" type="password" value="{get_setting('admin_password')}"></div>
    <button class="btn btn-primary" onclick="saveSettings()" style="width:100%;margin-top:10px">💾 ذخیره تنظیمات</button>
</div></div>

<script>
let currentUser = {{}};

function openModal(type, data=null){{
    document.getElementById('userModal').classList.add('show');
    if(type=='add'){{
        document.getElementById('modalTitle').textContent = '➕ کاربر جدید';
        document.getElementById('edit-id').value = '';
        document.getElementById('email').value = '';
        document.getElementById('volume').value = '0';
        document.getElementById('expiry').value = '0';
        document.getElementById('host').value = '';
        document.getElementById('port').value = '{get_setting('default_port','443')}';
        document.getElementById('note').value = '';
        document.querySelectorAll('.proto-check input').forEach(c=>c.checked=false);
        document.querySelector('.proto-check input').checked = true;
    }}
}}

function closeModal(id){{
    document.getElementById(id).classList.remove('show');
}}

async function saveUser(){{
    const protos = [];
    document.querySelectorAll('.proto-check input:checked').forEach(c=>protos.push(c.value));
    const body = {{
        email: document.getElementById('email').value,
        protocol: protos.join(','),
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value) || 443,
        total_gb: parseInt(document.getElementById('volume').value) || 0,
        expiry_days: parseInt(document.getElementById('expiry').value) || 0,
        note: document.getElementById('note').value
    }};
    const editId = document.getElementById('edit-id').value;
    const url = editId ? `/api/users/`+editId : '/api/users';
    const method = editId ? 'PUT' : 'POST';
    try{{
        const r = await fetch(url, {{method, headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
        if(r.ok){{closeModal('userModal');location.reload();}}
        else alert('خطا');
    }}catch(e){{alert(e.message)}}
}}

async function editUser(id){{
    const r = await fetch('/api/users/'+id);
    const u = await r.json();
    if(!u.success) return;
    document.getElementById('modalTitle').textContent = '✏️ ویرایش کاربر';
    document.getElementById('edit-id').value = id;
    document.getElementById('email').value = u.email;
    document.getElementById('host').value = u.host;
    document.getElementById('port').value = u.port;
    document.getElementById('volume').value = u.total_bytes > 0 ? (u.total_bytes/1024**3).toFixed(1) : 0;
    document.getElementById('expiry').value = u.expiry_date ? 30 : 0;
    document.getElementById('note').value = u.note || '';
    document.querySelectorAll('.proto-check input').forEach(c=>{{
        c.checked = u.protocol.includes(c.value);
    }});
    document.getElementById('userModal').classList.add('show');
}}

async function deleteUser(id){{
    if(!confirm('حذف شود؟')) return;
    await fetch('/api/users/'+id, {{method:'DELETE'}});
    location.reload();
}}

async function copyLink(id){{
    const r = await fetch('/api/users/'+id);
    const u = await r.json();
    if(u.links && u.links[0]){{
        navigator.clipboard.writeText(u.links[0]);
    }}
}}

function filterTable(){{
    const q = document.getElementById('search').value.toLowerCase();
    document.querySelectorAll('#users-table tbody tr').forEach(r=>{{
        r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
}}

function openSettings(){{
    document.getElementById('settingsModal').classList.add('show');
}}

async function saveSettings(){{
    await fetch('/api/settings', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{
            title: document.getElementById('s-title').value,
            host: document.getElementById('s-host').value,
            port: document.getElementById('s-port').value,
            password: document.getElementById('s-pass').value
        }})
    }});
    closeModal('settingsModal');
    location.reload();
}}
</script>
</body></html>""")

# ─── API: کاربران ──────────────────────────────────────────────────────────
@app.get("/api/users")
async def list_users():
    users = c.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    cols = ["id","email","uuid","protocol","host","port","total_bytes","used_bytes","expiry_date","enabled","note","created_at","sub_id"]
    result = []
    for u in users:
        d = dict(zip(cols, u))
        configs = build_user_configs(d)
        d["links"] = configs["links"]
        d["subscription"] = configs["subscription"]
        d["sub_url"] = configs["sub_url"]
        d["used_fmt"] = fmt_bytes(d["used_bytes"])
        d["total_fmt"] = fmt_bytes(d["total_bytes"]) if d["total_bytes"] else "♾"
        result.append(d)
    return {"users": result, "total": len(result)}

@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    u = c.execute("SELECT * FROM users WHERE id=? OR email=?", (user_id, user_id)).fetchone()
    if not u:
        raise HTTPException(404, "کاربر پیدا نشد")
    cols = ["id","email","uuid","protocol","host","port","total_bytes","used_bytes","expiry_date","enabled","note","created_at","sub_id"]
    d = dict(zip(cols, u))
    configs = build_user_configs(d)
    d["links"] = configs["links"]
    d["subscription"] = configs["subscription"]
    d["sub_url"] = configs["sub_url"]
    d["success"] = True
    return d

@app.post("/api/users")
async def create_user(request: Request):
    body = await request.json()
    email = body.get("email", f"user_{secrets.token_hex(4)}")
    protocol = body.get("protocol", "vless-ws")
    host = body.get("host", "")
    port = body.get("port", int(get_setting("default_port", "443")))
    total_gb = body.get("total_gb", 0)
    expiry_days = body.get("expiry_days", 0)
    note = body.get("note", "")
    
    # چک تکراری نبودن
    existing = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        return {"success": False, "error": "این ایمیل قبلاً ثبت شده"}
    
    user_id = gen_uuid()
    user_uuid = gen_uuid()
    sub_id = secrets.token_hex(8)
    expiry = None
    if expiry_days > 0:
        expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d %H:%M:%S")
    
    total_bytes = int(total_gb * 1024**3) if total_gb > 0 else 0
    
    c.execute("""INSERT INTO users (id,email,uuid,protocol,host,port,total_bytes,expiry_date,note,sub_id) 
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (user_id, email, user_uuid, protocol, host, port, total_bytes, expiry, note, sub_id))
    conn.commit()
    
    return {"success": True, "id": user_id, "uuid": user_uuid, "email": email}

@app.put("/api/users/{user_id}")
async def update_user(user_id: str, request: Request):
    body = await request.json()
    existing = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "کاربر پیدا نشد")
    
    email = body.get("email", existing[1])
    protocol = body.get("protocol", existing[3])
    host = body.get("host", existing[4])
    port = body.get("port", existing[5])
    total_gb = body.get("total_gb", existing[6]/1024**3 if existing[6] > 0 else 0)
    expiry_days = body.get("expiry_days", 0)
    note = body.get("note", existing[9])
    
    total_bytes = int(total_gb * 1024**3) if total_gb > 0 else 0
    expiry = None
    if expiry_days > 0:
        expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("""UPDATE users SET email=?,protocol=?,host=?,port=?,total_bytes=?,expiry_date=?,note=? WHERE id=?""",
              (email, protocol, host, port, total_bytes, expiry, note, user_id))
    conn.commit()
    return {"success": True}

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str):
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    return {"success": True}

@app.post("/api/users/{user_id}/toggle")
async def toggle_user(user_id: str):
    u = c.execute("SELECT enabled FROM users WHERE id=?", (user_id,)).fetchone()
    if not u: raise HTTPException(404)
    new = 0 if u[0] else 1
    c.execute("UPDATE users SET enabled=? WHERE id=?", (new, user_id))
    conn.commit()
    return {"success": True, "enabled": bool(new)}

@app.post("/api/users/{user_id}/reset-traffic")
async def reset_traffic(user_id: str):
    c.execute("UPDATE users SET used_bytes=0 WHERE id=?", (user_id,))
    conn.commit()
    return {"success": True}

@app.post("/api/users/{user_id}/add-traffic")
async def add_traffic(user_id: str, request: Request):
    body = await request.json()
    gb = body.get("gb", 0)
    if gb <= 0: return {"success": False, "error": "مقدار نامعتبر"}
    c.execute("UPDATE users SET total_bytes=total_bytes+? WHERE id=?", (int(gb*1024**3), user_id))
    conn.commit()
    return {"success": True}

# ─── API: تنظیمات ──────────────────────────────────────────────────────────
@app.post("/api/settings")
async def save_settings(request: Request):
    body = await request.json()
    if "title" in body: c.execute("INSERT OR REPLACE INTO settings VALUES ('panel_title',?)", (body["title"],))
    if "host" in body: c.execute("INSERT OR REPLACE INTO settings VALUES ('default_host',?)", (body["host"],))
    if "port" in body: c.execute("INSERT OR REPLACE INTO settings VALUES ('default_port',?)", (str(body["port"]),))
    if "password" in body: c.execute("INSERT OR REPLACE INTO settings VALUES ('admin_password',?)", (body["password"],))
    conn.commit()
    return {"success": True}

@app.get("/api/settings")
async def get_settings():
    rows = c.execute("SELECT key,value FROM settings").fetchall()
    return {k: v for k, v in rows}

# ─── API: آمار ─────────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    users = c.execute("SELECT * FROM users").fetchall()
    total = len(users)
    active = sum(1 for u in users if u[9] and (not u[8] or u[8] > now_str()))
    total_traffic = sum(u[7] for u in users)
    return {
        "total_users": total,
        "active_users": active,
        "total_traffic": total_traffic,
        "total_traffic_fmt": fmt_bytes(total_traffic)
    }

# ─── سابسکریپشن ────────────────────────────────────────────────────────────
@app.get("/sub/{sub_id}")
async def get_subscription(sub_id: str):
    u = c.execute("SELECT * FROM users WHERE sub_id=? OR id=?", (sub_id, sub_id)).fetchone()
    if not u: raise HTTPException(404, "نداشت")
    cols = ["id","email","uuid","protocol","host","port","total_bytes","used_bytes","expiry_date","enabled","note","created_at","sub_id"]
    d = dict(zip(cols, u))
    
    if not d["enabled"]:
        return HTMLResponse("کاربر غیرفعال است", status_code=403)
    
    configs = build_user_configs(d)
    return configs["subscription"]

# ─── استارت ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
