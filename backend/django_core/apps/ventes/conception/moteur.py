"""ADEV133 — LE point d'entrée unique du moteur (D-ACAL-97), sans aucune écriture.

``calculer_conception(lead, company)`` COMPOSE, pour les trois marchés, les
fonctions que le devis automatique appelle lui-même (une définition chacune) :
décisions de ``conception/decisions.py``, étapes 1-4 du pipeline
(``pipeline.composer_l_intention``), lignes NON enregistrées de l'écrivain
(``lignes.lignes_neuves``), puis les études PAR LIGNES de
``conception/etudes_lignes.py`` sur un ``Devis`` jamais enregistré
(:class:`~apps.ventes.conception.etudes_lignes.DevisAuxLignes`). ``etude_params``
est fusionné par ``etude_schema.fusionner`` (la règle de l'écrivain unique, sans
sa persistance). Aucun noyau n'est réécrit ; rien n'est écrit en base.

Ce que le moteur NE reproduit PAS est DIT dans ``absents`` (``{clé: raison}``),
jamais simulé : « une seule batterie » C&I (``poser_depart`` simule dans une
transaction) et toute étude qui lève (le devis l'aurait avalée).
"""
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

VERSION_MOTEUR = 'moteur-unique-1'
CODE_LOCALISATION = 'localisation_inconnue'
MESSAGE_LOCALISATION = 'Ville inconnue du moteur : renseigner la ville ou le point GPS du lead.'
CODE_REFUS_MOTEUR = 'refus_moteur'
#: La sortie servie (contrat ``contract_samples/conception_lead.json``).
CLES_SORTIE = ('etat', 'refus', 'marche', 'option_retenue', 'valeurs', 'blocs', 'suppositions',
               'entrees_utilisees', 'empreinte', 'niveau_regles', 'version_moteur')


@dataclass
class ResultatConception:
    """La sortie du moteur (:data:`CLES_SORTIE`, :meth:`sortie`) et, NON servis,
    ce que l'écrivain du devis (ADEV135/ADEV142) relit : ``etude_params`` tel
    qu'un devis automatique né de cette conception le porterait (sans le
    ``journal_auto`` que seul un appelant à journal fait ranger :
    ``creation_auto.cles_rapides(journal)``), ``lignes`` (``LigneDevis`` NON
    enregistrées), ``conception_electrique`` (``electrical_design``),
    ``journal`` (ce que ``build_devis_auto`` rend à son appelant) et
    ``absents`` (``{clé: raison}``)."""
    marche: str
    entrees_utilisees: dict
    empreinte: str
    niveau_regles: int
    etat: str = 'complet'
    refus: object = None
    option_retenue: object = None
    valeurs: dict = field(default_factory=dict)
    blocs: dict = field(default_factory=dict)
    suppositions: list = field(default_factory=list)
    version_moteur: str = VERSION_MOTEUR
    etude_params: dict = field(default_factory=dict)
    lignes: list = field(default_factory=list)
    conception_electrique: object = None
    journal: dict = field(default_factory=dict)
    absents: dict = field(default_factory=dict)
    materiel_pompage: dict = field(default_factory=dict)

    def sortie(self):
        return {cle: getattr(self, cle) for cle in CLES_SORTIE}


def calculer_conception(lead, company, *, entrees=None, toit=None, imposes=None, investissement=None):
    """La conception du ``lead`` (de ``company`` seulement), SANS ÉCRITURE.

    ``entrees`` : ``EntreesConception`` déjà lues (sinon ``entrees_pour``) ;
    ``toit`` : la pose servie (son ``empreinte`` entre dans l'empreinte ; son
    ``plafond_panneaux`` borne le résidentiel comme le ``plafond_toit`` du
    tunnel) ; ``imposes`` : composition imposée résidentielle (forme
    ``composition_imposee.imposition_du_corps``) ; ``investissement`` (MAD) :
    le prix de référence du payback. Un lead sans ville ni GPS ⇒ refus
    ``localisation_inconnue`` ; un refus du devis automatique ⇒ refus
    ``refus_moteur`` nommant son champ."""
    from apps.ventes.conception.entrees import _empreinte, entrees_pour
    from apps.ventes.domain.regles_calcul import REGLES_COURANTES
    from apps.ventes.domain.taille import AutoDevisError

    if getattr(lead, 'company_id', None) != getattr(company, 'pk', None):
        raise ValueError('Lead hors de la société : aucune conception.')
    entrees = entrees or entrees_pour(lead, company, toit=toit)
    resultat = ResultatConception(
        marche=entrees.marche, entrees_utilisees=entrees.entrees_utilisees,
        niveau_regles=REGLES_COURANTES, empreinte=_empreinte({
            'entrees': entrees.empreinte, 'version_moteur': VERSION_MOTEUR,
            'niveau_regles': REGLES_COURANTES, 'imposes': imposes or {}}))
    refus = _refus_localisation(lead)
    if refus is None:
        calcul = {'residentiel': _residentiel, 'agricole': _agricole}.get(entrees.marche, _ci)
        try:
            calcul(resultat, lead, company, entrees, toit=toit, imposes=imposes)
        except AutoDevisError as exc:
            refus = {'code': CODE_REFUS_MOTEUR, 'champ': exc.field or '', 'message': exc.message}
    if refus is not None:
        resultat.etat, resultat.refus = 'refus', refus
        resultat.etude_params, resultat.lignes, resultat.conception_electrique = {}, [], None
        return resultat
    resultat.blocs = blocs_du_moteur(resultat.etude_params)
    resultat.option_retenue, options = _options(resultat)
    resultat.valeurs = {option: _valeurs(resultat, lead, option, investissement) for option in options}
    return resultat


def _refus_localisation(lead):
    from apps.crm.selectors import ville_effective
    if ville_effective(lead) or (getattr(lead, 'gps_lat', None) is not None
                                 and getattr(lead, 'gps_lng', None) is not None):
        return None
    return {'code': CODE_LOCALISATION, 'champ': 'ville', 'message': MESSAGE_LOCALISATION}


def blocs_du_moteur(etude_params):
    """Les clés DÉRIVÉES des quatre moteurs d'étude (contrat ``blocs``)."""
    from apps.ventes.domain import etude_schema as es
    proprietaires = {es.MOTEUR_HORAIRE, es.MOTEUR_DIMENSIONNEMENT, es.MOTEUR_CI, es.MOTEUR_POMPAGE}
    return {cle: valeur for cle, valeur in etude_params.items()
            if (es.SCHEMA.get(cle) or {}).get('nature') == es.DERIVEE
            and es.SCHEMA[cle]['proprietaire'] in proprietaires}


def _fusion(devis, proprietaire, **cles):
    from apps.ventes.domain.etude_schema import fusionner
    devis.etude_params = fusionner(devis.etude_params or {}, proprietaire=proprietaire, **cles)


def _devis_neuf(intention, specs, avertissements):
    """Le brouillon NON enregistré (champs de ``_creer_brouillon``) et son
    contexte aux lignes de l'écrivain (``lignes_neuves``)."""
    from apps.ventes.conception.etudes_lignes import DevisAuxLignes
    from apps.ventes.domain.lignes import lignes_neuves
    from django.utils import timezone

    from apps.ventes.domain.pipeline import champs_du_brouillon
    from apps.ventes.models import Devis

    devis = Devis(**champs_du_brouillon(intention))
    # Ce que ``Devis.save`` poserait (``auto_now``) : la couche « devis » des
    # entrées C&I est datée de lui (``etude_ci._couche_devis``).
    devis.updated_at = timezone.now()
    lignes = lignes_neuves(devis, specs, intention.company, avertissements=avertissements)
    return devis, DevisAuxLignes(devis, lignes), lignes


def _provenance(devis, contexte, intention):
    from apps.ventes.domain.etude_schema import PIPELINE
    from apps.ventes.domain.pipeline import estampille_de_provenance
    stamp = estampille_de_provenance(contexte, intention)
    if stamp is not None:
        _fusion(devis, PIPELINE, provenance=stamp)


def _residentiel(resultat, lead, company, entrees, *, toit, imposes):
    """``_build_devis_auto_residentiel`` sans écriture : décision, contrôle à
    blanc, intention, étapes 1-4, lignes de l'écrivain, étapes 6-8."""
    from apps.ventes.conception.decisions import decider_taille_residentielle, verifier_composition_residentielle
    from apps.ventes.domain import creation_auto_residentiel as R
    from apps.ventes.domain import etude_schema as es
    from apps.ventes.domain.creation_auto import cles_rapides
    from apps.ventes.domain.pipeline import cles_etude_de_composition, composer_l_intention, specs_de_composition
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    from apps.ventes.utils.company_settings import tva_standard

    taux, journal, imposition, scenario = tva_standard(company), {}, None, None
    if imposes:
        from apps.ventes.domain.composition_imposee import _alerter, preparer_imposition
        imposition, alertes, _phase, _isole = preparer_imposition(company=company, lead=lead, imposes=imposes)
        scenario = imposition.scenario
        for alerte in alertes:
            _alerter(journal.setdefault('alertes', []), alerte['code'], alerte['message'], alerte.get('champ'))
    decision = decider_taille_residentielle(
        lead=lead, company=company, scenario=scenario, imposition=imposition,
        plafond_toit=getattr(toit, 'plafond_panneaux', None), dimensionner=R._panneaux_dimensionnement_horaire)
    R._verser_au_journal(journal, decision.journal)
    structure_produit_id, structure_type = verifier_composition_residentielle(
        decision, lead=lead, company=company, taux_tva=taux, imposition=imposition)
    intention = R.intention_auto_residentielle(
        decision, lead=lead, company=company, taux_tva=taux, structure_produit_id=structure_produit_id,
        structure_type=structure_type, imposition=imposition, entrees=entrees.moteur)
    avertissements = []
    _entrees, _cible, composition = composer_l_intention(None, intention, avertissements)
    devis, contexte, resultat.lignes = _devis_neuf(intention, specs_de_composition(composition), avertissements)
    _fusion(devis, es.CALEPINAGE, **cles_etude_de_composition(contexte, intention, composition))
    _provenance(devis, contexte, intention)
    _etudes(resultat, devis, contexte)
    _fusion(devis, es.CALEPINAGE, puissance_kwc=puissance_kwc_du_devis(contexte))
    resultat.conception_electrique = _conception_electrique(resultat, contexte, garde=False)
    R._journaliser_avertissements(contexte, {'avertissements': avertissements}, journal)
    if imposition is not None:
        from apps.ventes.domain.composition_imposee import CLE_MARQUEUR
        _fusion(devis, es.COMPOSITION_IMPOSEE, **{CLE_MARQUEUR: dict(imposition.marqueur)})
    _fusion(devis, es.AUTO_DEVIS, **cles_rapides(None))
    resultat.etude_params, resultat.journal = devis.etude_params, journal


def _ci(resultat, lead, company, entrees, *, toit, imposes):
    from apps.ventes.conception.decisions import decider_ci, etude_params_creation_ci
    from apps.ventes.domain.creation_auto import alertes_journal_ci

    etude, lignes, scenario = decider_ci(lead=lead, company=company)
    params = etude_params_creation_ci(etude, mode=lead.type_installation, scenario=scenario)
    contexte = _lignes_du_moteur(resultat, lead, company, params, lignes)
    resultat.journal = {'alertes': alertes_journal_ci(etude, contexte)}


def _agricole(resultat, lead, company, entrees, *, toit, imposes):
    from apps.ventes.conception.decisions import decider_agricole
    from apps.ventes.domain.creation_auto_agricole import alertes_journal_agricole, etude_params_creation_agricole

    decision = decider_agricole(lead=lead, company=company)
    params = etude_params_creation_agricole(decision, lead)
    _lignes_du_moteur(resultat, lead, company, params, decision.lignes, sortie=decision.sortie)
    resultat.journal = {'alertes': alertes_journal_agricole(decision.sortie, decision.omises)}
    resultat.materiel_pompage = {
        role: {'produit': ligne['produit_id'], 'nom': ligne['designation']}
        for ligne in decision.lignes for role in ('pompe', 'variateur_pompage')
        if ligne.get('role_pompage') == role}


def _lignes_du_moteur(resultat, lead, company, params, lignes, *, sortie=None):
    """C&I et agricole : ``_ecrire_devis_auto_par_pipeline`` sans écriture —
    ``MODE_ECRIRE`` (écrivain de lignes, provenance) puis ``MODE_RAFRAICHIR``
    (études, ville de calcul, kWc)."""
    from apps.ventes.domain import etude_schema as es
    from apps.ventes.domain.creation_auto import cles_rapides, specs_des_lignes_moteur
    from apps.ventes.domain.pipeline import ORIGINE_AUTO, IntentionDevis, specs_de_composition
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    from apps.ventes.utils.company_settings import tva_standard

    intention = IntentionDevis(origine=ORIGINE_AUTO, company=company, lead=lead,
                               mode_installation=lead.type_installation, taux_tva=tva_standard(company),
                               etude_initiale=params)
    devis, contexte, resultat.lignes = _devis_neuf(
        intention, specs_de_composition(specs_des_lignes_moteur(lignes)), [])
    _provenance(devis, contexte, intention)
    resultat.conception_electrique = _etudes(resultat, devis, contexte, sortie=sortie)
    _fusion(devis, es.CALEPINAGE, puissance_kwc=puissance_kwc_du_devis(contexte))
    _fusion(devis, es.AUTO_DEVIS, **cles_rapides(None))
    resultat.etude_params = devis.etude_params
    return contexte


def _etudes(resultat, devis, contexte, *, sortie=None):
    """``etudes.rafraichir_etudes_du_devis`` + ``consigner_ville_calcul``, dans
    leur ordre et avec leurs gardes de marché, par leurs moitiés CALCUL. Rend la
    conception électrique rangée hors résidentiel (où ``finaliser`` la range)."""
    from apps.ventes.conception import etudes_lignes as EL
    from apps.ventes.domain import etude_schema as es
    from apps.ventes.domain.pipeline import ville_calcul_du_devis
    from apps.ventes.profils_comparatifs import profils_comparatifs_estampilles

    marche, design = resultat.marche, None

    def _horaire():
        kwc, kwc_sans = EL.puissances_des_lignes(contexte)
        bloc, bloc_sans = EL.blocs_horaires_des_lignes(contexte, kwc=kwc, kwc_sans=kwc_sans)
        _fusion(devis, es.MOTEUR_HORAIRE, etude_horaire=bloc, etude_horaire_sans=bloc_sans)

    def _dimensionnement():
        etat, bloc = EL.dimensionnement_des_lignes(contexte)
        if etat in ('retirer', 'calcule'):
            _fusion(devis, es.MOTEUR_DIMENSIONNEMENT, dimensionnement=bloc)

    def _pompage():
        _derivees, a_ecrire = EL.etude_pompage_des_lignes(contexte, force=True, sortie=sortie)
        _fusion(devis, es.MOTEUR_POMPAGE, **a_ecrire)

    if marche == 'residentiel':
        _au_mieux(resultat, 'etude_horaire', _horaire)
    _au_mieux(resultat, 'dimensionnement', _dimensionnement)
    _au_mieux(resultat, 'profils_comparatifs', lambda: _fusion(
        devis, es.MOTEUR_PROFILS, profils_comparatifs=profils_comparatifs_estampilles(contexte)))
    if marche != 'residentiel':
        design = _conception_electrique(resultat, contexte, garde=True)
    if marche in ('commercial', 'industriel'):
        _au_mieux(resultat, 'etude_ci', lambda: _etude_ci(resultat, devis, contexte))
    if marche == 'agricole':
        _au_mieux(resultat, 'etude_pompage', _pompage)
    _au_mieux(resultat, 'ville_calcul', lambda: _fusion(
        devis, es.PIPELINE, ville_calcul=ville_calcul_du_devis(contexte)))
    return design


def _au_mieux(resultat, cle, calcul):
    """Une étude qui lève : le devis l'aurait avalée (best-effort) ; le moteur
    la DIT absente, jamais simulée."""
    try:
        calcul()
    except Exception as exc:  # noqa: BLE001 — étude best-effort, dite absente (D-ENF22-BLE001)
        logger.warning('Étude %s non calculée (moteur unique)', cle, exc_info=True)
        resultat.absents[cle] = 'erreur : %s' % type(exc).__name__


def _etude_ci(resultat, devis, contexte):
    """``etude_ci.rafraichir_etude_ci_devis`` à la création (sans ``force``,
    aucune étude rangée) : préparation, étude en taille donnée, dérivées."""
    from apps.ventes.conception.etudes_lignes import etude_ci_calculee, preparation_etude_ci
    from apps.ventes.domain import etude_ci as C
    from apps.ventes.domain.depart_une_batterie_ci import phrase_demandee
    from apps.ventes.domain.etude_schema import MOTEUR_CI

    preparation = preparation_etude_ci(contexte)
    etude, bloc = (etude_ci_calculee(contexte, preparation) if preparation and preparation['kwc']
                   else (None, None))
    if bloc is not None and phrase_demandee(devis.etude_params):
        resultat.absents['etude_ci.depart_une_batterie'] = (
            '« une seule batterie » : depart_une_batterie_ci.poser_depart simule dans une transaction '
            '(non extrait)')
    _fusion(devis, MOTEUR_CI, **{
        C.CLE_ETUDE_CI: bloc, C.CLE_PRODUCTION_FIGEE: etude.get('production') if bloc else None,
        C.CLE_PRODUCTION_FIGEE_RASANTE: etude.get('production_rasante') if bloc else None})


def _conception_electrique(resultat, contexte, *, garde):
    """Ce que le devis RANGERAIT en ``electrical_design`` : hors résidentiel,
    derrière les trois portails (``rafraichir_conception_electrique_devis``) ;
    en résidentiel, ``finaliser`` la range sans eux. Une fiche incomplète n'est
    jamais rangée (``build_electrical_design``)."""
    from apps.ventes import electrical_service as E
    try:
        if garde and not E.conception_electrique_dessinable(contexte):
            return None
        return None if E.motifs_fiche_incomplete(contexte) else E.build_electrical_design(
            contexte, persister=False)
    except Exception as exc:  # noqa: BLE001 — le devis l'aurait avalée : dite absente (D-ENF22-BLE001)
        logger.warning('Conception électrique non calculée (moteur unique)', exc_info=True)
        resultat.absents['conception_electrique'] = 'erreur : %s' % type(exc).__name__
        return None


# ── La table §2 de la conception, PAR OPTION ({valeur, unite, source}) ──────
# Lue sur les blocs, les lignes et la conception électrique : aucun calcul.

def _v(valeur, unite=None, source='moteur'):
    return {'valeur': valeur, 'unite': unite, 'source': source}


def _options(resultat):
    """``(option retenue, options)`` : agricole ``sans`` ; sinon le scénario
    servable (« Les deux » ⇒ les deux) ; retenue = la recommandée (C&I), sinon
    l'option que décrit le bloc principal (``avec`` à deux options, I7)."""
    from apps.ventes.domain import scenario as S
    params = resultat.etude_params
    if resultat.marche == 'agricole':
        return 'sans', ('sans',)
    scenario = params.get('scenario')
    if scenario == S.SCENARIO_LES_DEUX:
        recommandee = params.get('recommended_option')
        return ('sans' if recommandee == S.SCENARIO_SANS_BATTERIE else 'avec'), ('sans', 'avec')
    option = 'avec' if scenario == S.SCENARIO_AVEC_BATTERIE else 'sans'
    return option, (option,)


def _materiel(resultat, option):
    from apps.ventes.domain.catalogue import classer_produit
    from apps.ventes.quote_engine.lignes_classement import panneaux_et_watt_lu
    lignes = [li for li in resultat.lignes if li.type_ligne == 'produit' and not li.optionnelle
              and (li.variante or '') in ('', option)]
    classes = [(li, classer_produit(getattr(li.produit, 'nom', '') or li.designation) or '') for li in lignes]
    panneaux = [li for li, c in classes if c == 'panneau']
    onduleurs = [{'produit': li.produit_id, 'designation': li.designation, 'quantite': int(li.quantite)}
                 for li, c in classes if c.startswith('onduleur')]
    return panneaux, panneaux_et_watt_lu(panneaux), onduleurs


def _electrique(design, onduleurs):
    """Chaînes, tension à froid, ratio : seulement pour l'option dont la
    conception électrique rangée porte l'onduleur ; sinon ``None``."""
    onduleur = ((design or {}).get('materiel') or {}).get('onduleur') or {}
    if not design or onduleur.get('designation') not in {o['designation'] for o in onduleurs}:
        return None, None, None
    chaines = design.get('chaines') or []
    longueurs = [c.get('nb_modules') for c in chaines]
    return ({'nombre': len(chaines), 'longueurs': longueurs, 'longueur': max(longueurs, default=None)},
            max((c.get('voc_froid_v') or 0 for c in chaines), default=None), design.get('ratio_dc_ac'))


def _bilan(resultat, option):
    """``(production, mensuelle, autoconso, couverture, économies, conso,
    forme, source de la forme)`` lus sur le bloc de l'option."""
    params = resultat.etude_params
    if resultat.marche == 'residentiel':
        bloc = (params.get('etude_horaire_sans') if option == 'sans' else None) or params.get('etude_horaire') or {}
        annuel = bloc.get('annuel') or {}
        return (annuel.get('production_kwh'), [m.get('production_kwh') for m in bloc.get('mois') or []],
                annuel.get('taux_autoconso_%s' % option), annuel.get('couverture_%s' % option),
                annuel.get('economie_%s_mad' % option), annuel.get('consommation_kwh'),
                bloc.get('occupation'), 'defaut' if bloc.get('profil_suppose') else 'moteur')
    etude = params.get('etude_ci') or {}
    source = (etude.get('option_avec') or {}) if option == 'avec' else etude
    bilan, economie = source.get('bilan') or {}, source.get('economie_ci') or {}
    mois = bilan.get('par_mois') or []
    return (bilan.get('production_kwh'), [m.get('production_kwh') for m in mois], bilan.get('taux_autoconso'),
            bilan.get('taux_couverture'), (economie.get('economie_annee1') or {}).get('total_mad'),
            sum(m.get('consommation_kwh') or 0 for m in mois) if mois else None,
            (etude.get('profil_charge') or {}).get('archetype'), 'moteur')


def _valeurs(resultat, lead, option, investissement):
    if resultat.marche == 'agricole':
        champ, params = resultat.etude_params.get('champ') or {}, resultat.etude_params
        return {'nb_panneaux': _v(champ.get('nb_panneaux'), 'panneaux'), 'puissance_kwc': _v(champ.get('kwc'), 'kWc'),
                'pompe': _v(resultat.materiel_pompage.get('pompe')),
                'variateur': _v(resultat.materiel_pompage.get('variateur_pompage')),
                'm3_jour': _v(params.get('m3_jour'), 'm³/jour')}
    from apps.ventes.compatibilites import froid_du_lead
    from apps.ventes.quote_engine.lignes_classement import kwc_des_lignes
    from apps.ventes.quote_engine.pricing import payback_publiable
    panneaux, (nb, watt), onduleurs = _materiel(resultat, option)
    chaines, tension, ratio = _electrique(resultat.conception_electrique, onduleurs)
    froid = froid_du_lead(lead)
    production, mensuelle, autoconso, couverture, economies, conso, forme, source_forme = _bilan(resultat, option)
    payback = (payback_publiable(investissement, economies, stockage=option == 'avec')['payback_years']
               if investissement is not None else None)
    devis = resultat.lignes[0].devis if resultat.lignes else None
    return {
        'nb_panneaux': _v(nb, 'panneaux'), 'puissance_kwc': _v(kwc_des_lignes(panneaux, nb, watt, devis), 'kWc'),
        'module': _v(panneaux[0].designation if panneaux else None), 'onduleurs': _v(onduleurs),
        'nombre_onduleurs': _v(sum(o['quantite'] for o in onduleurs), 'onduleurs'),
        'chaines': _v(chaines, 'panneaux'), 'tension_froid': _v(tension, 'V'), 'ratio_dc_ac': _v(ratio),
        'temperature_froid': _v(getattr(froid, 'valeur_c', None), '°C',
                                'moteur' if getattr(froid, 'source', None) else 'defaut'),
        'production_annuelle': _v(production, 'kWh/an'), 'production_mensuelle': _v(mensuelle or None, 'kWh'),
        'autoconsommation': _v(autoconso, 'ratio'), 'couverture': _v(couverture, 'ratio'),
        'economies_annuelles': _v(economies, 'MAD/an'),
        'payback': _v(payback, 'ans', 'devis' if investissement is not None else 'moteur'),
        'consommation_annuelle': _v(conso, 'kWh/an'), 'forme_horaire': _v(forme, None, source_forme),
    }
