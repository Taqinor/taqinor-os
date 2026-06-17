# N38 — clé MinIO du dernier export UBL 2.1 (aperçu brouillon).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0015_facture_statut_teledeclaration"),
    ]

    operations = [
        migrations.AddField(
            model_name="facture",
            name="fichier_ubl",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
