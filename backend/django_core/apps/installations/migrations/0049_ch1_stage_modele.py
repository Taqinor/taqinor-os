# CH1 — Étapes/gates CONFIGURABLES du cycle de vie chantier (StageModele) +
# pointeur nullable ``Installation.etape``.
#
# Additif et réversible : aucune donnée existante n'est touchée. L'enum
# historique ``Installation.statut`` (7 étapes + héritées) est CONSERVÉ tel
# quel — ``StageModele.statut_legacy`` fait le pont pour que les effets de
# bord existants (stock à « Installé », garantie/parc à « Réceptionné »)
# continuent de tirer sur les gates mappés. Migration écrite À LA MAIN,
# strictement cohérente avec les modèles (aucun makemigrations).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('installations', '0048_dc40_equipe_canonique'),
    ]

    operations = [
        migrations.CreateModel(
            name='StageModele',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('cle', models.CharField(max_length=40)),
                ('libelle', models.CharField(max_length=120)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('bloquant', models.BooleanField(default=False)),
                ('exige_checklist', models.BooleanField(default=False)),
                ('exige_photos', models.BooleanField(default=False)),
                ('exige_series', models.BooleanField(default=False)),
                ('exige_tests', models.BooleanField(default=False)),
                ('exige_materiel', models.BooleanField(default=False)),
                ('exige_dossier', models.BooleanField(default=False)),
                ('exige_pack', models.BooleanField(default=False)),
                ('statut_legacy', models.CharField(
                    blank=True,
                    choices=[
                        ('signe', 'Signé'),
                        ('materiel_commande', 'Matériel commandé'),
                        ('planifie', 'Planifié'),
                        ('en_cours', 'En cours'),
                        ('installe', 'Installé'),
                        ('receptionne', 'Réceptionné'),
                        ('cloture', 'Clôturé'),
                        ('a_planifier', 'À planifier'),
                        ('pose_en_cours', 'Pose en cours'),
                        ('pose', 'Posé'),
                        ('raccordement_onee', 'Raccordement ONEE'),
                        ('mise_en_service', 'Mise en service'),
                    ],
                    max_length=20, null=True)),
                ('actif', models.BooleanField(default=True)),
                ('protege', models.BooleanField(default=False)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stages_chantier',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Étape de chantier (gate)',
                'verbose_name_plural': 'Étapes de chantier (gates)',
                'ordering': ['ordre', 'id'],
                'unique_together': {('company', 'cle')},
            },
        ),
        migrations.AddField(
            model_name='installation',
            name='etape',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='chantiers',
                to='installations.stagemodele'),
        ),
    ]
