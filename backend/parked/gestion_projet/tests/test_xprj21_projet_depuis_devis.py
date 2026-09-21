"""Tests XPRJ21 — créer un projet depuis un devis accepté.

Couvre : projet + lien + budget créés depuis un devis de la MÊME société
(autre société → 404), re-run sur le même devis → 400 « déjà lié », et la
lecture du devis via ``apps.ventes.selectors.devis_pour_projet`` (jamais un
import de ``ventes.models`` côté gestion_projet).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

from apps.gestion_projet.models import BudgetProjet, ProjetLien
from apps.gestion_projet.services import (
    DevisVersProjetError, creer_projet_depuis_devis,
)
from apps.ventes.selectors import devis_pour_projet

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


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


class DevisPourProjetSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj21-sel', 'S')
        self.client_obj = Client.objects.create(
            company=self.co, nom='Client', prenom='X',
            email='x21@example.com', telephone='+212600000021')
        self.devis = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0021',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        produit_mat = Produit.objects.create(
            company=self.co, nom='Panneau', sku='X21-PAN',
            prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
            quantite_stock=10)
        produit_mo = Produit.objects.create(
            company=self.co, nom='Pose', sku='X21-POSE',
            prix_vente=Decimal('500'), prix_achat=Decimal('1'),
            quantite_stock=10)
        LigneDevis.objects.create(
            devis=self.devis, produit=produit_mat, designation='Panneau solaire',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
        LigneDevis.objects.create(
            devis=self.devis, produit=produit_mo, designation='Installation',
            quantite=Decimal('1'), prix_unitaire=Decimal('4000'))

    def test_selector_ventile_materiel_main_oeuvre(self):
        data = devis_pour_projet(self.devis.id, self.co)
        self.assertIsNotNone(data)
        self.assertEqual(data['montant_materiel'], Decimal('10000'))
        self.assertEqual(data['montant_main_oeuvre'], Decimal('4000'))

    def test_selector_none_si_pas_accepte(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save()
        data = devis_pour_projet(self.devis.id, self.co)
        self.assertIsNone(data)

    def test_selector_none_autre_societe(self):
        autre_co = make_company('gp-xprj21-autre-sel', 'Autre')
        data = devis_pour_projet(self.devis.id, autre_co)
        self.assertIsNone(data)


class CreerProjetDepuisDevisServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj21-svc', 'S')
        self.client_obj = Client.objects.create(
            company=self.co, nom='Client', prenom='Y',
            email='y21@example.com', telephone='+212600000022')
        self.devis = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0022',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))

    def test_creation_projet_lien_budget(self):
        devis_data = devis_pour_projet(self.devis.id, self.co)
        resultat = creer_projet_depuis_devis(devis_data, company=self.co)
        self.assertTrue(resultat['projet'].code.startswith('PRJ-'))
        self.assertEqual(resultat['lien'].cible_id, self.devis.id)
        self.assertEqual(resultat['budget'].projet_id, resultat['projet'].id)

    def test_rerun_meme_devis_refuse(self):
        devis_data = devis_pour_projet(self.devis.id, self.co)
        creer_projet_depuis_devis(devis_data, company=self.co)
        with self.assertRaises(DevisVersProjetError):
            creer_projet_depuis_devis(devis_data, company=self.co)

    def test_code_reprend_le_plus_haut_suffixe_apres_suppression(self):
        """ARC7 — continuité de numérotation : un ``Projet`` supprimé ne doit
        JAMAIS faire régresser le prochain code (jamais ``count()+1``, qui
        collisionnerait après une suppression). Crée 3 projets, supprime celui
        du MILIEU (le compte redescend à 2 mais le plus haut suffixe utilisé
        reste 3), puis vérifie que le 4e projet reprend bien à suffixe 4 (pas
        3, qui collisionnerait avec le projet #3 encore existant)."""
        from apps.gestion_projet.models import Projet

        devis_ids = []
        for i in range(3):
            client_obj = Client.objects.create(
                company=self.co, nom='Client', prenom=f'C{i}',
                email=f'cont{i}@example.com', telephone=f'+21260000003{i}')
            devis = Devis.objects.create(
                company=self.co, reference=f'DEV-{MONTH}-010{i}',
                client=client_obj, statut=Devis.Statut.ACCEPTE,
                taux_tva=Decimal('20'))
            devis_ids.append(devis.id)

        codes = []
        for devis_id in devis_ids:
            devis_data = devis_pour_projet(devis_id, self.co)
            resultat = creer_projet_depuis_devis(devis_data, company=self.co)
            codes.append(resultat['projet'].code)

        # Les 3 codes sont des suffixes consécutifs croissants (PRJ-<année>-NNNN).
        suffixes = [int(c.rsplit('-', 1)[1]) for c in codes]
        self.assertEqual(suffixes, sorted(suffixes))
        self.assertEqual(suffixes[-1] - suffixes[0], 2)

        # Supprime le projet du MILIEU : le compte baisse mais le plus haut
        # suffixe utilisé (celui du 3e projet) reste en base.
        milieu_code = codes[1]
        Projet.objects.filter(company=self.co, code=milieu_code).delete()

        client_obj_4 = Client.objects.create(
            company=self.co, nom='Client', prenom='C4',
            email='cont4@example.com', telephone='+212600000034')
        devis_4 = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0104',
            client=client_obj_4, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        devis_data_4 = devis_pour_projet(devis_4.id, self.co)
        resultat_4 = creer_projet_depuis_devis(devis_data_4, company=self.co)

        suffixe_4 = int(resultat_4['projet'].code.rsplit('-', 1)[1])
        # Reprend au suffixe suivant le plus haut RÉELLEMENT utilisé (suffixes[-1] + 1),
        # jamais au suffixe libéré par la suppression (qui collisionnerait si
        # un autre projet gardait une référence à l'ancien trou).
        self.assertEqual(suffixe_4, suffixes[-1] + 1)
        # Le code n'est jamais réutilisé (unique_together company+code tiendrait
        # de toute façon, mais on vérifie l'algorithme, pas seulement la
        # contrainte DB).
        self.assertNotEqual(resultat_4['projet'].code, milieu_code)


class DepuisDevisEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj21-api', 'S')
        self.user = make_user(self.co, 'resp-xprj21')
        self.client_obj = Client.objects.create(
            company=self.co, nom='Client', prenom='Z',
            email='z21@example.com', telephone='+212600000023')
        self.devis = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0023',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))

    def test_endpoint_creation(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/gestion-projet/projets/depuis-devis/',
            {'devis_id': self.devis.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            ProjetLien.objects.filter(
                cible_id=self.devis.id,
                type_cible=ProjetLien.TypeCible.DEVIS).exists())
        self.assertTrue(
            BudgetProjet.objects.filter(
                projet_id=resp.data['id']).exists())

    def test_endpoint_rerun_400(self):
        api = auth(self.user)
        api.post(
            '/api/django/gestion-projet/projets/depuis-devis/',
            {'devis_id': self.devis.id}, format='json')
        resp2 = api.post(
            '/api/django/gestion-projet/projets/depuis-devis/',
            {'devis_id': self.devis.id}, format='json')
        self.assertEqual(resp2.status_code, 400)

    def test_endpoint_404_autre_societe(self):
        autre_co = make_company('gp-xprj21-autre-api', 'Autre')
        autre_user = make_user(autre_co, 'user-autre-x21')
        api = auth(autre_user)
        resp = api.post(
            '/api/django/gestion-projet/projets/depuis-devis/',
            {'devis_id': self.devis.id}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_404_non_accepte(self):
        devis_brouillon = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0024',
            client=self.client_obj, statut=Devis.Statut.BROUILLON)
        api = auth(self.user)
        resp = api.post(
            '/api/django/gestion-projet/projets/depuis-devis/',
            {'devis_id': devis_brouillon.id}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_devis_id_obligatoire(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/gestion-projet/projets/depuis-devis/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)
