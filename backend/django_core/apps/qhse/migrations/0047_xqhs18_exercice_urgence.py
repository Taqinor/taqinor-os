import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0046_xqhs17_observation_securite'),
    ]

    operations = [
        migrations.AddField(
            model_name='planurgence',
            name='frequence_mois',
            field=models.PositiveIntegerField(
                default=12, verbose_name="Fréquence cible des exercices (mois)"),
        ),
        migrations.CreateModel(
            name='ExerciceUrgence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_exercice', models.CharField(choices=[('evacuation', 'Évacuation'), ('incendie', 'Incendie'), ('deversement', 'Déversement'), ('autre', 'Autre')], default='evacuation', max_length=15, verbose_name="Type d'exercice")),
                ('date_prevue', models.DateField(blank=True, null=True, verbose_name='Date prévue')),
                ('date_realisee', models.DateField(blank=True, null=True, verbose_name='Date réalisée')),
                ('duree_evacuation_secondes', models.PositiveIntegerField(blank=True, null=True, verbose_name="Durée d'évacuation chronométrée (secondes)")),
                ('nb_participants', models.PositiveIntegerField(blank=True, null=True, verbose_name='Nombre de participants')),
                ('participants_libre', models.TextField(blank=True, default='', verbose_name='Participants (liste libre)')),
                ('observations', models.TextField(blank=True, default='', verbose_name='Observations / écarts')),
                ('statut', models.CharField(choices=[('planifie', 'Planifié'), ('realise', 'Réalisé'), ('annule', 'Annulé')], default='planifie', max_length=10, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_exercices_urgence', to='authentication.company', verbose_name='Société')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exercices', to='qhse.planurgence', verbose_name="Plan d'urgence")),
                ('capa_liee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exercices_urgence_origine', to='qhse.actioncorrectivepreventive', verbose_name='CAPA liée')),
            ],
            options={
                'verbose_name': "Exercice d'urgence",
                'verbose_name_plural': "Exercices d'urgence",
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='exerciceurgence',
            index=models.Index(fields=['company', 'plan'], name='qhse_exeurg_co_plan'),
        ),
        migrations.AddIndex(
            model_name='exerciceurgence',
            index=models.Index(fields=['company', 'statut'], name='qhse_exeurg_co_statut'),
        ),
    ]
