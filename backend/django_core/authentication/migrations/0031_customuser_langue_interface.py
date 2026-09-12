"""NTI18N3 — langue d'interface persistée par utilisateur (pas seulement
`localStorage`), pour qu'il la retrouve en se connectant d'un autre poste.

Additive : défaut 'fr', tout compte existant garde le comportement N93
actuel (FR par défaut) sans modification.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='langue_interface',
            field=models.CharField(
                choices=[('fr', 'Français'), ('en', 'English'), ('ar', 'العربية')],
                default='fr', max_length=2,
                verbose_name="Langue d'interface"),
        ),
    ]
