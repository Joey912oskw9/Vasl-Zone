# main.py - VaslZone Gateway v2 (3X-UI / Marzban backend)
import os
import json
import logging
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from xui_api import XUIClient, create_config_on_xui
from marzban_api import MarzbanClient, create_config_on_marzban
from configs import *

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VaslZone-v2")

app = FastAPI(title="VaslZone Panel v2", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ─── کانفیگ از Environment Variables ──────────────────────────────────────
CONFIG = {
    "xui_url": os.environ.get("XUI_URL", ""),
    "xui_user": os.environ.get("XUI_USER", "admin"),
    "xui_pass": os.environ.get("XUI_PASS", "admin"),
    "marzban_url": os.environ.get("MARZBAN_URL", ""),
    "marzban_user": os.environ.get("MARZBAN_USER", "admin"),
    "marzban_pass": os.environ.get("MARZBAN_PASS", "admin"),
    "default_mode": os.environ.get("DEFAULT_MODE", "xui"),  # xui or marzban
    "default_port": int(os.environ.get("DEFAULT_PORT", "443")),
    "port": int(os.environ.get("PORT", "8000")),
}

# ─── صفحه اصلی ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VaslZone Panel v2</title>
    <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap" rel="stylesheet">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Vazirmatn',sans-serif;background:#060f1d;color:#E8F4FF;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
        .card{background:rgba(10,22,40,0.9);border:1px solid rgba(239,68,68,0.2);border-radius:20px;padding:40px;max-width:500px;width:100%;text-align:center}
        h1{color:#D97706;margin-bottom:10px;font-size:24px}
        p{color:#7BAED4;margin-bottom:30px;font-size:14px}
        .btn{display:inline-block;padding:12px 24px;border-radius:10px;border:none;cursor:pointer;font-family:inherit;font-size:14px;font-weight:700;text-decoration:none;margin:5px;transition:.2s}
        .btn-primary{background:linear-gradient(135deg,#2563EB,#1D4ED8);color:#fff}
        .btn-success{background:linear-gradient(135deg,#059669,#065F46);color:#fff}
        .btn:hover{opacity:.9;transform:translateY(-1px)}
        .badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:11px;background:rgba(239,68,68,0.1);color:#D97706;margin-bottom:20px}
        .status{margin-top:20px;padding:15px;border-radius:10px;background:rgba(16,185,129,0.05);border:1px solid rgba(16,185,129,0.1)}
        .status-item{display:flex;justify-content:space-between;padding:8px 0;font-size:13px;border-bottom:1px solid rgba(239,68,68,0.05)}
        .status-item:last-child{border-bottom:none}
        .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:6px}
        .dot-green{background:#34D399}
        .dot-red{background:#F87171}
        .dot-yellow{background:#FBBF24}
    </style>
    </head>
    <body>
    <div class="card">
        <div class="badge">⚡ VaslZone v2</div>
        <h1>VaslZone Panel</h1>
        <p>مدیریت کانفیگ‌ها از طریق 3X-UI و Marzban</p>
        <a href="/dashboard" class="btn btn-primary">🚀 ورود به داشبورد</a>
        <a href="/status" class="btn btn-success">📊 وضعیت سرورها</a>
        <div class="status">
            <div class="status-item"><span>🌐 3X-UI</span><span><span class="dot dot-green"></span> متصل</span></div>
            <div class="status-item"><span>🟣 Marzban</span><span><span class="dot dot-yellow"></span> غیرفعال</span></div>
        </div>
    </div>
    </body>
    </html>
    """)

# ─── وضعیت سرورها ─────────────────────────────────────────────────────────
@app.get("/api/status")
async def api_status():
    status = {"3x-ui": False, "marzban": False, "mode": CONFIG["default_mode"]}
    try:
        if CONFIG["xui_url"]:
            client = XUIClient(CONFIG["xui_url"], CONFIG["xui_user"], CONFIG["xui_pass"])
            status["3x-ui"] = await client.login()
            await client.close()
        if CONFIG["marzban_url"]:
            client = MarzbanClient(CONFIG["marzban_url"], CONFIG["marzban_user"], CONFIG["marzban_pass"])
            status["marzban"] = await client.login()
            await client.close()
    except Exception as e:
        logger.error(f"Status check error: {e}")
    return status

@app.get("/status")
async def status_page():
    return HTMLResponse("""
    <!DOCTYPE html><html lang="fa" dir="rtl"><head>
    <meta charset="UTF-8"><title>وضعیت سرورها</title>
    <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap" rel="stylesheet">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Vazirmatn',sans-serif;background:#060f1d;color:#E8F4FF;padding:40px}
        .card{background:rgba(10,22,40,0.9);border:1px solid rgba(239,68,68,0.2);border-radius:20px;padding:30px;max-width:600px;margin:0 auto}
        h1{color:#D97706;font-size:22px;margin-bottom:20px}
        .row{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid rgba(239,68,68,0.1);font-size:14px}
        .loading{text-align:center;padding:40px;color:#7BAED4}
        .btn{display:inline-block;padding:10px 20px;border-radius:10px;border:none;cursor:pointer;font-family:inherit;font-size:13px;font-weight:700;text-decoration:none;background:linear-gradient(135deg,#2563EB,#1D4ED8);color:#fff;margin-top:20px}
    </style>
    </head><body>
    <div class="card">
        <h1>📊 وضعیت سرورها</h1>
        <div id="status">
            <div class="loading">⏳ در حال بررسی...</div>
        </div>
        <a href="/dashboard" class="btn">🔙 بازگشت</a>
    </div>
    <script>
    async function checkStatus(){
        const r=await fetch('/api/status');
        const d=await r.json();
        document.getElementById('status').innerHTML=
            '<div class="row"><span>🌐 3X-UI</span><span>'+(d['3x-ui']?'<span style="color:#34D399">✅ متصل</span>':'<span style="color:#F87171">❌ قطع</span>')+'</span></div>'+
            '<div class="row"><span>🟣 Marzban</span><span>'+(d.marzban?'<span style="color:#34D399">✅ متصل</span>':'<span style="color:#F87171">❌ قطع</span>')+'</span></div>'+
            '<div class="row"><span>⚙️ حالت فعلی</span><span>'+d.mode+'</span></div>';
    }
    checkStatus();
    setInterval(checkStatus,10000);
    </script>
    </body></html>
    """)

# ─── داشبورد ──────────────────────────────────────────────────────────────
@app.get("/dashboard")
async def dashboard():
    return HTMLResponse("""
    <!DOCTYPE html><html lang="fa" dir="rtl"><head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>داشبورد · VaslZone v2</title>
    <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Vazirmatn',sans-serif;background:#060f1d;color:#E8F4FF;padding:20px}
        .container{max-width:900px;margin:0 auto}
        h1{font-size:22px;color:#D97706;margin-bottom:5px;display:flex;align-items:center;gap:10px}
        .sub{color:#7BAED4;font-size:13px;margin-bottom:25px}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:25px}
        .card{background:rgba(10,22,40,0.9);border:1px solid rgba(239,68,68,0.15);border-radius:16px;padding:20px;transition:.2s}
        .card:hover{border-color:rgba(239,68,68,0.3)}
        .card-title{font-size:13px;color:#7BAED4;margin-bottom:8px;display:flex;align-items:center;gap:6px}
        .card-value{font-size:24px;font-weight:700;color:#E8F4FF}
        .card-desc{font-size:11px;color:#3D6B8E;margin-top:4px}
        .section-title{font-size:16px;font-weight:700;color:#D97706;margin-bottom:15px;margin-top:10px}
        .form-group{margin-bottom:15px}
        .form-group label{display:block;font-size:12px;color:#7BAED4;margin-bottom:5px;font-weight:600}
        .form-control{width:100%;padding:10px 14px;border-radius:10px;border:1px solid rgba(239,68,68,0.2);background:rgba(0,0,0,0.3);color:#E8F4FF;font-family:inherit;font-size:13px;outline:none;transition:.2s}
        .form-control:focus{border-color:rgba(239,68,68,0.5);background:rgba(0,0,0,0.4)}
        .form-control::placeholder{color:#3D6B8E}
        select.form-control option{background:#0a1628;color:#E8F4FF}
        .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
        .btn{width:100%;padding:12px;border-radius:10px;border:none;cursor:pointer;font-family:inherit;font-size:14px;font-weight:700;transition:.2s}
        .btn-primary{background:linear-gradient(135deg,#2563EB,#1D4ED8);color:#fff}
        .btn-success{background:linear-gradient(135deg,#059669,#065F46);color:#fff}
        .btn-info{background:linear-gradient(135deg,#7C3AED,#6D28D9);color:#fff}
        .btn:hover{opacity:.9;transform:translateY(-1px)}
        .output{margin-top:15px;padding:15px;border-radius:10px;background:rgba(0,0,0,0.3);border:1px solid rgba(239,68,68,0.1);display:none;word-break:break-all;font-size:12px;font-family:monospace;max-height:300px;overflow-y:auto;white-space:pre-wrap}
        .output.show{display:block}
        .copy-btn{position:sticky;top:0;float:left;padding:6px 14px;border-radius:6px;border:none;cursor:pointer;font-size:11px;background:rgba(37,99,235,0.3);color:#60A5FA;margin-bottom:5px}
        .copy-btn:hover{background:rgba(37,99,235,0.5)}
        .proto-chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:15px}
        .proto-chip{padding:8px 16px;border-radius:20px;border:1px solid rgba(239,68,68,0.2);cursor:pointer;font-size:12px;transition:.2s;background:rgba(0,0,0,0.2);color:#7BAED4}
        .proto-chip.active{background:rgba(217,119,6,0.15);border-color:#D97706;color:#D97706}
        .proto-chip:hover{border-color:rgba(217,119,6,0.4)}
        .nav{display:flex;gap:10px;margin-bottom:20px}
        .nav-btn{padding:8px 18px;border-radius:10px;border:1px solid rgba(239,68,68,0.15);cursor:pointer;font-size:12px;font-family:inherit;background:rgba(0,0,0,0.2);color:#7BAED4;transition:.2s}
        .nav-btn.active{background:rgba(217,119,6,0.12);border-color:#D97706;color:#D97706}
        @media(max-width:600px){.grid,.row{grid-template-columns:1fr}}
    </style>
    </head><body>
    <div class="container">
        <h1><i class="ti ti-brand-vue"></i> VaslZone v2</h1>
        <div class="sub">مدیریت کانفیگ با 3X-UI و Marzban</div>
        
        <div class="nav">
            <div class="nav-btn active" onclick="switchTab('create',this)">🛠 ساخت کانفیگ</div>
            <div class="nav-btn" onclick="switchTab('bulk',this)">📦 ساخت گروهی</div>
            <div class="nav-btn" onclick="switchTab('sub',this)">🔗 ساب گروهی</div>
        </div>

        <div id="tab-create">
            <div class="section-title">🛠 ساخت کانفیگ تکی</div>
            <div class="card">
                <div class="form-group">
                    <label>پروتکل</label>
                    <div class="proto-chips" id="proto-select">
                        <div class="proto-chip active" onclick="selectProto('vless-ws',this)">VLESS + WS</div>
                        <div class="proto-chip" onclick="selectProto('xhttp-packet',this)">XHTTP packet-up</div>
                        <div class="proto-chip" onclick="selectProto('xhttp-stream',this)">XHTTP stream-up</div>
                        <div class="proto-chip" onclick="selectProto('all',this)">🔀 هر سه باهم</div>
                    </div>
                </div>
                <div class="row">
                    <div class="form-group">
                        <label>منبع</label>
                        <select class="form-control" id="source">
                            <option value="xui">3X-UI</option>
                            <option value="marzban">Marzban</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Inbound ID (برای 3X-UI)</label>
                        <input class="form-control" id="inbound" type="number" value="1" placeholder="1">
                    </div>
                </div>
                <div class="row">
                    <div class="form-group">
                        <label>حجم (GB) — 0 = نامحدود</label>
                        <input class="form-control" id="volume" type="number" value="0" placeholder="0">
                    </div>
                    <div class="form-group">
                        <label>روز انقضا — 0 = نامحدود</label>
                        <input class="form-control" id="expiry" type="number" value="0" placeholder="0">
                    </div>
                </div>
                <div class="form-group">
                    <label>نام کاربری (اختیاری)</label>
                    <input class="form-control" id="username" type="text" placeholder="مثال: user1">
                </div>
                <button class="btn btn-primary" onclick="createConfig()">🚀 ساخت کانفیگ</button>
                <div class="output" id="output"></div>
            </div>
        </div>

        <div id="tab-bulk" style="display:none">
            <div class="section-title">📦 ساخت گروهی کانفیگ</div>
            <div class="card">
                <div class="form-group">
                    <label>تعداد</label>
                    <input class="form-control" id="bulk-count" type="number" value="5" min="1" max="100">
                </div>
                <div class="row">
                    <div class="form-group">
                        <label>پروتکل</label>
                        <select class="form-control" id="bulk-proto">
                            <option value="vless-ws">VLESS + WS</option>
                            <option value="xhttp-packet">XHTTP packet-up</option>
                            <option value="xhttp-stream">XHTTP stream-up</option>
                            <option value="all">🔀 هر سه باهم</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>پیشوند نام</label>
                        <input class="form-control" id="bulk-prefix" type="text" value="user">
                    </div>
                </div>
                <button class="btn btn-success" onclick="createBulk()">📦 ساخت گروهی</button>
                <div class="output" id="bulk-output"></div>
            </div>
        </div>

        <div id="tab-sub" style="display:none">
            <div class="section-title">🔗 سابسکریپشن گروهی</div>
            <div class="card">
                <p style="font-size:13px;color:#7BAED4;margin-bottom:15px">چند کانفیگ رو با newline جدا کن تا یه لینک ساب واحد بسازه</p>
                <div class="form-group">
                    <label>لینک‌ها (هر خط یک لینک)</label>
                    <textarea class="form-control" id="sub-links" rows="5" placeholder="vless://...\nvmess://...\ntrojan://..."></textarea>
                </div>
                <button class="btn btn-info" onclick="makeSub()">🔗 ساخت ساب</button>
                <div class="output" id="sub-output"></div>
            </div>
        </div>
    </div>

    <script>
    let selectedProto = 'vless-ws';
    function selectProto(p,el){
        document.querySelectorAll('.proto-chip').forEach(c=>c.classList.remove('active'));
        el.classList.add('active');
        selectedProto = p;
    }
    function switchTab(tab,el){
        document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
        el.classList.add('active');
        document.getElementById('tab-create').style.display = tab==='create'?'block':'none';
        document.getElementById('tab-bulk').style.display = tab==='bulk'?'block':'none';
        document.getElementById('tab-sub').style.display = tab==='sub'?'block':'none';
    }
    async function createConfig(){
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = '⏳ در حال ساخت...';
        const out = document.getElementById('output');
        out.classList.remove('show');
        try{
            const r = await fetch('/api/create',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                    protocol: selectedProto,
                    source: document.getElementById('source').value,
                    inbound_id: parseInt(document.getElementById('inbound').value),
                    volume_gb: parseInt(document.getElementById('volume').value),
                    expiry_days: parseInt(document.getElementById('expiry').value),
                    username: document.getElementById('username').value || undefined
                })
            });
            const d = await r.json();
            if(d.success){
                let txt = '✅ کانفیگ ساخته شد!\n\n';
                if(d.subscription_url) txt += '🔗 ساب: ' + d.subscription_url + '\n';
                if(d.links) txt += '\n' + d.links.join('\n');
                out.textContent = txt;
            } else {
                out.textContent = '❌ خطا: ' + (d.error || 'نامشخص');
            }
        } catch(e){
            out.textContent = '❌ خطا: ' + e.message;
        }
        out.classList.add('show');
        btn.disabled = false;
        btn.textContent = '🚀 ساخت کانفیگ';
    }
    async function createBulk(){
        document.getElementById('bulk-output').classList.remove('show');
        try{
            const r = await fetch('/api/create-bulk',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                    count: parseInt(document.getElementById('bulk-count').value),
                    protocol: document.getElementById('bulk-proto').value,
                    prefix: document.getElementById('bulk-prefix').value
                })
            });
            const d = await r.json();
            if(d.success && d.results){
                let txt = d.results.map(item => item.link).join('\n\n');
                document.getElementById('bulk-output').textContent = txt;
            }
        } catch(e){
            document.getElementById('bulk-output').textContent = '❌ خطا: ' + e.message;
        }
        document.getElementById('bulk-output').classList.add('show');
    }
    async function makeSub(){
        document.getElementById('sub-output').classList.remove('show');
        try{
            const r = await fetch('/api/make-sub',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                    links: document.getElementById('sub-links').value.split('\n').filter(l=>l.trim())
                })
            });
            const d = await r.json();
            document.getElementById('sub-output').textContent = d.subscription || '❌ خطا';
        } catch(e){
            document.getElementById('sub-output').textContent = '❌ خطا: ' + e.message;
        }
        document.getElementById('sub-output').classList.add('show');
    }
    </script>
    </body></html>
    """)

# ─── API: ساخت کانفیگ ─────────────────────────────────────────────────────
@app.post("/api/create")
async def api_create(request: Request):
    body = await request.json()
    protocol = body.get("protocol", "vless-ws")
    source = body.get("source", CONFIG["default_mode"])
    inbound_id = body.get("inbound_id", 1)
    volume_gb = body.get("volume_gb", 0)
    expiry_days = body.get("expiry_days", 0)
    username = body.get("username", "")

    total_bytes = volume_gb * 1024**3 if volume_gb > 0 else 0

    if source == "xui":
        client = XUIClient(CONFIG["xui_url"], CONFIG["xui_user"], CONFIG["xui_pass"])
        result = await client.add_client(
            inbound_id=inbound_id,
            email=username or f"user_{generate_uuid()[:8]}",
            total_gb=total_bytes,
            expiry_days=expiry_days
        )
        await client.close()
        if result.get("success"):
            # ساخت لینک‌های پروتکل
            uuid = result.get("client_id", generate_uuid())
            host = CONFIG["xui_url"].replace("https://", "").replace("http://", "").split(":")[0]
            port = CONFIG["default_port"]
            links = []
            if protocol == "all":
                links = build_all_protocols(uuid, host, port)
            else:
                funcs = {
                    "vless-ws": build_vless_ws,
                    "xhttp-packet": build_xhttp_packet,
                    "xhttp-stream": build_xhttp_stream
                }
                if protocol in funcs:
                    links.append(funcs[protocol](uuid, host, port))
            return {
                "success": True,
                "subscription_url": result.get("subscription_url", ""),
                "client_id": uuid,
                "links": links,
                "source": "xui"
            }
        else:
            return {"success": False, "error": result.get("error", "unknown")}

    elif source == "marzban":
        client = MarzbanClient(CONFIG["marzban_url"], CONFIG["marzban_user"], CONFIG["marzban_pass"])
        result = await client.create_user(
            username=username or f"user_{generate_uuid()[:8]}",
            total_gb=total_bytes,
            expiry_days=expiry_days
        )
        await client.close()
        if result.get("success"):
            return {
                "success": True,
                "subscription_url": result.get("subscription_url", ""),
                "username": result.get("username", ""),
                "source": "marzban"
            }
        else:
            return {"success": False, "error": result.get("error", "unknown")}

    return {"success": False, "error": "منبع نامعتبر"}

# ─── API: ساخت گروهی ──────────────────────────────────────────────────────
@app.post("/api/create-bulk")
async def api_create_bulk(request: Request):
    body = await request.json()
    count = min(body.get("count", 5), 100)
    protocol = body.get("protocol", "vless-ws")
    prefix = body.get("prefix", "user")
    
    results = generate_bulk_configs(protocol, "example.com", CONFIG["default_port"], count, prefix)
    links = [r["link"] for r in results]
    sub = build_subscription(links)
    
    return {
        "success": True,
        "count": count,
        "results": results,
        "subscription": sub
    }

# ─── API: ساخت سابسکریپشن ─────────────────────────────────────────────────
@app.post("/api/make-sub")
async def api_make_sub(request: Request):
    body = await request.json()
    links = body.get("links", [])
    if not links:
        return {"success": False, "error": "لینکی وارد نشده"}
    sub = build_subscription(links)
    return {
        "success": True,
        "count": len(links),
        "subscription": sub
    }

# ─── استارت ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=CONFIG["port"], reload=False)
