FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Koyeb injects PORT; default to 8000 for local runs
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} -w 2 --timeout 120 main:app"]
