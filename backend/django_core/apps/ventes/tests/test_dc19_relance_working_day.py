"""DC19 — la prochaine relance auto d'une facture tombe sur un JOUR OUVRÉ.

Quand relance_reminders avance la date de relance au niveau suivant, la date
est reportée au prochain jour ouvré de la société (par défaut Lun–Ven) via le
référentiel calendrier partagé — on ne relance jamais un client un week-end.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, FollowupLevel, LigneFacture
from apps.ventes import scheduled

User = get_user_model()


def _company():
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug='dc19v-co', defaults={'nom': 'DC19V Co'})
    return c


class TestDC19RelanceWorkingDay(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='dc19v_u', password='x', role_legacy='responsable',
            company=self.company)
        self.cl = Client.objects.create(
            company=self.company, nom='Deb', prenom='DC19',
            email='dc19v@example.com', telephone='+212600000191')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-DC19V',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20'))
        # Deux niveaux : le scheduler avancera la date au 2e niveau.
        for ordre, nom, delai in [(1, 'Rappel', 7), (2, 'Relance', 15)]:
            FollowupLevel.objects.create(
                company=self.company, ordre=ordre, nom=nom, delai_jours=delai)
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-DC19V-1', client=self.cl,
            statut=Facture.Statut.EN_RETARD, taux_tva=Decimal('20'),
            date_echeance=date.today() - timedelta(days=45),
            prochaine_relance=date.today())
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20'))

    def test_next_relance_is_a_working_day(self):
        scheduled.relance_reminders()
        self.facture.refresh_from_db()
        # Après la 1re relance, une date de 2e relance est programmée…
        self.assertIsNotNone(self.facture.prochaine_relance)
        # …et elle tombe un jour ouvré (Lun–Ven, config par défaut).
        self.assertLess(
            self.facture.prochaine_relance.weekday(), 5,
            "la prochaine relance ne doit jamais tomber un week-end (DC19)")
