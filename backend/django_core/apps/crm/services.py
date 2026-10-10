"""QJ6 + Lead → Client resolution.

QJ6 — recompute_lead_score(lead) persiste le score calculé sur le lead pour
permettre un tri pagination-safe (?ordering=-score). Appelé dans perform_create
et perform_update du LeadViewSet.

Lead → Client resolution (approach approved by the founder, 2026-06-12).

A quote always carries a Client; when it starts from a Lead the client is
resolved automatically, without ever creating duplicates:

  1. the lead is already linked to a client  → reuse that client;
  2. the lead has an email matching an existing client of the SAME company
     (case-insensitive)                      → link and reuse that client;
  3. otherwise                               → create a client from the lead's
     contact details and link it.

The resolved link is persisted on the lead, so every later quote from the
same lead reuses the same client. Everything stays tenant-scoped.
"""
import contextlib
import datetime
import hashlib as _hashlib
import logging
import re as _re

from django.apps import apps as django_apps
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

# CRX26 — LA date MÉTIER (Africa/Casablanca), lue EXPLICITEMENT : elle ne dépend
# d'aucun réglage global. Avant AUD836, ``settings.TIME_ZONE`` valait ``'UTC'``
# et ``timezone.localdate()`` était en retard d'un jour entier une heure par
# nuit ; le réglage dit désormais la même chose, ce helper reste la garantie.
from core.dates import aujourd_hui_local

from apps.parametres import models_relance as gabarit_relance

from . import activity, cadence_config, stages
from .cadence_config import (
    CLE_APPEL_APRES_REPONSE, CLE_CONFIRMATION, CLE_DEBRIEF, CLE_DECIDER_SUITE,
    CLE_DERNIER_APPEL, CLE_DEVIS, CLE_DEVIS_MODIFIE, CLE_MESSAGE_CRENEAU,
    CLE_PLANIFIER, CLE_RAPPEL_CONVENU, CLES_APRES_CONTACT, CLES_VISITE,
    cle_de, est_etape, q_etape,
)
from .models import Client, Lead, LeadActivity, PointContact, RelanceEtape

from .leads_socle import (
    MOTIF_BULK_CADENCE_ACTIVE,
    _company_fallback_managers,
    lead_notification_recipients,
    leads_avec_cadence_active,
    visite_point_eau_requise,
    visite_pro_avant_devis,
)
from .leads_socle import motif_refus_valide, user_and_superior_recipients  # noqa: F401 — façade

from .leads_doublons import (
    _MERGE_FILL_FIELDS,
    _est_vide,
    _strip_accents,
    find_duplicates_by_contact,
    normalize_email,
    normalize_phone,
)
from .leads_doublons import is_strong_identity_match  # noqa: F401 — façade

from .leads_attribution import default_responsable_for, responsable_leads_pro

from .leads_premier_contact import marquer_premier_contact, maybe_set_first_contacted_at

from .leads_consentement import (
    BASE_LEGALE_NON_COLLECTEE,
    BASE_LEGALE_SOLLICITATION,
    CONSENT_SOURCE_DOCUMENT,
    CONSENT_SOURCE_META_LEAD_ADS,
    CONSENT_SOURCE_WHATSAPP_ENTRANT,
    _ecrire_registre_contact,
    enregistrer_base_legale_lead,
)
from .leads_consentement import enregistrer_consentements_intake_web  # noqa: F401 — façade

from .visites_rdv import resoudre_lien_rdv
from .visites_rdv import public_booking_url, send_due_appointment_reminders  # noqa: F401 — façade

from .visites_retour_lead import ecrire_retour_lead_visite
from .visites_retour_lead import journaliser_visite  # noqa: F401 — façade

# T-TRACE — le traçage des visiteurs externes vit dans son propre module
# (``apps/crm/visites.py``) pour ne pas gonfler ce fichier déjà très long,
# mais il est RÉEXPORTÉ ici : `services` reste la porte d'entrée unique des
# écritures CRM (les accroches n'importent jamais `visites` directement).
from .visites import (  # noqa: F401 — réexport public délibéré
    COOKIE_APPAREIL,
    COOKIE_EQUIPE,
    alerter_appareil_partage,
    appareil_de_requete,
    appareils_equipe_ids,
    avec_direction,
    detecter_concurrent,
    domaine_cookies_equipe,
    enregistrer_appareil_equipe,
    enregistrer_visite_externe,
    est_appareil_equipe,
    historique_appareil,
    ip_de_requete,
    rattacher_visites_au_lead,
    requete_marquee_equipe,
    resume_historique_fr,
    tracer_et_correler,
    user_agent_de_requete,
    utilisateurs_direction,
)

logger = logging.getLogger(__name__)

# Mouvement automatique du funnel à partir des statuts DOCUMENT du devis
# (couche séparée et permanente — CLAUDE.md règles #2/#4) :
#   devis « envoye »  → étape QUOTE_SENT (Devis envoyé)
#   devis « accepte » → étape SIGNED (Signé)
# Clés scalaires uniquement — jamais de nouvelle liste d'étapes (STAGES.py).
_STATUT_VERS_STAGE = {
    'envoye': ('QUOTE_SENT', 'envoyé'),
    'accepte': ('SIGNED', 'accepté'),
}


def _rang_funnel(stage_key: str) -> int:
    """Rang d'avancement dans le funnel, depuis l'ordre canonique de STAGES.

    COLD est un état de PARKING, pas « plus avancé » : il est classé SOUS
    NEW (rang -1, donc sous toute étape active y compris NEW/CONTACTED) pour
    qu'un lead froid soit RÉACTIVÉ par les mouvements automatiques (devis
    envoyé/accepté, réactivation sur nouvelle touche YLEAD11) quelle que soit
    l'étape cible visée.
    """
    if stage_key == 'COLD':
        return -1
    return stages.STAGES.index(stage_key)


# ── QJ7 — Avance automatique NEW → CONTACTED au premier contact ──────────────
#
# Kinds d'activité qui comptent comme « premier contact » :
#   NOTE, APPEL, EMAIL — une CREATION ou MODIFICATION ne suffit pas.
_CONTACT_KINDS = frozenset([
    LeadActivity.Kind.NOTE,
    LeadActivity.Kind.APPEL,
    LeadActivity.Kind.EMAIL,
    # MRY10 — un WhatsApp envoyé fait AVANCER NEW → CONTACTED, exactement
    # comme un e-mail : c'est le canal principal de Meryem.
    LeadActivity.Kind.WHATSAPP,
])

# Clé canonique de l'étape « Contacté » (STAGES.py — jamais hardcodée ailleurs).
_STAGE_CONTACTED = 'CONTACTED'


def _emit_stage_changed(lead, old_stage, new_stage, user=None):
    """NTCRM12 — Émet ``core.events.lead_stage_changed`` pour TOUT point
    d'entrée qui fait bouger ``Lead.stage``. No-op si l'étape n'a pas changé.
    Best-effort : n'échoue jamais l'appelant."""
    if old_stage == new_stage:
        return
    try:
        from core.events import lead_stage_changed
        lead_stage_changed.send(
            sender=Lead, lead=lead, old_stage=old_stage, new_stage=new_stage,
            user=user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'NTCRM12: émission lead_stage_changed échouée pour le lead #%s',
            getattr(lead, 'pk', '?'), exc_info=True)


def appliquer_stage_lead(lead, nouveau_stage, *, user=None):
    """CRX20 — Point de passage CANONIQUE de toute écriture de ``Lead.stage``.

    Écrit l'étape (``save(update_fields=['stage'])``) PUIS émet
    ``core.events.lead_stage_changed`` via :func:`_emit_stage_changed`, de
    sorte qu'aucun chemin ne puisse plus déplacer un lead « en muet » (les
    récepteurs playbook NTCRM12 et séquences compta XMKT1 s'abonnent à ce
    signal — un chemin muet les prive silencieusement de leur déclencheur).

    Ne journalise RIEN dans le chatter : chaque appelant garde sa propre
    écriture d'historique (note système, ``activity.log_bulk_change``…), qui
    diffère d'un point d'entrée à l'autre.

    ``nouveau_stage`` doit être une clé canonique de STAGES.py — jamais un
    littéral inventé. No-op si l'étape ne change pas.

    Renvoie ``True`` si l'étape a effectivement changé, ``False`` sinon.
    Point d'entrée PUBLIC : ``apps.ventes`` l'appelle pour l'expiration des
    devis (jamais un import des models crm depuis ventes).
    """
    ancien_stage = lead.stage
    if ancien_stage == nouveau_stage:
        return False
    lead.stage = nouveau_stage
    lead.save(update_fields=['stage'])
    _emit_stage_changed(lead, ancien_stage, nouveau_stage, user=user)
    return True


class SortieSigneBloquee(Exception):
    """Décision fondateur (08/10/2026) — le lead ne peut pas sortir de
    « Signé » : son devis accepté a déjà une suite RÉELLE (facture, bon de
    commande, chantier avancé…). ``message`` est la phrase française à
    montrer telle quelle (HTTP 409 à l'unité, motif de saut en masse)."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def desaccepter_devis_du_lead(lead, user, *, motif=''):
    """Décision fondateur (08/10/2026) — un lead qui SORT de « Signé » par
    une action utilisateur dés-accepte ses devis acceptés (actifs) : chacun
    repasse « envoyé » par la porte de ``ventes``
    (``services.annuler_acceptation``), qui défait ce que l'acceptation avait
    créé automatiquement (événement ``devis_acceptation_annulee``).

    À appeler DANS la transaction de l'écriture d'étape, AVANT elle : si un
    devis est bloqué, ``SortieSigneBloquee`` est levée — l'appelant laisse la
    transaction s'annuler (aucun devis dés-accepté, étape inchangée). Les
    chemins AUTOMATIQUES (recyclage système) n'appellent jamais cette
    fonction. Rend le nombre de devis dés-acceptés (0 = comportement
    inchangé pour un lead « Signé » sans devis accepté)."""
    from apps.ventes.selectors import devis_acceptes_actifs
    from apps.ventes.services import (
        AnnulationAcceptationBloquee, annuler_acceptation,
    )
    libelle = stages.STAGE_LABELS[stages.SIGNED]
    nb = 0
    for devis in devis_acceptes_actifs(lead.company, lead_id=lead.pk):
        try:
            annuler_acceptation(
                devis=devis, user=user,
                motif=motif or f'lead sorti de « {libelle} »')
        except AnnulationAcceptationBloquee as exc:
            raise SortieSigneBloquee(
                f'Impossible de sortir ce lead de « {libelle} » : '
                f'{exc.message}') from exc
        nb += 1
    return nb


def _playbook_correspond_au_lead(playbook, lead):
    """NTCRM26 — ``playbook.condition`` matche-t-il ce lead ? ``None``/vide =
    playbook universel (comportement historique) — toujours ``True``.
    Réutilise ``core.rules.evaluate_condition_group`` (FG367), jamais un
    nouveau moteur. Tolérant : jamais d'exception, ``False`` en cas de doute."""
    if not playbook.condition:
        return True
    from core.rules import evaluate_condition_group
    criteres = {
        'type_installation': getattr(lead, 'type_installation', None),
        'canal': getattr(lead, 'canal', None),
        # AGR525 — le playbook FDA vise le REMPLACEMENT DU BUTANE (Guide FDA
        # 2024, D-AGR-6) : l'énergie de la pompe actuelle est un critère.
        'pompe_alim_actuelle': getattr(lead, 'pompe_alim_actuelle', None),
        # CIQ517 (D-CIQ-6) — le playbook « raccordement et autorisations du
        # site » vise un site MT, une régularisation 82-21 ou un client qui
        # veut revendre : ces trois critères sont lus.
        'tension_raccordement': getattr(lead, 'tension_raccordement', None),
        'regularisation_8221': getattr(lead, 'regularisation_8221', None),
        'objectif_projet': getattr(lead, 'objectif_projet', None),
    }
    try:
        return evaluate_condition_group(playbook.condition, criteres)
    except Exception:  # noqa: BLE001 — tolérant, jamais bloquant
        return False


def playbooks_recommandes(lead, stage):
    """NTCRM26 — Playbooks ACTIFS de la société de ``lead`` portant une étape
    sur ``stage`` dont ``condition`` matche le profil du lead (universels
    inclus). Lecture pure, sert à l'aperçu et à ``generer_playbook_progress``."""
    from .models import Playbook

    playbooks = Playbook.objects.filter(
        company=lead.company, actif=True, etapes__stage=stage,
    ).distinct()
    return [p for p in playbooks if _playbook_correspond_au_lead(p, lead)]


def generer_playbook_progress(lead, new_stage):
    """NTCRM12/NTCRM26 — Quand ``lead`` entre dans ``new_stage``, crée la
    progression (``LeadPlaybookProgress``, une par tâche) pour chaque playbook
    ACTIF de la société portant une étape sur ``new_stage`` ET dont
    ``condition`` matche le profil du lead (auto-sélection par similarité —
    un playbook sans condition reste universel, comportement historique
    inchangé). Idempotent (``unique_together(lead, tache)``, ``get_or_create``)
    : rejouer l'événement (ex. réactivation YLEAD11 qui repasse par la même
    étape) ne duplique jamais les tâches. Ne bloque JAMAIS le changement
    d'étape (avertissement seulement — cohérent avec « never auto-move ») :
    appelé en best-effort par le récepteur."""
    from .models import LeadPlaybookProgress, PlaybookEtape

    playbooks_ok = {p.pk for p in playbooks_recommandes(lead, new_stage)}
    etapes = PlaybookEtape.objects.filter(
        playbook__company=lead.company, playbook__actif=True,
        stage=new_stage, playbook_id__in=playbooks_ok,
    ).prefetch_related('taches')
    created = []
    for etape in etapes:
        for tache in etape.taches.all():
            _progress, was_created = LeadPlaybookProgress.objects.get_or_create(
                lead=lead, tache=tache)
            if was_created:
                created.append(_progress)
    return created


SEUIL_VUES_SIGNAL_INTERET = 3
FENETRE_SIGNAL_INTERET_HEURES = 48


def detecter_signal_interet_salle_vente(salle):
    """NTCRM27 — Si ``salle`` (une ``crm.SalleVente``) est liée à un lead en
    stage QUOTE_SENT et a reçu ``SEUIL_VUES_SIGNAL_INTERET`` vues ou plus en
    moins de ``FENETRE_SIGNAL_INTERET_HEURES``, journalise une note NOTE
    informationnelle « signal d'intérêt fort » sur le chatter du lead
    (JAMAIS un changement de stage automatique) et émet
    ``core.events.salle_vente_signal_interet``. Idempotent PAR JOUR : une
    nouvelle vue au-delà du seuil le même jour ne duplique pas la note.
    Best-effort — appelé depuis la vue publique, ne doit jamais lever.

    CRX31 — le comptage est DÉDUPLIQUÉ PAR APPAREIL ET PAR JOUR. Il portait sur
    les vues BRUTES : trois rechargements de la page par le MÊME visiteur dans
    la même minute déclenchaient « signal d'intérêt fort », et le commercial
    rappelait un client qui n'avait rien fait de plus qu'appuyer sur F5. On
    compte désormais les couples DISTINCTS (empreinte de visiteur, jour local) —
    donc des visites RÉELLEMENT distinctes. Les vues sans empreinte exploitable
    (IP illisible) partagent la clé vide : elles comptent pour UNE, jamais pour
    trois — sous-compter est le bon sens du doute, sur-compter ne l'est pas.
    """
    from django.db.models.functions import TruncDate

    from core.dates import TZ_METIER

    try:
        lead = getattr(salle, 'lead', None)
        if lead is None or lead.stage != stages.QUOTE_SENT:
            return None
        depuis = timezone.now() - timezone.timedelta(hours=FENETRE_SIGNAL_INTERET_HEURES)
        vues_fenetre = salle.vues.filter(created_at__gte=depuis)
        # Jour LOCAL (Africa/Casablanca, CRX26) : le découpage journalier du
        # signal doit être celui du terrain, pas celui d'UTC.
        # `.order_by()` OBLIGATOIRE : ``SalleVenteVue.Meta.ordering`` vaut
        # ``['-created_at']``, et Django ajoute les colonnes de tri au SELECT
        # d'un `.distinct()` — chaque vue redeviendrait alors « distincte » et
        # la déduplication serait un no-op silencieux.
        nb_vues = (vues_fenetre
                   .annotate(jour=TruncDate('created_at', tzinfo=TZ_METIER))
                   .order_by()
                   .values('ip_hash', 'jour')
                   .distinct()
                   .count())
        if nb_vues < SEUIL_VUES_SIGNAL_INTERET:
            return None
        # ALEA3 — idempotence PAR JOUR LOCAL ET PAR SALLE : borne explicite
        # « minuit à Casablanca » (jamais le ``__date`` du fuseau actif, qui
        # dépend de la requête) et la salle nommée en fin de note.
        from core.dates import maintenant_local
        debut_jour = maintenant_local().replace(
            hour=0, minute=0, second=0, microsecond=0)
        deja_note = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='signal d\'intérêt fort',
            body__endswith=f'(salle de vente « {salle.titre} »)',
            created_at__gte=debut_jour,
        ).exists()
        if deja_note:
            return None
        note = LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(
                f"signal d'intérêt fort — {nb_vues} consultations distinctes "
                f"en {FENETRE_SIGNAL_INTERET_HEURES}h "
                f"(salle de vente « {salle.titre} »)"
            ),
        )
        try:
            from core.events import salle_vente_signal_interet
            salle_vente_signal_interet.send(
                sender=type(salle), lead=lead, salle=salle, company=lead.company)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'NTCRM27: émission salle_vente_signal_interet échouée pour le lead #%s',
                lead.pk, exc_info=True)
        return note
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'NTCRM27: détection signal intérêt échouée pour la salle #%s',
            getattr(salle, 'pk', '?'), exc_info=True)
        return None


def avancer_stage_new_vers_contacted(lead, user) -> bool:
    """Avance le stage du lead NEW → CONTACTED lors du premier contact.

    « Premier contact » = première activité de type NOTE, APPEL ou EMAIL.
    Idempotent : si le lead n'est plus à NEW (ou est perdu), ne fait rien et
    renvoie False. Ne recule jamais une étape déjà plus avancée.
    Renvoie True si l'avance a effectivement eu lieu, False sinon.
    """
    # Relire l'état courant en base : l'instance passée par le signal peut être
    # périmée (ex. un autre effet du même flux a déjà avancé le lead vers
    # QUOTE_SENT) — sans cela, on écraserait une étape plus avancée par CONTACTED.
    if lead.pk:
        lead.refresh_from_db(fields=['stage', 'perdu', 'first_contacted_at'])
    if lead.perdu:
        return False
    if lead.stage != stages.NEW:
        return False
    lead.stage = _STAGE_CONTACTED
    lead.save(update_fields=['stage'])
    # FG28/MRY19 — le premier contact passe par LA source unique
    # (``marquer_premier_contact``) : plus de pose artisanale ici.
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[stages.NEW],
        new_value=stages.STAGE_LABELS[_STAGE_CONTACTED],
        body='auto — premier contact',
    )
    marquer_premier_contact(lead)
    _emit_stage_changed(lead, stages.NEW, _STAGE_CONTACTED, user)
    return True


def avancer_stage_sur_reponse_devis(lead, user) -> bool:
    """QJ-FUNNEL (fondateur 09/09/2026 — « le lead reste en Contacté et ne
    bouge ni vers Devis envoyé ni vers Relance sur les réponses aux
    touches ») — avance QUOTE_SENT → FOLLOW_UP quand le client RÉPOND après
    l'envoi de sa proposition.

    Symétrique EXACT de ``avancer_stage_new_vers_contacted`` juste au-dessus,
    un cran plus loin dans le funnel, sous la MÊME doctrine 07/09/2026 : le
    funnel ne bouge que sur une réponse CONFIRMÉE (« joint »/« intéressé »)
    journalisée par un humain — jamais sur un comportement observé (YLEAD10
    débranché) ni sur une touche sautée. Le déclencheur est le même récepteur
    d'activité (receivers ``_avancer_stage_on_contact_activity``), donc il
    couvre d'un seul mécanisme la clôture de touche de cadence
    (``marquer_etape_relance``) ET l'appel journalisé à la main
    (``log_interaction``).

    Garde d'étape EXACTE (QUOTE_SENT seul) : un lead encore à CONTACTED dont
    l'appel aboutit reste à CONTACTED (aucun devis envoyé — « Relance » vient
    APRÈS « Devis envoyé » dans l'ordre canonique STAGES.py) ; un lead déjà à
    FOLLOW_UP ou plus avancé ne bouge pas. Idempotent, jamais en arrière,
    leads perdus ignorés."""
    if lead.pk:
        lead.refresh_from_db(fields=['stage', 'perdu'])
    if lead.perdu:
        return False
    if lead.stage != stages.QUOTE_SENT:
        return False
    lead.stage = stages.FOLLOW_UP
    lead.save(update_fields=['stage'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[stages.QUOTE_SENT],
        new_value=stages.STAGE_LABELS[stages.FOLLOW_UP],
        body='auto — réponse du client après devis',
    )
    _emit_stage_changed(lead, stages.QUOTE_SENT, stages.FOLLOW_UP, user)
    return True


def avancer_stage_devis_envoye_sur_touche(lead, user) -> bool:
    """QJ-FUNNEL (fondateur 09/09/2026 — « when I do Fait for quote sent, it
    should be at quote sent ») — place le lead à QUOTE_SENT quand la touche
    « Préparer et envoyer le devis » est cochée FAIT sans issue (le même
    geste que RELANCE-SUITE lit déjà comme « devis parti » pour démarrer le
    plan après-devis — appelé par ``marquer_etape_relance`` sur LA MÊME
    détection, jamais une seconde règle de libellé).

    Avance-seulement par RANG (``_rang_funnel``) : un lead COLD est RÉACTIVÉ
    (rang -1 — même doctrine que les mouvements devis envoyé/accepté), un
    lead déjà à QUOTE_SENT ou plus avancé ne bouge pas, un lead perdu est
    ignoré. C'est un mouvement de la couche FUNNEL seule (règle #2) : le
    STATUT document du devis, lui, ne bascule que par ``mark_devis_sent``
    (envoi réel — email, WhatsApp, lien copié)."""
    if lead.pk:
        lead.refresh_from_db(fields=['stage', 'perdu'])
    if lead.perdu:
        return False
    if _rang_funnel(lead.stage) >= _rang_funnel(stages.QUOTE_SENT):
        return False
    ancien = lead.stage
    lead.stage = stages.QUOTE_SENT
    lead.save(update_fields=['stage'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[ancien],
        new_value=stages.STAGE_LABELS[stages.QUOTE_SENT],
        body='auto — touche « envoyer le devis » faite',
    )
    _emit_stage_changed(lead, ancien, stages.QUOTE_SENT, user)
    return True


# ── YLEAD11 — Réactivation d'un lead perdu/COLD sur nouvelle touche entrante ──

def reactivate_lead_on_new_touch(lead, *, source='site web') -> bool:
    """YLEAD11 — Réactive ``lead`` s'il est actuellement PERDU ou COLD.

    Une nouvelle touche entrante (re-POST site web, nouveau message WhatsApp)
    sur un lead perdu/froid rouvre le cycle d'achat : lève ``perdu``,
    repositionne le funnel (AVANCE-SEULEMENT, jamais en arrière — donc un
    lead déjà ≥ CONTACTED et non perdu ne bouge pas) vers CONTACTED s'il
    avait déjà été contacté (``first_contacted_at`` posé), sinon NEW, et
    journalise une activité de réactivation. N'écrase JAMAIS l'attribution
    first-touch d'origine (ce service ne touche à aucun champ UTM/fbclid).
    Idempotent : un lead ni perdu ni COLD → no-op (False). Company-scopée par
    construction (opère sur l'instance ``lead`` déjà résolue dans SA société).
    """
    if lead is None:
        return False
    etait_perdu = bool(lead.perdu)
    etait_cold = lead.stage == stages.COLD
    if not etait_perdu and not etait_cold:
        return False

    if etait_perdu:
        lead.perdu = False
        lead.save(update_fields=['perdu'])

    cible = _STAGE_CONTACTED if lead.first_contacted_at else stages.NEW
    ancien_stage = None  # étape déjà ≥ cible — pas de changement d'étape.
    if _rang_funnel(lead.stage) < _rang_funnel(cible):
        etape_avant = lead.stage
        # ALEA2 — sortie du Froid/Perdu par le point de passage CANONIQUE
        # (CRX20) : écrit l'étape et émet `lead_stage_changed`.
        if appliquer_stage_lead(lead, cible):
            ancien_stage = etape_avant

    # ALEA2 — libellé lisible au chatter : « Nouvelle demande reçue (site
    # web) » / « (WhatsApp) ».
    body = f'auto — réactivation : Nouvelle demande reçue ({source})'
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=body)
    if ancien_stage is not None:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.MODIFICATION,
            field='stage', field_label='Étape',
            old_value=stages.STAGE_LABELS[ancien_stage],
            new_value=stages.STAGE_LABELS[cible],
            body=f'auto — réactivation ({source})',
        )
    # CAD107 — une réouverture pose une CADENCE DE REPRISE, quel que soit le
    # chemin. Best-effort : une nouvelle touche entrante ne doit jamais
    # échouer sur une cadence.
    try:
        reprendre_cadence_apres_reouverture(lead, None, origine=source)
    except Exception:  # noqa: BLE001
        logger.warning(
            'CAD107: reprise non posée après réactivation (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
    return True


# ── ACRM35 — un geste de cadence à la fois par lead ─────────────────────────

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


def _lead_de_l_etape(etape, *args, **kwargs):
    return getattr(etape, 'lead', None)


# ── CAD-B ── CAD107 ─────────────────────────────────────────────────────────

@_sous_verrou_du_lead(_lead_premier_argument)
def reprendre_cadence_apres_reouverture(lead, user, *, origine=''):
    """CAD107 — UN seul comportement pour les trois chemins de réouverture.

    Un client PERDU qui revient est le meilleur signal d'achat qui existe, et
    il avait trois sorties différentes : le PATCH qui décoche « Perdu » ne
    déclenchait RIEN (seul le passage inverse était traité), le lot
    `unset_perdu` appelait le filet, et `reactivate_lead_on_new_touch` ne
    créait aucune `RelanceEtape`. Dans les trois cas la prise de contact ne
    pouvait de toute façon pas repartir (garde « déjà contacté ») : au mieux
    une étape nue.

    Le comportement unique REUTILISE la cadence RÉVEIL — jamais une nouvelle
    cadence (CADX), et c'est exactement ce à quoi elle sert : reprendre le
    contact d'un dossier mis de côté, sans rejouer six appels en quatorze
    jours à quelqu'un qu'on a déjà travaillé.

    Trois no-op délibérés :

    * une touche est DÉJÀ ouverte ⇒ rien. CADX interdit deux cadences en
      parallèle, et le dossier est déjà suivi ;
    * lead perdu, archivé, « ne plus contacter », signé ou au froid ⇒ rien :
      ce n'est pas une réouverture ;
    * une cadence plus prioritaire est active ⇒ `CadenceActiveConflit` est
      avalée, l'humain arrête d'abord (recette du 08/09).

    Rend la liste des touches posées (vide sur no-op).
    """
    if lead is None or not getattr(lead, 'pk', None):
        return []
    lead.refresh_from_db(
        fields=['stage', 'perdu', 'is_archived', 'ne_plus_contacter'])
    if (lead.perdu or lead.is_archived
            or getattr(lead, 'ne_plus_contacter', False)):
        return []
    if lead.stage in (stages.SIGNED, stages.COLD):
        return []
    if lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).exists():
        return []
    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence='reveil', depart=timezone.now())
    except CadenceActiveConflit:
        etapes = []
    if not etapes:
        # REPLI — société sans gabarit de réveil, ou conflit de cadence :
        # QJ-INVARIANT prime, un lead actif ne reste jamais sans prochaine
        # étape. Le filet pose alors ce qu'il sait poser.
        etape = assurer_prochaine_etape_apres_succes(lead, user)
        return [etape] if etape is not None else []
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=('Dossier rouvert' + (f' ({origine})' if origine else '')
              + ' — cadence de reprise posée.'))
    return etapes


def avancer_stage_pour_devis(devis, ancien_statut, nouveau_statut, user):
    """Avance l'étape du lead quand le STATUT d'un devis change.

    Ne recule jamais, ignore les leads perdus (drapeau `perdu`), n'agit que sur
    les transitions envoye/accepte. Écrit UNE entrée d'historique marquée
    automatique (« auto — devis … »).
    """
    if nouveau_statut == ancien_statut:
        return
    cible = _STATUT_VERS_STAGE.get(nouveau_statut)
    if cible is None:
        return
    # `getattr` défensif : un vrai Devis résout son FK `lead` à l'identique
    # (chargement paresseux), mais ce récepteur est câblé au signal partagé
    # `devis_accepted` — un émetteur d'un autre domaine (ex. la séquence
    # d'inscription XMKT1) peut envoyer un objet devis minimal ne portant que
    # `lead_id` : on l'ignore alors proprement plutôt que de lever AttributeError.
    lead = getattr(devis, 'lead', None)
    if lead is None:
        return
    if lead.perdu:
        return  # lead perdu (drapeau) — le funnel ne bouge plus automatiquement.

    stage_cible, suffixe = cible
    if _rang_funnel(lead.stage) >= _rang_funnel(stage_cible):
        return  # jamais en arrière (ni sur-place).

    ancien_stage = lead.stage
    lead.stage = stage_cible
    lead.save(update_fields=['stage'])
    _emit_stage_changed(lead, ancien_stage, stage_cible, user)

    if stage_cible == 'SIGNED':
        # QJ9 — CAPI SignedQuote : le hook réside dans ventes.services.accept_devis
        # (_fire_capi_signed_quote, gated sur META_CAPI_ACCESS_TOKEN). L'avancée
        # manuelle en masse vers SIGNED (set_stage bulk) ne reporte pas de devis
        # accepté et ne dispose pas de l'attribution UTM — pas de CAPI ici.
        pass

    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[ancien_stage],
        new_value=stages.STAGE_LABELS[stage_cible],
        body=f"auto — devis {devis.reference} {suffixe}",
    )


# ── U11 — Cohérence funnel : « Signé sans devis actif » (DÉCISION fondateur) ──
#
# Le funnel n'avance jamais en arrière (avancer_stage_pour_devis), donc un lead
# peut rester à SIGNED alors que son SEUL devis accepté a depuis été refusé : un
# « signé fantôme ». La règle #2 (le funnel est une couche PERMANENTE, séparée
# des statuts DOCUMENT — les deux ne se mélangent jamais) interdit de reculer
# l'étape à l'aveugle. Option conservatrice retenue : on NE recule PAS l'étape,
# on SIGNALE l'incohérence (drapeau dérivé + note de chatter) pour que l'UI
# puisse la badger et que le commercial décide.

# Statut DOCUMENT « accepté » d'un devis (couche séparée — STATUT, pas étape).
_DEVIS_STATUT_ACCEPTE = 'accepte'


def lead_signe_sans_devis_actif(lead) -> bool:
    """Drapeau DÉRIVÉ (lecture seule) : le lead est à SIGNED mais n'a plus aucun
    devis accepté actif.

    « Actif » = un devis au statut DOCUMENT « accepté » qui n'est pas archivé.
    Ne modifie RIEN (aucune écriture, aucune migration) : c'est un calcul que
    l'UI peut badger pour repérer un « signé fantôme ». Renvoie ``False`` dès que
    le lead n'est pas à SIGNED (rien à signaler hors de l'étape Signé).
    """
    if getattr(lead, 'stage', None) != 'SIGNED':
        return False
    qs = lead.devis.filter(statut=_DEVIS_STATUT_ACCEPTE)
    # Certains devis peuvent être archivés (champ optionnel selon le schéma) —
    # on les exclut s'il existe, sinon on compte tous les devis acceptés.
    try:
        Devis = lead.devis.model
        if any(f.name == 'is_archived' for f in Devis._meta.get_fields()):
            qs = qs.filter(is_archived=False)
    except Exception:
        pass
    return not qs.exists()


def signaler_mismatch_signe_sur_refus(devis, user):
    """À l'événement « devis refusé » : si le refus laisse un lead SIGNED sans
    AUCUN devis accepté actif, consigne UNE note de chatter pour signaler le
    « signé sans devis actif » — SANS jamais reculer l'étape (règle #2).

    Best-effort, idempotent dans les faits : on n'écrit la note que lorsque
    l'incohérence est réellement présente après le refus. Ne crée pas de doublon
    pour un même refus car ``date_refus``/``motif_refus`` y figurent en clair.
    """
    lead = getattr(devis, 'lead', None)
    if lead is None:
        return
    # Le refus a déjà été appliqué (statut DOCUMENT) avant l'émission du signal,
    # donc le devis refusé n'est plus compté comme « accepté actif » ici.
    if not lead_signe_sans_devis_actif(lead):
        return
    activity.log_note(
        lead, user,
        f"⚠ Étape Signé sans devis actif : le devis {devis.reference} "
        f"(qui avait fait passer ce lead à « Signé ») est désormais refusé et "
        f"plus aucun devis accepté n'est actif. L'étape n'a PAS été reculée "
        f"automatiquement (à vérifier).")


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


def _lead_porte_tag(lead, tag) -> bool:
    """``lead`` porte-t-il l'étiquette ``tag`` ?

    ``Lead.tags`` est un champ LIBRE (texte séparé par des virgules), saisi à
    la main : la comparaison ignore la casse ET les accents — « Decision a
    plusieurs » vaut « Décision à plusieurs »."""
    def _cle(valeur):
        return _strip_accents((valeur or '').strip()).casefold()

    cible = _cle(tag)
    if not cible:
        return False
    return any(_cle(morceau) == cible
               for morceau in (getattr(lead, 'tags', '') or '').split(','))


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

#: VISITE-CADENCE (fondateur 15/09/2026) — « le client accepte la visite ».
#: C'est une issue de SUCCÈS d'un genre nouveau : le client n'a ni signé ni
#: refusé, il a dit oui à un RENDEZ-VOUS. Le suivi de PROPOSITION ne
#: s'arrête donc PAS (la proposition reste à relancer si la visite tombe à
#: l'eau), mais poser le geste générique suivant du protocole serait absurde :
#: la seule chose à faire est de CALER la visite. Le filet ci-dessous s'en
#: charge.
#: Décision fondateur du 24/09/2026 — l'issue vaut sur TOUTE touche, prise de
#: contact et réveil compris : un client qui accepte la visite a atteint le
#: but de la prise de contact, exactement comme « joint » — ces deux cadences
#: s'arrêtent (``CADENCES_ARRETEES_PAR_ISSUE``, bas de fichier).
OUTCOME_VISITE_ACCEPTEE = 'visite_acceptee'

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


#: MRY10 — canal de la touche → type d'activité du chatter. Une touche traitée
#: doit laisser UNE ligne typée (appel/WhatsApp/e-mail), pas une note libre :
#: c'est elle que compte le compteur de tentatives (MRY20) et que lisent les
#: règles d'arrêt sur l'issue (MRY9). « visite » n'a pas de type dédié — elle
#: reste une NOTE, faute de mieux, plutôt qu'un type inventé.
_CANAL_VERS_KIND = {
    RelanceEtape.Canal.APPEL: LeadActivity.Kind.APPEL,
    RelanceEtape.Canal.WHATSAPP: LeadActivity.Kind.WHATSAPP,
    RelanceEtape.Canal.EMAIL: LeadActivity.Kind.EMAIL,
    RelanceEtape.Canal.VISITE: LeadActivity.Kind.NOTE,
}

# ── CAD-K ── CAD131 — la première TENTATIVE n'est pas le premier CONTACT ────
#
# Audit L3 du 21/09/2026. ``first_contacted_at`` était posé dès qu'une note,
# un appel, un e-mail ou un WhatsApp était écrit par un humain — or SAUTER une
# touche écrit une NOTE signée par le commercial. Sauter la toute première
# touche satisfaisait donc la promesse client (« rappelé en moins de N
# minutes ») ET éteignait l'escalade, qui n'agit que sur les leads SANS
# horodatage : personne ne parlait au client, et plus rien ne le signalait.
#
# Le verbe est hissé en CONSTANTE pour que la reconnaissance vive à UN SEUL
# endroit, celui qui ÉCRIT la note — jamais un texte deviné ailleurs (même
# discipline que les préfixes du journal RLC2).
VERBE_TOUCHE_SAUTEE = 'sautée'
MENTION_TOUCHE_SAUTEE = f'marquée {VERBE_TOUCHE_SAUTEE}.'


def touche_traitee_en_avance(etape):
    """CAD44 — cette touche a-t-elle été TRAITÉE AVANT son échéance (jour local
    Casablanca de ``traite_le`` antérieur à ``due_date``) ?

    Décision fondateur du 21/09/2026 : agir en avance est permis (appeler,
    écrire, reporter), et une touche faite avant son jour n'est PAS une faute
    d'adhérence (``selectors._a_lheure``, CAD22). Le serveur la marque à sa
    date RÉELLE et le chatter le dit ; le reste du plan ne bouge pas (les
    barreaux suivants restent datés depuis l'ancre ``cadence_depart``)."""
    from . import horaires

    if etape is None or etape.traite_le is None or etape.due_date is None:
        return False
    return (etape.traite_le.astimezone(horaires.CASABLANCA).date()
            < etape.due_date)


def est_note_de_touche_sautee(activite):
    """CAD131 — cette ligne de chatter est-elle la note d'une touche SAUTÉE ?

    Une touche sautée n'est PAS une tentative : rien n'est sorti vers le
    client. Seule cette note doit être écartée du premier contact — une note
    ordinaire écrite à la main par la commerciale (« Appelé, pas de réponse »)
    reste un contact, comme depuis MRY19.
    """
    if activite is None:
        return False
    if getattr(activite, 'kind', None) != LeadActivity.Kind.NOTE:
        return False
    return MENTION_TOUCHE_SAUTEE in (getattr(activite, 'body', '') or '')


# ── COCKPIT-CONTRÔLE B4 — un REPORT n'est pas un premier contact ────────────
#
# Même trou que CAD131, par une autre porte : « Reporter » (et « Mettre en
# veille ») écrit une NOTE signée par la commerciale — « Rappel demandé le … —
# touche « … » reportée. » — et le récepteur QJ7 la prenait pour une
# tentative : reporter la toute première touche d'un lead neuf horodatait
# ``first_contacted_at`` et ÉTEIGNAIT l'escalade, sans que personne ait parlé
# au client. Les textes sont hissés en CONSTANTES, utilisées pour ÉCRIRE les
# notes (``reporter_prochaine_touche``, ``_veille_simple``,
# ``_basculer_veille_en_reveil``) et pour les RECONNAÎTRE — jamais un texte
# deviné ailleurs.
PREFIXE_NOTE_REPORT = 'Rappel demandé le '
FIN_NOTE_REPORT = ' reportée.'
PREFIXE_NOTE_VEILLE = 'Mise en veille '


def est_note_de_report(activite):
    """COCKPIT-CONTRÔLE B4 — cette ligne de chatter est-elle la note d'un
    REPORT de touche ou d'une MISE EN VEILLE ?

    Un report déplace le PLAN, rien ne sort vers le client : cette note ne
    pose pas ``first_contacted_at`` (même patron que
    ``est_note_de_touche_sautee``). Une note ordinaire de la commerciale, et
    la ligne TYPÉE d'une réponse « Plus tard » (un vrai échange, issue « à
    rappeler »), restent des contacts."""
    if activite is None:
        return False
    if getattr(activite, 'kind', None) != LeadActivity.Kind.NOTE:
        return False
    corps = getattr(activite, 'body', '') or ''
    return ((corps.startswith(PREFIXE_NOTE_REPORT)
             and corps.endswith(FIN_NOTE_REPORT))
            or corps.startswith(PREFIXE_NOTE_VEILLE))


@_sous_verrou_du_lead(_lead_de_l_etape)
def marquer_etape_relance(etape, user, statut, note='', outcome='',
                          body='', suite=True, canal_reel=None):
    """Marque une ``RelanceEtape`` ``fait`` ou ``sautee`` (jamais un retour
    silencieux en arrière) : trace l'acteur/l'horodatage, journalise dans le
    chatter du lead, puis fait AVANCER ``Lead.relance_date`` vers la
    prochaine étape ``a_faire`` de CE plan (ou la vide si le plan est
    terminé) — garde ``sync_relance_activity`` en phase, jamais un second
    système de rappel concurrent.

    CKP2 — c'est aussi ICI que naît la touche SUIVANTE du protocole
    (``materialiser_touche_suivante``) quand la clôture n'est pas un succès :
    la cadence est RÉACTIVE, une touche à la fois, et c'est l'issue saisie qui
    programme le geste d'après.

    CAD-A (réponses de touche) — ``suite=False`` : l'APPELANT décide seul de
    ce qui vient après (« Ne plus me contacter » n'a pas de suite, « Question
    de prix » ou « Devis modifié » posent LEUR étape). Ni barreau suivant, ni
    clôture au froid, ni filet d'invariant : ces trois automatismes
    choisiraient une suite contraire à ce que le client vient de dire. La
    trace (touche close, ligne de chatter, issue) reste identique.

    SUIVI E16 (30/09/2026) — ``canal_reel`` : le canal par lequel la touche
    a RÉELLEMENT été faite quand il diffère du canal prévu (« Client joint au
    téléphone » sur une touche message). La ligne de chatter est alors typée
    selon ce canal réel (un APPEL abouti) : c'est elle que lisent le
    récepteur d'issue (MRY9 — la suite d'un appel abouti, jamais « il a
    répondu au message ») et le compteur de tentatives."""
    if statut not in (RelanceEtape.Statut.FAIT, RelanceEtape.Statut.SAUTEE):
        raise ValueError("Statut de relance invalide (fait ou sautee attendu).")

    # MRY11 × MRY9 — combien de touches de CETTE cadence restaient ouvertes
    # AVANT toute écriture, celle-ci exclue. Se le demander APRÈS était le
    # bug : marquer une touche de milieu de cadence « joint » déclenche le
    # récepteur `_arreter_cadence_on_outcome` (MRY9), qui passe TOUTES les
    # touches restantes à SAUTEE de façon SYNCHRONE sur le post_save de
    # l'activité — la question « reste-t-il une touche à faire ? » posée
    # ensuite répondait donc toujours « non », et le lead qu'on venait
    # justement de JOINDRE partait au froid, étiqueté injoignable, avec des
    # réveils J30/J60. La photo est prise avant, jamais après.
    restantes_avant = etape.lead.relance_etapes.filter(
        cadence=etape.cadence,
        statut=RelanceEtape.Statut.A_FAIRE,
    ).exclude(pk=etape.pk).count()

    etape.statut = statut
    etape.note = note or ''
    etape.traite_par = user
    etape.traite_le = timezone.now()
    # CAD118 — l'issue est écrite SUR la touche, au même instant que la ligne
    # d'historique ci-dessous. La ligne de chatter reste la source de vérité
    # du chatter ; cette colonne est ce qui rend mesurable « quelle touche, à
    # quelle heure, quel jour, sur quel canal joint réellement le client »
    # (CAD87) sans la fenêtre de rapprochement de deux minutes.
    etape.outcome = outcome or ''
    etape.save(update_fields=['statut', 'note', 'outcome', 'traite_par',
                              'traite_le'])

    verbe = ('faite' if statut == RelanceEtape.Statut.FAIT
             else VERBE_TOUCHE_SAUTEE)
    # SUIVI E16 — le canal RÉEL, quand la touche n'a pas été faite par le
    # canal prévu (le préfixe RLC2, seul relu ailleurs, ne change pas).
    canal_reel = (canal_reel or '').strip() or None
    if canal_reel == etape.canal:
        canal_reel = None
    canal_affiche = (f'{RelanceEtape.Canal(canal_reel).label} au lieu de '
                     f'{etape.get_canal_display()}' if canal_reel
                     else etape.get_canal_display())
    # MRY5 — le corps disait « Relance J+{ordre} », faux depuis que `ordre`
    # est un RANG dans la cadence et non plus un délai en jours (la touche 2
    # de la prise de contact tombe à J0 + 3 minutes, pas à J+2).
    corps = (f'{prefixe_activite_touche(etape)} '
             f'({canal_affiche}, cadence '
             f'{etape.cadence}) marquée {verbe}.')
    # CAD44 — une touche faite AVANT son échéance le dit dans le journal (sa
    # date réelle est `traite_le`) ; ce n'est pas une faute d'adhérence.
    if (statut == RelanceEtape.Statut.FAIT
            and touche_traitee_en_avance(etape)):
        corps += (' Traitée en avance (échéance du '
                  f'{etape.due_date:%d/%m/%Y}).')
    if body:
        corps += f' {body}'
    if note:
        corps += f" Note : {note}"
    # MRY10 — UNE SEULE ligne de chatter par touche, TYPÉE selon le canal
    # (jamais une note libre en plus d'une activité) : c'est elle que compte
    # le compteur de tentatives et que lisent les règles d'arrêt (MRY9).
    # SUIVI E16 — typée selon le canal RÉEL quand il diffère du prévu.
    kind = (_CANAL_VERS_KIND.get(canal_reel or etape.canal,
                                 LeadActivity.Kind.NOTE)
            if statut == RelanceEtape.Statut.FAIT
            else LeadActivity.Kind.NOTE)
    ligne = LeadActivity(
        company=etape.company, lead=etape.lead, user=user,
        kind=kind, body=corps, outcome=(outcome or ''))
    # SUIVI E22 (30/09/2026) — la touche close VOYAGE avec sa ligne de
    # chatter (attribut TRANSITOIRE, jamais une colonne) : le récepteur
    # d'issue MRY9, qui ne tient que l'activité, sait ainsi QUELLE touche
    # vient d'aboutir (``touche_close_de``) — sur la DERNIÈRE touche du
    # suivi de proposition, il pose « Décider la suite », jamais l'étape
    # devis d'un devis déjà parti.
    setattr(ligne, _ATTRIBUT_TOUCHE_CLOSE, etape)
    ligne.save(force_insert=True)

    lead = etape.lead
    # RELANCE-SUITE (08/09/2026) — LA détection « devis parti » : la touche
    # générique d'envoi du devis, sans issue. Hissée ici (une seule règle de
    # libellé) car DEUX consommateurs la lisent désormais : le filet plus bas
    # (démarrage du plan après-devis, comportement inchangé) et QJ-FUNNEL
    # juste en dessous (l'étape du funnel).
    # PARAM-CADENCE — reconnue par sa CLÉ (``devis``) : une société qui la
    # renomme « Faire le devis » garde « Fait » sans issue = devis parti.
    # SUIVI E13 (30/09/2026) — « Préparer le devis modifié — rappeler le
    # client » cochée FAITE sans issue vaut « devis parti », exactement comme
    # l'étape devis : c'est le devis MODIFIÉ qui part.
    touche_envoi_devis = not (outcome or '') and (
        (etape.cadence == 'generique' and est_etape(etape, CLE_DEVIS))
        or est_etape(etape, CLE_DEVIS_MODIFIE))
    # SUIVI E7 (30/09/2026) — « devis parti » seulement quand l'étape est
    # COCHÉE FAITE : une étape devis SAUTÉE n'a rien envoyé. Avant, le saut
    # passait `brouillon_compris` au filet et DÉMARRAIT le suivi de
    # proposition sans qu'aucun devis ne soit parti ; désormais le filet
    # applique sa ceinture (on ne re-pose jamais la touche close) et pose
    # « Décider la suite ».
    devis_parti = touche_envoi_devis and statut == RelanceEtape.Statut.FAIT
    # QJ-FUNNEL (fondateur 09/09/2026 — « when I do Fait for quote sent, it
    # should be at quote sent ») — cocher FAIT la touche d'envoi place le
    # lead à « Devis envoyé » sur-le-champ, quel que soit le reste du plan
    # (une touche SAUTÉE ne vaut jamais un envoi).
    if devis_parti:
        avancer_stage_devis_envoye_sur_touche(lead, user)
    # CKP2 — LA CADENCE RÉACTIVE : la touche suivante du protocole naît ICI,
    # de l'issue qu'on vient de saisir, et nulle part ailleurs.
    #   * FAIT sans issue d'arrêt (« pas de réponse » sur un appel, ou aucune
    #     issue sur un message/e-mail/visite) → le geste suivant est programmé.
    #   * SAUTÉE par un humain → idem : passer une touche ne doit pas éteindre
    #     la cadence, sinon sauter le message d'identité supprimait le reste du
    #     protocole.
    #   * « joint »/« intéressé »/« refus » → RIEN : le récepteur MRY9 vient
    #     d'ANNULER les touches restantes et le filet
    #     `assurer_prochaine_etape_apres_succes` pose la vraie suite.
    #   * « visite acceptée » → RIEN NON PLUS : le client a dit oui à un
    #     RENDEZ-VOUS, la seule suite utile est de le CALER. Le filet juste
    #     en dessous pose cette étape-là, jamais le barreau suivant du
    #     protocole (qui relancerait un client déjà conquis).
    # CAD1 — la condition se lit désormais AVEC la cadence de la touche :
    # « intéressé » n'arrête PAS le suivi de proposition, il en fait naître le
    # barreau suivant, exactement comme « pas de réponse ».
    suivante = None
    raison_suite = None
    if suite and (statut == RelanceEtape.Statut.SAUTEE
                  or issue_fait_naitre_la_suite(outcome, etape.cadence)):
        try:
            suivante, raison_suite = materialiser_touche_suivante(
                etape, user, avec_raison=True)
        except Exception:  # noqa: BLE001 — jamais bloquant pour le geste
            # ACRM12 — une panne n'est JAMAIS une fin de cadence : raison
            # INDÉTERMINÉE, le filet plus bas pose la suite (jamais le Froid).
            raison_suite = RaisonSuite.INDETERMINE
            logger.warning(
                'CKP2: touche suivante non matérialisée (étape #%s)',
                getattr(etape, 'pk', '?'), exc_info=True)
    # VISITE-CADENCE — « le client accepte la visite » : on pose LA seule
    # suite qui a du sens, planifier le passage du technicien. Sauf si un
    # rendez-vous est DÉJÀ calé (le client avait déjà sa date) — sinon cocher
    # deux fois l'issue empilerait deux rappels pour la même visite.
    if (statut == RelanceEtape.Statut.FAIT
            and (outcome or '') == OUTCOME_VISITE_ACCEPTEE):
        try:
            poser_filet_visite_a_planifier(
                lead, user, devis_id=etape.devis_id)
        except Exception:  # noqa: BLE001 — jamais bloquant pour le geste
            logger.warning(
                'VISITE-CADENCE: filet « planifier la visite » non posé '
                '(étape #%s)', getattr(etape, 'pk', '?'), exc_info=True)
    # ACRM37 — LE recalage unique de la file (``_recaler_file``).
    _recaler_file(lead, user)
    if not suite:
        # CAD-A — l'appelant pose (ou refuse) lui-même la suite.
        return etape
    # MRY11 — la cadence vient-elle de s'ÉPUISER ? Uniquement ici : une
    # cadence ARRÊTÉE (MRY9) n'est pas une cadence terminée, et clôturer un
    # lead qu'on vient de joindre serait exactement l'inverse du bon geste.
    # DEUX conditions, et aucune ne se lit après coup :
    #   * cette touche était bien la DERNIÈRE encore ouverte (photo prise
    #     avant l'écriture, cf. `restantes_avant`) ;
    #   * son issue n'est pas une issue de SUCCÈS — joindre, intéresser ou
    #     convenir d'un rappel ne clôt jamais un dossier au froid.
    # CKP2 — TROISIÈME condition, indispensable depuis la cadence réactive :
    # `restantes_avant == 0` est désormais VRAI à chaque touche (il n'y en a
    # jamais qu'une d'ouverte à la fois). Sans le `suivante is None`, le
    # premier « pas de réponse » du protocole aurait envoyé le lead au parking
    # étiqueté « Injoignable 6 appels » — après UN seul appel. La cadence n'est
    # épuisée que si le gabarit n'a plus rien à faire naître.
    # QUATRIÈME condition (décision fondateur du 24/09/2026 — « et même après
    # ça rien ne se passe ») : une étape de VISITE (planifier, confirmer,
    # débrief, devis modifié) n'est PAS un barreau du protocole, c'est un
    # geste posé À CÔTÉ de lui. Elle portait la cadence ``apres_devis`` et
    # aucune touche suivante ne naît d'elle : un débrief « pas de réponse »
    # épuisait donc la cadence et parquait le lead au FROID, étiqueté « Devis
    # sans suite », avec réveils J30/J60 — même sans aucun devis envoyé.
    # Jamais plus : c'est le filet ci-dessous (QJ-INVARIANT) qui prend le
    # relais — le plan s'il est pendant, sinon « Rappeler — dernier essai
    # avant de chiffrer » (``_FILET_SANS_REPONSE_PALIERS``), puis le devis.
    # ACRM12 (C-ACRM-007) — CINQUIÈME condition : la clôture n'a lieu que si
    # le gabarit est RÉELLEMENT épuisé (``RaisonSuite.FIN_GABARIT``, relu sur
    # les barreaux actifs). Un barreau désactivé, une panne, un barreau déjà
    # pris ou un lead hors relance ne parquent plus le lead au Froid.
    if (restantes_avant == 0 and suivante is None
            and raison_suite == RaisonSuite.FIN_GABARIT
            and (outcome or '') not in _OUTCOMES_SANS_CLOTURE
            and not est_etape_de_visite(etape)):
        cloturer_cadence(lead, user, etape.cadence)
    # QJ-INVARIANT (fondateur 07/09/2026, « fix this relance once and for
    # all ») — aucun geste de relance ne laisse un lead ACTIF sans prochaine
    # étape : si ni la cadence, ni la clôture MRY11 (parking Froid + réveils),
    # ni le récepteur MRY9 n'ont laissé de suite, le filet en pose une (plan
    # après-devis complet si un devis existe — l'étape générique « envoyer le
    # devis » traitée démarre ainsi le VRAI suivi de proposition — sinon une
    # étape générique). Ses gardes (signé/froid/perdu/archivé) décident
    # seules : la liste ne se termine que par Froid ou Signé.
    if _prochaine_touche_a_faire(lead) is None:
        # RELANCE-SUITE (08/09/2026) — seul le fait de COCHER l'étape
        # « préparer et envoyer le devis » vaut « devis parti » : elle seule
        # démarre le suivi de proposition sur un devis resté brouillon (cas
        # AR). Toute autre touche laissée sans suite reçoit une étape
        # générique — le suivi de proposition, lui, démarre à l'ENVOI.
        # (Détection hissée en tête de fonction — `devis_parti`, SUIVI E7 :
        # une étape devis SAUTÉE ne vaut jamais « devis parti ».)
        assurer_prochaine_etape_apres_succes(
            lead, user, brouillon_compris=devis_parti,
            libelle_touche_close=(etape.libelle or ''),
            # PARAM-CADENCE — la CLÉ de la touche close voyage avec elle : la
            # ceinture et l'escalier la lisent, jamais le libellé.
            cle_touche_close=cle_de(etape),
            # CAD3 — l'issue voyage avec le libellé : la ceinture doit pouvoir
            # distinguer « le client a demandé un rappel » d'un arbitrage.
            issue_touche_close=(outcome or '').strip(),
            # CAD2 — une étape de VISITE close (confirmer, débrief, devis
            # modifié, planifier) ne DÉMARRE jamais le suivi de proposition :
            # « Client joint » sur un débrief relançait tout le plan depuis
            # « Le PDF s'ouvre bien ? ». Le poursuivre reste permis (CAD1).
            # SUIVI E13 — sauf « devis modifié envoyé » : un devis part, son
            # suivi démarre (ou se poursuit).
            demarrer_plan=devis_parti or not est_etape_de_visite(etape))
    return etape


# ── RLC1 — ANNULER UNE TOUCHE TRAITÉE PAR ERREUR (retour arrière < 24 h) ─────
#
# Relevé fondateur du 08/09/2026 (lead test1 aa) : « une touche "Fait" par
# erreur ne se défait pas ». Ce qui manquait n'est pas un journal de plus —
# c'est le RETRAIT d'un geste, journalisé comme tout le reste.
#
# TROIS RÈGLES, et rien d'autre :
#   1. on ne défait QUE ce que le code PROUVE défaisable. Chaque effet annulé
#      ci-dessous est rattaché à sa clôture par une preuve datée (``created_at``
#      d'une étape née dans la fenêtre de la clôture, ``traite_le`` d'une touche
#      annulée par l'arrêt de cadence, entrée de chatter du mouvement d'étape) ;
#   2. un effet devenu irréversible donne un REFUS MOTIVÉ nommant le champ
#      fautif — jamais une annulation à moitié faite qui laisserait le plan
#      incohérent. Irréversibles : devis parti (le lead est passé « Devis
#      envoyé »), cadence clôturée (dossier parqué au Froid avec ses réveils),
#      lead signé ou perdu, touche suivante déjà traitée, étape du lead
#      déplacée depuis par quelqu'un d'autre ;
#   3. rien n'est EFFACÉ de l'historique : la ligne de chatter de la touche
#      reste (elle dit la vérité de ce qui a été saisi), et l'annulation AJOUTE
#      sa propre note système qui dit qui a annulé et ce qui a été défait.

#: RLC1 — au-delà, une touche traitée ne s'annule plus (« depuis moins de
#: 24 h »). Le contrôle est SERVEUR ; l'écran n'affiche le bouton que dans la
#: même fenêtre, jamais l'inverse.
ANNULATION_TOUCHE_HEURES = 24

#: RLC1 — largeur de la fenêtre qui RATTACHE un effet à la clôture qui l'a
#: produit. Toute la cascade de ``marquer_etape_relance`` (matérialisation de la
#: touche suivante, arrêt de cadence par le récepteur MRY9, filets, mouvement
#: d'étape du funnel) est SYNCHRONE dans la requête qui a coché la touche :
#: deux minutes sont une borne très large pour une requête HTTP, et assez
#: étroite pour ne pas attraper un geste ultérieur indépendant sur le lead.
_ANNULATION_FENETRE_EFFETS = datetime.timedelta(minutes=2)

#: RLC1 — les issues qui valent « le client a RÉPONDU » : ce sont elles qui
#: font avancer le funnel (récepteur QJ7). Si une AUTRE activité du lead en
#: porte une, l'avance d'étape est confirmée par ailleurs et l'annulation de
#: CETTE touche ne la défait pas (règle fondateur : « annulée si aucune autre
#: réponse ne l'a confirmée »).
_OUTCOMES_REPONSE_CONFIRMEE = ISSUES_CLIENT_JOINT


class AnnulationToucheRefusee(Exception):
    """RLC1 — refus MOTIVÉ d'une annulation de touche.

    Porte le CHAMP fautif et le message exact à afficher sous lui (règle
    fondateur du 08/09/2026) — jamais un « action impossible » générique qui
    laisserait l'utilisatrice deviner ce qui bloque."""

    def __init__(self, champ, message):
        super().__init__(message)
        self.champ = champ
        self.message = message


def _stage_depuis_libelle(valeur):
    """La clé d'étape STAGES.py derrière une valeur de chatter.

    Le chatter stocke le LIBELLÉ FR (``activity._display``) ; d'anciennes
    écritures portent la clé brute — les deux sont acceptées, comme le fait
    déjà la vérification d'annulation LB39. ``None`` si la valeur ne désigne
    aucune étape connue : on ne devine JAMAIS une étape."""
    brut = (valeur or '').strip()
    if not brut:
        return None
    if brut in stages.STAGES:
        return brut
    for cle, libelle in stages.STAGE_LABELS.items():
        if brut == libelle:
            return cle
    return None


def _activite_de_cloture(etape, *, debut, fin):
    """RLC1 — l'unique ligne de chatter que ``marquer_etape_relance`` a écrite
    pour CETTE clôture (celle qui porte son issue).

    Reconnue par son corps (« Touche « <libellé> » … ») dans la fenêtre de la
    clôture : c'est la seule activité de toute la cascade à porter un
    ``outcome``, ce qui permet de la distinguer d'une réponse saisie AILLEURS.
    ``None`` si elle est introuvable — l'appelant retombe alors sur la fenêtre,
    jamais sur une supposition."""
    return (etape.lead.activites
            .filter(created_at__gte=debut, created_at__lte=fin,
                    body__startswith=prefixe_activite_touche(etape))
            .order_by('created_at', 'pk').first())


def _defaire_avance_funnel(lead, user, mouvements, *, debut, fin, cloture):
    """RLC1 — défait l'avance d'étape produite par la clôture qu'on annule.

    ``mouvements`` = les entrées de chatter ``field='stage'`` écrites dans la
    fenêtre ``[debut, fin]`` de la clôture, dans l'ordre. L'étape est ramenée à
    l'``old_value`` du PREMIER mouvement : la chaîne entière (NEW → Contacté,
    puis le cran suivant si l'issue en a déclenché deux) se défait d'un coup,
    jamais à moitié.

    NE défait RIEN quand une AUTRE réponse confirmée du client existe sur le
    lead : l'avance tient alors de CELLE-LÀ, et la retirer effacerait un fait
    vrai (règle fondateur : « annulée si aucune autre réponse ne l'a
    confirmée »). « Autre » = toute activité à issue joint/intéressé saisie par
    un humain, sauf la ligne de la clôture elle-même (``cloture``) — à défaut de
    savoir laquelle c'est, toute la fenêtre de la clôture est écartée.

    Renvoie ``(ancienne_cle, nouvelle_cle)`` si l'étape a bougé, sinon
    ``None``. Passe par ``appliquer_stage_lead`` (point de passage canonique
    CRX20) : aucun déplacement d'étape muet."""
    if not mouvements:
        return None
    autres_reponses = lead.activites.filter(
        outcome__in=_OUTCOMES_REPONSE_CONFIRMEE, user__isnull=False)
    if cloture is not None:
        autres_reponses = autres_reponses.exclude(pk=cloture.pk)
    else:
        autres_reponses = autres_reponses.exclude(
            created_at__gte=debut, created_at__lte=fin)
    if autres_reponses.exists():
        return None
    cible = _stage_depuis_libelle(mouvements[0].old_value)
    if cible is None or cible == lead.stage:
        return None
    ancien = lead.stage
    if not appliquer_stage_lead(lead, cible, user=user):
        return None
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS.get(ancien, ancien),
        new_value=stages.STAGE_LABELS.get(cible, cible),
        body='annulation de touche — avance automatique défaite')
    return ancien, cible


def annuler_touche_relance(etape, user):
    """RLC1 — Annule une touche « Fait »/« Sautée » traitée par erreur.

    La touche redevient ``a_faire`` à SON échéance d'origine (``due_at``/
    ``due_date`` n'ont jamais bougé — seuls statut, note et traçabilité de
    clôture sont retirés), et les effets automatiques de son issue sont défaits
    dans la mesure où le code les prouve défaisables :

      * les touches ANNULÉES par l'arrêt de cadence que cette issue a
        déclenché (récepteur MRY9, ``traite_par`` NULL + motif en note)
        redeviennent ``a_faire`` ;
      * l'étape que cette clôture a fait NAÎTRE — barreau suivant du protocole
        (``materialiser_touche_suivante``) ou étape de filet
        (``assurer_prochaine_etape_apres_succes`` / visite) — est supprimée ;
      * l'avance d'étape du funnel (NEW → Contacté, et le cran suivant s'il a
        été franchi dans le même geste) est défaite quand aucune AUTRE réponse
        du client ne l'a confirmée.

    Refus motivé (``AnnulationToucheRefusee``, champ + message exact) quand un
    effet n'est plus défaisable — voir le bloc de doctrine au-dessus.

    Journalise UNE note système (``user`` NULL — annuler est un geste tracé,
    pas une prise de contact ; le nom de l'auteur vit dans le texte) qui dit
    qui a annulé et ce qui a été défait. Renvoie la touche remise à faire."""
    from django.db import transaction

    if etape.statut not in (RelanceEtape.Statut.FAIT,
                            RelanceEtape.Statut.SAUTEE):
        raise AnnulationToucheRefusee(
            'statut',
            "Cette touche n'a pas été traitée par quelqu'un : il n'y a rien "
            'à annuler.')
    if etape.traite_le is None:
        raise AnnulationToucheRefusee(
            'traite_le',
            "Cette touche ne porte pas d'horodatage de traitement : son "
            "annulation ne peut pas être bornée aux "
            f'{ANNULATION_TOUCHE_HEURES} h.')
    if (timezone.now() - etape.traite_le
            > datetime.timedelta(hours=ANNULATION_TOUCHE_HEURES)):
        raise AnnulationToucheRefusee(
            'traite_le',
            f'Passé {ANNULATION_TOUCHE_HEURES} h, une touche traitée ne '
            "s'annule plus. Relancez la cadence depuis la fiche.")

    lead = etape.lead
    if lead.pk:
        lead.refresh_from_db(fields=['stage', 'perdu', 'ne_plus_contacter'])
    if lead.perdu:
        raise AnnulationToucheRefusee(
            'lead',
            'Ce lead est marqué perdu : rouvrez-le avant d\'annuler une '
            'touche de son plan.')
    if lead.ne_plus_contacter:
        # CAD5 — rouvrir des touches sur un client qui a demandé qu'on ne le
        # contacte plus violerait la garde dure (loi 09-08 art. 9 al. 2).
        # L'opposition se lève sur la FICHE, par un humain, jamais par un
        # retour arrière de touche.
        raise AnnulationToucheRefusee(
            'lead',
            'Ce lead est marqué « Ne plus contacter » : décochez la case sur '
            'la fiche avant d\'annuler une touche de son plan.')
    if lead.stage == stages.SIGNED:
        raise AnnulationToucheRefusee(
            'lead',
            'Ce lead est signé : les touches de son plan ne se rouvrent plus.')

    debut = etape.traite_le
    fin = debut + _ANNULATION_FENETRE_EFFETS
    # Ce que CETTE clôture a fait naître (preuve : l'horodatage de création).
    nees = lead.relance_etapes.filter(
        created_at__gte=debut, created_at__lte=fin).exclude(pk=etape.pk)
    if nees.filter(cadence='reveil').exists():
        raise AnnulationToucheRefusee(
            'statut',
            'Cette touche a clôturé la cadence : le dossier est parti au '
            'froid avec ses réveils. Utilisez « Relancer la cadence » sur la '
            'fiche plutôt que cette annulation.')
    if nees.exclude(statut=RelanceEtape.Statut.A_FAIRE).exists():
        raise AnnulationToucheRefusee(
            'statut',
            "L'étape programmée par cette touche a déjà été traitée : "
            "annuler celle-ci n'est plus possible.")

    mouvements = list(lead.activites.filter(
        kind=LeadActivity.Kind.MODIFICATION, field='stage',
        created_at__gte=debut, created_at__lte=fin,
    ).order_by('created_at', 'pk'))
    if any(_stage_depuis_libelle(m.new_value) == stages.QUOTE_SENT
           for m in mouvements):
        raise AnnulationToucheRefusee(
            'statut',
            "Cette touche a acté l'envoi du devis (le lead est passé « "
            f'{stages.STAGE_LABELS[stages.QUOTE_SENT]} ») : cet effet ne se '
            'défait pas ici.')
    if mouvements:
        arrivee = _stage_depuis_libelle(mouvements[-1].new_value)
        if arrivee is not None and lead.stage != arrivee:
            raise AnnulationToucheRefusee(
                'lead',
                "L'étape du lead a changé depuis : l'avance produite par "
                'cette touche ne peut plus être défaite.')

    with transaction.atomic():
        # L'ÉTAPE DU LEAD D'ABORD, les touches ensuite — l'ordre compte : un
        # retour vers COLD réveille le récepteur d'arrêt de cadence (MRY9 (b)),
        # qui n'annule que les touches encore À FAIRE. Défaire l'avance AVANT
        # de rouvrir les touches les met donc hors de sa portée ; l'inverse les
        # aurait refermées dans la seconde.
        mouvement_defait = _defaire_avance_funnel(
            lead, user, mouvements, debut=debut, fin=fin,
            cloture=_activite_de_cloture(etape, debut=debut, fin=fin))
        supprimees = sorted(
            (e.libelle or e.get_canal_display())
            for e in nees.only('libelle', 'canal'))
        nees.delete()
        # Les touches retirées du plan par l'ARRÊT de cadence déclenché par
        # cette issue : elles n'ont jamais été traitées par un humain
        # (`traite_par` NULL), leur motif vit en note — les deux repartent.
        restaurees = lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.ANNULEE,
            traite_le__gte=debut, traite_le__lte=fin,
        ).update(statut=RelanceEtape.Statut.A_FAIRE, note='', traite_le=None)
        libelle = (etape.libelle or '').strip() or etape.get_canal_display()
        etape.statut = RelanceEtape.Statut.A_FAIRE
        etape.note = ''
        etape.traite_par = None
        etape.traite_le = None
        etape.save(update_fields=['statut', 'note', 'traite_par', 'traite_le'])
        # ACRM37 — LE recalage unique de la file.
        _recaler_file(lead, user)
        # JAMAIS un prénom en dur : l'auteur vient de la variable `user`.
        qui = getattr(user, 'username', '') or 'système'
        morceaux = [
            f'Annulation par {qui} : touche « {libelle} » '
            f'({etape.get_canal_display()}, cadence {etape.cadence}) remise '
            f'à faire au {etape.due_date:%d/%m/%Y}.']
        if restaurees:
            morceaux.append(
                f'{restaurees} touche(s) remise(s) à faire '
                "(arrêt de cadence défait).")
        if supprimees:
            morceaux.append(
                'Étape(s) programmée(s) par cette touche retirée(s) : '
                + ', '.join(f'« {s} »' for s in supprimees) + '.')
        if mouvement_defait:
            ancien, cible = mouvement_defait
            morceaux.append(
                'Étape du lead ramenée de « '
                f'{stages.STAGE_LABELS.get(ancien, ancien)} » à « '
                f'{stages.STAGE_LABELS.get(cible, cible)} ».')
        activity.log_note(lead, None, ' '.join(morceaux))
    return etape


#: MRY11 × MRY9 — les issues qui INTERDISENT la clôture, même sur la dernière
#: touche : on a joint la personne (ou on est convenu d'un rappel). La mettre
#: au froid et l'étiqueter « injoignable » serait l'inverse du bon geste.
#: B1 (revue Fable 07/09/2026) — ``refuse`` aussi : le client a RÉPONDU.
#: Clôturer l'étiquetterait « Injoignable » et lui enverrait des réveils
#: J30/J60 « vous étiez injoignable » ; le filet « décider la suite » (posé
#: par le récepteur MRY9) assure déjà la suite du dossier.
#: VISITE-CADENCE — « visite acceptée » aussi, évidemment : envoyer au parking
#: Froid, étiqueté « Injoignable », un client qui vient d'accepter de recevoir
#: le technicien chez lui serait l'erreur la plus grossière du moteur.
_OUTCOMES_SANS_CLOTURE = frozenset({'joint', 'interesse', 'rappel', 'refuse',
                                    OUTCOME_VISITE_ACCEPTEE})


#: MRY11 — ce que devient un lead dont la cadence s'est épuisée sans réponse.
#: Le tag NOMME la raison : « injoignable » et « devis sans suite » ne se
#: traitent pas de la même façon au réveil.
#: « 6 appels » et non « 7 tentatives » : le Protocole v3 compte SIX appels
#: (plus cinq WhatsApp) — l'étiquette affichée à Meryem doit dire ce que la
#: cadence a réellement fait. Migration 0093 pour l'existant.
_CLOTURE_TAG_INJOIGNABLE = 'Injoignable 6 appels'
#: SUIVI E26 (décision fondateur du 30/09/2026) — la cadence COURTE « deuxième
#: affaire » (CAD128, un message et un appel) s'épuise comme la prise de
#: contact : parking Froid + réveils. Son étiquette dit ce que CETTE cadence a
#: réellement fait — jamais « 6 appels », elle n'en compte qu'un.
_CLOTURE_TAG_DEUXIEME_AFFAIRE = 'Deuxième affaire sans réponse'
_CLOTURE_TAGS = {
    'contact': _CLOTURE_TAG_INJOIGNABLE,
    'apres_devis': 'Devis sans suite',
    'deuxieme_affaire': _CLOTURE_TAG_DEUXIEME_AFFAIRE,
}

#: MRY11 — étape la plus AVANCÉE qu'une cadence puisse encore parquer.
#: `_bulk_stage_allowed` autorise « vers COLD » depuis N'IMPORTE OÙ (c'est
#: voulu pour une mise au parking manuelle) : sans ce plafond, épuiser une
#: cadence `contact` sur un lead qui a depuis SIGNÉ le ferait retomber au
#: froid — un devis signé effacé par un rappel resté ouvert.
_CLOTURE_PLAFOND = {
    'contact': stages.CONTACTED,
    'apres_devis': stages.FOLLOW_UP,
    # SUIVI E26 — la deuxième affaire est la prise de contact d'un client
    # acquis qui revient (une fiche NEUVE) : même plafond que ``contact``.
    # Avant, sa dernière touche sans réponse posait « Préparer et envoyer le
    # devis » le lendemain — un chiffrage réclamé pour quelqu'un que personne
    # n'avait eu au téléphone, alors que le guide annonçait le Froid.
    'deuxieme_affaire': stages.CONTACTED,
}

#: SUIVI E19 — le motif écrit sur une étape de filet annulée parce que le
#: dossier part au parking Froid (``cloturer_cadence``).
MOTIF_PARQUE_AU_FROID = 'dossier parqué au Froid'


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


#: MRY34 — libellé du FILET « client joint » : l'étape unique posée quand une
#: cadence s'arrête sur une issue de SUCCÈS (joint/intéressé) sans qu'aucune
#: autre étape ne reste ouverte. Sans elle, le lead qu'on venait de JOINDRE
#: disparaissait de toutes les vues de relance (incident du 07/09/2026 : onze
#: touches barrées « joint », plus AUCUNE prochaine étape) — l'inverse exact
#: de MRY11, qui ne parque au froid que les cadences épuisées SANS réponse.
#: RELANCE-SUITE (fondateur 08/09/2026, lead test1 aa) — l'ancien libellé,
#: encore porté par les étapes posées avant le 08/09 : coché, il vaut « devis
#: parti » exactement comme le nouveau.
#:
#: PARAM-CADENCE (décision fondateur du 25/09/2026) — ces libellés sont
#: désormais les DÉFAUTS LIVRÉS du gabarit « Après l'appel (avant devis) »
#: de Paramètres (``apps/parametres/models_relance.py``, source unique) : une
#: société peut les renommer. Le moteur ne compare plus JAMAIS un libellé —
#: il reconnaît une étape par sa CLÉ (``cadence_config.est_etape``). Les noms
#: ci-dessous restent des alias des défauts, pour les lecteurs historiques.
_FILET_JOINT_LIBELLE_ANCIEN = cadence_config.LIBELLE_DEVIS_ANCIEN
FILET_JOINT_LIBELLE = gabarit_relance.LIBELLE_DEVIS

#: RELANCE-SUITE — le client a RÉPONDU à un MESSAGE (WhatsApp, e-mail) : la
#: suite est de L'APPELER, au prochain créneau d'appel — jamais le suivi de
#: proposition avant qu'un devis soit parti (« je fais le devis, je l'envoie,
#: PUIS vos étapes viennent »).
FILET_APPEL_LIBELLE = gabarit_relance.LIBELLE_APPEL_APRES_REPONSE
_KINDS_MESSAGE = frozenset({LeadActivity.Kind.WHATSAPP, LeadActivity.Kind.EMAIL})

#: QJ-INVARIANT — libellé du filet après un REFUS (téléphonique ou de devis) :
#: la suite d'un refus est une décision HUMAINE (MRY22), mais le dossier ne
#: doit pas disparaître des files en attendant qu'elle soit prise.
FILET_REFUS_LIBELLE = gabarit_relance.LIBELLE_DECIDER_SUITE

#: CAD3 — le filet posé après un RAPPEL CONVENU. « Rappelle-moi la semaine
#: prochaine » est la réponse la plus fréquente avant décision : la ceinture
#: anti-tapis-roulant renommait pourtant l'étape « Décider la suite — perdu
#: (motif) ou relance ultérieure », c'est-à-dire un arbitrage, là où le client
#: a seulement demandé du temps. Le nom de l'étape doit dire la vérité.
FILET_RAPPEL_LIBELLE = gabarit_relance.LIBELLE_RAPPEL_CONVENU

#: CAD102 — les deux paliers de « il a écrit, puis il ne décroche plus ».
#: L'appel du filet resté sans réponse envoyait directement sur « préparer et
#: envoyer le devis » : l'ERP réclamait un chiffrage pour quelqu'un que
#: personne n'avait jamais eu au téléphone. On tente d'abord de le JOINDRE —
#: un message pour convenir d'un créneau, puis un dernier appel — et seulement
#: ensuite on parle de devis. Ce sont des étapes de FILET, pas des barreaux du
#: protocole : le nombre de touches de la cadence ne bouge pas.
FILET_MESSAGE_CRENEAU_LIBELLE = gabarit_relance.LIBELLE_MESSAGE_CRENEAU
FILET_DERNIER_APPEL_LIBELLE = gabarit_relance.LIBELLE_DERNIER_APPEL

#: CAD54 — la touche qui DIT au client que son dossier change de mains. C'est
#: une étape de FILET (posée par le moteur, hors protocole), déclarée ici avec
#: ses sœurs pour que `_LIBELLES_FILET` la connaisse sans second littéral.
PASSATION_LIBELLE = 'Passation — prévenir le client du changement de conseiller'

#: CAD7 — le client NÉGOCIE le prix : le suivi de proposition se met en PAUSE
#: le temps de préparer l'appel du fondateur. Étape de FILET (posée par le
#: moteur, hors protocole) : la traiter rouvre le suivi au barreau suivant
#: (CAD1). Aucun texte d'offre n'y est attaché — l'offre ne part JAMAIS avant
#: la décision du fondateur (CAD60).
QUESTION_PRIX_LIBELLE = (
    'Question de prix — préparer l’appel du fondateur (aucune offre avant '
    'sa décision)')

#: CKP2 — les libellés des étapes POSÉES PAR LE FILET. Elles portent la
#: cadence `generique` sans être un barreau du gabarit `generique` : leur suite
#: est décidée par `assurer_prochaine_etape_apres_succes`, jamais par la
#: matérialisation réactive (`materialiser_touche_suivante` les ignore).
#: PARAM-CADENCE — les deux étapes HORS gabarit (passation, question de prix)
#: n'ont pas de clé : elles restent reconnues par leur libellé, qui n'est pas
#: réglable.
_LIBELLES_FILET_HORS_GABARIT = frozenset({
    PASSATION_LIBELLE,  # CAD54
    QUESTION_PRIX_LIBELLE,  # CAD7
})
#: Les libellés PAR DÉFAUT des étapes de filet (les étapes posées avant la
#: clé en portent un) — un lecteur ne s'en sert plus pour RECONNAÎTRE une
#: étape (``est_etape_de_filet``/``q_filet``), seulement pour les nommer.
_LIBELLES_FILET = (cadence_config.libelles_par_defaut(*CLES_APRES_CONTACT)
                   | _LIBELLES_FILET_HORS_GABARIT)

# ── VISITE-CADENCE — LES TROIS GESTES DU RENDEZ-VOUS ────────────────────────
#
# Doctrine fondateur (15/09/2026) : la visite technique n'est pas un préalable
# à l'étude, c'est un OUTIL DE CLOSING posé APRÈS l'envoi du devis, pendant que
# le client est chaud. Le suivi doit donc RÉAGIR à elle — et jusqu'ici il
# l'ignorait complètement : une visite pouvait être calée, faite, validée, sans
# qu'une seule touche de relance bouge.
#
# Trois libellés, trois moments, et rien de plus :
#   1. le client a dit oui au principe → CALER la date ;
#   2. la date est posée → la CONFIRMER la veille (le premier motif
#      d'échec d'une visite terrain est un client absent) ;
#   3. le technicien est reparti → RAPPELER dans les 24-48 h, quand tout est
#      encore frais. C'est le geste que la visite existe pour provoquer.
#: PARAM-CADENCE — défauts livrés du gabarit « Visite technique » de
#: Paramètres (source unique), réglables par société ; alias historiques.
VISITE_FILET_LIBELLE = gabarit_relance.LIBELLE_PLANIFIER
VISITE_CONFIRMATION_LIBELLE = gabarit_relance.LIBELLE_CONFIRMATION
VISITE_DEBRIEF_LIBELLE = gabarit_relance.LIBELLE_DEBRIEF

#: AMENDEMENT FONDATEUR n°2 (15/09/2026) — quand le terrain rapporte que le
#: devis est « à modifier » ou « à refaire », le débrief change de NATURE : la
#: prochaine chose à faire n'est plus de rappeler pour conclure, c'est de
#: PRÉPARER le devis corrigé. L'étape porte donc un autre libellé — et c'est
#: l'envoi du nouveau devis qui déclenchera sa propre cadence, par la mécanique
#: existante ; rien n'est câblé ici pour ça.
VISITE_DEVIS_LIBELLE = gabarit_relance.LIBELLE_DEVIS_MODIFIE

#: Les deux libellés PAR DÉFAUT que peut porter l'étape de débrief. Elle est
#: UNE, quelle que soit sa nature : la retrouver par ses DEUX clés (et jamais
#: par une seule) est ce qui empêche une re-qualification de laisser deux
#: débriefs dans la file.
_LIBELLES_DEBRIEF = (VISITE_DEBRIEF_LIBELLE, VISITE_DEVIS_LIBELLE)
_CLES_DEBRIEF = (CLE_DEBRIEF, CLE_DEVIS_MODIFIE)

#: Les libellés PAR DÉFAUT des quatre gestes de visite (lecteurs historiques
#: seulement : la reconnaissance passe par ``est_etape_de_visite``).
_LIBELLES_VISITE = cadence_config.libelles_par_defaut(*CLES_VISITE)


def est_etape_de_visite(etape):
    """PARAM-CADENCE — un des gestes du rendez-vous de visite (planifier,
    confirmer, débrief, devis modifié), reconnu par sa CLÉ."""
    return est_etape(etape, *CLES_VISITE)


def q_visite():
    """``est_etape_de_visite`` en requête."""
    return q_etape(*CLES_VISITE)


def _q_plan_ouvert():
    """ACRM46 — LE prédicat « plan ouvert » (TREADMILL-1538) : une touche
    de cadence À FAIRE qui n'est pas un geste de visite. Partagé par
    ``initialiser_plan_relance`` (idempotence) et le placement des anciens
    leads (``deja_en_cadence``) : des touches toutes closes ne tiennent plus
    un lead."""
    from django.db.models import Q

    return Q(statut=RelanceEtape.Statut.A_FAIRE) & ~q_visite()


def q_filet():
    """``est_etape_de_filet`` en requête : les étapes du gabarit « Après
    l'appel » (par clé, ou libellé par défaut) et les deux hors gabarit."""
    from django.db.models import Q

    return (q_etape(*CLES_APRES_CONTACT)
            | Q(cle='', libelle__in=tuple(_LIBELLES_FILET_HORS_GABARIT)))


def q_etape_moteur():
    """Toute étape posée par le moteur À CÔTÉ du protocole (filet ou
    visite) — jamais un barreau de gabarit de plan."""
    return q_filet() | q_visite()


def annuler_etapes_moteur_ouvertes(lead, *cles, note):
    """SUIVI-PARCOURS — ANNULE (statut moteur CKP1 : ``traite_par`` NULL, le
    motif dans ``note``) les étapes moteur encore ouvertes de ces CLÉS —
    reconnues par la clé, ou le libellé par défaut d'une étape posée avant
    la clé (``q_etape``). Une étape qui a rempli son office n'est jamais
    « sautée par un humain ». Renvoie le nombre d'étapes annulées."""
    if not cles:
        return 0
    return lead.relance_etapes.filter(
        q_etape(*cles), statut=RelanceEtape.Statut.A_FAIRE,
    ).update(statut=RelanceEtape.Statut.ANNULEE, note=(note or '')[:500],
             traite_par=None, traite_le=timezone.now())


def _canal_configure(config):
    """Le canal RÉEL d'une étape configurée — un gabarit réglé sur
    « visite » (canal de barreau historique) devient un appel (CAD58)."""
    canal = config.get('canal') or RelanceEtape.Canal.APPEL
    return (RelanceEtape.Canal.APPEL if canal == RelanceEtape.Canal.VISITE
            else canal)


def _echeance_configuree(lead, config, *, depuis=None, jours=None):
    """PARAM-CADENCE — l'échéance d'une étape de FILET configurée :
    ``depuis`` (maintenant) + ``delai_jours`` (ou ``jours`` imposé par
    l'appelant — le moment convenu devant le client) + ``delai_minutes`` ;
    ``heure_cible`` posée REMPLACE l'heure calculée, puis recalage sur la
    fenêtre du canal (même règle que ``calculer_echeances_cadence``, MRY8 /
    CAD21). Une étape ne naît jamais déjà échue (CAD22)."""
    from . import cadence_temps, horaires

    maintenant = timezone.now()
    base = depuis or maintenant
    delai = config['delai_jours'] if jours is None else jours
    vise = base + datetime.timedelta(
        days=delai, minutes=config.get('delai_minutes') or 0)
    heure = config.get('heure_cible')
    if heure is not None:
        vise = vise.astimezone(horaires.CASABLANCA).replace(
            hour=heure.hour, minute=heure.minute, second=0, microsecond=0)
    canal = _canal_configure(config)
    # D1 — un barreau moteur peut porter `dimanche_ok`/`samedi_ok` (réglé
    # depuis Paramètres, exactement comme un barreau du protocole) : sans ces
    # deux drapeaux, `prochain_creneau_appel` recale toujours sur le lundi,
    # même quand la société a explicitement ouvert le samedi ou le dimanche à
    # cette étape (même règle que `calculer_echeances_cadence`).
    echeance = horaires.prochain_creneau_appel(
        vise, lead.company, canal=canal, heure_cible=heure,
        dimanche=bool(config.get('dimanche_ok')),
        samedi=bool(config.get('samedi_ok')))
    if echeance < maintenant:
        # ACRM36 — les drapeaux du barreau voyagent jusqu'au recalage.
        echeance = cadence_temps.echeance_jamais_echue(
            echeance, company=lead.company, canal=canal,
            samedi=bool(config.get('samedi_ok')), heure_cible=heure)
    return echeance


def _jour_de_visite_configure(lead, config, jour):
    """L'échéance d'un geste de VISITE, ancré sur un JOUR (``date``) :
    ``heure_cible`` du barreau (09 h sinon) + ``delai_minutes``, recalé sur
    la fenêtre du canal."""
    from . import horaires

    heure = config.get('heure_cible') or datetime.time(9, 0)
    vise = datetime.datetime.combine(
        jour, heure, tzinfo=horaires.CASABLANCA) + datetime.timedelta(
            minutes=config.get('delai_minutes') or 0)
    # D1 — même garde-fou que `_echeance_configuree` : un barreau de visite
    # marqué `dimanche_ok`/`samedi_ok` doit tenir sa fenêtre, pas retomber sur
    # le lundi.
    return horaires.prochain_creneau_appel(
        vise, lead.company, canal=_canal_configure(config),
        heure_cible=config.get('heure_cible'),
        dimanche=bool(config.get('dimanche_ok')),
        samedi=bool(config.get('samedi_ok')))


#: Ces trois étapes portent la cadence ``apres_devis`` (elles suivent bien la
#: proposition, et l'écran les affiche dans la même frise) mais ne sont PAS des
#: barreaux du gabarit : leur ``ordre`` est délibérément HORS de la plage du
#: gabarit (1-10) pour qu'aucune matérialisation réactive ne puisse les
#: confondre avec un barreau, et pour qu'elles se rangent après lui à
#: échéance égale.
VISITE_ORDRE_CONFIRMATION = 90
VISITE_ORDRE_DEBRIEF = 91
VISITE_ORDRE_FILET = 92

#: La cadence dans laquelle vivent les trois gestes ci-dessus. NOMMÉE une fois
#: : le jour où le fondateur voudra une cadence « visite » distincte, il y a UN
#: endroit à changer.
VISITE_CADENCE = 'apres_devis'

#: Délai (jours) du filet : DEMAIN, recalé sur le prochain créneau d'appel de
#: la société (fenêtres MRY4). Si Meryem donne une date de rappel en marquant
#: la touche, `reporter_prochaine_touche` déplace ce filet sur SA date — le
#: J+1 n'est que le défaut quand aucune date n'est saisie.
FILET_JOINT_DELAI_JOURS = 1


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


#: MRY13 — la touche dont le texte est un SCRIPT à dire, pas un message à
#: coller : son lien wa.me ne doit donc porter aucun `?text=`.
_TEMPLATES_VOCAUX = frozenset({'vocal_j3'})

#: Placeholders que le rendu sait remplir. Un placeholder de cette liste resté
#: SANS valeur fait OMETTRE sa phrase — jamais un blanc, jamais un défaut.
_PLACEHOLDERS_RENDUS = (
    'civilite', 'nom', 'prenom', 'ville', 'reference', 'lien',
    'lien_rdv', 'date_validite', 'conseiller',
    # CAD96 (21/09/2026) — le nom de marque affiché (résolu côté serveur,
    # jamais codé en dur ; voir ``_nom_affiche_marque``).
    'marque',
    # VISITE-CADENCE (15/09/2026) — la date du RENDEZ-VOUS de visite technique
    # posée sur la fiche (``Lead.visite_prevue_le``), rendue « mardi 16
    # septembre ». Fiche sans date ⇒ valeur vide ⇒ la phrase entière est OMISE
    # comme n'importe quel autre placeholder non résolu : on ne confirme jamais
    # un rendez-vous dont on ignore le jour.
    'date_visite',
    # 08/09/2026 — la PREUVE de la touche `j4_preuve` (mois, ville et lien de
    # la page publique d'une `parametres.Realisation` réelle).
    # CAD95 (21/09/2026) — vidéo COURTE (30-60 s) du même chantier, proposée
    # EN PLUS du lien (jamais à la place) ; sa propre phrase est omise SEULE
    # (MRY13) quand `Realisation.lien_video` est vide.
    # CAD71 (21/09/2026) — `avis_google` : lien de la fiche Google, réglage
    # société (`CompanyProfile.lien_avis_google`) — PAS le lien du devis.
    'mois_preuve', 'ville_preuve', 'lien_preuve', 'puissance_preuve',
    'lien_video_preuve', 'lien_google',
    # CAD127 (21/09/2026) — l'origine RÉELLE du lead : le nom de la personne
    # qui l'a recommandé, et le mois où il nous avait consultés. Vides quand
    # la donnée n'existe pas ⇒ leur phrase est OMISE, jamais un crochet.
    'prescripteur', 'mois_dossier',
    # CIQ500 (05/10/2026) — la raison sociale du lead (``Lead.societe``,
    # nettoyée — contrat CIQ1 `lead_pro.json`). Vide ⇒ la phrase qui la porte
    # est OMISE (MRY13), jamais un blanc « pour  ».
    'societe')

#: Les trois placeholders de la preuve. Regroupés pour n'aller chercher une
#: réalisation QUE si le texte en porte au moins un (même discipline que
#: `{lien_rdv}` : aucun travail, aucune requête, quand ce n'est pas demandé).
_PLACEHOLDERS_PREUVE = ('{mois_preuve}', '{ville_preuve}', '{lien_preuve}',
                        '{puissance_preuve}', '{lien_video_preuve}')

#: Noms de mois en français, pour « posée en juillet 2026 ». Codés ici plutôt
#: que via une locale système : le rendu d'un message client ne doit pas
#: dépendre des locales installées sur le serveur.
_MOIS_FR = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre')


#: Jours de la semaine en français (lundi = 0, comme ``date.weekday()``).
#: Codés ici, comme ``_MOIS_FR`` juste au-dessus : le rendu d'un message client
#: ne doit dépendre d'aucune locale installée sur le serveur.
_JOURS_FR = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi',
             'dimanche')


def _date_visite_francais(valeur):
    """« mardi 16 septembre » à partir d'une date, ou '' si elle est inconnue.

    VISITE-CADENCE — la forme PARLÉE plutôt que « 16/09/2026 » : c'est un
    rendez-vous qu'on confirme à quelqu'un, pas une échéance administrative, et
    « mardi » est précisément l'information qui évite l'absence du client.
    L'ANNÉE est tue à dessein : on confirme la veille, elle n'apporte rien et
    alourdit la phrase.

    Une date absente rend une chaîne VIDE, ce qui fait OMETTRE la phrase
    (MRY13) — on n'écrit jamais un jour approximatif."""
    if valeur is None:
        return ''
    try:
        return (f'{_JOURS_FR[valeur.weekday()]} {valeur.day} '
                f'{_MOIS_FR[valeur.month - 1]}')
    except (AttributeError, IndexError, TypeError):
        return ''


def _mois_francais(valeur):
    """« juillet 2026 » à partir d'une date, ou '' si elle est inconnue.

    Une date absente rend une chaîne VIDE, ce qui fait omettre la phrase
    (MRY13) — on n'écrit jamais un mois approximatif."""
    if valeur is None:
        return ''
    try:
        return f'{_MOIS_FR[valeur.month - 1]} {valeur.year}'
    except (AttributeError, IndexError, TypeError):
        return ''


def _kwc_francais(valeur):
    """« 11,44 » / « 5 » à partir d'une puissance en kWc, ou '' si inconnue
    (la phrase « Puissance installée » est alors omise SEULE, MRY13)."""
    if valeur is None:
        return ''
    try:
        texte = f'{float(valeur):.2f}'.rstrip('0').rstrip('.')
    except (TypeError, ValueError):
        return ''
    return texte.replace('.', ',')


def _contexte_preuve(lead):
    """MRY-PREUVE — mois / ville / lien d'une réalisation RÉELLE pour ce lead.

    Le catalogue et le choix vivent dans l'app FONDATION `parametres`
    (`selectors.realisation_pour_lead` : même ville d'abord, sinon la plus
    proche dans le rayon, sinon la DERNIÈRE installation de la société —
    repli fondateur 08/09/2026) ; `crm` ne fait que consommer ce sélecteur. Aucune
    réalisation utilisable → les trois valeurs restent VIDES et
    `_omettre_phrases_incompletes` retire la phrase entière : jamais un
    chantier inventé, jamais un crochet laissé au client."""
    vide = {'mois_preuve': '', 'ville_preuve': '', 'lien_preuve': '',
            'puissance_preuve': '', 'lien_video_preuve': ''}
    try:
        from apps.parametres.selectors import realisation_pour_lead
        realisation = realisation_pour_lead(lead)
    except Exception:  # noqa: BLE001 — une preuve absente n'est jamais inventée
        logger.warning('Preuve J4 : catalogue illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return vide
    if realisation is None:
        return vide
    return {
        'mois_preuve': _mois_francais(realisation.mise_en_service),
        'ville_preuve': (realisation.ville or '').strip(),
        'lien_preuve': (realisation.url_page or '').strip(),
        'puissance_preuve': _kwc_francais(realisation.puissance_kwc),
        # CAD95 — vidéo courte EN PLUS du lien ; vide si la réalisation n'en
        # porte aucune (jamais un défaut inventé).
        'lien_video_preuve': (realisation.lien_video or '').strip(),
    }


def _omettre_phrases_incompletes(texte, manquants):
    """MRY13 — retire les phrases qui portent un placeholder sans valeur.

    Laisser un blanc à la place d'une date de validité ou d'une référence
    produirait un message client trompeur (« valable jusqu'au  »). On préfère
    perdre la phrase que mentir : découpe par ligne puis par « . », et on
    ne garde que les fragments dont tous les placeholders sont résolus."""
    if not manquants:
        return texte
    trous = ['{' + cle + '}' for cle in manquants]
    lignes_gardees = []
    for ligne in (texte or '').split('\n'):
        if not any(trou in ligne for trou in trous):
            lignes_gardees.append(ligne)
            continue
        morceaux = ligne.split('. ')
        gardes = [m for m in morceaux
                  if not any(trou in m for trou in trous)]
        if gardes:
            recolle = '. '.join(gardes)
            if ligne.rstrip().endswith('.') and not recolle.endswith('.'):
                recolle += '.'
            lignes_gardees.append(recolle)
    return '\n'.join(lignes_gardees).strip()


def _nom_affiche_conseiller(lead, user):
    """Règle fondateur du 08/09/2026 : aucun prénom de personne (Meryem,
    Reda) n'est codé en dur dans un message client — l'expéditeur affiché
    est TOUJOURS le RESPONSABLE du lead (``lead.owner``), jamais forcément
    l'utilisateur qui clique sur « Envoyer ». Repli sur le responsable par
    défaut des leads de la société (``CompanyProfile.responsable_defaut_leads``
    — même lecture que ``default_responsable_for``, sans son round-robin : on
    rend un message, on n'assigne pas un lead) ; en dernier repli seulement,
    l'utilisateur courant."""
    conseiller = getattr(lead, 'owner', None)
    if conseiller is None:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=lead.company).first()
        conseiller = profile.responsable_defaut_leads if profile else None
    if conseiller is None:
        conseiller = user
    if conseiller is None:
        return ''
    return (getattr(conseiller, 'first_name', '')
            or getattr(conseiller, 'username', '') or '')


def _nom_affiche_marque(lead):
    """CAD96 (21/09/2026) — le nom de marque AFFICHÉ dans un texte client.

    Trois graphies codées en dur coexistaient (« la marque », « la marque
    Solutions », « Taqinor Solutions ») dans le même guide de messages,
    incohérence déjà présente dans le document source validé. Plutôt que de
    figer UNE de ces graphies dans le code (une future société white-label
    hériterait du nom de la marque), la marque vient désormais de
    ``parametres.CompanyProfile.nom`` — même source que les PDFs (SCA27) —
    avec repli sur ``Company.nom`` si la société n'a pas encore de profil."""
    company = getattr(lead, 'company', None)
    if company is None:
        return ''
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — un profil illisible ne bloque jamais l'envoi
        profile = None
    nom = (getattr(profile, 'nom', '') or '').strip()
    if nom:
        return nom
    return (getattr(company, 'nom', '') or '').strip()


def _civilite_et_prenom(lead, langue):
    """``(civilite, prenom)`` de la salutation d'un message client.

    CAD65 (audit L3 du 21/09/2026) — la civilité vient de la DONNÉE
    ``Lead.civilite`` (M./Mme, saisie au premier contact), jamais d'un défaut
    codé en dur : le « M. » posé d'office le 07/09/2026 faisait écrire
    « Bonjour M. » à une cliente sur tous les messages. Rendu : « M. » /
    « Mme » en français, « السي » / « لالة » en darija. Civilité INCONNUE ⇒
    chaîne VIDE ⇒ salutation NEUTRE (le prénom seul), jamais un genre supposé
    — ``_placer_civilite`` retire alors le placeholder et son espace, sans
    faire sauter la phrase d'accueil.

    Sans prénom (formulaire Meta au nom seul, société), le NOM prend sa place
    dans la salutation plutôt que de faire SAUTER toute la phrase d'accueil.

    Extrait de ``message_pour_etape`` (VISITE-CADENCE) pour que le rendu d'un
    message de VISITE — qui n'a pas de touche derrière lui — s'adresse au
    client exactement de la même façon : deux copies de cette règle auraient
    fini par se vouvoyer différemment.
    """
    civilite = (getattr(lead, 'civilite', '') or '').strip()
    if langue == 'darija':
        civilite = _CIVILITE_DARIJA.get(civilite, '')
    elif civilite not in _CIVILITES_CONNUES:
        civilite = ''
    prenom = (lead.prenom or '').strip() or (lead.nom or '').strip()
    return civilite, prenom


def _societe_du_lead(lead):
    """CIQ500 — la raison sociale du lead telle que servie par le contrat
    CIQ1 (``Lead.societe``), NETTOYÉE : espaces de bord retirés et blancs
    internes réduits à un seul. Vide ⇒ ``''`` (la phrase qui porte
    ``{societe}`` est alors omise — MRY13 —, jamais un blanc)."""
    return ' '.join(str(getattr(lead, 'societe', '') or '').split())


#: CAD65 — les civilités du lead (``Lead.Civilite``) et leur rendu darija.
_CIVILITES_CONNUES = ('M.', 'Mme')
_CIVILITE_DARIJA = {'M.': 'السي', 'Mme': 'لالة'}


def _placer_civilite(corps, civilite):
    """CAD65 — ``{civilite}`` est FACULTATIF : sans valeur, on retire le
    placeholder ET son espace (« Bonjour {civilite} {prenom} » → « Bonjour
    {prenom} »), au lieu de le compter manquant — ce qui ferait OMETTRE
    toute la phrase d'accueil (MRY13) — ou de laisser un double espace."""
    if civilite or '{civilite}' not in (corps or ''):
        return corps
    return (corps.replace('{civilite} ', '').replace(' {civilite}', '')
            .replace('{civilite}', ''))


#: VISITE-CADENCE — les clés de gabarit que le rendu « message de visite »
#: accepte. Liste FERMÉE : un `?cle=` inconnu est un 400 qui NOMME le champ,
#: jamais un message vide servi en 200 (l'écran croirait avoir un texte).
#: AGR414 — ``visite_releve_point_eau`` : la visite de relevé du point d'eau
#: proposée AVANT le devis agricole, avec sa liste de préparation (FR + darija).
CLES_MESSAGE_VISITE = (
    'visite_proposition', 'visite_confirmation', 'visite_releve_point_eau',
)

#: AGR526 — les textes des DOSSIERS institutionnels (playbooks de segment
#: CAD125) que le même rendu sert — mais SEULEMENT au lead pour qui
#: ``cle_message_segment`` renvoie cette clé (jamais un FDA à un exploitant
#: au gasoil, jamais un 82-21 à un résidentiel).
CLES_MESSAGE_DOSSIER = ('dossier_fda', 'dossier_8221')


def cle_message_visite_autorisee(lead, cle):
    """AGR526 — ``cle`` est-elle un texte que ``message-visite`` rend pour CE
    lead ? Une clé de visite toujours ; une clé de dossier seulement quand le
    playbook de segment du lead la confirme (``cle_message_segment``)."""
    if cle in CLES_MESSAGE_VISITE:
        return True
    return cle in CLES_MESSAGE_DOSSIER and cle_message_segment(lead) == cle


def cles_message_visite_du_lead(lead):
    """AGR526 — les clés que ``message-visite`` accepte pour CE lead (le
    refus 400 les NOMME)."""
    cles = list(CLES_MESSAGE_VISITE)
    dossier = cle_message_segment(lead)
    if dossier in CLES_MESSAGE_DOSSIER:
        cles.append(dossier)
    return cles


def message_visite_pour_lead(lead, cle, *, user=None, masquer_numero=False):
    """VISITE-CADENCE — le message de visite d'un LEAD, rendu côté serveur.

    ``{'corps_fr': str, 'corps_darija': str}`` — les DEUX langues d'un coup :
    l'écran propose le copier-coller dans celle que le client parle, sans
    second aller-retour.

    CAD111 — plus ``wa_url_fr`` / ``wa_url_darija`` / ``phone`` : le lien
    wa.me est construit CÔTÉ SERVEUR (numéro normalisé E.164 par
    ``build_wa_url`` — « 06… » devient « 2126… »), comme pour les touches
    normales ; l'écran ne fabrique plus un lien en chiffres bruts.
    ``masquer_numero`` (rôle sans ``client_pii_voir``) : aucun numéro ne sort
    — liens ``None``, ``phone`` vide, même règle que la file des relances.

    MÊME machinerie que les messages de cadence (``message_pour_etape``) :
    mêmes placeholders autorisés, même ``{conseiller}`` = le RESPONSABLE du
    lead (jamais un prénom codé en dur), et surtout même règle MRY13 — une
    phrase dont le placeholder n'a pas de valeur RÉELLE est OMISE. Un lead
    sans ``visite_prevue_le`` ne reçoit donc pas « la visite prévue  chez
    vous » : la phrase disparaît, et le reste du message tient debout.

    Le serveur REND, il n'ENVOIE pas (décision D5) — aucun appel sortant.

    Renvoie ``None`` si ``cle`` n'est pas une clé de visite connue : c'est
    l'appelant (la vue) qui en fait un 400 nommant le champ.
    """
    from apps.parametres.models_messages import MessageTemplate
    from apps.ventes.utils.whatsapp import build_wa_url, render_message_template

    # AGR526 — une clé de DOSSIER n'est rendue qu'au lead dont le playbook de
    # segment la confirme ; sinon ``None`` (la vue en fait un 400 sur ``cle``).
    if not cle_message_visite_autorisee(lead, cle):
        return None

    date_visite = _date_visite_francais(
        getattr(lead, 'visite_prevue_le', None))
    rendu = {}
    for champ, langue in (('corps_fr', 'fr'), ('corps_darija', 'darija')):
        civilite, prenom = _civilite_et_prenom(lead, langue)
        contexte = {
            'civilite': civilite,
            'nom': (lead.nom or '').strip(),
            'prenom': prenom,
            'ville': (lead.ville or '').strip(),
            'conseiller': _nom_affiche_conseiller(lead, user),
            'marque': _nom_affiche_marque(lead),
            'date_visite': date_visite,
            # CIQ500 — la raison sociale, vide ⇒ phrase omise (MRY13).
            'societe': _societe_du_lead(lead),
        }
        corps = MessageTemplate.get_corps(lead.company, cle, langue) or ''
        # CAD126 — variante de SEGMENT par exception (pompage / B2B).
        corps = _corps_pour_segment(corps, cle, lead, langue)
        # CAD65 — civilité inconnue : salutation neutre, jamais omise.
        corps = _placer_civilite(corps, civilite)
        manquants = [c for c in _PLACEHOLDERS_RENDUS
                     if '{' + c + '}' in corps
                     and not str(contexte.get(c, '')).strip()]
        rendu[champ] = render_message_template(
            _omettre_phrases_incompletes(corps, manquants), contexte)
    # CAD111 — les liens wa.me construits par le SERVEUR (E.164), un par
    # langue, jamais par l'écran ; aucun numéro pour un rôle sans droit PII.
    phone = '' if masquer_numero else (lead.whatsapp or lead.telephone or '')
    rendu['wa_url_fr'] = build_wa_url(phone, rendu['corps_fr']) if phone else None
    rendu['wa_url_darija'] = (build_wa_url(phone, rendu['corps_darija'])
                              if phone else None)
    rendu['phone'] = phone
    return rendu


#: CAD111 — les langues dans lesquelles le message de visite peut être ouvert
#: (les deux corps que `message_visite_pour_lead` rend).
LANGUES_MESSAGE_VISITE = ('fr', 'darija')


def journaliser_message_visite_ouvert(lead, user, *, cle, langue, etape=None):
    """CAD111 — le message de VISITE a été OUVERT dans WhatsApp (clic humain).

    Jumeau de ``journaliser_whatsapp_ouvert`` : une activité typée WhatsApp au
    chatter — comptée comme tentative et premier contact par les récepteurs —,
    journalisée comme « ouvert » et JAMAIS comme « fait » : aucune issue,
    aucune touche avancée, aucune cadence arrêtée. Quand le message est ouvert
    depuis une TOUCHE (``etape``, encore à faire), la ligne porte le préfixe
    RLC3 de cette touche : son panneau « Fait » sait alors que le message a
    été ouvert, au lieu de faire cocher l'aveu faux « marquée faite sans avoir
    ouvert le message ». Renvoie l'activité créée."""
    quoi = {
        'visite_proposition': 'proposer la visite',
        # AGR414 — la visite de relevé du point d'eau (agricole).
        'visite_releve_point_eau': 'proposer le relevé du point d’eau',
        # AGR526 — les textes de dossier des playbooks de segment.
        'dossier_fda': 'demander où en est le dossier de subvention FDA',
        'dossier_8221': 'demander où en est le dossier du site',
    }.get(cle, 'confirmer la visite')
    langue_txt = 'darija' if langue == 'darija' else 'français'
    if etape is not None:
        corps = (f'{prefixe_activite_message_ouvert(etape)} (cadence '
                 f'{etape.cadence}) : message de visite « {quoi} » ouvert en '
                 f'{langue_txt} ; la touche reste à faire jusqu’à la réponse '
                 'du client.')
    else:
        corps = (f'WhatsApp ouvert — message de visite « {quoi} » en '
                 f'{langue_txt} : message préparé, rien n’est marqué fait.')
    activite = LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.WHATSAPP, body=corps)
    marquer_premier_contact(lead)
    return activite


# ── CAD-F ── CAD63 — changer la langue AU MOMENT UTILE ───────────────────────
#
# Le texte d'une touche était rendu dans la langue de la fiche, point : si la
# commerciale découvrait au téléphone que le client ne lit pas le français,
# elle devait quitter la touche, ouvrir la fiche, changer le champ, revenir.
# La langue peut désormais être CHOISIE pour le message affiché (``langue=``
# sur le rendu) et ENREGISTRÉE sur le lead en un geste — la réponse « ne parle
# que darija » de la touche, ou la confirmation de l'aperçu. Le vocabulaire
# est celui du champ ``Lead.langue_preferee`` lui-même : aucune langue n'est
# ouverte ici sans texte validé derrière elle (CAD64 — ni l'anglais ni l'arabe
# classique tant que la relance n'en a pas).

def langues_relance():
    """CAD63 — les langues qu'on peut CHOISIR pour le message d'une touche :
    les valeurs du champ ``Lead.langue_preferee`` (lues sur le modèle, jamais
    recopiées)."""
    return tuple(Lead.LanguePreferee.values)


def refus_langue_relance(langue):
    """CAD63 — pourquoi ``langue`` n'est pas une langue de relance, ou
    ``None``. Le message NOMME la valeur reçue et les langues proposées
    (règle fondateur du 08/09/2026 : jamais un refus muet)."""
    langue = (langue or '').strip()
    if langue in langues_relance():
        return None
    proposees = ', '.join(
        f'« {valeur} » ({libelle})'
        for valeur, libelle in Lead.LanguePreferee.choices)
    return (f'« Langue du message » : « {langue} » n’est pas une langue de '
            f'relance. Langues proposées : {proposees}.')


def definir_langue_preferee(lead, user, langue):
    """CAD63 — pose ``Lead.langue_preferee`` et le JOURNALISE comme la fiche
    le ferait (ligne « modification » du chatter, ancien → nouveau).

    L'appelant a validé ``langue`` (``refus_langue_relance``). Idempotente :
    une langue déjà posée ne produit ni écriture ni ligne. Renvoie ``True``
    si la langue vient de changer."""
    import copy

    if (lead.langue_preferee or '') == langue:
        return False
    avant = copy.copy(lead)
    lead.langue_preferee = langue
    lead.save(update_fields=['langue_preferee'])
    activity.log_changes(avant, lead, user)
    return True


# ── CAD-F ── CAD64 — le repli de langue devient VISIBLE ─────────────────────
#
# Deux causes, un seul effet silencieux. (1) La langue de la relance se lisait
# ``lead.langue_preferee or 'fr'`` au lieu de passer par le résolveur COMMUN
# des documents client (``parametres.i18n_resolver.resolve_langue_sortie`` —
# ``Client.langue_document`` puis la langue de repli de la société) : un devis
# pouvait partir en arabe pendant que la relance restait en français, sans que
# rien ne le dise. (2) ``MessageTemplate.get_corps`` retombe sur le FRANÇAIS
# quand la clé n'a pas de texte dans la langue demandée — darija, anglais ou
# arabe classique — sans un mot. On ne traduit JAMAIS automatiquement : on
# PRÉVIENT (``repli_langue`` dans la réponse, avertissement à l'aperçu).

def langue_relance_du_lead(lead):
    """CAD64 — la langue DEMANDÉE pour les messages de relance de ce lead.

    La préférence posée sur le lead (``langue_preferee`` — FR ou darija, le
    seul registre de la relance WhatsApp) prime ; à défaut, le résolveur
    COMMUN des documents client (langue documentaire du client, puis repli de
    la société, puis FR). Aucun texte n'est ouvert ici : si la langue résolue
    n'a pas de texte validé pour une clé, le rendu retombe sur le français et
    le DIT (``repli_langue``)."""
    preference = (getattr(lead, 'langue_preferee', '') or '').strip()
    if preference:
        return preference
    from apps.parametres.i18n_resolver import resolve_langue_sortie
    return resolve_langue_sortie(
        client=getattr(lead, 'client', None),
        company=getattr(lead, 'company', None))


def texte_en_repli_de_langue(company, cle, langue):
    """CAD64 — le texte de ``cle`` retombe-t-il sur le FRANÇAIS faute
    d'exister dans ``langue`` ?

    Lu par l'API publique du catalogue (``MessageTemplate.get_corps``), jamais
    en recopiant sa règle : la langue demandée est en repli quand elle n'est
    pas le français et que son corps est EXACTEMENT le corps français."""
    if not cle or (langue or 'fr') == 'fr':
        return False
    from apps.parametres.models_messages import MessageTemplate
    corps_langue = MessageTemplate.get_corps(company, cle, langue) or ''
    if not corps_langue.strip():
        return False
    return corps_langue == (MessageTemplate.get_corps(company, cle, 'fr') or '')


# ── CAD-F ── CAD69 — les crochets [ ] ne partent plus en silence ────────────
#
# `render_message_template` ne substitue que les {accolades} et MRY13 n'omet
# que les phrases à accolades vides : un blanc écrit « [jour] », « [montant en
# dirhams] » dans un texte validé (`rappel_plus_tard`, `offre_reda`) partait
# TEL QUEL dans WhatsApp, alors que le catalogue promet « jamais un crochet
# vide envoyé au client ». Ces blancs sont à compléter À LA MAIN (on n'invente
# ni un jour ni un montant) : le rendu les LISTE, l'aperçu bloque l'ouverture
# tant qu'ils sont là.

#: Un blanc à compléter : un texte court entre crochets, sur une seule ligne.
_RE_CROCHET = _re.compile(r'\[[^\[\]\n]{1,80}\]')


def crochets_a_completer(texte):
    """CAD69 — les blancs ``[…]`` encore présents dans ``texte``, dans l'ordre
    d'apparition, sans doublon (``[]`` si aucun)."""
    vus = []
    for trou in _RE_CROCHET.findall(texte or ''):
        if trou not in vus:
            vus.append(trou)
    return vus


def message_pour_etape(etape, *, request=None, user=None, cle=None,
                       langue=None):
    """MRY13 — Le message d'UNE touche, rendu côté serveur.

    Forme `relance_etape_message` (contrat MRY25) :
    ``{message, wa_url, langue, phone, placeholders_manquants}``.

    CAD63 — ``langue`` (une de ``langues_relance()``, validée par
    l'appelant) force la langue du rendu pour CE message, sans toucher la
    fiche : c'est l'aperçu qu'on bascule FR ↔ darija au téléphone.

    CAD-A — ``cle`` (une des ``CLES_MESSAGE_REPONSE``) rend, pour le lead de
    cette touche, le texte de RÉPONSE convenu (« stop_contact » après « Ne
    plus me contacter », « rappel_plus_tard » après « Plus tard ») au lieu du
    gabarit de la touche. Même machinerie, même forme : l'écran propose
    l'envoi, le clic humain ouvre WhatsApp (décision D5).

    Le serveur RÉEND, il n'ENVOIE pas (décision D5) : l'écran montre une
    modale d'aperçu, et c'est le clic humain qui ouvre WhatsApp. Aucun BSP,
    aucun appel réseau sortant.

    Règle absolue du lot : AUCUN chiffre inventé. Une phrase dont le
    placeholder n'a pas de valeur réelle est OMISE (jamais un blanc, jamais un
    défaut), et `placeholders_manquants` le dit à l'appelant. Les prix, kWc et
    économies ne sont pas des placeholders du tout : ils restent dans le devis
    et la proposition."""
    from apps.parametres.models_messages import MessageTemplate
    from apps.ventes.utils.whatsapp import build_wa_url, render_message_template

    lead = etape.lead
    # CAD64 — la langue passe par le résolveur COMMUN (préférence du lead,
    # puis langue documentaire du client, puis repli société), jamais un
    # `or 'fr'` local qui laissait la relance en français pendant que le
    # devis partait en arabe.
    langue = langue or langue_relance_du_lead(lead)
    # CAD-A — le texte de réponse demandé remplace le gabarit de la touche.
    template_cle = cle or etape.template_cle
    # CAD127 — le premier message dit la VÉRITÉ sur l'origine : « vous venez
    # de remplir notre formulaire » est faux pour un lead venu par téléphone,
    # en boutique, par recommandation ou d'un message entrant. La clé est
    # choisie d'après le canal déjà enregistré, AVANT de lire le gabarit.
    cle_rendue = cle_identite_pour_lead(lead, template_cle,
                                        reference=etape.due_date)
    corps = MessageTemplate.get_corps(
        lead.company, cle_rendue, langue) if cle_rendue else ''
    # CAD64 — le texte n'existe pas dans la langue demandée : c'est la version
    # FRANÇAISE qui part, et on le DIT. Le texte est alors rendu comme un
    # texte français (civilité « M. »/« Mme » — CAD65 —, variante de
    # segment), jamais un « السي » collé dans une phrase française.
    repli_langue = texte_en_repli_de_langue(lead.company, cle_rendue, langue)
    langue_texte = 'fr' if repli_langue else langue
    # CAD126 — variante de SEGMENT par exception : « sur votre toit » ne part
    # pas à un pompage au bord d'un forage, « en famille » pas à une
    # entreprise. Par exception SEULEMENT, et jamais sur un texte que la
    # société a personnalisé.
    # CIQ506 — une touche de canal E-MAIL (sans texte de réponse demandé) se
    # rend dans sa FORME e-mail (`forme_email`, CIQ502 : objet + corps,
    # français, neutre de segment) ; sans forme pour sa clé — ou dans une
    # autre langue que le français —, le texte de la clé tient lieu de corps
    # (comme `relance_email_j10`), sans objet.
    est_email = (etape.canal == RelanceEtape.Canal.EMAIL and not cle)
    forme = None
    if est_email and langue_texte == 'fr':
        from apps.parametres.models_messages import forme_email
        forme = forme_email(template_cle)
    if forme:
        corps = forme['corps']
    else:
        corps = _corps_pour_segment(corps, cle_rendue, lead, langue_texte)
    objet_gabarit = forme['objet'] if forme else ''

    civilite, prenom = _civilite_et_prenom(lead, langue_texte)
    # CAD65 — civilité inconnue : salutation neutre, jamais omise.
    corps = _placer_civilite(corps, civilite)
    objet_gabarit = _placer_civilite(objet_gabarit, civilite)
    contexte = {
        'civilite': civilite,
        'nom': (lead.nom or '').strip(),
        'prenom': prenom,
        'ville': (lead.ville or '').strip(),
        'conseiller': _nom_affiche_conseiller(lead, user),
        'marque': _nom_affiche_marque(lead),
        # CIQ500 — la raison sociale du lead ; vide ⇒ phrase OMISE (MRY13)
        # et `societe` listé dans `placeholders_manquants`.
        'societe': _societe_du_lead(lead),
        'reference': '',
        'lien': '',
        'date_validite': '',
        # VISITE-CADENCE (revue Fable 15/09) — la touche « Confirmer la visite
        # (veille) » porte template_cle='visite_confirmation' et se rend par
        # ICI (ToucheMessageDialog → message/) : sans cette clé, la phrase
        # avec la date était TOUJOURS omise et le message ne confirmait rien.
        'date_visite': _date_visite_francais(
            getattr(lead, 'visite_prevue_le', None)),
        'lien_google': '',
        # CAD127 — l'origine réelle. Résolus seulement si le texte les
        # demande (aucune requête sinon) ; vides ⇒ phrase OMISE (MRY13).
        'prescripteur': (_nom_prescripteur(lead)
                         if '{prescripteur}' in (corps or '') else ''),
        'mois_dossier': (_mois_dossier_francais(lead)
                         if '{mois_dossier}' in (corps or '') else ''),
    }
    # CAD71 (21/09/2026) — {lien_google} : lien de la fiche Google de la
    # société, réglage dédié (`CompanyProfile.lien_avis_google`) — AVANT
    # ce champ, `avis_google` recevait le lien du DEVIS via `{lien}`, jamais
    # celui de la fiche Google. Résolu seulement si le texte le demande
    # (même discipline que `{lien_rdv}`/la preuve J4).
    if '{lien_google}' in (corps or ''):
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=lead.company).first()
        contexte['lien_google'] = (
            (profile.lien_avis_google if profile else '') or '').strip()
    if etape.devis_id:
        try:
            from apps.ventes.selectors import get_devis_by_pk
            from apps.ventes.utils.client_links import url_proposition
            devis = get_devis_by_pk(etape.devis_id)
            if devis is not None:
                contexte['reference'] = getattr(devis, 'reference', '') or ''
                # CAD59 — le message applique le MÊME repli que le PDF :
                # `date_validite` si posée, sinon date de création + le
                # réglage société `quote_validity_days`. Lire le seul champ
                # laissait MRY13 supprimer la phrase entière quand il était
                # vide, et le WhatsApp contredisait alors un PDF qui, lui,
                # affichait « valable jusqu'au X ». Règle #4 respectée : on ne
                # touche pas au moteur de rendu, on lit la MÊME règle.
                validite = _date_validite_comme_le_pdf(devis)
                if validite:
                    contexte['date_validite'] = validite.strftime('%d/%m/%Y')
                contexte['lien'] = url_proposition(devis) or ''
        except Exception:  # noqa: BLE001 — un lien absent n'est jamais inventé
            logger.warning(
                'MRY13: contexte devis illisible (étape #%s)',
                getattr(etape, 'pk', '?'), exc_info=True)

    # `{lien_rdv}` n'est résolu QUE s'il est présent (aucun jeton créé sinon),
    # et sa valeur rejoint le CONTEXTE au lieu d'être substituée tout de suite
    # dans le corps. C'était le trou : `resoudre_lien_rdv` remplaçait le
    # placeholder par '' quand la génération du jeton échouait, AVANT le calcul
    # des placeholders manquants — la phrase « réservez ici : {lien_rdv} »
    # n'était donc jamais omise et partait au client avec un blanc, exactement
    # ce que la règle « aucun chiffre/lien inventé » interdit.
    if '{lien_rdv}' in (corps or ''):
        contexte['lien_rdv'] = (
            resoudre_lien_rdv('{lien_rdv}', lead, request=request) or '')

    # La PREUVE de la touche J4 : mois, ville et lien d'une réalisation RÉELLE
    # de la société, choisie sur la ville du lead. Résolue seulement si le
    # texte la demande, et rejoignant le CONTEXTE (donc soumise au calcul des
    # placeholders manquants) — sans catalogue, la phrase est OMISE.
    # CAD70 — sans AUCUNE réalisation utilisable (le cas PAR DÉFAUT d'une
    # société qui n'a rien publié), les phrases de preuve sautent toutes et il
    # ne reste qu'une phrase orpheline (« Le suivi de production est en temps
    # réel… ») : la touche ne doit alors PAS proposer ce message. Le drapeau
    # `preuve_manquante` le dit à l'aperçu (et le POST `whatsapp/` le refuse).
    preuve_manquante = False
    if any(t in (corps or '') for t in _PLACEHOLDERS_PREUVE):
        preuve = _contexte_preuve(lead)
        contexte.update(preuve)
        preuve_manquante = not any(
            str(valeur).strip() for valeur in preuve.values())

    manquants = [cle for cle in _PLACEHOLDERS_RENDUS
                 if ('{' + cle + '}' in (corps or '')
                     or '{' + cle + '}' in objet_gabarit)
                 and not str(contexte.get(cle, '')).strip()]
    corps = _omettre_phrases_incompletes(corps, manquants)
    message = render_message_template(corps, contexte)
    # CIQ506 — l'objet : même contexte, même omission MRY13 (un objet dont le
    # placeholder n'a pas de valeur est OMIS, jamais un blanc ni un défaut).
    objet = render_message_template(
        _omettre_phrases_incompletes(objet_gabarit, manquants),
        contexte).strip() if objet_gabarit else ''

    phone = lead.whatsapp or lead.telephone or ''
    if est_email:
        # Une touche e-mail n'ouvre pas WhatsApp : `wa_url` vaut `null`, et le
        # lien `mailto:` est construit par le serveur. Rien n'est envoyé (D5).
        wa_url = None
    elif template_cle in _TEMPLATES_VOCAUX:
        # Le texte est le SCRIPT du vocal : on ouvre la conversation, on ne
        # pré-remplit rien — coller un script à dire serait absurde.
        wa_url = build_wa_url(phone, '')
        if wa_url:
            wa_url = wa_url.split('?text=')[0]
    else:
        wa_url = build_wa_url(phone, message)
    return {
        'message': message,
        'wa_url': wa_url,
        'langue': langue,
        'phone': phone,
        'placeholders_manquants': manquants,
        # CAD64 — `True` : le texte n'existe pas dans `langue`, la version
        # française part à sa place (l'aperçu le dit ; le cas se mesure).
        'repli_langue': repli_langue,
        # CAD69 — les blancs `[…]` à compléter à la main avant tout envoi
        # (l'aperçu bloque « Ouvrir WhatsApp » tant qu'il y en a).
        'crochets': crochets_a_completer(message),
        # CAD70 — `True` : le texte demande une preuve (J4) et la société n'a
        # AUCUNE réalisation publiée — jamais une preuve inventée ni un
        # chantier mélangé : l'aperçu remplace l'envoi par l'aide.
        'preuve_manquante': preuve_manquante,
        # CAD79 — `True` : le texte est le SCRIPT d'une note vocale à DIRE
        # (`wa_url` sans `?text=`), jamais un message écrit à envoyer.
        'vocal': template_cle in _TEMPLATES_VOCAUX,
        # CIQ506 — l'objet de l'e-mail (chaîne VIDE hors canal e-mail) et le
        # lien `mailto:` (RFC 6068) ; `null` hors e-mail, sans adresse, ou
        # pour un rôle sans `client_pii_voir` (même masquage que `lead_email`).
        'objet': objet if est_email else '',
        'mailto_url': (_mailto_url(lead, objet, message, user)
                       if est_email else None),
    }


def _mailto_url(lead, objet, corps, user):
    """CIQ506 — ``mailto:<adresse>?subject=…&body=…`` (RFC 6068, espaces en
    ``%20``, sauts de ligne en CRLF), ou ``None`` : fiche sans adresse, ou
    rôle sans ``client_pii_voir`` (la file des relances ne doit pas rendre
    l'adresse que la fiche lui masque)."""
    from urllib.parse import quote

    from .serializers import pii_masquee_pour

    adresse = (getattr(lead, 'email', '') or '').strip()
    if not adresse or pii_masquee_pour(user):
        return None
    parametres = []
    if objet:
        parametres.append('subject=' + quote(objet, safe=''))
    if corps:
        crlf = corps.replace('\r\n', '\n').replace('\n', '\r\n')
        parametres.append('body=' + quote(crlf, safe=''))
    url = 'mailto:' + quote(adresse, safe='@+')
    return url + ('?' + '&'.join(parametres) if parametres else '')


#: CAD70 — le refus du POST `whatsapp/` quand la preuve manque (le champ est
#: nommé tel que l'écran le montre).
REFUS_PREUVE_MANQUANTE = (
    '« Preuve — installation comparable » : aucune réalisation publiée. '
    'Ajoutez-en une au catalogue (Paramètres → Réalisations) ou passez cette '
    'touche — ce message ne part pas sans preuve réelle.')


# ── CAD-F ── CAD71 (21/09/2026) ──────────────────────────────────────────
class GabaritNonAssignable(Exception):
    """Un gabarit de message exige un réglage société qui manque encore."""


#: Gabarits dont l'assignation exige un réglage société non vide, avec le
#: libellé humain du réglage manquant (repris dans le refus). `avis_google`
#: envoyait le lien du DEVIS du client à la place d'un lien vers la fiche
#: Google tant que ce garde-fou n'existait pas (`{lien}` n'était alimenté que
#: par `url_proposition`, jamais un lien Google) : on refuse maintenant
#: l'ASSIGNATION plutôt que de laisser la phrase partir vide ou fausse.
_GABARITS_REGLAGE_REQUIS = {
    'avis_google': ('lien_avis_google', 'lien de la fiche Google'),
}


def verifier_gabarit_assignable(company, template_cle):
    """CAD71 — lève ``GabaritNonAssignable`` si ``template_cle`` exige un
    réglage société (``CompanyProfile``) qui est vide ; ne fait rien pour un
    gabarit sans exigence (comportement historique inchangé). À appeler
    AVANT d'enregistrer l'assignation d'un gabarit à une touche (gabarit
    `parametres.CadenceRelanceEtape` ou touche `crm.RelanceEtape`) — crochet
    attendu côté écran : `apps/parametres/views_referentiels.py`
    (`CadenceRelanceEtapeViewSet`/son serializer) doit l'appeler avant
    `save()` pour que le refus atteigne réellement l'éditeur."""
    exige = _GABARITS_REGLAGE_REQUIS.get(template_cle)
    if exige is None:
        return
    champ, libelle = exige
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.objects.filter(company=company).first()
    valeur = ((getattr(profile, champ, '') if profile else '') or '').strip()
    if not valeur:
        raise GabaritNonAssignable(
            f'« {libelle} » n\'est pas renseigné dans les réglages de la '
            f'société : assignez d\'abord ce réglage avant de choisir ce '
            f'gabarit (Paramètres → Société).')


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


# FG28 — SLA première prise de contact ────────────────────────────────────────

def prefixe_activite_touche(etape):
    """RLC2 — le PRÉFIXE de la ligne de chatter d'une touche CLÔTURÉE.

    Écrit par ``marquer_etape_relance``, relu par l'annulation (RLC1) et par le
    journal du plan (``selectors.journal_relance``, qui apparie une touche avec
    l'ISSUE saisie à sa clôture). Même raison que
    ``prefixe_activite_message_ouvert`` : trois littéraux identiques auraient
    dérivé, et l'appariement se serait tu sans qu'aucune garde ne rougisse."""
    libelle = (etape.libelle or '').strip() or etape.get_canal_display()
    return f'Touche « {libelle} »'


#: SUIVI E22 — l'attribut TRANSITOIRE (jamais une colonne) par lequel la
#: ligne de chatter d'une touche close porte LA touche jusqu'aux récepteurs
#: de ``post_save`` (MRY9). Une seule source : écrit par
#: ``marquer_etape_relance``, relu par ``touche_close_de``.
_ATTRIBUT_TOUCHE_CLOSE = '_touche_close'


def touche_close_de(activite):
    """SUIVI E22 — la touche dont ``activite`` est la ligne de CLÔTURE, telle
    que ``marquer_etape_relance`` vient de l'écrire ; ``None`` pour toute
    autre ligne (journal d'appel de la fiche, note, ligne relue en base) —
    le récepteur retombe alors sur son comportement ordinaire."""
    return getattr(activite, _ATTRIBUT_TOUCHE_CLOSE, None)


def est_cloture_d_etape_visite(activite):
    """CAD2 — cette ligne de chatter est-elle la CLÔTURE d'une étape de visite
    (planifier, confirmer, débrief, devis modifié) ?

    Relue par le récepteur d'issue (MRY9), qui ne tient que l'activité : c'est
    le PRÉFIXE écrit par ``marquer_etape_relance`` (``prefixe_activite_touche``,
    source unique RLC2) qui dit de quelle touche elle vient — jamais un
    littéral recopié."""
    corps = getattr(activite, 'body', '') or ''
    if any(corps.startswith(
            prefixe_activite_touche(RelanceEtape(libelle=libelle)))
           for libelle in _LIBELLES_VISITE):
        return True
    # PARAM-CADENCE — une étape de visite RENOMMÉE par la société porte son
    # propre libellé : on relit les étapes de visite À CLÉ déjà traitées de
    # CE lead (quelques lignes, une requête) plutôt que de deviner.
    lead_id = getattr(activite, 'lead_id', None)
    if not corps.startswith('Touche « ') or lead_id is None:
        return False
    etapes = (RelanceEtape.objects
              .filter(lead_id=lead_id, cle__in=CLES_VISITE)
              .exclude(traite_le=None).only('libelle', 'canal'))
    return any(corps.startswith(prefixe_activite_touche(etape))
               for etape in etapes)


def prefixe_activite_message_ouvert(etape):
    """RLC3 — le PRÉFIXE de la ligne de chatter « message ouvert » de CETTE
    touche.

    UNE seule source : ``journaliser_whatsapp_ouvert`` juste dessous l'écrit,
    ``RelanceEtapeSerializer.get_message_ouvert_le`` le relit. Deux littéraux
    auraient dérivé au premier ajustement de la phrase, et le rappel « message
    ouvert ? » du panneau « Fait » se serait tu sans que rien ne rougisse."""
    libelle = (etape.libelle or '').strip() or etape.get_canal_display()
    return f'WhatsApp ouvert — touche « {libelle} »'


def journaliser_whatsapp_ouvert(etape, user):
    """RELANCE-WA (fondateur 08/09/2026) — ouvrir WhatsApp depuis une touche
    n'AVANCE plus la touche. Le clic est INSCRIT dans l'historique du lead
    (activité typée WhatsApp : comptée comme tentative MRY20 et comme premier
    contact MRY19 par les récepteurs) et la touche reste À FAIRE jusqu'à la
    réponse aux questions guidées (« Fait »). Avant, le clic marquait la
    touche faite (décision D5 du 07/09) : une conversation ouverte n'est pas
    une réponse du client. Aucune issue posée → aucune cadence arrêtée,
    aucune avance d'étape."""
    return LeadActivity.objects.create(
        company=etape.company, lead=etape.lead, user=user,
        kind=LeadActivity.Kind.WHATSAPP,
        body=(f'{prefixe_activite_message_ouvert(etape)} (cadence '
              f'{etape.cadence}) : message préparé ; la touche reste à faire '
              "jusqu'à la réponse du client."))


# ── CAD-B ── CAD106 ─────────────────────────────────────────────────────────

#: Le motif porté par une touche que la FUSION retire du plan. Statut
#: ANNULEE (CKP1 : annulation MOTEUR, jamais un saut humain) — sans quoi la
#: fusion compterait autant de manquements d'adhérence que de touches.
FUSION_TOUCHE_NOTE = 'annulée — fusion de fiches'


def relances_ouvertes_de(lead):
    """Les touches encore À FAIRE d'un lead (l'aperçu et la fusion comptent
    la même chose — jamais deux définitions)."""
    return lead.relance_etapes.filter(statut=RelanceEtape.Statut.A_FAIRE)


def reprendre_relances_apres_fusion(absorbed, survivor, user):
    """CAD106 — les relances SUIVENT le dossier quand deux fiches fusionnent.

    `merge_leads` déplaçait devis, chantiers, activités, pièces jointes et
    historique — et pas une seule relance. Les touches ouvertes restaient
    accrochées à une fiche ARCHIVÉE, donc invisibles dans la file (qui exclut
    les archivés), jamais passées en « annulée », et rien ne reposait de
    prochaine étape sur la survivante. Le cas est garanti d'arriver : le
    nouveau lead venait justement d'être privé de cadence par la garde
    « doublon ».

    Ce qu'on fait, et POURQUOI pas un simple déplacement : la survivante a
    souvent DÉJÀ une cadence active, et CADX interdit deux cadences en
    parallèle sur un lead. Les touches ouvertes de l'absorbée sont donc
    CLOSES en ANNULÉE avec le motif « fusion » — elles ne comptent alors
    comme un manquement nulle part (CKP1) — puis le FILET garantit à la
    survivante une prochaine étape, exactement comme à la reprise d'un lead
    dé-perdu (`unset_perdu`).

    Rend le nombre de touches retirées du plan de l'absorbée.
    """
    from django.utils import timezone

    ouvertes = list(relances_ouvertes_de(absorbed))
    if ouvertes:
        RelanceEtape.objects.filter(
            pk__in=[e.pk for e in ouvertes],
        ).update(statut=RelanceEtape.Statut.ANNULEE,
                 note=FUSION_TOUCHE_NOTE, traite_par=None,
                 traite_le=timezone.now())
        absorbed.relance_date = None
        absorbed.save(update_fields=['relance_date'])
    # QJ-INVARIANT — la survivante ne reste jamais sans prochaine étape.
    # Best-effort : une fusion n'échoue pas sur un filet.
    try:
        assurer_prochaine_etape_apres_succes(survivor, user)
    except Exception:  # noqa: BLE001
        logger.warning(
            'CAD106: filet non posé après fusion (lead #%s)',
            getattr(survivor, 'pk', '?'), exc_info=True)
    return len(ouvertes)


def _transferer_calepinages_apres_fusion(absorbed, survivor, user):
    """ACAL177 — fait suivre les calepinages de l'absorbé au survivant.

    Appel DIRECT du service ``apps.calepinage.services.liens.transferer_lead``
    (même patron que ``update_installation_lead`` : transactionnel, pas
    d'événement), import FONCTION-LOCAL (frontière inter-apps : jamais un
    modèle de calepinage). Sous-bloc ``atomic`` (savepoint) : un échec annule
    le seul transfert, la fusion continue, et le chatter du survivant le dit.
    """
    from django.db import transaction

    try:
        from apps.calepinage.services.liens import transferer_lead

        with transaction.atomic():
            transferer_lead(survivor.company, de_lead_id=absorbed.pk,
                            vers_lead_id=survivor.pk, user=user)
    except Exception:  # noqa: BLE001 — la fusion ne casse jamais ici
        logger.exception(
            'ACAL177 : calepinages du lead #%s non transférés vers #%s',
            absorbed.pk, survivor.pk)
        LeadActivity.objects.create(
            company=survivor.company, lead=survivor, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Fusion : les calepinages du lead #{absorbed.pk} n\'ont '
                  'pas pu être rattachés à cette fiche — rattachez-les depuis '
                  'le module Calepinage.'))


def raison_refus_suppression(lead):
    """ACAL177 — LA garde de corbeille d'un lead, écrite UNE fois.

    Sert les DEUX chemins de suppression (``LeadViewSet.destroy`` et
    l'opération en masse ``delete``). Rend ``None`` si le lead peut partir en
    corbeille, sinon un dict ``{detail, [calepinages]}`` (corps du 409) :

    * des devis liés : on n'orpheline jamais de pièces financières ;
    * un calepinage OUVERT (non archivé) : refus qui le NOMME. Un calepinage
      archivé ne bloque pas.
    """
    if lead.devis.exists():
        return {'detail': "Ce lead a des devis liés. Supprimer le lead "
                          "détacherait ces pièces — archivez-le plutôt."}
    from apps.calepinage.selectors import calepinages_ouverts_du_lead

    ouverts = calepinages_ouverts_du_lead(lead.company, lead.pk)
    if ouverts:
        premier = ouverts[0]
        titre = (getattr(premier, 'titre', '') or '').strip() or 'sans titre'
        return {
            'detail': (f'Ce lead porte le calepinage « {titre} » '
                       f'(#{premier.pk}) : archivez-le d\'abord ou ouvrez-le '
                       'depuis le module Calepinage'),
            'calepinages': [c.pk for c in ouverts],
        }
    return None


def _nom_fiche_client(client):
    """ACRM40 — « Nom Prénom (#id) » d'une fiche client, pour la note."""
    nom = f"{client.nom or ''} {client.prenom or ''}".strip() or 'Client'
    return f'{nom} (#{client.pk})'


def merge_leads(survivor, others, user):
    """Fusionne `others` dans `survivor` SANS perte de données. Déplace devis,
    activités, pièces jointes, historique et chantiers ; complète les champs
    vides du survivant ; archive les leads absorbés avec une note. Ne laisse
    JAMAIS un devis/chantier orphelin. Tout est transactionnel.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction
    from django.utils import timezone

    others = [o for o in others if o.pk != survivor.pk
              and o.company_id == survivor.company_id]
    if not others:
        return survivor

    ct = ContentType.objects.get_for_model(Lead)
    relances_reprises = 0
    # ACRM40 (C-ACRM-035) — les fiches client DISTINCTES rencontrées : le
    # survivant garde la sienne, les devis de l'autre restent sur l'autre.
    deux_clients = []
    with transaction.atomic():
        for absorbed in others:
            if (survivor.client_id and absorbed.client_id
                    and survivor.client_id != absorbed.client_id):
                deux_clients.append((
                    absorbed.client,
                    list(absorbed.devis.filter(client_id=absorbed.client_id)
                         .order_by('pk').values_list('reference', flat=True))))
            # 1) Devis → survivant (related_name='devis').
            absorbed.devis.update(lead=survivor)
            # 2) Chantiers liés au lead → survivant (FK SET_NULL, on réassigne).
            try:
                from apps.installations.selectors import (
                    update_installation_lead,
                )
                update_installation_lead(absorbed, survivor)
            except Exception:
                pass
            # 2 bis) ACAL177 — les CALEPINAGES suivent le dossier (D06-T04).
            # Savepoint : un transfert qui échoue ne casse jamais la fusion,
            # mais il est tracé (journal + note au chatter du survivant).
            _transferer_calepinages_apres_fusion(absorbed, survivor, user)
            # 3) Activités + pièces jointes génériques → survivant.
            try:
                from apps.records.models import Activity, Attachment
                Activity.objects.filter(
                    content_type=ct, object_id=absorbed.id).update(
                    object_id=survivor.id)
                Attachment.objects.filter(
                    content_type=ct, object_id=absorbed.id).update(
                    object_id=survivor.id)
            except Exception:
                pass
            # 4) Historique chatter → survivant.
            LeadActivity.objects.filter(lead=absorbed).update(lead=survivor)
            # 4 bis) CAD106 — les RELANCES suivent le dossier : les touches
            # ouvertes de l'absorbée sortent de son plan (annulées « fusion »,
            # donc jamais comptées comme des manquements) et le filet garantit
            # une prochaine étape à la survivante.
            relances_reprises += reprendre_relances_apres_fusion(
                absorbed, survivor, user)
            # 5) Client : adopter celui de l'absorbé si le survivant n'en a pas.
            if not survivor.client_id and absorbed.client_id:
                survivor.client = absorbed.client
            # 6) Compléter les champs VIDES du survivant — ACRM13 : vide au
            # sens de ``_est_vide`` (un 0 saisi du survivant SURVIT).
            for field in _MERGE_FILL_FIELDS:
                cur = getattr(survivor, field, None)
                if _est_vide(survivor, field, cur):
                    val = getattr(absorbed, field, None)
                    if not _est_vide(absorbed, field, val):
                        setattr(survivor, field, val)
            # 7) Fusionner les tags (union).
            tags = set()
            for src in (survivor, absorbed):
                for t in (src.tags or '').split(','):
                    t = t.strip()
                    if t:
                        tags.add(t)
            if tags:
                survivor.tags = ', '.join(sorted(tags))[:500]
            # 8) Archiver l'absorbé (jamais supprimé).
            absorbed.is_archived = True
            absorbed.archived_by = user
            absorbed.archived_at = timezone.now()
            absorbed.note = ((absorbed.note or '') +
                             f'\n[Fusionné dans le lead #{survivor.id} '
                             f'par {getattr(user, "username", "?")}]').strip()
            absorbed.save()
            LeadActivity.objects.create(
                company=survivor.company, lead=survivor, user=user,
                kind=LeadActivity.Kind.NOTE,
                body=(f"Fusion : lead « {absorbed.nom} {absorbed.prenom or ''} »"
                      f" (#{absorbed.id}) absorbé dans cette fiche."))
        # ACRM40 — DEUX fiches client pour une même personne : la fusion le
        # DIT (chatter du survivant + ``survivor._clients_distincts`` que la
        # vue rend) ; la fusion des clients reste un geste humain (outil de
        # fusion de clients, NTDATA18) — jamais automatique.
        survivor._clients_distincts = []
        if deux_clients:
            gardee = survivor.client
            survivor._clients_distincts = [gardee.pk] + [
                client.pk for client, _refs in deux_clients]
            for client, refs in deux_clients:
                devis_txt = (f"devis {', '.join(refs)} rattachés" if refs
                             else 'aucun devis rattaché')
                LeadActivity.objects.create(
                    company=survivor.company, lead=survivor, user=user,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'Deux fiches client pour ce lead : '
                          f'{_nom_fiche_client(gardee)} (gardée) et '
                          f'{_nom_fiche_client(client)} ({devis_txt}) — à '
                          'fusionner (outil de fusion des clients).'))
        survivor.save()
    if relances_reprises:
        # CAD106 — la fusion DIT ce qu'elle a fait des relances : sans cette
        # ligne, des touches disparaissaient du plan sans un mot.
        LeadActivity.objects.create(
            company=survivor.company, lead=survivor, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Fusion : {relances_reprises} relance(s) reprise(s) — '
                  'les touches des fiches absorbées sont retirées de leur '
                  'plan et le suivi continue sur cette fiche.'))
    # CRX33 — l'étape 6 complète les champs VIDES du survivant depuis les
    # absorbés (téléphone, e-mail, ville, facture, orientation…) : autant de
    # composantes du score. Sans ce recalcul, le survivant gardait le score
    # d'AVANT la fusion — une fiche enrichie restait « froide », et le badge
    # comme le tri mentaient jusqu'à la prochaine édition manuelle.
    recompute_lead_score(survivor)
    return survivor


def recompute_lead_score(lead) -> int:
    """Calcule et persiste le score de qualité du lead.

    QJ6 — le score est stocké sur Lead.score pour permettre un tri
    pagination-safe (?ordering=-score). Renvoie le score calculé.
    Best-effort : n'échoue jamais l'enregistrement du lead appelant.
    """
    try:
        from .scoring import compute_score
        score = compute_score(lead)
        lead.score = score
        lead.save(update_fields=['score'])
        maybe_assign_mql(lead)
        return score
    except Exception:
        return 0


#: CRX22 — un lead édité aujourd'hui a déjà son score à jour (le PATCH appelle
#: ``recompute_lead_score``) : le passage nocturne ne s'occupe QUE des autres.
DELAI_SCORE_OBSOLETE_JOURS = 1


def recalculer_scores_obsoletes(*, taille_lot=500) -> dict:
    """CRX22 — rafraîchit le score des leads que PERSONNE n'a touchés.

    ``Lead.score`` n'était (re)calculé qu'à la création et à l'édition. Or la
    composante de RÉCENCE décroît avec le temps (12 pts le premier jour, 1 pt
    au-delà de 90 jours) : un lead jamais rouvert gardait éternellement le
    score de son premier jour. Le tri « par score » remontait donc des leads
    vieux de six mois au-dessus de leads du jour, et le badge affichait une
    chaleur qui n'existait plus.

    Ce passage quotidien recalcule les leads dont ``date_modification`` a plus
    de :data:`DELAI_SCORE_OBSOLETE_JOURS` jour(s) et n'écrit QUE ceux dont la
    valeur bouge réellement. Il passe par ``recompute_lead_score`` — l'unique
    propriétaire de l'écriture du score — plutôt que par un ``update()`` en
    masse : une seule fonction décide de la valeur, ici comme à l'édition.

    ``save(update_fields=['score'])`` ne touche PAS ``date_modification``
    (``auto_now`` n'est rafraîchi que si le champ figure dans
    ``update_fields``) : le passage nocturne ne fait donc jamais passer un
    lead dormant pour un lead fraîchement édité.

    CAD141 (21/09/2026) — les leads ARCHIVÉS et PERDUS sont écartés : un
    dossier clos n'a plus besoin d'un score à jour, et un score recalculé
    pourrait le faire ressortir dans un tri (CAD83).

    Renvoie ``{'examines': int, 'mis_a_jour': int}``.
    """
    from datetime import timedelta

    from .scoring import compute_score

    seuil = timezone.now() - timedelta(days=DELAI_SCORE_OBSOLETE_JOURS)
    examines = 0
    mis_a_jour = 0
    # CAD141 (21/09/2026) — écarte archivés et perdus : un dossier CLOS n'a
    # plus besoin d'un score à jour (coût divisé) et ne doit jamais remonter
    # dans un tri par score après ce passage (CAD83).
    queryset = (
        Lead.objects
        .filter(date_modification__lt=seuil, is_archived=False, perdu=False)
        .order_by('pk').iterator(chunk_size=taille_lot))
    for lead in queryset:
        examines += 1
        if compute_score(lead) == lead.score:
            continue
        recompute_lead_score(lead)
        mis_a_jour += 1
    logger.info(
        'CRX22 recalculer_scores_obsoletes: %d lead(s) examiné(s), '
        '%d score(s) rafraîchi(s)', examines, mis_a_jour)
    return {'examines': examines, 'mis_a_jour': mis_a_jour}


# ── XMKT21 — Passage MQL automatique sur seuil de score ──────────────────────

def _seuil_mql_for(company) -> int:
    """Seuil de score MQL configuré pour la société. 0 = désactivé (défaut)."""
    if company is None:
        return 0
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        if profile is not None and profile.seuil_mql:
            return int(profile.seuil_mql)
    except Exception:
        pass
    return 0


def _next_round_robin_commercial(company):
    """Choisit le prochain commercial actif par round-robin.

    Round-robin simple et sans état dédié : parmi les commerciaux actifs de
    la société (rôle « Commercial »), on prend celui qui a le MOINS de leads
    MQL déjà assignés (``mql_assigned_at`` renseigné) — départage par id pour
    rester déterministe. Renvoie None si aucun commercial actif.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Count, Q

    User = get_user_model()
    candidats = list(
        User.objects.filter(
            company=company, is_active=True, role__nom='Commercial',
        ).annotate(
            nb_mql=Count(
                'leads_assignes',
                filter=Q(leads_assignes__mql_assigned_at__isnull=False)),
        ).order_by('nb_mql', 'id')
    )
    return candidats[0] if candidats else None


def maybe_assign_mql(lead) -> bool:
    """XMKT21 — Assigne+notifie automatiquement un lead franchissant le seuil MQL.

    Idempotent (``mql_assigned_at`` posé une seule fois) : seuil non configuré
    (0/NULL) → no-op, lead déjà passé MQL → no-op, score sous le seuil → no-op.
    Assigne le lead (round-robin parmi les commerciaux actifs de la société,
    ou via le territoire FG236 si un jour câblé — hors périmètre ici), notifie
    l'assigné et journalise le contexte marketing dans le chatter.
    Best-effort : n'échoue jamais l'appelant.
    """
    try:
        if lead is None or lead.mql_assigned_at is not None:
            return False
        seuil = _seuil_mql_for(getattr(lead, 'company', None))
        if not seuil:
            return False
        if (lead.score or 0) < seuil:
            # NTMKT18 — le module marketing (score de maturité additif) est
            # SORTI (SOLMVP10) : seul le score de qualité QJ6 déclenche
            # désormais le seuil, comportement pré-NTMKT18.
            return False

        assignee = None
        if not lead.owner_id:
            assignee = _next_round_robin_commercial(lead.company)
            if assignee is not None:
                lead.owner = assignee

        lead.mql_assigned_at = timezone.now()
        update_fields = ['mql_assigned_at']
        if assignee is not None:
            update_fields.append('owner')
        lead.save(update_fields=update_fields)

        contexte = []
        if getattr(lead, 'utm_source', None):
            contexte.append(f"source={lead.utm_source}")
        if getattr(lead, 'utm_campaign', None):
            contexte.append(f"campagne={lead.utm_campaign}")
        if getattr(lead, 'canal', None):
            contexte.append(f"canal={lead.get_canal_display()}")
        contexte_txt = ', '.join(contexte) if contexte else 'aucun'
        body = (f"auto — MQL : score {lead.score} ≥ seuil {seuil}"
                f"{' — assigné à ' + str(assignee) if assignee else ''}. "
                f"Contexte marketing : {contexte_txt}.")
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=body)

        # Si on vient d'assigner un owner (round-robin), le save() ci-dessus a
        # déjà déclenché apps.notifications.signals.lead_post_save
        # (LEAD_ASSIGNED sur transition d'owner) — ne pas notifier une
        # deuxième fois ici. On ne notifie explicitement que le cas où le
        # lead avait DÉJÀ un owner (pas de transition, donc pas de signal).
        if assignee is None:
            try:
                from apps.notifications.services import notify
                cible = getattr(lead, 'owner', None)
                if cible is not None:
                    nom = (getattr(lead, 'nom', '') or '').strip() or 'Nouveau prospect'
                    # Réutilise EventType.LEAD_ASSIGNED (pas de nouveau type
                    # dédié « lead_mql » — le corps du message précise le
                    # déclencheur MQL).
                    notify(
                        cible, 'lead_assigned',
                        f'Lead MQL : {nom}',
                        body=f'{nom} a franchi le seuil MQL (score {lead.score}).',
                        link=f'/crm/leads?lead={lead.pk}',
                        company=lead.company,
                    )
            except Exception:
                pass
        return True
    except Exception:
        return False


def ecrire_identite_client(client) -> bool:
    """ARC21 (founder-gated, OFF par défaut) — quand la bascule write-path est
    ACTIVE (``TIERS_SOURCE_ECRITURE`` ON), pousse l'identité du client vers son
    ``Tiers`` (source d'écriture unique), puis le client relira le miroir.

    Flag OFF (défaut) : NO-OP strict — renvoie ``False`` sans rien écrire (le
    client reste l'unique chemin d'écriture, comportement byte-identique à
    aujourd'hui). Best-effort ; ne fait jamais échouer l'appelant.

    Voir docs/decisions/ARC21-tiers-source-ecriture.md.
    """
    try:
        from apps.tiers import services as tiers_services
        if not tiers_services.identite_source_est_tiers():
            return False  # flag OFF — rien ne change.
        if client is None or client.tiers_id is None:
            return False
        return tiers_services.ecrire_identite(
            company=client.company, tiers=client.tiers,
            champs={
                'nom': client.nom or '',
                'prenom': client.prenom or '',
                'email': client.email or '',
                'telephone': client.telephone or '',
                'adresse': client.adresse or '',
                'ice': client.ice or '',
                'rc': client.rc or '',
                'identifiant_fiscal': client.if_fiscal or '',
                'cin': client.cin or '',
            })
    except Exception:
        return False


def attacher_tiers_au_lead(lead: Lead, client: Client) -> None:
    """ARC56 — Rattache le lead au MÊME ``tiers.Tiers`` que le Client résolu.

    Le pont crm.Client → Tiers (ARC18) a déjà créé/lié le Tiers du client à la
    sauvegarde ; ce hook ne fait que RECOPIER ce lien sur le lead pour que le
    recoupement « qui est ce tiers ? » (ARC20) couvre aussi le stade amont du
    funnel. Ne CRÉE jamais un 2ᵉ Tiers, n'écrit ni ne lit AUCUN champ de nom du
    lead (QW7), et n'écrit que si le lien change. Best-effort : ne fait jamais
    échouer la résolution du client.

    Hook APPELÉ APRÈS ``resolve_client_for_lead`` (jamais dans sa logique de
    résolution) — le Tiers vient toujours du client, jamais recalculé ici.
    """
    try:
        if lead is None or client is None:
            return
        tiers_id = getattr(client, 'tiers_id', None)
        if tiers_id is None:
            # Le client n'a pas encore de Tiers (miroir best-effort échoué à la
            # création) : on relit une fois après un refresh, sinon on abandonne
            # proprement (le prochain save du client re-tentera le miroir).
            client.refresh_from_db(fields=['tiers'])
            tiers_id = getattr(client, 'tiers_id', None)
        if tiers_id is None:
            return
        if lead.tiers_id != tiers_id:
            # Écriture CIBLÉE (update_fields=['tiers']) — aucun champ de nom
            # n'est touché, aucun autre effet de bord (QW7).
            Lead.objects.filter(pk=lead.pk).update(tiers_id=tiers_id)
            lead.tiers_id = tiers_id
    except Exception:
        pass


def dupliquer_client(client: Client, *, user) -> Client:
    """NTUX13 — Duplique une fiche ``Client`` en une fiche indépendante.

    ``nom`` reçoit le suffixe « (copie) » et les identifiants UNIQUES
    (``email``, ``ice``) sont VIDÉS — jamais recopiés tels quels — pour
    forcer une saisie explicite plutôt que de créer silencieusement un
    doublon sur une contrainte d'unicité (company, email) ou de propager un
    ICE qui identifie légalement une AUTRE entreprise. Les autres champs
    (téléphone, adresse, type, CIN/IF/RC) sont recopiés tels quels — ce sont
    des coordonnées, pas des identifiants d'unicité."""
    copie = Client.objects.create(
        company=client.company,
        nom=f'{client.nom} (copie)',
        prenom=client.prenom,
        email=None,
        telephone=client.telephone,
        adresse=client.adresse,
        type_client=client.type_client,
        cin=client.cin,
        ice=None,
        if_fiscal=client.if_fiscal,
        rc=client.rc,
        created_by=user,
    )
    return copie


@contextlib.contextmanager
def _verrou_client_par_telephone(company_id, cle_telephone):
    """CRX24 — sérialise la résolution de client du chemin SANS e-mail.

    Le chemin e-mail est arbitré par la base (contrainte unique
    ``crx24_client_email_unique_ci``, insensible à la casse) : deux créations
    concurrentes ⇒ ``IntegrityError`` rattrapée, puis relecture. Le repli
    TÉLÉPHONE (QX17) n'a AUCUNE contrainte équivalente — ``Client`` ne porte
    pas de colonne normalisée — donc deux devis générés en même temps pour le
    même prospect sans e-mail créaient DEUX fiches client, silencieusement.

    Verrou consultatif PostgreSQL porté par la transaction
    (``pg_advisory_xact_lock``) : il ne bloque aucune ligne, se libère tout
    seul à la fin de la transaction (même en cas d'erreur), et ne sérialise
    QUE les résolutions visant le même (société, téléphone normalisé). Sur un
    moteur sans verrou consultatif, ou sans clé téléphone exploitable, le
    contexte est un no-op : comportement strictement inchangé.
    """
    from django.db import connection, transaction

    if not cle_telephone or connection.vendor != 'postgresql':
        yield False
        return
    empreinte = _hashlib.blake2b(
        f'crm.resolve_client:{company_id}:{cle_telephone}'.encode('utf-8'),
        digest_size=8).digest()
    verrou = int.from_bytes(empreinte, 'big', signed=True)
    with transaction.atomic():
        with connection.cursor() as curseur:
            curseur.execute('SELECT pg_advisory_xact_lock(%s)', [verrou])
        yield True


def _email_identite(valeur):
    """ACRM38 (C-ACRM-033) — LA clé e-mail d'identité client : la même que
    la dédup (``normalize_email`` : bords retirés, minuscules), et ``None``
    pour un vide — jamais ``''`` ni ``' '`` (deux personnes sans e-mail ne
    partagent jamais un client, et ``''`` heurtait la contrainte d'unicité
    insensible à la casse)."""
    return normalize_email(valeur) or None


def _telephone_identite(valeur):
    """ACRM38 — le téléphone d'identité, normalisé sur la valeur RÉELLEMENT
    stockée côté Client (tronquée à 20 caractères) : deux résolutions du
    même lead comparent la même chose."""
    return normalize_phone((valeur or '')[:20])


def resolve_client_for_lead(lead: Lead) -> Client:
    if lead.client_id:
        # Rattache le Tiers du client déjà lié (stade amont ARC56), sans
        # jamais modifier la résolution existante ni un champ de nom.
        attacher_tiers_au_lead(lead, lead.client)
        return lead.client

    lead_ice = _ice_normalise(getattr(lead, 'ice', None))

    def _find_existing():
        # CIQ403 (contrat CIQ8, ``rattachement``) — l'ICE d'abord : jamais un
        # second client pour le même ICE dans la même société.
        if lead_ice:
            for candidate in Client.objects.filter(
                    company=lead.company, ice__isnull=False).exclude(ice=''):
                if _ice_normalise(candidate.ice) == lead_ice:
                    return candidate
        lead_email = _email_identite(lead.email)
        if lead_email:
            match = Client.objects.filter(
                company=lead.company, email__iexact=lead_email,
            ).first()
            if match is not None:
                _verifier_ice_compatible(match, lead_ice, "l'e-mail")
                return match
        # QX17 — repli téléphone : un client marocain récurrent n'a pas
        # toujours le MÊME email (ou aucun) d'un dossier à l'autre — le
        # téléphone est l'identité de facto. Comparaison Python-side (pas de
        # colonne normalisée indexée sur Client, à la différence de
        # Lead.phone_normalise) : borne de perf documentée — un scan de TOUS
        # les clients de la société, acceptable au volume actuel (PME
        # marocaines, quelques centaines à quelques milliers de clients par
        # société) ; à indexer (colonne normalisée + index, comme QW10 sur
        # Lead) si ce volume devient un goulot mesuré.
        lead_phone = _telephone_identite(lead.telephone)
        if not lead_phone:
            return None
        for candidate in Client.objects.filter(company=lead.company):
            if _telephone_identite(candidate.telephone) == lead_phone:
                _verifier_ice_compatible(candidate, lead_ice, 'le téléphone')
                return candidate
        return None

    # CRX24 — le chemin SANS e-mail (repli téléphone QX17) n'a aucune
    # contrainte d'unicité en base pour l'arbitrer : on le sérialise par
    # (société, téléphone normalisé) le temps du « chercher puis créer ». Le
    # chemin e-mail garde son arbitrage par la base (contrainte unique
    # insensible à la casse + relecture) et le verrou y est un no-op.
    cle_verrou = ('' if _email_identite(lead.email)
                  else _telephone_identite(lead.telephone))
    with _verrou_client_par_telephone(lead.company_id, cle_verrou):
        client = _resoudre_ou_creer_client(lead, _find_existing)

    lead.client = client
    lead.save(update_fields=['client'])
    # Trace la résolution/création du client dans le chatter du lead (geste
    # automatique côté serveur). L'utilisateur acteur n'est pas connu ici
    # (résolution déclenchée par le générateur de devis) → entrée système.
    nom_client = f"{client.nom} {client.prenom or ''}".strip()
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Client lié : {nom_client}")
    # ARC56 — rattache le lead au MÊME Tiers que le client fraîchement résolu
    # (le pont ARC18 a déjà posé client.tiers à sa sauvegarde). Aucun champ de
    # nom du lead n'est touché (QW7).
    attacher_tiers_au_lead(lead, client)
    return client


class ConflitIdentiteEntreprise(DRFValidationError):
    """CIQ403 (contrat CIQ8 ``exemple_conflit``) — l'e-mail ou le téléphone
    du lead désigne un client dont l'ICE DIFFÈRE de celui du lead : jamais
    une réutilisation silencieuse. Sous-classe de ``ValidationError`` DRF :
    tout appelant HTTP rend un 400 qui nomme ``ice`` sans être modifié."""

    default_code = 'conflit_identite_entreprise'

    def __init__(self, message):
        super().__init__({'code': 'conflit_identite_entreprise',
                          'champ': 'ice', 'message': message})


def _ice_normalise(valeur):
    """ICE comparable : espaces retirés ; vide = ``''``."""
    return _re.sub(r'\s', '', str(valeur or '')).upper()


def _verifier_ice_compatible(client, lead_ice, par):
    client_ice = _ice_normalise(client.ice)
    if lead_ice and client_ice and client_ice != lead_ice:
        raise ConflitIdentiteEntreprise(
            f'Le client trouvé par {par} (« {client.nom} ») porte l\'ICE '
            f'{client.ice}, différent de celui du lead ({lead_ice}) : '
            "vérifier l'ICE avant de créer ou de rattacher le client.")


def lead_est_entreprise(lead):
    """CIQ403 (contrat CIQ8, ``creation_depuis_lead.quand_entreprise``) —
    le client d'un lead commercial/industriel, ou qui porte une raison
    sociale, est une ENTREPRISE ; sinon un particulier (inchangé)."""
    return (getattr(lead, 'type_installation', None)
            in ('commercial', 'industriel')
            or bool((getattr(lead, 'societe', None) or '').strip()))


def _nom_personne(lead):
    return ' '.join(
        p.strip() for p in (getattr(lead, 'prenom', None),
                            getattr(lead, 'nom', None))
        if p and p.strip())


def _resoudre_ou_creer_client(lead, _find_existing):
    """Cœur « chercher, sinon créer » de :func:`resolve_client_for_lead`,
    extrait pour tenir sous le verrou CRX24 sans dupliquer une ligne de sa
    logique. Aucun changement de comportement."""
    from django.db import IntegrityError, transaction

    client = _find_existing()

    if client is None:
        # Séparateur VISIBLE entre rue et ville : un \n disparaît dans les
        # champs <input> et collait l'adresse à la ville (« …AuditCasablanca »).
        adresse = lead.adresse or ''
        if lead.ville:
            adresse = ', '.join(p for p in (adresse, lead.ville) if p)
        # QX18 — l'arabophone ne doit pas disparaître à la couche document :
        # un lead qui préfère la darija (message WhatsApp) obtenait quand
        # même un PDF FLAGSHIP en français par défaut. Seed
        # `langue_document='ar'` UNIQUEMENT à la création (jamais écrasé sur
        # un client déjà existant réutilisé ci-dessus — sa préférence
        # documentaire, si posée manuellement, prime toujours).
        langue_document = (
            Client.LangueDocument.AR
            if lead.langue_preferee == Lead.LanguePreferee.DARIJA
            else Client.LangueDocument.FR
        )
        try:
            # Savepoint : si une création concurrente partageant le même email
            # a gagné la course, l'unique_together (company, email) lève une
            # IntegrityError — on la rattrape et on réutilise le client existant
            # (style get_or_create), au lieu de propager un 500.
            champs = dict(
                company=lead.company,
                nom=lead.nom,
                prenom=lead.prenom,
                # ACRM38 — e-mail normalisé, jamais '' (NULL quand vide).
                email=_email_identite(lead.email),
                telephone=(lead.telephone or '')[:20] or None,
                adresse=adresse or None,
                langue_document=langue_document,
            )
            if lead_est_entreprise(lead):
                # CIQ403 — client ENTREPRISE (contrat CIQ8) : la raison
                # sociale nomme le client, la personne devient « à
                # l'attention de ». Sans raison sociale : le nom de la
                # personne, marqué à confirmer (jamais bloquant). Les
                # identifiants sont recopiés tels que DÉCLARÉS.
                raison = (lead.societe or '').strip()
                personne = _nom_personne(lead)
                champs.update(
                    type_client=Client.TypeClient.ENTREPRISE,
                    nom=raison or personne or lead.nom,
                    prenom=None,
                    raison_sociale_a_confirmer=not raison,
                    contact_nom=personne or None,
                    contact_fonction=lead.fonction_contact or None,
                    ice=(lead.ice or '').strip() or None,
                    rc=lead.rc or None,
                    if_fiscal=lead.if_fiscal or None,
                    adresse_siege=lead.adresse_siege or None,
                    tva_recuperable=lead.tva_recuperable or None,
                )
            with transaction.atomic():
                client = Client.objects.create(**champs)
        except IntegrityError:
            # CRX24 — attrape AUSSI la contrainte insensible à la casse
            # ``crx24_client_email_unique_ci`` : ``_find_existing`` cherche en
            # ``email__iexact``, donc la relecture retrouve bien le gagnant de
            # la course, quelle que soit la casse qu'il a écrite.
            client = _find_existing()
            if client is None:
                raise

    return client


def completer_client_depuis_acceptation(client_id, company, *,
                                        raison_sociale='', ice=''):
    """CIQ319 (complément, contrat CIQ8) — l'identité d'entreprise déclarée à
    l'acceptation en ligne d'un devis C&I remonte au Client, SANS JAMAIS
    écraser ce qu'il porte déjà.

    * ICE : écrit seulement si le Client n'en a aucun. Un ICE DIFFÉRENT déjà
      présent reste intact (le cas est signalé par
      ``ventes.domain.cycle_vie.divergence_ice``) ;
    * raison sociale : remplace le nom seulement quand il est marqué « à
      confirmer » (le nom de la personne posé faute de raison sociale,
      CIQ403) ; le marqueur est alors levé ;
    * un client qui reçoit une identité légale devient « Entreprise ».

    Borné à la société. Rend la liste des champs écrits (``[]`` = rien)."""
    raison = str(raison_sociale or '').strip()[:255]
    ice_net = str(ice or '').strip()[:30]
    if not client_id or not (raison or ice_net):
        return []
    client = Client.objects.filter(pk=client_id, company=company).first()
    if client is None:
        return []
    ecrits = []
    if ice_net and not _ice_normalise(client.ice):
        client.ice = ice_net
        ecrits.append('ice')
    if raison and client.raison_sociale_a_confirmer:
        client.nom = raison
        client.raison_sociale_a_confirmer = False
        ecrits += ['nom', 'raison_sociale_a_confirmer']
    if ecrits and client.type_client != Client.TypeClient.ENTREPRISE:
        client.type_client = Client.TypeClient.ENTREPRISE
        ecrits.append('type_client')
    if ecrits:
        client.save(update_fields=[*ecrits, 'date_modification'])
    return ecrits


# ── QJR590 : l'identité client SUIT le lead tant qu'elle n'a pas divergé ─────
#: Champs d'identité recopiés du lead vers sa fiche Client (contrat
#: ``lead_client_ecart.json``) — ordre stable, celui de l'écart servi.
IDENTITE_CLIENT_CHAMPS = ('nom', 'prenom', 'email', 'telephone', 'adresse')
#: CIQ403 (contrat ``lead_client_ecart.json`` → ``exemple_entreprise``) — un
#: client ENTREPRISE suit en plus son identité légale ; ``prenom`` n'a pas de
#: sens pour lui (la personne est ``contact_nom``).
IDENTITE_CLIENT_CHAMPS_ENTREPRISE = (
    'nom', 'email', 'telephone', 'adresse', 'contact_nom',
    'contact_fonction', 'ice', 'rc', 'if_fiscal', 'adresse_siege',
    'tva_recuperable',
)


def _champs_identite(client):
    if getattr(client, 'type_client', None) == Client.TypeClient.ENTREPRISE:
        return IDENTITE_CLIENT_CHAMPS_ENTREPRISE
    return IDENTITE_CLIENT_CHAMPS


def identite_client_depuis_lead(lead, *, entreprise=False):
    """Identité Client telle que :func:`_resoudre_ou_creer_client` la
    recopie d'un lead (adresse = adresse + ', ' + ville ; téléphone ≤ 20).

    CIQ403 — ``entreprise=True`` : nom ← societe (sinon la personne),
    contact_nom ← prénom + nom, et l'identité légale déclarée."""
    adresse = getattr(lead, 'adresse', None) or ''
    ville = getattr(lead, 'ville', None)
    if ville:
        adresse = ', '.join(p for p in (adresse, ville) if p)
    identite = {
        'nom': getattr(lead, 'nom', None),
        'prenom': getattr(lead, 'prenom', None),
        # ACRM38 — la même clé e-mail que la création du client.
        'email': _email_identite(getattr(lead, 'email', None)),
        'telephone': (getattr(lead, 'telephone', None) or '')[:20] or None,
        'adresse': adresse or None,
    }
    if entreprise:
        personne = _nom_personne(lead) or None
        identite.update(
            nom=(getattr(lead, 'societe', None) or '').strip() or personne,
            prenom=None,
            contact_nom=personne,
            contact_fonction=getattr(lead, 'fonction_contact', None),
            ice=(getattr(lead, 'ice', None) or '').strip() or None,
            rc=getattr(lead, 'rc', None),
            if_fiscal=getattr(lead, 'if_fiscal', None),
            adresse_siege=getattr(lead, 'adresse_siege', None),
            tva_recuperable=getattr(lead, 'tva_recuperable', None),
        )
    return identite


def _identite_egale(champ, a, b):
    """Égalité « métier » : casse ignorée pour l'e-mail, numéro normalisé
    pour le téléphone, espaces de bord ignorés partout ; vide == None."""
    a = (a or '').strip()
    b = (b or '').strip()
    if champ == 'email':
        return a.casefold() == b.casefold()
    if champ == 'telephone':
        return (normalize_phone(a) or a) == (normalize_phone(b) or b)
    return a == b


def _client_synchronisable(lead):
    client = getattr(lead, 'client', None) if lead.client_id else None
    if client is None or getattr(client, 'is_anonymized', False):
        return None
    if client.company_id != lead.company_id:
        return None
    return client


def client_ecart(lead):
    """QJR590 — champs d'identité où la fiche Client liée diffère du lead
    (liste ordonnée, ``[]`` sans client ou client anonymisé). Lecture seule."""
    client = _client_synchronisable(lead)
    if client is None:
        return []
    champs = _champs_identite(client)
    cible = identite_client_depuis_lead(
        lead, entreprise=champs is IDENTITE_CLIENT_CHAMPS_ENTREPRISE)
    return [c for c in champs
            if not _identite_egale(c, getattr(client, c, None), cible[c])]


def synchroniser_identite_client(lead, avant, user, *, force=False):
    """QJR590 — propage une correction d'identité du lead à SA fiche Client.

    Un champ n'est recopié que si la valeur actuelle du Client ÉGALE celle
    qu'avait le lead AVANT (``avant`` = instantané pris avant l'écriture) :
    un Client modifié à la main, divergé, n'est jamais écrasé. ``force=True``
    (action « Mettre à jour la fiche client ») recopie tout l'écart. Jamais un
    Client anonymisé, jamais un Client d'une autre société, jamais un Client
    désigné par le corps de requête (``lead.client`` seulement).

    E-mail déjà pris par un autre client (contrainte
    ``crx24_client_email_unique_ci``) : les autres champs passent, l'e-mail
    non, et un message le dit (chatter + valeur rendue). Chaque devis ENVOYÉ
    du client reçoit la trace « corrigé après envoi » (objet « identité
    client », QJR518) ; un accepté garde son exemplaire signé figé.

    Rend ``(champs_mis_a_jour, message|None)``.
    """
    from django.db import IntegrityError, transaction

    client = _client_synchronisable(lead)
    if client is None:
        return [], None
    champs_suivis = _champs_identite(client)
    entreprise = champs_suivis is IDENTITE_CLIENT_CHAMPS_ENTREPRISE
    cible = identite_client_depuis_lead(lead, entreprise=entreprise)
    ancienne = (identite_client_depuis_lead(avant, entreprise=entreprise)
                if avant is not None else {})
    champs = []
    for c in champs_suivis:
        actuelle = getattr(client, c, None)
        if _identite_egale(c, actuelle, cible[c]):
            continue
        if force or _identite_egale(c, actuelle, ancienne.get(c)):
            champs.append(c)
    if not champs:
        return [], None
    if 'nom' in champs and not (cible['nom'] or '').strip():
        champs.remove('nom')  # Client.nom est requis : jamais vidé
    message = None
    anciennes = {c: getattr(client, c, None) for c in champs}
    for c in champs:
        setattr(client, c, cible[c])
    try:
        with transaction.atomic():
            client.save(update_fields=champs)
    except IntegrityError:
        setattr(client, 'email', anciennes.get('email'))
        champs = [c for c in champs if c != 'email']
        message = ("La fiche client n'a pas repris l'e-mail : il est déjà "
                   'utilisé par un autre client.')
        if champs:
            with transaction.atomic():
                client.save(update_fields=champs)
    acteur = getattr(user, 'username', None) or 'système'
    if champs:
        libelles = ', '.join(champs)
        corps = (f'Fiche client {client.nom} mise à jour depuis le lead '
                 f'({libelles}) par {acteur}.')
        for lead_client in client.leads.all():
            LeadActivity.objects.create(
                company=lead_client.company, lead=lead_client, user=user,
                kind=LeadActivity.Kind.NOTE, body=corps)
        from apps.ventes.selectors import devis_envoyes_du_client
        from apps.ventes.services import consigner_correction_apres_envoi
        for devis in devis_envoyes_du_client(client.company_id, client.pk):
            consigner_correction_apres_envoi(
                devis, user=user, objet='identité client',
                resume=f'identité client ({libelles})')
    if message:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE, body=message)
    return champs, message


class ClientIntrouvable(ValueError):
    """ACRM7 — le client à lier est absent OU hors de la portée de
    l'appelant : les deux cas reçoivent la MÊME réponse (jamais un oracle
    d'existence)."""

    MESSAGE = 'Client introuvable.'

    def __init__(self):
        super().__init__(self.MESSAGE)


def convertir_lead_en_client(*, lead, user, mode, client_id=None,
                             clients=None):
    """ZSAL4 — assistant de conversion EXPLICITE lead → client (Odoo « Convert
    to Opportunity » : nouveau contact / lier un contact existant / ne pas
    lier), à la main du commercial.

    ``mode``:
      - ``'nouveau'`` : crée un client depuis les champs du lead. Réutilise
        STRICTEMENT :func:`resolve_client_for_lead` (jamais un 2ᵉ chemin de
        création) — si le lead est déjà lié, ce mode ne duplique jamais.
      - ``'lier'`` : rattache un ``crm.Client`` EXISTANT, borné à la même
        société que le lead (``client_id`` obligatoire ; ValueError sinon,
        ou si le client n'existe pas / est d'une autre société).
      - ``'aucun'`` : marque le lead qualifié sans client (ne crée rien).

    ACRM7 — ``clients`` (queryset) borne le mode ``'lier'`` à la PORTÉE de
    l'appelant (la vue passe ``scope_client_queryset``) : un client hors
    portée lève :class:`ClientIntrouvable`, exactement comme un id
    inexistant. ``None`` = toute la société (chemins système).

    Toute conversion est journalisée dans le chatter du lead (choix +
    acteur). Retourne le :class:`Client` résolu (ou None pour ``'aucun'``).
    """
    if mode not in ('nouveau', 'lier', 'aucun'):
        raise ValueError("Mode de conversion invalide (nouveau|lier|aucun).")

    if mode == 'aucun':
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE,
            body="Conversion : lead qualifié SANS client rattaché "
                 f"(choix de {getattr(user, 'username', '?')}).")
        return None

    if mode == 'lier':
        if not client_id:
            raise ValueError("client_id requis pour le mode « lier ».")
        base = Client.objects if clients is None else clients
        try:
            client = base.filter(
                id=int(client_id), company=lead.company).first()
        except (TypeError, ValueError):
            client = None
        if client is None:
            raise ClientIntrouvable()
        lead.client = client
        lead.save(update_fields=['client'])
        nom_client = f"{client.nom} {client.prenom or ''}".strip()
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=f"Conversion : client existant lié — {nom_client} "
                 f"(choix de {getattr(user, 'username', '?')}).")
        return client

    # mode == 'nouveau' : jamais un 2ᵉ chemin de création — délègue
    # entièrement à resolve_client_for_lead (réutilise le lien existant, sinon
    # crée). Le chatter de resolve_client_for_lead trace déjà la résolution ;
    # on ajoute une entrée dédiée précisant que c'est une conversion EXPLICITE.
    client = resolve_client_for_lead(lead)
    nom_client = f"{client.nom} {client.prenom or ''}".strip()
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=f"Conversion : nouveau client — {nom_client} "
             f"(choix de {getattr(user, 'username', '?')}).")
    return client


def appliquer_plan_activite(*, lead, plan, user):
    """ZSAL2 — applique un :class:`~apps.crm.models.PlanActivite` à un lead.

    Crée une ``records.Activity`` par étape du plan, échéance = aujourd'hui +
    ``etape.delai_jours``, assignée à ``etape.assigne_par_defaut`` si posé
    sinon au owner du lead sinon à l'acteur. IDEMPOTENT par (lead, plan) : les
    activités déjà créées par une précédente application de CE plan sur CE
    lead sont retrouvées via ``summary`` + une marque dédiée dans ``note``
    (``[plan:<id>:<etape_id>]``) — une seconde application ne duplique rien et
    renvoie la liste déjà existante. Un plan archivé (``actif=False``) n'est
    jamais applicable (ValueError, traduit en 400 par la vue).

    Retourne la liste des ``records.Activity`` (créées ou déjà existantes,
    dans l'ordre des étapes).
    """
    if not plan.actif:
        raise ValueError("Ce plan d'activité est archivé et n'est plus applicable.")
    if plan.company_id != lead.company_id:
        raise ValueError("Plan hors de votre société.")

    from django.contrib.contenttypes.models import ContentType
    from apps.records.models import Activity

    ct = ContentType.objects.get_for_model(Lead)
    today = aujourd_hui_local()
    resultats = []
    for etape in plan.etapes.select_related(
            'activity_type', 'assigne_par_defaut').order_by('ordre', 'delai_jours'):
        marque = f'[plan:{plan.id}:{etape.id}]'
        existante = Activity.objects.filter(
            company=lead.company, content_type=ct, object_id=lead.id,
            note__contains=marque,
        ).first()
        if existante is not None:
            resultats.append(existante)
            continue
        assigne = etape.assigne_par_defaut or lead.owner or user
        from datetime import timedelta
        due = today + timedelta(days=etape.delai_jours)
        act = Activity.objects.create(
            company=lead.company, content_type=ct, object_id=lead.id,
            activity_type=etape.activity_type,
            summary=(etape.resume_defaut or etape.activity_type.nom)[:255],
            due_date=due,
            assigned_to=assigne,
            note=marque,
            created_by=user,
        )
        resultats.append(act)

    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=f"Plan d'activité « {plan.nom} » appliqué "
             f"({len(plan.etapes.all())} étape(s)).")
    return resultats


def create_draft_lead_from_ocr(*, company, user, fields) -> Lead:
    """FG106 — crée un LEAD brouillon à partir de champs extraits par l'OCR.

    Point d'entrée cross-app sanctionné (services.py) pour la passerelle
    OCR → CRM (apps.publicapi). La société vient TOUJOURS du serveur (jamais du
    corps), l'attribution du propriétaire suit la même règle que la création
    normale d'un lead, et la création est tracée dans le chatter. ``fields`` est
    le dict de données structurées OCR ; seuls des champs sûrs y sont lus —
    aucune confiance n'est accordée à des clés inattendues.

    Le lead reste à l'étape par défaut (NEW) : ce service CRÉE, il ne fait pas
    avancer le funnel.
    """
    fields = fields or {}
    nom = (fields.get('fournisseur') or fields.get('client') or '').strip()
    if not nom:
        raise ValueError("Aucun nom de fournisseur/client exploitable dans le document.")

    extra = {}
    # Même règle d'attribution que LeadViewSet.perform_create : un compte à
    # portée restreinte garde la propriété de ce qu'il crée.
    if user is not None and getattr(user, 'record_scope', None) and \
            user.record_scope() != 'all':
        extra['owner'] = user
    else:
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default

    lead = Lead.objects.create(
        company=company,
        nom=nom[:255],
        source=Lead.Source.OS_NATIVE,
        canal=Lead.Canal.AUTRE,
        **extra,
    )
    activity.log_creation(lead, user)
    # Note SYSTÈME (user=None) : annotation automatique, pas un contact manuel —
    # sinon le récepteur QJ7 ferait avancer le lead NEW → CONTACTED alors que ce
    # service CRÉE seulement et laisse le funnel à l'étape par défaut (NEW).
    activity.log_note(
        lead, None,
        "Lead créé depuis un document OCR (brouillon à compléter).")
    # CAD90 — données lues sur un document, jamais collectées auprès de la
    # personne par nous : c'est l'art. 5 §3 qui s'applique, et le registre
    # doit le dire au lieu de rester muet.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_DOCUMENT,
        base_legale=BASE_LEGALE_NON_COLLECTEE)
    recompute_lead_score(lead)
    return lead


# ── XSAL8 — Scan de carte de visite (salon/chantier) → pré-remplissage ──────
#
# NE crée JAMAIS de lead : lit une photo, l'envoie à l'OCR EXISTANT
# (``core.ai.services.extract_document``, gabarit ``carte_visite`` — la même
# capacité que FG355/XRH23, key-gated ZHIPU_API_KEY, NO-OP-safe), et renvoie
# les champs reconnus pour PRÉ-REMPLIR le modal « Lead express » — la création
# reste TOUJOURS un geste explicite de l'utilisateur (bouton « Créer »).

# Mêmes octets magiques que ``apps.records.storage`` (jamais de nouvelle
# dépendance) : la carte de visite est une simple PHOTO (JPEG/PNG/WebP),
# jamais un PDF.
_CARTE_VISITE_MAX_BYTES = 8 * 1024 * 1024  # 8 Mo (photo mobile courante)
_CARTE_VISITE_MAGIC = {
    'image/png': lambda h: h[:8] == b'\x89PNG\r\n\x1a\n',
    'image/jpeg': lambda h: h[:3] == b'\xff\xd8\xff',
    'image/webp': lambda h: h[:4] == b'RIFF' and h[8:12] == b'WEBP',
}


class CarteVisiteScanUnavailable(Exception):
    """XSAL8 — levée quand l'OCR n'est pas configuré (503 douce côté vue) ou
    quand le fichier fourni n'est pas une image reconnue (400 côté vue)."""


def scan_carte_visite(*, company, file_bytes, mime_hint='', queryset=None):
    """XSAL8 — Extrait nom/société/téléphone/email d'une photo de carte de
    visite, PRÉ-VÉRIFIE les doublons, et renvoie un dict prêt à pré-remplir le
    modal « Lead express » — NE CRÉE JAMAIS de lead (l'utilisateur valide).

    Lève :class:`CarteVisiteScanUnavailable` si le fichier n'est pas une image
    reconnue (magic bytes) OU trop volumineux OU si aucun fournisseur OCR
    n'est configuré (``ZHIPU_API_KEY`` absent — dégradation propre, jamais
    d'appel réseau). Ne persiste JAMAIS l'image reçue au-delà du traitement en
    mémoire (aucun stockage MinIO — contrairement aux autres flux OCR qui
    rattachent le fichier en pièce jointe).

    ACRM7 (jumeau) — ``queryset`` borne la pré-vérification des doublons aux
    leads de la PORTÉE de l'appelant (``None`` = toute la société)."""
    if not file_bytes:
        raise CarteVisiteScanUnavailable('Aucune image fournie.')
    if len(file_bytes) > _CARTE_VISITE_MAX_BYTES:
        raise CarteVisiteScanUnavailable('Image trop volumineuse (max 8 Mo).')

    header = file_bytes[:12]
    mime = None
    for candidate_mime, test in _CARTE_VISITE_MAGIC.items():
        if test(header):
            mime = candidate_mime
            break
    if mime is None:
        raise CarteVisiteScanUnavailable(
            'Format non reconnu (JPEG, PNG ou WebP uniquement).')

    from core.ai.services import extract_document
    result = extract_document(
        content=file_bytes, mime_type=mime, schema='carte_visite')
    if not result.configured:
        raise CarteVisiteScanUnavailable(
            "Aucun fournisseur OCR n'est configuré (clé absente) — "
            'saisie manuelle requise.')

    data = result.data or {}
    nom = str(data.get('nom') or '').strip()[:255]
    prenom = str(data.get('prenom') or '').strip()[:255]
    societe = str(data.get('societe') or '').strip()[:255]
    telephone = str(data.get('telephone') or '').strip()[:50]
    email = str(data.get('email') or '').strip()[:254]

    doublons = []
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None,
            queryset=queryset)
        doublons = [
            {'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
             'telephone': d.telephone, 'email': d.email}
            for d in dupes
        ]

    return {
        'nom': nom, 'prenom': prenom, 'societe': societe,
        'telephone': telephone, 'email': email,
        'doublons': doublons,
    }


# ── YLEAD8 — Rattacher l'inbound WhatsApp à un lead OUVERT existant ──────────

def resolve_or_create_lead_from_whatsapp(company, telephone, nom='',
                                         user=None) -> Lead:
    """YLEAD8 — Réutilise un lead OUVERT existant (même téléphone) au lieu de
    toujours créer un doublon sur un message WhatsApp entrant.

    « Ouvert » = non perdu (``Lead.perdu`` False) et non archivé
    (``archived_at`` NULL). Parmi les leads ouverts partageant ce téléphone,
    prend le plus récent ; journalise le message inbound dans SON chatter.

    YLEAD11 — si aucun lead OUVERT n'existe mais qu'un lead PERDU/COLD (non
    archivé) partage ce téléphone, il est RÉACTIVÉ (même règle que le
    webhook site : lève ``perdu``, repositionne NEW/CONTACTED avance-seul)
    plutôt que de créer un doublon — une nouvelle touche WhatsApp rouvre
    aussi le cycle d'achat.

    N'appelle ``create_draft_lead_from_ocr`` qu'en DERNIER RECOURS (aucun
    lead — ouvert ou réactivable — trouvé pour ce numéro) — c'est ce service
    qui doit être appelé par ``compta.services.capturer_message_whatsapp``,
    jamais l'inverse. Company-scopé ; gated en amont par l'appelant (NO-OP si
    WhatsApp OFF).
    """
    candidates = find_duplicates_by_contact(company, phone=telephone)
    non_archives = [c for c in candidates if c.archived_at is None]
    # ALEA2 — un lead au Froid (non perdu) n'est PAS « ouvert » : il est
    # réactivable, comme le perdu (alignement sur le webhook du site).
    ouverts = [lead_ for lead_ in non_archives
               if not lead_.perdu and lead_.stage != stages.COLD]
    if ouverts:
        lead = sorted(ouverts, key=lambda d: d.date_creation, reverse=True)[0]
        body = 'Nouveau message WhatsApp reçu'
        if nom:
            body += f' de {nom}'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE, body=body)
        return lead

    # YLEAD11 — aucun lead ouvert : un lead perdu/COLD non archivé est
    # réactivé plutôt que dupliqué.
    reactivables = [lead_ for lead_ in non_archives
                    if lead_.perdu or lead_.stage == stages.COLD]
    if reactivables:
        lead = sorted(
            reactivables, key=lambda d: d.date_creation, reverse=True)[0]
        reactivate_lead_on_new_touch(lead, source='WhatsApp')
        return lead

    lead = create_draft_lead_from_ocr(
        company=company, user=user,
        fields={'client': nom or telephone})
    # create_draft_lead_from_ocr ne lit que fournisseur/client (nom) — le
    # téléphone/whatsapp est posé ICI pour que le PROCHAIN message du même
    # numéro retrouve ce lead via find_duplicates_by_contact (sinon YLEAD8
    # créerait un doublon à chaque message, ce que ce service existe pour
    # éviter). BUG RÉEL corrigé ici : Lead.save() recalcule
    # phone_normalise/email_normalise EN MÉMOIRE à chaque save() (avant
    # super().save()), mais save(update_fields=[...]) ne PERSISTE que les
    # colonnes listées — sans 'phone_normalise' ici, la colonne restait ''
    # en base malgré le téléphone posé, et find_duplicates_by_contact (qui
    # filtre sur phone_normalise) ne retrouvait jamais ce lead au message
    # suivant : chaque nouveau message du même numéro créait un DOUBLON.
    if telephone:
        lead.telephone = telephone
        lead.whatsapp = telephone
        lead.save(update_fields=['telephone', 'whatsapp', 'phone_normalise',
                                 'whatsapp_normalise'])
    return lead


# ── XMKT32 — Sync Meta Lead Ads → leads CRM (gated) ───────────────────────────

_META_LEAD_ADS_SYSTEM = 'meta_lead_ads'

# Marqueur d'idempotence de la note « réponses du formulaire » (une seule note
# par lead, quel que soit le nombre de retries webhook / passes du pull).
_META_FORM_NOTE_MARKER = '[Formulaire Meta]'


def _norm_form_text(value):
    """Minuscule, sans accents, underscores → espaces — les clés/valeurs des
    Instant Forms Meta arrivent en snake_case accentué (ex.
    ``quelle_est_votre_facture_moyenne_d'électricité_par_mois_?`` /
    ``entre_1000_dh_à_2000_dh``) ; ce normalisateur rend le matching tolérant
    aux variantes de wording entre formulaires."""
    import unicodedata

    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.replace('_', ' ').lower().strip()


# ── CAD-K ── CAD134 — le délai déclaré côté Meta, dans le champ DÉJÀ scoré ──
#
# Mots-clés → ``Lead.ProjectTimeline``, sur du texte libre normalisé par
# ``_norm_form_text``. TOLÉRANT (les libellés varient d'un Instant Form à
# l'autre) et SANS invention : un libellé non reconnu ne pose RIEN — mieux
# vaut un champ vide qu'un délai deviné, qui vaudrait des points au score.
# L'ORDRE compte : « le plus tôt possible » gagne avant « 3 mois ».
_META_TIMELINE_MOTS = (
    (('plus tot possible', 'ce mois', 'immediat', 'des que possible',
      'urgent'), Lead.ProjectTimeline.IMMEDIAT),
    (('renseigne', 'plus tard', 'pas presse', 'aucune idee', 'compare'),
     Lead.ProjectTimeline.PLUS_TARD),
    (('3 mois', 'trois mois'), Lead.ProjectTimeline.MOINS_3_MOIS),
    (('6 mois', 'six mois'), Lead.ProjectTimeline.MOINS_6_MOIS),
)


def _meta_project_timeline(valeur_normalisee):
    """CAD134 — le délai déclaré côté Meta en clé ``ProjectTimeline``, ou ''.

    ``valeur_normalisee`` est déjà passée par ``_norm_form_text``. Renvoie
    une chaîne VIDE quand rien n'est reconnu : on ne devine pas un délai."""
    texte = str(valeur_normalisee or '')
    for mots, cle in _META_TIMELINE_MOTS:
        if any(mot in texte for mot in mots):
            return cle
    return ''


# ── CIQ407 — formulaire Meta « pour mon entreprise » (D-CIQ-19) ─────────────
#
# Mots ENTIERS sur du texte normalisé (``_norm_form_text``). L'ORDRE compte :
# un mot d'industrie l'emporte sur « entreprise »/« société » (« Entreprise
# industrielle » est une usine) ; un cas qui touche deux segments que rien
# ne départage ne pose AUCUN type (il reste dans la note).
_META_MOTS_RESIDENTIEL = (r'villa', r'maison', r'appartement', r'domicile',
                          r'residen\w*')
_META_MOTS_INDUSTRIEL = (r'usine', r'industri\w*', r'atelier', r'hangar')
_META_MOTS_AGRICOLE = (r'ferme', r'agricole', r'pompage', r'puits')
#: Activité → ``Lead.categorie_commerciale`` (liste fermée du contrat CIQ1).
_META_CATEGORIES = (
    ((r'hotel', r'riad'), 'hotel'),
    ((r'restaurant', r'cafe', r'snack'), 'restaurant'),
    ((r'entrepot frigorifique', r'chambre froide', r'froid'), 'froid'),
    ((r'supermarche', r'magasin', r'commerce', r'boutique'), 'commerce'),
    ((r'bureau', r'bureaux'), 'bureau'),
    ((r'clinique', r'cabinet', r'sante', r'centre medical'), 'sante'),
    ((r'ecole', r'creche', r'lycee'), 'ecole'),
    ((r'hammam', r'spa', r'gym', r'salle de sport'), 'hammam'),
    ((r'boulangerie', r'patisserie'), 'boulangerie'),
)
_META_MOTS_COMMERCIAL = (r'entreprise', r'societe', r'local')
_META_MOTS_TRANCHE_OUVERTE = ('plus de', 'au dela', 'superieur', '>',
                              'more than', 'over')
#: TQ-F6 (10/2026) — « moins de X » : le plancher d'une facture est 0, la
#: réponse vaut donc la tranche FERMÉE 0–X (même convention de milieu que les
#: autres tranches fermées) — jamais X comme montant.
_META_MOTS_TRANCHE_OUVERTE_BASSE = ('moins de', 'inferieur', '<',
                                    'less than', 'under')


def _meta_mot_entier(texte, motifs):
    return any(_re.search(rf'\b{motif}\b', texte) for motif in motifs)


def _meta_categorie(valeur_normalisee):
    """CIQ407 — la catégorie commerciale d'une réponse, ou '' (mots entiers ;
    la première catégorie de la table qui répond gagne)."""
    for motifs, cle in _META_CATEGORIES:
        if _meta_mot_entier(valeur_normalisee, motifs):
            return cle
    return ''


def _meta_type_installation(valeur_normalisee):
    """CIQ407 — le segment d'une réponse « où installer », ou ''.

    Industrie AVANT entreprise/société ; « local » en mot entier seulement ;
    une activité commerciale reconnue (clinique, école…) vaut commercial. Un
    cas ambigu (résidentiel ou agricole ET autre chose) ne pose rien."""
    v = valeur_normalisee
    residentiel = _meta_mot_entier(v, _META_MOTS_RESIDENTIEL)
    industriel = _meta_mot_entier(v, _META_MOTS_INDUSTRIEL)
    agricole = _meta_mot_entier(v, _META_MOTS_AGRICOLE)
    commercial = (_meta_mot_entier(v, _META_MOTS_COMMERCIAL)
                  or bool(_meta_categorie(v)))
    pro = industriel or commercial
    if sum((residentiel, agricole, pro)) != 1:
        return ''
    if residentiel:
        return Lead.TypeInstallation.RESIDENTIEL
    if agricole:
        return Lead.TypeInstallation.AGRICOLE
    if industriel:
        return Lead.TypeInstallation.INDUSTRIEL
    return Lead.TypeInstallation.COMMERCIAL


def _meta_tranche_facture(valeur_normalisee, libelle):
    """CIQ407 (D-CIQ-19) — ``(montant, tranche)`` d'une réponse de facture.

    Tranche FERMÉE (deux nombres) : montant = milieu (inchangé) + tranche
    {min, max}. Tranche OUVERTE (« plus de X ») : AUCUN montant, tranche
    {X, None}. Nombre unique sans « plus de » : un montant, pas de tranche."""
    texte = _re.sub(r'(?<=\d)[\s.](?=\d{3}\b)', '', valeur_normalisee)
    nums = [int(n) for n in _re.findall(r'\d{3,6}', texte)]
    if len(nums) >= 2:
        bas, haut = sorted(nums[:2])
        return (bas + haut) // 2, {'min_mad': bas, 'max_mad': haut,
                                   'libelle': libelle, 'source': 'meta'}
    if nums:
        if any(mot in texte for mot in _META_MOTS_TRANCHE_OUVERTE):
            return None, {'min_mad': nums[0], 'max_mad': None,
                          'libelle': libelle, 'source': 'meta'}
        if any(mot in texte for mot in _META_MOTS_TRANCHE_OUVERTE_BASSE):
            return nums[0] // 2, {'min_mad': 0, 'max_mad': nums[0],
                                  'libelle': libelle, 'source': 'meta'}
        return nums[0], None
    return None, None


def _parse_meta_form_extras(field_data):
    """Réponses NON-contact du formulaire Meta → champs CRM structurés.

    Renvoie un dict : ``qa`` (paires question/réponse verbatim, pour la note
    chatter — rien n'est perdu), et selon les questions reconnues :
    ``facture_estimee`` (MAD/mois — milieu de tranche, ou borne pour une
    tranche ouverte « plus de X »), ``facture_declaree`` (réponse verbatim),
    ``type_installation`` (choix canonique du modèle), ``priorite`` (dérivée
    du délai déclaré : « le plus tôt possible » → haute, « je me renseigne » →
    basse, sinon normale)."""
    contact_keys = {'full_name', 'nom', 'name', 'first_name', 'email',
                    'phone_number', 'telephone', 'city', 'ville'}
    extras = {'qa': []}
    for entry in (field_data or []):
        raw_name = str(entry.get('name', '')).strip()
        if raw_name.lower() in contact_keys:
            continue
        values = entry.get('values') or []
        raw_value = str((values[0] if values else '') or '')
        if not raw_value:
            continue
        extras['qa'].append((raw_name, raw_value))
        # CIQ407 — raison sociale et fonction : champs Meta standard,
        # recopiés en remplissage seulement (et cités dans la note).
        if raw_name.lower() == 'company_name':
            extras['societe'] = raw_value.strip()[:255]
            continue
        if raw_name.lower() == 'job_title':
            extras['fonction_contact'] = raw_value.strip()[:120]
            continue
        q = _norm_form_text(raw_name)
        v = _norm_form_text(raw_value)
        if 'facture' in q:
            # CIQ407 (D-CIQ-19) — une tranche OUVERTE (« plus de 4000 dh »)
            # n'est JAMAIS un montant : elle va dans la tranche déclarée,
            # la facture reste vide.
            montant, tranche = _meta_tranche_facture(
                v, raw_value.replace('_', ' '))
            if montant is not None:
                extras['facture_estimee'] = montant
            if tranche is not None:
                extras['facture_tranche'] = tranche
            extras['facture_declaree'] = raw_value
        elif 'quand' in q or 'commencer' in q or 'delai' in q:
            if 'plus tot possible' in v or 'ce mois' in v or 'immediat' in v:
                extras['priorite'] = Lead.Priorite.HAUTE
            elif 'renseigne' in v or 'compare' in v:
                extras['priorite'] = Lead.Priorite.BASSE
            else:
                extras['priorite'] = Lead.Priorite.NORMALE
            # CAD134 (audit L3 du 21/09/2026) — LA MÊME PHRASE VAUT LE MÊME
            # SCORE DES DEUX CÔTÉS. Depuis le site, « je veux démarrer
            # immédiatement » devenait `project_timeline='immediat'` et valait
            # +8 au score ; depuis Meta, « le plus tôt possible » ne devenait
            # qu'une `priorite=haute` — absente de `compute_score`, donc ZÉRO
            # point, aucune remontée dans la file, aucun changement d'heure ni
            # de canal. Le webhook Meta écrit donc AUSSI `project_timeline`,
            # qui est déjà scoré ; la priorité reste le drapeau MANUEL du
            # commercial.
            #
            # Conversion TOLÉRANTE (ce sont des mots-clés sur du texte libre,
            # de qualité inégale) et TRACÉE : le libellé BRUT part dans
            # `extras['qa']`, que la note de formulaire recopie telle quelle —
            # un humain peut donc toujours relire ce que le client a coché.
            # Un délai non reconnu ne pose RIEN plutôt qu'une valeur inventée.
            extras['delai_declare'] = raw_value
            delai = _meta_project_timeline(v)
            if delai:
                extras['project_timeline'] = delai
        elif 'install' in q or 'logement' in q or 'type de bien' in q:
            # CIQ407 — industrie AVANT entreprise/société, mots entiers ; un
            # cas ambigu ne pose aucun type (il reste dans la note).
            segment = _meta_type_installation(v)
            if segment:
                extras['type_installation'] = segment
            categorie = _meta_categorie(v)
            if categorie and segment == Lead.TypeInstallation.COMMERCIAL:
                extras['categorie_commerciale'] = categorie
        elif 'contact' in q and ('prefer' in q or 'joindre' in q
                                 or 'comment' in q):
            # TQ-F6 (10/2026) — « Comment préférez-vous être contacté ? » →
            # la préférence EXPLICITE du lead (QW3), remplissage seulement.
            if 'whatsapp' in v:
                extras['contact_preference'] = (
                    Lead.ContactPreference.WHATSAPP_ONLY)
            elif 'appel' in v or 'telephone' in v or 'phone' in v:
                extras['contact_preference'] = Lead.ContactPreference.PHONE_OK
        elif _meta_mot_entier(v, (r'proprietaire', r'locataire')):
            # TQ-F6 — « Vous êtes : propriétaire / locataire » → ownership
            # (champ site CAD150, éditable avec provenance).
            extras['ownership'] = (
                Lead.Ownership.PROPRIETAIRE if 'proprietaire' in v
                else Lead.Ownership.LOCATAIRE)
        elif 'activite' in q or 'secteur' in q or 'etablissement' in q:
            # CIQ407 — question d'activité du formulaire modifié par Reda.
            categorie = _meta_categorie(v)
            if categorie:
                extras['categorie_commerciale'] = categorie
        else:
            # AGR410 — FORM-AGRI-1 : questions de pompage reconnues par
            # mots-clés (``_meta_reponse_agricole``).
            _meta_reponse_agricole(q, v, extras)
    # AGR410 — une question AGRICOLE pose le type agricole, seulement si le
    # formulaire n'a pas dit autre chose (et ``_apply_meta_form_extras`` ne
    # l'écrit que sur un type VIDE).
    if extras.pop('_agricole', False):
        extras.setdefault('type_installation',
                          Lead.TypeInstallation.AGRICOLE)
    return extras


# ── AGR410 — Formulaire Meta agricole (FORM-AGRI-1) ─────────────────────────
#
# Mots-clés sur du texte NORMALISÉ (``_norm_form_text``). Une TRANCHE ne
# devient JAMAIS un nombre (pas de milieu de tranche) : seule une réponse à
# nombre UNIQUE, sans « plus/moins/entre », remplit une colonne ; sinon la
# réponse reste dans la note, mot pour mot. Rien n'est jamais écrasé
# (``_apply_meta_form_extras``). Aucune création de campagne ici (règle #3).
_META_SOURCE_EAU_MOTS = (
    (('forage',), 'forage'),
    (('puits',), 'puits'),
    (('bassin',), 'bassin'),
    (('riviere', 'oued'), 'riviere'),
)
_META_ENERGIE_POMPE_MOTS = (
    (('pas de pompe', 'aucune', 'pas encore'), 'aucune'),
    # « gazoil » AVANT « gaz » : l'ordre de la table compte.
    (('gasoil', 'diesel', 'gazoil'), 'diesel'),
    (('butane', 'gaz'), 'butane'),
    (('electri', 'reseau', 'onee'), 'electrique'),
)
_META_MOTS_TRANCHE = ('plus', 'moins', 'entre', '>', '<', 'jusqu')


def _meta_nombre_unique(valeur_normalisee):
    """Le nombre d'une réponse à nombre UNIQUE, ou None (tranche / texte)."""
    from decimal import Decimal, InvalidOperation

    texte = str(valeur_normalisee or '')
    if any(mot in texte for mot in _META_MOTS_TRANCHE):
        return None
    nombres = _re.findall(r'\d+(?:[.,]\d+)?', texte.replace(' ', ''))
    if len(nombres) != 1:
        return None
    try:
        return Decimal(nombres[0].replace(',', '.'))
    except InvalidOperation:
        return None


def _meta_mot_cle(valeur_normalisee, table):
    for mots, cle in table:
        if any(mot in valeur_normalisee for mot in mots):
            return cle
    return ''


def _meta_reponse_agricole(q, v, extras):
    """AGR410 — une question de pompage du formulaire Meta → ``extras``.

    ``q``/``v`` déjà normalisés. Pose ``extras['_agricole']`` dès qu'une
    question agricole est reconnue, même si sa réponse ne remplit rien."""
    from decimal import Decimal

    if (('eau' in q and ('source' in q or 'vient' in q or 'provient' in q))
            or 'puits' in q or 'forage' in q):
        extras['_agricole'] = True
        source = _meta_mot_cle(v, _META_SOURCE_EAU_MOTS)
        if source:
            extras['source_eau'] = source
    elif 'pompe' in q and any(k in q for k in (
            'energie', 'fonctionne', 'marche', 'alimente', 'alimentation')):
        extras['_agricole'] = True
        energie = _meta_mot_cle(v, _META_ENERGIE_POMPE_MOTS)
        if energie:
            extras['pompe_alim_actuelle'] = energie
    elif 'hectare' in q or ('surface' in q and (
            'irrig' in q or 'cultiv' in q or 'terrain' in q
            or 'exploitation' in q)):
        extras['_agricole'] = True
        surface = _meta_nombre_unique(v)
        if surface is not None and surface < Decimal('10000000'):
            extras['surface_irriguee_ha'] = surface
    elif ('depense' in q or 'depensez' in q) and any(k in q for k in (
            'carburant', 'gasoil', 'butane', 'gaz', 'pompe', 'diesel')):
        extras['_agricole'] = True
        depense = _meta_nombre_unique(v)
        if depense is not None and depense < Decimal('100000000'):
            extras['depense_carburant_mad_mois'] = depense


def _apply_meta_form_extras(lead, extras):
    """Pose les champs structurés du formulaire SANS jamais écraser une valeur
    déjà présente (une saisie humaine gagne toujours sur l'auto-remplissage).
    ``priorite`` : posée seulement en « upgrade » (NORMALE par défaut → HAUTE
    déclarée) — jamais de downgrade automatique. Renvoie la liste des champs
    modifiés (vide si rien à faire)."""
    from decimal import Decimal

    changed = []
    # AGR410 — le type d'abord : sur un lead AGRICOLE, la tranche de facture
    # ne remplit PAS facture_hiver (elle gonflerait son score) — elle reste
    # dans la note seulement.
    if extras.get('type_installation') and not lead.type_installation:
        lead.type_installation = extras['type_installation']
        changed.append('type_installation')
    if (extras.get('facture_estimee') is not None and lead.facture_hiver is None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE):
        lead.facture_hiver = Decimal(int(extras['facture_estimee']))
        changed.append('facture_hiver')
    # CIQ407 (D-CIQ-19) — la tranche déclarée : toujours pour une tranche
    # OUVERTE (jamais un montant), en plus du milieu pour un PRO.
    tranche = extras.get('facture_tranche')
    if (tranche and lead.facture_tranche_declaree is None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE
            and (tranche['max_mad'] is None or lead.type_installation in (
                Lead.TypeInstallation.COMMERCIAL,
                Lead.TypeInstallation.INDUSTRIEL))):
        lead.facture_tranche_declaree = dict(tranche)
        changed.append('facture_tranche_declaree')
    # CIQ407 — activité, raison sociale, fonction : remplissage seulement.
    for champ in ('categorie_commerciale', 'societe', 'fonction_contact'):
        if extras.get(champ) and not getattr(lead, champ, None):
            setattr(lead, champ, extras[champ])
            changed.append(champ)
    # AGR410 — réponses de pompage : remplissage seulement, jamais
    # d'écrasement.
    for champ in ('source_eau', 'pompe_alim_actuelle', 'surface_irriguee_ha',
                  'depense_carburant_mad_mois'):
        if extras.get(champ) is not None and getattr(lead, champ) in (
                None, ''):
            setattr(lead, champ, extras[champ])
            changed.append(champ)
    if (extras.get('priorite') == Lead.Priorite.HAUTE
            and lead.priorite == Lead.Priorite.NORMALE):
        lead.priorite = Lead.Priorite.HAUTE
        changed.append('priorite')
    # CAD134 — le délai déclaré remplit le champ DÉJÀ scoré, et seulement
    # s'il est vide : un délai saisi à la main par la commerciale (ou venu du
    # site) n'est JAMAIS écrasé par un mot-clé lu sur du texte libre.
    if extras.get('project_timeline') and not getattr(
            lead, 'project_timeline', None):
        lead.project_timeline = extras['project_timeline']
        changed.append('project_timeline')
    # TQ-F6 (10/2026) — statut d'occupation et préférence de contact lus sur
    # le formulaire : remplissage seulement, jamais d'écrasement ; la
    # préférence est horodatée (QX15 : le SLA rappel court depuis sa pose).
    if extras.get('ownership') and not getattr(lead, 'ownership', None):
        lead.ownership = extras['ownership']
        changed.append('ownership')
    if (extras.get('contact_preference')
            and not getattr(lead, 'contact_preference', None)):
        lead.contact_preference = extras['contact_preference']
        lead.contact_preference_set_at = timezone.now()
        changed.extend(['contact_preference', 'contact_preference_set_at'])
    if lead.telephone and not lead.whatsapp:
        # Un lead Meta arrive par mobile : le même numéro sert de lien wa.me
        # pour la première prise de contact de Meryem.
        lead.whatsapp = lead.telephone
        changed.append('whatsapp')
    return changed


def _enrichir_meta_trace(lead, extras):
    """ACRM14 (C-ACRM-009) — applique ``_apply_meta_form_extras`` et
    JOURNALISE chaque champ écrit (une ligne MODIFICATION par champ :
    champ, ancienne → nouvelle valeur, acteur système) : un enrichissement
    automatique est visible au chatter comme toute autre écriture. Enregistre
    les champs modifiés et les rend."""
    from . import activity as _activity

    avant = {}
    for champ in ('type_installation', 'facture_hiver',
                  'facture_tranche_declaree', 'categorie_commerciale',
                  'societe', 'fonction_contact', 'source_eau',
                  'pompe_alim_actuelle', 'surface_irriguee_ha',
                  'depense_carburant_mad_mois', 'priorite', 'project_timeline',
                  'whatsapp', 'ownership', 'contact_preference'):
        avant[champ] = getattr(lead, champ, None)
    changed = _apply_meta_form_extras(lead, extras)
    if changed:
        lead.save(update_fields=changed)
        for champ in changed:
            if champ == 'contact_preference_set_at':
                continue   # horodatage technique, pas une donnée du client
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.MODIFICATION, field=champ,
                field_label=_activity.TRACKED_FIELDS.get(champ, champ),
                old_value=_activity._display(lead, champ, avant.get(champ)),
                new_value=_activity._display(
                    lead, champ, getattr(lead, champ, None)))
    return changed


def _meta_deja_enrichi(lead):
    """ACRM14 — la note « [Formulaire Meta] » (marqueur EXISTANT de
    ``_ensure_meta_form_note``) dit qu'une première passe a déjà enrichi ce
    lead : une passe suivante (rejeu webhook, pull) ne réécrit plus rien —
    une correction humaine faite entre-temps SURVIT."""
    return LeadActivity.objects.filter(
        lead=lead, body__startswith=_META_FORM_NOTE_MARKER).exists()


def _ensure_meta_form_note(lead, extras, form_id=''):
    """Une note chatter avec TOUTES les réponses verbatim du formulaire —
    rien n'est perdu, même les questions non reconnues. Idempotente par
    marqueur (retries webhook / re-passes du pull ne dupliquent jamais)."""
    if not extras.get('qa'):
        return
    if LeadActivity.objects.filter(
            lead=lead, body__startswith=_META_FORM_NOTE_MARKER).exists():
        return
    suffix = f' (formulaire {form_id})' if form_id else ''
    lines = [f'{_META_FORM_NOTE_MARKER} Réponses du prospect{suffix} :']
    for question, answer in extras['qa']:
        lines.append('• %s → %s' % (question.replace('_', ' '),
                                    answer.replace('_', ' ')))
    # AGR410 — sur un lead agricole, la facture n'est PAS pré-remplie : la
    # note ne le prétend pas (la réponse reste citée mot pour mot plus haut).
    if (extras.get('facture_estimee') is not None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE):
        lines.append(
            '(facture hiver pré-remplie à %s MAD depuis la tranche déclarée '
            '« %s » — à préciser au premier appel)'
            % (int(extras['facture_estimee']),
               extras.get('facture_declaree', '').replace('_', ' ')))
    elif (extras.get('facture_tranche') or {}).get('max_mad', 0) is None:
        # CIQ407 (D-CIQ-19) — tranche ouverte : AUCUN montant pré-rempli.
        lines.append(
            '(tranche ouverte « %s » : aucune facture pré-remplie — le '
            'montant réel est à demander au premier appel)'
            % extras.get('facture_declaree', '').replace('_', ' '))
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body='\n'.join(lines))


#: MRY0 (lot B) — bornes d'acceptation d'une ``created_time`` Meta : on ne
#: repose JAMAIS une date de création hors de cette fenêtre (une valeur
#: aberrante fausserait SLA et KPI aussi sûrement que l'heure du pull).
_META_CREATED_TIME_MAX_ANCIENNETE_JOURS = 90
_META_CREATED_TIME_MARGE_FUTUR_MINUTES = 5


def _parse_meta_created_time(brut):
    """``created_time`` Meta → datetime aware, ou ``None``.

    Deux formes réelles : ISO ``2026-09-03T11:04:04+0000`` (pull) et epoch
    secondes (webhook). Hors de la fenêtre ``[now - 90 j, now + 5 min]`` →
    ``None`` (refusée, jamais posée)."""
    import datetime as _dt

    from django.utils.dateparse import parse_datetime as _parse_dt

    if brut in (None, ''):
        return None
    moment = None
    if isinstance(brut, bool):
        return None
    if isinstance(brut, _dt.datetime):
        moment = brut
    elif isinstance(brut, (int, float)):
        try:
            moment = _dt.datetime.fromtimestamp(
                int(brut), tz=_dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        texte = str(brut).strip()
        if texte.isdigit():
            try:
                moment = _dt.datetime.fromtimestamp(
                    int(texte), tz=_dt.timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        else:
            try:
                moment = _parse_dt(texte)
            except ValueError:
                return None
    if moment is None:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, _dt.timezone.utc)
    maintenant = timezone.now()
    if moment > maintenant + _dt.timedelta(
            minutes=_META_CREATED_TIME_MARGE_FUTUR_MINUTES):
        return None
    if moment < maintenant - _dt.timedelta(
            days=_META_CREATED_TIME_MAX_ANCIENNETE_JOURS):
        return None
    return moment


def create_lead_from_meta_lead_ads(
        *, company, leadgen_id, field_data,
        ad_id='', adgroup_id='', form_id='', access_token='',
        created_time=None, origine='') -> Lead:
    """XMKT32 — Crée (ou dédupe sur) un lead depuis un formulaire Meta Lead Ads.

    Point d'entrée cross-app sanctionné (services.py), appelé par
    ``webhooks.meta_lead_ads_webhook`` une fois le lead récupéré via l'API
    officielle (jamais de scraping). ``field_data`` est la liste
    ``[{'name': ..., 'values': [...]}, ...]`` renvoyée par le Graph API pour
    ce ``leadgen_id`` — seuls des champs connus (nom/email/téléphone/ville)
    sont lus.

    Dédup — D-CRX1 (décision fondateur du 02/09/2026) : UNE SEULE couche.
      1. même ``leadgen_id`` déjà traité (idempotence webhook — retries Meta)
         → renvoie le lead existant, enrichi (backfill) depuis le formulaire.

    L'ancienne « Couche 2 (QJ8) » — téléphone/e-mail connu dans la société ⇒
    ABSORPTION de la touche dans le lead existant — est SUPPRIMÉE. Chaque
    touche Meta est une nouvelle demande et crée un NOUVEAU lead, exactement
    comme une soumission du site (règle fondateur du 18/08/2026, étendue à Meta
    le 02/09/2026). Aucun lead existant n'est plus écrit par ce chemin : le
    rapprochement se fait EN VISIBILITÉ, avec les deux mêmes primitives que le
    webhook site (aucune seconde implémentation) —
      • ``webhooks._flag_possible_duplicates`` pose UNE note chatter de doublon
        sur le NOUVEAU lead (les archivés y sont mentionnés, cf. QW11) ;
      • ``webhooks._pick_owner_from_duplicates`` fait HÉRITER le commercial du
        doublon le plus pertinent (parité QW11), pour qu'un même client ne soit
        jamais rappelé par deux commerciaux différents.
    Conséquence VOULUE : un contact connu mais ARCHIVÉ donne lui aussi un
    NOUVEAU lead — il est signalé dans la note sans transmettre son owner
    (l'absorption, elle, ressuscitait silencieusement la fiche au rebut).
    L'attribution (canal/utm/meta_ids) et ``external_system``/``external_id``
    se posent donc TOUJOURS sur le lead nouvellement créé.

    Attribution (ADSENG1) : ``canal=META_ADS``, ``utm_source='facebook'``.
    Meta ne pousse JAMAIS campaign_name/adset_name dans le webhook leadgen ; il
    pousse ``ad_id``/``adgroup_id``/``form_id`` — capturés ici en clés de
    jointure stables (``meta_ad_id``/``meta_adset_id``/``meta_campaign_id``/
    ``meta_form_id``). Les NOMS lisibles sont résolus via les miroirs adsengine
    (``adsengine.selectors.resolve_meta_ad_names`` — jamais un import des modèles
    adsengine), avec repli paresseux via l'API si ``access_token`` est fourni.
    ``utm_campaign`` porte le nom de campagne résolu ; ``utm_content`` suit la
    convention ``ad-<ad_id>`` (formalisée en ADSENG23) — jamais l'adset_name,
    toujours vide en prod.

    Best-effort côté séquence de bienvenue : XMKT1 (moteur d'exécution des
    séquences) n'est pas encore construit — aucune inscription automatique
    tant qu'il n'existe pas ; ce service reste le point d'accroche futur.

    MRY0 (lot B) — ``created_time`` : l'heure Meta RÉELLE de la soumission.
    Appliquée UNIQUEMENT à la création (jamais sur un lead déjà capturé) et
    seulement si elle tombe dans ``[now - 90 j, now + 5 min]``. ``date_creation``
    étant ``auto_now_add``, elle n'est pas posable au ``create()`` : on la
    repose par un ``update()`` ciblé. Sans elle, un lead rattrapé par le pull
    portait l'heure du beat (07:25) et faussait SLA, KPI premier contact et
    notifications. ``origine`` (texte libre, ex. « Meta Lead Ads (webhook) »)
    nomme le chemin d'entrée dans la ligne « création » du chatter.
    """
    fields = {}
    for entry in (field_data or []):
        name = str(entry.get('name', '')).strip().lower()
        values = entry.get('values') or []
        value = (values[0] if values else '') or ''
        if name in ('full_name', 'nom', 'name'):
            fields['nom'] = str(value)[:255]
        elif name == 'first_name':
            fields.setdefault('nom', str(value)[:255])
        elif name in ('email',):
            fields['email'] = str(value)[:254]
        elif name in ('phone_number', 'telephone'):
            fields['telephone'] = str(value)[:20]
        elif name in ('city', 'ville'):
            fields['ville'] = str(value)[:120]
    # Réponses métier du formulaire (facture, type d'installation, délai…) —
    # structurées vers les VRAIS champs CRM, verbatim conservé en note.
    extras = _parse_meta_form_extras(field_data)

    # ── Couche 1 : idempotence sur le leadgen_id (retries webhook Meta) ──────
    # Un lead déjà capturé n'est PAS renvoyé tel quel : il est ENRICHI
    # (backfill) depuis les réponses du formulaire — champs vides uniquement,
    # jamais un écrasement de saisie humaine. C'est ce chemin qui remplit les
    # leads importés avant que le mapping complet n'existe.
    existing = Lead.objects.filter(
        company=company, external_system=_META_LEAD_ADS_SYSTEM,
        external_id=str(leadgen_id)).first()
    if existing is not None:
        # ACRM14 — UNE seule passe d'enrichissement : déjà enrichi (note
        # « [Formulaire Meta] » présente) → aucune écriture, la saisie
        # humaine faite depuis la première passe gagne.
        if _meta_deja_enrichi(existing):
            return existing
        _enrichir_meta_trace(existing, extras)
        if fields.get('ville') and not existing.ville:
            existing.ville = fields['ville']
            existing.save(update_fields=['ville'])
        _ensure_meta_form_note(existing, extras, form_id=str(form_id or ''))
        return existing

    nom = (fields.get('nom') or '').strip() or 'Lead Meta Ads'
    telephone = fields.get('telephone') or ''
    # ACRM38 — l'e-mail du formulaire Meta est nettoyé et validé comme
    # celui du site (``_clean_email``) : un « ' ' » n'est jamais une identité.
    from .webhooks import _clean_email
    email = _clean_email(fields.get('email')) or ''

    # ── D-CRX1 : plus AUCUNE absorption ─────────────────────────────────────
    # Les doublons sont cherchés ICI, AVANT la création, pour DEUX usages
    # strictement en lecture : (a) l'héritage du commercial (QW11) qui doit
    # être décidé avant le round-robin, (b) la note de signalement posée après
    # la création. Aucun lead existant n'est modifié sur ce chemin. Une seule
    # requête, réutilisée par les deux (jamais deux fois la même).
    dupes = []
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)

    # ADSENG1 — identifiants Meta natifs (clés de jointure stables) + noms
    # résolus via les miroirs adsengine (jamais un import des modèles adsengine).
    ad_id = str(ad_id or '')
    adgroup_id = str(adgroup_id or '')
    form_id = str(form_id or '')
    from apps.adsengine.selectors import resolve_meta_ad_names
    names = resolve_meta_ad_names(
        company, ad_id=ad_id, adgroup_id=adgroup_id, access_token=access_token)

    utm_source = 'facebook'
    utm_campaign = (names.get('campaign_name') or '')[:300] or None
    # Convention ADSENG23 : utm_content = ad-<ad_id> (jamais l'adset_name).
    utm_content = f'ad-{ad_id}'[:300] if ad_id else None
    meta_ad_id = ad_id[:64] or None
    meta_adset_id = adgroup_id[:64] or None
    meta_campaign_id = (names.get('campaign_id') or '')[:64] or None
    meta_form_id = form_id[:64] or None

    # QW11 (parité site) — l'héritage du commercial se décide AVANT le
    # round-robin : un lead qui EST un doublon n'entre pas dans l'attribution
    # normale, il revient au commercial qui suit déjà ce contact. Les deux
    # filtres d'éligibilité (doublon non archivé, owner actif+habilité) sont
    # DANS ``_pick_owner_from_duplicates`` — jamais redécidés ici.
    from .webhooks import _flag_possible_duplicates, _pick_owner_from_duplicates

    extra = {}
    inherited_owner, inherited_from = _pick_owner_from_duplicates(
        dupes, telephone=telephone, email=email, company=company)
    if inherited_owner is not None:
        extra['owner'] = inherited_owner
    else:
        # CIQ416 — le type lu sur le formulaire route un lead pro vers son
        # responsable désigné (sinon : comportement inchangé).
        default = default_responsable_for(
            company,
            lead_attrs={'type_installation': extras.get('type_installation')})
        if default is not None:
            extra['owner'] = default
    # À la CRÉATION, le délai déclaré pose la priorité pleinement (haute,
    # normale ou basse) ; en enrichissement (leads existants), seule la
    # montée NORMALE→HAUTE est automatique (_apply_meta_form_extras).
    if extras.get('priorite'):
        extra['priorite'] = extras['priorite']
    # CAD134 — et le MÊME délai déclaré pose `project_timeline`, le champ que
    # `compute_score` lit déjà : depuis Meta la phrase « le plus tôt possible »
    # valait zéro point, contre +8 pour la même phrase venue du site.
    if extras.get('project_timeline'):
        extra['project_timeline'] = extras['project_timeline']
    lead = Lead.objects.create(
        company=company,
        nom=nom,
        email=email or None,
        telephone=telephone or None,
        ville=fields.get('ville') or None,
        source=Lead.Source.META_LEAD_ADS,
        canal=Lead.Canal.META_ADS,
        utm_source=utm_source,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        meta_ad_id=meta_ad_id,
        meta_adset_id=meta_adset_id,
        meta_campaign_id=meta_campaign_id,
        meta_form_id=meta_form_id,
        external_system=_META_LEAD_ADS_SYSTEM,
        external_id=str(leadgen_id),
        **extra,
    )
    # Réponses métier du formulaire → champs structurés (facture hiver,
    # type d'installation, priorité selon le délai déclaré, wa.me).
    # ACRM14 — chaque champ écrit est journalisé (ancien → nouveau).
    _enrichir_meta_trace(lead, extras)
    # MRY0 (lot B) — vraie date d'arrivée : ``date_creation`` est
    # ``auto_now_add`` (models.py), donc jamais posable au ``create()``.
    moment_meta = _parse_meta_created_time(created_time)
    if moment_meta is not None:
        Lead.objects.filter(pk=lead.pk).update(date_creation=moment_meta)
        lead.refresh_from_db(fields=['date_creation'])
    activity.log_creation(lead, None, origine=origine)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body='Lead créé depuis Meta Lead Ads (formulaire Facebook/Instagram).')
    _ensure_meta_form_note(lead, extras, form_id=str(form_id or ''))
    # CAD90 — la cohorte Meta n'avait aucune entrée au registre : ses données
    # ne sont pas collectées auprès de la personne par nous (art. 5 §3), et
    # l'horodatage tracé est celui de l'arrivée RÉELLE, jamais celui du beat.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_META_LEAD_ADS,
        base_legale=BASE_LEGALE_NON_COLLECTEE,
        occurred_at=moment_meta or lead.date_creation)
    # D-CRX1 — signalement du doublon EN VISIBILITÉ (jamais une fusion), avec
    # la mention de l'héritage quand il a eu lieu. Réutilise ``dupes`` déjà
    # calculés (jamais une 2e requête). Best-effort, comme côté site : un
    # rapprochement en échec ne remet jamais la capture du lead en cause.
    try:
        _flag_possible_duplicates(
            lead, telephone=telephone, email=email, dupes=dupes,
            inherited_owner=inherited_owner, inherited_from=inherited_from)
    except Exception as _exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'create_lead_from_meta_lead_ads: note de doublon échouée '
            '(lead #%s) : %s', lead.pk, _exc)
    try:
        notify_new_lead(lead)
    except Exception:  # noqa: BLE001 — best-effort
        pass

    # MRY6 — démarrage EXPLICITE de la cadence de contact. Best-effort :
    # une cadence en échec ne fait JAMAIS échouer la création du lead.
    demarrer_cadence_contact(lead, origine='meta_lead_ads')
    recompute_lead_score(lead)
    return lead


def import_external_notes_for_contact(company, *, phone=None, email=None,
                                      notes):
    """Importe des notes EXTERNES (ex. chatter Odoo) dans le chatter du lead
    correspondant — point d'entrée cross-app sanctionné (services.py), appelé
    par la commande ``adsengine.odoo_import_notes``.

    ``notes`` : liste de paires ``(marker, body)`` — ``marker`` est le préfixe
    d'idempotence du corps (ex. ``[Odoo note 123]``) : une note déjà importée
    (même marqueur sur ce lead) n'est JAMAIS dupliquée, la commande est
    re-exécutable à volonté.

    Matching : téléphone puis email, via les mêmes colonnes normalisées que le
    reste du CRM (``find_duplicates_by_contact``) ; prend le lead le plus
    récent. Renvoie ``(matched: bool, created: int)`` — aucun lead n'est créé
    ici (les leads sans correspondance attendent la migration complète)."""
    dupes = find_duplicates_by_contact(
        company, phone=phone or None, email=email or None)
    if not dupes:
        return False, 0
    lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]
    created = 0
    for marker, body in notes:
        if not (body or '').strip():
            continue
        if LeadActivity.objects.filter(
                lead=lead, body__startswith=marker).exists():
            continue
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=body)
        created += 1
    return True, created


def create_minimal_lead_from_ctwa(*, company, phone, ad_id='') -> Lead:
    """PUB27 — Crée (ou dédupe sur) un Lead minimal pour une conversation
    WhatsApp/CTWA entrante SANS lead préalable.

    Point d'entrée cross-app WRITE sanctionné (services.py — jamais un import
    des modèles crm côté adsengine) : appelé par
    ``apps.adsengine.whatsapp_webhook`` quand ``_lead_id_for_phone`` ne trouve
    AUCUN lead pour le téléphone d'un message entrant portant un ``referral``
    CTWA (Click-to-WhatsApp) — jusqu'ici, ce cas laissait le ``CtwaReferral``
    orphelin (``crm_lead_id=None``) et l'attribution par ad était perdue.

    Dédupliqué par TÉLÉPHONE (``find_duplicates_by_contact`` — mêmes colonnes
    normalisées QW10 que le reste du CRM, indexées) : un second message de la
    même conversation (ou un prospect déjà connu par un autre canal) ne crée
    JAMAIS de doublon — renvoie le lead existant le plus récent tel quel, sans
    l'altérer (« referral avec lead → comportement inchangé »).

    Env-gated COMME le webhook : cette fonction n'est jamais appelée hors de
    ``WhatsAppCloudWebhookView.post`` (gardé par
    ``WHATSAPP_CLOUD_VERIFY_TOKEN``/``WHATSAPP_CLOUD_APP_SECRET`` — sans les
    deux, le webhook répond 404 et n'atteint jamais ce chemin), donc aucun
    flag séparé n'est nécessaire ici.

    Attribution : ``canal=WHATSAPP_CTWA``, ``meta_ad_id`` posé quand
    ``ad_id`` est fourni (même colonne de jointure que ADSENG1/XMKT32 — la
    variante Meta reste résolvable par ``apps.adsengine.attribution``).
    ``source=OS_NATIVE`` (créé nativement dans l'ERP — CTWA n'est pas un
    import, contrairement à ``META_LEAD_ADS``)."""
    phone = (phone or '').strip()
    if not phone or company is None:
        return None

    dupes = find_duplicates_by_contact(company, phone=phone)
    if dupes:
        return sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    extra = {}
    default = default_responsable_for(company)
    if default is not None:
        extra['owner'] = default
    ad_id = str(ad_id or '')[:64] or None
    lead = Lead.objects.create(
        company=company,
        nom='Lead WhatsApp/CTWA',
        telephone=phone,
        source=Lead.Source.OS_NATIVE,
        canal=Lead.Canal.WHATSAPP_CTWA,
        meta_ad_id=ad_id,
        **extra,
    )
    activity.log_creation(lead, None)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body='Lead créé depuis une conversation WhatsApp/CTWA entrante '
             '(aucun lead préalable trouvé pour ce numéro).',
    )
    # CAD90 — la personne a ÉCRIT la première : relation précontractuelle à
    # sa demande. Le registre le dit, plutôt que de rester muet sur un lead
    # dont la touche n°1 partira justement sur WhatsApp.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_WHATSAPP_ENTRANT,
        base_legale=BASE_LEGALE_SOLLICITATION)
    try:
        notify_new_lead(lead)
    except Exception:  # noqa: BLE001 — best-effort
        pass
    # MRY6 — démarrage EXPLICITE de la cadence de contact. Best-effort :
    # une cadence en échec ne fait JAMAIS échouer la création du lead.
    demarrer_cadence_contact(lead, origine='ctwa')
    recompute_lead_score(lead)
    return lead


def fetch_meta_lead_node(leadgen_id, access_token):  # pragma: no cover - réseau
    """ADSENG1 — Récupère les identifiants natifs (ad_id/adgroup_id/form_id) du
    nœud lead Meta via le Graph API officiel, pour le backfill.

    Isolé en fonction module (jamais dans ``webhooks.py`` — inchangé hors
    mapping) pour rester simulable en test (monkeypatch). Renvoie le dict brut
    ou lève sur échec (capté par l'appelant, best-effort par lead).

    CRX5 — la version de l'API vient de la SOURCE UNIQUE partagée
    (``apps.adsengine.api_version.GRAPH_BASE_URL``), jamais d'un littéral :
    la « v25.0 » codée en dur ici était la dernière copie divergente du
    dépôt, et c'est exactement de cette façon que la v19.0 du webhook est
    restée morte en production pendant des mois (ADSENG2). Constante plain —
    aucun modèle adsengine n'est importé.
    """
    import json
    import urllib.parse
    import urllib.request

    from apps.adsengine.api_version import GRAPH_BASE_URL

    qs = urllib.parse.urlencode({
        'fields': 'ad_id,adgroup_id,form_id',
        'access_token': access_token,
    })
    url = f'{GRAPH_BASE_URL}/{leadgen_id}?{qs}'
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def backfill_meta_lead_attribution(
        *, company=None, access_token='', fetch_fn=None, limit=None):
    """ADSENG1 — Rétro-remplit l'attribution par variante des leads Lead Ads
    EXISTANTS (créés avant qu'on capture ad_id/adgroup_id/form_id).

    Pour chaque ``Lead`` de source ``meta_lead_ads`` dont ``meta_ad_id`` est
    encore vide, récupère ses identifiants natifs (ad_id/adgroup_id/form_id)
    depuis le nœud lead Meta via ``fetch_fn(leadgen_id, access_token)`` (défaut :
    ``services.fetch_meta_lead_node``, juste au-dessus — CRX5 : la docstring
    nommait ``webhooks.fetch_meta_lead_node``, qui n'a jamais existé et
    envoyait le lecteur chercher dans le mauvais module ; injectable/simulable
    en test), les
    stocke, résout les noms via les miroirs adsengine, et remplit ``utm_content``
    = ``ad-<ad_id>`` + ``utm_campaign`` = nom de campagne résolu.

    IDEMPOTENT : un lead déjà backfillé (``meta_ad_id`` non vide) est sauté ; une
    seconde exécution ne change rien. Best-effort par lead : un échec réseau sur
    un lead n'interrompt jamais le lot (loggé, sauté). Scopé société si
    ``company`` fourni. Renvoie ``{'scanned', 'updated', 'skipped', 'failed'}``.
    """
    import logging
    from django.db.models import Q
    from apps.adsengine.selectors import resolve_meta_ad_names

    if fetch_fn is None:
        fetch_fn = fetch_meta_lead_node
    _log = logging.getLogger(__name__)

    qs = Lead.objects.filter(
        external_system=_META_LEAD_ADS_SYSTEM,
        external_id__isnull=False,
    ).filter(
        Q(meta_ad_id__isnull=True) | Q(meta_ad_id=''),
    )
    if company is not None:
        qs = qs.filter(company=company)
    qs = qs.order_by('id')
    if limit:
        qs = qs[:limit]

    stats = {'scanned': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
    for lead in qs:
        stats['scanned'] += 1
        try:
            node = fetch_fn(lead.external_id, access_token) or {}
        except Exception as exc:  # noqa: BLE001 — un lead ne bloque pas le lot
            stats['failed'] += 1
            _log.warning(
                'backfill_meta_lead_attribution: fetch échoué (lead #%s) : %s',
                lead.pk, exc)
            continue
        ad_id = str(node.get('ad_id') or '')
        adgroup_id = str(node.get('adgroup_id') or node.get('adset_id') or '')
        form_id = str(node.get('form_id') or '')
        if not ad_id:
            stats['skipped'] += 1
            continue
        names = resolve_meta_ad_names(
            lead.company, ad_id=ad_id, adgroup_id=adgroup_id,
            access_token=access_token)
        lead.meta_ad_id = ad_id[:64]
        lead.meta_adset_id = adgroup_id[:64] or lead.meta_adset_id
        lead.meta_form_id = form_id[:64] or lead.meta_form_id
        campaign_id = (names.get('campaign_id') or '')[:64]
        if campaign_id and not lead.meta_campaign_id:
            lead.meta_campaign_id = campaign_id
        # utm_content = ad-<ad_id> (convention ADSENG23) ; remplit sans écraser
        # une valeur déjà posée par un autre canal (first-touch préservée).
        if not lead.utm_content:
            lead.utm_content = f'ad-{ad_id}'[:300]
        campaign_name = (names.get('campaign_name') or '')[:300]
        if campaign_name and not lead.utm_campaign:
            lead.utm_campaign = campaign_name
        lead.save()
        stats['updated'] += 1
    return stats


# ── XMKT37 — Livechat / assistant IA de qualification (ERP-side) ─────────────

def create_lead_from_livechat(*, company, nom, telephone='', email='',
                              transcript_text='') -> Lead:
    """XMKT37 — Crée (ou dédupe sur) un lead dès que nom + contact sont captés
    par une session de livechat public.

    Point d'entrée cross-app sanctionné (services.py), appelé par
    ``apps.crm.public_chat_views``. Dédup (QJ8) par téléphone/email dans la
    société avant de créer (comme le webhook site) ; canal ``livechat``,
    stage NEW (STAGES.py, jamais hardcodé — ``Lead.stage`` a NEW pour
    défaut). Le transcript complet est collé en note chatter (``LeadActivity``).
    """
    nom = (nom or '').strip()[:255] or 'Prospect livechat'
    telephone = (telephone or '').strip()[:20]
    email = (email or '').strip()[:254]

    lead = None
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)
        if dupes:
            lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    if lead is None:
        extra = {}
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default
        lead = Lead.objects.create(
            company=company,
            nom=nom,
            telephone=telephone or None,
            email=email or None,
            canal=Lead.Canal.AUTRE,
            **extra,
        )
        activity.log_creation(lead, None)
        try:
            notify_new_lead(lead)
        except Exception:  # noqa: BLE001 — best-effort
            pass
        # MRY6 — même démarrage explicite que les autres créateurs vivants.
        demarrer_cadence_contact(lead, origine='livechat')
    else:
        changed = False
        if telephone and not lead.telephone:
            lead.telephone = telephone
            changed = True
        if email and not lead.email:
            lead.email = email
            changed = True
        if changed:
            lead.save()

    if transcript_text:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=f'Transcript livechat :\n{transcript_text}')

    recompute_lead_score(lead)
    return lead


def noter_devis_ouvert(devis_reference: str, lead) -> None:
    """QJ1 — Consigne « Le client a ouvert le devis » dans le chatter du lead.

    Appelé par ``public_views.py`` uniquement à la PREMIÈRE ouverture du lien
    public. Best-effort : les appelants catchent toute exception.
    ``lead`` doit être un objet Lead avec company_id ; ``devis_reference`` est
    la référence textuelle du devis (pas d'import ventes ici).

    YLEAD10 — après la note, avance aussi l'étape du lead vers FOLLOW_UP
    (fast-lane comportemental : une forte intention — l'ouverture de la
    proposition — sort le lead du parking). Distinct de QJ5 (re-stage sur
    staleness TEMPORELLE) : ici le déclencheur est un COMPORTEMENT observé.
    """
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Le client a ouvert le devis {devis_reference}")
    # RÈGLE FONDATEUR 07/09/2026 — plus d'avance de funnel AUTOMATIQUE sur
    # l'ouverture (YLEAD10 débranché) : le funnel ne bouge que sur une
    # réponse confirmée de Meryem. La note et la notification restent.
    # CAD133 — le score, lui, se recalcule À L'INSTANT : sans cela le badge
    # mentirait jusqu'au passage nocturne, et la file du jour classerait un
    # client qui vient d'ouvrir sa proposition comme s'il n'avait rien fait.
    recompute_lead_score(lead)


def noter_devis_reouvert(devis_reference: str, lead, vues=None) -> None:
    """QJ1bis (fondateur 07/09/2026) — Consigne une RÉOUVERTURE du devis dans
    le chatter du lead : chaque retour du client sur sa proposition doit
    rester lisible dans l'historique (les notifications s'effacent, le
    chatter reste). Appelé par ``public_views._notify_open`` sur toute
    ouverture publique au-delà de la première, hors fenêtre de
    sessionisation. ``vues`` (compteur ShareLink) contextualise sans jamais
    être inventé — omis s'il est inconnu."""
    suffixe = f' — {int(vues)}ᵉ consultation' if vues and int(vues) > 1 else ''
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Le client a rouvert le devis {devis_reference}{suffixe}")
    # CAD133 — revenir sur sa proposition est le signal de comportement le
    # plus fort : le score monte À L'INSTANT, pas au passage nocturne.
    recompute_lead_score(lead)


def noter_devis_envoye(devis_reference: str, lead) -> None:
    """ZSAL5 — Consigne « Devis DEV-… envoyé par email » dans le chatter du
    lead. Appelé par ``apps.ventes`` (jamais d'import des models crm depuis
    ventes) quand l'action d'envoi de devis (QJ14) réussit. ``lead`` doit
    être un objet Lead avec company_id ; ``devis_reference`` est la
    référence textuelle du devis (pas d'import ventes ici). Note système
    (``user=None``), best-effort — l'appelant catche toute exception."""
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Devis {devis_reference} envoyé par email")


def noter_devis_corrige(devis_reference: str, lead, resume: str = '') -> None:
    """QJR518 — reflet sur le chatter du LEAD d'une correction après envoi
    d'un devis (même patron que ``noter_devis_envoye`` : appelé par
    ``apps.ventes``, jamais d'import des models crm depuis ventes ; note
    système, best-effort — l'appelant catche toute exception)."""
    detail = f' ({resume})' if resume else ''
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Devis {devis_reference} corrigé après envoi{detail}")


def noter_touche_marketing(lead, message, *, ordre=0, cout=None):
    """XMKT16 — Consigne un événement marketing significatif (envoi/ouverture/
    clic de campagne, étape de séquence exécutée, réponse WhatsApp entrante)
    dans le chatter du lead (``LeadActivity``) + le journal d'attribution
    multi-touch FG204 (``PointContact``). Appelé par le module marketing de
    compta — jamais d'import du modèle CRM depuis compta, ce point d'entrée
    reste dans ``apps.crm.services`` comme toutes les écritures cross-app.

    Le canal réutilise ``Lead.Canal.AUTRE`` (aucun nouveau vocabulaire de
    canal n'est inventé) ; ``message`` porte le libellé lisible de
    l'événement (ex. « Campagne X envoyée »), stocké aussi dans
    ``PointContact.detail`` pour l'attribution.
    """
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=message)
    return PointContact.objects.create(
        company=lead.company, lead=lead, canal=Lead.Canal.AUTRE,
        source='marketing', date_contact=timezone.now(),
        ordre=ordre, detail=message, cout=cout)


# ── YLEAD10 — Fast-lane comportemental : FOLLOW_UP à l'ouverture du devis ────

def avancer_stage_sur_ouverture_devis(lead) -> bool:
    """YLEAD10 — Avance le lead à FOLLOW_UP (STAGES.py) quand le client ouvre
    sa proposition, comme les autres avances de funnel automatiques
    (``avancer_stage_pour_devis``) : ne recule jamais, ignore les leads
    perdus et ceux déjà ≥ FOLLOW_UP (donc un lead déjà SIGNED/COLD-au-delà
    ne bouge pas). Idempotent : une seconde ouverture ne réécrit rien de
    plus (le rang est déjà atteint). Renvoie True si l'avance a eu lieu.

    CAD139 (21/09/2026) — CONSERVÉE SANS APPELANT DE PRODUCTION. La RÈGLE
    FONDATEUR du 07/09/2026 a débranché cette avance automatique
    (``noter_devis_ouvert`` ne l'appelle plus : « le funnel ne bouge que sur
    une réponse confirmée de Meryem ») ; seuls ``tests_crx20_stage_events.py``
    et ``tests_ylead10_fastlane_open.py`` l'invoquent aujourd'hui. Gardée
    plutôt que supprimée (version préférée de l'audit L3, round 2) : c'est
    l'implémentation TESTÉE et idempotente du fast-lane comportemental que la
    décision du 07/09 a désactivé sans l'invalider — si le fondateur revient
    sur ce choix, le comportement et ses tests existent déjà, au lieu d'être
    re-dérivés de zéro. Ni code mort silencieux, ni suppression d'un choix
    documenté.
    """
    if lead is None or lead.perdu:
        return False
    cible = stages.FOLLOW_UP
    if _rang_funnel(lead.stage) >= _rang_funnel(cible):
        return False  # déjà à FOLLOW_UP ou plus avancé (jamais en arrière).

    ancien_stage = lead.stage
    # CRX20 — chemin canonique : écrit ET émet ``lead_stage_changed`` (ce
    # point d'entrée était muet, les playbooks/séquences ne partaient pas).
    appliquer_stage_lead(lead, cible, user=None)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[ancien_stage],
        new_value=stages.STAGE_LABELS[cible],
        body='auto — devis ouvert par le client',
    )
    return True


# ── QJ2 — Speed-to-lead : notifications vendeur avec lien wa.me ──────────────


def _build_lead_wa_reply_url(lead):
    """Construit un lien wa.me « répondre maintenant » vers le prospect du lead.

    Utilise le numéro WhatsApp du lead (sinon son téléphone). Renvoie l'URL
    ou None si aucun numéro n'est disponible. Best-effort — jamais d'exception.
    """
    try:
        import urllib.parse
        phone_raw = (
            getattr(lead, 'whatsapp', None)
            or getattr(lead, 'telephone', None)
            or ''
        )
        # ACRM39 — normaliseur sanctionné (E.164) : un numéro français reste
        # 33…, « +212 (0)6… » perd son zéro ; non normalisable ⇒ pas de lien
        # (jamais un numéro inventé).
        from apps.ventes.utils.phone import normalize_phone_e164
        digits = normalize_phone_e164(phone_raw)
        if not digits:
            return None
        nom = (
            (getattr(lead, 'nom', '') or '').strip()
            or 'votre client'
        )
        # Message pré-rempli court — le vendeur personnalise avant d'envoyer.
        text = urllib.parse.quote(f'Bonjour {nom}, je vous contacte suite à votre demande.')
        return f'https://wa.me/{digits}?text={text}'
    except Exception:
        return None


def notify_new_lead(lead, *, sous_seuil=False) -> None:
    """QJ2 (a) — Notifie le responsable du lead à la CRÉATION d'un nouveau lead.

    Événement de speed-to-lead : le owner du lead est notifié dès l'arrivée du
    lead (webhook site web ou création manuelle). La notification porte un lien
    wa.me « répondre maintenant » vers le prospect. Best-effort : jamais
    d'exception propagée — un échec de notification ne doit pas casser le flux
    de création.

    Multi-tenant : le owner est résolu depuis le lead (server-side, jamais du
    corps de requête). QJ27 : le supérieur du owner (``supervisor``) est aussi
    notifié — repli sur les managers société (« Commercial responsable » /
    « Directeur ») quand le owner ou son supérieur manque. Aucun destinataire
    résolvable → no-op.

    ``sous_seuil`` (18/08/2026 — le site transmet désormais les leads sous le
    seuil de facture, `qualified: false`) : le lead est notifié comme les
    autres — jamais silencieux, il est bien arrivé — mais le titre et le corps
    portent la mention « (sous le seuil) », pour que le commercial arbitre en
    VOYANT la notification et non après avoir décroché. Le défaut ``False``
    laisse tous les autres appelants (création manuelle, imports) inchangés.

    T-TRACE (25/08/2026) — DEUX ajouts, tous deux additifs :
      · la DIRECTION est systématiquement ajoutée aux destinataires
        (« always add the director in the notifications ») ;
      · quand l'appareil du demandeur a un historique de visites RÉEL, le
        corps le dit (« A visité le site N fois avant sa demande … ») — c'est
        exactement ce que le fondateur a demandé de voir. Sans historique,
        la phrase est simplement absente : jamais « 0 visite ».
    """
    try:
        recipients = avec_direction(
            lead_notification_recipients(lead),
            getattr(lead, 'company', None))
        # CIQ416 (D-CIQ-20) — un lead PRO se dit pro dès le titre, et son
        # responsable désigné est ajouté aux destinataires.
        segment = getattr(lead, 'type_installation', None)
        pro = segment in (Lead.TypeInstallation.COMMERCIAL,
                          Lead.TypeInstallation.INDUSTRIEL)
        if pro:
            recipients = _avec_responsable_pro(recipients, lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Nouveau prospect'
        wa_url = _build_lead_wa_reply_url(lead)
        suffixe = ' (sous le seuil)' if sous_seuil else ''
        body_parts = [f'Un nouveau lead vient d\'arriver : {nom}{suffixe}.']
        if pro:
            body_parts.extend(lignes_notification_pro(lead))
        if sous_seuil:
            body_parts.append(
                'Facture déclarée sous le seuil de 1 000 MAD — à traiter '
                'en second, après les leads au-dessus du seuil.')
        historique = resume_historique_fr(
            historique_appareil(getattr(lead, 'company', None),
                                getattr(lead, 'appareil_id', '')),
            avant_demande=True)
        if historique:
            body_parts.append(historique)
        # L-DESSIN (fondateur 25/08/2026 : « when the client draws his roof i
        # still do not receive the drawing ») — la notification d'arrivée DIT
        # désormais qu'un tracé accompagne la demande. Sans contour, la phrase
        # est simplement absente : jamais « 0 point », jamais un tracé annoncé
        # qui n'existe pas.
        contour = getattr(lead, 'roof_outline', None)
        if isinstance(contour, list) and len(contour) >= 3:
            body_parts.append(
                f'Le client a DESSINÉ le contour de son toit '
                f'({len(contour)} points) — visible sur la fiche, '
                'section « Toiture & site ».')
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        titre = (f'Nouveau lead PRO ({segment}) : {nom}{suffixe}' if pro
                 else f'Nouveau lead : {nom}{suffixe}')
        notify_many(
            recipients,
            'lead_new',
            titre,
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ2: notify_new_lead échoué pour lead #%s : %s',
            getattr(lead, 'pk', '?'), exc)


def _avec_responsable_pro(recipients, lead):
    """CIQ416 — ajoute le responsable des leads pro aux destinataires (sans
    doublon). Best-effort : un profil absent ne change rien."""
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.objects.filter(
        company_id=getattr(lead, 'company_id', None)).first()
    responsable = responsable_leads_pro(
        profile, {'type_installation': lead.type_installation})
    liste = list(recipients or [])
    if responsable is not None and responsable.pk not in {
            getattr(u, 'pk', None) for u in liste}:
        liste.append(responsable)
    return liste


def _montant_fr(valeur):
    from decimal import Decimal
    nombre = Decimal(str(valeur))
    if nombre == nombre.to_integral_value():
        return f'{int(nombre):,}'.replace(',', ' ')
    return f'{nombre:,.2f}'.replace(',', ' ').replace('.', ',')


def lignes_notification_pro(lead):
    """CIQ416 — le corps d'un lead PRO : catégorie, facture ou kWh DÉCLARÉS
    (jamais une estimation) et tension si elle est déclarée. Une donnée
    absente n'écrit aucune ligne."""
    lignes = []
    categorie = getattr(lead, 'categorie_commerciale', None)
    if categorie:
        libelle = dict(Lead.CategorieCommerciale.choices).get(
            categorie, categorie)
        lignes.append(f'Activité : {libelle}.')
    elif getattr(lead, 'secteur_industriel', None):
        lignes.append(f'Activité : {lead.secteur_industriel}.')
    tranche = getattr(lead, 'facture_tranche_declaree', None)
    kwh = (getattr(lead, 'conso_mensuelle_kwh', None)
           or getattr(lead, 'bill_kwh', None))
    if getattr(lead, 'facture_hiver', None):
        lignes.append('Facture déclarée : '
                      f'{_montant_fr(lead.facture_hiver)} MAD/mois.')
    elif isinstance(tranche, dict) and tranche.get('libelle'):
        lignes.append(f'Facture déclarée : « {tranche["libelle"]} ».')
    if kwh:
        lignes.append(f'Consommation déclarée : {_montant_fr(kwh)} kWh/mois.')
    tension = getattr(lead, 'tension_raccordement', None)
    if (tension in ('bt', 'mt')
            and getattr(lead, 'tension_source', None)
            != 'site_defaut_visible'):
        lignes.append('Raccordement : ' + (
            'moyenne tension (MT).' if tension == 'mt'
            else 'basse tension (BT).'))
    return lignes


def notify_devis_opened(devis_reference: str, lead, *, ip='',
                        appareil_id='', reprise=False) -> None:
    """QJ2 (b) — Notifie le responsable du lead à l'ouverture du devis.

    QJ1bis (fondateur 07/09/2026) — ``reprise=True`` : ce n'est plus la
    première ouverture mais un RETOUR du client sur sa proposition ; même
    notification, formulée « a rouvert » — le fondateur veut être prévenu à
    CHAQUE visite, pas seulement la première.

    Complémente noter_devis_ouvert (QJ1) : en plus de la note chatter, envoie
    une notification in-app + Web Push au owner du lead, avec un lien wa.me
    « répondre maintenant » vers le prospect. QJ27 : le supérieur du owner est
    aussi notifié (repli managers société quand owner/supervisor manque).
    Best-effort — jamais d'exception propagée.

    T-TRACE (25/08/2026) — ``ip`` et ``appareil_id`` sont FACULTATIFS (les
    appelants qui ne les connaissent pas restent inchangés) et lus CÔTÉ
    SERVEUR par l'appelant, jamais d'un corps de requête. Quand ils sont
    fournis, le corps dit d'OÙ vient l'ouverture et si l'appareil était DÉJÀ
    connu — le premier indice qu'un « client » qui ouvre est en fait un
    visiteur déjà vu ailleurs. La DIRECTION est toujours destinataire.

    QJEQUIPE3 (16/09/2026) — le lien pointe l'écran VISITEURS filtré sur ce
    lead (``/crm/visiteurs?lead=<pk>``), c'est-à-dire l'historique de ses
    accès : quand/depuis quoi/combien de temps il a lu, et le bouton pour
    marquer l'appareil « équipe » si l'ouverture vient en fait de nous. La
    liste des leads ne montrait rien de tout cela — et comme la cloche
    regroupe les notifications par ``link`` (VX208), « devis ouvert » s'y
    fondait dans « nouveau lead », qui porte le même lien.
    """
    try:
        company = getattr(lead, 'company', None)
        recipients = avec_direction(
            lead_notification_recipients(lead), company)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Votre client'
        wa_url = _build_lead_wa_reply_url(lead)
        verbe = 'a rouvert' if reprise else "vient d'ouvrir"
        body_parts = [f'{nom} {verbe} le devis {devis_reference}.']
        if ip:
            body_parts.append(f'Ouverture depuis l’adresse IP {ip}.')
        if appareil_id:
            # « Connu » = cet appareil a DÉJÀ laissé une trace avant cette
            # ouverture-ci (l'ouverture elle-même est déjà enregistrée quand
            # on arrive ici : un appareil vu pour la 1re fois n'a donc qu'UNE
            # seule visite).
            historique = historique_appareil(company, appareil_id)
            visites = (historique or {}).get('visites') or 0
            if visites > 1:
                body_parts.append('Appareil DÉJÀ connu de nos surfaces.')
                resume = resume_historique_fr(historique)
                if resume:
                    body_parts.append(resume)
            else:
                body_parts.append('Appareil jamais vu auparavant.')
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            'devis_opened',
            (f'Devis {devis_reference} rouvert par le client' if reprise
             else f'Devis {devis_reference} ouvert par le client'),
            body='\n'.join(body_parts),
            link=f'/crm/visiteurs?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ2: notify_devis_opened échoué pour lead #%s devis %s : %s',
            getattr(lead, 'pk', '?'), devis_reference, exc)


# ── CAD-K ── CAD135 — les signaux de lecture remontent au LEAD ──────────────
#
# Audit L3 du 21/09/2026. Quand un client revient plusieurs fois sur la même
# section (le prix, l'étude), le système écrit lui-même « signal de friction,
# un appel peut débloquer la décision » — dans l'historique du DEVIS, sans
# aucune notification. Même sort pour « a commencé à lire en détail ».
# Personne ne les lit, sauf à ouvrir cet onglet par hasard.
#
# Ces deux signaux empruntent désormais le MÊME chemin que « devis ouvert » :
# une ligne dans le chatter du LEAD et une notification au responsable, avec
# le lien pour appeler. La note côté DEVIS reste écrite — elle appartient à
# l'historique du document, ce point d'entrée ne la remplace pas.
#
# NUANCE ASSUMÉE (round 2) : « le signal le plus prédictif » reste une
# HYPOTHÈSE tant que CAD87 ne l'a pas mesuré. Rien ici ne classe, ne priorise
# ni ne réordonne quoi que ce soit : on rend un fait visible, c'est tout.

def noter_version_remplacee_ouverte(devis_reference: str, lead, *,
                                    remplacee_par: str = '') -> bool:
    """ACRM11 (C-ACRM-006, volet signaux) — le client a ouvert le lien d'une
    version REMPLACÉE par une révision : UNE note système au chatter du lead
    (« ancienne version <V1> (remplacée par <V2>) ouverte »), et RIEN
    d'autre — ni touche « Proposition rouverte — appeler », ni report de la
    prochaine touche, ni recalcul de score, ni notification : la relance
    porte sur la version en vigueur. Idempotente (une seule note par
    version remplacée, quel que soit le nombre d'ouvertures). Renvoie
    ``True`` si la note vient d'être écrite. Best-effort côté appelant."""
    if lead is None or getattr(lead, 'company_id', None) is None:
        return False
    corps = f'Ancienne version {devis_reference}'
    if remplacee_par:
        corps += f' (remplacée par {remplacee_par})'
    corps += ' ouverte par le client — la relance porte sur la version en ' \
             'vigueur.'
    if LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE, body=corps).exists():
        return False
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=corps)
    return True


def notifier_signal_lecture(devis_reference: str, lead, *, friction_section='',
                            resume='', remplacee_par=None) -> None:
    """CAD135 — « il relit le prix » / « il lit en détail » arrivent au lead.

    ``friction_section`` non vide ⇒ signal de FRICTION (relecture répétée
    d'une section, le libellé FR est fourni par l'appelant) ; sinon ⇒ lecture
    APPROFONDIE. ``resume`` est le détail déjà composé côté document, repris
    tel quel — ce module n'invente aucun chiffre de temps passé.

    Écrit une note SYSTÈME (``user=None`` : ne fait jamais avancer le funnel,
    règle du 07/09/2026) puis notifie par le chemin commun. Best-effort
    intégral : un signal de lecture ne fait jamais retomber une requête
    publique.

    ACRM11 — ``remplacee_par`` (non ``None``) : le signal vient d'une version
    REMPLACÉE ; seule la note « ancienne version » est écrite
    (``noter_version_remplacee_ouverte``), aucune notification.
    """
    if remplacee_par is not None:
        try:
            noter_version_remplacee_ouverte(
                devis_reference, lead, remplacee_par=remplacee_par)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'ACRM11 : note de version remplacée non écrite (lead #%s)',
                getattr(lead, 'pk', None), exc_info=True)
        return
    try:
        if lead is None or getattr(lead, 'company_id', None) is None:
            return
        if friction_section:
            corps = (f'Le client relit la section « {friction_section} » de '
                     f'la proposition {devis_reference} — un appel peut '
                     'débloquer la décision.')
            titre = f'Devis {devis_reference} — le client relit une section'
        else:
            corps = ('Le client a commencé à lire la proposition '
                     f'{devis_reference} en détail.')
            titre = f'Devis {devis_reference} — lecture en détail'
        if resume:
            corps += f' ({resume})'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=corps)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD135 : note de signal de lecture non écrite (lead #%s)',
            getattr(lead, 'pk', None), exc_info=True)
        return
    try:
        company = getattr(lead, 'company', None)
        recipients = avec_direction(
            lead_notification_recipients(lead), company)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        corps_notif = [corps]
        wa_url = _build_lead_wa_reply_url(lead)
        if wa_url:
            corps_notif.append(f'Appeler / répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            # Aucun type d'événement neuf : le signal emprunte le MÊME chemin
            # que « devis ouvert », dont il est la suite directe.
            'devis_opened',
            titre,
            body='\n'.join(corps_notif),
            link=f'/crm/visiteurs?lead={lead.pk}',
            company=company,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD135 : notification de signal de lecture échouée (lead #%s)',
            getattr(lead, 'pk', None), exc_info=True)


# ── CAD-K ── CAD136 — le client vient d'agir, et personne n'était prévenu ───
#
# Audit L3 du 21/09/2026. Répondre à une section du questionnaire enrichissait
# le lead, recalculait le score et écrivait une note — sans AUCUNE
# notification ; la photo de facture envoyée depuis le site était attachée
# (avec OCR si la clé est active) sans prévenir personne. Le client vient
# pourtant de passer cinq minutes sur NOTRE formulaire : c'est la meilleure
# fenêtre de la semaine.
#
# CE QUE CE POINT D'ENTRÉE FAIT, ET NE FAIT PAS. Il NOTIFIE, et rien d'autre.
# Les deux GESTES que ces signaux appellent sont posés par leurs appelants,
# chacun par sa mécanique : la touche « Questionnaire complété — appeler »
# par celle de CAD130 (``poser_touche_signal``, plus bas), et la photo de
# facture, qui appelle une tâche de PRODUCTION (« préparer le devis ») et non
# une relance (nuance du round 2), par ``poser_etape_preparer_devis``.

#: Les deux natures de signal, et le geste qu'elles appellent. Le libellé dit
#: au responsable ce qu'il a à faire — jamais un « il s'est passé quelque
#: chose » qu'il faut aller décoder.
SIGNAL_QUESTIONNAIRE = 'questionnaire'
SIGNAL_PHOTO_FACTURE = 'photo_facture'

_SIGNAUX_CLIENT = {
    SIGNAL_QUESTIONNAIRE: (
        'a répondu au questionnaire',
        'Le client vient de remplir NOTRE formulaire : c\'est la meilleure '
        'fenêtre de la semaine pour l\'appeler.'),
    SIGNAL_PHOTO_FACTURE: (
        'a envoyé une photo de sa facture',
        'Tout est là pour PRÉPARER LE DEVIS — ce n\'est pas une relance, '
        'c\'est de la production.'),
}


def notifier_signal_client(lead, signal, *, detail='') -> None:
    """CAD136 — prévient le responsable qu'un client vient d'AGIR.

    ``signal`` ∈ ``SIGNAL_QUESTIONNAIRE`` / ``SIGNAL_PHOTO_FACTURE``. Un
    signal inconnu ne notifie RIEN plutôt qu'un message vide. ``detail``
    précise (la section répondue, par exemple) sans jamais rien inventer.

    Best-effort intégral : ni une réponse de questionnaire ni une photo ne
    peuvent retomber parce que la cloche est en panne.
    """
    libelle = _SIGNAUX_CLIENT.get(signal)
    if libelle is None or lead is None or getattr(
            lead, 'company_id', None) is None:
        return
    quoi, conseil = libelle
    try:
        company = getattr(lead, 'company', None)
        recipients = avec_direction(
            lead_notification_recipients(lead), company)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Le client'
        corps = [f'{nom} {quoi}.']
        if detail:
            corps.append(detail)
        corps.append(conseil)
        wa_url = _build_lead_wa_reply_url(lead)
        if wa_url:
            corps.append(f'Appeler / répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            # Aucun type d'événement neuf : c'est le même canal que les
            # autres signaux venus du client.
            'devis_opened',
            f'{nom} {quoi}',
            body='\n'.join(corps),
            link=f'/crm/leads/{lead.pk}',
            company=company,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD136 : notification de signal client échouée (lead #%s, %s)',
            getattr(lead, 'pk', None), signal, exc_info=True)


# ── CAD-K ── CAD130 — un signal du client fait BOUGER la cadence ────────────
#
# Audit L3 du 21/09/2026. Le client rouvre sa proposition trois fois dans la
# soirée : une note, une notification — et la file de Meryem ne bouge pas d'un
# millimètre. L'avance d'étape sur ouverture a été débranchée à juste titre
# (règle fondateur du 07/09 : le FUNNEL ne bouge que sur une réponse
# confirmée), mais rien n'avait pris sa place côté RAPPEL.
#
# DÉCISION DE CONCEPTION (round 2) — ``reporter_prochaine_touche`` DÉCALE une
# touche existante, il n'en fabrique pas une. Un signal, lui, doit PRODUIRE
# une touche visible, nommée par ce qui s'est passé (« Proposition rouverte —
# appeler »). Elle est donc CRÉÉE — une, jamais deux — et elle REMPLACE la
# prochaine touche du plan : si celle-ci tomberait avant elle ou le même
# jour, elle glisse derrière (avec toute sa suite et son ancre, par la
# mécanique existante — décaler, jamais redémarrer, jamais un second plan).
#
# LES CINQ GARDES, toutes vérifiables :
#   1. la touche signal remplace la prochaine touche du plan en la décalant ;
#   2. jamais plus d'un appel et d'un message par jour et par lead (CAD20) ;
#   3. jamais hors fenêtre (``horaires.prochain_creneau_appel``) ;
#   4. jamais sur un lead « ne plus contacter », perdu, archivé ou signé ;
#   5. un délai minimal depuis la dernière touche faite
#      (``cadence_temps.SIGNAL_ECART_MIN``).

#: La nature du signal qui a posé la touche. `SIGNAL_QUESTIONNAIRE` (CAD136)
#: est déclaré plus haut : même vocabulaire que la notification.
SIGNAL_PROPOSITION_ROUVERTE = 'proposition_rouverte'

#: Le libellé de la touche que chaque signal pose. Il dit le GESTE (« appeler »)
#: et sa raison — c'est ce que la file affiche. Sert aussi de clé
#: d'idempotence : une touche signal encore ouverte n'est jamais doublée.
TOUCHES_SIGNAL = {
    SIGNAL_PROPOSITION_ROUVERTE: 'Proposition rouverte — appeler',
    SIGNAL_QUESTIONNAIRE: 'Questionnaire complété — appeler',
}

#: Les touches signal vivent dans la cadence hors protocole déjà utilisée par
#: le dépôt (même choix que le rappel demandé de CAD129) : elles ne sont pas
#: un barreau, et aucune matérialisation réactive ne leur fait naître de suite.
SIGNAL_CADENCE = 'generique'

#: Ce que le moteur a fait, en une phrase, pour le chatter — et pourquoi une
#: touche n'a PAS été posée (lead hors cadence), pour les journaux.
_SIGNAL_RAISONS = {
    SIGNAL_PROPOSITION_ROUVERTE: 'le client a rouvert sa proposition à '
                                 'plusieurs reprises',
    SIGNAL_QUESTIONNAIRE: 'le client vient de répondre au questionnaire',
}


def _libelles_touche_signal():
    """Les touches qui COUVRENT déjà un signal : les touches signal elles-mêmes
    et le rappel que le client a demandé (CAD129) — un client qui attend
    notre appel n'a pas besoin d'une seconde touche pour le même appel."""
    return tuple(TOUCHES_SIGNAL.values()) + (RAPPEL_DEMANDE_LIBELLE,)


def refus_touche_signal(lead):
    """CAD130 — la raison (FR) pour laquelle AUCUNE touche signal ne se pose
    sur ce lead, ou ``''``. Garde 4 : ne plus contacter, perdu, archivé,
    signé — dans cet ordre, la première qui s'applique."""
    if lead is None or getattr(lead, 'company_id', None) is None:
        return 'lead sans société'
    if getattr(lead, 'ne_plus_contacter', False):
        return 'le client a demandé à ne plus être contacté'
    if getattr(lead, 'perdu', False):
        return 'lead perdu'
    if getattr(lead, 'is_archived', False):
        return 'lead archivé'
    if getattr(lead, 'stage', None) == stages.SIGNED:
        return 'lead signé'
    return ''


def _prochaine_touche_du_plan(lead, exclure_libelles):
    """La prochaine touche À FAIRE du PLAN — un barreau de protocole, pas une
    étape posée à la main par le moteur (filet, visite, rappel, signal) :
    celles-là ont leur propre date, décidée pour une autre raison."""
    from django.db.models import F

    return (lead.relance_etapes
            .filter(statut=RelanceEtape.Statut.A_FAIRE)
            .exclude(q_etape_moteur())
            .exclude(libelle__in=tuple(exclure_libelles))
            .order_by(F('due_at').asc(nulls_last=True), 'due_date', 'ordre')
            .first())


def _genre_du_canal(canal):
    """CAD20 — les deux seuls genres que la règle distingue : un MESSAGE
    (WhatsApp / e-mail, ``horaires.est_un_message`` fait autorité) ou un
    APPEL (tout le reste, visite comprise — le plus prudent)."""
    from . import horaires

    return 'message' if horaires.est_un_message(canal) else 'appel'


def _jour_occupe_pour(lead, genre, exclure_pk=None):
    """CAD20 — ``jour_occupe(date_locale)`` pour ce lead et ce GENRE (appel /
    message) : une touche du même genre déjà FAITE ce jour-là, ou encore À
    FAIRE à ce jour-là (la touche du plan qui va glisser exceptée)."""
    from . import horaires

    def _meme_genre(canal):
        return _genre_du_canal(canal) == genre

    def jour_occupe(jour):
        debut = datetime.datetime.combine(
            jour, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
        fin = debut + datetime.timedelta(days=1)
        a_faire = (lead.relance_etapes
                   .filter(statut=RelanceEtape.Statut.A_FAIRE, due_date=jour))
        faites = (lead.relance_etapes
                  .filter(statut=RelanceEtape.Statut.FAIT,
                          traite_le__gte=debut, traite_le__lt=fin))
        if exclure_pk is not None:
            a_faire = a_faire.exclude(pk=exclure_pk)
        canaux = (list(a_faire.values_list('canal', flat=True))
                  + list(faites.values_list('canal', flat=True)))
        return any(_meme_genre(c) for c in canaux)

    return jour_occupe


def poser_touche_signal(lead, signal, *, user=None, maintenant=None):
    """CAD130 — un SIGNAL du client pose UNE touche « …, appeler » dans la file.

    ``signal`` ∈ ``TOUCHES_SIGNAL`` (proposition rouverte, questionnaire
    complété). Renvoie la touche signal (créée, ou déjà ouverte), ou ``None``
    quand le signal ne pose rien (signal inconnu, garde 4).

    IDEMPOTENTE : une touche signal — ou un rappel demandé par le client —
    encore ouverte couvre déjà le signal ; trois ouvertures de la proposition
    ne font jamais trois touches, ni trois décalages du plan.

    Best-effort intégral : un signal ne fait jamais retomber la requête ou la
    tâche planifiée qui l'observe."""
    from . import cadence_temps, horaires

    libelle = TOUCHES_SIGNAL.get(signal)
    if libelle is None:
        return None
    if getattr(lead, 'pk', None):
        # L'instance de l'appelant peut être périmée (même précaution que
        # `assurer_prochaine_etape_apres_succes`) : la garde 4 lit l'état réel.
        try:
            lead.refresh_from_db(fields=['stage', 'perdu', 'is_archived',
                                         'ne_plus_contacter',
                                         'contact_preference'])
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning('CAD130 : lead #%s illisible', lead.pk,
                           exc_info=True)
            return None
    if refus_touche_signal(lead):
        return None
    try:
        # 1. Idempotence : le signal est déjà couvert par une touche ouverte.
        deja = (lead.relance_etapes
                .filter(libelle__in=_libelles_touche_signal(),
                        statut=RelanceEtape.Statut.A_FAIRE)
                .order_by('due_date', 'pk').first())
        if deja is not None:
            return deja

        # 2. Le canal : un appel — sauf pour un client « WhatsApp uniquement »
        #    (CAD32 : sa préférence gagne toujours, on lui écrit).
        canal = RelanceEtape.Canal.APPEL
        if (getattr(lead, 'contact_preference', '')
                == cadence_temps.PREFERENCE_WHATSAPP_ONLY):
            canal = RelanceEtape.Canal.WHATSAPP
        genre = _genre_du_canal(canal)

        # 3. Les dates, par la règle PURE (cadence_temps.echeances_signal).
        instant = maintenant or timezone.now()
        derniere = (lead.relance_etapes
                    .filter(statut=RelanceEtape.Statut.FAIT,
                            traite_le__isnull=False)
                    .order_by('-traite_le').values_list('traite_le',
                                                        flat=True).first())
        plan = _prochaine_touche_du_plan(lead, _libelles_touche_signal())
        echeance, glisse_a = cadence_temps.echeances_signal(
            maintenant=instant, derniere_faite=derniere,
            prochaine=getattr(plan, 'due_at', None),
            jour_occupe=_jour_occupe_pour(
                lead, genre, exclure_pk=getattr(plan, 'pk', None)),
            creneau=lambda dt: horaires.prochain_creneau_appel(
                dt, lead.company, canal=canal),
            lendemain=lambda dt: cadence_temps.lendemain_joignable(
                dt, lead.company, canal))

        # 4. La touche du plan glisse DERRIÈRE la touche signal, avec toute sa
        #    suite et son ancre (mécanique existante, jamais une seconde).
        deplacee = None
        if plan is not None and glisse_a is not None:
            # Les gestes du RENDEZ-VOUS de visite (confirmer la veille,
            # débriefer le lendemain) partagent la cadence du plan mais sont
            # ancrés sur la DATE DE VISITE : le glissement de la suite du plan
            # ne doit jamais les emporter. Ils sont remis à leur date.
            # COCKPIT-CONTRÔLE — un glissement décidé par le MOTEUR : aucun
            # report compté (``compter_report=False``), et les gestes de
            # visite retrouvent AUSSI leur échéance d'origine.
            visites = list(lead.relance_etapes
                           .filter(q_visite(),
                                   statut=RelanceEtape.Statut.A_FAIRE)
                           .values_list('pk', 'due_at', 'due_date',
                                        'due_initial_at'))
            deplacee = reporter_prochaine_touche(
                lead, user, glisse_a, etape=plan, journaliser=False,
                compter_report=False)
            for pk, due_at, due_date, due_initial_at in visites:
                RelanceEtape.objects.filter(pk=pk).update(
                    due_at=due_at, due_date=due_date,
                    due_initial_at=due_initial_at)

        # 5. LA touche signal.
        etape = RelanceEtape.objects.create(
            company=lead.company, lead=lead, cadence=SIGNAL_CADENCE, ordre=0,
            canal=canal, libelle=libelle,
            due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            note=f'Posée automatiquement : {_SIGNAL_RAISONS[signal]}.')
        _recaler_file(lead, user)

        # 6. UNE note système (``user=None`` : poser une touche n'est pas un
        #    contact, garde QJ7) qui dit ce que le moteur a fait.
        quand = echeance.astimezone(horaires.CASABLANCA)
        corps = (f'Signal client — {_SIGNAL_RAISONS[signal]} : touche « '
                 f'{libelle} » posée pour le {quand:%d/%m/%Y à %H:%M}.')
        if deplacee is not None:
            apres = deplacee.due_at.astimezone(horaires.CASABLANCA)
            nom = (deplacee.libelle or '').strip() \
                or deplacee.get_canal_display()
            corps += (f' La touche du plan « {nom} » glisse au '
                      f'{apres:%d/%m/%Y à %H:%M}, avec sa suite (décaler, '
                      'jamais redémarrer).')
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=corps)
        return etape
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD130 : touche signal non posée (lead #%s, %s)',
            getattr(lead, 'pk', None), signal, exc_info=True)
        return None


def poser_etape_preparer_devis(lead, *, origine, user=None, jours=None,
                               journaliser=True):
    """CAD136 — une pièce qui permet de CHIFFRER (la photo de la facture) pose
    la tâche de PRODUCTION « Préparer et envoyer le devis (ou fixer un
    rappel) » — jamais une relance (nuance du round 2) : tout est là pour
    faire le devis, c'est ce geste-là qu'il faut dans la file.

    Même étape, même délai que le filet « client joint » et que la pièce reçue
    sur WhatsApp (CAD101) : DEMAIN, au prochain créneau d'appel. Une étape
    « préparer le devis » déjà ouverte n'est ni doublée ni DÉPLACÉE (elle a
    peut-être été datée à la main). Garde 4 de CAD130 : rien sur un lead ne
    plus contacter, perdu, archivé ou signé. Best-effort : ne lève jamais.
    Renvoie l'étape (posée ou déjà ouverte), ou ``None``.

    Retour de visite SANS devis (décision fondateur du 24/09/2026) — deux
    réglages, et rien d'autre :

    * ``jours`` : le délai quand le terrain a convenu d'un moment DEVANT le
      client (« cette semaine » = trois jours, ``_plan_du_debrief``) ; par
      défaut (``None``), celui du barreau ``devis`` de la société
      (Paramètres, PARAM-CADENCE — demain par défaut) ;
    * ``journaliser=False`` : l'appelant écrit lui-même la suite dans SA note
      (la note du retour terrain), jamais une seconde ligne de chatter."""
    from . import horaires

    if getattr(lead, 'pk', None) is None or refus_touche_signal(lead):
        return None
    try:
        ouverte = (lead.relance_etapes
                   .filter(q_etape(CLE_DEVIS),
                           statut=RelanceEtape.Statut.A_FAIRE)
                   .order_by('due_date', 'pk').first())
        if ouverte is not None:
            return ouverte
        etape = _poser_etape_de_filet(
            lead, cle=CLE_DEVIS, jours=jours, note=f'Posée : {origine}.')
        _recaler_file(lead, user)
        if not journaliser:
            return etape
        quand = etape.due_at.astimezone(horaires.CASABLANCA)
        # Note SYSTÈME (``user=None``) : poser une tâche n'est pas un contact.
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(f'{origine[:1].upper()}{origine[1:]} : étape « '
                  f'{etape.libelle} » posée pour le '
                  f'{quand:%d/%m/%Y à %H:%M} — tâche de production, pas une '
                  'relance.'))
        return etape
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD136 : étape « préparer le devis » non posée (lead #%s)',
            getattr(lead, 'pk', None), exc_info=True)
        return None


def poser_touche_signal_du_lead_id(lead_id, signal, *, company):
    """CAD130 — variante par ID pour les autres apps (``ventes`` ne tient que
    ``devis.lead_id`` et n'importe jamais les modèles du CRM). La société est
    TOUJOURS celle de l'appelant (le devis), jamais déduite du lead seul.
    Ne lève jamais."""
    if not lead_id or company is None:
        return None
    try:
        lead = Lead.objects.filter(pk=lead_id, company=company).first()
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('CAD130 : lead #%s illisible', lead_id, exc_info=True)
        return None
    if lead is None:
        return None
    return poser_touche_signal(lead, signal)


#: QW5 — libellés FR par canal de contact proposition (WJ85/WJ54 — le site
#: envoie 'rappel'/'whatsapp'/'question'/'voice'/'revision', un vocabulaire
#: plus large que ce que ce module connaissait (whatsapp/rappel seuls).
_CONTACT_CANAL_LABELS = {
    'whatsapp': 'par WhatsApp',
    'rappel': 'par téléphone (rappel)',
    'question': 'question avant signature',
    'voice': 'orienté vers une note vocale WhatsApp',
    'revision': 'demande de modification',
}

#: QW5 — libellés FR par type de modification demandée (WJ54, uniquement
#: pertinent quand canal == 'revision').
_REVISION_KIND_LABELS = {
    'kwc': 'ajuster la puissance (kWc)',
    'batterie': 'changer l’option batterie',
    'autre': 'autre modification',
}


def notify_client_contact_request(devis_reference: str, lead,
                                  canal='', message='', revision_kind='') -> None:
    """QJ27/QW5 — Le CLIENT demande à être contacté (proposition publique).

    Consigne la demande dans le chatter du lead (note SYSTÈME, user=None — ne
    fait donc jamais avancer le funnel QJ7) ET notifie le responsable du lead
    ET son supérieur (repli managers société quand l'un des deux manque), avec
    un lien wa.me « répondre maintenant ». Best-effort — jamais d'exception
    propagée. La société vient TOUJOURS du lead (jamais d'un corps de requête).

    QW5 — ``revision_kind`` (WJ54, uniquement quand ``canal == 'revision'``)
    est journalisé dans le chatter et le corps de notification. Le canal
    ``rappel`` sur une demande CLIENT (proposition) est une obligation de
    RAPPEL — même sémantique que QW4 (``contact_preference=phone_ok``) : si le
    lead lié n'a pas encore cette préférence posée, on la pose ici aussi et on
    déclenche la même notification distincte + SLA rappel (jamais dupliquée —
    ``notify_lead_callback_requested`` est déjà idempotent par lead)."""
    try:
        canal_key = (canal or '').strip()
        canal_label = _CONTACT_CANAL_LABELS.get(canal_key, '')
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Le client'
        # Note chatter (toujours, même sans destinataire notifiable).
        note = f'Le client demande à être contacté ({devis_reference})'
        if canal_label:
            note += f' — {canal_label}'
        if canal_key == 'revision' and revision_kind:
            note += f' [{_REVISION_KIND_LABELS.get(revision_kind, revision_kind)}]'
        if message:
            note += f' : « {message[:2000]} »'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=note)

        # ACRM63 (D-ACRM-5 (3)=(a)) — la personne « ne plus contacter » qui
        # demande ELLE-MÊME un rappel lève son opposition (note datée +
        # registre), AVANT de poser la touche.
        if canal_key == 'rappel':
            _lever_opposition_a_la_demande_du_client(lead)

        # QW5/QW4 — un rappel demandé DEPUIS LA PROPOSITION est la même
        # obligation qu'un rappel demandé à la capture : pose la préférence si
        # absente et route vers la notification distincte + SLA rappel.
        if canal_key == 'rappel' and getattr(lead, 'contact_preference', None) != Lead.ContactPreference.PHONE_OK:
            lead.contact_preference = Lead.ContactPreference.PHONE_OK
            # QX15 — même horodatage dédié que le webhook : le SLA rappel
            # mesure depuis la POSE de la préférence, pas depuis la création
            # du lead (un vieux lead qui demande un rappel MAINTENANT ne doit
            # pas être instantanément « SLA rompu »).
            lead.contact_preference_set_at = timezone.now()
            lead.save(update_fields=[
                'contact_preference', 'contact_preference_set_at'])
        if canal_key == 'rappel':
            notify_lead_callback_requested(lead)
            # CAD129 — la demande entre dans la FILE, pas seulement dans la
            # cloche : une notification noyée faisait disparaître la demande
            # la plus forte qu'un prospect puisse faire.
            poser_touche_rappel_demande(lead, user=None)

        recipients = lead_notification_recipients(lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        wa_url = _build_lead_wa_reply_url(lead)
        body_parts = [
            f'{nom} demande à être contacté au sujet du devis '
            f'{devis_reference}'
            + (f' ({canal_label})' if canal_label else '') + '.']
        if canal_key == 'revision' and revision_kind:
            body_parts.append(
                f'Type de modification : {_REVISION_KIND_LABELS.get(revision_kind, revision_kind)}')
        if message:
            body_parts.append(f'Message : « {message[:2000]} »')
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            'client_contact_request',
            f'Le client demande à être contacté — {devis_reference}',
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ27: notify_client_contact_request échoué pour lead #%s '
            'devis %s : %s', getattr(lead, 'pk', '?'), devis_reference, exc)


#: ACRM63 — source de registre et libellé de chatter d'une opposition levée
#: PAR la personne elle-même (demande de rappel depuis sa proposition).
CONSENT_SOURCE_OPPOSITION_LEVEE_CLIENT = (
    'opposition levée à la demande du client (rappel demandé)')
NOTE_OPPOSITION_LEVEE_CLIENT = 'opposition levée à la demande du client'


def _lever_opposition_a_la_demande_du_client(lead) -> bool:
    """ACRM63 — D-ACRM-5 (3)=(a) : un lead ``ne_plus_contacter`` dont la
    personne demande elle-même un rappel passe à ``False``, avec une note de
    chatter datée « opposition levée à la demande du client » et les lignes
    ``ConsentRecord`` accordées (réutilise ``tracer_levee_opposition_registre``
    via ``_ecrire_registre_contact`` — aucune seconde écriture du registre).
    Un lead non opposé : rien. Renvoie ``True`` si l'opposition a été levée."""
    if lead is None or not getattr(lead, 'ne_plus_contacter', False):
        return False
    maintenant = timezone.now()
    lead.ne_plus_contacter = False
    lead.save(update_fields=['ne_plus_contacter'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=(f'{NOTE_OPPOSITION_LEVEE_CLIENT} '
              f'({timezone.localtime(maintenant):%d/%m/%Y %H:%M})'))
    _ecrire_registre_contact(
        lead, granted=True, source=CONSENT_SOURCE_OPPOSITION_LEVEE_CLIENT,
        occurred_at=maintenant)
    return True


#: QW4 — marqueur de note système : posé UNE FOIS par lead pour éviter de
#: notifier plusieurs fois la même demande de rappel (idempotence, même
#: patron que ``ESCALATION_MARKER`` de ``recycler_leads_non_travailles``).
CALLBACK_REQUESTED_MARKER = 'auto — rappel demandé (contact_preference=phone_ok)'


def notify_lead_callback_requested(lead) -> None:
    """QW4 — Notification DISTINCTE, urgence plus élevée, quand un lead arrive
    avec ``contact_preference=phone_ok`` (« rappel demandé »), différente du
    générique ``notify_new_lead`` (réponse WhatsApp). Notifie owner + supérieur
    (repli managers société). Idempotent par lead — jamais renotifié deux fois
    pour la même demande (marqueur chatter). Best-effort — jamais d'exception
    propagée."""
    try:
        if getattr(lead, 'contact_preference', None) != Lead.ContactPreference.PHONE_OK:
            return
        already = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith=CALLBACK_REQUESTED_MARKER,
        ).exists()
        if already:
            return
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=f'{CALLBACK_REQUESTED_MARKER}.',
        )
        recipients = lead_notification_recipients(lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Un prospect'
        body_parts = [f'{nom} a demandé un RAPPEL téléphonique (pas une réponse WhatsApp).']
        tel = (getattr(lead, 'telephone', '') or '').strip()
        if tel:
            body_parts.append(f'Numéro à rappeler : {tel}')
        notify_many(
            recipients,
            'lead_callback_requested',
            f'☎ Rappeler {nom} — rappel demandé',
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QW4: notify_lead_callback_requested échoué pour lead #%s : %s',
            getattr(lead, 'pk', '?'), exc)


PARRAINAGE_SIGNUP_MARKER = 'auto — filleul détecté (utm_source=parrainage)'
PARRAINAGE_IGNORED_MARKER = '2e code de parrainage ignoré'
PARRAINAGE_DEJA_ENREGISTRE_MARKER = (
    'Parrainage déjà enregistré pour ce filleul')


def _format_date_fr(valeur):
    """Date FR courte (JJ/MM/AAAA) pour une note chatter, en heure locale.
    Tolérant : toute valeur non datable est rendue telle quelle (une note ne
    casse jamais le flux qui l'écrit)."""
    try:
        return timezone.localtime(valeur).strftime('%d/%m/%Y')
    except Exception:  # noqa: BLE001 — jamais bloquant pour une note
        return str(valeur)


def handle_parrainage_signup(lead) -> None:
    """QX35 — Wire la promesse de la page /parrainage : un lead capté avec
    ``utm_source=parrainage`` crée automatiquement un ``Parrainage`` en
    attente, rattaché au CLIENT parrain identifié par son code (porté par
    ``utm_campaign`` — voir ``apps/web/src/pages/parrainage.astro``, le lien
    personnel est `?utm_source=parrainage&utm_campaign=<code>`).

    Idempotent PAR FILLEUL (18/08/2026 — décision fondateur). Depuis que
    chaque soumission du site CRÉE un nouveau ``Lead`` (règle fondateur du
    18/08/2026), le même filleul qui re-soumet /parrainage obtient une fiche
    DIFFÉRENTE à chaque fois — la seule garde ``Parrainage.objects.filter(
    filleul_lead=lead)`` (idempotente PAR LEAD, conservée ci-dessous pour le
    replay du MÊME lead) ne voit donc plus ces reprises et laissait créer un
    2e ``Parrainage en_attente`` pour la même personne. Le filleul est donc
    aussi identifié par TÉLÉPHONE/E-MAIL normalisés parmi tous les
    ``Parrainage`` déjà posés pour la société :
      - même filleul, MÊME parrain → aucun 2e ``Parrainage``, mais une note
        chatter sobre sur le NOUVEAU lead (jamais une sortie silencieuse :
        une recommandation qui ne laisse aucune trace est une
        recommandation perdue) ;
      - même filleul, parrain DIFFÉRENT → cas ambigu : on GARDE le premier
        parrainage (jamais réattribué) et on pose une note chatter sur le
        NOUVEAU lead expliquant que son code a été ignoré.

    no-op (comportement inchangé) si ``utm_source`` n'est pas
    ``'parrainage'``, si le code de parrain est absent/inconnu, ou en cas
    d'auto-parrainage (le filleul est déjà le même téléphone/email que le
    parrain — anti-abus minimal). Notifie les managers de la société (repli
    ``_company_fallback_managers``, pas de owner dédié à ce stade).
    Best-effort — jamais d'exception propagée."""
    try:
        if (getattr(lead, 'utm_source', None) or '').strip().lower() != 'parrainage':
            return
        from .models import Parrainage

        if Parrainage.objects.filter(filleul_lead=lead).exists():
            return  # déjà traité (idempotent — visiteur revenant, replay).

        code = (getattr(lead, 'utm_campaign', None) or '').strip()
        if not code:
            return
        parrain = Client.objects.filter(
            company=lead.company, code_parrainage=code).first()
        if parrain is None:
            return  # code inconnu/périmé — jamais bloquant, jamais d'erreur.

        # Anti auto-parrainage minimal : même téléphone/email normalisé que
        # le parrain → on ne crée rien (le parrain ne peut pas se parrainer
        # lui-même, ni un dossier déjà connu sous une autre forme — promesse
        # affichée sur /parrainage).
        lead_phone = normalize_phone(getattr(lead, 'telephone', None))
        lead_email = normalize_email(getattr(lead, 'email', None))
        parrain_phone = normalize_phone(getattr(parrain, 'telephone', None))
        parrain_email = normalize_email(getattr(parrain, 'email', None))
        if ((lead_phone and lead_phone == parrain_phone)
                or (lead_email and lead_email == parrain_email)):
            return

        # Idempotence PAR FILLEUL (voir docstring) : cherche un Parrainage
        # déjà posé pour la société dont le filleul_lead partage le téléphone
        # OU l'e-mail normalisé du lead courant — le PREMIER (plus ancien)
        # fait foi.
        existing_signup = None
        if lead_phone or lead_email:
            from django.db.models import Q
            contact_q = Q()
            if lead_phone:
                contact_q |= Q(filleul_lead__phone_normalise=lead_phone)
            if lead_email:
                contact_q |= Q(filleul_lead__email_normalise=lead_email)
            existing_signup = (
                Parrainage.objects
                .filter(company=lead.company)
                .exclude(filleul_lead__isnull=True)
                .filter(contact_q)
                .order_by('date_creation')
                .first()
            )
        if existing_signup is not None:
            if existing_signup.parrain_id == parrain.pk:
                # Même filleul, MÊME parrain : rien à recréer — mais plus de
                # sortie SILENCIEUSE. Deux salariés d'un même client (adresse
                # `contact@societe.ma` partagée) ou un foyer au même mobile
                # tombent ici : sans trace, la 2e recommandation disparaissait
                # du CRM sans que personne ne puisse savoir qu'elle a existé.
                # Une note sobre sur le NOUVEAU lead, jamais un 2e Parrainage.
                LeadActivity.objects.create(
                    company=lead.company, lead=lead, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'{PARRAINAGE_DEJA_ENREGISTRE_MARKER} (parrain '
                          f'{parrain.nom}, '
                          f'{_format_date_fr(existing_signup.date_creation)}) '
                          '— pas de doublon créé.'),
                )
                return
            # Parrain DIFFÉRENT sur re-soumission : cas ambigu — on GARDE le
            # premier parrainage (jamais réattribué), on note l'ignoré.
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body=(f'{PARRAINAGE_IGNORED_MARKER} (déjà parrainé par '
                      f'{existing_signup.parrain.nom}).'),
            )
            return

        Parrainage.objects.create(
            company=lead.company, parrain=parrain,
            filleul_lead=lead, filleul_nom=lead.nom or '',
            statut=Parrainage.Statut.EN_ATTENTE,
        )
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=f'{PARRAINAGE_SIGNUP_MARKER} — parrain : {parrain.nom}.',
        )

        managers = _company_fallback_managers(lead.company)
        if managers:
            from apps.notifications.services import notify_many
            nom = (lead.nom or '').strip() or 'Un prospect'
            notify_many(
                managers,
                'lead_new',
                f'🤝 Parrainage : {parrain.nom} recommande {nom}',
                body=(f'{nom} est arrivé via le lien de parrainage de '
                      f'{parrain.nom} (code {code}).'),
                link=f'/crm/parrainage?parrain={parrain.pk}',
                company=lead.company,
            )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QX35: handle_parrainage_signup échoué pour lead #%s : %s',
            getattr(lead, 'pk', '?'), exc)


# ─────────────────────────────────────────────────────────────────────────────
# Actions EN MASSE sur les leads (T3) — multi-sélection liste/kanban.
#
# Toute la logique métier vit ici (les vues restent fines) : règles du funnel
# (jamais en arrière, jamais un lead Perdu, réactivation du Froid), journal
# Historique par lead marqué « en masse », et garde-fous (devis liés bloquent la
# suppression). Tout est borné à la société de l'utilisateur appelant.
# ─────────────────────────────────────────────────────────────────────────────

COLD = 'COLD'  # état de PARKING (pas une régression) — cf. _rang_funnel.


def _bulk_stage_allowed(current, target):
    """Le funnel n'avance jamais EN ARRIÈRE en masse.

    - même étape → non (rien à faire) ;
    - Froid → n'importe quelle étape active → oui (réactivation) ;
    - vers Froid → oui (mise au parking, autorisée depuis n'importe où) ;
    - sinon → uniquement vers une étape PLUS avancée.

    INCHANGÉ par l'ordre fondateur 2026-08-01 (« les leads doivent pouvoir
    revenir en arrière d'étape, avec une confirmation avant ») : LE BULK RESTE
    EN AVANT SEULEMENT. Cette fonction reste la définition PURE de « ce qui
    avance », et elle demeure l'unique source du garde funnel — le
    ``LeadSerializer`` continue de l'appeler telle quelle pour un PATCH
    unitaire, puis décide seul d'accepter un recul quand l'utilisatrice l'a
    confirmé (champ write-only ``confirme_recul``). Une confirmation vise UN
    lead nommé, avec ses deux étapes affichées ; il n'existe aucune boîte de
    dialogue capable de faire assumer sincèrement le recul de 200 leads d'un
    coup — l'action de masse ne gagne donc pas d'échappatoire.
    """
    if current == target:
        return False
    if current == COLD or target == COLD:
        return True
    return _rang_funnel(target) > _rang_funnel(current)


def _resolve_owner(company, owner_id):
    """Responsable cible (société courante uniquement) ou None si vidé."""
    if owner_id in (None, '', 'null'):
        return None
    from authentication.models import CustomUser
    return CustomUser.objects.filter(id=owner_id, company=company).first()


def _corps_whatsapp_en_masse(lead, tpl, corps_direct=''):
    """ACRM15 — le texte d'un message de la file WhatsApp en masse, rendu
    avec la discipline de ``message_pour_etape`` (MRY13) :

    * la LANGUE préférée du lead (``langue_relance_du_lead``) : un gabarit de
      même nom dans cette langue est préféré au gabarit choisi ;
    * ``{lien_rdv}`` résolu seulement s'il est présent ;
    * une phrase dont un placeholder n'a PAS de valeur réelle (``{lien}`` —
      aucun devis ici —, ``{lien_rdv}`` non généré, ``{prenom}``/``{ville}``
      vides) est OMISE — jamais « Réservez votre visite : » suivi de rien."""
    from apps.ventes.utils.whatsapp import render_message_template

    from .models import MessageTemplate

    corps = corps_direct or ''
    if tpl is not None:
        langue = langue_relance_du_lead(lead)
        if tpl.langue != langue:
            traduit = (MessageTemplate.objects
                       .filter(company=lead.company, nom=tpl.nom,
                               langue=langue, archived=False)
                       .first())
            if traduit is not None:
                tpl = traduit
        corps = tpl.corps or ''
    contexte = {
        'prenom': (lead.prenom or lead.nom or '').strip(),
        'ville': (lead.ville or '').strip(),
        'lien': '',
    }
    if '{lien_rdv}' in corps:
        contexte['lien_rdv'] = (
            resoudre_lien_rdv('{lien_rdv}', lead) or '')
    manquants = [cle for cle, valeur in contexte.items()
                 if '{' + cle + '}' in corps and not str(valeur).strip()]
    return render_message_template(
        _omettre_phrases_incompletes(corps, manquants), contexte)


# ── QJ20 — Site-visit appointment service ────────────────────────────────────


# ── XKB33 — WhatsApp entrant → chatter du lead/client ────────────────────────

def find_lead_by_phone(company, telephone):
    """Lead de `company` dont téléphone OU whatsapp correspond (normalisé).

    Point d'entrée cross-app sanctionné pour `apps.notifications` (webhook BSP
    WhatsApp) : matching par numéro SANS jamais exposer les modèles crm.
    Renvoie le lead le plus RÉCEMMENT créé en cas de doublon, ou None."""
    key = normalize_phone(telephone)
    if not key:
        return None
    candidates = [
        lead for lead in Lead.objects.filter(company=company)
        .order_by('-date_creation')
        if normalize_phone(lead.telephone) == key
        or normalize_phone(lead.whatsapp) == key
    ]
    return candidates[0] if candidates else None


def find_lead_by_email(company, email):
    """NTAPI15 — Lead de `company` dont l'email correspond (insensible à la
    casse). Point d'entrée cross-app sanctionné pour `apps.publicapi` (dédup
    upsert de l'import bulk) — jamais d'import direct de `Lead` ailleurs.
    Renvoie le lead le plus RÉCEMMENT créé en cas de doublon, ou None."""
    # ACRM38 (jumeau) — la même clé que l'identité client.
    email = _email_identite(email)
    if not email:
        return None
    return (
        Lead.objects.filter(company=company, email__iexact=email)
        .order_by('-date_creation')
        .first()
    )


# ── ZSAV8 — Convertir un ticket SAV en opportunité CRM ──────────────────────
# apps.sav ne peut PAS importer apps.crm.models directement (règle de
# modularité CLAUDE.md) : cette fonction est son unique porte d'entrée pour
# créer un lead depuis un ticket (upsell/remplacement).

def create_lead_depuis_ticket(*, company, user, client, contexte=''):
    """ZSAV8 — Crée (ou réutilise) un lead CRM depuis un ticket SAV.

    Réutilise un lead OUVERT (stage != COLD, non archivé) déjà lié à ce
    ``client`` plutôt que d'en créer un doublon. Sinon, crée un nouveau lead
    au stade ``NEW`` (STAGES.py, jamais codé en dur), pré-rempli avec
    l'identité du client + ``contexte`` en description.

    La note de ``contexte`` est attribuée au SYSTÈME (``user=None``) et non à
    l'utilisateur appelant : le récepteur QJ7
    (``_avancer_stage_on_contact_activity``) ne fait avancer NEW -> CONTACTED
    que sur un premier contact MANUEL (``instance.user is not None``), donc une
    note système laisse le lead au stade ``NEW`` attendu par ZSAV8 tout en
    conservant la trace « Créé depuis le ticket SAV … » sur le chatter du lead.

    Renvoie ``(lead, created)``."""
    # ACRM43 — la docstring dit « non archivé » : un lead archivé n'est
    # jamais réutilisé (nouveau lead à la place).
    existant = (
        Lead.objects
        .filter(company=company, client=client, is_archived=False)
        .exclude(stage=stages.COLD)
        .order_by('-date_creation')
        .first())
    if existant is not None:
        contexte_existant = (contexte or '').strip()
        if contexte_existant:
            # ACRM43 — le contexte du ticket est tracé au chatter du lead
            # réutilisé (note SYSTÈME, même règle QJ7 que la création).
            activity.log_note(existant, None, contexte_existant)
        return existant, False

    lead = Lead.objects.create(
        company=company,
        nom=f'{client.nom} {client.prenom or ""}'.strip() or client.nom,
        prenom=client.prenom or None,
        email=client.email or None,
        telephone=client.telephone or None,
        client=client,
        canal=Lead.Canal.AUTRE,
        stage=stages.NEW,
    )
    activity.log_creation(lead, user)
    contexte = (contexte or '').strip()
    if contexte:
        # Note SYSTÈME (user=None) : garde le lead au stade NEW (le récepteur
        # QJ7 ignore les activités système), tout en traçant l'origine.
        activity.log_note(lead, None, contexte)
    return lead, True


# ── XMKT4 — écriture de consentement marketing pour un lead ────────────────
# Point d'entrée UNIQUE pour poser un ``core.ConsentRecord`` depuis un lead
# (jamais d'écriture directe de compta/parametres dans core.ConsentRecord au
# nom d'un lead — cette fonction reste la porte d'entrée crm).


# ── XMKT19 — Actions CRM exécutables depuis une étape de séquence ──────────
# Point d'entrée UNIQUE pour qu'une ``EtapeSequence`` (module marketing de
# compta) exécute une action CRM au lieu d'un message — jamais d'import
# direct du modèle crm depuis compta ; chaque fonction journalise le chatter
# (``LeadActivity``) via ``activity``, jamais silencieuse.

def avancer_stage_lead_vers(lead, user, stage_cible):
    """XMKT19 — avance ``lead`` vers ``stage_cible`` (clé canonique
    STAGES.py, jamais hardcodée par l'appelant). Refuse un recul (même règle
    que le bulk edit, ``_bulk_stage_allowed``). Renvoie True si appliqué.
    """
    if not _bulk_stage_allowed(lead.stage, stage_cible):
        return False
    ancien = lead.stage
    lead.stage = stage_cible
    lead.save(update_fields=['stage'])
    activity.log_bulk_change(lead, user, 'stage', ancien, stage_cible)
    _emit_stage_changed(lead, ancien, stage_cible, user)
    return True


def assigner_lead_a(lead, user, owner_id):
    """XMKT19 — assigne (ou vide) le propriétaire du lead."""
    nouveau = _resolve_owner(lead.company, owner_id)
    ancien = lead.owner
    lead.owner = nouveau
    lead.save(update_fields=['owner'])
    activity.log_bulk_change(
        lead, user,
        'owner',
        getattr(ancien, 'username', '') if ancien else '',
        getattr(nouveau, 'username', '') if nouveau else '')
    return lead


def poser_tag_lead(lead, user, tag):
    """XMKT19 — ajoute (idempotent) un tag au lead."""
    tag = (tag or '').strip()
    if not tag:
        return lead
    current = [t.strip() for t in (lead.tags or '').split(',') if t.strip()]
    if tag in current:
        return lead
    old = lead.tags or ''
    current.append(tag)
    lead.tags = ', '.join(current)[:500]
    lead.save(update_fields=['tags'])
    activity.log_bulk_change(lead, user, 'tags', old, lead.tags)
    return lead


def retirer_tag_lead(lead, user, tag):
    """XMKT19 — retire (idempotent) un tag du lead."""
    tag = (tag or '').strip()
    if not tag:
        return lead
    current = [t.strip() for t in (lead.tags or '').split(',') if t.strip()]
    if tag not in current:
        return lead
    old = lead.tags or ''
    current.remove(tag)
    lead.tags = ', '.join(current)[:500]
    lead.save(update_fields=['tags'])
    activity.log_bulk_change(lead, user, 'tags', old, lead.tags)
    return lead


def ajuster_score_lead(lead, user, delta):
    """XMKT19 — ajuste le score du lead de ``delta`` (peut être négatif),
    borné à [0, 100]."""
    ancien = lead.score or 0
    nouveau = max(0, min(100, ancien + int(delta)))
    lead.score = nouveau
    lead.save(update_fields=['score'])
    activity.log_bulk_change(lead, user, 'score', ancien, nouveau)
    return lead


def creer_relance_lead(lead, user, *, relance_date, note=''):
    """XMKT19 — crée/pose une relance/tâche (FG31) sur le lead."""
    lead.relance_date = relance_date
    lead.save(update_fields=['relance_date'])
    body = f'Relance planifiée le {relance_date}'
    if note:
        body += f' — {note}'
    activity.log_note(lead, user, body)
    return lead


# ── XMKT28 — Lead depuis une inscription à un événement marketing ──────────

def create_lead_from_evenement_marketing(
        *, company, nom, telephone='', email='', evenement_nom='') -> Lead:
    """XMKT28 — Crée (ou dédupe sur) un lead dès qu'un inscrit à un
    ``EvenementMarketing`` (module marketing de compta) est capturé. Même
    pattern que ``create_lead_from_livechat`` (XMKT37) : dédup par
    téléphone/email dans la société avant de créer, canal ``AUTRE``, stage
    NEW (défaut du champ).
    """
    nom = (nom or '').strip()[:255] or 'Prospect événement'
    telephone = (telephone or '').strip()[:20]
    email = (email or '').strip()[:254]

    lead = None
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)
        if dupes:
            lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    if lead is None:
        extra = {}
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default
        lead = Lead.objects.create(
            company=company,
            nom=nom,
            telephone=telephone or None,
            email=email or None,
            canal=Lead.Canal.AUTRE,
            **extra,
        )
        activity.log_creation(lead, None)
        # MRY6 — un inscrit d'événement marketing est une demande réelle.
        demarrer_cadence_contact(lead, origine='evenement_marketing')
    else:
        changed = False
        if telephone and not lead.telephone:
            lead.telephone = telephone
            changed = True
        if email and not lead.email:
            lead.email = email
            changed = True
        if changed:
            lead.save()

    if evenement_nom:
        activity.log_note(
            lead, None, f'Inscrit à l\'événement « {evenement_nom} »')
    recompute_lead_score(lead)
    return lead


# ── XPLT5 — API publique en ÉCRITURE (leads:write / activities:write) ───────
# Point d'entrée cross-app sanctionné (services.py) pour `apps.publicapi` :
# la société vient TOUJOURS de l'appelant (résolue depuis la clé API, jamais
# du corps), jamais acceptée en argument depuis les données utilisateur.

PUBLIC_LEAD_WRITABLE_FIELDS = (
    'nom', 'prenom', 'societe', 'email', 'telephone', 'ville',
    'canal', 'priorite', 'type_installation', 'stage',
)


def create_lead_from_public_api(*, company, fields):
    """XPLT5 — crée un lead depuis l'API publique en écriture.

    ``fields`` est filtré à la liste blanche ``PUBLIC_LEAD_WRITABLE_FIELDS``
    (un champ non listé est silencieusement ignoré — jamais 500). ``stage``,
    s'il est fourni, doit être une clé canonique STAGES.py valide (sinon
    ``ValueError`` — jamais de nouvelle liste d'étapes, jamais hardcodée) ;
    absent, le lead prend le défaut du modèle (NEW). ``nom`` est obligatoire.
    Company forcée serveur, jamais du body. Journalise la création
    (``LeadActivity``, acteur système) comme tout autre point d'entrée."""
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS and v not in (None, '')}
    nom = (clean.pop('nom', '') or '').strip()
    if not nom:
        raise ValueError("Le champ « nom » est obligatoire.")
    stage = clean.pop('stage', None)
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    lead = Lead.objects.create(
        company=company, nom=nom,
        stage=stage or stages.NEW,
        **clean,
    )
    activity.log_creation(lead, None)
    # MRY6 — l'API publique crée de VRAIES demandes (formulaire partenaire,
    # intégration) : elles entrent dans la cadence comme les autres.
    demarrer_cadence_contact(lead, origine='api_publique')
    return lead


#: CRX21 — colonnes DÉRIVÉES recalculées par ``Lead.save()`` (QW10). Sans
#: elles dans ``update_fields``, un changement de téléphone/email n'est PAS
#: répercuté sur les colonnes indexées de dédup : le lead reste trouvable par
#: son ANCIEN numéro et invisible sous le nouveau. Même table que
#: ``LeadViewSet.COLONNES_DERIVEES`` (views.py) — la parité est le sujet de la
#: tâche : l'API publique écrit les mêmes leads que l'écran.
PUBLIC_LEAD_COLONNES_DERIVEES = {'telephone': 'phone_normalise',
                                 'email': 'email_normalise'}


def update_lead_from_public_api(*, company, lead_id, fields):
    """XPLT5 — met à jour un lead EXISTANT DE CETTE SOCIÉTÉ depuis l'API
    publique en écriture. Lève ``Lead.DoesNotExist`` si le lead n'appartient
    pas (ou plus) à ``company`` — jamais de fuite cross-tenant. Champs
    filtrés à la même liste blanche que la création ; ``stage`` validé contre
    STAGES.py. Journalise chaque champ changé (chatter, acteur système).

    CRX21 — PARITÉ avec le PATCH de l'écran (``LeadViewSet.perform_update``),
    qui manquait entièrement à ce chemin :

    * **verrou du lead perdu** — un lead marqué perdu ne change pas d'étape,
      pas même par une intégration (le ``LeadSerializer`` refuse déjà, et ce
      verrou PRÉCÈDE toute échappatoire) ;
    * **garde funnel** ``_bulk_stage_allowed`` — une intégration ne recule ni
      ne rouvre un pipeline. Il n'y a PAS ici l'échappatoire ``confirme_recul``
      de l'écran : elle suppose une confirmation HUMAINE devant un lead nommé,
      qu'aucun appel machine ne peut donner ;
    * **les 4 effets internes** de ``perform_update`` : émission de
      ``lead_stage_changed``, ``first_contacted_at`` (FG28), recalcul du score
      (QJ6) et synchronisation de l'activité de relance ;
    * **colonnes dérivées** (``phone_normalise``/``email_normalise``) ajoutées
      à ``update_fields`` quand leur source change — sinon la dédup indexée
      devient aveugle après un changement de téléphone (chemins publicapi bulk
      ET PATCH unitaire).

    Lève ``ValueError`` (traduit en 400 par les vues publiques) sur une étape
    inconnue, un lead perdu, ou un recul de funnel.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS}
    stage = clean.get('stage')
    # ACRM58 — ``stage`` présent mais vide (null comme '') : erreur SOUS LE
    # CHAMP (400 ``{stage: [...]}``), jamais un IntegrityError (500). Une
    # ValidationError DRF (pas un ValueError) pour que la vue publique la
    # rende telle quelle, champ nommé ; l'import en masse l'inscrit en ligne
    # en erreur.
    if 'stage' in clean and stage in (None, ''):
        raise DRFValidationError(
            {'stage': ["L'étape ne peut pas être vide."]})
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    if stage is not None and stage != lead.stage:
        if lead.perdu:
            raise ValueError('Lead perdu — étape non modifiable.')
        if not _bulk_stage_allowed(lead.stage, stage):
            raise ValueError("On ne recule pas une étape.")
    old = Lead.objects.get(pk=lead.pk)
    changed_fields = []
    for field, value in clean.items():
        if value in (None, '') and field != 'stage':
            continue
        if getattr(lead, field) != value:
            setattr(lead, field, value)
            changed_fields.append(field)
    if changed_fields:
        ecrits = list(changed_fields)
        for source, derivee in PUBLIC_LEAD_COLONNES_DERIVEES.items():
            if source in changed_fields:
                ecrits.append(derivee)
        lead.save(update_fields=ecrits)
        activity.log_changes(old, lead, None)
        # Les 4 effets du PATCH de l'écran, dans le même ordre. Tous sont
        # best-effort par construction (chacun catche pour son compte) : une
        # intégration ne doit jamais échouer sur un effet secondaire.
        sync_relance_activity(lead, None)
        maybe_set_first_contacted_at(old, lead)
        recompute_lead_score(lead)
        _emit_stage_changed(lead, old.stage, lead.stage, user=None)
    return lead


def create_activity_from_public_api(*, company, lead_id, body):
    """XPLT5 — ajoute une note (activité chatter) sur un lead DE CETTE
    SOCIÉTÉ depuis l'API publique en écriture. Lève ``Lead.DoesNotExist`` si
    hors société (jamais de fuite cross-tenant). ``body`` ne peut être vide."""
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    return activity.log_note(lead, None, body)


def ajouter_note_lead(*, company, lead_id, user, body):
    """NTMOB1 — ajoute une note (activité chatter) sur un lead DE CETTE
    SOCIÉTÉ, avec l'utilisateur ACTEUR (contrairement à
    ``create_activity_from_public_api``, qui journalise sans acteur).

    Point d'entrée cross-app pour rejouer une note posée hors-ligne sans
    importer ``apps.crm.models``/``views``. Lève ``Lead.DoesNotExist`` hors
    société (jamais de fuite cross-tenant) et ``ValueError`` sur un corps vide.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    return activity.log_note(lead, user, body)


def ajouter_note_lead_si_nouvelle(*, company, lead_id, user, body):
    """Comme :func:`ajouter_note_lead`, mais SANS RÉPÉTER un corps identique.

    Rend l'activité créée, ou ``None`` si le lead porte DÉJÀ une note au corps
    exactement identique.

    POURQUOI ELLE EXISTE (F6, 29/08/2026). L'auto-pipeline du tunnel doit
    laisser une trace quand le moteur REFUSE de chiffrer un lead — sans quoi le
    commercial constate seulement que « hier ces leads recevaient un devis ».
    Mais le refus RELÂCHE la marque de dédup (une donnée manquante aujourd'hui
    ne doit pas fermer le lead pour toujours) : chaque nouvelle livraison du
    webhook rejoue donc le même refus, et une note par rejeu ensevelirait
    l'historique du lead sous le même paragraphe. La note est donc posée une
    fois par MOTIF : le motif change ⇒ une nouvelle note ; le motif se répète
    ⇒ silence.

    La comparaison porte sur le CORPS et rien d'autre — c'est lui que le
    commercial lit, et c'est lui qui nomme le champ manquant.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    deja = LeadActivity.objects.filter(
        company=company, lead=lead, kind=LeadActivity.Kind.NOTE,
        body=body).exists()
    if deja:
        return None
    return activity.log_note(lead, user, body)


# CAD72 (21/09/2026) — le SECOND catalogue « parrainage » de YSERV11 a
# disparu d'ici. Un dictionnaire de textes par défaut + un générateur
# `get_or_create_*` vivaient ici, semant une SECONDE ligne
# `crm.MessageTemplate` au premier usage — texte FR promettant une
# récompense FERME, et texte darija TRANSCRIT EN ALPHABET LATIN (chiffres
# pour des lettres arabes — « 3 »/« 9 »), alors que le catalogue darija
# validé (`parametres.MESSAGE_TEMPLATE_DEFAULTS_DARIJA`) est écrit en
# arabe, relu par un natif le 04/09/2026. Leur seul appelant vivait dans
# `apps/compta/services.py` (flux NPS), retiré quand `compta` a été mis en
# coquille par le drain SOLMVP (`apps/compta/` n'a plus de `services.py`) —
# plus aucun appelant (grep sur tout le backend). Le catalogue UNIQUE pour
# les messages client est désormais `parametres.MessageTemplate` (clé
# `parrainage`, déjà validée dans `docs/crm/messages_meryem.md`, rendue par
# `message_pour_etape` comme n'importe quelle autre touche) — voir
# `tests_cad72_parrainage_catalogue_unique.py`.


# ─────────────────────────────────────────────────────────────────────────────
# QX42 — Rétention PII des copies brutes d'intake (registre YOPSB10, core.retention)
#
# `WebsiteLeadPayload` (PII brute + IP) et `ChatSessionPublique`
# s'accumulaient INDÉFINIMENT. ACRM19 — l'effacement d'un lead
# (`dsr_provider.anonymiser_lead`, DSR ET rétention) caviarde désormais LUI-MÊME
# ces copies brutes : les purges par âge ci-dessous ne sont plus le seul
# rempart, seulement le ménage de fond. Le framework générique existe (`core.retention`)
# mais son registre est VIDE — aucune app n'y enregistre de politique. Ceci
# enregistre la politique CRM (voir `CrmConfig.ready()`), fenêtre par défaut
# 180 jours, override founder via `WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS` /
# `CHAT_SESSION_RETENTION_DAYS` (settings/.env — même patron que les autres
# constantes founder-configurables de ce module, ex.
# `WEBSITE_LEAD_WEBHOOK_SECRET`). 0/négatif désactive la purge (conservation
# illimitée, comportement actuel inchangé).


# ─────────────────────────────────────────────────────────────────────────────
# YOPSB11 — Archivage par lots de `LeadActivity` (chatter à forte croissance)
#
# Le chatter (`LeadActivity`) est append-only et grossit sans borne, alourdissant
# le chemin chaud. `archiver_anciens(now, jours)` DÉPLACE les entrées plus
# vieilles que `jours` vers la table froide `LeadActivityArchive` (par lots de
# 5 000, un commit par lot — jamais de transaction géante) puis les supprime de
# la table vive. Fenêtre par défaut 0 = OFF (aucun archivage, comportement
# inchangé) ; réglage via `CRM_LEADACTIVITY_ARCHIVE_DAYS`. La politique est
# enregistrée dans le registre partagé YOPSB10 depuis `CrmConfig.ready()`.

DEFAULT_LEADACTIVITY_ARCHIVE_DAYS = 0


def _leadactivity_to_archive(row):
    """Mappe une `LeadActivity` vive vers les champs de `LeadActivityArchive`
    (FK dénormalisées en identifiants entiers — archive froide indépendante)."""
    return {
        'original_id': row.pk,
        'company_id': row.company_id,
        'lead_id': row.lead_id,
        'kind': row.kind,
        'field': row.field,
        'field_label': row.field_label,
        'old_value': row.old_value,
        'new_value': row.new_value,
        'body': row.body,
        'outcome': row.outcome,
        'attachment_id': row.attachment_id,
        'bulk': row.bulk,
        'user_id': row.user_id,
        'created_at': row.created_at,
    }


def archiver_anciens(now, jours, apply_=True):
    """YOPSB11 — archive les `LeadActivity` plus vieilles que `jours`.

    Déplacement par lots de 5 000 (un commit par lot) vers `LeadActivityArchive`
    puis suppression de la table vive. `jours <= 0` (défaut OFF) → 0, rien ne
    bouge. `apply_=False` (dry-run du registre) → compte sans déplacer. Renvoie
    le nombre d'entrées archivées."""
    from core.retention import archive_old_rows
    from .models import LeadActivity, LeadActivityArchive

    return archive_old_rows(
        LeadActivity, LeadActivityArchive, _leadactivity_to_archive,
        cutoff_field='created_at', now=now, jours=jours, apply_=apply_,
    )


class SuppressionLeadsRefusee(Exception):
    """``delete_leads_for_company`` appelée sur une société qui n'est PAS un
    bac à sable — la suppression est refusée AVANT toute écriture."""


def _est_societe_bac_a_sable(company):
    """True uniquement si ``company`` est la société-JUMELLE d'un
    ``publicapi.SandboxTenant`` (jamais la société réelle propriétaire).

    Lecture par le registre Django (``apps.get_model``) et non par un import
    statique : le domaine ``crm`` ne se couple pas au satellite ``publicapi``
    (aucune nouvelle arête d'import, aucun cycle de chargement — c'est
    ``publicapi`` qui appelle ``crm``, jamais l'inverse). La garde échoue
    FERMÉ : app absente, société inconnue ou ``None`` → False → refus.
    """
    if company is None:
        return False
    company_pk = getattr(company, 'pk', company)
    if company_pk is None:
        return False
    try:
        SandboxTenant = django_apps.get_model('publicapi', 'SandboxTenant')
        return SandboxTenant.objects.filter(
            sandbox_company_id=company_pk).exists()
    except (LookupError, TypeError, ValueError):
        # App absente, ou identifiant non convertible (slug, objet exotique) :
        # on ne PROUVE pas que c'est un bac à sable → refus.
        return False


def delete_leads_for_company(company):
    """NTAPI27 — supprime TOUS les leads de ``company``. Point d'entrée
    d'ÉCRITURE cross-app sanctionné pour ``apps.publicapi`` (reset du bac à
    sable API). Renvoie le nombre supprimé.

    DÉFENSE EN PROFONDEUR (garde posée ICI, pas seulement chez l'appelant) :
    c'est une suppression DURE — elle contourne la corbeille/soft-delete, il
    n'existe donc NI trace NI annulation. Le seul appelant légitime
    (``publicapi.services.reset_sandbox``) vise toujours
    ``tenant.sandbox_company``, mais un unique ``SandboxTenant`` mal pointé
    suffirait à détruire le pipeline commercial RÉEL sans recours. La fonction
    REFUSE donc de s'exécuter — bruyamment, avant la moindre écriture — tant
    que la société cible n'est pas prouvée société-jumelle d'un bac à sable.
    """
    from .models import Lead

    if not _est_societe_bac_a_sable(company):
        raise SuppressionLeadsRefusee(
            "Suppression de masse REFUSÉE : la société ciblée (%r) n'est pas "
            "un bac à sable — aucun SandboxTenant ne la désigne comme "
            "société-jumelle. `delete_leads_for_company` supprime "
            "DÉFINITIVEMENT tous les leads (suppression dure, sans corbeille "
            "ni annulation) et reste réservée au reset du bac à sable API."
            % (getattr(company, 'pk', company),))

    qs = Lead.objects.filter(company=company)
    count = qs.count()
    qs.delete()
    return count


# ── NTMIG28 — miroir du compteur de déploiements d'un partenaire ────────────

def poser_compteur_deploiements(partenaire_id, company, nb_reussis):
    """Pose le nombre de déploiements RÉUSSIS reconnus d'un partenaire.

    Point d'entrée d'ÉCRITURE pour ``apps.migration`` (qui possède la table des
    déploiements) : la fiche partenaire vit ici, donc c'est ici qu'on l'écrit —
    jamais un ``Partenaire.objects.update()`` depuis une autre app.

    Le compteur est un MIROIR dénormalisé, jamais la source : l'appelant fournit
    le total qu'il vient de recompter sur SA table, on ne le devine pas ici.
    Renvoie le partenaire mis à jour, ou ``None`` si l'id ne désigne aucun
    partenaire de cette société (jamais une écriture cross-tenant).
    """
    from .models import Partenaire

    partenaire = Partenaire.objects.filter(
        pk=partenaire_id, company=company).first()
    if partenaire is None:
        return None
    nb_reussis = max(0, int(nb_reussis or 0))
    if partenaire.nb_deploiements_reussis != nb_reussis:
        partenaire.nb_deploiements_reussis = nb_reussis
        partenaire.save(update_fields=['nb_deploiements_reussis'])
    return partenaire


# ── NTMIG31 — spécialité proposée par un parcours de formation partenaire ───

def ajouter_specialite_partenaire(partenaire_id, company, specialite):
    """Ajoute UNE spécialité à la fiche partenaire si elle n'y est pas déjà.

    Point d'entrée d'ÉCRITURE pour ``apps.migration`` (qui possède le parcours
    de certification NTMIG31) : la fiche partenaire vit ici, donc c'est ici
    qu'on l'écrit — jamais un ``Partenaire.objects.update()`` depuis une
    autre app. N'ajoute QUE si la clé appartient au référentiel FERMÉ
    (``Partenaire.SPECIALITES_CLES``) — une spécialité hors liste rendrait
    l'annuaire des certifiés (NTMIG29) infiltrable par une clé libre.
    L'action reste une PROPOSITION validée explicitement par un admin en
    amont (jamais un effet de bord automatique de fin de parcours) ; cette
    fonction ne fait qu'exécuter la validation déjà décidée. Idempotent :
    une spécialité déjà présente n'est jamais dupliquée. Renvoie le
    partenaire mis à jour, ou ``None`` si l'id ne désigne aucun partenaire de
    cette société (jamais une écriture cross-tenant).
    """
    from .models import Partenaire

    partenaire = Partenaire.objects.filter(
        pk=partenaire_id, company=company).first()
    if partenaire is None:
        return None
    if specialite not in Partenaire.SPECIALITES_CLES:
        return partenaire
    specialites = list(partenaire.specialites or [])
    if specialite not in specialites:
        specialites.append(specialite)
        partenaire.specialites = specialites
        partenaire.save(update_fields=['specialites'])
    return partenaire


# ── NTPRT28 — Deal registration : soumission d'un lead par un partenaire ────
#
# Point d'entrée d'ÉCRITURE pour ``apps.portail`` (le portail partenaire
# authentifié) : la fiche partenaire et ses soumissions vivent ici, donc c'est
# ici qu'on les écrit — jamais un ``SoumissionLeadPartenaire.objects.create()``
# depuis une autre app.

#: NTPRT28 — fenêtre pendant laquelle une re-soumission du MÊME prospect par le
#: MÊME partenaire est traitée comme un doublon (critère d'acceptation).
FENETRE_DOUBLON_SOUMISSION_JOURS = 30


def soumission_partenaire_deja_faite(company, partenaire_id, email_prospect,
                                     fenetre_jours=None,
                                     telephone_prospect=None):
    """NTPRT28 — soumission RÉCENTE du même prospect par le même partenaire.

    Renvoie la soumission existante, ou ``None``. La comparaison se fait sur
    l'email du prospect, normalisé (casse/espaces) quand il est fourni.

    ADOC145 (C-ADOC-057) — quand l'email est VIDE, la clé est le téléphone
    du prospect, normalisé par ``normalize_phone`` (la MÊME normalisation que
    la déduplication des leads CRM — jamais une seconde) : '0611111111' et
    '+212 611111111' sont le même prospect. Sans email NI téléphone
    exploitable, jamais de doublon — deux prospects anonymes distincts ne
    s'annulent pas, et deux téléphones différents restent deux soumissions.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import SoumissionLeadPartenaire

    email = (email_prospect or '').strip().lower()
    telephone = normalize_phone(telephone_prospect)
    if company is None or not partenaire_id or not (email or telephone):
        return None
    jours = (FENETRE_DOUBLON_SOUMISSION_JOURS if fenetre_jours is None
             else fenetre_jours)
    depuis = timezone.now() - timedelta(days=jours)
    recentes = (SoumissionLeadPartenaire.objects
                .filter(company=company, partenaire_id=partenaire_id,
                        date_soumission__gte=depuis)
                .order_by('-date_soumission'))
    if email:
        return recentes.filter(email_prospect__iexact=email).first()
    # Le téléphone est stocké tel que saisi : la normalisation se fait ici,
    # sur les seules soumissions récentes de CE partenaire (ensemble borné).
    for soumission in recentes.exclude(telephone_prospect=''):
        if normalize_phone(soumission.telephone_prospect) == telephone:
            return soumission
    return None


def soumettre_lead_partenaire(company, partenaire_id, donnees):
    """NTPRT28 — enregistre la soumission d'un prospect par un partenaire.

    Renvoie ``(soumission, doublon)`` :

    * ``(None, None)`` — le partenaire n'existe pas dans CETTE société (jamais
      d'écriture cross-tenant) ;
    * ``(None, existante)`` — une soumission du MÊME prospect par le MÊME
      partenaire date de moins de 30 jours : RIEN n'est créé, l'appelant
      signale « déjà soumis » (jamais de doublon silencieux) ;
    * ``(creee, None)`` — nominal.

    ``company`` et ``partenaire`` sont posés par le serveur ; seuls les champs
    de coordonnées du prospect sont lus de ``donnees``. Le statut naît
    ``SOUMIS`` : la qualification (et la création du lead réel, référencé par
    ``lead_id`` — la piste de traçabilité pour la commission) reste un acte
    INTERNE, jamais un effet de bord de la soumission.
    """
    from .models import Partenaire, SoumissionLeadPartenaire

    if company is None or not partenaire_id:
        return None, None
    partenaire = (Partenaire.objects
                  .filter(company=company, pk=partenaire_id).first())
    if partenaire is None:
        return None, None

    donnees = donnees or {}
    email = str(donnees.get('email_prospect') or '').strip()
    existante = soumission_partenaire_deja_faite(
        company, partenaire.id, email,
        telephone_prospect=donnees.get('telephone_prospect'))
    if existante is not None:
        return None, existante

    soumission = SoumissionLeadPartenaire.objects.create(
        company=company,
        partenaire=partenaire,
        nom_prospect=str(donnees.get('nom_prospect') or '').strip()[:200],
        telephone_prospect=str(
            donnees.get('telephone_prospect') or '').strip()[:30],
        email_prospect=email[:254],
        ville=str(donnees.get('ville') or '').strip()[:120],
        note=str(donnees.get('note') or '').strip()[:4000],
        statut=SoumissionLeadPartenaire.Statut.SOUMIS,
    )
    return soumission, None


# ---------------------------------------------------------------------------
# AUD518 — Effets de CRÉATION d'un lead importé (dataimport)
# ---------------------------------------------------------------------------


def finaliser_lead_importe(lead, *, user=None, lead_attrs=None):
    """AUD518 — applique à un lead IMPORTÉ les effets de création du chemin
    MANUEL, dont il était intégralement privé.

    ``apps.dataimport`` faisait ``Lead.objects.create(company=…, **f)`` et
    s'arrêtait là : pas d'``owner`` (donc un lead invisible de l'écran « mes
    leads »), aucune ``LeadActivity`` de création (aucune trace, et le sweep
    d'inactivité sans point de départ), ``score`` figé à 0 (donc jamais
    évalué MQL). Ce point d'entrée est le SEUL que ``dataimport`` appelle :
    la frontière cross-app est respectée (aucun import de ``crm.activity`` ni
    du modèle depuis l'app d'import).

    Trois effets, dans l'ordre du chemin manuel
    (``LeadViewSet.perform_create``) :

    1. OWNER — même règle exactement : un utilisateur à portée restreinte
       garde la propriété de ce qu'il crée, sinon le responsable par défaut
       de la société (territoires NTCRM1 puis repli round-robin XSAL11) est
       résolu depuis les attributs de la ligne. Un ``owner`` déjà posé par le
       fichier n'est JAMAIS écrasé.
    2. CHATTER — ``activity.log_creation`` (l'app d'import n'y touche pas
       elle-même).
    3. SCORE — ``recompute_lead_score``, qui évalue aussi le passage MQL
       (``maybe_assign_mql``). Déjà best-effort en interne.

    Renvoie le lead.
    """
    from . import activity

    if not lead.owner_id:
        proprietaire = None
        portee = getattr(user, 'record_scope', None)
        if user is not None and callable(portee) and portee() != 'all':
            proprietaire = user
        else:
            proprietaire = default_responsable_for(
                lead.company, lead_attrs=lead_attrs)
        if proprietaire is not None:
            lead.owner = proprietaire
            lead.save(update_fields=['owner'])

    activity.log_creation(lead, user)
    recompute_lead_score(lead)
    return lead


# ── MRY30 — PLACEMENT DES ANCIENS LEADS DANS LES CADENCES DU MOTEUR ──────────
#
# Le moteur de relances ne démarre que sur les leads qui ARRIVENT. Le
# portefeuille déjà présent — plusieurs centaines de dossiers, dont les 930
# leads du miroir Odoo — resterait donc sans aucune cadence, et le bénéfice
# n'arriverait qu'au fil des semaines. Décision fondateur du 06/09/2026 :
# « tous les anciens leads non Froid sont traités ; le moteur décide à quelle
# étape des six appels chacun se trouve ».
#
# Trois différences assumées avec la reprise MRY23
# (`demarrer_cadences_existantes`, qui reste en place et ne change pas) :
#
#   1. le MIROIR ODOO EST INCLUS. `_garde_cadence_contact` refuse
#      `source == ODOO_IMPORT_TEST` — garde juste pour un démarrage AUTOMATIQUE
#      à la création (elle empêche un import de 930 lignes d'inonder la file),
#      fausse pour un placement DEMANDÉ à la main sur ce même portefeuille.
#      C'est pourquoi ce service appelle `initialiser_plan_relance`
#      directement et JAMAIS `demarrer_cadence_contact` ;
#   2. il n'y a pas de fenêtre d'éligibilité qui laisse des leads de côté :
#      un dossier trop ancien pour être relancé n'est pas ignoré, il est mis
#      en DORMANCE explicite (Froid + étiquette + réveil étalé) ;
#   3. l'aperçu et l'application partagent LE MÊME CALCUL — sans partager
#      les écritures. L'aperçu était une exécution complète dans une
#      transaction annulée : fidèle, mais il matérialisait les touches des
#      277 candidats pour les jeter aussitôt, soit plus de 20 s pendant
#      lesquelles le navigateur abandonnait (deux 499 dans nginx le
#      07/09/2026, sur le clic « Aperçu » du Cockpit). Il est désormais un
#      CALCUL PUR : mêmes décisions, mêmes créneaux, mêmes dates — obtenus
#      par `calculer_echeances_cadence`, la fonction que l'application
#      utilise elle aussi pour créer les touches. Un dry-run qui recalcule
#      « à côté » finit toujours par annoncer autre chose que ce que --apply
#      fait ; partager la FONCTION donne la même garantie que partager
#      l'exécution, pour le prix d'un calcul ;
#   4. l'application se fait PAR LOTS de `limite` leads (défaut 40), l'écran
#      rappelant tant que `restants > 0`. Écrire 277 dossiers d'un trait
#      dépassait le délai du navigateur exactement comme l'aperçu.

#: Au-delà de ce silence, un dossier n'est plus « en cours » : lui envoyer la
#: touche J+1 d'une cadence positionnée serait un message hors sujet. Il part
#: en dormance (réveil), pas en relance.
PLACEMENT_FENETRE_JOURS = 14

#: Réveils démarrés par JOUR OUVRÉ. Lancer 200 réveils le même matin
#: saturerait la journée de Meryem et ferait partir 200 messages en rafale
#: depuis le même numéro — le meilleur moyen de se faire signaler comme spam.
PLACEMENT_REVEILS_PAR_JOUR = 8

#: Les huit créneaux du matin, 20 minutes d'écart (10 h 00 → 12 h 20). Chacun
#: passe ensuite par `horaires.prochain_creneau_appel` au canal `whatsapp`
#: (une cadence de réveil s'ouvre par un message) : un créneau hors fenêtre
#: est recalé, jamais gardé tel quel. La pause du vendredi ne le concerne pas
#: — elle ne vaut que pour les appels (07/09/2026).
PLACEMENT_CRENEAUX = tuple(
    datetime.time(10 + (rang * 20) // 60, (rang * 20) % 60)
    for rang in range(PLACEMENT_REVEILS_PAR_JOUR))

#: Délai (jours) de la PREMIÈRE touche de réveil, quand la société n'a pas
#: encore de gabarit `reveil` en base. Le créneau étalé est la date visée pour
#: cette première touche : `depart = créneau − ce délai`.
PLACEMENT_REVEIL_DELAI_JOURS = 30

#: MRY30 — l'étiquette du dormant JAMAIS CHIFFRÉ. Le pendant « Devis sans
#: suite » existe déjà (`_CLOTURE_TAGS['apres_devis']`) : on le RÉUTILISE
#: plutôt que d'écrire un second libellé qui divergerait.
_PLACEMENT_TAG_JAMAIS_CHIFFRE = 'Jamais chiffré'

#: MRY30 — pour un dormant « devis sans suite », les deux touches de réveil
#: DOIVENT parler d'une proposition reçue (A1 puis A3) : ces leads ont bien
#: reçu un devis — dans Odoo — même sans devis ERP, et
#: `_adapter_gabarits_reveil` (qui ne lit que les devis ERP) choisirait
#: sinon le message « jamais chiffré », faux pour eux.
_PLACEMENT_CLES_REVEIL_DEVIS = ('reveil_a1', 'reveil_a3')

#: MRY30 — marque de la note chatter. Elle NOMME la décision fondateur du
#: 06/09/2026 qui a créé ce placement ; ce n'est pas la date d'exécution (déjà
#: portée par l'horodatage de l'activité) — un texte fixe, donc lisible et
#: vérifiable à l'identique quel que soit le jour du passage.
PLACEMENT_MARQUEUR = 'moteur, 06/09/2026'

#: Les cinq décisions possibles, DANS L'ORDRE du contrat
#: `contract_samples/placement_anciens_leads.json` : (code, libellé, cadence).
PLACEMENT_DECISIONS = (
    ('contact_complete',
     "Contact — depuis la première touche (Message d'identité)", 'contact'),
    ('contact_positionne',
     "Contact — positionné selon l'ancienneté, touches passées sautées",
     'contact'),
    ('apres_devis_positionne',
     'Après devis — positionné depuis l\'envoi, touches passées sautées',
     'apres_devis'),
    ('dormant_devis',
     'Dormant — Froid, tag « Devis sans suite », réveil étalé', 'reveil'),
    ('dormant_jamais_chiffre',
     'Dormant — Froid, tag « Jamais chiffré », réveil étalé', 'reveil'),
)

_PLACEMENT_CADENCES = {code: cadence for code, _, cadence in PLACEMENT_DECISIONS}

#: Le code de dormance de CHAQUE famille : c'est le repli d'une cadence
#: positionnée dont TOUTES les touches sont déjà passées (rien à faire demain
#: = un dossier dormant, pas une cadence vide).
_PLACEMENT_REPLI_DORMANT = {
    'contact_positionne': 'dormant_jamais_chiffre',
    'apres_devis_positionne': 'dormant_devis',
}

#: L'étiquette posée par chaque code de dormance.
_PLACEMENT_TAGS = {
    'dormant_devis': _CLOTURE_TAGS['apres_devis'],
    'dormant_jamais_chiffre': _PLACEMENT_TAG_JAMAIS_CHIFFRE,
}

#: Note portée par une touche déjà échue au moment du placement. La REJOUER
#: enverrait aujourd'hui le message du J+1 d'il y a dix jours.
PLACEMENT_NOTE_PASSEE = 'passée avant le moteur'

#: Leads placés PAR APPEL d'application. 277 dossiers d'un trait, c'est
#: plusieurs milliers d'écritures dans une seule requête HTTP — au-delà du
#: délai du navigateur (20 s côté axios), donc un 499 et un placement dont
#: personne ne sait ce qu'il a fait. L'écran rappelle jusqu'à `restants == 0`.
PLACEMENT_LOT_DEFAUT = 40

#: Borne haute de `limite` : au-delà, on retombe dans le cas qui a produit le
#: 499. Ce n'est pas un réglage de confort, c'est la garde.
PLACEMENT_LOT_MAX = 200

#: Lignes détaillées du rapport. Ce sont les SEULES à être datées : calculer
#: l'échéance des 270 autres coûterait le prix qu'on vient justement de
#: supprimer, pour un écran qui n'en montre que vingt.
PLACEMENT_APERCU_MAX = 20


#: ACRM47/ACRM61 — message de la réponse 503 ``{detail}`` (contrat
#: ``placement_anciens_leads.json``, ``exemple_erreur``).
PLACEMENT_DEVIS_ILLISIBLES = (
    "Lecture des devis acceptés indisponible : placement suspendu, rien "
    "n'a été appliqué")


class PlacementImpossible(Exception):
    """Un lead retenu n'a finalement pas pu être placé (cadence vide, gabarit
    absent…). Comptée dans ``erreurs`` du rapport, jamais propagée : le
    placement est best-effort LEAD PAR LEAD — un dossier bancal n'empêche
    jamais les 276 autres d'être traités."""


def _placement_moment(valeur):
    """Normalise une ancre en datetime AWARE (une ``date`` comparée à un
    datetime lèverait ``TypeError`` au premier lead)."""
    from . import horaires

    if valeur is None:
        return None
    if not isinstance(valeur, datetime.datetime):
        return datetime.datetime.combine(
            valeur, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
    if timezone.is_naive(valeur):
        return timezone.make_aware(valeur, datetime.timezone.utc)
    return valeur


def _placement_derniers_par_lead(qs):
    """``{lead_id: created_at}`` du plus récent de chaque lead — UNE requête."""
    from django.db.models import Max
    return {
        ligne['lead_id']: ligne['dernier']
        for ligne in qs.values('lead_id').annotate(dernier=Max('created_at'))
    }


def _placement_devis_du_lot(company, lead_ids):
    """Les deux lectures cross-app du placement, via ``ventes.selectors``
    (jamais ``ventes.models`` — frontière M3) : les leads à devis ACCEPTÉ (à
    écarter) et le dernier devis ENVOYÉ de chacun (qui date la cadence).

    ACRM47 — échoue FERMÉ : si ``ventes`` est illisible, la garde « devis
    accepté » ne peut plus écarter les signés — continuer enverrait au Froid
    un client qui a dit oui. ``PlacementImpossible`` (message français) est
    levée AVANT toute écriture : la vue répond 503 ``{detail}``, la commande
    sort en erreur, rien n'est appliqué."""
    try:
        from apps.ventes.selectors import (
            dernier_devis_envoye_par_lead, leads_avec_devis_accepte)
        return (leads_avec_devis_accepte(company, lead_ids),
                dernier_devis_envoye_par_lead(company, lead_ids))
    except Exception as exc:  # noqa: BLE001 — journalisé puis échec fermé
        logger.warning(
            'MRY30: devis illisibles (société %s)',
            getattr(company, 'pk', '?'), exc_info=True)
        raise PlacementImpossible(PLACEMENT_DEVIS_ILLISIBLES) from exc


def _decider_placements(company, maintenant, gabarits=None,
                        leads_en_portee=None):
    """Phase de DÉCISION : QUI est candidat, QUI est écarté, QUELLE décision
    s'applique à chacun — et, pour les cadences positionnées, s'il leur reste
    seulement une touche à faire (sinon elles basculent en dormance ici même,
    cf. ``_trancher_cadence_positionnee``).

    N'écrit AUCUNE donnée métier — pas une touche, pas une étiquette, pas un
    changement d'étape. Seule exception, pré-existante et assumée :
    ``CadenceRelanceEtape.cadence_pour`` seede le GABARIT d'une société qui
    n'en a pas encore (un référentiel de paramètres, jamais un dossier).

    Renvoie ``(decisions, ignores, total_candidats)``. Chaque décision est un
    dictionnaire de travail que l'étalement puis l'exécution complètent
    (``creneau``…) — jamais un modèle enregistré."""
    gabarits = gabarits or _placement_gabarits(company)
    base = Lead.objects.filter(
        company=company, is_archived=False, perdu=False,
        ne_plus_contacter=False,
    ).exclude(stage__in=[stages.COLD, stages.SIGNED])
    # ALEA25 — appelé depuis l'API, le placement est BORNÉ par la portée de
    # l'utilisateur (``LeadViewSet._leads_en_portee``) : un Commercial ne
    # voit ni ne place les leads d'un collègue hors équipe. ``None`` (la
    # commande de gestion) = toute la société, comme avant.
    if leads_en_portee is not None:
        base = base.filter(pk__in=leads_en_portee.values('pk'))
    candidats = list(base.order_by('pk'))
    total = len(candidats)
    # ACRM61/ACRM20 — ``rappel_manuel_a_venir`` : entier, jamais null.
    ignores = {'deja_en_cadence': 0, 'devis_accepte_non_signe': 0,
               'rappel_manuel_a_venir': 0}
    if not candidats:
        return [], ignores, total
    # ACRM20 — date LOCALE du jour (Africa/Casablanca) du moment de décision.
    aujourdhui = timezone.localtime(maintenant).date()

    ids = [lead.pk for lead in candidats]
    # Le moteur TIENT déjà ces dossiers : une seconde cadence dessus, ce sont
    # deux séries de messages parallèles à la même personne.
    # ACRM46 — seul un plan OUVERT (touche À FAIRE, prédicat partagé avec
    # ``initialiser_plan_relance``) tient le lead : des touches toutes closes
    # (faites/sautées/annulées) le rendent candidat au placement.
    deja = set(RelanceEtape.objects.filter(
        _q_plan_ouvert(), company=company, lead_id__in=ids)
        .values_list('lead_id', flat=True))
    acceptes, envoyes = _placement_devis_du_lot(company, ids)

    humaines = _placement_derniers_par_lead(
        LeadActivity.objects.filter(lead_id__in=ids, user__isnull=False)
        .exclude(kind__in=[LeadActivity.Kind.CREATION,
                           LeadActivity.Kind.MODIFICATION]))
    etapes_stage = _placement_derniers_par_lead(
        LeadActivity.objects.filter(lead_id__in=ids, field='stage'))

    decisions = []
    for lead in candidats:
        if lead.pk in deja:
            ignores['deja_en_cadence'] += 1
            continue
        if lead.pk in acceptes:
            # Un devis accepté attend un passage en Signé À LA MAIN, pas une
            # relance : demander « alors, ce devis ? » à quelqu'un qui a dit
            # oui est le pire message du portefeuille.
            ignores['devis_accepte_non_signe'] += 1
            continue
        if lead.relance_date is not None and lead.relance_date >= aujourdhui:
            # ACRM20 — un rappel MANUEL à venir (posé par la commerciale) tient
            # le lead hors dormance : jamais de Froid, d'étiquette ni de
            # Réveil, et sa ``relance_date`` n'est jamais remplacée.
            ignores['rappel_manuel_a_venir'] += 1
            continue
        devis = envoyes.get(lead.pk)
        # L'ANCRE : le dernier signe de vie du dossier, quelle qu'en soit la
        # nature. La seule date de création ferait passer pour dormant un lead
        # rappelé hier ; la seule dernière activité raterait un devis parti
        # sans qu'on note rien.
        ancre = _placement_moment(lead.date_creation)
        for candidate in (humaines.get(lead.pk), etapes_stage.get(lead.pk),
                          getattr(devis, 'date_envoi', None)):
            candidate = _placement_moment(candidate)
            if candidate is not None and (ancre is None or candidate > ancre):
                ancre = candidate
        ancre = ancre or maintenant
        jours = (maintenant - ancre).days
        recent = jours <= PLACEMENT_FENETRE_JOURS

        if devis is not None:
            # Un devis ERP ENVOYÉ date la cadence, quel que soit son âge : le
            # suivi part de l'envoi RÉEL et les touches déjà passées seront
            # sautées. S'il n'en reste aucune, le repli dormant s'en charge.
            code, depart = 'apres_devis_positionne', devis.date_envoi
        elif lead.stage in (stages.QUOTE_SENT, stages.FOLLOW_UP):
            code, depart = (('apres_devis_positionne', ancre) if recent
                            else ('dormant_devis', None))
        elif lead.stage == stages.CONTACTED:
            code, depart = (('contact_positionne', ancre) if recent
                            else ('dormant_jamais_chiffre', None))
        else:  # NEW — le seul restant (Froid et Signé sont exclus en amont).
            code, depart = (('contact_complete', maintenant) if recent
                            else ('dormant_jamais_chiffre', None))

        entree = {
            'lead': lead,
            'code': code,
            'cadence': _PLACEMENT_CADENCES[code],
            'depart': _placement_moment(depart),
            'devis': devis if code == 'apres_devis_positionne' else None,
            'positionne': code in _PLACEMENT_REPLI_DORMANT,
            'ancre': ancre,
            'jours': jours,
            'nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
            'stage_libelle': stages.STAGE_LABELS.get(lead.stage, lead.stage),
            'source': lead.source or '',
            'creneau': None,
            'prochaine_touche': '',
            'prochaine_le': None,
        }
        if entree['positionne']:
            _trancher_cadence_positionnee(entree, maintenant, gabarits)
        decisions.append(entree)
    return decisions, ignores, total


def _echeances_best_effort(lead, cadence, depart, gabarits):
    """``calculer_echeances_cadence`` en mode best-effort : une liste vide au
    lieu d'une exception.

    Le placement est best-effort LEAD PAR LEAD (`PlacementImpossible`) : un
    dossier dont les horaires ou le gabarit se lisent mal ne doit pas faire
    tomber l'aperçu des 276 autres — c'est-à-dire toute la carte."""
    try:
        return calculer_echeances_cadence(lead, cadence, depart,
                                          gabarits=gabarits(cadence))
    except Exception:  # noqa: BLE001 — un dossier bancal n'arrête rien
        logger.warning('MRY30: échéances illisibles (lead #%s, cadence %s)',
                       getattr(lead, 'pk', '?'), cadence, exc_info=True)
        return []


def _trancher_cadence_positionnee(entree, maintenant, gabarits):
    """Date une cadence positionnée — ou la BASCULE en dormance.

    Une cadence positionnée dont TOUTES les touches sont déjà échues ne
    relancerait personne : elle bascule sur la dormance de sa famille. Cette
    bascule change un CHIFFRE que la carte affiche (`par_etape`), elle
    appartient donc à la DÉCISION, pas à l'exécution — sinon l'aperçu
    annoncerait « après devis : 30 » là où l'application écrirait « dormants :
    30 », et le second clic montrerait autre chose que le premier. C'est la
    leçon de MRY23, tirée un cran plus tôt.

    C'est le SEUL calcul d'échéances mené pour toute une famille — et il ne
    concerne que les positionnés (42 sur 270 en production) : une cadence
    complète part de maintenant et un dormant de son créneau, ni l'une ni
    l'autre n'a de touche passée à examiner."""
    echeances = _echeances_best_effort(
        entree['lead'], entree['cadence'], entree['depart'], gabarits)
    if not echeances:
        # Gabarit vide ou illisible : la cadence n'est pas « intégralement
        # passée », elle est INCONNUE. Basculer tout un portefeuille au froid
        # sur un référentiel absent serait la pire lecture de ce silence ;
        # l'exécution comptera ces leads en `erreurs`, ce qui est la vérité.
        return
    futures = [(echeance, gabarit.ordre, gabarit)
               for gabarit, echeance in echeances if echeance >= maintenant]
    if futures:
        echeance, _, gabarit = min(futures, key=lambda ligne: ligne[:2])
        entree['prochaine_touche'] = gabarit.libelle or ''
        entree['prochaine_le'] = echeance
        return
    entree.update(code=_PLACEMENT_REPLI_DORMANT[entree['code']],
                  cadence='reveil', positionne=False, devis=None, depart=None)


def _placement_gabarits(company):
    """``cadence -> gabarit`` mémorisé pour la durée d'UN placement.

    Sans cette mémoire, chaque lead relisait (et seedait) sa cadence : 270
    allers-retours pour trois réponses possibles."""
    cache = {}

    def lire(cadence):
        if cadence not in cache:
            try:
                from apps.parametres.models_relance import CadenceRelanceEtape
                cache[cadence] = CadenceRelanceEtape.cadence_pour(
                    company, cadence)
            except Exception:  # noqa: BLE001 — jamais bloquant
                logger.warning('MRY30: gabarit « %s » illisible', cadence,
                               exc_info=True)
                cache[cadence] = []
        return cache[cadence]

    return lire


def _placement_gabarit_reveil(company, gabarits=None):
    """Le PREMIER barreau actif du gabarit « réveil » de la société.

    Trois réponses d'une seule lecture : son ``delai_jours`` (pour remonter le
    départ jusqu'au créneau visé), son ``ordre`` (pour reconnaître les réveils
    DÉJÀ posés, cf. `_placement_occupation_reveils`) et son ``libelle`` (la
    touche que l'aperçu annonce pour un dormant, « Réveil J30 » par défaut).
    ``None`` si le gabarit est illisible — le placement continue alors sur les
    valeurs de repli plutôt que d'échouer en bloc."""
    lire = gabarits or _placement_gabarits(company)
    barreaux = lire('reveil')
    return barreaux[0] if barreaux else None


def _placement_occupation_reveils(company, jour_zero, gabarit):
    """``{jour local: premières touches de réveil DÉJÀ posées}``, à partir de
    ``jour_zero``.

    Sans elle, chaque lot d'application recommencerait la file au premier
    créneau : le lot 2 poserait ses huit réveils SUR ceux du lot 1 — seize
    messages le même matin depuis le même numéro, précisément ce que
    l'étalement existe pour empêcher. Et l'aperçu lancé entre deux lots
    annoncerait des créneaux déjà pris.

    Ne compte que le PREMIER barreau (``ordre``) : c'est lui qu'on étale ; le
    J60 suit mécaniquement."""
    from collections import Counter

    ordre = getattr(gabarit, 'ordre', None)
    if ordre is None:
        return Counter()
    return Counter(
        RelanceEtape.objects.filter(
            company=company, cadence='reveil', ordre=ordre,
            statut=RelanceEtape.Statut.A_FAIRE, due_date__gte=jour_zero,
        ).values_list('due_date', flat=True))


def _etaler_reveils(dormants, company, maintenant, *, gabarit=None):
    """Pose ``creneau`` (et le ``depart`` qui en découle) sur chaque dormant,
    8 par jour ouvré, LES ANCRES LES PLUS RÉCENTES D'ABORD.

    L'ordre n'est pas cosmétique : le dossier dont on a eu des nouvelles la
    semaine dernière a bien plus de chances de répondre que celui qui dort
    depuis huit mois — c'est lui qui doit occuper les premiers créneaux.

    Le premier jour est AUJOURD'HUI si la fenêtre d'appel n'est pas déjà
    close, sinon le prochain jour ouvré : ``prochain_creneau_appel`` répond
    exactement à cette question. Les jours déjà PLEINS (réveils posés par un
    lot précédent) sont sautés, et un jour partiellement occupé reprend au
    créneau suivant : la file se PROLONGE, elle ne recommence jamais.

    N'écrit rien : renvoie les dormants DANS L'ORDRE d'étalement."""
    from apps.notifications.calendar_utils import ajouter_jours_ouvres

    from . import horaires

    if not dormants:
        return []
    if gabarit is None:
        gabarit = _placement_gabarit_reveil(company)
    delai = (getattr(gabarit, 'delai_jours', None)
             or PLACEMENT_REVEIL_DELAI_JOURS)
    # Une cadence « réveil » commence par un MESSAGE WhatsApp : sa fenêtre est
    # celle des messages (08:30), pas celle des appels (09:00) — 07/09/2026.
    base = horaires.prochain_creneau_appel(
        maintenant, company, canal='whatsapp')
    base_locale = base.astimezone(horaires.CASABLANCA)
    jour_zero = base_locale.date()
    if base_locale.time() > PLACEMENT_CRENEAUX[0]:
        # Les créneaux du jour (10 h-12 h 20) sont déjà derrière nous : un
        # placement lancé l'après-midi commence le PROCHAIN jour ouvré, jamais
        # avec des touches « en retard » à la seconde où elles naissent.
        jour_zero = ajouter_jours_ouvres(jour_zero, 1, company)
    occupation = _placement_occupation_reveils(company, jour_zero, gabarit)
    ordonnes = sorted(dormants,
                      key=lambda e: (e['ancre'], e['lead'].pk), reverse=True)
    jour = jour_zero
    for entree in ordonnes:
        while occupation[jour] >= PLACEMENT_REVEILS_PAR_JOUR:
            jour = ajouter_jours_ouvres(jour, 1, company)
        rang = occupation[jour]
        occupation[jour] += 1
        creneau = horaires.prochain_creneau_appel(
            datetime.datetime.combine(
                jour, PLACEMENT_CRENEAUX[rang], tzinfo=horaires.CASABLANCA),
            company, canal='whatsapp')
        entree['creneau'] = creneau
        # La cadence « réveil » place sa première touche à J+`delai` : on
        # remonte donc le départ d'autant pour qu'elle tombe SUR le créneau.
        entree['depart'] = creneau - datetime.timedelta(days=delai)
    return ordonnes


def _placement_touches_creees(lead, cadence, devis=None):
    """Les touches de CETTE cadence, relues triées par échéance."""
    from django.db.models import F
    qs = lead.relance_etapes.filter(cadence=cadence)
    if devis is not None:
        qs = qs.filter(devis=devis)
    return list(qs.order_by(F('due_at').asc(nulls_last=True), 'due_date',
                            'ordre'))


def _placer_cadence_positionnee(entree, *, user, maintenant):
    """Cadence `contact`/`apres_devis` datée depuis l'ancre (ou l'envoi du
    devis), touches déjà échues ANNULÉES (CKP1 — c'est le MOTEUR qui les
    retire, pas un commercial : ``traite_par`` reste NULL).

    Les touches passées sont annulées par un UPDATE direct, jamais par
    ``marquer_etape_relance`` : celui-ci journalise une ligne de chatter par
    touche (dix lignes « touche sautée » sur un dossier qu'on vient à peine de
    reprendre) et, sur la DERNIÈRE, déclencherait ``cloturer_cadence`` — le
    lead partirait au froid étiqueté « injoignable » à la seconde même où on
    l'inscrit dans la cadence.

    Renvoie ``True`` si une touche reste À FAIRE, ``False`` si la cadence est
    intégralement passée. Ce second cas est désormais TRANCHÉ EN AMONT par
    ``_trancher_cadence_positionnee`` (l'aperçu doit annoncer la bascule) : le
    voir ici est une anomalie, que l'appelant compte en ``erreurs``. La remise
    en état reste néanmoins écrite, parce qu'elle doit être exacte le jour où
    elle sert."""
    lead = entree['lead']
    # Photo d'AVANT : de quoi défaire proprement si la cadence s'avère
    # intégralement passée (voir plus bas). Un rappel posé à la main par un
    # commercial ne doit pas disparaître dans l'opération.
    relance_avant = lead.relance_date
    activites_avant = set(lead.activites.values_list('pk', flat=True))

    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence=entree['cadence'], depart=entree['depart'],
            devis=entree['devis'])
    except CadenceActiveConflit as exc:
        raise PlacementImpossible(str(exc))
    if not etapes:
        raise PlacementImpossible(
            f'aucune touche créée (cadence {entree["cadence"]})')
    if not entree['positionne']:
        return True

    passees = [e.pk for e in etapes
               if e.due_at is not None and e.due_at < maintenant]
    if passees:
        RelanceEtape.objects.filter(
            pk__in=passees, statut=RelanceEtape.Statut.A_FAIRE,
        ).update(statut=RelanceEtape.Statut.ANNULEE,
                 note=PLACEMENT_NOTE_PASSEE, traite_par=None,
                 traite_le=maintenant)
    if len(passees) >= len(etapes):
        # Rien ne reste à faire : cette cadence ne relancerait personne. On
        # défait TOUT ce qu'on vient de créer — touches, note « Plan de
        # relance initialisé » (elle annoncerait un plan qui n'existe plus) et
        # `relance_date` — puis l'appelant compte l'anomalie. Sans cette
        # remise en état, le lead gardait une échéance de relance pointant sur
        # une touche supprimée : un rappel fantôme, en retard pour toujours.
        RelanceEtape.objects.filter(pk__in=[e.pk for e in etapes]).delete()
        lead.activites.exclude(pk__in=activites_avant).delete()
        lead.relance_date = relance_avant
        lead.save(update_fields=['relance_date'])
        sync_relance_activity(lead, user)
        return False

    # `initialiser_plan_relance` a pointé `relance_date` sur la PREMIÈRE
    # touche — celle qu'on vient peut-être de sauter. On la recale sur la
    # prochaine réellement à faire, exactement comme `marquer_etape_relance`.
    # ACRM37 — par LE recalage unique (une touche au moins reste ouverte ici).
    _recaler_file(lead, user)
    return True


def _placer_dormant(entree, *, user):
    """Dormance explicite : Froid + étiquette qui dit POURQUOI + cadence de
    réveil posée sur le créneau étalé.

    Froid est un PARKING, pas une perte (même garantie que ``cloturer_cadence``
    MRY11) : aucun motif de perte n'est posé, ``Lead.perdu`` n'est jamais
    touché."""
    lead = entree['lead']
    avancer_stage_lead_vers(lead, user, stages.COLD)
    tag = _PLACEMENT_TAGS.get(entree['code'])
    if tag:
        poser_tag_lead(lead, user, tag)
    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence='reveil', depart=entree['depart'])
    except CadenceActiveConflit as exc:
        raise PlacementImpossible(str(exc))
    if not etapes:
        raise PlacementImpossible('aucune touche de réveil créée')
    if entree['code'] == 'dormant_devis':
        for etape, cle in zip(sorted(etapes, key=lambda e: e.ordre),
                              _PLACEMENT_CLES_REVEIL_DEVIS):
            if etape.template_cle != cle:
                etape.template_cle = cle
                etape.save(update_fields=['template_cle'])
    return True


def _placer_un(entree, *, user, maintenant):
    """Place UN lead, puis journalise la touche qui l'attend."""
    if entree['cadence'] != 'reveil':
        if not _placer_cadence_positionnee(
                entree, user=user, maintenant=maintenant):
            # La DÉCISION a déjà vérifié qu'une touche restait à faire
            # (`_trancher_cadence_positionnee`) : si la matérialisation dit le
            # contraire, c'est une anomalie — comptée, jamais silencieuse.
            raise PlacementImpossible(
                'cadence intégralement passée après décision')
    else:
        _placer_dormant(entree, user=user)

    lead = entree['lead']
    touches = _placement_touches_creees(
        lead, entree['cadence'], devis=entree['devis'])
    a_faire = [e for e in touches if e.statut == RelanceEtape.Statut.A_FAIRE]
    reference = (a_faire or touches or [None])[0]
    # Le libellé est relu sur la touche RÉELLEMENT créée : la décision ne date
    # que les vingt lignes de l'aperçu, et cette note doit nommer la bonne
    # touche pour les 250 autres aussi.
    libelle = (getattr(reference, 'libelle', '') or ''
               or entree['prochaine_touche'])
    # FG28/MRY19 — note SYSTÈME (``user=None``), JAMAIS l'utilisateur qui a
    # lancé le placement. Le récepteur QJ7 (`_avancer_stage_on_contact_
    # activity`) fait avancer NEW → CONTACTED et stampe `first_contacted_at`
    # sur toute note portant un `user` : posée avec l'acteur, cette ligne
    # aurait déclaré « contactés » les leads NEW qu'on vient justement
    # d'inscrire dans la cadence de PREMIER contact — 270 dossiers marqués
    # joints sans qu'un humain ait décroché, et le KPI de premier contact
    # faussé du même coup. Même choix, trois lignes plus haut, que la note de
    # `initialiser_plan_relance`. QUI a lancé le placement reste tracé : par
    # les lignes de modification (étape, étiquette), qui portent l'acteur.
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f'Placé dans la cadence {entree["cadence"]} à la touche '
             f'« {libelle} » ({PLACEMENT_MARQUEUR}).')
    return True


def _placement_ordre(decisions, company, maintenant, *, gabarit=None):
    """L'ordre de traitement d'un lot : les cadences vivantes (les dossiers
    les plus RÉCENTS d'abord), puis les dormants dans leur ordre d'étalement.

    L'étalement est calculé ICI, pour tout le monde et dans les deux modes :
    c'est lui qui donne son créneau à chaque dormant, donc `reveils_jusqu_au`
    et la date affichée par l'aperçu. Borner le lot APRÈS cet ordre garantit
    que le lot 1 prend bien les premiers créneaux et le lot 2 les suivants."""
    dormants = _etaler_reveils(
        [e for e in decisions if e['cadence'] == 'reveil'], company,
        maintenant, gabarit=gabarit)
    vivants = sorted([e for e in decisions if e['cadence'] != 'reveil'],
                     key=lambda e: (e['jours'], e['lead'].pk))
    return vivants + dormants


def _dater_apercu(decisions, maintenant, *, gabarits, gabarit_reveil):
    """Donne sa touche et sa date à CHACUNE des vingt lignes de l'aperçu —
    et à elles seules.

    C'est le cœur de la correction du 07/09 : dater les 270 décisions
    revenait à matérialiser 270 cadences (le dry-run en transaction annulée),
    alors que le rapport n'en montre que vingt. Les positionnées sont déjà
    datées par la décision (elle devait, de toute façon, savoir s'il leur
    restait une touche) ; restent les cadences complètes, calculées ici, et
    les dormants, dont la date EST leur créneau étalé."""
    for entree in sorted(
            decisions,
            key=lambda e: (e['jours'], e['lead'].pk))[:PLACEMENT_APERCU_MAX]:
        if entree['prochaine_le'] is not None:
            continue
        if entree['cadence'] == 'reveil':
            entree['prochaine_touche'] = (
                getattr(gabarit_reveil, 'libelle', '') or '')
            entree['prochaine_le'] = entree['creneau']
            continue
        echeances = _echeances_best_effort(
            entree['lead'], entree['cadence'], entree['depart'], gabarits)
        futures = [(echeance, gabarit.ordre, gabarit)
                   for gabarit, echeance in echeances
                   if echeance >= maintenant]
        if futures:
            echeance, _, gabarit = min(futures, key=lambda ligne: ligne[:2])
            entree['prochaine_touche'] = gabarit.libelle or ''
            entree['prochaine_le'] = echeance


def _executer_placements(entrees, *, user, maintenant):
    """Exécute les décisions du LOT, lead par lead, best-effort.

    ``entrees`` arrive déjà ordonné et borné (`_placement_ordre`, `limite`) :
    cette fonction ne décide plus rien — elle pose ce que la décision a
    tranché. Renvoie ``(applique, erreurs)``."""
    from django.db import transaction

    applique = erreurs = 0
    for entree in entrees:
        try:
            with transaction.atomic():
                _placer_un(entree, user=user, maintenant=maintenant)
        except Exception:  # noqa: BLE001 — un dossier bancal n'arrête rien
            logger.warning(
                'MRY30: placement échoué (lead #%s, code %s)',
                entree['lead'].pk, entree['code'], exc_info=True)
            erreurs += 1
            continue
        applique += 1
    return applique, erreurs


def _rapport_placement(decisions, ignores, total, *, apply, applique, erreurs,
                       restants):
    """Le rapport, forme ``contract_samples/placement_anciens_leads.json``."""
    from . import horaires

    par_code = {}
    for entree in decisions:
        par_code[entree['code']] = par_code.get(entree['code'], 0) + 1
    par_etape = [
        {'code': code, 'libelle': libelle, 'cadence': cadence,
         'nombre': par_code[code]}
        for code, libelle, cadence in PLACEMENT_DECISIONS if code in par_code
    ]
    apercu = [
        {
            'lead': entree['lead'].pk,
            'nom': entree['nom'],
            'stage_libelle': entree['stage_libelle'],
            'source': entree['source'],
            'ancre': entree['ancre'].astimezone(
                horaires.CASABLANCA).date().isoformat(),
            'jours': entree['jours'],
            'code': entree['code'],
            'cadence': entree['cadence'],
            'prochaine_touche': entree['prochaine_touche'],
            'prochaine_le': (
                entree['prochaine_le'].astimezone(
                    horaires.CASABLANCA).isoformat()
                if entree['prochaine_le'] is not None else None),
        }
        for entree in sorted(
            decisions,
            key=lambda e: (e['jours'], e['lead'].pk))[:PLACEMENT_APERCU_MAX]
    ]
    creneaux = [e['creneau'] for e in decisions if e['creneau'] is not None]
    return {
        'apply': bool(apply),
        'total_candidats': total,
        'a_placer': len(decisions),
        'ignores': ignores,
        'par_etape': par_etape,
        'apercu': apercu,
        'reveils_jusqu_au': (
            max(creneaux).astimezone(horaires.CASABLANCA).date().isoformat()
            if creneaux else None),
        'applique': applique,
        'erreurs': erreurs,
        'restants': restants,
    }


def _placement_limite(limite):
    """``limite`` bornée à [1, PLACEMENT_LOT_MAX] (défaut PLACEMENT_LOT_DEFAUT).

    La vue REFUSE une valeur hors bornes (400) : ce garde-fou-ci protège les
    appelants internes (commande, tâche) d'un lot de 100 000 leads."""
    if limite is None:
        return PLACEMENT_LOT_DEFAUT
    return max(1, min(int(limite), PLACEMENT_LOT_MAX))


def placer_anciens_leads(company, user, *, apply=False, maintenant=None,
                         limite=None, leads_en_portee=None):
    """Enveloppe de `_placer_anciens_leads_sans_cache` sous `horaires.cache_local()` :
    profil société et jours ouvrés lus UNE fois pour toute l'opération. Sans
    cela, dater les touches de 272 leads coûtait ~7 000 requêtes et 24 s en
    production (07/09/2026), au-delà du délai du navigateur."""
    from . import horaires
    with horaires.cache_local():
        return _placer_anciens_leads_sans_cache(
            company, user, apply=apply, maintenant=maintenant, limite=limite,
            leads_en_portee=leads_en_portee)


def _placer_anciens_leads_sans_cache(company, user, *, apply=False,
                                     maintenant=None, limite=None,
                                     leads_en_portee=None):
    """MRY30 — Place les anciens leads d'une société dans les cadences du
    moteur de relances. Rapport = ``contract_samples/placement_anciens_leads``.

    ``apply=False`` (défaut) est un CALCUL PUR : aucune écriture, aucune
    transaction, aucun rollback. L'aperçu partage le CALCUL de l'application
    — ``calculer_echeances_cadence`` pour les dates, ``_etaler_reveils`` pour
    les créneaux, ``_decider_placements`` pour les codes — et c'est ce partage
    qui le rend fidèle, comme l'était l'ancienne exécution en transaction
    annulée. Celle-ci matérialisait en revanche les touches des 277 candidats
    pour les jeter aussitôt : plus de 20 s, donc un 499 (le navigateur
    abandonne à 20 s) et un écran qui n'affichait jamais rien — l'incident du
    07/09/2026. Les vingt lignes de l'aperçu sont les seules datées.

    ``apply=True`` place AU PLUS ``limite`` leads (défaut 40), dans l'ordre
    d'`_placement_ordre` : les cadences vivantes des dossiers les plus récents
    d'abord, puis les dormants dans leur ordre d'étalement. Chaque lead est
    posé sous son propre ``transaction.atomic`` : son échec est journalisé et
    compté dans ``erreurs``, il n'annule jamais les autres. La réponse porte
    ``restants`` ; l'écran (et la commande) rappellent jusqu'à ce qu'il tombe
    à zéro. IDEMPOTENT : les leads du lot précédent reviennent en
    ``deja_en_cadence``, et l'étalement REPREND à la suite des réveils déjà
    posés — jamais au premier créneau du jour.

    ``par_etape``, ``apercu`` et ``reveils_jusqu_au`` décrivent l'ensemble
    RESTANT au DÉBUT de l'appel : ce qu'un aperçu montrerait à cette seconde,
    dans les deux modes."""
    maintenant = maintenant or timezone.now()
    gabarits = _placement_gabarits(company)
    decisions, ignores, total = _decider_placements(
        company, maintenant, gabarits, leads_en_portee=leads_en_portee)
    # Lu SEULEMENT s'il y a un dormant : `cadence_pour` seede la cadence
    # absente, et une société sans aucun dormant n'a aucune raison de voir
    # naître un gabarit de réveil au passage d'un aperçu.
    gabarit_reveil = (
        _placement_gabarit_reveil(company, gabarits)
        if any(e['cadence'] == 'reveil' for e in decisions) else None)
    ordre = _placement_ordre(decisions, company, maintenant,
                             gabarit=gabarit_reveil)
    _dater_apercu(decisions, maintenant, gabarits=gabarits,
                  gabarit_reveil=gabarit_reveil)
    rapport = _rapport_placement(
        decisions, ignores, total, apply=apply, applique=0, erreurs=0,
        restants=len(decisions))
    if not apply:
        return rapport
    applique, erreurs = _executer_placements(
        ordre[:_placement_limite(limite)], user=user, maintenant=maintenant)
    rapport['applique'] = applique
    rapport['erreurs'] = erreurs
    rapport['restants'] = max(0, len(decisions) - applique - erreurs)
    return rapport


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


#: Combien de jours après la visite le plan de relance REPREND. Deux : le
#: débrief est à J+1, la relance générique ne doit pas tomber le même jour que
#: l'appel de débrief (deux sollicitations le même jour pour un client qu'on
#: vient de voir chez lui). Ce n'est pas un délai « commercial » inventé, c'est
#: la place du débrief plus un jour.
#: PARAM-CADENCE (25/09/2026) — reste une CONSTANTE, pas un barreau de
#: Paramètres : ce n'est pas une étape posée, c'est le décalage du plan.
VISITE_REPRISE_JOURS = 2


def _touche_pendante_du_plan(lead):
    """La touche du PLAN après-devis encore à faire — hors gestes de visite.

    C'est elle que la visite fait taire : les trois étapes de visite portent la
    même cadence (l'écran les montre dans la même frise) mais ne sont pas des
    barreaux du protocole, et décaler le débrief au motif qu'une visite est
    planifiée n'aurait aucun sens."""
    from django.db.models import F

    return (lead.relance_etapes
            .filter(cadence=VISITE_CADENCE,
                    statut=RelanceEtape.Statut.A_FAIRE)
            .exclude(q_visite())
            .order_by(F('due_at').asc(nulls_last=True), 'due_date', 'ordre')
            .first())


def suspendre_plan_jusqu_apres_visite(lead, user, date_prevue):
    """AMENDEMENT FONDATEUR (15/09/2026) — le plan se TAIT, il ne meurt pas.

    La touche pendante du protocole est REPORTÉE à ``date_prevue +
    VISITE_REPRISE_JOURS``, et avec elle — par la mécanique EXISTANTE de
    ``reporter_prochaine_touche``, jamais une seconde — toutes les touches
    suivantes de la cadence ET l'ancre ``cadence_depart``, du même delta. Le
    lead reste donc EXACTEMENT à sa place : même barreau, même libellé, même
    reste de plan, simplement plus tard. Si la visite n'aboutit pas, le suivi
    reprend de lui-même — aucun redémarrage de cadence n'existe nulle part.

    Deux no-op délibérés :

    * aucune touche pendante (le plan n'a pas démarré, ou il est épuisé) ⇒
      rien à décaler, et surtout rien à CRÉER : ce serait un restart ;
    * la touche pendante tombe DÉJÀ après la reprise ⇒ on ne la tire jamais
      EN AVANT. Une visite planifiée ne doit pas accélérer une relance.

    Renvoie la touche déplacée, ou ``None``."""
    cible = _touche_pendante_du_plan(lead)
    if cible is None:
        return None
    reprise = date_prevue + datetime.timedelta(days=VISITE_REPRISE_JOURS)
    if cible.due_date is not None and cible.due_date >= reprise:
        return None
    from . import horaires

    quand = datetime.datetime.combine(
        reprise, datetime.time(9, 0), tzinfo=horaires.CASABLANCA)
    # ``journaliser=False`` : l'appelant écrit UNE note qui dit la vraie
    # raison (« Relances décalées après la visite »), et « Rappel demandé »
    # serait faux — le client n'a rien demandé. COCKPIT-CONTRÔLE : un
    # décalage du MOTEUR, jamais un report compté à la commerciale.
    return reporter_prochaine_touche(
        lead, user, quand, etape=cible, journaliser=False,
        compter_report=False)


# ── CAD-B ── CAD28 ──────────────────────────────────────────────────────────

def reprendre_plan_apres_retour_visite(lead, user):
    """CAD28 — la reprise du protocole part du RETOUR RÉELLEMENT SAISI.

    La suspension calait la reprise sur la date PRÉVUE de la visite. Une
    visite reportée à la dernière minute sans mise à jour de la fiche laissait
    donc la relance repartir quand même : le client recevait un message
    « suite à notre visite » avant que quiconque soit passé chez lui.

    Le retour de visite, lui, est déjà saisi (``appliquer_retour_visite``).
    On recale donc la touche pendante du protocole sur CE jour-là plus le
    délai de débrief, par la mécanique EXISTANTE — jamais une seconde :
    ``suspendre_plan_jusqu_apres_visite`` avec la date du jour. Elle apporte
    ses deux garde-fous tels quels : aucune touche pendante ⇒ on ne CRÉE
    rien ; une touche déjà postérieure à la reprise ⇒ on ne la tire jamais EN
    AVANT (un retour tardif ne doit pas accélérer une relance).

    Le délai reste ``VISITE_REPRISE_JOURS`` — la place du débrief plus un
    jour, non réglable : un réglage de plus pour deux personnes. PARAM-CADENCE
    (25/09/2026) : ce n'est PAS un barreau du gabarit « Visite technique » —
    c'est le décalage du PLAN autour de la visite, pas une étape posée.

    Rend la touche déplacée, ou ``None`` (les deux no-op ci-dessus).
    """
    deplacee = suspendre_plan_jusqu_apres_visite(
        lead, user, aujourd_hui_local())
    if deplacee is None:
        return None
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=('Relances recalées sur le retour de visite — prochaine touche '
              f'le {deplacee.due_date:%d/%m/%Y}.'))
    return deplacee


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


def _recaler_file(lead, user):
    """Remet ``Lead.relance_date`` (et le rappel Calendrier) sur la prochaine
    touche ouverte — le geste de fin de toutes les écritures de relance."""
    prochaine = _prochaine_touche_a_faire(lead)
    lead.relance_date = prochaine.due_date if prochaine else None
    lead.save(update_fields=['relance_date'])
    sync_relance_activity(lead, user)


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


def _devis_id_de_la_cadence(lead):
    """L'id du devis suivi par la cadence après-devis, s'il est SANS DOUTE.

    Deux devis relancés en parallèle (cas rare mais réel) ⇒ ``None`` : mieux
    vaut deux étapes de visite sans devis attaché qu'un rendez-vous rattaché
    au mauvais dossier."""
    ids = set(
        lead.relance_etapes
        .filter(cadence=VISITE_CADENCE)
        .exclude(devis__isnull=True)
        .values_list('devis_id', flat=True))
    return ids.pop() if len(ids) == 1 else None


# ── CAD123 — une visite SANS devis envoyé : on AVERTIT, on ne bloque pas
# (décision fondateur du 21/09/2026).
#
# La doctrine du 15/09 est « visite technique jamais avant le devis » : le
# panneau de coaching la respecte (il ne vit que sur le suivi de proposition),
# mais la fiche (``SectionVisite``) planifiait sans aucune garde. Le terrain a
# des exceptions légitimes : l'écran NOMME la règle et laisse passer. Le texte
# vit ICI, une fois — chaque chemin qui planifie l'affiche tel quel, il ne
# peut donc pas dire deux choses différentes. La visite posée malgré tout est
# signalée comme telle dans le suivi (note de ``appliquer_visite_planifiee``).

#: CAD123 — la règle, telle que l'écran la dit.
AVERTISSEMENT_VISITE_SANS_DEVIS = (
    'Aucun devis n’a encore été envoyé à ce client. Règle : la visite '
    'technique se propose APRÈS le devis (c’est un outil de closing). Vous '
    'pouvez la planifier quand même — elle sera signalée « sans devis » dans '
    'le suivi.')

#: CAD123 × CAD122 — l'effet de bord juridique, rappelé à côté : un bon de
#: commande signé pendant la visite, chez le client, est un démarchage à
#: domicile (loi 31-08, art. 45) ; les mentions viennent de la décision
#: CAD122 (`docs/crm/messages_meryem.md`), rien n'est ajouté.
RAPPEL_JURIDIQUE_VISITE_DOMICILE = (
    'Si le bon de commande se signe pendant la visite, chez le client : '
    'démarchage à domicile (loi 31-08, art. 45) — cocher « signé au '
    'domicile », formulaire de rétractation remis, aucun acompte encaissé '
    'avant 7 jours (art. 49 et 50).')

#: La phrase ajoutée à la note de planification quand aucun devis n'est parti.
MENTION_VISITE_SANS_DEVIS = (
    'Planifiée SANS devis envoyé — exception à la règle « la visite se '
    'propose après le devis ».')


#: AGR408 (D-AGR-4) — la règle POMPAGE : pour un lead agricole dont le niveau
#: d'eau ou le débit du forage est inconnu, la visite de relevé du point d'eau
#: se fait AVANT le devis. Ce n'est pas une exception.
AVERTISSEMENT_VISITE_POINT_EAU = (
    'Pompage : niveau d’eau ou débit du forage inconnu — la visite de relevé '
    'du point d’eau se fait AVANT le devis.')

#: AGR408 — la phrase de la note de planification dans ce cas.
MENTION_VISITE_POINT_EAU = (
    'Visite de relevé du point d’eau, avant devis (règle pompage).')


#: CIQ411 (D-CIQ-5) — la règle SITE PROFESSIONNEL : pour un lead commercial
#: ou industriel dont le site est en MT, ou dont la tension, la puissance
#: souscrite ou le toit restent inconnus, la visite technique se fait AVANT le
#: devis final. Ce n'est pas une exception ; jamais un blocage.
AVERTISSEMENT_VISITE_PRO = (
    'Site professionnel : {motifs} — la visite technique se fait AVANT le '
    'devis final (un devis indicatif reste possible, marqué « estimation '
    'sous réserve de visite »).')

#: CIQ411 — la phrase de la note de planification dans ce cas.
MENTION_VISITE_PRO = 'Visite technique avant devis (règle site professionnel).'


def visite_sans_devis(lead):
    """CAD123 — ce lead n'a-t-il encore reçu AUCUN devis (sorti du
    brouillon) ? Lecture par le sélecteur de ``ventes`` (frontière M3).
    Best-effort : dans le doute (lecture en échec), on répond NON — un
    avertissement faux vaut moins que pas d'avertissement."""
    if lead is None or not getattr(lead, 'pk', None):
        return False
    try:
        from apps.ventes.selectors import lead_a_un_devis

        return not lead_a_un_devis(lead)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning('CAD123 : devis du lead #%s illisibles',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return False


#: Décision fondateur du 24/09/2026 — la note des étapes « préparer et
#: envoyer le devis » mises EN ATTENTE par une visite planifiée sans devis.
NOTE_DEVIS_APRES_VISITE = ('visite planifiée : le devis se prépare après la '
                           'visite')
#: … et la phrase ajoutée, dans ce cas, à la note de planification.
#: PARAM-CADENCE — la phrase porte le libellé RÉEL de l'étape annulée
#: (``mention_devis_apres_visite``) ; cette constante est la phrase au
#: libellé par défaut.
MENTION_DEVIS_APRES_VISITE = (
    f'Étape « {FILET_JOINT_LIBELLE} » mise en attente : le devis se prépare '
    'après la visite.')


def mention_devis_apres_visite(libelle):
    """La phrase de ``MENTION_DEVIS_APRES_VISITE`` au libellé réel."""
    return (f'Étape « {libelle or FILET_JOINT_LIBELLE} » mise en attente : '
            'le devis se prépare après la visite.')


#: La note d'un débrief annulé au retour terrain sans devis.
NOTE_RETOUR_SANS_DEVIS = 'retour terrain sans devis : préparer le devis'
#: Relevé du 25/09/2026 — la note de l'étape « Confirmer la visite (veille) »
#: encore ouverte quand le retour terrain arrive : la visite a eu lieu, il n'y
#: a plus rien à confirmer (même geste que le filet « planifier la visite »,
#: annulé à la planification).
NOTE_CONFIRMATION_VISITE_FAITE = 'visite effectuée'

#: La notification « Retour de visite » du responsable — la suite par défaut
#: (débrief : un devis est parti, il reste à conclure).
NOTIF_RETOUR_VISITE_RAPPELER = ('La visite technique est terminée. Rappeler '
                                'le client sous 24-48 h pour conclure.')


def phrase_notification_retour_visite(etape):
    """Le corps de la notification « Retour de visite », lu sur l'étape que
    ``appliquer_retour_visite`` vient de RENDRE — jamais deviné.

    Relevé du 25/09/2026 (décision fondateur du 24/09) : sans devis parti, la
    suite du retour est « Préparer et envoyer le devis », pas un rappel « pour
    conclure » ; la notification disait pourtant toujours « rappeler sous
    24-48 h ». Elle dit désormais la suite posée et sa date."""
    if (etape is not None and getattr(etape, 'due_date', None) is not None
            and est_etape(etape, CLE_DEVIS)):
        return ('La visite technique est terminée. Suite : préparer et '
                f'envoyer le devis pour le {etape.due_date:%d/%m}.')
    return NOTIF_RETOUR_VISITE_RAPPELER


def _suivi_de_proposition_existe(lead):
    """Un suivi de proposition a-t-il déjà existé pour ce lead (un barreau
    ``apres_devis`` du protocole, quel que soit son statut — hors gestes de
    visite) ? C'est la trace d'un devis parti HORS ERP : cocher « préparer et
    envoyer le devis » démarre le suivi sans objet devis (TREADMILL-1538)."""
    return (lead.relance_etapes.filter(cadence='apres_devis')
            .exclude(q_visite()).exists())


def aucun_devis_parti(lead):
    """Décision fondateur du 24/09/2026 — AUCUN devis n'est encore parti vers
    ce client : ni devis sorti du brouillon dans l'ERP (``visite_sans_devis``,
    CAD123), ni suivi de proposition démarré sur un devis envoyé hors ERP.

    C'est le cas d'une visite qui PRÉCÈDE le devis : le devis se prépare
    APRÈS elle, et c'est lui — pas un débrief « rappeler le client » — que la
    visite doit faire naître."""
    return visite_sans_devis(lead) and not _suivi_de_proposition_existe(lead)


def avertissement_visite(lead):
    """CAD123 — ``{'avertissement_sans_devis', 'rappel_juridique'}`` pour
    l'écran qui planifie une visite : les deux textes quand aucun devis n'est
    parti, deux chaînes VIDES (jamais null) sinon. Aucun blocage : c'est une
    information, pas un refus."""
    if visite_sans_devis(lead):
        # AGR408 (D-AGR-4) — pompage au point d'eau inconnu : la visite de
        # relevé vient AVANT le devis, c'est la règle (le rappel juridique,
        # lui, est inchangé).
        texte = (AVERTISSEMENT_VISITE_POINT_EAU
                 if visite_point_eau_requise(lead)
                 else AVERTISSEMENT_VISITE_SANS_DEVIS)
        # CIQ411 (D-CIQ-5) — site pro en MT ou aux faits inconnus : la
        # visite AVANT le devis final est la règle, pas une exception.
        pro = visite_pro_avant_devis(lead)
        if pro is not None:
            texte = AVERTISSEMENT_VISITE_PRO.format(
                motifs=', '.join(pro['motifs']))
        return {'avertissement_sans_devis': texte,
                'rappel_juridique': RAPPEL_JURIDIQUE_VISITE_DOMICILE}
    return {'avertissement_sans_devis': '', 'rappel_juridique': ''}


def appliquer_visite_planifiee(lead, user, date_prevue, commercial_nom=''):
    """Un RENDEZ-VOUS de visite est posé (ou déplacé) : le suivi s'y recale.

    Dans l'ordre, et jamais autrement :

    1. la fiche porte la date (``Lead.visite_prevue_le``) — c'est elle que lit
       le message de confirmation ``{date_visite}`` ;
    2. sur un lead ACTIF : le plan après-devis en cours est SUSPENDU PAR
       DÉCALAGE (``suspendre_plan_jusqu_apres_visite``) — jamais annulé. Le
       lead garde sa position exacte dans le protocole et, si la visite
       n'aboutit pas, le suivi reprend tout seul là où il en était ;
    3. UNE note de chatter, toujours — même sur un dossier qu'on ne relance
       plus : savoir qu'une visite a été calée reste une information. Elle dit
       le décalage quand il a eu lieu, et se tait sinon (annoncer des relances
       décalées alors qu'aucune n'était pendante serait faux) ;
    4. les DEUX gestes du rendez-vous — confirmer la veille, débriefer le
       lendemain. Le filet « planifier la visite convenue », s'il traînait, est
       ANNULÉ : lui seul, et parce qu'il a rempli son office ;
    5. décision fondateur du 24/09/2026 — SANS devis parti
       (``aucun_devis_parti``), l'étape « préparer et envoyer le devis »
       restée ouverte est ANNULÉE (le devis se prépare APRÈS la visite, le
       retour terrain la re-pose) et la note de l'étape 3 le dit.

    RE-PLANIFICATION : les deux étapes encore ouvertes sont DÉPLACÉES, jamais
    dupliquées (``_poser_etape_visite`` est idempotente par libellé) — « on
    décale à jeudi » ne doit pas laisser la confirmation de mardi dans la file
    — et le plan glisse d'un delta ADDITIONNEL depuis la nouvelle date.

    ``STAGES.py`` n'est pas touché, et AUCUNE étape du plan après-devis n'est
    annulée. Renvoie les étapes posées/déplacées."""
    champs = []
    if lead.visite_prevue_le != date_prevue:
        lead.visite_prevue_le = date_prevue
        champs.append('visite_prevue_le')
    if champs:
        lead.save(update_fields=champs)

    relancable = _lead_relancable(lead)
    # Le décalage AVANT la note : c'est lui qui décide de la dernière phrase.
    decalee = (suspendre_plan_jusqu_apres_visite(lead, user, date_prevue)
               if relancable else None)
    sans_devis = visite_sans_devis(lead)
    # Décision fondateur du 24/09/2026 — une visite planifiée SANS devis met
    # le devis EN ATTENTE d'elle : l'étape « préparer et envoyer le devis »
    # restée ouverte (filet « client joint », datée de demain) est ANNULÉE —
    # statut moteur CKP1, comme le filet « planifier la visite » plus bas.
    # Laissée là, elle restait orpheline dans la file ; et cochée « Fait »
    # sans issue, elle valait « devis parti » (QJ-FUNNEL) alors qu'aucun
    # devis n'était fait. C'est le retour terrain qui la re-posera
    # (``appliquer_retour_visite``). Idempotent : une re-planification ne
    # trouve plus rien à annuler, et la note n'en dit rien.
    devis_en_attente = 0
    libelle_devis = ''
    if (relancable and sans_devis
            and not _suivi_de_proposition_existe(lead)):
        en_attente = lead.relance_etapes.filter(
            q_etape(CLE_DEVIS), statut=RelanceEtape.Statut.A_FAIRE)
        libelle_devis = (en_attente.values_list('libelle', flat=True)
                         .first() or '')
        devis_en_attente = en_attente.update(
            statut=RelanceEtape.Statut.ANNULEE,
            note=NOTE_DEVIS_APRES_VISITE, traite_par=None,
            traite_le=timezone.now())

    quand = date_prevue.strftime('%d/%m/%Y')
    corps = f'Visite technique planifiée le {quand}'
    corps += (f' — assignée à {commercial_nom}.' if commercial_nom
              else ' — pas encore assignée.')
    if decalee is not None:
        corps += ' Relances décalées après la visite.'
    if sans_devis:
        # CAD123 — la visite posée avant tout devis est VISIBLE comme telle
        # dans le suivi : on a averti, on n'a pas bloqué, on le dit.
        # AGR408 (D-AGR-4) — pour un lead agricole au point d'eau inconnu,
        # c'est la RÈGLE pompage, pas une exception.
        # CIQ411 (D-CIQ-5) — site pro : visite avant devis, la règle.
        if visite_pro_avant_devis(lead) is not None:
            corps += f' {MENTION_VISITE_PRO}'
        else:
            corps += (f' {MENTION_VISITE_POINT_EAU}'
                      if visite_point_eau_requise(lead)
                      else f' {MENTION_VISITE_SANS_DEVIS}')
    if devis_en_attente:
        corps += f' {mention_devis_apres_visite(libelle_devis)}'
    # Note SYSTÈME (``user=None``) : PLANIFIER n'est pas AVOIR contacté le
    # lead — même motif que ``arreter_cadence`` / ``initialiser_plan_relance``
    # (garde QJ7, qui traiterait sinon cette note comme un premier contact).
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=corps)

    if not relancable:
        return []

    devis_id = _devis_id_de_la_cadence(lead)
    # Le filet « planifier la visite convenue » a rempli son office : on
    # l'ANNULE (statut moteur CKP1, jamais « sautée par un humain »). C'est la
    # SEULE étape que cette fonction annule — le plan, lui, est décalé.
    lead.relance_etapes.filter(
        q_etape(CLE_PLANIFIER),
        statut=RelanceEtape.Statut.A_FAIRE).update(
            statut=RelanceEtape.Statut.ANNULEE, note='visite planifiée',
            traite_par=None, traite_le=timezone.now())

    # PARAM-CADENCE — les deux gestes suivent le gabarit « Visite technique »
    # de la société : ``delai_jours`` de la confirmation = jours AVANT la
    # visite (la veille = 1), celui du débrief = jours APRÈS.
    confirmation = _config_visite(lead, CLE_CONFIRMATION)
    debrief = _config_visite(lead, CLE_DEBRIEF)
    veille = date_prevue - datetime.timedelta(
        days=confirmation['delai_jours'])
    if veille < aujourd_hui_local():
        # Visite calée pour aujourd'hui ou demain-matin-même : la veille est
        # déjà passée. On confirme AUJOURD'HUI — jamais une étape rétrodatée,
        # qui naîtrait « en retard » dans la file sans que personne n'ait
        # manqué quoi que ce soit.
        veille = aujourd_hui_local()
    # RE-PLANIFICATION — les deux étapes ci-dessous ont pu être emportées par
    # le décalage du plan (elles portent la même cadence et un ``ordre``
    # supérieur, donc ``reporter_prochaine_touche`` les glisse aussi). C'est
    # sans conséquence : elles sont RÉ-ANCRÉES ici même sur la nouvelle date de
    # visite, qui est leur seule vérité.
    etapes = [
        _poser_etape_visite(
            lead, cle=CLE_CONFIRMATION, ordre=VISITE_ORDRE_CONFIRMATION,
            quand=veille, devis_id=devis_id, config=confirmation),
        _poser_etape_visite(
            lead, cle=CLE_DEBRIEF, ordre=VISITE_ORDRE_DEBRIEF,
            quand=date_prevue + datetime.timedelta(
                days=debrief['delai_jours']),
            devis_id=devis_id, config=debrief),
    ]
    _recaler_file(lead, user)
    return etapes


def clore_etape_apres_planification(etape, user, *, note='',
                                    echeance_avant=None):
    """SUIVI E18 (30/09/2026) — la planification d'une visite CLÔT la touche
    qui l'a demandée (l'écran n'envoie plus jamais « Fait visite acceptée »
    AVANT d'avoir planifié).

    Appelée APRÈS la planification réussie (``visite_planifiee`` a déjà recalé
    le suivi) :

    * la touche est encore À FAIRE → close « visite acceptée » avec
      ``note`` (``marquer_etape_relance``) : la prise de contact s'arrête, le
      funnel avance, et le filet « planifier la visite » ne pose rien — un
      rendez-vous est calé ;
    * EXCEPTION : « Confirmer la visite » et « Débrief visite » encore
      ouvertes SUIVENT le rendez-vous (re-planification : la planification
      vient de les recaler) — elles restent ouvertes ;
    * la planification l'a déjà annulée (« Planifier la visite », ou l'étape
      devis mise en attente de la visite) → elle reste annulée.

    Dans les deux derniers cas, la note éventuelle part dans UNE ligne de
    chatter. Renvoie la touche (relue).

    COCKPIT-CONTRÔLE B8 — UNE ÉTAPE CLOSE GARDE L'ÉCHÉANCE QU'ELLE AVAIT
    QUAND ON L'A TRAITÉE. La planification vient de décaler le suivi pendant
    — cette touche comprise — jusqu'après la visite
    (``suspendre_plan_jusqu_apres_visite``, un déplacement du MOTEUR) ; close
    telle quelle, la touche se lisait due APRÈS la visite, « traitée en
    avance », et le contrôle du suivi la jugeait sur un jour à venir.
    ``echeance_avant`` = ``(due_at, due_date, due_initial_at)`` lus par
    l'appelant AVANT la planification : quand CETTE fonction clôt la touche,
    ces trois colonnes — et elles seules (UPDATE borné) — sont rétablies,
    juste avant la clôture (la ligne de chatter dit ainsi la vraie
    échéance). Ni ``cadence_depart``, ni la suite du plan (décalée après la
    visite), ni la naissance d'une touche ne changent : « visite acceptée »
    n'en fait naître aucune (``issue_fait_naitre_la_suite``)."""
    etape.refresh_from_db()
    note = str(note or '').strip()
    if (etape.statut == RelanceEtape.Statut.A_FAIRE
            and not est_etape(etape, CLE_CONFIRMATION, CLE_DEBRIEF)):
        if echeance_avant is not None:
            _retablir_echeance_traitee(etape, echeance_avant)
        return marquer_etape_relance(
            etape, user, RelanceEtape.Statut.FAIT, note=note,
            outcome=OUTCOME_VISITE_ACCEPTEE)
    if note:
        libelle = (etape.libelle or '').strip() or etape.get_canal_display()
        activity.log_note(
            etape.lead, user,
            f'Visite planifiée depuis l’étape « {libelle} » — note : {note}')
    return etape


def _retablir_echeance_traitee(etape, echeance):
    """COCKPIT-CONTRÔLE B8 — rétablit ``(due_at, due_date, due_initial_at)``
    sur ``etape`` : un UPDATE borné à ces trois colonnes (jamais un ``save``
    complet qui réécrirait le reste), puis l'instance en mémoire suit."""
    due_at, due_date, due_initial_at = echeance
    RelanceEtape.objects.filter(pk=etape.pk).update(
        due_at=due_at, due_date=due_date, due_initial_at=due_initial_at)
    etape.due_at = due_at
    etape.due_date = due_date
    etape.due_initial_at = due_initial_at


def annuler_rendez_vous_du_lead(lead, user, *, motif='',
                                vider_date_passee=True):
    """SUIVI E4/E21 (30/09/2026) — le rendez-vous de visite EN ATTENTE du
    lead est annulé : côté visites par LEUR service
    (``apps.visites.services.annuler_rendez_vous`` — frontière M3, jamais
    ``visites.models``), côté fiche ``Lead.visite_prevue_le`` est vidé.

    BEST-EFFORT : un module visites en échec ne bloque jamais le geste
    commercial qui a demandé l'annulation (il est déjà acté). Avec
    ``vider_date_passee=False``, une date de visite PASSÉE (la visite a eu
    lieu, ou non) reste sur la fiche : seul un rendez-vous à venir est une
    promesse faite au technicien. Renvoie le nombre de rendez-vous annulés
    dans le module visites."""
    annules = 0
    try:
        from apps.visites.services import annuler_rendez_vous

        annules = annuler_rendez_vous(lead, user, motif=motif)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'SUIVI E21 : rendez-vous de visite non annulé (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
    jour = getattr(lead, 'visite_prevue_le', None)
    if jour is not None and (vider_date_passee
                             or jour >= aujourd_hui_local()):
        lead.visite_prevue_le = None
        lead.save(update_fields=['visite_prevue_le'])
    return annules


#: SUIVI E21 — les causes écrites (visite, message au technicien, chatter)
#: quand un arrêt de tout le suivi annule aussi le rendez-vous.
CAUSE_RDV_REFUS = 'le client a refusé'
CAUSE_RDV_NE_PLUS_CONTACTER = 'le client ne veut plus être contacté'


def cause_rdv_perdu(motif=''):
    """SUIVI E21 — la cause d'annulation d'un rendez-vous quand le lead
    passe PERDU (avec son motif s'il en a un)."""
    motif = str(motif or '').strip()
    return f'dossier perdu ({motif})' if motif else 'dossier perdu'


def annuler_rendez_vous_sur_arret(lead, user, *, cause):
    """SUIVI E21 (30/09/2026) — quand TOUT s'arrête (« Refus », « Perdu »,
    « Ne plus me contacter »), le rendez-vous de visite EN ATTENTE s'annule
    aussi.

    Avant, les relances s'arrêtaient mais la visite planifiée restait dans le
    module Visites : le technicien se serait déplacé chez un client qui venait
    de refuser. Même porte que E4 (``annuler_rendez_vous_du_lead``), avec
    ``vider_date_passee=False`` : une visite PASSÉE reste sur la fiche, c'est
    de l'historique. UNE note système le dit — seulement quand un rendez-vous
    a RÉELLEMENT été annulé (idempotent : un second arrêt ne trouve plus rien
    et n'écrit rien).

    BEST-EFFORT : ne lève jamais — l'arrêt qui l'a demandé est déjà acté.
    Renvoie le nombre de rendez-vous annulés dans le module visites."""
    try:
        if getattr(lead, 'pk', None):
            lead.refresh_from_db(fields=['visite_prevue_le'])
        jour = lead.visite_prevue_le
        annules = annuler_rendez_vous_du_lead(
            lead, user, motif=cause, vider_date_passee=False)
        date_retiree = jour is not None and lead.visite_prevue_le is None
        if annules or date_retiree:
            quand = f' du {jour:%d/%m/%Y}' if date_retiree else ''
            prevenu = ' (le technicien est prévenu)' if annules else ''
            # Note SYSTÈME (``user=None``) : dire ce que le moteur a fait
            # n'est pas un contact (garde QJ7).
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body=(f'Rendez-vous de visite{quand} annulé{prevenu} : '
                      f'{cause}.'))
        return annules
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'SUIVI E21 : rendez-vous non annulé à l’arrêt (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
        return 0


#: Longueur maximale de la note de retour terrain posée au chatter. Un
#: technicien consciencieux peut écrire beaucoup ; l'historique d'un lead doit
#: rester lisible. Le texte intégral reste sur la visite, jamais perdu.
RETOUR_VISITE_MAX = 1500


def _lignes_qualification(qualification):
    """Les lignes « Qualification : … » / « Conseil : … », ou une liste vide.

    Le vocabulaire et les libellés vivent dans ``apps.visites.qualification``
    (frontière M3 : on lit le module de l'app qui POSSÈDE ce vocabulaire, on ne
    redéclare pas une table de libellés qui dériverait au premier
    reformulage du fondateur). Best-effort : une qualification illisible ne
    fait jamais perdre le retour terrain qui la suit."""
    if not qualification:
        return []
    try:
        from apps.visites.selectors import conseil, phrase

        return [ligne for ligne in (phrase(qualification),
                                    conseil(qualification)) if ligne]
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning('VISITE-CADENCE: qualification illisible',
                       exc_info=True)
        return []


def composer_note_retour_visite(retour, auteur='', qualification=None):
    """La note de chatter du RETOUR TERRAIN, tronquée à ``RETOUR_VISITE_MAX``.

    La QUALIFICATION vient EN TÊTE (amendement fondateur n°2 du 15/09/2026) :
    c'est la ligne qu'un responsable lit en diagonale avant de rappeler —
    « Client chaud · Le devis convient · Décide seul · … ». Le conseil de
    closing la suit, puis le retour libre.

    Le texte libre du technicien EST l'information : « le tableau est saturé »,
    « accès par le garage » — rien de tout cela n'entre dans un récap de
    mesures, et c'est pourtant ce que le commercial doit lire avant de
    rappeler. Un retour muet le DIT (« sans commentaire ») plutôt que de poser
    une note vide qui ferait croire à un oubli d'affichage."""
    entete = 'Visite technique terminée'
    entete += f' par {auteur}.' if auteur else '.'
    notes = (retour or {}).get('notes') or ''
    lignes = _lignes_qualification(qualification)
    if notes.strip():
        lignes.append(f'{entete} Retour terrain : « {notes.strip()} »')
    else:
        lignes.append(f'{entete} Aucun commentaire écrit sur place.')
    for photo in (retour or {}).get('commentaires_photos') or []:
        commentaire = (photo.get('commentaire') or '').strip()
        if not commentaire:
            continue
        lignes.append(f'— {photo.get("slot") or ""} : {commentaire}')
    corps = '\n'.join(lignes)
    if len(corps) > RETOUR_VISITE_MAX:
        corps = corps[:RETOUR_VISITE_MAX - 1].rstrip() + '…'
    return corps


def _plan_du_debrief(qualification, lead=None):
    """``(clé, jours, rappel_choisi)`` du débrief, dictés par la
    qualification du terrain.

    Sans qualification, le comportement historique : « rappeler le client »,
    DEMAIN. Avec elle, c'est le terrain qui décide — il a vu le client :

    * le MOMENT vient de ``rappel`` (demain matin/soir ⇒ demain ; cette
      semaine ⇒ trois jours : le client a dit qu'il ne fallait pas le presser) ;
    * la NATURE vient de ``devis`` : à modifier ou à refaire ⇒ la prochaine
      chose à faire n'est plus de rappeler pour conclure, c'est de PRÉPARER le
      devis corrigé, et le libellé de l'étape le dit.

    Le troisième élément du tuple dit si le MOMENT est un choix EXPLICITE du
    terrain : lui seul autorise à déplacer un débrief déjà posé dans les deux
    sens (voir ``appliquer_retour_visite``).

    Lecture du vocabulaire par le module de l'app qui le possède (frontière
    M3). Best-effort : une qualification illisible retombe sur le défaut.

    PARAM-CADENCE — la NATURE est une clé (``debrief`` / ``devis_modifie``)
    et le moment PAR DÉFAUT est le ``delai_jours`` de son barreau « Visite
    technique » (demain par défaut) ; un moment choisi par le terrain le
    remplace."""
    def _defaut(cle):
        if lead is None:
            return gabarit_relance.barreau_par_defaut(
                cadence_config.CADENCE_DE_LA_CLE[cle], cle)['delai_jours']
        return _config_visite(lead, cle)['delai_jours']

    if not qualification:
        return CLE_DEBRIEF, _defaut(CLE_DEBRIEF), False
    try:
        from apps.visites.selectors import (
            devis_a_reprendre, jours_avant_rappel, rappel_explicite,
        )

        cle = (CLE_DEVIS_MODIFIE if devis_a_reprendre(qualification)
               else CLE_DEBRIEF)
        return (cle, jours_avant_rappel(qualification, defaut=_defaut(cle)),
                rappel_explicite(qualification))
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning('VISITE-CADENCE: plan de débrief non déduit',
                       exc_info=True)
        return CLE_DEBRIEF, _defaut(CLE_DEBRIEF), False


def _debrief_ouvert(lead):
    """L'étape de débrief encore à faire, quel que soit son LIBELLÉ.

    Elle est UNE : la chercher sous ses deux CLÉS est ce qui empêche une
    re-qualification (« finalement le devis est à modifier ») de laisser deux
    débriefs ouverts dans la file."""
    for cle in _CLES_DEBRIEF:
        etape = _etape_visite_ouverte(lead, cle)
        if etape is not None:
            return etape
    return None


def _requalifier_debrief(etape, cle, config=None):
    """RENOMME l'étape de débrief vers la nature ``cle`` (clé ET libellé
    configuré) plutôt que de la recréer : c'est la MÊME étape, dont la nature
    vient d'être précisée. No-op si elle l'a déjà."""
    if cle_de(etape) == cle:
        return etape
    config = config or _config_visite(etape.lead, cle)
    etape.cle = cle
    etape.libelle = config['libelle']
    etape.save(update_fields=['cle', 'libelle'])
    return etape


def appliquer_retour_visite(lead, user, retour, auteur='',
                            qualification=None):
    """Le technicien est reparti : son retour redescend, et on rappelle.

    1. UNE note de chatter portant, dans cet ordre, la QUALIFICATION du client
       (une ligne lisible en diagonale), le conseil de closing s'il y en a un,
       puis le TEXTE LIBRE du terrain (notes + un commentaire de photo par
       ligne, le tout tronqué) ;
    2. ``Lead.visite_effectuee`` est posé — via ``ecrire_retour_lead_visite``,
       donc avec ses garanties : idempotent, et une note écrite à la main dans
       ``visite_notes`` n'est JAMAIS écrasée ;
    3. le DÉBRIEF est calé sur ce que le terrain a rapporté
       (``_plan_du_debrief``) : DEMAIN par défaut, dans trois jours si le
       client a demandé « cette semaine », et son libellé devient « préparer le
       devis modifié » quand le devis doit être repris. Il existait déjà (posé
       à la planification) ? Il est RENOMMÉ si besoin et AVANCÉ seulement s'il
       était plus loin — jamais repoussé, jamais dupliqué. Il n'existe pas
       (visite faite sans avoir été planifiée dans l'ERP) ? On le pose, à
       condition que le lead soit encore relançable ;
    4. CAD28 — la reprise du PROTOCOLE est recalée sur CE retour plutôt que
       sur la date prévue de la visite (``reprendre_plan_apres_retour_visite``),
       et jamais tirée en avant.

    VISITE SANS DEVIS (décision fondateur du 24/09/2026 — « et même après ça
    rien ne se passe »). Quand aucun devis n'est parti (``aucun_devis_parti``)
    et que le terrain ne dit pas « devis à modifier / à refaire », la suite du
    retour n'est PAS un débrief « rappeler le client » — il n'y a encore rien
    à conclure — mais la tâche de PRODUCTION « Préparer et envoyer le devis
    (ou fixer un rappel) » (``poser_etape_preparer_devis``) : demain, ou au
    moment que le terrain a convenu devant le client. Le débrief posé à la
    planification est ANNULÉ (statut moteur), et la note du retour — elle
    seule, jamais une seconde — dit la suite et sa date. Renvoie alors
    l'étape devis.

    ``STAGES.py`` n'est pas touché. Renvoie l'étape de débrief, ou ``None``."""
    corps = composer_note_retour_visite(retour, auteur=auteur,
                                        qualification=qualification)
    # Relevé du 25/09/2026 — la visite a EU LIEU : une « Confirmer la visite
    # (veille) » encore ouverte (retour saisi avant que la confirmation soit
    # cochée) n'a plus d'objet. Annulée par le moteur (CKP1, jamais « sautée
    # par un humain »), comme le filet « planifier » l'est à la planification.
    lead.relance_etapes.filter(
        q_etape(CLE_CONFIRMATION),
        statut=RelanceEtape.Statut.A_FAIRE).update(
            statut=RelanceEtape.Statut.ANNULEE,
            note=NOTE_CONFIRMATION_VISITE_FAITE, traite_par=None,
            traite_le=timezone.now())
    cle, jours, rappel_choisi = _plan_du_debrief(qualification, lead)
    if (cle == CLE_DEBRIEF and _lead_relancable(lead)
            and aucun_devis_parti(lead)):
        etape = poser_etape_preparer_devis(
            lead, origine='retour de visite technique', user=user,
            jours=jours if rappel_choisi else None,
            journaliser=False)
        if etape is not None:
            debrief = _debrief_ouvert(lead)
            if debrief is not None:
                RelanceEtape.objects.filter(pk=debrief.pk).update(
                    statut=RelanceEtape.Statut.ANNULEE,
                    note=NOTE_RETOUR_SANS_DEVIS, traite_par=None,
                    traite_le=timezone.now())
            corps += ('\nSuite : préparer et envoyer le devis (pour le '
                      f'{etape.due_date:%d/%m/%Y}).')
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE, body=corps)
            ecrire_retour_lead_visite(lead, '')
            _recaler_file(lead, user)
            return etape
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=corps)
    ecrire_retour_lead_visite(lead, '')

    if not _lead_relancable(lead):
        return None
    # CAD28 — la reprise du protocole part d'ICI, du retour réellement saisi,
    # et plus de la date PRÉVUE de la visite (voir
    # ``reprendre_plan_apres_retour_visite``). Best-effort : un recalage
    # impossible ne doit jamais faire échouer la redescente du terrain.
    try:
        reprendre_plan_apres_retour_visite(lead, user)
    except Exception:  # noqa: BLE001 — jamais bloquant pour le retour terrain
        logger.warning(
            'CAD28: reprise du plan non recalée sur le retour (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
    vise = aujourd_hui_local() + datetime.timedelta(days=jours)
    config = _config_visite(lead, cle)
    existante = _debrief_ouvert(lead)
    if existante is not None:
        # RENOMMER plutôt que recréer : c'est la MÊME étape, dont la nature
        # vient d'être précisée par le terrain.
        _requalifier_debrief(existante, cle, config)
    if (existante is not None and existante.due_date <= vise
            and not rappel_choisi):
        # Sans choix EXPLICITE du terrain, un débrief déjà dû plus tôt n'est
        # jamais repoussé. Quand le terrain a convenu d'un moment DEVANT le
        # client (« cette semaine » = ne pas le presser), c'est SON choix qui
        # gagne — dans les deux sens : l'écran du wizard promet « le rappel
        # de closing se calera dessus », et rappeler avant le moment convenu
        # serait exactement la pression que le client a refusée.
        return existante
    etape = _poser_etape_visite(
        lead, cle=cle, ordre=VISITE_ORDRE_DEBRIEF, quand=vise,
        devis_id=_devis_id_de_la_cadence(lead), config=config)
    _recaler_file(lead, user)
    return etape


# ── VT1 — CHATTER AUTOMATIQUE DE LA VISITE TECHNIQUE TERRAIN ─────────────────
#
# Le chatter du lead (``LeadActivity``) est le journal COMMUN de tout ce qui
# arrive à un lead : la visite technique y écrit ses quatre moments — création,
# terminaison, feu vert, renvoi — plutôt que d'ouvrir un second historique.
# L'auteur et la société viennent TOUJOURS du serveur (jamais du corps de
# requête), comme le reste du chatter.


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


# ── NTDATA18 — FUSION SUPERVISÉE DE CLIENTS ─────────────────────────────────
#
# Sur le modèle de `merge_leads` ci-dessus, mais pour `Client` : le détecteur
# (`dataquality.services.doublons_clients`) PROPOSE, un humain DÉCIDE, et cette
# fonction exécute. Jamais de fusion automatique.
#
# TROIS GARANTIES DURES :
#
# 1. AUCUNE SUPPRESSION. Le doublon n'est jamais effacé : il est NEUTRALISÉ.
#    `Client` ne porte pas (encore) de drapeau d'archivage — ajouter une
#    colonne supposerait une migration `crm`, hors du périmètre de cette
#    tâche. On utilise donc le mécanisme EXISTANT prévu pour ça :
#    `avertissement_bloquant` (une garde serveur refuse dès lors l'acceptation
#    et la facturation d'un devis pour ce client, patron XFAC28) + un
#    avertissement lisible, + un marqueur `custom_data['fusionne_dans']` qui
#    trace la cible et la date. La fiche reste consultable, son historique
#    intact, et la fusion est intégralement réversible à la main.
#
# 2. AUCUN ORPHELIN. Tout ce qui pointait le doublon pointe le survivant —
#    non pas une liste de quatre modèles écrite à la main (le dépôt compte
#    plus de trente FK vers `Client`), mais le parcours des relations inverses
#    déclarées par Django (`core.merge.repointer_relations`, la MÊME mécanique
#    que la fusion fournisseur/produit de `stock` — jamais une seconde
#    implémentation). Chaque relation est repointée dans son PROPRE point de
#    sauvegarde : une contrainte d'unicité qui refuse (le survivant a déjà sa
#    limite de crédit, par exemple) annule CETTE relation seule et le rapport
#    la NOMME, au lieu de faire échouer toute la fusion en silence.
#
# 3. AUCUN IMPORT D'APP ÉTRANGÈRE. Le parcours passe par l'API `_meta` de
#    Django, donc `crm` n'importe ni `ventes`, ni `facturation`, ni
#    `installations`, ni `sav`.

#: Champs du client dont une valeur VIDE chez le survivant est complétée
#: depuis un doublon (jamais l'inverse : on n'écrase jamais une valeur saisie).
_MERGE_CLIENT_FILL_FIELDS = (
    'prenom', 'email', 'telephone', 'adresse', 'cin', 'ice', 'if_fiscal',
    'rc', 'langue_document', 'delai_paiement_jours',
)

#: Clé où l'e-mail CÉDÉ au survivant est conservé sur le doublon neutralisé.
#: Même patron (et même esprit « rien n'est perdu ») que la migration CRX24
#: ``crm/0086_crx24_client_email_unique_ci``.
CLE_EMAIL_AVANT_FUSION = 'email_avant_fusion'


def merge_clients(survivor, others, user):
    """Fusionne ``others`` dans ``survivor`` sans perte ni suppression.

    Renvoie un rapport ::

        {'survivant': <Client>, 'absorbes': [ids],
         'repointes': {'<app.Modele.champ>': n, …},
         'non_repointes': [{'relation': …, 'motif': …}, …]}

    ``non_repointes`` n'est PAS un échec silencieux : c'est la liste, nommée,
    de ce qu'un humain doit trancher (typiquement une contrainte d'unicité
    déjà occupée chez le survivant).
    """
    from django.db import transaction
    from django.utils import timezone

    from core.merge import completer_champs_vides, repointer_relations

    others = [o for o in others
              if o.pk != survivor.pk and o.company_id == survivor.company_id]
    rapport = {'survivant': survivor, 'absorbes': [],
               'repointes': {}, 'non_repointes': []}
    if not others:
        return rapport

    with transaction.atomic():
        for absorbed in others:
            repointes, non_repointes = repointer_relations(absorbed, survivor)
            for etiquette, n in repointes.items():
                rapport['repointes'][etiquette] = (
                    rapport['repointes'].get(etiquette, 0) + n)
            rapport['non_repointes'].extend(non_repointes)

            # Compléter les champs VIDES du survivant (jamais écraser).
            completes = completer_champs_vides(survivor, absorbed,
                                               _MERGE_CLIENT_FILL_FIELDS)

            # Neutraliser le doublon — jamais le supprimer.
            marqueur = dict(absorbed.custom_data or {})
            marqueur['fusionne_dans'] = survivor.pk
            marqueur['fusionne_le'] = timezone.now().isoformat()
            marqueur['fusionne_par'] = getattr(user, 'username', '') or ''
            champs_absorbe = ['custom_data', 'avertissement_bloquant',
                              'avertissement_vente', 'date_modification']
            if 'email' in completes:
                # CRX24 — l'e-mail client est UNIQUE par société (index
                # fonctionnel insensible à la casse
                # ``crx24_client_email_unique_ci``). Le doublon n'étant JAMAIS
                # supprimé, il faut qu'il LIBÈRE l'e-mail qu'il vient de céder
                # au survivant : sinon les deux fiches le portent et
                # PostgreSQL refuse le ``survivor.save()`` final — la fusion
                # entière échouait alors sur une IntegrityError. Rien n'est
                # perdu : la valeur est conservée sur le doublon dans
                # ``custom_data`` (même patron que la migration CRX24).
                marqueur[CLE_EMAIL_AVANT_FUSION] = absorbed.email
                absorbed.email = None
                champs_absorbe.append('email')
            absorbed.custom_data = marqueur
            absorbed.avertissement_bloquant = True
            absorbed.avertissement_vente = (
                'Fiche fusionnée dans le client #%s — ne plus utiliser.'
                % survivor.pk)
            absorbed.save(update_fields=champs_absorbe)
            rapport['absorbes'].append(absorbed.pk)

            _journaliser_fusion_client(survivor, absorbed, user)

        survivor.save()
    return rapport


def _journaliser_fusion_client(survivor, absorbed, user):
    """Trace la fusion dans le chatter GÉNÉRIQUE (``records.Activity``, ARC8).

    Best-effort : une trace manquante ne doit jamais annuler une fusion déjà
    appliquée — mais elle n'est pas avalée en silence non plus (log).
    """
    try:
        from apps.records.services import log_note
        log_note(
            survivor, user,
            'Fusion : le client « %s » (#%s) a été absorbé dans cette fiche.'
            % (absorbed.nom, absorbed.pk),
            company=survivor.company)
        log_note(
            absorbed, user,
            'Fiche fusionnée dans le client #%s — conservée en lecture, '
            'bloquée à la vente.' % survivor.pk,
            company=absorbed.company)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception(
            'NTDATA18 : chatter de fusion non écrit (client #%s → #%s)',
            absorbed.pk, survivor.pk)


def clients_par_ids(company, ids):
    """NTDATA18 — point d'entrée cross-app : les clients d'une société par id.

    Utilisé par le module dataquality pour charger un groupe de doublons
    AVANT de demander la fusion — jamais un import de ``crm.models`` là-bas. Le
    filtre société est POSÉ ICI : une autre app ne peut pas charger le client
    d'un autre tenant en passant un id deviné.
    """
    return list(Client.objects.filter(company=company, pk__in=list(ids or [])))


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

#: L'intention de financement qui déclenche la validité longue. Valeur de
#: ``crm.Lead.FinancingIntent.CREDIT`` — lue en littéral ici pour ne pas
#: importer les modèles depuis une fonction appelée à chaud.
FINANCEMENT_CREDIT = 'credit'


def lead_finance_a_credit(lead):
    """Le lead a-t-il DÉCLARÉ financer à crédit ?

    « Pas encore décidé » et « comptant » ne déclenchent rien : on n'allonge
    pas une validité sur une supposition.
    """
    return (getattr(lead, 'financing_intent', None) or '') == \
        FINANCEMENT_CREDIT


def lead_dossier_subvention_en_instruction(lead):
    """AGR523 — le dossier de subvention du lead est-il DÉPOSÉ (en
    instruction) ? « À déposer », vide, accordé ou refusé : non."""
    return (getattr(lead, 'dossier_subvention', None) or '') == 'depose'


#: AGR523 — la fin de la note d'historique quand la validité vient du
#: dossier de subvention en instruction.
MOTIF_VALIDITE_SUBVENTION = ('dossier de subvention en instruction (réglage '
                             'société)')
#: CIQ510 — la fin de la note quand la validité vient d'une attente d'accord.
MOTIF_VALIDITE_ATTENTE = "en attente d'un accord (réglage société)"

#: CIQ510 (contrat CIQ1 ``lead_pro.json``, ``financing_intent``) — les
#: financements PRO déclarés qui reçoivent la règle « financé » : crédit
#: bancaire / offre de financement / ligne verte (``credit``) et crédit-bail
#: (``credit_bail``, valeur interne). Comptant et indécis : jamais.
FINANCEMENTS_PRO = ('credit', 'credit_bail')
#: Les segments PRO (``Lead.type_installation``).
SEGMENTS_PRO = ('commercial', 'industriel')


def lead_financement_pro_declare(lead):
    """CIQ510 — un lead commercial/industriel a-t-il DÉCLARÉ un financement
    pro (contrat CIQ1) ? Jamais sur une supposition."""
    return ((getattr(lead, 'type_installation', None) or '') in SEGMENTS_PRO
            and (getattr(lead, 'financing_intent', None) or '')
            in FINANCEMENTS_PRO)


def lead_en_attente_d_accord(lead):
    """CIQ510 — le lead porte-t-il une étiquette d'attente posée par la
    réponse « En attente d'un accord » (CIQ508, une par raison) ?"""
    return any(_lead_porte_tag(lead, tag)
               for tag in ETIQUETTES_RAISON_ATTENTE)


def _validite_selon_financement(lead, devis, date_fin_de_suivi):
    """La date de validité à POSER sur ce devis.

    Comptant / indécis : la fin du plan de suivi (comportement VALID1
    inchangé — une date dérivée des cadences du fondateur, jamais inventée).
    Crédit : la date du réglage société, si elle est PLUS LOINTAINE — on ne
    raccourcit jamais une validité déjà plus longue, et une société qui règle
    sa validité à 10 jours ne se retrouve pas avec un devis financé qui expire
    AVANT la fin de son propre suivi.
    """
    # AGR523 — un dossier de subvention DÉPOSÉ (en instruction) reçoit la
    # MÊME règle que le crédit : le réglage société, s'il est plus lointain.
    # Aucun nouveau nombre, aucune durée propre à la FDA.
    # CIQ510 — même règle pour un financement PRO déclaré (contrat CIQ1) et
    # pour un lead qui porte une étiquette d'attente d'accord (CIQ508).
    if not (lead_finance_a_credit(lead)
            or lead_financement_pro_declare(lead)
            or lead_en_attente_d_accord(lead)
            or lead_dossier_subvention_en_instruction(lead)):
        return date_fin_de_suivi
    try:
        from apps.ventes.services import date_validite_credit
        candidate = date_validite_credit(devis)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD57 : validité crédit illisible (devis #%s)',
            getattr(devis, 'pk', '?'), exc_info=True)
        return date_fin_de_suivi
    if candidate is None:
        return date_fin_de_suivi
    if date_fin_de_suivi is None:
        return candidate
    return max(candidate, date_fin_de_suivi)


# ── CAD-E ── CAD59 — le message J9 et le PDF disent la MÊME date ───────────
#
# Le moteur de devis a un repli documenté (``date_validite``, sinon date de
# création + le réglage société ``quote_validity_days``) alors que
# ``message_pour_etape`` ne lisait QUE ``devis.date_validite`` : vide, MRY13
# supprimait la phrase entière et le WhatsApp enchaînait sur « Après, je dois
# revalider les prix… » pendant que le PDF affichait « valable jusqu'au X ».
# Deux voix contradictoires sur le même dossier.
#
# Règle #4 respectée : on ne touche PAS au moteur de rendu — on lit la MÊME
# règle, par la surface de lecture de ventes.

def _date_validite_comme_le_pdf(devis):
    """La date de validité que le PDF affiche, ou ``None``.

    ``None`` fait OMETTRE la phrase (MRY13) — c'est le comportement voulu
    quand la date est indéterminable : jamais un blanc, jamais une date
    inventée. Le chemin ``devis=None`` (TREADMILL-1538) reste couvert par
    CAD55.
    """
    if devis is None:
        return None
    try:
        from apps.ventes.selectors import date_validite_effective
        return date_validite_effective(devis)
    except Exception:  # noqa: BLE001 — jamais bloquant, jamais inventé
        logger.warning(
            'CAD59 : validité illisible (devis #%s)',
            getattr(devis, 'pk', '?'), exc_info=True)
        return getattr(devis, 'date_validite', None)


# ── CAD-E ── CAD58 — plus aucune touche de cadence n'est une VISITE ────────
#
# [TRANCHÉ 21/09/2026] Le barreau 5 de la cadence générique portait le canal
# `visite` à J+35 sans poser AUCUNE condition de devis, alors que la décision
# fondateur du 15/09 est « visite technique JAMAIS avant le devis, proposée
# après ». Le gabarit par défaut a changé (J+35 = appel), mais une société
# seedée AVANT cette date garde sa ligne en base : `seed_cadence` ne retouche
# jamais un barreau existant (et c'est une bonne règle — le fondateur peut
# personnaliser). On normalise donc à la MATÉRIALISATION, là où la touche
# devient réelle : un gabarit legacy `visite` pose un APPEL.
#
# Ni le nombre, ni l'ordre, ni le J+N des barreaux ne changent : seul le canal
# du dernier. La visite technique garde son chemin propre (proposition après
# devis, VISITE-CADENCE du 15/09) — ce n'est pas un barreau de protocole.

#: Le canal retiré des cadences. Valeur de ``parametres.CanalRelance.VISITE``,
#: reprise en littéral (ce module ne dépend d'aucun modèle de référentiel).
CANAL_VISITE = 'visite'

#: Ce qu'une touche legacy `visite` devient : un appel. C'est le canal le plus
#: prudent (fenêtre d'appel, pause du vendredi respectée) et c'est la décision.
CANAL_VISITE_REMPLACEMENT = 'appel'


def _canal_effectif(gabarit):
    """Le canal RÉEL d'une touche de cadence — jamais `visite` (CAD58).

    `appel` par défaut, jamais deviné. Un gabarit encore en `visite` (société
    seedée avant le 21/09/2026) est normalisé ici plutôt que refusé : la
    touche existe, elle doit juste cesser d'annoncer une visite.
    """
    canal = getattr(gabarit, 'canal', None) or CANAL_VISITE_REMPLACEMENT
    if canal == CANAL_VISITE:
        return CANAL_VISITE_REMPLACEMENT
    return canal


# ── CAD-J ── CAD124 — pas d'axe segment dans le gabarit de cadence ────────
#
# [TRANCHÉ 21/09/2026] `calculer_echeances_cadence` ne lit AUCUN segment, et
# ce n'est pas un oubli : le gabarit de cadence reste aveugle au
# `type_installation`. Le CRM s'en sert ailleurs — pour scorer
# (`apps/crm/scoring.py`) et pour exiger les bons champs au devis
# (`apps/ventes/devis_auto.py`) — mais l'ordonnancement des touches, lui, est
# le MÊME protocole pour tout le monde.
#
# Ce que les segments changent vraiment, c'est le TEXTE : variantes par
# exception sur les clés qui mentent (CAD126) et playbook conditionné sur
# `{type_installation}` (CAD125). Les deux passent par des mécanismes qui
# existent déjà — zéro migration, zéro sélecteur de plus, zéro barreau ajouté.
#
# La décision se rouvrira sur le VOLUME par segment (comptage CADM7), pas
# avant. Voir aussi le commentaire jumeau dans
# `apps/parametres/models_relance.py` (clé `unique_together` du gabarit).

#: CAD124 — la trace lisible de la décision, pour un futur audit qui se
#: demanderait pourquoi le gabarit ignore le segment.
CAD124_PAS_D_AXE_SEGMENT = (
    'pas d’axe segment dans le gabarit de cadence — décision du 21/09/2026'
)


# ── CAD-J ── CAD125 — le dossier 82-21 et le dossier FDA ont une parole ────
#
# `Lead.regularisation_8221` est capté, LU par le scoring (+5 points) — et par
# aucune logique de message ni de touche ; aucune des clés de relance ne
# parlait d'une subvention ou d'un dossier institutionnel, alors que le
# résidentiel a son équivalent avec `j6_garanties`.
#
# Le remède n'ajoute NI barreau NI migration de cadence : c'est une TÂCHE de
# `Playbook`, conditionnée sur `{type_installation}` — le mécanisme existe et
# est déjà évalué contre ce contexte (`_playbook_correspond_au_lead`).
#
# Contexte daté (pour la docstring, jamais pour le client) : le décret
# d'application de la loi 82-21 est en vigueur depuis le 09/06/2026 (BO 7489).
# GARDE-FOU « zéro chiffre inventé » : les TEXTES ne citent AUCUN montant,
# AUCUN plafond, AUCUNE fenêtre de dépôt (le plafond FDA et la fenêtre du
# round 2 sont introuvables sur leur source), AUCUN nombre de régimes.

#: Les deux playbooks de segment, avec leur condition et leur tâche unique.
#: `stage` vient de STAGES.py (règle #2), jamais d'un littéral.
PLAYBOOKS_SEGMENT_CAD125 = (
    {
        # Le NOM reste la clé d'idempotence du seed (jamais renommé : un
        # nouveau nom doublerait le playbook des sociétés existantes).
        'nom': 'Segment — dossier d’autoproduction 82-21',
        'segments': ('industriel', 'commercial'),
        # CIQ517 (D-CIQ-6) — seulement un site MT (contrat CIQ1), une
        # régularisation 82-21 ou un client qui veut revendre : AU MOINS UN
        # de ces critères. Un commerce en BT ne reçoit plus la question
        # (Q9/CAD163 : on n'aborde jamais la loi 82-21 spontanément).
        'criteres_un_parmi': (
            ('tension_raccordement', 'mt'),
            ('regularisation_8221', True),
            ('objectif_projet', 'injection_8221'),
        ),
        'cle_message': 'dossier_8221',
        'tache': ('Demander où en sont le raccordement et les autorisations '
                  'du site (texte « dossier_8221 » au catalogue des '
                  'messages)'),
    },
    {
        'nom': 'Segment — dossier de subvention agricole (FDA)',
        'segments': ('agricole',),
        # AGR525 — réservé à la pompe AU BUTANE : le pilote FDA vise le
        # remplacement du butane (Guide FDA 2024, D-AGR-6). Un exploitant au
        # gasoil ou sur le réseau ne reçoit pas la question.
        'criteres': (('pompe_alim_actuelle', 'butane'),),
        'cle_message': 'dossier_fda',
        'tache': ('Demander où en est le dossier de subvention agricole FDA '
                  '(texte « dossier_fda » au catalogue des messages)'),
    },
)


def _condition_playbook_segment(entree):
    """La condition `core.rules` d'un playbook de segment : ses segments, ET
    ses critères supplémentaires (AGR525, tous requis) ou alternatifs
    (CIQ517, ``criteres_un_parmi`` : au moins un) quand il en porte."""
    criteres = entree.get('criteres') or ()
    un_parmi = entree.get('criteres_un_parmi') or ()
    if not (criteres or un_parmi):
        return _condition_segment(entree['segments'])
    if un_parmi:
        return {
            'op': 'and',
            'conditions': [
                _condition_segment(entree['segments']),
                {'op': 'or', 'conditions': [
                    {'field': champ, 'operator': 'eq', 'value': valeur}
                    for champ, valeur in un_parmi]},
            ],
        }
    feuilles = [
        {'field': 'type_installation', 'operator': 'eq', 'value': segment}
        for segment in entree['segments']]
    segment = (feuilles[0] if len(feuilles) == 1
               else {'op': 'or', 'conditions': feuilles})
    return {
        'op': 'and',
        'conditions': [segment] + [
            {'field': champ, 'operator': 'eq', 'value': valeur}
            for champ, valeur in criteres],
    }


def _lead_satisfait_criteres(lead, entree):
    un_parmi = entree.get('criteres_un_parmi') or ()
    if un_parmi and not any(getattr(lead, champ, None) == valeur
                            for champ, valeur in un_parmi):
        return False
    return all(getattr(lead, champ, None) == valeur
               for champ, valeur in (entree.get('criteres') or ()))


def _condition_segment(segments):
    """L'arbre `core.rules` qui matche ces `type_installation` — et eux seuls.

    Un lead sans segment renseigné ne matche AUCUN des deux : on ne pose pas
    la question du dossier 82-21 à quelqu'un dont on ignore le marché.
    """
    return {
        'op': 'or',
        'conditions': [
            {'field': 'type_installation', 'operator': 'eq', 'value': segment}
            for segment in segments
        ],
    }


def seed_playbooks_segment(company, *, stage=None):
    """CAD125 — pose (idempotemment) les deux playbooks de segment.

    ``stage`` est l'étape du funnel qui porte la tâche ; par défaut celle de
    la prise de contact (``stages.CONTACTED``), importée de STAGES.py. Renvoie
    la liste des ``Playbook`` concernés (créés ou déjà présents).

    Additif et rejouable : ``get_or_create`` sur (société, nom), puis sur
    l'étape et la tâche. Un playbook que le fondateur aurait désactivé ou
    personnalisé n'est JAMAIS réécrit.
    """
    from . import stages as _stages
    from .models import Playbook, PlaybookEtape, PlaybookTache

    cible = stage or _stages.CONTACTED
    resultats = []
    for entree in PLAYBOOKS_SEGMENT_CAD125:
        playbook, cree = Playbook.objects.get_or_create(
            company=company, nom=entree['nom'],
            defaults={'actif': True,
                      'condition': _condition_playbook_segment(entree)})
        resultats.append(playbook)
        if not cree:
            continue
        etape, _ = PlaybookEtape.objects.get_or_create(
            playbook=playbook, stage=cible, defaults={'ordre': 0})
        PlaybookTache.objects.get_or_create(
            etape=etape, libelle=entree['tache'],
            defaults={'obligatoire': False, 'ordre': 0})
    return resultats


def cle_message_segment(lead):
    """La clé de message institutionnelle de CE lead, ou ``None``.

    Lecture pure : sert à l'écran qui propose le texte à copier, et au test.
    Un lead résidentiel — ou sans segment — n'en a AUCUNE : il a déjà
    `j6_garanties`, et on n'invente pas un dossier institutionnel pour lui.
    """
    segment = (getattr(lead, 'type_installation', None) or '').strip()
    if not segment:
        return None
    for entree in PLAYBOOKS_SEGMENT_CAD125:
        if segment in entree['segments']:
            # AGR525 — `dossier_fda` pour un agricole AU BUTANE seulement.
            if not _lead_satisfait_criteres(lead, entree):
                return None
            return entree['cle_message']
    return None


def rattraper_playbooks_pompe(lead):
    """AGR525 (3) — l'énergie de la pompe vient de passer à « butane » sur un
    lead agricole déjà à la prise de contact OU au-delà : les tâches des
    playbooks qui lisent ``pompe_alim_actuelle`` (le playbook FDA) sont
    générées pour les étapes déjà atteintes. Idempotent (``get_or_create`` sur
    (lead, tâche)) ; jamais au Froid ni à « Nouveau ». Renvoie les
    progressions créées."""
    if (getattr(lead, 'type_installation', None) or '') != 'agricole' \
            or getattr(lead, 'pompe_alim_actuelle', None) != 'butane':
        return []
    return _rattraper_playbooks_lisant(lead, ('pompe_alim_actuelle',))


#: CIQ517 — les champs du lead que lit le playbook « raccordement et
#: autorisations du site ».
CHAMPS_PLAYBOOK_8221 = ('tension_raccordement', 'regularisation_8221',
                        'objectif_projet')


def rattraper_playbooks_8221(lead):
    """CIQ517 — un lead commercial/industriel déjà à la prise de contact (ou
    au-delà) passe en MT, se déclare en régularisation 82-21 ou veut
    revendre : la tâche « raccordement et autorisations du site » est
    générée pour les étapes atteintes (idempotent, comme AGR525)."""
    if (getattr(lead, 'type_installation', None) or '') \
            not in ('commercial', 'industriel'):
        return []
    return _rattraper_playbooks_lisant(lead, CHAMPS_PLAYBOOK_8221)


def _rattraper_playbooks_lisant(lead, champs):
    """AGR525/CIQ517 — génère, pour les étapes DÉJÀ atteintes (prise de
    contact incluse, jamais Froid), les tâches des playbooks ACTIFS dont la
    condition lit l'un de ``champs`` ET matche le lead. Idempotent."""
    from . import stages as _stages
    from .models import LeadPlaybookProgress, Playbook

    ordre = [s for s in _stages.STAGES if s != _stages.COLD]
    if lead.stage not in ordre or ordre.index(lead.stage) < ordre.index(
            _stages.CONTACTED):
        return []
    atteintes = ordre[ordre.index(_stages.CONTACTED):ordre.index(lead.stage) + 1]
    import json as _json
    created = []
    for playbook in Playbook.objects.filter(company=lead.company, actif=True):
        condition = _json.dumps(playbook.condition or {})
        if not any(champ in condition for champ in champs):
            continue
        if not _playbook_correspond_au_lead(playbook, lead):
            continue
        for etape in playbook.etapes.filter(stage__in=atteintes) \
                .prefetch_related('taches'):
            for tache in etape.taches.all():
                progress, cree = LeadPlaybookProgress.objects.get_or_create(
                    lead=lead, tache=tache)
                if cree:
                    created.append(progress)
    return created


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


def _corps_pour_segment(corps, cle, lead, langue):
    """Le corps adapté au segment du lead — ou le corps reçu, inchangé.

    Trois garde-fous, dans cet ordre :

      * seuls le FRANÇAIS et la DARIJA ont des variantes (AGR511, D-AGR-11 :
        darija du pompage écrite phrase par phrase du FR validé, jamais une
        traduction automatique) ; ``en``/``ar`` restent inchangés ;
      * un texte que la société a PERSONNALISÉ n'est jamais remplacé — la
        variante ne s'applique qu'au texte encore au catalogue d'origine DE
        CETTE LANGUE (``MESSAGE_TEMPLATE_DEFAULTS`` en FR,
        ``MESSAGE_TEMPLATE_DEFAULTS_DARIJA`` en darija), même règle que
        `_REVEIL_CLES_SEEDEES` ;
      * un segment absent, inconnu ou résidentiel ne change RIEN.

    Best-effort : en cas de lecture impossible, le corps d'origine part.
    """
    langue = (langue or 'fr')
    if not corps or not cle or langue not in ('fr', 'darija'):
        return corps
    try:
        from apps.parametres.models_messages import (
            MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
            variante_segment,
        )
        variante = variante_segment(
            cle, getattr(lead, 'type_installation', None), langue)
        if not variante:
            return corps
        defauts = (MESSAGE_TEMPLATE_DEFAULTS if langue == 'fr'
                   else MESSAGE_TEMPLATE_DEFAULTS_DARIJA)
        if corps.strip() != (defauts.get(cle, '') or '').strip():
            return corps
        return variante
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning(
            'CAD126 : variante de segment illisible (clé %s)', cle,
            exc_info=True)
        return corps


# ── CAD-J ── CAD127 — le premier message dit la VÉRITÉ sur l'origine ──────
#
# « Vous venez de remplir notre formulaire » est FAUX pour la moitié des
# origines : la même cadence part pour un lead arrivé par téléphone, en
# boutique, par recommandation, depuis un salon, repositionné par l'écran de
# placement, ou né d'une conversation entrante (CTWA, livechat). Une première
# phrase fausse est exactement ce qui fait perdre la confiance au premier
# contact.
#
# `unique_together (company, cle)` interdit toute VARIANTE sur `identite` :
# les quatre textes sont donc des clés ADDITIVES, choisies ici d'après le
# canal DÉJÀ enregistré. Aucun barreau ajouté, aucune migration.
#
# Correction du round 2 : le ticket SAV n'est PAS une origine —
# `create_lead_depuis_ticket` ne démarre aucune cadence (vérifié sur les 8
# appelants de `demarrer_cadence_contact`).


def _nom_prescripteur(lead):
    """Le nom de la personne qui a recommandé ce lead, ou ``''``.

    Lu sur le parrainage enregistré (``crm.Parrainage.parrain``) — jamais un
    prénom codé en dur (règle fondateur du 08/09). Absent ⇒ chaîne vide ⇒ la
    phrase qui le porte est OMISE (MRY13), jamais un crochet envoyé.

    CAD164 — à défaut de parrainage, le LOCATAIRE qui a donné les coordonnées
    de son propriétaire : la note de lien (``PREFIXE_LIEN_LOCATAIRE``) porte
    l'id de sa fiche, et c'est son PRÉNOM (à défaut son nom) qui est rendu.
    """
    try:
        from .models import Parrainage
        lien = (Parrainage.objects
                .filter(company=lead.company, filleul_lead=lead)
                .select_related('parrain')
                .order_by('-date_creation', '-id').first())
    except Exception:  # noqa: BLE001 — jamais bloquant, jamais inventé
        logger.warning('CAD127 : prescripteur illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return ''
    if lien is not None and lien.parrain is not None:
        return (getattr(lien.parrain, 'nom', '') or '').strip()
    return _prenom_du_locataire_prescripteur(lead)


def _prenom_du_locataire_prescripteur(lead):
    """CAD164 — le prénom (à défaut le nom) du locataire qui a recommandé ce
    propriétaire, lu sur la note de lien ; ``''`` sinon. Bornée à la SOCIÉTÉ
    du lead. Ne lève jamais."""
    try:
        note = (LeadActivity.objects
                .filter(company=lead.company, lead=lead,
                        kind=LeadActivity.Kind.NOTE,
                        body__startswith=PREFIXE_LIEN_LOCATAIRE)
                .order_by('-created_at', '-pk')
                .values_list('body', flat=True).first())
        if not note:
            return ''
        brut = note[len(PREFIXE_LIEN_LOCATAIRE):].split(' ', 1)[0]
        if not brut.isdigit():
            return ''
        locataire = Lead.objects.filter(
            company=lead.company, pk=int(brut)).first()
    except Exception:  # noqa: BLE001 — jamais bloquant, jamais inventé
        logger.warning('CAD164 : locataire prescripteur illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return ''
    if locataire is None:
        return ''
    return ((locataire.prenom or '').strip()
            or (locataire.nom or '').strip())


def _mois_dossier_francais(lead):
    """« mars 2026 » — le mois où ce prospect nous avait consultés.

    Dérivé de la date de création de SA fiche : une date réelle et traçable,
    jamais une estimation. Fiche sans date ⇒ chaîne vide ⇒ phrase omise.
    """
    from . import horaires

    quand = getattr(lead, 'date_creation', None)
    if not quand:
        return ''
    locale = quand.astimezone(horaires.CASABLANCA)
    return f'{_MOIS_FR[locale.month - 1]} {locale.year}'


def cle_identite_pour_lead(lead, cle_gabarit, *, reference=None):
    """La clé de message à RENDRE pour cette touche — souvent ``cle_gabarit``.

    Ne change QUE la touche d'identité (`identite`) : toutes les autres clés
    passent inchangées, y compris une clé personnalisée par la société.

    Ordre de décision :

      1. une fiche OUVERTE UN MOIS ANTÉRIEUR à la touche n'est pas une
         demande fraîche — c'est un dossier repris (repositionnement,
         réactivation) : `identite_ancien_dossier`. Aucun seuil inventé, on
         compare des MOIS calendaires, ce que le texte dit littéralement ;
      2. sinon, le canal d'origine enregistré décide
         (`CLE_IDENTITE_PAR_CANAL`) ;
      3. sinon `identite` reste : `site_web` et `meta_ads` sont de VRAIS
         formulaires, la phrase d'origine y est exacte.
    """
    if cle_gabarit != 'identite':
        return cle_gabarit
    try:
        from apps.parametres.models_messages import CLE_IDENTITE_PAR_CANAL
    except Exception:  # noqa: BLE001 — jamais bloquant
        return cle_gabarit

    ouverture = getattr(lead, 'date_creation', None)
    if ouverture is not None and reference is not None:
        from . import horaires
        locale = ouverture.astimezone(horaires.CASABLANCA).date()
        if (locale.year, locale.month) < (reference.year, reference.month):
            return 'identite_ancien_dossier'

    canal = (getattr(lead, 'canal', None) or '').strip()
    return CLE_IDENTITE_PAR_CANAL.get(canal, cle_gabarit)


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


# ── CAD-I ── CAD90 — le registre couvre TOUTES les créations de lead ────────
#
# Audit L3 du 21/09/2026. ``enregistrer_consentement_lead`` n'était appelée
# que depuis le webhook du formulaire du site : un lead créé à la main par la
# commerciale (appel entrant, WhatsApp reçu au salon), un lead Meta Lead Ads
# ou un lead venu d'un document n'écrivaient RIEN au registre
# ``core.ConsentRecord`` — alors que la cadence démarre quand même et que sa
# touche n°1 est un WhatsApp, le canal le plus encadré.
#
# CE QUE ``granted`` VEUT DIRE ICI, ET CE QU'IL NE VEUT PAS DIRE. Il dit
# seulement si un CONSENTEMENT A ÉTÉ RECUEILLI — jamais si le traitement est
# licite. Sur ces chemins, aucune case n'a été cochée par la personne : la
# licéité vient de la BASE LÉGALE, tracée dans ``source``. Écrire
# ``granted=True`` pour faire joli fabriquerait une preuve fausse, ce qui est
# pire qu'une preuve absente (même raison que ``ip_confirmation`` laissée
# vide par l'intake web).
#
# LES DEUX BASES, SUR TEXTE PRIMAIRE (extraction du round 2 de l'audit, PDF
# adala.justice.gov.ma) :
#   * données NON collectées auprès de la personne (Meta, import, document) —
#     loi 09-08 art. 5 §3, avec l'information due « par tous moyens » de
#     l'art. 34 du décret 2-09-165 ;
#   * la personne a elle-même SOLLICITÉ le contact (appel entrant, message
#     WhatsApp, demande au salon) — relation précontractuelle à sa demande,
#     loi 09-08 art. 5. Le CNDP distingue les deux, le registre aussi.


# ── CAD-K ── CAD129 — « rappelez-moi » entre dans la FILE, pas dans la cloche ─
#
# Audit L3 du 21/09/2026. Un clic « rappelez-moi » écrivait une note, notifiait
# le responsable et son supérieur, et posait la préférence « joignable par
# téléphone » — mais ne créait AUCUNE touche. Si la notification est noyée dans
# la cloche, la demande la plus forte qu'un prospect puisse faire disparaît.
#
# LA RÈGLE : décaler, jamais redémarrer. Quand le lead a déjà un plan en cours,
# on RAMÈNE sa prochaine touche au prochain créneau d'appel et tout le reste du
# plan glisse du MÊME delta (``reporter_prochaine_touche`` le fait déjà, ancre
# comprise) : le lead garde sa position dans le protocole, on ne fabrique pas un
# second plan concurrent. Quand il n'a plus aucune touche ouverte (cadence
# terminée ou arrêtée), on pose UNE touche — une seule, jamais un plan.

#: Libellé de la touche « rappel demandé ». Sert aussi de clé d'idempotence :
#: deux clics du même client ne laissent jamais deux lignes dans la file.
RAPPEL_DEMANDE_LIBELLE = 'Rappeler le client (il l’a demandé)'

#: Cadence des touches hors protocole déjà utilisée par le dépôt.
RAPPEL_DEMANDE_CADENCE = 'generique'


def _touche_rappel_demande_ouverte(lead):
    """La touche « rappel demandé » encore À FAIRE sur ce lead, ou ``None``."""
    return (lead.relance_etapes
            .filter(libelle=RAPPEL_DEMANDE_LIBELLE,
                    statut=RelanceEtape.Statut.A_FAIRE)
            .order_by('due_date', 'pk')
            .first())


def poser_touche_rappel_demande(lead, *, user=None, quand=None):
    """CAD129 — un rappel demandé devient une TOUCHE datée, pas une notification.

    ``quand`` (instant ou date) par défaut = maintenant ; l'échéance réelle est
    toujours recalée sur le prochain créneau d'APPEL de la société — un rappel
    promis à 23 h ne rend service à personne.

    Renvoie la touche (déplacée ou créée), ou ``None`` si le lead n'a pas de
    société. Best-effort intégral : une demande client n'est JAMAIS perdue
    parce que la file n'a pas pu être écrite — l'appelant a déjà consigné la
    note et notifié le responsable.
    """
    from . import horaires

    if lead is None or getattr(lead, 'company_id', None) is None:
        return None
    try:
        instant = quand or timezone.now()
        if not isinstance(instant, datetime.datetime):
            instant = datetime.datetime.combine(
                instant, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
        elif timezone.is_naive(instant):
            instant = timezone.make_aware(instant, datetime.timezone.utc)
        echeance = horaires.prochain_creneau_appel(
            instant, lead.company, canal=RelanceEtape.Canal.APPEL)

        # 1. Une touche « rappel demandé » déjà ouverte est DÉPLACÉE, jamais
        #    dupliquée : deux clics ne font pas deux lignes dans la file.
        #    COCKPIT-CONTRÔLE : une demande du CLIENT, jamais un report
        #    compté à la commerciale — l'origine suit l'échéance.
        deja = _touche_rappel_demande_ouverte(lead)
        if deja is not None:
            deplacer_echeance_etape(deja, echeance)
            _recaler_file(lead, user)
            return deja

        # 2. Un plan en cours : on le RAMÈNE, avec tout son reste (l'ancre
        #    comprise). C'est « décaler, jamais redémarrer ».
        ouverte = _prochaine_touche_a_faire(lead)
        if ouverte is not None:
            deplacee = reporter_prochaine_touche(
                lead, user, echeance, etape=ouverte, journaliser=False,
                compter_report=False)
            if deplacee is not None:
                # Python 3.11 (prod/CI) refuse une expression MULTI-LIGNE dans
                # une f-string : le libellé est composé AVANT.
                quand_local = echeance.astimezone(horaires.CASABLANCA)
                quand_lisible = quand_local.strftime('%d/%m/%Y à %H:%M')
                activity.log_note(
                    lead, user,
                    'Rappel demandé par le client : la prochaine touche est '
                    f'ramenée au {quand_lisible}, et la suite du plan glisse '
                    'du même écart.')
                return deplacee

        # 3. Plus aucune touche ouverte : UNE touche, jamais un second plan.
        etape = RelanceEtape.objects.create(
            company=lead.company, lead=lead,
            cadence=RAPPEL_DEMANDE_CADENCE, ordre=0,
            canal=RelanceEtape.Canal.APPEL,
            libelle=RAPPEL_DEMANDE_LIBELLE,
            due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            note='Posée automatiquement : le client a demandé un rappel.')
        _recaler_file(lead, user)
        return etape
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD129 : touche de rappel non posée pour le lead #%s',
            getattr(lead, 'pk', None), exc_info=True)
        return None


# ── CAD-A ── CAD1 — « intéressé » poursuit le plan, il ne le rejoue pas ──────
#
#: Quelles cadences une ISSUE arrête — LA source unique, lue par le récepteur
#: MRY9 (``receivers._arreter_cadence_on_outcome``) comme par la
#: matérialisation réactive ci-dessous. Deux listes séparées auraient dérivé :
#: c'est précisément ce que CAD1 répare, puisque la matérialisation traitait
#: « intéressé » comme un arrêt TOTAL alors que le récepteur, lui, laissait
#: vivre le suivi de proposition.
#:
#: * ``joint`` / ``interesse`` → la PRISE DE CONTACT a atteint son but, et les
#:   réveils d'un dormant n'ont plus lieu d'être. Le suivi de PROPOSITION, lui,
#:   continue : un client joint reste à relancer sur son devis.
#: * ``refuse`` → tout s'arrête, y compris la proposition refusée. Le lead
#:   n'est PAS marqué perdu pour autant (MRY22 : décision humaine, avec motif).
#: * ``visite_acceptee`` (décision fondateur du 24/09/2026) → exactement comme
#:   ``joint`` : le client qui accepte la visite a atteint le but de la prise
#:   de contact, et un dormant qui l'accepte n'a plus à être réveillé. Le
#:   suivi de proposition continue (il se décale autour du rendez-vous,
#:   ``suspendre_plan_jusqu_apres_visite``). La suite n'est pas l'étape
#:   générique du filet mais « Planifier la visite technique convenue »
#:   (``poser_filet_visite_a_planifier``).
#: * SUIVI E15 (30/09/2026) — la DEUXIÈME AFFAIRE (CAD128, la prise de
#:   contact d'un client acquis) s'arrête exactement comme la prise de
#:   contact : « joint » posait l'étape de filet ET faisait naître le
#:   barreau 2 (deux touches ouvertes pour un client déjà joint).
CADENCES_ARRETEES_PAR_ISSUE = {
    'joint': ('contact', 'reveil', 'deuxieme_affaire'),
    'interesse': ('contact', 'reveil', 'deuxieme_affaire'),
    'refuse': ('contact', 'apres_devis', 'reveil', 'deuxieme_affaire'),
    OUTCOME_VISITE_ACCEPTEE: ('contact', 'reveil', 'deuxieme_affaire'),
}


def issue_fait_naitre_la_suite(outcome, cadence):
    """CAD1 — cette ISSUE, sur une touche de CETTE cadence, doit-elle faire
    naître le barreau suivant du protocole ?

    Trois cas, et rien d'autre :

    * « visite acceptée » → JAMAIS : le client a dit oui à un rendez-vous, la
      seule suite utile est de le caler (VISITE-CADENCE) ;
    * une issue qui ARRÊTE la cadence de la touche → non plus : le récepteur
      MRY9 vient d'annuler ce qui restait, et le filet pose la vraie suite ;
    * tout le reste (« pas de réponse », « à rappeler », aucune issue sur un
      message, et « intéressé »/« joint » sur le suivi de PROPOSITION que ces
      issues n'arrêtent pas) → oui, le geste suivant est programmé.
    """
    issue = (outcome or '').strip()
    if issue == OUTCOME_VISITE_ACCEPTEE:
        return False
    return cadence not in CADENCES_ARRETEES_PAR_ISSUE.get(issue, ())


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


#: APAR51 — les issues de ``appliquer_champ_automatique``.
CHAMP_AUTO_APPLIQUE = 'applique'
CHAMP_AUTO_INCHANGE = 'inchange'
CHAMP_AUTO_INVALIDE = 'invalide'
CHAMP_AUTO_CADENCE = 'cadence_active'


def appliquer_champ_automatique(lead, champ, valeur, user=None):
    """APAR51 (C-APAR-032) — LA porte d'écriture d'un champ de lead par une
    AUTOMATISATION (règle SET_FIELD, action serveur, assignation) : la même
    discipline que le geste manuel.

    * la valeur est VALIDÉE par le champ du modèle (choix, longueur, type) —
      hors choix ⇒ ``(CHAMP_AUTO_INVALIDE, motif)``, rien n'est écrit ;
    * ``relance_date`` sur un lead à CADENCE ACTIVE ⇒ refus CAD49
      (``(CHAMP_AUTO_CADENCE, MOTIF_BULK_CADENCE_ACTIVE)``) : la date vient
      de la prochaine touche du plan ;
    * une valeur égale ⇒ ``(CHAMP_AUTO_INCHANGE, '')`` ;
    * sinon le champ est écrit et UNE ligne MODIFICATION (ancien → nouveau)
      entre au chatter, l'acteur étant ``user`` (la règle).

    ``champ='owner'`` accepte un utilisateur (ou son identifiant) de la
    société du lead. Rend ``(issue, motif)``."""
    from django.core.exceptions import ValidationError

    from . import activity as _activity

    try:
        champ_modele = Lead._meta.get_field(champ)
    except Exception:  # noqa: BLE001
        return CHAMP_AUTO_INVALIDE, f'Champ « {champ} » inconnu.'
    if champ == 'owner':
        from django.contrib.auth import get_user_model
        pk = getattr(valeur, 'pk', valeur)
        cible = get_user_model().objects.filter(
            pk=pk, company=lead.company).first() if pk else None
        if cible is None:
            return CHAMP_AUTO_INVALIDE, 'Utilisateur cible inconnu.'
        ancien = lead.owner
        if ancien is not None and ancien.pk == cible.pk:
            return CHAMP_AUTO_INCHANGE, ''
        lead.owner = cible
        lead.save(update_fields=['owner'])
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.MODIFICATION, field='owner',
            field_label=_activity.TRACKED_FIELDS.get('owner', 'owner'),
            old_value=_activity._display(lead, 'owner', ancien),
            new_value=_activity._display(lead, 'owner', cible))
        return CHAMP_AUTO_APPLIQUE, ''
    try:
        propre = champ_modele.clean(valeur, lead)
    except ValidationError as exc:
        hors_choix = bool(getattr(champ_modele, 'choices', None))
        detail = '; '.join(exc.messages)
        return CHAMP_AUTO_INVALIDE, (
            f'Valeur hors choix pour « {champ} » : {valeur!r}.' if hors_choix
            else f'Valeur invalide pour « {champ} » : {detail}')
    if champ == 'relance_date' and leads_avec_cadence_active(
            lead.company, [lead.pk]):
        return CHAMP_AUTO_CADENCE, MOTIF_BULK_CADENCE_ACTIVE
    ancien = getattr(lead, champ, None)
    if ancien == propre:
        return CHAMP_AUTO_INCHANGE, ''
    setattr(lead, champ, propre)
    lead.save(update_fields=[champ])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION, field=champ,
        field_label=_activity.TRACKED_FIELDS.get(champ, champ),
        old_value=_activity._display(lead, champ, ancien),
        new_value=_activity._display(lead, champ, propre))
    if champ == 'relance_date':
        sync_relance_activity(lead, user)
    return CHAMP_AUTO_APPLIQUE, ''


# ── CAD-A ── RÉPONSES DE TOUCHE : ce que le client DIT décide de la suite ─────
#
# Audit L3 du 21/09/2026. Les réponses offertes sur une touche se limitaient
# aux issues de ``LeadActivity.OUTCOMES`` (joint / non joint / à rappeler /
# refus / intéressé / visite acceptée) : « arrêtez de m'appeler », « plus
# tard », « c'est une question de prix », « refaites-moi le devis », « on
# décide en famille » n'avaient AUCUN bouton, et la commerciale choisissait
# l'issue la moins fausse — dont la suite automatique était, elle, fausse.
#
# LA RÈGLE. Une RÉPONSE est une clé connue du SERVEUR, jamais une nouvelle
# valeur d'énumération : elle se traduit en une issue EXISTANTE (aucune
# migration), une note typée (la phrase du client, telle qu'elle est comptée
# dans le chatter) et UN effet — celui que le client a demandé. L'écran
# n'envoie que la clé ; l'issue est dérivée ICI, et nulle part ailleurs.

#: L'étiquette posée par cette réponse (seedée par ``views.seed_tags``).
TAG_ATTENTE_ACCORD = 'Attend un accord (DPA / banque)'

#: CIQ508 (D-CIQ, 06/10/2026) — la RAISON de l'attente, liste FERMÉE du contrat
#: CIQ10 (``relance_etape_v2.json``, ``ajout_ciq10_raison_attente``) :
#: ``(valeur, libellé affiché, étiquette posée)``. ``administration`` pose
#: l'étiquette d'AGR520, inchangée ; les autres, une étiquette par RAISON
#: (seedée par ``views.seed_tags``). Aucune étape de ``STAGES.py`` : l'attente
#: ne change jamais l'étape du dossier.
RAISONS_ATTENTE = (
    ('direction', 'La direction / le comité',
     'Attend la direction / le comité'),
    ('financement', "La banque / l'organisme de financement",
     "Attend la banque / l'organisme de financement"),
    ('bailleur_murs', 'Le bailleur des murs', 'Attend le bailleur des murs'),
    ('budget_exercice', "Le budget de l'exercice suivant",
     "Budget de l'exercice suivant"),
    ('consultation', 'Une consultation en cours', 'Consultation en cours'),
    ('administration', "L'administration (DPA, dossier FDA)",
     TAG_ATTENTE_ACCORD),
)
ETIQUETTES_RAISON_ATTENTE = tuple(r[2] for r in RAISONS_ATTENTE)


# ── CAD-A ── CAD7 — « Question de prix — veut négocier » ────────────────────

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


# ── CAD158 — « votre facture, c'est pour un mois ou pour deux ? » ───────────
#
# Le moteur (`apps/ventes/etude_horaire.py`, inversion au barème) lit
# `facture_hiver` comme un montant MENSUEL : un client qui donne le montant de
# sa facture BIMESTRIELLE faussait tout l'aval (niveau de facture, économie).
# Décision fondateur du 21/09/2026 (Q24) : le montant est ramené au mois AU
# MOMENT DE LA SAISIE, et aucun champ « périodicité » n'est stocké.

def refus_periodicite_facture(periodicite):
    """CAD158 — le message (FR, qui NOMME le champ) si ``periodicite`` n'est
    pas une période connue, sinon ``None``."""
    if periodicite in Lead.PERIODICITES_FACTURE:
        return None
    choix = ' ou '.join(f'« {cle} »' for cle in Lead.PERIODICITES_FACTURE)
    return (f'« Période de la facture » : {choix} attendu '
            f'(reçu « {periodicite} »).')


def facture_au_mois(montant, periodicite):
    """CAD158 — le montant MENSUEL d'une facture déclarée sur ``periodicite``
    (``mensuelle`` : inchangé ; ``bimestrielle`` : divisé par deux), arrondi
    au centime selon la convention monétaire (moitié vers le haut).

    ``None`` reste ``None`` : aucun montant n'est jamais inventé."""
    from decimal import Decimal

    from core.money import quantize_mad

    if montant is None or montant == '':
        return None
    mois = Lead.PERIODICITES_FACTURE[periodicite]
    return quantize_mad(Decimal(str(montant)) / Decimal(mois))


# ── CAD164 — le LOCATAIRE : demander le propriétaire, sinon « Perdu — Locataire »
#
# Décision fondateur du 21/09/2026 : on demande le propriétaire ; s'il est
# joignable, on crée SA fiche, LIÉE à celle du locataire (le locataire reste le
# prescripteur : son prénom passe par la variable `{prescripteur}` du texte
# d'origine « recommandation », CAD127 — jamais en dur) ; sinon on clôt avec
# le motif EXISTANT « Locataire ». Aucune valeur d'énumération neuve : le motif
# existe (`MotifPerte`), le canal « Référence » aussi, et le lien entre les deux
# fiches est une NOTE d'historique de chaque côté — jamais une fusion
# automatique (conduite `FLUX_LOCATAIRE` du script d'appel).


#: Le préfixe de la note posée sur la fiche du PROPRIÉTAIRE : il porte l'id de
#: la fiche du locataire, et c'est lui que `_nom_prescripteur` relit. Source
#: unique (même discipline que les préfixes RLC2).
PREFIXE_LIEN_LOCATAIRE = 'Recommandé par le locataire — fiche #'
