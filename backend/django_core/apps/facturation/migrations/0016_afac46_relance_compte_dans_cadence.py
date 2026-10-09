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


BATCH_SIZE = 1000


def neutraliser_resolues(apps, schema_editor):
    # YOPSB4 — mise à jour par lots bornés (jamais un UPDATE global qui
    # verrouille la table des relances le temps de tout réécrire).
    RelanceLog = apps.get_model('facturation', 'RelanceLog')
    a_traiter = RelanceLog.objects.filter(
        note=NOTE_RESOLUE, compte_dans_cadence=True).order_by('pk')
    while True:
        batch_ids = list(a_traiter.values_list('pk', flat=True)[:BATCH_SIZE])
        if not batch_ids:
            break
        RelanceLog.objects.filter(pk__in=batch_ids).update(
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
