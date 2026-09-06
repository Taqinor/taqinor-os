"""AUD836 — le balayage des factures en retard bascule à MINUIT marocain.

`apps/automation/beat_tasks.py` compare `date_echeance__lt=timezone.localdate()`
et le beat Celery est planifié en Africa/Casablanca
(`erp_agentique/celery.py`). Tant que Django vivait en UTC, la « journée » du
balayage commençait à 01 h 00 locale : une facture échue la veille au soir
n'était vue qu'une heure trop tard, et le marqueur d'idempotence quotidien
(AUD822, clé datée) portait la date de la veille pendant cette heure-là.

ROUGE D'ABORD, rejouable : à 23 h 30 UTC le 1ᵉʳ janvier il est déjà le 2 à
Casablanca. Avec l'ancien réglage la fenêtre de balayage restait celle du 1ᵉʳ
(une facture échue le 1ᵉʳ n'était PAS en retard) ; elle est désormais celle du
2, et la facture est vue.

Run :
    docker compose exec django_core python manage.py test \
        apps.automation.test_aud836_fuseau_casablanca -v 2
"""
import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes.models import Facture
from authentication.models import Company
from testkit.time import frozen

MINUIT_PASSE_AU_MAROC = '2026-01-01 23:30:00'
JOUR_MAROCAIN = dt.date(2026, 1, 2)


class FenetreDuBalayageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aud836-auto-co', defaults={'nom': 'AUD836 Automation'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD836A',
            email='aud836a@example.invalid', telephone='+212600000837')
        # Échue le 1ᵉʳ janvier : en retard dès le 2 au matin, heure du Maroc.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD836A-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            date_echeance=dt.date(2026, 1, 1), montant_ttc=Decimal('1000'))

    def test_a_00h30_marocain_la_facture_echue_la_veille_est_en_retard(self):
        with frozen(MINUIT_PASSE_AU_MAROC):
            today = timezone.localdate()
            self.assertEqual(today, JOUR_MAROCAIN)
            en_retard = Facture.objects.filter(
                company=self.company,
                date_echeance__lt=today,
            ).exclude(statut='payee')
            self.assertIn(self.facture, list(en_retard))

    def test_le_marqueur_du_jour_porte_la_date_marocaine(self):
        """AUD822 — le marqueur d'idempotence est clé-daté : avec la date UTC
        il rejouait la journée précédente pendant l'heure 23 h-minuit."""
        with frozen(MINUIT_PASSE_AU_MAROC):
            self.assertEqual(timezone.localdate().isoformat(), '2026-01-02')
