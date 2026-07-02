# Stage 1: Build MATIEC Compiler
FROM python:3.11-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates gcc g++ make git bison flex autoconf automake \
    && rm -rf /var/lib/apt/lists/*

# Clone the official public Beremiz MATIEC repository and build it
RUN git clone --depth 1 https://github.com/beremiz/matiec.git /matiec \
    && cd /matiec \
    && autoreconf -i \
    && ./configure \
    && make -j"$(nproc)" \
    && install -m 0755 /matiec/iec2c /usr/local/bin/iec2c \
    && mkdir -p /usr/local/share/matiec \
    && cp -r /matiec/lib /usr/local/share/matiec/lib \
    && chmod -R 755 /usr/local/share/matiec/lib

# Stage 2: Final Runtime Environment
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install runtime dependencies (Java for PLCverif)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre wget \
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled MATIEC binary from the builder stage
COPY --from=builder /usr/local/bin/iec2c /usr/local/bin/iec2c
# Copy MATIEC standard library files from builder stage
COPY --from=builder /usr/local/share/matiec/lib /usr/local/share/matiec/lib

# Create a placeholder for PLCverif executable
RUN touch /usr/local/bin/plcverif && chmod +x /usr/local/bin/plcverif

# Copy requirements and install Python dependencies
# ننسخ الملف من داخل مجلد backend
# Copy requirements and install Python dependencies
COPY backend/requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel

# ثبّت PyTorch CPU فقط، بدون CUDA
RUN python -m pip install --default-timeout=1000 --retries 10 \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.5.1
RUN python -c "import torch; print(torch.__version__); print(torch.version.cuda)"

# ثبّت باقي المتطلبات
RUN python -m pip install --default-timeout=1000 --retries 10 \
    -r requirements.txt

# Copy the rest of the application code
# ننسخ محتويات مجلد backend إلى داخل المجلد الحالي في الحاوية
COPY backend/ .
COPY backend/knowledge_base /app/knowledge_base

EXPOSE 8000

# Start the FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]