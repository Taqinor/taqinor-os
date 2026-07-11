import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('identity', '0003_oidcauthstate'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScimToken',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('label', models.CharField(
                    blank=True, default='', max_length=120)),
                ('token_hash', models.CharField(
                    db_index=True, max_length=64, unique=True)),
                ('prefix', models.CharField(
                    blank=True, default='', max_length=20)),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('last_rotated_at', models.DateTimeField(
                    blank=True, null=True)),
                ('rotation_period_days', models.PositiveIntegerField(
                    default=0)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scim_tokens',
                    to='authentication.company')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='scim_tokens_crees',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Jeton SCIM',
                'verbose_name_plural': 'Jetons SCIM',
                'ordering': ['-created_at'],
            },
        ),
    ]
