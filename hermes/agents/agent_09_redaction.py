"""Agent 09 — Redaction.

Produit le brouillon HTML selon le template, sans hallucination
ni contenu generique. C'est le coeur du pipeline Hermes SEO.
Utilise Claude Sonnet 4.6 pour la qualite d'ecriture francaise.
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.core.budget import BudgetTracker
from hermes.models.agent_data import Brouillon
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState
from hermes.utils.text import compter_mots


def _build_system_prompt(state: SessionState) -> str:
    """Construit le prompt systeme avec toutes les donnees contextuelles.

    Ce prompt est lourd (2000-3000 tokens) mais contient tout ce dont
    le redacteur a besoin pour produire un contenu de qualite.
    Prompt caching activable pour les sections repetitives.
    """
    entreprise = state.fiche_entreprise or {}
    persona = state.fiche_persona or {}
    offre = state.offre_conversion_data or {}
    diff = state.angles_differenciants or {}
    template = state.template_data or {}
    cannib = state.anti_cannib_data or {}
    serp = state.serp_data or {}

    # ── Brief entreprise ──
    nom = entreprise.get("nom", "l'entreprise")
    secteur = entreprise.get("secteur", "generaliste")
    positionnement = entreprise.get("positionnement", "")
    ton = entreprise.get("ton_marque", "Professionnel")
    contraintes = entreprise.get("contraintes_legales", [])
    interdits = entreprise.get("mots_cles_interdits", [])
    preuves_ent = entreprise.get("preuves", [])
    offres_list = entreprise.get("offres", [])

    # ── Persona ──
    nom_persona = persona.get("nom_persona", "le lecteur")
    maturite = persona.get("maturite", "intermediaire")
    voc = persona.get("vocabulaire_recommande", [])
    obj_lecture = persona.get("objectif_lecture", "s'informer")
    freins = persona.get("freins", [])
    niveau = persona.get("niveau_expertise", "intermediaire")

    # ── Offre & Conversion ──
    benefices = offre.get("benefices", [])
    objections = offre.get("objections", [])
    preuves_offre = offre.get("preuves", [])
    cta = offre.get("cta_principal", "")
    cta2 = offre.get("cta_secondaire", "")
    vau = offre.get("valeur_ajoutee_unique", "")

    # ── Differenciation ──
    angle = diff.get("angle_principal", "")
    faiblesses = diff.get("angles_faibles", [])

    # ── SERP ──
    concurrents = ", ".join(serp.get("concurrents_directs", [])[:5]) or "non identifies"
    paa_list = serp.get("paa", [])[:8]
    ai_overview = ""
    if serp.get("ai_overviews"):
        ai_overview = serp["ai_overviews"][0].get("content", "")[:300]

    # ── Template ──
    structure = template.get("structure", [])
    sections_guide = "\n".join(
        f"  {s.get('ordre', i)}. [{s.get('type', '?')}] {s.get('titre', '')}"
        f" — {s.get('contenu_guide', '')}"
        for i, s in enumerate(structure)
    ) if structure else "(Structure a definir)"

    # ── Anti-cannibalisation ──
    contrainte_cannib = ""
    if cannib.get("conflit_detecte"):
        contrainte_cannib = (
            f"\n**ATTENTION :** Contenu existant detecte sur le meme sujet. "
            f"Recommandation : {cannib.get('recommandation', '')}. "
            f"Action : {cannib.get('action', '')}."
        )

    # ── Assemblage ──
    prompt = f"""# Hermes SEO — Redacteur Editorial

Tu es un redacteur expert pour {nom}, {positionnement}.
Tu ecris pour {nom_persona}, un lecteur de niveau {niveau} qui cherche a {obj_lecture}.

## Consignes redactionnelles

**Secteur :** {secteur}
**Ton :** {ton}
**Valeur ajoutee unique :** {vau}
**Angle editorial :** {angle}

**Mots interdits :** {', '.join(interdits) if interdits else 'aucun'}
**Contraintes legales :** {', '.join(contraintes) if contraintes else 'aucune'}

## Lecteur cible ({nom_persona})

- Maturite : {maturite}
- Niveau technique : {niveau}
- Vocabulaire a privilegier : {', '.join(voc) if voc else 'vocabulaire courant'}
- Freins a lever : {', '.join(freins) if freins else 'aucun identifie'}

## Benefices a mettre en avant

{chr(10).join(f'- {b}' for b in benefices) if benefices else '- (a definir)'}

## Objections a traiter

{chr(10).join(f'- {o}' for o in objections) if objections else '- (a definir)'}

## Preuves disponibles

{chr(10).join(f'- {p}' for p in (preuves_ent + preuves_offre)) if (preuves_ent or preuves_offre) else '- (a definir)'}

## Ce que les concurrents ne font PAS bien

{chr(10).join(f'- {f}' for f in faiblesses) if faiblesses else '- (non analyse)'}

## Concurrents dans le top 10

{concurrents}

## Questions que le lecteur se pose (PAA)

{chr(10).join(f'{i+1}. {q}' for i, q in enumerate(paa_list)) if paa_list else '(non disponible)'}

## Structure a suivre IMPERATIVEMENT

{sections_guide}

## CTA

- Principal : {cta or 'a definir'}
- Secondaire : {cta2 or 'a definir'}

## AI Overview (a depasser en qualite)

{ai_overview or '(non disponible)'}
{contrainte_cannib}

## Regles d'ecriture

1. **Ecrire pour le lecteur**, pas pour Google. Phrases naturelles, rythme varie.
2. **Chaque section doit meriter d'etre lue.** Si un paragraphe n'apporte rien, le supprimer.
3. **Pas de Lorem Ipsum, pas de remplissage.** Chaque phrase doit contenir une information.
4. **Chiffres, exemples concrets, sources.** Jamais d'affirmation vague sans etai.
5. **Respecter les contraintes legales** du secteur. Ajouter les avertissements necessaires.
6. **Ne JAMAIS utiliser les mots interdits.**
7. **Adapter le niveau de langage** au persona : {niveau}.
8. **Inclure les preuves** la ou elles renforcent le propos.
9. **Chaque H2 repond a une question reelle** du lecteur.
10. **Le CTA doit etre naturel**, pas force.
"""
    return prompt


def _build_user_message(state: SessionState) -> str:
    """Le message utilisateur : la commande de redaction."""
    keyword = state.keyword or "le sujet"
    type_page = state.type_page or "article"
    intention = state.intention or "informative"
    objectif = state.objectif or f"Informer sur {keyword}"

    return (
        f"Redige le contenu complet en HTML pour :\n\n"
        f"**Mot-cle principal :** {keyword}\n"
        f"**Type de page :** {type_page}\n"
        f"**Intention :** {intention}\n"
        f"**Objectif :** {objectif}\n\n"
        f"Retourne UNIQUEMENT un objet JSON valide avec :\n"
        f'- html: le contenu complet en HTML (h1, h2, h3, p, ul, ol, blockquote...)\n'
        f'- word_count: nombre de mots\n'
        f'- titre: le titre H1\n'
        f'- meta_description: meta description (140-160 caracteres)\n'
        f'- sections: ["titre section 1", "titre section 2", ...]\n\n'
        f'IMPORTANT :\n'
        f'- Le HTML doit etre propre, sans CSS inline, sans javascript\n'
        f'- Utiliser les balises semantiques : h1, h2, h3, p, ul, ol, li, blockquote, strong, em\n'
        f'- Chaque section H2 doit contenir au moins 150 mots\n'
        f'- Le contenu total doit etre exhaustif et couvrir TOUTES les questions PAA\n'
        f'- Inclure la FAQ et le bloc En bref SI le template le demande\n'
        f'- Echapper les guillemets doubles dans le HTML (\\\")'
    )


def _extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except json.JSONDecodeError: pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(0))
        except json.JSONDecodeError: pass
    try: return json.loads(text.strip())
    except json.JSONDecodeError: pass
    return {}


def _extract_html(text: str) -> str:
    """Extrait le HTML meme si le LLM l'a mis en dehors du JSON.

    Cherche du contenu HTML structurel et le recupere.
    """
    # 1. Bloc HTML dans un code fence markdown ```html ... ```
    match = re.search(r"```html?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        html = match.group(1).strip()
        if len(html) > 200:
            return html

    # 2. Premiere balise structurelle (h1, h2, article, section, div, main)
    for tag in ("h1", "h2", "article", "section", "div", "main"):
        match = re.search(rf"<{tag}[ >].*?</{tag}>", text, re.DOTALL | re.IGNORECASE)
        if match:
            reste = text[match.start():].strip()
            if len(reste) > 200:
                return reste

    # 3. Dernier recours : chercher tout bloc commencant par <
    for part in reversed(text.split("\n\n")):
        part = part.strip()
        if part.startswith("<") and len(part) > 200:
            return part

    return ""


def _mock_brouillon(state: SessionState) -> Brouillon:
    """Genere un brouillon simule realiste pour le dry-run."""
    keyword = state.keyword or "le sujet"
    entreprise = state.fiche_entreprise or {}
    nom = entreprise.get("nom", "L'entreprise")
    template = state.template_data or {}
    structure = template.get("structure", [])
    intention = state.intention or "informative"

    # Si pas de structure, utiliser un template article minimal
    if not structure:
        structure = [
            {"type": "h1", "titre": f"Guide {keyword}", "contenu_guide": "Titre", "obligatoire": True, "ordre": 0},
            {"type": "intro", "titre": "Introduction", "contenu_guide": "Intro", "obligatoire": True, "ordre": 1},
            {"type": "h2", "titre": f"Tout savoir sur {keyword}", "contenu_guide": "Corps", "obligatoire": True, "ordre": 2},
            {"type": "conclusion", "titre": "Conclusion", "contenu_guide": "Fin", "obligatoire": True, "ordre": 3},
        ]

    # Construire le HTML a partir du template
    sections_html = []
    section_titles = []

    for s in structure:
        stype = s.get("type", "h2")
        titre = s.get("titre", "").replace("[", "").replace("]", "")
        contenu_guide = s.get("contenu_guide", "")

        if stype == "h1":
            sections_html.append(
                f'<h1>Guide Complet {keyword.replace("-", " ").title()} — '
                f'Conseils d\'Experts {nom}</h1>'
            )
            section_titles.append(titre)
        elif stype == "intro":
            sections_html.append(
                f'<p><strong>{keyword.replace("-", " ").title()}</strong> est un sujet '
                f'essentiel pour les professionnels et les particuliers. '
                f'Dans ce guide complet, nous abordons tous les aspects importants : '
                f'definition, fonctionnement, avantages, et conseils pratiques '
                f'pour faire le bon choix.</p>\n'
                f'<p>Que vous soyez debutant ou expert, ce guide vous apportera '
                f'des informations verificables et des exemples concrets.</p>'
            )
        elif stype in ("h2", "h3"):
            titre_clean = titre.replace(f"{keyword} ", "").replace(f" {keyword}", "")
            sections_html.append(f'<h2>{titre_clean}</h2>')
            section_titles.append(titre_clean)
            paragraphs = max(1, min(3, int(len(contenu_guide) / 80)))
            for _ in range(paragraphs):
                sections_html.append(
                    f'<p>Contenu detaille sur {titre_clean.lower()} concernant '
                    f'{keyword}. Cette section couvre les points essentiels avec '
                    f'des exemples concrets et des donnees verificables.</p>'
                )
        elif stype == "faq":
            sections_html.append('<h2>FAQ — Questions Frequentes</h2>')
            section_titles.append("FAQ")
            for i in range(1, 6):
                sections_html.append(
                    f'<h3>Question {i} sur {keyword} ?</h3>\n'
                    f'<p>Reponse detaillee a la question {i}, avec des informations '
                    f'precises et utiles pour le lecteur.</p>'
                )
        elif stype == "en_bref":
            sections_html.append('<h2>En Bref</h2>')
            section_titles.append("En Bref")
            sections_html.append('<ul>')
            for i in range(1, 6):
                sections_html.append(
                    f'<li><strong>Point cle {i} :</strong> information essentielle '
                    f'a retenir sur {keyword}.</li>'
                )
            sections_html.append('</ul>')
        elif stype == "cta":
            cta_text = "Demandez votre devis gratuit" if intention == "transactionnelle" else "Telechargez notre guide complet"
            sections_html.append(
                f'<div><h2>Passez a l\'action</h2>\n'
                f'<p>Vous avez maintenant toutes les cles pour comprendre {keyword}. '
                f'Notre equipe d\'experts est la pour vous accompagner.</p>\n'
                f'<p><strong>{cta_text}</strong></p></div>'
            )
        elif stype == "conclusion":
            sections_html.append(
                f'<h2>Conclusion</h2>\n'
                f'<p>En resume, {keyword} est un domaine riche qui merite '
                f'une attention particuliere. Nous avons couvert les points '
                f'essentiels pour vous permettre de prendre une decision eclairee.</p>\n'
                f'<p>N\'hesitez pas a consulter nos autres guides pour approfondir '
                f'vos connaissances.</p>'
            )
            section_titles.append("Conclusion")

    html = "\n".join(sections_html)
    word_count = compter_mots(html)

    return Brouillon(
        html=html,
        word_count=word_count,
        titre=f"Guide Complet {keyword.replace('-', ' ').title()} — Conseils d'Experts",
        meta_description=f"Decouvrez notre guide complet sur {keyword}. "
                         f"Conseils d'experts, exemples concrets et guide pas a pas.",
        sections=section_titles[:15],
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_09"
    agent_name = "Redaction"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"

    try:
        if state.config.dry_run:
            brouillon = _mock_brouillon(state)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            # Verifier le budget avant l'appel (Claude Sonnet est cher)
            tracker = BudgetTracker(
                token_budget=state.config.token_budget,
                cost_budget=state.config.cost_budget,
            )
            tracker.tokens_used = state.total_tokens
            tracker.cost_used = state.total_cost

            # Estimer : prompt ~3000 tokens, reponse ~4000 tokens
            ok, warning = tracker.can_proceed(3000, 4000, "claude-sonnet-4-6")
            if not ok:
                raise ValueError(f"Budget insuffisant pour la redaction: {warning}")

            factory = LLMFactory(
                anthropic_api_key=config.ANTHROPIC_API_KEY,
                openai_api_key=config.OPENAI_API_KEY,
                deepseek_api_key=config.DEEPSEEK_API_KEY,
                gemini_api_key=config.GEMINI_API_KEY,
                ollama_base_url=config.OLLAMA_BASE_URL,
                dry_run=False,
            )

            system_prompt = _build_system_prompt(state)
            user_message = _build_user_message(state)

            texte, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=user_message,
                agent_id=agent_id,
                temperature=0.7,
                max_tokens=8000,
            )

            data = _extract_json(texte)

            # Si le JSON est vide mais qu'il y a du HTML brut, l'extraire
            html = data.get("html", "")
            if not html:
                html = _extract_html(texte)

            if not html:
                raise ValueError(
                    "Le LLM n'a pas produit de HTML exploitable. "
                    f"Debut de la reponse: {texte[:300]}..."
                )

            brouillon = Brouillon(
                html=html,
                word_count=data.get("word_count", compter_mots(html)),
                titre=data.get("titre", ""),
                meta_description=data.get("meta_description", ""),
                sections=data.get("sections", []),
            )

            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            cost = tracker.estimate_cost(model_used, tokens_in, tokens_out)
            result.cost_estimated = round(cost, 6)
            state.total_tokens += tokens_in + tokens_out
            state.total_cost += cost

        state.brouillon_html = brouillon.html
        result.data = brouillon.model_dump()
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        # NE PAS faire de fallback silencieux vers le mock.
        # Un echec de redaction = pipeline arrete, pas de placeholder.
        result.status = AgentStatus.FAILED
        result.error_message = str(e)
        result.error_traceback = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
        state.status = "failed"
        state.error_count += 1
        result.finished_at = datetime.now()
        return state

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    log_agent_completed(
        agent_id, agent_name, result.duration_ms,
        tokens_input=result.tokens_input or 0,
        tokens_output=result.tokens_output or 0,
        cost_estimated=result.cost_estimated or 0.0,
        prompt_version="v1",
        model_used=result.model_used or "inconnu",
    )
    state.last_completed_agent_id = agent_id
    return state
