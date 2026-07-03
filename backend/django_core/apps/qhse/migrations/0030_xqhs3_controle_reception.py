# Generated for XQHS3 — Contrôle qualité à la réception fournisseur +
# quarantaine.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("stock", "0028_dc34_fournisseur_type_soustraitantprofile"),
        ("qhse", "0029_xqhs2_disposition_derogation"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanControleReception",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=255, verbose_name="Nom")),
                ("taux_echantillonnage", models.PositiveSmallIntegerField(
                    default=100,
                    verbose_name="Taux d'échantillonnage (%)")),
                ("actif", models.BooleanField(
                    default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("categorie", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="qhse_plans_controle_reception",
                    to="stock.categorie", verbose_name="Catégorie")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="qhse_plans_controle_reception",
                    to="authentication.company", verbose_name="Société")),
                ("produit", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="qhse_plans_controle_reception",
                    to="stock.produit", verbose_name="Produit")),
            ],
            options={
                "verbose_name": "Plan de contrôle réception",
                "verbose_name_plural": "Plans de contrôle réception",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="PointControleReception",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("ordre", models.PositiveIntegerField(
                    default=0, verbose_name="Ordre")),
                ("intitule", models.CharField(
                    max_length=255, verbose_name="Intitulé")),
                ("type_releve", models.CharField(
                    choices=[
                        ("mesure", "Mesure"),
                        ("visuel", "Visuel"),
                        ("document", "Document"),
                        ("essai", "Essai"),
                    ],
                    default="visuel", max_length=10,
                    verbose_name="Type de relevé")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="qhse_points_controle_reception",
                    to="authentication.company", verbose_name="Société")),
                ("plan", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="points", to="qhse.plancontrolereception",
                    verbose_name="Plan de contrôle réception")),
            ],
            options={
                "verbose_name": "Point de contrôle réception",
                "verbose_name_plural": "Points de contrôle réception",
                "ordering": ["plan", "ordre", "id"],
            },
        ),
        migrations.CreateModel(
            name="ControleReception",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("reception_id", models.PositiveIntegerField(
                    verbose_name="ID de la réception fournisseur")),
                ("produit_id", models.PositiveIntegerField(
                    blank=True, null=True, verbose_name="ID du produit")),
                ("verdict", models.CharField(
                    choices=[
                        ("en_attente", "En attente"),
                        ("accepte", "Accepté"),
                        ("refuse", "Refusé"),
                        ("quarantaine", "Quarantaine"),
                    ],
                    default="en_attente", max_length=15,
                    verbose_name="Verdict")),
                ("notes", models.TextField(
                    blank=True, default="", verbose_name="Notes")),
                ("date_controle", models.DateTimeField(
                    blank=True, null=True, verbose_name="Contrôlé le")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="qhse_controles_reception",
                    to="authentication.company", verbose_name="Société")),
                ("controleur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="qhse_controles_reception",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Contrôleur")),
                ("non_conformite", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="qhse_controles_reception",
                    to="qhse.nonconformite",
                    verbose_name="Non-conformité liée")),
                ("plan", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="controles",
                    to="qhse.plancontrolereception",
                    verbose_name="Plan de contrôle réception")),
            ],
            options={
                "verbose_name": "Contrôle réception",
                "verbose_name_plural": "Contrôles réception",
                "ordering": ["-id"],
            },
        ),
        migrations.AddIndex(
            model_name="plancontrolereception",
            index=models.Index(
                fields=["company", "produit"], name="qhse_plancr_co_produit"),
        ),
        migrations.AddIndex(
            model_name="plancontrolereception",
            index=models.Index(
                fields=["company", "categorie"], name="qhse_plancr_co_categ"),
        ),
        migrations.AddIndex(
            model_name="controlereception",
            index=models.Index(
                fields=["company", "verdict"],
                name="qhse_ctrlrecep_co_verdict"),
        ),
        migrations.AddIndex(
            model_name="controlereception",
            index=models.Index(
                fields=["company", "reception_id"],
                name="qhse_ctrlrecep_co_recep"),
        ),
        migrations.AddConstraint(
            model_name="controlereception",
            constraint=models.UniqueConstraint(
                fields=("company", "reception_id", "plan"),
                name="qhse_ctrlrecep_co_recep_plan_uniq"),
        ),
    ]
