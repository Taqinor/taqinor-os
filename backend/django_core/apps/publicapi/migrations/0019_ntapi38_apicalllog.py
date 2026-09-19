import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('publicapi', '0018_ntapi36_partenaireedi'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApiCallLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('methode', models.CharField(max_length=10)),
                ('chemin', models.CharField(max_length=512)),
                ('statut', models.PositiveSmallIntegerField()),
                ('latence_ms', models.PositiveIntegerField(default=0)),
                ('request_id', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('taille_payload', models.PositiveIntegerField(default=0, help_text='Taille du corps de RÉPONSE en octets.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('api_key', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='call_logs', to='publicapi.apikey')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Appel d'API publique",
                'verbose_name_plural': "Appels d'API publique",
                'ordering': ['-created_at', '-id'],
                'indexes': [
                    models.Index(fields=['company', 'created_at'], name='publicapi_acl_co_cree_idx'),
                    models.Index(fields=['company', 'statut'], name='publicapi_acl_co_statut_idx'),
                ],
            },
        ),
    ]
