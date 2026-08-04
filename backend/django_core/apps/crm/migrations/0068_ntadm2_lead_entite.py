"""NTADM2 — champ `entite` OPTIONNEL sur crm.Lead.

Additif pur : colonne nullable, aucun backfill. NULL = « non affecté » —
comportement identique à aujourd'hui pour toutes les lignes existantes.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entites', '0001_initial'),
        ('crm', '0067_lb48_savedview'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='entite',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='crm_leads',
                to='entites.entite',
                verbose_name='Entité'),
        ),
    ]
