echo "1. Setting up docker containers..."
sleep 1
if [[ $1 == "-b" ]]; then
    docker compose up -d --build
else
    docker compose up -d
fi
echo "2. Excuting APMQ service..."
sleep 5
docker exec ocppcontroller python charging_progress.py &
echo "APMQ service executed"