"""Services (écritures / orchestration) du module « calepinage » — CAL233.

POURQUOI UN PAQUET, ET PAS UN MODULE ``services.py``
----------------------------------------------------
Un module ``services.py`` et un paquet ``services/`` ne peuvent pas coexister
dans un même paquet Python. Or le module Calepinage écrit les deux formes selon
les lanes (``services.py`` pour la fondation, ``services/electrique.py``,
``services/pompage.py``… pour l'ingénierie) : le choix est donc TRANCHÉ ICI,
une fois, AVANT toute lane, pour que les lanes restent réellement
file-disjointes. Précédent vérifié dans le dépôt : ``apps/ventes/services.py``
n'est lui-même qu'un ré-export de ``apps/ventes/domain/*``.

LA RÈGLE
--------
* un SOUS-MODULE par domaine (``creation``, ``layout``, ``variantes``,
  ``versions``, ``liens``, ``journal``, ``electrique``, ``production``,
  ``consommation``, ``pompage``, ``planche``, ``sorties``…) ;
* ce ``__init__`` RÉ-EXPORTE les fonctions publiques : l'appelant écrit
  ``from apps.calepinage import services`` puis ``services.creer_pour_lead(...)``
  sans jamais connaître le découpage interne ;
* les imports sont FONCTION-LOCAUX dans les sous-modules là où ils évitent un
  cycle au chargement des apps.

FRONTIÈRE INTER-APPS (import-linter) — une AUTRE app qui écrit dans ce module
passe par une fonction ré-exportée ici, jamais par ``apps.calepinage.models``
ou ``.views``. Symétriquement, ce module ne lit crm / ventes / ao QUE par leurs
``selectors.py`` (``apps.crm.selectors``, ``apps.ventes.selectors``,
``apps.ao.selectors``).
"""
from __future__ import annotations

#: Les sous-modules de services, dans l'ordre où les lanes les posent. La liste
#: est DOCUMENTAIRE (aucun import au chargement) : elle dit où va quoi, pour
#: qu'aucune lane n'invente un second foyer pour un domaine existant.
SOUS_MODULES = (
    'parametres',     # CAL45 — réglages société (une base, sept extensions)
    'site',           # CAL47 — section « imagerie & pays » (contrat CAL46)
    'lidar_ign',      # CAL237 — suggestion pente/azimut IGN (France seule)
    'photos',         # CAL52 — photos de site (records.Attachment + MinIO)
    'releve',         # CAL64 — relevé terrain (solveur de cotes du noyau)
    'zones',          # CAL68 — exclusionZones -> zones du moteur
    'zones_reglementaires',  # CAL74 — gabarits de zone SOURCÉS (CAL45)
    'creation',       # CAL11 — obtenir_ou_creer_pour_devis / lead / client
    'liens',          # CAL12 — lier_devis / lier_appel_offre
    'layout',         # CAL13 — enregistrer_layout (hash + version)
    'variantes',      # CAL9 + CAL14 — creer / retenir / dupliquer
    'versions',       # CAL8 — instantanés jamais réécrits, purge bornée
    'devis',          # CAL24/CAL25 — générer / resynchroniser (via ventes)
    'journal',        # CAL26 — chatter par la primitive records
    'norme',          # CAL130 — norme électrique applicable (règle D5)
    'electrique',     # CAL123/125/127-130/170 — entrée et verdicts électriques
    'chaines',        # CAL124/125 — chaînes par pan et affectation nominative
    'cables',         # CAL131 — sections et chutes sur les longueurs du plan
    'protections',    # CAL132 — check-list d'organes paramétrable
    'terre',          # CAL134 — check-list de mise à la terre
)

__all__ = ['SOUS_MODULES']


def __getattr__(nom):
    """Ré-export PARESSEUX des fonctions publiques des sous-modules.

    ``services.creer_pour_lead`` résout à la volée vers
    ``services.creation.creer_pour_lead``. Paresseux à dessein : importer
    ``apps.calepinage.services`` ne doit charger NI les modèles NI une app
    tierce au démarrage de Django (les sous-modules sont importés au premier
    usage réel, jamais au chargement des apps).
    """
    from importlib import import_module

    for sous_module in SOUS_MODULES:
        chemin = f'{__name__}.{sous_module}'
        try:
            module = import_module(chemin)
        except ModuleNotFoundError as erreur:
            # Un sous-module pas encore posé par sa lane est simplement SAUTÉ ;
            # une dépendance manquante DANS un sous-module existant remonte
            # telle quelle (ne jamais avaler une vraie erreur d'import).
            if erreur.name != chemin:
                raise
            continue
        if hasattr(module, nom):
            return getattr(module, nom)
    raise AttributeError(
        f"Le module de services « calepinage » n'expose pas « {nom} ». "
        f"Sous-modules connus : {', '.join(SOUS_MODULES)}.")
