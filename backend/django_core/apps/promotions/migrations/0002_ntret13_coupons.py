# NTRET13 — Coupons à code unique (distinct de compta.CodePromotion) :
# CouponUnique + CouponUtilisation (journal, porte la contrainte structurelle
# 1×/client en mode unique_par_client).
import django.db.models.deletion
from django.db import migrations, models

import apps.promotions.models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0014_customuser_account_lockout"),
        ("crm", "0068_ntadm2_lead_entite"),
        ("promotions", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CouponUnique",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(
                    default=apps.promotions.models.default_coupon_code, max_length=32)),
                ("mode_limite", models.CharField(choices=[
                    ("unique_par_client", "1 utilisation par client"),
                    ("global", "N utilisations au total (global)"),
                ], default="global", max_length=20)),
                ("limite_usage", models.PositiveIntegerField(default=1)),
                ("date_expiration", models.DateField(blank=True, null=True)),
                ("actif", models.BooleanField(default=True)),
                ("utilise_le", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="coupons_uniques", to="authentication.company")),
                ("regle", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="coupons", to="promotions.reglexpromotion")),
                ("utilise_par", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="coupons_utilises_en_premier", to="crm.client")),
            ],
            options={
                "verbose_name": "Coupon à code unique",
                "verbose_name_plural": "Coupons à code unique",
                "unique_together": {("company", "code")},
            },
        ),
        migrations.CreateModel(
            name="CouponUtilisation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("utilise_le", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="utilisations_coupon", to="authentication.company")),
                ("coupon", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="utilisations", to="promotions.couponunique")),
                ("client", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="utilisations_coupon", to="crm.client")),
            ],
            options={
                "verbose_name": "Utilisation de coupon",
                "verbose_name_plural": "Utilisations de coupon",
                "ordering": ["-utilise_le"],
            },
        ),
        migrations.AddConstraint(
            model_name="couponutilisation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("client__isnull", False)),
                fields=("coupon", "client"),
                name="promotions_couponutilisation_unique_par_client",
            ),
        ),
    ]
