# NTHCM17 — parcours de formation structurés (modules ordonnés).
#
# Purement ADDITIF : trois tables neuves (+ la table de liaison M2M générée
# par Django), aucun champ existant touché.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0096_nthcm16_feedback_continu'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParcoursFormation',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('obligatoire', models.BooleanField(
                    default=False, verbose_name='Obligatoire')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('poste_cible', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='parcours_formation',
                    to='rh.poste', verbose_name='Poste ciblé')),
                ('departement_cible', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='parcours_formation',
                    to='rh.departement', verbose_name='Département ciblé')),
            ],
            options={
                'verbose_name': 'Parcours de formation',
                'verbose_name_plural': 'Parcours de formation',
                'ordering': ['-obligatoire', 'titre'],
            },
        ),
        migrations.CreateModel(
            name='EtapeParcours',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name='Ordre')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('type_contenu', models.CharField(
                    choices=[('session', 'Session de formation'),
                             ('quiz', 'Quiz'),
                             ('document_kb',
                              'Document (base de connaissances)'),
                             ('lien_externe', 'Lien externe')],
                    default='session', max_length=14,
                    verbose_name='Type de contenu')),
                ('document_kb_id', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name='Document KB (identifiant)')),
                ('url_externe', models.URLField(
                    blank=True, default='', verbose_name='Lien externe')),
                ('obligatoire_pour_completer', models.BooleanField(
                    default=True,
                    verbose_name='Obligatoire pour compléter')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('parcours', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='etapes',
                    to='rh.parcoursformation', verbose_name='Parcours')),
                ('session_ref', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='etapes_parcours',
                    to='rh.sessionformation', verbose_name='Session liée')),
                ('quiz_ref', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='etapes_parcours',
                    to='rh.quizformation', verbose_name='Quiz lié')),
            ],
            options={
                'verbose_name': 'Étape de parcours',
                'verbose_name_plural': 'Étapes de parcours',
                'ordering': ['ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ProgressionParcours',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('statut', models.CharField(
                    choices=[('non_commence', 'Non commencé'),
                             ('en_cours', 'En cours'),
                             ('termine', 'Terminé')],
                    default='non_commence', max_length=12,
                    verbose_name='Statut')),
                ('pourcentage', models.PositiveSmallIntegerField(
                    default=0, verbose_name='Avancement (%)')),
                ('date_completion', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de complétion')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('parcours', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progressions',
                    to='rh.parcoursformation', verbose_name='Parcours')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progressions_parcours',
                    to='rh.dossieremploye', verbose_name='Employé')),
                ('etapes_completees', models.ManyToManyField(
                    blank=True, related_name='progressions',
                    to='rh.etapeparcours',
                    verbose_name='Étapes complétées')),
            ],
            options={
                'verbose_name': 'Progression de parcours',
                'verbose_name_plural': 'Progressions de parcours',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='parcoursformation',
            index=models.Index(
                fields=['company', 'obligatoire'],
                name='rh_parcform_comp_oblig_idx'),
        ),
        migrations.AddIndex(
            model_name='etapeparcours',
            index=models.Index(
                fields=['company', 'parcours'],
                name='rh_etapeparc_comp_parc_idx'),
        ),
        migrations.AddIndex(
            model_name='progressionparcours',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_progparc_comp_emp_idx'),
        ),
        migrations.AddConstraint(
            model_name='progressionparcours',
            constraint=models.UniqueConstraint(
                fields=('company', 'parcours', 'employe'),
                name='rh_progparc_comp_parc_emp_uniq'),
        ),
    ]
