"""QJ10 — DevisSignature : enregistrement immuable de signature électronique."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0030_qj1_sharelink_view_tracking'),
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DevisSignature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('signataire_nom', models.CharField(max_length=150)),
                ('consentement_explicite', models.BooleanField(default=False)),
                ('ip_address', models.GenericIPAddressField(
                    blank=True, null=True, verbose_name='Adresse IP')),
                ('user_agent', models.CharField(
                    blank=True, default='', max_length=512,
                    verbose_name='User-Agent')),
                ('content_hash', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='Hash du contenu signé (SHA-256)')),
                ('signed_at', models.DateTimeField(
                    verbose_name='Horodatage de signature')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='devis_signatures',
                    to='authentication.company')),
                ('devis', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='signature',
                    to='ventes.devis')),
            ],
            options={
                'verbose_name': 'Signature électronique',
                'verbose_name_plural': 'Signatures électroniques',
                'ordering': ['-signed_at'],
            },
        ),
        migrations.AddIndex(
            model_name='devissignature',
            index=models.Index(
                fields=['devis'],
                name='ventes_devissig_dev_idx',
            ),
        ),
    ]
