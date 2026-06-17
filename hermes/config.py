"""Configuration centrale Hermes SEO.

Charge les variables d'environnement et expose les constantes de l'application.
Compatible .env (local) et Streamlit Secrets (cloud).
Utilise un chargement lazy pour les cles API afin d'eviter les
problemes d'initialisation sur Streamlit Cloud.
"""

from pathlib import Path

from dotenv import dotenv_values

# ─── Racine du projet ───────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Charger .env (local uniquement) via lecture directe du fichier
_env = dotenv_values(PROJECT_ROOT / ".env")


class _LazyConfig:
    """Wrapper lazy qui evalue les cles API a la premiere lecture.

    Sur Streamlit Cloud, st.secrets n'est pret qu'apres st.set_page_config().
    En local, le .env est lu des l'import.
    """

    def _resolve(self, key: str, default: str = "") -> str:
        # 1. .env (local prioritaire)
        val = _env.get(key)
        if val:
            return val

        # 2. Streamlit Secrets (cloud) — evalue a chaque appel
        try:
            import streamlit as st
            val = st.secrets.get(key)
            if val:
                return str(val)
        except (ImportError, RuntimeError, FileNotFoundError):
            pass

        return default

    @property
    def ANTHROPIC_API_KEY(self) -> str:
        return self._resolve("ANTHROPIC_API_KEY")

    @property
    def OPENAI_API_KEY(self) -> str:
        return self._resolve("OPENAI_API_KEY")

    @property
    def DEEPSEEK_API_KEY(self) -> str:
        return self._resolve("DEEPSEEK_API_KEY")

    @property
    def GEMINI_API_KEY(self) -> str:
        return self._resolve("GEMINI_API_KEY")

    @property
    def TALORDATA_API_KEY(self) -> str:
        return self._resolve("TALORDATA_API_KEY")

    @property
    def SCRAPEDO_API_KEY(self) -> str:
        return self._resolve("SCRAPEDO_API_KEY")

    @property
    def SERPSTACK_API_KEY(self) -> str:
        return self._resolve("SERPSTACK_API_KEY")

    @property
    def GSC_CLIENT_ID(self) -> str:
        return self._resolve("GSC_CLIENT_ID")

    @property
    def GSC_CLIENT_SECRET(self) -> str:
        return self._resolve("GSC_CLIENT_SECRET")


_cfg = _LazyConfig()

# ─── Helper pour les valeurs non-API ────────────────────────────────────

def _get(key: str, default: str = "") -> str:
    """Resout une valeur de config : .env > st.secrets > default.

    Pour les cles API, utilisez _cfg._resolve() qui est lazy.
    Pour le reste (chemins, budgets...), resolution immediate.
    """
    val = _env.get(key)
    if val:
        return val
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return str(val)
    except (ImportError, RuntimeError, FileNotFoundError):
        pass
    return default


# ─── APIs lazy — resolues a chaque acces ────────────────────────────
# Accedees via config.ANTHROPIC_API_KEY, resolues par __getattr__.

_LAZY_KEYS: set[str] = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY", "TALORDATA_API_KEY", "SCRAPEDO_API_KEY",
    "SERPSTACK_API_KEY", "GSC_CLIENT_ID", "GSC_CLIENT_SECRET",
}


def __getattr__(name: str) -> str:
    """Resolution lazy des cles API — evalue st.secrets a chaque acces."""
    if name in _LAZY_KEYS:
        return _cfg._resolve(name)
    raise AttributeError(f"module 'hermes.config' has no attribute '{name}'")


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
