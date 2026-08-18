from django.db import migrations, models


class Migration(migrations.Migration):
    """PVFRESH — empreinte des données dont le PDF stocké a été rendu.

    Additif et réversible : colonne JSON nullable, aucune donnée retouchée. Les
    devis existants la portent à ``NULL``, ce qui vaut « on ne sait pas de quoi
    ce fichier a été rendu » → les chemins de service re-rendent, jamais un
    fichier périmé.
    """

    dependencies = [
        ('ventes', '0097_pvmrq_parametres_gammes'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='pdf_render_meta',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
