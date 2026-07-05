import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0053_xqhs24_demande_changement'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VeilleReglementaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texte_suivi', models.CharField(max_length=255, verbose_name='Texte réglementaire suivi')),
                ('source', models.CharField(blank=True, default='', max_length=255, verbose_name='Source (BO / ministère)')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('cadence_jours', models.PositiveIntegerField(default=90, verbose_name='Cadence de revue (jours)')),
                ('date_derniere_revue', models.DateField(blank=True, null=True, verbose_name='Dernière revue')),
                ('date_prochaine_revue', models.DateField(blank=True, null=True, verbose_name='Prochaine revue')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_veilles_reglementaires', to='authentication.company', verbose_name='Société')),
                ('registre_conformite', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='veilles_reglementaires', to='qhse.conformiteenvironnementale', verbose_name='Entrée du registre légal liée')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_veilles_reglementaires', to=settings.AUTH_USER_MODEL, verbose_name='Responsable HSE')),
            ],
            options={
                'verbose_name': 'Veille réglementaire',
                'verbose_name_plural': 'Veilles réglementaires',
                'ordering': ['date_prochaine_revue', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='veillereglementaire',
            index=models.Index(fields=['company', 'date_prochaine_revue'], name='qhse_veille_co_prochaine'),
        ),
        migrations.CreateModel(
            name='RevueVeilleReglementaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_echeance', models.DateField(blank=True, null=True, verbose_name='Échéance de la revue')),
                ('date_revue', models.DateField(blank=True, null=True, verbose_name='Date de revue effective')),
                ('conclusion', models.CharField(choices=[('a_faire', 'À faire'), ('applicable', 'Applicable'), ('non_applicable', 'Non applicable')], default='a_faire', max_length=15, verbose_name='Conclusion')),
                ('impact_evalue', models.TextField(blank=True, default='', verbose_name='Impact évalué')),
                ('resume_ia', models.TextField(blank=True, default='', verbose_name='Résumé IA du changement (XQHS25, optionnel)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_revues_veille', to='authentication.company', verbose_name='Société')),
                ('veille', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revues', to='qhse.veillereglementaire', verbose_name='Veille réglementaire')),
            ],
            options={
                'verbose_name': 'Revue de veille réglementaire',
                'verbose_name_plural': 'Revues de veille réglementaire',
                'ordering': ['-date_echeance', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='revueveillereglementaire',
            index=models.Index(fields=['company', 'conclusion'], name='qhse_revveille_co_concl'),
        ),
    ]
