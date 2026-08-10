#!/usr/bin/env bash
set -u
pkill -f 'huggingface-cli download' 2>/dev/null || true
pkill -f 'hf download' 2>/dev/null || true
pkill -f 'smoke_summarize_sample.py' 2>/dev/null || true
pkill -f 'download_jais2.sh' 2>/dev/null || true
pkill -f 'resume_jais2_dl.sh' 2>/dev/null || true
pkill -f 'restart_jais2_dl.sh' 2>/dev/null || true
pkill -f 'run_smoke_summarize.sh' 2>/dev/null || true
sleep 1
echo "remaining:"
pgrep -af 'huggingface-cli|smoke_summarize|jais2_dl|download_jais' || echo none
