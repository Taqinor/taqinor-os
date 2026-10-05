from django.db import migrations, models


class Migration(migrations.Migration):
    """AGR217 (contrat AGR200) — base légale TVA d'une ligne exonérée.

    Additive : colonne texte vide par défaut, aucun backfill (les lignes
    historiques ne sont pas réécrites).
    """

    dependencies = [
        ('ventes', '0121_err_qjr570_ligne_composee'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignedevis',
            name='tva_base_legale',
            field=models.CharField(
                blank=True, default='', max_length=160,
                help_text="Base légale de l'exonération (ligne à 0 %). Saisie "
                          "par l'utilisateur ; vide = aucune."),
        ),
    ]
