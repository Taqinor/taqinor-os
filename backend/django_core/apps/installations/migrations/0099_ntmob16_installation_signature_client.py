"""NTMOB16 — signature client tracée sur le bon de livraison chantier.

Additif pur (mêmes champs que FG69 Intervention.signature_client) : aucune
migration existante modifiée."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0098_ntmob11_photochecklistmeta'),
    ]

    operations = [
        migrations.AddField(
            model_name='installation',
            name='signature_client',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='installation',
            name='signataire_nom',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='installation',
            name='signe_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
