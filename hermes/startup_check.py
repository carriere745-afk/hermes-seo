"""Vérifications pré-démarrage Hermes SEO.

Exécuté avant tout lancement de pipeline. Si un check échoue,
le pipeline NE DOIT PAS démarrer.
"""

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

from hermes import config


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str = ""
    fix: str = ""


@dataclass
class StartupReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    def display(self) -> str:
        lines = []
        for r in self.results:
            icon = "OK" if r.passed else "FAIL"
            lines.append(f"  [{icon}] {r.name}")
            if not r.passed:
                lines.append(f"       → {r.message}")
                if r.fix:
                    lines.append(f"       Fix: {r.fix}")
        return "\n".join(lines)


def run_startup_check(require_llm: bool = True, require_serp: bool = True) -> StartupReport:
    """Exécute tous les checks de démarrage.

    Args:
        require_llm: Si True, vérifie qu'au moins une API LLM est configurée.
        require_serp: Si True, vérifie qu'au moins une API SERP est configurée.

    Returns:
        StartupReport avec le résultat de chaque check.
    """
    report = StartupReport()

    # 1. Clés API LLM
    llm_keys = {
        "ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY,
        "OPENAI_API_KEY": config.OPENAI_API_KEY,
        "DEEPSEEK_API_KEY": config.DEEPSEEK_API_KEY,
        "GEMINI_API_KEY": config.GEMINI_API_KEY,
    }
    configured = [k for k, v in llm_keys.items() if v]
    if require_llm and not configured:
        report.results.append(CheckResult(
            name="API LLM keys",
            passed=False,
            message="Aucune cle API LLM configuree. Au moins une est requise.",
            fix="Definissez ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY ou GEMINI_API_KEY dans .env",
        ))
    else:
        report.results.append(CheckResult(
            name="API LLM keys",
            passed=True,
            message=f"{len(configured)} configuree(s): {', '.join(configured) if configured else 'Ollama (local)'}",
        ))

    # 2. API SERP
    if require_serp:
        has_serp = bool(config.TALORDATA_API_KEY or config.SCRAPEDO_API_KEY or config.SERPSTACK_API_KEY)
        report.results.append(CheckResult(
            name="API SERP",
            passed=has_serp,
            message="OK" if has_serp else "Aucune API SERP configuree",
            fix="Definissez TALORDATA_API_KEY, SCRAPEDO_API_KEY ou SERPSTACK_API_KEY dans .env, ou utilisez --dry-run",
        ))

    # 3. Répertoires
    for d in config.REQUIRED_DIRS:
        try:
            d.mkdir(parents=True, exist_ok=True)
            report.results.append(CheckResult(
                name=f"Répertoire {d}",
                passed=True,
                message="OK (créé si nécessaire)",
            ))
        except OSError as e:
            report.results.append(CheckResult(
                name=f"Répertoire {d}",
                passed=False,
                message=str(e),
                fix=f"Vérifiez les permissions d'écriture sur {d.parent}",
            ))

    # 4. Fichiers de prompts
    prompts_dir = config.PROMPTS_DIR
    missing_prompts = []
    for i in range(0, 27):
        agent_num = f"{i:02d}"
        v1_dir = prompts_dir / f"agent_{agent_num}_"  # Le nom exact sera vérifié
        # On vérifie juste que le dossier prompts/ existe avec des sous-dossiers
    if prompts_dir.exists():
        subdirs = list(prompts_dir.glob("agent_*"))
        if len(subdirs) >= 26:
            report.results.append(CheckResult(
                name="Dossiers prompts",
                passed=True,
                message=f"{len(subdirs)} dossiers d'agent trouvés",
            ))
        else:
            missing = 26 - len(subdirs)
            report.results.append(CheckResult(
                name="Dossiers prompts",
                passed=False,
                message=f"{len(subdirs)} trouvés, {missing} manquants",
                fix="Vérifiez que prompts/ contient 27 dossiers agent_XX_nom/",
            ))
    else:
        report.results.append(CheckResult(
            name="Dossiers prompts",
            passed=False,
            message="Dossier prompts/ introuvable",
            fix="Créez les dossiers prompts/agent_XX_nom/v1/",
        ))

    # 5. Dépendances Python
    required_modules = [
        ("langgraph", "langgraph"),
        ("pydantic", "pydantic"),
        ("loguru", "loguru"),
        ("tenacity", "tenacity"),
        ("yaml", "pyyaml"),
        ("httpx", "httpx"),
        ("dotenv", "python-dotenv"),
        ("rich", "rich"),
    ]
    for import_name, package_name in required_modules:
        try:
            importlib.import_module(import_name)
            report.results.append(CheckResult(
                name=f"Module {package_name}",
                passed=True,
                message="OK",
            ))
        except ImportError:
            report.results.append(CheckResult(
                name=f"Module {package_name}",
                passed=False,
                message=f"Module {package_name} non installé",
                fix=f"pip install {package_name}",
            ))

    # 6. Registre des agents
    registry_path = config.REGISTRY_PATH
    if registry_path.exists():
        report.results.append(CheckResult(
            name="Registre agents",
            passed=True,
            message=f"{registry_path} trouvé",
        ))
    else:
        report.results.append(CheckResult(
            name="Registre agents",
            passed=False,
            message=f"{registry_path} introuvable",
            fix="Créez agents_registry.yaml à la racine du projet",
        ))

    # 7. Modèles importables
    try:
        from hermes.models import SessionState, AgentResult  # noqa: F401
        report.results.append(CheckResult(
            name="Modèles Pydantic",
            passed=True,
            message="Tous les modèles s'importent correctement",
        ))
    except Exception as e:
        report.results.append(CheckResult(
            name="Modèles Pydantic",
            passed=False,
            message=str(e),
            fix="Vérifiez les imports dans hermes/models/",
        ))

    return report


def check_and_exit(require_llm: bool = True, require_serp: bool = True) -> None:
    """Exécute le startup check et quitte si échec.

    Cette fonction est appelée au début du main.
    """
    report = run_startup_check(require_llm, require_serp)
    print("\n" + "=" * 60)
    print("HERMES SEO — Startup Check")
    print("=" * 60)
    print(report.display())

    if not report.all_passed:
        print("\n" + "=" * 60)
        print("ÉCHEC DU STARTUP CHECK — Le pipeline ne peut pas démarrer.")
        print("Corrigez les erreurs ci-dessus et réessayez.")
        print("=" * 60 + "\n")
        sys.exit(1)
    else:
        print("\nTous les checks OK. Pipeline prêt.\n")
