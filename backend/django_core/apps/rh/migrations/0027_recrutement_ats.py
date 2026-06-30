# Generated 2026-06-30 — FG189 Recrutement (ATS-lite)
#
# Entièrement additive : ``CreateModel`` (``OuverturePoste``, ``Candidature``)
# + index nommés — réversible. L'ouverture de poste porte un intitulé, un poste
# de référence (FK ``rh.Poste``) et un département (FK ``rh.Departement``)
# optionnels, une description, un nombre de postes, un statut (ouvert → pourvu /
# clos / annulé) et des dates. La candidature rattache un candidat à une
# ouverture, avec un pipeline d'étapes (reçu → présélection → entretien → offre
# → embauché / rejeté) et un FK ``employe_cree`` (``SET_NULL``) posé à
# l'embauche (service ``apps.rh.services.embaucher``). Société posée côté
# serveur. RUNTIME-SAFETY (leçon FG136) : codes bornés ``statut`` / ``etape``
# ≤ 20 ; chaînes plafonnées ; descriptions/notes en TextField ; index nommés
# explicitement (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0026_besoin_formation'),
    ]

    operations = [
        migrations.CreateModel(
            name='OuverturePoste',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intitule', models.CharField(max_length=200, verbose_name='Intitulé')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('nombre_postes', models.PositiveIntegerField(default=1, verbose_name='Nombre de postes')),
                ('statut', models.CharField(choices=[('ouvert', 'Ouvert'), ('pourvu', 'Pourvu'), ('clos', 'Clos'), ('annule', 'Annulé')], default='ouvert', max_length=20, verbose_name='Statut')),
                ('date_ouverture', models.DateField(blank=True, null=True, verbose_name="Date d'ouverture")),
                ('date_cible', models.DateField(blank=True, null=True, verbose_name='Date cible')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_ouvertures_poste', to='authentication.company', verbose_name='Société')),
                ('departement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ouvertures', to='rh.departement', verbose_name='Département')),
                ('poste_ref', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ouvertures', to='rh.poste', verbose_name='Poste')),
            ],
            options={
                'verbose_name': 'Ouverture de poste',
                'verbose_name_plural': 'Ouvertures de poste',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='Candidature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=160, verbose_name='Nom')),
                ('email', models.EmailField(blank=True, default='', max_length=254, verbose_name='E-mail')),
                ('telephone', models.CharField(blank=True, default='', max_length=30, verbose_name='Téléphone')),
                ('cv_fichier', models.FileField(blank=True, null=True, upload_to='rh/candidatures/cv/', verbose_name='CV')),
                ('source', models.CharField(blank=True, default='', max_length=80, verbose_name='Source')),
                ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                ('etape', models.CharField(choices=[('recu', 'Reçu'), ('preselection', 'Présélection'), ('entretien', 'Entretien'), ('offre', 'Offre'), ('embauche', 'Embauché'), ('rejete', 'Rejeté')], default='recu', max_length=20, verbose_name='Étape')),
                ('date_candidature', models.DateField(blank=True, null=True, verbose_name='Date de candidature')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_candidatures', to='authentication.company', verbose_name='Société')),
                ('employe_cree', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='candidatures_origine', to='rh.dossieremploye', verbose_name='Employé créé')),
                ('ouverture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='candidatures', to='rh.ouvertureposte', verbose_name='Ouverture')),
            ],
            options={
                'verbose_name': 'Candidature',
                'verbose_name_plural': 'Candidatures',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='ouvertureposte',
            index=models.Index(fields=['company', 'statut'], name='rh_op_comp_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='candidature',
            index=models.Index(fields=['company', 'etape'], name='rh_cand_comp_etap_idx'),
        ),
        migrations.AddIndex(
            model_name='candidature',
            index=models.Index(fields=['company', 'ouverture'], name='rh_cand_comp_ouv_idx'),
        ),
    ]
