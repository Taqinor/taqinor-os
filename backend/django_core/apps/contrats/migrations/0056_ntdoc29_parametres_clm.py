"""NTDOC29 — Reglages du cycle de vie contractuel (CLM) par societe.

Purement ADDITIF (creation de table) et revertable : aucune donnee existante
n'est touchee, aucun champ existant n'est modifie. Les valeurs par defaut
reproduisent EXACTEMENT le comportement d'avant (garde stricte NTDOC4 active,
negociation non obligatoire, aucune relance de parapheur), donc une societe
qui n'ouvre jamais l'ecran ne voit rien changer.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('contrats', '0055_ntdoc20_parametre_renouvellement'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresCLM',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resolution_commentaires_obligatoire', models.BooleanField(default=True, help_text='NTDOC4 — exiger que TOUS les commentaires de redline soient résolus avant de clôturer une négociation (comportement historique : activé).', verbose_name='Résolution des commentaires obligatoire')),
                ('negociation_obligatoire_avant_signature', models.BooleanField(default=False, help_text="Interdire le passage direct « brouillon → en approbation » : un round de négociation devient obligatoire (comportement historique : désactivé).", verbose_name='Négociation obligatoire avant approbation')),
                ('duree_defaut_expiration_salle_donnees_jours', models.PositiveIntegerField(default=30, help_text="NTDOC11-16 — durée proposée à la création d'une salle de données.", verbose_name="Durée de vie par défaut d'une salle de données (jours)")),
                ('parapheur_notification_quotidienne', models.BooleanField(default=False, help_text='NTDOC7/NTDOC34 — envoyer au dirigeant un récapitulatif quotidien de son parapheur (comportement historique : aucune relance).', verbose_name='Relance quotidienne du parapheur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Paramètres CLM',
                'verbose_name_plural': 'Paramètres CLM',
            },
        ),
        migrations.AddConstraint(
            model_name='parametresclm',
            constraint=models.UniqueConstraint(fields=('company',), name='contrats_parametresclm_uniq_co'),
        ),
    ]
