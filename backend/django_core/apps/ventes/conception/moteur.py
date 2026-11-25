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
from contextlib import contextmanager
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

VERSION_MOTEUR = 'moteur-unique-2'  # relecture E5 m4 : identifiants produit servis
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
    #: ADEV142 — résidentiel : ce que le moteur horaire a rendu à la décision
    #: (``taille.ResultatTaille``), ``None`` s'il n'a pas été appelé (taille
    #: demandée). Jamais rangé : le devis né dans la MÊME requête le relit.
    taille_moteur: object = None
    #: ADEV142 — C&I : ``(etude, lignes, scenario)`` de ``decider_ci`` ;
    #: agricole : la ``decider_agricole`` — jamais rangée, relue par le devis
    #: de la même requête (aucune seconde décision).
    decision_devis: object = None

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
    if getattr(lead, 'company_id', None) != getattr(company, 'pk', None):
        raise ValueError('Lead hors de la société : aucune conception.')
    with reglages_lus_sans_creer(company):
        return _calculer(lead, company, entrees, toit, imposes, investissement)


@contextmanager
def reglages_lus_sans_creer(company):
    """Relecture ADEV134 — ``TariffSettings.get`` / ``CompanyProfile.get``
    (``get_or_create``) rendent, le temps du calcul, la ligne existante sinon une
    instance NON enregistrée (``CompanyProfile.lire``) : aucune écriture.

    Relecture E4 B1 — l'empreinte du catalogue est lue dans le mémo de la
    requête ENGLOBANTE (une page de 50 leads la calcule une fois) puis reposée
    dans le mémo neuf de ce calcul."""
    from apps.parametres.models import CompanyProfile
    from apps.parametres.models_tariff import TariffSettings
    from apps.ventes.conception.societe import cle_memo_catalogue, empreinte_catalogue
    from core import request_cache

    catalogue = empreinte_catalogue(company)
    with request_cache.request_scope():
        request_cache.memoize(cle_memo_catalogue(company.pk), lambda: catalogue)
        request_cache.memoize(TariffSettings._cle_memo_id(company.pk), lambda: (
            TariffSettings.objects.filter(company=company).first() or TariffSettings(company=company)))
        request_cache.memoize(CompanyProfile._cle_memo_id(company.pk), lambda: CompanyProfile.lire(company))
        yield


def _calculer(lead, company, entrees, toit, imposes, investissement):
    from apps.ventes.conception.entrees import entrees_pour
    from apps.ventes.domain.regles_calcul import REGLES_COURANTES
    from apps.ventes.domain.taille import AutoDevisError

    entrees = entrees or entrees_pour(lead, company, toit=toit)
    resultat = ResultatConception(
        marche=entrees.marche, entrees_utilisees=entrees.entrees_utilisees,
        niveau_regles=REGLES_COURANTES, empreinte=empreinte_conception(entrees, imposes))
    refus = refus_localisation(lead)
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
    from apps.ventes.conception import valeurs as V
    from apps.ventes.compatibilites import froid_du_lead
    froid = None if entrees.marche == 'agricole' else froid_du_lead(lead)
    resultat.blocs = blocs_du_moteur(resultat.etude_params)
    from apps.ventes.conception.suppositions import suppositions_de
    resultat.suppositions = suppositions_de(resultat, froid=froid)
    resultat.option_retenue, options = V.options(resultat)
    resultat.valeurs = {option: V.valeurs(resultat, option, investissement, froid=froid) for option in options}
    return _sans_cles_interdites_partout(resultat)


def sans_cles_interdites(noeud):
    """Retire, à toute profondeur, toute clé d'achat ou de marge : la liste
    ``domain/etude_ci.py::CLES_INTERDITES`` (``prix_achat``, ``marge``) et leurs
    variantes (``prix_achat_ht``, ``marge_snapshot``). Seule définition du
    paquet (l'écrivain l'applique aussi à ce qu'il range)."""
    from apps.ventes.domain.etude_ci import CLES_INTERDITES

    if isinstance(noeud, dict):
        return {cle: sans_cles_interdites(valeur) for cle, valeur in noeud.items()
                if not any(str(cle).startswith(i) or i == 'prix_achat' and i in str(cle) for i in CLES_INTERDITES)}
    if isinstance(noeud, (list, tuple)):
        return [sans_cles_interdites(valeur) for valeur in noeud]
    return noeud


def _sans_cles_interdites_partout(resultat):
    """Tout ce que le résultat EXPOSE (les ``lignes``, instances non
    enregistrées, ne sont jamais sérialisées : l'écrivain n'en lit rien)."""
    for nom in ('valeurs', 'blocs', 'suppositions', 'entrees_utilisees', 'etude_params', 'journal',
                'conception_electrique', 'materiel_pompage'):
        valeur = getattr(resultat, nom)
        if valeur is not None:
            setattr(resultat, nom, sans_cles_interdites(valeur))
    return resultat


def empreinte_conception(entrees, imposes=None):
    """L'empreinte d'une conception : entrées (pose comprise), version du
    moteur, niveau de règles, composition imposée — égale ⇒ même calcul."""
    from apps.ventes.conception.entrees import _empreinte
    from apps.ventes.domain.regles_calcul import REGLES_COURANTES
    return _empreinte({'entrees': entrees.empreinte, 'version_moteur': VERSION_MOTEUR,
                       'niveau_regles': REGLES_COURANTES, 'imposes': imposes or {}})


def lead_du_calepinage(calepinage, company):
    """ADEV136 (Q3) — l'entrée d'un calepinage SANS lead : un lead NON
    ENREGISTRÉ (jamais sauvegardé) ne portant que ce que le calepinage sait
    d'une entrée du moteur, le marché de son devis lié. Rien n'est inventé :
    sans ville ni consommation, le moteur rend son refus nommé."""
    from django.apps import apps
    marche = getattr(calepinage.devis, 'mode_installation', None) if calepinage.devis_id else None
    return apps.get_model('crm', 'Lead')(company=company, type_installation=marche or None)


def refus_localisation(lead):
    from apps.crm.selectors import ville_effective
    if ville_effective(lead) or (getattr(lead, 'gps_lat', None) is not None
                                 and getattr(lead, 'gps_lng', None) is not None):
        return None
    return {'code': CODE_LOCALISATION, 'champ': 'ville', 'message': MESSAGE_LOCALISATION}


def blocs_du_moteur(etude_params):
    """ADEV135 — contrat ``blocs`` : le contenu COMPLET d'``etude_params`` tel
    que le devis automatique né de cette conception le porterait (blocs
    d'étude, ``profils_comparatifs``, ``puissance_kwc``, ``ville_calcul``,
    ``origine_conception``…), pour qu'un devis créé de la version rangée n'ait
    rien à recalculer ; jamais les notes vendeur ``journal_auto``."""
    return {cle: valeur for cle, valeur in etude_params.items() if cle != 'journal_auto'}


def _fusion(devis, proprietaire, **cles):
    # Fusion clé à clé EN MÉMOIRE (aucune écriture en base : le devis n'est
    # jamais enregistré par le moteur, ADEV133).
    from apps.ventes.domain.etude_schema import appliquer
    appliquer(devis, proprietaire=proprietaire, **cles)


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

    def dimensionner(**kw):  # ADEV142 — la sortie du moteur horaire, gardée pour le devis de cette requête
        resultat.taille_moteur = R._panneaux_dimensionnement_horaire(**kw)
        return resultat.taille_moteur
    decision = decider_taille_residentielle(
        lead=lead, company=company, scenario=scenario, imposition=imposition,
        plafond_toit=getattr(toit, 'plafond_panneaux', None), dimensionner=dimensionner)
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

    etude, lignes, scenario = resultat.decision_devis = decider_ci(lead=lead, company=company)
    params = etude_params_creation_ci(etude, mode=lead.type_installation, scenario=scenario)
    contexte = _lignes_du_moteur(resultat, lead, company, params, lignes)
    resultat.journal = {'alertes': alertes_journal_ci(etude, contexte)}


def _agricole(resultat, lead, company, entrees, *, toit, imposes):
    from apps.ventes.conception.decisions import decider_agricole
    from apps.ventes.domain.creation_auto_agricole import alertes_journal_agricole, etude_params_creation_agricole

    decision = resultat.decision_devis = decider_agricole(lead=lead, company=company)
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
