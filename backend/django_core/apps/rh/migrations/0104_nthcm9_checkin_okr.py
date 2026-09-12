# NTHCM9 — check-ins continus sur un OKR individuel.
#
# Purement ADDITIF : une table neuve, aucun champ existant touché.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0103_nthcm3_rattachement_fonctionnel'),
    ]

    operations = [
        migrations.CreateModel(
            name='CheckInOkr',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('commentaire', models.TextField(
                    blank=True, default='', verbose_name='Commentaire')),
                ('valeurs_snapshot', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Valeurs au moment du check-in')),
                ('date', models.DateField(
                    verbose_name='Date du check-in')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('okr', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checkins',
                    to='rh.okrindividuel', verbose_name='OKR')),
                ('auteur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rh_checkins_okr',
                    to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
            ],
            options={
                'verbose_name': 'Check-in OKR',
                'verbose_name_plural': 'Check-ins OKR',
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='checkinokr',
            index=models.Index(
                fields=['company', 'okr'],
                name='rh_checkinokr_comp_okr_idx'),
        ),
    ]
