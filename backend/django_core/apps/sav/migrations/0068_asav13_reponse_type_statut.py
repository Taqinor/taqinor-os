"""ASAV13 — ``ReponseType.nouveau_statut`` limité aux choix de ``Ticket.Statut``.

Données : toute valeur hors choix (ex. « bidon », saisie avant la validation)
est remise à vide (= la macro ne change plus le statut). Réversible : le
retour arrière ne restaure rien (no-op), la valeur invalide n'avait aucun
usage légitime.
"""
from django.db import migrations, models

BATCH_SIZE = 500
STATUTS_VALIDES = ('nouveau', 'planifie', 'en_cours', 'resolu', 'cloture')


def vider_statuts_invalides(apps, schema_editor):
    ReponseType = apps.get_model('sav', 'ReponseType')
    ids = list(ReponseType.objects
               .exclude(nouveau_statut='')
               .exclude(nouveau_statut__in=STATUTS_VALIDES)
               .values_list('pk', flat=True))
    # Mise à jour par lots (BATCH_SIZE) : jamais un UPDATE global verrouillant.
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        ReponseType.objects.filter(pk__in=batch).update(nouveau_statut='')


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0067_ciq642_ticket_arret'),
    ]

    operations = [
        migrations.RunPython(
            vider_statuts_invalides, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='reponsetype',
            name='nouveau_statut',
            field=models.CharField(
                blank=True,
                choices=[
                    ('nouveau', 'Nouveau'),
                    ('planifie', 'Planifié'),
                    ('en_cours', 'En cours'),
                    ('resolu', 'Résolu'),
                    ('cloture', 'Clôturé'),
                ],
                default='',
                help_text="Statut optionnel appliqué au ticket à l'insertion.",
                max_length=12),
        ),
    ]
