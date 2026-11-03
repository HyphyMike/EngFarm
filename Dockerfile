FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
RUN apt-get update && apt-get install -y --no-install-recommends xvfb \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
COPY . .
ENV HEADLESS=0
CMD ["xvfb-run", "-a", "python", "main.py"]
