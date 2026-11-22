#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename "$SCRIPT_DIR")

echo
echo "Installing $SERVICE_NAME..."

# set permissions for script files
echo "Setting permissions..."
chmod 755 "$SCRIPT_DIR"/*.py
chmod 755 "$SCRIPT_DIR"/*.sh
chmod 755 "$SCRIPT_DIR/service/run"
chmod 755 "$SCRIPT_DIR/service/log/run"

# create sym-link to the service folder, an existing link stays as it is
if [ ! -L "/service/$SERVICE_NAME" ]; then
    echo "Creating service..."
    ln -s "$SCRIPT_DIR/service" "/service/$SERVICE_NAME"
else
    echo "Service already exists."
fi

# add install script to rc.local, so the driver survives a firmware update
filename=/data/rc.local
if [ ! -f "$filename" ]; then
    touch "$filename"
    chmod 755 "$filename"
    echo "#!/bin/bash" >> "$filename"
    echo >> "$filename"
fi

# add the line only once
grep -qxF "bash $SCRIPT_DIR/install.sh" "$filename" || echo "bash $SCRIPT_DIR/install.sh" >> "$filename"

echo
