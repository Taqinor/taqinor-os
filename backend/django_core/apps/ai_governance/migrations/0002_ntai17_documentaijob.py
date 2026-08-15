# NTAI17 — File de traitement document AI (classification + extraction).
#
# CHAÎNE DE MIGRATIONS : enchaîne EXPLICITEMENT sur `0001_initial` de cette app
# (jamais un redépart) et ne dépend de la GED que par `0001_initial` — la
# migration qui CRÉE `ged.Document` —, pour ne pas entrer en collision avec les
# migrations GED que d'autres lanes ajoutent en parallèle.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('ged', '0001_initial'),
        ('ai_governance', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentAiJob',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'categorie',
                    models.CharField(
                        blank=True, default='',
                        help_text='Catégorie détectée par la classification '
                                  '(GED34).',
                        max_length=60),
                ),
                (
                    'schema',
                    models.CharField(
                        blank=True, default='',
                        help_text="Gabarit d'extraction retenu pour la "
                                  "catégorie détectée.",
                        max_length=60),
                ),
                (
                    'statut',
                    models.CharField(
                        choices=[('en_attente', 'En attente'),
                                 ('traite', 'Traité'),
                                 ('erreur', 'Erreur')],
                        default='en_attente', max_length=20),
                ),
                (
                    'resultat_json',
                    models.JSONField(
                        blank=True, default=dict,
                        help_text='Résultat brut proposé (champs extraits) — '
                                  'jamais appliqué automatiquement à un '
                                  'modèle métier.'),
                ),
                (
                    'confiance',
                    models.FloatField(
                        default=0.0,
                        help_text='Confiance rapportée par le fournisseur '
                                  '(0 = inconnue).'),
                ),
                (
                    'message',
                    models.TextField(
                        blank=True, default='',
                        help_text="Message d'erreur capturé (statut "
                                  "« erreur »)."),
                ),
                ('traite_le', models.DateTimeField(blank=True, null=True)),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
                (
                    'document',
                    models.ForeignKey(
                        help_text='Pièce GED traitée (le job meurt avec elle).',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='ai_jobs', to='ged.document'),
                ),
            ],
            options={
                'verbose_name': 'Traitement IA de document',
                'verbose_name_plural': 'Traitements IA de documents',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='documentaijob',
            index=models.Index(fields=['company', 'statut'],
                               name='ai_gov_docjob_co_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='documentaijob',
            index=models.Index(fields=['company', 'document'],
                               name='ai_gov_docjob_co_doc_idx'),
        ),
    ]
