FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
COPY api/requirements.txt ./api_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r api_requirements.txt
COPY . .
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
