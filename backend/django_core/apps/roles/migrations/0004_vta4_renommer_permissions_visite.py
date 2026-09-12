# VTA4 — les codes de permission de la visite terrain passent de
# ``crm_visite_*`` à ``visites_*`` (la visite a quitté le CRM pour son app
# autonome ; un commercial terrain porte ces droits SANS aucun droit CRM).
#
# Sans cette data migration, TOUS les rôles déjà en base garderaient l'ancien
# code : le serveur ne le reconnaîtrait plus et chaque responsable perdrait
# silencieusement l'accès aux visites au déploiement. On réécrit donc
# ``Role.permissions`` (JSONField) pour TOUS les rôles de TOUTES les sociétés.
#
# Prudences :
# * IDEMPOTENTE — un rôle déjà migré (ou créé après) n'est pas retouché, et
#   l'ordre des codes est préservé (aucun tri qui ferait un diff cosmétique) ;
# * pas de doublon — si un rôle porte DÉJÀ le nouveau code, l'ancien est
#   simplement retiré ;
# * RÉVERSIBLE — l'inverse repointe ``visites_*`` sur ``crm_visite_*`` ;
# * écriture ligne à ligne, avec ``update_fields`` : jamais un UPDATE global.

from django.db import migrations

RENOMMAGES = {
    'crm_visite_voir': 'visites_voir',
    'crm_visite_creer': 'visites_creer',
    'crm_visite_modifier': 'visites_modifier',
    'crm_visite_valider': 'visites_valider',
}


def _reecrire(apps, table):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.all().iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if not any(code in table for code in avant):
            continue  # déjà migré, ou aucun droit visite : on ne touche pas.
        apres = []
        for code in avant:
            nouveau = table.get(code, code)
            if nouveau not in apres:
                apres.append(nouveau)
        if apres != avant:
            role.permissions = apres
            role.save(update_fields=['permissions'])


def renommer(apps, schema_editor):
    _reecrire(apps, RENOMMAGES)


def renommer_inverse(apps, schema_editor):
    _reecrire(apps, {v: k for k, v in RENOMMAGES.items()})


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0003_ntadm21_role_perimetre'),
    ]

    operations = [
        migrations.RunPython(renommer, renommer_inverse),
    ]
