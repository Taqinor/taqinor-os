"""AFAC46 — ``RelanceLog.compte_dans_cadence`` : une relance neutralisée au
solde de la facture ne compte plus dans la cadence (au lieu de réécrire la note
des seules relances automatiques).

ADDITIF : un booléen défaut True. Données : les journaux dont la note est la
note « résolue » historique passent à False. Réversible : revenir à
facturation 0015 (le reverse des données est un no-op, la colonne disparaît).
"""
from django.db import migrations, models

NOTE_RESOLUE = (
    'Relance automatique programmée (email). [résolue — facture soldée]')


def neutraliser_resolues(apps, schema_editor):
    RelanceLog = apps.get_model('facturation', 'RelanceLog')
    RelanceLog.objects.filter(note=NOTE_RESOLUE).update(
        compte_dans_cadence=False)


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0015_afac32_avoir_note_debit'),
    ]

    operations = [
        migrations.AddField(
            model_name='relancelog',
            name='compte_dans_cadence',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(neutraliser_resolues, migrations.RunPython.noop),
    ]
