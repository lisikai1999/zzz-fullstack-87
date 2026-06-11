#!/bin/bash

echo "=== 博弈论仿真平台 ==="
echo ""

# Start backend
echo "Starting backend (FastAPI) on port 8000..."
cd "$(dirname "$0")/backend"
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend (Vite) on port 3000..."
cd "$(dirname "$0")/frontend"
npx vite --port 3000 &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
