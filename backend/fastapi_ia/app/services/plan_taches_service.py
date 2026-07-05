"""XPRJ29 — Génération IA d'un brouillon de plan de tâches (WBS) depuis un devis.

Key-gated sur ``GROQ_API_KEY`` (même clé LLM que l'agent SQL, ``SQL_AGENT_
PROVIDER``/``SQL_AGENT_MODEL`` — AUCUNE nouvelle dépendance payante). Sans clé
configurée : ``PlanTachesIndisponible`` levée (l'endpoint la traduit en 503
propre, no-op net).

Ce service ne fait QUE PROPOSER : il ne touche ni la base Django ni aucune
écriture. Le brouillon JSON (phases/tâches/durées/dépendances FS) est renvoyé
à l'ERP qui le matérialise APRÈS confirmation explicite de l'utilisateur
(pattern propose→confirm du Group R, ``apps.gestion_projet.services.
materialiser_plan_taches``).
"""
import json
import logging

from app.core.config import GROQ_API_KEY, SQL_AGENT_MODEL, SQL_AGENT_PROVIDER

logger = logging.getLogger(__name__)

# Phases standard reconnues — MÊMES CLÉS que ``PhaseProjet.TypePhase`` côté ERP
# (etude/appro/pose/mes/reception) pour que ``materialiser_plan_taches``
# rattache directement chaque tâche à sa phase SANS table de traduction. Ce
# service FastAPI ne les importe PAS (aucune dépendance à l'ORM Django) : les
# clés sont dupliquées littéralement, en connaissance de cause.
_PHASES_CONNUES = ('etude', 'appro', 'pose', 'mes', 'reception')


class PlanTachesIndisponible(Exception):
    """Levée quand aucune clé LLM n'est configurée (dégradation propre)."""


def _construire_prompt(devis_data: dict, type_installation: str) -> str:
    """Prompt structuré : lignes du devis + type d'installation → JSON strict."""
    lignes_materiel = devis_data.get('nb_lignes_materiel', 0)
    lignes_mo = devis_data.get('nb_lignes_main_oeuvre', 0)
    montant_materiel = devis_data.get('montant_materiel', 0)
    montant_mo = devis_data.get('montant_main_oeuvre', 0)
    return (
        "Tu es un planificateur de projets d'installation solaire au Maroc. "
        f"Type d'installation : {type_installation}. "
        f"Devis : {lignes_materiel} ligne(s) matériel "
        f"({montant_materiel} MAD), {lignes_mo} ligne(s) main-d'œuvre "
        f"({montant_mo} MAD). "
        "Propose un brouillon de plan de tâches (WBS) au format JSON STRICT, "
        "sans texte autour, avec la forme exacte : "
        '{"taches": [{"code": "1", "libelle": "...", "phase": "etude", '
        '"duree_jours": 2, "dependances_fs": []}, ...]}. '
        f"``phase`` doit être une valeur parmi {list(_PHASES_CONNUES)} "
        "(étude, approvisionnement, pose, mise en service, réception). "
        "``dependances_fs`` liste les ``code`` des tâches PRÉDÉCESSEURS "
        "(fin→début) de cette tâche. Reste concis : 5 à 12 tâches, phases "
        "standard étude → approvisionnement → pose → mise en service → "
        "réception."
    )


def _build_llm():
    """Factory LLM minimale — même provider/clé que l'agent SQL existant.

    Lève ``PlanTachesIndisponible`` si aucune clé n'est configurée pour le
    provider actif (dégradation propre, jamais une exception brute).
    """
    provider = (SQL_AGENT_PROVIDER or 'groq').lower()
    if provider == 'groq':
        if not GROQ_API_KEY:
            raise PlanTachesIndisponible('GROQ_API_KEY manquante.')
        from langchain_groq import ChatGroq
        return ChatGroq(model=SQL_AGENT_MODEL, api_key=GROQ_API_KEY, temperature=0)
    raise PlanTachesIndisponible(
        f"Provider LLM '{provider}' non supporté pour la génération de plan.")


def _parser_reponse_llm(texte: str) -> dict:
    """Extrait le premier objet JSON valide de la réponse LLM.

    Tolère un texte entourant le JSON (certains modèles ajoutent des
    explications malgré la consigne). Lève ``ValueError`` si aucun JSON
    exploitable n'est trouvé (l'appelant renvoie alors une erreur propre)."""
    texte = (texte or '').strip()
    debut = texte.find('{')
    fin = texte.rfind('}')
    if debut == -1 or fin == -1 or fin < debut:
        raise ValueError('Réponse LLM sans JSON exploitable.')
    return json.loads(texte[debut:fin + 1])


def _valider_plan(plan: dict) -> dict:
    """Valide/normalise la forme du plan proposé — un plan malformé lève
    ``ValueError`` (l'endpoint retourne 502 plutôt que de propager un plan
    inutilisable à l'ERP)."""
    if not isinstance(plan, dict) or not isinstance(plan.get('taches'), list):
        raise ValueError("Le plan doit contenir une liste 'taches'.")
    taches = []
    codes_connus = set()
    for brut in plan['taches']:
        if not isinstance(brut, dict):
            continue
        code = str(brut.get('code', '')).strip()
        libelle = str(brut.get('libelle', '')).strip()
        if not code or not libelle:
            continue
        phase = str(brut.get('phase', '')).strip().lower()
        if phase not in _PHASES_CONNUES:
            phase = 'etude'
        try:
            duree = int(brut.get('duree_jours', 1) or 1)
        except (TypeError, ValueError):
            duree = 1
        duree = max(1, duree)
        deps = brut.get('dependances_fs') or []
        deps = [str(d).strip() for d in deps if str(d).strip()]
        codes_connus.add(code)
        taches.append({
            'code': code, 'libelle': libelle, 'phase': phase,
            'duree_jours': duree, 'dependances_fs': deps,
        })
    # Retire les dépendances vers un code inexistant (garde-fou anti-crash côté
    # matérialisation ERP) et l'auto-dépendance.
    for tache in taches:
        tache['dependances_fs'] = [
            d for d in tache['dependances_fs']
            if d in codes_connus and d != tache['code']]
    if not taches:
        raise ValueError('Aucune tâche exploitable dans le plan proposé.')
    return {'taches': taches}


def generer_plan_taches(devis_data: dict, type_installation: str) -> dict:
    """Propose un brouillon de WBS (JSON) depuis les lignes d'un devis (XPRJ29).

    ``devis_data`` — dict LECTURE SEULE tel que renvoyé par ``apps.ventes.
    selectors.devis_pour_projet`` côté Django (ce service FastAPI ne se
    connecte JAMAIS à la base ventes : l'ERP lui passe déjà les données).
    Lève ``PlanTachesIndisponible`` sans clé LLM configurée ; ``ValueError``
    si la réponse du LLM est inexploitable. AUCUNE écriture : pure proposition.
    """
    llm = _build_llm()
    prompt = _construire_prompt(devis_data, type_installation)
    try:
        reponse = llm.invoke(prompt)
        texte = getattr(reponse, 'content', None) or str(reponse)
    except Exception as exc:  # pragma: no cover - dépend du réseau/provider
        logger.warning('generer_plan_taches: appel LLM échoué : %s', exc)
        raise ValueError('Le service IA est momentanément indisponible.') from exc

    plan_brut = _parser_reponse_llm(texte)
    return _valider_plan(plan_brut)
