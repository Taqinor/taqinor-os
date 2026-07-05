# XMKT27 - constructeur d'enquetes avec logique conditionnelle : Enquete
# (questions JSON typees, lien public tokenise) + ReponseEnquete (soumission,
# contact_ref opaque). Additif, nouvelles tables.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0087_xmkt23_approbation_envoi_campagne"),
    ]

    operations = [
        migrations.CreateModel(
            name="Enquete",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("titre", models.CharField(max_length=200, verbose_name="Titre")),
                ("questions", models.JSONField(
                    blank=True, default=list, verbose_name="Questions (JSON)")),
                ("token", models.CharField(
                    max_length=64, unique=True, verbose_name="Jeton public")),
                ("actif", models.BooleanField(default=True, verbose_name="Active")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créée le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="enquetes", to="authentication.company",
                    verbose_name="Société")),
            ],
            options={
                "verbose_name": "Enquête",
                "verbose_name_plural": "Enquêtes",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.CreateModel(
            name="ReponseEnquete",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("contact_ref", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Référence contact (lead/client, opaque)")),
                ("reponses", models.JSONField(
                    blank=True, default=dict, verbose_name="Réponses (JSON)")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Soumise le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="reponses_enquete",
                    to="authentication.company", verbose_name="Société")),
                ("enquete", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="reponses", to="compta.enquete",
                    verbose_name="Enquête")),
            ],
            options={
                "verbose_name": "Réponse à une enquête",
                "verbose_name_plural": "Réponses à une enquête",
                "ordering": ["-date_creation"],
            },
        ),
    ]
