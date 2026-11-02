"""AARG24 (C-AARG-019) — réécrit les niveaux de relance encore à l'ANCIEN texte
exact semé par ``ventes/0010_seed_followup_levels`` : les nouveaux disent ce qui
est dû (``{reference}``, ``{montant_du}``, ``{date_echeance}``), sans
« ci-dessus » ni salutation. Un message personnalisé (texte différent) n'est
jamais touché. Réversible : le retour remet l'ancien texte aux seuls niveaux qui
portent le nouveau.
"""
from django.db import migrations

ANCIENS_NOUVEAUX = (
    ("Bonjour, sauf erreur de notre part, la facture ci-dessus reste en "
     "attente de règlement. Merci de votre retour.",
     "Sauf erreur de notre part, la facture {reference} reste en attente de "
     "règlement : {montant_du} MAD dus (échéance : {date_echeance}). "
     "Merci de votre retour."),
    ("Malgré notre précédent rappel, votre facture demeure impayée. "
     "Merci de procéder au règlement dans les meilleurs délais.",
     "Malgré notre précédent rappel, la facture {reference} demeure impayée : "
     "{montant_du} MAD dus (échéance : {date_echeance}). "
     "Merci de procéder au règlement dans les meilleurs délais."),
    ("Votre facture est en retard de paiement important. À défaut de "
     "règlement, nous serons contraints d'envisager des mesures de "
     "recouvrement.",
     "La facture {reference} est en retard de paiement important : "
     "{montant_du} MAD dus (échéance : {date_echeance}). À défaut de "
     "règlement, nous serons contraints d'envisager des mesures de "
     "recouvrement."),
)


def reecrire(apps, schema_editor):
    FollowupLevel = apps.get_model('facturation', 'FollowupLevel')
    for ancien, nouveau in ANCIENS_NOUVEAUX:
        FollowupLevel.objects.filter(message=ancien).update(message=nouveau)


def retablir(apps, schema_editor):
    FollowupLevel = apps.get_model('facturation', 'FollowupLevel')
    for ancien, nouveau in ANCIENS_NOUVEAUX:
        FollowupLevel.objects.filter(message=nouveau).update(message=ancien)


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0026_aarg22_facture_contestee'),
    ]

    operations = [migrations.RunPython(reecrire, retablir)]
