FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    curl nodejs npm git python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g opencode-ai

RUN curl -fsSL https://raw.githubusercontent.com/multica-ai/multica/main/scripts/install.sh | bash

RUN mkdir -p /root/.config/opencode /data

COPY admin.py /admin.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
