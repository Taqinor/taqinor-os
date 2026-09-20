"""CAL16 — le viewset CRUD du pivot, ses filtres et ses refus.

Ce qui est prouvé ici :

* CHAQUE filtre (``?lead=`` ``?client=`` ``?statut=`` ``?depuis=`` ``?q=``)
  change RÉELLEMENT le jeu renvoyé — la leçon PV22 est qu'un ``?statut=``
  ignoré fait ouvrir le mauvais objet ;
* un filtre ILLISIBLE (statut inconnu, date invalide) est refusé 400 en
  NOMMANT le champ, jamais avalé en silence ;
* ``POST`` accepte lead XOR client, refuse les deux et refuse aucun, avec un
  message français qui NOMME le champ fautif ;
* un ``company`` envoyé dans le corps est IGNORÉ (la société est celle de
  l'appelant, posée côté serveur) ;
* sans ``calepinage_voir`` la liste répond 403 ;
* un calepinage d'une AUTRE société est introuvable (404), jamais « interdit ».

Run :
    python manage.py test apps.calepinage.tests.test_api_liste -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.roles.models import DIRECTEUR_PERMISSIONS, TECHNICIEN_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/calepinage/calepinages/'


def url_detail(pk):
    return f'{URL}{pk}/'


class BaseApiCalepinage(TestCase):
    """Deux sociétés, un porteur des droits, un technicien sans droit."""

    def setUp(self):
        self.company = Company.objects.create(nom='Calep Co',
                                              slug='calep-co-16')
        self.autre = Company.objects.create(nom='Voisine Co',
                                            slug='voisine-co-16')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.role_autre = Role.objects.create(
            company=self.autre, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.role_sans = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS))
        self.user = User.objects.create_user(
            username='cal_api', password='x', company=self.company,
            role=self.role)
        self.user_autre = User.objects.create_user(
            username='cal_api_voisin', password='x', company=self.autre,
            role=self.role_autre)
        self.user_sans = User.objects.create_user(
            username='cal_api_tech', password='x', company=self.company,
            role=self.role_sans)
        self.api = self._client(self.user)
        self.api_autre = self._client(self.user_autre)
        self.api_sans = self._client(self.user_sans)

        self.lead = Lead.objects.create(company=self.company,
                                        nom='Toiture Anfa')
        self.lead_2 = Lead.objects.create(company=self.company,
                                          nom='Toiture Maârif')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')

    @staticmethod
    def _client(user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    @staticmethod
    def _lignes(reponse):
        donnees = reponse.data
        if isinstance(donnees, dict) and 'results' in donnees:
            return donnees['results']
        return donnees


class FiltresListeTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.sur_lead = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            titre='Villa Anfa', statut=Calepinage.Statut.BROUILLON)
        self.sur_lead_2 = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk,
            titre='Hangar Maârif', statut=Calepinage.Statut.VALIDE)
        self.sur_client = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            titre='Usine Atlas', statut=Calepinage.Statut.BROUILLON)
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=999, titre='Chez la voisine')

    def _ids(self, **params):
        reponse = self.api.get(URL, params)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return {ligne['id'] for ligne in self._lignes(reponse)}

    def test_liste_bornee_societe(self):
        ids = self._ids()
        self.assertEqual(
            ids, {self.sur_lead.pk, self.sur_lead_2.pk, self.sur_client.pk})
        self.assertNotIn(self.etranger.pk, ids)

    def test_filtre_lead(self):
        self.assertEqual(self._ids(lead=self.lead.pk), {self.sur_lead.pk})

    def test_filtre_client(self):
        self.assertEqual(self._ids(client=self.client_a.pk),
                         {self.sur_client.pk})

    def test_filtre_statut(self):
        self.assertEqual(self._ids(statut=Calepinage.Statut.VALIDE),
                         {self.sur_lead_2.pk})

    def test_filtre_q_sur_le_titre(self):
        self.assertEqual(self._ids(q='anfa'), {self.sur_lead.pk})

    def test_filtre_depuis(self):
        from datetime import timedelta

        demain = (self.sur_lead.created_at + timedelta(days=1)).date()
        self.assertEqual(self._ids(depuis=demain.isoformat()), set())
        hier = (self.sur_lead.created_at - timedelta(days=1)).date()
        self.assertEqual(len(self._ids(depuis=hier.isoformat())), 3)

    def test_statut_inconnu_refuse_en_nommant_le_champ(self):
        reponse = self.api.get(URL, {'statut': 'en_cours'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('statut', reponse.data)

    def test_date_illisible_refusee_en_nommant_le_champ(self):
        reponse = self.api.get(URL, {'depuis': 'la semaine dernière'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('depuis', reponse.data)

    def test_detail_d_une_autre_societe_est_introuvable(self):
        reponse = self.api.get(url_detail(self.etranger.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_de_lecture_403(self):
        reponse = self.api_sans.get(URL)
        self.assertEqual(reponse.status_code, 403)


class CreationTest(BaseApiCalepinage):
    def test_creation_sur_lead(self):
        reponse = self.api.post(URL, {'lead': self.lead.pk,
                                      'titre': 'Villa Anfa'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        calepinage = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(calepinage.company_id, self.company.pk)
        self.assertEqual(calepinage.lead_id, self.lead.pk)
        self.assertEqual(calepinage.cree_par_id, self.user.pk)

    def test_creation_sur_client(self):
        reponse = self.api.post(URL, {'client': self.client_a.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            Calepinage.objects.get(pk=reponse.data['id']).client_id,
            self.client_a.pk)

    def test_les_deux_refuses_en_nommant_le_champ(self):
        reponse = self.api.post(
            URL, {'lead': self.lead.pk, 'client': self.client_a.pk},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('client', reponse.data)

    def test_aucun_des_deux_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(URL, {'titre': 'Orphelin'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('client', reponse.data)

    def test_lead_d_une_autre_societe_introuvable(self):
        lead_voisin = Lead.objects.create(company=self.autre, nom='Voisin')
        reponse = self.api.post(URL, {'lead': lead_voisin.pk}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('lead', reponse.data)

    def test_client_d_une_autre_societe_refuse(self):
        client_voisin = Client.objects.create(company=self.autre,
                                              nom='Client voisin')
        reponse = self.api.post(URL, {'client': client_voisin.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('client', reponse.data)

    def test_company_du_corps_est_ignoree(self):
        reponse = self.api.post(
            URL, {'lead': self.lead.pk, 'company': self.autre.pk},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            Calepinage.objects.get(pk=reponse.data['id']).company_id,
            self.company.pk)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self.api_sans.post(URL, {'lead': self.lead.pk},
                                     format='json')
        self.assertEqual(reponse.status_code, 403)
