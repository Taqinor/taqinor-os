import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('core', '0056_ntgrc3_dsr_echeance'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApiDeprecation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(default='v1', help_text="Version de l'API publique concernée (ex. « v1 »).", max_length=10, verbose_name='Version')),
                ('endpoint_pattern', models.CharField(help_text='Motif glob comparé au chemin complet, ex. « /api/public/v1/leads/* ».', max_length=200, verbose_name='Motif de chemin')),
                ('deprecated_at', models.DateTimeField(help_text="Date d'annonce de la dépréciation.", verbose_name='Déprécié le')),
                ('sunset_at', models.DateTimeField(help_text="Date à laquelle l'endpoint cesse de répondre (RFC 8594).", verbose_name='Fin de vie le')),
                ('message', models.TextField(blank=True, default='', help_text='Explication FR affichée aux intégrateurs (migration à faire).', verbose_name='Message')),
                ('doc_url', models.CharField(blank=True, default='', help_text='Cible de l\'en-tête « Link: <…>; rel="deprecation" ». Vide = la référence publique par défaut.', max_length=300, verbose_name='Lien de documentation')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, help_text='Vide = annonce globale (toutes les sociétés).', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='api_deprecations', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Dépréciation d'API",
                'verbose_name_plural': "Dépréciations d'API",
                'ordering': ['-sunset_at', 'id'],
                'indexes': [models.Index(fields=['version', 'actif'], name='core_apidepr_ver_actif_idx')],
            },
        ),
    ]
