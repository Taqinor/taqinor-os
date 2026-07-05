"""XMKT6 — Segments dynamiques enregistrés et réutilisables.

Additif : ``SegmentMarketing`` (règles JSON validées, ré-évalué à chaque
usage). Ne touche à aucun modèle existant.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('compta', '0070_listediffusion_abonnementliste_campagne_listes'),
    ]

    operations = [
        migrations.CreateModel(
            name='SegmentMarketing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom du segment')),
                ('regles', models.JSONField(blank=True, default=dict, verbose_name='Règles (JSON)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='segments_marketing', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Segment marketing',
                'verbose_name_plural': 'Segments marketing',
                'ordering': ['nom'],
            },
        ),
    ]
