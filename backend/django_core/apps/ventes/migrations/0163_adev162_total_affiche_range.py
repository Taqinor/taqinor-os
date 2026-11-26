"""ADEV162 — ``Devis.total_affiche_range`` + ``Devis.total_affiche_empreinte`` :
le total affiché rangé (cache de ``display_totals``) et l'empreinte de ce dont
il a été calculé, pour l'en-tête de la liste des devis. Ajout nullable,
réversible ; aucune donnée existante touchée (la synthèse recalcule tant que
rien n'est rangé)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0162_adev143_pointeur_conception'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='total_affiche_range',
            field=models.DecimalField(blank=True, decimal_places=2, editable=False, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='devis',
            name='total_affiche_empreinte',
            field=models.CharField(blank=True, default='', editable=False, max_length=80),
        ),
    ]
