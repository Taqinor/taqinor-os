"""AGNR40 (C-AGNR-028) — ``POST /ventes/devis/atomic/`` (le VRAI chemin de
création du générateur) respecte ``Idempotency-Key`` :

  * deux POST identiques avec la MÊME clé (le 2ᵉ après une coupure côté
    client survenue APRÈS le commit) -> UN seul devis, la 2ᵉ réponse rend le
    premier ;
  * même clé, corps différent -> 409 ``idempotency_conflict`` ;
  * une clé neuve (nouvelle session de création) -> un nouveau devis ;
  * la clé de ``/atomic/`` ne rejoue jamais une création de ``POST /devis/`` ;
  * un refus (400) n'est pas mémorisé : corrigé, la même clé crée.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agnr40_atomic_idempotent"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
URL = '/api/django/ventes/devis/atomic/'


class AtomicIdempotentTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agnr40-co', defaults={'nom': 'agnr40-co'})
        self.user = User.objects.create_user(
            username='agnr40_user', password='x', role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AGNR40', telephone='+212600000040')
        self.produit = Produit.objects.create(
            company=self.company, nom='Smart Meter', prix_vente=Decimal('1200'),
            prix_achat=Decimal('800'), quantite_stock=10, tva=Decimal('20.00'))

    def _corps(self, quantite='1'):
        return {
            'client': self.client_obj.id, 'statut': 'brouillon', 'taux_tva': '20.00',
            'lignes': [{'produit': self.produit.id, 'designation': 'Smart Meter',
                        'quantite': quantite, 'prix_unitaire': '1200.00', 'taux_tva': '20'}],
        }

    def _nb(self):
        return Devis.objects.filter(company=self.company).count()

    def test_meme_cle_un_seul_devis(self):
        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-session-1'}
        premier = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(premier.status_code, (200, 201), premier.content)
        second = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertEqual(second.status_code, premier.status_code)
        self.assertEqual(second.json()['id'], premier.json()['id'])
        self.assertEqual(self._nb(), 1)

    def test_meme_cle_corps_different_409(self):
        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-session-2'}
        premier = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(premier.status_code, (200, 201), premier.content)
        autre = self.api.post(URL, self._corps(quantite='2'), format='json', **cle)
        self.assertEqual(autre.status_code, 409)
        self.assertEqual(self._nb(), 1)

    def test_cle_neuve_nouveau_devis_et_sans_cle_inchange(self):
        a = self.api.post(URL, self._corps(), format='json', HTTP_IDEMPOTENCY_KEY='s-a')
        b = self.api.post(URL, self._corps(), format='json', HTTP_IDEMPOTENCY_KEY='s-b')
        c = self.api.post(URL, self._corps(), format='json')
        for r in (a, b, c):
            self.assertIn(r.status_code, (200, 201), r.content)
        self.assertEqual(self._nb(), 3)

    def test_espace_de_cles_distinct_de_create(self):
        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-partagee'}
        cree = self.api.post('/api/django/ventes/devis/',
                             {'client': self.client_obj.id, 'taux_tva': '20.00'},
                             format='json', **cle)
        self.assertIn(cree.status_code, (200, 201), cree.content)
        atomique = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(atomique.status_code, (200, 201), atomique.content)
        self.assertNotEqual(atomique.json()['id'], cree.json()['id'])

    def test_refus_non_memorise(self):
        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-session-3'}
        vide = dict(self._corps(), lignes=[])
        refus = self.api.post(URL, vide, format='json', **cle)
        self.assertEqual(refus.status_code, 400)
        ok = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(ok.status_code, (200, 201), ok.content)
        self.assertEqual(self._nb(), 1)

    # ── ERR-AGNR40-IDEMPOTENCE-EN-VOL (preuve en direct : AGNR42 P5.1) ──
    # Trois clics « Créer le devis » avec la MÊME clé pendant que le premier
    # POST tournait encore (~100 s) avaient créé trois devis : la clé n'était
    # enregistrée qu'APRÈS ``creer()``. Elle est désormais RÉSERVÉE avant.

    def _endpoint(self):
        from apps.ventes.views.devis import DevisViewSet
        return f'{DevisViewSet()._idempotency_endpoint()}.atomic'

    def _reservation(self, cle):
        from core.idempotency import IdempotencyRecord, _fingerprint
        return IdempotencyRecord.objects.create(
            company=self.company, endpoint=self._endpoint(), key=cle,
            request_fingerprint=_fingerprint(self._corps()), response_status=0,
            response_body={}, etat=IdempotencyRecord.Etat.EN_COURS)

    def test_doublon_pendant_la_creation_ne_cree_rien(self):
        """Simulation déterministe de la course : PENDANT ``creer()`` du 1er
        POST, un 2ᵉ POST identique arrive -> 409 « en cours », jamais un
        second devis ; après coup, la même clé rejoue le premier."""
        from apps.ventes.views.devis_edition import DevisEditionActionsMixin
        from core.idempotency import IdempotencyRecord

        cle = {'HTTP_IDEMPOTENCY_KEY': '13172b31-en-vol'}
        original = DevisEditionActionsMixin._creer_atomique
        doublons = []

        def pendant(vue, request):
            if not doublons:
                doublons.append(self.api.post(URL, self._corps(), format='json', **cle))
            return original(vue, request)

        with patch.object(DevisEditionActionsMixin, '_creer_atomique',
                          autospec=True, side_effect=pendant):
            premier = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(premier.status_code, (200, 201), premier.content)
        self.assertEqual(len(doublons), 1)
        self.assertEqual(doublons[0].status_code, 409, doublons[0].content)
        self.assertEqual(doublons[0].json()['code'], 'idempotency_en_cours')
        self.assertEqual(self._nb(), 1)

        record = IdempotencyRecord.objects.get(company=self.company, key='13172b31-en-vol')
        self.assertEqual(record.etat, IdempotencyRecord.Etat.TERMINE)
        rejeu = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertEqual(rejeu.status_code, premier.status_code)
        self.assertEqual(rejeu.json()['id'], premier.json()['id'])
        self.assertEqual(self._nb(), 1)

    def test_reservation_en_cours_bloque_un_second_post(self):
        """Réservation présente et non terminée -> ``creer()`` ne s'exécute pas."""
        from apps.ventes.views.devis_edition import DevisEditionActionsMixin

        self._reservation('agnr40-en-cours')
        with patch.object(DevisEditionActionsMixin, '_creer_atomique') as creer:
            r = self.api.post(URL, self._corps(), format='json',
                              HTTP_IDEMPOTENCY_KEY='agnr40-en-cours')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.json()['code'], 'idempotency_en_cours')
        creer.assert_not_called()
        self.assertEqual(self._nb(), 0)

    def test_corps_different_pendant_reservation_409_conflit(self):
        self._reservation('agnr40-en-cours-autre')
        r = self.api.post(URL, self._corps(quantite='2'), format='json',
                          HTTP_IDEMPOTENCY_KEY='agnr40-en-cours-autre')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertNotEqual(r.json().get('code'), 'idempotency_en_cours')
        self.assertEqual(self._nb(), 0)

    def test_echec_de_creer_libere_la_cle(self):
        from apps.ventes.views.devis_edition import DevisEditionActionsMixin
        from core.idempotency import IdempotencyRecord

        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-echec'}
        with patch.object(DevisEditionActionsMixin, '_creer_atomique',
                          side_effect=RuntimeError('panne')):
            try:
                r = self.api.post(URL, self._corps(), format='json', **cle)
                self.assertGreaterEqual(r.status_code, 500)
            except RuntimeError:
                pass
        self.assertFalse(IdempotencyRecord.objects.filter(
            company=self.company, key='agnr40-echec').exists())
        ok = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(ok.status_code, (200, 201), ok.content)
        self.assertEqual(self._nb(), 1)

    def test_refus_libere_la_reservation(self):
        from core.idempotency import IdempotencyRecord
        refus = self.api.post(URL, dict(self._corps(), lignes=[]), format='json',
                              HTTP_IDEMPOTENCY_KEY='agnr40-refus')
        self.assertEqual(refus.status_code, 400)
        self.assertFalse(IdempotencyRecord.objects.filter(
            company=self.company, key='agnr40-refus').exists())

    def test_reservation_abandonnee_reprise(self):
        """Processus mort en pleine création : la réservation expirée est
        reprise, la clé n'est jamais bloquée à vie."""
        from django.utils import timezone
        from core.idempotency import RESERVATION_EXPIREE, IdempotencyRecord

        res = self._reservation('agnr40-abandon')
        IdempotencyRecord.objects.filter(pk=res.pk).update(
            created_at=timezone.now() - RESERVATION_EXPIREE * 2)
        r = self.api.post(URL, self._corps(), format='json',
                          HTTP_IDEMPOTENCY_KEY='agnr40-abandon')
        self.assertIn(r.status_code, (200, 201), r.content)
        self.assertEqual(self._nb(), 1)
        record = IdempotencyRecord.objects.get(company=self.company, key='agnr40-abandon')
        self.assertEqual(record.etat, IdempotencyRecord.Etat.TERMINE)
        self.assertEqual(record.response_body.get('id'), r.json()['id'])
