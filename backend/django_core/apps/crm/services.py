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

# CRX26 — LA date MÉTIER (Africa/Casablanca), lue EXPLICITEMENT : elle ne dépend
# d'aucun réglage global. Avant AUD836, ``settings.TIME_ZONE`` valait ``'UTC'``
# et ``timezone.localdate()`` était en retard d'un jour entier une heure par
# nuit ; le réglage dit désormais la même chose, ce helper reste la garantie.
from core.dates import aujourd_hui_local

from . import activity, stages
from .models import Canal, Client, Lead, LeadActivity, PointContact, RelanceEtape
# T-TRACE — le traçage des visiteurs externes vit dans son propre module
# (``apps/crm/visites.py``) pour ne pas gonfler ce fichier déjà très long,
# mais il est RÉEXPORTÉ ici : `services` reste la porte d'entrée unique des
# écritures CRM (les accroches n'importent jamais `visites` directement).
from .visites import (  # noqa: F401 — réexport public délibéré
    alerter_appareil_partage,
    appareil_de_requete,
    avec_direction,
    detecter_concurrent,
    enregistrer_visite_externe,
    historique_appareil,
    ip_de_requete,
    rattacher_visites_au_lead,
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
        aujourd_hui = aujourd_hui_local()
        deja_note = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='signal d\'intérêt fort',
            created_at__date=aujourd_hui,
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

    update_fields = []
    if etait_perdu:
        lead.perdu = False
        update_fields.append('perdu')

    cible = _STAGE_CONTACTED if lead.first_contacted_at else stages.NEW
    if _rang_funnel(lead.stage) < _rang_funnel(cible):
        ancien_stage = lead.stage
        lead.stage = cible
        update_fields.append('stage')
    else:
        ancien_stage = None  # étape déjà ≥ cible — pas de changement d'étape.

    if update_fields:
        lead.save(update_fields=update_fields)

    body = f'auto — réactivation : nouvelle demande {source}'
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
        _emit_stage_changed(lead, ancien_stage, cible, None)
    return True


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

    from . import horaires

    def _canal(gabarit):
        """Le canal de CETTE touche — `appel` par défaut, jamais deviné."""
        return getattr(gabarit, 'canal', None) or 'appel'

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

    echeances = []
    for gabarit in gabarits:
        if ((getattr(gabarit, 'template_cle', '') or '')
                == _TEMPLATE_DIMANCHE_FAMILLE
                and not _lead_porte_tag(lead, _TAG_DECISION_A_PLUSIEURS)):
            # MRY4 — touche RÉSERVÉE aux dossiers étiquetés « Décision à
            # plusieurs ». Posée sur tous, elle envoyait un message dominical
            # « parlez-en en famille » à des prospects qui décident seuls.
            # La numérotation `ordre` garde son trou : elle vient du gabarit
            # de la société, pas d'un compteur local.
            continue
        delai_minutes = getattr(gabarit, 'delai_minutes', 0) or 0
        heure_cible = getattr(gabarit, 'heure_cible', None)
        if getattr(gabarit, 'dimanche_ok', False):
            # MRY4/MRY8 — une touche dominicale se PLACE sur un dimanche, elle
            # ne s'y recale pas. `prochain_creneau_appel` ne sait que borner un
            # instant dans la fenêtre de SON jour : l'« appel du dimanche »
            # calculé en J+5 depuis un mercredi tombait un lundi, et le seul
            # rendez-vous dominical du protocole n'avait jamais lieu un
            # dimanche. On prend donc le PREMIER dimanche dont la date atteint
            # `depart + delai_jours`, à 16 h 30 (milieu de la fenêtre 16 h-19 h)
            # — l'`heure_cible` du gabarit ne s'applique pas ici : elle vise un
            # jour ouvré, et 10 h 30 un dimanche n'existe pas.
            echeance = horaires.prochain_dimanche(
                depart + timedelta(days=gabarit.delai_jours))
            if echeance < depart:  # garde-fou : jamais dans le passé
                echeance = horaires.prochain_dimanche(
                    echeance + timedelta(days=1))
        elif gabarit.delai_jours == 0 and heure_cible is None:
            # Les touches DU JOUR MÊME s'enchaînent depuis l'origine ouvrable,
            # pas depuis l'heure brute d'arrivée du lead : les écarts du
            # protocole (3 min, 2 h 30) sont ainsi PRÉSERVÉS quelle que soit
            # l'heure d'arrivée.
            echeance = origine + timedelta(minutes=delai_minutes)
        else:
            echeance = depart + timedelta(
                days=gabarit.delai_jours, minutes=delai_minutes)
            if heure_cible is not None:
                locale = echeance.astimezone(horaires.CASABLANCA)
                echeance = locale.replace(
                    hour=heure_cible.hour, minute=heure_cible.minute,
                    second=0, microsecond=0)
        echeance = horaires.prochain_creneau_appel(
            echeance, lead.company,
            dimanche=bool(getattr(gabarit, 'dimanche_ok', False)),
            canal=_canal(gabarit))
        echeances.append((gabarit, echeance))
    return echeances


def initialiser_plan_relance(lead, user, *, depart=None, cadence='contact',
                             devis=None):
    """Matérialise UNE cadence de relance sur ``lead`` depuis le gabarit de sa
    société (``parametres.CadenceRelanceEtape.cadence_pour``).

    IDEMPOTENT **PAR CADENCE** (MRY5) : un lead peut porter simultanément sa
    prise de contact et le suivi d'un devis ; l'ancienne idempotence globale
    « ce lead a déjà des étapes » les aurait confondus et un devis envoyé
    n'aurait jamais eu son plan. Pour ``apres_devis``, l'idempotence est en
    plus portée PAR DEVIS.

    ``depart`` est un datetime AWARE (défaut : maintenant). Chaque touche vaut
    ``depart + delai_jours + delai_minutes``, puis — si le gabarit porte une
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
    existantes = list(deja.order_by('ordre', 'due_date'))
    if existantes:
        return existantes

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
    etapes = [
        RelanceEtape(
            company=lead.company, lead=lead, cadence=cadence,
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
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
    resultats = list(
        lead.relance_etapes.filter(cadence=cadence)
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

    if not lead.relance_date or lead.relance_date > premiere.due_date:
        lead.relance_date = premiere.due_date
        lead.save(update_fields=['relance_date'])
    sync_relance_activity(lead, user)
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
            if poser_validite_devis(devis, derniere):
                LeadActivity.objects.create(
                    company=lead.company, lead=lead, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'Validité de la proposition posée au '
                          f'{derniere:%d/%m/%Y} — fin du plan de '
                          'suivi.'))
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


def materialiser_touche_suivante(etape_close, user=None):
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

    Rend la ``RelanceEtape`` créée, ou ``None`` (fin du gabarit, lead qu'on ne
    relance plus, société sans gabarit, ancre introuvable)."""
    from apps.parametres.models_relance import CadenceRelanceEtape

    from . import horaires

    lead = etape_close.lead
    if (getattr(lead, 'ne_plus_contacter', False)
            or getattr(lead, 'perdu', False)
            or getattr(lead, 'is_archived', False)):
        return None

    # Les étapes du FILET (MRY34 / QJ-INVARIANT) portent la cadence
    # `generique` mais ne sont PAS un barreau de protocole : ce sont des
    # étapes posées à la main par `assurer_prochaine_etape_apres_succes`, dont
    # la suite est décidée par le filet lui-même (plan après-devis si un devis
    # est parti, sinon une nouvelle étape générique). Leur faire naître le
    # « barreau 2 » du gabarit `generique` remplissait la file d'une touche
    # sans objet ET — parce qu'une prochaine touche existait alors — empêchait
    # le filet de démarrer le vrai suivi de proposition (cas AR du 07/09).
    if (etape_close.libelle or '').strip() in _LIBELLES_FILET:
        return None

    cadence = etape_close.cadence
    gabarits = CadenceRelanceEtape.cadence_pour(lead.company, cadence)
    if not gabarits:
        # Cadence sans gabarit (« generique », posée à la main par le filet) :
        # il n'y a pas de suite à faire naître — l'invariant « jamais un lead
        # actif sans prochaine touche » reste tenu par le filet lui-même.
        return None

    ancre = etape_close.cadence_depart
    if ancre is None:
        # Lignes d'avant CKP2 : l'ancre n'a jamais été écrite. La plus
        # ancienne échéance de la cadence en est la meilleure approximation
        # connue — jamais une valeur inventée.
        ancre = (lead.relance_etapes.filter(cadence=cadence)
                 .exclude(due_at=None).order_by('due_at')
                 .values_list('due_at', flat=True).first())
    if ancre is None:
        return None

    echeances = calculer_echeances_cadence(
        lead, cadence, ancre, gabarits=gabarits)
    rang = next((i for i, (g, _e) in enumerate(echeances)
                 if g.ordre == etape_close.ordre), None)
    if rang is None:
        return None
    gabarit_close = echeances[rang][0]

    deja = lead.relance_etapes.filter(cadence=cadence)
    if etape_close.devis_id is not None:
        deja = deja.filter(devis_id=etape_close.devis_id)
    ordres_pris = set(deja.values_list('ordre', flat=True))

    for suivant in range(rang + 1, len(echeances)):
        gabarit, echeance = echeances[suivant]
        if gabarit.ordre in ordres_pris:
            # IDEMPOTENCE : le barreau qui suit celui qu'on vient de clore
            # existe DÉJÀ (double appel, ou cadence rétrodatée dont plusieurs
            # touches échues ont été matérialisées d'un coup). On s'arrête —
            # SAUTER par-dessus pour en créer un plus loin ferait naître deux
            # touches au lieu d'une et casserait l'ordre du protocole.
            return None
        if (gabarit.delai_jours == 0
                and not getattr(gabarit, 'dimanche_ok', False)
                and getattr(gabarit, 'heure_cible', None) is None):
            ecart = ((getattr(gabarit, 'delai_minutes', 0) or 0)
                     - (getattr(gabarit_close, 'delai_minutes', 0) or 0))
            base = etape_close.traite_le or timezone.now()
            echeance = horaires.prochain_creneau_appel(
                base + datetime.timedelta(minutes=max(0, ecart)),
                lead.company,
                canal=getattr(gabarit, 'canal', None) or 'appel')
        etape = RelanceEtape(
            company=lead.company, lead=lead, cadence=cadence,
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=getattr(gabarit, 'template_cle', '') or '',
            devis_id=etape_close.devis_id, cadence_depart=ancre)
        if cadence == 'reveil':
            _adapter_gabarits_reveil(lead, [etape], rang_initial=suivant)
        etape.save()
        return etape
    return None


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


def marquer_etape_relance(etape, user, statut, note='', outcome='',
                          body=''):
    """Marque une ``RelanceEtape`` ``fait`` ou ``sautee`` (jamais un retour
    silencieux en arrière) : trace l'acteur/l'horodatage, journalise dans le
    chatter du lead, puis fait AVANCER ``Lead.relance_date`` vers la
    prochaine étape ``a_faire`` de CE plan (ou la vide si le plan est
    terminé) — garde ``sync_relance_activity`` en phase, jamais un second
    système de rappel concurrent.

    CKP2 — c'est aussi ICI que naît la touche SUIVANTE du protocole
    (``materialiser_touche_suivante``) quand la clôture n'est pas un succès :
    la cadence est RÉACTIVE, une touche à la fois, et c'est l'issue saisie qui
    programme le geste d'après."""
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
    etape.save(update_fields=['statut', 'note', 'traite_par', 'traite_le'])

    verbe = 'faite' if statut == RelanceEtape.Statut.FAIT else 'sautée'
    # MRY5 — le corps disait « Relance J+{ordre} », faux depuis que `ordre`
    # est un RANG dans la cadence et non plus un délai en jours (la touche 2
    # de la prise de contact tombe à J0 + 3 minutes, pas à J+2).
    libelle = (etape.libelle or '').strip() or etape.get_canal_display()
    corps = (f'Touche « {libelle} » ({etape.get_canal_display()}, cadence '
             f'{etape.cadence}) marquée {verbe}.')
    if body:
        corps += f' {body}'
    if note:
        corps += f" Note : {note}"
    # MRY10 — UNE SEULE ligne de chatter par touche, TYPÉE selon le canal
    # (jamais une note libre en plus d'une activité) : c'est elle que compte
    # le compteur de tentatives et que lisent les règles d'arrêt (MRY9).
    kind = (_CANAL_VERS_KIND.get(etape.canal, LeadActivity.Kind.NOTE)
            if statut == RelanceEtape.Statut.FAIT
            else LeadActivity.Kind.NOTE)
    LeadActivity.objects.create(
        company=etape.company, lead=etape.lead, user=user,
        kind=kind, body=corps, outcome=(outcome or ''))

    lead = etape.lead
    # RELANCE-SUITE (08/09/2026) — LA détection « devis parti » : la touche
    # générique d'envoi du devis, sans issue. Hissée ici (une seule règle de
    # libellé) car DEUX consommateurs la lisent désormais : le filet plus bas
    # (démarrage du plan après-devis, comportement inchangé) et QJ-FUNNEL
    # juste en dessous (l'étape du funnel).
    touche_envoi_devis = (
        etape.cadence == 'generique' and not (outcome or '')
        and (etape.libelle or '').strip()
        in (FILET_JOINT_LIBELLE, _FILET_JOINT_LIBELLE_ANCIEN))
    # QJ-FUNNEL (fondateur 09/09/2026 — « when I do Fait for quote sent, it
    # should be at quote sent ») — cocher FAIT la touche d'envoi place le
    # lead à « Devis envoyé » sur-le-champ, quel que soit le reste du plan
    # (une touche SAUTÉE ne vaut jamais un envoi).
    if statut == RelanceEtape.Statut.FAIT and touche_envoi_devis:
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
    suivante = None
    if (statut == RelanceEtape.Statut.SAUTEE
            or (outcome or '') not in _OUTCOMES_ARRET_CADENCE):
        try:
            suivante = materialiser_touche_suivante(etape, user)
        except Exception:  # noqa: BLE001 — jamais bloquant pour le geste
            logger.warning(
                'CKP2: touche suivante non matérialisée (étape #%s)',
                getattr(etape, 'pk', '?'), exc_info=True)
    prochaine = _prochaine_touche_a_faire(lead)
    lead.relance_date = prochaine.due_date if prochaine else None
    lead.save(update_fields=['relance_date'])
    sync_relance_activity(lead, user)
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
    if (restantes_avant == 0 and suivante is None
            and (outcome or '') not in _OUTCOMES_SANS_CLOTURE):
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
        # (Détection hissée en tête de fonction — `touche_envoi_devis`.)
        assurer_prochaine_etape_apres_succes(
            lead, user, brouillon_compris=touche_envoi_devis)
    return etape


#: MRY11 × MRY9 — les issues qui INTERDISENT la clôture, même sur la dernière
#: touche : on a joint la personne (ou on est convenu d'un rappel). La mettre
#: au froid et l'étiqueter « injoignable » serait l'inverse du bon geste.
#: B1 (revue Fable 07/09/2026) — ``refuse`` aussi : le client a RÉPONDU.
#: Clôturer l'étiquetterait « Injoignable » et lui enverrait des réveils
#: J30/J60 « vous étiez injoignable » ; le filet « décider la suite » (posé
#: par le récepteur MRY9) assure déjà la suite du dossier.
_OUTCOMES_SANS_CLOTURE = frozenset({'joint', 'interesse', 'rappel', 'refuse'})


#: MRY11 — ce que devient un lead dont la cadence s'est épuisée sans réponse.
#: Le tag NOMME la raison : « injoignable » et « devis sans suite » ne se
#: traitent pas de la même façon au réveil.
#: « 6 appels » et non « 7 tentatives » : le Protocole v3 compte SIX appels
#: (plus cinq WhatsApp) — l'étiquette affichée à Meryem doit dire ce que la
#: cadence a réellement fait. Migration 0093 pour l'existant.
_CLOTURE_TAG_INJOIGNABLE = 'Injoignable 6 appels'
_CLOTURE_TAGS = {
    'contact': _CLOTURE_TAG_INJOIGNABLE,
    'apres_devis': 'Devis sans suite',
}

#: MRY11 — étape la plus AVANCÉE qu'une cadence puisse encore parquer.
#: `_bulk_stage_allowed` autorise « vers COLD » depuis N'IMPORTE OÙ (c'est
#: voulu pour une mise au parking manuelle) : sans ce plafond, épuiser une
#: cadence `contact` sur un lead qui a depuis SIGNÉ le ferait retomber au
#: froid — un devis signé effacé par un rappel resté ouvert.
_CLOTURE_PLAFOND = {
    'contact': stages.CONTACTED,
    'apres_devis': stages.FOLLOW_UP,
}


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
_FILET_JOINT_LIBELLE_ANCIEN = 'Prochaine étape — envoyer le devis ou fixer un rappel'
FILET_JOINT_LIBELLE = 'Préparer et envoyer le devis (ou fixer un rappel)'

#: RELANCE-SUITE — le client a RÉPONDU à un MESSAGE (WhatsApp, e-mail) : la
#: suite est de L'APPELER, au prochain créneau d'appel — jamais le suivi de
#: proposition avant qu'un devis soit parti (« je fais le devis, je l'envoie,
#: PUIS vos étapes viennent »).
FILET_APPEL_LIBELLE = 'Appeler le client — il a répondu au message'
_KINDS_MESSAGE = frozenset({LeadActivity.Kind.WHATSAPP, LeadActivity.Kind.EMAIL})

#: QJ-INVARIANT — libellé du filet après un REFUS (téléphonique ou de devis) :
#: la suite d'un refus est une décision HUMAINE (MRY22), mais le dossier ne
#: doit pas disparaître des files en attendant qu'elle soit prise.
FILET_REFUS_LIBELLE = 'Décider la suite — perdu (motif) ou relance ultérieure'

#: CKP2 — les libellés des étapes POSÉES PAR LE FILET. Elles portent la
#: cadence `generique` sans être un barreau du gabarit `generique` : leur suite
#: est décidée par `assurer_prochaine_etape_apres_succes`, jamais par la
#: matérialisation réactive (`materialiser_touche_suivante` les ignore).
_LIBELLES_FILET = frozenset({
    FILET_JOINT_LIBELLE, _FILET_JOINT_LIBELLE_ANCIEN,
    FILET_APPEL_LIBELLE, FILET_REFUS_LIBELLE,
})

#: Délai (jours) du filet : DEMAIN, recalé sur le prochain créneau d'appel de
#: la société (fenêtres MRY4). Si Meryem donne une date de rappel en marquant
#: la touche, `reporter_prochaine_touche` déplace ce filet sur SA date — le
#: J+1 n'est que le défaut quand aucune date n'est saisie.
FILET_JOINT_DELAI_JOURS = 1


def assurer_prochaine_etape_apres_succes(lead, user,
                                         libelle=FILET_JOINT_LIBELLE,
                                         avec_plan_devis=True,
                                         brouillon_compris=False,
                                         canal_touche=None):
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
    posée (la première du plan) ou ``None``."""
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
        etapes = initialiser_plan_relance(
            lead, user, cadence='apres_devis', devis=devis)
        ouvertes = [e for e in etapes
                    if e.statut == RelanceEtape.Statut.A_FAIRE]
        if ouvertes:
            return ouvertes[0]
        # Plan déjà consommé pour CE devis → l'étape générique ci-dessous.
    if canal_touche in _KINDS_MESSAGE:
        # RELANCE-SUITE — message répondu : on l'appelle, dès le prochain
        # créneau d'appel (maintenant si la fenêtre est ouverte).
        libelle = FILET_APPEL_LIBELLE
        vise = timezone.now()
    else:
        vise = timezone.now() + datetime.timedelta(days=FILET_JOINT_DELAI_JOURS)
    quand = horaires.prochain_creneau_appel(vise, lead.company, canal='appel')
    etape = RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence='generique', ordre=1,
        canal=RelanceEtape.Canal.APPEL, libelle=libelle,
        due_at=quand, due_date=quand.astimezone(horaires.CASABLANCA).date(),
        note='Posée automatiquement : aucune autre relance ouverte.')
    lead.relance_date = etape.due_date
    lead.save(update_fields=['relance_date'])
    sync_relance_activity(lead, user)
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
    # 08/09/2026 — la PREUVE de la touche `j4_preuve` (mois, ville et lien de
    # la page publique d'une `parametres.Realisation` réelle).
    'mois_preuve', 'ville_preuve', 'lien_preuve', 'puissance_preuve')

#: Les trois placeholders de la preuve. Regroupés pour n'aller chercher une
#: réalisation QUE si le texte en porte au moins un (même discipline que
#: `{lien_rdv}` : aucun travail, aucune requête, quand ce n'est pas demandé).
_PLACEHOLDERS_PREUVE = ('{mois_preuve}', '{ville_preuve}', '{lien_preuve}',
                        '{puissance_preuve}')

#: Noms de mois en français, pour « posée en juillet 2026 ». Codés ici plutôt
#: que via une locale système : le rendu d'un message client ne doit pas
#: dépendre des locales installées sur le serveur.
_MOIS_FR = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre')


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
            'puissance_preuve': ''}
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


def message_pour_etape(etape, *, request=None, user=None):
    """MRY13 — Le message d'UNE touche, rendu côté serveur.

    Forme `relance_etape_message` (contrat MRY25) :
    ``{message, wa_url, langue, phone, placeholders_manquants}``.

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
    langue = lead.langue_preferee or 'fr'
    corps = MessageTemplate.get_corps(
        lead.company, etape.template_cle, langue) if etape.template_cle else ''

    # Civilité (décision fondateur 07/09/2026) : on s'adresse à une personne
    # qu'on ne connaît pas encore avec « M. » / « السي » devant le prénom —
    # l'usage marocain respectueux — jamais le prénom nu. Une civilité connue
    # sur le lead (champ futur) prime ; « Mme » se rend « لالة » en darija.
    civilite = (getattr(lead, 'civilite', '') or '').strip()
    if langue == 'darija':
        civilite = {'': 'السي', 'M.': 'السي', 'Mme': 'لالة'}.get(
            civilite, civilite)
    else:
        civilite = civilite or 'M.'
    # Sans prénom (formulaire Meta au nom seul, société), le nom prend sa place
    # dans la salutation plutôt que de faire SAUTER toute la phrase d'accueil.
    prenom = (lead.prenom or '').strip() or (lead.nom or '').strip()
    contexte = {
        'civilite': civilite,
        'nom': (lead.nom or '').strip(),
        'prenom': prenom,
        'ville': (lead.ville or '').strip(),
        'conseiller': _nom_affiche_conseiller(lead, user),
        'reference': '',
        'lien': '',
        'date_validite': '',
    }
    if etape.devis_id:
        try:
            from apps.ventes.selectors import get_devis_by_pk
            from apps.ventes.utils.client_links import url_proposition
            devis = get_devis_by_pk(etape.devis_id)
            if devis is not None:
                contexte['reference'] = getattr(devis, 'reference', '') or ''
                validite = getattr(devis, 'date_validite', None)
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
    if any(t in (corps or '') for t in _PLACEHOLDERS_PREUVE):
        contexte.update(_contexte_preuve(lead))

    manquants = [cle for cle in _PLACEHOLDERS_RENDUS
                 if '{' + cle + '}' in (corps or '')
                 and not str(contexte.get(cle, '')).strip()]
    corps = _omettre_phrases_incompletes(corps, manquants)
    message = render_message_template(corps, contexte)

    phone = lead.whatsapp or lead.telephone or ''
    if etape.template_cle in _TEMPLATES_VOCAUX:
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
    }


#: MRY6 — codes de garde dont le refus est TRACÉ en chatter. Les autres
#: (miroir Odoo, lead déjà contacté, cadence déjà en place…) restent muets :
#: les journaliser inonderait l'historique de chaque import.
_GARDES_CADENCE_TRACEES = frozenset({'sans_numero', 'doublon'})


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
        return ('miroir', 'lead du miroir Odoo')
    if lead.stage != stages.NEW or lead.first_contacted_at is not None:
        return ('deja_contacte', 'lead déjà contacté ou hors étape NEW')
    if lead.perdu or lead.is_archived or lead.ne_plus_contacter:
        return ('inactif', 'lead perdu, archivé ou « ne plus contacter »')
    from apps.ventes.utils.whatsapp import build_wa_url
    if build_wa_url(lead.whatsapp or lead.telephone or '', '') is None:
        return ('sans_numero',
                'aucun numéro exploitable — cadence à lancer à la main')
    doublons = [
        autre for autre in find_duplicates_by_contact(
            lead.company, phone=lead.telephone, email=lead.email,
            exclude_pk=lead.pk)
        if not autre.is_archived and not autre.perdu]
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
            if code in _GARDES_CADENCE_TRACEES:
                # MRY6/MRY10 — les deux refus « rattrapables à la main » sont
                # ÉCRITS : sans numéro exploitable ou sur un doublon vivant,
                # Meryem doit savoir que le lead n'est PAS suivi.
                return _refus_cadence(lead, user, motif)
            return []          # gardes muettes (import, déjà contacté…)
        return initialiser_plan_relance(
            lead, user, cadence='contact', depart=timezone.now())
    except Exception:  # noqa: BLE001 — jamais vers l'appelant
        logger.warning(
            'demarrer_cadence_contact: échec sur le lead #%s (%s)',
            getattr(lead, 'pk', '?'), origine, exc_info=True)
        return []


def reporter_prochaine_touche(lead, user, quand, *, etape=None):
    """MRY10 — « Rappelez-moi jeudi » : décale une touche ET sa suite.

    Décaler la SEULE touche du jour serait faux : les suivantes se
    téléscoperaient avec elle (« rappelez-moi dans 10 jours » ferait tomber
    trois touches la même semaine). Toutes les touches SUIVANTES de la même
    cadence glissent donc du MÊME delta — jamais réordonnées, jamais
    recalculées depuis zéro.

    ``quand`` est un datetime (ou une date) ; il est recalé sur la fenêtre de
    la société pour le CANAL de la touche déplacée (07/09/2026 : « rappelez-moi
    jeudi 8 h » vaut 08:30 pour un message, 09:00 pour un appel). ``etape``
    cible une touche précise ; sinon c'est la prochaine À FAIRE. Renvoie la
    touche déplacée, ou ``None`` s'il n'y en a aucune.
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
    cible.due_at = nouveau
    cible.due_date = nouveau.astimezone(horaires.CASABLANCA).date()
    cible.save(update_fields=['due_at', 'due_date'])

    if delta:
        suivantes = lead.relance_etapes.filter(
            cadence=cible.cadence, statut=RelanceEtape.Statut.A_FAIRE,
            ordre__gt=cible.ordre, due_at__isnull=False)
        for suivante in suivantes:
            decalee = suivante.due_at + delta
            suivante.due_at = decalee
            suivante.due_date = decalee.astimezone(
                horaires.CASABLANCA).date()
            suivante.save(update_fields=['due_at', 'due_date'])

    quand_local = nouveau.astimezone(horaires.CASABLANCA)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=('Rappel demandé le '
              f'{quand_local:%d/%m/%Y à %H:%M} — touche « '
              f'{(cible.libelle or cible.get_canal_display())} » reportée.'))

    prochaine = _prochaine_touche_a_faire(lead)
    lead.relance_date = prochaine.due_date if prochaine else None
    lead.save(update_fields=['relance_date'])
    sync_relance_activity(lead, user)
    return cible


def arreter_cadence(lead, *, user, motif, cadences=None):
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

    Renvoie le nombre de touches arrêtées."""
    ouvertes = lead.relance_etapes.filter(statut=RelanceEtape.Statut.A_FAIRE)
    if cadences:
        ouvertes = ouvertes.filter(cadence__in=list(cadences))
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
    prochaine = _prochaine_touche_a_faire(lead)
    lead.relance_date = prochaine.due_date if prochaine else None
    lead.save(update_fields=['relance_date'])
    sync_relance_activity(lead, user)
    return len(pks)


def arreter_cadence_du_lead_id(lead_id, *, company=None, user=None, motif='',
                               cadences=None):
    """Variante par ID, best-effort — pour les receivers qui ne tiennent qu'un
    ``devis.lead_id``. Ne lève JAMAIS : un arrêt de cadence en échec ne doit
    pas faire retomber l'acceptation d'un devis déjà actée."""
    if not lead_id:
        return 0
    try:
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


def _leads_ouverts_count(commercial):
    """XSAL11 — Nombre de leads OUVERTS assignés à un commercial : stage NON
    SIGNED/COLD (clés STAGES.py — jamais codées en dur) et jamais perdu. Sert
    de plafond de saturation pour la rotation round-robin équilibrée."""
    return Lead.objects.filter(
        owner=commercial, perdu=False,
    ).exclude(stage__in=[stages.SIGNED, stages.COLD]).count()


def _next_balanced_round_robin_commercial(company, plafond):
    """XSAL11 — Round-robin ÉQUILIBRÉ : parmi les commerciaux actifs de la
    société (rôle « Commercial » — pas de territoire câblé dans ce dépôt,
    voir FG236), affecte au prochain dans la rotation (moins de leads
    OUVERTS d'abord, départage par id) EN SAUTANT quiconque a atteint/dépassé
    ``plafond`` leads ouverts. Renvoie None si TOUS les commerciaux actifs
    sont saturés (l'appelant retombe alors sur ``responsable_defaut_leads``)
    ou s'il n'y a aucun commercial actif du tout."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    candidats = list(
        User.objects.filter(
            company=company, is_active=True, role__nom='Commercial',
        ).order_by('id')
    )
    if not candidats:
        return None
    eligibles = [
        c for c in candidats if _leads_ouverts_count(c) < plafond
    ]
    if not eligibles:
        return None  # tous saturés — fallback à l'appelant
    eligibles.sort(key=lambda c: (_leads_ouverts_count(c), c.id))
    return eligibles[0]


def default_responsable_for(company, lead_attrs=None):
    """Responsable assigné par défaut aux nouveaux leads d'une société.

    NTCRM1 — quand ``lead_attrs`` (dict brut : ville/type_installation/
    montant_estime/canal — le lead n'existe pas encore à ce stade) est fourni,
    le moteur de territoires (``apps.territoires``) est consulté EN PREMIER :
    si au moins un territoire actif matche, son membre résolu par rotation
    l'emporte. Sinon (aucun territoire ne matche, ``lead_attrs`` absent, ou
    l'app territoires échoue) — repli sur le comportement round-robin XSAL11
    ci-dessous, STRICTEMENT inchangé. ``lead_attrs=None`` (défaut) est donc
    byte-identique au comportement pré-NTCRM1 pour tout appelant existant qui
    ne le passe pas.

    XSAL11 — quand ``CompanyProfile.round_robin_leads_actif`` est ON, la
    rotation ÉQUILIBRÉE (en sautant les commerciaux saturés — plafond
    ``round_robin_plafond_leads_ouverts``) est tentée EN PREMIER ; si tous
    sont saturés, replie sur le responsable par défaut explicite. OFF
    (défaut) = comportement byte-identique à avant XSAL11 : le profil
    entreprise (Paramètres → « Responsable par défaut ») prime, et QW6 replie
    sur un round-robin simple (par charge totale) si ce réglage est vide.
    None si aucune société ou aucun commercial actif (comportement inchangé
    dans ce cas — un lead sans owner reste possible).
    """
    if company is None:
        return None
    if lead_attrs is not None:
        try:
            from apps.territoires.services import resoudre_owner_pour_attrs
            territoire_owner = resoudre_owner_pour_attrs(company, lead_attrs)
            if territoire_owner is not None:
                return territoire_owner
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'NTCRM1: résolution territoire échouée, repli round-robin',
                exc_info=True)
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.objects.filter(company=company).first()
    explicit = profile.responsable_defaut_leads if profile else None

    if profile is not None and profile.round_robin_leads_actif:
        balanced = _next_balanced_round_robin_commercial(
            company, profile.round_robin_plafond_leads_ouverts)
        if balanced is not None:
            return balanced
        # Tous saturés (ou aucun commercial actif) — fallback explicite.
        return explicit

    if explicit is not None:
        return explicit
    return pick_round_robin_owner(company)


def pick_round_robin_owner(company):
    """QW6 — Choisit un propriétaire par ROUND-ROBIN parmi les utilisateurs
    commerciaux actifs de la société (permission ``crm_creer``), pour qu'un
    lead ne reste JAMAIS sans responsable quand aucun « responsable par
    défaut » n'est configuré. Sans état dédié à maintenir : le tour revient à
    l'utilisateur ayant le MOINS de leads assignés (ties départagés par id,
    ordre stable) — équivalent d'une rotation, sans compteur externe. None si
    la société n'a aucun utilisateur commercial actif."""
    from django.contrib.auth import get_user_model
    from django.db.models import Count, Q

    User = get_user_model()
    candidates = list(
        User.objects.filter(
            company=company, is_active=True,
        ).filter(
            Q(role__permissions__contains=['crm_creer'])
            | Q(role__isnull=True, role_legacy__in=['admin', 'responsable']),
        ).annotate(
            nb_leads=Count('leads_assignes'),
        ).order_by('nb_leads', 'pk').distinct()
    )
    return candidates[0] if candidates else None


# FG28 — SLA première prise de contact ────────────────────────────────────────

def journaliser_whatsapp_ouvert(etape, user):
    """RELANCE-WA (fondateur 08/09/2026) — ouvrir WhatsApp depuis une touche
    n'AVANCE plus la touche. Le clic est INSCRIT dans l'historique du lead
    (activité typée WhatsApp : comptée comme tentative MRY20 et comme premier
    contact MRY19 par les récepteurs) et la touche reste À FAIRE jusqu'à la
    réponse aux questions guidées (« Fait »). Avant, le clic marquait la
    touche faite (décision D5 du 07/09) : une conversation ouverte n'est pas
    une réponse du client. Aucune issue posée → aucune cadence arrêtée,
    aucune avance d'étape."""
    libelle = (etape.libelle or '').strip() or etape.get_canal_display()
    return LeadActivity.objects.create(
        company=etape.company, lead=etape.lead, user=user,
        kind=LeadActivity.Kind.WHATSAPP,
        body=(f'WhatsApp ouvert — touche « {libelle} » (cadence '
              f'{etape.cadence}) : message préparé ; la touche reste à faire '
              "jusqu'à la réponse du client."))


def marquer_premier_contact(lead, *, when=None) -> bool:
    """MRY19 — LA pose de ``first_contacted_at``. Une seule, partout.

    Quatre endroits l'écrivaient à la main, avec quatre conditions
    LÉGÈREMENT différentes (dont deux qui exigeaient l'étape NEW) : un lead
    saisi à la main, déjà CONTACTED, ne recevait donc JAMAIS d'horodatage —
    et sortait silencieusement du KPI de premier contact. Ici la règle est
    unique et sans condition d'étape : si le champ est vide, on le pose.

    Idempotente — jamais un écrasement. Renvoie True si la pose a eu lieu.
    Best-effort : ne lève jamais."""
    try:
        if lead is None or getattr(lead, 'first_contacted_at', None):
            return False
        lead.first_contacted_at = when or timezone.now()
        lead.save(update_fields=['first_contacted_at'])
        return True
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return False


def maybe_set_first_contacted_at(old_lead, new_lead):
    """Pose ``first_contacted_at`` quand le stage quitte NEW.

    Signature INCHANGÉE (appelée par ``LeadViewSet.perform_update``) ; MRY19
    délègue simplement à ``marquer_premier_contact`` — plus aucune seconde
    règle qui pourrait diverger."""
    try:
        if old_lead.stage == stages.NEW and new_lead.stage != stages.NEW:
            marquer_premier_contact(new_lead)
    except Exception:
        pass


def lead_sla_hours(company) -> int:
    """Retourne le délai SLA (heures) configuré pour la société. 24 par défaut."""
    if company is None:
        return 24
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        if profile is not None:
            return profile.lead_sla_hours
    except Exception:
        pass
    return 24


def callback_sla_hours(company) -> int:
    """QW4 — Délai SLA (heures) d'un RAPPEL demandé (``contact_preference=
    phone_ok``), plus SERRÉ que le SLA générique de premier contact
    (``lead_sla_hours``) : la moitié, plancher 2 h. AUCUN nouveau champ
    société (on reste dans `apps/crm`, pas de dépendance nouvelle sur
    `parametres`) — dérivé du SLA générique déjà configurable. 0 (SLA
    générique désactivé) désactive aussi le SLA rappel."""
    generic = lead_sla_hours(company)
    if not generic:
        return 0
    return max(2, generic // 2)


# Champs scalaires recopiés sur le survivant SEULEMENT s'il les a vides
# (« on garde la valeur la plus complète », jamais d'écrasement).
_MERGE_FILL_FIELDS = [
    'prenom', 'societe', 'email', 'telephone', 'whatsapp', 'adresse', 'ville',
    'langue_preferee', 'gps_lat', 'gps_lng',
    'facture_hiver', 'facture_ete', 'ete_differente',
    'conso_mensuelle_kwh', 'tranche_onee', 'raccordement', 'regularisation_8221',
    'type_installation', 'priorite', 'relance_date',
    'type_toiture', 'surface_toiture_m2', 'orientation', 'inclinaison_deg',
    'ombrage', 'ombrage_notes', 'nb_etages', 'structure_pref',
    'taille_souhaitee_kwc', 'batterie_souhaitee', 'pompe_cv', 'pompe_hmt_m',
    'pompe_debit_m3h', 'canal', 'motif_perte', 'note', 'whatsapp_opt_in',
    # Visite technique (légère) — préservée à la fusion.
    'visite_prevue_le', 'visite_effectuee', 'visite_notes',
    # Intake site web (taqinor.ma) — attribution + diagnostic préservés.
    'bill_range_bucket', 'roof_type', 'roi_band', 'consent_timestamp', 'fbclid',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
]


def normalize_phone(value):
    """Téléphone normalisé pour comparaison : chiffres seuls, indicatif marocain
    réduit, zéro initial retiré. '+212 6 12-34' et '0612 34' → même clé."""
    digits = _re.sub(r'\D', '', str(value or ''))
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('212'):
        digits = digits[3:]
    digits = digits.lstrip('0')
    return digits


def normalize_email(value):
    return str(value or '').strip().lower()


def _strip_accents(text):
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text)
        if not unicodedata.combining(c))


def normalize_name(nom, prenom=None, societe=None):
    """Clé de nom pour le rapprochement : accents retirés, minuscules, mots
    triés, ponctuation/espaces écrasés. « Société Bélkacem » et « belkacem
    societe » donnent la même clé. Vide si le nom est trop court (évite de
    rapprocher des leads sur un nom générique d'un seul caractère)."""
    parts = [p for p in (nom, prenom, societe) if p]
    raw = _strip_accents(' '.join(str(p) for p in parts)).lower()
    raw = _re.sub(r'[^a-z0-9 ]', ' ', raw)
    tokens = sorted(t for t in raw.split() if t)
    key = ' '.join(tokens)
    return key if len(key) >= 4 else ''


def _completeness(lead):
    """Score « complétude » d'un lead : nombre de champs de fond renseignés.
    Sert à proposer par défaut le survivant le plus riche lors d'une fusion."""
    score = 0
    for field in _MERGE_FILL_FIELDS:
        val = getattr(lead, field, None)
        if val not in (None, '', False):
            score += 1
    return score


def find_duplicate_clusters(company, include_archived=False):
    """Scanne TOUS les leads d'une société et regroupe les doublons probables
    par téléphone OU email OU nom normalisé (union-find). Renvoie une liste de
    clusters (chacun une liste de Lead, ≥ 2 membres), triés par taille puis par
    membre le plus récent. Les leads archivés sont inclus seulement si demandé
    (ils restent visibles pour comprendre une fusion passée)."""
    qs = Lead.objects.filter(company=company)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    leads = list(qs)

    parent = {lead.pk: lead.pk for lead in leads}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Indexe par chaque clé ; union des leads partageant une clé non vide.
    for keyer in (
        lambda lead: ('p', normalize_phone(lead.telephone)),
        lambda lead: ('e', normalize_email(lead.email)),
        lambda lead: ('n', normalize_name(lead.nom, lead.prenom, lead.societe)),
    ):
        buckets = {}
        for lead in leads:
            tag, val = keyer(lead)
            if not val:
                continue
            buckets.setdefault((tag, val), []).append(lead.pk)
        for members in buckets.values():
            first = members[0]
            for other in members[1:]:
                union(first, other)

    groups = {}
    by_id = {lead.pk: lead for lead in leads}
    for lead in leads:
        groups.setdefault(find(lead.pk), []).append(lead)

    clusters = [g for g in groups.values() if len(g) >= 2]
    # Chaque cluster : membre le plus récent en tête ; tri global par taille.
    for g in clusters:
        g.sort(key=lambda lead_: lead_.date_creation, reverse=True)
    clusters.sort(
        key=lambda g: (len(g), max(le.date_creation for le in g)),
        reverse=True)
    return clusters, by_id


def cluster_match_keys(group):
    """Clés de rapprochement PARTAGÉES par au moins deux membres d'un cluster
    (pour expliquer dans l'UI POURQUOI ils sont regroupés) : 'telephone',
    'email' et/ou 'nom'. Renvoie une liste ordonnée et stable."""
    out = []
    checks = (
        ('telephone', lambda le: normalize_phone(le.telephone)),
        ('email', lambda le: normalize_email(le.email)),
        ('nom', lambda le: normalize_name(le.nom, le.prenom, le.societe)),
    )
    for label, keyer in checks:
        seen = {}
        shared = False
        for le in group:
            val = keyer(le)
            if not val:
                continue
            if val in seen:
                shared = True
                break
            seen[val] = True
        if shared:
            out.append(label)
    return out


def find_duplicate_leads(lead):
    """Leads probablement en double : même téléphone OU email normalisé, même
    société, hors le lead lui-même. Inclut les archivés (pour les retrouver)."""
    return find_duplicates_by_contact(
        lead.company, phone=lead.telephone, email=lead.email,
        exclude_pk=lead.pk)


def find_duplicates_by_contact(company, *, phone=None, email=None,
                               exclude_pk=None):
    """Leads d'une société partageant un téléphone OU un email normalisé avec
    les valeurs fournies (saisie libre acceptée — mêmes normaliseurs que la
    détection de doublons). Sert AUSSI au contrôle PRÉ-CRÉATION, où aucun Lead
    n'existe encore (d'où l'absence d'instance). Inclut les archivés.

    QW10 — requête INDEXÉE sur les colonnes normalisées maintenues par
    `Lead.save()` (`phone_normalise`/`email_normalise`, backfillées par la
    migration pour les lignes existantes) — jamais un scan Python complet de
    la société à chaque appel."""
    from django.db.models import Q

    phone = normalize_phone(phone)
    email = normalize_email(email)
    if not phone and not email:
        return []
    qs = Lead.objects.filter(company=company)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)

    q = Q()
    if phone:
        q |= Q(phone_normalise=phone)
    if email:
        q |= Q(email_normalise=email)
    return list(qs.filter(q))


def is_strong_identity_match(other, *, phone=None, email=None):
    """« Identité forte » : `other` partage À LA FOIS l'e-mail normalisé exact
    ET le téléphone normalisé exact avec les valeurs fournies.

    Niveau DISTINCT du rapprochement ordinaire (même téléphone OU même
    e-mail) : le fondateur veut pouvoir dire « très probablement le même
    client » sans jamais fusionner à la place du commercial. Les deux clés
    doivent être non vides des DEUX côtés — un lead sans e-mail (ou sans
    téléphone) n'est jamais une identité forte, seulement un doublon possible.
    """
    phone = normalize_phone(phone)
    email = normalize_email(email)
    if not phone or not email:
        return False
    return (normalize_phone(other.telephone) == phone
            and normalize_email(other.email) == email)


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
    with transaction.atomic():
        for absorbed in others:
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
            # 5) Client : adopter celui de l'absorbé si le survivant n'en a pas.
            if not survivor.client_id and absorbed.client_id:
                survivor.client = absorbed.client
            # 6) Compléter les champs VIDES du survivant.
            for field in _MERGE_FILL_FIELDS:
                cur = getattr(survivor, field, None)
                if cur in (None, '', False):
                    val = getattr(absorbed, field, None)
                    if val not in (None, '', False):
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
        survivor.save()
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

    Renvoie ``{'examines': int, 'mis_a_jour': int}``.
    """
    from datetime import timedelta

    from .scoring import compute_score

    seuil = timezone.now() - timedelta(days=DELAI_SCORE_OBSOLETE_JOURS)
    examines = 0
    mis_a_jour = 0
    queryset = (Lead.objects.filter(date_modification__lt=seuil)
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
            # NTMKT18 — additif : le seuil peut AUSSI se déclencher sur le
            # score de maturité marketing (jamais sur le score de qualité
            # QJ6 lui-même, jamais lu si le paramètre société marketing est
            # resté désactivé — comportement actuel inchangé par défaut).
            # Best-effort : une erreur côté marketing ne bloque jamais XMKT21.
            maturite_ok = False
            try:
                from apps.marketing import selectors as marketing_selectors
                if marketing_selectors.maturite_active_pour_mql(lead.company):
                    maturite_ok = (
                        marketing_selectors.score_maturite_valeur(
                            lead.company, lead.pk) >= seuil)
            except Exception:
                maturite_ok = False
            if not maturite_ok:
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


def resolve_client_for_lead(lead: Lead) -> Client:
    if lead.client_id:
        # Rattache le Tiers du client déjà lié (stade amont ARC56), sans
        # jamais modifier la résolution existante ni un champ de nom.
        attacher_tiers_au_lead(lead, lead.client)
        return lead.client

    def _find_existing():
        if lead.email:
            match = Client.objects.filter(
                company=lead.company, email__iexact=lead.email,
            ).first()
            if match is not None:
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
        lead_phone = normalize_phone(lead.telephone)
        if not lead_phone:
            return None
        for candidate in Client.objects.filter(company=lead.company):
            if normalize_phone(candidate.telephone) == lead_phone:
                return candidate
        return None

    # CRX24 — le chemin SANS e-mail (repli téléphone QX17) n'a aucune
    # contrainte d'unicité en base pour l'arbitrer : on le sérialise par
    # (société, téléphone normalisé) le temps du « chercher puis créer ». Le
    # chemin e-mail garde son arbitrage par la base (contrainte unique
    # insensible à la casse + relecture) et le verrou y est un no-op.
    cle_verrou = '' if lead.email else normalize_phone(lead.telephone)
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
            with transaction.atomic():
                client = Client.objects.create(
                    company=lead.company,
                    nom=lead.nom,
                    prenom=lead.prenom,
                    email=lead.email,
                    telephone=(lead.telephone or '')[:20] or None,
                    adresse=adresse or None,
                    langue_document=langue_document,
                )
        except IntegrityError:
            # CRX24 — attrape AUSSI la contrainte insensible à la casse
            # ``crx24_client_email_unique_ci`` : ``_find_existing`` cherche en
            # ``email__iexact``, donc la relecture retrouve bien le gagnant de
            # la course, quelle que soit la casse qu'il a écrite.
            client = _find_existing()
            if client is None:
                raise

    return client


def convertir_lead_en_client(*, lead, user, mode, client_id=None):
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
        client = Client.objects.filter(
            id=client_id, company=lead.company).first()
        if client is None:
            raise ValueError("Client introuvable dans votre société.")
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


def scan_carte_visite(*, company, file_bytes, mime_hint=''):
    """XSAL8 — Extrait nom/société/téléphone/email d'une photo de carte de
    visite, PRÉ-VÉRIFIE les doublons, et renvoie un dict prêt à pré-remplir le
    modal « Lead express » — NE CRÉE JAMAIS de lead (l'utilisateur valide).

    Lève :class:`CarteVisiteScanUnavailable` si le fichier n'est pas une image
    reconnue (magic bytes) OU trop volumineux OU si aucun fournisseur OCR
    n'est configuré (``ZHIPU_API_KEY`` absent — dégradation propre, jamais
    d'appel réseau). Ne persiste JAMAIS l'image reçue au-delà du traitement en
    mémoire (aucun stockage MinIO — contrairement aux autres flux OCR qui
    rattachent le fichier en pièce jointe)."""
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
            company, phone=telephone or None, email=email or None)
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
    ouverts = [lead_ for lead_ in non_archives if not lead_.perdu]
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
    reactivables = [lead_ for lead_ in non_archives if lead_.perdu]
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
        lead.save(update_fields=['telephone', 'whatsapp', 'phone_normalise'])
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
        q = _norm_form_text(raw_name)
        v = _norm_form_text(raw_value)
        if 'facture' in q:
            nums = [int(n) for n in _re.findall(r'\d{3,6}', v)]
            if len(nums) >= 2:
                extras['facture_estimee'] = (nums[0] + nums[1]) // 2
            elif nums:
                # Tranche ouverte (« plus de 4000 dh ») : borne déclarée,
                # jamais un montant inventé au-delà.
                extras['facture_estimee'] = nums[0]
            extras['facture_declaree'] = raw_value
        elif 'quand' in q or 'commencer' in q or 'delai' in q:
            if 'plus tot possible' in v or 'ce mois' in v or 'immediat' in v:
                extras['priorite'] = Lead.Priorite.HAUTE
            elif 'renseigne' in v:
                extras['priorite'] = Lead.Priorite.BASSE
            else:
                extras['priorite'] = Lead.Priorite.NORMALE
        elif 'install' in q:
            if any(k in v for k in ('villa', 'maison', 'appartement',
                                    'domicile', 'residen')):
                extras['type_installation'] = Lead.TypeInstallation.RESIDENTIEL
            elif any(k in v for k in ('entreprise', 'societe', 'commerce',
                                      'bureau', 'magasin', 'hotel', 'local')):
                extras['type_installation'] = Lead.TypeInstallation.COMMERCIAL
            elif 'usine' in v or 'industri' in v:
                extras['type_installation'] = Lead.TypeInstallation.INDUSTRIEL
            elif any(k in v for k in ('ferme', 'agricole', 'pompage', 'puits')):
                extras['type_installation'] = Lead.TypeInstallation.AGRICOLE
    return extras


def _apply_meta_form_extras(lead, extras):
    """Pose les champs structurés du formulaire SANS jamais écraser une valeur
    déjà présente (une saisie humaine gagne toujours sur l'auto-remplissage).
    ``priorite`` : posée seulement en « upgrade » (NORMALE par défaut → HAUTE
    déclarée) — jamais de downgrade automatique. Renvoie la liste des champs
    modifiés (vide si rien à faire)."""
    from decimal import Decimal

    changed = []
    if extras.get('facture_estimee') is not None and lead.facture_hiver is None:
        lead.facture_hiver = Decimal(int(extras['facture_estimee']))
        changed.append('facture_hiver')
    if extras.get('type_installation') and not lead.type_installation:
        lead.type_installation = extras['type_installation']
        changed.append('type_installation')
    if (extras.get('priorite') == Lead.Priorite.HAUTE
            and lead.priorite == Lead.Priorite.NORMALE):
        lead.priorite = Lead.Priorite.HAUTE
        changed.append('priorite')
    if lead.telephone and not lead.whatsapp:
        # Un lead Meta arrive par mobile : le même numéro sert de lien wa.me
        # pour la première prise de contact de Meryem.
        lead.whatsapp = lead.telephone
        changed.append('whatsapp')
    return changed


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
    if extras.get('facture_estimee') is not None:
        lines.append(
            '(facture hiver pré-remplie à %s MAD depuis la tranche déclarée '
            '« %s » — à préciser au premier appel)'
            % (int(extras['facture_estimee']),
               extras.get('facture_declaree', '').replace('_', ' ')))
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
        changed = _apply_meta_form_extras(existing, extras)
        if fields.get('ville') and not existing.ville:
            existing.ville = fields['ville']
            changed.append('ville')
        if changed:
            existing.save(update_fields=changed)
        _ensure_meta_form_note(existing, extras, form_id=str(form_id or ''))
        return existing

    nom = (fields.get('nom') or '').strip() or 'Lead Meta Ads'
    telephone = fields.get('telephone') or ''
    email = fields.get('email') or ''

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
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default
    # À la CRÉATION, le délai déclaré pose la priorité pleinement (haute,
    # normale ou basse) ; en enrichissement (leads existants), seule la
    # montée NORMALE→HAUTE est automatique (_apply_meta_form_extras).
    if extras.get('priorite'):
        extra['priorite'] = extras['priorite']
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
    changed = _apply_meta_form_extras(lead, extras)
    if changed:
        lead.save(update_fields=changed)
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


def noter_touche_marketing(lead, message, *, ordre=0, cout=None):
    """XMKT16 — Consigne un événement marketing significatif (envoi/ouverture/
    clic de campagne, étape de séquence exécutée, réponse WhatsApp entrante)
    dans le chatter du lead (``LeadActivity``) + le journal d'attribution
    multi-touch FG204 (``PointContact``). Appelé par ``apps.compta`` — jamais
    d'import du modèle CRM depuis compta, ce point d'entrée reste dans
    ``apps.crm.services`` comme toutes les écritures cross-app.

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

def _company_fallback_managers(company):
    """QJ27 — Managers de repli d'une société : utilisateurs actifs portant le
    rôle fin « Commercial responsable » ou « Directeur ».

    Sert quand un lead n'a pas de responsable, ou quand le responsable n'a pas
    de supérieur direct (``supervisor``). Liste éventuellement vide — jamais
    d'exception. La société est toujours résolue côté serveur."""
    if company is None:
        return []
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return list(User.objects.filter(
            company=company, is_active=True,
            role__nom__in=('Commercial responsable', 'Directeur'),
        ).order_by('id'))
    except Exception:  # noqa: BLE001 — best-effort
        return []


def user_and_superior_recipients(user, company):
    """QJ27 — Destinataires « handler + supérieur » pour une notification.

    Renvoie une liste dédupliquée (ordre préservé) :
      - le handler (``user``) s'il est renseigné ;
      - son ``supervisor`` direct s'il existe, SINON les managers de repli de
        la société (« Commercial responsable » / « Directeur ») ;
      - handler absent → uniquement les managers de repli.

    Peut renvoyer une liste vide (aucun destinataire résolvable)."""
    recipients = []
    if user is not None:
        recipients.append(user)
        superior = getattr(user, 'supervisor', None)
        if superior is not None and getattr(superior, 'is_active', True):
            recipients.append(superior)
        else:
            recipients.extend(_company_fallback_managers(company))
    else:
        recipients.extend(_company_fallback_managers(company))
    seen, out = set(), []
    for u in recipients:
        pk = getattr(u, 'pk', None)
        if pk is not None and pk not in seen:
            seen.add(pk)
            out.append(u)
    return out


def lead_notification_recipients(lead):
    """QJ27 — Destinataires des notifications d'un lead : owner + supérieur
    (repli managers société quand l'un des deux manque)."""
    return user_and_superior_recipients(
        getattr(lead, 'owner', None), getattr(lead, 'company', None))


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
        digits = ''.join(c for c in (phone_raw or '') if c.isdigit())
        if not digits:
            return None
        # Format international marocain (wa.me exige l'indicatif pays).
        if digits.startswith('00'):
            digits = digits[2:]
        if digits.startswith('0'):
            digits = '212' + digits[1:]
        elif not digits.startswith('212'):
            digits = '212' + digits
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
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Nouveau prospect'
        wa_url = _build_lead_wa_reply_url(lead)
        suffixe = ' (sous le seuil)' if sous_seuil else ''
        body_parts = [f'Un nouveau lead vient d\'arriver : {nom}{suffixe}.']
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
        notify_many(
            recipients,
            'lead_new',
            f'Nouveau lead : {nom}{suffixe}',
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ2: notify_new_lead échoué pour lead #%s : %s',
            getattr(lead, 'pk', '?'), exc)


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
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ2: notify_devis_opened échoué pour lead #%s devis %s : %s',
            getattr(lead, 'pk', '?'), devis_reference, exc)


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

BULK_ACTIONS = {
    'reassign', 'add_tag', 'remove_tag', 'set_stage', 'set_canal',
    'set_priorite', 'set_relance', 'clear_relance', 'set_perdu',
    'unset_perdu', 'archive', 'unarchive', 'delete', 'plan_activity',
    'prepare_whatsapp',  # FG33 — file de click-through WhatsApp en masse
}

# Priorités valides (clés du modèle Lead.Priorite).
_PRIORITES = {'basse', 'normale', 'haute'}
# Actions réservées à l'admin (la suppression définitive l'est déjà partout).
BULK_ADMIN_ONLY = {'delete'}


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


def _parse_date(value):
    from datetime import date
    if isinstance(value, date):
        return value
    if not value:
        return None
    from django.utils.dateparse import parse_date
    return parse_date(str(value))


def _resolve_activity_type(company, type_id, type_nom):
    """Type d'activité cible pour une planification en masse : par id (société
    courante) sinon par nom (créé à la volée s'il manque), repli sur « À faire ».
    """
    from apps.records.models import ActivityType
    if type_id not in (None, '', 'null'):
        atype = ActivityType.objects.filter(id=type_id, company=company).first()
        if atype is not None:
            return atype
    nom = (type_nom or 'À faire').strip() or 'À faire'
    atype = ActivityType.objects.filter(company=company, nom=nom).first()
    if atype is None:
        atype = ActivityType.objects.create(company=company, nom=nom, ordre=50)
    return atype


def coerce_id_list(raw):
    """Normalise une liste d'ids reçue du client en entiers uniques.

    Accepte ints et chaînes numériques ; déduplique en préservant l'ordre.
    Lève ValueError sur un élément non entier — la vue le traduit en 400 propre
    au lieu de laisser un 500 remonter du `id__in` (PostgreSQL refuse un id
    non numérique). Sert aux endpoints en masse + WhatsApp.
    """
    if not isinstance(raw, (list, tuple)):
        raise ValueError("Liste d'identifiants invalide.")
    out = []
    seen = set()
    for item in raw:
        if isinstance(item, bool):
            raise ValueError("Identifiant invalide.")
        try:
            value = int(item)
        except (TypeError, ValueError):
            raise ValueError("Identifiant invalide.")
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def apply_bulk_action(*, company, user, lead_ids, op, params):
    """Applique une action en masse à une sélection de leads de la société.

    Renvoie un récapitulatif : nombre mis à jour, nombre inchangés, et la liste
    des leads ignorés avec leur raison (en français). Chaque modification écrit
    une entrée Historique marquée « en masse ».
    """
    from django.db import transaction

    if op not in BULK_ACTIONS:
        raise ValueError("Action en masse inconnue.")

    lead_ids = coerce_id_list(lead_ids)
    leads = list(
        Lead.objects.filter(company=company, id__in=lead_ids).order_by('id'))
    updated, unchanged, skipped = 0, 0, []

    def skip(lead, reason):
        skipped.append({'id': lead.id, 'nom': str(lead), 'reason': reason})

    # Pré-validation des paramètres dépendant de l'action.
    target_stage = None
    owner_obj = None
    tag = (params.get('tag') or '').strip() if op in ('add_tag', 'remove_tag') else None
    relance = None
    target_canal = None
    target_priorite = None
    activity_type = None
    activity_due = None
    activity_summary = None
    if op == 'set_stage':
        target_stage = params.get('stage')
        if target_stage not in stages.STAGES:
            raise ValueError("Étape cible invalide.")
    elif op == 'set_canal':
        target_canal = (params.get('canal') or '').strip()
        if not target_canal:
            raise ValueError("Canal cible vide.")
        # Le canal doit appartenir au référentiel géré (s'il existe).
        if (Canal.objects.filter(company=company).exists()
                and not Canal.objects.filter(
                    company=company, cle=target_canal, archived=False).exists()):
            raise ValueError("Canal inconnu.")
    elif op == 'set_priorite':
        target_priorite = params.get('priorite')
        if target_priorite not in _PRIORITES:
            raise ValueError("Priorité invalide.")
    elif op == 'reassign':
        owner_obj = _resolve_owner(company, params.get('owner'))
        if params.get('owner') not in (None, '', 'null') and owner_obj is None:
            raise ValueError("Responsable introuvable dans cette société.")
    elif op in ('add_tag', 'remove_tag') and not tag:
        raise ValueError("Étiquette vide.")
    elif op == 'set_relance':
        relance = _parse_date(params.get('relance_date'))
        if relance is None:
            raise ValueError("Date de relance invalide.")
    elif op == 'plan_activity':
        activity_due = _parse_date(params.get('due_date'))
        if activity_due is None:
            raise ValueError("Date d'échéance invalide.")
        activity_summary = (params.get('summary') or '').strip()
        if not activity_summary:
            raise ValueError("Intitulé de l'activité vide.")
        activity_type = _resolve_activity_type(
            company, params.get('activity_type_id'), params.get('type_nom'))

    with transaction.atomic():
        for lead in leads:
            if op == 'reassign':
                if lead.owner_id == (owner_obj.id if owner_obj else None):
                    unchanged += 1
                    continue
                old = lead.owner
                lead.owner = owner_obj
                lead.save(update_fields=['owner'])
                activity.log_bulk_change(lead, user, 'owner', old, owner_obj)
                sync_relance_activity(lead, user)
                updated += 1

            elif op in ('add_tag', 'remove_tag'):
                current = [t.strip() for t in (lead.tags or '').split(',') if t.strip()]
                has = tag in current
                if op == 'add_tag' and has:
                    unchanged += 1
                    continue
                if op == 'remove_tag' and not has:
                    unchanged += 1
                    continue
                old = lead.tags or ''
                if op == 'add_tag':
                    current.append(tag)
                else:
                    current = [t for t in current if t != tag]
                lead.tags = ', '.join(current)[:500]
                lead.save(update_fields=['tags'])
                activity.log_bulk_change(lead, user, 'tags', old, lead.tags)
                updated += 1

            elif op == 'set_stage':
                if lead.perdu:
                    skip(lead, "lead Perdu — étape non modifiée")
                    continue
                if not _bulk_stage_allowed(lead.stage, target_stage):
                    skip(lead, "étape déjà atteinte ou recul non autorisé")
                    continue
                old = lead.stage
                # CRX20 — chemin canonique : le bulk émet enfin
                # ``lead_stage_changed`` (playbooks NTCRM12 + séquences compta
                # XMKT1 partaient pour un PATCH unitaire, jamais pour un bulk).
                appliquer_stage_lead(lead, target_stage, user=user)
                activity.log_bulk_change(lead, user, 'stage', old, target_stage)
                # QJ9 — entrée manuelle en masse dans SIGNED : pas de CAPI ici
                # (pas de devis accepté associé ni d'attribution UTM disponible).
                updated += 1

            elif op == 'set_canal':
                if lead.canal == target_canal:
                    unchanged += 1
                    continue
                old = lead.canal
                lead.canal = target_canal
                lead.save(update_fields=['canal'])
                activity.log_bulk_change(lead, user, 'canal', old, target_canal)
                updated += 1

            elif op == 'set_priorite':
                if (lead.priorite or 'normale') == target_priorite:
                    unchanged += 1
                    continue
                old = lead.priorite
                lead.priorite = target_priorite
                lead.save(update_fields=['priorite'])
                activity.log_bulk_change(lead, user, 'priorite', old, target_priorite)
                updated += 1

            elif op == 'set_relance':
                if lead.relance_date == relance:
                    unchanged += 1
                    continue
                old = lead.relance_date
                lead.relance_date = relance
                lead.save(update_fields=['relance_date'])
                activity.log_bulk_change(lead, user, 'relance_date', old, relance)
                sync_relance_activity(lead, user)
                updated += 1

            elif op == 'clear_relance':
                if not lead.relance_date:
                    unchanged += 1
                    continue
                old = lead.relance_date
                lead.relance_date = None
                lead.save(update_fields=['relance_date'])
                activity.log_bulk_change(lead, user, 'relance_date', old, None)
                sync_relance_activity(lead, user)
                updated += 1

            elif op == 'set_perdu':
                motif = (params.get('motif') or '').strip() or None
                if not motif:
                    # MRY22 — même exigence qu'à l'unité : perdre 40 leads
                    # d'un coup SANS raison est pire, pas plus acceptable.
                    raise ValueError(
                        'Motif de perte obligatoire pour une mise en perte '
                        'en masse.')
                if lead.perdu and lead.motif_perte == motif:
                    unchanged += 1
                    continue
                old_perdu, old_motif = lead.perdu, lead.motif_perte
                lead.perdu = True
                lead.motif_perte = motif
                lead.save(update_fields=['perdu', 'motif_perte'])
                if not old_perdu:
                    activity.log_bulk_change(lead, user, 'perdu', old_perdu, True)
                    # MRY9 (c) — un lead perdu EN MASSE arrête ses relances
                    # exactement comme un lead perdu à l'unité : sans cela,
                    # une purge de 40 leads laissait 40 cadences vivantes.
                    arreter_cadence(lead, user=user,
                                    motif=motif or 'lead perdu')
                if old_motif != motif:
                    activity.log_bulk_change(lead, user, 'motif_perte', old_motif, motif)
                updated += 1

            elif op == 'unset_perdu':
                if not lead.perdu:
                    unchanged += 1
                    continue
                lead.perdu = False
                old_motif = lead.motif_perte
                lead.motif_perte = None
                lead.save(update_fields=['perdu', 'motif_perte'])
                activity.log_bulk_change(lead, user, 'perdu', True, False)
                if old_motif:
                    activity.log_bulk_change(lead, user, 'motif_perte', old_motif, None)
                # QJ-INVARIANT — un lead REPRIS (dé-perdu) redevient actif :
                # ses cadences avaient été arrêtées au marquage, le filet lui
                # repose une prochaine étape (plan après-devis si devis).
                assurer_prochaine_etape_apres_succes(lead, user)
                updated += 1

            elif op == 'archive':
                if lead.is_archived:
                    unchanged += 1
                    continue
                lead.is_archived = True
                lead.archived_by = user
                lead.archived_at = timezone.now()
                lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
                activity.log_bulk_note(
                    lead, user,
                    f"Lead archivé en masse par {getattr(user, 'username', '?')}")
                updated += 1

            elif op == 'unarchive':
                if not lead.is_archived:
                    unchanged += 1
                    continue
                lead.is_archived = False
                lead.archived_by = None
                lead.archived_at = None
                lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
                activity.log_bulk_note(
                    lead, user,
                    f"Lead restauré en masse par {getattr(user, 'username', '?')}")
                # QJ-INVARIANT — même filet qu'au dé-perdu ci-dessus.
                assurer_prochaine_etape_apres_succes(lead, user)
                updated += 1

            elif op == 'plan_activity':
                # Crée UNE activité ouverte (records.Activity) par lead, échéance
                # + intitulé communs, assignée au responsable du lead (repli sur
                # l'acteur). Aucune dédup : planifier deux fois crée deux rappels.
                from django.contrib.contenttypes.models import ContentType
                from apps.records.models import Activity
                ct = ContentType.objects.get_for_model(lead.__class__)
                Activity.objects.create(
                    company=company, content_type=ct, object_id=lead.id,
                    activity_type=activity_type, summary=activity_summary[:255],
                    due_date=activity_due,
                    assigned_to=lead.owner or user, created_by=user)
                activity.log_bulk_note(
                    lead, user,
                    f"Activité « {activity_summary} » planifiée en masse "
                    f"pour le {activity_due.isoformat()}")
                updated += 1

            elif op == 'delete':
                if lead.devis.exists():
                    skip(lead, "devis liés — archivez-le plutôt")
                    continue
                # VX96 — soft-delete réversible (corbeille 30 min), cohérent avec
                # la suppression unitaire : plus de destruction définitive ici.
                import logging
                logging.getLogger('crm.audit').warning(
                    'BULK SOFT DELETE lead id=%s "%s" par user=%s (company=%s)',
                    lead.id, lead, getattr(user, 'username', '?'), company.id)
                lead.soft_delete(user)
                updated += 1

            # FG33 — Préparer la file WhatsApp en masse (pas d'envoi auto)
            elif op == 'prepare_whatsapp':
                # Pas de décompte updated/unchanged — cette action retourne
                # directement en dehors de la boucle (pas de side-effect).
                pass

    # FG33 — Résultat spécial : file de click-through WhatsApp ordonné
    if op == 'prepare_whatsapp':
        from apps.ventes.utils.whatsapp import build_wa_url
        template_id = params.get('template_id')
        body_tpl = params.get('body') or ''
        queue = []
        for lead in leads:
            phone = lead.whatsapp or lead.telephone
            if not phone:
                continue
            # Résoudre le corps : template ou texte direct
            corps = body_tpl
            if template_id:
                try:
                    from .models import MessageTemplate
                    tpl = MessageTemplate.objects.filter(
                        company=company, id=template_id).first()
                    if tpl:
                        corps = tpl.render(
                            prenom=lead.prenom or lead.nom or '',
                            ville=lead.ville or '',
                            lien='',
                        )
                except Exception:
                    pass
            wa_url = build_wa_url(phone, corps)
            queue.append({
                'lead_id': lead.id,
                'nom': str(lead),
                'phone': phone,
                'wa_url': wa_url,
            })
        return {
            'ok': True,
            'op': 'prepare_whatsapp',
            'queue': queue,
            'count': len(queue),
        }

    return {
        'ok': True,
        'updated': updated,
        'unchanged': unchanged,
        'skipped': skipped,
        'total': len(leads),
    }


# ── QJ20 — Site-visit appointment service ────────────────────────────────────

import logging as _logging  # noqa: E402

_appt_logger = _logging.getLogger(__name__)

# How many minutes before a scheduled appointment to send the reminder.
APPOINTMENT_REMINDER_MINUTES = 60

# RAMADAN-AWARE PACING: when the per-company flag ``ramadan_pacing`` is enabled
# (a simple boolean stored in CompanyProfile), reminders are suppressed during
# the iftar-sensitive window (18h–21h Africa/Casablanca, local time). This avoids
# interrupting families at meal time. The window is deliberately simple and
# documented — no external calendar needed. The beat job reschedules to just
# after the window end (21h) when the slot would land inside.
RAMADAN_AVOID_START_H = 18
RAMADAN_AVOID_END_H = 21
RAMADAN_TZ = 'Africa/Casablanca'


def _ramadan_pacing_enabled(company) -> bool:
    """True si le drapeau « pacing Ramadan » est actif pour la société.

    MRY8 — ce helper lisait ``CompanyProfile.ramadan_pacing``, un champ qui
    N'A JAMAIS EXISTÉ : il renvoyait donc toujours False et le pacing Ramadan
    (report des rappels de RDV pendant l'iftar) était mort depuis sa création.
    Il s'appuie désormais sur la PÉRIODE réellement saisie par la société
    (``ramadan_debut``/``ramadan_fin``, MRY8) : vrai pendant cette période,
    faux partout ailleurs — et faux tant que la société n'a rien saisi (la
    période n'est jamais devinée). ``ramadan_pacing`` reste honoré s'il est
    un jour ajouté, pour ne pas retirer un interrupteur explicite.
    """
    if company is None:
        return False
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        if bool(getattr(profile, 'ramadan_pacing', False)):
            return True
        from apps.crm import horaires
        return horaires.est_en_ramadan(
            aujourd_hui_local(), company, profil=profile)
    except Exception:
        return False


def _is_ramadan_iftar_window(dt_utc) -> bool:
    """True si le datetime UTC tombe dans la plage iftar-sensible (18h–21h Casablanca).

    Vérifie que l'heure locale (Africa/Casablanca) est dans [18, 21).
    """
    try:
        from zoneinfo import ZoneInfo
        local_dt = dt_utc.astimezone(ZoneInfo(RAMADAN_TZ))
        return RAMADAN_AVOID_START_H <= local_dt.hour < RAMADAN_AVOID_END_H
    except Exception:
        return False


def book_appointment(*, lead, scheduled_at, notes=None, user=None):
    """QJ20 — Planifie un rendez-vous (visite commerciale/technique) sur un lead.

    Crée un ``crm.Appointment`` lié au lead et à sa société (forcé côté serveur —
    jamais lu d'un corps de requête). Écrit une entrée de chatter sur le lead.
    Renvoie l'instance Appointment créée.

    ``scheduled_at`` doit être un datetime timezone-aware (UTC recommandé).
    ``notes`` est optionnel.
    ``user`` est l'utilisateur actif (peut être None pour les appels beat).
    """
    from .models import Appointment

    if scheduled_at is None:
        raise ValueError('scheduled_at est requis pour planifier un rendez-vous.')

    # Company is always forced from the lead (never from request body).
    company = lead.company

    appointment = Appointment.objects.create(
        company=company,
        lead=lead,
        scheduled_at=scheduled_at,
        statut=Appointment.Statut.PLANIFIE,
        notes=notes or '',
        created_by=user,
    )

    # Chatter entry on the lead.
    try:
        import zoneinfo
        local = scheduled_at.astimezone(zoneinfo.ZoneInfo(RAMADAN_TZ))
        date_str = local.strftime('%d/%m/%Y à %H:%M')
    except Exception:
        date_str = str(scheduled_at)
    activity.log_note(
        lead, user,
        f'Visite planifiée le {date_str} (RDV #{appointment.pk}).',
    )

    _appt_logger.info(
        'QJ20: RDV #%d créé pour lead %s le %s (company %s)',
        appointment.pk, lead.pk, scheduled_at, getattr(company, 'id', '?'))
    return appointment


# ── VX245(b) — confirmation WhatsApp POST-RDV (aperçu date/heure + .ics) ────

def build_appointment_confirmation_whatsapp(request, appointment):
    """VX245(b) — construit le message de CONFIRMATION WhatsApp d'un rendez-
    vous : date/heure (Africa/Casablanca) + lien de téléchargement `.ics`
    (VX245(a), `apps.crm.views.AppointmentViewSet.ics`). N'ENVOIE RIEN — même
    convention que `build_devis_whatsapp`/`build_facture_whatsapp` : ouvre
    WhatsApp avec le message pré-rempli, le commercial appuie lui-même sur
    Envoyer. Renvoie `(message, wa_url, ics_url)` ; `wa_url` est `None` si le
    lead n'a pas de numéro exploitable."""
    import zoneinfo

    from apps.ventes.utils.whatsapp import build_wa_url

    lead = appointment.lead
    phone = lead.whatsapp or lead.telephone
    nom = f'{lead.prenom or ""} {lead.nom or ""}'.strip() or (lead.nom or '')
    try:
        local_dt = appointment.scheduled_at.astimezone(
            zoneinfo.ZoneInfo(RAMADAN_TZ))
        date_str = local_dt.strftime('%d/%m/%Y à %H:%M')
    except Exception:  # pragma: no cover - défensif
        date_str = str(appointment.scheduled_at)

    ics_url = request.build_absolute_uri(
        f'/api/django/crm/appointments/{appointment.pk}/ics/')
    salutation = f'Bonjour {nom},' if nom else 'Bonjour,'
    message = (
        f'{salutation} je confirme notre rendez-vous le {date_str}.\n'
        f'Ajouter à votre agenda : {ics_url}'
    )
    return message, build_wa_url(phone, message), ics_url


# ── XSAL17 — Placeholder {lien_rdv} : lien de réservation dans les messages ──

def public_booking_url(lead, *, request=None):
    """XSAL17 — Crée (ou réutilise) un ``BookingLink`` NON expiré/NON utilisé
    pour ``lead`` et renvoie son URL PUBLIQUE complète. Réutilise un lien
    existant tant qu'il n'est ni expiré ni déjà utilisé (évite de multiplier
    les jetons à chaque envoi) ; en crée un nouveau sinon. Company-scopé
    (le lien porte la société du lead, jamais du corps de requête)."""
    from django.conf import settings
    from django.utils import timezone as _timezone

    from .models import BookingLink

    now = _timezone.now()
    link = (
        BookingLink.objects
        .filter(lead=lead, used_at__isnull=True, expires_at__gt=now)
        .order_by('-created_at')
        .first()
    )
    if link is None:
        link = BookingLink.objects.create(company=lead.company, lead=lead)

    if request is not None:
        base = request.build_absolute_uri('/')[:-1]
    else:
        base = (getattr(settings, 'PUBLIC_SITE_URL', '') or '').rstrip('/')
    return f'{base}/rdv/{link.token}'


def resoudre_lien_rdv(text, lead, *, request=None) -> str:
    """XSAL17 — Résout le placeholder ``{lien_rdv}`` dans ``text`` au moment
    de l'ENVOI (jamais généré à l'avance/en masse) : un template SANS le
    placeholder est renvoyé INCHANGÉ (aucun jeton créé — no-op, jamais de
    coût inutile). Best-effort : une erreur de génération de lien ne casse
    jamais l'envoi — le placeholder est alors simplement retiré."""
    if '{lien_rdv}' not in (text or ''):
        return text
    try:
        url = public_booking_url(lead, request=request)
    except Exception:  # noqa: BLE001 — jamais bloquer l'envoi d'un message
        url = ''
    return text.replace('{lien_rdv}', url)


class BookingLinkUnavailable(Exception):
    """XSAL17 — levée quand un jeton de réservation est invalide, expiré ou
    déjà utilisé (l'appelant — la vue publique — traduit en 404/410 douce)."""


def resolve_booking_link(token):
    """XSAL17 — Résout un jeton de réservation PUBLIC : renvoie le
    ``BookingLink`` s'il existe, n'est ni expiré ni déjà utilisé. Lève
    :class:`BookingLinkUnavailable` sinon (message explicite). Lecture
    seule — ne réserve rien elle-même."""
    from .models import BookingLink

    link = BookingLink.objects.select_related('lead', 'company').filter(
        token=token).first()
    if link is None:
        raise BookingLinkUnavailable('Lien de réservation introuvable.')
    if link.is_used:
        raise BookingLinkUnavailable('Ce créneau a déjà été réservé.')
    if link.is_expired:
        raise BookingLinkUnavailable('Ce lien de réservation a expiré.')
    return link


#: CRX23 — horizon maximal d'une réservation PUBLIQUE, en jours. Sert de
#: borne haute de bon sens : un visiteur (ou un script) ne réserve pas une
#: visite en l'an 9999. Constante de module pour que les tests la patchent.
BOOKING_HORIZON_JOURS = 365


def _valider_creneau_public(scheduled_at):
    """CRX23 — bornes d'un créneau réservé PUBLIQUEMENT.

    Le corps public arrive de ``parse_datetime`` : il rend un datetime NAÏF
    quand la chaîne ne porte pas d'offset, et accepte n'importe quelle année.
    Un naïf serait stocké tel quel (interprétation de fuseau indéterminée) et
    une année absurde polluerait durablement le calendrier du commercial.

    Lève ``ValueError`` (traduit en 400 par la vue publique) si le créneau
    est absent, naïf, déjà passé, ou au-delà de :data:`BOOKING_HORIZON_JOURS`.
    """
    from datetime import timedelta

    from django.utils import timezone as _timezone

    if scheduled_at is None:
        raise ValueError('Date/heure de créneau manquante.')
    if _timezone.is_naive(scheduled_at):
        raise ValueError(
            'Le créneau doit porter son fuseau horaire (date/heure naïve '
            'refusée).')
    now = _timezone.now()
    if scheduled_at <= now:
        raise ValueError('Le créneau demandé est déjà passé.')
    if scheduled_at > now + timedelta(days=BOOKING_HORIZON_JOURS):
        raise ValueError(
            'Le créneau demandé est trop lointain '
            f'(au-delà de {BOOKING_HORIZON_JOURS} jours).')


def reserver_creneau_public(token, *, scheduled_at, notes=None):
    """XSAL17 — Réservation PUBLIQUE d'un créneau via un jeton
    ``BookingLink`` : crée l'``Appointment`` (via ``book_appointment``,
    même logique métier que la création interne — user=None, un visiteur
    anonyme n'est jamais un utilisateur ERP) et marque le lien comme
    UTILISÉ (idempotent : un second appel avec le même jeton lève
    :class:`BookingLinkUnavailable`, jamais un second rendez-vous).
    Le lead atterrit toujours sur SON lead d'origine (booking-to-lead) —
    jamais un autre, jamais choisi par le visiteur.

    CRX23 — l'idempotence est désormais VRAIE sous concurrence. Avant, deux
    requêtes simultanées passaient toutes les deux le ``resolve_booking_link``
    (``used_at`` encore nul pour les deux), créaient DEUX rendez-vous sur le
    même lien, et la seconde écrasait ``link.appointment`` : le commercial
    voyait deux visites pour un seul créneau réservé. Le lien est maintenant
    RÉCLAMÉ par un UPDATE conditionnel (``used_at__isnull=True`` → nombre de
    lignes touchées) DANS la transaction : exactement une requête gagne, la
    perdante reçoit :class:`BookingLinkUnavailable` (410). Le rendez-vous est
    créé APRÈS la réclamation, dans la même transaction — un échec de création
    annule la réclamation (le lien reste utilisable), jamais un lien brûlé
    pour rien.
    """
    from django.db import transaction
    from django.utils import timezone as _timezone

    from .models import BookingLink

    # Le jeton d'abord (404/410 honnête, lecture seule), puis les bornes du
    # créneau — AVANT toute écriture : un créneau invalide ne doit pas
    # consommer le lien (le visiteur doit pouvoir corriger et réessayer).
    link = resolve_booking_link(token)
    _valider_creneau_public(scheduled_at)

    with transaction.atomic():
        maintenant = _timezone.now()
        reclame = BookingLink.objects.filter(
            pk=link.pk, used_at__isnull=True).update(used_at=maintenant)
        if not reclame:
            raise BookingLinkUnavailable('Ce créneau a déjà été réservé.')
        appointment = book_appointment(
            lead=link.lead, scheduled_at=scheduled_at, notes=notes, user=None)
        BookingLink.objects.filter(pk=link.pk).update(appointment=appointment)

    link.used_at = maintenant
    link.appointment = appointment
    return appointment


def dispatch_appointment_reminder(appointment) -> bool:
    """QJ20 — Envoie le rappel de visite pour un rendez-vous à venir.

    Canaux (par priorité) :
      1. WhatsApp wa.me draft (log uniquement — pas d'API WhatsApp gated).
      2. Notifications in-app via notifications.services.notify.

    RAMADAN-AWARE PACING : si le drapeau est actif pour la société ET que
    l'heure du rappel tombe dans la plage iftar-sensible (18h–21h Casablanca),
    le rappel est différé (renvoie False sans marquer reminder_sent).

    Idempotent : si reminder_sent est déjà True, renvoie True sans rien envoyer.
    Renvoie True si le rappel a été envoyé, False sinon (différé ou erreur).
    """
    from django.utils import timezone as tz

    if appointment.reminder_sent:
        return True  # already sent — idempotent

    # Ramadan-aware pacing check.
    if _ramadan_pacing_enabled(appointment.company):
        if _is_ramadan_iftar_window(tz.now()):
            _appt_logger.info(
                'QJ20: rappel RDV #%d différé (plage iftar Ramadan)',
                appointment.pk)
            return False

    lead = appointment.lead
    phone = (
        getattr(lead, 'whatsapp', '') or getattr(lead, 'telephone', '') or ''
    ).strip()

    # 1) wa.me draft logged (no WhatsApp API dependency).
    try:
        import urllib.parse
        import zoneinfo
        local = appointment.scheduled_at.astimezone(
            zoneinfo.ZoneInfo(RAMADAN_TZ))
        date_str = local.strftime('%d/%m/%Y à %H:%M')
        msg = (
            f'Rappel : votre visite est prévue le {date_str}. '
            f'Notre équipe sera présente. Merci !'
        )
        if phone:
            digits = ''.join(c for c in phone if c.isdigit())
            wa_url = (f'https://wa.me/{digits}?text='
                      f'{urllib.parse.quote(msg)}')
            _appt_logger.info(
                'QJ20 rappel wa.me RDV #%d lead %s → %s',
                appointment.pk, lead.pk, wa_url)
    except Exception as exc:  # noqa: BLE001
        _appt_logger.warning(
            'QJ20: wa.me draft échec RDV #%d : %s', appointment.pk, exc)

    # 2) In-app notification to the lead owner (if any).
    try:
        from apps.notifications.services import notify
        owner = getattr(lead, 'owner', None)
        if owner is not None:
            import zoneinfo
            local = appointment.scheduled_at.astimezone(
                zoneinfo.ZoneInfo(RAMADAN_TZ))
            date_str = local.strftime('%d/%m/%Y à %H:%M')
            notify(
                user=owner,
                event_type='appointment_reminder',
                title=f'Rappel visite — {lead.nom}',
                body=(
                    f'Rendez-vous prévu le {date_str} '
                    f'avec {lead.nom} (RDV #{appointment.pk}).'
                ),
                link=f'/crm/leads/{lead.pk}',
                company=appointment.company,
            )
    except Exception as exc:  # noqa: BLE001
        _appt_logger.warning(
            'QJ20: notify échec RDV #%d : %s', appointment.pk, exc)

    # Mark as sent (idempotency guard).
    appointment.reminder_sent = True
    appointment.save(update_fields=['reminder_sent'])

    _appt_logger.info('QJ20: rappel envoyé pour RDV #%d', appointment.pk)
    return True


def send_due_appointment_reminders() -> int:
    """QJ20 — Parcourt les rendez-vous à venir et envoie les rappels dus.

    Un rappel est dû quand :
      - l'appointment est à l'état PLANIFIE ou CONFIRME (pas EFFECTUE / ANNULE) ;
      - ``scheduled_at`` est dans les prochaines APPOINTMENT_REMINDER_MINUTES
        minutes (fenêtre glissante) ;
      - ``reminder_sent`` est False.

    Renvoie le nombre de rappels envoyés.
    """
    from datetime import timedelta
    from django.utils import timezone as tz
    from .models import Appointment

    now = tz.now()
    window_end = now + timedelta(minutes=APPOINTMENT_REMINDER_MINUTES)

    due = Appointment.objects.filter(
        statut__in=[Appointment.Statut.PLANIFIE, Appointment.Statut.CONFIRME],
        scheduled_at__gte=now,
        scheduled_at__lte=window_end,
        reminder_sent=False,
    ).select_related('lead', 'lead__owner', 'company')

    sent = 0
    for appt in due:
        try:
            if dispatch_appointment_reminder(appt):
                sent += 1
        except Exception as exc:  # noqa: BLE001
            _appt_logger.warning(
                'QJ20: erreur rappel RDV #%d : %s', appt.pk, exc)

    _appt_logger.info('QJ20 send_due_appointment_reminders: %d rappel(s)', sent)
    return sent


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
    email = (email or '').strip()
    if not email:
        return None
    return (
        Lead.objects.filter(company=company, email__iexact=email)
        .order_by('-date_creation')
        .first()
    )


def log_whatsapp_message_on_lead(lead, *, texte, expediteur, nom_profil=''):
    """Ajoute un message WhatsApp entrant au chatter d'un lead (XKB33).

    Note SYSTÈME (user=None) — un message reçu n'est pas une action manuelle
    d'un utilisateur de l'ERP. Best-effort : jamais d'exception remontée (le
    webhook qui appelle cette fonction ne doit jamais planter)."""
    if lead is None:
        return None
    try:
        body = f"WhatsApp de {nom_profil or expediteur} : {texte}".strip()
        return activity.log_note(lead, None, body)
    except Exception:  # noqa: BLE001 — jamais bloquant pour le webhook
        return None


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
    existant = (
        Lead.objects
        .filter(company=company, client=client)
        .exclude(stage=stages.COLD)
        .order_by('-date_creation')
        .first())
    if existant is not None:
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

def enregistrer_consentement_lead(
        lead, *, purpose, granted=True, source='', version_texte='',
        ip_confirmation=None, occurred_at=None):
    """Pose (ou met à jour) le consentement d'un lead pour un canal donné.

    ``purpose`` ∈ 'marketing' / 'email' / 'sms' / 'whatsapp'…
    ``lead.email`` est utilisé comme identifiant si présent, sinon
    ``lead.telephone``. Crée une NOUVELLE entrée à chaque appel (le registre
    ``ConsentRecord`` est un historique append-only, cf. FG394) — la lecture
    de l'état courant prend toujours la ligne la plus récente.

    CRX39 — ``occurred_at`` (additif, défaut ``now()`` : tout appelant existant
    est inchangé) porte l'horodatage RÉEL du consentement quand on le connaît,
    comme le champ le demande explicitement (« sur le consent_timestamp
    existant côté métier »). Sans lui, le registre daterait le consentement du
    moment où l'ERP l'a enregistré, pas de celui où la personne l'a donné —
    une preuve CNDP fausse est pire qu'une preuve absente.
    """
    from core.models import ConsentRecord

    identifiant = (lead.email or lead.telephone or '').strip()
    if not identifiant:
        return None
    return ConsentRecord.objects.create(
        company=lead.company,
        subject_identifier=identifiant,
        purpose=purpose,
        granted=granted,
        source=source or '',
        occurred_at=occurred_at or timezone.now(),
        version_texte=version_texte or '',
        ip_confirmation=ip_confirmation,
    )


#: CRX39 — origine consignée dans ``ConsentRecord.source`` pour l'intake web.
CONSENT_SOURCE_SITE_WEB = 'formulaire site web'


def enregistrer_consentements_intake_web(lead):
    """CRX39 (DRAFT165-57) — trace au REGISTRE le consentement recueilli par le
    formulaire du site, FINALITÉ PAR FINALITÉ.

    Jusqu'ici le consentement du visiteur ne vivait que sur la fiche
    (``Lead.consent_timestamp`` / ``Lead.whatsapp_opt_in``) : le registre
    ``core.ConsentRecord`` — celui qu'une demande CNDP interroge, celui que
    lisent le DSR et les filtres marketing — restait VIDE pour la source de
    leads n°1. Cette fonction est le pont, appelée à la CRÉATION du lead par
    le webhook site.

    Deux finalités, chacune écrite SEULEMENT si la donnée existe (jamais un
    consentement supposé — règle « aucun chiffre/fait inventé ») :
      • ``marketing`` — la case du formulaire, ACCORDÉE, datée du
        ``consentTimestamp`` transmis par le site (pas de l'instant serveur) ;
      • ``whatsapp`` — l'opt-in WhatsApp, accordé OU refusé selon la case
        (``whatsapp_opt_in`` vaut ``None`` quand la question n'a pas été posée
        : on n'écrit alors RIEN, un silence n'est pas un refus).

    ``ip_confirmation`` reste vide À DESSEIN : ce champ est la preuve du clic
    de confirmation d'un DOUBLE opt-in, que le formulaire du site ne pratique
    pas — y verser l'IP de la soumission maquillerait un simple opt-in en
    double opt-in. Idem ``version_texte`` : le site ne transmet aucune version
    de texte de consentement aujourd'hui.

    Renvoie la liste des entrées créées (vide si aucune donnée exploitable).
    Ne lève pas sur un lead sans email ni téléphone (le point d'entrée unique
    ``enregistrer_consentement_lead`` renvoie alors ``None``).
    """
    horodatage = getattr(lead, 'consent_timestamp', None)
    creees = []
    if horodatage:
        entree = enregistrer_consentement_lead(
            lead, purpose='marketing', granted=True,
            source=CONSENT_SOURCE_SITE_WEB, occurred_at=horodatage)
        if entree is not None:
            creees.append(entree)
    opt_in = getattr(lead, 'whatsapp_opt_in', None)
    if opt_in is not None:
        entree = enregistrer_consentement_lead(
            lead, purpose='whatsapp', granted=bool(opt_in),
            source=CONSENT_SOURCE_SITE_WEB, occurred_at=horodatage or None)
        if entree is not None:
            creees.append(entree)
    return creees


# ── XMKT19 — Actions CRM exécutables depuis une étape de séquence ──────────
# Point d'entrée UNIQUE pour qu'une ``EtapeSequence`` (apps.compta) exécute
# une action CRM au lieu d'un message — jamais d'import direct du modèle
# crm depuis compta ; chaque fonction journalise le chatter (``LeadActivity``)
# via ``activity``, jamais silencieuse.

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
    ``EvenementMarketing`` (apps.compta) est capturé. Même pattern que
    ``create_lead_from_livechat`` (XMKT37) : dédup par téléphone/email dans
    la société avant de créer, canal ``AUTRE``, stage NEW (défaut du champ).
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


# ── YSERV11 — Gabarit de message « parrainage » (FR + darija, éditable) ─────

# Corps par défaut — ÉDITABLES ensuite par l'admin comme tout MessageTemplate.
_PARRAINAGE_TEMPLATE_DEFAULTS = {
    'fr': (
        'parrainage',
        "Bonjour {prenom}, merci pour votre confiance ! Si un proche "
        "souhaite passer au solaire, recommandez-nous : notre programme de "
        "parrainage vous récompense. Parlez-en à votre conseiller ou "
        "répondez à ce message.",
    ),
    'darija': (
        'parrainage_darija',
        "Salam {prenom}, choukran 3la ti9a dyalek ! Ila kan chi wahed 9rib "
        "lik bagh idir solaire, 3eyet lina — barnamaj l'parrainage dyalna "
        "kay3tik mokafaa. Hder m3a lmostachar dyalek wla jaweb 3la had "
        "l'message.",
    ),
}


def get_or_create_parrainage_template(company, langue='fr'):
    """YSERV11 — renvoie (crée au premier usage) le ``MessageTemplate``
    « parrainage » de la société pour ``langue`` ('fr'|'darija').

    Point d'entrée cross-app THIN (appelé par ``apps.compta`` au moment de
    l'enchantement NPS) : la clé template est posée additivement, idempotente
    par (company, nom), le corps reste éditable par l'admin — jamais écrasé.
    Langue inconnue → repli FR."""
    from .models import MessageTemplate
    cle = 'darija' if (langue or '').strip().lower() == 'darija' else 'fr'
    nom, corps_defaut = _PARRAINAGE_TEMPLATE_DEFAULTS[cle]
    template, _ = MessageTemplate.objects.get_or_create(
        company=company, nom=nom,
        defaults={
            'langue': (MessageTemplate.Langue.DARIJA if cle == 'darija'
                       else MessageTemplate.Langue.FR),
            'corps': corps_defaut,
        })
    return template


# ─────────────────────────────────────────────────────────────────────────────
# QX42 — Rétention PII des copies brutes d'intake (registre YOPSB10, core.retention)
#
# `WebsiteLeadPayload` (PII brute + IP, SET_NULL depuis Lead → l'effacement
# RGPD d'un lead n'atteint JAMAIS ce payload brut) et `ChatSessionPublique`
# s'accumulent INDÉFINIMENT. Le framework générique existe (`core.retention`)
# mais son registre est VIDE — aucune app n'y enregistre de politique. Ceci
# enregistre la politique CRM (voir `CrmConfig.ready()`), fenêtre par défaut
# 180 jours, override founder via `WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS` /
# `CHAT_SESSION_RETENTION_DAYS` (settings/.env — même patron que les autres
# constantes founder-configurables de ce module, ex.
# `WEBSITE_LEAD_WEBHOOK_SECRET`). 0/négatif désactive la purge (conservation
# illimitée, comportement actuel inchangé).

DEFAULT_WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS = 180
DEFAULT_CHAT_SESSION_RETENTION_DAYS = 180


def _retention_days(setting_name, default_days):
    from django.conf import settings
    value = getattr(settings, setting_name, None)
    if value is None:
        return default_days
    try:
        return int(value)
    except (TypeError, ValueError):
        return default_days


def purge_website_lead_payloads(now, apply_) -> int:
    """QX42 — purge les ``WebsiteLeadPayload`` PROCESSED au-delà de la
    fenêtre de rétention. Les payloads NON traités ou en ERREUR (``error``
    non vide) sont EXEMPTÉS — ils doivent d'abord vieillir via la surface de
    rejeu QX16 (un payload en erreur reste la seule trace récupérable d'un
    lead potentiellement perdu ; on ne purge jamais une piste encore
    actionnable). Contrat ``core.retention`` : ``apply_=False`` (dry-run) ne
    supprime rien, renvoie le compte qui SERAIT supprimé."""
    from django.db.models import Q

    from .models import WebsiteLeadPayload

    days = _retention_days(
        'WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS',
        DEFAULT_WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS)
    if days <= 0:
        return 0
    cutoff = now - timezone.timedelta(days=days)
    qs = WebsiteLeadPayload.objects.filter(
        processed=True, received_at__lt=cutoff,
    ).filter(Q(error__isnull=True) | Q(error=''))
    count = qs.count()
    if apply_ and count:
        qs.delete()
    return count


def purge_stale_chat_sessions(now, apply_) -> int:
    """QX42 — purge les ``ChatSessionPublique`` (transcript PII d'un visiteur
    anonyme) inactives au-delà de la fenêtre de rétention (mesurée sur
    ``last_message_at`` — une session encore active récemment n'est jamais
    purgée même si ``created_at`` est ancien). Une session déjà liée à un
    Lead réel (``lead_id`` renseigné) garde son transcript — la conversation
    fait partie de l'historique du lead, pas une trace anonyme jetable."""
    from .models import ChatSessionPublique

    days = _retention_days(
        'CHAT_SESSION_RETENTION_DAYS', DEFAULT_CHAT_SESSION_RETENTION_DAYS)
    if days <= 0:
        return 0
    cutoff = now - timezone.timedelta(days=days)
    qs = ChatSessionPublique.objects.filter(
        last_message_at__lt=cutoff, lead__isnull=True)
    count = qs.count()
    if apply_ and count:
        qs.delete()
    return count


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
                                     fenetre_jours=None):
    """NTPRT28 — soumission RÉCENTE du même prospect par le même partenaire.

    Renvoie la soumission existante, ou ``None``. La comparaison se fait sur
    l'email du prospect, normalisé (casse/espaces) : c'est la seule clé
    stable dont on dispose côté partenaire. Un email VIDE ne déclenche jamais
    de doublon — sinon deux prospects anonymes distincts s'annuleraient
    mutuellement.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import SoumissionLeadPartenaire

    email = (email_prospect or '').strip().lower()
    if company is None or not partenaire_id or not email:
        return None
    jours = (FENETRE_DOUBLON_SOUMISSION_JOURS if fenetre_jours is None
             else fenetre_jours)
    depuis = timezone.now() - timedelta(days=jours)
    return (SoumissionLeadPartenaire.objects
            .filter(company=company, partenaire_id=partenaire_id,
                    email_prospect__iexact=email,
                    date_soumission__gte=depuis)
            .order_by('-date_soumission')
            .first())


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
        company, partenaire.id, email)
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

    Best-effort : si ``ventes`` est illisible, le placement continue SANS
    information de devis plutôt que d'échouer en bloc — les décisions
    retombent alors sur l'étape et l'ancienneté."""
    try:
        from apps.ventes.selectors import (
            dernier_devis_envoye_par_lead, leads_avec_devis_accepte)
        return (leads_avec_devis_accepte(company, lead_ids),
                dernier_devis_envoye_par_lead(company, lead_ids))
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning(
            'MRY30: devis illisibles (société %s)',
            getattr(company, 'pk', '?'), exc_info=True)
        return set(), {}


def _decider_placements(company, maintenant, gabarits=None):
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
    candidats = list(
        Lead.objects.filter(
            company=company, is_archived=False, perdu=False,
            ne_plus_contacter=False,
        ).exclude(stage__in=[stages.COLD, stages.SIGNED]).order_by('pk'))
    total = len(candidats)
    ignores = {'deja_en_cadence': 0, 'devis_accepte_non_signe': 0}
    if not candidats:
        return [], ignores, total

    ids = [lead.pk for lead in candidats]
    # Le moteur TIENT déjà ces dossiers : une seconde cadence dessus, ce sont
    # deux séries de messages parallèles à la même personne.
    deja = set(RelanceEtape.objects.filter(
        company=company, lead_id__in=ids).values_list('lead_id', flat=True))
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

    etapes = initialiser_plan_relance(
        lead, user, cadence=entree['cadence'], depart=entree['depart'],
        devis=entree['devis'])
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
    prochaine = _prochaine_touche_a_faire(lead)
    lead.relance_date = prochaine.due_date if prochaine else relance_avant
    lead.save(update_fields=['relance_date'])
    sync_relance_activity(lead, user)
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
    etapes = initialiser_plan_relance(
        lead, user, cadence='reveil', depart=entree['depart'])
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
                         limite=None):
    """Enveloppe de `_placer_anciens_leads_sans_cache` sous `horaires.cache_local()` :
    profil société et jours ouvrés lus UNE fois pour toute l'opération. Sans
    cela, dater les touches de 272 leads coûtait ~7 000 requêtes et 24 s en
    production (07/09/2026), au-delà du délai du navigateur."""
    from . import horaires
    with horaires.cache_local():
        return _placer_anciens_leads_sans_cache(
            company, user, apply=apply, maintenant=maintenant, limite=limite)


def _placer_anciens_leads_sans_cache(company, user, *, apply=False,
                                     maintenant=None, limite=None):
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
        company, maintenant, gabarits)
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


# ── VT1 — CHATTER AUTOMATIQUE DE LA VISITE TECHNIQUE TERRAIN ─────────────────
#
# Le chatter du lead (``LeadActivity``) est le journal COMMUN de tout ce qui
# arrive à un lead : la visite technique y écrit ses quatre moments — création,
# terminaison, feu vert, renvoi — plutôt que d'ouvrir un second historique.
# L'auteur et la société viennent TOUJOURS du serveur (jamais du corps de
# requête), comme le reste du chatter.

#: Moment de la visite → phrase FR posée au chatter.
_VISITE_CHATTER = {
    'creation': 'Visite technique créée.',
    'terminee': 'Visite technique terminée par le commercial.',
    'validee': "Visite technique validée par le bureau d'études (feu vert).",
    'a_refaire': 'Visite technique renvoyée au commercial.',
}


def journaliser_visite(visite, user, moment, detail=''):
    """Pose UNE note de chatter sur le lead pour ``moment``.

    Best-effort : un chatter indisponible ne doit jamais faire échouer la
    transition métier qui vient d'aboutir (même prudence qu'ailleurs dans ce
    module). Renvoie l'activité créée, ou ``None``.
    """
    from . import activity

    phrase = _VISITE_CHATTER.get(moment)
    if phrase is None:
        return None
    corps = f'{phrase} {detail}'.strip() if detail else phrase
    try:
        return activity.log_note(visite.lead, user, corps)
    except Exception:  # pragma: no cover - défensif, jamais bloquant
        return None


# ── VT3/VT12/VTA5 — RETOUR DU FEU VERT SUR LA FICHE LEAD ─────────────────────
#
# VTA5 — l'app ``visites`` n'appelle PLUS ce retour : elle ÉMET
# ``visite_validee`` (bus ``core.events``) et c'est ``apps/crm/receivers.py``
# qui s'abonne et appelle cette fonction avec le récap DÉJÀ calculé par le
# selector de l'app visites. Le CRM n'a donc plus rien à recalculer, et
# ``visites`` ne fait plus aucun écrit sur ``crm.Lead``.


def ecrire_retour_lead_visite(lead, recap):
    """VT12 — le feu vert REDESCEND sur la fiche lead.

    Le lead est la fiche que tout le monde ouvre : après le feu vert, il porte
    lui-même ``visite_effectuee=True`` et un récap COURT dans ``visite_notes``
    (uniquement des mesures RÉELLEMENT saisies — jamais un défaut inventé ;
    c'est ``visites.selectors.recap_visite_terrain`` qui compose la phrase,
    unique source de vérité, et elle arrive ici toute faite).

    Deux prudences : le récap est APPENDU (une note déjà écrite à la main n'est
    jamais écrasée) et il n'est écrit qu'une fois (une re-validation ne le
    duplique pas). Rien de tout ceci ne double le chatter : la note
    ``journaliser_visite(..., 'validee')`` reste l'unique trace d'historique.
    """
    if lead is None:
        return None
    existantes = (lead.visite_notes or '').strip()
    champs = []
    if not lead.visite_effectuee:
        lead.visite_effectuee = True
        champs.append('visite_effectuee')
    if recap and recap not in existantes:
        lead.visite_notes = (f'{existantes}\n{recap}'.strip()
                             if existantes else recap)
        champs.append('visite_notes')
    if champs:
        lead.save(update_fields=champs)
    return lead


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

    Utilisé par ``apps.dataquality`` pour charger un groupe de doublons AVANT
    de demander la fusion — jamais un import de ``crm.models`` là-bas. Le
    filtre société est POSÉ ICI : une autre app ne peut pas charger le client
    d'un autre tenant en passant un id deviné.
    """
    return list(Client.objects.filter(company=company, pk__in=list(ids or [])))
