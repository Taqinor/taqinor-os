# NTRET12 — Moteur de promotions panier (ReglexPromotion) : nouvelle app,
# nouvelle table. company-scopée (TenantModel) ; categorie/produit référencent
# apps.stock par FK (lecture seule — aucune migration côté apps/stock).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0014_customuser_account_lockout"),
        ("stock", "0085_ntadm2_produit_entite"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReglexPromotion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("nom", models.CharField(max_length=150)),
                ("type_regle", models.CharField(choices=[
                    ("remise_pourcentage_produit", "Remise % produit/catégorie"),
                    ("remise_montant_panier", "Remise montant fixe panier"),
                    ("n_pour_m", "N pour M (ex. 3 pour 2)"),
                    ("plage_horaire", "Plage horaire (happy hour)"),
                ], max_length=30)),
                ("actif", models.BooleanField(default=True)),
                ("priorite", models.PositiveSmallIntegerField(default=100)),
                ("cumulable", models.BooleanField(default=False, help_text=(
                    "Peut se combiner avec les autres règles actives (sinon, "
                    "seule la plus prioritaire des règles non cumulables "
                    "applicables est retenue)."))),
                ("montant_min_panier", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    help_text="Montant minimum du panier (TTC) pour que la "
                              "règle s'applique. Vide = aucun minimum.")),
                ("remise_pct", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True,
                    help_text="Pourcentage de remise (remise_pourcentage_produit "
                              "/ plage_horaire).")),
                ("remise_montant", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    help_text="Montant fixe de remise (remise_montant_panier).")),
                ("n_achete", models.PositiveSmallIntegerField(
                    blank=True, null=True, help_text="N (n_pour_m) — ex. 3.")),
                ("m_paye", models.PositiveSmallIntegerField(
                    blank=True, null=True, help_text="M (n_pour_m) — ex. 2.")),
                ("heure_debut", models.TimeField(
                    blank=True, null=True,
                    help_text="Début de la plage horaire (happy hour).")),
                ("heure_fin", models.TimeField(
                    blank=True, null=True,
                    help_text="Fin de la plage horaire (happy hour).")),
                ("jours_semaine", models.JSONField(blank=True, default=list, null=True)),
                ("date_debut", models.DateField(blank=True, null=True)),
                ("date_fin", models.DateField(blank=True, null=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="regles_promotion", to="authentication.company")),
                ("categorie", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="regles_promotion", to="stock.categorie")),
                ("produit", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="regles_promotion", to="stock.produit")),
            ],
            options={
                "verbose_name": "Règle de promotion",
                "verbose_name_plural": "Règles de promotion",
                "ordering": ["priorite", "nom"],
            },
        ),
    ]
