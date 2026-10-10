"""Moteur du plan de relance : échéances, plan, démarrage, arrêt, réveils (SPL11, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import datetime
import logging

from django.utils import timezone

from . import stages
from .cadence_config import CLES_APRES_CONTACT, est_etape
from .cadence_messages import (
    MOTIF_VALIDITE_SUBVENTION,
    _validite_selon_financement,
    lead_dossier_subvention_en_instruction,
    lead_en_attente_d_accord,
    lead_finance_a_credit,
    lead_financement_pro_declare,
)
from .cadence_reperes import (
    FIN_NOTE_REPORT,
    MOTIF_PARQUE_AU_FROID,
    OUTCOME_VISITE_ACCEPTEE,
    PREFIXE_NOTE_REPORT,
    _CLOTURE_PLAFOND,
    _CLOTURE_TAGS,
    _LIBELLES_FILET_HORS_GABARIT,
    _canal_effectif,
    _lead_porte_tag,
    est_etape_de_visite,
    q_visite,
)
from .fiche_funnel import _rang_funnel, avancer_stage_lead_vers, poser_tag_lead
from .leads_doublons import find_duplicates_by_contact
from .models import Lead, LeadActivity, RelanceEtape

logger = logging.getLogger(__name__)


def _verrouiller_lead(lead):
    """ACRM35 (C-ACRM-030) — pose un verrou de LIGNE sur ``lead``
    (``SELECT … FOR UPDATE``) dans la transaction en cours : deux gestes de
    cadence sur le MÊME lead (double clic, deux onglets, récepteur + clic)
    s'exécutent l'un APRÈS l'autre, et le second lit l'état écrit par le
    premier. À appeler sous ``transaction.atomic()``."""
    if lead is None or getattr(lead, 'pk', None) is None:
        return
    list(Lead._base_manager.select_for_update()
         .filter(pk=lead.pk).values_list('pk', flat=True))


def _sous_verrou_du_lead(lead_de):
    """ACRM35 — décorateur : exécute la fonction dans ``transaction.atomic()``
    APRÈS ``_verrouiller_lead`` sur le lead que ``lead_de(*args, **kwargs)``
    désigne. Les lectures d'idempotence de la fonction (touches ouvertes,
    cadences actives, ordres déjà pris) se font donc APRÈS le verrou : deux
    initialisations concurrentes ne créent qu'un plan."""
    import functools

    def decorer(fonction):
        @functools.wraps(fonction)
        def enveloppe(*args, **kwargs):
            from django.db import transaction
            with transaction.atomic():
                _verrouiller_lead(lead_de(*args, **kwargs))
                return fonction(*args, **kwargs)
        return enveloppe
    return decorer


def _lead_premier_argument(lead, *args, **kwargs):
    return lead


def sync_relance_activity(lead, user):
    """Garde UN seul système de rappel : la `relance_date` du lead pilote une
    activité « Relance » auto-gérée (records.Activity). On ne crée jamais deux
    rappels concurrents — le Calendrier continue d'afficher relance_date, qui
    EST l'échéance de cette activité.

    relance_date posée  → crée/maj l'activité Relance ouverte (échéance + owner).
    relance_date vidée  → clôt l'activité Relance ouverte s'il y en a une.
    Best-effort : n'échoue jamais l'enregistrement du lead.
    """
    try:
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Activity, ActivityType
        ct = ContentType.objects.get_for_model(lead.__class__)
        open_qs = Activity.objects.filter(
            content_type=ct, object_id=lead.id,
            auto_relance=True, done=False)
        if lead.relance_date:
            atype = (ActivityType.objects
                     .filter(company=lead.company, nom='Relance').first())
            if atype is None:
                atype = ActivityType.objects.create(
                    company=lead.company, nom='Relance', icone='📅',
                    ordre=40, est_systeme=True)
            act = open_qs.first()
            if act is None:
                Activity.objects.create(
                    company=lead.company, content_type=ct, object_id=lead.id,
                    activity_type=atype, auto_relance=True,
                    summary='Relance commerciale',
                    due_date=lead.relance_date,
                    assigned_to=lead.owner, created_by=user)
            else:
                act.due_date = lead.relance_date
                act.assigned_to = lead.owner
                act.save(update_fields=['due_date', 'assigned_to'])
        else:
            for act in open_qs:
                act.done = True
                act.done_at = timezone.now()
                act.done_by = user
                act.save(update_fields=['done', 'done_at', 'done_by'])
    except Exception:
        pass


# ── RELANCE FOUNDATION — plan de relance structuré (multi-touches) ──────────
#
# Distinct de ``sync_relance_activity`` ci-dessus (rappel UNIQUE piloté par
# ``Lead.relance_date``) : ce plan matérialise plusieurs touches successives
# (gabarit ``parametres.CadenceRelanceEtape``, ex. J+2/J+5/J+10/J+20/J+35) sur
# UN lead, chacune avec son propre canal SUGGÉRÉ et son propre statut. AUCUN
# envoi automatique (WhatsApp/e-mail) n'est jamais déclenché ici — ce sont des
# rappels VISUELS pour le commercial (panneau « Relances du jour »), jamais un
# message sortant.
def _refus_cadence(lead, user, raison):
    """Note chatter expliquant pourquoi AUCUNE cadence n'a été posée.

    Un refus silencieux est le pire des deux mondes : Meryem croit le lead
    relancé alors qu'il ne l'est pas. Le refus est donc toujours écrit.

    FG28/MRY19 — note SYSTÈME (``user=None``), jamais l'utilisateur qui a
    déclenché la création/l'initialisation : même motif que
    ``create_lead_depuis_ticket`` (ZSAV8). Le récepteur QJ7
    (``_avancer_stage_on_contact_activity``) ne fait avancer NEW → CONTACTED
    (et ne stampe ``first_contacted_at``) que sur un contact MANUEL
    (``instance.user is not None``) — un refus automatique de cadence n'est
    JAMAIS un premier contact, et posait pourtant CONTACTED + le stamp SLA
    dès la simple création d'un lead sans numéro exploitable."""
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f'Cadence de relance non initialisée : {raison}.')
    return []


#: MRY11 × MRY12 — les gabarits de la cadence « réveil » dépendent du DOSSIER.
#: Le gabarit seedé dit « reveil_a1 » (A1 du Guide : « vous aviez reçu un
#: devis chez nous ») à J30 pour tout le monde — faux, donc interdit, pour un
#: lead jamais chiffré (clôture de la cadence de contact). Un lead sans devis
#: reçoit M6 (« reveil_a2 ») à J30 ; à J60, tous reçoivent la dernière chance
#: (« reveil_a3 »). Seuls les barreaux encore au gabarit d'origine sont
#: adaptés : une clé personnalisée par le fondateur est respectée.
_REVEIL_GABARITS = {
    True: ('reveil_a1', 'reveil_a3'),    # dormant AVEC devis
    False: ('reveil_a2', 'reveil_a3'),   # jamais chiffré
}
_REVEIL_CLES_SEEDEES = frozenset({'reveil_a1', 'reveil_a2'})


def _adapter_gabarits_reveil(lead, etapes, *, rang_initial=0):
    """Réassigne, EN PLACE, les ``template_cle`` des touches « réveil » selon
    que le lead a déjà reçu une proposition ou non (lecture cross-app par le
    sélecteur ``ventes.lead_a_un_devis``). Best-effort : en cas d'erreur de
    lecture, le gabarit seedé reste tel quel.

    CKP2 — l'affectation se fait par RANG dans la partition, plus par
    consommation d'un itérateur sur la liste reçue : depuis que la cadence est
    réactive, la touche J+60 est matérialisée SEULE, des semaines après la
    J+30, et un itérateur reparti de zéro lui aurait redonné le message de la
    PREMIÈRE relance. ``rang_initial`` est son rang réel dans le gabarit."""
    from apps.ventes.selectors import lead_a_un_devis
    try:
        avec_devis = bool(lead_a_un_devis(lead))
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning('MRY11: lecture des devis du lead #%s impossible',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return
    cles = _REVEIL_GABARITS[avec_devis]
    for decalage, etape in enumerate(sorted(etapes, key=lambda e: e.ordre)):
        rang = rang_initial + decalage
        if etape.template_cle in _REVEIL_CLES_SEEDEES and rang < len(cles):
            etape.template_cle = cles[rang]


#: MRY4 — le gabarit « dimanche famille » du suivi après devis n'est PAS pour
#: tout le monde : le Guide v2.1 le réserve aux dossiers où la décision se
#: prend en famille, le dimanche. Posé sur tous, il envoyait un message
#: dominical inapproprié à des prospects qui décident seuls.
_TEMPLATE_DIMANCHE_FAMILLE = 'dimanche_famille'
_TEMPLATE_PREUVE_J4 = 'j4_preuve'


def _realisation_eligible(lead):
    """AGR514 — une réalisation éligible existe-t-elle pour ce lead ?

    Consomme le sélecteur de la fondation `parametres` (frontière respectée).
    Un catalogue illisible vaut « aucune » : jamais une preuve inventée."""
    try:
        from apps.parametres.selectors import realisation_pour_lead
        return realisation_pour_lead(lead) is not None
    except Exception:  # noqa: BLE001
        logger.warning('Preuve J4 : catalogue illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return False


_TAG_DECISION_A_PLUSIEURS = 'décision à plusieurs'


def _normaliser_depart(depart):
    """L'ANCRE de cadence, toujours un datetime AWARE (CKP2).

    Extrait de ``calculer_echeances_cadence`` pour que l'ancre ÉCRITE dans
    ``RelanceEtape.cadence_depart`` soit exactement celle depuis laquelle les
    échéances ont été calculées — deux normalisations parallèles auraient
    dérivé, et la touche J+5 matérialisée des semaines plus tard serait tombée
    ailleurs que là où l'aperçu l'avait annoncée."""
    from . import horaires

    if depart is None:
        return timezone.now()
    if not isinstance(depart, datetime.datetime):
        # Rétro-compat : un appelant historique passe une DATE. On la place à
        # l'ouverture de la fenêtre plutôt qu'à minuit (qui serait aussitôt
        # repoussé au lendemain par le recalage).
        return datetime.datetime.combine(
            depart, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
    if timezone.is_naive(depart):
        return timezone.make_aware(depart, datetime.timezone.utc)
    return depart


def calculer_echeances_cadence(lead, cadence, depart, *, gabarits=None):
    """Les ÉCHÉANCES d'une cadence, SANS RIEN ÉCRIRE :
    ``[(gabarit, échéance aware), …]`` dans l'ordre du gabarit.

    C'est le cœur de calcul d'``initialiser_plan_relance``, extrait pour que
    l'APERÇU du placement (MRY30) puisse DATER une cadence sans la
    matérialiser. L'aperçu créait auparavant les touches des 277 candidats
    dans une transaction annulée : plus de 20 s de calcul pour un écran dont
    le navigateur abandonne au bout de 20 s — les deux 499 lus dans nginx le
    07/09/2026.

    ``initialiser_plan_relance`` appelle CETTE fonction : les deux ne peuvent
    donc pas diverger — ce que l'aperçu annonce EST ce que l'application
    créera. C'était déjà l'intention du dry-run en transaction annulée ; c'en
    est la version qui ne coûte rien.

    Ne lit la base que pour le gabarit
    (``CadenceRelanceEtape.cadence_pour``, qui SEEDE la cadence à son premier
    usage — comportement pré-existant, assumé) et pour les horaires de la
    société. ``gabarits`` permet de réutiliser un gabarit déjà chargé et
    d'éviter cette lecture : un placement en lit trois, pas trois cents.
    """
    from datetime import timedelta

    from apps.parametres.models_relance import CadenceRelanceEtape

    from . import cadence_temps, horaires

    def _canal(gabarit):
        """Le canal de CETTE touche — `appel` par défaut, jamais deviné."""
        return _canal_effectif(gabarit)

    if gabarits is None:
        gabarits = CadenceRelanceEtape.cadence_pour(lead.company, cadence)
    if not gabarits:
        return []

    depart = _normaliser_depart(depart)

    # MRY5/MRY8 — l'ORIGINE des touches du jour même : le premier instant
    # réellement joignable à partir du départ. Sans elle, chaque touche J0
    # était recalée INDÉPENDAMMENT, et un lead arrivé la nuit ou le week-end
    # voyait ses trois premières touches (J0+0, J0+3 min, J0+2 h 30) écrasées
    # sur la MÊME minute d'ouverture — 08:30, 08:30, 08:30 : trois rappels
    # simultanés au lieu d'une séquence, et un « rappelé dans les cinq
    # minutes » qui ne voulait plus rien dire.
    # L'origine est celle du MESSAGE (07/09/2026) : la touche 1 du protocole
    # est le message d'identité, posé dès 08:30. Les écarts du protocole se
    # comptent donc à partir de là, et chaque touche est ENSUITE recalée sur
    # la fenêtre de SON canal — l'appel d'ouverture calculé à 08:33 tombe à
    # 09:00, le suivant (08:30 + 2 h 30) à 11:00.
    origine = horaires.prochain_creneau_appel(
        depart, lead.company, canal='whatsapp')

    # CAD43 × CAD19 — l'origine d'une touche qui a LE DROIT AU SAMEDI.
    # `origine` ci-dessus ignore le drapeau `samedi_ok` : pour un lead arrivé
    # le samedi, elle vaut déjà le lundi, et la touche marquée `samedi_ok`
    # repartait donc du lundi — le drapeau par touche de CAD43 ne servait
    # plus à rien dès que le lead lui-même arrivait un samedi (exactement le
    # cas qu'il est fait pour servir : le lead du vendredi soir / du samedi).
    # Deux origines, pas une : celle du protocole ordinaire, et celle des
    # touches à qui la société a explicitement ouvert le samedi. Rien n'est
    # ouvert pour les autres — `samedi_ok` est FAUX partout par défaut.
    origine_samedi = horaires.prochain_creneau_appel(
        depart, lead.company, canal='whatsapp', samedi=True)

    # CAD19 — L'ANCRE EST UNIQUE : c'est `origine`, pour TOUTES les touches.
    # Les touches du jour même partaient déjà d'elle, mais les autres
    # partaient de `depart`, l'instant BRUT d'arrivée. Un lead arrivé samedi
    # 11 h voyait donc J0, J+1 et J+2 s'écraser sur le même lundi : trois
    # jours de protocole en un, des touches qui NAISSENT en retard, et une
    # adhérence fausse. Le même défaut frappait `apres_devis`, dont le départ
    # est l'instant d'envoi du devis — un devis fini un vendredi soir empilait
    # J+1, J+2 et J+3 sur deux jours. Les délais du protocole (J+N) ne
    # changent pas d'un jour : c'est le POINT ZÉRO depuis lequel on les compte
    # qui devient le premier instant réellement joignable.
    # EXCEPTION `reveil` : MRY30 rétrodate EXPRÈS son départ (créneau moins
    # `delai_jours`) pour que la touche J+30 tombe SUR le créneau d'étalement
    # qu'il vient de calculer. Recaler cette ancre-là sur l'ouverture
    # déplacerait le créneau dès que le départ rétrodaté tombe un week-end —
    # et ferait dérailler le quota de huit réveils par jour ouvré.
    ancre = depart if cadence == 'reveil' else origine

    # AGR514 (D-AGR-10) — J4 « preuve » n'est posée que s'il existe une
    # réalisation ÉLIGIBLE à montrer (sélecteur filtré par segment, AGR513).
    # Filtre sur une DONNÉE, pas sur un segment : le gabarit reste unique
    # (CAD124) et le trou de numérotation `ordre` est gardé. Calculé une seule
    # fois, et seulement si le gabarit porte cette touche.
    preuve_disponible = None

    echeances = []
    for gabarit in gabarits:
        if (getattr(gabarit, 'template_cle', '') or '') == _TEMPLATE_PREUVE_J4:
            if preuve_disponible is None:
                preuve_disponible = _realisation_eligible(lead)
            if not preuve_disponible:
                continue
        if ((getattr(gabarit, 'template_cle', '') or '')
                == _TEMPLATE_DIMANCHE_FAMILLE
                and not _lead_porte_tag(lead, _TAG_DECISION_A_PLUSIEURS)):
            # MRY4 — touche RÉSERVÉE aux dossiers étiquetés « Décision à
            # plusieurs ». Posée sur tous, elle envoyait un message dominical
            # « parlez-en en famille » à des prospects qui décident seuls.
            # La numérotation `ordre` garde son trou : elle vient du gabarit
            # de la société, pas d'un compteur local.
            continue
        # CAD32 — « WhatsApp uniquement » est saisi par le client, une fois,
        # explicitement, et la cadence ne le lisait NULLE PART : le prospect
        # qui a coché « ne m'appelez pas » recevait quand même les six appels
        # du protocole. Sur ce segment, un barreau d'appel naît en WhatsApp —
        # le canal change, rien d'autre : ni le nombre de touches, ni les
        # libellés, ni les délais, ni les jours.
        # CAD33 [TRANCHÉ 21/09/2026] — la préférence du client prime JUSQUE
        # sur le rendez-vous du dimanche : lui aussi naît en WhatsApp pour un
        # lead `whatsapp_only`. La fenêtre 16 h-19 h et l'unicité de la touche
        # ne changent pas — c'est le canal, et lui seul, qui suit le client.
        gabarit = cadence_temps.adapter_canal_au_lead(gabarit, lead)
        # CAD34 — le symétrique : sans WhatsApp joignable (aucun numéro
        # exploitable, ou une ligne FIXE), un barreau de message naît en
        # APPEL. La touche 1 du protocole est un WhatsApp : un lead arrivé
        # par téléphone n'avait sinon aucune cadence du tout.
        gabarit = cadence_temps.adapter_canal_au_numero(gabarit, lead)
        delai_minutes = getattr(gabarit, 'delai_minutes', 0) or 0
        heure_cible = getattr(gabarit, 'heure_cible', None)
        # CAD43 × CAD19 — cette touche-là compte ses jours depuis l'origine
        # qui lui ouvre le samedi. La cadence `reveil` garde son ancre
        # rétrodatée (MRY30) : son créneau d'étalement ne se déplace pas.
        samedi_ok = bool(getattr(gabarit, 'samedi_ok', False))
        depuis = (origine_samedi if (samedi_ok and cadence != 'reveil')
                  else ancre)
        depuis_jour_meme = origine_samedi if samedi_ok else origine
        if getattr(gabarit, 'dimanche_ok', False):
            # MRY4/MRY8 — une touche dominicale se PLACE sur un dimanche, elle
            # ne s'y recale pas. `prochain_creneau_appel` ne sait que borner un
            # instant dans la fenêtre de SON jour : l'« appel du dimanche »
            # calculé en J+5 depuis un mercredi tombait un lundi, et le seul
            # rendez-vous dominical du protocole n'avait jamais lieu un
            # dimanche.
            # CAD24 — l'HEURE CIBLE du gabarit est désormais HONORÉE quand
            # elle tombe dans la fenêtre dominicale 16 h-19 h : le réglage de
            # l'écran Paramètres s'enregistrait sans le moindre effet ici.
            # Hors de cette fenêtre (10 h 30 un dimanche n'existe pas), on
            # garde 16 h 30 — le milieu de la fenêtre, jamais son bord.
            heure_dimanche = (
                heure_cible
                if (heure_cible is not None
                    and horaires.DIMANCHE_DEBUT <= heure_cible
                    < horaires.DIMANCHE_FIN)
                else horaires.DIMANCHE_HEURE_DEFAUT)
            # CAD23 (TRANCHÉ 21/09/2026) — le dimanche le PLUS PROCHE du J+N
            # visé, AVANT ou après : le premier dimanche ≥ J+5 faisait dériver
            # le rendez-vous de J+5 (lead du mardi) à J+11 (lead du mercredi),
            # et la touche J+7 naissait ensuite déjà en retard. `plancher`
            # garantit qu'il ne précède jamais l'ancre de la cadence.
            echeance = horaires.dimanche_le_plus_proche(
                ancre + timedelta(days=gabarit.delai_jours), heure_dimanche,
                plancher=ancre)
        elif gabarit.delai_jours == 0 and heure_cible is None:
            # Les touches DU JOUR MÊME s'enchaînent depuis l'origine ouvrable,
            # pas depuis l'heure brute d'arrivée du lead : les écarts du
            # protocole (3 min, 2 h 30) sont ainsi PRÉSERVÉS quelle que soit
            # l'heure d'arrivée.
            echeance = depuis_jour_meme + timedelta(minutes=delai_minutes)
        else:
            echeance = depuis + timedelta(
                days=gabarit.delai_jours, minutes=delai_minutes)
            if heure_cible is not None:
                locale = echeance.astimezone(horaires.CASABLANCA)
                echeance = locale.replace(
                    hour=heure_cible.hour, minute=heure_cible.minute,
                    second=0, microsecond=0)
        echeance = horaires.prochain_creneau_appel(
            echeance, lead.company,
            dimanche=bool(getattr(gabarit, 'dimanche_ok', False)),
            # CAD43 — drapeau PAR TOUCHE, faux partout par défaut.
            samedi=samedi_ok,
            canal=_canal(gabarit),
            # CAD21 — l'heure imposée du gabarit SURVIT au passage au jour
            # ouvré suivant : l'« Appel 4 » de 18 h ne ressort plus à 09 h le
            # lundi. Jamais sur la touche dominicale : son heure est celle de
            # la fenêtre 16 h-19 h, et 10 h 30 un dimanche n'existe pas.
            heure_cible=(None
                         if getattr(gabarit, 'dimanche_ok', False)
                         else heure_cible))
        echeances.append((gabarit, echeance))
    # CAD20 — « jamais plus d'un appel ET d'un message par jour » était écrite
    # dans le référentiel des cadences et exécutée nulle part : le recalage sur
    # les jours ouvrés empile tout seul un J+13 dominical et un J+14 sur le
    # même lundi, et un délai retouché depuis Paramètres pouvait poser trois
    # appels le même jour. La garde s'exécute ICI, en dernier, sur la partition
    # complète — les trois gestes J0 et le rendez-vous dominical en sont
    # exemptés, et rien n'est ajouté, retiré ni réordonné.
    return cadence_temps.un_geste_par_jour(echeances, lead.company)


# ── CADX (fondateur 15/09/2026) — UNE SEULE cadence active par lead ──────────
#
# « Make sure no lead have two cadences in parallel, this should never
# happen. » Le point d'entrée UNIQUE de création (`initialiser_plan_relance`)
# arbitre par PRIORITÉ : démarrer une cadence plus prioritaire REMPLACE
# l'active (annulée moteur, motif tracé) ; une cadence de priorité inférieure
# ou égale est REFUSÉE — l'humain passe par « Arrêter la cadence » d'abord
# (recette du 08/09), et un job système (le placement « contact » du 11/09
# par-dessus un après-devis actif — lead #348) est neutralisé net.
_PRIORITE_CADENCE = {'reveil': 0, 'generique': 1, 'contact': 2,
                     # CAD128 — « deuxième affaire » a la MÊME priorité que
                     # la prise de contact : c'est le même moment du cycle
                     # (l'ouverture), pour un client acquis. Elle ne prend
                     # donc jamais la place d'un suivi après-devis en cours.
                     'deuxieme_affaire': 2,
                     'apres_devis': 3}


class CadenceActiveConflit(Exception):
    """CADX — une cadence au moins aussi prioritaire est déjà active."""


class CadenceRemplacementAConfirmer(Exception):
    """CAD51 — démarrer la cadence demandée ARRÊTERAIT une cadence en cours.

    Le moteur (devis envoyé, placement…) remplace en silence, c'est voulu :
    la cadence la plus prioritaire gagne (CADX). Mais un HUMAIN qui clique
    « Relancer la cadence » doit savoir ce qu'il tue : ce refus porte
    ``apercu`` (``apercu_remplacement_cadence``) — la ou les cadences qui
    seraient arrêtées et le nombre de touches ouvertes perdues — et n'est
    levé que sur demande (``exiger_confirmation``), tant qu'aucun motif
    d'arrêt n'accompagne la demande."""

    def __init__(self, message, *, apercu):
        super().__init__(message)
        self.apercu = apercu


def _libelle_cadence(cadence):
    """Libellé FR d'une cadence (``parametres.Cadence``), la clé sinon."""
    from apps.parametres.models_relance import Cadence
    return dict(Cadence.choices).get(cadence, cadence)


def apercu_remplacement_cadence(lead, cadence, *, devis=None):
    """CAD51 — ce que DÉMARRER ``cadence`` sur ``lead`` arrêterait, SANS rien
    écrire. ``None`` quand rien ne serait arrêté.

    Miroir EXACT des gardes de ``initialiser_plan_relance``, dans le même
    ordre : un lead ``ne_plus_contacter``/perdu/archivé n'arrête rien (refus
    en amont) ; un plan OUVERT de la même cadence (du même devis pour
    ``apres_devis``) est renvoyé tel quel (idempotence) ; une cadence active
    au moins aussi prioritaire est un REFUS (``CadenceActiveConflit``), pas un
    remplacement. Reste le cas qui tuait en silence : une cadence MOINS
    prioritaire est en cours.

    Renvoie ``{cadence, cadence_libelle, cadences_arretees,
    cadences_arretees_libelles, touches_ouvertes}`` — la forme publiée dans
    ``contract_samples/lead_relance_initialiser.json`` (``remplacement``)."""
    if (getattr(lead, 'ne_plus_contacter', False)
            or getattr(lead, 'perdu', False)
            or getattr(lead, 'is_archived', False)):
        return None
    ouvertes = lead.relance_etapes.filter(statut=RelanceEtape.Statut.A_FAIRE)
    # SUIVI E1 — même lecture que l'idempotence de `initialiser_plan_relance` :
    # une étape de VISITE (cadence `apres_devis`, hors protocole) n'est pas un
    # plan ouvert de cette cadence.
    meme = ouvertes.filter(cadence=cadence).exclude(q_visite())
    if cadence == 'apres_devis' and devis is not None:
        meme = meme.filter(devis=devis)
    if meme.exists():
        return None
    autres = ouvertes.exclude(cadence=cadence)
    actives = sorted(set(autres.values_list('cadence', flat=True)))
    if not actives:
        return None
    prio = _PRIORITE_CADENCE.get(cadence, 1)
    if any(_PRIORITE_CADENCE.get(c, 1) >= prio for c in actives):
        return None
    return {
        'cadence': cadence,
        'cadence_libelle': _libelle_cadence(cadence),
        'cadences_arretees': actives,
        'cadences_arretees_libelles': [_libelle_cadence(c) for c in actives],
        'touches_ouvertes': autres.count(),
    }


def message_remplacement_cadence(apercu):
    """CAD51 — la phrase qui NOMME ce qui sera arrêté (écran + refus 409)."""
    libelles = apercu['cadences_arretees_libelles']
    arretees = ('la cadence ' if len(libelles) == 1 else 'les cadences ') \
        + ', '.join(f'« {x} »' for x in libelles)
    n = apercu['touches_ouvertes']
    perte = ('1 touche ouverte sera annulée' if n == 1
             else f'{n} touches ouvertes seront annulées')
    return (f'Relancer la cadence « {apercu["cadence_libelle"]} » arrête '
            f'{arretees} en cours : {perte}. '
            "Confirmez, avec un motif d'arrêt.")


#: CAD55 — les deux phrases qui préviennent AVANT le lancement d'un suivi
#: « après devis » depuis la fiche (jamais découvert touche par touche).
MESSAGE_RELANCE_SANS_DEVIS = (
    'Aucun devis envoyé sur ce lead — les messages ne pourront pas citer la '
    'proposition.')
MESSAGE_RELANCE_PLUSIEURS_DEVIS = (
    'Plusieurs devis envoyés sur ce lead : lequel ce suivi doit-il citer ?')


def devis_envoyes_pour_relance(lead):
    """CAD55 — les devis ENVOYÉS du lead, toujours en attente de réponse, le
    PLUS RÉCENT d'abord : ceux qu'un suivi « après devis » peut citer.

    Même ensemble que ``ventes.selectors.dernier_devis_envoye_par_lead``
    (statut ``envoye``, ``date_envoi`` renseignée) — dont le premier élément
    est donc le « dernier devis envoyé ». Lecture via le sélecteur de ventes
    (frontière M3), jamais ``ventes.models``."""
    from apps.ventes.selectors import devis_envoyes_en_attente
    return list(
        devis_envoyes_en_attente(lead.company)
        .filter(lead_id=lead.pk).order_by('-date_envoi', '-id'))


def choix_devis_relance(devis_liste):
    """CAD55 — la ligne de choix « lequel ? » : ``[{id, reference,
    date_envoi}]`` (date LOCALE Casablanca, AAAA-MM-JJ). Aucun montant."""
    from . import horaires
    return [
        {'id': d.pk, 'reference': d.reference or '',
         'date_envoi': (timezone.localtime(d.date_envoi, horaires.CASABLANCA)
                        .date().isoformat() if d.date_envoi else None)}
        for d in devis_liste]


@_sous_verrou_du_lead(_lead_premier_argument)
def initialiser_plan_relance(lead, user, *, depart=None, cadence='contact',
                             devis=None, exiger_confirmation=False,
                             motif_remplacement=''):
    """Matérialise UNE cadence de relance sur ``lead`` depuis le gabarit de sa
    société (``parametres.CadenceRelanceEtape.cadence_pour``).

    IDEMPOTENT **PAR CADENCE** (MRY5) : un lead peut porter simultanément sa
    prise de contact et le suivi d'un devis ; l'ancienne idempotence globale
    « ce lead a déjà des étapes » les aurait confondus et un devis envoyé
    n'aurait jamais eu son plan. Pour ``apres_devis``, l'idempotence est en
    plus portée PAR DEVIS.

    ``depart`` est un datetime AWARE (défaut : maintenant). CAD19 — toutes les
    touches se comptent depuis l'ORIGINE (``prochain_creneau_appel(depart,
    canal='whatsapp')``, le premier instant réellement joignable), plus depuis
    l'instant brut d'arrivée : sans quoi un lead du week-end voyait J0, J+1 et
    J+2 s'écraser sur le même lundi. Seule la cadence ``reveil`` garde
    ``depart`` pour ancre (MRY30 le rétrodate exprès sur son créneau).
    Chaque touche vaut donc
    ``ancre + delai_jours + delai_minutes``, puis — si le gabarit porte une
    ``heure_cible`` — l'heure locale est REMPLACÉE par celle-ci, et enfin
    l'instant est recalé sur la fenêtre d'appel de la société
    (``horaires.prochain_creneau_appel``, MRY8) — sur la fenêtre de SON CANAL
    (07/09/2026) : un message dès ``message_heure_debut`` (08:30), un appel
    jamais avant ``appel_heure_debut`` (09:00). EXCEPTION pour les touches du
    JOUR MÊME (``delai_jours == 0`` sans ``heure_cible``) : elles s'enchaînent
    depuis l'ORIGINE ouvrable (``prochain_creneau_appel(depart,
    canal='whatsapp')``, l'ouverture du message d'identité) et non depuis
    l'heure brute d'arrivée, sans quoi un lead arrivé la nuit voyait ses trois
    premières touches écrasées sur la même minute d'ouverture. Une
    touche marquée
    ``dimanche_ok`` échappe à cette formule : elle est PLACÉE sur le premier
    dimanche atteignant ``depart + delai_jours``, à 16 h 30 (fenêtre
    dominicale 16 h-19 h du Protocole v3, ``horaires.prochain_dimanche``).
    ``due_date`` = date LOCALE de ``due_at`` : les filtres `scope` gardent
    leur grain jour.

    ÉCARTE (MRY4) le barreau ``dimanche_famille`` du suivi après devis quand
    le lead ne porte PAS l'étiquette « Décision à plusieurs » : le Guide v2.1
    le réserve aux dossiers décidés en famille.

    REFUSE (liste vide + note chatter) un lead ``ne_plus_contacter``, ``perdu``
    ou archivé — les trois cas où relancer serait une faute.

    Pose aussi ``Lead.relance_date`` sur l'échéance de la première touche (via
    ``sync_relance_activity``) : le Calendrier / « Ma file » reflètent la
    prochaine touche sans second système de rappel concurrent.

    Le CALCUL des échéances vit dans ``calculer_echeances_cadence`` (partagé
    avec l'aperçu du placement MRY30) : cette fonction ne fait qu'en
    matérialiser le résultat, si bien qu'aperçu et application ne peuvent pas
    dater deux choses différentes.

    CKP2 — MATÉRIALISATION RÉACTIVE (fondateur 2026-09-10) : cette fonction ne
    crée plus la cadence entière. Elle crée les touches DÉJÀ ÉCHUES (une
    cadence rétrodatée doit pouvoir montrer, et annuler, ce qui n'a pas eu
    lieu) PLUS la première encore à venir — et elle seule. Les suivantes
    naissent de l'ISSUE saisie, une par une
    (``materialiser_touche_suivante``). ``calculer_echeances_cadence`` reste la
    PARTITION complète : l'aperçu MRY30 annonce le plan entier, la
    matérialisation le suit. Chaque touche créée porte l'ancre
    ``cadence_depart`` pour que la J+5 tombe, des semaines plus tard, très
    exactement là où l'aperçu l'avait annoncée.

    CAD51 — ``exiger_confirmation`` (le chemin HUMAIN « Relancer la
    cadence ») : si démarrer cette cadence en ARRÊTAIT une autre, la demande
    est refusée (``CadenceRemplacementAConfirmer``, avant toute écriture)
    tant que ``motif_remplacement`` est vide ; avec un motif, l'arrêt passe
    par ``arreter_cadence`` comme un arrêt normal, sous ce motif. Sans
    ``exiger_confirmation`` (le moteur), le remplacement reste silencieux.

    Retourne la liste des ``RelanceEtape`` MATÉRIALISÉES de CETTE cadence
    (créées ou déjà existantes)."""
    from apps.parametres.models_relance import CadenceRelanceEtape

    from . import horaires

    if getattr(lead, 'ne_plus_contacter', False):
        return _refus_cadence(lead, user, 'lead marqué « ne plus contacter »')
    if getattr(lead, 'perdu', False):
        return _refus_cadence(lead, user, 'lead perdu')
    if getattr(lead, 'is_archived', False):
        return _refus_cadence(lead, user, 'lead archivé')

    deja = lead.relance_etapes.filter(cadence=cadence)
    if cadence == 'apres_devis' and devis is not None:
        deja = deja.filter(devis=devis)
    # TREADMILL-1538 (fondateur 15/09/2026) — l'idempotence porte sur le plan
    # OUVERT, jamais sur l'HISTORIQUE : des touches toutes closes (faites/
    # sautées/annulées) ne bloquent plus un (re)démarrage. C'est ce blocage
    # qui enfermait le lead TEST-16 : plan après-devis démarré en avance par
    # « préparer et envoyer », arrêté par « le client a répondu », puis
    # l'ENVOI RÉEL du devis restait muet (« déjà créé » → rien d'ouvert) et
    # le filet se re-posait à l'infini. Répare AUSSI « Arrêter la cadence »
    # puis « Relancer » (recette du 08/09), qui butait sur le même mur.
    # SUIVI E1 (30/09/2026) — seuls les BARREAUX du protocole sont un plan
    # ouvert : les gestes de VISITE (planifier, confirmer, débrief, devis
    # modifié) portent la cadence `apres_devis` sans en être. Les compter
    # rendait l'étape de visite comme « plan déjà en cours » et aucun suivi
    # de proposition ne démarrait.
    ouvertes_deja = list(
        deja.filter(_q_plan_ouvert())  # ACRM46 — prédicat partagé
        .order_by('ordre', 'due_date'))
    if ouvertes_deja:
        return ouvertes_deja

    # CADX — jamais deux cadences en parallèle (voir le bandeau plus haut).
    # CAD51 — `set` : le tri Meta (`ordre`, `due_date`) entre dans le SELECT
    # DISTINCT et répète la clé (« Cadence reveil, reveil arrêtée »).
    actives = sorted(set(
        lead.relance_etapes.filter(statut=RelanceEtape.Statut.A_FAIRE)
        .exclude(cadence=cadence)
        .values_list('cadence', flat=True)))
    if actives:
        prio = _PRIORITE_CADENCE.get(cadence, 1)
        bloquantes = sorted(
            c for c in actives if _PRIORITE_CADENCE.get(c, 1) >= prio)
        if bloquantes:
            raise CadenceActiveConflit(
                'Une seule cadence à la fois : la cadence '
                f'« {bloquantes[0]} » est déjà active sur ce lead — '
                'arrêtez-la d’abord (« Arrêter la cadence »).')
        motif_humain = (motif_remplacement or '').strip()
        if exiger_confirmation and not motif_humain:
            # CAD51 — jamais un arrêt silencieux depuis la fiche : on refuse
            # AVANT toute écriture, en nommant ce qui serait arrêté.
            apercu = apercu_remplacement_cadence(lead, cadence, devis=devis)
            if apercu is not None:
                raise CadenceRemplacementAConfirmer(
                    message_remplacement_cadence(apercu), apercu=apercu)
        if motif_humain:
            # CAD51 — l'arrêt confirmé est un arrêt NORMAL : même fonction,
            # le motif de l'humain en tête, le remplacement nommé à la suite.
            motif = (f'{motif_humain} (remplacée par la cadence '
                     f'« {_libelle_cadence(cadence)} »)')
        else:
            motif = f'remplacée par la cadence « {cadence} »'
        arreter_cadence(lead, user=user, motif=motif, cadences=actives)

    gabarits = CadenceRelanceEtape.cadence_pour(lead.company, cadence)
    if not gabarits:
        return []

    ancre = _normaliser_depart(depart)
    echeances = calculer_echeances_cadence(
        lead, cadence, ancre, gabarits=gabarits)
    # CKP2 (fondateur 2026-09-10, décision (3) « CADENCE RÉACTIVE ») — on ne
    # programme QUE le prochain geste. Les trois appels J0 créés d'avance
    # tombaient tous les trois dans la file même quand le premier avait suffi.
    # Sont matérialisées : les touches DÉJÀ ÉCHUES (une cadence rétrodatée —
    # reprise MRY23, placement MRY30 — doit pouvoir les annuler et montrer ce
    # qui n'a pas eu lieu) PLUS la première encore à venir, et elle seule. La
    # suite naît de l'ISSUE, dans ``materialiser_touche_suivante``.
    # EXCEPTION `reveil` : les deux réveils J30/J60 du PARKING (MRY11) ne sont
    # pas un protocole de gestes qui s'enchaînent — ce sont les deux alarmes
    # d'un dossier mis de côté, et la décision fondateur (3) vise les trois
    # appels J0 de la prise de contact, pas elles. `cloturer_cadence` refuse
    # d'ailleurs de clore une cadence `reveil` : elle n'a aucune mécanique de
    # clôture pour faire naître la seconde. Elles restent posées ensemble.
    maintenant = timezone.now()
    reactive = cadence != 'reveil'
    a_creer = []
    for rang, (gabarit, echeance) in enumerate(echeances):
        a_creer.append((rang, gabarit, echeance))
        if reactive and echeance >= maintenant:
            break
    # COCKPIT-CONTRÔLE — ``due_initial_at`` posée ICI : un ``bulk_create`` ne
    # passe pas par ``RelanceEtape.save``, qui la pose pour tout le reste.
    etapes = [
        RelanceEtape(
            company=lead.company, lead=lead, cadence=cadence,
            ordre=gabarit.ordre, due_at=echeance, due_initial_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=_canal_effectif(gabarit), libelle=gabarit.libelle,
            template_cle=getattr(gabarit, 'template_cle', '') or '',
            devis=devis, cadence_depart=ancre,
        )
        for _rang, gabarit, echeance in a_creer
    ]
    if not etapes:
        # Tous les barreaux de la cadence ont été écartés (cas limite : une
        # société dont la cadence ne contient QUE la touche réservée).
        return []
    if cadence == 'reveil':
        _adapter_gabarits_reveil(lead, etapes)
    RelanceEtape.objects.bulk_create(etapes)
    # SUIVI E1 — les barreaux de CETTE cadence, jamais les gestes de visite
    # qui partagent sa cadence.
    resultats = list(
        lead.relance_etapes.filter(cadence=cadence).exclude(q_visite())
        .order_by('ordre', 'due_date'))
    if devis is not None:
        resultats = [e for e in resultats if e.devis_id == devis.pk]

    premiere = resultats[0]
    quand = (premiere.due_at.astimezone(horaires.CASABLANCA)
             .strftime('%d/%m/%Y à %H:%M') if premiere.due_at
             else str(premiere.due_date))
    # FG28/MRY19 — note SYSTÈME (``user=None``), pas l'utilisateur qui a
    # déclenché l'initialisation : DÉMARRER une cadence n'est pas AVOIR
    # contacté le lead. Avec ``user`` posé ici, le récepteur QJ7 la traitait
    # comme un premier contact manuel et avançait NEW → CONTACTED (+ stampait
    # ``first_contacted_at``) dès la création — avant qu'un humain n'ait
    # réellement appelé/écrit. Même motif que ``_refus_cadence`` ci-dessus.
    # CKP2 — la note annonce le PLAN COMPLET (la partition, `len(echeances)`),
    # pas le nombre de lignes matérialisées : « 1 touche » sur un protocole de
    # onze aurait fait croire à un plan tronqué. Le plan est annoncé, la
    # matérialisation suit les issues.
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f'Plan de relance initialisé — cadence « {cadence} » '
             f'({len(echeances)} touche(s) prévue(s), première le {quand}).')

    # ACRM37 — LE recalage unique (``_recaler_file``) : une ancienne
    # ``relance_date`` déjà passée n'est plus conservée — le lead n'apparaît
    # plus « en retard » alors que sa première touche est à venir.
    _recaler_file(lead, user)
    # VALID1 (fondateur 07/09/2026) — le plan après-devis POSE la validité
    # de la proposition (si vide) : valable jusqu'à la DERNIÈRE touche du
    # plan — une date dérivée des cadences du fondateur, jamais inventée.
    # Les messages « validité de la proposition » cessent d'omettre leur
    # phrase. Frontière M3 : écriture via la façade services de ventes.
    if cadence == 'apres_devis' and devis is not None:
        try:
            from apps.ventes.services import poser_validite_devis
            # CKP2 — la validité se lit sur la DERNIÈRE échéance de la
            # PARTITION, jamais sur la dernière ligne matérialisée : depuis la
            # cadence réactive, celle-ci est la PREMIÈRE touche, et la
            # proposition aurait expiré le jour même de son envoi.
            derniere = echeances[-1][1].astimezone(horaires.CASABLANCA).date()
            # CAD57 — un PARTICULIER financé à crédit ne peut pas, légalement,
            # boucler dans cette fenêtre : la loi 31-08 (consommateur) impose
            # 10 jours de réflexion PUIS 7 jours de rétractation une fois
            # l'offre de crédit émise. CIQ510 — un PROFESSIONNEL n'est pas
            # visé par la loi 31-08 : c'est le délai d'instruction de sa
            # banque ou de l'organisme (financement pro déclaré) ou l'attente
            # d'un accord déclarée qui allonge — sans conclusion juridique.
            # Décision fondateur du 21/09/2026 : validité distincte et plus
            # longue (le réglage société), J+14 sinon.
            fin_du_plan = derniere
            derniere = _validite_selon_financement(lead, devis, derniere)
            # AGR523 — la note dit d'où vient une validité allongée par un
            # dossier de subvention en instruction (le crédit garde la sienne).
            # CIQ510 — idem pour une attente d'accord déclarée.
            if derniere == fin_du_plan or lead_finance_a_credit(lead) \
                    or lead_financement_pro_declare(lead):
                motif = 'fin du plan de suivi'
            elif lead_en_attente_d_accord(lead):
                motif = MOTIF_VALIDITE_ATTENTE
            elif lead_dossier_subvention_en_instruction(lead):
                motif = MOTIF_VALIDITE_SUBVENTION
            else:
                motif = 'fin du plan de suivi'
            if poser_validite_devis(devis, derniere):
                LeadActivity.objects.create(
                    company=lead.company, lead=lead, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'Validité de la proposition posée au '
                          f'{derniere:%d/%m/%Y} — {motif}.'))
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            pass
    return resultats


#: CKP2 — les issues qui ARRÊTENT la cadence (le récepteur MRY9
#: ``_arreter_cadence_on_outcome`` s'en charge, en ANNULANT les touches
#: restantes) et qui n'ont donc AUCUNE touche suivante à matérialiser : on a
#: joint la personne, elle est intéressée, ou elle refuse. Toute autre issue —
#: y compris l'absence d'issue sur un message ou un e-mail — fait naître le
#: geste suivant du protocole.
_OUTCOMES_ARRET_CADENCE = frozenset({'joint', 'interesse', 'refuse'})


#: Les issues qui disent « le client a été JOINT » — il a répondu, jusqu'à
#: accepter un rendez-vous. Ce sont elles qui font avancer le funnel (QJ7 :
#: Nouveau → Contacté ; QJ-FUNNEL : Devis envoyé → Relance) et qui confirment
#: une réponse pour l'annulation d'une touche (RLC1). Décision fondateur du
#: 24/09/2026, relevée au 25/09 : « visite acceptée » en fait partie — un
#: lead Nouveau qui acceptait la visite dès le premier appel restait Nouveau.
ISSUES_CLIENT_JOINT = ('joint', 'interesse', OUTCOME_VISITE_ACCEPTEE)

#: CKP2 × VISITE-CADENCE — les issues qui ne font naître AUCUNE touche
#: générique suivante. Les trois premières parce que la cadence s'arrête
#: (récepteur MRY9) ; « visite acceptée » parce que la suite n'est pas un
#: barreau du protocole mais un rendez-vous à caler.
#: CAD1 — cette table ne DÉCIDE plus : elle était trop grossière, puisqu'elle
#: rangeait « intéressé » parmi les arrêts sans regarder la cadence de la
#: touche, et faisait donc rejouer tout le suivi de proposition. La décision
#: vit désormais dans ``issue_fait_naitre_la_suite`` (bas de fichier), qui lit
#: l'issue ET la cadence. Le jeu reste exposé pour les écrans et les tests qui
#: nomment « les issues qui ne font naître aucun barreau générique ».
_OUTCOMES_SANS_MATERIALISATION = (
    _OUTCOMES_ARRET_CADENCE | {OUTCOME_VISITE_ACCEPTEE})


class RaisonSuite:
    """ACRM12 (C-ACRM-007) — POURQUOI ``materialiser_touche_suivante`` n'a
    rien fait naître. Seule ``FIN_GABARIT`` (aucun barreau ACTIF d'ordre
    supérieur, relu sur ``CadenceRelanceEtape.cadence_pour``) autorise
    ``marquer_etape_relance`` à CLORE la cadence (Froid + étiquette) ; les
    autres raisons laissent le filet poser la suite."""

    CREEE = 'creee'                  # une touche est née
    FIN_GABARIT = 'fin_gabarit'      # plus aucun barreau actif après celle-ci
    INDETERMINE = 'indetermine'      # ancre introuvable, panne : on ne sait pas
    DEJA_PRISE = 'deja_prise'        # le barreau suivant existe déjà
    NON_RELANCABLE = 'non_relancable'  # lead hors relance, filet, visite


def materialiser_touche_suivante(etape_close, user=None, *, avec_raison=False):
    """ACRM12 — ``avec_raison=True`` rend ``(etape | None, RaisonSuite.*)``
    au lieu de la seule étape (les appelants historiques sont inchangés).

    ACRM35 — sous ``transaction.atomic()`` + verrou du lead : la lecture
    d'idempotence (ordres déjà pris) se fait APRÈS le verrou, donc deux
    clôtures concurrentes ne font naître qu'UNE touche suivante. Appelée
    depuis une transaction, l'``atomic`` est un point de sauvegarde : une
    panne ici n'empoisonne pas la transaction de l'appelant."""
    from django.db import transaction
    with transaction.atomic():
        _verrouiller_lead(getattr(etape_close, 'lead', None))
        etape, raison = _materialiser_touche_suivante(etape_close, user)
    return (etape, raison) if avec_raison else etape


def _materialiser_touche_suivante(etape_close, user=None):
    """CKP2 — Fait naître LA touche suivante du gabarit, à partir d'une touche
    qu'on vient de CLORE sans avoir joint le client.

    C'est le cœur de la cadence RÉACTIVE (décision fondateur 2026-09-10) : on
    ne programme que le prochain geste, et c'est l'issue saisie (« pas de
    réponse ») qui programme celui d'après. Les trois appels J0 créés d'avance
    encombraient la file de Meryem de rappels que le premier appel rendait
    caducs.

    ÉCHÉANCE, deux régimes — c'est là que tout se joue :

      * gabarit ``delai_jours == 0`` (les touches du JOUR MÊME) → ancrée sur
        l'INSTANT DE CLÔTURE, plus l'écart intra-journée que le protocole
        prévoit entre les deux touches (``delai_minutes`` de la suivante moins
        celui de la close). Ancrer sur le départ serait faux : un appel
        d'ouverture passé à 15 h ne se rappelle pas « 2 h 30 après 08 h 30 »,
        c'est-à-dire dans le passé.
      * gabarit ``delai_jours > 0`` → ancrée sur le DÉPART DE CADENCE, comme
        aujourd'hui : le J+5 du protocole est un J+5 depuis l'arrivée du lead,
        pas depuis le dernier geste — sinon un dossier repris tardivement
        décalerait tout son plan et l'aperçu MRY30 mentirait.

    Dans les deux cas le recalage fenêtres/dimanche est celui des fonctions
    existantes (``horaires.prochain_creneau_appel`` / ``prochain_dimanche``,
    via ``calculer_echeances_cadence``) — aucune règle d'horaire n'est
    réécrite ici.

    IDEMPOTENTE : une touche déjà matérialisée pour cet ``ordre`` (et ce
    devis) n'est jamais recréée. Ne touche NI ``Lead.relance_date`` NI le
    chatter : c'est l'appelant (``marquer_etape_relance``) qui recale la file
    en une fois, comme il le faisait déjà.

    Rend ``(RelanceEtape créée | None, RaisonSuite.*)`` — ACRM12 : la raison
    d'une absence est TYPÉE (fin du gabarit, lead qu'on ne relance plus,
    barreau déjà pris, ancre introuvable) et seule la fin réelle du gabarit
    clôt la cadence. Un barreau DÉSACTIVÉ (celui de la touche close) n'est
    plus une fin : la suite part du premier barreau actif d'ordre supérieur."""
    from apps.parametres.models_relance import CadenceRelanceEtape

    from . import cadence_temps, horaires

    lead = etape_close.lead
    if (getattr(lead, 'ne_plus_contacter', False)
            or getattr(lead, 'perdu', False)
            or getattr(lead, 'is_archived', False)):
        return None, RaisonSuite.NON_RELANCABLE

    # Les étapes du FILET (MRY34 / QJ-INVARIANT) portent la cadence
    # `generique` mais ne sont PAS un barreau de protocole : ce sont des
    # étapes posées à la main par `assurer_prochaine_etape_apres_succes`, dont
    # la suite est décidée par le filet lui-même (plan après-devis si un devis
    # est parti, sinon une nouvelle étape générique). Leur faire naître le
    # « barreau 2 » du gabarit `generique` remplissait la file d'une touche
    # sans objet ET — parce qu'une prochaine touche existait alors — empêchait
    # le filet de démarrer le vrai suivi de proposition (cas AR du 07/09).
    # VISITE-CADENCE — les trois étapes du RENDEZ-VOUS portent la cadence
    # `apres_devis` (elles suivent bien la proposition) sans être des barreaux
    # du gabarit : leur `ordre` est hors plage exprès, mais on le dit ICI aussi
    # plutôt que de compter sur ce hasard — « confirmer la veille » n'a jamais
    # à faire naître « le PDF s'ouvre bien ? ».
    # PARAM-CADENCE — reconnues par leur CLÉ, jamais par leur libellé.
    if est_etape_de_filet(etape_close) or est_etape_de_visite(etape_close):
        return None, RaisonSuite.NON_RELANCABLE

    cadence = etape_close.cadence
    gabarits = CadenceRelanceEtape.cadence_pour(lead.company, cadence)
    if not gabarits:
        # Cadence sans gabarit (« generique », posée à la main par le filet) :
        # il n'y a pas de suite à faire naître — l'invariant « jamais un lead
        # actif sans prochaine touche » reste tenu par le filet lui-même.
        return None, RaisonSuite.NON_RELANCABLE
    # ACRM12 — la FIN du gabarit se lit sur les barreaux ACTIFS : aucun
    # barreau d'ordre supérieur à celui de la touche close.
    if not any(g.ordre > etape_close.ordre for g in gabarits):
        return None, RaisonSuite.FIN_GABARIT

    ancre = etape_close.cadence_depart
    if ancre is None:
        # Lignes d'avant CKP2 : l'ancre n'a jamais été écrite. La plus
        # ancienne échéance de la cadence en est la meilleure approximation
        # connue — jamais une valeur inventée.
        ancre = (lead.relance_etapes.filter(cadence=cadence)
                 .exclude(due_at=None).order_by('due_at')
                 .values_list('due_at', flat=True).first())
    if ancre is None:
        return None, RaisonSuite.INDETERMINE

    echeances = calculer_echeances_cadence(
        lead, cadence, ancre, gabarits=gabarits)
    rang = next((i for i, (g, _e) in enumerate(echeances)
                 if g.ordre == etape_close.ordre), None)
    if rang is None:
        # ACRM12 — le barreau de la touche close a été DÉSACTIVÉ (ou
        # renuméroté) : ce n'est pas une fin de gabarit. La suite part du
        # premier barreau actif d'ordre supérieur ; l'écart intra-journée se
        # lit alors depuis 0 (pas de barreau de référence).
        premier = next((i for i, (g, _e) in enumerate(echeances)
                        if g.ordre > etape_close.ordre), None)
        if premier is None:
            return None, RaisonSuite.FIN_GABARIT
        rang = premier - 1
        gabarit_close = None
    else:
        gabarit_close = echeances[rang][0]

    deja = lead.relance_etapes.filter(cadence=cadence)
    if etape_close.devis_id is not None:
        deja = deja.filter(devis_id=etape_close.devis_id)
    if etape_close.cadence_depart is not None:
        # TREADMILL-1538 — un plan REDÉMARRÉ (nouvelle ancre) vit sa vie :
        # les ordres consommés par une génération PRÉCÉDENTE (closes) ne
        # doivent pas étouffer la naissance de ses propres barreaux.
        deja = deja.filter(cadence_depart=etape_close.cadence_depart)
    ordres_pris = set(deja.values_list('ordre', flat=True))

    for suivant in range(rang + 1, len(echeances)):
        gabarit, echeance = echeances[suivant]
        if gabarit.ordre in ordres_pris:
            # IDEMPOTENCE : le barreau qui suit celui qu'on vient de clore
            # existe DÉJÀ (double appel, ou cadence rétrodatée dont plusieurs
            # touches échues ont été matérialisées d'un coup). On s'arrête —
            # SAUTER par-dessus pour en créer un plus loin ferait naître deux
            # touches au lieu d'une et casserait l'ordre du protocole.
            return None, RaisonSuite.DEJA_PRISE
        if (gabarit.delai_jours == 0
                and not getattr(gabarit, 'dimanche_ok', False)
                and getattr(gabarit, 'heure_cible', None) is None):
            ecart = ((getattr(gabarit, 'delai_minutes', 0) or 0)
                     - (getattr(gabarit_close, 'delai_minutes', 0) or 0))
            base = etape_close.traite_le or timezone.now()
            # ACRM36 — le samedi du barreau (CAD43) tient aussi ici.
            echeance = horaires.prochain_creneau_appel(
                base + datetime.timedelta(minutes=max(0, ecart)),
                lead.company,
                canal=_canal_effectif(gabarit),
                samedi=bool(getattr(gabarit, 'samedi_ok', False)))
        # CAD22 — une touche ne NAÎT JAMAIS déjà échue : après l'appel du
        # dimanche (posé entre J+5 et J+11), la J+7 du protocole naissait avec
        # une date passée et ne pouvait plus jamais être « à l'heure ». Elle
        # est ramenée au prochain créneau joignable — le J+N du protocole
        # n'est pas touché, seule cette échéance-ci l'est.
        # ACRM36 — samedi et heure cible du barreau transmis au recalage.
        echeance = cadence_temps.echeance_jamais_echue(
            echeance, company=lead.company,
            dimanche=bool(getattr(gabarit, 'dimanche_ok', False)),
            canal=_canal_effectif(gabarit),
            samedi=bool(getattr(gabarit, 'samedi_ok', False)),
            heure_cible=getattr(gabarit, 'heure_cible', None))
        etape = RelanceEtape(
            company=lead.company, lead=lead, cadence=cadence,
            ordre=gabarit.ordre, due_at=echeance, due_initial_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=_canal_effectif(gabarit), libelle=gabarit.libelle,
            template_cle=getattr(gabarit, 'template_cle', '') or '',
            devis_id=etape_close.devis_id, cadence_depart=ancre)
        if cadence == 'reveil':
            _adapter_gabarits_reveil(lead, [etape], rang_initial=suivant)
        etape.save()
        return etape, RaisonSuite.CREEE
    return None, RaisonSuite.FIN_GABARIT


def cloturer_cadence(lead, user, cadence):
    """MRY11 — Fin de cadence : dormance COLD, étiquette, réveils J30/J60.

    Un lead dont les touches sont toutes traitées sans réponse ne doit pas
    rester au milieu du pipeline à encombrer la vue de Meryem : il part au
    PARKING (COLD) avec une étiquette qui dit POURQUOI, et deux réveils
    J30/J60 qui le rendront un jour. C'est ce qui distingue « mis de côté »
    de « oublié ».

    Trois garanties :
      * COLD est un parking, PAS une perte — aucun motif de perte n'est posé
        ici ; `Lead.perdu` n'est jamais touché (décision humaine, MRY22) ;
      * `avancer_stage_lead_vers` respecte le rang du funnel : un lead déjà
        plus avancé (devis envoyé, signé) ne RECULE jamais vers COLD ;
      * la cadence `reveil` ne se clôture pas elle-même — sinon un lead
        réveillé sans réponse rentrerait dans une boucle de réveils infinie.

    Best-effort : ne lève jamais."""
    if cadence == 'reveil':
        return
    try:
        plafond = _CLOTURE_PLAFOND.get(cadence)
        if plafond is None:
            return
        # L'instance peut être PÉRIMÉE (le lead a bougé pendant la cadence,
        # exactement le cas que le plafond ci-dessous doit attraper) : on relit
        # l'étape courante avant d'en juger — même précaution que
        # `avancer_stage_new_vers_contacted`.
        if lead.pk:
            lead.refresh_from_db(fields=['stage', 'perdu', 'is_archived'])
        if lead.stage != stages.COLD and (
                _rang_funnel(lead.stage) > _rang_funnel(plafond)):
            # Le lead a PROGRESSÉ pendant la cadence (devis envoyé, signé) :
            # la touche restée ouverte ne doit pas le faire retomber.
            return
        avancer_stage_lead_vers(lead, user, stages.COLD)
        tag = _CLOTURE_TAGS.get(cadence)
        if tag:
            poser_tag_lead(lead, user, tag)
        # SUIVI E19 (30/09/2026) — une étape de FILET encore ouverte (cadence
        # ``generique`` : « Appeler le client », « Question de prix »,
        # « Rappeler le client (il l'a demandé) »…) BLOQUAIT les réveils :
        # ``initialiser_plan_relance`` levait ``CadenceActiveConflit`` (une
        # seule cadence à la fois, CADX), avalé plus bas — et le lead restait
        # au Froid SANS aucun réveil. Le dossier est parqué : ces étapes
        # n'ont plus d'objet, elles sont annulées (statut moteur, motif
        # tracé) AVANT de poser les réveils.
        arreter_cadence(lead, user=user, motif=MOTIF_PARQUE_AU_FROID,
                        cadences=['generique'])
        initialiser_plan_relance(
            lead, user, cadence='reveil', depart=timezone.now())
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'MRY11: clôture de cadence échouée (lead #%s, cadence %s)',
            getattr(lead, 'pk', '?'), cadence, exc_info=True)


def _q_plan_ouvert():
    """ACRM46 — LE prédicat « plan ouvert » (TREADMILL-1538) : une touche
    de cadence À FAIRE qui n'est pas un geste de visite. Partagé par
    ``initialiser_plan_relance`` (idempotence) et le placement des anciens
    leads (``deja_en_cadence``) : des touches toutes closes ne tiennent plus
    un lead."""
    from django.db.models import Q

    return Q(statut=RelanceEtape.Statut.A_FAIRE) & ~q_visite()


#: MRY6 — codes de garde dont le refus est TRACÉ en chatter. Les autres
#: (cadence déjà en place, lead qu'on ne relance plus…) restent muets : les
#: journaliser inonderait l'historique de chaque import.
#:
#: CAD103 (21/09/2026) — `deja_contacte` REJOINT les refus tracés. Le cas est
#: le plus courant de tous : la commerciale reçoit un appel, crée la fiche,
#: la passe en « Contacté » parce que c'est la vérité — et le dossier n'entre
#: dans AUCUN plan, sans une ligne pour le dire. Même silence pour l'API
#: publique partenaire, qui accepte une étape dans sa requête puis appelle la
#: cadence. Un refus muet est le pire des deux mondes.
#: CAD104 (21/09/2026) — `miroir` REJOINT les refus tracés. Odoo est le
#: cockpit où la commerciale travaille encore, et trois chemins donnaient
#: trois résultats sur la MÊME population : la cadence automatique refusait en
#: silence, l'écran « placer les anciens leads » ne filtre AUCUNE source, et
#: la commande de reprise passe, elle, par cette garde. L'asymétrie
#: automatique/manuel reste VOULUE (elle est datée et commentée) — ce qui
#: change est seulement qu'un dossier non suivi cesse de l'être en silence.
_GARDES_CADENCE_TRACEES = frozenset({'sans_numero', 'doublon',
                                     'deja_contacte', 'miroir'})

#: CAD103 — ce que le refus PROPOSE, en toutes lettres. Le protocole ne
#: change pas : c'est la touche 3 (le rappel du jour même) qui reprend un
#: dossier après un premier échange, et le placement à barreau intermédiaire
#: existe déjà (MRY30, « Placer les anciens leads » : il pose le plan depuis
#: une ancre rétrodatée et annule les touches déjà passées).
SUITE_DEJA_CONTACTE = (
    'démarrez le protocole à la touche 3 (le rappel du jour même) depuis '
    '« Placer les anciens leads »')


def _garde_cadence_contact(lead):
    """MRY6/MRY23 — Les six gardes de la cadence « contact », SANS AUCUNE
    écriture.

    Renvoie ``None`` si la cadence peut partir, sinon ``(code, motif)``. La
    partie PURE est isolée parce que deux appelants en ont besoin :
    ``demarrer_cadence_contact`` (qui écrit) et le DRY-RUN de la reprise
    MRY23, qui annonçait jusqu'ici un nombre de leads que ``--apply``
    n'atteignait jamais — il ne comptait que « pas de cadence existante »,
    ignorant numéro et doublon. Une simulation qui ne simule pas la vraie
    décision ne vaut rien."""
    if lead is None:
        return ('absent', 'lead absent')
    if lead.source == Lead.Source.ODOO_IMPORT_TEST:
        # CAD105 [TRANCHÉ 21/09/2026] — la synchronisation démarre la cadence
        # des leads NEUFS, avec EXACTEMENT les mêmes gardes que le site : un
        # lead né dans Odoo après la bascule tombe donc à travers cette garde
        # et affronte les suivantes (numéro, doublon, étape, inactivité).
        # « Neuf » se juge sur la date de création DANS ODOO (CAD119), jamais
        # sur l'instant de synchronisation — sans quoi les 930 fiches du
        # rattrapage historique seraient toutes « neuves ».
        from . import odoo_sync
        if not odoo_sync.lead_odoo_neuf(lead):
            # CAD104 — le motif DIT la suite : ce refus est désormais tracé,
            # et le libellé du modèle reconnaît lui-même qu'« Import Odoo »
            # n'est plus un test. Le placement à la main, lui, ne filtre
            # aucune source.
            return ('miroir',
                    'lead du miroir Odoo antérieur à la mise en service de '
                    'la synchronisation — la cadence automatique ne part pas '
                    'sur le rattrapage historique ; lancez-la depuis '
                    '« Placer les anciens leads » si ce dossier doit être '
                    'suivi')
    if lead.stage != stages.NEW or lead.first_contacted_at is not None:
        # CAD103 — le motif DIT la suite : ce refus est désormais tracé, et
        # une ligne qui constate sans proposer ne sert à rien.
        return ('deja_contacte',
                'lead déjà contacté ou hors étape « Nouveau » — '
                f'{SUITE_DEJA_CONTACTE}')
    if lead.perdu or lead.is_archived or lead.ne_plus_contacter:
        return ('inactif', 'lead perdu, archivé ou « ne plus contacter »')
    # CAD34 — on cherche le premier numéro EXPLOITABLE de la fiche :
    # `lead.whatsapp or lead.telephone` ne se repliait sur le téléphone que si
    # le champ WhatsApp était VIDE, jamais s'il était INUTILISABLE. Une ligne
    # FIXE ne bloque plus rien : la cadence démarre par un APPEL (CAD34).
    # L'erreur NOMME les champs à remplir (règle fondateur du 08/09/2026).
    from . import cadence_temps
    if not cadence_temps.numero_joignable(lead):
        return ('sans_numero',
                'aucun numéro exploitable — renseignez « Téléphone » ou '
                '« WhatsApp » sur la fiche')
    doublons = [
        autre for autre in find_duplicates_by_contact(
            lead.company, phone=lead.telephone, email=lead.email,
            exclude_pk=lead.pk, whatsapp=lead.whatsapp)  # ACRM32
        if not autre.is_archived and not autre.perdu]
    # CAD128 — un homonyme SIGNÉ n'est pas un doublon vivant : c'est un CLIENT
    # qui revient, le meilleur lead du portefeuille. Il sort de la garde
    # UNIQUEMENT couplé à la cadence courte « deuxième affaire »
    # (``demarrer_cadence_contact`` la lance à sa place) — jamais le protocole
    # contact, six appels sur quatorze jours sur quelqu'un qui a déjà acheté.
    if doublons and all(d.stage == stages.SIGNED for d in doublons):
        return ('deuxieme_affaire',
                'client déjà signé qui revient — cadence courte « deuxième '
                'affaire », jamais le protocole contact')
    if doublons:
        refs = ', '.join(f'#{d.pk}' for d in doublons[:3])
        return ('doublon',
                f'doublon possible de {refs} — fusionner ou lancer la '
                'cadence à la main')
    if lead.relance_etapes.filter(cadence='contact').exists():
        return ('deja_en_place', 'cadence de contact déjà en place')
    return None


def demarrer_cadence_contact(lead, *, user=None, origine=''):
    """MRY6 — Démarre la cadence « contact » à l'arrivée d'un lead VIVANT.

    Déclenchement EXPLICITE, appelé par chaque créateur de lead — JAMAIS un
    ``post_save(Lead)`` global : un signal se déclencherait aussi sur
    l'``dataimport``, sur l'import Odoo (930 leads miroir) et sur les tests,
    et inonderait la file de Meryem de milliers de touches qui ne
    correspondent à aucune demande réelle.

    Six gardes, dans cet ordre (``_garde_cadence_contact``, fonction PURE — la
    reprise MRY23 s'en sert pour que son DRY-RUN annonce exactement ce que
    ``--apply`` fera) :

      1. le lead vient bien d'une demande réelle (``source != ODOO_IMPORT_TEST``
         — le miroir Odoo n'en est pas une ; OS_NATIVE/SITE_WEB/META_LEAD_ADS
         le sont TOUTES : un lead Meta Ads ou site web mérite sa cadence
         exactement comme une saisie manuelle, cf. ``test_meta_lead_ads``) ;
      2. il est neuf (étape NEW) et jamais contacté ;
      3. ni perdu, ni archivé, ni « ne plus contacter » ;
      4. il porte un numéro exploitable — sans lui, aucune des touches
         (appel comme WhatsApp) n'est réalisable ;
      5. il n'est pas un DOUBLON d'un lead vivant : deux cadences sur la même
         personne, c'est deux commerciaux qui l'appellent le même jour ;
      6. aucune cadence `contact` n'existe déjà.

    Les deux refus RATTRAPABLES À LA MAIN (4 et 5) sont journalisés en chatter
    — un refus muet ferait croire que le lead est suivi. Les autres restent
    volontairement muets : les écrire inonderait l'historique de chaque import.

    Best-effort intégral : toute exception est journalisée, jamais propagée —
    une cadence en échec ne doit JAMAIS faire échouer la création du lead.
    Renvoie la liste des touches créées (vide si refus)."""
    try:
        garde = _garde_cadence_contact(lead)
        if garde is not None:
            code, motif = garde
            if code == 'deuxieme_affaire':
                # CAD128 — le client acquis prend la cadence COURTE. Les deux
                # fiches sont LIÉES par une note, jamais fusionnées d'office.
                return _demarrer_deuxieme_affaire(lead, user)
            if code in _GARDES_CADENCE_TRACEES:
                # MRY6/MRY10 — les deux refus « rattrapables à la main » sont
                # ÉCRITS : sans numéro exploitable ou sur un doublon vivant,
                # Meryem doit savoir que le lead n'est PAS suivi.
                return _refus_cadence(lead, user, motif)
            return []          # gardes muettes (import, déjà contacté…)
        return initialiser_plan_relance(
            lead, user, cadence='contact', depart=timezone.now())
    except CadenceActiveConflit as exc:
        # CADX — le refus est ÉCRIT (chatter) : Meryem voit pourquoi le lead
        # n'a pas reçu de nouvelle prise de contact.
        return _refus_cadence(lead, user, str(exc))
    except Exception:  # noqa: BLE001 — jamais vers l'appelant
        logger.warning(
            'demarrer_cadence_contact: échec sur le lead #%s (%s)',
            getattr(lead, 'pk', '?'), origine, exc_info=True)
        return []


def deplacer_echeance_etape(etape, quand, *, report_humain=False):
    """COCKPIT-CONTRÔLE (30/09/2026) — LE geste qui déplace l'échéance d'une
    étape OUVERTE, avec la règle de ses deux traces écrite UNE fois
    (``RelanceEtape.due_initial_at`` / ``nb_reports``) :

    * ``report_humain=True`` — un HUMAIN repousse CETTE étape (« Reporter »,
      « Mettre en veille », « À rappeler le… » / « Plus tard » qui la garde,
      rappel demandé au journal d'appel) : ``nb_reports`` + 1 (incrément
      ATOMIQUE, ``F()``) et l'échéance d'origine NE BOUGE PAS — c'est tout
      l'intérêt de la garder : un retard ne disparaît plus en silence ;
    * sinon — le MOTEUR déplace l'étape (ricochet d'un report sur la suite du
      plan, relances décalées autour d'une visite, recalage d'une
      confirmation ou d'un débrief sur la nouvelle date de visite, filet
      déplacé, redatage d'un suivi) : l'origine suit l'échéance du MÊME
      écart, rien n'est compté. Une étape sans origine connue prend la
      nouvelle échéance.

    ``quand`` est un datetime AWARE ; ``due_date`` reste sa date LOCALE
    Casablanca (MRY5). Écriture bornée aux colonnes en jeu
    (``save(update_fields=…)``). Rend l'étape, ``nb_reports`` relu."""
    from django.db.models import F

    from . import horaires

    ancien = etape.due_at
    origine = etape.due_initial_at
    etape.due_at = quand
    etape.due_date = quand.astimezone(horaires.CASABLANCA).date()
    champs = ['due_at', 'due_date']
    if report_humain:
        if origine is None and ancien is not None:
            # Une étape née sans trace d'origine garde au moins l'échéance
            # qu'on lui retire (défensif : la création et la reprise 0116 la
            # posent partout).
            etape.due_initial_at = ancien
            champs.append('due_initial_at')
        etape.nb_reports = F('nb_reports') + 1
        champs.append('nb_reports')
    else:
        etape.due_initial_at = (quand if origine is None or ancien is None
                                else origine + (quand - ancien))
        champs.append('due_initial_at')
    etape.save(update_fields=champs)
    if report_humain:
        etape.refresh_from_db(fields=['nb_reports'])
    return etape


def reporter_prochaine_touche(lead, user, quand, *, etape=None,
                              journaliser=True, compter_report=True):
    """MRY10 — « Rappelez-moi jeudi » : décale une touche ET sa suite.

    Décaler la SEULE touche du jour serait faux : les suivantes se
    téléscoperaient avec elle (« rappelez-moi dans 10 jours » ferait tomber
    trois touches la même semaine). Toutes les touches SUIVANTES de la même
    cadence glissent donc du MÊME delta — jamais réordonnées, jamais
    recalculées depuis zéro.

    CKP2 × VISITE-CADENCE (15/09/2026) — L'ANCRE GLISSE AUSSI. Depuis la
    cadence RÉACTIVE, les touches qui restent à venir n'existent pas encore :
    elles NAÎTRONT de l'issue saisie sur la touche courante, datées depuis
    ``cadence_depart`` (``materialiser_touche_suivante``). Décaler les seules
    lignes MATÉRIALISÉES laissait donc l'ancre au jour 0 : la touche suivante
    naissait à sa date d'origine — dans le passé, immédiatement en retard, et
    tout le report était annulé au premier geste. On applique le MÊME delta à
    ``cadence_depart`` des touches encore ouvertes : le lead garde sa POSITION
    exacte dans le protocole, l'ensemble du reste du plan glisse avec lui.

    ``quand`` est un datetime (ou une date) ; il est recalé sur la fenêtre de
    la société pour le CANAL de la touche déplacée (07/09/2026 : « rappelez-moi
    jeudi 8 h » vaut 08:30 pour un message, 09:00 pour un appel). ``etape``
    cible une touche précise ; sinon c'est la prochaine À FAIRE. Renvoie la
    touche déplacée, ou ``None`` s'il n'y en a aucune.

    ``journaliser=False`` supprime la SEULE note « Rappel demandé le … » :
    l'appelant en écrit une qui dit la vraie raison. C'est le cas de la
    suspension pour visite technique — écrire « rappel demandé » là où le
    client n'a rien demandé serait un mensonge dans l'historique, et deux
    notes pour un seul geste rendraient le chatter illisible.

    COCKPIT-CONTRÔLE (30/09/2026) — ``compter_report`` (défaut ``True``) :
    un geste HUMAIN qui repousse CETTE touche (« Reporter », « Mettre en
    veille », « À rappeler le… » qui garde l'étape, rappel demandé au
    journal d'appel, date de relance saisie sur la fiche) incrémente son
    ``nb_reports`` et lui laisse son échéance d'origine. Les déplacements
    décidés par le MOTEUR — touche du plan glissée derrière une touche
    signal, relances décalées autour d'une visite, rappel demandé par le
    CLIENT, placement de la touche qu'une réponse vient de faire naître —
    passent ``False`` : rien n'est compté et l'origine suit l'échéance. Les
    touches SUIVANTES décalées par ricochet ne sont jamais comptées (elles
    n'ont pas été repoussées une à une) : leur origine glisse du même écart
    (``deplacer_echeance_etape``).
    """
    from . import horaires

    cible = etape or _prochaine_touche_a_faire(lead)
    if cible is None:
        return None
    if not isinstance(quand, datetime.datetime):
        quand = datetime.datetime.combine(
            quand, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
    elif timezone.is_naive(quand):
        quand = timezone.make_aware(quand, datetime.timezone.utc)
    nouveau = horaires.prochain_creneau_appel(
        quand, lead.company, canal=getattr(cible, 'canal', None) or 'appel')

    ancien = cible.due_at
    delta = (nouveau - ancien) if ancien else None
    deplacer_echeance_etape(cible, nouveau, report_humain=compter_report)

    if delta:
        # CAD22 — le jeu des touches à décaler est CHRONOLOGIQUE, pas
        # seulement `ordre__gt`. L'ordre du PROTOCOLE et l'ordre des DATES
        # divergent : l'appel du dimanche (ordre 8, J+5) est placé sur le
        # premier dimanche atteignant J+5, donc parfois APRÈS la touche J+7
        # (ordre 9). Ne glisser que les `ordre__gt` laissait cette touche-là
        # sur place et réordonnait le plan en silence. On décale donc toute
        # touche ouverte qui vient après la reportée — par l'ordre OU par la
        # date —, du MÊME delta : aucune n'est réordonnée, aucune n'est
        # laissée derrière.
        from django.db.models import Q

        suivantes = lead.relance_etapes.filter(
            cadence=cible.cadence, statut=RelanceEtape.Statut.A_FAIRE,
            due_at__isnull=False,
        ).filter(
            Q(ordre__gt=cible.ordre) | Q(due_at__gte=ancien)
        ).exclude(pk=cible.pk)
        for suivante in suivantes:
            # Ricochet : jamais un report compté, l'origine glisse du même
            # écart (COCKPIT-CONTRÔLE).
            deplacer_echeance_etape(suivante, suivante.due_at + delta)
        # CKP2 — l'ANCRE des touches encore ouvertes glisse du même delta,
        # sans quoi le prochain barreau naîtrait à sa date d'origine (voir la
        # docstring). EN UNE REQUÊTE, avec ``F()`` : c'est un incrément pur
        # (jamais un lire-décider-écrire), donc rien à verrouiller. Sur une
        # ligne d'avant CKP2 (`cadence_depart` NULL) il n'y a rien à décaler :
        # la matérialisation réactive retombe alors sur son repli — la plus
        # ancienne échéance de la cadence, qui vient d'être décalée.
        from django.db.models import F

        lead.relance_etapes.filter(
            cadence=cible.cadence, statut=RelanceEtape.Statut.A_FAIRE,
            cadence_depart__isnull=False,
        ).update(cadence_depart=F('cadence_depart') + delta)
        if cible.cadence_depart is not None:
            # L'objet rendu doit porter la MÊME ancre que sa ligne : c'est lui
            # que l'appelant passera à `materialiser_touche_suivante`.
            cible.refresh_from_db(fields=['cadence_depart'])

    if journaliser:
        # COCKPIT-CONTRÔLE B4 — texte bâti sur les constantes que
        # ``est_note_de_report`` reconnaît : cette note ne pose pas le
        # premier contact.
        quand_local = nouveau.astimezone(horaires.CASABLANCA)
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(PREFIXE_NOTE_REPORT
                  + f'{quand_local:%d/%m/%Y à %H:%M} — touche « '
                  + f'{(cible.libelle or cible.get_canal_display())} »'
                  + FIN_NOTE_REPORT))

    # ACRM37 — LE recalage unique de la file (``_recaler_file``).
    _recaler_file(lead, user)
    return cible


def arreter_cadence(lead, *, user, motif, cadences=None, exclure=None):
    """MRY9 — LA fonction d'arrêt d'une (ou de toutes les) cadence(s).

    UNE seule implémentation pour SIX déclencheurs (devis accepté, passage
    SIGNED/COLD, lead perdu, « ne plus contacter », issue d'appel « joint » /
    « intéressé » / « refus », devis refusé) : deux implémentations auraient
    dérivé, et un lead aurait continué d'être relancé après avoir signé — la
    faute la plus visible qu'un CRM puisse commettre.

    Toutes les touches ``A_FAIRE`` (restreintes à ``cadences`` si fourni)
    passent à ``ANNULEE`` en UNE requête, avec le motif et l'horodatage.
    CKP1 (fondateur 2026-09-10) — ``traite_par`` est mis à NULL, délibérément :
    ARRÊTER une cadence est un geste du MOTEUR, pas de l'humain qui a
    déclenché l'événement. Estampiller son nom sur les neuf touches restantes
    les affichait « Sautée par Meryem » et les comptait comme neuf
    manquements dans les KPI d'adhérence — l'inverse exact de la vérité (le
    client avait répondu). Le motif, lui, reste écrit dans ``note``.
    UNE note chatter. ``Lead.relance_date`` est recalculée sur la prochaine
    touche restante (ou vidée) et ``sync_relance_activity`` remise en phase.

    IDEMPOTENTE : zéro touche ouverte ⇒ rien, pas même une note (sinon chaque
    passage d'étape empilerait des lignes vides dans l'historique).

    CAD5 — ``exclure`` (une touche) la laisse ouverte : la réponse « Ne plus
    me contacter » arrête TOUT le reste sous son vrai motif, puis clôt
    elle-même la touche sur laquelle le client l'a dit (qui porte l'issue).

    Renvoie le nombre de touches arrêtées."""
    ouvertes = lead.relance_etapes.filter(statut=RelanceEtape.Statut.A_FAIRE)
    if cadences:
        ouvertes = ouvertes.filter(cadence__in=list(cadences))
    if exclure is not None:
        ouvertes = ouvertes.exclude(pk=exclure.pk)
    pks = list(ouvertes.values_list('pk', flat=True))
    if not pks:
        return 0
    RelanceEtape.objects.filter(pk__in=pks).update(
        statut=RelanceEtape.Statut.ANNULEE,
        note=(motif or '')[:500],
        traite_par=None,
        traite_le=timezone.now())
    quelles = ', '.join(cadences) if cadences else 'toutes cadences'
    # FG28/MRY19 — note SYSTÈME (``user=None``), jamais l'utilisateur qui a
    # déclenché l'arrêt (même motif que ``initialiser_plan_relance`` et
    # ``_refus_cadence`` ci-dessus) : ARRÊTER une cadence n'est pas AVOIR
    # contacté le lead. Avec ``user`` posé ici, le récepteur QJ7
    # (``_avancer_stage_on_contact_activity``) traitait cette note comme un
    # premier contact manuel et avançait NEW → CONTACTED dès qu'un lead tout
    # neuf était marqué « perdu » / « ne plus contacter » — le bug était
    # visible dans ``test_une_seule_note_chatter`` (4 notes au lieu de 3).
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f'Cadence {quelles} arrêtée ({len(pks)} touche(s)) : {motif}.')
    # ACRM37 — LE recalage unique de la file (``_recaler_file``).
    _recaler_file(lead, user)
    return len(pks)


def arreter_cadence_du_lead_id(lead_id, *, company=None, user=None, motif='',
                               cadences=None):
    """Variante par ID, best-effort — pour les receivers qui ne tiennent qu'un
    ``devis.lead_id``. Ne lève JAMAIS : un arrêt de cadence en échec ne doit
    pas faire retomber l'acceptation d'un devis déjà actée."""
    if not lead_id:
        return 0
    from django.db import transaction
    try:
        # ADEV54 — point de sauvegarde PROPRE : une erreur base pendant
        # l'arrêt est annulée seule, jamais la signature du devis.
        with transaction.atomic():
            qs = Lead.objects.filter(pk=lead_id)
            if company is not None:
                qs = qs.filter(company=company)
            lead = qs.first()
            if lead is None:
                return 0
            return arreter_cadence(lead, user=user, motif=motif,
                                   cadences=cadences)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'arreter_cadence: échec sur le lead #%s', lead_id, exc_info=True)
        return 0


def _prochaine_touche_a_faire(lead):
    """La prochaine touche À FAIRE du lead, toutes cadences confondues.

    Trie sur ``due_at`` d'abord (granularité minute, MRY5) avec les lignes
    d'avant MRY5 — qui n'ont pas d'heure — placées EN DERNIER plutôt qu'en
    tête : sans ``nulls_last``, Postgres les remonterait et ``relance_date``
    reculerait vers une vieille étape."""
    from django.db.models import F

    return (lead.relance_etapes
            .filter(statut=RelanceEtape.Statut.A_FAIRE)
            .order_by(F('due_at').asc(nulls_last=True), 'due_date', 'ordre')
            .first())


def _recaler_file(lead, user):
    """Remet ``Lead.relance_date`` (et le rappel Calendrier) sur la prochaine
    touche ouverte — le geste de fin de toutes les écritures de relance."""
    prochaine = _prochaine_touche_a_faire(lead)
    lead.relance_date = prochaine.due_date if prochaine else None
    lead.save(update_fields=['relance_date'])
    sync_relance_activity(lead, user)


# ── CAD-G ── CAD74 — réveil saisonnier (`reveil_b`) ────────────────────────
# Le câblage vit dans `apps/crm/cadence_reveil_saison.py` (module autonome —
# ce fichier est partagé par des dizaines de tâches). Ces deux passe-plats
# sont le point d'entrée attendu par les appelants de `services` ; ils ne
# dupliquent aucune logique. Crochet planifié : AUCUN aujourd'hui — la pose
# se déclenche par un appel explicite, jamais à l'insu de la commerciale.


def poser_reveil_saisonnier(lead, user=None, *, maintenant=None):
    """CAD74 — pose LA touche `reveil_b` sur un dormant (ou ``None``)."""
    from .cadence_reveil_saison import poser_reveil_saisonnier as _poser
    return _poser(lead, user, maintenant=maintenant)


def poser_reveils_saisonniers(company, user=None, *, maintenant=None,
                              limite=200):
    """CAD74 — passe la fenêtre juin-septembre sur les dormants d'une société."""
    from .cadence_reveil_saison import poser_reveils_saisonniers as _tous
    return _tous(company, user, maintenant=maintenant, limite=limite)


# ── CAD-E ── CAD57 — validité J+30 pour un dossier financé, J+14 sinon ─────
#
# [TRANCHÉ 21/09/2026] La validité était posée sur la DERNIÈRE touche de la
# cadence, c'est-à-dire J+14 : le devis expirait le jour exact où le suivi
# s'arrête. Pour un PARTICULIER, la loi 31-08 (consommateur) impose, une fois
# l'offre de crédit émise, 10 jours de réflexion + 7 jours de rétractation
# avant déblocage : il ne peut pas, légalement, boucler dans la fenêtre qu'on
# lui annonce. CIQ510 — pour un PROFESSIONNEL (la loi 31-08 vise les besoins
# non professionnels, art. 2), la même règle « financé » tient pour une autre
# raison : le délai d'instruction de la banque ou de l'organisme, ou l'attente
# d'un accord déclarée. Aucune conclusion juridique ici (avis d'un juriste :
# tâche manuelle).
#
# Garde-fou : la DURÉE vient d'un réglage société
# (``CompanyProfile.quote_validity_days``, lu par la façade de ventes), jamais
# d'un nombre écrit dans le code du message. Le message J9 et le PDF affichent
# la MÊME date (CAD59).

#: CIQ510 — la fin de la note quand la validité vient d'une attente d'accord.
MOTIF_VALIDITE_ATTENTE = "en attente d'un accord (réglage société)"


# ── CAD-J ── CAD126 — variantes de SEGMENT, par exception ─────────────────
#
# Les textes sont 100 % résidentiels : « vos panneaux posés sur votre toit »
# part à un pompage au bord d'un forage, où il n'y a littéralement pas de
# toit, et `valeur_j1` demande « votre facture », sans objet pour une
# exploitation au butane. Côté industriel, `dimanche_famille` EST filtré par
# l'étiquette « décision à plusieurs » — c'est donc un industriel TAGUÉ qui
# reçoit « en famille ».
#
# Le dictionnaire de variantes vit dans `apps/parametres/models_messages.py`
# (à côté des textes), sur le modèle du dictionnaire darija : dict SÉPARÉ,
# repli sur le FR quand la clé est absente. Rien ici n'est une matrice
# complète : uniquement les clés qui MENTENT.


# ── CAD-J ── CAD128 — le client DÉJÀ SIGNÉ qui redemande un devis ─────────
#
# La garde doublon retenait tout lead partageant le téléphone ou l'e-mail et
# n'écartait que les archivés et les perdus : une fiche SIGNÉE était donc un
# doublon vivant, et le meilleur lead du portefeuille — il a déjà acheté —
# repartait sans protocole, avec une simple ligne « doublon possible de #… ».
#
# Version RÉDUITE du round 2 : SIGNED sort de la garde **uniquement couplé**
# à une cadence courte « deuxième affaire », avec son propre texte — jamais
# le protocole contact, six appels sur quatorze jours sur un client acquis.
#
# Garde-fou : les deux fiches sont LIÉES par une note d'historique, JAMAIS
# fusionnées d'office. Le volume (signés partageant un téléphone avec un lead
# actif) est l'un des comptages de CADM7 : la liaison en base, s'il en faut
# une, se décidera là — pas ici.

#: Le nom de la cadence courte. Valeur de
#: ``parametres.Cadence.DEUXIEME_AFFAIRE``, reprise en littéral comme les
#: autres noms de cadence de ce module.
CADENCE_DEUXIEME_AFFAIRE = 'deuxieme_affaire'


def homonymes_signes(lead):
    """Les fiches SIGNÉES qui partagent le téléphone ou l'e-mail de ``lead``.

    Lecture pure (aucune écriture) : sert à la garde, au geste manuel et au
    test. Les archivés et les perdus n'en font jamais partie.
    """
    if lead is None:
        return []
    return [
        autre for autre in find_duplicates_by_contact(
            lead.company, phone=lead.telephone, email=lead.email,
            exclude_pk=lead.pk, whatsapp=lead.whatsapp)  # ACRM32 (jumeau)
        if not autre.is_archived and not autre.perdu
        and autre.stage == stages.SIGNED
    ]


def _demarrer_deuxieme_affaire(lead, user):
    """CAD128 — lance la cadence COURTE et LIE les deux fiches.

    Renvoie les touches créées (liste vide si la cadence ne peut pas partir —
    même tolérance que le reste du moteur : jamais d'exception vers
    l'appelant).
    """
    anciens = homonymes_signes(lead)
    refs = ', '.join(f'#{autre.pk}' for autre in anciens[:3])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=(f'Client déjà signé qui revient (fiche {refs or "?"}) — '
              'cadence courte « deuxième affaire » lancée, PAS le protocole '
              'de prise de contact. Les deux fiches restent distinctes : '
              'aucune fusion automatique.'))
    for ancien in anciens[:3]:
        # La liaison est SYMÉTRIQUE : depuis la fiche signée, on doit voir
        # qu'une deuxième affaire est partie — sinon personne ne le sait.
        LeadActivity.objects.create(
            company=lead.company, lead=ancien, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Nouvelle demande de ce client : fiche #{lead.pk} — '
                  'cadence courte « deuxième affaire ».'))
    return initialiser_plan_relance(
        lead, user, cadence=CADENCE_DEUXIEME_AFFAIRE, depart=timezone.now())


def est_etape_de_filet(etape):
    """CAD3 — cette touche est-elle une étape posée par le FILET
    (``assurer_prochaine_etape_apres_succes``) plutôt qu'un barreau du
    protocole ?

    Les étapes de filet portent la cadence ``generique`` sans être des
    barreaux du gabarit : ce sont « préparer et envoyer le devis (ou fixer un
    rappel) », « appeler le client — il a répondu au message », « décider la
    suite » et le rappel convenu de CAD3. C'est sur elles que « rappelle-moi
    la semaine prochaine » tombe le plus souvent — l'étape que la commerciale
    voit le plus — et les CLORE pour en recréer une autre faisait perdre à la
    fois leur date et leur nom.
    """
    if etape is None:
        return False
    # PARAM-CADENCE — par la CLÉ (gabarit « Après l'appel »), ou le libellé
    # des deux étapes hors gabarit (passation, question de prix).
    if est_etape(etape, *CLES_APRES_CONTACT):
        return True
    return (not (getattr(etape, 'cle', '') or '')
            and (etape.libelle or '').strip() in _LIBELLES_FILET_HORS_GABARIT)
