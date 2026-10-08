"""ASTK182 — la porte COMPTE fournisseur de la confirmation de BCF rend les
400/409 nommés du cœur stock (ASTK180/ASTK181) : plus de parse local, plus de
troncature silencieuse ``[:100]``.

Source réelle : route compte réelle + vue publique jeton réelle — aucun mock.

Run :
    python manage.py test apps.portail.tests.test_astk_confirmation_compte -v 2
"""
import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.portail.tests.test_ntprt21_mes_bcf import (
    make_bcf, make_company, make_fournisseur, make_portal_user, url_confirmer,
)
from apps.stock.services import generer_token_portail_fournisseur
from authentication.models import CustomUser

PUBLIC = '/api/django/public/stock/portail-fournisseur/'


class ConfirmationCompteTests(TestCase):
    def setUp(self):
        self.company = make_company('astk182-co', 'ASTK182 Société')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')
        self.bcf = make_bcf(self.company, self.fournisseur)
        self.user = make_portal_user(
            self.company, 'astk182-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.fournisseur.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.token = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user).token

    def _compte(self, corps):
        return self.api.post(url_confirmer(self.bcf.id), corps, format='json')

    def _jeton(self, corps):
        return APIClient().post(
            f'{PUBLIC}{self.token}/bcf/{self.bcf.id}/confirmer/', corps,
            format='json')

    def _inchange(self):
        self.bcf.refresh_from_db()
        self.assertIsNone(self.bcf.date_confirmee_fournisseur)
        self.assertEqual(self.bcf.numero_confirmation_fournisseur or '', '')

    def test_numero_101_refuse_400(self):
        res = self._compte({'date_confirmee': '2026-03-18',
                            'numero_confirmation': 'x' * 101})
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('numero_confirmation_fournisseur', res.data)
        self._inchange()

    def test_date_illisible_refusee_400(self):
        res = self._compte({'date_confirmee': '18/03/2026'})
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('date_confirmee_fournisseur', res.data)
        self._inchange()

    def test_messages_identiques_aux_deux_portes(self):
        compte = self._compte({'date_confirmee': 'pas-une-date',
                               'numero_confirmation': 'x' * 101})
        jeton = self._jeton({'date_confirmee_fournisseur': 'pas-une-date',
                             'numero_confirmation_fournisseur': 'x' * 101})
        self.assertEqual(compte.status_code, 400)
        self.assertEqual(jeton.status_code, 400)
        self.assertEqual(compte.data, jeton.data)

    def test_saisie_valide_reste_200(self):
        res = self._compte({'date_confirmee': '2026-03-18',
                            'numero_confirmation': 'ACK-42'})
        self.assertEqual(res.status_code, 200, res.data)
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.date_confirmee_fournisseur,
                         datetime.date(2026, 3, 18))
        self.assertEqual(self.bcf.numero_confirmation_fournisseur, 'ACK-42')

    def test_bcf_non_envoye_refuse_409(self):
        from apps.stock.models import BonCommandeFournisseur
        self.bcf.statut = BonCommandeFournisseur.Statut.RECU
        self.bcf.save(update_fields=['statut'])
        res = self._compte({'date_confirmee': '2026-03-18'})
        self.assertEqual(res.status_code, 409, res.data)
        self._inchange()
