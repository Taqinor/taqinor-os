# XCTR17 — location de matériel SORTANTE (aux clients) : `louable` +
# tarifs indicatifs sur `Produit`. Additif, tout par défaut inchangé
# (`louable=False`, tarifs NULL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0040_fournisseur_custom_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="produit",
            name="louable",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Peut faire l'objet d'un ordre de location client "
                    "(groupe électrogène, pompe, nacelle…)."
                ),
                verbose_name="Louable aux clients",
            ),
        ),
        migrations.AddField(
            model_name="produit",
            name="tarif_location_jour",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name="Tarif location / jour"),
        ),
        migrations.AddField(
            model_name="produit",
            name="tarif_location_semaine",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name="Tarif location / semaine"),
        ),
        migrations.AddField(
            model_name="produit",
            name="tarif_location_mois",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name="Tarif location / mois"),
        ),
    ]
