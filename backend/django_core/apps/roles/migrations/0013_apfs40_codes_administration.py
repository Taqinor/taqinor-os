# APFS40 / D-APFS-1 — ``integrations_gerer``, ``modules_gerer`` et ``dsr_traiter``
# entrent au catalogue (patron ``0006_astk16_codes_achats``) : AVANT, aucun rôle
# déjà en base ne les reçoit (les rôles système sont réalignés par
# ``init_roles``) ; ARRIÈRE, les codes sont retirés de chaque rôle qui les porte.

from django.db import migrations

CODES = frozenset({'integrations_gerer', 'modules_gerer', 'dsr_traiter'})


def aucun_titulaire(apps, schema_editor):
    """Zéro titulaire : rien n'est écrit, volontairement."""


def retirer_les_codes(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.all().iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODES.intersection(avant):
            role.permissions = [code for code in avant if code not in CODES]
            role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0012_organigramme'),
    ]

    operations = [
        migrations.RunPython(aucun_titulaire, retirer_les_codes),
    ]
