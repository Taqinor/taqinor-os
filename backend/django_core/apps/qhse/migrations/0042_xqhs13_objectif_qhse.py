import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0041_xqhs12_reunion_qhse'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ObjectifQhse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domaine', models.CharField(choices=[('qualite', 'Qualité'), ('securite', 'Sécurité'), ('environnement', 'Environnement'), ('esg', 'ESG')], default='qualite', max_length=15, verbose_name='Domaine')),
                ('intitule', models.CharField(max_length=255, verbose_name='Intitulé')),
                ('indicateur_libre', models.CharField(blank=True, default='', max_length=255, verbose_name='Indicateur (libre)')),
                ('valeur_baseline', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='Valeur de référence (baseline)')),
                ('annee_baseline', models.PositiveIntegerField(blank=True, null=True, verbose_name='Année de base')),
                ('valeur_cible', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='Valeur cible')),
                ('echeance', models.DateField(blank=True, null=True, verbose_name='Échéance')),
                ('sens_amelioration', models.CharField(choices=[('hausse', 'Hausse souhaitée'), ('baisse', 'Baisse souhaitée')], default='hausse', max_length=10, verbose_name="Sens d'amélioration")),
                ('frequence_revue', models.CharField(choices=[('mensuelle', 'Mensuelle'), ('trimestrielle', 'Trimestrielle'), ('semestrielle', 'Semestrielle'), ('annuelle', 'Annuelle')], default='trimestrielle', max_length=15, verbose_name='Fréquence de revue')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_objectifs', to='authentication.company', verbose_name='Société')),
                ('indicateur_esg', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='objectifs', to='qhse.indicateuresg', verbose_name='Indicateur ESG lié')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_objectifs', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
            ],
            options={
                'verbose_name': 'Objectif QHSE',
                'verbose_name_plural': 'Objectifs QHSE',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='RevueObjectif',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('periode', models.CharField(blank=True, default='', max_length=30, verbose_name='Période')),
                ('date_revue', models.DateField(blank=True, null=True, verbose_name='Date de revue')),
                ('valeur_constatee', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='Valeur constatée')),
                ('atteint', models.BooleanField(blank=True, null=True, verbose_name='Atteint')),
                ('commentaire', models.TextField(blank=True, default='', verbose_name='Commentaire')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_revues_objectif', to='authentication.company', verbose_name='Société')),
                ('objectif', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revues', to='qhse.objectifqhse', verbose_name='Objectif')),
            ],
            options={
                'verbose_name': "Revue d'objectif",
                'verbose_name_plural': "Revues d'objectif",
                'ordering': ['-date_revue', '-id'],
            },
        ),
    ]
