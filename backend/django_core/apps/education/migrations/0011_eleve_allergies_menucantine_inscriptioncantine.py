# NTEDU25 — Cantine (menus + inscriptions) + Eleve.allergies.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('education', '0010_creneauemploidutemps'),
    ]

    operations = [
        migrations.AddField(
            model_name='eleve',
            name='allergies',
            field=models.TextField(blank=True, default='', verbose_name='Allergies'),
        ),
        migrations.CreateModel(
            name='MenuCantine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField(verbose_name='Date')),
                ('description', models.CharField(max_length=255, verbose_name='Description')),
                ('allergenes', models.JSONField(blank=True, default=list, verbose_name='Allergènes')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Menu cantine',
                'verbose_name_plural': 'Menus cantine',
                'ordering': ['-date'],
                'constraints': [models.UniqueConstraint(fields=('company', 'date'), name='education_un_menu_cantine_par_jour')],
            },
        ),
        migrations.CreateModel(
            name='InscriptionCantine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_debut', models.DateField(verbose_name='Date de début')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='Date de fin')),
                ('jours_semaine', models.JSONField(default=list, verbose_name='Jours de la semaine')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('eleve', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inscriptions_cantine', to='education.eleve', verbose_name='Élève')),
            ],
            options={
                'verbose_name': 'Inscription cantine',
                'verbose_name_plural': 'Inscriptions cantine',
                'ordering': ['-id'],
            },
        ),
    ]
