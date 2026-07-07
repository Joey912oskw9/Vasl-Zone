# marzban_api.py - اتصال به API پنل Marzban (Gozargah)
import httpx
import json
import logging

logger = logging.getLogger("marzban_api")

class MarzbanClient:
    def __init__(self, base_url: str, username: str = "", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = httpx.AsyncClient(verify=False, timeout=15.0)
        self.token = ""
        self.logged_in = False

    async def login(self) -> bool:
        """گرفتن توکن از Marzban"""
        try:
            resp = await self.session.post(
                f"{self.base_url}/api/admin/token",
                data={
                    "username": self.username,
                    "password": self.password,
                    "grant_type": "password"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token", "")
                self.logged_in = bool(self.token)
                logger.info("✅ Marzban login successful")
                return self.logged_in
            else:
                logger.error(f"❌ Marzban login failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Marzban login error: {e}")
            return False

    async def create_user(
        self,
        username: str,
        total_gb: int = 0,
        expiry_days: int = 0,
        data_limit_reset_strategy: str = "no_reset",
        status: str = "active",
        note: str = ""
    ) -> dict:
        """
        ساخت کاربر جدید در Marzban
        Returns: {"success": bool, "subscription_url": str, "username": str, ...}
        """
        if not self.logged_in and not await self.login():
            return {"success": False, "error": "login failed"}

        expiry_date = None
        if expiry_days > 0:
            from datetime import datetime, timedelta
            expiry_date = (datetime.now() + timedelta(days=expiry_days)).isoformat()

        payload = {
            "username": username,
            "proxies": {
                "vless": {"flow": ""},
                "vmess": {},
                "trojan": {"password": username},
                "shadowsocks": {"method": "chacha20-ietf-poly1305", "password": username}
            },
            "inbounds": {
                "vless": ["VLESS_INBOUND"],
                "vmess": ["VMESS_INBOUND"],
                "trojan": ["TROJAN_INBOUND"]
            },
            "expire": expiry_date,
            "data_limit": total_gb if total_gb > 0 else 0,
            "data_limit_reset_strategy": data_limit_reset_strategy,
            "status": status,
            "note": note
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            resp = await self.session.post(
                f"{self.base_url}/api/user",
                json=payload,
                headers=headers
            )

            if resp.status_code in [200, 201]:
                data = resp.json()
                sub_url = f"{self.base_url}/sub/{data.get('subscription_url', username)}"
                logger.info(f"✅ Marzban user created: {username}")
                return {
                    "success": True,
                    "username": username,
                    "subscription_url": sub_url,
                    "raw": data
                }
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            logger.error(f"❌ Marzban create_user error: {e}")
            return {"success": False, "error": str(e)}

    async def get_users(self, offset: int = 0, limit: int = 50) -> list:
        """لیست کاربران"""
        if not self.logged_in and not await self.login():
            return []
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = await self.session.get(
                f"{self.base_url}/api/users?offset={offset}&limit={limit}",
                headers=headers
            )
            if resp.status_code == 200:
                return resp.json().get("users", [])
            return []
        except:
            return []

    async def delete_user(self, username: str) -> bool:
        """حذف کاربر"""
        if not self.logged_in and not await self.login():
            return False
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = await self.session.delete(
                f"{self.base_url}/api/user/{username}",
                headers=headers
            )
            return resp.status_code == 200
        except:
            return False

    async def get_user_traffic(self, username: str) -> dict:
        """گرفتن آمار ترافیک"""
        if not self.logged_in and not await self.login():
            return {}
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = await self.session.get(
                f"{self.base_url}/api/user/{username}",
                headers=headers
            )
            if resp.status_code == 200:
                return resp.json()
            return {}
        except:
            return {}

    async def close(self):
        await self.session.aclose()


# === تابع کمکی ===
async def create_config_on_marzban(
    marzban_url: str,
    marzban_user: str,
    marzban_pass: str,
    username: str,
    total_gb: int = 0,
    expiry_days: int = 0
) -> dict:
    client = MarzbanClient(marzban_url, username=marzban_user, password=marzban_pass)
    result = await client.create_user(
        username=username,
        total_gb=total_gb,
        expiry_days=expiry_days
    )
    await client.close()
    return result
