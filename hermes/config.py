"""Configuration centrale Hermes SEO.

Charge les variables d'environnement et expose les constantes de l'application.
Compatible .env (local) et Streamlit Secrets (cloud).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Charger .env (local uniquement)
load_dotenv()

# ─── Helper ─────────────────────────────────────────────────────────

def _get(key: str, default: str = "") -> str:
    """Lit une variable : Streamlit Secrets > .env > default."""
    try:
        import streamlit as st
        # Streamlit Cloud utilise st.secrets
        val = st.secrets.get(key)
        if val is not None:
            return str(val)
    except (ImportError, RuntimeError, FileNotFoundError):
        pass
    return os.getenv(key, default)


# ─── Racine du projet ───────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent

# ─── Clés API ───────────────────────────────────────────────────────

ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _get("OPENAI_API_KEY")
DEEPSEEK_API_KEY = _get("DEEPSEEK_API_KEY")
GEMINI_API_KEY = _get("GEMINI_API_KEY")
# SERP APIs (priorite: TalorData > Scrape.do > Serpstack)
TALORDATA_API_KEY = _get("TALORDATA_API_KEY")
SCRAPEDO_API_KEY = _get("SCRAPEDO_API_KEY")
SERPSTACK_API_KEY = _get("SERPSTACK_API_KEY")
# Google
GSC_CLIENT_ID = _get("GSC_CLIENT_ID")
GSC_CLIENT_SECRET = _get("GSC_CLIENT_SECRET")

# ─── Base de données ────────────────────────────────────────────────

CHROMA_PERSIST_DIRECTORY = _get("CHROMA_PERSIST_DIRECTORY", "./data/chroma")
SQLITE_DB_PATH = _get("SQLITE_DB_PATH", "./data/sqlite/hermes.db")

# ─── Logs & sessions ────────────────────────────────────────────────

LOG_DIRECTORY = Path(_get("LOG_DIRECTORY", "./logs"))
SESSION_DIRECTORY = Path(_get("SESSION_DIRECTORY", "./sessions"))
LOG_LEVEL = _get("LOG_LEVEL", "INFO")

# ─── Budgets ────────────────────────────────────────────────────────

DEFAULT_TOKEN_BUDGET = int(_get("DEFAULT_TOKEN_BUDGET", "1000000"))
DEFAULT_COST_BUDGET = float(_get("DEFAULT_COST_BUDGET", "5.0"))

# ─── Mode par défaut ────────────────────────────────────────────────

DEFAULT_QUALITY_MODE = _get("DEFAULT_QUALITY_MODE", "standard")

# ─── Ollama (fallback local) ────────────────────────────────────────

OLLAMA_BASE_URL = _get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _get("OLLAMA_MODEL", "llama4:latest")

# ─── Chemins relatifs ───────────────────────────────────────────────

PROMPTS_DIR = PROJECT_ROOT / "prompts"
TESTS_DIR = PROJECT_ROOT / "tests"
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
REGISTRY_PATH = PROJECT_ROOT / "agents_registry.yaml"

# ─── Dossiers à créer ───────────────────────────────────────────────

REQUIRED_DIRS: list[Path] = [
    LOG_DIRECTORY,
    SESSION_DIRECTORY,
    Path(CHROMA_PERSIST_DIRECTORY),
    Path(SQLITE_DB_PATH).parent,
]
