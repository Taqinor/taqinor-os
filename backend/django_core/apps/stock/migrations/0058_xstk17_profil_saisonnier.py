# XSTK17 — profils saisonniers de seuils min/max/cible (saison pompage).
# Additif : nouveau modèle ProfilSaisonnier, lu en PRIORITÉ par
# produits_a_reapprovisionner (FG54) pendant sa fenêtre ; hors saison ou sans
# profil actif, comportement historique inchangé (repli sur seuil_alerte).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0057_xstk10_motifs_rebut"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfilSaisonnier",
            fields=[
                ("id", models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(
                    blank=True, max_length=100, null=True)),
                ("mois_debut", models.PositiveSmallIntegerField()),
                ("mois_fin", models.PositiveSmallIntegerField()),
                ("seuil_min", models.PositiveIntegerField(
                    blank=True, null=True)),
                ("seuil_max", models.PositiveIntegerField(
                    blank=True, null=True)),
                ("quantite_cible", models.PositiveIntegerField(
                    blank=True, null=True)),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("categorie", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profils_saisonniers", to="stock.categorie")),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profils_saisonniers",
                    to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="profils_saisonniers_crees",
                    to=settings.AUTH_USER_MODEL)),
                ("produit", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profils_saisonniers", to="stock.produit")),
            ],
            options={
                "verbose_name": "Profil saisonnier",
                "verbose_name_plural": "Profils saisonniers",
                "ordering": ["mois_debut"],
            },
        ),
        migrations.AddConstraint(
            model_name="profilsaisonnier",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("categorie__isnull", True), ("produit__isnull", False),
                ) | models.Q(
                    ("categorie__isnull", False), ("produit__isnull", True),
                ),
                name="stock_profilsaisonnier_produit_xor_categorie",
            ),
        ),
    ]
