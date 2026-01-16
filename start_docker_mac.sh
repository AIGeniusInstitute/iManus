#!/bin/bash

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Starting Docker Desktop..."
    open -a Docker
    
    # Wait for Docker to start
    echo "Waiting for Docker to start..."
    while ! docker info > /dev/null 2>&1; do
        sleep 1
        printf "."
    done
    echo ""
    echo "Docker started!"
else
    echo "Docker is already running."
fi

