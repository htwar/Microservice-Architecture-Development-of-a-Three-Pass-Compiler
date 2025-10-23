# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy all your .py (lexer.py, parser.py, codegen.py, orchestrator.py, models.py)
COPY . .

# Build-time args (defaults are fine)
ARG ENTRY="lexer:app"
ARG PORT=8000

# Make them available at runtime
ENV ENTRY=${ENTRY}
ENV PORT=${PORT}

EXPOSE 8000

# Use shell so $ENTRY and $PORT expand
CMD ["/bin/sh","-c","uvicorn $ENTRY --host 0.0.0.0 --port $PORT"]
