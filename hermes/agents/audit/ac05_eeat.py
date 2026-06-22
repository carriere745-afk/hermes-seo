"""AC05 — Scoring EEAT (Expertise, Experience, Autorite, Fiabilite).

Score 0-16. YMYL detection pour les sujets sensibles.
Deterministe (pas de LLM).
"""

from datetime import datetime

from hermes.models.audit import AuditSessionState, DimensionScore


def _check_ymyl(url: str, title: str, content: str = "") -> bool:
    """Detecte si une page traite d'un sujet YMYL."""
    ymyl_keywords = (
        "assurance", "credit", "pret", "cancer", "traitement", "diagnostic",
        "avocat", "juridique", "fiscal", "impot", "comptable", "investissement",
        "placement", "retraite", "mutuelle", "hospitalisation", "chirurgie",
        "medicament", "vaccin", "divorce", "heritage", "licenciement",
        "banque", "bourse", "sante", "medical", "pharmacie",
    )
    combined = (url + " " + title + " " + content).lower()
    return any(kw in combined for kw in ymyl_keywords)


async def run(state: AuditSessionState) -> AuditSessionState:
    """Score EEAT pour chaque page."""
    state.current_agent = "ac05"

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        # Expertise (0-4)
        expertise = 0
        if page.author_detected: expertise += 2
        if len(page.h2_list) >= 5: expertise += 1  # Contenu substantiel
        if page.json_ld_valid: expertise += 1

        # Experience (0-4)
        experience = 0
        if page.date_published: experience += 1
        if page.date_modified: experience += 1
        if page.word_count >= 1500: experience += 1  # Profondeur
        if page.h2_list and any("exemple" in h.lower() or "cas" in h.lower() for h in page.h2_list):
            experience += 1

        # Autorite (0-4)
        autorite = 0
        if page.external_links >= 3: autorite += 1  # Sources externes
        if page.json_ld_valid: autorite += 1
        if page.author_detected: autorite += 1  # Auteur identifiable
        if page.word_count >= 2000: autorite += 1

        # Fiabilite (0-4)
        fiabilite = 0
        if page.has_cta: fiabilite += 1  # Contact possible
        if page.has_breadcrumbs: fiabilite += 1  # Structure claire
        fiabilite += 1  # HTTPS (toujours 1 si fetch a reussi)
        if page.date_published and page.date_modified: fiabilite += 1

        total_eeat = expertise + experience + autorite + fiabilite

        # YMYL check
        is_ymyl = _check_ymyl(page.url, page.title)
        ymyl_note = "⚠️ Sujet YMYL" if is_ymyl else ""
        if is_ymyl and total_eeat < 8:
            strenghts = []
            weaknesses = [
                f"EEAT insuffisant pour un sujet YMYL ({total_eeat}/16, min 8 recommande)",
                "Ajouter auteur + bio + sources institutionnelles"
            ]
        else:
            strenghts = []
            weaknesses = []
            if expertise < 2: weaknesses.append("Expertise faible : auteur ou contenu insuffisant")
            if experience < 2: weaknesses.append("Experience faible : pas de dates, exemples")
            if autorite < 2: weaknesses.append("Autorite faible : peu de sources externes")
            if fiabilite < 3: weaknesses.append("Fiabilite a renforcer")
            if total_eeat >= 10:
                strenghts.append(f"Bon score EEAT ({total_eeat}/16)")

        state.scores[page.url].eea_t = DimensionScore(
            score=total_eeat,
            max_score=16,
            strengths=strenghts,
            weaknesses=weaknesses,
        )

        if ymyl_note:
            state.scores[page.url].eea_t.issues.append({
                "type": "ymyl_eeat_low",
                "gravity": "high",
                "fix": "Renforcer EEAT : auteur identifie, sources institutionnelles, mentions legales"
            })

    state.updated_at = datetime.now()
    return state
