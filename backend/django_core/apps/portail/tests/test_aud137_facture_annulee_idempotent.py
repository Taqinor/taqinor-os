"""AUD137 — portail : une facture ANNULÉE n'est plus « payable », et « Payer »
devient idempotent.

Deux défauts distincts, un seul scénario client :

1. ``factures_du_client_portail`` (``ventes/selectors.py``) n'excluait QUE le
   brouillon ; ``Facture.montant_du`` (``facturation/models.py``) ne regarde
   JAMAIS le statut et rend donc le TTC entier pour une facture ANNULÉE sans
   paiement. L'écran (``!f.payee``) affichait alors « reste dû » + le bouton
   « Payer » sur une facture annulée.
2. ``MesFacturesPortailViewSet.payer`` créait un ``PaiementFacturePortail``
   INCONDITIONNEL à chaque appel, montant figé au clic : trois clics sur
   « Payer » empilaient trois intentions du même client pour la même facture,
   à des montants divergents.

Le test ROUGE de référence est conservé en commentaire à chaque cas : avant ce
correctif, (1) rendait ``payable`` absent / ``montant_du`` == TTC entier pour
une facture annulée et permettait ``payer`` dessus (200), et (2) créait un
nouveau ``PaiementFacturePortail`` à chaque appel.

PACT10 — l'exemple de la liste est celui COMMITTÉ dans
``apps/portail/contract_samples/mes_factures_liste.json``, jamais un
dictionnaire réécrit à la main ici.

Run :
    python manage.py test apps.portail.tests.test_aud137_facture_annulee_idempotent -v2
"""
import itertools
import json
import pathlib
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.facturation.models import Facture, Paiement
from apps.portail.models import PaiementFacturePortail
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT, Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'mes_factures_liste.json')
    .read_text(encoding='utf-8'))


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD137-{n}',
        email=f'aud137-{company.id}-{n}@example.invalid')


def make_facture(
        company, client, statut=Facture.Statut.EMISE,
        montant_ttc=Decimal('20400')):
    n = next(_seq)
    montant_ht = (montant_ttc / Decimal('1.2')).quantize(Decimal('0.01'))
    return Facture.objects.create(
        company=company, reference=f'FAC-AUD137-{n}', client=client,
        statut=statut, montant_ht=montant_ht,
        montant_tva=montant_ttc - montant_ht,
        montant_ttc=montant_ttc, taux_tva=Decimal('20'))


def make_portal_user(company, username, scope_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = scope_id
    user.save()
    return user


class FactureAnnuleeNonPayableTests(TestCase):
    def setUp(self):
        self.company = make_company('aud137-co-a', 'AUD137 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.facture_annulee = make_facture(
            self.company, self.client_a, statut=Facture.Statut.ANNULEE)
        self.facture_payee = make_facture(
            self.company, self.client_a, statut=Facture.Statut.PAYEE)
        self.facture_ouverte = make_facture(
            self.company, self.client_a, statut=Facture.Statut.EMISE)
        self.user_a = make_portal_user(
            self.company, 'aud137-portail-a', self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def _ligne(self, facture_id):
        res = self.api.get('/api/django/portail/mes-factures/')
        return next(x for x in res.data['results'] if x['id'] == facture_id)

    # ROUGE avant correctif : `payable` était absent et `montant_du` valait le
    # TTC entier (20400.00) pour une facture annulée sans paiement.
    def test_facture_annulee_non_payable_et_montant_du_zero(self):
        ligne = self._ligne(self.facture_annulee.id)
        self.assertFalse(ligne['payable'])
        self.assertEqual(ligne['montant_du'], '0.00')

    def test_facture_payee_non_payable(self):
        ligne = self._ligne(self.facture_payee.id)
        self.assertFalse(ligne['payable'])

    def test_facture_ouverte_reste_payable(self):
        ligne = self._ligne(self.facture_ouverte.id)
        self.assertTrue(ligne['payable'])
        self.assertEqual(ligne['montant_du'], '20400.00')

    # ROUGE avant correctif : la vue ne vérifiait AUCUN statut et répondait
    # 200 pour une facture annulée.
    def test_payer_une_facture_annulee_refuse(self):
        res = self.api.post(
            f'/api/django/portail/mes-factures/{self.facture_annulee.id}/'
            f'payer/', {}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(
            PaiementFacturePortail.objects.filter(
                facture=self.facture_annulee).exists())

    def test_payer_une_facture_deja_payee_refuse(self):
        res = self.api.post(
            f'/api/django/portail/mes-factures/{self.facture_payee.id}/'
            f'payer/', {}, format='json')
        self.assertEqual(res.status_code, 400)

    # ── PACT10 : la forme servie EST celle du contrat committé ──────────────
    def test_la_reponse_liste_a_exactement_les_cles_du_contrat(self):
        ligne = self._ligne(self.facture_ouverte.id)
        self.assertEqual(
            set(ligne.keys()),
            set(CONTRAT['exemple']['results'][0].keys()))
        self.assertEqual(
            CONTRAT['endpoint'], 'GET /api/django/portail/mes-factures/')


class PayerIdempotentTests(TestCase):
    def setUp(self):
        self.company = make_company('aud137-pay-co', 'AUD137 Paiement')
        self.client_a = make_client(self.company, 'Alpha')
        self.facture = make_facture(
            self.company, self.client_a, montant_ttc=Decimal('9000'))
        self.user_a = make_portal_user(
            self.company, 'aud137-pay-a', self.client_a.id)
        self.url = (
            f'/api/django/portail/mes-factures/{self.facture.id}/payer/')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    # ROUGE avant correctif : chaque POST créait une NOUVELLE ligne — trois
    # clics -> trois `PaiementFacturePortail`, trois montants figés distincts.
    def test_trois_clics_successifs_ne_creent_quune_seule_intention(self):
        r1 = self.api.post(self.url, {}, format='json')
        r2 = self.api.post(self.url, {}, format='json')
        r3 = self.api.post(self.url, {}, format='json')
        for r in (r1, r2, r3):
            self.assertEqual(r.status_code, 200, r.data)

        self.assertEqual(
            PaiementFacturePortail.objects.filter(
                facture=self.facture).count(), 1)
        self.assertEqual(r1.data['paiement_id'], r2.data['paiement_id'])
        self.assertEqual(r2.data['paiement_id'], r3.data['paiement_id'])

    def test_le_montant_de_lintention_suit_le_reste_du_courant(self):
        r1 = self.api.post(self.url, {}, format='json')
        self.assertEqual(r1.data['montant'], '9000.00')

        # Un paiement partiel réel réduit le reste dû entre deux clics.
        Paiement.objects.create(
            company=self.company, facture=self.facture, client=self.client_a,
            montant=Decimal('4000'), date_paiement=timezone.now().date())

        r2 = self.api.post(self.url, {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['montant'], '5000.00')
        self.assertEqual(r1.data['paiement_id'], r2.data['paiement_id'])
        paiement = PaiementFacturePortail.objects.get(id=r2.data['paiement_id'])
        self.assertEqual(paiement.montant, Decimal('5000.00'))
