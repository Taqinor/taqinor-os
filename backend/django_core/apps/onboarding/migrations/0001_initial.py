import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_items(apps, schema_editor):
    """Seed initial du catalogue global d'items (idempotent)."""
    from apps.onboarding.services import seed_default_items
    Item = apps.get_model('onboarding', 'OnboardingChecklistItem')
    seed_default_items(model=Item)


def unseed_items(apps, schema_editor):
    Item = apps.get_model('onboarding', 'OnboardingChecklistItem')
    Item.objects.filter(company__isnull=True).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OnboardingChecklistItem',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('key', models.SlugField(
                    max_length=80, unique=True,
                    help_text="Clé stable (jamais renommée) — identifiant "
                              "d'auto-complétion.")),
                ('libelle', models.CharField(max_length=200)),
                ('ordre', models.PositiveIntegerField(default=100)),
                ('roles_cibles', models.JSONField(blank=True, default=list)),
                ('lien', models.CharField(
                    blank=True, default='', max_length=255)),
                ('event_key', models.CharField(
                    blank=True, default='', max_length=60)),
                ('actif', models.BooleanField(default=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='onboarding_items',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Item de checklist onboarding',
                'verbose_name_plural': 'Items de checklist onboarding',
                'ordering': ['ordre', 'key'],
            },
        ),
        migrations.CreateModel(
            name='OnboardingProgress',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('complete_le', models.DateTimeField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='onboarding_progress',
                    to='authentication.company')),
                ('item', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progress',
                    to='onboarding.onboardingchecklistitem')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='onboarding_progress',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Avancement onboarding',
                'verbose_name_plural': 'Avancements onboarding',
                'unique_together': {('user', 'item')},
            },
        ),
        migrations.RunPython(seed_items, unseed_items),
    ]
