# XFSM10 — Astreinte / rotation après-heures.
# Additif : on AJOUTE une seule table (Astreinte). Aucune colonne d'une table
# existante n'est modifiée. Aucune migration destructive.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0069_xfsm8_notes_acces_site'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Astreinte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_debut', models.DateTimeField()),
                ('date_fin', models.DateTimeField()),
                ('telephone_astreinte', models.CharField(blank=True, max_length=30, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='astreintes', to='authentication.company')),
                ('technicien', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='astreintes', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='astreintes_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Astreinte',
                'verbose_name_plural': 'Astreintes',
                'ordering': ['-date_debut'],
            },
        ),
        migrations.AddIndex(
            model_name='astreinte',
            index=models.Index(fields=['company', 'date_debut', 'date_fin'], name='idx_astreinte_co_dates'),
        ),
    ]
