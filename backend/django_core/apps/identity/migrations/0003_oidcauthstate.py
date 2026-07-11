import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        ('identity', '0002_consumedassertion'),
    ]

    operations = [
        migrations.CreateModel(
            name='OidcAuthState',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('state', models.CharField(
                    db_index=True, max_length=128, unique=True)),
                ('nonce', models.CharField(max_length=128)),
                ('code_verifier', models.CharField(max_length=128)),
                ('used', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='oidc_states',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'État OIDC (PKCE)',
                'verbose_name_plural': 'États OIDC (PKCE)',
            },
        ),
    ]
