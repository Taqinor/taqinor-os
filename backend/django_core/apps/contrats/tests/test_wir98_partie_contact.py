"""WIR98 — rattachement d'une PartieContrat au référentiel contacts canonique.

Couvre :
* créer une partie DEPUIS un contact existant pré-remplit nom/fonction/email/
  téléphone (le référentiel amorce les coordonnées) ;
* une valeur explicitement saisie n'est jamais écrasée par le contact ;
* le contact lié doit appartenir à la société de l'utilisateur (400 sinon) ;
* le FK reste optionnel : une partie hors référentiel (aucun contact) reste
  valide tant qu'un nom est fourni.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contacts.models import ContactClient
from apps.contrats.models import Contrat, PartieContrat
from apps.crm.models import Client

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Wir98PartieContactTests(TestCase):
    BASE = '/api/django/contrats/parties/'

    def setUp(self):
        self.co_a = make_company('wir98-a', 'A')
        self.co_b = make_company('wir98-b', 'B')
        self.user_a = make_user(self.co_a, 'wir98-a')
        self.contrat_a = Contrat.objects.create(company=self.co_a, objet='A')
        self.client_a = Client.objects.create(company=self.co_a, nom='ACME')
        self.contact_a = ContactClient.objects.create(
            company=self.co_a, client=self.client_a, nom='Alaoui',
            prenom='Karim', poste='Directeur', email='k@acme.ma',
            telephone='0600112233')
        # Contact d'une AUTRE société (pour la garde cross-tenant).
        self.client_b = Client.objects.create(company=self.co_b, nom='OTHER')
        self.contact_b = ContactClient.objects.create(
            company=self.co_b, client=self.client_b, nom='Bennani')

    def test_create_from_contact_prefills_coordonnees(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'contrat': self.contrat_a.id,
            'type_partie': PartieContrat.TypePartie.CLIENT,
            'contact': self.contact_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PartieContrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.contact_id, self.contact_a.id)
        self.assertEqual(obj.nom, 'Alaoui Karim')
        self.assertEqual(obj.fonction, 'Directeur')
        self.assertEqual(obj.email, 'k@acme.ma')
        self.assertEqual(obj.telephone, '0600112233')

    def test_explicit_values_not_overwritten(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'contrat': self.contrat_a.id,
            'contact': self.contact_a.id,
            'nom': 'Nom manuel',
            'email': 'manuel@x.ma',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PartieContrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.nom, 'Nom manuel')
        self.assertEqual(obj.email, 'manuel@x.ma')
        # Les champs non fournis sont tout de même amorcés par le contact.
        self.assertEqual(obj.fonction, 'Directeur')

    def test_contact_cross_company_rejected(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'contrat': self.contrat_a.id,
            'contact': self.contact_b.id,
            'nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_contact_optional_free_text_still_valid(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'contrat': self.contrat_a.id,
            'nom': 'Témoin externe',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PartieContrat.objects.get(id=resp.data['id'])
        self.assertIsNone(obj.contact_id)
        self.assertEqual(obj.nom, 'Témoin externe')

    def test_no_nom_and_no_contact_rejected(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'contrat': self.contrat_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
