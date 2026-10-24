"""AMOT100 (D-ACI-19=a) — facteur d'émission du réseau marocain (CompanyProfile).

ADDITIF : trois colonnes vides par défaut (valeur NULL, source '', date NULL) —
tant qu'elles le restent, aucun document C&I ne parle de CO₂. Réversible :
``python manage.py migrate parametres 0128``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0128_amot97_sensibilites_ci_seedees'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='facteur_co2_reseau_g_kwh',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=7, null=True,
                help_text='Vide = aucune mention CO₂ sur les documents C&I.',
                verbose_name="Facteur d'émission du réseau (gCO₂/kWh)"),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='facteur_co2_reseau_source',
            field=models.TextField(
                blank=True, default='',
                verbose_name="Source du facteur d'émission du réseau"),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='facteur_co2_reseau_date',
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Date du facteur d'émission du réseau"),
        ),
    ]
