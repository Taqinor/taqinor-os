"""Fenêtre « Relancer » (fondateur, 05/10/2026) —
``GET /api/django/ventes/factures/<id>/relance-apercu/``.

* les 3 niveaux par défaut (Rappel courtois / Relance / Relance ferme) sont
  créés pour une société qui n'en a aucun, jamais en double ;
* niveau_suivant progresse 1 → 2 → 3 d'après le journal des relances, puis
  ``deja_tous_envoyes`` ;
* l'aperçu (objet + corps) est EXACTEMENT l'email envoyé par ``relancer`` ;
* pas d'email client → ``peut_envoyer_email`` false ; isolation société.
Contrat : ``apps/ventes/contract_samples/facture_relance_apercu.json``.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, FollowupLevel, RelanceLog
from authentication.models import Company

User = get_user_model()
_CTR = [0]

CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'facture_relance_apercu.json')


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestRelanceApercu(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='RAP Co', slug=f'rap-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'rap_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Débiteur', prenom='RAP',
            email='debiteur.rap@example.com', telephone='+212600000601')
        self.facture = self._facture(self.company, self.client_obj)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        mail.outbox = []

    def _facture(self, company, client):
        return Facture.objects.create(
            company=company, reference=f'FAC-RAP-{_nxt():04d}',
            client=client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), libelle='Installation',
            montant_ht=Decimal('12500.00'), montant_tva=Decimal('2500.00'),
            montant_ttc=Decimal('15000.00'),
            date_echeance=date.today() - timedelta(days=18))

    def _apercu(self, facture=None):
        return self.api.get(
            f'/api/django/ventes/factures/{(facture or self.facture).id}'
            f'/relance-apercu/')

    def test_niveaux_par_defaut_crees_pour_une_societe_vierge(self):
        self.assertFalse(
            FollowupLevel.objects.filter(company=self.company).exists())
        resp = self._apercu()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            [(n['ordre'], n['nom'], n['delai_jours'])
             for n in resp.data['niveaux']],
            [(1, 'Rappel courtois', 7), (2, 'Relance', 15),
             (3, 'Relance ferme', 30)])
        # Idempotent : un second appel ne double rien.
        self._apercu()
        self.assertEqual(
            FollowupLevel.objects.filter(company=self.company).count(), 3)

    def test_ne_touche_pas_des_niveaux_existants(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Maison', delai_jours=10)
        resp = self._apercu()
        self.assertEqual([n['nom'] for n in resp.data['niveaux']], ['Maison'])

    def test_forme_et_valeurs_du_contrat(self):
        resp = self._apercu()
        exemple = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']
        self.assertEqual(set(resp.data), set(exemple))
        self.assertEqual(resp.data['facture_reference'],
                         self.facture.reference)
        self.assertEqual(resp.data['montant_du'], '15000.00')
        self.assertEqual(resp.data['jours_retard'], 18)
        self.assertEqual(resp.data['niveau_suivant']['ordre'], 1)
        self.assertFalse(resp.data['deja_tous_envoyes'])
        self.assertEqual(resp.data['relances_envoyees'], 0)
        self.assertEqual(resp.data['email_client'],
                         'debiteur.rap@example.com')
        self.assertTrue(resp.data['peut_envoyer_email'])

    def test_niveau_suivant_progresse_puis_tous_envoyes(self):
        attendus = [1, 2, 3]
        for ordre in attendus:
            resp = self._apercu()
            self.assertEqual(resp.data['niveau_suivant']['ordre'], ordre)
            self.assertFalse(resp.data['deja_tous_envoyes'])
            RelanceLog.objects.create(
                company=self.company, facture=self.facture, niveau=ordre,
                niveau_nom=resp.data['niveau_suivant']['nom'])
        resp = self._apercu()
        self.assertTrue(resp.data['deja_tous_envoyes'])
        self.assertEqual(resp.data['niveau_suivant']['ordre'], 3)
        self.assertEqual(resp.data['relances_envoyees'], 3)

    def test_sans_email_client(self):
        sans_mail = Client.objects.create(
            company=self.company, nom='Sans', telephone='+212600000602')
        facture = self._facture(self.company, sans_mail)
        resp = self._apercu(facture)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['email_client'], '')
        self.assertFalse(resp.data['peut_envoyer_email'])

    def test_apercu_identique_a_l_email_envoye(self):
        apercu = self._apercu().data
        niveau = apercu['niveau_suivant']
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/relancer/',
            {'niveau': niveau['ordre'], 'envoyer_email': True},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, apercu['sujet'])
        self.assertEqual(mail.outbox[0].body, apercu['message'])
        # La relance consignée fait avancer le niveau suivant.
        self.assertEqual(self._apercu().data['niveau_suivant']['ordre'], 2)

    def test_relancer_cree_les_niveaux_par_defaut(self):
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/relancer/',
            {'niveau': 1}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            FollowupLevel.objects.filter(company=self.company).count(), 3)

    def test_liste_des_niveaux_cree_les_niveaux_par_defaut(self):
        resp = self.api.get('/api/django/ventes/niveaux-relance/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            FollowupLevel.objects.filter(company=self.company).count(), 3)

    def test_isolation_societe(self):
        autre = Company.objects.create(nom='Autre', slug=f'rap-autre-{_nxt()}')
        autre_client = Client.objects.create(
            company=autre, nom='Autre', email='autre@example.com',
            telephone='+212600000603')
        facture_autre = self._facture(autre, autre_client)
        resp = self._apercu(facture_autre)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(FollowupLevel.objects.filter(company=autre).exists())


class TestSeedDefaultsSourceUnique(TestCase):
    """``seed-defaults`` sème LE jeu canonique (plus le second jeu 0-2)."""

    def test_seed_defaults_seme_le_jeu_canonique(self):
        company = Company.objects.create(nom='Seed', slug=f'rap-seed-{_nxt()}')
        admin = User.objects.create_user(
            username=f'rap_seed_{_nxt()}', password='x', role_legacy='admin',
            company=company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        resp = api.post('/api/django/ventes/niveaux-relance/seed-defaults/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            list(FollowupLevel.objects.filter(company=company)
                 .order_by('ordre').values_list('ordre', 'nom')),
            [(1, 'Rappel courtois'), (2, 'Relance'), (3, 'Relance ferme')])
