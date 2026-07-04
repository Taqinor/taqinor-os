# Generated for XRH25 — entretien de sortie (exit interview) + turnover.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0060_reglagerh_retention_candidatures_mois'),
    ]

    operations = [
        migrations.CreateModel(
            name='EntretienSortie',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('date', models.DateField(
                    blank=True, null=True,
                    verbose_name="Date de l'entretien")),
                ('motif_principal', models.CharField(
                    blank=True, choices=[
                        ('salaire', 'Salaire'),
                        ('management', 'Management'),
                        ('conditions', 'Conditions de travail'),
                        ('distance', 'Distance / trajet'),
                        ('opportunite', 'Opportunité ailleurs'),
                        ('sante', 'Santé'),
                        ('autre', 'Autre'),
                    ], default='', max_length=20,
                    verbose_name='Motif principal')),
                ('questionnaire', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Questionnaire (réponses)')),
                ('recommanderait', models.BooleanField(
                    blank=True, null=True,
                    verbose_name='Recommanderait l’entreprise')),
                ('commentaire', models.TextField(
                    blank=True, default='', verbose_name='Commentaire')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_entretiens_sortie',
                    to='authentication.company', verbose_name='Société')),
                ('employe', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='entretien_sortie', to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Entretien de sortie',
                'verbose_name_plural': 'Entretiens de sortie',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='entretiensortie',
            index=models.Index(
                fields=['company', 'motif_principal'],
                name='rh_ent_sortie_comp_motif_idx'),
        ),
    ]
