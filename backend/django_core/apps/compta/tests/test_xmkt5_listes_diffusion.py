"""XMKT5 — Listes de diffusion nommées + abonnements.

Couvre : CRUD listes, inscription idempotente + dédoublonnage par
destinataire normalisé, import avec rapport (ajoutés/doublons/ignorés-
supprimés) jamais d'écrasement des désinscrits, ciblage de campagne par
liste, historique par contact, isolation multi-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import AbonnementListe, Campagne, ListeDiffusion

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


class ListeDiffusionTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt5', 'XMKT5')
        self.user = make_user(self.co, 'xmkt5-user')

    def test_creation_liste(self):
        liste = services.creer_liste_diffusion(
            self.co, nom='Clients Casablanca', description='Zone 1')
        self.assertEqual(liste.company_id, self.co.id)

    def test_inscription_idempotente_et_normalisee(self):
        liste = services.creer_liste_diffusion(self.co, nom='L')
        services.inscrire_dans_liste(liste, '  A@X.MA  ', contact_ref='lead:1')
        services.inscrire_dans_liste(liste, 'a@x.ma')
        self.assertEqual(
            AbonnementListe.objects.filter(liste=liste).count(), 1)

    def test_inscription_normalise_telephone(self):
        liste = services.creer_liste_diffusion(self.co, nom='L')
        services.inscrire_dans_liste(liste, '06 12 34 56 78')
        services.inscrire_dans_liste(liste, '+212612345678')
        self.assertEqual(
            AbonnementListe.objects.filter(liste=liste).count(), 1)
        abo = AbonnementListe.objects.get(liste=liste)
        self.assertEqual(abo.destinataire, '212612345678')

    def test_desinscrire_de_liste(self):
        liste = services.creer_liste_diffusion(self.co, nom='L')
        services.inscrire_dans_liste(liste, 'a@x.ma')
        services.desinscrire_de_liste(liste, 'a@x.ma')
        abo = AbonnementListe.objects.get(liste=liste, destinataire='a@x.ma')
        self.assertEqual(abo.statut, AbonnementListe.Statut.DESINSCRIT)

    def test_import_rapporte_ajoutes_doublons_ignores_supprimes(self):
        liste = services.creer_liste_diffusion(self.co, nom='L')
        services.inscrire_dans_liste(liste, 'existing@x.ma')
        services.inscrire_dans_liste(liste, 'unsub@x.ma')
        services.desinscrire_de_liste(liste, 'unsub@x.ma')

        rapport = services.importer_abonnements_liste(liste, [
            {'destinataire': 'new@x.ma'},
            {'destinataire': 'existing@x.ma'},   # doublon
            {'destinataire': 'unsub@x.ma'},       # ignoré (désinscrit)
            {'destinataire': 'new@x.ma'},          # doublon dans le fichier lui-même
        ])
        self.assertEqual(rapport, {
            'ajoutes': 1, 'doublons': 2, 'ignores_supprimes': 1,
        })
        # Le désinscrit ne doit JAMAIS être ré-inscrit par l'import.
        abo = AbonnementListe.objects.get(liste=liste, destinataire='unsub@x.ma')
        self.assertEqual(abo.statut, AbonnementListe.Statut.DESINSCRIT)

    def test_ciblage_campagne_par_liste(self):
        liste = services.creer_liste_diffusion(self.co, nom='L')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        camp.listes.add(liste)
        self.assertIn(liste, camp.listes.all())
        self.assertIn(camp, liste.campagnes.all())

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt5-b', 'XMKT5-B')
        liste_a = services.creer_liste_diffusion(self.co, nom='A')
        liste_b = services.creer_liste_diffusion(other, nom='B')
        api = auth(self.user)
        resp = api.get('/api/django/compta/listes-diffusion/')
        noms = {r['nom'] for r in resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])}
        self.assertIn('A', noms)
        self.assertNotIn('B', noms)
        self.assertNotEqual(liste_a.id, liste_b.id)


class ListeDiffusionApiTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt5-api', 'XMKT5 API')
        self.user = make_user(self.co, 'xmkt5-api-user')

    def test_creer_liste_endpoint_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/listes-diffusion/', {
            'nom': 'VIP', 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        liste = ListeDiffusion.objects.get(id=resp.data['id'])
        self.assertEqual(liste.company_id, self.co.id)

    def test_importer_endpoint_avec_rapport(self):
        liste = services.creer_liste_diffusion(self.co, nom='L')
        api = auth(self.user)
        resp = api.post(
            f'/api/django/compta/listes-diffusion/{liste.id}/importer/', {
                'lignes': [
                    {'destinataire': 'a@x.ma'},
                    {'destinataire': 'a@x.ma'},
                ],
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['ajoutes'], 1)
        self.assertEqual(resp.data['doublons'], 1)

    def test_abonnes_endpoint_historique_par_contact(self):
        liste = services.creer_liste_diffusion(self.co, nom='L')
        services.inscrire_dans_liste(
            liste, 'a@x.ma', contact_ref='lead:7')
        api = auth(self.user)
        resp = api.get(
            f'/api/django/compta/listes-diffusion/{liste.id}/abonnes/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['contact_ref'], 'lead:7')
