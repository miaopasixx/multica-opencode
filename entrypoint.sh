#!/bin/bash
set -e

# ============================================
# 从持久化卷恢复配置
# ============================================
mkdir -p /root/.config/opencode

if [ -f /data/providers.json ]; then
    echo "[entrypoint] 从 /data/providers.json 恢复配置"
    python3 /admin.py --restore
else
    echo "[entrypoint] 首次启动，使用 OpenCode 内置免费模型"
    echo '{}' > /root/.config/opencode/opencode.json
fi

# ============================================
# 连接 Multica Cloud
# ============================================
multica config set server_url https://api.multica.ai
multica config set app_url https://multica.ai
echo "$MULTICA_TOKEN" | multica login --token

# ============================================
# 后台启动 daemon
# ============================================
multica daemon start &
DAEMON_PID=$!
echo "[entrypoint] multica daemon PID=$DAEMON_PID"
echo $DAEMON_PID > /tmp/daemon.pid

# ============================================
# 前台启动管理界面
# ============================================
echo "[entrypoint] 管理界面: http://0.0.0.0:8080"
exec python3 /admin.py --serve
