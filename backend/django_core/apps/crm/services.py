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
from .models import Canal, Client, Lead, LeadActivity

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

    COLD est un état de PARKING, pas « plus avancé » : il est classé sous
    QUOTE_SENT pour qu'un lead froid soit RÉACTIVÉ par les deux mouvements
    automatiques (devis envoyé / accepté).
    """
    if stage_key == 'COLD':
        return stages.STAGES.index('QUOTE_SENT') - 1
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
    if lead.perdu:
        return False
    if lead.stage != stages.NEW:
        return False
    lead.stage = _STAGE_CONTACTED
    lead.save(update_fields=['stage'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[stages.NEW],
        new_value=stages.STAGE_LABELS[_STAGE_CONTACTED],
        body='auto — premier contact',
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
    lead = devis.lead
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
    n'existe encore (d'où l'absence d'instance). Inclut les archivés."""
    phone = normalize_phone(phone)
    email = normalize_email(email)
    if not phone and not email:
        return []
    qs = Lead.objects.filter(company=company)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    candidates = []
    for other in qs:
        if phone and normalize_phone(other.telephone) == phone:
            candidates.append(other)
        elif email and normalize_email(other.email) == email:
            candidates.append(other)
    return candidates


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
        return score
    except Exception:
        return 0


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


def noter_devis_ouvert(devis_reference: str, lead) -> None:
    """QJ1 — Consigne « Le client a ouvert le devis » dans le chatter du lead.

    Appelé par ``public_views.py`` uniquement à la PREMIÈRE ouverture du lien
    public. Best-effort : les appelants catchent toute exception.
    ``lead`` doit être un objet Lead avec company_id ; ``devis_reference`` est
    la référence textuelle du devis (pas d'import ventes ici).
    """
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Le client a ouvert le devis {devis_reference}")


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
        digits = ''.join(c for c in (phone_raw or '') if c.isdigit())
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


def notify_new_lead(lead) -> None:
    """QJ2 (a) — Notifie le responsable du lead à la CRÉATION d'un nouveau lead.

    Événement de speed-to-lead : le owner du lead est notifié dès l'arrivée du
    lead (webhook site web ou création manuelle). La notification porte un lien
    wa.me « répondre maintenant » vers le prospect. Best-effort : jamais
    d'exception propagée — un échec de notification ne doit pas casser le flux
    de création.

    Multi-tenant : le owner est résolu depuis le lead (server-side, jamais du
    corps de requête). Rien à notifier si le lead n'a pas de responsable.
    """
    try:
        owner = getattr(lead, 'owner', None)
        if owner is None:
            return
        from apps.notifications.services import notify
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Nouveau prospect'
        wa_url = _build_lead_wa_reply_url(lead)
        body_parts = [f'Un nouveau lead vient d\'arriver : {nom}.']
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        notify(
            user=owner,
            event_type='lead_new',
            title=f'Nouveau lead : {nom}',
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
    « répondre maintenant » vers le prospect. Best-effort — jamais d'exception
    propagée.
    """
    try:
        owner = getattr(lead, 'owner', None)
        if owner is None:
            return
        from apps.notifications.services import notify
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Votre client'
        wa_url = _build_lead_wa_reply_url(lead)
        body_parts = [f'{nom} vient d\'ouvrir le devis {devis_reference}.']
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        notify(
            user=owner,
            event_type='devis_opened',
            title=f'Devis {devis_reference} ouvert par le client',
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ2: notify_devis_opened échoué pour lead #%s devis %s : %s',
            getattr(lead, 'pk', '?'), devis_reference, exc)


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
