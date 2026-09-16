"""STKCAT6 — `GET /api/django/stock/produits/?categorie=<id[,id]>`.

Le filtre est MANUEL (aucun ``DjangoFilterBackend`` n'est monté sur ce
viewset : un ``filterset_fields`` y serait un no-op SILENCIEUX). Ce que ces
tests verrouillent :

  * ``?categorie=<id>`` et ``?categorie=<id,id>`` filtrent réellement ;
  * ``?categorie=abc`` (ou vide) est IGNORÉ — jamais un 500 sur un paramètre
    d'URL mal tapé (``categorie_id=<texte>`` lèverait un ``ValueError``) ;
  * le scoping société de ``super().get_queryset()`` reste posé EN AMONT : le
    produit d'une autre société n'apparaît pas, même en visant SA catégorie.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
from apps.stock.models import Categorie, Produit
from authentication.models import Company

User = get_user_model()

URL_PRODUITS = '/api/django/stock/produits/'


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def noms(reponse):
    """Les désignations rendues, quelle que soit l'enveloppe (paginée ou non)."""
    data = reponse.data
    lignes = data['results'] if isinstance(data, dict) else data
    return [ligne['nom'] for ligne in lignes]


class STKCAT6FiltreBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='stkcat6-filtre-co', defaults={'nom': 'STKCAT6 Filtre Co'})[0]
        cls.other_company = Company.objects.get_or_create(
            slug='stkcat6-filtre-co-other',
            defaults={'nom': 'STKCAT6 Filtre Other Co'})[0]
        cls.roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            cls.roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.user = User.objects.create_user(
            username='stkcat6_filtre_dir', password='x', company=cls.company,
            role=cls.roles['Directeur'])

        cls.cat_structures = Categorie.objects.create(
            company=cls.company, nom='STKCAT6F Structures', ordre=10,
            type_equipement=Categorie.TypeEquipement.STRUCTURE)
        cls.cat_panneaux = Categorie.objects.create(
            company=cls.company, nom='STKCAT6F Panneaux', ordre=20,
            type_equipement=Categorie.TypeEquipement.PANNEAU)
        cls.cat_divers = Categorie.objects.create(
            company=cls.company, nom='STKCAT6F Divers', ordre=30)
        cls.cat_autre_societe = Categorie.objects.create(
            company=cls.other_company, nom='STKCAT6F Structures voisines',
            ordre=10, type_equipement=Categorie.TypeEquipement.STRUCTURE)

        cls.structure = Produit.objects.create(
            company=cls.company, nom='STKCAT6F Pergola acier 4x3',
            categorie=cls.cat_structures, prix_vente=Decimal('18000'))
        cls.panneau = Produit.objects.create(
            company=cls.company, nom='STKCAT6F Panneau 710W',
            categorie=cls.cat_panneaux, prix_vente=Decimal('1450'))
        cls.divers = Produit.objects.create(
            company=cls.company, nom='STKCAT6F Visserie',
            categorie=cls.cat_divers, prix_vente=Decimal('50'))
        cls.produit_voisin = Produit.objects.create(
            company=cls.other_company, nom='STKCAT6F Pergola voisine',
            categorie=cls.cat_autre_societe, prix_vente=Decimal('19000'))


class TestFiltreCategorie(STKCAT6FiltreBase):
    def test_un_seul_id_filtre(self):
        r = api_for(self.user).get(
            URL_PRODUITS, {'categorie': self.cat_structures.id})
        self.assertEqual(r.status_code, 200, r.data)
        rendus = noms(r)
        self.assertIn('STKCAT6F Pergola acier 4x3', rendus)
        self.assertNotIn('STKCAT6F Panneau 710W', rendus)
        self.assertNotIn('STKCAT6F Visserie', rendus)

    def test_liste_d_ids_separes_par_des_virgules(self):
        r = api_for(self.user).get(URL_PRODUITS, {
            'categorie': '%s,%s' % (self.cat_structures.id,
                                    self.cat_panneaux.id)})
        self.assertEqual(r.status_code, 200, r.data)
        rendus = noms(r)
        self.assertIn('STKCAT6F Pergola acier 4x3', rendus)
        self.assertIn('STKCAT6F Panneau 710W', rendus)
        self.assertNotIn('STKCAT6F Visserie', rendus)

    def test_valeur_non_numerique_ignoree_jamais_500(self):
        r = api_for(self.user).get(
            URL_PRODUITS, {'categorie': 'abc', 'page_size': 200})
        self.assertEqual(r.status_code, 200, r.data)
        rendus = noms(r)
        # Ignorée = AUCUN filtre : la liste complète de la société revient.
        self.assertIn('STKCAT6F Pergola acier 4x3', rendus)
        self.assertIn('STKCAT6F Panneau 710W', rendus)
        self.assertIn('STKCAT6F Visserie', rendus)

    def test_valeur_vide_ignoree(self):
        r = api_for(self.user).get(
            URL_PRODUITS, {'categorie': '', 'page_size': 200})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('STKCAT6F Visserie', noms(r))

    def test_liste_mixte_ne_garde_que_les_ids_numeriques(self):
        r = api_for(self.user).get(URL_PRODUITS, {
            'categorie': 'abc,%s' % self.cat_structures.id})
        self.assertEqual(r.status_code, 200, r.data)
        rendus = noms(r)
        self.assertIn('STKCAT6F Pergola acier 4x3', rendus)
        self.assertNotIn('STKCAT6F Panneau 710W', rendus)

    def test_sans_parametre_comportement_inchange(self):
        r = api_for(self.user).get(URL_PRODUITS, {'page_size': 200})
        self.assertEqual(r.status_code, 200, r.data)
        rendus = noms(r)
        self.assertIn('STKCAT6F Pergola acier 4x3', rendus)
        self.assertIn('STKCAT6F Panneau 710W', rendus)
        self.assertIn('STKCAT6F Visserie', rendus)


class TestScopingSocieteEnAmont(STKCAT6FiltreBase):
    def test_la_categorie_d_une_autre_societe_ne_fait_rien_fuiter(self):
        """Le filtre s'ajoute APRÈS le scoping société : viser la catégorie
        d'une autre société rend une liste VIDE, jamais son produit."""
        r = api_for(self.user).get(
            URL_PRODUITS, {'categorie': self.cat_autre_societe.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(noms(r), [])

    def test_le_produit_voisin_n_apparait_dans_aucune_liste(self):
        r = api_for(self.user).get(URL_PRODUITS, {'page_size': 200})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn('STKCAT6F Pergola voisine', noms(r))
