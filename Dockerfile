# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
# Note: .dockerignore will prevent secrets.toml and ledger.db from being copied
COPY . .

# Expose the port that Streamlit will run on
EXPOSE 8501

# Healthcheck to ensure the container is running correctly
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run the application
# We use 0.0.0.0 to allow connections from outside the container
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
