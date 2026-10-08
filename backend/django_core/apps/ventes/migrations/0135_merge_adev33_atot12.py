# Fusion de deux branches de migration ventes nées en parallèle
# (vague 2 « work on all plans » PC 2 et la session du portable).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0133_adev33_remise_approuvee_pct'),
        ('ventes', '0134_atot12_remise_reference_unique'),
    ]

    operations = []
