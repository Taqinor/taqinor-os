"""AANA37 — le pull CSV ``?token=`` refuse toute clé portant un scope
d'écriture.

Constat C-AANA-013 : une clé ``read:leads`` + ``leads:write`` collée dans une
cellule ``=IMPORTDATA()`` répondait 200 — le jeton, exposé dans l'URL (logs,
historique, feuille partagée), ouvrait aussi l'écriture. Désormais
``QueryTokenAuthentication`` refuse (403) une clé qui porte un scope
d'écriture ; une clé de lecture seule passe.

Vraie vue, vraie authentification, vraie base ; rien n'est mocké.

Run :
    python manage.py test apps.publicapi.tests_aana_token_url -v2
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Lead
from authentication.models import Company

from .auth import SCOPES_ECRITURE
from .models import ApiKey
from .portees import (
    ALL_SCOPES, SCOPE_READ_LEADS, SCOPE_WRITE_ACTIVITIES, SCOPE_WRITE_DEVIS,
    SCOPE_WRITE_LEADS, SCOPE_WRITE_TICKETS,
)

URL = '/api/public/v1/exports/leads.csv?token={}'


class TokenUrlLectureSeuleTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana37-co', defaults={'nom': 'AANA37'})
        Lead.objects.create(company=self.co, nom='Lead AANA37')

    def _pull(self, scopes):
        _cle, brute = ApiKey.issue(company=self.co, label='tableur',
                                   scopes=scopes)
        return APIClient().get(URL.format(brute))

    def test_cle_ecriture_refusee(self):
        resp = self._pull([SCOPE_READ_LEADS, SCOPE_WRITE_LEADS])
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('Lead AANA37', resp.content.decode('utf-8'))

    def test_cle_lecture_seule_acceptee(self):
        resp = self._pull([SCOPE_READ_LEADS])
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Lead AANA37', resp.content.decode('utf-8'))

    def test_tout_scope_d_ecriture_est_refuse(self):
        for ecriture in (SCOPE_WRITE_ACTIVITIES, SCOPE_WRITE_DEVIS,
                         SCOPE_WRITE_TICKETS):
            with self.subTest(scope=ecriture):
                resp = self._pull([SCOPE_READ_LEADS, ecriture])
                self.assertEqual(resp.status_code, 403)

    def test_les_scopes_d_ecriture_sont_ceux_du_registre(self):
        self.assertEqual(SCOPES_ECRITURE, {
            SCOPE_WRITE_LEADS, SCOPE_WRITE_ACTIVITIES, SCOPE_WRITE_DEVIS,
            SCOPE_WRITE_TICKETS})
        self.assertTrue(SCOPES_ECRITURE <= set(ALL_SCOPES))
