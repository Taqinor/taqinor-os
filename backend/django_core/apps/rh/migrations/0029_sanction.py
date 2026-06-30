# Generated 2026-06-30 — FG191 Disciplinaire & sanctions
#
# Entièrement additive : ``CreateModel`` (``Sanction``) + index nommés —
# réversible. Registre des mesures disciplinaires (code du travail marocain) :
# observation, avertissement, blâme, mise à pied (durée en jours), mutation,
# rétrogradation, licenciement, rattachées à un employé (DossierEmploye, même
# société) avec date des faits, date de notification, motif, auteur et statut
# (notifiée → contestée → annulée). Société posée côté serveur. RUNTIME-SAFETY :
# codes bornés ≤ 20 ; motif en TextField ; index nommés (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0028_entretiens_evaluations'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sanction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_sanction', models.CharField(choices=[('observation', 'Observation'), ('avertissement', 'Avertissement'), ('blame', 'Blâme'), ('mise_a_pied', 'Mise à pied'), ('mutation', 'Mutation disciplinaire'), ('retrogradation', 'Rétrogradation'), ('licenciement', 'Licenciement')], default='avertissement', max_length=20, verbose_name='Type de sanction')),
                ('date_faits', models.DateField(blank=True, null=True, verbose_name='Date des faits')),
                ('date_notification', models.DateField(blank=True, null=True, verbose_name='Date de notification')),
                ('duree_jours', models.PositiveIntegerField(default=0, verbose_name='Durée (jours)')),
                ('motif', models.TextField(blank=True, default='', verbose_name='Motif')),
                ('statut', models.CharField(choices=[('notifiee', 'Notifiée'), ('contestee', 'Contestée'), ('annulee', 'Annulée')], default='notifiee', max_length=20, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('auteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sanctions_prononcees', to='rh.dossieremploye', verbose_name='Auteur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_sanctions', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sanctions', to='rh.dossieremploye', verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Sanction disciplinaire',
                'verbose_name_plural': 'Sanctions disciplinaires',
                'ordering': ['-date_notification', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='sanction',
            index=models.Index(fields=['company', 'employe'], name='rh_sanc_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='sanction',
            index=models.Index(fields=['company', 'statut'], name='rh_sanc_comp_stat_idx'),
        ),
    ]
