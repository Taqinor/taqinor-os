"""CIQ511 — le lien public de la proposition vit AU MOINS jusqu'à la validité
du devis (fin du jour, Africa/Casablanca), jamais raccourci ; une validité
prolongée recule les liens vivants (même jeton). Les liens de facture gardent
leurs 30 jours ; l'avis d'expiration reste NEUTRE (N100(c)).

Le temps est GELÉ.
"""
import datetime
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from core.dates import TZ_METIER
from testkit.time import frozen

from apps.crm.models import Client
from apps.ventes.models import SHARE_LINK_TTL_DAYS, Devis, ShareLink

MAINTENANT = datetime.datetime(2026, 10, 6, 10, 0, tzinfo=TZ_METIER)
J = MAINTENANT.date()


def _fin_du_jour(jour):
    return datetime.datetime.combine(
        jour, datetime.time(23, 59, 59), tzinfo=TZ_METIER)


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class LienSuitLaValidite(TestCase):

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CIQ511 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client CIQ511',
            email='ciq511@example.test')
        self.n = 0

    def _devis(self, validite=None, statut=Devis.Statut.ENVOYE):
        self.n += 10
        return Devis.objects.create(
            company=self.company, reference=f'DEV-CIQ511-{self.n:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            date_validite=validite, date_envoi=timezone.now())

    def test_a_validite_j45_lien_jusqu_a_la_fin_de_j45(self):
        devis = self._devis(J + datetime.timedelta(days=45))
        lien = ShareLink.for_devis(devis)
        self.assertEqual(lien.expires_at,
                         _fin_du_jour(J + datetime.timedelta(days=45)))

    def test_b_validite_courte_ou_absente_30_jours_inchange(self):
        for validite in (J + datetime.timedelta(days=14), None):
            with self.subTest(validite=validite):
                devis = self._devis(validite)
                lien = ShareLink.for_devis(devis)
                self.assertEqual(
                    lien.expires_at,
                    timezone.now()
                    + datetime.timedelta(days=SHARE_LINK_TTL_DAYS))

    def test_c_validite_prolongee_meme_jeton_expires_at_recule(self):
        from apps.ventes.services import prolonger_validite_devis
        devis = self._devis(J + datetime.timedelta(days=14))
        lien = ShareLink.for_devis(devis)
        avant = lien.expires_at
        nouvelle = J + datetime.timedelta(days=60)
        self.assertEqual(prolonger_validite_devis(devis, nouvelle), nouvelle)
        lien.refresh_from_db()
        self.assertEqual(lien.expires_at, _fin_du_jour(nouvelle))
        self.assertGreater(lien.expires_at, avant)
        self.assertEqual(ShareLink.for_devis(devis).token, lien.token)

    def test_reutilisation_prolonge_un_lien_qui_expirerait_avant(self):
        devis = self._devis()
        lien = ShareLink.for_devis(devis)
        Devis.objects.filter(pk=devis.pk).update(
            date_validite=J + datetime.timedelta(days=50))
        devis.refresh_from_db()
        reutilise = ShareLink.for_devis(devis)
        self.assertEqual(reutilise.token, lien.token)
        self.assertEqual(reutilise.expires_at,
                         _fin_du_jour(J + datetime.timedelta(days=50)))

    def test_jamais_raccourci(self):
        devis = self._devis(J + datetime.timedelta(days=50))
        lien = ShareLink.for_devis(devis)
        avant = lien.expires_at
        Devis.objects.filter(pk=devis.pk).update(
            date_validite=J + datetime.timedelta(days=5))
        devis.refresh_from_db()
        ShareLink.prolonger_pour_devis(devis)
        lien.refresh_from_db()
        self.assertEqual(lien.expires_at, avant)
        self.assertEqual(ShareLink.for_devis(devis).expires_at, avant)

    def test_d_lien_de_facture_garde_30_jours(self):
        from apps.ventes.models import Facture
        devis = self._devis(J + datetime.timedelta(days=45))
        facture = Facture.objects.create(
            company=self.company, reference='FAC-CIQ511-0001',
            client=self.client_obj, devis=devis, statut='brouillon',
            taux_tva=Decimal('20'))
        lien = ShareLink.for_facture(facture)
        self.assertEqual(
            lien.expires_at,
            timezone.now() + datetime.timedelta(days=SHARE_LINK_TTL_DAYS))

    def test_e_lien_expire_meme_reponse_neutre(self):
        devis = self._devis(J + datetime.timedelta(days=45))
        lien = ShareLink.for_devis(devis)
        api = APIClient()
        with frozen(MAINTENANT + datetime.timedelta(days=46)):
            expire = api.get(f'/api/django/public/proposal/{lien.token}/data/')
            inconnu = api.get('/api/django/public/proposal/inconnu-xyz/data/')
        self.assertEqual(expire.status_code, inconnu.status_code)
        self.assertEqual(expire.content, inconnu.content)
