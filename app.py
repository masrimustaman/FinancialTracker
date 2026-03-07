import streamlit as st
import os
import google.generativeai as genai
import json
from datetime import datetime
from PIL import Image
import io
import pandas as pd
from db import init_db, save_transaction, get_recent_transactions, get_monthly_report, get_available_months, get_unique_categories, get_unique_accounts, run_query, delete_transaction, update_transaction
import streamlit.components.v1 as components
import re

# --- Configuration ---
st.set_page_config(page_title="Expense Tracker", page_icon="🧾", layout="wide")

# Directory for storing receipt files
RECEIPTS_DIR = "data/receipts"
if not os.path.exists(RECEIPTS_DIR):
    os.makedirs(RECEIPTS_DIR)

# PWA Injection
components.html(
    """
    <script>
    const manifest = document.createElement('link');
    manifest.rel = 'manifest';
    manifest.href = '/static/manifest.json';
    document.head.appendChild(manifest);

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/static/sw.js');
    }
    </script>
    """,
    height=0,
)

# Initialize DB on startup
init_db()

# Setup Gemini API
st.sidebar.subheader("🔑 API Configuration")
env_api_key = os.environ.get("GEMINI_API_KEY")
if not env_api_key:
    try:
        env_api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        env_api_key = ""

API_KEY = st.sidebar.text_input("Gemini API Key", type="password", value=env_api_key)

if API_KEY:
    genai.configure(api_key=API_KEY)
    model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    try:
        model = genai.GenerativeModel(model_name)
    except Exception:
        model = genai.GenerativeModel("gemini-2.0-flash")
else:
    st.sidebar.warning("Please enter your Google Gemini API Key.")

# --- Helper Functions ---
def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def save_receipt_file(file_bytes, date, payee, amount, original_name):
    ext = os.path.splitext(original_name)[1] or (".jpg")
    clean_payee = sanitize_filename(payee)
    timestamp = datetime.now().strftime("%H%M%S")
    amount_str = str(int(round(amount)))
    filename = f"{date}_{clean_payee}_{amount_str}_{timestamp}{ext}"
    file_path = os.path.join(RECEIPTS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return file_path

def parse_receipt_with_ai(file_bytes, mime_type):
    if not API_KEY: return None
    existing_categories = get_unique_categories()
    existing_accounts = get_unique_accounts()
    category_context = f"Suggested categories: {', '.join(existing_categories)}" if existing_categories else ""
    account_context = f"Known accounts: {', '.join(existing_accounts)}" if existing_accounts else ""

    prompt = f"""
    Act as an OCR assistant. Extract:
    - Date (YYYY-MM-DD)
    - Payee name
    - Item name (short desc)
    - Invoice Number
    - Total Amount (float)
    - Category. {category_context}
    - Account. {account_context}
    Return STRICTLY JSON with keys: "date", "payee", "item_name", "invoice_number", "amount", "category", "account".
    """
    
    try:
        if 'pdf' in str(mime_type).lower():
            temp_path = f"data/temp_{datetime.now().strftime('%H%M%S')}.pdf"
            with open(temp_path, "wb") as f: f.write(file_bytes)
            try:
                uploaded_file = genai.upload_file(path=temp_path)
                response = model.generate_content([prompt, uploaded_file])
            finally:
                if os.path.exists(temp_path): os.remove(temp_path)
        else:
            img = Image.open(io.BytesIO(file_bytes))
            response = model.generate_content([prompt, img])
        
        text = response.text
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return None
    except Exception: return None

# --- Pages ---
def entry_page():
    st.title("📸 Receipt Entry")
    
    if "form_data" not in st.session_state:
        st.session_state.form_data = {
            "date": datetime.now().strftime("%Y-%m-%d"), "payee": "", "item_name": "",
            "invoice_number": "", "amount": 0.0, "category": "Misc", "account": "Checking",
            "file_content": None, "original_name": ""
        }
    if "pending_items" not in st.session_state: st.session_state.pending_items = []

    files_to_process = []

    # --- TOP BUTTON ---
    ai_col1, ai_col2 = st.columns([3, 1])
    with ai_col1:
        parse_btn = st.button("✨ PARSE RECEIPT WITH AI", type="primary", use_container_width=True)
    with ai_col2:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.pop("cam_data_val", None)
            st.rerun()

    # --- INPUT TABS ---
    tab1, tab2 = st.tabs(["📸 Camera", "📂 Upload"])
    
    with tab1:
        # CSS to hide the bridge text input entirely
        st.markdown(
            """
            <style>
            div[data-testid="stTextInput"]:has(input[aria-label="Hidden Camera Data"]) {
                display: none;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        # Hidden input to receive data from JS
        captured_data = st.text_input("Hidden Camera Data", key="cam_data_val", label_visibility="collapsed")
        
        camera_html = """
        <div style="display: flex; flex-direction: column; align-items: center; gap: 10px; background: #f0f2f6; padding: 15px; border-radius: 15px;">
            <div style="display: flex; gap: 10px; width: 100%;">
                <button id="snap" style="flex: 2; padding: 18px; background: #FF4B4B; color: white; border: none; border-radius: 10px; font-weight: bold; font-size: 20px;">📸 CAPTURE PHOTO</button>
                <button id="flip" style="flex: 1; padding: 18px; background: white; border: 2px solid #FF4B4B; border-radius: 10px; font-weight: bold;">🔄 FLIP</button>
            </div>
            <p id="status" style="margin: 0; font-size: 14px; font-weight: bold; color: #FF4B4B;">Ready</p>
            <video id="v" width="100%" height="auto" autoplay playsinline style="border-radius: 10px; background: black; max-height: 400px;"></video>
            <canvas id="c" style="display:none;"></canvas>
        </div>
        <script>
        const v = document.getElementById('v'), snap = document.getElementById('snap'), c = document.getElementById('c'), flip = document.getElementById('flip'), status = document.getElementById('status');
        let stream = null, useBack = true;
        async function init() {
            if (stream) stream.getTracks().forEach(t => t.stop());
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: useBack ? "environment" : "user" } });
                v.srcObject = stream;
                status.innerText = "Camera: " + (useBack ? "BACK" : "FRONT");
            } catch (e) { status.innerText = "Error: " + e.message; }
        }
        flip.onclick = () => { useBack = !useBack; init(); };
        snap.onclick = () => {
            const ctx = c.getContext('2d'); c.width = v.videoWidth; c.height = v.videoHeight; ctx.drawImage(v, 0, 0);
            const data = c.toDataURL('image/jpeg', 0.9);
            const inputs = window.parent.document.querySelectorAll('input');
            for (let i of inputs) { if (i.ariaLabel === "Hidden Camera Data") { i.value = data; i.dispatchEvent(new Event('input', {bubbles:true})); break; } }
            status.innerText = "✅ PHOTO TAKEN!";
        };
        init();
        </script>
        """
        components.html(camera_html, height=550)
        
        if captured_data and captured_data.startswith("data:image"):
            import base64
            img_bytes = base64.b64decode(captured_data.split(",")[1])
            files_to_process.append({"name": "capture.jpg", "content": img_bytes, "mime_type": "image/jpeg"})

    with tab2:
        up = st.file_uploader("Upload", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)
        if up:
            for f in up: files_to_process.append({"name": f.name, "content": f.getvalue(), "mime_type": f.type})

    # --- PROCESS AI ---
    if parse_btn:
        if not files_to_process:
            st.warning("Please capture a photo or upload a file first!")
        else:
            with st.spinner("AI analyzing..."):
                for f in files_to_process:
                    res = parse_receipt_with_ai(f["content"], f["mime_type"])
                    if res:
                        res["file_content"], res["original_name"] = f["content"], f["name"]
                        st.session_state.pending_items.append(res)
                if st.session_state.pending_items:
                    st.session_state.form_data.update(st.session_state.pending_items.pop(0))
                    st.success("Analysis complete!")
                    st.rerun()

    # --- VERIFICATION FORM ---
    st.divider()
    if st.session_state.pending_items: st.info(f"📂 {len(st.session_state.pending_items)} more items in queue.")
    
    with st.form("entry_form"):
        col1, col2 = st.columns(2)
        with col1:
            d_val = st.text_input("Date", value=st.session_state.form_data["date"])
            p_val = st.text_input("Payee", value=st.session_state.form_data["payee"])
            i_val = st.text_input("Item", value=st.session_state.form_data["item_name"])
            inv_val = st.text_input("Invoice #", value=st.session_state.form_data["invoice_number"])
            a_val = st.number_input("Amount", value=float(st.session_state.form_data["amount"]), step=0.01)
        with col2:
            cat_val = st.text_input("Category", value=st.session_state.form_data["category"])
            acc_val = st.text_input("Account", value=st.session_state.form_data["account"])
        
        if st.form_submit_button("💾 SAVE TRANSACTION"):
            fp = None
            if st.session_state.form_data.get("file_content"):
                fp = save_receipt_file(st.session_state.form_data["file_content"], d_val, p_val, a_val, st.session_state.form_data["original_name"])
            if save_transaction(d_val, p_val, a_val, cat_val, acc_val, fp, item_name=i_val, invoice_number=inv_val):
                st.success("Saved!")
                if st.session_state.pending_items:
                    st.session_state.form_data.update(st.session_state.pending_items.pop(0))
                else:
                    st.session_state.form_data = {"date": datetime.now().strftime("%Y-%m-%d"), "payee": "", "item_name": "", "invoice_number": "", "amount": 0.0, "category": "Misc", "account": "Checking", "file_content": None, "original_name": ""}
                st.rerun()

    with st.sidebar:
        st.subheader("Recent")
        rdf = get_recent_transactions(5)
        if not rdf.empty: st.dataframe(rdf[["date", "payee", "amount"]], hide_index=True)

def report_page():
    st.title("📊 Reports")
    m = get_available_months()
    if not m: return st.info("No data.")
    sm = st.selectbox("Month", m)
    y, mon = sm.split("-")
    df = get_monthly_report(y, mon)
    if not df.empty:
        st.metric("Total", f"${df['amount'].sum():,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)

def editor_page():
    st.title("✏️ Editor")
    df, _ = run_query("SELECT * FROM transactions ORDER BY date DESC LIMIT 100")
    st.data_editor(df, use_container_width=True, hide_index=True)

def admin_page():
    st.title("🗄️ Admin")
    q = st.text_area("SQL", "SELECT * FROM transactions LIMIT 50")
    if st.button("Run"):
        res, err = run_query(q)
        if err: st.error(err)
        else: st.dataframe(res, use_container_width=True, hide_index=True)

pg = st.navigation([st.Page(entry_page, title="Add", icon="📸"), st.Page(report_page, title="Reports", icon="📊"), st.Page(editor_page, title="Editor", icon="✏️"), st.Page(admin_page, title="Admin", icon="🗄️")])
pg.run()
