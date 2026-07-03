"""QC1 — autocomplete entreprise sur les données propres de la société.

GET /crm/clients/search/?q= : recherche floue (nom/ICE) sur clients +
fournisseurs + leads, STRICTEMENT scopée à la société de l'utilisateur.
Remplit ice/if_fiscal/rc/adresse/telephone quand disponibles (clients), vide
sinon (fournisseurs/leads). Provider seam : la vue passe par
``search_companies`` (QC2 pourra brancher un registre licencié).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Fournisseur
from authentication.models import Company

User = get_user_model()

URL = '/api/django/crm/clients/search/'


def api_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return c


class QC1Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='qc1-co', defaults={'nom': 'QC1 Co'})[0]
        cls.other = Company.objects.get_or_create(
            slug='qc1-other', defaults={'nom': 'QC1 Other'})[0]
        cls.user = User.objects.create_user(
            username='qc1user', password='x', company=cls.company,
            role_legacy='responsable')

        cls.client_ent = Client.objects.create(
            company=cls.company, nom='Zellige Trans SARL', type_client='entreprise',
            ice='001234567000089', if_fiscal='12345678', rc='RC-4521',
            adresse='Zone Sidi Maarouf, Casablanca', telephone='+212522000000',
            email='contact@zellige.ma')
        cls.fournisseur = Fournisseur.objects.create(
            company=cls.company, nom='Zellige Import Fournisseur',
            adresse='Ain Sebaa', telephone='+212522111111',
            email='achat@zelligeimport.ma')
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Contact Zellige', societe='Zellige Prospect',
            telephone='+212600000000', adresse='Rabat')
        # Enregistrements d'une AUTRE société (ne doivent jamais remonter).
        Client.objects.create(
            company=cls.other, nom='Zellige Autre Societe', type_client='entreprise',
            ice='999', adresse='Ailleurs')


class TestSearchOwnData(QC1Base):
    def test_recherche_floue_nom_couvre_les_trois_sources(self):
        r = api_for(self.user).get(URL, {'q': 'zellige'})
        self.assertEqual(r.status_code, 200, r.data)
        results = r.data['results']
        sources = {h['source'] for h in results}
        self.assertEqual(sources, {'client', 'fournisseur', 'lead'})
        noms = {h['nom'] for h in results}
        self.assertIn('Zellige Trans SARL', noms)
        self.assertIn('Zellige Import Fournisseur', noms)
        self.assertIn('Zellige Prospect', noms)  # lead → societe privilégiée

    def test_client_remplit_les_identifiants_legaux(self):
        r = api_for(self.user).get(URL, {'q': 'Zellige Trans'})
        hit = next(h for h in r.data['results'] if h['source'] == 'client')
        self.assertEqual(hit['ice'], '001234567000089')
        self.assertEqual(hit['if_fiscal'], '12345678')
        self.assertEqual(hit['rc'], 'RC-4521')
        self.assertEqual(hit['adresse'], 'Zone Sidi Maarouf, Casablanca')
        self.assertEqual(hit['telephone'], '+212522000000')

    def test_recherche_par_ice(self):
        r = api_for(self.user).get(URL, {'q': '001234567'})
        noms = {h['nom'] for h in r.data['results']}
        self.assertIn('Zellige Trans SARL', noms)

    def test_scoping_societe_stricte(self):
        r = api_for(self.user).get(URL, {'q': 'zellige'})
        noms = {h['nom'] for h in r.data['results']}
        self.assertNotIn('Zellige Autre Societe', noms)

    def test_q_vide_renvoie_liste_vide(self):
        r = api_for(self.user).get(URL, {'q': '  '})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['results'], [])

    def test_sans_correspondance_liste_vide(self):
        r = api_for(self.user).get(URL, {'q': 'introuvablexyz'})
        self.assertEqual(r.data['results'], [])


class TestProviderSeam(TestCase):
    """Le provider seam permet de substituer la source (QC2) sans changer la
    vue : ``search_companies`` délègue au provider fourni, défaut own-data."""

    def test_search_companies_delegue_au_provider_fourni(self):
        from apps.crm.company_search import search_companies
        called = {}

        def fake_provider(company, q, *, limit):
            called['q'] = q
            called['limit'] = limit
            return [{'source': 'registre', 'id': 0, 'nom': f'Registre {q}',
                     'ice': '', 'if_fiscal': '', 'rc': '',
                     'adresse': '', 'telephone': '', 'email': ''}]

        out = search_companies(None, 'acme', provider=fake_provider)
        self.assertEqual(called['q'], 'acme')
        self.assertEqual(out[0]['nom'], 'Registre acme')

    def test_provider_defaut_est_own_data(self):
        # Sans provider explicite, aucune exception et retour liste (vide ici,
        # pas de données) : le défaut own-data est bien câblé.
        from apps.crm.company_search import search_companies
        company = Company.objects.get_or_create(
            slug='qc1-seam', defaults={'nom': 'QC1 Seam'})[0]
        self.assertEqual(search_companies(company, 'rien'), [])
