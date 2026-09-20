"""CAL64 — le relevé terrain mobile (photos + cotes saisies + boussole).

Deux opérations, toutes deux ADDITIVES :
  * une table neuve ``ReleveTerrain`` ;
  * ``PhotoSite.releve``, FK NULLABLE : une photo déposée seule (CAL52) reste
    une photo de première classe, et aucune ligne existante n'est réécrite.

Revertable par un simple ``git revert`` + rollback : rien n'est détruit.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0002_cal52_photosite'),
        ('authentication', '0032_customuser_calendrier_hegirien'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReleveTerrain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chaines', models.JSONField(blank=True, default=list, verbose_name='Chaînes de cotes (saisie)')),
                ('geometrie', models.JSONField(blank=True, null=True, verbose_name='Géométrie résolue')),
                ('azimut_boussole_deg', models.FloatField(blank=True, null=True, verbose_name='Azimut boussole (°)')),
                ('precision_azimut_deg', models.FloatField(blank=True, null=True, verbose_name='Précision de l’azimut (°)')),
                ('releve_le', models.DateField(verbose_name='Relevé le')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes de terrain')),
                ('calepinage', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='releves_terrain', to='calepinage.calepinage', verbose_name='Calepinage')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('releve_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calepinage_releves_terrain', to=settings.AUTH_USER_MODEL, verbose_name='Relevé par')),
            ],
            options={
                'verbose_name': 'Relevé terrain',
                'verbose_name_plural': 'Relevés terrain',
                'ordering': ['-releve_le', '-id'],
            },
        ),
        migrations.AddField(
            model_name='photosite',
            name='releve',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='photos', to='calepinage.releveterrain', verbose_name='Relevé terrain'),
        ),
        migrations.AddIndex(
            model_name='releveterrain',
            index=models.Index(fields=['calepinage', '-releve_le'], name='cal_rel_cal_date_idx'),
        ),
        migrations.AddIndex(
            model_name='releveterrain',
            index=models.Index(fields=['company', '-created_at'], name='cal_rel_co_cree_idx'),
        ),
    ]
