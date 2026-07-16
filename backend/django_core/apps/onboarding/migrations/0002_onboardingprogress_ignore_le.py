from django.db import migrations, models


class Migration(migrations.Migration):
    """NTDMO13 — champ ``ignore_le`` (masquage manuel persistant d'un item)."""

    dependencies = [
        ('onboarding', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='onboardingprogress',
            name='ignore_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
