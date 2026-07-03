# XRH20 — Promesse d'embauche / lettre d'offre PDF + e-sign interne.

import django.db.models.deletion
import apps.rh.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0056_gabarit_email_recrutement"),
    ]

    operations = [
        migrations.CreateModel(
            name="PromesseEmbauche",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("poste_propose", models.CharField(
                    blank=True, default="", max_length=200)),
                ("type_contrat", models.CharField(
                    choices=[
                        ("cdi", "CDI"), ("cdd", "CDD"),
                        ("anapec", "ANAPEC"), ("stage", "Stage"),
                        ("interim", "Intérim")],
                    default="cdi", max_length=10)),
                ("date_debut_proposee", models.DateField(
                    blank=True, null=True)),
                ("salaire_propose", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True)),
                ("statut", models.CharField(
                    choices=[
                        ("envoyee", "Envoyée"), ("signee", "Signée"),
                        ("expiree", "Expirée")],
                    default="envoyee", max_length=10)),
                ("token", models.CharField(
                    default=apps.rh.models._default_promesse_token,
                    editable=False, max_length=64, unique=True)),
                ("expires_at", models.DateTimeField(
                    default=apps.rh.models._default_promesse_expiry)),
                ("signataire_nom", models.CharField(
                    blank=True, default="", max_length=255)),
                ("date_signature", models.DateTimeField(
                    blank=True, null=True)),
                ("ip_adresse", models.CharField(
                    blank=True, default="", max_length=45)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("candidature", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="promesse_embauche", to="rh.candidature")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_promesses_embauche",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Promesse d'embauche",
                "verbose_name_plural": "Promesses d'embauche",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="promesseembauche",
            index=models.Index(
                fields=["token"], name="rh_promesse_token_idx"),
        ),
    ]
