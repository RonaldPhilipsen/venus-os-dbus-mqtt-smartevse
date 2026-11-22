#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename "$SCRIPT_DIR")

# make sure SERVICE_NAME is set and not empty
if [ -z "$SERVICE_NAME" ]; then
    echo "Error: SERVICE_NAME is not set."
    exit 1
fi

echo
echo "Uninstalling $SERVICE_NAME..."

# remove the driver from rc.local
echo "Removing driver from rc.local..."
sed -i "/$SERVICE_NAME/d" /data/rc.local

# stop the service
echo "Stopping service..."
svc -d "/service/$SERVICE_NAME"

sleep 1

# remove the service symlink
echo "Removing driver from services..."
rm "/service/$SERVICE_NAME"

# stop the remaining processes
pkill -f "supervise .*$SERVICE_NAME"
pkill -f "multilog .*$SERVICE_NAME"
pkill -f "python3 .*$SERVICE_NAME"

echo "done."
echo

# ask the user if the driver files must go too
echo "Do you also want to delete all driver files including the config? [y/N]"
read -r DELETE_FILES

if [[ "$DELETE_FILES" == "y" || "$DELETE_FILES" == "Y" ]]; then
    echo "Deleting all driver files..."
    rm -rf "$SCRIPT_DIR"
    echo "done."
else
    echo "Driver files not deleted."
fi

echo
echo "*** Please reboot your device to complete the uninstallation. ***"
echo
