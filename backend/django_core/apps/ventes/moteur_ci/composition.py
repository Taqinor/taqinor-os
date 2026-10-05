"""CIQ115 — composition C&I SERVEUR (BOQ) : fin du kit résidentiel mis à
l'échelle.

``composer_ci(kwc, catalogue, *, onduleurs, entrees, forfaits)`` rend la forme
``composition`` de ``contract_samples/etude_ci_preview.json`` :
``{lignes, onduleurs, prix_a_renseigner, incomplet, options, alertes,
hypotheses}`` — chaque ligne ``{role, produit, designation, quantite, unite,
prix_connu, motif, a_confirmer_visite}``.

* Panneaux : module retenu (fiche complète), nombre = plafond(kWc ÷ Wc).
* Onduleurs : la combinaison de CIQ111 (``onduleurs`` = son résultat).
* Câble DC : Σ chaînes × longueur DÉCLARÉE ; protections et câble AC par
  onduleur par ``core.electrique`` (``courant_emploi_ac``,
  ``calibre_disjoncteur``, ``proposer_section`` sur le barème étendu
  CIQ139). Hors barème ⇒ « section/calibre à dimensionner par le bureau
  d'études » (``a_confirmer_visite``), JAMAIS une section extrapolée ;
  longueur non déclarée ⇒ ligne ``a_confirmer_visite`` sans quantité.
* Chaque organe est apparié au catalogue par son rôle C&I ET sa grandeur de
  fiche (calibre / pôles / section / type de pose — posés par CIQ103), sinon
  ligne « prix à renseigner » nommée (patron PV47).
* Structure : rôle ``structure_ci`` du ``type_pose`` du toit, jamais le
  bouton acier/alu résidentiel.
* Comptage / limitation d'injection : sans revente (BT toujours, MT sans
  revente choisie), un dispositif par POINT DE RACCORDEMENT déclaré, autant
  de compteurs/contrôleurs que l'impose ``lim_onduleurs_max`` ; fiche muette
  ⇒ « à confirmer fournisseur ». Logger dès 2 onduleurs, borné par
  ``log_onduleurs_max`` quand publié.
* Cellule MT seulement si ``besoin_cellule_mt`` est déclaré ; site MT sans ce
  fait ⇒ alerte « poste de livraison à confirmer à la visite », aucune ligne.
* Prestations : une ligne par prestation des forfaits C&I de la société
  (CIQ105 : fixe + par kWc + par panneau) ; non réglée ⇒ « prix à
  renseigner » ; AUCUN barème résidentiel (L-FORFAIT intouché).
* Option O&M NOMMÉE toujours proposée ; option batterie seulement si un
  ``batterie_ci`` est au catalogue ET un besoin déclaré — « valeur non
  chiffrée ». Aucun onduleur hybride ni batterie COMPOSÉS.
* ``incomplet = vrai`` dès qu'une ligne n'a pas de prix. Jamais ``prix_achat``
  ni marge.

PUR : aucun Django, aucune base, aucun ``apps.*`` (garde AST du test).
"""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation

from core.electrique.cables import (
    AMPACITE_U1000R2V_MONO, AMPACITE_U1000R2V_TRI, CHUTE_CIBLE_AC_PCT,
    bareme_pour, proposer_section,
)
from core.electrique.protections import calibre_disjoncteur, courant_emploi_ac
from core.pricing_paliers import MODE_VOLUME, calculer_prix_paliers

#: Prestations C&I réglées par société (``CompanyProfile.forfaits_ci``).
PRESTATIONS_CI = (
    ('etudes_ingenierie', 'Études et ingénierie C&I'),
    ('pose_structure', 'Pose de la structure C&I'),
    ('pose_modules', 'Pose des modules C&I'),
    ('raccordement_ac', 'Raccordement AC C&I'),
    ('mise_en_service', 'Mise en service C&I'),
    ('dossier_raccordement', 'Dossier de raccordement C&I'),
    ('levage_acces', 'Levage et accès C&I'),
    ('transport_ci', 'Transport C&I'),
)

MOTIF_PRIX = 'article C&I « prix à renseigner »'
MOTIF_FOURNISSEUR = 'à confirmer fournisseur (fiche muette)'
MOTIF_BUREAU = ("section/calibre à dimensionner par le bureau d'études "
                "(hors barème relevé)")
MOTIF_LONGUEUR = 'longueur non déclarée : à relever à la visite'


def _d(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        x = Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return None
    return x if x.is_finite() else None


def _f(valeur):
    try:
        x = float(valeur)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _alerte(code, message, niveau='alerte', champ='composition'):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': True}


def _du_role(catalogue, role, filtre=None):
    """Le premier article ÉLIGIBLE du rôle (C&I ou de devis) qui passe le
    filtre de fiche — ordre déterministe (id)."""
    for p in sorted(catalogue, key=lambda x: (x.get('id') or 0)):
        if p.get('eligible_ci') is False:
            continue
        if role not in (p.get('role_ci'), p.get('role_devis')):
            continue
        if filtre is not None and not filtre(p.get('fiche') or {}, p):
            continue
        return p
    return None


def _ligne(role, article, designation, quantite, unite, *, motif=None,
           a_confirmer=False):
    prix_connu = bool(article and article.get('prix_connu'))
    if article is None and motif is None:
        motif = MOTIF_PRIX
    elif article is not None and not prix_connu and motif is None:
        motif = MOTIF_PRIX
    ligne = {
        'role': role,
        'produit': article.get('id') if article else None,
        'designation': (article.get('nom') if article else None)
        or designation,
        'quantite': quantite,
        'unite': unite,
        'prix_connu': prix_connu,
        'motif': motif,
        'a_confirmer_visite': bool(a_confirmer),
    }
    if article is not None and article.get('prix_vente_ht') is not None:
        ligne['prix_unitaire_ht'] = str(article['prix_vente_ht'])
    _appliquer_palier(ligne, article)
    return ligne


def _appliquer_palier(ligne, article):
    """CIQ123 — prix de VENTE TTC du palier atteint par la quantité (moteur
    générique ``core.pricing_paliers``, mode volume), dit dans la ligne.
    Paliers vides ⇒ ligne inchangée (prix catalogue). ``delai_appro_jours``
    (article « sur commande ») est servi à côté."""
    if not article:
        return
    if article.get('delai_appro_jours') is not None:
        ligne['delai_appro_jours'] = article['delai_appro_jours']
    paliers = article.get('paliers_prix_vente') or []
    quantite = _d(ligne.get('quantite'))
    if not paliers or quantite is None or quantite <= 0:
        return
    total = calculer_prix_paliers(
        quantite, [{'seuil_min': p.get('seuil_min'),
                    'seuil_max': p.get('seuil_max'),
                    'prix_unitaire': p.get('prix_vente_ttc')}
                   for p in paliers], MODE_VOLUME)
    if total is None:
        return
    atteint = None
    for p in sorted(paliers, key=lambda x: _d(x.get('seuil_min')) or 0):
        if quantite >= (_d(p.get('seuil_min')) or 0):
            atteint = p
    ligne['prix_unitaire_ttc'] = str(
        (total / quantite).quantize(Decimal('0.01')))
    ligne['palier'] = {'seuil_min': atteint.get('seuil_min'),
                       'seuil_max': atteint.get('seuil_max'),
                       'mention': 'prix palier dès %s unités' % (
                           atteint.get('seuil_min'),)} if atteint else None
    ligne['prix_connu'] = True
    if ligne.get('motif') == MOTIF_PRIX:
        ligne['motif'] = None


def _par_id(catalogue):
    return {p.get('id'): p for p in catalogue}


def _onduleurs_unitaires(onduleurs):
    """``[(produit, kw_ac, triphase?)]`` — un élément PAR appareil."""
    sortie = []
    for item in (onduleurs or {}).get('combinaison') or []:
        for _ in range(int(item.get('quantite') or 0)):
            sortie.append(item)
    return sortie


def _protection_et_cable_ac(catalogue, ondu, entrees, lignes, alertes,
                            hypotheses):
    kw = _f(ondu.get('kw_ac')) or 0.0
    triphase = entrees.get('phase') != 'mono'
    phases = 3 if triphase else 1
    ib = courant_emploi_ac(kw, phases)
    calibre = calibre_disjoncteur(ib)
    poles = 4 if triphase else 2
    disj = _du_role(catalogue, 'protection_ac', lambda f, _p: (
        f.get('prot_type') == 'disjoncteur'
        and _f(f.get('prot_calibre_a')) == calibre
        and f.get('prot_poles') in (None, poles)))
    nom = ondu.get('nom') or 'onduleur'
    if ib > calibre + 1e-9:
        lignes.append(_ligne('protection_ac', None,
                             'Protection AC sortie %s' % nom, 1, 'u',
                             motif=MOTIF_BUREAU, a_confirmer=True))
    else:
        lignes.append(_ligne(
            'protection_ac', disj,
            'Disjoncteur AC %g A sortie %s' % (calibre, nom), 1, 'u'))
    longueur = _f(entrees.get('longueur_ac_m'))
    if longueur is None or longueur <= 0:
        lignes.append(_ligne('cable_ac', None,
                             'Câble AC %s → TGBT' % nom, None, 'm',
                             motif=MOTIF_LONGUEUR, a_confirmer=True))
        return
    base = AMPACITE_U1000R2V_TRI if triphase else AMPACITE_U1000R2V_MONO
    bareme = bareme_pour(base, ib, calibre)
    proposee = proposer_section(
        ib, longueur, 400.0 if triphase else 230.0, CHUTE_CIBLE_AC_PCT,
        bareme=bareme, coefficient=math.sqrt(3.0) if triphase else 2.0,
        calibre_in_a=calibre)
    if proposee.thermique_hors_bareme or proposee.hors_bareme:
        lignes.append(_ligne('cable_ac', None,
                             'Câble AC %s → TGBT' % nom, longueur, 'm',
                             motif=MOTIF_BUREAU, a_confirmer=True))
        return
    section = float(proposee.section_mm2)
    cable = _du_role(catalogue, 'cable_ac', lambda f, _p: (
        f.get('cable_cote') in ('ac', None, '')
        and _f(f.get('cable_section_mm2')) == section))
    lignes.append(_ligne(
        'cable_ac', cable, 'Câble AC %g mm² %s → TGBT' % (section, nom),
        longueur, 'm'))
    hypotheses.append({
        'cle': 'section_ac_%s' % (ondu.get('produit') or nom),
        'valeur': section, 'statut': 'source',
        'source': '%s (Ib %.1f A, In %g A, chute %.2f %%)' % (
            proposee.critere, ib, calibre, proposee.chute_pct)})


def _comptage(catalogue, nb_ond, entrees, lignes, alertes):
    tension = (entrees.get('tension') or '').upper()
    revente = bool(entrees.get('revente_choisie'))
    if tension == 'MT' and revente:
        return
    points = entrees.get('nb_points_raccordement')
    try:
        points = int(points) if points not in (None, '') else None
    except (TypeError, ValueError):
        points = None
    a_confirmer = points is None
    points = points or 1
    article = (_du_role(catalogue, 'controleur_injection')
               or _du_role(catalogue, 'compteur_injection'))
    role = article.get('role_ci') if article else 'compteur_injection'
    fiche = (article or {}).get('fiche') or {}
    max_pilotes = fiche.get('lim_onduleurs_max')
    if max_pilotes:
        quantite = points * int(math.ceil(nb_ond / float(max_pilotes)))
        motif = None
    else:
        quantite = points
        motif = MOTIF_FOURNISSEUR
        a_confirmer = True
    lignes.append(_ligne(
        role, article, "Comptage / limitation d'injection", quantite, 'u',
        motif=motif,
        a_confirmer=a_confirmer))
    if a_confirmer and entrees.get('nb_points_raccordement') in (None, ''):
        alertes.append(_alerte(
            'CI_POINTS_RACCORDEMENT',
            'nombre de points de raccordement non déclaré : un dispositif '
            'de comptage compté, à confirmer à la visite'))


def _logger(catalogue, nb_ond, lignes):
    if nb_ond < 2:
        return
    article = _du_role(catalogue, 'logger_supervision')
    max_sup = ((article or {}).get('fiche') or {}).get('log_onduleurs_max')
    quantite = int(math.ceil(nb_ond / float(max_sup))) if max_sup else 1
    lignes.append(_ligne('logger_supervision', article,
                         'Logger de supervision', quantite, 'u',
                         motif=MOTIF_FOURNISSEUR, a_confirmer=True))


def _prestation(cle, libelle, forfait, article, kwc, nb_panneaux):
    montants = [_d((forfait or {}).get(k))
                for k in ('fixe_ht', 'par_kwc_ht', 'par_panneau_ht')]
    source = ((forfait or {}).get('source') or '').strip()
    if not source or all(m is None for m in montants):
        return _ligne(cle, None, libelle, 1, 'forfait',
                      motif='prestation non réglée : prix à renseigner')
    fixe, par_kwc, par_panneau = (m or Decimal('0') for m in montants)
    total = (fixe + par_kwc * Decimal(str(kwc))
             + par_panneau * Decimal(nb_panneaux)).quantize(Decimal('0.01'))
    ligne = _ligne(cle, article, libelle, 1, 'forfait')
    ligne['prix_connu'] = True
    ligne['motif'] = 'forfait société (source : %s)' % source
    ligne['prix_unitaire_ht'] = str(total)
    return ligne


def composer_ci(kwc, catalogue, *, onduleurs, entrees, forfaits):
    """La composition C&I serveur (forme ``composition`` du contrat).

    ``catalogue`` : éléments ``stock.selectors.produits_ci`` (+ facultatif
    ``prix_vente_ht``). ``onduleurs`` : résultat de
    ``moteur_ci.onduleurs.combiner_onduleurs``. ``entrees`` : ``{module
    {produit, designation, pmax_wc, prix_connu}, phase, tension BT|MT,
    type_pose, longueur_dc_m, longueur_ac_m, nb_points_raccordement,
    revente_choisie, besoin_cellule_mt, batterie_souhaitee}``. ``forfaits`` :
    ``CompanyProfile.forfaits_ci``.
    """
    catalogue = list(catalogue or [])
    entrees = dict(entrees or {})
    lignes, alertes, hypotheses = [], [], []
    kwc = _f(kwc) or 0.0

    # ── Panneaux
    module = entrees.get('module') or {}
    pmax = _f(module.get('pmax_wc'))
    nb_panneaux = int(math.ceil(kwc * 1000.0 / pmax - 1e-9)) if pmax else 0
    if pmax:
        lignes.append({
            'role': 'panneau', 'produit': module.get('produit'),
            'designation': module.get('designation') or 'Module PV',
            'quantite': nb_panneaux, 'unite': 'u',
            'prix_connu': bool(module.get('prix_connu')),
            'motif': None if module.get('prix_connu') else MOTIF_PRIX,
            'a_confirmer_visite': False})
        _appliquer_palier(lignes[-1], module)
    else:
        alertes.append(_alerte('CI_MODULE_FICHE',
                               'module sans puissance publiée : nombre de '
                               'panneaux non calculé', niveau='bloquant'))

    # ── Onduleurs (combinaison CIQ111)
    par_id = _par_id(catalogue)
    for item in (onduleurs or {}).get('combinaison') or []:
        lignes.append(_ligne(
            'onduleur_string_tri', par_id.get(item.get('produit')) or {
                'id': item.get('produit'), 'nom': item.get('nom'),
                'prix_connu': True},
            item.get('nom') or 'Onduleur', item.get('quantite'), 'u'))
    unitaires = _onduleurs_unitaires(onduleurs)
    nb_ond = len(unitaires)

    # ── Câble DC : Σ chaînes × longueur déclarée
    chaines = (onduleurs or {}).get('chaines')
    longueur_dc = _f(entrees.get('longueur_dc_m'))
    cable_dc = _du_role(catalogue, 'cable_dc')
    if not chaines:
        lignes.append(_ligne('cable_dc', cable_dc, 'Câble solaire DC', None,
                             'm', motif='chaînes à vérifier : quantité non '
                             'calculée', a_confirmer=True))
    elif longueur_dc is None or longueur_dc <= 0:
        lignes.append(_ligne('cable_dc', cable_dc, 'Câble solaire DC', None,
                             'm', motif=MOTIF_LONGUEUR, a_confirmer=True))
    else:
        nb_chaines = sum(int(c.get('nb_chaines') or 0) for c in chaines)
        lignes.append(_ligne('cable_dc', cable_dc, 'Câble solaire DC',
                             round(nb_chaines * longueur_dc, 2), 'm'))
        hypotheses.append({
            'cle': 'cable_dc_m', 'valeur': round(nb_chaines * longueur_dc, 2),
            'statut': 'declare',
            'source': '%d chaînes × %g m (longueur déclarée par chaîne)' % (
                nb_chaines, longueur_dc)})

    # ── Coffrets DC (un par onduleur), protections et câble AC par onduleur
    if nb_ond:
        lignes.append(_ligne('coffret_dc', _du_role(catalogue, 'coffret_dc'),
                             'Coffret DC C&I', nb_ond, 'u'))
    for ondu in unitaires:
        _protection_et_cable_ac(catalogue, ondu, entrees, lignes, alertes,
                                hypotheses)

    # ── Structure par type de pose du toit
    type_pose = (entrees.get('type_pose') or '').strip()
    if type_pose:
        structure = _du_role(catalogue, 'structure_ci', lambda f, p: (
            (p.get('type_pose') or f.get('struct_type_pose')) == type_pose))
        lignes.append(_ligne('structure_ci', structure,
                             'Structure C&I (%s)' % type_pose, nb_panneaux,
                             'module'))
    else:
        lignes.append(_ligne('structure_ci', None, 'Structure C&I',
                             nb_panneaux, 'module',
                             motif='type de pose non déclaré : structure à '
                             'confirmer à la visite', a_confirmer=True))

    # ── Comptage / limitation, logger, coffret AC
    _comptage(catalogue, nb_ond, entrees, lignes, alertes)
    _logger(catalogue, nb_ond, lignes)
    lignes.append(_ligne('coffret_ac', _du_role(catalogue, 'coffret_ac'),
                         'Coffret AC C&I', 1, 'u'))

    # ── Cellule MT
    tension = (entrees.get('tension') or '').upper()
    if entrees.get('besoin_cellule_mt') is True:
        lignes.append(_ligne('cellule_mt', _du_role(catalogue, 'cellule_mt'),
                             'Cellule MT', 1, 'u'))
    elif tension == 'MT' and entrees.get('besoin_cellule_mt') is None:
        alertes.append(_alerte(
            'CI_POSTE_LIVRAISON',
            'poste de livraison à confirmer à la visite', champ='tension'))

    # ── Prestations réglées par la société
    for cle, libelle in PRESTATIONS_CI:
        lignes.append(_prestation(cle, libelle, (forfaits or {}).get(cle),
                                  _du_role(catalogue, cle), kwc, nb_panneaux))

    # ── Options : O&M nommée toujours ; batterie seulement si catalogue+besoin
    om = _du_role(catalogue, 'om_ci')
    options = [{'cle': 'om',
                'libelle': (om or {}).get('nom')
                or 'Exploitation et maintenance (O&M)',
                'prix_connu': bool(om and om.get('prix_connu')),
                'valeur': 'valeur non chiffrée'}]
    batterie = _du_role(catalogue, 'batterie_ci')
    if batterie is not None and entrees.get('batterie_souhaitee'):
        options.append({'cle': 'batterie', 'libelle': batterie.get('nom'),
                        'prix_connu': bool(batterie.get('prix_connu')),
                        'valeur': 'valeur non chiffrée'})

    prix_a_renseigner = [ligne['designation'] for ligne in lignes
                         if not ligne['prix_connu']]
    return {
        'lignes': lignes,
        'onduleurs': {
            'combinaison': (onduleurs or {}).get('combinaison'),
            'ratio_dc_ac': (onduleurs or {}).get('ratio_dc_ac'),
            'chaines': chaines,
        },
        'prix_a_renseigner': prix_a_renseigner,
        'incomplet': bool(prix_a_renseigner),
        'options': options,
        'alertes': alertes,
        'hypotheses': hypotheses,
    }
