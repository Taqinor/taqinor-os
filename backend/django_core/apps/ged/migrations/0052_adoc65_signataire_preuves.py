"""ADOC65 — preuves de signature PAR destinataire du circuit multi.

Additive et revertable : six colonnes à défaut neutre sur `SignataireDemande`
(consentement, IP, user-agent, signature tapée/tracée, hash du contenu signé),
posées par la routine de preuve partagée avec la signature mono.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0051_adoc64_signataire_otp_degrade'),
    ]

    operations = [
        migrations.AddField(
            model_name='signatairedemande',
            name='consentement_explicite',
            field=models.BooleanField(
                default=False, verbose_name='consentement explicite à signer'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='adresse_ip',
            field=models.GenericIPAddressField(
                blank=True, null=True,
                verbose_name='adresse IP du signataire'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='user_agent',
            field=models.CharField(
                blank=True, default='', max_length=512,
                verbose_name='user-agent'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='signature_texte',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='signature tapée'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='signature_tracee',
            field=models.TextField(
                blank=True, default='',
                verbose_name='signature tracée (vecteur/data-URL)'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='hash_contenu',
            field=models.CharField(
                blank=True, default='', max_length=64,
                verbose_name='hash du contenu signé (SHA-256)'),
        ),
    ]
