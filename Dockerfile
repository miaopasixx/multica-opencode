FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    curl git python3 ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/*

# 安装 Node.js 18（Ubuntu 22.04 自带版本太旧）
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g opencode-ai

RUN curl -fsSL https://raw.githubusercontent.com/multica-ai/multica/main/scripts/install.sh | bash

RUN mkdir -p /root/.config/opencode /data

COPY admin.py /admin.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
