import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebAuthnCredential',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('credential_id', models.CharField(
                    db_index=True, max_length=255, unique=True)),
                ('public_key', models.TextField()),
                ('sign_count', models.PositiveBigIntegerField(default=0)),
                ('nom_appareil', models.CharField(
                    blank=True, default='', max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webauthn_credentials',
                    to='authentication.customuser')),
            ],
            options={
                'verbose_name': 'Passkey (WebAuthn)',
                'verbose_name_plural': 'Passkeys (WebAuthn)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WebAuthnChallenge',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('challenge', models.CharField(db_index=True, max_length=255)),
                ('purpose', models.CharField(
                    choices=[('register', 'Enregistrement'),
                             ('login', 'Connexion')], max_length=10)),
                ('used', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webauthn_challenges',
                    to='authentication.customuser')),
            ],
            options={
                'verbose_name': 'Défi WebAuthn',
                'verbose_name_plural': 'Défis WebAuthn',
                'ordering': ['-created_at'],
            },
        ),
    ]
