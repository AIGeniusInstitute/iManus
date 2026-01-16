#!/bin/bash

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running."
    
    # Check if systemctl is available (standard on Ubuntu)
    if command -v systemctl >/dev/null 2>&1; then
        echo "Attempting to start Docker via systemctl..."
        
        # Check permissions and start service
        if [ "$EUID" -ne 0 ]; then
            echo "This script requires sudo privileges to start the Docker service."
            sudo systemctl start docker
        else
            systemctl start docker
        fi
        
        # Wait for Docker to start
        echo "Waiting for Docker daemon to initialize..."
        TIMEOUT=30
        COUNTER=0
        while ! docker info > /dev/null 2>&1; do
            if [ $COUNTER -gt $TIMEOUT ]; then
                echo ""
                echo "Timed out waiting for Docker to start."
                exit 1
            fi
            sleep 1
            printf "."
            COUNTER=$((COUNTER+1))
        done
        echo ""
        echo "Docker started successfully!"
    else
        echo "Error: 'systemctl' not found. Cannot automatically start Docker."
        echo "Please start Docker manually (e.g., 'sudo service docker start')."
        exit 1
    fi
else
    echo "Docker is already running."
fi


