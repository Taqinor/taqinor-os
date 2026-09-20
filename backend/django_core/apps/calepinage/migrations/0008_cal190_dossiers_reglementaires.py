"""CAL190 — les gabarits de dossier réglementaire et les dossiers.

ADDITIVE et SANS DONNÉE : les deux tables naissent VIDES, et c'est la règle
même de la tâche — une société sans gabarit déposé ne voit AUCUN dossier
proposé, parce qu'il n'y a pas de gabarit fictif en base. L'ERP ne fabrique
aucun formulaire officiel qu'il n'a pas reçu.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('calepinage', '0007_cal163_lestage'),
        ('records', '0013_vx210_snooze_trigger_event'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GabaritDossierReglementaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True,
                                           serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('pays', models.CharField(db_index=True, max_length=2,
                                          verbose_name='Pays')),
                ('code', models.SlugField(max_length=60,
                                          verbose_name='Code')),
                ('genre', models.SlugField(blank=True, default='',
                                           max_length=40,
                                           verbose_name='Genre')),
                ('intitule', models.CharField(max_length=200,
                                              verbose_name='Intitulé')),
                ('pieces_attendues', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Pièces attendues')),
                ('champs', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Champs du gabarit')),
                ('version', models.CharField(blank=True, default='',
                                             max_length=20,
                                             verbose_name='Version')),
                ('actif', models.BooleanField(default=True,
                                              verbose_name='Actif')),
                ('depose_le', models.DateTimeField(blank=True, null=True,
                                                   verbose_name='Déposé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('depose_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='calepinage_gabarits_dossier',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Déposé par')),
                ('fichier', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='gabarits_dossier_calepinage',
                    to='records.attachment',
                    verbose_name='Fichier de gabarit')),
            ],
            options={
                'verbose_name': 'Gabarit de dossier réglementaire',
                'verbose_name_plural': 'Gabarits de dossier réglementaire',
                'ordering': ['pays', 'intitule', 'id'],
            },
        ),
        migrations.CreateModel(
            name='DossierReglementaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True,
                                           serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('champs_saisis', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Champs saisis')),
                ('pieces_jointes', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Pièces jointes')),
                ('genere_le', models.DateTimeField(blank=True, null=True,
                                                   verbose_name='Généré le')),
                ('document_id', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name='Document (identifiant)')),
                ('calepinage', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dossiers_reglementaires',
                    to='calepinage.calepinage',
                    verbose_name='Calepinage')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('gabarit', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='dossiers',
                    to='calepinage.gabaritdossierreglementaire',
                    verbose_name='Gabarit')),
            ],
            options={
                'verbose_name': 'Dossier réglementaire',
                'verbose_name_plural': 'Dossiers réglementaires',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='gabaritdossierreglementaire',
            index=models.Index(fields=['company', 'pays', 'actif'],
                               name='cal_gab_co_pays_idx'),
        ),
        migrations.AddConstraint(
            model_name='gabaritdossierreglementaire',
            constraint=models.UniqueConstraint(
                fields=('company', 'pays', 'code'),
                name='uniq_gabarit_dossier_par_societe_pays'),
        ),
        migrations.AddIndex(
            model_name='dossierreglementaire',
            index=models.Index(fields=['company', 'calepinage'],
                               name='cal_dos_co_cal_idx'),
        ),
        migrations.AddConstraint(
            model_name='dossierreglementaire',
            constraint=models.UniqueConstraint(
                fields=('calepinage', 'gabarit'),
                name='uniq_dossier_reglementaire_par_gabarit'),
        ),
    ]
