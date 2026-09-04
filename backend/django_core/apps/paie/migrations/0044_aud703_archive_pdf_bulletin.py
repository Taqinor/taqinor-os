"""AUD703 — archive immuable du PDF du bulletin (doctrine D9).

Additive et réversible : trois colonnes de TRAÇABILITÉ de l'artefact remis au
salarié (clé de l'objet archivé, empreinte SHA-256, horodatage). Aucune donnée
de paie n'est touchée, aucune valeur par défaut n'est calculée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0043_yhard1_encrypt_profilpaie'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulletinpaie',
            name='pdf_archive_cle',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name="Clé de l'archive PDF"),
        ),
        migrations.AddField(
            model_name='bulletinpaie',
            name='pdf_sha256',
            field=models.CharField(
                blank=True, default='', max_length=64,
                verbose_name='Empreinte SHA-256 du PDF archivé'),
        ),
        migrations.AddField(
            model_name='bulletinpaie',
            name='pdf_archive_le',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='PDF archivé le'),
        ),
    ]
