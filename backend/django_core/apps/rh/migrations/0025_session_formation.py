# Generated 2026-06-30 — FG187 Gestion de la formation (sessions / inscriptions)
#
# Entièrement additive : ``CreateModel`` (``SessionFormation`` +
# ``InscriptionFormation``) + contrainte d'unicité + index nommés — réversible.
# La session de formation (interne / externe) porte un coût, des dates, un lieu
# et une compétence visée optionnelle (FK même app ``rh.Competence``) ; les
# inscriptions tracent participant / présence / résultat. Quand une session est
# marquée RÉALISÉE et qu'une compétence est visée, le niveau des participants
# présents est mis à jour dans la matrice (``CompetenceEmploye``). Société posée
# côté serveur. RUNTIME-SAFETY (leçon FG136) : codes bornés ``type`` /
# ``statut`` / ``resultat`` ≤ 20, ``intitule`` / ``organisme`` / ``lieu``
# plafonnés, ``notes`` / ``note`` en TextField ; index nommés explicitement
# (≤ 30 chars) pour éviter la divergence d'auto-nommage.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0024_analyse_risques_chantier'),
    ]

    operations = [
        migrations.CreateModel(
            name='SessionFormation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intitule', models.CharField(max_length=200, verbose_name='Intitulé')),
                ('type', models.CharField(choices=[('interne', 'Interne'), ('externe', 'Externe')], default='interne', max_length=20, verbose_name='Type')),
                ('organisme', models.CharField(blank=True, default='', max_length=200, verbose_name='Organisme')),
                ('date_debut', models.DateField(verbose_name='Date de début')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='Date de fin')),
                ('lieu', models.CharField(blank=True, default='', max_length=255, verbose_name='Lieu')),
                ('cout', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=12, verbose_name='Coût')),
                ('statut', models.CharField(choices=[('planifiee', 'Planifiée'), ('realisee', 'Réalisée'), ('annulee', 'Annulée')], default='planifiee', max_length=20, verbose_name='Statut')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('competence_visee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions_formation', to='rh.competence', verbose_name='Compétence visée')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_sessions_formation', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Session de formation',
                'verbose_name_plural': 'Sessions de formation',
                'ordering': ['-date_debut', '-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='InscriptionFormation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('present', models.BooleanField(default=False, verbose_name='Présent')),
                ('resultat', models.CharField(choices=[('non_evalue', 'Non évalué'), ('reussi', 'Réussi'), ('echec', 'Échec')], default='non_evalue', max_length=20, verbose_name='Résultat')),
                ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_inscriptions_formation', to='authentication.company', verbose_name='Société')),
                ('participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='formations', to='rh.dossieremploye', verbose_name='Participant')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inscriptions', to='rh.sessionformation', verbose_name='Session')),
            ],
            options={
                'verbose_name': 'Inscription à une formation',
                'verbose_name_plural': 'Inscriptions aux formations',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='sessionformation',
            index=models.Index(fields=['company', 'date_debut'], name='rh_sf_comp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='sessionformation',
            index=models.Index(fields=['company', 'statut'], name='rh_sf_comp_stat_idx'),
        ),
        migrations.AddConstraint(
            model_name='inscriptionformation',
            constraint=models.UniqueConstraint(fields=('session', 'participant'), name='rh_inscr_form_uniq'),
        ),
        migrations.AddIndex(
            model_name='inscriptionformation',
            index=models.Index(fields=['company', 'session'], name='rh_if_comp_sess_idx'),
        ),
    ]
