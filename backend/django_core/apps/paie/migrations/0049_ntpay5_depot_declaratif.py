# NTPAY5 — Registre des dépôts déclaratifs & accusés (preuve de conformité).
#
# `EcheanceDeclarative` (XPAI6) suit le CALENDRIER des déclarations dues ; rien
# ne conservait la PREUVE du dépôt (référence, récépissé, montant déclaré,
# rejet). `DepotDeclaratif` rattache ce dossier de preuve à l'échéance.
#
# Migration purement ADDITIVE : une nouvelle table, aucun champ existant touché.
from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0048_ntpay2_schema_comptable_paie'),
    ]

    operations = [
        migrations.CreateModel(
            name='DepotDeclaratif',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type_declaration', models.CharField(
                    choices=[
                        ('bds', 'BDS (CNSS)'),
                        ('ir_mensuel', 'IR mensuel'),
                        ('etat_9421', 'État 9421 (annuel)'),
                        ('cimr', 'CIMR'),
                    ],
                    max_length=12, verbose_name='Type')),
                ('annee', models.PositiveIntegerField(verbose_name='Année')),
                ('mois', models.PositiveSmallIntegerField(
                    blank=True, null=True, verbose_name='Mois')),
                ('reference_depot', models.CharField(
                    blank=True, default='', max_length=80,
                    verbose_name='Référence de dépôt')),
                ('date_depot', models.DateField(
                    verbose_name='Date de dépôt')),
                ('fichier_key', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name="Clé de l'accusé (MinIO)")),
                ('montant_declare', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=16,
                    verbose_name='Montant déclaré')),
                ('statut', models.CharField(
                    choices=[
                        ('depose', 'Déposé'),
                        ('accepte', 'Accepté'),
                        ('rejete', 'Rejeté'),
                    ],
                    default='depose', max_length=10, verbose_name='Statut')),
                ('motif_rejet', models.CharField(
                    blank=True, default='', max_length=300,
                    verbose_name='Motif du rejet')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='paie_depots_declaratifs',
                    to='authentication.company', verbose_name='Société')),
                ('echeance', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='depots', to='paie.echeancedeclarative',
                    verbose_name='Échéance déclarative')),
            ],
            options={
                'verbose_name': 'Dépôt déclaratif',
                'verbose_name_plural': 'Dépôts déclaratifs',
                'ordering': ['-date_depot', '-id'],
            },
        ),
    ]
