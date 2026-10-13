"""NTADM13/14 — Package de configuration exportable, avec diff avant
application (jamais silencieux — `ConfigPackageApplication`).

Catégories exportées : `Role` custom (`est_systeme=False`), `CustomFieldDef`,
`MessageTemplate`. JAMAIS de donnée métier/client (leads/devis/clients),
jamais de secret (RIB/ICE/logo exclus explicitement). `roles`/`customfields`/
`parametres` sont des apps de FONDATION — import direct autorisé.

SOLMVP-sweep (2026-09-21) — la catégorie `playbooks` (NTMIG24 — articles `kb`
de type playbook) est retirée : `apps.kb` est sorti du MVP solaire (Groupe
SOLMVP, en cours de mise en coquille par la lane SOLMVP30b), donc
`kb.selectors.playbooks_config_snapshot`/`kb.services.appliquer_playbook_config`
n'existent plus. Aucun test ne couvrait cette catégorie par sa clé (vérifié)."""
from __future__ import annotations

from rest_framework import serializers

from .models import ConfigPackage, ConfigPackageApplication

_INT_MAX = 2147483647


def _contient_nul(valeur):
    """Un caractère NUL fait échouer l'écriture PostgreSQL (500)."""
    if isinstance(valeur, str):
        return '\x00' in valeur
    if isinstance(valeur, dict):
        return any(_contient_nul(k) or _contient_nul(v)
                   for k, v in valeur.items())
    if isinstance(valeur, list):
        return any(_contient_nul(v) for v in valeur)
    return False


def valider_contenu_import(contenu):
    """ENF11 (api-fuzz « Server error ») — valide la FORME d'un package avant
    toute lecture/écriture : un contenu mal formé (liste là où une chaîne est
    attendue, clé naturelle absente ou non texte, NUL…) levait ``KeyError`` /
    ``TypeError`` / ``DataError`` (500). Lève une 400 nommant le champ fautif ;
    un package bien formé (même vide) passe inchangé."""
    erreurs = {}
    if _contient_nul(contenu):
        erreurs['contenu'] = ['Caractère nul interdit.']
    nom = contenu.get('_nom', '')
    if not isinstance(nom, str) or len(nom) > 150:
        erreurs['_nom'] = ['Chaîne de 150 caractères maximum attendue.']
    version = contenu.get('_version', 1)
    if (isinstance(version, bool) or not isinstance(version, int)
            or not 0 <= version <= _INT_MAX):
        erreurs['_version'] = ['Entier positif attendu.']
    # (catégorie, clé naturelle, {champ texte: longueur max})
    for categorie, cle, textes in (
            ('roles_custom', 'nom', {'nom': 100}),
            ('custom_fields', 'code',
             {'code': 50, 'module': 60, 'type': 12, 'libelle': 120}),
            ('message_templates', 'cle',
             {'cle': 40, 'corps_fr': None, 'corps_darija': None})):
        liste = contenu.get(categorie, [])
        if not isinstance(liste, list):
            erreurs[categorie] = ['Liste attendue.']
            continue
        for i, item in enumerate(liste):
            if not isinstance(item, dict)                     or not isinstance(item.get(cle), str):
                erreurs[categorie] = [
                    f'Élément {i} : objet avec « {cle} » (texte) attendu.']
                break
            faux = [
                c for c, maxi in textes.items()
                if c in item and (not isinstance(item[c], str)
                                  or (maxi and len(item[c]) > maxi))]
            if categorie == 'roles_custom' and 'permissions' in item and (
                    not isinstance(item['permissions'], list)
                    or not all(isinstance(x, str)
                               for x in item['permissions'])):
                faux.append('permissions')
            if faux:
                erreurs[categorie] = [
                    f'Élément {i} : champ(s) invalide(s) : '
                    f'{", ".join(faux)}.']
                break
    if erreurs:
        raise serializers.ValidationError(erreurs)


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
    valider_contenu_import(contenu_importe)
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
