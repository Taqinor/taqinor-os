"""ACAL278 (C-ACAL-142) — ``from-layout`` (et ``auto``, qui portait la MÊME
copie de ``_dec``) refuse une remise ou une TVA non finie ou hors bornes en
400 NOMMÉ, jamais un 500.

ROUGE AVANT : ``POST ventes/devis/from-layout/ {remise_globale: '150'}``
passait ``Decimal('150')`` tel quel au service ; l'insert heurtait la
contrainte ``ck_devis_remise_globale_0_100`` (``ventes/models.py``) →
IntegrityError → 500. ``taux_tva: 'NaN'`` / ``'1e999'`` passaient aussi le
``Decimal(str(raw))`` sans borne. Réversion (test-du-test) : rétablir
``Decimal(str(raw))`` sans borne dans ``_pourcentage_saisi`` ⇒ ces tests
échouent.

Règle (même que calepinage ``_montants``, bornée) : fini, 0..100, au plus
2 décimales (``DecimalField(max_digits=5, decimal_places=2)``). Les deux
``def _dec`` imbriqués sont remplacés par UNE fonction de module,
``views/devis_gardes._pourcentage_saisi``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_from_layout_montants"
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.crm.models import Lead
from apps.ventes.models import Devis
from apps.ventes.tests.test_from_layout_endpoint import (
    FROM_LAYOUT_URL, SAMPLE_LAYOUT, auth_client, make_company, make_user,
    seed_catalogue,
)

AUTO_URL = '/api/django/ventes/devis/auto/'


class PourcentageSaisi(SimpleTestCase):
    """La fonction de module elle-même (aucune base)."""

    def _f(self, valeur, defaut=Decimal('20')):
        from apps.ventes.views.devis_gardes import _pourcentage_saisi
        return _pourcentage_saisi({'taux_tva': valeur}, 'taux_tva', defaut)

    def test_absent_ou_vide_rend_le_defaut(self):
        self.assertEqual(self._f(None), (Decimal('20'), None))
        self.assertEqual(self._f(''), (Decimal('20'), None))

    def test_valeurs_valides(self):
        for brut, attendu in (('0', Decimal('0')), ('100', Decimal('100')),
                              ('12.5', Decimal('12.5')), (7, Decimal('7')),
                              ('20.00', Decimal('20.00'))):
            with self.subTest(brut=brut):
                self.assertEqual(self._f(brut), (attendu, None))

    def test_refus_nommes(self):
        for brut in ('NaN', 'nan', 'Infinity', '-Infinity', '1e999', '150',
                     '-1', '100.01', '5.123', 'abc', [], {}, True):
            with self.subTest(brut=brut):
                valeur, erreur = self._f(brut)
                self.assertIsNone(valeur)
                self.assertEqual(list(erreur), ['taux_tva'])
                self.assertTrue(erreur['taux_tva'])


class FromLayoutMontants(TestCase):

    def setUp(self):
        self.company = make_company('acal278-co')
        self.user = make_user(self.company, 'acal278user')
        self.api = auth_client(self.user)
        seed_catalogue(self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Acal', prenom='278',
            email='acal278@ex.com')

    def _post(self, **montants):
        corps = {'layout': SAMPLE_LAYOUT, 'lead': self.lead.id}
        corps.update(montants)
        return self.api.post(FROM_LAYOUT_URL, corps, format='json')

    def test_remise_hors_bornes_400(self):
        avant = Devis.objects.count()
        resp = self._post(remise_globale='150')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('remise_globale', resp.data)
        self.assertEqual(Devis.objects.count(), avant)

    def test_taux_tva_nan_400(self):
        avant = Devis.objects.count()
        resp = self._post(taux_tva='NaN')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('taux_tva', resp.data)
        self.assertEqual(Devis.objects.count(), avant)

    def test_taux_tva_infini_400(self):
        avant = Devis.objects.count()
        resp = self._post(taux_tva='1e999')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('taux_tva', resp.data)
        self.assertEqual(Devis.objects.count(), avant)

    def test_trois_decimales_400(self):
        resp = self._post(remise_globale='5.125')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('remise_globale', resp.data)

    def test_valeurs_valides_creent_le_devis(self):
        resp = self._post(remise_globale='12.5', taux_tva='10')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.remise_globale, Decimal('12.50'))
        self.assertEqual(devis.taux_tva, Decimal('10.00'))


class AutoMontants(TestCase):
    """``auto`` portait la seconde copie de ``_dec`` : même refus nommé."""

    def setUp(self):
        self.company = make_company('acal278-auto-co')
        self.user = make_user(self.company, 'acal278auto')
        self.api = auth_client(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='Auto', prenom='278',
            email='acal278auto@ex.com')

    def test_remise_hors_bornes_400(self):
        avant = Devis.objects.count()
        resp = self.api.post(
            AUTO_URL, {'lead': self.lead.id, 'remise_globale': '150'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('remise_globale', resp.data)
        self.assertEqual(Devis.objects.count(), avant)

    def test_taux_tva_nan_400(self):
        resp = self.api.post(
            AUTO_URL, {'lead': self.lead.id, 'taux_tva': 'NaN'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('taux_tva', resp.data)
