"""AUD326 — « Clôturé » devient un état gelé : drapeau `cloture_verrouillee`.

Additif pur (un `BooleanField(default=False)` sur `Installation`) : aucun
champ existant modifié, aucune donnée touchée. Les chantiers déjà clôturés
partent à `False` et se verrouillent au prochain passage par CLOTURE — le
comportement historique reste donc byte-identique tant que rien ne les
re-traverse.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0102_ntp2p2_approbation_achat'),
    ]

    operations = [
        migrations.AddField(
            model_name='installation',
            name='cloture_verrouillee',
            field=models.BooleanField(default=False),
        ),
    ]
