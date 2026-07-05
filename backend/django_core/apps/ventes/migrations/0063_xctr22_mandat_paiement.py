# XCTR22 — Encaissement récurrent automatique des abonnements (tokenisation
# carte / mandat) + dunning carte. Nouveaux modèles uniquement : ne change
# rien au comportement actuel tant qu'aucun mandat n'est créé (key-gated,
# dépend de la disponibilité de la tokenisation CMI — DECISION fondateur).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("crm", "0001_initial"),
        ("ventes", "0062_xfsm19_remise_encaissement"),
    ]

    operations = [
        migrations.CreateModel(
            name="MandatPaiement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("provider", models.CharField(default="noop", max_length=40)),
                ("token", models.CharField(
                    blank=True, default="", max_length=200)),
                ("derniers_chiffres", models.CharField(
                    blank=True, default="", max_length=4)),
                ("expiration_mois", models.CharField(
                    blank=True, default="", max_length=7)),
                ("statut", models.CharField(
                    choices=[
                        ("actif", "Actif"),
                        ("expire", "Expiré"),
                        ("revoque", "Révoqué"),
                    ], default="actif", max_length=10)),
                ("consentement_horodate", models.DateTimeField(
                    blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("client", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="mandats_paiement", to="crm.client")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="mandats_paiement",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Mandat de paiement récurrent",
                "verbose_name_plural": "Mandats de paiement récurrent",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="TentativeDebitMandat",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("periode", models.CharField(max_length=20)),
                ("statut", models.CharField(
                    choices=[("reussi", "Réussi"), ("echec", "Échec")],
                    max_length=10)),
                ("motif_echec", models.CharField(
                    blank=True, default="", max_length=255)),
                ("date_tentative", models.DateTimeField(auto_now_add=True)),
                ("prochaine_retentative", models.DateField(
                    blank=True, null=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="tentatives_debit_mandat",
                    to="authentication.company")),
                ("mandat", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="tentatives", to="ventes.mandatpaiement")),
                ("paiement", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="tentatives_debit_mandat",
                    to="ventes.paiement")),
            ],
            options={
                "verbose_name": "Tentative de débit (mandat)",
                "verbose_name_plural": "Tentatives de débit (mandat)",
                "ordering": ["-date_tentative"],
            },
        ),
    ]
