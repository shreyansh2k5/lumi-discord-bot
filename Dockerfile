FROM python:3.12-slim

# Only need opus now — Lavalink handles all audio processing
RUN apt-get update && apt-get install -y libopus0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
