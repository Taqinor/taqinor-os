# AOF5 + AOF12 — le PROJET d'appel d'offres au complet, en une seule migration
# additive (le groupe AOF impose des migrations groupées : chaque migration
# nouvelle force un cache-MISS du gate CI).
#
#   * AOF5  — ``reference_acheteur`` : la référence du marché CÔTÉ ACHETEUR,
#     strictement distincte de NOTRE référence générée ``AO-YYYYMM-0001``.
#   * AOF12 — maître d'ouvrage vs acheteur, soumissionnaire/groupement, site
#     (adresse + point GPS), mode de passation, référence CPS, dates
#     d'ouverture des plis et de validité (75 j), délai d'exécution, nombre
#     d'exemplaires, engagement global en modules, montants d'offre HT/TTC.
#
# AUCUN champ de coût, de marge ni de bénéfice : l'économie de l'AO vit dans
# des tables SÉPARÉES derrière ``ao_rentabilite_voir``. Purement additive, aucun
# ``AlterModelTable`` (``db_table='compta_appeloffre'`` inchangée).

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0002_tenantmodel'),
    ]

    operations = [
        migrations.AddField(
            model_name='appeloffre',
            name='date_ouverture_plis',
            field=models.DateField(blank=True, null=True, verbose_name="Date d'ouverture des plis"),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='delai_execution_jours',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Délai d'exécution (jours)"),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='engagement_modules',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Engagement global (modules)'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='groupement',
            field=models.BooleanField(default=False, verbose_name='Dépôt en groupement'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='groupement_membres',
            field=models.TextField(blank=True, default='', verbose_name='Membres du groupement (un par ligne)'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='maitre_ouvrage',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name="Maître d'ouvrage"),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='mode_passation',
            field=models.CharField(choices=[('appel_ouvert', "Appel d'offres ouvert"), ('appel_restreint', "Appel d'offres restreint"), ('concours', 'Concours'), ('negocie', 'Marché négocié'), ('consultation', 'Consultation / bon de commande'), ('autre', 'Autre')], default='appel_ouvert', max_length=20, verbose_name='Mode de passation'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='montant_offre_ht',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=16, verbose_name="Montant de l'offre HT (MAD)"),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='montant_offre_ttc',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=16, verbose_name="Montant de l'offre TTC (MAD)"),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='nombre_exemplaires',
            field=models.PositiveSmallIntegerField(default=2, verbose_name="Nombre d'exemplaires à remettre"),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='reference_acheteur',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Référence du marché (acheteur)'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='reference_cps',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Référence du CPS'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='site_adresse',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Adresse du site'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='site_gps_lat',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)], verbose_name='Latitude du site'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='site_gps_lng',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)], verbose_name='Longitude du site'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='soumissionnaire',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Soumissionnaire (raison sociale déposante)'),
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='validite_offre_jours',
            field=models.PositiveIntegerField(default=75, verbose_name="Validité de l'offre (jours)"),
        ),
    ]
