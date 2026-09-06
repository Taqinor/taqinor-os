"""AUD836 — la datation de l'argent suit le jour MAROCAIN, plus le jour UTC.

Django vivait en UTC (`settings.TIME_ZONE = 'UTC'`) pendant que le métier et le
scheduler vivaient à Casablanca (`erp_agentique/celery.py` : « toute la logique
de temps des jobs raisonne en Africa/Casablanca »). `timezone.localdate()`
rendait donc la date UTC : la bascule de jour avait lieu à 01 h 00 locale, et un
paiement carte capturé à 00 h 30 heure du Maroc était daté DE LA VEILLE
(`apps/ventes/receivers.py`, `date_paiement=timezone.localdate()`).

ROUGE D'ABORD, rejouable : à 23 h 30 UTC le 1ᵉʳ janvier, il est 00 h 30 le
2 janvier à Casablanca. Avec l'ancien réglage `timezone.localdate()` rendait
`2026-01-01` (la veille) ; il rend désormais `2026-01-02`. Le premier test
ci-dessous mesure LES DEUX interprétations côte à côte, donc il aurait échoué
avant le correctif et prouve le sens de la bascule après.

Janvier est hors Ramadan : le Maroc est à UTC+1, sans ambiguïté.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_aud836_fuseau_casablanca -v 2
"""
import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from authentication.models import Company
from core import payment as core_payment
from core.dates import aujourd_hui_local
from testkit.time import frozen

#: 1ᵉʳ janvier 2026, 23 h 30 UTC = 2 janvier 00 h 30 à Casablanca (UTC+1).
MINUIT_PASSE_AU_MAROC = '2026-01-01 23:30:00'
JOUR_MAROCAIN = dt.date(2026, 1, 2)
JOUR_UTC = dt.date(2026, 1, 1)


class FuseauActifTests(TestCase):
    def test_le_fuseau_actif_est_celui_du_metier(self):
        self.assertEqual(settings.TIME_ZONE, 'Africa/Casablanca')
        # Le stockage reste UTC : seule l'interprétation locale change.
        self.assertTrue(settings.USE_TZ)

    def test_a_00h30_marocain_la_date_du_jour_est_marocaine(self):
        with frozen(MINUIT_PASSE_AU_MAROC):
            # L'horloge est FIGÉE : `instant_utc` n'est pas une lecture vive
            # (YTEST15), c'est la même seconde que `localdate()` ci-dessous.
            instant_utc = timezone.now().astimezone(dt.timezone.utc)
            self.assertEqual(timezone.localdate(), JOUR_MAROCAIN)
            # L'ancien comportement, mesuré côte à côte : la date UTC est
            # encore la VEILLE — c'est exactement le jour de retard corrigé.
            self.assertEqual(instant_utc.date(), JOUR_UTC)

    def test_le_reglage_et_le_helper_metier_disent_la_meme_chose(self):
        """CRX26 (`core.dates.aujourd_hui_local`) et `timezone.localdate()` se
        contredisaient une heure par nuit ; ils coïncident désormais."""
        with frozen(MINUIT_PASSE_AU_MAROC):
            self.assertEqual(aujourd_hui_local(), timezone.localdate())
        with frozen('2026-01-01 12:00:00'):
            self.assertEqual(aujourd_hui_local(), timezone.localdate())

    def test_le_fuseau_actif_est_celui_du_scheduler(self):
        """Le beat Celery est explicitement planifié à Casablanca : Django ne
        doit plus raisonner dans un autre fuseau que son propre scheduler."""
        from erp_agentique.celery import app as celery_app

        self.assertEqual(str(celery_app.conf.timezone), settings.TIME_ZONE)
        self.assertEqual(
            timezone.get_current_timezone(), ZoneInfo(settings.TIME_ZONE))


class PaiementCarteDeMinuitTests(TestCase):
    """Le site ancré par le constat : `receivers.py` → `date_paiement`."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aud836-co', defaults={'nom': 'AUD836 Co'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD836',
            email='aud836@example.invalid', telephone='+212600000836')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-AUD836',
            prix_vente=Decimal('5000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD836-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('5000'), taux_tva=Decimal('20.00'))

    def test_un_paiement_capture_a_00h30_est_date_du_jour_marocain(self):
        with frozen(MINUIT_PASSE_AU_MAROC):
            tx = core_payment.creer_transaction(
                self.company, montant=Decimal('6000'), target=self.facture)
            core_payment.marquer_paye(tx, external_ref='PSP-AUD836')

        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(paiement.date_paiement, JOUR_MAROCAIN)
        self.assertNotEqual(paiement.date_paiement, JOUR_UTC)
