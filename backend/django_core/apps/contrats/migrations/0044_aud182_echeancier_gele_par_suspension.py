# AUD182 — marque de gel « suspension pour impayé » sur EcheancierContrat.
#
# `_appliquer_suspension_impaye` ne faisait que changer `Contrat.statut`, sans
# jamais toucher `EcheancierContrat.facturation_active` — or le beat quotidien
# ne filtre QUE sur l'échéancier, jamais sur `contrat.statut` : un contrat
# suspendu pour impayé continuait à produire une facture ÉMISE chaque nuit.
#
# Le champ est ADDITIF avec un défaut booléen déjà connu de Django pour les
# lignes existantes (False = « pas gelé par une suspension »), donc aucune
# reprise de données et aucun comportement modifié rétroactivement.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0043_aud181_taux_tva'),
    ]

    operations = [
        migrations.AddField(
            model_name='echeanciercontrat',
            name='gele_par_suspension',
            field=models.BooleanField(
                default=False,
                verbose_name='Gelé par une suspension pour impayé'),
        ),
    ]
