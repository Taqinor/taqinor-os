# D-ACAL-117 (fondateur, 25/11/2026, « Also Commercial responsable ») — le rôle SYSTÈME
# « Commercial responsable » gagne ``calepinage_approuver`` (changer les réglages de la
# société, appliquer / retirer le profil de départ, décider l'approbation, déroger à un
# verdict électrique). Personne d'autre ne gagne ni ne perd rien.
#
# Patron ``0014_dacal106_technicien_releve`` : AJOUT en fin de liste au seul rôle SYSTÈME
# nommé, un code déjà porté n'est pas répété, un rôle personnalisé ne reçoit rien.
# ``init_roles`` (relancé à chaque déploiement) réaligne de toute façon les rôles système sur
# ``permissions_registre.py`` ; cette migration rend le droit effectif dès ``migrate``.
#
# Retour : retrait du même code, du même rôle système seulement (limite assumée, identique à
# 0008 / 0014 : un code ajouté à la main avant cette migration serait aussi retiré).

from django.db import migrations

ROLE = 'Commercial responsable'
CODE = 'calepinage_approuver'


def ajouter(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True, nom=ROLE).iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE in avant:
            continue
        role.permissions = list(avant) + [CODE]
        role.save(update_fields=['permissions'])


def retirer(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True, nom=ROLE).iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE not in avant:
            continue
        role.permissions = [c for c in avant if c != CODE]
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0014_dacal106_technicien_releve'),
    ]

    operations = [
        migrations.RunPython(ajouter, retirer),
    ]
