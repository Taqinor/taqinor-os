# Generated for XFLT20 — Registre de remise clés / carte / badge / tag Jawaz.
# Crée ``RemiseAccessoire``. Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0044_approbation_or"),
    ]

    operations = [
        migrations.CreateModel(
            name="RemiseAccessoire",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_accessoire", models.CharField(
                    choices=[
                        ("cle", "Clé"), ("double_cle", "Double de clé"),
                        ("carte_carburant", "Carte carburant"),
                        ("tag_jawaz", "Tag Jawaz"), ("badge", "Badge"),
                    ], max_length=16, verbose_name="Type")),
                ("date_remise", models.DateField(verbose_name="Date de remise")),
                ("date_retour", models.DateField(
                    blank=True, null=True, verbose_name="Date de retour")),
                ("commentaire", models.TextField(
                    blank=True, verbose_name="Commentaire")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("actif_flotte", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_remises_accessoire",
                    to="flotte.actifflotte",
                    verbose_name="Actif (véhicule ou engin)")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_remises_accessoire",
                    to="authentication.company", verbose_name="Société")),
                ("conducteur", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_remises_accessoire",
                    to="flotte.conducteur", verbose_name="Détenteur")),
            ],
            options={
                "verbose_name": "Remise d'accessoire",
                "verbose_name_plural": "Remises d'accessoire",
                "ordering": ["-date_remise", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="remiseaccessoire",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_rem_co_actif_idx"),
        ),
        migrations.AddIndex(
            model_name="remiseaccessoire",
            index=models.Index(
                fields=["company", "conducteur"],
                name="flotte_rem_co_cond_idx"),
        ),
    ]
