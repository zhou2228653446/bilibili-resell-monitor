#!/usr/bin/env bash
# ============================================================
# B站会员购转售监控 —— 服务器一键部署脚本 (Ubuntu 24.04)
#
# 用法（在服务器上以 root 执行）：
#   bash deploy.sh
#
# 前提：项目文件已上传到 /opt/bili-monitor
# ============================================================
set -e

APP_DIR="/opt/bili-monitor"
SVC_NAME="bili-monitor"
APP_PORT="${APP_PORT:-8000}"
LOG_FILE="/var/log/${SVC_NAME}.log"

echo "============================================"
echo " B站转售监控 · 部署开始"
echo " 目录: ${APP_DIR}"
echo " 端口: ${APP_PORT}"
echo "============================================"

# ---------- 0. 环境检查 ----------
if [ "$(id -u)" -ne 0 ]; then
    echo "[错误] 请用 root 执行： sudo bash deploy.sh"
    exit 1
fi

if [ ! -d "${APP_DIR}" ]; then
    echo "[错误] 目录 ${APP_DIR} 不存在，请先上传项目文件。"
    exit 1
fi

if [ ! -f "${APP_DIR}/web_server.py" ]; then
    echo "[错误] ${APP_DIR}/web_server.py 不存在，项目文件不完整。"
    exit 1
fi

echo ""
echo "[1/6] 检查 Python3 ..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "  未检测到 python3，正在安装 ..."
    apt-get update -qq && apt-get install -y -qq python3
fi
PY_VER=$(python3 -V 2>&1)
echo "  OK: ${PY_VER}"

# ---------- 1. 端口占用检查 ----------
echo ""
echo "[2/6] 检查端口 ${APP_PORT} 是否被占用 ..."
if command -v ss >/dev/null 2>&1; then
    OCCUPIED=$(ss -lntp 2>/dev/null | grep -c ":${APP_PORT} " || true)
elif command -v netstat >/dev/null 2>&1; then
    OCCUPIED=$(netstat -lntp 2>/dev/null | grep -c ":${APP_PORT} " || true)
else
    OCCUPIED=0
fi

if [ "${OCCUPIED}" -gt 0 ]; then
    echo "  [警告] 端口 ${APP_PORT} 已被占用！"
    echo "  占用情况："
    (ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null) | grep ":${APP_PORT} " || true
    echo ""
    echo "  >> 若占用者是预装的 Hermes Agent，请改用其他端口，例如："
    echo "     APP_PORT=8081 bash deploy.sh"
    echo ""
    read -r -p "  仍要继续吗？(y/N) " ans
    if [ "${ans}" != "y" ] && [ "${ans}" != "Y" ]; then
        echo "  已取消。"
        exit 1
    fi
else
    echo "  OK: 端口 ${APP_PORT} 空闲"
fi

# ---------- 2. 可选依赖 ----------
echo ""
echo "[3/6] 安装可选依赖 requests（提升抓取抗 429 能力）..."
if python3 -c "import requests" 2>/dev/null; then
    echo "  OK: requests 已安装"
else
    if apt-get install -y -qq python3-requests 2>/dev/null; then
        echo "  OK: 已通过 apt 安装 python3-requests"
    else
        echo "  [跳过] 安装失败，程序会自动回退到 urllib（不影响运行）"
    fi
fi

# ---------- 3. 创建数据目录 ----------
echo ""
echo "[4/6] 准备数据与缓存目录 ..."
mkdir -p "${APP_DIR}/cache/img"
touch "${LOG_FILE}"
echo "  OK: ${APP_DIR}/cache/img"
echo "  OK: ${LOG_FILE}"

# ---------- 4. 写入 systemd 服务 ----------
echo ""
echo "[5/6] 配置 systemd 服务 ..."
cat > "/etc/systemd/system/${SVC_NAME}.service" <<EOF
[Unit]
Description=Bilibili Resell Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
# --no-open 必需：服务器无桌面环境，禁止尝试拉起浏览器
ExecStart=/usr/bin/python3 ${APP_DIR}/web_server.py --port ${APP_PORT} --no-open
Restart=always
RestartSec=10
StandardOutput=append:${LOG_FILE}
StandardError=append:${LOG_FILE}

# 环境变量（如需调整图片缓存，取消注释）
# Environment=IMG_CACHE_MAX_MB=512
# Environment=IMG_AUTO_PREFETCH=1
# Environment=IMG_FETCH_INTERVAL=0.15

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SVC_NAME}" >/dev/null 2>&1
echo "  OK: /etc/systemd/system/${SVC_NAME}.service"

# ---------- 5. 启动 ----------
echo ""
echo "[6/6] 启动服务 ..."
systemctl restart "${SVC_NAME}"
sleep 4

if systemctl is-active --quiet "${SVC_NAME}"; then
    echo "  OK: 服务已启动"
else
    echo "  [错误] 服务启动失败，最近日志："
    echo "  ----------------------------------------"
    tail -n 30 "${LOG_FILE}" || true
    echo "  ----------------------------------------"
    exit 1
fi

# ---------- 自检 ----------
echo ""
echo "本地自检 ..."
if command -v curl >/dev/null 2>&1; then
    CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${APP_PORT}/" || echo "000")
    echo "  GET /  -> HTTP ${CODE}"
    CODE2=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${APP_PORT}/api/imgcache/stat" || echo "000")
    echo "  GET /api/imgcache/stat -> HTTP ${CODE2}"
fi

PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "<你的公网IP>")

echo ""
echo "============================================"
echo " 部署完成！"
echo "============================================"
echo " 访问地址:  http://${PUBLIC_IP}:${APP_PORT}"
echo ""
echo " 常用命令:"
echo "   查看状态   systemctl status ${SVC_NAME}"
echo "   查看日志   tail -f ${LOG_FILE}"
echo "   重启服务   systemctl restart ${SVC_NAME}"
echo "   停止服务   systemctl stop ${SVC_NAME}"
echo ""
echo " ⚠️  还需去控制台「防火墙」放通 ${APP_PORT}/TCP，否则外网访问不到。"
echo " ⚠️  本服务无鉴权，强烈建议用 Nginx + Basic Auth 反代，"
echo "     不要长期把 ${APP_PORT} 明文暴露在公网。"
echo "============================================"
