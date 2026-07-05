import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0045_xqhs16_signalement_public'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ObservationSecurite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_observation', models.DateField(blank=True, null=True, verbose_name="Date de l'observation")),
                ('chantier_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID du chantier')),
                ('categorie', models.CharField(choices=[('epi', 'EPI'), ('hauteur', 'Travail en hauteur'), ('electrique', 'Électrique'), ('manutention', 'Manutention'), ('environnement', 'Environnement'), ('autre', 'Autre')], default='autre', max_length=15, verbose_name='Catégorie')),
                ('type_observation', models.CharField(choices=[('sur', 'Sûr'), ('a_risque', 'À risque')], default='sur', max_length=10, verbose_name="Type d'observation")),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('feedback_donne', models.BooleanField(default=False, verbose_name='Feedback donné sur place')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_observations_securite', to='authentication.company', verbose_name='Société')),
                ('observateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_observations_securite', to=settings.AUTH_USER_MODEL, verbose_name='Observateur')),
                ('action_liee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='observations_origine', to='qhse.actioncorrectivepreventive', verbose_name='CAPA liée')),
                ('non_conformite_liee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='observations_origine', to='qhse.nonconformite', verbose_name='NCR liée')),
            ],
            options={
                'verbose_name': 'Observation sécurité (BBS)',
                'verbose_name_plural': 'Observations sécurité (BBS)',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='observationsecurite',
            index=models.Index(fields=['company', 'type_observation'], name='qhse_obssec_co_type'),
        ),
        migrations.AddIndex(
            model_name='observationsecurite',
            index=models.Index(fields=['company', 'observateur'], name='qhse_obssec_co_observ'),
        ),
    ]
