FROM python:3.14-bookworm

# Qt tests and packaged Linux executables need these libraries.
RUN apt-get update && apt-get install --yes --no-install-recommends \
    binutils \
    git \
    libdbus-1-3 \
    libegl1 \
    libfontconfig1 \
    libgl1 \
    libglib2.0-0 \
    libx11-6 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-shape0 \
    libxkbcommon-x11-0 \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    QT_QPA_PLATFORM=offscreen

RUN python -m venv "$VIRTUAL_ENV"
COPY requirements.txt requirements-dev.txt /tmp/duplicate-size-scanner/
RUN python -m pip install --no-cache-dir -r /tmp/duplicate-size-scanner/requirements-dev.txt \
    && rm -rf /tmp/duplicate-size-scanner \
    && useradd --create-home --shell /bin/bash vscode \
    && chown -R vscode:vscode "$VIRTUAL_ENV"

USER vscode
