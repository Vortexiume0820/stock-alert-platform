#!/bin/bash
export SLACK_WEBHOOK_URL=$(grep SLACK_WEBHOOK_URL .env | cut -d '=' -f2)
envsubst < ./monitoring/alertmanager.yml.template > ./monitoring/alertmanager.yml
docker compose up -d