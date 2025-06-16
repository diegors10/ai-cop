FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y \
    build-essential \
    cmake \
    libboost-all-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/Kitware/CMake/releases/download/v3.27.9/cmake-3.27.9-linux-x86_64.sh && \
    chmod +x cmake-3.27.9-linux-x86_64.sh && \
    ./cmake-3.27.9-linux-x86_64.sh --skip-license --prefix=/usr/local && \
    rm cmake-3.27.9-linux-x86_64.sh

RUN pip install --upgrade pip

RUN pip install --no-cache-dir dlib==19.24.2

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["python", "main.py"]

