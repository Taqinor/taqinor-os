"""NTADM41 — notification d'un changement de plan de licence.

Appelé depuis ``apps.parametres.admin.CompanyProfileAdmin.save_model`` (le
SEUL point d'écriture de ``CompanyProfile.plan`` — assignation réservée au
founder, jamais un endpoint tenant-facing) : journalise le changement
(``SettingsAuditLog``, section ``'licence'`` — lu par l'écran NTADM9,
``apps.adminops.views_licences._historique_plan``) puis déclenche le webhook
sortant ``plan.changed`` (``apps.publicapi``, NTADM41). Best-effort, jamais
bloquant pour l'enregistrement du profil."""
from __future__ import annotations


def notifier_changement_plan(profile, *, ancien_plan_id, user=None):
    """``profile.plan`` a DÉJÀ été sauvegardé (nouvelle valeur) ; reconstruit
    l'ANCIEN plan par ``ancien_plan_id`` (lu via
    ``apps.adminops.selectors.plan_par_id`` — jamais un import direct du
    modèle d'une autre app)."""
    from apps.adminops import selectors as adminops_selectors

    ancien = adminops_selectors.plan_par_id(ancien_plan_id)
    nouveau = profile.plan

    from .models import SettingsAuditLog
    try:
        SettingsAuditLog.log_change(
            company=profile.company, user=user, section='licence', field='plan',
            field_label='Plan de licence',
            old=ancien.nom if ancien else None,
            new=nouveau.nom if nouveau else None,
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        pass

    if profile.company_id is None:
        return
    try:
        from apps.publicapi import delivery
        from apps.publicapi.constants import EVENT_PLAN_CHANGED
        delivery.dispatch_event(profile.company_id, EVENT_PLAN_CHANGED, {
            'event': EVENT_PLAN_CHANGED,
            'company_id': profile.company_id,
            'ancien_plan': ancien.code if ancien else None,
            'nouveau_plan': nouveau.code if nouveau else None,
        })
    except Exception:  # noqa: BLE001 — jamais bloquant
        pass


def journaliser_modification_palier(plan, avant, user=None):
    """APAR55 — trace la modification d'un PALIER ``PlanLicence`` (admin
    founder, ``apps.adminops.admin.PlanLicenceAdmin.save_model``) dans le
    journal ``licence`` de CHAQUE société rattachée à ce palier (avant/après).

    ``avant`` : ``{champ: valeur}`` lu en base AVANT l'enregistrement. Retourne
    le nombre de lignes écrites. Une société n'apprend jamais en silence que
    son palier a changé de contenu."""
    from .models import CompanyProfile, SettingsAuditLog

    champs = (
        ('modules_inclus', 'Modules inclus du palier'),
        ('actif', 'Palier actif'),
        ('nom', 'Nom du palier'),
        ('code', 'Code du palier'),
    )
    changes = []
    for champ, libelle in champs:
        ancien = (avant or {}).get(champ)
        nouveau = getattr(plan, champ, None)
        if champ == 'modules_inclus':
            ancien = sorted(ancien or [])
            nouveau = sorted(nouveau or [])
        if ancien != nouveau:
            changes.append((champ, libelle, ancien, nouveau))
    if not changes:
        return 0
    ecrites = 0
    profils = CompanyProfile.objects.filter(plan_id=plan.pk).exclude(
        company__isnull=True).select_related('company')
    for profil in profils:
        for champ, libelle, ancien, nouveau in changes:
            SettingsAuditLog.log_change(
                company=profil.company, user=user, section='licence',
                field=f'palier.{champ}',
                field_label=f'{libelle} « {plan.nom} »',
                old=ancien, new=nouveau)
            ecrites += 1
    return ecrites
