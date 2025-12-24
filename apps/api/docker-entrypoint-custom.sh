#!/bin/bash
set -e

# Patch harness.js to increase timeout from 30000ms to 90000ms
if [ -f /app/dist/src/harness.js ]; then
    echo "Patching harness.js to increase startup timeout..."
    sed -i 's/timeoutMs = 30000/timeoutMs = 90000/g' /app/dist/src/harness.js
    echo "Timeout increased to 90 seconds"
fi

# Execute the original command
exec "$@"
