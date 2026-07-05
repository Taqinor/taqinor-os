# XMKT29 - ponts QR pour supports offline : LienTrackee.campagne devient
# nullable (un lien tracke peut venir d'un SupportOffline, pas seulement du
# corps d'une campagne) + nouveau modele SupportOffline. Additif/retro-
# compatible : campagne reste obligatoire pour les usages XMKT9 existants.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0089_xmkt28_evenement_marketing"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lientrackee",
            name="campagne",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="liens_trackes", to="compta.campagne"),
        ),
        migrations.CreateModel(
            name="SupportOffline",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(
                    max_length=200,
                    verbose_name="Nom (ex. « Flyer SIAM 2026 »)")),
                ("url_cible", models.URLField(
                    max_length=1000, verbose_name="URL cible")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="supports_offline",
                    to="authentication.company", verbose_name="Société")),
                ("lien_tracke", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="supports_offline", to="compta.lientrackee",
                    verbose_name="Lien tracké (QR)")),
            ],
            options={
                "verbose_name": "Support offline",
                "verbose_name_plural": "Supports offline",
                "ordering": ["-date_creation"],
            },
        ),
    ]
