# XFSM19 — Rapprochement des encaissements terrain par technicien.
# Nouveaux modèles (pas de champ additif sur un modèle existant) : ne change
# rien au comportement actuel tant qu'aucune remise n'est créée.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("ventes", "0061_xpos7_retour_client"),
    ]

    operations = [
        migrations.CreateModel(
            name="RemiseEncaissement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("reference", models.CharField(
                    blank=True, default="", max_length=50)),
                ("date_collecte", models.DateField()),
                ("montant_declare", models.DecimalField(
                    decimal_places=2, max_digits=12)),
                ("statut", models.CharField(
                    choices=[
                        ("ouverte", "Ouverte"),
                        ("cloturee", "Clôturée"),
                        ("validee", "Validée"),
                    ], default="ouverte", max_length=15)),
                ("note", models.TextField(blank=True, default="")),
                ("fichier_pdf", models.CharField(
                    blank=True, max_length=500, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_cloture", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="remises_encaissement",
                    to="authentication.company")),
                ("technicien", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="remises_encaissement",
                    to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="remises_encaissement_creees",
                    to=settings.AUTH_USER_MODEL)),
                ("cloture_par", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="remises_encaissement_cloturees",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Remise d'encaissement terrain",
                "verbose_name_plural": "Remises d'encaissement terrain",
                "ordering": ["-date_collecte", "-id"],
            },
        ),
        migrations.CreateModel(
            name="LigneRemiseEncaissement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("paiement", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="lignes_remise_encaissement",
                    to="ventes.paiement")),
                ("remise", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lignes",
                    to="ventes.remiseencaissement")),
            ],
            options={
                "verbose_name": "Ligne de remise d'encaissement",
                "verbose_name_plural": "Lignes de remise d'encaissement",
            },
        ),
        migrations.AlterUniqueTogether(
            name="ligneremiseencaissement",
            unique_together={("remise", "paiement")},
        ),
    ]
