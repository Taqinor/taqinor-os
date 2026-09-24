# CALX347 — le code ``calepinage_approuver`` entre au catalogue des rôles.
#
# ``Role.permissions`` est une LISTE JSON sans ``choices`` : ajouter un code à
# ``ALL_PERMISSIONS`` ne change aucun schéma. Cette migration existe pour
# graver, DANS la chaîne de ``roles``, les deux garanties du geste :
#
# * AVANT (``forwards``) — AUCUN rôle déjà en base ne reçoit le code. La
#   décision fondateur du 21/09/2026 est « rôle d'approbation à zéro titulaire
#   tant qu'il n'est pas attribué » : l'approbation ne doit pas s'ouvrir en
#   silence à un rôle métier existant. (Les rôles SYSTÈME Directeur et
#   Administrateur, eux, sont réalignés sur le catalogue à chaque déploiement
#   par ``init_roles`` — comme pour tout code du catalogue, sans exception.)
# * ARRIÈRE (``backwards``) — le code est RETIRÉ de chaque rôle qui l'aurait
#   reçu entre-temps. Sans ce retrait, un retour arrière laisserait en base un
#   code que l'ancien serveur ne connaît plus : ``RoleSerializer.
#   validate_permissions`` refuserait alors TOUTE modification de ce rôle
#   (« Permissions invalides »), et l'administrateur ne pourrait plus le
#   corriger depuis l'écran des rôles.
#
# Prudences (patron ``0004_vta4``) : ligne à ligne avec ``update_fields``,
# l'ordre des autres codes est préservé, idempotente.

from django.db import migrations

CODE = 'calepinage_approuver'


def aucun_titulaire(apps, schema_editor):
    """Zéro titulaire : rien n'est écrit, volontairement."""


def retirer_le_code(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.all().iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE not in avant:
            continue
        role.permissions = [code for code in avant if code != CODE]
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0004_vta4_renommer_permissions_visite'),
    ]

    operations = [
        migrations.RunPython(aucun_titulaire, retirer_le_code),
    ]
