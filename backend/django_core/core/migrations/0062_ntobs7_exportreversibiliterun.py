# NTOBS7 — historique des exports de reversibilite. Migration ecrite a la
# main (INTERDIT manage.py sur cette lane) ; state Django equivalent a ce que
# `makemigrations` produirait pour `core.export_registry.ExportReversibiliteRun`.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('core', '0061_ntobs6_signeddownload'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportReversibiliteRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('statut', models.CharField(choices=[('en_cours', 'En cours'), ('pret', 'Prêt'), ('expire', 'Expiré'), ('echec', 'Échec')], default='en_cours', max_length=10, verbose_name='Statut')),
                ('fichier_key', models.CharField(blank=True, default='', max_length=500, verbose_name='Clé objet MinIO')),
                ('taille_octets', models.BigIntegerField(blank=True, null=True, verbose_name='Taille (octets)')),
                ('token', models.CharField(blank=True, default='', max_length=64, verbose_name='Jeton de téléchargement')),
                ('expire_le', models.DateTimeField(blank=True, null=True, verbose_name='Expire le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='core_exportreversibiliterun_set', to='authentication.company', verbose_name='Société')),
                ('demande_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Demandé par')),
            ],
            options={
                'verbose_name': 'Export de réversibilité',
                'verbose_name_plural': 'Exports de réversibilité',
                'ordering': ['-created_at'],
            },
        ),
    ]
