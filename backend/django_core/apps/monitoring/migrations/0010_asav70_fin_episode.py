# ASAV70 — fin d'un épisode de sous-performance : motif et note de clôture du
# drapeau (« données indisponibles », « retour à la normale »…). Additif et
# réversible : deux colonnes avec défaut vide, aucune donnée existante touchée.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0009_ciq645_source_import'),
    ]

    operations = [
        migrations.AddField(
            model_name='underperformanceflag',
            name='motif_cloture',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='underperformanceflag',
            name='note_cloture',
            field=models.TextField(blank=True, default=''),
        ),
    ]
