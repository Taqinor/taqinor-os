# Generated 2026-06-30 — FG192 Éléments variables de paie (export)
#
# Entièrement additive : ``CreateModel`` (``ElementsVariablesPaie``) +
# contrainte d'unicité + index nommés — réversible. Bordereau MENSUEL par
# employé destiné au prestataire de paie (pas un moteur de paie) : heures
# normales/supp, jours d'absence/congés, primes, retenues, commentaire, statut
# (brouillon → validé → exporté) + date d'export posée côté serveur. Le couple
# (employe, annee, mois) est unique. Société posée côté serveur. RUNTIME-SAFETY :
# statut borné ≤ 20 ; montants/quantités en DecimalField ; index nommés (≤ 30).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0029_sanction'),
    ]

    operations = [
        migrations.CreateModel(
            name='ElementsVariablesPaie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('annee', models.PositiveIntegerField(verbose_name='Année')),
                ('mois', models.PositiveSmallIntegerField(verbose_name='Mois')),
                ('heures_normales', models.DecimalField(decimal_places=2, default=0, max_digits=7, verbose_name='Heures normales')),
                ('heures_supp', models.DecimalField(decimal_places=2, default=0, max_digits=7, verbose_name='Heures supplémentaires')),
                ('jours_absence', models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name="Jours d'absence")),
                ('jours_conges', models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Jours de congés')),
                ('primes', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Primes/indemnités (total)')),
                ('retenues', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Retenues (total)')),
                ('commentaire', models.TextField(blank=True, default='', verbose_name='Commentaire')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('valide', 'Validé'), ('exporte', 'Exporté')], default='brouillon', max_length=20, verbose_name='Statut')),
                ('date_export', models.DateTimeField(blank=True, null=True, verbose_name='Exporté le')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_elements_variables_paie', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements_variables_paie', to='rh.dossieremploye', verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Éléments variables de paie',
                'verbose_name_plural': 'Éléments variables de paie',
                'ordering': ['-annee', '-mois', 'employe'],
            },
        ),
        migrations.AddConstraint(
            model_name='elementsvariablespaie',
            constraint=models.UniqueConstraint(fields=('employe', 'annee', 'mois'), name='rh_evp_emp_an_mois_uniq'),
        ),
        migrations.AddIndex(
            model_name='elementsvariablespaie',
            index=models.Index(fields=['company', 'annee', 'mois'], name='rh_evp_comp_an_mois_idx'),
        ),
        migrations.AddIndex(
            model_name='elementsvariablespaie',
            index=models.Index(fields=['company', 'statut'], name='rh_evp_comp_stat_idx'),
        ),
    ]
