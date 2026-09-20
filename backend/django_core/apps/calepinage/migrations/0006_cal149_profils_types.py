"""CAL149 — les PROFILS TYPES de consommation, saisis par la société.

ADDITIVE et SANS DONNÉE : la table naît VIDE. Une société sans profil se
comporte donc exactement comme avant — les profils codés en dur du dépôt
restent servis en repli, mais ÉTIQUETÉS « hypothèse interne »
(``services/profils_types.py``), jamais présentés comme une mesure.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('calepinage', '0005_cal139_pertes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfilTypeConsommation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cle', models.SlugField(max_length=60, verbose_name='Clé')),
                ('libelle', models.CharField(max_length=160, verbose_name='Libellé')),
                ('famille', models.CharField(choices=[('residentiel', 'Résidentiel'), ('commercial', 'Commercial / tertiaire'), ('industriel', 'Industriel'), ('agricole', 'Agricole'), ('autre', 'Autre')], default='residentiel', max_length=16, verbose_name='Famille')),
                ('courbe', models.JSONField(default=dict, verbose_name='Courbe 24 h par saison')),
                ('provenance', models.TextField(verbose_name='Provenance')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('saisi_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calepinage_profils_types', to=settings.AUTH_USER_MODEL, verbose_name='Saisi par')),
            ],
            options={
                'verbose_name': 'Profil type de consommation',
                'verbose_name_plural': 'Profils types de consommation',
                'ordering': ['famille', 'libelle', 'id'],
                'indexes': [models.Index(fields=['company', 'famille'], name='cal_pro_co_fam_idx')],
                'constraints': [models.UniqueConstraint(fields=('company', 'cle'), name='uniq_profil_type_conso_par_societe')],
            },
        ),
    ]
