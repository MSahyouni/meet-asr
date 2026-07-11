#!/usr/bin/env bash

set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root_dir"

preferred_venv_dir="$root_dir/.venv"
legacy_venv_dir="$root_dir/venv"
venv_dir="$preferred_venv_dir"
api_dir="$root_dir/apps/api"
requirements_file="$api_dir/requirements.txt"
host_name="${HOST:-127.0.0.1}"
port="${PORT:-8000}"

log() {
    printf '[run] %s\n' "$1"
}

pick_python() {
    if command -v python3 >/dev/null 2>&1; then
        printf 'python3'
        return
    fi
    if command -v python >/dev/null 2>&1; then
        printf 'python'
        return
    fi
    return 1
}

if [[ -x "$preferred_venv_dir/bin/python" ]]; then
    venv_dir="$preferred_venv_dir"
    log "استخدام البيئة الافتراضية: .venv"
elif [[ -x "$legacy_venv_dir/bin/python" ]]; then
    venv_dir="$legacy_venv_dir"
    log "استخدام البيئة الافتراضية القديمة: venv (يُفضَّل الترحيل: ./scripts/migrate_to_dot_venv.sh)"
else
    base_python="$(pick_python)" || {
        echo "Python غير موجود في PATH. ثبّت python3 ثم أعد المحاولة." >&2
        exit 1
    }

    log "إنشاء البيئة الافتراضية .venv"
    "$base_python" -m venv "$preferred_venv_dir"
    venv_dir="$preferred_venv_dir"
fi

venv_python="$venv_dir/bin/python"
requirements_stamp="$venv_dir/.requirements.sha256"

if [[ ! -f "$requirements_file" ]]; then
    echo "ملف requirements.txt غير موجود: $requirements_file" >&2
    exit 1
fi

current_req_hash="$(sha256sum "$requirements_file" | awk '{print $1}')"
installed_req_hash=""
if [[ -f "$requirements_stamp" ]]; then
    installed_req_hash="$(head -n 1 "$requirements_stamp")"
fi

if [[ "$current_req_hash" != "$installed_req_hash" ]]; then
    log "تثبيت أو تحديث المتطلبات"
    "$venv_python" -m pip install -U pip
    "$venv_python" -m pip install -r "$requirements_file"
    printf '%s\n' "$current_req_hash" > "$requirements_stamp"
else
    log "المتطلبات مثبتة مسبقًا"
fi

if command -v xdg-open >/dev/null 2>&1; then
    (
        for _ in $(seq 1 30); do
            if RUN_HOST="$host_name" RUN_PORT="$port" "$venv_python" - <<'PY' >/dev/null 2>&1
import socket
import os

sock = socket.socket()
try:
    sock.settimeout(0.2)
    sock.connect((os.environ["RUN_HOST"], int(os.environ["RUN_PORT"])))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
            then
                xdg-open "http://${host_name}:${port}/" >/dev/null 2>&1 || true
                exit 0
            fi
            sleep 1
        done
    ) &
fi

log "تشغيل السيرفر على http://${host_name}:${port}/"
log "للإيقاف: Ctrl+C"

cd "$api_dir"
exec "$venv_python" -m uvicorn api:app --host "$host_name" --port "$port"