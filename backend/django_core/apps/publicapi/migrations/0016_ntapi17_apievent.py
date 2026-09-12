import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('publicapi', '0015_ntapi12_webhook_filtres'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApiEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence', models.BigIntegerField()),
                ('type', models.CharField(max_length=50)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('event_id', models.CharField(blank=True, db_index=True, default='', max_length=36)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Évènement d'API publique",
                'verbose_name_plural': "Évènements d'API publique",
                'ordering': ['company', 'sequence'],
                'indexes': [models.Index(fields=['company', 'sequence'], name='publicapi_apievent_cur_idx')],
                'constraints': [models.UniqueConstraint(fields=('company', 'sequence'), name='publicapi_apievent_co_seq')],
            },
        ),
    ]
