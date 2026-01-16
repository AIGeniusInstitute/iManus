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
        echo "Attempting to stop Docker via systemctl..."
        
        # Check if Docker service exists
        if ! systemctl list-units --full -all | grep -q docker.service; then
            echo "Error: Docker service not found."
            exit 1
        fi
        
        # Check permissions and stop service
        if [ "$EUID" -ne 0 ]; then
            echo "This script requires sudo privileges to stop the Docker service."
            sudo systemctl stop docker
        else
            systemctl stop docker
        fi
        
        # Wait for Docker to stop
        echo "Waiting for Docker daemon to initialize..."
        TIMEOUT=30
        COUNTER=0
        while ! docker info > /dev/null 2>&1; do
            if [ $COUNTER -gt $TIMEOUT ]; then
                echo ""
                echo "Timed out waiting for Docker to stop."
                exit 1
            fi
            sleep 1
            printf "."
            COUNTER=$((COUNTER+1))
        done
        echo ""
        echo "Docker stoped successfully!"
    else
        echo "Error: 'systemctl' not found. Cannot automatically stop Docker."
        echo "Please stop Docker manually (e.g., 'sudo service docker stop')."
        exit 1
    fi
else
    echo "Docker is already stopped."
fi
