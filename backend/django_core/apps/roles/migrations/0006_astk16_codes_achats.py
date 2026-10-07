# ASTK16 — les codes ``achats_commander``, ``achats_receptionner``,
# ``achats_payer`` et ``catalogue_prix_modifier`` entrent au catalogue des rôles.
#
# ``Role.permissions`` est une LISTE JSON sans ``choices`` : ajouter des codes à
# ``ALL_PERMISSIONS`` ne change aucun schéma. Cette migration grave, DANS la
# chaîne de ``roles``, les deux garanties du geste (patron ``0005_calx347``) :
#
# * AVANT (``forwards``) — AUCUN rôle déjà en base ne reçoit ces codes : un
#   rôle personnalisé existant ne gagne pas en silence le droit de commander,
#   réceptionner, payer ou modifier un prix. (Les rôles SYSTÈME — Directeur,
#   Administrateur, Technicien responsable — sont réalignés sur le catalogue à
#   chaque déploiement par ``init_roles``, comme pour tout code.)
# * ARRIÈRE (``backwards``) — les codes sont RETIRÉS de chaque rôle qui les
#   aurait reçus entre-temps ; sans ce retrait, ``RoleSerializer.
#   validate_permissions`` de l'ancien serveur refuserait toute modification
#   du rôle (« Permissions invalides »).
#
# Prudences : ligne à ligne avec ``update_fields``, l'ordre des autres codes
# est préservé, idempotente.

from django.db import migrations

CODES = frozenset({
    'achats_commander',
    'achats_receptionner',
    'achats_payer',
    'catalogue_prix_modifier',
})


def aucun_titulaire(apps, schema_editor):
    """Zéro titulaire : rien n'est écrit, volontairement."""


def retirer_les_codes(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.all().iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if not CODES.intersection(avant):
            continue
        role.permissions = [code for code in avant if code not in CODES]
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0005_calx347_permission_calepinage_approuver'),
    ]

    operations = [
        migrations.RunPython(aucun_titulaire, retirer_les_codes),
    ]
