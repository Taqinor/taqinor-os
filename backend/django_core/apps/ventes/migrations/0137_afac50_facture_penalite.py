"""AFAC50 (C-AFAC-040 a) — ``FacturePenalite`` : liaison durable (facture
d'origine, niveau) → facture de pénalités, unique par (facture, niveau).

ADDITIF : une table neuve, aucune donnée existante touchée. Réversible :
revenir à ventes 0136.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('facturation', '0014_atot6_avoir_ventilation_tva'),
        ('ventes', '0136_afac34_abandon_creance'),
    ]

    operations = [
        migrations.CreateModel(
            name='FacturePenalite',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('niveau', models.PositiveIntegerField()),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='factures_penalite',
                    to='authentication.company')),
                ('facture_origine', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='liaisons_penalite',
                    to='facturation.facture')),
                ('facture_penalite', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='liaisons_penalite_source',
                    to='facturation.facture')),
            ],
            options={
                'verbose_name': 'Facture de pénalités',
                'verbose_name_plural': 'Factures de pénalités',
                'constraints': [models.UniqueConstraint(
                    fields=('facture_origine', 'niveau'),
                    name='uniq_facture_penalite_par_niveau')],
            },
        ),
    ]
