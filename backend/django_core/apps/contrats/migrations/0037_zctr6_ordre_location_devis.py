# ZCTR6 — Devis/commande portant des lignes de location (Rental order via
# ventes). Ajoute `OrdreLocation.devis_id` / `devis_ligne_id` (liens LÂCHES,
# nullables) pour rattacher un ordre de location créé depuis un devis accepté
# et servir de garde anti-doublon. Purement additif : NULL = ordre créé
# manuellement (comportement XCTR17 inchangé).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0036_zctr4_parametres_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordrelocation",
            name="devis_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="ID du devis d'origine"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="devis_ligne_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="ID de la ligne devis d'origine"),
        ),
        migrations.AddIndex(
            model_name="ordrelocation",
            index=models.Index(
                fields=["devis_id", "devis_ligne_id"],
                name="contrats_ordloc_devis_ligne"),
        ),
    ]
