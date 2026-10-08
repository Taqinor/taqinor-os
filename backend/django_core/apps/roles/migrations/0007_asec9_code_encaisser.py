# ASEC9 / D-ASEC-1 — le code ``encaisser`` entre au catalogue des rôles.
#
# ``Role.permissions`` est une LISTE JSON sans ``choices`` : aucun schéma ne
# change. Cette migration grave le geste dans la chaîne de ``roles`` (patron
# ``0006_astk16``) :
#
# * AVANT (``forwards``) — ajout aux SEULS rôles système autorisés
#   (``est_systeme=True`` : Directeur, Administrateur, Commercial, Commercial
#   responsable). Un rôle personnalisé existant ne reçoit RIEN.
# * ARRIÈRE (``backwards``) — le code est RETIRÉ de tout rôle ; sans ce retrait
#   ``RoleSerializer.validate_permissions`` de l'ancien serveur refuserait toute
#   modification du rôle (« Permissions invalides »).
#
# Ligne à ligne avec ``update_fields``, ordre des autres codes préservé
# (ajout en fin), idempotente.

from django.db import migrations

CODE = 'encaisser'
TITULAIRES = frozenset({
    'Directeur', 'Administrateur', 'Commercial', 'Commercial responsable',
})


def ajouter_aux_roles_systeme(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    qs = Role.objects.filter(est_systeme=True, nom__in=TITULAIRES)
    for role in qs.iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE in avant:
            continue
        role.permissions = list(avant) + [CODE]
        role.save(update_fields=['permissions'])


def retirer_le_code(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.all().iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE not in avant:
            continue
        role.permissions = [c for c in avant if c != CODE]
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0006_astk16_codes_achats'),
    ]

    operations = [
        migrations.RunPython(ajouter_aux_roles_systeme, retirer_le_code),
    ]
