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
import logging
import re as _re

from django.utils import timezone

from . import activity, stages
from .models import Canal, Client, Lead, LeadActivity, PointContact

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


def generer_playbook_progress(lead, new_stage):
    """NTCRM12 — Quand ``lead`` entre dans ``new_stage``, crée la progression
    (``LeadPlaybookProgress``, une par tâche) pour CHAQUE playbook ACTIF de la
    société portant une étape sur ``new_stage``. Idempotent (``unique_together
    (lead, tache)``, ``get_or_create``) : rejouer l'événement (ex. réactivation
    YLEAD11 qui repasse par la même étape) ne duplique jamais les tâches.
    Ne bloque JAMAIS le changement d'étape (avertissement seulement — cohérent
    avec « never auto-move ») : appelé en best-effort par le récepteur."""
    from .models import LeadPlaybookProgress, PlaybookEtape

    etapes = PlaybookEtape.objects.filter(
        playbook__company=lead.company, playbook__actif=True,
        stage=new_stage,
    ).prefetch_related('taches')
    created = []
    for etape in etapes:
        for tache in etape.taches.all():
            _progress, was_created = LeadPlaybookProgress.objects.get_or_create(
                lead=lead, tache=tache)
            if was_created:
                created.append(_progress)
    return created


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
    update_fields = ['stage']
    # FG28 — le premier contact fait quitter NEW via CE signal (hors du
    # perform_update du lead qui posait first_contacted_at avant) : on le pose ici.
    if getattr(lead, 'first_contacted_at', None) is None:
        from django.utils import timezone
        lead.first_contacted_at = timezone.now()
        update_fields.append('first_contacted_at')
    lead.save(update_fields=update_fields)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[stages.NEW],
        new_value=stages.STAGE_LABELS[_STAGE_CONTACTED],
        body='auto — premier contact',
    )
    _emit_stage_changed(lead, stages.NEW, _STAGE_CONTACTED, user)
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


def _next_round_robin_owner_for_new_lead(company):
    """QW6 — Round-robin parmi les commerciaux actifs d'une société, quand
    AUCUN responsable par défaut n'est configuré (``CompanyProfile.
    responsable_defaut_leads``).

    Distinct de ``_next_round_robin_commercial`` (XMKT21, départagé par
    ``mql_assigned_at``, réservé au franchissement du seuil MQL) : ici on
    départage par le nombre TOTAL de leads déjà assignés (tous statuts), pour
    répartir la charge entrante générale — pas seulement les MQL. Renvoie
    None si aucun commercial actif (no-op : le lead reste sans owner, comme
    aujourd'hui).
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Count

    User = get_user_model()
    candidats = list(
        User.objects.filter(
            company=company, is_active=True, role__nom='Commercial',
        ).annotate(
            nb_leads=Count('leads_assignes'),
        ).order_by('nb_leads', 'id')
    )
    return candidats[0] if candidats else None


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

def maybe_set_first_contacted_at(old_lead, new_lead):
    """Pose ``first_contacted_at`` sur le lead dès que son stage quitte NEW
    pour la première fois (et que le champ n'est pas déjà renseigné).

    Best-effort : n'échoue jamais et ne modifie rien si la condition n'est
    pas remplie.
    """
    try:
        if new_lead.first_contacted_at is not None:
            return  # déjà posé — ne rien écraser
        if old_lead.stage == stages.NEW and new_lead.stage != stages.NEW:
            new_lead.first_contacted_at = timezone.now()
            new_lead.save(update_fields=['first_contacted_at'])
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


def resolve_client_for_lead(lead: Lead) -> Client:
    from django.db import IntegrityError, transaction

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
            client = _find_existing()
            if client is None:
                raise

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
    today = timezone.now().date()
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


def create_lead_from_meta_lead_ads(
        *, company, leadgen_id, field_data,
        ad_id='', adgroup_id='', form_id='', access_token='') -> Lead:
    """XMKT32 — Crée (ou dédupe sur) un lead depuis un formulaire Meta Lead Ads.

    Point d'entrée cross-app sanctionné (services.py), appelé par
    ``webhooks.meta_lead_ads_webhook`` une fois le lead récupéré via l'API
    officielle (jamais de scraping). ``field_data`` est la liste
    ``[{'name': ..., 'values': [...]}, ...]`` renvoyée par le Graph API pour
    ce ``leadgen_id`` — seuls des champs connus (nom/email/téléphone/ville)
    sont lus.

    Dédup (QJ8) — DEUX couches, dans l'ordre :
      1. même ``leadgen_id`` déjà traité (idempotence webhook — retries Meta)
         → renvoie le lead existant sans le modifier ;
      2. sinon, téléphone/email connu dans la société (visiteur/prospect déjà
         en base, ex. venu par un autre canal) → absorbe la nouvelle touche
         dans le lead existant (complète sans écraser), comme le webhook site.

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
    """
    # ── Couche 1 : idempotence sur le leadgen_id (retries webhook Meta) ──────
    existing = Lead.objects.filter(
        company=company, external_system=_META_LEAD_ADS_SYSTEM,
        external_id=str(leadgen_id)).first()
    if existing is not None:
        return existing

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

    nom = (fields.get('nom') or '').strip() or 'Lead Meta Ads'
    telephone = fields.get('telephone') or ''
    email = fields.get('email') or ''

    # ── Couche 2 (QJ8) : dédup société par téléphone/email ──────────────────
    absorbed = None
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)
        if dupes:
            absorbed = sorted(
                dupes, key=lambda d: d.date_creation, reverse=True)[0]

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

    if absorbed is not None:
        lead = absorbed
        for field_name, value in (
            ('email', email), ('telephone', telephone),
            ('ville', fields.get('ville')),
        ):
            if value and not getattr(lead, field_name, None):
                setattr(lead, field_name, value)
        # first-touch UTM/attribution préservée si déjà posée.
        if not lead.utm_source:
            lead.utm_source = utm_source
        if not lead.utm_campaign:
            lead.utm_campaign = utm_campaign
        if not lead.utm_content:
            lead.utm_content = utm_content
        # Identifiants Meta natifs : posés seulement si absents (first-touch).
        if not lead.meta_ad_id:
            lead.meta_ad_id = meta_ad_id
        if not lead.meta_adset_id:
            lead.meta_adset_id = meta_adset_id
        if not lead.meta_campaign_id:
            lead.meta_campaign_id = meta_campaign_id
        if not lead.meta_form_id:
            lead.meta_form_id = meta_form_id
        if not lead.external_system:
            lead.external_system = _META_LEAD_ADS_SYSTEM
            lead.external_id = str(leadgen_id)
        lead.save()
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Nouvelle touche Meta Lead Ads (leadgen_id={leadgen_id}) '
                  f'absorbée dans ce lead existant.'))
    else:
        extra = {}
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default
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
        activity.log_creation(lead, None)
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body='Lead créé depuis Meta Lead Ads (formulaire Facebook/Instagram).')
        try:
            notify_new_lead(lead)
        except Exception:  # noqa: BLE001 — best-effort
            pass

    recompute_lead_score(lead)
    return lead


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
    recompute_lead_score(lead)
    return lead


def fetch_meta_lead_node(leadgen_id, access_token):  # pragma: no cover - réseau
    """ADSENG1 — Récupère les identifiants natifs (ad_id/adgroup_id/form_id) du
    nœud lead Meta via le Graph API officiel, pour le backfill.

    Isolé en fonction module (jamais dans ``webhooks.py`` — inchangé hors
    mapping) pour rester simulable en test (monkeypatch). Utilise la version
    courante de l'API (v25 — jamais la v19 expirée). Renvoie le dict brut ou
    lève sur échec (capté par l'appelant, best-effort par lead).
    """
    import json
    import urllib.parse
    import urllib.request

    qs = urllib.parse.urlencode({
        'fields': 'ad_id,adgroup_id,form_id',
        'access_token': access_token,
    })
    url = f'https://graph.facebook.com/v25.0/{leadgen_id}?{qs}'
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def backfill_meta_lead_attribution(
        *, company=None, access_token='', fetch_fn=None, limit=None):
    """ADSENG1 — Rétro-remplit l'attribution par variante des leads Lead Ads
    EXISTANTS (créés avant qu'on capture ad_id/adgroup_id/form_id).

    Pour chaque ``Lead`` de source ``meta_lead_ads`` dont ``meta_ad_id`` est
    encore vide, récupère ses identifiants natifs (ad_id/adgroup_id/form_id)
    depuis le nœud lead Meta via ``fetch_fn(leadgen_id, access_token)`` (défaut :
    ``webhooks.fetch_meta_lead_node`` — injectable/simulable en test), les
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
    avancer_stage_sur_ouverture_devis(lead)


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
    lead.stage = cible
    lead.save(update_fields=['stage'])
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


def notify_new_lead(lead) -> None:
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
    """
    try:
        recipients = lead_notification_recipients(lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Nouveau prospect'
        wa_url = _build_lead_wa_reply_url(lead)
        body_parts = [f'Un nouveau lead vient d\'arriver : {nom}.']
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            'lead_new',
            f'Nouveau lead : {nom}',
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ2: notify_new_lead échoué pour lead #%s : %s',
            getattr(lead, 'pk', '?'), exc)


def notify_devis_opened(devis_reference: str, lead) -> None:
    """QJ2 (b) — Notifie le responsable du lead à la PREMIÈRE ouverture du devis.

    Complémente noter_devis_ouvert (QJ1) : en plus de la note chatter, envoie
    une notification in-app + Web Push au owner du lead, avec un lien wa.me
    « répondre maintenant » vers le prospect. QJ27 : le supérieur du owner est
    aussi notifié (repli managers société quand owner/supervisor manque).
    Best-effort — jamais d'exception propagée.
    """
    try:
        recipients = lead_notification_recipients(lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Votre client'
        wa_url = _build_lead_wa_reply_url(lead)
        body_parts = [f'{nom} vient d\'ouvrir le devis {devis_reference}.']
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            'devis_opened',
            f'Devis {devis_reference} ouvert par le client',
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


def handle_parrainage_signup(lead) -> None:
    """QX35 — Wire la promesse de la page /parrainage : un lead capté avec
    ``utm_source=parrainage`` crée automatiquement un ``Parrainage`` en
    attente, rattaché au CLIENT parrain identifié par son code (porté par
    ``utm_campaign`` — voir ``apps/web/src/pages/parrainage.astro``, le lien
    personnel est `?utm_source=parrainage&utm_campaign=<code>`).

    Idempotent (un seul ``Parrainage`` par ``filleul_lead``) ; no-op si
    ``utm_source`` n'est pas ``'parrainage'``, si le code de parrain est
    absent/inconnu, ou en cas d'auto-parrainage (le filleul est déjà le même
    téléphone/email que le parrain — anti-abus minimal). Notifie les managers
    de la société (repli ``_company_fallback_managers``, pas de owner dédié à
    ce stade). Best-effort — jamais d'exception propagée."""
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
    """Le funnel n'avance jamais EN ARRIÈRE en masse (même règle qu'un edit).

    - même étape → non (rien à faire) ;
    - Froid → n'importe quelle étape active → oui (réactivation) ;
    - vers Froid → oui (mise au parking, autorisée depuis n'importe où) ;
    - sinon → uniquement vers une étape PLUS avancée.
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
                lead.stage = target_stage
                lead.save(update_fields=['stage'])
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
                if lead.perdu and lead.motif_perte == motif:
                    unchanged += 1
                    continue
                old_perdu, old_motif = lead.perdu, lead.motif_perte
                lead.perdu = True
                lead.motif_perte = motif
                lead.save(update_fields=['perdu', 'motif_perte'])
                if not old_perdu:
                    activity.log_bulk_change(lead, user, 'perdu', old_perdu, True)
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

    Lit ``CompanyProfile.ramadan_pacing`` (BooleanField nullable, défaut False).
    Renvoie False si le profil n'existe pas ou que le champ est absent.
    Ajout futur : le champ ``ramadan_pacing`` est posé au besoin sur
    CompanyProfile via une migration dédiée ; en attendant, ce helper renvoie
    toujours False (comportement non-ramadan inchangé).
    """
    if company is None:
        return False
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        return bool(getattr(profile, 'ramadan_pacing', False))
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


def reserver_creneau_public(token, *, scheduled_at, notes=None):
    """XSAL17 — Réservation PUBLIQUE d'un créneau via un jeton
    ``BookingLink`` : crée l'``Appointment`` (via ``book_appointment``,
    même logique métier que la création interne — user=None, un visiteur
    anonyme n'est jamais un utilisateur ERP) et marque le lien comme
    UTILISÉ (idempotent : un second appel avec le même jeton lève
    :class:`BookingLinkUnavailable`, jamais un second rendez-vous).
    Le lead atterrit toujours sur SON lead d'origine (booking-to-lead) —
    jamais un autre, jamais choisi par le visiteur."""
    from django.utils import timezone as _timezone

    link = resolve_booking_link(token)
    appointment = book_appointment(
        lead=link.lead, scheduled_at=scheduled_at, notes=notes, user=None)
    link.used_at = _timezone.now()
    link.appointment = appointment
    link.save(update_fields=['used_at', 'appointment'])
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
        ip_confirmation=None):
    """Pose (ou met à jour) le consentement d'un lead pour un canal donné.

    ``purpose`` ∈ 'marketing' / 'email' / 'sms' / 'whatsapp'…
    ``lead.email`` est utilisé comme identifiant si présent, sinon
    ``lead.telephone``. Crée une NOUVELLE entrée à chaque appel (le registre
    ``ConsentRecord`` est un historique append-only, cf. FG394) — la lecture
    de l'état courant prend toujours la ligne la plus récente.
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
        occurred_at=timezone.now(),
        version_texte=version_texte or '',
        ip_confirmation=ip_confirmation,
    )


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
    return lead


def update_lead_from_public_api(*, company, lead_id, fields):
    """XPLT5 — met à jour un lead EXISTANT DE CETTE SOCIÉTÉ depuis l'API
    publique en écriture. Lève ``Lead.DoesNotExist`` si le lead n'appartient
    pas (ou plus) à ``company`` — jamais de fuite cross-tenant. Champs
    filtrés à la même liste blanche que la création ; ``stage`` validé contre
    STAGES.py. Journalise chaque champ changé (chatter, acteur système)."""
    lead = Lead.objects.get(company=company, pk=lead_id)
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS}
    stage = clean.get('stage')
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    old = Lead.objects.get(pk=lead.pk)
    changed_fields = []
    for field, value in clean.items():
        if value in (None, '') and field != 'stage':
            continue
        if getattr(lead, field) != value:
            setattr(lead, field, value)
            changed_fields.append(field)
    if changed_fields:
        lead.save(update_fields=changed_fields)
        activity.log_changes(old, lead, None)
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


def delete_leads_for_company(company):
    """NTAPI27 — supprime TOUS les leads de ``company``. Point d'entrée
    d'ÉCRITURE cross-app sanctionné pour ``apps.publicapi`` (reset du bac à
    sable API) : ``company`` y est TOUJOURS la société-jumelle sandbox,
    jamais une société réelle — l'appelant en est seul responsable. Renvoie
    le nombre supprimé."""
    from .models import Lead
    qs = Lead.objects.filter(company=company)
    count = qs.count()
    qs.delete()
    return count
