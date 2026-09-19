import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModeleML',
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
                    'nom',
                    models.CharField(
                        choices=[
                            ('churn', 'Risque de churn'),
                            ('win_proba', 'Probabilité de gain (devis)'),
                            ('retard_paiement', 'Retard de paiement'),
                            ('reappro', 'Réapprovisionnement (seuil stock)'),
                            ('anomalie', "Détection d'anomalie"),
                        ],
                        max_length=20),
                ),
                ('version', models.PositiveIntegerField(default=1)),
                ('params_json', models.JSONField(blank=True, default=dict)),
                ('actif', models.BooleanField(default=False)),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='mlops_modeleml_set',
                        to='authentication.company',
                        verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Version de modèle ML',
                'verbose_name_plural': 'Versions de modèle ML',
                'ordering': ['nom', '-version'],
            },
        ),
        migrations.AddIndex(
            model_name='modeleml',
            index=models.Index(
                fields=['company', 'nom'], name='mlops_modele_co_nom_idx'),
        ),
        migrations.AddConstraint(
            model_name='modeleml',
            constraint=models.UniqueConstraint(
                fields=('company', 'nom', 'version'),
                name='uniq_mlops_modele_co_nom_ver'),
        ),
        migrations.AddConstraint(
            model_name='modeleml',
            constraint=models.UniqueConstraint(
                condition=models.Q(('actif', True)),
                fields=('company', 'nom'),
                name='uniq_mlops_modele_actif'),
        ),
    ]
