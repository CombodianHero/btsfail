FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY extractor.py main.py bot.py app.py .

ENV PORT=8000
EXPOSE 8000

# Runs Flask (health check on $PORT) + Telegram bot (polling) together
CMD ["python", "app.py"]
