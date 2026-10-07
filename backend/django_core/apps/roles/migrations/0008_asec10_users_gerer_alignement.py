# ASEC10 / D-ASEC-4 — ``users_gerer`` est APPLIQUÉ côté serveur sur toute
# écriture de compte (/users/). Les rôles système de palier « responsable » qui
# géraient déjà les comptes (via ``IsAdminOrResponsableTier``) — Commercial
# responsable, Technicien responsable, Responsable (légacy) — reçoivent le code
# pour garder cet accès. Admin RH le portait déjà ; Admin Ventes ne le porte PAS
# (choix NTADM20 verrouillé par un test) et perd donc l'écriture de comptes.
#
# Aller : ajout en fin de liste aux seuls rôles SYSTÈME nommés ci-dessous. Un
# rôle personnalisé ne reçoit rien. Retour : retrait des mêmes rôles système
# uniquement (Directeur, Administrateur, Admin RH gardent le leur).
# Idempotente, ligne à ligne, ordre des autres codes préservé.

from django.db import migrations

CODE = 'users_gerer'
ROLES = frozenset({
    'Commercial responsable', 'Technicien responsable', 'Responsable',
})


def aligner(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True, nom__in=ROLES).iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE in avant:
            continue
        role.permissions = list(avant) + [CODE]
        role.save(update_fields=['permissions'])


def desaligner(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True, nom__in=ROLES).iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE not in avant:
            continue
        role.permissions = [c for c in avant if c != CODE]
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0007_asec9_code_encaisser'),
    ]

    operations = [
        migrations.RunPython(aligner, desaligner),
    ]
