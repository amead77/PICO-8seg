#!/bin/bash

SESSION_NAME="8seg"
PYTHON_SCRIPT="python3 ~/bin/pc_server.py"

while :; do
    if ! tmux has-session -t $SESSION_NAME 2>/dev/null; then
        echo "Starting in tmux session '$SESSION_NAME'"
        tmux new-session -d -s $SESSION_NAME "$PYTHON_SCRIPT both"
    fi

    # Check every 60 seconds
    sleep 60
done