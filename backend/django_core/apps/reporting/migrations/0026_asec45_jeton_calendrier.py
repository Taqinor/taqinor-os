"""ASEC45 — version du jeton de flux iCal par utilisateur (additif, revertable)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0010_customuser_supervisor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reporting', '0025_solmvp18_kpi_choices'),
    ]

    operations = [
        migrations.CreateModel(
            name='JetonCalendrier',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='jetons_calendrier',
                    verbose_name='Société',
                    to='authentication.company')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='jeton_calendrier',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Version de jeton de calendrier',
                'verbose_name_plural': 'Versions de jeton de calendrier',
            },
        ),
    ]
