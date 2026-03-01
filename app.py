import streamlit as st
import os
import google.generativeai as genai
import json
from datetime import datetime
from PIL import Image
import io
import pandas as pd
from db import init_db, save_transaction, get_recent_transactions, get_monthly_report, get_available_months, get_unique_categories, get_unique_accounts, run_query
import streamlit.components.v1 as components
import re

# --- Configuration ---
st.set_page_config(page_title="Expense Tracker", page_icon="🧾", layout="wide")

# Directory for storing receipt files
RECEIPTS_DIR = "data/receipts"
if not os.path.exists(RECEIPTS_DIR):
    os.makedirs(RECEIPTS_DIR)

# PWA Injection: This adds the manifest and service worker registration to the app
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
    
    # Allow model selection via environment variable, defaulting to gemini-2.5-flash
    model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    
    # Using the specified model name
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        st.error(f"Failed to initialize model '{model_name}': {e}")
        # Fallback to a safe default if the provided one fails
        model = genai.GenerativeModel("gemini-2.0-flash")
else:
    st.sidebar.warning("Please enter your Google Gemini API Key above.")
    st.error("Please provide a Gemini API Key to use the AI features.")

# --- Helper Functions ---
def sanitize_filename(name):
    """Sanitizes strings for safe filesystem usage."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def save_receipt_file(file_bytes, date, payee, amount, original_name):
    """Saves file to disk and returns the relative path."""
    ext = os.path.splitext(original_name)[1] or (".pdf" if "pdf" in original_name.lower() else ".jpg")
    clean_payee = sanitize_filename(payee)
    timestamp = datetime.now().strftime("%H%M%S")
    
    # Round to nearest integer (e.g., 15.50 -> 16, 15.40 -> 15)
    amount_str = str(int(round(amount)))
    
    # Naming convention: YYYY-MM-DD_Payee_RoundedAmount_HHMMSS.ext
    filename = f"{date}_{clean_payee}_{amount_str}_{timestamp}{ext}"
    file_path = os.path.join(RECEIPTS_DIR, filename)
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return file_path

def parse_receipt_with_ai(file_bytes, mime_type):
    """Sends file to Gemini and returns structured JSON."""
    if not API_KEY:
        st.error("Please provide a Gemini API Key in the sidebar.")
        return None

    # Ensure model is initialized (it should be if API_KEY is present, but good to check)
    if 'model' not in globals():
        st.error("AI Model not initialized. Please check your API key.")
        return None

    # Fetch existing categories and accounts for context
    existing_categories = get_unique_categories()
    existing_accounts = get_unique_accounts()
    
    category_context = f"Suggested categories: {', '.join(existing_categories)}" if existing_categories else "Common categories: Food, Utilities, Transport, Shopping, Health, Entertainment"
    account_context = f"Known accounts: {', '.join(existing_accounts)}" if existing_accounts else "Common accounts: Cash, Credit Card, Checking, Debit Card"

    prompt = f"""
    Act as an OCR and accounting assistant. Analyze this receipt and extract:
    - Date (formatted exactly as YYYY-MM-DD)
    - Payee name
    - Total Amount (as a float)
    - A suitable expense category. {category_context}
    - The payment account or method used. {account_context}. 
      If a specific card brand or last 4 digits are mentioned, suggest 'Credit Card' or 'Debit Card' accordingly.

    Return the data STRICTLY as a JSON object with keys: "date", "payee", "amount", "category", "account".
    Do not include any other text or markdown formatting.
    """
    
    try:
        # Check if the file is a PDF (by mime type or extension)
        is_pdf = (mime_type == 'application/pdf') or \
                 (mime_type == 'application/octet-stream' and 'pdf' in str(mime_type).lower()) or \
                 (isinstance(mime_type, str) and 'pdf' in mime_type.lower())
        
        # Fallback check if mime_type is None or ambiguous but original_name (if available) ends in .pdf
        # Since we don't pass original_name to parse_receipt_with_ai currently, 
        # let's just make the mime_type check as broad as possible or use a try-except for PIL.
        
        if is_pdf:
            # For PDFs, it's safer to use the File API for processing
            # We'll save to a temporary file for uploading
            temp_path = f"data/temp_{datetime.now().strftime('%H%M%S')}.pdf"
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            
            try:
                # Upload to Gemini File API
                uploaded_file = genai.upload_file(path=temp_path, display_name="Receipt PDF")
                response = model.generate_content([prompt, uploaded_file])
                
                # Cleanup: You might want to delete the uploaded_file via File API if needed, 
                # but it expires automatically in 48h.
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        else:
            # Standard image processing
            img = Image.open(io.BytesIO(file_bytes))
            response = model.generate_content([prompt, img])
        
        text = response.text
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            clean_json = text[start_idx:end_idx+1]
            return json.loads(clean_json)
        return None
    except Exception as e:
        if "404" in str(e) or "not found" in str(e).lower():
            st.error(f"The selected model was not found: {e}")
            try:
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                st.info(f"Available models for your API key: {available_models}")
            except Exception as list_err:
                st.warning(f"Could not list available models: {list_err}")
        else:
            st.error(f"Failed to parse AI response: {e}")
        return None

# --- Main App Logic ---
def entry_page():
    st.title("📸 Receipt Entry")
    st.markdown("Digitize your receipts and save them to SQLite.")

    # Initialize session state
    if "form_data" not in st.session_state:
        st.session_state.form_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "payee": "",
            "amount": 0.0,
            "category": "Misc",
            "account": "Checking",
            "file_content": None,
            "original_name": ""
        }
    
    if "pending_items" not in st.session_state:
        st.session_state.pending_items = []

    # 1. Input Section
    tab1, tab2 = st.tabs(["📸 Camera", "📂 Upload"])

    files_to_process = []
    with tab1:
        camera_img = st.camera_input("Take a picture of your receipt")
        if camera_img:
            files_to_process.append({"name": "Camera Capture.jpg", "content": camera_img.getvalue(), "mime_type": "image/jpeg"})

    with tab2:
        uploaded_files = st.file_uploader("Choose receipt files (Images or PDF)...", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)
        if uploaded_files:
            for f in uploaded_files:
                files_to_process.append({"name": f.name, "content": f.getvalue(), "mime_type": f.type})

    # 2. AI Processing
    if files_to_process:
        if st.button(f"✨ Parse {len(files_to_process)} Receipt(s) with AI"):
            with st.spinner(f"Analyzing {len(files_to_process)} receipt(s)..."):
                new_items = []
                for file_data in files_to_process:
                    result = parse_receipt_with_ai(file_data["content"], file_data["mime_type"])
                    if result:
                        # Include file content for saving later
                        result["file_content"] = file_data["content"]
                        result["original_name"] = file_data["name"]
                        new_items.append(result)
                
                if new_items:
                    st.session_state.pending_items.extend(new_items)
                    # Load the first item from the newly added items if form is currently default
                    st.session_state.form_data.update(st.session_state.pending_items.pop(0))
                    st.success(f"Added {len(new_items)} items to queue. Reviewing the first one.")
                else:
                    st.error("AI could not extract data from the provided image(s).")

    # 3. Verification Form
    st.divider()
    st.subheader("Verify & Edit Details")

    # Queue status indicator
    if st.session_state.pending_items:
        st.info(f"📂 **{len(st.session_state.pending_items)}** more item(s) waiting in your processing queue.")
        if st.button("🗑️ Clear Queue"):
            st.session_state.pending_items = []
            st.rerun()

    with st.form("entry_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            date_val = st.text_input("Date (YYYY-MM-DD)", value=st.session_state.form_data["date"])
            payee_val = st.text_input("Payee", value=st.session_state.form_data["payee"])
            amount_val = st.number_input("Total Amount", value=float(st.session_state.form_data["amount"]), step=0.01, format="%.2f")

        with col2:
            category_val = st.text_input("Expense Category", value=st.session_state.form_data["category"])
            account_val = st.text_input("Payment Account", value=st.session_state.form_data["account"])

        submit_button = st.form_submit_button("💾 Save Transaction")

        if submit_button:
            # Save file first if we have content
            file_path = None
            if st.session_state.form_data.get("file_content"):
                file_path = save_receipt_file(
                    st.session_state.form_data["file_content"],
                    date_val,
                    payee_val,
                    amount_val,
                    st.session_state.form_data.get("original_name", "receipt.jpg")
                )

            if save_transaction(date_val, payee_val, amount_val, category_val, account_val, file_path):
                st.success(f"Successfully saved to database!")
                # Load next item from queue if available
                if st.session_state.pending_items:
                    st.session_state.form_data.update(st.session_state.pending_items.pop(0))
                else:
                    # Reset to defaults
                    st.session_state.form_data = {
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "payee": "",
                        "amount": 0.0,
                        "category": "Misc",
                        "account": "Checking",
                        "file_content": None,
                        "original_name": ""
                    }
                st.rerun()

    # Show recent entries in the sidebar
    with st.sidebar:
        st.subheader("Recent Entries")
        recent_df = get_recent_transactions(5)
        if not recent_df.empty:
            st.dataframe(recent_df[["date", "payee", "amount"]], hide_index=True)
        else:
            st.info("No recent entries found.")

def report_page():
    st.title("📊 Monthly Reports")
    st.markdown("View and download your monthly statements.")

    available_months = get_available_months()
    if not available_months:
        st.info("No data available yet. Add some receipts first!")
        return

    # User selection for month/year
    selected_month_str = st.selectbox("Select Month", available_months)
    year, month = selected_month_str.split("-")

    # Fetch data
    report_df = get_monthly_report(year, month)

    if not report_df.empty:
        # Display summary statistics
        total_spent = report_df["amount"].sum()
        count = len(report_df)
        
        col1, col2 = st.columns(2)
        col1.metric("Total Transactions", count)
        col2.metric("Total Monthly Spent", f"${total_spent:,.2f}")

        # Display dataframe
        st.dataframe(report_df.drop(columns=["id", "created_at"]), use_container_width=True, hide_index=True)

        # Download CSV
        csv = report_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Statement (CSV)",
            data=csv,
            file_name=f"statement_{selected_month_str}.csv",
            mime="text/csv",
        )

        # Basic visualization (category breakdown)
        st.subheader("Spending by Category")
        category_counts = report_df.groupby("category")["amount"].sum().reset_index()
        st.bar_chart(category_counts.set_index("category"))

    else:
        st.warning(f"No transactions found for {selected_month_str}.")

def sql_admin_page():
    st.title("🗄️ SQL Admin Console")
    st.markdown("Execute raw SQL commands against the database. Use with caution!")

    # Pre-filled query for convenience
    default_query = "SELECT * FROM transactions LIMIT 50"
    
    query = st.text_area("SQL Query", value=default_query, height=150)
    
    col1, col2 = st.columns([1, 4])
    with col1:
        run_button = st.button("🚀 Run Query", use_container_width=True)
    
    if run_button and query:
        with st.spinner("Executing query..."):
            result, error = run_query(query)
            
            if error:
                st.error(f"SQL Error: {error}")
            elif isinstance(result, pd.DataFrame):
                if result.empty:
                    st.info("Query returned no results.")
                else:
                    st.success(f"Query returned {len(result)} rows.")
                    st.dataframe(result, use_container_width=True, hide_index=True)
                    
                    # Download CSV
                    csv = result.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Results (CSV)",
                        data=csv,
                        file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )
            else:
                st.success(result)

# --- Sidebar Navigation ---
pg = st.navigation([
    st.Page(entry_page, title="Add Receipt", icon="📸"),
    st.Page(report_page, title="Reports", icon="📊"),
    st.Page(sql_admin_page, title="Admin (SQL)", icon="🗄️"),
])
pg.run()
