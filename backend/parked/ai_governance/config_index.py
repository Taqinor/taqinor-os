"""NTAI35 — Index des écrans de PARAMÉTRAGE (« Setup Copilot »).

Catalogue statique, en LECTURE SEULE, des écrans de configuration réellement
montés dans la SPA, avec leur lien profond, leurs mots-clés et un résumé
utilisable tel quel comme réponse de FAQ quand aucun LLM n'est configuré.

DEUX GARDES structurantes :

  1. **Aucun lien inventé.** Chaque ``lien`` ci-dessous doit exister dans
     ``frontend/src/features/parametres/module.config.jsx`` — un test le
     vérifie en lisant CE fichier. C'est la réponse directe au travers connu du
     dépôt (des URL profondes ad-hoc qui tombent en 404).
  2. **Aucune écriture.** Ce module ne fait que guider ; il n'expose aucune
     fonction d'écriture, et l'endpoint qui le consomme est en lecture seule.

Récupération : score par mots-clés (déterministe, sans clé, sans réseau).
Quand la recherche sémantique cross-module (NTAI24/25) sera posée, seule
:func:`rechercher_ecrans` changera de moteur — le contrat de sortie et
l'endpoint restent identiques.
"""
from __future__ import annotations

import re
import unicodedata

#: Écrans de configuration. ``roles`` reflète le gating RÉEL de la route SPA
#: (``module.config.jsx``) : un utilisateur qui n'y a pas droit ne se voit
#: jamais proposer le lien.
CONFIG_ENTRIES = [
    {
        'cle': 'entreprise',
        'titre': "Paramètres de l'entreprise",
        'lien': '/parametres',
        'roles': ['responsable', 'admin'],
        'mots_cles': [
            'tva', 'taux de tva', 'ice', 'identifiant fiscal', 'rib',
            'logo', 'raison sociale', 'adresse', 'entreprise', 'société',
            'mentions légales', 'devise', 'coordonnées',
        ],
        'resume': (
            "Le taux de TVA par défaut, l'ICE, l'identifiant fiscal, le RIB, "
            "le logo et les coordonnées de la société se règlent dans "
            "Paramètres → Entreprise."
        ),
    },
    {
        'cle': 'notifications',
        'titre': 'Préférences de notification',
        'lien': '/parametres/notifications',
        'roles': [],
        'mots_cles': [
            'notification', 'notifications', 'alerte par email', 'email',
            'whatsapp', 'push', 'relance', 'relances', 'rappel', 'rappels',
            'heures calmes', 'canal',
        ],
        'resume': (
            "Les canaux de notification (in-app, e-mail, WhatsApp, push), les "
            "rappels et relances automatiques et les heures calmes s'activent "
            "écran par écran dans Paramètres → Notifications."
        ),
    },
    {
        'cle': 'alertes_kpi',
        'titre': 'Alertes sur KPI',
        'lien': '/parametres/alertes-kpi',
        'roles': ['responsable', 'admin'],
        'mots_cles': [
            'alerte', 'alertes', 'kpi', 'seuil', 'seuils', 'indicateur',
            'indicateurs', 'tableau de bord', 'objectif',
        ],
        'resume': (
            "Les alertes de seuil sur les KPI agrégés (déclenchement, "
            "destinataires) se configurent dans Paramètres → Alertes KPI."
        ),
    },
    {
        'cle': 'export',
        'titre': 'Export & sauvegarde',
        'lien': '/parametres/export',
        'roles': [],
        'mots_cles': [
            'export', 'exporter', 'sauvegarde', 'backup', 'données',
            'portabilité', 'archive',
        ],
        'resume': (
            "L'export complet des données de la société et les sauvegardes se "
            "lancent depuis Paramètres → Export & sauvegarde."
        ),
    },
    {
        'cle': 'marketing',
        'titre': "Domaine d'envoi (SPF/DKIM/DMARC)",
        'lien': '/parametres/marketing',
        'roles': ['responsable', 'admin'],
        'mots_cles': [
            'domaine', "domaine d'envoi", 'spf', 'dkim', 'dmarc',
            'délivrabilité', 'emailing', 'campagne', 'marketing',
        ],
        'resume': (
            "Le domaine d'envoi e-mail et ses enregistrements SPF/DKIM/DMARC "
            "se vérifient dans Paramètres → Marketing."
        ),
    },
    {
        'cle': 'vues',
        'titre': 'Configuration des vues',
        'lien': '/parametres/vues',
        'roles': ['responsable', 'admin'],
        'mots_cles': [
            'vue', 'vues', 'colonnes', 'filtre', 'filtres', 'affichage',
            'liste', 'tri', 'groupement', 'vue par défaut',
        ],
        'resume': (
            "Les vues sauvegardées (colonnes, filtres, tri) et la vue par "
            "défaut d'un rôle se pilotent dans Paramètres → Vues."
        ),
    },
    {
        'cle': 'territoires',
        'titre': 'Territoires commerciaux',
        'lien': '/parametres/territoires',
        'roles': ['responsable', 'admin'],
        'mots_cles': [
            'territoire', 'territoires', 'secteur', 'zone', 'affectation',
            'répartition', 'ville', 'région',
        ],
        'resume': (
            "Le découpage des territoires commerciaux et leur affectation se "
            "règlent dans Paramètres → Territoires."
        ),
    },
    {
        'cle': 'playbooks',
        'titre': 'Playbooks commerciaux',
        'lien': '/parametres/playbooks',
        'roles': ['responsable', 'admin'],
        'mots_cles': [
            'playbook', 'playbooks', 'étape', 'étapes', 'tâche', 'tâches',
            'processus de vente', 'pipeline', 'stage',
        ],
        'resume': (
            "Les playbooks (étapes et tâches attendues par stade du pipeline) "
            "se créent dans Paramètres → Playbooks."
        ),
    },
    {
        'cle': 'achats',
        'titre': 'Paramètres achats',
        'lien': '/parametres/achats',
        'roles': ['responsable', 'admin'],
        'mots_cles': [
            'achat', 'achats', 'fournisseur', 'fournisseurs', 'commande',
            'approvisionnement', 'tolérance', 'réception',
        ],
        'resume': (
            "Les règles d'achat (tolérances de réception, politique de "
            "facturation fournisseur) sont dans Paramètres → Achats."
        ),
    },
    {
        'cle': 'ia',
        'titre': 'Diagnostic IA',
        'lien': '/parametres/ia',
        'roles': ['admin'],
        'mots_cles': [
            'ia', 'intelligence artificielle', 'ocr', 'transcription',
            'chatbot', 'clé api', 'fournisseur ia', 'llm', 'diagnostic',
        ],
        'resume': (
            "L'état des capacités IA (OCR, transcription, LLM) et des clés "
            "configurées se consulte dans Paramètres → IA."
        ),
    },
    {
        'cle': 'journal',
        'titre': "Journal d'activité",
        'lien': '/journal',
        'roles': ['normal', 'responsable', 'admin'],
        'mots_cles': [
            'journal', 'historique', 'audit', 'trace', 'qui a modifié',
            'activité',
        ],
        'resume': (
            "Qui a fait quoi et quand se retrouve dans le Journal d'activité."
        ),
    },
]


def _sans_accents(texte: str) -> str:
    normalise = unicodedata.normalize('NFD', str(texte or '').lower())
    return ''.join(c for c in normalise if unicodedata.category(c) != 'Mn')


_MOT_RE = re.compile(r"[a-z0-9]+")

#: Mots vides FR — sans eux, « où » et « comment » domineraient le score.
_STOPWORDS = frozenset({
    'ou', 'comment', 'je', 'peux', 'puis', 'on', 'le', 'la', 'les', 'de',
    'des', 'du', 'un', 'une', 'et', 'a', 'au', 'aux', 'en', 'pour', 'dans',
    'sur', 'est', 'ce', 'cette', 'qui', 'que', 'quoi', 'mon', 'ma', 'mes',
    'se', 'faire', 'fait', 'regler', 'reglage', 'activer', 'configurer',
    'parametre', 'parametres', 'trouve', 'trouver', 'ecran', 'page',
})


def _mots_utiles(texte: str) -> list:
    return [m for m in _MOT_RE.findall(_sans_accents(texte))
            if len(m) > 2 and m not in _STOPWORDS]


def _tokens(texte: str) -> set:
    """Mots (sans accents) d'un texte — comparaison par MOT ENTIER.

    Volontairement PAS une comparaison par sous-chaîne : « devis » ne doit pas
    matcher « devise », sinon une question sur un devis renvoie l'écran des
    devises (faux positif observé et corrigé).
    """
    return set(_MOT_RE.findall(_sans_accents(texte)))


def _score(entry: dict, mots: list) -> int:
    """Score déterministe d'un écran pour une question."""
    if not mots:
        return 0
    cles = _tokens(' '.join(entry['mots_cles']))
    titre = _tokens(entry['titre'])
    resume = _tokens(entry['resume'])
    total = 0
    for mot in set(mots):
        if mot in cles:
            total += 3
        if mot in titre:
            total += 2
        if mot in resume:
            total += 1
    return total


def rechercher_ecrans(question: str, *, role=None, limit=3) -> list:
    """Écrans de configuration les plus pertinents pour ``question``.

    Déterministe, hors ligne, sans clé. ``role`` (``role_legacy``) filtre les
    écrans que l'utilisateur ne peut pas atteindre — on ne propose jamais un
    lien qui répondrait 403.
    """
    mots = _mots_utiles(question)
    resultats = []
    for entry in CONFIG_ENTRIES:
        roles = entry.get('roles') or []
        if role is not None and roles and role not in roles:
            continue
        score = _score(entry, mots)
        if score > 0:
            resultats.append((score, entry))
    resultats.sort(key=lambda couple: (-couple[0], couple[1]['cle']))
    return [entry for _score_, entry in resultats[:limit]]
