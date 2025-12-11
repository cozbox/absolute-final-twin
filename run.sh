#!/usr/bin/with-contenv bashio

# Read configuration
GEMINI_API_KEY=$(bashio::config 'gemini_api_key')

# Export environment variables
export GEMINI_API_KEY="${GEMINI_API_KEY}"
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"

# Log startup
bashio::log.info "Starting TwinSync Spot..."

# Start the application
cd /opt
exec uvicorn app.main:app --host 0.0.0.0 --port 8099 --proxy-headers --forwarded-allow-ips='*'
