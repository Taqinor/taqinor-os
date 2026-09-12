"""NTGRC4 — politique de rétention CRM pilotée par `grc.PolitiqueRetentionObjet`.

Le CRM garde la main sur le COMMENT (quels objets, quel scrub) ; ``grc`` ne
fournit que le QUOI et le COMBIEN DE TEMPS (type d'objet, durée, action). La
politique s'enregistre dans le registre de FONDATION ``core.retention`` —
``core`` ne connaît que le nom et le callable, jamais la logique métier.

DRY-RUN par défaut : ``run_retention`` passe ``apply_=False`` tant que
``--commit``/``--apply`` n'est pas donné, et une politique en dry-run NE DOIT
RIEN modifier. C'est respecté ici : en dry-run on se contente de COMPTER.

Actions réellement exécutables côté CRM : ``anonymiser``. ``archiver`` n'a
aucun sens pour un lead/client (il n'existe pas d'archive CRM) : l'action
retombe alors sur ``signaler`` — un simple comptage, jamais une suppression
inventée.
"""
from __future__ import annotations

TYPES = ('crm_lead', 'crm_client')

MOTIF = 'Rétention CRM échue (politique GRC)'


def _echus(politique, now):
    """Objets échus pour CETTE politique (queryset borné à sa société)."""
    from django.utils import timezone

    from .models import Client, Lead

    cutoff = now - timezone.timedelta(days=politique['jours'])
    company = politique['company']
    if politique['type_objet'] == 'crm_lead':
        return Lead.objects.filter(company=company, date_creation__lt=cutoff)
    return Client.objects.filter(
        company=company, date_creation__lt=cutoff, is_anonymized=False)


def sweep_objets(now, apply_):
    """Balaye les leads/clients échus selon les politiques GRC actives.

    Renvoie le nombre d'objets échus (dry-run) ou réellement traités.
    """
    from apps.grc.selectors import politiques_retention_actives

    from .dsr_provider import anonymiser_client, anonymiser_lead

    total = 0
    for politique in politiques_retention_actives(TYPES):
        qs = _echus(politique, now)
        if not apply_:
            total += qs.count()
            continue
        if politique['action'] != 'anonymiser':
            # « signaler » (et « archiver », sans archive CRM) : on compte, on
            # ne touche à RIEN.
            total += qs.count()
            continue
        company = politique['company']
        est_lead = politique['type_objet'] == 'crm_lead'
        for objet in qs.iterator(chunk_size=200):
            if est_lead:
                total += anonymiser_lead(company, objet, motif=MOTIF)
            else:
                total += anonymiser_client(company, objet, motif=MOTIF)
    return total


def register():
    """Enregistre la politique CRM par TYPE D'OBJET (idempotent, ready())."""
    from core.retention import register_retention_policy

    register_retention_policy('crm_objets_echus', sweep_objets)
