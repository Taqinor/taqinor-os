# ZSTK12 - nomenclature de code-barres configurable (Default/GS1) par societe
# + regles de routage (motif -> type d'entite). Additif : sans nomenclature
# ACTIVE, le resolveur de scan reste byte-identique au comportement actuel
# (aucune donnee/BCF/produit existant touche par cette migration).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0070_zpur11_motif_annulation"),
    ]

    operations = [
        migrations.CreateModel(
            name="NomenclatureCodeBarres",
            fields=[
                ("id", models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=100)),
                ("type_nomenclature", models.CharField(
                    choices=[("default", "Défaut (EAN/UPC)"), ("gs1", "GS1")],
                    default="default", max_length=10)),
                ("actif", models.BooleanField(default=False)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_mise_a_jour", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="nomenclatures_code_barres",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Nomenclature de code-barres",
                "verbose_name_plural": "Nomenclatures de code-barres",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="RegleCodeBarres",
            fields=[
                ("id", models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("motif", models.CharField(max_length=200)),
                ("est_regex", models.BooleanField(default=False)),
                ("encode", models.CharField(
                    choices=[
                        ("produit", "Produit"), ("lot", "Lot"),
                        ("serie", "Série"),
                        ("emplacement", "Emplacement"),
                        ("quantite", "Quantité"),
                    ],
                    max_length=20)),
                ("priorite", models.PositiveIntegerField(default=100)),
                ("nomenclature", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="regles",
                    to="stock.nomenclaturecodebarres")),
            ],
            options={
                "verbose_name": "Règle de code-barres",
                "verbose_name_plural": "Règles de code-barres",
                "ordering": ["priorite", "id"],
            },
        ),
    ]
