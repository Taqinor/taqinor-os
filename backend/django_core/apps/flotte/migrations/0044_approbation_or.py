# Generated for XFLT19 — Approbation des devis de réparation externe. Ajoute
# des champs additifs sur ``OrdreReparation`` (montant_devis, devis_fichier,
# approuve_par, date_approbation, ecart_facture_devis_pct) et crée
# ``ParametreApprobationOR``. Additif, multi-société.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("flotte", "0043_budgetflotte"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordrereparation",
            name="montant_devis",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Montant du devis (MAD)"),
        ),
        migrations.AddField(
            model_name="ordrereparation",
            name="devis_fichier",
            field=models.FileField(
                blank=True, null=True,
                upload_to="flotte/ordres_reparation/devis/%Y/%m/",
                verbose_name="Devis (scan)"),
        ),
        migrations.AddField(
            model_name="ordrereparation",
            name="approuve_par",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="flotte_ordres_reparation_approuves",
                to=settings.AUTH_USER_MODEL, verbose_name="Approuvé par"),
        ),
        migrations.AddField(
            model_name="ordrereparation",
            name="date_approbation",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Date d'approbation"),
        ),
        migrations.AddField(
            model_name="ordrereparation",
            name="ecart_facture_devis_pct",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=6, null=True,
                verbose_name="Écart facture / devis (%)"),
        ),
        migrations.CreateModel(
            name="ParametreApprobationOR",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("seuil_approbation", models.DecimalField(
                    decimal_places=2, default=5000, max_digits=12,
                    verbose_name="Seuil d’approbation (MAD)")),
                ("ecart_alerte_pct", models.DecimalField(
                    decimal_places=2, default=10, max_digits=5,
                    verbose_name="Écart facture/devis alerte (%)")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_parametre_approbation_or",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Paramètre d'approbation OR",
                "verbose_name_plural": "Paramètres d'approbation OR",
            },
        ),
    ]
