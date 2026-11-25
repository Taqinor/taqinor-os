"""ADEV160 — la moitié « CALCUL » des rafraîchisseurs d'étude, par LIGNES (D-ACAL-97).

Chaque fonction reçoit ``devis`` (le CONTEXTE : société, lead, marché,
``etude_params``, niveau de règles) et ``lignes`` : ``None`` ⇒ les lignes du
devis, lues comme aujourd'hui (les rafraîchisseurs sur devis délèguent ainsi,
au comportement près) ; une liste ⇒ ces lignes COMPOSÉES, jamais relues en
base (:class:`DevisAuxLignes`). Rien n'est écrit ici : l'écriture
(``etude_schema.ecrire``), les gardes et les relèvements de règles restent au
rafraîchisseur. Les collaborateurs sont importés au moment de l'appel depuis
leur module porteur (``etude_horaire``, ``etude_ci``, ``pompage``…) : les
``patch`` des tests y sont toujours vus. Aucun noyau n'est réécrit.

``blocs_horaires_des_lignes`` passe par ``etude_horaire_pour_devis`` (gardes
d'exception comprises) sur le devis aux lignes : le bloc horaire lit donc les
lignes composées sans qu'aucune signature d'``etude_horaire`` ne change.
"""


class _LignesComposees:
    """Le gestionnaire ``devis.lignes`` réduit à ce que lisent les études."""

    def __init__(self, lignes):
        self._lignes = list(lignes)

    def all(self):
        return list(self._lignes)

    def select_related(self, *_champs):
        return self

    prefetch_related = select_related

    def order_by(self, *champs):
        lignes = list(self._lignes)
        for champ in reversed(champs):
            nom = champ.lstrip('-')
            lignes.sort(key=lambda li: (getattr(li, nom, None) is None, getattr(li, nom, None) or 0),
                        reverse=champ.startswith('-'))
        return _LignesComposees(lignes)

    def __iter__(self):
        return iter(self._lignes)

    def __getattr__(self, nom):
        raise AttributeError('lignes composées : « %s » non servi (jamais une relecture en base)' % nom)


class DevisAuxLignes:
    """Le devis (contexte, en LECTURE) dont ``.lignes`` rend des lignes
    composées. Tout autre attribut est celui du devis ; toute écriture est
    refusée (une étude ne modifie jamais son devis)."""

    def __init__(self, devis, lignes):
        self.__dict__['_devis'] = devis
        self.__dict__['lignes'] = _LignesComposees(lignes)

    def __getattr__(self, nom):
        return getattr(self.__dict__['_devis'], nom)

    def __setattr__(self, nom, valeur):
        raise AttributeError('DevisAuxLignes est en lecture seule (%s)' % nom)


def avec_lignes(devis, lignes):
    """``devis`` lui-même (``lignes is None``), sinon :class:`DevisAuxLignes`."""
    return devis if lignes is None else DevisAuxLignes(devis, lignes)


def etude_horaire_des_lignes(devis, lignes=None, *, kwc, batterie_kwh_utile, data,
                             occupation=None, jour_reference=None):
    """Le bloc ``etude_horaire`` sur ces lignes : LE corps
    ``etude_horaire._etude_horaire_pour_devis`` (laissé chez son porteur, où
    les tests patchent ses lecteurs ``EH.capacite_batterie_du_devis``…), lu
    sur :class:`DevisAuxLignes` ; aucune seconde définition."""
    from apps.ventes.etude_horaire import _etude_horaire_pour_devis
    return _etude_horaire_pour_devis(
        avec_lignes(devis, lignes), kwc=kwc, batterie_kwh_utile=batterie_kwh_utile, data=data,
        occupation=occupation, jour_reference=jour_reference)


def blocs_horaires_des_lignes(devis, lignes=None, *, kwc=None, batterie_kwh_utile=None, kwc_sans=None):
    """``(bloc, bloc_sans)`` estampillés ``_empreinte_entrees`` (moitié calcul
    de ``etudes.rafraichir_etude_horaire`` ; entrées lues UNE fois, QJR45)."""
    from apps.ventes.domain.entrees import empreinte_entrees, entrees_depuis_devis
    from apps.ventes.etude_horaire import etude_horaire_pour_devis
    devis = avec_lignes(devis, lignes)
    entrees = entrees_depuis_devis(devis)
    empreinte = (empreinte_entrees(entrees)
                 if entrees is not None and entrees.conso_kwh_mensuelles else None)

    def _calculer(puissance):
        bloc_calcule = etude_horaire_pour_devis(
            devis, kwc=puissance, batterie_kwh_utile=batterie_kwh_utile,
            jour_reference=(entrees.jour_reference if entrees else None))
        if bloc_calcule is None:
            return None
        bloc_calcule = dict(bloc_calcule)
        bloc_calcule['_empreinte_entrees'] = empreinte
        return bloc_calcule

    return _calculer(kwc), (_calculer(kwc_sans) if kwc_sans else None)


def puissances_des_lignes(devis, lignes=None):
    """I7 — ``(kwc du bloc principal, kwc du bloc « sans » ou None)`` (corps
    déplacé de ``etudes.puissances_etude_horaire``, qui délègue ici)."""
    from apps.ventes.quote_engine.builder import (
        _scalaires_par_option, _variante_de_ligne, panneaux_et_watt_lu)
    from apps.ventes.quote_engine.lignes_classement import kwc_des_lignes
    devis = avec_lignes(devis, lignes)
    lignes = [
        li for li in devis.lignes.select_related('produit', 'produit__fiche_technique').all()
        if getattr(li, 'type_ligne', 'produit') == 'produit' and not getattr(li, 'optionnelle', False)
    ]
    par_option = _scalaires_par_option(
        [li for li in lignes if _variante_de_ligne(li) in ('', 'sans')],
        [li for li in lignes if _variante_de_ligne(li) in ('', 'avec')],
        devis)  # AGNR70 — kWc Σ quantité × watt lu au niveau 12
    if par_option['divergents']:
        return par_option['kwc_avec'], par_option['kwc_sans']
    # ERR-ETUDE-KWC-DOUBLE — panneaux variantés à comptes égaux : UNE option.
    if any(_variante_de_ligne(li) in ('sans', 'avec') for li in lignes if panneaux_et_watt_lu([li])[0]):
        return par_option['kwc_avec'] or par_option['kwc_sans'], None
    nb_panneaux, watt = panneaux_et_watt_lu(lignes)
    return kwc_des_lignes(lignes, nb_panneaux, watt, devis), None


def dimensionnement_des_lignes(devis, lignes=None, *, force=False):
    """Moitié calcul de ``etudes.rafraichir_dimensionnement_devis`` (T5,
    QJR43) : ``(etat, bloc)`` — ``etat`` ``None`` (rien à faire), ``'retirer'``
    (plus de consommation : clé à retirer), ``'a_jour'`` (empreinte
    concordante : ``bloc`` est le bloc rangé) ou ``'calcule'`` (``bloc`` neuf,
    ``_empreinte`` posée)."""
    from apps.ventes.dimensionnement import recommander_taille
    from apps.ventes.domain.entrees import empreinte_entrees
    from apps.ventes.domain.etudes import entrees_dimensionnement_du_devis
    devis = avec_lignes(devis, lignes)
    # P2-A / QJR42 — LECTURE UNIQUE des entrées, AVEC contexte (empreinte).
    entrees = entrees_dimensionnement_du_devis(devis)
    if entrees is None:
        return None, None
    etude_params = entrees['etude_params']
    conso = entrees['conso_kwh_mensuelles']
    if not conso:
        if not force and 'dimensionnement' not in etude_params:
            return None, None
        return 'retirer', None
    empreinte = empreinte_entrees(entrees)
    bloc = etude_params.get('dimensionnement')
    if not force and isinstance(bloc, dict) and bloc.get('_empreinte') == empreinte:
        return 'a_jour', bloc
    resultat = recommander_taille(**_arguments_du_balayage(devis, entrees))
    resultat['_empreinte'] = empreinte
    return 'calcule', resultat


def _arguments_du_balayage(devis, entrees):
    """Les arguments de ``recommander_taille`` pour ``devis`` (UNE lecture des entrées)."""
    from apps.ventes.domain.regles_calcul import REGLES_CORRIGEES_2710, regles_au_moins
    return dict(
        company=entrees['company'], conso_kwh_mensuelles=entrees['conso_kwh_mensuelles'],
        ville=entrees['ville'], lat=entrees['lat'], lon=entrees['lon'],
        occupation=entrees['occupation'], equipements=entrees['equipements'],
        source_conso=entrees['source_conso'], jour_reference=entrees['jour_reference'],
        tranches=entrees['tranches'], charges_fixes_mad=entrees['charges_fixes_mad'],  # QJR46
        phase=entrees['phase'], gamme_nom_devis=entrees['gamme_nom_devis'],  # QJR606
        hors_reseau=entrees['hors_reseau'], mppt_paires=entrees['mppt_paires'],  # ERR-QJR605
        # RSIZ2/3/5 — un devis aux règles < 3 garde ses sondes.
        regles_2710=regles_au_moins(devis, REGLES_CORRIGEES_2710), devis=devis)  # AMOT130


def lignes_aux_tailles(devis, lignes, nombres):
    """T4-X4-018 — les lignes du tableau de dimensionnement de ``devis`` aux tailles
    ``nombres`` (panneaux), chacune par LE balayage (``recommander_taille``, bornes
    forcées à cette taille : ``min_panneaux = max_panneaux``) ; ``[]`` sans
    consommation. Aucune seconde règle : même évaluation, même choix de batterie."""
    from apps.ventes.dimensionnement import recommander_taille
    from apps.ventes.domain.etudes import entrees_dimensionnement_du_devis
    devis = avec_lignes(devis, lignes)
    entrees = entrees_dimensionnement_du_devis(devis)
    if entrees is None or not entrees['conso_kwh_mensuelles']:
        return []
    arguments, trouvees = _arguments_du_balayage(devis, entrees), []
    for nombre in sorted(set(int(n) for n in nombres)):
        tableau = recommander_taille(**arguments, min_panneaux=nombre, max_panneaux=nombre)['tableau']
        trouvees += [ligne for ligne in tableau if ligne.get('panneaux') == nombre]
    return trouvees


def preparation_etude_ci(devis, lignes=None):
    """CIQ119 — ce que le rafraîchisseur C&I lit AVANT de décider : ``None``
    hors commercial / industriel ; sinon ``{'params', 'kwc'}`` (``kwc`` nul ⇒
    plus aucun panneau) complété, quand ``kwc``, du catalogue C&I, des
    onduleurs et de l'option « avec » DES LIGNES, de la base de production
    (pose réelle, ACAL1195) et de l'empreinte."""
    from apps.ventes.domain.depart_une_batterie_ci import empreinte_depart
    from apps.ventes.domain.etude_ci import (
        CLE_ETUDE_CI, MODES, _empreinte, _kwc_option_servie, _onduleurs_des_lignes,
        _option_avec_du_devis, cles_hors_empreinte, lire_catalogue_ci)
    from apps.ventes.domain.etudes import puissances_etude_horaire
    from apps.ventes.horaire.productible_pose import base_etude_ci
    devis = avec_lignes(devis, lignes)
    mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    if mode not in MODES:
        return None
    params = dict(getattr(devis, 'etude_params', None) or {})
    kwc = _kwc_option_servie(devis, *puissances_etude_horaire(devis))
    if not kwc:
        return {'params': params, 'kwc': None}
    company = getattr(devis, 'company', None)
    catalogue = lire_catalogue_ci(company)
    onduleurs = _onduleurs_des_lignes(devis, catalogue)
    imposee, mono = _option_avec_du_devis(devis, catalogue, *puissances_etude_horaire(devis))
    hors = cles_hors_empreinte()  # CIQ129 — seules les ENTRÉES entrent dans l'empreinte
    stockees = {k: v for k, v in params.items() if k not in hors}
    base, hyp_base = base_etude_ci(devis, kwc=kwc)
    return {'params': params, 'kwc': kwc, 'mode': mode, 'company': company, 'onduleurs': onduleurs,
            'imposee': imposee, 'mono': mono, 'base': base, 'hyp_base': hyp_base,
            'empreinte': empreinte_depart(devis, _empreinte(stockees, kwc, onduleurs, imposee, base)),
            'existant': params.get(CLE_ETUDE_CI) or {}}


def lignes_de_l_ecran(devis, lignes):
    """T4-X6-008 — les lignes PRODUIT que l'écran d'édition envoie (``produit`` de la société
    du devis, quantité, prix, remise, TVA, option), en ``LigneDevis`` NON enregistrées : la
    composition que l'étude lit (:class:`DevisAuxLignes`), jamais écrite. Une ligne
    illisible ou d'un produit étranger est ignorée (elle n'apporte rien)."""
    from decimal import Decimal, InvalidOperation

    from apps.stock.selectors import get_produit_scoped
    from apps.ventes.models import LigneDevis

    def _decimal(valeur, defaut):
        return Decimal(str(valeur)) if valeur not in (None, '') else defaut

    composees = []
    for ordre, ligne in enumerate(li for li in (lignes or []) if isinstance(li, dict)):
        if (ligne.get('type_ligne') or 'produit') != 'produit':
            continue
        try:
            produit = get_produit_scoped(devis.company, int(ligne.get('produit')))
            valeurs = {'quantite': _decimal(ligne.get('quantite'), None),
                       'prix_unitaire': _decimal(ligne.get('prix_unitaire'), None),
                       'remise': _decimal(ligne.get('remise'), Decimal('0')),
                       'taux_tva': _decimal(ligne.get('taux_tva'), devis.taux_tva)}
        except (TypeError, ValueError, InvalidOperation):
            continue
        if produit is None or valeurs['quantite'] is None:
            continue
        composees.append(LigneDevis(
            devis=devis, produit=produit, designation=str(ligne.get('designation') or produit.nom)[:255],
            type_ligne='produit', ordre=ordre, variante=str(ligne.get('variante') or ''),
            optionnelle=bool(ligne.get('optionnelle')), **valeurs))
    return composees


def etude_ci_de_l_ecran(devis, lignes, entrees):
    """T4-X6-008 — l'étude C&I de l'écran d'édition : LE calcul rangé du devis
    (:func:`preparation_etude_ci` + :func:`etude_ci_calculee`, taille, onduleurs et option
    « avec » DES LIGNES envoyées) avec les entrées TAPÉES par-dessus ; ``None`` quand les
    lignes ne portent aucun panneau (l'écran garde l'aperçu du moteur)."""
    composees = lignes_de_l_ecran(devis, lignes)
    preparation = preparation_etude_ci(devis, composees)
    if not preparation or not preparation.get('kwc'):
        return None
    return etude_ci_calculee(devis, preparation, composees, entrees=entrees)[0]


def etude_ci_calculee(devis, preparation, lignes=None, *, entrees=None):
    """``etudier_ci`` en TAILLE DONNÉE sur la préparation : ``(etude, bloc)``,
    ``bloc`` ``None`` sans bilan. Sans « une seule batterie »
    (``depart_une_batterie_ci.poser_depart``, qui simule dans une transaction :
    laissé au rafraîchisseur). ``entrees`` (T4-X6-008, écran) : les saisies tapées,
    posées par-dessus le devis avec la provenance « saisie »."""
    from apps.ventes.domain.etude_ci import (
        CLE_PRODUCTION_FIGEE, CLE_PRODUCTION_FIGEE_RASANTE, CLE_TAILLE_CREATION, VERSION_MOTEUR,
        _source_production, bloc_etude_ci_stocke, etudier_ci, provenance_lignes_du_devis)
    devis = avec_lignes(devis, lignes)
    params, base = preparation['params'], preparation['base']
    corps = dict(entrees or {}, mode=preparation['mode'], taille_explicite_kwc=preparation['kwc'])
    etude = etudier_ci(
        preparation['company'], corps,
        devis=devis, lead=getattr(devis, 'lead', None),
        production_figee=None if base else params.get(CLE_PRODUCTION_FIGEE),
        onduleurs_imposes=preparation['onduleurs'] or None,
        source_production_figee=_source_production(preparation['existant']),
        option_avec_imposee=preparation['imposee'],
        production_figee_rasante=params.get(CLE_PRODUCTION_FIGEE_RASANTE),
        verdict_creation=params.get(CLE_TAILLE_CREATION),
        provenance_corps=None if entrees else provenance_lignes_du_devis(), base_production=base)
    if preparation['hyp_base'] and etude.get('bilan') is not None:
        etude['hypotheses'] = list(etude.get('hypotheses') or []) + [preparation['hyp_base']]
    if etude.get('bilan') is None:
        return etude, None
    return etude, dict(bloc_etude_ci_stocke(etude, mono=preparation['mono']), version=VERSION_MOTEUR,
                       empreinte=preparation['empreinte'])


def etude_pompage_des_lignes(devis, lignes=None, *, force=False, sortie=None):
    """AGR123 — moitié calcul de ``pompage.rafraichir_etude_pompage_devis`` :
    ``None`` quand l'empreinte concorde (sans ``force``) ; sinon
    ``(derivees, a_ecrire)`` — les dérivées ``moteur_pompage`` et celles qui
    diffèrent de l'étude rangée."""
    from apps.ventes.domain.pompage import (
        _empreinte, _sortie_precalculee, derivees_de_l_etude, etudier_pompage, facture_du_devis,
        lire_catalogue)
    from apps.ventes.domain.pompage_pose import plan_pose_pompage
    from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111, regles_au_moins
    devis = avec_lignes(devis, lignes)
    etude = dict(devis.etude_params or {})
    company = devis.company
    lead = getattr(devis, 'lead', None)
    catalogue = lire_catalogue(company)
    facture = facture_du_devis(devis, catalogue)
    plan = plan_pose_pompage(devis)  # ACAL1201 — None ⇒ empreinte d'avant
    empreinte = _empreinte(etude, facture, getattr(lead, 'id', None), plan)
    stockee = (etude.get('provenance_pompage') or {}).get('_empreinte')
    if not force and stockee == empreinte:
        return None
    corps = {}
    fige = etude.get('pvgis_fige') or {}
    localisation = etude.get('localisation') or {}
    if (fige.get('lat') is not None and fige.get('lon') is not None
            and (localisation.get('lat') is None or localisation.get('lon') is None)):
        corps['localisation'] = dict(localisation, lat=fige['lat'], lon=fige['lon'])
    # AGQ24 — l'étude écrite par le devis automatique est RELUE : jamais deux calculs.
    sortie = sortie or _sortie_precalculee(devis)
    if sortie is None:
        sortie = etudier_pompage(company, corps, devis=devis, lead=lead, facture=facture)
    derivees = derivees_de_l_etude(sortie, pvgis_fige=fige or None)
    if derivees.get('production') and not regles_au_moins(devis, REGLES_POSE_REELLE_2111):  # ACAL1201
        derivees['production'] = {k: v for k, v in derivees['production'].items()
                                  if k != 'plan_irradiation'}
    # ``pvgis_fige`` est entrée ET dérivée : l'empreinte stockée décrit l'état APRÈS écriture.
    empreinte = _empreinte(dict(etude, pvgis_fige=derivees.get('pvgis_fige')), facture,
                           getattr(lead, 'id', None), plan)
    derivees['provenance_pompage']['_empreinte'] = empreinte
    return derivees, {cle: valeur for cle, valeur in derivees.items() if etude.get(cle) != valeur}
