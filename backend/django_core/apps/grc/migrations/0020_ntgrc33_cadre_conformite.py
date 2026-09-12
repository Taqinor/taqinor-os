# NTGRC33 — cadres de conformité multi-référentiels + leurs exigences.
# Deux tables NEUVES, purement additives. Le contrôle qui couvre une exigence
# est référencé par un identifiant TEXTE (string-FK), conformément au reste du
# module.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0019_ntgrc30_flux_donnees'),
    ]

    operations = [
        migrations.CreateModel(
            name='CadreConformite',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(
                    choices=[('ISO27001', 'ISO/IEC 27001'),
                             ('loi_09-08', 'Loi 09-08 (Maroc)'),
                             ('RGPD', 'RGPD (UE 2016/679)'),
                             ('SOX_lite', 'SOX allégé'),
                             ('ISO27701', 'ISO/IEC 27701')],
                    max_length=20, verbose_name='Code')),
                ('intitule', models.CharField(
                    max_length=200, verbose_name='Intitulé')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Cadre de conformité',
                'verbose_name_plural': 'Cadres de conformité',
                'ordering': ['code', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ExigenceCadre',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code_exigence', models.CharField(
                    max_length=40, verbose_name="Code de l'exigence")),
                ('intitule', models.CharField(
                    max_length=300, verbose_name='Intitulé')),
                ('controle_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant texte du grc.ControleInterne '
                              '(string-FK).',
                    max_length=64, verbose_name='Contrôle couvrant')),
                ('statut_couverture', models.CharField(
                    choices=[('couvert', 'Couvert'),
                             ('partiel', 'Partiellement couvert'),
                             ('non_couvert', 'Non couvert')],
                    default='non_couvert', max_length=12,
                    verbose_name='Couverture')),
                ('cadre', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='exigences', to='grc.cadreconformite',
                    verbose_name='Cadre')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Exigence de cadre',
                'verbose_name_plural': 'Exigences de cadre',
                'ordering': ['code_exigence', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='exigencecadre',
            index=models.Index(fields=['company', 'statut_couverture'],
                               name='grc_exigence_co_couv_idx'),
        ),
        migrations.AddConstraint(
            model_name='cadreconformite',
            constraint=models.UniqueConstraint(
                fields=('company', 'code'),
                name='grc_cadreconformite_co_code'),
        ),
        migrations.AddConstraint(
            model_name='exigencecadre',
            constraint=models.UniqueConstraint(
                fields=('cadre', 'code_exigence'),
                name='grc_exigencecadre_cadre_code'),
        ),
    ]
