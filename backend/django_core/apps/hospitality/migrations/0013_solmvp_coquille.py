"""SOLMVP — coquille de migrations de l'app « hospitality ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app hospitality`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate hospitality 0012_reservation_formule_pension_ticketpension`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hospitality', '0012_reservation_formule_pension_ticketpension'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='EvenementBanquet'),
                migrations.DeleteModel(name='FicheClient'),
                migrations.DeleteModel(name='IngredientRecette'),
                migrations.DeleteModel(name='LigneFolio'),
                migrations.DeleteModel(name='MainCourante'),
                migrations.DeleteModel(name='ParametresTaxeSejour'),
                migrations.DeleteModel(name='PlanTarifaire'),
                migrations.DeleteModel(name='TacheMenage'),
                migrations.DeleteModel(name='TicketPension'),
                migrations.DeleteModel(name='Folio'),
                migrations.DeleteModel(name='Recette'),
                migrations.DeleteModel(name='SalleEvenement'),
                migrations.DeleteModel(name='Reservation'),
                migrations.DeleteModel(name='Chambre'),
                migrations.DeleteModel(name='TypeChambre'),
            ],
            database_operations=[],
        ),
    ]
