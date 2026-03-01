# 🧾 AI Receipt Tracker & Reporter

An intelligent expense management application that uses **Google Gemini AI** to extract data from receipt images and stores them in a **SQLite** database for monthly reporting and export.

## ✨ Features

- **📸 AI OCR Entry**: Take a photo or upload a receipt; Gemini AI extracts the date, payee, amount, and category automatically.
- **🗄️ SQLite Backend**: Local, reliable storage for all your financial transactions.
- **📊 Monthly Reports**: View total spending and category breakdowns for any month.
- **📥 Data Export**: Download your monthly statements as CSV files for use in Excel or other accounting software.
- **📱 Responsive UI**: Built with Streamlit for a clean, easy-to-use interface on both desktop and mobile.

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- A [Google Gemini API Key](https://aistudio.google.com/app/apikey)

### Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd /path/to/project
   ```

2. **Set up a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

1. **Set your API Key as an environment variable:**
   ```bash
   export GEMINI_API_KEY='your_api_key_here'
   ```
   *(Alternatively, you can enter the key directly in the app's sidebar.)*

2. **Launch Streamlit:**
   ```bash
   streamlit run app.py
   ```

## 🐳 Dockerization

You can run this application in a container using Docker.

### 1. Build the Docker Image

```bash
docker build -t expense-tracker .
```

### 2. Run with Docker Compose (Recommended)

This is the easiest way to manage the container, volumes, and environment variables.

1. **Create a `.env` file** in the project root:
   ```bash
   GEMINI_API_KEY='your_actual_api_key_here'
   # Optional: Set a different model
   # GEMINI_MODEL_NAME='gemini-2.5-flash'
   ```

2. **Start the application:**
   ```bash
   docker compose up -d
   ```

The application will be accessible at `http://localhost:8501`.

### 3. Run with Docker CLI (Alternative)

The application requires a **Google Gemini API Key**. For security, the `.streamlit/secrets.toml` file is ignored by Docker during the build process. You must provide the key at runtime using one of the following methods:

#### Option 1: Environment Variable (Recommended)
This is the most secure and standard way to provide secrets to a container.

```bash
docker run -d \
  --name expense-tracker \
  -p 8501:8501 \
  -e GEMINI_API_KEY='your_actual_api_key_here' \
  -v $(pwd)/data:/app/data \
  expense-tracker
```

*Note: `GEMINI_MODEL_NAME` defaults to `gemini-1.5-flash` if not specified. This allows you to easily switch to newer versions (e.g., `gemini-2.0-flash`) as they become available without rebuilding the image.*

#### Option 2: Mounting the Secrets File
If you already have a `.streamlit/secrets.toml` file on your host machine, you can mount it into the container.

1. Create the file if it doesn't exist:
   ```toml
   # .streamlit/secrets.toml
   GEMINI_API_KEY = "your_actual_api_key_here"
   ```
2. Run with a volume mount:
   ```bash
   docker run -d \
     --name expense-tracker \
     -p 8501:8501 \
     -v $(pwd)/.streamlit/secrets.toml:/app/.streamlit/secrets.toml \
     -v $(pwd)/data:/app/data \
     expense-tracker
   ```

### 💾 Data Persistence
To ensure your transaction history is saved when the container is stopped or updated, **always** include the volume mapping for the `data/` directory: `-v $(pwd)/data:/app/data` (or use the Docker Compose configuration which handles this automatically).

## 📂 Project Structure

- `app.py`: The main Streamlit application (UI and navigation).
- `db.py`: Database logic for SQLite (schema, saving, and reporting).
- `data/`: Directory containing the SQLite database (created automatically).
- `data/ledger.db`: The SQLite database file.
- `requirements.txt`: List of Python dependencies.

## 🛠️ Tech Stack

- **Frontend**: Streamlit
- **AI/OCR**: Google Generative AI (Gemini 1.5 Flash)
- **Database**: SQLite
- **Data Handling**: Pandas
- **Image Processing**: Pillow
