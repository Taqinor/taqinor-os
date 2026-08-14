# NTRET1 — mode offline caisse : `uuid_client` généré côté navigateur pour
# une vente créée sans réseau, avec dédup serveur (contrainte unique par
# société) au rejeu. Additif : NULL = comportement historique inchangé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0002_odx17_facture_facturation_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="ventecomptoir",
            name="uuid_client",
            field=models.CharField(
                blank=True, max_length=64, null=True,
                help_text="UUID client (mode offline, NTRET1) — dédup serveur au rejeu."),
        ),
        migrations.AddConstraint(
            model_name="ventecomptoir",
            constraint=models.UniqueConstraint(
                condition=models.Q(("uuid_client__isnull", False)),
                fields=("company", "uuid_client"),
                name="pos_ventecomptoir_unique_uuid_client_per_company",
            ),
        ),
    ]
