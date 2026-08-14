# NTLOG36 - ParametresDouane (reglages singleton par societe).
import django.db.models.deletion
import apps.douane.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        ('douane', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresDouane',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('regime_douanier_par_defaut', models.CharField(choices=[('mise_consommation', 'Mise à la consommation'), ('admission_temporaire', 'Admission temporaire'), ('entrepot_douane', 'Entrepôt sous douane'), ('transit', 'Transit'), ('perfectionnement_actif', 'Perfectionnement actif')], default='mise_consommation', max_length=24)),
                ('alerte_expiration_jours', models.JSONField(default=apps.douane.models._defaut_alerte_jours)),
                ('mention_estimation_droits', models.TextField(blank=True, default='Estimation — non contractuelle, barème à vérifier à jour.')),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='douane_parametres', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Paramètres douane',
                'verbose_name_plural': 'Paramètres douane',
            },
        ),
    ]
