# MIB ship image — PaddleOCR FT + geometry regions (offline).
# Constraints: network-none at runtime, 4 vCPU / 8 GiB, ≤6 s/PDF avg.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# Vendored det/rec/cls (+ FT rec) — must stay offline
COPY models /app/models
COPY pyproject.toml README.md /app/
COPY src /app/src

# CPU paddle; pin versions known to work with PP-OCRv4 mobile
RUN pip install --no-cache-dir \
    "numpy>=1.26.0" \
    "opencv-python-headless>=4.8.0" \
    "pdf2image>=1.17.0" \
    "pillow>=10.0.0" \
    "pypdf>=5.0.0" \
    "paddlepaddle==3.0.0" \
    "paddleocr==2.10.0" \
  && pip install --no-cache-dir --no-deps .

ENV MIB_OCR_ENGINE=paddle \
    MIB_PADDLE_MODELS=/app/models/paddle \
    MIB_OCR_DPI=150 \
    MIB_OCR_MAX_PAGES=4 \
    MIB_OCR_CLAHE=0 \
    MIB_WORKERS=2 \
    OMP_THREAD_LIMIT=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    CUDA_VISIBLE_DEVICES= \
    FLAGS_use_mkldnn=0 \
    FLAGS_fraction_of_gpu_memory_to_use=0 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    TMPDIR=/tmp

COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

ENTRYPOINT ["/app/run.sh"]
