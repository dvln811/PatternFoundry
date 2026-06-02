#!/usr/bin/env bash
# restart_server.sh — kill any existing Flask on PORT, spawn fresh, wait for ready.

PORT=${1:-5000}
PROJ="/media/devlyn/Leviathan/Projects/PatternFoundry"
PYTHON="$PROJ/.venv/bin/python"

# Kill anything on the port
PIDS=$(lsof -ti tcp:"$PORT" 2>/dev/null)
if [ -n "$PIDS" ]; then
    kill -9 $PIDS 2>/dev/null
    sleep 0.5
fi

# Spawn detached
BOARD_API_KEY="M_rnFxusEXFytMlA-ovFL-_vp3WTiteZ-MynS1XTImE" nohup "$PYTHON" "$PROJ/app.py" > "$PROJ/flask.log" 2>&1 &
SERVER_PID=$!
disown "$SERVER_PID"

# Poll up to 10s
DEADLINE=$((SECONDS + 10))
while [ $SECONDS -lt $DEADLINE ]; do
    if curl -sf "http://127.0.0.1:$PORT/" -o /dev/null 2>/dev/null; then
        echo "Server ready (PID $SERVER_PID) → http://127.0.0.1:$PORT/"
        exit 0
    fi
    sleep 0.4
done

echo "Server did not respond within 10s (PID $SERVER_PID). Check flask.log."
exit 1
