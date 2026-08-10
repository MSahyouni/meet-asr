#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
du -sh data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat 2>/dev/null || echo "no dir"
ps -C python -o pid,etime,cmd 2>/dev/null | grep -F smoke_summarize || echo "no smoke process"
tail -n 12 data/outputs/smoke_summarize.log 2>/dev/null || true
