# Generated for DC34 — référentiel tiers-fournisseur UNIFIÉ (matériel + service)
# et satellite sous-traitant. Additif : Fournisseur.type (défaut 'materiel', donc
# tout fournisseur existant reste matériel) + le modèle SousTraitantProfile.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # stock 0027 dépend déjà (transitivement) d'authentication ≥0003 où vit
        # Company : la FK company se résout par cette chaîne. On ajoute la
        # dépendance swappable pour la FK created_by → user.
        ("stock", "0027_fichetechnique"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="fournisseur",
            name="type",
            field=models.CharField(
                choices=[
                    ("materiel", "Matériel"),
                    ("service", "Service / sous-traitance"),
                    ("mixte", "Mixte (matériel + service)"),
                ],
                default="materiel",
                max_length=10,
                help_text="Nature du fournisseur : matériel, service "
                          "(sous-traitance) ou mixte.",
            ),
        ),
        migrations.CreateModel(
            name="SousTraitantProfile",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("metier", models.CharField(
                    choices=[
                        ("terrassement", "Terrassement"),
                        ("genie_civil", "Génie civil"),
                        ("electricite", "Électricité"),
                        ("levage", "Levage"),
                        ("transport", "Transport"),
                        ("autre", "Autre"),
                    ],
                    default="autre", max_length=20)),
                ("actif", models.BooleanField(default=True)),
                ("note", models.TextField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sous_traitant_profils",
                    to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="sous_traitant_profils_crees",
                    to=settings.AUTH_USER_MODEL)),
                ("fournisseur", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profil_sous_traitant",
                    to="stock.fournisseur")),
            ],
            options={
                "verbose_name": "Profil sous-traitant",
                "verbose_name_plural": "Profils sous-traitant",
                "ordering": ["fournisseur__nom"],
            },
        ),
        migrations.AddIndex(
            model_name="soustraitantprofile",
            index=models.Index(
                fields=["company", "metier"], name="idx_stp_co_metier"),
        ),
        migrations.AddIndex(
            model_name="soustraitantprofile",
            index=models.Index(
                fields=["company", "actif"], name="idx_stp_co_actif"),
        ),
    ]
