import streamlit as st
import os
import google.generativeai as genai
import json
from datetime import datetime
from PIL import Image
import io
import pandas as pd
from db import init_db, save_transaction, get_recent_transactions, get_monthly_report, get_available_months
import streamlit.components.v1 as components

# --- Configuration ---
st.set_page_config(page_title="Expense Tracker", page_icon="🧾", layout="wide")

# PWA Injection: This adds the manifest and service worker registration to the app
components.html(
    """
    <script>
    const manifest = document.createElement('link');
    manifest.rel = 'manifest';
    manifest.href = '/app/static/manifest.json';
    document.head.appendChild(manifest);

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/app/static/sw.js');
    }
    </script>
    """,
    height=0,
)

# Initialize DB on startup
init_db()

# Setup Gemini API
# Standard practice: check environment variables first, then streamlit secrets
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        API_KEY = None

if not API_KEY:
    st.sidebar.warning("GEMINI_API_KEY not found in .streamlit/secrets.toml or environment variables. Please enter it below:")
    API_KEY = st.sidebar.text_input("Gemini API Key", type="password")

if API_KEY:
    genai.configure(api_key=API_KEY)
    # Using 'gemini-1.5-flash' which is the standard model name for this package
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Please provide a Gemini API Key to use the AI features.")

# --- Helper Functions ---
def parse_receipt_with_ai(image_bytes):
    """Sends image to Gemini and returns structured JSON."""
    prompt = """
    Act as an OCR and accounting assistant. Analyze this receipt and extract:
    - Date (formatted exactly as YYYY-MM-DD)
    - Payee name
    - Total Amount (as a float)
    - A suitable expense category (e.g., 'Food', 'Utilities', 'Transport', 'Shopping')

    Return the data STRICTLY as a JSON object with keys: "date", "payee", "amount", "category".
    Do not include any other text or markdown formatting.
    """
    
    img = Image.open(io.BytesIO(image_bytes))
    response = model.generate_content([prompt, img])
    
    try:
        text = response.text
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            clean_json = text[start_idx:end_idx+1]
            return json.loads(clean_json)
        return None
    except Exception as e:
        st.error(f"Failed to parse AI response: {e}")
        return None

# --- Main App Logic ---
def entry_page():
    st.title("📸 Receipt Entry")
    st.markdown("Digitize your receipts and save them to SQLite.")

    # Initialize session state for form values
    if "form_data" not in st.session_state:
        st.session_state.form_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "payee": "",
            "amount": 0.0,
            "category": "Misc",
            "account": "Checking"
        }

    # 1. Input Section
    tab1, tab2 = st.tabs(["📸 Camera", "📂 Upload"])

    captured_image = None
    with tab1:
        camera_img = st.camera_input("Take a picture of your receipt")
        if camera_img:
            captured_image = camera_img.getvalue()

    with tab2:
        uploaded_file = st.file_uploader("Choose a receipt image...", type=["jpg", "jpeg", "png"])
        if uploaded_file:
            captured_image = uploaded_file.getvalue()

    # 2. AI Processing
    if captured_image:
        if st.button("✨ Parse with AI"):
            with st.spinner("Analyzing receipt..."):
                result = parse_receipt_with_ai(captured_image)
                if result:
                    st.session_state.form_data.update(result)
                    st.success("AI extraction complete!")

    # 3. Verification Form
    st.divider()
    st.subheader("Verify & Edit Details")

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
            if save_transaction(date_val, payee_val, amount_val, category_val, account_val):
                st.success(f"Successfully saved to database!")
                # Reset form for next entry
                st.session_state.form_data = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "payee": "",
                    "amount": 0.0,
                    "category": "Misc",
                    "account": "Checking"
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

# --- Sidebar Navigation ---
pg = st.navigation([
    st.Page(entry_page, title="Add Receipt", icon="📸"),
    st.Page(report_page, title="Reports", icon="📊"),
])
pg.run()
