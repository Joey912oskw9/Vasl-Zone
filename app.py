import json, uuid, time, os
from fastapi import FastAPI
import gradio as gr

app = FastAPI()
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"groups": {}, "users": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def create_configs(protocols, count, port, expiry, group, volume):
    data = load_data()
    output_lines = []
    
    if group not in data["groups"]:
        data["groups"][group] = []

    for _ in range(int(count)):
        user_id = str(uuid.uuid4())  # هر بار یک UUID جدید و خودکار می‌سازه
        
        # ساخت لینک شبیه‌سازی‌شده (اینجا می‌تونی آدرس سرور واقعیت رو بزنی)
        link = f"vless://{user_id}@YOUR_SERVER_IP:{port}?encryption=none&security=auto&type=ws&path=/vless#{group}"
        output_lines.append(link)
        
        data["groups"][group].append(user_id)
        data["users"].append({
            "id": user_id,
            "group": group,
            "expiry": expiry,
            "volume": volume,
            "protocols": protocols
        })
    
    save_data(data)
    return "\n".join(output_lines)  # هر کانفیگ در یک خط جدا

# ---------- بخش رابط کاربری Gradio ----------
def panel_ui():
    with gr.Blocks(theme=gr.themes.Soft(), title="Premium Panel") as demo:
        gr.Markdown("# 🚀 پنل مدیریت فروش کانفیگ")
        
        with gr.Row():
            protocols = gr.CheckboxGroup(
                ["vless+ws", "grpc", "shadowtls"], 
                label="پروتکل‌ها (چندتا رو هم‌زمان انتخاب کن)", 
                value=["vless+ws"]
            )
            count = gr.Number(label="تعداد کانفیگ", value=10, precision=0)
            port = gr.Number(label="پورت سرور (مثلاً 443)", value=443, precision=0)
        
        with gr.Row():
            expiry = gr.Textbox(label="تاریخ انقضا (مثلاً 2026-12-31)")
            group = gr.Textbox(label="نام گروه (مثلاً VIP)", value="VIP")
            volume = gr.Number(label="حجم (گیگابایت)", value=100, precision=0)

        generate_btn = gr.Button("🔥 ساخت کانفیگ‌های گروهی")
        output = gr.Textbox(label="لیست کانفیگ‌ها (همه در یک پیام)", lines=15)
        
        generate_btn.click(
            create_configs, 
            inputs=[protocols, count, port, expiry, group, volume], 
            outputs=output
        )
        
        gr.Markdown("---")
        gr.Markdown("🔗 **لینک ساب‌اسکریپشن اختصاصی:** `/public_page?group=VIP` (بعداً شخصی‌سازی کن)")
    return demo

# اتصال Gradio به FastAPI در مسیر اصلی (Root)
demo = panel_ui()
app = gr.mount_gradio_app(app, demo, path="/")
