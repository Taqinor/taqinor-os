# QX9 — preuve de signature électronique réelle (loi 43-20). Additif/nullable :
# les signatures existantes gardent leurs valeurs par défaut, comportement
# strictement inchangé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0078_facture_condition_paiement_ref'),
    ]

    operations = [
        migrations.AddField(
            model_name='devissignature',
            name='signature_image',
            field=models.TextField(
                blank=True, default='',
                verbose_name='Image de la signature (data-URL / clé MinIO)'),
        ),
        migrations.AddField(
            model_name='devissignature',
            name='consent_esign',
            field=models.BooleanField(
                default=False,
                verbose_name='Consentement explicite e-signature (43-20)'),
        ),
        migrations.AddField(
            model_name='devissignature',
            name='signed_at_client',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Horodatage client de la signature'),
        ),
        migrations.AddField(
            model_name='devissignature',
            name='on_behalf_of',
            field=models.CharField(
                blank=True, default='', max_length=150,
                verbose_name='Signe au nom de (facultatif)'),
        ),
    ]
