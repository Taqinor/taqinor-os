"""Score et MQL des leads (SPL16, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import logging

from django.utils import timezone

from .models import Lead, LeadActivity

logger = logging.getLogger(__name__)


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
