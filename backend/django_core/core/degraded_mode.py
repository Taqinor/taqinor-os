"""NTOBS11 — mode dégradé documenté et exposé par dépendance externe.

``core/health.py`` (FG397) détecte DÉJÀ chaque service down (``check_services``)
mais ne documente/n'expose pas ce qui reste FONCTIONNEL côté métier quand
c'est le cas. Ce module ajoute la MATRICE (registre STATIQUE versionné dans
le code, jamais en DB — dict pur, aucune dépendance) qui traduit un statut de
sonde en impact humain lisible.

Doc jumelle ``docs/degraded-mode.md`` : NON créée dans ce lot (contrainte de
périmètre de cette lane — jamais toucher ``docs/``) ; la matrice ci-dessous
EST la source de vérité versionnée, et cette docstring en tient lieu de
résumé technique jusqu'à ce qu'une lane autorisée à toucher ``docs/`` publie
le miroir texte.
"""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Registre STATIQUE (dict pur) — jamais en DB, jamais généré dynamiquement :
# chaque entrée est une description humaine, écrite une fois, relue à chaque
# incident. Clés alignées sur les dépendances externes réelles du dépôt.
DEGRADED_MODE_MATRIX = {
    'db': {
        'label': 'Base de données (PostgreSQL)',
        'impactees': [
            'Toute lecture/écriture (CRM, devis, factures, chantiers, tickets)',
            'Authentification (connexion/déconnexion)',
        ],
        'continuent': [],
    },
    'cache': {
        'label': 'Cache (Redis)',
        'impactees': [
            'Limites de débit (rate-limit) moins précises',
            'Page de statut publique et compteurs de configuration recalculés '
            'à chaque requête plutôt que servis depuis le cache',
        ],
        'continuent': [
            'CRUD standard (leads, devis, factures)',
            'Génération de PDF',
            'Authentification',
        ],
    },
    'celery_broker': {
        'label': 'Broker de tâches asynchrones (Celery/Redis)',
        'impactees': [
            'Envois différés (email/WhatsApp en tâche de fond)',
            'Exports planifiés et rapports SLA mensuels',
            'Notifications par lot (digest, relances programmées)',
            "Export de réversibilité (tâche asynchrone)",
        ],
        'continuent': [
            'CRUD standard (leads, devis, factures)',
            'Génération de PDF de proposition (synchrone)',
            'Authentification',
        ],
    },
    'storage': {
        'label': 'Stockage objet (MinIO)',
        'impactees': [
            'Génération de PDF devis dégradée (pas de photos/pièces jointes)',
            'Téléversement et consultation de documents (GED)',
            'Export de réversibilité (dépend du stockage)',
        ],
        'continuent': [
            'CRUD leads/devis/factures',
            'Authentification',
            'Notifications in-app',
        ],
    },
    'llm_ia': {
        'label': 'Fournisseurs IA (OCR/LLM, key-gated)',
        'impactees': [
            'Copilotes IA contextuels (résumés, suggestions de brouillon)',
            'OCR de documents',
            'Assistant conversationnel / agent de requêtes en langage naturel',
        ],
        'continuent': [
            "Tout le reste de l'ERP — l'IA reste un copilote qui PROPOSE, "
            'jamais un chemin obligatoire (aucune écriture métier implicite).',
        ],
    },
}

# Correspondance clé de la matrice -> nom de sonde ``core.health.check_services()``
# (``llm_ia`` n'a pas de sonde infra dédiée — même limite que le composant
# public « IA » de ``apps.statuspage.tasks``, dérivé de ``core.ai.registry``
# plutôt que d'un probe direct).
_PROBE_NAME_FOR_KEY = {
    'db': 'database',
    'cache': 'cache',
    'celery_broker': 'broker',
    'storage': 'storage',
}


def _statut_llm_ia():
    """Best-effort, même logique que ``apps.statuspage.tasks._statut_ia_public``
    (pas de sonde infra dédiée pour l'IA — dérivé du registre de fournisseurs)."""
    try:
        from core.ai.registry import is_capability_configured
    except Exception:  # noqa: BLE001 — module IA absent/KO, jamais bloquant
        return 'unknown'
    for capability in ('llm', 'ocr', 'stt'):
        try:
            is_capability_configured(capability)
        except Exception:  # noqa: BLE001
            return 'degraded'
    return 'ok'


def degraded_mode_status():
    """NTOBS11 — combine les statuts RÉELS (``check_services()``) avec la
    matrice d'impact humain. Renvoie une liste ``[{cle, label, statut,
    impactees, continuent}]``."""
    from . import health

    try:
        services = {s['name']: s['status'] for s in health.check_services()}
    except Exception:  # noqa: BLE001 — jamais bloquant
        services = {}

    resultat = []
    for cle, entree in DEGRADED_MODE_MATRIX.items():
        if cle == 'llm_ia':
            statut = _statut_llm_ia()
        else:
            probe_name = _PROBE_NAME_FOR_KEY.get(cle)
            statut = services.get(probe_name, 'unknown')
        resultat.append({
            'cle': cle,
            'label': entree['label'],
            'statut': statut,
            'impactees': entree['impactees'],
            'continuent': entree['continuent'],
        })
    return resultat


@api_view(['GET'])
@permission_classes([AllowAny])
def degraded_mode_status_view(request):
    """GET /api/django/core/degraded-mode-status/ — public (AllowAny), ZÉRO
    donnée société (infra système uniquement) — même politique que les
    probes ``health/live``/``health/ready`` déjà publiques dans ce fichier.
    Consommé par la page de statut publique (NTOBS1) ET le panneau admin
    interne (Paramètres → Fiabilité → « État des dépendances »)."""
    return Response(degraded_mode_status())
