# CIQ614 (Groupe CIQ, 03/10/2026) — les seuils 82-21 de la société ne sont
# plus que des SURCHARGES : champs nullables, sans défaut ; la valeur de
# référence vient des textes (``core.reglementaire.regime_8221``).
#
# Migration de DONNÉES réversible (notée au DONE LOG) :
# * aller : une ligne égale à l'ANCIEN défaut (déclaration 11, ANRE 1 000)
#   passe à NULL (= seuil sourcé) ; une valeur différente (choix délibéré de la
#   société) est conservée telle quelle ;
# * retour : NULL reprend l'ancien défaut (11 / 1 000) AVANT que la colonne
#   redevienne NOT NULL.
from decimal import Decimal

from django.db import migrations, models

ANCIEN_DEFAUT_DECLARATION = Decimal('11')
ANCIEN_DEFAUT_ANRE = Decimal('1000')


def anciens_defauts_vers_null(apps, schema_editor):
    CompanyProfile = apps.get_model('parametres', 'CompanyProfile')
    CompanyProfile.objects.filter(
        seuil_regime_declaration_kwc=ANCIEN_DEFAUT_DECLARATION,
    ).update(seuil_regime_declaration_kwc=None)
    CompanyProfile.objects.filter(
        seuil_regime_anre_kwc=ANCIEN_DEFAUT_ANRE,
    ).update(seuil_regime_anre_kwc=None)


def null_vers_anciens_defauts(apps, schema_editor):
    CompanyProfile = apps.get_model('parametres', 'CompanyProfile')
    CompanyProfile.objects.filter(
        seuil_regime_declaration_kwc__isnull=True,
    ).update(seuil_regime_declaration_kwc=ANCIEN_DEFAUT_DECLARATION)
    CompanyProfile.objects.filter(
        seuil_regime_anre_kwc__isnull=True,
    ).update(seuil_regime_anre_kwc=ANCIEN_DEFAUT_ANRE)


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0117_ciq105_forfaits_ci'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companyprofile',
            name='seuil_regime_declaration_kwc',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AlterField(
            model_name='companyprofile',
            name='seuil_regime_anre_kwc',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.RunPython(
            anciens_defauts_vers_null, null_vers_anciens_defauts),
    ]
