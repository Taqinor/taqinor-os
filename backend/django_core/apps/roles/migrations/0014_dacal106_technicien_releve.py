# D-ACAL-106 (fondateur, 25/11/2026) — « Technicien too » : le rôle qui monte
# sur le toit ouvre les visites qui lui sont assignées, lit le calepinage et
# fait le relevé au téléphone ; il ne voit toujours ni devis ni prix.
#
# Patron ``0008_asec10_users_gerer_alignement`` : AJOUT en fin de liste aux
# seuls rôles SYSTÈME nommés ci-dessous, code par code (un code déjà porté
# n'est pas répété, l'ordre des autres codes est préservé). Un rôle
# personnalisé ne reçoit rien ; aucun code n'est retiré à personne.
# ``init_roles`` (relancé à chaque déploiement) réaligne de toute façon les
# rôles système sur ``permissions_registre.py`` : cette migration rend le
# droit effectif dès ``migrate``, même là où ``init_roles`` ne tourne pas.
#
# Retour : retrait des mêmes codes, des mêmes rôles système seulement.
# ``calepinage_releve`` n'existait pas avant (personne ne le portait) ; pour les
# trois autres, un code AJOUTÉ À LA MAIN avant cette migration à l'un de ces
# deux rôles système serait lui aussi retiré au retour — limite assumée,
# identique à 0008.

from django.db import migrations

AJOUTS = {
    'Technicien': ('visites_voir', 'visites_modifier',
                   'calepinage_voir', 'calepinage_releve'),
    'Technicien responsable': ('calepinage_voir', 'calepinage_releve'),
}


def ajouter(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True,
                                    nom__in=AJOUTS).iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        manquants = [c for c in AJOUTS[role.nom] if c not in avant]
        if not manquants:
            continue
        role.permissions = list(avant) + manquants
        role.save(update_fields=['permissions'])


def retirer(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True,
                                    nom__in=AJOUTS).iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        codes = AJOUTS[role.nom]
        if not any(c in avant for c in codes):
            continue
        role.permissions = [c for c in avant if c not in codes]
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0013_apfs40_codes_administration'),
    ]

    operations = [
        migrations.RunPython(ajouter, retirer),
    ]
