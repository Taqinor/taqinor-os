"""NTI18N9 — CompanyProfile.devise_tenant (devise d'affichage société, ISO 4217, défaut MAD)."""
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0135_reveil_j30_en_appel'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='devise_tenant',
            field=models.CharField(
                default='MAD', max_length=3,
                validators=[django.core.validators.RegexValidator(
                    '^[A-Z]{3}$',
                    'Code ISO 4217 sur 3 lettres majuscules (ex. MAD, XOF).')],
                verbose_name="Devise d'affichage",
                help_text="Code ISO 4217 de la devise d'affichage par défaut de la "
                          "société (tableaux de bord, listes, rapports). Défaut MAD. "
                          "N'affecte pas la devise propre à chaque document (FG52)."),
        ),
    ]
