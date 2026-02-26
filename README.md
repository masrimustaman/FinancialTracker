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
docker build -t receipt-tracker .
```

### 2. Run the Container

To run the container, you need to provide your Gemini API key. We recommend using an environment variable for security.

#### Basic Run (Temporary Data)
```bash
docker run -p 8501:8501 -e GEMINI_API_KEY='your_api_key_here' receipt-tracker
```

#### Recommended: Persistent Storage & Security
To ensure your transactions are saved even if the container is restarted or removed, mount the `data/` directory as a volume.

```bash
docker run -d -p 8501:8501 \
  --name receipt-tracker \
  -e GEMINI_API_KEY='your_api_key_here' \
  -v $(pwd)/data:/app/data \
  receipt-tracker
```

### 🔐 Handling Secrets "Accordingly"

- **Environment Variable (Best Practice)**: Pass `-e GEMINI_API_KEY=your_key` when running the container. This keeps the secret out of the image layers and filesystems.
- **Secrets File**: The Docker image is configured to ignore `.streamlit/secrets.toml`. If you prefer using the file, you can mount it at runtime:
  ```bash
  docker run -p 8501:8501 \
    -v $(pwd)/.streamlit/secrets.toml:/app/.streamlit/secrets.toml \
    receipt-tracker
  ```

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
