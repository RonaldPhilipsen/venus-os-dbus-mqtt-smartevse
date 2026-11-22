#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename "$SCRIPT_DIR")

echo
echo "Restarting $SERVICE_NAME..."

# kill the Python process, daemontools starts it again
pid=$(pgrep -f "python3 $SCRIPT_DIR/$SERVICE_NAME.py")
if [ -n "$pid" ]; then
    pkill -f "python3 $SCRIPT_DIR/$SERVICE_NAME.py" > /dev/null 2>&1
    echo "done."
else
    echo "driver is not running!"
fi

echo
