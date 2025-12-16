# 1. Base Image (Slim version use karein taaki size kam ho)
FROM python:3.11-slim

# 2. Working Directory set karein
WORKDIR /Auto-Filter-Bot

# 3. System Dependencies Install karein (Sabse Jaruri Step)
# FFmpeg: Video processing ke liye
# Git: Agar requirement me koi git link ho to
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# 4. Pehle sirf requirements copy karein (Caching ke liye)
# Isse agli baar build fast hoga agar sirf code change kiya ho
COPY requirements.txt .

# 5. Pip install karein
RUN pip install --no-cache-dir -r requirements.txt

# 6. Ab baaki saara code copy karein
COPY . .

# 7. Bot start command
CMD ["python", "bot.py"]
