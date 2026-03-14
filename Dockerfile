FROM python:3.12-slim

# Install ffmpeg, libopus, and nodejs (required for yt-dlp signature solving)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
