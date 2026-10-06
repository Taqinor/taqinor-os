"""ADOC72 — garde d'état serveur des documents de chantier (409 nommé).

Constat C-ADOC-039 (S2) : la règle N6 (« PV / attestation une fois le chantier
installé ») ne vivait que dans l'écran (``pvReady``) — une URL directe servait
une attestation « achevés et conformes » pour un chantier signé, annulé ou à
recette non conforme.

Run :
    python manage.py test apps.documents.tests.test_adoc_garde_etat_documents -v2
"""
import itertools

import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.models_chantier import CommissioningRecord
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/documents/chantiers'
DOCS = ('pv-reception', 'bon-livraison', 'dossier-remise', 'attestation')


class GardeEtatDocumentsTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'adoc72-co-{n}', nom=f'ADOC72 Co {n}')
        self.user = User.objects.create_user(
            username=f'adoc72-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_crm = Client.objects.create(
            company=self.company, nom='Tazi', prenom='Omar',
            telephone='+212600000072')

    def _chantier(self, statut, annule=False, recette=None):
        chantier = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC72-{next(_seq)}',
            client=self.client_crm, statut=statut, annule=annule)
        if recette is not None:
            CommissioningRecord.objects.create(
                company=self.company, installation=chantier,
                resultat=recette)
        return chantier

    def _get(self, chantier, route, **params):
        return self.api.get(f'{BASE}/{chantier.pk}/{route}/', params)

    def test_attestation_fin_travaux_refusee_chantier_signe(self):
        for statut in (Installation.Statut.SIGNE, Installation.Statut.EN_COURS):
            with self.subTest(statut=statut):
                chantier = self._chantier(statut)
                r = self._get(chantier, 'attestation', type='fin_travaux')
                self.assertEqual(r.status_code, 409)
                self.assertEqual(
                    r.data['detail'],
                    'Disponible une fois le chantier installé')
                for route in DOCS:
                    self.assertEqual(
                        self._get(chantier, route).status_code, 409, route)

    def test_documents_refuses_chantier_annule(self):
        chantier = self._chantier(Installation.Statut.INSTALLE, annule=True)
        for route in DOCS:
            with self.subTest(route=route):
                r = self._get(chantier, route)
                self.assertEqual(r.status_code, 409)
                self.assertEqual(r.data['detail'], 'Chantier annulé')
        chantier_signe = self._chantier(Installation.Statut.SIGNE, annule=True)
        r = self._get(chantier_signe, 'attestation', type='installation')
        self.assertEqual(r.status_code, 409)

    def test_attestation_refusee_recette_non_conforme(self):
        chantier = self._chantier(
            Installation.Statut.INSTALLE,
            recette=CommissioningRecord.Resultat.NON_CONFORME)
        r = self._get(chantier, 'attestation', type='fin_travaux')
        self.assertEqual(r.status_code, 409)
        self.assertIn('recette non conforme', r.data['detail'])
        # Le PV constate les réserves : autorisé.
        self.assertEqual(self._get(chantier, 'pv-reception').status_code, 200)
        # L'attestation d'INSTALLATION n'affirme pas la conformité.
        self.assertEqual(
            self._get(chantier, 'attestation', type='installation')
            .status_code, 200)

    def test_temoin_installe_conforme_autorise(self):
        chantier = self._chantier(
            Installation.Statut.INSTALLE,
            recette=CommissioningRecord.Resultat.CONFORME)
        r = self._get(chantier, 'attestation', type='fin_travaux')
        self.assertEqual(r.status_code, 200)
        doc = fitz.open(stream=r.content, filetype='pdf')
        try:
            texte = '\n'.join(page.get_text() for page in doc)
        finally:
            doc.close()
        self.assertIn('achevés et', texte)
        for route in DOCS:
            self.assertEqual(self._get(chantier, route).status_code, 200)

    def test_statut_herite_pose_autorise(self):
        chantier = self._chantier(Installation.Statut.POSE)
        for route in DOCS:
            with self.subTest(route=route):
                self.assertEqual(self._get(chantier, route).status_code, 200)
        # Rabattu sur un rang inférieur à « installé » → refusé.
        encours = self._chantier(Installation.Statut.POSE_EN_COURS)
        self.assertEqual(
            self._get(encours, 'pv-reception').status_code, 409)
