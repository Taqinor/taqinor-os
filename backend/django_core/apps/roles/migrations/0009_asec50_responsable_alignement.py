# ASEC50 / D-ASEC-4 — les codes d'export, de réaffectation et d'affectation
# technicien sont APPLIQUÉS côté serveur (``apps.roles.permissions.
# DroitDeLaGrille``). Le rôle système légacy « Responsable » faisait déjà ces
# gestes (export leads / clients / RGPD / DGI / rapport, réaffectation de lead,
# d'équipe SAV, de technicien) sans porter les codes : il les reçoit pour garder
# cet accès. Les autres rôles système suivent la grille telle quelle (Viewer,
# Utilisateur et Commercial perdent ce que la grille ne leur donne pas).
#
# Aller : ajout en fin de liste au seul rôle SYSTÈME « Responsable », de chaque
# société. Un rôle personnalisé ne reçoit rien. Retour : retrait des mêmes codes
# de ce même rôle système uniquement (Directeur, Administrateur… gardent les
# leurs). Idempotente, ligne à ligne, ordre des autres codes préservé.

from django.db import migrations

CODES = (
    'crm_export', 'crm_reassign', 'ventes_export', 'reporting_export',
    'sav_reassign', 'technicien_assign',
)
ROLES = frozenset({'Responsable'})


def aligner(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True, nom__in=ROLES).iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        manquants = [c for c in CODES if c not in avant]
        if not manquants:
            continue
        role.permissions = list(avant) + manquants
        role.save(update_fields=['permissions'])


def desaligner(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True, nom__in=ROLES).iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if not any(c in avant for c in CODES):
            continue
        role.permissions = [c for c in avant if c not in CODES]
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0008_asec10_users_gerer_alignement'),
    ]

    operations = [
        migrations.RunPython(aligner, desaligner),
    ]
