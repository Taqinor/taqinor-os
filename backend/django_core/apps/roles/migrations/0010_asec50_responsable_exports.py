# ASEC50 / D-ASEC-50 (décision fondateur du 24/10/2026, option a) — trois
# derniers codes de la grille APPLIQUÉS côté serveur (``apps.roles.
# permissions.DroitDeLaGrille``) : ``sav_export`` (insights SAV fcr /
# performance-agent ``?export=xlsx``), ``installation_export`` (liste des
# interventions ``?export=xlsx``) et ``ventes_supprimer`` (suppression d'une
# facture brouillon). Le rôle système légacy « Responsable » faisait déjà ces
# gestes sans porter les codes : il les reçoit pour garder cet accès (même
# patron que 0009_asec50_responsable_alignement).
#
# Aller : ajout en fin de liste au seul rôle SYSTÈME « Responsable », de chaque
# société. Un rôle personnalisé ne reçoit rien. Retour : retrait des mêmes codes
# de ce même rôle système uniquement (Directeur, Administrateur… gardent les
# leurs). Idempotente, ligne à ligne, ordre des autres codes préservé.

from django.db import migrations

CODES = ('sav_export', 'installation_export', 'ventes_supprimer')
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
        ('roles', '0009_asec50_responsable_alignement'),
    ]

    operations = [
        migrations.RunPython(aligner, desaligner),
    ]
