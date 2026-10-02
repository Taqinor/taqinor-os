from django.db import migrations, models


class Migration(migrations.Migration):
    """ERR-QJR570 (D-QJR5-4) — provenance persistante d'une ligne de devis.

    Additive : colonne NULL, aucun backfill (NULL = provenance inconnue).
    """

    dependencies = [
        ('ventes', '0120_qjr647_retrait_rooflayout'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignedevis',
            name='ligne_composee',
            field=models.BooleanField(
                blank=True, default=None, null=True,
                verbose_name='Ligne composée par le moteur',
                help_text="True = posée par la composition (une recomposition "
                          "la remplace) ; False = ajoutée à la main (jamais "
                          "remplacée) ; vide = inconnue (ligne antérieure)."),
        ),
    ]
