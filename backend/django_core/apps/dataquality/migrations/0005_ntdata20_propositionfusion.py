"""NTDATA20 — `PropositionFusion` : la file de revue humaine des doublons.

Table NEUVE, purement additive. `decideur` est en SET_NULL : désactiver un
utilisateur ne doit jamais effacer la trace qu'une décision a été prise sur un
groupe (sinon le groupe redeviendrait « jamais tranché » et le scan suivant le
reproposerait).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('dataquality', '0004_ntdata23_survivorship'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PropositionFusion',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entite', models.CharField(max_length=20,
                                            verbose_name='Entité')),
                (
                    'ids_groupe',
                    models.JSONField(
                        default=list, verbose_name='Fiches du groupe',
                        help_text='Identifiants des fiches rapprochées.'),
                ),
                (
                    'empreinte',
                    models.CharField(
                        max_length=64, verbose_name='Empreinte du groupe',
                        help_text='Identité stable du groupe (ses '
                                  'identifiants triés) — ce qui permet de ne '
                                  'pas reproposer un groupe déjà tranché.'),
                ),
                (
                    'score',
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=4,
                        verbose_name='Score du détecteur',
                        help_text='Confiance du DÉTECTEUR (poids du critère '
                                  'le plus fort), jamais une mesure métier.'),
                ),
                (
                    'motifs',
                    models.JSONField(blank=True, default=list,
                                     verbose_name='Critères concordants'),
                ),
                (
                    'libelles',
                    models.JSONField(blank=True, default=list,
                                     verbose_name='Libellés des fiches'),
                ),
                (
                    'statut',
                    models.CharField(
                        choices=[('en_attente', 'En attente de décision'),
                                 ('fusionne', 'Fusionné'),
                                 ('ignore', 'Ignoré (pas des doublons)')],
                        default='en_attente', max_length=15,
                        verbose_name='Statut'),
                ),
                ('decide_le', models.DateTimeField(blank=True, null=True,
                                                   verbose_name='Décidé le')),
                (
                    'detail_decision',
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name='Détail de la décision',
                        help_text='Ce que la fusion a réellement '
                                  'repointé/absorbé.'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
                (
                    'decideur',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='propositions_fusion_decidees',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Décideur'),
                ),
            ],
            options={
                'verbose_name': 'Proposition de fusion',
                'verbose_name_plural': 'Propositions de fusion',
                'ordering': ['statut', '-score', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='propositionfusion',
            constraint=models.UniqueConstraint(
                fields=('company', 'entite', 'empreinte'),
                name='uniq_propositionfusion_co_ent_emp'),
        ),
    ]
