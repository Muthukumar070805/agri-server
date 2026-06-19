FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

COPY . .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]