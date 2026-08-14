# NTRET8 — Paramètres POS dédiés (onglet Paramètres → Point de vente) :
# ParametresPos (taux horaire main-d'œuvre comptoir) + BoutiquePos (boutiques
# actives, référence LECTURE SEULE de stock.EmplacementStock par FK — aucune
# migration côté apps/stock).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0014_customuser_account_lockout"),
        ("stock", "0085_ntadm2_produit_entite"),
        ("parametres", "0069_ntadm8_companyprofile_nb_sieges_max"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParametresPos",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("taux_horaire_comptoir", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    help_text="Taux horaire main-d'œuvre comptoir (MAD/heure).")),
                ("company", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="parametres_pos", to="authentication.company")),
            ],
            options={
                "verbose_name": "Paramètres POS",
                "verbose_name_plural": "Paramètres POS",
            },
        ),
        migrations.CreateModel(
            name="BoutiquePos",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("actif", models.BooleanField(default=True)),
                ("adresse", models.TextField(blank=True, default="")),
                ("horaires", models.CharField(blank=True, default="", max_length=255)),
                ("surface_m2", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    help_text="Surface de vente (m²) — alimente le KPI ventes/m² (NTRET16).")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="boutiques_pos", to="authentication.company")),
                ("emplacement", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="boutique_pos", to="stock.emplacementstock")),
            ],
            options={
                "verbose_name": "Boutique (point de vente)",
                "verbose_name_plural": "Boutiques (points de vente)",
                "ordering": ["emplacement__nom"],
            },
        ),
    ]
