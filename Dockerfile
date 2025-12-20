FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for building python packages
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
# Create landings directory if not exists
RUN mkdir -p landings

CMD ["python", "-m", "app.main"]