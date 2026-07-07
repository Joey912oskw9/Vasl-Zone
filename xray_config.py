import json, uuid
from typing import List, Dict

def generate_config(protocols: List[str], user_id: str, ws_path: str = "ws") -> Dict:
    inbounds = []
    for p in protocols:
        config = {"port": 10000, "listen": "127.0.0.1", "protocol": "vless",
                  "settings": {"clients": [{"id": user_id}], "decryption": "none"}}
        if p == "vless+ws":
            config["streamSettings"] = {"network": "ws", "wsSettings": {"path": f"/{ws_path}"}}
        elif p == "grpc":
            config["streamSettings"] = {"network": "grpc", "grpcSettings": {"serviceName": "vless"}}
        # add other protocols
        inbounds.append(config)
    return {"inbounds": inbounds, "outbounds": [{"protocol": "freedom"}]}
