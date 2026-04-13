FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY server.py ./server.py
COPY static ./static

USER appuser

EXPOSE 8080

CMD ["python", "server.py"]
