"""XACC21 — Contrôle du budget COMPTABLE à l'engagement (warning/blocage).

Additif : champ ``Budget.controle`` (défaut ``warning`` = comportement actuel
inchangé). Aucun modèle existant n'est autrement modifié.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0057_ventilation_analytique_regle_imputation'),
    ]

    operations = [
        migrations.AddField(
            model_name='budget',
            name='controle',
            field=models.CharField(choices=[('warning', 'Avertissement (non bloquant)'), ('bloquant', 'Bloquant (override responsable)')], default='warning', max_length=10, verbose_name="Mode de contrôle à l'engagement"),
        ),
    ]
