"""NTADM13/14 — Package de configuration exportable, avec diff avant
application (jamais silencieux — `ConfigPackageApplication`).

Catégories exportées : `Role` custom (`est_systeme=False`), `CustomFieldDef`,
`MessageTemplate`. JAMAIS de donnée métier/client (leads/devis/clients),
jamais de secret (RIB/ICE/logo exclus explicitement). `roles`/`customfields`/
`parametres` sont des apps de FONDATION — import direct autorisé."""
from __future__ import annotations

from .models import ConfigPackage, ConfigPackageApplication


def _roles_custom(company):
    from apps.roles.models import Role
    return [
        {'nom': r.nom, 'permissions': r.permissions}
        for r in Role.objects.filter(company=company, est_systeme=False).order_by('nom')
    ]


def _custom_fields(company):
    from apps.customfields.models import CustomFieldDef
    return [
        {'code': f.code, 'module': f.module, 'type': f.type, 'libelle': f.libelle}
        for f in CustomFieldDef.objects.filter(company=company).order_by('code')
    ]


def _message_templates(company):
    from apps.parametres.models_messages import MessageTemplate
    return [
        {'cle': t.cle, 'corps_fr': t.corps_fr, 'corps_darija': t.corps_darija}
        for t in MessageTemplate.objects.filter(company=company).order_by('cle')
    ]


def construire_contenu(company):
    """Snapshot horodaté des catégories de configuration — jamais de donnée
    métier/client."""
    return {
        'roles_custom': _roles_custom(company),
        'custom_fields': _custom_fields(company),
        'message_templates': _message_templates(company),
    }


def exporter_config(company, *, nom, user=None):
    """NTADM13 — exporte la config actuelle en `ConfigPackage` versionné."""
    derniere_version = ConfigPackage.objects.filter(
        company=company, nom=nom).order_by('-version').first()
    version = (derniere_version.version + 1) if derniere_version else 1
    contenu = construire_contenu(company)
    return ConfigPackage.objects.create(
        company=company, nom=nom, version=version, contenu=contenu,
        cree_par=user if getattr(user, 'pk', None) else None)


def _diff_liste(actuel, importe, cle):
    """Diff simple d'une liste de dicts par `cle` : ajouts / modifications /
    suppressions (par rapport à l'état ACTUEL du tenant cible)."""
    par_cle_actuel = {item[cle]: item for item in actuel}
    par_cle_importe = {item[cle]: item for item in importe}
    ajouts = [v for k, v in par_cle_importe.items() if k not in par_cle_actuel]
    suppressions = [v for k, v in par_cle_actuel.items() if k not in par_cle_importe]
    modifications = [
        {'avant': par_cle_actuel[k], 'apres': v}
        for k, v in par_cle_importe.items()
        if k in par_cle_actuel and par_cle_actuel[k] != v
    ]
    return {'ajouts': ajouts, 'modifications': modifications, 'suppressions': suppressions}


def previsualiser_import(company, contenu_importe):
    """NTADM14 — dry-run, N'ÉCRIT RIEN : diff structuré entre `contenu_importe`
    et l'état courant de `company`."""
    actuel = construire_contenu(company)
    return {
        'roles_custom': _diff_liste(
            actuel['roles_custom'], contenu_importe.get('roles_custom', []), 'nom'),
        'custom_fields': _diff_liste(
            actuel['custom_fields'], contenu_importe.get('custom_fields', []), 'code'),
        'message_templates': _diff_liste(
            actuel['message_templates'],
            contenu_importe.get('message_templates', []), 'cle'),
    }


def appliquer_import(company, contenu_importe, *, user=None):
    """NTADM14 — applique le package importé après confirmation explicite.
    Exclut les rôles `est_systeme=True` et les données propres au tenant
    (RIB/ICE/logo) — seule la STRUCTURE (libellés/permissions/templates) est
    importée. Idempotent : rejouer 2 fois donne un diff vide au 2e passage
    (`get_or_create`/`update_or_create` sur les clés naturelles)."""
    diff = previsualiser_import(company, contenu_importe)

    from apps.roles.models import Role
    for role_data in contenu_importe.get('roles_custom', []):
        # Lookup aligné sur l'unique (company, nom) ; ne JAMAIS écraser un rôle
        # système (est_systeme=True) — la structure importée ne touche que les
        # rôles custom (NTADM14).
        existant = Role.objects.filter(
            company=company, nom=role_data['nom']).first()
        if existant and existant.est_systeme:
            continue
        Role.objects.update_or_create(
            company=company, nom=role_data['nom'],
            defaults={
                'permissions': role_data.get('permissions', []),
                'est_systeme': False,
            })

    from apps.customfields.models import CustomFieldDef
    for field in contenu_importe.get('custom_fields', []):
        # Lookup aligné sur l'unique (company, module, code).
        CustomFieldDef.objects.update_or_create(
            company=company, module=field.get('module', ''), code=field['code'],
            defaults={
                'type': field.get('type', 'text'),
                'libelle': field.get('libelle', field['code']),
            })

    from apps.parametres.models_messages import MessageTemplate
    for tpl in contenu_importe.get('message_templates', []):
        # Lookup aligné sur l'unique (company, cle).
        MessageTemplate.objects.update_or_create(
            company=company, cle=tpl['cle'],
            defaults={
                'corps_fr': tpl.get('corps_fr', ''),
                'corps_darija': tpl.get('corps_darija', ''),
            })

    ConfigPackageApplication.objects.create(
        company=company,
        package_nom=contenu_importe.get('_nom', ''),
        package_version=contenu_importe.get('_version', 1),
        action=ConfigPackageApplication.Action.APPLICATION,
        diff=diff,
        applique_par=user if getattr(user, 'pk', None) else None)
    return diff
