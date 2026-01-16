#!/bin/bash
ps aux | grep "docker-compose-" | grep -v grep | awk '{print $2}' | xargs -r kill -9