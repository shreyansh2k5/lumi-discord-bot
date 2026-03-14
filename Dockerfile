FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp looks for "node" but Debian installs it as "nodejs"
RUN ln -sf /usr/bin/nodejs /usr/local/bin/node

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install -U yt-dlp

COPY . .

CMD ["python", "main.py"]
