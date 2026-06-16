"""
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

from . import stages
from .models import Client, Lead, LeadActivity

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


def stage_rank(stage_key: str) -> int:
    """Rang public d'avancement d'une étape (réutilise _rang_funnel)."""
    return _rang_funnel(stage_key)


def can_move_to_stage(lead, nouveau_stage: str):
    """Règle « jamais en arrière » du funnel pour un changement MANUEL d'étape.

    Renvoie (ok: bool, raison: str|None). Aligné sur la logique de
    avancer_stage_pour_devis :
      - une étape inconnue est refusée ;
      - un lead Perdu (drapeau) ne bouge jamais via une action en masse ;
      - réactiver depuis COLD/Froid est autorisé (COLD est un parking, classé
        sous QUOTE_SENT par _rang_funnel — comme une édition simple) ;
      - sinon on n'autorise que d'avancer (ou de parquer en COLD).
    """
    if nouveau_stage not in stages.STAGES:
        return False, "Étape inconnue."
    if lead.perdu:
        return False, "Lead perdu — réactivez-le d'abord."
    if lead.stage == nouveau_stage:
        return False, "Déjà à cette étape."
    # COLD est un parking : on peut toujours y mettre un lead.
    if nouveau_stage == 'COLD':
        return True, None
    # Sinon : pas de recul dans l'entonnoir (COLD compte comme < QUOTE_SENT,
    # donc en sortir vers une étape plus avancée est permis).
    if _rang_funnel(nouveau_stage) < _rang_funnel(lead.stage):
        return False, "Le funnel ne recule pas — étape ignorée."
    return True, None


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
        # SIGNED_QUOTE_CAPI_HOOK: fire on transition INTO SIGNED — entering Signé here
        # (auto via devis accepté) est équivalent à une entrée manuelle.
        pass

    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[ancien_stage],
        new_value=stages.STAGE_LABELS[stage_cible],
        body=f"auto — devis {devis.reference} {suffixe}",
    )


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


# Champs scalaires recopiés sur le survivant SEULEMENT s'il les a vides
# (« on garde la valeur la plus complète », jamais d'écrasement).
_MERGE_FILL_FIELDS = [
    'prenom', 'societe', 'email', 'telephone', 'whatsapp', 'adresse', 'ville',
    'gps_lat', 'gps_lng', 'facture_hiver', 'facture_ete', 'ete_differente',
    'conso_mensuelle_kwh', 'tranche_onee', 'raccordement', 'type_installation',
    'type_toiture', 'surface_toiture_m2', 'orientation', 'inclinaison_deg',
    'ombrage', 'ombrage_notes', 'nb_etages', 'structure_pref',
    'taille_souhaitee_kwc', 'batterie_souhaitee', 'pompe_cv', 'pompe_hmt_m',
    'pompe_debit_m3h', 'canal', 'motif_perte', 'note', 'whatsapp_opt_in',
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


def find_duplicate_leads(lead):
    """Leads probablement en double : même téléphone OU email normalisé, même
    société, hors le lead lui-même. Inclut les archivés (pour les retrouver)."""
    phone = normalize_phone(lead.telephone)
    email = normalize_email(lead.email)
    qs = Lead.objects.filter(company=lead.company).exclude(pk=lead.pk)
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
                from apps.installations.models import Installation
                Installation.objects.filter(lead=absorbed).update(lead=survivor)
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


def resolve_client_for_lead(lead: Lead) -> Client:
    if lead.client_id:
        return lead.client

    client = None
    if lead.email:
        client = Client.objects.filter(
            company=lead.company, email__iexact=lead.email,
        ).first()

    if client is None:
        # Séparateur VISIBLE entre rue et ville : un \n disparaît dans les
        # champs <input> et collait l'adresse à la ville (« …AuditCasablanca »).
        adresse = lead.adresse or ''
        if lead.ville:
            adresse = ', '.join(p for p in (adresse, lead.ville) if p)
        client = Client.objects.create(
            company=lead.company,
            nom=lead.nom,
            prenom=lead.prenom,
            email=lead.email,
            telephone=(lead.telephone or '')[:20] or None,
            adresse=adresse or None,
        )

    lead.client = client
    lead.save(update_fields=['client'])
    return client
