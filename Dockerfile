FROM python:3.12-slim-bookworm

# Instalar dependências do sistema necessárias para o dlib
RUN apt-get update && apt-get install -y \
  cmake \
  build-essential \
  libopenblas-dev \
  liblapack-dev \
  libx11-dev \
  libgtk-3-dev \
  python3-dev \
  && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia o arquivo de dependências e instala dentro de um ambiente virtual
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copia o restante do código da aplicação
COPY . .

# Expõe a porta
EXPOSE 8000

# Comando de execução
CMD ["python", "main.py"]
