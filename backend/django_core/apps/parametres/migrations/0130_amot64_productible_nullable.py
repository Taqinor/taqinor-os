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
#: L'ancienne sentinelle était une BANDE (``abs(v − 1600) ≤ 0,5`` ⇒ PVGIS de
#: la ville, ``productible._HISTORICAL_DEFAULT``) : toute la bande passe à NULL,
#: sinon une société à 1600,3 basculerait de PVGIS à 1600,3 sans rien saisir.
BANDE_MIN, BANDE_MAX = Decimal('1599.5'), Decimal('1600.5')


LOT = 500


def _par_lots(qs, valeur):
    """``update`` par lots de :data:`LOT` clés (jamais un update global)."""
    lot = []
    for pk in qs.values_list('pk', flat=True).iterator(chunk_size=LOT):
        lot.append(pk)
        if len(lot) >= LOT:
            qs.model.objects.filter(pk__in=lot).update(
                productible_kwh_kwc=valeur)
            lot = []
    if lot:
        qs.model.objects.filter(pk__in=lot).update(productible_kwh_kwc=valeur)


def sentinelle_vers_null(apps, schema_editor):
    CompanyProfile = apps.get_model('parametres', 'CompanyProfile')
    _par_lots(CompanyProfile.objects.filter(
        productible_kwh_kwc__gte=BANDE_MIN,
        productible_kwh_kwc__lte=BANDE_MAX), None)


def null_vers_sentinelle(apps, schema_editor):
    CompanyProfile = apps.get_model('parametres', 'CompanyProfile')
    _par_lots(CompanyProfile.objects.filter(productible_kwh_kwc__isnull=True),
              SENTINELLE)


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
