import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('publicapi', '0016_ntapi17_apievent'),
    ]

    operations = [
        migrations.CreateModel(
            name='OAuthClient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=120)),
                ('client_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('client_secret_hash', models.CharField(db_index=True, max_length=64)),
                ('scopes', models.JSONField(blank=True, default=list)),
                ('actif', models.BooleanField(default=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('api_key', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='oauth_clients', to='publicapi.apikey')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='oauth_clients_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Client OAuth2 (API publique)',
                'verbose_name_plural': 'Clients OAuth2 (API publique)',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['company', 'actif'], name='publicapi_oauth_co_actif_idx')],
            },
        ),
    ]
