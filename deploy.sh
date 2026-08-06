#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
trap 'die "部署在第 ${LINENO} 行失败，请检查上方输出。"' ERR

REPO_URL="${REPO_URL:-https://github.com/gjzxyb/ExamForge-Math.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/ExamForge-Math}"
DATA_DIR_OVERRIDE="${DATA_DIR:-}"
DATA_DIR="${DATA_DIR_OVERRIDE:-$INSTALL_DIR/data}"
SERVICE_NAME="${SERVICE_NAME:-examforge-math}"
SERVICE_HOST="${SERVICE_HOST:-0.0.0.0}"
SERVICE_PORT="${SERVICE_PORT:-8001}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-${USER:-$(id -un)}}}"
ENV_FILE_OVERRIDE="${ENV_FILE:-}"
ENV_FILE="${ENV_FILE_OVERRIDE:-$INSTALL_DIR/.env}"
LLM_BACKEND="${LLM_BACKEND:-mock}"
LLM_PROVIDER="${LLM_PROVIDER:-deepseek}"
LLM_BASE_URL="${LLM_BASE_URL:-https://api.deepseek.com/v1}"
LLM_API_KEY="${LLM_API_KEY:-}"
LLM_MODEL="${LLM_MODEL:-deepseek-chat}"
LLM_THINKING_MODE="${LLM_THINKING_MODE:-auto}"
LLM_TIMEOUT="${LLM_TIMEOUT:-300}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
SKIP_SYSTEM_DEPS="${SKIP_SYSTEM_DEPS:-0}"
SKIP_TESTS="${SKIP_TESTS:-0}"
NON_INTERACTIVE="${NON_INTERACTIVE:-0}"
GIT_RETRY_ATTEMPTS="${GIT_RETRY_ATTEMPTS:-5}"
ALLOW_OFFLINE_DEPLOY="${ALLOW_OFFLINE_DEPLOY:-1}"

refresh_paths() {
    ENV_FILE="${ENV_FILE_OVERRIDE:-$INSTALL_DIR/.env}"
    DATA_DIR="${DATA_DIR_OVERRIDE:-$INSTALL_DIR/data}"
}

usage() {
    cat <<'EOF'
ExamForge-Math Linux 一键部署/更新脚本

用法：bash deploy.sh [选项]

选项：
  --port PORT          服务端口，默认 8001
  --host HOST          监听地址，默认 0.0.0.0
  --install-dir DIR    安装目录，默认 ~/ExamForge-Math
  --data-dir DIR       持久化数据目录，默认 <安装目录>/data
  --llm-key KEY        配置 DeepSeek/OpenAI 兼容 API Key，并启用 http 后端
  --llm-provider NAME  供应商预设（deepseek/openai/qwen/zhipu/moonshot/custom）
  --llm-base URL       LLM Base URL
  --llm-model MODEL    模型名称
  --llm-thinking MODE  思考模式（auto/disabled/low/high/max）
  --python VERSION     Python 版本，默认 3.12
  --skip-tests         跳过部署前测试
  --skip-system-deps   跳过系统依赖安装
  --non-interactive    非交互部署，自动安装并启动 systemd 服务
  -h, --help           显示帮助

也可使用同名环境变量：SERVICE_PORT、INSTALL_DIR、DATA_DIR、LLM_API_KEY 等。
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) SERVICE_PORT="$2"; shift 2 ;;
        --host) SERVICE_HOST="$2"; shift 2 ;;
        --install-dir) INSTALL_DIR="$2"; refresh_paths; shift 2 ;;
        --data-dir) DATA_DIR_OVERRIDE="$2"; DATA_DIR="$2"; shift 2 ;;
        --llm-key) LLM_API_KEY="$2"; LLM_BACKEND="http"; shift 2 ;;
        --llm-provider) LLM_PROVIDER="$2"; shift 2 ;;
        --llm-base) LLM_BASE_URL="$2"; shift 2 ;;
        --llm-model) LLM_MODEL="$2"; shift 2 ;;
        --llm-thinking) LLM_THINKING_MODE="$2"; shift 2 ;;
        --python) PYTHON_VERSION="$2"; shift 2 ;;
        --skip-tests) SKIP_TESTS=1; shift ;;
        --skip-system-deps) SKIP_SYSTEM_DEPS=1; shift ;;
        --non-interactive) NON_INTERACTIVE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "未知参数：$1（使用 --help 查看帮助）" ;;
    esac
done

[[ "$SERVICE_PORT" =~ ^[0-9]+$ ]] && (( SERVICE_PORT >= 1 && SERVICE_PORT <= 65535 )) \
    || die "端口必须是 1-65535 之间的整数"
[[ "$(uname -s)" == "Linux" ]] || die "该脚本仅支持 Linux"

as_root() {
    if [[ ${EUID} -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

git_network_retry() {
    local label="$1" attempt delay
    shift
    for ((attempt = 1; attempt <= GIT_RETRY_ATTEMPTS; attempt++)); do
        info "${label}（第 ${attempt}/${GIT_RETRY_ATTEMPTS} 次）"
        # 强制 HTTP/1.1 与 TLS 1.2，规避部分国内云网络上的 GnuTLS -110。
        if GIT_TERMINAL_PROMPT=0 git \
            -c http.version=HTTP/1.1 \
            -c http.sslVersion=tlsv1.2 \
            -c http.lowSpeedLimit=1000 \
            -c http.lowSpeedTime=60 \
            "$@"; then
            return 0
        fi
        if (( attempt < GIT_RETRY_ATTEMPTS )); then
            delay=$((attempt * 3))
            warn "${label}失败，${delay} 秒后重试"
            sleep "$delay"
        fi
    done
    return 1
}

detect_pkg_manager() {
    if command -v apt-get >/dev/null 2>&1; then echo apt
    elif command -v dnf >/dev/null 2>&1; then echo dnf
    elif command -v yum >/dev/null 2>&1; then echo yum
    else die "不支持的发行版，请先安装 git、curl、python3 和 sudo"
    fi
}

install_system_deps() {
    [[ "$SKIP_SYSTEM_DEPS" == 1 ]] && { warn "已跳过系统依赖安装"; return; }
    local pm; pm="$(detect_pkg_manager)"
    info "使用 $pm 安装系统依赖"
    case "$pm" in
        apt)
            as_root apt-get update -qq
            as_root apt-get install -y git curl ca-certificates python3 python3-pip
            ;;
        dnf|yum)
            as_root "$pm" install -y git curl ca-certificates python3 python3-pip
            ;;
    esac
    ok "系统依赖安装完成"
}

install_uv() {
    if command -v uv >/dev/null 2>&1; then ok "$(uv --version)"; return; fi
    info "安装 uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    command -v uv >/dev/null 2>&1 || die "uv 安装失败"
    ok "$(uv --version)"
}

prepare_repo() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "更新已有仓库"
        # 云服务器上的临时改动不参与发布：仅暂存已跟踪文件，.env/data 等
        # 未跟踪运行数据保持原位。暂存不自动恢复，避免旧改动重新覆盖新版代码。
        if ! git -C "$INSTALL_DIR" diff --quiet \
            || ! git -C "$INSTALL_DIR" diff --cached --quiet; then
            local stash_message stash_ref
            stash_message="examforge-deploy-backup-$(date +%Y%m%d-%H%M%S)"
            warn "检测到服务器未提交修改，自动备份后继续更新（不会恢复到运行目录）"
            git -C "$INSTALL_DIR" stash push -m "$stash_message" >/dev/null
            stash_ref="$(git -C "$INSTALL_DIR" stash list -1 --format='%gd')"
            ok "服务器修改已备份到 ${stash_ref:-git stash}"
        fi
        if git_network_retry "从 GitHub 获取更新" \
            -C "$INSTALL_DIR" fetch --prune origin main; then
            # fetch 已完成网络传输，直接合并远端引用，避免 pull 再请求一次 GitHub。
            git -C "$INSTALL_DIR" merge --ff-only origin/main
        elif [[ "$ALLOW_OFFLINE_DEPLOY" == 1 ]]; then
            warn "GitHub TLS 连接连续失败，暂用本机现有版本继续部署"
            warn "网络恢复后重新运行 bash deploy.sh 即可更新代码"
        else
            die "无法连接 GitHub；请检查服务器网络、DNS、代理后重试"
        fi
    elif [[ -e "$INSTALL_DIR" ]] && [[ -n "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
        die "$INSTALL_DIR 已存在且不是空目录/Git 仓库"
    else
        info "克隆仓库到 $INSTALL_DIR"
        git_network_retry "从 GitHub 克隆仓库" clone "$REPO_URL" "$INSTALL_DIR" \
            || die "仓库克隆失败；请检查服务器到 GitHub 的网络连接"
    fi
    ok "当前版本：$(git -C "$INSTALL_DIR" log -1 --oneline)"
}

sync_dependencies() {
    info "使用 Python ${PYTHON_VERSION} 同步 Python 依赖"
    (cd "$INSTALL_DIR" && uv python install "$PYTHON_VERSION")
    (cd "$INSTALL_DIR" && uv sync --frozen --python "$PYTHON_VERSION")
    ok "Python 依赖同步完成"
}

write_env_file() {
    mkdir -p "$DATA_DIR"
    if [[ -f "$ENV_FILE" ]]; then
        info "保留现有 $ENV_FILE"
        if [[ -n "$LLM_API_KEY" ]]; then
            [[ "$LLM_API_KEY" != *$'\n'* ]] || die "LLM API Key 不能包含换行"
            cat >> "$ENV_FILE" <<EOF

# deploy.sh 更新的 LLM 配置（同名变量以最后一项为准）
EXAMFORGE_LLM_BACKEND=http
EXAMFORGE_LLM_PROVIDER=${LLM_PROVIDER}
EXAMFORGE_LLM_BASE=${LLM_BASE_URL}
EXAMFORGE_LLM_KEY=${LLM_API_KEY}
EXAMFORGE_LLM_MODEL=${LLM_MODEL}
EXAMFORGE_LLM_THINKING_MODE=${LLM_THINKING_MODE}
EXAMFORGE_LLM_TIMEOUT=${LLM_TIMEOUT}
EOF
            chmod 600 "$ENV_FILE"
            ok "已更新 .env 中的真实 LLM 配置"
        else
            info "未覆盖已有环境配置；Web 设置仍以 $DATA_DIR/settings.json 为准"
        fi
        return
    fi
    if [[ "$LLM_BACKEND" == http && -z "$LLM_API_KEY" ]]; then
        warn "未提供 LLM_API_KEY，首次部署将使用 mock；可稍后在系统设置页配置真实 API"
        LLM_BACKEND=mock
    fi
    info "创建 $ENV_FILE"
    cat > "$ENV_FILE" <<EOF
EXAMFORGE_LLM_BACKEND=${LLM_BACKEND}
EXAMFORGE_LLM_PROVIDER=${LLM_PROVIDER}
EXAMFORGE_LLM_BASE=${LLM_BASE_URL}
EXAMFORGE_LLM_KEY=${LLM_API_KEY}
EXAMFORGE_LLM_MODEL=${LLM_MODEL}
EXAMFORGE_LLM_THINKING_MODE=${LLM_THINKING_MODE}
EXAMFORGE_LLM_TIMEOUT=${LLM_TIMEOUT}
EXAMFORGE_EMBED_BACKEND=mock
EXAMFORGE_OCR_PROVIDER=mock
PYTHONUNBUFFERED=1
EOF
    chmod 600 "$ENV_FILE"
    ok "环境配置已创建"
}

initialize_data() {
    info "初始化/迁移数据库和预置方法"
    (cd "$INSTALL_DIR" && uv run examforge initdb --data-dir "$DATA_DIR")
    (cd "$INSTALL_DIR" && uv run examforge seed --data-dir "$DATA_DIR")
    ok "持久化目录：$DATA_DIR"
}

configure_runtime_llm() {
    [[ -n "$LLM_API_KEY" ]] || return 0
    info "把真实 LLM 配置写入持久化 settings.json"
    pushd "$INSTALL_DIR" >/dev/null
    EXAMFORGE_DEPLOY_DATA_DIR="$DATA_DIR" \
    EXAMFORGE_DEPLOY_LLM_BASE="$LLM_BASE_URL" \
    EXAMFORGE_DEPLOY_LLM_KEY="$LLM_API_KEY" \
    EXAMFORGE_DEPLOY_LLM_MODEL="$LLM_MODEL" \
    EXAMFORGE_DEPLOY_LLM_PROVIDER="$LLM_PROVIDER" \
    EXAMFORGE_DEPLOY_LLM_THINKING_MODE="$LLM_THINKING_MODE" \
    EXAMFORGE_DEPLOY_LLM_TIMEOUT="$LLM_TIMEOUT" \
    uv run python - <<'PY'
import os
from pathlib import Path

from examforge.config.settings import init_settings_store

store = init_settings_store(Path(os.environ["EXAMFORGE_DEPLOY_DATA_DIR"]))
store.update(llm={
    "backend": "http",
    "provider": os.environ["EXAMFORGE_DEPLOY_LLM_PROVIDER"],
    "base_url": os.environ["EXAMFORGE_DEPLOY_LLM_BASE"],
    "api_key": os.environ["EXAMFORGE_DEPLOY_LLM_KEY"],
    "model": os.environ["EXAMFORGE_DEPLOY_LLM_MODEL"],
    "thinking_mode": os.environ["EXAMFORGE_DEPLOY_LLM_THINKING_MODE"],
    "timeout": float(os.environ["EXAMFORGE_DEPLOY_LLM_TIMEOUT"]),
})
PY
    popd >/dev/null
    LLM_BACKEND=http
    ok "持久化 LLM 配置已更新"
}

run_tests() {
    [[ "$SKIP_TESTS" == 1 ]] && { warn "已跳过测试"; return; }
    info "运行部署前测试"
    (cd "$INSTALL_DIR" && uv run pytest -q)
    ok "测试通过"
}

install_service() {
    command -v systemctl >/dev/null 2>&1 || die "未检测到 systemd，请按最后给出的手动命令启动"
    local uv_path service_file
    uv_path="$(command -v uv)"
    service_file="/etc/systemd/system/${SERVICE_NAME}.service"
    info "写入 systemd 服务 $service_file"
    as_root tee "$service_file" >/dev/null <<EOF
[Unit]
Description=ExamForge-Math Web Service
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
Environment=HOME=$(getent passwd "$SERVICE_USER" | cut -d: -f6)
ExecStart=${uv_path} run examforge serve --data-dir ${DATA_DIR} --host ${SERVICE_HOST} --port ${SERVICE_PORT}
Restart=always
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
    as_root systemctl daemon-reload
    as_root systemctl enable "$SERVICE_NAME.service" >/dev/null
    as_root systemctl restart "$SERVICE_NAME.service"
    sleep 3
    as_root systemctl is-active --quiet "$SERVICE_NAME.service" \
        || { as_root journalctl -u "$SERVICE_NAME.service" -n 100 --no-pager; die "服务启动失败"; }
    ok "systemd 服务运行正常"
}

health_check() {
    local health_host="$SERVICE_HOST"
    [[ "$health_host" == "0.0.0.0" || "$health_host" == "::" ]] && health_host="127.0.0.1"
    info "检查 http://${health_host}:${SERVICE_PORT}/healthz"
    for _ in {1..15}; do
        if curl -fsS --max-time 3 "http://${health_host}:${SERVICE_PORT}/healthz" | grep -q '"ok":true'; then
            ok "健康检查通过"
            return
        fi
        sleep 1
    done
    as_root journalctl -u "$SERVICE_NAME.service" -n 100 --no-pager
    die "健康检查失败"
}

print_summary() {
    local public_ip
    public_ip="$(curl -4fsS --max-time 3 https://api.ipify.org 2>/dev/null || true)"
    echo
    echo -e "${GREEN}ExamForge-Math 部署完成${NC}"
    echo "版本：      $(git -C "$INSTALL_DIR" log -1 --oneline)"
    echo "安装目录：  $INSTALL_DIR"
    echo "数据目录：  $DATA_DIR"
    echo "本机访问：  http://127.0.0.1:${SERVICE_PORT}"
    [[ -n "$public_ip" ]] && echo "公网访问：  http://${public_ip}:${SERVICE_PORT}"
    echo "服务状态：  sudo systemctl status ${SERVICE_NAME} --no-pager"
    echo "实时日志：  sudo journalctl -u ${SERVICE_NAME} -f"
    echo "更新部署：  cd ${INSTALL_DIR} && bash deploy.sh --skip-system-deps"
    if [[ "$LLM_BACKEND" == mock ]]; then
        warn "当前 .env 使用 mock。请登录系统设置页配置真实 LLM，或用 --llm-key 重新部署。"
    fi
    warn "请确认云防火墙/安全组已放行 TCP ${SERVICE_PORT}。"
}

main() {
    install_system_deps
    install_uv
    prepare_repo
    sync_dependencies
    write_env_file
    initialize_data
    configure_runtime_llm
    run_tests
    if [[ "$NON_INTERACTIVE" != 1 ]]; then
        read -r -p "安装并重启 systemd 服务 ${SERVICE_NAME}? [Y/n] " answer
        [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]] || { warn "已跳过服务安装"; exit 0; }
    fi
    install_service
    health_check
    print_summary
}

main
