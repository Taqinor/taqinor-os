# backend/django_core/Dockerfile
FROM python:3.11.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Fuseaux horaires : zoneinfo ne lit QUE le paquet pip `tzdata` (épinglé dans
# requirements.txt), jamais /usr/share/zoneinfo — la tzdata de Debian peut être
# en retard sur IANA (bookworm servait encore 2026b le 21/09/2026, donc SANS le
# décret marocain 2.26.530 qui fixe le pays à UTC+0 depuis le 20/09/2026).
ENV PYTHONTZPATH=""

# Dépendances système pour WeasyPrint (Pango, Cairo, GDK-PixBuf) +
# python3-saml/NTSEC2 (libxml2 + xmlsec1 requis à l'installation du wheel).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi8 \
    libharfbuzz0b \
    shared-mime-info \
    fonts-liberation \
    fonts-noto-core \
    pkg-config \
    libxml2-dev \
    libxmlsec1-dev \
    libxmlsec1-openssl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
# Modern setuptools so the http-ece sdist (transitive de pywebpush, N109) build.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
