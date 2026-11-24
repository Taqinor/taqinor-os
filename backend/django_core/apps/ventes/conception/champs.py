"""ADEV130 — les colonnes du lead qui sont des ENTRÉES du moteur unique.

Une colonne est ici si et seulement si l'adaptateur de son marché la LIT :
``domain/entrees.py::entrees_depuis_lead`` (résidentiel),
``domain/etude_ci.py::resoudre_entrees`` (commercial, industriel) et
``domain/pompage.py::resoudre_entrees`` (agricole), sélecteurs du CRM compris
(``equipements_pour_lead``, ``entrees_ci_du_lead``, ``entrees_pompage_du_lead``,
``ville_effective``). La liste se DÉDUIT des adaptateurs, elle ne les remplace
pas : ``apps/ventes/tests/test_conception_lead.py`` espionne leurs lectures sur
un lead renseigné et rougit dès qu'une colonne lue manque ici. Lecteurs à
venir : l'émission de ``lead_entrees_modifiees`` (ALEA68), la relance (ADEV139),
le filet d'empreinte (ADEV140).

Deux ajouts assumés, lus hors du chemin que l'espion parcourt :
``type_installation`` (le marché choisit l'adaptateur) et ``ville`` (lue par
``ville_effective`` seulement quand ``ville_reference`` est vide). Les colonnes
``*_source`` sont des entrées : ``tension_source`` change la tension retenue.

ADEV159 (24/11/2026) — la liste couvre aussi ce que la CRÉATION du devis
automatique lit hors des adaptateurs (espion sur un ``build_devis_auto``
complet par marché, lecteurs identifiés par la pile) : taille et batterie
souhaitées, structure épinglée et préférée, tracé du toit (``roof_outline``),
distributeur (bloc horaire), raccordement de la pompe (alimentation) et
provenance des mesures du forage. Seuls la résolution du client et le tampon de
provenance du devis en sont exclus : ils ne calculent rien.
"""

#: Souhaits du lead que la création applique (taille souveraine, options).
_SOUHAITS = ('taille_souhaitee_kwc', 'batterie_souhaitee')

_LIEU = ('type_installation', 'ville', 'ville_reference', 'gps_lat', 'gps_lng')

_RESIDENTIEL = _LIEU + (
    'facture_hiver', 'facture_ete', 'ete_differente', 'conso_mensuelle_kwh',
    'occupation_jour', 'raccordement', 'distributeur', 'roof_outline',
    'structure_pref', 'structure_produit',
    # Équipements (``crm.selectors.equipements_pour_lead``).
    'equip_piscine', 'equip_piscine_pompe_kw', 'equip_piscine_heures_jour',
    'equip_piscine_creneau', 'equip_voiture_electrique', 'equip_ve_km_semaine',
    'equip_ve_chargeur_kw', 'equip_ve_creneau', 'equip_ve_statut', 'equip_clim',
    'equip_clim_pieces', 'equip_clim_kw', 'equip_clim_creneau',
    'equip_chauffe_eau_electrique', 'equip_chauffe_eau_kw',
    'equip_chauffe_eau_creneau',
) + _SOUHAITS

_CI = _LIEU + (
    # Consommation et contrat.
    'facture_hiver', 'conso_mensuelle_kwh', 'bill_kwh', 'releve_conso',
    'tension_raccordement', 'tension_source', 'contrat_electricite',
    'option_tarifaire_bt', 'raccordement', 'compteur_puissance_kva',
    'puissance_souscrite_source', 'tva_recuperable',
    # Rythme d'activité.
    'jours_ouverture', 'heure_debut', 'heure_fin', 'regime_equipes',
    'fermeture_mois', 'categorie_commerciale', 'reponses_categorie',
    'equipements_hors_horaires', 'secteur_industriel', 'web_questionnaire',
    # Toit déclaré.
    'type_surface', 'type_toiture', 'surface_toiture_m2', 'surface_source',
    'inclinaison_deg', 'orientation',
    # Informations (alertes internes : groupe, PV existant, cos φ, export).
    'groupe_electrogene', 'groupe_kva', 'groupe_litres_mois',
    'groupe_depense_mad_mois', 'pv_existant_kwc', 'cos_phi', 'export_ue_declare',
    # Tracé du toit (bornes de taille, ``dimensionnement_devis``).
    'roof_outline',
) + _SOUHAITS

_AGRICOLE = _LIEU + (
    # Point d'eau, besoin et HMT.
    'mode_pompe', 'pompe_hmt_m', 'pompe_hmt_source', 'pompe_debit_m3h',
    'besoin_eau_m3j', 'besoin_eau_source', 'niveau_statique_m',
    'niveau_statique_source', 'debit_forage_source',
    # Alimentation de la pompe déduite du raccordement (garde de la création).
    'raccordement',
    'profondeur_forage_m', 'debit_forage_m3h', 'autorisation_debit_l_s',
    'autorisation_volume_m3_an', 'compteur_eau', 'distance_forage_champ_m',
    'culture', 'surface_irriguee_ha', 'irrigation_methode', 'region_agricole',
    'pompage_heures_jour', 'mois_irrigation', 'jours_irrigation_semaine',
    # Pompe actuelle (plaque).
    'pompe_actuelle_kw', 'pompe_actuelle_cv', 'pompe_actuelle_tension_v',
    'pompe_actuelle_phases', 'pompe_actuelle_type', 'pompe_actuelle_debit_m3h',
    'pompe_alim_actuelle',
    # Économie du pompage (contrat AGR3).
    'butane_bouteilles_jour', 'carburant_litres_mois',
    'carburant_prix_unitaire_mad', 'depense_electricite_pompe_mad_mois',
    'depense_electricite_pompe_part_fixe_mad_mois',
)

#: Colonnes du lead lues par un adaptateur par marché.
CHAMPS_ENTREES = {
    'residentiel': _RESIDENTIEL,
    'commercial': _CI,
    'industriel': _CI,
    'agricole': _AGRICOLE,
}

#: Lues par les adaptateurs sans jamais changer un chiffre : l'identité (clé,
#: société) et la PROVENANCE d'une entrée (date de création du lead, lead venu
#: du site) — elles ne relancent jamais le moteur.
CHAMPS_LUS_HORS_ENTREES = ('id', 'company', 'date_creation', 'source')


def champs_pour(marche):
    """Les colonnes d'entrée du ``marche`` ; ``KeyError`` pour un marché inconnu."""
    return CHAMPS_ENTREES[marche]
