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

#: D-ACAL-109 / D-ACAL-110 : une conception désignée garde ses deux options et dit l'arrondi
#: (forme rangée changée : toute conception rangée est périmée et refaite par le filet).
VERSION_MOTEUR = 'moteur-unique-3'
CODE_LOCALISATION = 'localisation_inconnue'
MESSAGE_LOCALISATION = 'Ville inconnue du moteur : renseigner la ville ou le point GPS du lead.'
#: T4-X9-013 — le même refus pour un calepinage SANS lead : son entrée ne porte aucun lieu.
MESSAGE_LOCALISATION_SANS_LEAD = ("Sans lead, l'atelier ne calcule pas de conception : la production "
                                  'vient de la simulation de la pose.')
CODE_REFUS_MOTEUR = 'refus_moteur'
#: Relecture E6 — conception électrique non dessinée hors fiche incomplète (portails C&I).
MOTIF_NON_DESSINABLE = ('Conception électrique non calculée : aucun panneau à répartir en chaînes '
                        'ou configuration refusée par l\'onduleur (voir l\'étape Électrique).')
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
    #: Relecture E6 (acceptation) — POURQUOI la conception électrique manque
    #: (phrases françaises de ``electrical_service.motifs_fiche_incomplete`` :
    #: le champ de la fiche et où le remplir) ; ``[]`` quand elle est faite.
    motifs_electriques: list = field(default_factory=list)
    #: Relecture E6 B2 / m2 — la composition IMPOSÉE effectivement retenue (forme
    #: ``composition_imposee.CHAMPS_IMPOSES`` : pose ajustée, matériel désigné) et
    #: les suppositions des désignations écartées. Jamais servis tels quels.
    imposes_retenus: dict = field(default_factory=dict)
    designations_ecartees: list = field(default_factory=list)
    #: Relecture E6 M1 — niveau 15 : ``(calepinage_id, pose servie)`` dont la production
    #: sert de BASE aux études (posée sur le devis en mémoire avant elles), puis le
    #: productible servi retenu (``None`` : production de la ville). Jamais servis.
    pose_a_produire: object = None
    productible_pose: object = None
    #: ADEV155 (D-ACAL-108, niveau 15 seulement) — le lead SANS toit tracé dont le plan par
    #: défaut sert de BASE aux études (même chemin que la pose), puis ce que le plan suppose
    #: (pente, pose, production du toit supposé), ajouté aux suppositions. Jamais servis.
    plan_a_produire: object = None
    suppositions_plan: list = field(default_factory=list)
    #: Reste d'ACAL2020 — résidentiel : la forme 24 h (somme = 1) de la consommation que le
    #: moteur horaire a utilisée (occupation + équipements), servie par ``valeurs``.
    forme_horaire_24: object = None
    #: D-ACAL-109 / D-ACAL-110 (``conception/autre_option.py``) — l'option que la désignation
    #: a prise, l'autre option ``(option, ResultatConception)`` composée sans l'onduleur
    #: désigné, et les arrondis au module désigné. Jamais servis tels quels.
    option_designee: object = None
    autre_option: object = None
    arrondis: list = field(default_factory=list)

    def sortie(self):
        return {cle: getattr(self, cle) for cle in CLES_SORTIE}


def calculer_conception(lead, company, *, entrees=None, toit=None, imposes=None, investissement=None,
                        calepinage_id=None, souple=False):
    """La conception du ``lead`` (de ``company`` seulement), SANS ÉCRITURE.

    ``entrees`` : ``EntreesConception`` déjà lues (sinon ``entrees_pour``) ;
    ``toit`` : la pose servie (son ``empreinte`` entre dans l'empreinte ; son
    ``plafond_panneaux`` borne le résidentiel comme le ``plafond_toit`` du
    tunnel) ; ``imposes`` : composition imposée résidentielle (forme
    ``composition_imposee.imposition_du_corps``) ; ``investissement`` (MAD) :
    le prix de référence du payback. Un lead sans ville ni GPS ⇒ refus
    ``localisation_inconnue`` ; un refus du devis automatique ⇒ refus
    ``refus_moteur`` nommant son champ.

    ``calepinage_id`` (ADEV149/ADEV150, NIVEAU DE RÈGLES 15 seulement,
    ``REGLES_POSE_REELLE_2111``) : le toit tracé dont la pose sert. Pose
    ajustée à la main ⇒ son compte est IMPOSÉ (souverain, source ``pose``) ;
    pose complète ⇒ la production est celle de LA simulation de la pose
    (façade ``calepinage/services/pose_pour_moteur.py``, qui écrit le DÉTAIL
    dans ``Calepinage.resultat`` comme le bouton — seule écriture de ce
    chemin). Au niveau 14 courant : ignoré, chemin d'aujourd'hui.

    ``souple`` (relecture E6 B2, résidentiel) : ``imposes`` est le matériel DÉSIGNÉ À LA
    MAIN au calepinage (``porte_calepinage.designations_du_calepinage``, déjà filtré par
    le catalogue de vente). Sans compte de panneaux, la taille est celle que le moteur
    décide ; une désignation que la composition refuse n'est JAMAIS un refus de la
    conception : le matériel du moteur reste et une supposition le dit."""
    if getattr(lead, 'company_id', None) != getattr(company, 'pk', None):
        raise ValueError('Lead hors de la société : aucune conception.')
    porte, _conso = consommation_imposee(lead, company, calepinage_id, imposes)
    imposes = separer_consommation(imposes)[0]
    if porte is not lead:  # une consommation imposée : les entrées se relisent sur la copie
        lead, entrees = porte, None
    with reglages_lus_sans_creer(company):
        return _calculer(lead, company, entrees, toit, imposes, investissement, calepinage_id, souple)


def separer_consommation(imposes):
    """Reste d'ACAL2020 — ``(imposes sans consommation, consommation brute)``."""
    from apps.ventes.conception.consommation_imposee import separer
    return separer(imposes)


def consommation_imposee(lead, company, calepinage_id, imposes=None):
    """Reste d'ACAL2020 (``conception/consommation_imposee.py``) — ``(porteur, consommation |
    None)`` : ``imposes.consommation`` (validée) ou le relevé collé au calepinage, au NIVEAU DE
    RÈGLES 15 seulement (une conception rangée en change) ; l'aperçu, qui n'écrit rien, la
    pose lui-même avant l'appel (copie déjà portée : rendue telle quelle)."""
    from apps.ventes.conception import consommation_imposee as CI
    from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111, regles_au_moins

    brute = CI.separer(imposes)[1]
    imposee = (CI.valider(brute) if brute is not None and getattr(lead, '_consommation_imposee', None) is None
               and regles_au_moins(None, REGLES_POSE_REELLE_2111) else None)
    return CI.imposer(lead, company, calepinage_id, imposee=imposee)


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


def _calculer(lead, company, entrees, toit, imposes, investissement, calepinage_id=None, souple=False):
    from apps.ventes.conception.entrees import entrees_pour
    from apps.ventes.domain.regles_calcul import REGLES_COURANTES

    entrees = entrees or entrees_pour(lead, company, toit=toit)
    resultat = ResultatConception(
        marche=entrees.marche, entrees_utilisees=entrees.entrees_utilisees,
        niveau_regles=REGLES_COURANTES, empreinte=empreinte_conception(entrees, imposes))
    designes, imposes = (imposes, None) if souple and entrees.marche == 'residentiel' else (None, imposes)
    pose = pose_reelle(company, calepinage_id, entrees.marche)
    if pose is not None and pose['a_la_main'] and entrees.marche == 'residentiel':
        # ADEV150 : la pose souveraine — son compte et le module qu'elle porte (si catalogue) ;
        # relecture E6 (optionnel) : un module DÉSIGNÉ à la main passe devant celui de la pose.
        imposes = dict(imposes or {}, nb_panneaux=pose['nb_panneaux'],
                       **({'panneau_produit_id': pose['module_produit']} if pose.get('module_produit') else {}))
    if calepinage_id:
        from apps.ventes.conception.porte_calepinage import designations_ecartees
        resultat.designations_ecartees = designations_ecartees(company, calepinage_id)
    if pose is not None and pose['complete']:
        resultat.pose_a_produire = (calepinage_id, pose)
    elif plan_par_defaut_ouvert(calepinage_id, entrees.marche):
        resultat.plan_a_produire = lead
    refus = refus_localisation(lead)
    if refus is None:
        calcul = {'residentiel': _residentiel, 'agricole': _agricole}.get(entrees.marche, _ci)
        refus = _calcul_et_repli(resultat, calcul, (lead, company, entrees), toit, imposes, designes)
    if refus is not None:
        resultat.etat, resultat.refus = 'refus', refus
        resultat.etude_params, resultat.lignes, resultat.conception_electrique = {}, [], None
        return resultat
    from apps.ventes.conception import valeurs as V
    from apps.ventes.compatibilites import froid_du_lead
    froid = None if entrees.marche == 'agricole' else froid_du_lead(lead)
    resultat.blocs = blocs_du_moteur(resultat.etude_params)
    from apps.ventes.conception.suppositions import suppositions_de
    resultat.suppositions = (suppositions_de(resultat, froid=froid) + resultat.designations_ecartees
                             + resultat.suppositions_plan)
    resultat.option_retenue, options = V.options(resultat)
    resultat.valeurs = {option: V.valeurs(resultat, option, investissement, froid=froid, company=company)
                        for option in options}
    from apps.ventes.conception.autre_option import ajouter_l_autre_option
    ajouter_l_autre_option(resultat, investissement, froid=froid, company=company)
    V.dire_l_impose(resultat, 'calepinage' if souple or (pose or {}).get('a_la_main') else 'saisie',
                    pose_a_la_main=bool((pose or {}).get('a_la_main')) and entrees.marche == 'residentiel')
    from apps.ventes.conception.consommation_imposee import dire
    dire(resultat, getattr(lead, '_consommation_imposee', None))
    return _sans_cles_interdites_partout(resultat)


#: Relecture E6 B2 — une désignation que la composition refuse (famille, phase…).
CODE_DESIGNATION_ECARTEE = 'designation_ecartee'


def _calcul_et_repli(resultat, calcul, porteur, toit, imposes, designes):
    """Le calcul du marché ; ``None`` ou le refus nommé. Relecture E6 B2 — le matériel
    désigné (``designes``) est d'abord imposé (compte complété par le moteur) ; si la
    composition le refuse, la conception est refaite SANS lui et une supposition dit
    pourquoi : une désignation ne rend jamais la conception refusée."""
    from apps.ventes.conception.porte_calepinage import SimulationEnCours
    from apps.ventes.domain.taille import AutoDevisError

    if designes:
        avec = dict(imposes or {}, **designes)
        try:
            calcul(resultat, *porteur, toit=toit, imposes=avec, completer=True)
            resultat.imposes_retenus = avec
            if resultat.marche == 'residentiel':  # D-ACAL-109 : l'autre option reste
                from apps.ventes.conception.autre_option import garder_l_autre_option
                garder_l_autre_option(resultat, calcul, porteur, toit, imposes, designes)
            return None
        except SimulationEnCours:
            raise
        except AutoDevisError as exc:
            resultat.option_designee, resultat.arrondis = None, []
            champ = 'onduleur_produit' if str(exc.field or '').startswith('onduleur') or (
                'panneau_produit_id' not in designes) else 'module_produit'
            resultat.designations_ecartees.append({
                'code': CODE_DESIGNATION_ECARTEE, 'champ': champ, 'valeur': None, 'source': 'defaut',
                'message': ('Le matériel désigné ne convient pas à cette installation (%s) : la conception '
                            "utilise le matériel choisi par le moteur. Changez la désignation à l'étape "
                            'Électrique.' % exc.message.rstrip('. '))})
    try:
        calcul(resultat, *porteur, toit=toit, imposes=imposes)
    except SimulationEnCours:
        raise
    except AutoDevisError as exc:
        return {'code': CODE_REFUS_MOTEUR, 'champ': exc.field or '', 'message': exc.message}
    resultat.imposes_retenus = dict(imposes or {})
    return None


def _compte_designe(lead, company, toit, imposes, dimensionner, scenario=None, arrondis=None):
    """Relecture E6 B2 — ``(imposes complétés, scénario)`` d'un matériel désigné sans
    compte de panneaux : la taille que le moteur DÉCIDE sans la désignation (la facture
    garde la main ; un module désigné d'une autre puissance garde la même puissance crête,
    au panneau près) ; le scénario suit l'onduleur désigné (hybride ⇒ avec batterie,
    réseau ⇒ sans), sinon la décision. Constat T4-X9-009 : la taille est décidée POUR ce
    scénario (l'option « avec batterie » a son propre optimum) — sans cela un hybride
    désigné rangeait l'option « avec » à la taille de l'option « sans ».

    D-ACAL-109 — ``scenario`` : l'option demandée (l'AUTRE option d'une conception
    désignée, module désigné seul). D-ACAL-110 — ``arrondis`` reçoit le passage du compte
    du moteur au compte du module désigné (``autre_option.arrondi``)."""
    from apps.ventes.conception.autre_option import arrondi
    from apps.ventes.conception.decisions import decider_taille_residentielle
    from apps.ventes.domain import resolution_catalogue as rc
    from apps.ventes.domain.taille import panneaux_pour_la_meme_puissance

    onduleur = (rc.entree_du_produit(company, imposes['onduleur_produit_id'])
                if imposes.get('onduleur_produit_id') else None)
    force = scenario or {rc.FAMILLE_HYBRIDE: 'avec', rc.FAMILLE_RESEAU: 'sans'}.get(
        getattr(onduleur, 'famille', None))
    decision = decider_taille_residentielle(lead=lead, company=company, scenario=force, plafond_toit=getattr(
        toit, 'plafond_panneaux', None), dimensionner=dimensionner)
    nombre, complets, porte = decision.panneaux, {}, False
    panneau = (rc.entree_du_produit(company, imposes['panneau_produit_id'])
               if imposes.get('panneau_produit_id') else None)
    watt = float(getattr(panneau, 'wc', None) or 0)
    if watt and abs(watt - float(decision.watt or 0)) >= 0.5:
        nombre, porte = panneaux_pour_la_meme_puissance(decision.kwc, watt), True
    if panneau is None:  # le module du moteur (sa puissance, par LE résolveur), jamais le défaut 710 Wc
        resolution = rc.resoudre_panneau(company, rc.vivier(company), wc=decision.watt)
        if resolution.statut == rc.STATUT_UNIQUE:
            complets['panneau_produit_id'] = resolution.produit.pk
    scenario = force if onduleur is not None or force else ('avec' if decision.avec_batterie else 'sans')
    if arrondis is not None and porte:  # D-ACAL-110 : le kWc change toujours, le compte parfois
        arrondi(arrondis, scenario, panneau, decision, nombre)
    return dict(imposes, nb_panneaux=nombre, **complets), scenario


def pose_reelle(company, calepinage_id, marche):
    """ADEV149 — la pose servie (façade du calepinage) quand la branche est OUVERTE :
    niveau de règles courant ≥ 15 (``REGLES_POSE_REELLE_2111``, activé par le
    fondateur), un toit tracé, un marché solaire ; sinon ``None`` (chemin d'aujourd'hui)."""
    from apps.ventes.domain import regles_calcul as RC

    if not calepinage_id or marche == 'agricole' or RC.REGLES_COURANTES < RC.REGLES_POSE_REELLE_2111:
        return None
    from apps.ventes.conception.porte_calepinage import pose_du_calepinage
    pose = pose_du_calepinage(company, calepinage_id)
    return pose if pose and pose.get('nb_panneaux') else None


def plan_par_defaut_ouvert(calepinage_id, marche):
    """ADEV155 (D-ACAL-108, fondateur 25/11/2026 « Yes, with level 15 ») — la production d'un
    lead SANS toit tracé vient-elle du plan par défaut (``calepinage/services/plan_par_defaut.py``) ?
    Seulement quand le niveau de règles COURANT est ≥ 15 (``REGLES_POSE_REELLE_2111``, rendu
    courant par ACAL1001, jamais par cette tâche), aucun toit tracé, marché solaire (le pompage
    suit sa pose : D-ACAL-46). Au niveau 14 courant : fermé, chemin d'aujourd'hui au bit près."""
    from apps.ventes.domain import regles_calcul as RC

    return (not calepinage_id and marche_au_plan_par_defaut(marche)
            and RC.REGLES_COURANTES >= RC.REGLES_POSE_REELLE_2111)


def marche_au_plan_par_defaut(marche):
    """ADEV155 — LA règle de marché du plan par défaut (une seule place, lue par le moteur et
    par la liste ``remplir_conceptions --ecarts-sans-toit``) : tout marché solaire, jamais le
    pompage (il suit sa pose, D-ACAL-46)."""
    return marche != 'agricole'


def _materiel_des_lignes(resultat, devis=None):
    """``{module, onduleur}`` (identifiants produit) des lignes du moteur : l'onduleur de
    l'option « avec » d'abord. Le rôle RANGÉ d'abord (``domain.classe_ligne``), sinon les mots-clés."""
    from apps.ventes.domain.catalogue import classer_produit
    from apps.ventes.domain.classe_ligne import role_de_ligne

    classes = [(li, role_de_ligne(li, lambda li=li: classer_produit(
        getattr(li.produit, 'nom', '') or li.designation), devis=devis) or '')
               for li in resultat.lignes if li.type_ligne == 'produit' and not li.optionnelle]
    return {'module': next((li.produit_id for li, c in classes if c == 'panneau'), None),
            'onduleur': next((li.produit_id for li, c in sorted(
                classes, key=lambda paire: (paire[0].variante or '') != 'avec') if c.startswith('onduleur')),
                None)}


#: ADEV155 — le plan par défaut ouvert (niveau 15) mais non simulé : la supposition servie.
CODE_PLAN_NON_SIMULE = 'plan_par_defaut_non_simule'
MESSAGE_PLAN_NON_SIMULE = ('Production du toit supposé non simulée (%s) : la production standard de la ville est '
                           'utilisée — %s, ou tracer le toit au calepinage.')
GESTE_FICHE, GESTE_RELANCE = 'renseigner la fiche technique du produit dans Stock', 'relancer le calcul'


def _base_du_plan(resultat, devis, company):
    """ADEV155 — le productible du PLAN PAR DÉFAUT (porte ``productible_du_plan_par_defaut``)
    au kWc et au matériel des lignes du moteur, posé sur le devis EN MÉMOIRE avant ses études
    comme celui d'une pose : production, autoconsommation, économies et blocs en viennent tous.
    Non servi (plan refusé — météo injoignable comprise —, incomplet, fiche vide) ou en échec :
    la ville reste, et c'est DIT : ``absents`` (interne) ET une supposition SERVIE
    (:data:`CODE_PLAN_NON_SIMULE`, relecture lot 5 point 4 : ``absents`` n'est ni rangé ni
    servi, l'échec était muet à l'écran)."""
    from apps.ventes.conception.etudes_lignes import puissances_des_lignes
    from apps.ventes.conception.porte_calepinage import productible_du_plan_par_defaut

    try:
        servi, suppositions, motif = productible_du_plan_par_defaut(
            company, resultat.plan_a_produire, puissances_des_lignes(devis, resultat.lignes)[0],
            _materiel_des_lignes(resultat, devis))
    except Exception as exc:  # noqa: BLE001 — dite absente, la production de la ville reste (D-ENF22-BLE001)
        logger.warning('Plan par défaut non simulé (moteur unique)', exc_info=True)
        servi, suppositions, motif = None, [], 'erreur : %s' % type(exc).__name__
    if servi is None:
        resultat.absents['production_plan_par_defaut'] = motif
        fiche = 'fiche technique' in motif
        resultat.suppositions_plan = [{
            'code': CODE_PLAN_NON_SIMULE, 'champ': 'fiche_technique' if fiche else 'calepinage', 'valeur': None,
            'source': 'defaut', 'message': MESSAGE_PLAN_NON_SIMULE % (motif, GESTE_FICHE if fiche else GESTE_RELANCE)}]
        return
    resultat.productible_pose, resultat.suppositions_plan = servi, suppositions
    devis.productible_pose_moteur = servi


def _base_de_la_pose(resultat, devis, company):
    """Relecture E6 M1 (ADEV149, niveau 15, pose complète) — le productible de LA pose
    (porte ``productible_de_la_pose`` : le résultat rangé du calepinage s'il est à jour,
    sinon la simulation — en tâche seulement, ``SimulationEnCours`` dans une requête) pour
    le matériel des lignes du moteur, posé sur le devis EN MÉMOIRE avant ses études : la
    base de production de LA maison (``horaire/productible_pose.py``) le lit, donc
    production, autoconsommation, couverture, économies et blocs copiés au devis en
    viennent TOUS. Une lecture qui échoue autrement est DITE absente (production de la ville)."""
    if resultat.pose_a_produire is None:
        if resultat.plan_a_produire is not None:  # ADEV155, niveau 15 seulement
            _base_du_plan(resultat, devis, company)
        return
    from apps.ventes.conception.porte_calepinage import SimulationEnCours, productible_de_la_pose

    calepinage_id, _pose = resultat.pose_a_produire
    materiel = _materiel_des_lignes(resultat, devis)
    try:
        servi = productible_de_la_pose(company, calepinage_id, materiel)
    except SimulationEnCours:
        raise
    except Exception as exc:  # noqa: BLE001 — dite absente, la production de la ville reste (D-ENF22-BLE001)
        logger.warning('Productible de la pose non lu (moteur unique)', exc_info=True)
        resultat.absents['production_pose'] = 'erreur : %s' % type(exc).__name__
        return
    resultat.productible_pose = servi
    devis.productible_pose_moteur = servi


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
    lead = apps.get_model('crm', 'Lead')(company=company, type_installation=marche or None)
    lead.porteur_calepinage = True  # T4-X9-013 : le refus de lieu le dit sans « du lead »
    return lead


def refus_localisation(lead):
    from apps.crm.selectors import ville_effective
    if ville_effective(lead) or (getattr(lead, 'gps_lat', None) is not None
                                 and getattr(lead, 'gps_lng', None) is not None):
        return None
    sans_lead = getattr(lead, 'porteur_calepinage', False)  # T4-X9-013 : jamais « du lead » sans lead
    return {'code': CODE_LOCALISATION, 'champ': 'ville',
            'message': MESSAGE_LOCALISATION_SANS_LEAD if sans_lead else MESSAGE_LOCALISATION}


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

    from apps.ventes.domain.regles_calcul import REGLES_COURANTES

    devis = Devis(**champs_du_brouillon(intention))
    # Ce que ``Devis.save`` poserait (``auto_now``) : la couche « devis » des
    # entrées C&I est datée de lui (``etude_ci._couche_devis``).
    devis.updated_at = timezone.now()
    # Relecture E6 M1 / M3(b) — le devis en mémoire porte le niveau de règles COURANT :
    # les branches gardées par ``regles_au_moins(devis, …)`` sont celles du devis réel.
    devis.regles_calcul = REGLES_COURANTES
    lignes = lignes_neuves(devis, specs, intention.company, avertissements=avertissements)
    return devis, DevisAuxLignes(devis, lignes), lignes


def _provenance(devis, contexte, intention):
    from apps.ventes.domain.etude_schema import PIPELINE
    from apps.ventes.domain.pipeline import estampille_de_provenance
    stamp = estampille_de_provenance(contexte, intention)
    if stamp is not None:
        _fusion(devis, PIPELINE, provenance=stamp)


def _residentiel(resultat, lead, company, entrees, *, toit, imposes, completer=False, scenario=None):
    """``_build_devis_auto_residentiel`` sans écriture : décision, contrôle à
    blanc, intention, étapes 1-4, lignes de l'écrivain, étapes 6-8. ``completer``
    (relecture E6 B2) : un matériel désigné sans compte reçoit celui du moteur ;
    ``scenario`` (D-ACAL-109) : l'option demandée de ce compte."""
    demande_option = scenario
    from apps.ventes.conception.decisions import decider_taille_residentielle, verifier_composition_residentielle
    from apps.ventes.domain import creation_auto_residentiel as R
    from apps.ventes.domain import etude_schema as es
    from apps.ventes.domain.creation_auto import cles_rapides
    from apps.ventes.domain.pipeline import cles_etude_de_composition, composer_l_intention, specs_de_composition
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    from apps.ventes.utils.company_settings import tva_standard

    taux, journal, imposition, scenario = tva_standard(company), {}, None, None

    def dimensionner(**kw):  # ADEV142 — la sortie du moteur horaire, gardée pour le devis de cette requête
        resultat.taille_moteur = R._panneaux_dimensionnement_horaire(**kw)
        return resultat.taille_moteur
    if imposes:
        from apps.ventes.domain.composition_imposee import _alerter, preparer_imposition
        demande = None
        if completer and not imposes.get('nb_panneaux'):
            imposes, demande = _compte_designe(lead, company, toit, imposes, dimensionner, scenario=demande_option,
                                               arrondis=resultat.arrondis)
            resultat.option_designee = demande
        imposition, alertes, _phase, _isole = preparer_imposition(company=company, lead=lead, imposes=imposes,
                                                                  scenario=demande)
        scenario = imposition.scenario
        for alerte in alertes:
            _alerter(journal.setdefault('alertes', []), alerte['code'], alerte['message'], alerte.get('champ'))
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
    _base_de_la_pose(resultat, devis, company)
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


def _ci(resultat, lead, company, entrees, *, toit, imposes, completer=False):
    from apps.ventes.conception.decisions import decider_ci, etude_params_creation_ci
    from apps.ventes.domain.creation_auto import alertes_journal_ci

    etude, lignes, scenario = resultat.decision_devis = decider_ci(lead=lead, company=company)
    params = etude_params_creation_ci(etude, mode=lead.type_installation, scenario=scenario)
    contexte = _lignes_du_moteur(resultat, lead, company, params, lignes)
    resultat.journal = {'alertes': alertes_journal_ci(etude, contexte)}


def _agricole(resultat, lead, company, entrees, *, toit, imposes, completer=False):
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
    _base_de_la_pose(resultat, devis, company)
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
        if bloc:  # une forme illisible est dite absente, jamais l'étude horaire
            _au_mieux(resultat, 'forme_horaire_24', lambda: setattr(
                resultat, 'forme_horaire_24', forme_horaire_24(contexte, kwc)))

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


def forme_horaire_24(devis, kwc):
    """Reste d'ACAL2020 — la forme 24 h (somme = 1) de la consommation du moteur horaire
    résidentiel : les douze jours types de ``etude_horaire.jours_types_annee`` (LA source des
    courbes de l'étude : silhouette d'occupation + équipements + Ramadan, appelée telle
    quelle sur les entrées du devis), pondérés par leurs jours. ``None`` sans les douze."""
    from apps.ventes.domain.entrees import entrees_depuis_devis
    from apps.ventes.etude_horaire import jours_types_annee, kwargs_moteur_horaire

    entrees = entrees_depuis_devis(devis)
    if entrees is None:
        return None
    arguments = {cle: valeur for cle, valeur in kwargs_moteur_horaire(entrees).items()
                 if cle not in ('tranches', 'charges_fixes_mad')}
    jours, _avertissements, _sources = jours_types_annee(kwc=kwc, **arguments)
    if not jours or len(jours) != 12:
        return None
    total = [sum(jour['conso_24h'][heure] * jour['jours'] for jour in jours) for heure in range(24)]
    somme = sum(total)
    return [round(valeur / somme, 6) for valeur in total] if somme > 0 else None


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
        resultat.motifs_electriques = E.motifs_fiche_incomplete(contexte)
        if resultat.motifs_electriques:
            return None
        if garde and not E.conception_electrique_dessinable(contexte):
            resultat.motifs_electriques = [MOTIF_NON_DESSINABLE]
            return None
        return E.build_electrical_design(contexte, persister=False)
    except Exception as exc:  # noqa: BLE001 — le devis l'aurait avalée : dite absente (D-ENF22-BLE001)
        logger.warning('Conception électrique non calculée (moteur unique)', exc_info=True)
        resultat.absents['conception_electrique'] = 'erreur : %s' % type(exc).__name__
        return None
