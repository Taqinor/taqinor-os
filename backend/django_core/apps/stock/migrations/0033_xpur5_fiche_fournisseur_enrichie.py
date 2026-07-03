# XPUR5 — Fiche fournisseur enrichie : contacts multiples, catégorie/tags,
# devise/incoterm par défaut, validation ICE. Additif : CategorieFournisseur,
# ContactFournisseur, Fournisseur.categorie/devise_defaut/incoterm.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0032_xpur4_statut_fournisseur"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategorieFournisseur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=100)),
                ("archived", models.BooleanField(default=False)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="categories_fournisseur",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Catégorie fournisseur",
                "verbose_name_plural": "Catégories fournisseur",
                "ordering": ["nom"],
                "unique_together": {("company", "nom")},
            },
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="categorie",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fournisseurs", to="stock.categoriefournisseur"),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="devise_defaut",
            field=models.CharField(
                blank=True, default="", max_length=3,
                help_text='Devise par défaut pour les BCF de ce '
                          'fournisseur (vide = MAD, comportement '
                          'historique).',
            ),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="incoterm",
            field=models.CharField(
                blank=True, default="", max_length=10,
                help_text='Incoterm par défaut (EXW, FOB, CIF…). Vide = '
                          'non défini.',
            ),
        ),
        migrations.CreateModel(
            name="ContactFournisseur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=255)),
                ("fonction", models.CharField(
                    blank=True, default="", max_length=120)),
                ("email", models.EmailField(
                    blank=True, max_length=254, null=True)),
                ("telephone", models.CharField(
                    blank=True, max_length=20, null=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contacts_fournisseur",
                    to="authentication.company")),
                ("fournisseur", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contacts", to="stock.fournisseur")),
            ],
            options={
                "verbose_name": "Contact fournisseur",
                "verbose_name_plural": "Contacts fournisseur",
                "ordering": ["fournisseur_id", "nom"],
            },
        ),
    ]
