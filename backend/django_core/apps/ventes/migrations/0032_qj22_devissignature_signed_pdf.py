"""QJ22 — DevisSignature : clé MinIO du PDF de proposition signé.

Additive uniquement : une colonne nullable (``signed_pdf_key``) sur
DevisSignature. Les signatures antérieures à QJ22 conservent NULL ; le
comportement pré-QJ22 est strictement inchangé pour toutes les lignes
existantes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0031_qj10_devis_signature'),
    ]

    operations = [
        migrations.AddField(
            model_name='devissignature',
            name='signed_pdf_key',
            field=models.CharField(
                blank=True,
                max_length=500,
                null=True,
                verbose_name='Clé MinIO du PDF signé',
            ),
        ),
    ]
