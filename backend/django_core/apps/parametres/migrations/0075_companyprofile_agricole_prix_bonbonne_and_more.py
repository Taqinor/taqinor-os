# Q4 (fondateur, 20/08/2026) — prix bonbonne butane 12 kg (terrain) + coût réel
# non subventionné : deux réglages société, même modèle/style que le
# pré-existant agricole_pump_hours. Additif, défauts = valeurs terrain
# mi-2026 (50 / 128 MAD) : comportement du moteur agricole inchangé tant que
# la société ne les édite pas.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0074_ntret32_seuil_alerte_ecart_caisse'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='agricole_prix_bonbonne',
            field=models.DecimalField(decimal_places=2, default=50, max_digits=8),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='agricole_cout_reel_bonbonne',
            field=models.DecimalField(decimal_places=2, default=128, max_digits=8),
        ),
    ]
