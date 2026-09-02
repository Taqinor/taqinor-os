"""Tests AUD146 — le filtre « À rapprocher » est enfin honoré par le serveur.

Défaut d'origine : l'écran appelait
``GET /portail/paiements-facture-portail/?statut=initie`` (filtre par défaut),
mais le ViewSet ne déclarait que ``filters.OrderingFilter``, sans
``filterset_fields`` ni ``get_queryset`` custom, et les backends globaux
(``erp_agentique/settings/base.py``) sont ``OrderingFilter`` + ``SearchFilter``
uniquement — il n'y a PAS de ``DjangoFilterBackend``. Le paramètre était donc
silencieusement ignoré : l'opérateur croyait voir la file des virements à
rapprocher, y comptait des lignes déjà rapprochées et des lignes abandonnées,
et rapprochait deux fois.

Ces tests étaient ROUGES avant le correctif (la liste renvoyait les 3 lignes
quel que soit le filtre).

Côté écran, le contrat (URL appelée + contenu rendu) est déjà affirmé par
``frontend/src/features/portail/admin/PaiementsFacturePortailAdmin.test.jsx``
(appel par défaut avec ``{statut: 'initie'}``, lignes rendues, aucune action
sur une ligne ``paye``) — l'écran était correct, seul le serveur mentait.

Run :
    python manage.py test apps.portail.tests.test_aud146_filtre_statut -v2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.portail.models import PaiementFacturePortail
from authentication.models import Company, CustomUser

RACINE = '/api/django/portail/paiements-facture-portail/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FiltreStatutPaiementPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('aud146-co', 'AUD146 Société')
        self.user = CustomUser.objects.create_user(
            username='aud146-resp', password='motdepasse-test-1234',
            company=self.co, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        def paiement(facture_id, statut):
            return PaiementFacturePortail.objects.create(
                company=self.co, facture_id=facture_id,
                montant=Decimal('100.00'),
                methode=PaiementFacturePortail.Methode.VIREMENT,
                statut=statut)

        self.initie = paiement(1461, PaiementFacturePortail.Statut.INITIE)
        self.paye = paiement(1462, PaiementFacturePortail.Statut.PAYE)
        self.echoue = paiement(1463, PaiementFacturePortail.Statut.ECHOUE)

    def _ids(self, res):
        lignes = res.data.get('results') if isinstance(res.data, dict) \
            else res.data
        return {ligne['id'] for ligne in lignes}

    def test_statut_paye_ne_renvoie_que_les_lignes_payees(self):
        """ROUGE avant AUD146 : les 3 lignes revenaient."""
        res = self.api.get(f'{RACINE}?statut=paye')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(self._ids(res), {self.paye.id})

    def test_la_file_a_rapprocher_ne_montre_que_les_inities(self):
        """Le filtre par défaut de l'écran — le cœur du défaut."""
        res = self.api.get(f'{RACINE}?statut=initie')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(self._ids(res), {self.initie.id})

    def test_sans_filtre_tous_les_statuts_reviennent(self):
        res = self.api.get(RACINE)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(
            self._ids(res),
            {self.initie.id, self.paye.id, self.echoue.id})

    def test_un_filtre_vide_equivaut_a_aucun_filtre(self):
        res = self.api.get(f'{RACINE}?statut=')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(len(self._ids(res)), 3)

    def test_un_statut_inconnu_est_refuse_plutot_que_tout_rendre(self):
        res = self.api.get(f'{RACINE}?statut=nimportequoi')
        self.assertEqual(res.status_code, 400, res.content)

    def test_le_filtre_reste_borne_a_la_societe(self):
        autre = make_company('aud146-co-b', 'AUD146 Société B')
        PaiementFacturePortail.objects.create(
            company=autre, facture_id=1464, montant=Decimal('1.00'),
            statut=PaiementFacturePortail.Statut.PAYE)
        res = self.api.get(f'{RACINE}?statut=paye')
        self.assertEqual(self._ids(res), {self.paye.id})

    def test_rapprocher_fonctionne_toujours(self):
        """`get_queryset` sert aussi `get_object` : l'action ne doit pas
        tomber (AUD140 l'a conservée)."""
        res = self.api.post(f'{RACINE}{self.initie.id}/rapprocher/',
                            {}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
