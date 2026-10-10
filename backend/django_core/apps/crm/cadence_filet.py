"""Filet de sécurité après réponse : prochaine étape, paliers sans réponse, visite à planifier, rappel FDA (SPL12, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import datetime
import logging

from django.utils import timezone

from core.dates import aujourd_hui_local

from . import cadence_config, stages
from .cadence_config import (
    CLE_APPEL_APRES_REPONSE,
    CLE_CONFIRMATION,
    CLE_DEBRIEF,
    CLE_DECIDER_SUITE,
    CLE_DERNIER_APPEL,
    CLE_DEVIS,
    CLE_DEVIS_MODIFIE,
    CLE_MESSAGE_CRENEAU,
    CLE_PLANIFIER,
    CLE_RAPPEL_CONVENU,
    cle_de,
    q_etape,
)
from .cadence_plan import (
    _lead_premier_argument,
    _recaler_file,
    _sous_verrou_du_lead,
    deplacer_echeance_etape,
    initialiser_plan_relance,
    materialiser_touche_suivante,
)
from .cadence_reperes import (
    VISITE_CADENCE,
    VISITE_ORDRE_FILET,
    _KINDS_MESSAGE,
    _canal_configure,
    _echeance_configuree,
    _jour_de_visite_configure,
    q_etape_moteur,
    q_visite,
)
from .models import Lead, LeadActivity, RelanceEtape

logger = logging.getLogger(__name__)


#: AGR530 — la note de l'étape « Planifier la visite » posée à la place du
#: devis pour un pompage au point d'eau inconnu.
NOTE_RELEVE_POINT_EAU = (
    'Relevé du point d’eau : niveau et débit inconnus — demandez d’abord une '
    'photo de la fiche du foreur ou de l’autorisation ABH ; sinon le '
    'technicien les mesure.')

#: AGR530 — les gestes de VISITE : après eux, la reprise pose le devis.
_CLES_GESTES_VISITE = (CLE_PLANIFIER, CLE_CONFIRMATION, CLE_DEBRIEF)


def _poser_releve_point_eau(lead, user):
    """AGR530 — pose « Planifier la visite » (clé ``CLE_PLANIFIER``) au lieu
    du devis quand ``devis_auto.releve_eau_manquant`` le dit, sa note disant
    pourquoi. ``None`` (la suite ordinaire s'applique) pour tout autre lead,
    une visite déjà effectuée ou un rendez-vous déjà calé."""
    from .devis_auto import releve_eau_manquant

    lead.refresh_from_db()
    if getattr(lead, 'visite_effectuee', False) or not releve_eau_manquant(
            lead):
        return None
    etape = poser_filet_visite_a_planifier(lead, user)
    if etape is None:
        return None
    etape.note = NOTE_RELEVE_POINT_EAU
    etape.save(update_fields=['note'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=(f'Étape « {etape.libelle} » posée automatiquement à la place du '
              f'devis — {NOTE_RELEVE_POINT_EAU}'))
    return etape


@_sous_verrou_du_lead(_lead_premier_argument)
def assurer_prochaine_etape_apres_succes(lead, user,
                                         libelle=None,
                                         avec_plan_devis=True,
                                         brouillon_compris=False,
                                         canal_touche=None,
                                         libelle_touche_close='',
                                         issue_touche_close='',
                                         demarrer_plan=True,
                                         cle=None,
                                         cle_touche_close=None):
    """QJ-INVARIANT (fondateur 07/09/2026) — un lead ACTIF ne reste JAMAIS
    sans prochaine étape : sa liste de relances ne se termine que par le
    parking Froid ou la signature.

    Appelée partout où un geste de relance peut laisser zéro touche ouverte
    (issue « joint »/« intéressé », étape générique traitée, refus, reprise
    d'un lead perdu). Suites possibles, dans cet ordre :

    * le lead a un devis ENVOYÉ encore relançable → le PLAN APRÈS-DEVIS
      démarre (idempotent par devis, ``initialiser_plan_relance``).
      RELANCE-SUITE (fondateur 08/09/2026, lead test1 aa) : un BROUILLON ne
      compte que si ``brouillon_compris`` — quand l'humain vient de cocher
      l'étape « préparer et envoyer le devis » (devis parti par WhatsApp hors
      ERP, statut resté brouillon : cas AR du 07/09). JAMAIS depuis une issue
      « joint » : le suivi de proposition vient APRÈS l'envoi du devis, pas
      après la première réponse du client (le 08/09, un brouillon jamais
      envoyé faisait sauter l'appel ET l'envoi du devis) ;
    * sinon, si la touche qui vient d'aboutir était un MESSAGE
      (``canal_touche`` WhatsApp/e-mail) → UNE étape « appeler le client »
      au prochain créneau d'appel : il a répondu, on l'appelle ;
    * sinon → UNE étape `generique` (``libelle``, par défaut « préparer et
      envoyer le devis ») à demain, au prochain créneau de la société.

    No-op dès qu'une prochaine étape existe déjà, ou que le lead est signé,
    au froid (le réveil s'en charge), perdu ou archivé. Renvoie l'étape
    posée (la première du plan) ou ``None``.

    CAD2 — ``demarrer_plan=False`` : le suivi de proposition peut être
    POURSUIVI (barreau suivant d'un plan déjà consommé, CAD1) mais JAMAIS
    DÉMARRÉ depuis son barreau 1. C'est le cas d'une étape de VISITE close :
    après un débrief, « Le PDF s'ouvre bien ? » serait un contresens — la
    suite est alors l'étape générique.

    PARAM-CADENCE (décision fondateur du 25/09/2026) — l'étape posée est une
    CLÉ du gabarit « Après l'appel (avant devis) » de Paramètres (``cle`` ;
    ``libelle`` n'est plus lu que pour retrouver la clé d'un libellé par
    défaut) : libellé, délai, canal, heure et gabarit de message viennent du
    barreau de la société (``cadence_config.config_cle``). La touche close est
    reconnue par sa clé (``cle_touche_close``, déduite de
    ``libelle_touche_close`` à défaut)."""
    from . import horaires

    if not getattr(lead, 'pk', None):
        return None
    # L'instance peut être périmée (même précaution que `cloturer_cadence`).
    lead.refresh_from_db(
        fields=['stage', 'perdu', 'is_archived', 'ne_plus_contacter'])
    if (lead.perdu or lead.is_archived
            or getattr(lead, 'ne_plus_contacter', False)):
        return None
    if lead.stage in (stages.SIGNED, stages.COLD):
        return None
    if lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).exists():
        return None
    # Frontière M3 : le devis du lead se lit via le sélecteur de ventes.
    from apps.ventes.selectors import dernier_devis_relancable_du_lead
    # ``avec_plan_devis=False`` (refus) : relancer la PROPOSITION que le
    # client vient de refuser serait un contresens — étape de décision
    # générique seulement.
    devis = (dernier_devis_relancable_du_lead(
                 lead, brouillon_compris=brouillon_compris)
             if avec_plan_devis else None)
    if devis is not None:
        # CAD1 — le filet ne REJOUE jamais un plan dont des barreaux sont
        # déjà CONSOMMÉS pour le MÊME devis. Il le POURSUIT : la suite d'une
        # touche 5 clôturée « intéressé » est la touche 6, jamais la touche 1.
        # Sans ce garde-fou, l'idempotence de `initialiser_plan_relance` — qui
        # ne porte que sur les touches OUVERTES (TREADMILL-1538) — laissait
        # repartir les dix barreaux depuis « maintenant », et le client qui
        # venait de se dire intéressé recevait « Le PDF s'ouvre bien ? ».
        # « Consommé » = traité par un humain (FAIT/SAUTÉE) : un plan ANNULÉ
        # par le moteur reste redémarrable, c'est tout l'objet de
        # TREADMILL-1538.
        consomme = dernier_barreau_consomme(lead, 'apres_devis', devis)
        if consomme is not None:
            suite = materialiser_touche_suivante(consomme, user)
            if suite is not None:
                # SUIVI I6 (30/09/2026) — ``materialiser_touche_suivante`` ne
                # touche ni ``Lead.relance_date`` ni le Calendrier : l'appelant
                # (``marquer_etape_relance``) les avait recalés AVANT ce filet,
                # sur « plus rien d'ouvert ». Sans ce recalage, la touche
                # reprise était ouverte et ``relance_date`` restait vide.
                _recaler_file(lead, user)
                return suite
        elif demarrer_plan:
            etapes = initialiser_plan_relance(
                lead, user, cadence='apres_devis', devis=devis)
            ouvertes = [e for e in etapes
                        if e.statut == RelanceEtape.Statut.A_FAIRE]
            if ouvertes:
                _recaler_file(lead, user)
                return ouvertes[0]
        # Plan déjà consommé pour CE devis → l'étape générique ci-dessous.
        # CAD2 — idem quand l'appelant interdit le DÉMARRAGE (étape de visite
        # close) : on poursuit, on ne rejoue jamais depuis le barreau 1.
    elif avec_plan_devis:
        # SUIVI E6 (30/09/2026) — aucun devis relançable dans l'ERP, mais un
        # suivi de proposition a DÉJÀ servi (devis parti hors ERP,
        # TREADMILL-1538) : on le POURSUIT depuis son dernier barreau
        # consommé, exactement comme CAD1 le fait pour un devis de l'ERP.
        # Sans cela, « Client joint » sur un barreau sans devis posait
        # « Préparer et envoyer le devis » À CÔTÉ du barreau suivant (deux
        # touches ouvertes), et clore « Question de prix » re-posait l'étape
        # devis au lieu de reprendre le suivi. Plan épuisé : l'étape
        # générique ci-dessous.
        consomme = (dernier_barreau_consomme(lead, 'apres_devis', None)
                    if _suivi_de_proposition_existe(lead) else None)
        if consomme is not None:
            suite = materialiser_touche_suivante(consomme, user)
            if suite is not None:
                # SUIVI I6 — même recalage que la reprise CAD1 ci-dessus.
                _recaler_file(lead, user)
                return suite
        elif brouillon_compris:
            # TREADMILL-1538 — cas AR intégral : « un devis parti hors ERP
            # compte aussi ». Aucun devis dans l'ERP, mais l'humain vient de
            # cocher « préparer et envoyer le devis » : le suivi de
            # proposition démarre SANS objet devis (les gabarits vivent très
            # bien sans lui — MRY13 omet toute phrase sans valeur réelle),
            # plutôt que de re-poser le même filet à l'infini. SUIVI E6 —
            # seulement si AUCUN barreau n'a été consommé : sinon le suivi
            # est poursuivi (ci-dessus), jamais rejoué depuis le barreau 1.
            etapes = initialiser_plan_relance(
                lead, user, cadence='apres_devis', depart=timezone.now(),
                devis=None)
            ouvertes = [e for e in etapes
                        if e.statut == RelanceEtape.Statut.A_FAIRE]
            if ouvertes:
                _recaler_file(lead, user)
                return ouvertes[0]
    # PARAM-CADENCE — l'étape à poser est une CLÉ (défaut : le devis).
    cle = (cle or (cle_de(RelanceEtape(libelle=libelle)) if libelle else '')
           or CLE_DEVIS)
    cle_close = (cle_touche_close if cle_touche_close is not None
                 else cle_de(RelanceEtape(libelle=libelle_touche_close or '')))

    def _actif(cle_palier):
        return cadence_config.config_cle(lead.company, cle_palier)['actif']

    if canal_touche in _KINDS_MESSAGE and _actif(CLE_APPEL_APRES_REPONSE):
        # RELANCE-SUITE — message répondu : on l'appelle, dès le prochain
        # créneau d'appel (maintenant si la fenêtre est ouverte). Palier
        # désactivé dans Paramètres : sauté, la suite est le devis.
        cle = CLE_APPEL_APRES_REPONSE
    # CAD102 — « il a écrit, puis il ne décroche plus » : avant de réclamer un
    # devis pour quelqu'un que personne n'a jamais eu au téléphone, on pose un
    # ou deux gestes rapprochés pour LE JOINDRE (voir
    # `_FILET_SANS_REPONSE_PALIERS`, bas de fichier). Chaque palier est une
    # étape de filet de plus, jamais un barreau du protocole, et il n'y en a
    # qu'UNE d'ouverte à la fois (CKP2). Un palier désactivé est SAUTÉ.
    palier = prochain_palier_sans_reponse(cle_close, issue_touche_close,
                                          _actif)
    if palier is not None:
        cle = palier
    if cle_close and cle == cle_close:
        # CEINTURE anti-tapis-roulant (TREADMILL-1538) : ne JAMAIS re-poser à
        # l'identique la touche qu'on vient de clore — « Fait » doit toujours
        # faire avancer. L'étape de DÉCISION prend le relais.
        # CAD3 — sauf si l'issue saisie est « à rappeler » : le client n'a rien
        # arbitré, il a demandé du temps. L'étape porte alors un libellé de
        # RAPPEL, jamais « perdu (motif) ou relance ultérieure ».
        cle = (CLE_RAPPEL_CONVENU if issue_touche_close == 'rappel'
               else CLE_DECIDER_SUITE)
    # AGR530 (D-AGR-4 côté cadence) — l'étape à poser serait le DEVIS, mais le
    # lead est AGRICOLE et un groupe HYDRAULIQUE de la règle « devis auto
    # prêt » manque (HMT/niveau, ou débit/besoin) : le devis ne se chiffre
    # pas. La suite est « Planifier la visite — relevé du point d'eau ».
    # Jamais après un geste de VISITE (« Ne veut plus de visite » : la reprise
    # pose le devis comme aujourd'hui), ni après une visite effectuée.
    if cle == CLE_DEVIS and cle_close not in _CLES_GESTES_VISITE:
        visite = _poser_releve_point_eau(lead, user)
        if visite is not None:
            return visite
    config = cadence_config.config_cle(lead.company, cle)
    # CAD102 — le recalage suit le CANAL de l'étape posée : un message se cale
    # sur la fenêtre des messages, un appel sur celle des appels (la pause du
    # vendredi ne vise que les appels). Aucune règle d'horaire n'est réécrite.
    quand = _echeance_configuree(lead, config)
    libelle = config['libelle']
    etape = RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence='generique', ordre=1,
        canal=_canal_configure(config), libelle=libelle, cle=cle,
        # CAD18 — l'étape de filet porte un GABARIT quand son barreau en a un
        # (« Appeler le client — il a répondu au message » : le lead le plus
        # chaud du portefeuille était le seul à perdre son script).
        template_cle=config['template_cle'],
        due_at=quand, due_date=quand.astimezone(horaires.CASABLANCA).date(),
        note='Posée automatiquement : aucune autre relance ouverte.')
    # ACRM37 — LE recalage unique : la file pointe la prochaine touche
    # ouverte (celle-ci, sauf si une plus proche existe déjà).
    _recaler_file(lead, user)
    # Note SYSTÈME (``user=None``, même motif que `arreter_cadence`) : poser
    # un rappel n'est pas AVOIR contacté le lead (garde QJ7).
    quand_local = quand.astimezone(horaires.CASABLANCA)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=(f'Étape « {libelle} » posée automatiquement pour le '
              f'{quand_local:%d/%m/%Y à %H:%M} — aucune autre relance '
              'ouverte.'))
    return etape


# ── VISITE-CADENCE — LE SUIVI COMMERCIAL RÉAGIT À LA VISITE ──────────────────
#
# Ordre fondateur du 15/09/2026. La visite technique se place APRÈS l'envoi du
# devis, comme outil de closing. Trois conséquences, et elles vivent ICI (pas
# dans les récepteurs, qui restent minces et se contentent d'appeler) :
#
#   * quand un RENDEZ-VOUS est pris, les messages génériques de relance se
#     TAISENT jusqu'après la visite — continuer à demander « le PDF s'ouvre
#     bien ? » à quelqu'un qui reçoit le technicien jeudi est le genre de
#     faute qui décrédibilise tout le suivi — et deux gestes utiles les
#     remplacent en attendant ;
#
#     AMENDEMENT FONDATEUR (15/09/2026) — ils se TAISENT, ils ne MEURENT PAS.
#     La première écriture de ce lot ANNULAIT la cadence après-devis : le lead
#     perdait sa place dans le protocole, et une visite qui n'aboutit pas
#     laissait un dossier sans suivi (ou, pire, exigeait un REDÉMARRAGE de
#     cadence — un client reprenant le plan au barreau 1 après avoir déjà reçu
#     neuf messages). On DÉCALE désormais : la touche pendante, tout ce qui la
#     suit, ET l'ancre de la cadence glissent jusqu'après le débrief. Le lead
#     garde sa POSITION EXACTE (même ordre, même libellé, même reste de plan) ;
#     si la visite ne donne rien, le suivi reprend tout seul là où il en était.
#     Aucun `initialiser_plan_relance` n'est appelé sur un lead qui a déjà des
#     étapes après-devis : il n'y a JAMAIS de restart.
#   * quand le technicien repart, le RESPONSABLE doit rappeler sous 24-48 h,
#     tant que la visite est fraîche ;
#   * le TEXTE LIBRE du terrain entre dans l'historique du lead : c'est
#     souvent la seule trace de ce que le client a dit sur place.
#
# Aucune de ces fonctions ne touche ``Lead.stage`` : le statut d'une visite est
# un layer DOCUMENT, jamais une étape de funnel (``STAGES.py`` intact).


def _lead_relancable(lead):
    """Vrai si l'on a le droit de poser une relance sur ce lead.

    Les trois refus de ``initialiser_plan_relance``, relus ICI parce que les
    étapes de visite ne passent pas par lui : un lead perdu, archivé ou « ne
    plus contacter » ne reçoit AUCUNE touche — même pour une visite qui aurait
    été calée avant la décision."""
    return not (getattr(lead, 'ne_plus_contacter', False)
                or getattr(lead, 'perdu', False)
                or getattr(lead, 'is_archived', False))


def _visite_a_venir(lead):
    """Vrai si une visite technique est DÉJÀ calée à une date non passée.

    Lecture cross-app par le SÉLECTEUR de l'app visites (frontière M3 : `crm`
    n'importe jamais ``apps.visites.models``). Best-effort — module absent ou
    en erreur ⇒ « on ne sait pas » ⇒ on répond NON, et le filet se pose : un
    rappel en trop vaut mieux qu'une visite jamais calée."""
    try:
        from apps.visites.selectors import visites_pour_lead

        aujourdhui = aujourd_hui_local().isoformat()
        return any(ligne['date_prevue'] and ligne['date_prevue'] >= aujourdhui
                   for ligne in visites_pour_lead(lead))
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning(
            'VISITE-CADENCE: visites du lead #%s illisibles',
            getattr(lead, 'pk', '?'), exc_info=True)
        return False


def _etape_visite_ouverte(lead, *cles):
    """L'étape de visite de clé ``cles`` encore À FAIRE sur ce lead, ou
    ``None`` — reconnue par sa CLÉ (ou son libellé par défaut, étape posée
    avant la clé), jamais par un libellé renommé."""
    return (lead.relance_etapes
            .filter(q_etape(*cles), statut=RelanceEtape.Statut.A_FAIRE)
            .order_by('due_date', 'pk')
            .first())


def _config_visite(lead, cle):
    """PARAM-CADENCE — le barreau « Visite technique » de la société."""
    return cadence_config.config_cle(lead.company, cle)


def _poser_etape_visite(lead, *, cle, ordre, quand, devis_id=None,
                        config=None):
    """Crée UNE étape de visite à la date LOCALE ``quand`` (un ``date``).

    Recalée sur la fenêtre d'appel/message de la société (MRY8), comme toute
    autre touche : confirmer une visite à 6 h du matin ne rendrait service à
    personne. IDEMPOTENTE par clé : une étape de la même clé déjà ouverte
    est DÉPLACÉE, jamais dupliquée — une re-planification ne doit pas laisser
    deux « Confirmer la visite » dans la file.

    PARAM-CADENCE — libellé, canal, heure et gabarit de message viennent du
    barreau « Visite technique » de la société (clé ``cle``) ; l'étape porte
    cette clé."""
    from . import horaires

    config = config or _config_visite(lead, cle)
    echeance = _jour_de_visite_configure(lead, config, quand)
    etape = _etape_visite_ouverte(lead, cle)
    if etape is not None:
        # COCKPIT-CONTRÔLE — recalage sur la nouvelle date de visite : un
        # déplacement du MOTEUR (l'origine suit, rien n'est compté).
        return deplacer_echeance_etape(etape, echeance)
    return RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence=VISITE_CADENCE, ordre=ordre,
        canal=_canal_configure(config), libelle=config['libelle'], cle=cle,
        template_cle=config['template_cle'],
        due_at=echeance,
        due_date=echeance.astimezone(horaires.CASABLANCA).date(),
        devis_id=devis_id,
        note='Posée automatiquement : visite technique planifiée.')


def poser_filet_visite_a_planifier(lead, user, *, devis_id=None):
    """Le client a dit OUI au principe de la visite : reste à caler la date.

    Une étape d'APPEL due AUJOURD'HUI — pas demain : un accord de principe se
    transforme en rendez-vous dans la foulée, sinon il refroidit. No-op si un
    rendez-vous est déjà calé (le client avait déjà sa date) ou si le lead
    n'est plus relançable. Renvoie l'étape posée, ou ``None``.

    Appelée deux fois pour UNE issue « visite acceptée » saisie sur une touche
    (décision fondateur du 24/09/2026) : par le récepteur d'issue MRY9, qui ne
    connaît pas la touche, puis par ``marquer_etape_relance``, qui la connaît.
    L'étape est UNE (idempotente par libellé) ; le devis de la touche lui est
    rattaché s'il lui manquait."""
    if not _lead_relancable(lead) or _visite_a_venir(lead):
        return None
    config = _config_visite(lead, CLE_PLANIFIER)
    etape = _poser_etape_visite(
        lead, cle=CLE_PLANIFIER, ordre=VISITE_ORDRE_FILET,
        quand=aujourd_hui_local() + datetime.timedelta(
            days=config['delai_jours']),
        devis_id=devis_id, config=config)
    if devis_id is not None and etape.devis_id is None:
        etape.devis_id = devis_id
        etape.save(update_fields=['devis'])
    _recaler_file(lead, user)
    return etape


def _suivi_de_proposition_existe(lead):
    """Un suivi de proposition a-t-il déjà existé pour ce lead (un barreau
    ``apres_devis`` du protocole, quel que soit son statut — hors gestes de
    visite) ? C'est la trace d'un devis parti HORS ERP : cocher « préparer et
    envoyer le devis » démarre le suivi sans objet devis (TREADMILL-1538)."""
    return (lead.relance_etapes.filter(cadence='apres_devis')
            .exclude(q_visite()).exists())


# ── AGR522 — DOSSIER DE SUBVENTION FDA : LE RAPPEL DES 3 MOIS ───────────────
#
# Guide FDA 2024 (p.22-23, tableau « Délais ») : « Demande de subvention —
# 3 mois à compter de la date de l'approbation préalable », après la
# RÉALISATION. Au passage à « accordé », une étape MANUELLE datée est posée
# pour le lendemain (filet hors gabarit — jamais une touche de cadence,
# CAD124). Ce délai n'est JAMAIS écrit au client.


#: Délai du Guide FDA 2024 (p.22-23) entre l'approbation préalable et la
#: demande de subvention.
DELAI_DEMANDE_SUBVENTION_MOIS = 3


def _ajouter_mois(jour, mois):
    """``jour`` + ``mois`` mois calendaires (jour ramené à la fin du mois)."""
    import calendar

    total = jour.month - 1 + mois
    annee, mois_cible = jour.year + total // 12, total % 12 + 1
    dernier = calendar.monthrange(annee, mois_cible)[1]
    return jour.replace(year=annee, month=mois_cible,
                        day=min(jour.day, dernier))


def libelle_rappel_subvention(approbation):
    """Le libellé de l'étape « délai FDA » pour une approbation préalable."""
    limite = _ajouter_mois(approbation, DELAI_DEMANDE_SUBVENTION_MOIS)
    return (f'Approbation préalable du {approbation:%d/%m} : la pose ET le '
            'dépôt de la demande de subvention doivent tenir avant le '
            f'{limite:%d/%m} (3 mois — Guide FDA 2024, p.22-23)')


#: ACRM45 (C-ACRM-040) — la CLÉ STABLE du rappel FDA : l'étape se retrouve
#: par elle, jamais par son libellé (qui porte la date d'approbation et
#: changeait donc à chaque correction de cette date — deux rappels ouverts).
CLE_RAPPEL_FDA = 'rappel_fda'

#: Le début du libellé d'avant ACRM45 (``cle`` vide) : une étape ouverte
#: posée avant la clé est ADOPTÉE (sa clé est posée), jamais doublée.
_PREFIXE_LIBELLE_RAPPEL_FDA = 'Approbation préalable du '


def _rappel_fda_ouvert(lead):
    """ACRM45 — l'étape « délai FDA » OUVERTE du lead (clé stable, ou
    libellé d'avant la clé), ou ``None``."""
    from django.db.models import Q

    return (lead.relance_etapes
            .filter(statut=RelanceEtape.Statut.A_FAIRE)
            .filter(Q(cle=CLE_RAPPEL_FDA)
                    | Q(cle='',
                        libelle__startswith=_PREFIXE_LIBELLE_RAPPEL_FDA,
                        libelle__contains='Guide FDA'))
            .order_by('due_date', 'pk').first())


def poser_rappel_subvention(lead, user=None):
    """AGR522 — pose (ou retrouve) l'étape MANUELLE du délai FDA pour demain.

    ACRM45 — l'étape se retrouve par sa CLÉ STABLE (``CLE_RAPPEL_FDA``) :
      * « accordé » daté, aucune étape ouverte → elle est posée (demain) ;
      * la date d'approbation CHANGE → l'étape ouverte est DÉPLACÉE (libellé
        à la nouvelle date, échéance au prochain créneau de demain) — jamais
        un second rappel ;
      * le statut QUITTE « accordé » → l'étape ouverte est ANNULÉE (tracée).
    Puis la file est recalée (``_recaler_file``). Renvoie l'étape ouverte, ou
    ``None`` quand il n'y en a plus."""
    if lead is None:
        return None
    ouverte = _rappel_fda_ouvert(lead)
    accorde = (lead.dossier_subvention == Lead.DossierSubvention.ACCORDE
               and lead.dossier_subvention_le is not None)
    if not accorde:
        if ouverte is not None:
            ouverte.statut = RelanceEtape.Statut.ANNULEE
            ouverte.note = ('Annulée : le dossier de subvention n\'est plus '
                            '« accordé ».')
            ouverte.traite_le = timezone.now()
            ouverte.save(update_fields=['statut', 'note', 'traite_le'])
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body=('Rappel du délai FDA annulé : le dossier de subvention '
                      'n\'est plus « accordé ».'))
            _recaler_file(lead, user)
        return None
    from . import horaires

    libelle = libelle_rappel_subvention(lead.dossier_subvention_le)
    if ouverte is not None:
        if ouverte.libelle != libelle or ouverte.cle != CLE_RAPPEL_FDA:
            ouverte.libelle = libelle
            ouverte.cle = CLE_RAPPEL_FDA
            ouverte.save(update_fields=['libelle', 'cle'])
            quand = horaires.prochain_creneau_appel(
                timezone.now() + datetime.timedelta(days=1), lead.company,
                canal=ouverte.canal)
            ouverte = deplacer_echeance_etape(ouverte, quand)
        _recaler_file(lead, user)
        return ouverte
    etape = _poser_etape_de_filet(
        lead, libelle=libelle, canal=RelanceEtape.Canal.APPEL,
        vise=timezone.now() + datetime.timedelta(days=1),
        note='Posée automatiquement : dossier de subvention accordé — délai '
             'interne, jamais écrit au client.')
    if etape.cle != CLE_RAPPEL_FDA:
        etape.cle = CLE_RAPPEL_FDA
        etape.save(update_fields=['cle'])
    _recaler_file(lead, user)
    return etape


def dernier_barreau_consomme(lead, cadence, devis=None):
    """CAD1 — le barreau de PROTOCOLE le plus avancé que cette cadence a déjà
    consommé pour ce devis, ou ``None``.

    « Consommé » = traité par un humain, donc ``fait`` ou ``sautee``. Une
    touche ``annulee`` par le MOTEUR (arrêt de cadence) ne compte pas : un
    plan entièrement annulé doit rester redémarrable, c'est tout l'objet de
    TREADMILL-1538 — et c'est la différence qui permet à ce garde-fou d'être
    strict sans casser la reprise d'un dossier.

    Les étapes de FILET et les trois gestes de VISITE sont exclues : elles
    portent une cadence de protocole sans en être des barreaux (leur suite est
    décidée ailleurs), et les prendre pour le dernier barreau ferait naître un
    rang qui n'a rien à voir avec elles.
    """
    qs = lead.relance_etapes.filter(
        cadence=cadence,
        statut__in=(RelanceEtape.Statut.FAIT, RelanceEtape.Statut.SAUTEE),
    ).exclude(q_etape_moteur())
    if devis is not None:
        qs = qs.filter(devis=devis)
    else:
        qs = qs.filter(devis__isnull=True)
    return qs.order_by('-ordre', '-pk').first()


# ── CAD-A ── CAD3 — « à rappeler » sur une étape de filet la REPORTE ─────────


# ── CAD-A ── CAD102 — « il a écrit, puis il ne décroche plus » ───────────────
#
#: Les issues qui, sur une étape de FILET, veulent dire « je n'ai pas eu le
#: client ». ``non_joint`` porte aussi Répondeur et Occupé (CKP4 : la
#: précision part dans la note, aucune valeur d'énumération n'est ajoutée).
#: La chaîne VIDE ne vaut « pas joint » que sur une étape ÉCRITE, où l'écran
#: ne propose aucune issue : sur un appel, « Fait — passer à la suite » veut
#: dire que l'appel a eu lieu, et le devis est alors la bonne suite.
_ISSUES_SANS_REPONSE = ('non_joint',)

#: CAD102 — l'escalier du filet quand le client a RÉPONDU PAR ÉCRIT puis n'a
#: plus décroché. Chaque entrée : libellé clos → (libellé suivant, canal,
#: délai en jours), avec les issues qui déclenchent le palier.
#:
#: Deux gestes rapprochés, puis le devis. Le dernier appel n'a PAS d'entrée :
#: après lui, le filet reprend son cours normal (« préparer et envoyer le
#: devis »). C'est la garantie que l'escalier se termine — jamais une boucle.
#:
#: Les délais sont ceux du filet : le message part le jour même (prochain
#: créneau de MESSAGE), le dernier appel le lendemain (prochain créneau
#: d'APPEL) — aucun horaire nouveau n'est inventé, les fenêtres de la société
#: décident.
#:
#: Décision fondateur du 24/09/2026 — le DÉBRIEF de visite (sous ses deux
#: libellés) resté sans réponse monte sur la même dernière marche : « Rappeler
#: — dernier essai avant de chiffrer », demain. Il parquait le lead au Froid
#: (clôture MRY11), même sans devis. Le palier n'agit que quand le filet
#: s'exécute, c'est-à-dire quand RIEN d'autre n'est ouvert : un suivi de
#: proposition pendant (devis envoyé, plan repris après la visite) continue
#: seul, et un plan déjà servi est poursuivi avant tout palier (CAD1). Après
#: ce dernier essai, l'escalier retombe sur « préparer et envoyer le devis »
#: — jamais une boucle.
#:
#: PARAM-CADENCE (25/09/2026) — l'escalier est écrit en CLÉS du gabarit
#: « Après l'appel (avant devis) » : libellé, canal et délai de chaque marche
#: viennent du barreau de la société. Un PALIER désactivé (ou supprimé) dans
#: Paramètres est SAUTÉ : la chaîne passe à la marche suivante
#: (``_MARCHE_APRES_PALIER``), puis, au bout, au devis — jamais une boucle.
_PALIER_DEBRIEF_SANS_REPONSE = {
    'issues': _ISSUES_SANS_REPONSE,
    'suite': CLE_DERNIER_APPEL,
}
_FILET_SANS_REPONSE_PALIERS = {
    CLE_APPEL_APRES_REPONSE: {
        'issues': _ISSUES_SANS_REPONSE,
        'suite': CLE_MESSAGE_CRENEAU,
    },
    CLE_MESSAGE_CRENEAU: {
        # Une touche ÉCRITE se clôt sans issue : l'écran n'en propose pas.
        'issues': _ISSUES_SANS_REPONSE + ('',),
        'suite': CLE_DERNIER_APPEL,
    },
    # SUIVI E11 (30/09/2026) — le RAPPEL CONVENU (le client avait fixé
    # lui-même le moment) resté sans réponse : on ne chiffre pas encore, on
    # tente un dernier essai demain. Palier désactivé : sauté, comme les
    # autres (le devis).
    CLE_RAPPEL_CONVENU: {
        'issues': _ISSUES_SANS_REPONSE,
        'suite': CLE_DERNIER_APPEL,
    },
    CLE_DEBRIEF: _PALIER_DEBRIEF_SANS_REPONSE,
    CLE_DEVIS_MODIFIE: _PALIER_DEBRIEF_SANS_REPONSE,
}
#: La marche qui suit un palier SAUTÉ (``None`` : le filet reprend son cours
#: normal — « préparer et envoyer le devis »).
_MARCHE_APRES_PALIER = {
    CLE_MESSAGE_CRENEAU: CLE_DERNIER_APPEL,
    CLE_DERNIER_APPEL: None,
}


def prochain_palier_sans_reponse(cle_touche_close, issue_touche_close,
                                 est_actif):
    """CAD102 × PARAM-CADENCE — la CLÉ du palier suivant de l'escalier « ne
    décroche pas », ou ``None`` si cette clôture n'en déclenche aucun (ou si
    tous les paliers restants sont désactivés).

    ``est_actif(cle)`` dit si la société a gardé ce palier : un palier
    inactif est sauté, la marche suivante est essayée. Fonction PURE — le
    moteur passe la lecture qui seede (``config_cle``), l'écran la lecture
    qui n'écrit rien (``cles_actives``)."""
    palier = _FILET_SANS_REPONSE_PALIERS.get(cle_touche_close or '')
    if palier is None:
        return None
    if (issue_touche_close or '').strip() not in palier['issues']:
        return None
    cle = palier['suite']
    while cle is not None and not est_actif(cle):
        cle = _MARCHE_APRES_PALIER.get(cle)
    return cle


def _poser_etape_de_filet(lead, *, note, cle='', libelle='', canal=None,
                          vise=None, jours=None, a_la_date=None):
    """Pose UNE étape de FILET (cadence ``generique``, hors protocole) au
    prochain créneau de son canal — ou DÉPLACE celle encore ouverte : jamais
    deux fois la même étape dans la file.

    PARAM-CADENCE — avec ``cle`` (gabarit « Après l'appel (avant devis) ») :
    libellé, canal, délai (``jours`` l'impose quand l'appelant le connaît),
    heure et gabarit de message viennent du barreau de la société, et
    l'étape ouverte se retrouve par sa CLÉ. Sans clé (question de prix, hors
    gabarit) : ``libelle``/``canal``/``vise`` tels quels.

    SUIVI E10 — ``a_la_date`` (un instant AWARE, convenu DEVANT le client) :
    l'étape de clé ``cle`` est posée à CET instant, recalé sur la fenêtre de
    son canal (jamais née déjà échue), au lieu du délai du barreau."""
    from . import cadence_temps, horaires

    if cle:
        config = cadence_config.config_cle(lead.company, cle)
        if a_la_date is not None:
            canal_config = _canal_configure(config)
            # ACRM36 — le samedi de la clé (CAD43) tient aussi à la date
            # convenue ; l'heure cible n'y entre pas (l'heure est convenue).
            quand = horaires.prochain_creneau_appel(
                a_la_date, lead.company, canal=canal_config,
                samedi=bool(config.get('samedi_ok')))
            if quand < timezone.now():
                quand = cadence_temps.echeance_jamais_echue(
                    quand, company=lead.company, canal=canal_config,
                    samedi=bool(config.get('samedi_ok')))
        else:
            quand = _echeance_configuree(lead, config, jours=jours)
        libelle = config['libelle']
        canal = _canal_configure(config)
        template_cle = config['template_cle']
        ouvertes = lead.relance_etapes.filter(q_etape(cle))
    else:
        quand = horaires.prochain_creneau_appel(vise, lead.company,
                                                canal=canal)
        template_cle = ''
        ouvertes = lead.relance_etapes.filter(cle='', libelle=libelle)
    ouverte = (ouvertes.filter(statut=RelanceEtape.Statut.A_FAIRE)
               .order_by('due_date', 'pk').first())
    if ouverte is not None:
        # COCKPIT-CONTRÔLE — un filet DÉPLACÉ par le moteur : l'origine suit
        # l'échéance, aucun report n'est compté.
        return deplacer_echeance_etape(ouverte, quand)
    return RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence='generique', ordre=1,
        canal=canal, libelle=libelle, cle=cle, template_cle=template_cle,
        due_at=quand, due_date=quand.astimezone(horaires.CASABLANCA).date(),
        note=note)
