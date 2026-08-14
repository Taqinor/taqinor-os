# NTRET2 — Rapport X (lecture) / Rapport Z (clôture définitive) formels.
# `numero_rapport_z` : numérotation séquentielle anti-collision du rapport Z
# officiel (jamais count()+1), posée une seule fois par session. Additif :
# NULL = comportement historique inchangé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0003_ntret1_uuid_client"),
    ]

    operations = [
        migrations.AddField(
            model_name="sessioncaisse",
            name="numero_rapport_z",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddConstraint(
            model_name="sessioncaisse",
            constraint=models.UniqueConstraint(
                condition=models.Q(("numero_rapport_z__isnull", False)),
                fields=("company", "numero_rapport_z"),
                name="pos_sessioncaisse_unique_numero_rapport_z_per_company",
            ),
        ),
    ]
