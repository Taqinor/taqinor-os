"""ADVS4 (D-ADVS-2) — table des preuves de signature remplacées.

ADDITIVE ONLY : crée la seule table ``ventes_devissignaturearchivee``. Aucune
table ni colonne existante n'est touchée, aucune donnée déplacée.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0149_regles_calcul_niveau_10'),
    ]

    operations = [
        migrations.CreateModel(
            name='DevisSignatureArchivee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('preuve', models.JSONField()),
                ('archivee_le', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('devis', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='signatures_archivees',
                    to='ventes.devis')),
            ],
            options={
                'verbose_name': 'Signature archivée',
                'verbose_name_plural': 'Signatures archivées',
                'ordering': ['-archivee_le'],
            },
        ),
    ]
