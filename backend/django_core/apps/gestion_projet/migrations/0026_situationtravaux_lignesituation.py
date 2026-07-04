# Generated for XPRJ4 -- Situations de travaux (decomptes progressifs BTP).

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0025_timesheet_facture_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='SituationTravaux',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('numero', models.PositiveIntegerField(
                    verbose_name='N° de situation')),
                ('periode', models.DateField(
                    verbose_name='Période (1er jour du mois couvert)')),
                ('statut', models.CharField(
                    choices=[
                        ('brouillon', 'Brouillon'),
                        ('validee', 'Validée'),
                        ('facturee', 'Facturée'),
                    ],
                    default='brouillon', max_length=10, verbose_name='Statut')),
                ('retenue_garantie_pct', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True,
                    verbose_name='Retenue de garantie (%)')),
                ('contrat_id', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='ID du contrat (RG)')),
                ('facture_id', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name="ID de la facture d'acompte")),
                ('date_validation', models.DateTimeField(
                    blank=True, null=True, verbose_name='Date de validation')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gestion_projet_situations',
                    to='authentication.company', verbose_name='Société')),
                ('projet', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='situations', to='gestion_projet.projet',
                    verbose_name='Projet')),
            ],
            options={
                'verbose_name': 'Situation de travaux',
                'verbose_name_plural': 'Situations de travaux',
                'ordering': ['projet', 'numero'],
            },
        ),
        migrations.AddIndex(
            model_name='situationtravaux',
            index=models.Index(
                fields=['projet', 'numero'], name='gp_situation_proj_num_idx'),
        ),
        migrations.AddConstraint(
            model_name='situationtravaux',
            constraint=models.UniqueConstraint(
                fields=('projet', 'numero'),
                name='gp_situation_projet_numero_uniq'),
        ),
        migrations.CreateModel(
            name='LigneSituation',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('libelle', models.CharField(
                    max_length=200,
                    verbose_name='Libellé (lot / ligne de budget)')),
                ('montant_marche_ht', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Montant marché HT')),
                ('avancement_cumule_pct', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=5,
                    verbose_name='Avancement cumulé (%)')),
                ('montant_cumule_anterieur', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Montant cumulé antérieur')),
                ('montant_periode', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Montant de la période')),
                ('montant_cumule', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Montant cumulé')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gestion_projet_lignes_situation',
                    to='authentication.company', verbose_name='Société')),
                ('situation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lignes', to='gestion_projet.situationtravaux',
                    verbose_name='Situation')),
            ],
            options={
                'verbose_name': 'Ligne de situation',
                'verbose_name_plural': 'Lignes de situation',
                'ordering': ['situation', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='lignesituation',
            index=models.Index(
                fields=['situation'], name='gp_lignesit_situation_idx'),
        ),
    ]
