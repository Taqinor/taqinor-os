"""NTSUB24 — Reglages « Facturation recurrente » par societe.

Les seuils/delais du groupe NTSUB (J-3 fin d'essai NTSUB5, 30 jours avant
expiration de carte NTSUB9, 80 % d'un quota d'usage NTSUB18) etaient des
constantes codees en dur. Ce modele singleton par societe les rend reglables,
avec des valeurs par defaut STRICTEMENT egales aux constantes historiques :
une societe sans reglage explicite garde exactement le comportement actuel.

Purement ADDITIF (creation de table) et revertable : aucune donnee existante
n'est touchee, aucun champ existant n'est modifie.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('contrats', '0050_ntdoc4_statut_en_negociation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresAbonnement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('jours_alerte_fin_essai', models.PositiveIntegerField(default=3, help_text="NTSUB5 — nombre de jours avant la fin d'essai auquel le responsable est prévenu (défaut historique : 3).", verbose_name="Alerte avant fin d'essai (jours)")),
                ('jours_alerte_expiration_carte', models.PositiveIntegerField(default=30, help_text='NTSUB9 — délai de prévenance avant expiration du moyen de paiement (défaut historique : 30).', verbose_name='Alerte avant expiration de carte (jours)')),
                ('seuil_alerte_usage_pct_defaut', models.PositiveIntegerField(default=80, help_text="NTSUB18 — pourcentage du quota d'usage à partir duquel une alerte est levée (défaut historique : 80).", verbose_name="Seuil d'alerte d'usage par défaut (%)")),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('sequence_dunning_defaut', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='parametres_par_defaut', to='contrats.sequencedunning', verbose_name='Séquence de dunning par défaut')),
            ],
            options={
                'verbose_name': 'Paramètres abonnement',
                'verbose_name_plural': 'Paramètres abonnement',
            },
        ),
        migrations.AddConstraint(
            model_name='parametresabonnement',
            constraint=models.UniqueConstraint(fields=('company',), name='contrats_parametresabo_uniq_co'),
        ),
    ]
