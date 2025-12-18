FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DB_PATH=/app/data/voice.db
VOLUME /app/data

CMD ["python", "voicecreate.py"]
