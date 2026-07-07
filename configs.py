# configs.py - ساخت کانفیگ با پروتکل‌های VLESS+WS, XHTTP packet-up, XHTTP stream-up
import json
import base64
import urllib.parse
import secrets
import string

def generate_uuid() -> str:
    h = secrets.token_hex(16)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

def gen_rand_str(l=8):
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(l))

def build_vless_ws(uuid: str, host: str, port: int = 443, path: str = "", remark: str = "VLESS-WS") -> str:
    """VLESS + WebSocket + TLS"""
    ws_path = path or f"/ws/{uuid[:8]}"
    params = {
        "encryption": "none",
        "security": "tls",
        "type": "ws",
        "host": host,
        "path": ws_path,
        "sni": host,
        "fp": "chrome",
        "alpn": "http/1.1"
    }
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    return f"vless://{uuid}@{host}:{port}?{query}#{urllib.parse.quote(remark)}"

def build_xhttp_packet(uuid: str, host: str, port: int = 443, path: str = "", remark: str = "XHTTP-Packet") -> str:
    """XHTTP · packet-up (CDN compatible)"""
    xpath = path or f"/xhttp-packet/{uuid[:8]}"
    params = {
        "encryption": "none",
        "security": "tls",
        "type": "xhttp",
        "mode": "packet-up",
        "host": host,
        "path": xpath,
        "sni": host,
        "fp": "chrome",
        "alpn": "h2,http/1.1"
    }
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    return f"vless://{uuid}@{host}:{port}?{query}#{urllib.parse.quote(remark)}"

def build_xhttp_stream(uuid: str, host: str, port: int = 443, path: str = "", remark: str = "XHTTP-Stream") -> str:
    """XHTTP · stream-up (low latency)"""
    xpath = path or f"/xhttp-stream/{uuid[:8]}"
    params = {
        "encryption": "none",
        "security": "tls",
        "type": "xhttp",
        "mode": "stream-up",
        "host": host,
        "path": xpath,
        "sni": host,
        "fp": "chrome",
        "alpn": "h2,http/1.1"
    }
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    return f"vless://{uuid}@{host}:{port}?{query}#{urllib.parse.quote(remark)}"

def build_vmess_ws(uuid: str, host: str, port: int = 443, path: str = "", remark: str = "VMess-WS") -> str:
    """VMess + WebSocket + TLS (پشتیبانی بیشتر کلاینت‌ها)"""
    vmess_path = path or f"/vmess/{uuid[:8]}"
    obj = {
        "v": "2",
        "ps": remark,
        "add": host,
        "port": port,
        "id": uuid,
        "aid": "0",
        "scy": "auto",
        "net": "ws",
        "type": "none",
        "host": host,
        "path": vmess_path,
        "tls": "tls",
        "sni": host,
        "alpn": ""
    }
    return f"vmess://{base64.b64encode(json.dumps(obj, separators=(',',':')).encode()).decode()}"

def build_all_protocols(uuid: str, host: str, port: int = 443) -> list:
    """هر سه پروتکل با یه UUID مشترک (برای سابسکریپشن گروهی)"""
    return [
        build_vless_ws(uuid, host, port),
        build_xhttp_packet(uuid, host, port),
        build_xhttp_stream(uuid, host, port)
    ]

def build_subscription(links: list, base64_encode: bool = True) -> str:
    """تبدیل لیست کانفیگ‌ها به متن سابسکریپشن"""
    text = "\n".join(links)
    if base64_encode:
        return base64.b64encode(text.encode()).decode()
    return text

def parse_subscription(base64_text: str) -> list:
    """تبدیل سابسکریپشن به لیست کانفیگ‌ها"""
    try:
        text = base64.b64decode(base64_text.encode()).decode()
        return [line.strip() for line in text.split("\n") if line.strip()]
    except:
        return []

def generate_bulk_configs(
    protocol_type: str,
    host: str,
    port: int = 443,
    count: int = 1,
    prefix: str = "user"
) -> list:
    """ساخت گروهی کانفیگ"""
    results = []
    for i in range(count):
        uuid = generate_uuid()
        remark = f"{prefix}_{i+1}"
        if protocol_type == "vless-ws":
            link = build_vless_ws(uuid, host, port, remark=remark)
        elif protocol_type == "xhttp-packet":
            link = build_xhttp_packet(uuid, host, port, remark=remark)
        elif protocol_type == "xhttp-stream":
            link = build_xhttp_stream(uuid, host, port, remark=remark)
        elif protocol_type == "vmess-ws":
            link = build_vmess_ws(uuid, host, port, remark=remark)
        elif protocol_type == "all":
            link = "\n".join(build_all_protocols(uuid, host, port))
        else:
            link = build_vless_ws(uuid, host, port, remark=remark)
        results.append({"uuid": uuid, "remark": remark, "link": link})
    return results
