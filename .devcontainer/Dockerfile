FROM mcr.microsoft.com/devcontainers/base:ubuntu

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  curl \
  git \
  iproute2 \
  dnsutils \
  net-tools \
  build-essential \
  pkg-config \
  libssl-dev \
  cmake \
  make \
  gcc \
  g++ \
  python3-venv \
  python3-pip \
  && rm -rf /var/lib/apt/lists/*

ENV DEBIAN_FRONTEND=noninteractive
