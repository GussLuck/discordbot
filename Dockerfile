FROM python:3.12-slim

WORKDIR /app

# Avoid .pyc files and force unbuffered logs in container output.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
