# CIQ105 (Groupe CIQ, D-CIQ-12) — réglages société C&I SANS défaut : forfaits
# des prestations C&I (objet vide) et bande interne de contrôle du prix au kWc
# (NULL). Additive et réversible (RemoveField sans perte : colonnes neuves).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0116_ciq415_responsable_leads_pro'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='forfaits_ci',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='bande_prix_kwc_ci',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
