# XPUR22 — Portail fournisseur lecture seule + confirmation de date
# d'arrivée. Nouveau modèle additif PortailFournisseurToken (jeton public
# révocable/expirant, généré depuis la fiche fournisseur, pattern miroir de
# ventes.ShareLink / sav.Ticket.share_token).
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import apps.stock.models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0049_xpur18_revision_bcf"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PortailFournisseurToken",
            fields=[
                ("id", models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("token", models.CharField(
                    default=apps.stock.models._default_portail_token,
                    editable=False, max_length=64, unique=True)),
                ("expires_at", models.DateTimeField(
                    default=apps.stock.models._default_portail_expiry)),
                ("revoked", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(
                    blank=True, null=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="portail_fournisseur_tokens",
                    to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="portail_fournisseur_tokens_crees",
                    to=settings.AUTH_USER_MODEL)),
                ("fournisseur", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="portail_tokens", to="stock.fournisseur")),
            ],
            options={
                "verbose_name": "Jeton portail fournisseur",
                "verbose_name_plural": "Jetons portail fournisseur",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["token"]),
                ],
            },
        ),
    ]
