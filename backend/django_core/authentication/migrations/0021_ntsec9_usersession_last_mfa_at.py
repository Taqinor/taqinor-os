# NTSEC9 — horodatage de la dernière MFA sur une session (additif, nullable).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersession',
            name='last_mfa_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
