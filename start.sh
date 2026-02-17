#!/bin/bash
set -e

# Start both services in the background
echo "Starting dashboard..."
uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080} &
DASHBOARD_PID=$!

echo "Starting bot worker..."
python3 main.py &
WORKER_PID=$!

# Wait for either process to exit
wait -n

# If one exits, kill the other and exit
kill $DASHBOARD_PID $WORKER_PID 2>/dev/null || true
exit 1
