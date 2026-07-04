"""XPUR20 — envoi de la RFQ aux fournisseurs consultés (email + WhatsApp).

Couvre :
  * la consultation d'un fournisseur (jeton créé, idempotent) ;
  * l'envoi par email (fournisseur avec email) + brouillon wa.me (téléphone) ;
  * les boutons/canaux « grisés » quand le fournisseur n'a ni email ni
    téléphone (aucun envoi, raison explicite, aucune exception) ;
  * la relance qui ne cible QUE les non-répondants ;
  * qu'aucun prix d'achat d'un AUTRE fournisseur ne fuit dans les résultats.

Run :
    python manage.py test apps.installations.tests_xpur20_rfq_envoi -v2
"""
import itertools

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import RFQ, RFQOffre, RFQConsultation

_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xpur20-co-{n}', defaults={'nom': nom or f'XPUR20 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username or f'xpur20-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_fournisseur(company, nom='SolarImport', email=None, telephone=None):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(
        company=company, nom=nom, email=email, telephone=telephone)


class TestConsulterEtEnvoi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.rfq = RFQ.objects.create(
            company=self.company, reference='RFQ-XPUR20-1', objet='Panneaux',
            created_by=self.user)

    def test_consulter_fournisseur_creates_token(self):
        f = make_fournisseur(
            self.company, email='f@ex.com', telephone='0612345678')
        r = self.api.post(
            f'{BASE}/rfq/{self.rfq.id}/consulter/', {'fournisseur': f.id})
        self.assertEqual(r.status_code, 201, r.data)
        consultation = RFQConsultation.objects.get(rfq=self.rfq, fournisseur=f)
        self.assertTrue(consultation.token)
        self.assertEqual(consultation.company_id, self.company.id)

    def test_consulter_idempotent(self):
        f = make_fournisseur(self.company)
        r1 = self.api.post(
            f'{BASE}/rfq/{self.rfq.id}/consulter/', {'fournisseur': f.id})
        r2 = self.api.post(
            f'{BASE}/rfq/{self.rfq.id}/consulter/', {'fournisseur': f.id})
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(
            RFQConsultation.objects.filter(rfq=self.rfq, fournisseur=f).count(), 1)

    def test_consulter_foreign_fournisseur_rejected(self):
        autre = make_company()
        f = make_fournisseur(autre)
        r = self.api.post(
            f'{BASE}/rfq/{self.rfq.id}/consulter/', {'fournisseur': f.id})
        self.assertEqual(r.status_code, 400, r.data)

    def test_envoi_email_et_whatsapp(self):
        f = make_fournisseur(
            self.company, email='fournisseur@example.com',
            telephone='0612345678')
        consultation = RFQConsultation.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=f)
        r = self.api.post(
            f'{BASE}/rfq/{self.rfq.id}/envoyer-consultations/', {})
        self.assertEqual(r.status_code, 200, r.data)
        resultats = r.data['resultats']
        self.assertEqual(len(resultats), 1)
        self.assertTrue(resultats[0]['email']['envoye'])
        self.assertTrue(resultats[0]['whatsapp']['envoye'])
        self.assertIn('wa.me', resultats[0]['whatsapp']['url'])
        consultation.refresh_from_db()
        self.assertIsNotNone(consultation.email_envoye_le)
        self.assertIsNotNone(consultation.whatsapp_envoye_le)
        # Email réellement "envoyé" via le backend de test (locmem).
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.rfq.reference, mail.outbox[0].subject)

    def test_envoi_sans_coordonnees_grise(self):
        """Fournisseur sans email ni téléphone → aucun canal envoyé, raison
        explicite, jamais d'exception."""
        f = make_fournisseur(self.company, email=None, telephone=None)
        RFQConsultation.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=f)
        r = self.api.post(
            f'{BASE}/rfq/{self.rfq.id}/envoyer-consultations/', {})
        self.assertEqual(r.status_code, 200, r.data)
        res = r.data['resultats'][0]
        self.assertFalse(res['email']['envoye'])
        self.assertIsNotNone(res['email']['raison'])
        self.assertFalse(res['whatsapp']['envoye'])
        self.assertIsNotNone(res['whatsapp']['raison'])

    def test_envoi_ne_fuit_aucun_prix_autre_fournisseur(self):
        f1 = make_fournisseur(self.company, email='a@example.com', nom='A')
        f2 = make_fournisseur(self.company, email='b@example.com', nom='B')
        RFQOffre.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=f2,
            montant_ht=123456)
        RFQConsultation.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=f1)
        r = self.api.post(
            f'{BASE}/rfq/{self.rfq.id}/envoyer-consultations/', {})
        self.assertEqual(r.status_code, 200, r.data)
        payload_str = str(r.data)
        self.assertNotIn('123456', payload_str)
        # Le corps de l'email envoyé ne contient aucun montant.
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('123456', mail.outbox[0].body)


class TestRelanceNonRepondants(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.rfq = RFQ.objects.create(
            company=self.company, reference='RFQ-XPUR20-2', objet='X',
            created_by=self.user)
        self.f_repondu = make_fournisseur(
            self.company, nom='Repondu', email='r@example.com')
        self.f_sans_reponse = make_fournisseur(
            self.company, nom='SansReponse', email='sr@example.com')
        self.offre = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.f_repondu,
            montant_ht=1000)
        self.c_repondu = RFQConsultation.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.f_repondu,
            offre=self.offre)
        self.c_sans_reponse = RFQConsultation.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.f_sans_reponse)

    def test_relance_cible_uniquement_non_repondants(self):
        r = self.api.post(
            f'{BASE}/rfq/{self.rfq.id}/relancer-non-repondants/', {})
        self.assertEqual(r.status_code, 200, r.data)
        resultats = r.data['resultats']
        self.assertEqual(len(resultats), 1)
        self.assertEqual(
            resultats[0]['consultation'], self.c_sans_reponse.id)
        self.c_sans_reponse.refresh_from_db()
        self.assertEqual(self.c_sans_reponse.nb_relances, 1)
        self.c_repondu.refresh_from_db()
        self.assertEqual(self.c_repondu.nb_relances, 0)


class TestScopeRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.rfq = RFQ.objects.create(
            company=self.company, reference='RFQ-XPUR20-3', objet='X',
            created_by=self.user)

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(
            f'{BASE}/rfq/{self.rfq.id}/consulter/', {'fournisseur': 1})
        self.assertEqual(r.status_code, 403, r.data)

    def test_consultations_scoped(self):
        other = make_company()
        f = make_fournisseur(other)
        other_rfq = RFQ.objects.create(
            company=other, reference='RFQ-XPUR20-O', objet='Autre')
        RFQConsultation.objects.create(
            company=other, rfq=other_rfq, fournisseur=f)
        r = self.api.get(f'{BASE}/rfq-consultations/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 0)
