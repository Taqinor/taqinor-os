"""Gardes de MODULE de la lecture SQL de l'assistant (données, sans code).

Lues par ``sql_agent_service._verifier_module_et_portee`` (ALEC16, règle de
``core/data_explorer.py::run_query`` portée à l'agent). Déplacées ici (copilote
vague 2, FND12) : ``sql_agent_service.py`` est au mur des 2 000 lignes.
"""
from __future__ import annotations

# ALEC16 (C-ALEC-014, APFS4) — prefixe de table -> prefixes de code du module
# (au moins un exige), et tables a proprietaire refusees a une portee restreinte.
# FND12 — les tables de COMPTE et de REGLAGES (utilisateurs, societe, roles et
# leurs permissions, profil de la societe : RIB, ICE, politique de securite)
# exigent un droit d'administration : un commercial ne les lit plus par
# l'assistant (les colonnes secretes restent refusees a TOUS, AUD401).
# `parametres_voir` ne suffit PAS : le registre le donne a presque tous les
# roles (Commercial, Technicien, Viewer…) ; le droit de MODIFIER les reglages
# (Directeur, Administrateur) ou de gerer les comptes est exige.
MODULE_DES_TABLES = (
    ("ventes_", ("ventes_", "encaisser")), ("crm_", ("crm_",)),
    ("installations_", ("installation_", "intervention_")),
    ("sav_", ("sav_",)), ("stock_", ("stock_",)),
    ("adsengine_", ("adsengine_",)),  # ALEC46 : miroirs publicitaires
    ("authentication_", ("users_gerer", "roles_gerer", "parametres_modifier")),
    ("roles_", ("roles_gerer",)),
    ("parametres_", ("parametres_modifier",)),
)
TABLES_A_PROPRIETAIRE = frozenset({
    "ventes_devis", "ventes_facture", "ventes_boncommande", "crm_client",
    "installations_installation", "sav_ticket",
    # ALEC41 — lignes de documents, interventions et parc : memes proprietaires.
    "ventes_lignedevis", "ventes_lignefacture", "installations_intervention",
    "sav_equipement", "sav_contratmaintenance",
})
