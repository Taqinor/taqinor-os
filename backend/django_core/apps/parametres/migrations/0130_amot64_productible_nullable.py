"""AMOT64 (D-AMOT-3 = a) — ``CompanyProfile.productible_kwh_kwc`` nullable.

Avant : la valeur 1 600 servait de SENTINELLE (« non renseigné » ⇒ productible
PVGIS de la ville) ; une société qui SAISISSAIT 1 600 était ignorée. Désormais
NULL = PVGIS de la ville, et toute valeur saisie est respectée (1 600 compris).

Données : les lignes à exactement 1600 passent à NULL — elles lisaient déjà
le PVGIS de la ville, elles le lisent encore : AUCUN chiffre de devis ne bouge
à la migration (prouvé par ``apps.ventes.tests.test_dc2_company_tariff``).

Réversible : ``python manage.py migrate parametres 0129`` remet 1600 sur les
lignes NULL puis rend la colonne NOT NULL (défaut 1600).
"""
from decimal import Decimal

from django.db import migrations, models

SENTINELLE = Decimal('1600.0')


def sentinelle_vers_null(apps, schema_editor):
    CompanyProfile = apps.get_model('parametres', 'CompanyProfile')
    CompanyProfile.objects.filter(productible_kwh_kwc=SENTINELLE).update(
        productible_kwh_kwc=None)


def null_vers_sentinelle(apps, schema_editor):
    CompanyProfile = apps.get_model('parametres', 'CompanyProfile')
    CompanyProfile.objects.filter(productible_kwh_kwc__isnull=True).update(
        productible_kwh_kwc=SENTINELLE)


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0129_amot100_facteur_co2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companyprofile',
            name='productible_kwh_kwc',
            field=models.DecimalField(
                blank=True, decimal_places=1, default=None, max_digits=7,
                null=True),
        ),
        migrations.RunPython(sentinelle_vers_null, null_vers_sentinelle),
    ]
