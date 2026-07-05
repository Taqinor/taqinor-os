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
import re as _re

from django.utils import timezone

from . import activity, stages
from .models import Canal, Client, Lead, LeadActivity, PointContact

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


def default_responsable_for(company):
    """Responsable assigné par défaut aux nouveaux leads d'une société.

    Source unique : le profil entreprise (Paramètres → « Responsable par
    défaut des nouveaux leads »). None si non configuré ou pas de société.
    """
    if company is None:
        return None
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.objects.filter(company=company).first()
    return profile.responsable_defaut_leads if profile else None


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


def resolve_client_for_lead(lead: Lead) -> Client:
    from django.db import IntegrityError, transaction

    if lead.client_id:
        return lead.client

    def _find_existing():
        if not lead.email:
            return None
        return Client.objects.filter(
            company=lead.company, email__iexact=lead.email,
        ).first()

    client = _find_existing()

    if client is None:
        # Séparateur VISIBLE entre rue et ville : un \n disparaît dans les
        # champs <input> et collait l'adresse à la ville (« …AuditCasablanca »).
        adresse = lead.adresse or ''
        if lead.ville:
            adresse = ', '.join(p for p in (adresse, lead.ville) if p)
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
    # éviter).
    if telephone:
        lead.telephone = telephone
        lead.whatsapp = telephone
        lead.save(update_fields=['telephone', 'whatsapp'])
    return lead


# ── XMKT32 — Sync Meta Lead Ads → leads CRM (gated) ───────────────────────────

_META_LEAD_ADS_SYSTEM = 'meta_lead_ads'


def create_lead_from_meta_lead_ads(
        *, company, leadgen_id, field_data,
        campaign_name='', adset_name='') -> Lead:
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

    Attribution : ``canal=META_ADS``, ``utm_source='facebook'``,
    ``utm_campaign``/``utm_content`` portent le nom de campagne/adset quand
    fournis par l'appelant.

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

    utm_source = 'facebook'
    utm_campaign = (campaign_name or '')[:300] or None
    utm_content = (adset_name or '')[:300] or None

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


def notify_client_contact_request(devis_reference: str, lead,
                                  canal='', message='') -> None:
    """QJ27 — Le CLIENT demande à être contacté (depuis la proposition publique).

    Consigne la demande dans le chatter du lead (note SYSTÈME, user=None — ne
    fait donc jamais avancer le funnel QJ7) ET notifie le responsable du lead
    ET son supérieur (repli managers société quand l'un des deux manque), avec
    un lien wa.me « répondre maintenant ». Best-effort — jamais d'exception
    propagée. La société vient TOUJOURS du lead (jamais d'un corps de requête).
    """
    try:
        canal_label = {
            'whatsapp': 'par WhatsApp',
            'rappel': 'par téléphone (rappel)',
        }.get((canal or '').strip(), '')
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Le client'
        # Note chatter (toujours, même sans destinataire notifiable).
        note = f'Le client demande à être contacté ({devis_reference})'
        if canal_label:
            note += f' — {canal_label}'
        if message:
            note += f' : « {message[:500]} »'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=note)

        recipients = lead_notification_recipients(lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        wa_url = _build_lead_wa_reply_url(lead)
        body_parts = [
            f'{nom} demande à être contacté au sujet du devis '
            f'{devis_reference}'
            + (f' ({canal_label})' if canal_label else '') + '.']
        if message:
            body_parts.append(f'Message : « {message[:500]} »')
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
                import logging
                logging.getLogger('crm.audit').warning(
                    'BULK HARD DELETE lead id=%s "%s" par user=%s (company=%s)',
                    lead.id, lead, getattr(user, 'username', '?'), company.id)
                lead.delete()
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
