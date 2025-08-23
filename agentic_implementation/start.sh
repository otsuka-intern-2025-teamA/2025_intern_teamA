#!/bin/bash

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs
# Set log level if not specified
if [ -z "$LOG_LEVEL" ]; then
    export LOG_LEVEL="INFO"
    echo "Setting LOG_LEVEL to INFO (default)"
fi

echo "Logs will be saved to: logs/log.txt"
echo "Log level: $LOG_LEVEL"



# Start the backend server
echo "Starting backend server..."
echo "Check logs/log.txt for detailed logging information"
python backend_server.py
