"""Lectures servies au générateur et au moteur (SPL86, scission de
`selectors.py`) : factures, villes, profil site, profil d'activité,
occupation, équipements, kWh, entrées pompage et C&I.

Déplacement pur ; `apps.crm.selectors` ré-exporte chaque nom (frontière
inter-apps). N'importe jamais `.selectors` au niveau module.

Note : les appels internes à `lead_du_devis` restent dans ce module ; il
n'est jamais patché par les tests.
"""
from .clients_selectors import (
    get_latest_lead_for_client,
)


def lead_du_devis(devis):
    """QJR585 — LE résolveur unique « quel lead lit ce devis ».

    Le lead lié au devis, sinon le lead le plus récent de son client (borné
    société, :func:`get_latest_lead_for_client`), sinon ``None``. Tous les
    lecteurs « lead d'un devis » (factures, conso, ville/GPS, profil
    d'activité, occupation, équipements, provenance, phase, transport)
    passent par lui : un devis client-sans-lead n'est plus dimensionné sur les
    factures d'un lead mais sans sa ville, son GPS ni ses équipements.
    ``attribution_comparaison_devis`` reste volontairement strict (devis.lead).
    """
    lead = getattr(devis, 'lead', None)
    if lead is not None:
        return lead
    company_id = getattr(devis, 'company_id', None)
    if not company_id:
        return None
    return get_latest_lead_for_client(
        company_id, getattr(devis, 'client_id', None))


def ville_effective(lead):
    """QJR586 (contrat QJR506 ``lead_ville_effective.json``) — LA « ville de
    calcul » d'un lead : la ville ERP de RATTACHEMENT (``ville_reference``,
    choisie pour un douar hors gazetier, VREF) prime, sinon la ville tapée.
    Chaîne nettoyée, ``''`` quand les deux sont vides — jamais ``None``.

    Moteur (entrées, empreinte), PDF, transport, distributeur déduit,
    réalisation comparable et écran la lisent tous ICI : un douar rattaché
    sans GPS n'est plus refusé par le devis automatique alors que le PDF le
    chiffre."""
    if lead is None:
        return ''
    return ((getattr(lead, 'ville_reference', '') or '').strip()
            or (getattr(lead, 'ville', '') or '').strip())


def _srm_deduite(ville):
    """CAD167 — la SRM régionale de cette ville, ou ``None``. Ne lève jamais."""
    try:
        from .srm_regions import srm_depuis_ville
        return srm_depuis_ville(ville)
    except Exception:  # noqa: BLE001 — une déduction ratée n'arrête rien
        return None


def lead_bills_for_devis(devis):
    """Factures électriques RÉELLES (MAD/mois) du lead d'un devis, ou None.

    Point d'entrée cross-app LECTURE SEULE pour que ``ventes`` lise le profil de
    facture sans importer ``apps.crm.models``. Résolution : le lead lié au devis
    en priorité, sinon le premier lead rattaché au client du devis. Renvoie un
    dict ``{'facture_hiver', 'facture_ete', 'ete_differente'}`` (floats/None +
    bool) quand une facture d'hiver existe, sinon None (la page masque alors le
    graphe de consommation). Aucune donnée fabriquée.

    QJR585 — résolution par :func:`lead_du_devis` (plus de requête inline)."""
    lead = lead_du_devis(devis)
    if lead is None or lead.facture_hiver in (None, ''):
        return None
    return {
        'facture_hiver': float(lead.facture_hiver),
        'facture_ete': (float(lead.facture_ete)
                        if lead.facture_ete not in (None, '') else None),
        'ete_differente': bool(lead.ete_differente),
        # QX7d — distributeur pour convertir MAD→kWh par le barème réel
        # progressif-puis-sélectif (mêmes tranches que le chemin ROI), pas un
        # prix plat.
        # CAD167 — quand la fiche ne porte AUCUN distributeur, la SRM se
        # DÉDUIT de la ville (décision fondateur du 21/09/2026 : on ne la
        # demande plus). Ville inconnue de la table ⇒ toujours None : on
        # n'invente pas un rattachement régional. La valeur ne change aucun
        # prix — le barème est national.
        # QJR586 — la SRM se déduit de la ville de CALCUL du lead.
        'distributeur': (lead.distributeur
                         or _srm_deduite(ville_effective(lead) or None)),
    }


# DC12 — profil site/énergie réutilisable par client ─────────────────────────

# Champs du profil que le générateur peut pré-remplir (source unique).
#
# QJR107 / DÉCISION FONDATEUR D7 (29/08/2026) — `orientation`,
# `inclinaison_deg` et `ombrage` (+ `ombrage_notes`) NE SONT PAS DU CODE MORT.
# Une passe de nettoyage les prend facilement pour tels : AUCUN calcul du
# moteur ne les lit — ni le dimensionnement, ni l'étude horaire, ni le PDF.
# C'est VOULU et c'est TRANCHÉ : ils sont CRM-SEULEMENT (score du lead +
# complétude du questionnaire d'appel), et ils ne seront JAMAIS branchés au
# calcul tant que le fondateur n'aura pas fourni les COEFFICIENTS réels
# (perte par orientation, par inclinaison, par ombrage). Les brancher sans
# ces coefficients reviendrait à inventer un facteur de perte — c'est-à-dire
# à inventer un chiffre montré au client, ce que la règle fondateur interdit
# sans exception. NE PAS LES SUPPRIMER, NE PAS LES CÂBLER : les laisser ici.
SITE_PROFILE_FIELDS = (
    'facture_hiver', 'facture_ete', 'ete_differente', 'conso_mensuelle_kwh',
    'tranche_onee', 'raccordement', 'regularisation_8221', 'type_installation',
    'pompe_actuelle_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
    'type_toiture', 'surface_toiture_m2', 'orientation', 'inclinaison_deg',
    'ombrage', 'ombrage_notes', 'gps_lat', 'gps_lng',
)


#: AGR401 — nom de l'ALIAS lecture seule déprécié de ``pompe_actuelle_cv``
#: (ancien nom de colonne), servi tant que le frontend le lit ; AGR424 le
#: retire. Une seule constante pour le sélecteur et les sérialiseurs.
ALIAS_DEPRECIE_CV_ACTUELLE = 'pompe_cv'


def site_profile_for_client(client_id, company=None):
    """DC12 — profil site/énergie réutilisable d'un client, en dict.

    Renvoie les valeurs à pré-remplir dans le générateur (clés =
    ``SITE_PROFILE_FIELDS``), ou None si aucun profil n'existe. Scopé société
    si fournie : un profil d'une autre société n'est jamais renvoyé. Lecture
    seule — utilisé par le générateur de devis (y compris devis SANS lead) pour
    ne plus re-saisir le profil à chaque fois.
    """
    if not client_id:
        return None
    from .models import SiteProfile
    qs = SiteProfile.objects.filter(client_id=client_id)
    if company is not None:
        qs = qs.filter(company=company)
    profile = qs.first()
    if profile is None:
        return None
    profil = {f: getattr(profile, f) for f in SITE_PROFILE_FIELDS}
    # AGR401 — ALIAS DÉPRÉCIÉ (même valeur) tant que les lecteurs frontend du
    # pré-remplissage ne sont pas migrés (AGR126/AGR415/AGR420) ; retiré par
    # AGR424. Ce n'est PAS la puissance du devis : c'est la pompe actuelle.
    profil[ALIAS_DEPRECIE_CV_ACTUELLE] = profil['pompe_actuelle_cv']
    return profil


# AGR404 — `entrees_pompage` : UNE lecture lead → entrées du dimensionnement ──
#
# Contrat partagé : ``contract_samples/lead_pompage.json`` (AGR1), bloc
# ``entrees_pompage`` et ``regles.entrees_pompage.cibles``. C'est la SEULE
# source lue par le moteur agricole serveur (D1) et par l'écran. Chaque entrée
# = {colonne, valeur, provenance, date, cle_etude, chemin} ; ``provenance`` =
# la valeur ``detail`` (client|site_web|mesure_visite|derive) de la forme
# unique {origine, detail, date} d'AGR2 (l'origine y vaut toujours « lead ») ;
# ``cle_etude`` = une clé v2 d'AGR2 ou ``saisies_economie_pompage`` d'AGR3,
# JAMAIS une clé v1. AUCUN défaut nulle part : une colonne vide est listée
# dans ``manquants``, jamais remplacée (ni « tri », ni 20 m, ni « immergée »).

#: colonne → (cle_etude, chemin). L'ordre est l'ordre de service.
ENTREES_POMPAGE_CIBLES = (
    ('niveau_statique_m', 'source', 'source.niveau_statique_m'),
    ('profondeur_forage_m', 'source', 'source.profondeur_forage_m'),
    ('debit_forage_m3h', 'source', 'source.debit_exploitation_m3h'),
    ('autorisation_debit_l_s', 'source', 'source.debit_autorise_m3h'),
    ('autorisation_volume_m3_an', 'source',
     'source.volume_annuel_autorise_m3'),
    ('compteur_eau', 'source', 'source.compteur'),
    ('besoin_eau_m3j', 'besoin', 'besoin.volume_m3_jour'),
    ('pompe_debit_m3h', 'besoin', 'besoin.debit_souhaite_m3h'),
    ('pompe_actuelle_debit_m3h', 'besoin', 'besoin.debit_actuel_m3h'),
    ('pompage_heures_jour', 'besoin', 'besoin.heures_actuelles_jour'),
    ('culture', 'besoin', 'besoin.cultures[0].crop'),
    ('surface_irriguee_ha', 'besoin', 'besoin.cultures[0].surface_ha'),
    ('irrigation_methode', 'besoin', 'besoin.cultures[0].irrigation'),
    ('region_agricole', 'besoin', 'besoin.region'),
    ('pompe_hmt_m', 'hmt_entrees', 'hmt_entrees.saisie_m'),
    ('distance_forage_champ_m', 'distance_champ_m', 'distance_champ_m'),
    ('pompe_actuelle_cv', 'plaque', 'plaque.cv'),
    ('pompe_actuelle_type', 'type_pompe', 'type_pompe'),
    ('pompe_alim_actuelle', 'saisies_economie_pompage',
     'saisies_economie_pompage.energie_actuelle.valeur'),
    ('butane_bouteilles_jour', 'saisies_economie_pompage',
     'saisies_economie_pompage.consommation.quantite'),
    ('carburant_litres_mois', 'saisies_economie_pompage',
     'saisies_economie_pompage.consommation.quantite'),
    ('carburant_prix_unitaire_mad', 'saisies_economie_pompage',
     'saisies_economie_pompage.depense_unitaire_payee.valeur'),
    ('mois_irrigation', 'saisies_economie_pompage',
     'saisies_economie_pompage.mois_irrigation.mois'),
)


#: Colonnes dont la provenance vit dans une colonne ``*_source`` dédiée :
#: colonne → (colonne source, {valeur source → provenance}).
_ENTREES_POMPAGE_SOURCES = {
    'niveau_statique_m': ('niveau_statique_source', {
        'declare': 'client', 'site_web': 'site_web',
        'mesure_visite': 'mesure_visite'}),
    'debit_forage_m3h': ('debit_forage_source', {
        'essai': 'client', 'foreur': 'client', 'client': 'client',
        'mesure_visite': 'mesure_visite'}),
    'besoin_eau_m3j': ('besoin_eau_source', {
        'client': 'client', 'site_web': 'site_web',
        'pompe_actuelle': 'derive'}),
    'pompe_hmt_m': ('pompe_hmt_source', {
        'declaree': 'client', 'site_web': 'site_web'}),
}


#: La pompe ACTUELLE : lue par le moteur seulement en mode « pompe existante
#: conservée » (D-AGR-7) — servie marquée « information ».
_ENTREES_POMPAGE_INFORMATION = ('pompe_actuelle_cv', 'pompe_actuelle_type')


#: Les heures de la pompe ACTUELLE, jamais des heures de pompage solaire.
_LIBELLE_HEURES_ACTUELLES = 'heures de la pompe actuelle'


#: Formule du volume déclaré dérivé (D-AGR-3).
FORMULE_VOLUME_DECLARE = 'pompe_actuelle_debit_m3h × pompage_heures_jour'


def _entree_valeur(valeur):
    """Decimal → nombre JSON (entier quand il l'est) ; le reste tel quel."""
    from decimal import Decimal
    if isinstance(valeur, Decimal):
        return int(valeur) if valeur == valeur.to_integral_value() \
            else float(valeur)
    return valeur


def _entree_vide(valeur):
    return valeur is None or valeur == '' or valeur == []


def entrees_pompage_du_lead(lead):
    """AGR404 — ``{entrees: [...], manquants: [...]}`` (contrat AGR1).

    Lecture SEULE, aucune écriture. UNE requête au plus (l'historique des
    colonnes de pompage, pour dater et dire qui a saisi). La provenance d'une
    colonne sans ``*_source`` : dernière écriture HUMAINE → « client » ; une
    écriture SYSTÈME (ou la valeur de création) d'un lead venu du site →
    « site_web », sinon « client ».
    """
    from decimal import Decimal
    from .models import Lead, LeadActivity

    if lead is None:
        return {'entrees': [], 'manquants': []}
    # Seules les colonnes RENSEIGNÉES ont besoin d'une date : un lead sans
    # aucune donnée de pompage (résidentiel) ne paie AUCUNE requête.
    colonnes = [c for c, _cle, _chemin in ENTREES_POMPAGE_CIBLES
                if not _entree_vide(getattr(lead, c, None))]
    derniere = {}
    if colonnes and getattr(lead, 'pk', None):
        for ligne in (LeadActivity.objects
                      .filter(lead_id=lead.pk, company_id=lead.company_id,
                              kind=LeadActivity.Kind.MODIFICATION,
                              field__in=colonnes)
                      .order_by('created_at', 'pk')
                      .values('field', 'user_id', 'created_at')):
            derniere[ligne['field']] = ligne
    du_site = getattr(lead, 'source', None) == Lead.Source.SITE_WEB
    creation = getattr(lead, 'date_creation', None)

    def _date(colonne):
        if colonne == 'carburant_prix_unitaire_mad' \
                and lead.carburant_prix_declare_le:
            return lead.carburant_prix_declare_le.isoformat()
        ligne = derniere.get(colonne)
        moment = ligne['created_at'] if ligne else creation
        return moment.date().isoformat() if moment else None

    def _provenance(colonne):
        if colonne in _ENTREES_POMPAGE_SOURCES:
            champ_source, table = _ENTREES_POMPAGE_SOURCES[colonne]
            valeur_source = getattr(lead, champ_source, None)
            if valeur_source in table:
                return table[valeur_source]
        ligne = derniere.get(colonne)
        if ligne and ligne['user_id'] is not None:
            return 'client'
        return 'site_web' if du_site else 'client'

    entrees, manquants = [], []
    for colonne, cle_etude, chemin in ENTREES_POMPAGE_CIBLES:
        brute = getattr(lead, colonne, None)
        if colonne == 'pompe_actuelle_type' and brute == 'ne_sait_pas':
            brute = None  # « ne sait pas » ⇒ non transmis (contrat AGR1)
        if _entree_vide(brute):
            manquants.append(colonne)
            continue
        entree = {
            'colonne': colonne,
            'valeur': _entree_valeur(brute),
            'provenance': _provenance(colonne),
            'date': _date(colonne),
            'cle_etude': cle_etude,
            'chemin': chemin,
        }
        if colonne == 'autorisation_debit_l_s':
            # Conversion PHYSIQUE L/s → m³/h (× 3,6), jamais une estimation.
            entree['valeur'] = _entree_valeur(
                (Decimal(str(brute)) * Decimal('3.6')).quantize(
                    Decimal('0.01')))
            entree['conversion'] = 'L/s × 3,6 → m³/h'
        if colonne == 'debit_forage_m3h' and lead.debit_forage_source:
            entree['origine'] = lead.debit_forage_source
        if colonne in _ENTREES_POMPAGE_INFORMATION:
            entree['information'] = True
        if colonne == 'pompage_heures_jour':
            entree['libelle'] = _LIBELLE_HEURES_ACTUELLES
        if colonne == 'butane_bouteilles_jour':
            entree['unite'], entree['periode'] = 'bouteille_12kg', \
                'jour_irrigation'
        if colonne == 'carburant_litres_mois':
            entree['unite'], entree['periode'] = 'litre', 'mois'
        entrees.append(entree)

    # D-AGR-3 — volume déclaré : besoin_eau_m3j, sinon débit ACTUEL × heures
    # ACTUELLES, servi DÉRIVÉ avec sa formule (jamais écrit sur le lead).
    if _entree_vide(lead.besoin_eau_m3j) and lead.pompe_actuelle_debit_m3h \
            and lead.pompage_heures_jour:
        volume = (Decimal(str(lead.pompe_actuelle_debit_m3h))
                  * Decimal(str(lead.pompage_heures_jour))).quantize(
                      Decimal('0.01'))
        entrees.append({
            'colonne': 'besoin_eau_m3j',
            'valeur': _entree_valeur(volume),
            'provenance': 'derive',
            'date': max(filter(None, (_date('pompe_actuelle_debit_m3h'),
                                      _date('pompage_heures_jour'))),
                        default=None),
            'cle_etude': 'besoin',
            'chemin': 'besoin.volume_m3_jour',
            'formule': FORMULE_VOLUME_DECLARE,
        })
    return {'entrees': entrees, 'manquants': manquants}


def entrees_pompage_pour_lead_id(lead_id, company):
    """AGR404 — même lecture, par id, FILTRÉE par société (point d'entrée
    cross-app du moteur agricole : jamais un lead d'une autre société)."""
    from .models import Lead
    if not lead_id or company is None:
        return None
    lead = Lead.objects.filter(pk=lead_id, company=company).first()
    return entrees_pompage_du_lead(lead) if lead is not None else None


# ── CIQ405 — `entrees_ci` : UNE lecture lead → entrées du moteur C&I ─────────
#
# Contrat CIQ1 ``lead_pro.json`` (bloc ``entrees_ci``) : chaque entrée =
# {colonne, valeur, provenance {origine, detail, date} (forme AGR2), cle_etude
# (clé `etude_params` C&I v2, contrat CIQ2), chemin} ; une colonne vide
# n'émet AUCUNE entrée et figure dans ``manquants``. Aucun défaut nulle part :
# la tension a trois états (bt | mt | inconnue), jamais « bt » supposé.
# ``activity_profile`` du site n'est qu'une INFORMATION, jamais une entrée.

#: Provenance d'une colonne qui porte sa ``*_source`` → ``detail`` (AGR2 :
#: client | site_web | facture | mesure_visite | derive).
_CI_DETAIL_SOURCE = {
    'declare': 'client', 'site_web': 'site_web',
    'site_defaut_visible': 'site_web', 'facture': 'facture',
    'contrat': 'facture', 'mesure_visite': 'mesure_visite',
    'calepinage': 'derive', 'lu_sur_facture': 'facture',
    'ocr_confirme': 'facture',
}


_CI_COLONNE_SOURCE = {
    'tension_raccordement': 'tension_source',
    'compteur_puissance_kva': 'puissance_souscrite_source',
    'surface_toiture_m2': 'surface_source',
    'cos_phi': 'cos_phi_source',
}


#: Colonnes servies pour INFORMATION (Q17 : déclarées, jamais un calcul).
_CI_INFORMATIONS = (
    'groupe_electrogene', 'groupe_kva', 'groupe_litres_mois',
    'groupe_depense_mad_mois', 'pv_existant_kwc', 'cos_phi',
    'export_ue_declare',
)


_CI_PHASES = {'monophase': 'mono', 'triphase': 'tri', 'inconnu': 'inconnu'}


_CI_REGISTRES_MT = ('kwh_pointe', 'kwh_pleines', 'kwh_creuses',
                    'puissance_atteinte_kva', 'cos_phi')


def _ci_nombre(brut):
    from decimal import Decimal, InvalidOperation
    if brut is None:
        return None
    try:
        return _entree_valeur(Decimal(str(brut)))
    except (InvalidOperation, ValueError):
        return None


def entrees_ci_du_lead(lead):
    """CIQ405 — ``{entrees, manquants, informations}`` d'un lead commercial
    ou industriel (``None`` ailleurs). Lecture SEULE ; UNE requête au plus
    (l'historique des colonnes renseignées, pour dater et dire qui a saisi).
    C'est la SEULE source lue par le moteur serveur C&I (D-CIQ-0) et par
    l'écran."""
    from .devis_auto import _facture_mad_compte, _releve_rempli
    from .models import Lead, LeadActivity

    if lead is None:
        return None
    segment = getattr(lead, 'type_installation', None)
    if segment not in ('commercial', 'industriel'):
        return None
    commercial = segment == 'commercial'

    colonnes_lues = (
        'releve_conso', 'conso_mensuelle_kwh', 'bill_kwh', 'facture_hiver',
        'tension_raccordement', 'contrat_electricite', 'option_tarifaire_bt',
        'raccordement', 'compteur_puissance_kva',
        'jours_ouverture', 'heure_debut', 'heure_fin', 'regime_equipes',
        'fermeture_mois', 'categorie_commerciale', 'reponses_categorie',
        'secteur_industriel', 'type_surface', 'type_toiture',
        'surface_toiture_m2', 'tva_recuperable') + _CI_INFORMATIONS
    renseignees = [c for c in colonnes_lues
                   if not _entree_vide(getattr(lead, c, None))]
    derniere = {}
    if renseignees and getattr(lead, 'pk', None):
        for ligne in (LeadActivity.objects
                      .filter(lead_id=lead.pk, company_id=lead.company_id,
                              kind=LeadActivity.Kind.MODIFICATION,
                              field__in=renseignees)
                      .order_by('created_at', 'pk')
                      .values('field', 'user_id', 'created_at')):
            derniere[ligne['field']] = ligne
    du_site = getattr(lead, 'source', None) == Lead.Source.SITE_WEB
    creation = getattr(lead, 'date_creation', None)

    def _provenance(colonne, detail=None):
        ligne = derniere.get(colonne)
        moment = ligne['created_at'] if ligne else creation
        if detail is None:
            champ_source = _CI_COLONNE_SOURCE.get(colonne)
            source = getattr(lead, champ_source, None) if champ_source else None
            if source in _CI_DETAIL_SOURCE:
                detail = _CI_DETAIL_SOURCE[source]
            elif ligne and ligne['user_id'] is not None:
                detail = 'client'
            else:
                detail = 'site_web' if du_site else 'client'
        return {'origine': 'lead', 'detail': detail,
                'date': moment.date().isoformat() if moment else None}

    entrees, manquants = [], []

    def _entree(colonne, valeur, cle_etude, chemin, detail=None, **extra):
        entree = {'colonne': colonne, 'valeur': valeur,
                  'provenance': _provenance(colonne, detail),
                  'cle_etude': cle_etude, 'chemin': chemin}
        entree.update(extra)
        entrees.append(entree)

    # 1. Consommation : le relevé prime, puis le kWh mensuel, puis la
    # facture en MAD (convertie par le moteur, jamais ici).
    if _releve_rempli(lead):
        releve = lead.releve_conso
        mois = []
        for ligne in releve.get('mois') or []:
            if _ci_nombre(ligne.get('kwh')) is None:
                continue
            m = {'mois': ligne.get('mois'), 'kwh': _ci_nombre(ligne['kwh'])}
            for registre in _CI_REGISTRES_MT:
                if ligne.get(registre) not in (None, ''):
                    m[registre] = _ci_nombre(ligne[registre])
            mois.append(m)
        _entree('releve_conso', mois, 'consommation',
                'consommation.factures_mad',
                detail=_CI_DETAIL_SOURCE.get(releve.get('source'), 'client'))
    elif not _entree_vide(lead.conso_mensuelle_kwh):
        _entree('conso_mensuelle_kwh', _entree_valeur(lead.conso_mensuelle_kwh),
                'consommation', 'consommation.kwh_mensuels')
    elif not _entree_vide(lead.bill_kwh):
        _entree('bill_kwh', _entree_valeur(lead.bill_kwh), 'consommation',
                'consommation.kwh_mensuels')
    elif not _entree_vide(lead.facture_hiver) and _facture_mad_compte(lead):
        _entree('facture_hiver', _entree_valeur(lead.facture_hiver),
                'consommation', 'consommation.facture_mad',
                source_conso='facture_mad')
    else:
        manquants.append('conso_mensuelle_kwh')

    # 2. Tension : trois états, jamais « bt » par défaut.
    tension = lead.tension_raccordement
    if _entree_vide(tension):
        manquants.append('tension_raccordement')
    else:
        inconnue = (tension == 'ne_sait_pas'
                    or lead.tension_source == 'site_defaut_visible')
        _entree('tension_raccordement', 'inconnue' if inconnue else tension,
                'tension', 'tension')
        if inconnue:
            manquants.append('tension_raccordement')

    # 2 bis. CIQ666 (décision fondateur 08/10/2026) — le CONTRAT
    # d'électricité DÉCLARÉ → ``tarif_declare`` (vocabulaire CIQ222) : le
    # moteur résout la grille ONEE de CE contrat au lieu de refuser
    # (« tarif_omis »). « Ne sait pas » = aucun contrat, jamais un supposé ;
    # le bi-horaire n'est transmis que pour la force motrice. Un site MT sans
    # contrat déclaré n'en manque pas (la MT n'a qu'un Tarif Général).
    contrat = lead.contrat_electricite
    if not _entree_vide(contrat) and contrat != 'ne_sait_pas':
        tarif = {'contrat': contrat}
        if contrat == 'bt_force_motrice' and not _entree_vide(
                lead.option_tarifaire_bt):
            tarif['option_bi_horaire'] = (
                lead.option_tarifaire_bt == 'bi_horaire')
        _entree('contrat_electricite', tarif, 'tarif_declare',
                'tarif_declare')
    elif tension != 'mt':
        manquants.append('contrat_electricite')

    # 3. Phases (BT) et puissance souscrite.
    if not _entree_vide(lead.raccordement) and lead.raccordement in _CI_PHASES:
        _entree('raccordement', _CI_PHASES[lead.raccordement], 'phases',
                'phases')
    elif commercial:
        manquants.append('raccordement')
    if _entree_vide(lead.compteur_puissance_kva):
        manquants.append('compteur_puissance_kva')
    else:
        _entree('compteur_puissance_kva',
                _entree_valeur(lead.compteur_puissance_kva),
                'puissance_souscrite_kva', 'puissance_souscrite_kva')

    # 4. Rythme DÉCLARÉ, passé tel quel.
    if not lead.jours_ouverture:
        manquants.append('jours_ouverture')
    else:
        jours = set(lead.jours_ouverture or [])
        _entree('jours_ouverture', [j in jours for j in range(1, 8)],
                'rythme', 'rythme.jours_ouverts')
    if lead.heure_debut is None or lead.heure_fin is None:
        manquants.extend(c for c in ('heure_debut', 'heure_fin')
                         if getattr(lead, c) is None)
    else:
        _entree('heure_debut', {'ouvre': [[lead.heure_debut, lead.heure_fin]]},
                'rythme', 'rythme.plages')
    if _entree_vide(lead.regime_equipes):
        manquants.append('regime_equipes')
    else:
        _entree('regime_equipes', lead.regime_equipes, 'rythme',
                'rythme.equipes')
    if lead.fermeture_mois is None:
        manquants.append('fermeture_mois')
    else:
        _entree('fermeture_mois', list(lead.fermeture_mois), 'rythme',
                'rythme.fermetures')
    if commercial:
        if _entree_vide(lead.categorie_commerciale):
            manquants.append('categorie_commerciale')
        else:
            _entree('categorie_commerciale', lead.categorie_commerciale,
                    'rythme', 'rythme.categorie_commerciale')
        if lead.reponses_categorie:
            _entree('reponses_categorie', dict(lead.reponses_categorie),
                    'rythme', 'rythme.reponses_categorie')
    else:
        if _entree_vide(lead.secteur_industriel):
            manquants.append('secteur_industriel')
        else:
            _entree('secteur_industriel', lead.secteur_industriel, 'rythme',
                    'rythme.secteur_industriel')

    # 5. Toit / surface, avec leur source (le plafond est calculé par D1).
    for colonne, chemin in (('type_surface', 'toit.type_surface'),
                            ('type_toiture', 'toit.type_toiture'),
                            ('surface_toiture_m2', 'toit.surface_utile_m2')):
        valeur = getattr(lead, colonne)
        if _entree_vide(valeur):
            manquants.append(colonne)
        else:
            # La surface est un NOMBRE au contrat (`lead_pro.json`), même
            # quand l'instance porte encore la chaîne décimale reçue par l'API
            # (« 650.00 ») et pas le Decimal relu de la base.
            _entree(colonne,
                    (_ci_nombre(valeur) if colonne == 'surface_toiture_m2'
                     else _entree_valeur(valeur)), 'toit', chemin)

    # 6. TVA récupérable (forme posée par `economie_ci.json`, CIQ3).
    if _entree_vide(lead.tva_recuperable):
        manquants.append('tva_recuperable')
    else:
        _entree('tva_recuperable', lead.tva_recuperable, 'tva_recuperable',
                'tva_recuperable')

    # Informations : jamais une entrée de calcul.
    informations = []
    for colonne in _CI_INFORMATIONS:
        if colonne == 'cos_phi' and commercial:
            continue
        valeur = getattr(lead, colonne, None)
        if _entree_vide(valeur):
            continue
        informations.append({'colonne': colonne,
                             'valeur': _entree_valeur(valeur),
                             'provenance': _provenance(colonne)})
    profil = (lead.web_questionnaire or {}).get('activity_profile') \
        if isinstance(lead.web_questionnaire, dict) else None
    if profil:
        informations.append({
            'colonne': 'activity_profile', 'valeur': profil,
            'provenance': {'origine': 'lead', 'detail': 'site_web',
                           'date': (creation.date().isoformat()
                                    if creation else None)}})
    return {'entrees': entrees, 'manquants': manquants,
            'informations': informations}


def entrees_ci_pour_lead_id(lead_id, company):
    """CIQ405 — même lecture, par id, FILTRÉE par société (point d'entrée
    cross-app du moteur C&I : jamais un lead d'une autre société)."""
    from .models import Lead
    if not lead_id or company is None:
        return None
    lead = Lead.objects.filter(pk=lead_id, company=company).first()
    return entrees_ci_du_lead(lead) if lead is not None else None


def releve_declare_ci(lead):
    """CIQ606 — ce que le lead DÉCLARE des cinq faits qu'une visite C&I
    confronte au terrain : ``{niveau_tension, puissance_souscrite_kva,
    type_toiture, surface_utile, statut_occupation}`` (``None`` = non
    déclaré). Lecture SEULE, aucune requête, aucun défaut fabriqué.

    ``niveau_tension`` suit le vocabulaire de la visite (``bt`` | ``mt`` |
    ``inconnu``) : « ne sait pas » et une tension simplement SUPPOSÉE par le
    site (``site_defaut_visible``) valent ``inconnu`` — jamais une déclaration.
    ``type_toiture`` reste en codes ``Lead.TypeToiture``."""
    if lead is None:
        return {'niveau_tension': None, 'puissance_souscrite_kva': None,
                'type_toiture': None, 'surface_utile': None,
                'statut_occupation': None}
    tension = lead.tension_raccordement
    if _entree_vide(tension):
        tension = None
    elif (tension == 'ne_sait_pas'
          or lead.tension_source == 'site_defaut_visible'):
        tension = 'inconnu'

    def _nombre(valeur):
        valeur = _entree_valeur(valeur)
        return None if _entree_vide(valeur) else float(valeur)

    return {
        'niveau_tension': tension,
        'puissance_souscrite_kva': _nombre(lead.compteur_puissance_kva),
        'type_toiture': (None if _entree_vide(lead.type_toiture)
                         else lead.type_toiture),
        'surface_utile': _nombre(lead.surface_toiture_m2),
        'statut_occupation': (None if _entree_vide(lead.ownership)
                              else lead.ownership),
    }


def site_location_for_devis(devis):
    """DC13 — localisation du chantier à créer depuis un devis.

    Renvoie ``{'site_adresse', 'site_ville', 'gps_lat', 'gps_lng'}``. Quand le
    devis porte un lead, on reprend ses valeurs (comportement historique).
    Pour un devis SANS lead, ``site_adresse`` retombe sur ``client.adresse`` au
    lieu de rester vide (le client n'a ni ville ni GPS → restent None).
    Point d'entrée cross-app LECTURE SEULE pour que ``installations`` n'importe
    pas ``apps.crm.models`` ; ``create_installation_from_devis`` consomme ce
    seul accesseur. Aucune donnée fabriquée.

    QJR585 — le lead vient de :func:`lead_du_devis` (repli sur le lead le plus
    récent du client) : sa ville et son GPS suivent ses factures.
    """
    lead = lead_du_devis(devis)
    if lead is not None:
        return {
            'site_adresse': lead.adresse,
            # QJR586 — la ville de CALCUL (rattachement VREF prioritaire).
            'site_ville': ville_effective(lead) or None,
            'gps_lat': lead.gps_lat,
            'gps_lng': lead.gps_lng,
        }
    client = getattr(devis, 'client', None)
    return {
        'site_adresse': getattr(client, 'adresse', None) if client else None,
        'site_ville': None,
        'gps_lat': None,
        'gps_lng': None,
    }


#: Valeurs admises pour le profil d'activité PRO, telles que le webhook web les
#: valide déjà à l'entrée (``apps/crm/webhooks.py`` — QW2). Toute autre valeur
#: est traitée comme absente : on ne devine jamais un profil d'occupation.
PROFILS_ACTIVITE = ('day', 'day_evening', 'continuous')


def profil_activite_pour_devis(devis):
    """Profil d'activité PRO du lead d'un devis, ou ``None``.

    Point d'entrée cross-app LECTURE SEULE (``apps.ventes`` n'importe jamais
    ``apps.crm.models``). Renvoie la valeur de
    ``Lead.web_questionnaire['activity_profile']`` — le SEUL signal
    d'occupation en journée réellement câblé aujourd'hui, et seulement en mode
    PRO — quand elle fait partie de :data:`PROFILS_ACTIVITE`. Aucun lead, pas
    de questionnaire, valeur inconnue ⇒ ``None`` : l'appelant applique alors
    son propre défaut, jamais une valeur inventée ici.
    QJR585 — lead résolu par :func:`lead_du_devis`.
    """
    lead = lead_du_devis(devis)
    if lead is None:
        return None
    questionnaire = getattr(lead, 'web_questionnaire', None)
    if not isinstance(questionnaire, dict):
        return None
    valeur = questionnaire.get('activity_profile')
    return valeur if valeur in PROFILS_ACTIVITE else None


def occupation_jour_pour_devis(devis):
    """L4 (extension fondateur, 21/08/2026) — présence en journée déclarée
    au téléphone (``crm.Lead.occupation_jour``), ou ``None``.

    Point d'entrée cross-app LECTURE SEULE : ``apps/ventes/courbes_journalieres.py
    _occupation`` la consulte AVANT son défaut fondateur habituel — quand le
    commercial a posé la question, la réponse RÉELLE du lead prime. ``None``
    (lead absent, ou question pas encore posée) laisse l'appelant retomber
    sur son comportement actuel, inchangé.
    QJR585 — lead résolu par :func:`lead_du_devis`.
    """
    lead = lead_du_devis(devis)
    if lead is None:
        return None
    valeur = getattr(lead, 'occupation_jour', None)
    return valeur if valeur in ('present', 'absent', 'partiel') else None


def equipements_pour_lead(lead):
    """QJR9 — équipements électriques d'un LEAD, ou ``{}`` (lead absent).

    Point d'entrée cross-app LECTURE SEULE, jumeau de
    :func:`equipements_pour_devis` pour les chemins qui n'ont PAS encore de
    devis persisté (devis automatique, tunnel) : jusqu'ici ces chemins
    recomposaient la couche équipement à la main sur SIX clés, et les huit
    grandeurs L-BACK/L-BACK2 (chauffe-eau kW/créneau, chargeur VE kW/créneau,
    clim kW/créneau, piscine heures/créneau) plus ``chauffe_eau_electrique``
    n'atteignaient jamais le moteur. Il n'y a donc plus qu'UNE liste de champs
    lue, ici, pour les deux chemins.

    Valeurs BRUTES du lead — script d'appel du commercial (piscine/VE/clim/
    chauffe-eau), DISTINCT de ``futures_charges`` (case du questionnaire web,
    sans paramètre). Chaque valeur est ``None`` quand la question n'a pas été
    posée : aucune valeur n'est devinée ici, l'appelant décide de son propre
    repli (généralement : omettre la couche).
    """
    if lead is None:
        return {}
    return {
        'piscine': lead.equip_piscine,
        'piscine_pompe_kw': lead.equip_piscine_pompe_kw,
        'voiture_electrique': lead.equip_voiture_electrique,
        've_km_semaine': lead.equip_ve_km_semaine,
        'clim': lead.equip_clim,
        'clim_pieces': lead.equip_clim_pieces,
        'chauffe_eau_electrique': lead.equip_chauffe_eau_electrique,
        # L-BACK (24/08/2026) — grandeurs complémentaires (voir models.py) :
        # kW/créneau chauffe-eau, kW/créneau chargeur VE, kW clim déclarée,
        # heures/jour piscine. Mêmes None-par-défaut ; l'appelant décide.
        'chauffe_eau_kw': lead.equip_chauffe_eau_kw,
        'chauffe_eau_creneau': lead.equip_chauffe_eau_creneau,
        've_chargeur_kw': lead.equip_ve_chargeur_kw,
        've_creneau': lead.equip_ve_creneau,
        'clim_kw': lead.equip_clim_kw,
        'piscine_heures_jour': lead.equip_piscine_heures_jour,
        # L-BACK2 (24/08/2026) — créneaux clim/piscine (enrichissement d'une
        # couche déjà active, jamais une paire requise). Mêmes None-par-défaut.
        'clim_creneau': lead.equip_clim_creneau,
        'piscine_creneau': lead.equip_piscine_creneau,
        # CAD169 — « déjà là » ou « seulement prévu » : une voiture PRÉVUE est
        # comptée des deux côtés, mais le devis et la proposition portent
        # alors l'étiquette « avec votre future voiture ». Sans ce champ ici,
        # le moteur ne pourrait pas la poser — et le chiffre mentirait.
        've_statut': getattr(lead, 'equip_ve_statut', None),
    }


def equipements_pour_devis(devis):
    """L4 (21/08/2026) — équipements électriques du lead d'un devis, ou ``{}``.

    Point d'entrée cross-app LECTURE SEULE (``apps.ventes`` n'importe jamais
    ``apps.crm.models``) : ``apps/ventes/courbes_journalieres.py`` compose ses
    couches d'équipement à partir de ce dict.

    QJR9 — sortie INCHANGÉE : simple application de
    :func:`equipements_pour_lead` au lead du devis, pour que le chemin « devis
    persisté » et le chemin « lead seul » (devis automatique / tunnel) lisent
    exactement les mêmes champs.
    """
    return equipements_pour_lead(lead_du_devis(devis))


def lead_devis_ids_by_id(company, lead_id):
    """NTMKT18 — ids (str) des devis liés à un lead, par id OPAQUE (lecture
    seule) — pour un appelant cross-app (``marketing``) qui ne peut importer
    ``Lead`` et ne dispose que d'un ``lead_id`` (jamais d'objet ``Lead``).
    Renvoie ``[]`` si le lead n'existe pas ou n'a aucun devis."""
    from .models import Lead

    lead = Lead.objects.filter(company=company, pk=lead_id).only('id').first()
    if lead is None:
        return []
    return [str(d.id) for d in lead.devis.all()]


# ── CAD-M ── CAD166 — LES kWh DÉCLARÉS, JUSQU'AU MOTEUR
#
# Le moteur horaire sait lire une consommation en kWh depuis toujours ; il ne
# la RECEVAIT simplement pas du lead, et repartait donc des montants en
# dirhams inversés au barème même quand le client avait donné ses kWh.
# Décision fondateur du 21/09/2026 : les kWh saisis passent en PRIORITÉ 1.
#
# Point d'entrée cross-app LECTURE SEULE, DISTINCT de
# ``lead_bills_for_devis`` : celui-ci n'existe que si une facture d'hiver
# existe, alors que le cas visé est justement le dossier qui n'a QUE des kWh.
def _kwh_positif(valeur):
    """``valeur`` en ``float`` > 0, sinon ``None`` (vide, illisible, ≤ 0)."""
    if valeur in (None, ''):
        return None
    try:
        valeur = float(valeur)
    except (TypeError, ValueError):
        return None
    return valeur if valeur > 0 else None


#: QJR662 — segments du lead pour lesquels le kWh mensuel DÉCLARÉ sur le site
#: (``bill_kwh``) sert de repli au moteur. Jamais le résidentiel.
SEGMENTS_REPLI_KWH_SITE = ('industriel', 'commercial')


def conso_mensuelle_kwh_pour_devis(devis):
    """Consommation mensuelle (kWh) du lead d'un devis, ou ``None``.

    ``crm.Lead.conso_mensuelle_kwh`` est LE champ éditable (saisi par la
    commerciale, écrit par l'OCR de facture) et il PRIME toujours.
    QJR662 (décision fondateur 01/10/2026, amende CAD166) : pour un lead
    INDUSTRIEL ou COMMERCIAL dont ce champ est vide, le moteur se replie sur
    ``bill_kwh`` — le kWh mensuel déclaré sur le site, lu en LECTURE SEULE
    (sa provenance « saisi sur le site le … » reste celle de
    :func:`provenance_site`). Jamais pour le résidentiel ni l'agricole ; les
    deux colonnes ne fusionnent pas (aucune migration, aucune écriture).
    Même résolution de lead que le reste du module (le lead du devis, sinon le
    plus récent du client), même bornage société. Aucune donnée fabriquée :
    absente ⇒ ``None``. QJR585 — :func:`lead_du_devis`."""
    lead = lead_du_devis(devis)
    if lead is None:
        return None
    valeur = _kwh_positif(getattr(lead, 'conso_mensuelle_kwh', None))
    if valeur is not None:
        return valeur
    if getattr(lead, 'type_installation', None) in SEGMENTS_REPLI_KWH_SITE:
        return _kwh_positif(getattr(lead, 'bill_kwh', None))
    return None
