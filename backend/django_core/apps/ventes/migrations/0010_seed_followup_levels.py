"""Niveaux de relance par défaut (J+7 / J+15 / J+30) par société existante.

Idempotent : get_or_create par (company, ordre). Réversible (no-op au retour).
Le founder peut les modifier dans Paramètres.
"""
from django.db import migrations

DEFAULTS = [
    (1, 'Rappel courtois', 7,
     "Bonjour, sauf erreur de notre part, la facture ci-dessus reste en "
     "attente de règlement. Merci de votre retour."),
    (2, 'Relance', 15,
     "Malgré notre précédent rappel, votre facture demeure impayée. "
     "Merci de procéder au règlement dans les meilleurs délais."),
    (3, 'Relance ferme', 30,
     "Votre facture est en retard de paiement important. À défaut de "
     "règlement, nous serons contraints d'envisager des mesures de "
     "recouvrement."),
]


def seed(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    FollowupLevel = apps.get_model('ventes', 'FollowupLevel')
    companies = list(Company.objects.all()) or [None]
    for company in companies:
        for ordre, nom, delai, message in DEFAULTS:
            FollowupLevel.objects.get_or_create(
                company=company, ordre=ordre,
                defaults={'nom': nom, 'delai_jours': delai, 'message': message})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0009_facture_exclu_relances_facture_prochaine_relance_and_more'),
        ('authentication', '0001_initial'),
    ]

    operations = [migrations.RunPython(seed, noop)]
