# AGR107 (Groupe AGR, 02/10/2026) — réglages société du pompage, nullable et
# SANS défaut (zéro chiffre inventé). Migration additive et réversible.
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0110_cad176_relance_email_template_cle'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='agricole_part_debit_forage_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ]),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='agricole_marge_cable_descente_m',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=6, null=True,
                validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='agricole_salissure_supp_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ]),
        ),
    ]
