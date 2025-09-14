#!/bin/bash

# File to store stats
LOG_FILE="docker_stats.log"
# Container to monitor
CONTAINER_NAME="jina-openai"

# Clean up previous log file
if [ -f "$LOG_FILE" ]; then
    rm "$LOG_FILE"
fi

echo "Starting resource monitoring for container '$CONTAINER_NAME'..."
echo "Logging stats to $LOG_FILE"

# Start logging docker stats in the background
while true; do
    docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.PIDs}}" >> "$LOG_FILE"
    sleep 1
done &

# Get the Process ID (PID) of the background logging loop
LOGGING_PID=$!

# Kill the logging process on script exit
trap "echo 'Stopping logger...'; kill $LOGGING_PID; exit" SIGINT SIGTERM

echo "Logger started with PID: $LOGGING_PID"
echo "Waiting for container '$CONTAINER_NAME' to stop..."

# Use docker events to wait for the container to die, then kill the logger
docker events --filter "container=$CONTAINER_NAME" --filter "event=die" --format '{{.Status}}' | while read event; do
    echo "Container '$CONTAINER_NAME' stopped with event: $event. Stopping resource monitoring."
    kill $LOGGING_PID
    echo "Monitoring stopped. Log file is ready at $LOG_FILE."
    # Exit the pipe, which will terminate the script
    exit 0
done