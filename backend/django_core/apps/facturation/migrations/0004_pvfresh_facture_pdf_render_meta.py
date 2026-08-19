from django.db import migrations, models


class Migration(migrations.Migration):
    """PVFRESH (fondateur, 19/08/2026) — empreinte des données dont le PDF
    facture stocké a été rendu.

    Miroir de ``ventes.migrations.0098_pvfresh_pdf_render_meta`` (le champ
    équivalent sur ``Devis``) : celui-ci vivait dans ``apps.ventes`` au moment
    de PVFRESH, mais ``Facture`` a déménagé dans ``apps.facturation`` depuis
    ODX17 — la migration mirroir vit donc dans la migration chain RÉELLE du
    modèle, pas sous le numéro 0099 de ``ventes``.

    Additif et réversible : colonne JSON nullable, aucune donnée retouchée.
    Les factures existantes la portent à ``NULL``, ce qui vaut « on ne sait
    pas de quoi ce fichier a été rendu » → les chemins de service re-rendent,
    jamais un fichier périmé.
    """

    dependencies = [
        ('facturation', '0003_ntadm2_facture_entite'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='pdf_render_meta',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
