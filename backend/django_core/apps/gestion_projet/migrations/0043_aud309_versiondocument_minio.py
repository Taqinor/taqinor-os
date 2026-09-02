# AUD309 — `VersionDocument` : le contenu bascule dans MinIO (conventions
# `records.storage`, patron `apps.ged.DocumentVersion`). Additive et non
# destructive : les 4 champs de la clé objet sont AJOUTÉS, et l'ancien
# `FileField` devient simplement optionnel (plus jamais écrit) pour que les
# lignes historiques restent lisibles.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0042_soustraitant_fournisseur'),
    ]

    operations = [
        migrations.AddField(
            model_name='versiondocument',
            name='file_key',
            field=models.CharField(
                blank=True, default='', max_length=500,
                verbose_name='Clé MinIO'),
        ),
        migrations.AddField(
            model_name='versiondocument',
            name='filename',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Nom du fichier'),
        ),
        migrations.AddField(
            model_name='versiondocument',
            name='size',
            field=models.PositiveIntegerField(
                default=0, verbose_name='Taille (octets)'),
        ),
        migrations.AddField(
            model_name='versiondocument',
            name='mime',
            field=models.CharField(
                blank=True, default='', max_length=120,
                verbose_name='Type MIME'),
        ),
        migrations.AlterField(
            model_name='versiondocument',
            name='fichier',
            field=models.FileField(
                blank=True, null=True,
                upload_to='gestion_projet/documents/',
                verbose_name='Fichier (legacy, hors MinIO)'),
        ),
    ]
