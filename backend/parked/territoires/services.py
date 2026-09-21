"""NTCRM1/NTCRM2 — Résolution + rotation round-robin par territoire.

``_rotate_member`` est le cœur race-safe (verrouillage ``select_for_update``
dans une transaction — même esprit que le patron plus-haut-utilisé+1 de
``core.numbering``/``apps.ventes.utils.references`` : jamais un pur modulo sur
``count()``, un compteur persisté par membre, incrémenté sous verrou). Les
quotas (``TerritoireMembre.quota_pct``) sont respectés au mieux : un membre
dont la part courante dépasse déjà son quota est sauté tant qu'un autre membre
éligible existe ; jamais de blocage dur (repli sur le pool complet).
"""
import logging

from django.db import transaction
from django.utils import timezone

from .models import TerritoireMembre
from .selectors import lead_criteres, match_territoire

logger = logging.getLogger(__name__)


def _rotate_member(territoire):
    """Choisit puis MARQUE (persiste) le prochain membre du territoire, sous
    verrou de ligne — deux appels concurrents ne peuvent jamais choisir le même
    « tour ». Renvoie le ``TerritoireMembre`` choisi, ou ``None`` si le
    territoire n'a aucun membre actif."""
    with transaction.atomic():
        membres = list(
            TerritoireMembre.objects.select_for_update()
            .filter(territoire=territoire, actif=True)
            .order_by('id')
        )
        if not membres:
            return None
        total_assigne = sum(m.nb_assignations for m in membres)
        eligibles = []
        for m in membres:
            if m.quota_pct is not None and total_assigne > 0:
                part_pct = (m.nb_assignations / total_assigne) * 100
                if part_pct >= float(m.quota_pct):
                    continue
            eligibles.append(m)
        pool = eligibles or membres  # tous au-delà du quota → jamais de blocage dur
        pool.sort(key=lambda m: (m.nb_assignations, m.id))
        chosen = pool[0]
        chosen.nb_assignations += 1
        chosen.dernier_assigne_at = timezone.now()
        chosen.save(update_fields=['nb_assignations', 'dernier_assigne_at'])
        return chosen


def resoudre_owner_pour_attrs(company, lead_attrs):
    """NTCRM1 — Résolution PRÉ-création : ``lead_attrs`` (dict brut, le Lead
    n'existe pas encore — webhook/création manuelle) matche-t-il un territoire
    actif ? Si oui, fait tourner la rotation et renvoie l'utilisateur choisi.
    ``None`` si aucun territoire ne matche ou si le territoire matché n'a
    aucun membre actif — l'appelant (``apps.crm.services.
    default_responsable_for``) replie alors sur XSAL11, comportement inchangé.
    Aucun chatter journalisé ici (pas encore de Lead en base)."""
    if company is None:
        return None
    territoire, _regle = match_territoire(company, lead_criteres(lead_attrs))
    if territoire is None:
        return None
    membre = _rotate_member(territoire)
    return membre.utilisateur if membre else None


def assigner_lead_territoire(lead):
    """NTCRM2 — Assigne ``lead`` (une instance ``apps.crm.models.Lead``, reçue
    en duck-typing — cette app n'importe JAMAIS ``apps.crm.models`` au niveau
    module) au territoire qui matche ses attributs, via la rotation
    race-safe ci-dessus, et journalise l'assignation dans son chatter
    (``LeadActivity``, kind MODIFICATION, champ owner). Renvoie
    ``(territoire, utilisateur)`` ; ``(None, None)`` si aucun territoire actif
    ne matche — l'appelant replie alors sur le round-robin XSAL11 existant."""
    company = getattr(lead, 'company', None)
    territoire, _regle = match_territoire(company, lead_criteres(lead))
    if territoire is None:
        return None, None
    membre = _rotate_member(territoire)
    if membre is None:
        return territoire, None
    utilisateur = membre.utilisateur
    if getattr(lead, 'pk', None):
        ancien = lead.owner
        lead.owner = utilisateur
        lead.save(update_fields=['owner'])
        try:
            # Import fonction-local : cross-app write orchestré par l'app
            # QUI DÉTIENT LeadActivity (apps.crm) — jamais au niveau module.
            from apps.crm.models import LeadActivity
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.MODIFICATION,
                field='owner', field_label='Responsable',
                old_value=getattr(ancien, 'username', '') if ancien else '',
                new_value=getattr(utilisateur, 'username', ''),
                body=f'auto — territoire « {territoire.nom} »',
            )
        except Exception:  # noqa: BLE001 — best-effort, ne casse jamais l'assignation
            logger.warning(
                'territoires: chatter non journalisé pour le lead #%s',
                getattr(lead, 'pk', '?'), exc_info=True)
    return territoire, utilisateur
