# xui_api.py - اتصال به API پنل 3X-UI
import httpx
import json
import uuid as uuid_lib
import logging

logger = logging.getLogger("xui_api")

class XUIClient:
    def __init__(self, base_url: str, username: str = "", password: str = "", api_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.api_token = api_token
        self.session = httpx.AsyncClient(verify=False, timeout=15.0)
        self.cookies = {}
        self.logged_in = False

    async def login(self) -> bool:
        """لاگین به پنل 3X-UI با یوزرنیم/پسورد"""
        if self.api_token:
            self.logged_in = True
            return True
        try:
            resp = await self.session.post(
                f"{self.base_url}/login",
                data={"username": self.username, "password": self.password},
                timeout=10.0
            )
            if resp.status_code == 200:
                self.cookies = dict(resp.cookies)
                self.logged_in = True
                logger.info("✅ 3X-UI login successful")
                return True
            else:
                logger.error(f"❌ 3X-UI login failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 3X-UI login error: {e}")
            return False

    async def get_inbounds(self) -> list:
        """گرفتن لیست inbound‌های موجود"""
        if not self.logged_in and not await self.login():
            return []
        try:
            headers = {"Cookie": f"token={self.cookies.get('token', '')}"} if self.cookies else {}
            if self.api_token:
                headers = {"Authorization": f"Bearer {self.api_token}"}
            resp = await self.session.post(
                f"{self.base_url}/panel/api/inbounds/list",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data.get("obj", [])
            logger.warning(f"⚠️ get_inbounds failed: {resp.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"❌ get_inbounds error: {e}")
            return []

    async def add_client(
        self,
        inbound_id: int,
        email: str = "",
        total_gb: int = 0,       # 0 = unlimited
        expiry_days: int = 0,    # 0 = unlimited
        limit_ip: int = 0,       # 0 = unlimited
        flow: str = "",
        sub_id: str = ""
    ) -> dict:
        """
        ساخت کاربر جدید روی inbound مشخص
        Returns: {"success": bool, "subscription_url": str, "client_id": str, ...}
        """
        if not self.logged_in and not await self.login():
            return {"success": False, "error": "login failed"}

        client_uuid = str(uuid_lib.uuid4())
        client_email = email or f"user_{client_uuid[:8]}"
        client_sub_id = sub_id or client_uuid[:8]

        expiry_time = 0
        if expiry_days > 0:
            import time
            expiry_time = int((time.time() + expiry_days * 86400) * 1000)

        client_data = {
            "id": client_uuid,
            "email": client_email,
            "enable": True,
            "expiryTime": expiry_time,
            "limitIp": limit_ip,
            "totalGB": total_gb,
            "tgId": "",
            "subId": client_sub_id,
            "flow": flow
        }

        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [client_data]
            })
        }

        try:
            headers = {"Cookie": f"token={self.cookies.get('token', '')}"} if self.cookies else {}
            if self.api_token:
                headers = {"Authorization": f"Bearer {self.api_token}"}
            headers["Content-Type"] = "application/json"

            resp = await self.session.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                json=payload,
                headers=headers
            )

            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    # ساخت لینک ساب
                    sub_url = f"{self.base_url}/sub/{client_sub_id}"
                    logger.info(f"✅ Client created: {client_email}")
                    return {
                        "success": True,
                        "client_id": client_uuid,
                        "client_email": client_email,
                        "sub_id": client_sub_id,
                        "subscription_url": sub_url,
                        "inbound_id": inbound_id,
                        "raw": result
                    }
                else:
                    return {"success": False, "error": result.get("msg", "unknown")}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            logger.error(f"❌ add_client error: {e}")
            return {"success": False, "error": str(e)}

    async def add_clients_bulk(
        self,
        inbound_id: int,
        count: int = 1,
        total_gb: int = 0,
        expiry_days: int = 0,
        limit_ip: int = 0,
        prefix: str = "user"
    ) -> list:
        """ساخت چندتا کاربر یکجا"""
        results = []
        for i in range(count):
            email = f"{prefix}_{i+1}"
            result = await self.add_client(
                inbound_id=inbound_id,
                email=email,
                total_gb=total_gb,
                expiry_days=expiry_days,
                limit_ip=limit_ip
            )
            results.append(result)
        return results

    async def get_client_traffic(self, email: str) -> dict:
        """گرفتن ترافیک مصرفی یک کاربر"""
        if not self.logged_in and not await self.login():
            return {}
        try:
            headers = {"Cookie": f"token={self.cookies.get('token', '')}"} if self.cookies else {}
            if self.api_token:
                headers = {"Authorization": f"Bearer {self.api_token}"}
            resp = await self.session.post(
                f"{self.base_url}/panel/api/inbounds/getClientTraffics/{email}",
                headers=headers
            )
            if resp.status_code == 200:
                return resp.json()
            return {}
        except:
            return {}

    async def delete_client(self, inbound_id: int, client_id: str) -> bool:
        """حذف کاربر"""
        if not self.logged_in and not await self.login():
            return False
        try:
            headers = {"Cookie": f"token={self.cookies.get('token', '')}"} if self.cookies else {}
            if self.api_token:
                headers = {"Authorization": f"Bearer {self.api_token}"}
            resp = await self.session.post(
                f"{self.base_url}/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
                headers=headers
            )
            return resp.status_code == 200
        except:
            return False

    async def close(self):
        await self.session.aclose()


# === تابع کمکی برای استفاده در main.py ===
async def create_config_on_xui(
    xui_url: str,
    xui_user: str,
    xui_pass: str,
    inbound_id: int,
    email: str = "",
    total_gb: int = 0,
    expiry_days: int = 0
) -> dict:
    """
    تابع ساده برای ساخت کانفیگ روی 3X-UI
    مثال:
        result = await create_config_on_xui(
            "https://your-server.com:2060", "admin", "pass", 1, "user1", 10*1024, 30
        )
        print(result["subscription_url"])
    """
    client = XUIClient(xui_url, username=xui_user, password=xui_pass)
    result = await client.add_client(
        inbound_id=inbound_id,
        email=email,
        total_gb=total_gb,
        expiry_days=expiry_days
    )
    await client.close()
    return result
