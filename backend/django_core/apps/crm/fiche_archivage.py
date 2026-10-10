"""Archivage du chatter et suppression des leads (SPL20, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from django.apps import apps as django_apps


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
