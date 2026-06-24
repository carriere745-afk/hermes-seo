#!/bin/bash
# Hermes SEO v3 — Deployment script
# Usage: bash deploy.sh [streamlit|docker|vps]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Hermes SEO v3 — Deploy Script        ${NC}"
echo -e "${BLUE}========================================${NC}"

MODE=${1:-streamlit}

# Check .env
if [ ! -f .env ]; then
    echo -e "${RED}[ERROR] .env file not found. Copy .env.example to .env and configure your API keys.${NC}"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 is required.${NC}"
    exit 1
fi

case $MODE in
    streamlit)
        echo -e "${GREEN}[INFO] Deploying to Streamlit Cloud...${NC}"
        echo "1. Push your code to GitHub: git push origin main"
        echo "2. Go to https://share.streamlit.io"
        echo "3. Click 'New app' and select your repository"
        echo "4. Set main file path: app.py"
        echo "5. Add your .env variables in Streamlit Secrets"
        echo ""
        echo -e "${GREEN}Done. Your app will be available at https://[your-app].streamlit.app${NC}"
        ;;

    docker)
        echo -e "${GREEN}[INFO] Building Docker image...${NC}"
        docker build -t hermes-seo .
        echo -e "${GREEN}[INFO] Starting containers...${NC}"
        docker-compose up -d
        echo -e "${GREEN}[INFO] Hermes SEO running at http://localhost:8501${NC}"
        echo "  View logs: docker-compose logs -f"
        echo "  Stop: docker-compose down"
        ;;

    vps)
        echo -e "${GREEN}[INFO] Deploying to VPS...${NC}"
        pip install -r requirements.txt
        mkdir -p data logs sessions
        echo -e "${GREEN}[INFO] Starting Streamlit on port 8501...${NC}"
        nohup python -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0 > logs/streamlit.log 2>&1 &
        echo -e "${GREEN}[INFO] Hermes SEO running at http://$(hostname -I | awk '{print $1}'):8501${NC}"
        echo "  View logs: tail -f logs/streamlit.log"
        echo "  Stop: pkill -f 'streamlit run app.py'"
        ;;

    *)
        echo -e "${RED}[ERROR] Unknown mode: $MODE. Use: streamlit, docker, or vps${NC}"
        exit 1
        ;;
esac
