"""QJR563 — la création ATOMIQUE (chemin réel du générateur) applique la même
devise par défaut de la société que ``POST /devis/``, via UN helper
(``domain.creation.devise_par_defaut``, repli MAD). Une devise fournie dans le
corps est respectée. (``/proposal`` reste libellé MAD — non asserté ici.)
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.domain.creation import devise_par_defaut
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class TestDeviseDefautCreation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='QJR563 Co', slug='qjr563-co')
        CompanyProfile.objects.update_or_create(
            company=cls.company, defaults={'devise_defaut': 'EUR'})
        cls.user = User.objects.create_user(
            username='qjr563_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='QJR563',
            email='qjr563@example.com', telephone='+212600005630')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Panneau Canadien Solar 710W',
            sku='QJR563-PV', prix_vente=Decimal('1450'), quantite_stock=10)

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _lignes(self):
        return [{'produit': self.produit.id, 'designation': self.produit.nom,
                 'quantite': '4', 'prix_unitaire': '1450'}]

    def test_helper_repli_mad(self):
        self.assertEqual(devise_par_defaut(None), 'MAD')
        self.assertEqual(devise_par_defaut(self.company), 'EUR')
        autre = Company.objects.create(nom='QJR563 Autre', slug='qjr563-autre')
        self.assertEqual(devise_par_defaut(autre), 'MAD')

    def test_post_devis_prend_la_devise_societe(self):
        r = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_obj.id, 'taux_tva': '20'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Devis.objects.get(pk=r.data['id']).devise, 'EUR')

    def test_atomic_prend_la_devise_societe(self):
        r = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'taux_tva': '20',
            'lignes': self._lignes()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Devis.objects.get(pk=r.data['id']).devise, 'EUR')

    def test_atomic_respecte_la_devise_du_corps(self):
        r = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'taux_tva': '20', 'devise': 'MAD',
            'lignes': self._lignes()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Devis.objects.get(pk=r.data['id']).devise, 'MAD')

    def test_enf17_atomic_entite_bornee_societe(self):
        """ENF17 — l'entité d'une AUTRE société = id absent (400
        « objet inexistant »), rien n'est créé ; celle de la société passe."""
        from apps.entites.models import Entite
        autre = Company.objects.create(nom='ENF17 Autre', slug='enf17-autre')
        entite_b = Entite.objects.create(
            company=autre, nom='Entité B', code='ENF17-B')
        entite_a = Entite.objects.create(
            company=self.company, nom='Entité A', code='ENF17-A')
        url = '/api/django/ventes/devis/atomic/'
        corps = {'client': self.client_obj.id, 'taux_tva': '20',
                 'lignes': self._lignes()}
        avant = Devis.objects.count()
        r = self.api.post(url, {**corps, 'entite': entite_b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['entite'][0].code, 'does_not_exist')
        self.assertEqual(Devis.objects.count(), avant)
        r = self.api.post(url, {**corps, 'entite': entite_a.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Devis.objects.get(pk=r.data['id']).entite_id,
                         entite_a.id)
