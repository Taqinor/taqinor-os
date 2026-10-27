"""Organigramme (fondateur, 27/10/2026) — départements, fonctions (postes) et
équipes génériques. ADDITIF : trois tables neuves, rien de modifié.
Réversible : ``migrate roles 0011``."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0034_asec5_totp_dernier_pas'),
        ('roles', '0011_commercial_portee_soi'),
    ]

    operations = [
        migrations.CreateModel(
            name='Departement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=120)),
                ('est_direction', models.BooleanField(default=False)),
                ('ordre', models.IntegerField(default=0)),
                ('actif', models.BooleanField(default=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='departements_diriges', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Département',
                'verbose_name_plural': 'Départements',
                'ordering': ['-est_direction', 'ordre', 'nom'],
                'unique_together': {('company', 'nom')},
            },
        ),
        migrations.CreateModel(
            name='Poste',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('intitule', models.CharField(max_length=120)),
                ('actif', models.BooleanField(default=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('departement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='postes', to='roles.departement')),
                ('role', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='postes', to='roles.role')),
            ],
            options={
                'verbose_name': 'Fonction',
                'verbose_name_plural': 'Fonctions',
                'ordering': ['intitule'],
                'unique_together': {('company', 'intitule')},
            },
        ),
        migrations.CreateModel(
            name='EquipeOrg',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=120)),
                ('actif', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('chef', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='equipes_org_dirigees', to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('departement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='equipes_org', to='roles.departement')),
                ('membres', models.ManyToManyField(blank=True, related_name='equipes_org', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Équipe',
                'verbose_name_plural': 'Équipes',
                'ordering': ['nom'],
                'unique_together': {('company', 'nom')},
            },
        ),
    ]
