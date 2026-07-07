import json, uuid, time, subprocess
from fastapi import FastAPI, Request
import gradio as gr
from xray_config import generate_config

app = FastAPI()
users_db = {}  # In-memory DB

def create_configs(protocols, count, port, expiry, group, volume):
    user_id = str(uuid.uuid4())
    config = generate_config(protocols, user_id)
    subprocess.run(["pkill", "xray"], stderr=subprocess.DEVNULL)
    with open("/etc/xray/config.json", "w") as f:
        json.dump(config, f)
    subprocess.Popen(["/usr/bin/xray", "-c", "/etc/xray/config.json"])
    return "\n".join([f"vless://{user_id}@localhost:{port}?..." for _ in range(count)])  # Example

def panel_ui():
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Premium VPN Panel")
        with gr.Row():
            protocols = gr.CheckboxGroup(["vless+ws", "grpc"], label="Protocols", value=["vless+ws"])
            count = gr.Number(label="Number of Configs", value=10, precision=0)
            port = gr.Number(label="Port", value=443, precision=0)
            expiry = gr.Textbox(label="Expiry (YYYY-MM-DD)")
            group = gr.Textbox(label="Group Name", value="VIP")
            volume = gr.Number(label="Volume (GB)", value=100, precision=0)
        generate_btn = gr.Button("Generate Configs")
        output = gr.Textbox(label="Configs Output", lines=10)
        generate_btn.click(create_configs, inputs=[protocols, count, port, expiry, group, volume], outputs=output)
        gr.Markdown("### Public Page: [Subscription Link](/public_page)")
    return demo

@app.get("/public_page")
async def public_page():
    return """
    <html><body><h1>Subscription Links</h1>
    <pre>vless://... configs here</pre>
    </body></html>"""

if __name__ == "__main__":
    demo = panel_ui()
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860)  # Must be port 7860
