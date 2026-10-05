"""CALX145 — LE REGISTRE DES CLÉS des deux sections de réglages société
« simulation » et « electrique_societe » : une ligne par clé, ajoutée EN FIN.

POURQUOI CE FICHIER EXISTE (décision D-CALX 13, 21/09/2026)
------------------------------------------------------------
``ParametresCalepinage.SECTIONS`` était un tuple FERMÉ de neuf sections, et
``sections_inconnues()`` refusait tout le reste : aucune n'accueillait un
modèle d'incidence, une fenêtre d'années, une tolérance de polystring ni une
correspondance de nomenclature. Chaque tâche de simulation aurait donc réclamé
sa section — ou pire, un défaut codé dans son module.

Ici, DEUX sections et UN registre : chaque tâche qui a besoin d'un réglage
AJOUTE sa clé à l'un des deux tuples ci-dessous, avec son libellé français,
son unité et sa référence doctrinale. Rien d'autre n'entre dans ce fichier :
ni calcul, ni valeur, ni défaut.

LA RÈGLE, ET ELLE EST STRICTE
------------------------------
* UNE ligne par clé déclarée, terminée par son commentaire ``# CALX<id>`` ;
* elle s'ajoute **EN FIN** du tuple de sa section, jamais au milieu ;
* l'ordre existant n'est **JAMAIS** réordonné ni raccourci (la garde
  ``tests/test_calx145_parametres_simulation.py`` fige le socle initial et
  exige qu'il reste le PRÉFIXE de chaque tuple) ;
* ce fichier est déclaré APPEND-ONLY dans ``scripts/plan_lanes.py``
  (``_APPEND_ONLY_SUFFIXES``) : deux tâches qui l'écrivent ne fondent donc pas
  leurs lanes.

ZÉRO CHIFFRE INVENTÉ (décision D-CALX 7)
-----------------------------------------
Aucune VALEUR ne figure ici : le registre dit quelles clés EXISTENT, jamais ce
qu'elles valent. Une clé non saisie veut dire « non saisi », c'est-à-dire le
comportement d'aujourd'hui — l'étape qui en dépend est OMISE en nommant ce qui
manque, jamais forfaitisée. Les seuils publiés par les logiciels du marché
(tolérances de polystring, coefficients thermiques, LID) sont proposés en AIDE
à la saisie par l'écran de réglages, jamais préremplis.

Chaque valeur se saisit ``{valeur, source, reference}`` avec
``source ∈ SOURCES_ADMISES`` ; une valeur sans source est REFUSÉE en nommant
la clé (``services/parametres.py``).

SOURCES CITÉES (les références doctrinales ci-dessous renvoient ici)
---------------------------------------------------------------------
* PVsyst — Array and system losses :
  https://www.pvsyst.com/help/project-design/array-and-system-losses/index.html
* PVsyst — Array incidence loss (IAM) :
  https://www.pvsyst.com/help/project-design/array-and-system-losses/array-incidence-loss-iam.html
* PVsyst — Module quality losses :
  https://www.pvsyst.com/help/project-design/array-and-system-losses/module-quality-losses.html
* PVsyst — LID loss :
  https://www.pvsyst.com/help/project-design/array-and-system-losses/lid-loss.html
* PVsyst — Array thermal losses :
  https://www.pvsyst.com/help/project-design/array-and-system-losses/array-thermal-losses/index.html
* PVsyst — P50/P90 evaluations :
  https://www.pvsyst.com/help/project-design/p50-p90-evaluations.html
* PV*SOL — Configuration check :
  https://help.valentin-software.com/pvsol/en/pages/inverters/configuration-check/
* HelioScope — TMY weather file primer :
  https://help-center.helioscope.com/hc/en-us/articles/8316899662099-TMY-Weather-File-Primer
* PVGIS — seriescalc / printhorizon :
  https://joint-research-centre.ec.europa.eu/pvgis-online-tool_en
"""
from __future__ import annotations

#: Les DEUX sections que CALX145 ouvre. Elles vivent dans
#: ``ParametresCalepinage`` comme les neuf autres : une section vide ``{}``
#: veut dire « rien de saisi », donc « comportement d'aujourd'hui » (D12).
SECTION_SIMULATION = 'simulation'
SECTION_ELECTRIQUE_SOCIETE = 'electrique_societe'

#: CALX307 — la section « documents » (configuration DOCUMENTAIRE, par CODE
#: de document — ``{code_document: {sections: [...], langue: null}}``), et
#: le CODE du seul document qui s'y range aujourd'hui. Nommés ici pour la
#: même raison que les deux constantes ci-dessus (une chaîne écrite UNE
#: fois) — mais cette section n'entre PAS dans ``REGISTRES`` : sa forme
#: n'est pas ``{clé: {valeur, source, reference}}``, c'est une sélection de
#: codes validée par ``services/rapport/sections_societe.py`` contre le
#: contrat ``rapport_etude.json``, pas par ce registre.
SECTION_DOCUMENTS = 'documents'
CODE_RAPPORT_ETUDE = 'rapport_etude'

#: LA PROVENANCE ADMISE d'une valeur saisie — sans elle, la valeur est
#: refusée en nommant la clé (D-CALX 7 : un chiffre qu'on ne peut pas sourcer
#: ne se défend pas).
#:
#: * ``societe`` — la société l'a arrêtée et l'assume ;
#: * ``mesure``  — elle vient d'une mesure faite sur site ou en atelier ;
#: * ``saisie``  — elle vient d'un document du projet (fiche, devis, plan) ;
#: * ``texte``   — elle vient d'un texte cité, dont ``reference`` dit lequel.
SOURCES_ADMISES = ('societe', 'mesure', 'saisie', 'texte')

#: Les clés ADMISES de la section ``simulation`` :
#: ``(clé, libellé français, unité, référence doctrinale)``.
#: UNE LIGNE PAR CLÉ, AJOUTÉE EN FIN — voir la règle en tête de module.
CLES_SIMULATION = (
    ('fenetre_annees', "Fenêtre d'années météo", 'années', 'PVGIS — seriescalc, fenêtre pluriannuelle'),  # CALX145
    ('mode_meteo', 'Mode météo (année type ou fenêtre pluriannuelle)', '', 'HelioScope — TMY weather file primer'),  # CALX145
    ('modele_iam', "Modèle d'incidence (IAM)", '', 'PVsyst — Array incidence loss (IAM)'),  # CALX145
    ('b0_iam', 'Coefficient b0 du modèle ASHRAE', '', 'PVsyst — Array incidence loss (IAM)'),  # CALX145
    ('sigma_modele_pct', 'Incertitude de simulation (σ modèle)', '%', 'PVsyst — P50/P90 evaluations'),  # CALX145
    ('sigma_biais_meteo_pct', 'Biais long terme de la source météo (σ)', '%', 'PVsyst — P50/P90 evaluations'),  # CALX145
    ('sigma_meteo_saisi_pct', 'Variabilité interannuelle saisie (σ météo)', '%', 'PVsyst — P50/P90 evaluations'),  # CALX145
    ('tolerance_validation_pct', "Tolérance d'écart admise face à PVGIS", '%', 'Décision fondateur 21/09/2026 — aucun verdict sans tolérance saisie'),  # CALX145
    ('resolution_minutes', 'Pas de temps de la simulation', 'minutes', 'PVGIS — seriescalc, pas horaire'),  # CALX145
    ('albedo_mensuel', 'Albédo du sol, mois par mois', '', 'PVsyst — Array and system losses'),  # CALX145
    ('annees_exploitation', "Durée d'exploitation simulée", 'années', 'PVsyst — Array and system losses'),  # CALX145
    ('regle_qualite_module', 'Règle de qualité module (tolérance de puissance)', '', 'PVsyst — Module quality losses'),  # CALX145
    ('lid_par_techno', 'Perte LID déclarée par technologie de cellule', '%', 'PVsyst — LID loss (aucune valeur par défaut proposée)'),  # CALX145
    ('mismatch_fabricant_pct', 'Mismatch de fabrication entre modules', '%', 'PVsyst — Array and system losses'),  # CALX145
    ('modele_degradation', 'Modèle de dégradation pluriannuelle', '', 'PVsyst — Array and system losses'),  # CALX145
    ('thermique_par_pose', 'Coefficients Uc/Uv par type de pose', 'W/m²K et W/m³sK', 'PVsyst — Array thermal losses (Faiman)'),  # CALX145
    ('attenuation_horizon', "Atténuation appliquée au profil d'horizon", '', 'PVGIS — printhorizon, profil DEM'),  # CALX145
    ('salissure_mensuelle_pct', 'Salissure, mois par mois (12 valeurs, ou une seule pour les douze)', '%', 'PVsyst — Soiling loss (facteurs MENSUELS, aucune valeur universelle par défaut)'),  # CALX161
    ('indisponibilite_fenetres', "Fenêtres d'arrêt de l'installation (début, fin, motif)", '', 'PVsyst — Unavailability loss (des périodes d\'arrêt explicites, jamais un forfait annuel)'),  # CALX176
    ('auxiliaires_w_constants', 'Auxiliaires — terme constant en marche', 'W', 'PVsyst — Auxiliaries consumption (terme constant au-dessus d\'un seuil)'),  # CALX175
    ('auxiliaires_w_par_kw', 'Auxiliaires — terme proportionnel à la production', 'W/kW', 'PVsyst — Auxiliaries consumption (terme proportionnel en W/kW)'),  # CALX175
    ('auxiliaires_w_nuit', 'Auxiliaires — consommation de nuit', 'W', 'PVsyst — Auxiliaries consumption (consommation de nuit, valeur fixe distincte)'),  # CALX175
    ('bifacial_hauteur_pose_m', 'Hauteur de pose de la face arrière au-dessus du sol (repli quand le document ne la porte pas)', 'm', 'PVsyst — Bifacial systems (facteurs de vue : hauteur de pose)'),  # CALX177
    ('bifacial_taux_occupation', "Taux d'occupation du sol (GCR) retenu pour la face arrière (repli quand le document ne le porte pas)", '', 'PVsyst — Bifacial systems (facteurs de vue : taux d\'occupation)'),  # CALX177
    ('bifacial_pas_rangee_m', 'Pas entre rangées retenu pour la face arrière (repli quand le document ne le porte pas)', 'm', 'PVsyst — Bifacial systems (facteurs de vue : pas entre rangées)'),  # CALX177
    ('bifacial_mismatch_arriere_pct', 'Mismatch de face arrière', '%', 'PVsyst — Bifacial systems (les 10 % du logiciel sont CITÉS en aide à la saisie, jamais préremplis)'),  # CALX177
    ('seuil_derivation_acces', "Seuil d'accès solaire sous lequel un module est dérivé de sa chaîne", '', 'PV*SOL — Shading due to nearby objects (la caractéristique du module s\'effondre selon le nombre de brins ombrés ; aucun seuil n\'est proposé par défaut)'),  # CALX168
    ('plafond_modules_simules', 'Plafond de modules simulés un par un (au-delà, seul l\'agrégat est publié)', 'modules', 'Décision fondateur 21/09/2026 — plafond de simulation module par module à 5 000 modules, mesuré par CALX389'),  # CALX182
)

#: Les clés ADMISES de la section ``electrique_societe``, même forme et même
#: discipline d'ajout que ci-dessus.
CLES_ELECTRIQUE_SOCIETE = (
    ('tolerance_polystring_acceptable_pct', 'Tolérance de polystring acceptable', '%', 'PV*SOL — Configuration check (valeur du logiciel citée en aide, jamais préremplie)'),  # CALX145
    ('tolerance_polystring_bloquante_pct', 'Tolérance de polystring bloquante', '%', 'PV*SOL — Configuration check (valeur du logiciel citée en aide, jamais préremplie)'),  # CALX145
    ('seuil_desequilibre_pct', 'Seuil de déséquilibre entre chaînes', '%', 'PV*SOL — Configuration check'),  # CALX145
    ('borne_usuelle_dc_ac', 'Borne usuelle du rapport DC/AC', '', 'PV*SOL — Configuration check'),  # CALX145
    ('seuil_alerte_dc_ac', "Seuil d'alerte du rapport DC/AC", '', 'PV*SOL — Configuration check'),  # CALX145
    ('correspondances_nomenclature', 'Correspondances de nomenclature du bordereau', '', 'Réglage société — aucun code article n\'est deviné'),  # CALX145
    ('regle_bom_structure', 'Règle de sortie de la structure hors bordereau électrique', '', 'Décision fondateur 21/09/2026 — la structure sort du bordereau électrique'),  # CALX145
    ('cos_phi_par_defaut', 'Cos φ retenu à défaut de mesure', '', 'Réglage société — aucune valeur n\'est supposée'),  # CALX145
    ('seuil_bas_dc_ac', 'Seuil bas du rapport DC/AC (onduleur sous-utilisé)', '', 'OpenSolar — Inverter sizing and stringing recommendations'),  # CALX213
)

#: ``{section: tuple de déclarations}`` — le SEUL point d'entrée des lecteurs.
#: Une section absente de ce dict n'a pas de registre : elle traverse
#: inchangée (comportement des neuf sections historiques).
REGISTRES = {
    SECTION_SIMULATION: CLES_SIMULATION,
    SECTION_ELECTRIQUE_SOCIETE: CLES_ELECTRIQUE_SOCIETE,
}

__all__ = [
    'SECTION_SIMULATION', 'SECTION_ELECTRIQUE_SOCIETE', 'SECTION_DOCUMENTS',
    'CODE_RAPPORT_ETUDE', 'SOURCES_ADMISES', 'CLES_SIMULATION',
    'CLES_ELECTRIQUE_SOCIETE', 'REGISTRES', 'registre',
]


def registre(section):
    """``{clé: (libellé, unité, référence)}`` pour ``section``.

    Lecture PURE d'une déclaration : aucune valeur, aucun défaut, aucun accès
    base. Une section sans registre rend ``{}``.
    """
    return {cle: (libelle, unite, reference)
            for cle, libelle, unite, reference in REGISTRES.get(section, ())}


# ── ACAL132 — LE TYPE DE CHAQUE CLÉ (surface APPEND-ONLY, ajout en fin) ─────
#
# Le registre ci-dessus dit quelles clés EXISTENT ; cette table dit de QUEL
# TYPE est la valeur de chacune, pour que ``services/parametres.py`` refuse à
# l'ÉCRITURE une valeur illisible en nommant la clé (une virgule décimale
# « 2,5 » est normalisée en 2.5) au lieu de laisser l'étape qui la lit
# basculer en silence sur un repli (``etapes/iam.py`` : b0 illisible ⇒
# Fresnel). Toujours AUCUNE valeur ni défaut : un type et, quand la grandeur
# en a par définition, ses bornes (un pourcentage est dans [0, 100], un cos φ
# dans [0, 1]) — jamais un seuil métier inventé.
#
# Les types, publiés tels quels par ``selectors.registre_des_reglages`` :
#   * ``nombre``            — un réel fini (« 2,5 » admis) ;
#   * ``pourcentage``       — un réel fini dans [0, 100] ;
#   * ``entier``            — un entier (≥ ``minimum`` quand il est déclaré) ;
#   * ``enum``              — un mot parmi ``valeurs`` (casse et espaces tolérés) ;
#   * ``table_mensuelle``   — un nombre (les douze mois), douze valeurs, ou un
#     objet keyé 1…12 ; chaque valeur est un nombre fini (bornes comprises) ;
#   * ``intervalle_annees`` — deux années « 2015-2024 » ou [2015, 2024],
#     rangées [début, fin] ;
#   * ``booleen``           — oui / non (vrai, faux, 1, 0, « aucune », « non »…),
#     rangé en booléen ;
#   * ``table``             — une table structurée (objet ou liste non vide),
#     validée ligne par ligne par l'étape qui la lit.
TYPES_CLES = {
    SECTION_SIMULATION: {
        'fenetre_annees': {'type': 'intervalle_annees'},  # ACAL132
        'mode_meteo': {'type': 'enum', 'valeurs': ('tmy', 'pluriannuel')},  # ACAL132
        'modele_iam': {'type': 'enum', 'valeurs': ('fresnel', 'ashrae', 'martin_ruiz')},  # ACAL132
        'b0_iam': {'type': 'nombre'},  # ACAL132
        'sigma_modele_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'sigma_biais_meteo_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'sigma_meteo_saisi_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'tolerance_validation_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'resolution_minutes': {'type': 'entier', 'minimum': 1},  # ACAL132
        'albedo_mensuel': {'type': 'table_mensuelle', 'minimum': 0, 'maximum': 1},  # ACAL132
        'annees_exploitation': {'type': 'entier', 'minimum': 1},  # ACAL132
        'regle_qualite_module': {'type': 'enum', 'valeurs': ('quart_pvsyst', 'borne_basse', 'moyenne', 'aucune')},  # ACAL132
        'lid_par_techno': {'type': 'table'},  # ACAL132
        'mismatch_fabricant_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'modele_degradation': {'type': 'enum', 'valeurs': ('lineaire', 'exponentiel')},  # ACAL132
        'thermique_par_pose': {'type': 'table'},  # ACAL132
        'attenuation_horizon': {'type': 'booleen'},  # ACAL132
        'salissure_mensuelle_pct': {'type': 'table_mensuelle', 'minimum': 0, 'maximum': 100},  # ACAL132
        'indisponibilite_fenetres': {'type': 'table'},  # ACAL132
        'auxiliaires_w_constants': {'type': 'nombre', 'minimum': 0},  # ACAL132
        'auxiliaires_w_par_kw': {'type': 'nombre', 'minimum': 0},  # ACAL132
        'auxiliaires_w_nuit': {'type': 'nombre', 'minimum': 0},  # ACAL132
        'bifacial_hauteur_pose_m': {'type': 'nombre', 'minimum': 0},  # ACAL132
        'bifacial_taux_occupation': {'type': 'nombre', 'minimum': 0, 'maximum': 1},  # ACAL132
        'bifacial_pas_rangee_m': {'type': 'nombre', 'minimum': 0},  # ACAL132
        'bifacial_mismatch_arriere_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'seuil_derivation_acces': {'type': 'nombre', 'minimum': 0},  # ACAL132
        'plafond_modules_simules': {'type': 'entier', 'minimum': 1},  # ACAL132
    },
    SECTION_ELECTRIQUE_SOCIETE: {
        'tolerance_polystring_acceptable_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'tolerance_polystring_bloquante_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'seuil_desequilibre_pct': {'type': 'pourcentage', 'minimum': 0, 'maximum': 100},  # ACAL132
        'borne_usuelle_dc_ac': {'type': 'nombre', 'minimum': 0},  # ACAL132
        'seuil_alerte_dc_ac': {'type': 'nombre', 'minimum': 0},  # ACAL132
        'correspondances_nomenclature': {'type': 'table'},  # ACAL132
        'regle_bom_structure': {'type': 'table'},  # ACAL132
        'cos_phi_par_defaut': {'type': 'nombre', 'minimum': 0, 'maximum': 1},  # ACAL132
        'seuil_bas_dc_ac': {'type': 'nombre', 'minimum': 0},  # ACAL132
    },
}


def type_de_cle(section, cle):
    """ACAL132 — ``{'type', 'minimum'?, 'maximum'?, 'valeurs'?}`` de ``cle``.

    Lecture PURE. Une clé du registre sans type déclaré est une faute de
    l'ajout (la garde ``tests/test_acal_reglages_types.py`` l'interdit).
    """
    return dict(TYPES_CLES.get(section, {}).get(cle) or {})
