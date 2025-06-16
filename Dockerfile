FROM python:3.11-slim

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    git \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Configuração para melhorar compatibilidade do dlib
ENV LDFLAGS="-fno-lto"

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefer-binary --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

