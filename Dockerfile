FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# Force latest yt-dlp regardless of requirements.txt pin
RUN pip install -U yt-dlp

COPY . .

CMD ["python", "main.py"]
