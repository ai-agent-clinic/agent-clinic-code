#!/bin/bash

# A simple script to test the Titanium Pro Headless Cloud Function with a CSV payload.
# Ensure that 'make run-titanium-headless' is running in another terminal.

curl -X POST http://127.0.0.1:8081 \
  -H "Content-Type: application/json" \
  -d '{
    "role": "Chief Information Security Officer",
    "csv_data": "Company Name,Domain\nHome Depot,homedepot.com\nAflac,aflac.com"
  }'

echo -e "\n\nPayload sent! Check the HTML output above."
