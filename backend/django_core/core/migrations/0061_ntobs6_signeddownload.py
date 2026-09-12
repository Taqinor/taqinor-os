# NTOBS6 — liens de telechargement tokenises expirant (helper generique).
# Migration ecrite a la main (INTERDIT manage.py sur cette lane) ; state
# Django equivalent a ce que `makemigrations` produirait pour
# `core.signed_download.SignedDownload`.
import django.db.models.deletion
from django.db import migrations, models

import core.signed_download


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('core', '0060_ntobs4_slacreditpolicy'),
    ]

    operations = [
        migrations.CreateModel(
            name='SignedDownload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default=core.signed_download._default_token, max_length=64, unique=True)),
                ('bucket', models.CharField(max_length=100, verbose_name='Bucket MinIO')),
                ('object_key', models.CharField(max_length=500, verbose_name='Clé objet MinIO')),
                ('taille_octets', models.BigIntegerField(blank=True, null=True, verbose_name='Taille (octets)')),
                ('expire_le', models.DateTimeField(verbose_name='Expire le')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signed_downloads', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Lien de téléchargement tokenisé',
                'verbose_name_plural': 'Liens de téléchargement tokenisés',
                'ordering': ['-created_at'],
            },
        ),
    ]
