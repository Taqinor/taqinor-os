"""PV78 — la fiche lead expose la conception 3D de son devis.

Trois garanties :

* le sélecteur ventes est COMPANY-SCOPÉ (un devis d'une autre société ne fuit
  rien) et rend TOUJOURS ses deux clés ;
* ``crm`` lit ``ventes`` par son SÉLECTEUR, jamais par ses modèles ;
* le bloc n'est servi que sur la fiche (RETRIEVE) — jamais sur la liste, où il
  coûterait une requête + une URL pré-signée par carte.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv78_conception_lead -v 2
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.crm.selectors import conception_3d_du_lead
from apps.ventes.models import Devis
from apps.ventes.selectors import conception_pour_lead
from authentication.models import Company

User = get_user_model()

LAYOUT = {'result': {'kwc': 7.7, 'panels': 14, 'annualKwh': 12000},
          '_pans_geometry': [{'label': 'Sud', 'nb_panneaux': 14}]}


class ConceptionPourLeadTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv78-acme")
        self.other = Company.objects.create(nom="Autre", slug="pv78-autre")
        self.user = User.objects.create_user(
            username="pv78_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom="Lead PV78", telephone="0600000078")
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV78", email="pv78@example.com")
        self.crm_client_autre = Client.objects.create(
            company=self.other, nom="Client PV78 bis",
            email="pv78bis@example.com")

    def _devis(self, company=None, layout=LAYOUT, image='', lead=None):
        company = company or self.company
        return Devis.objects.create(
            company=company,
            reference="DV-PV78-%s" % Devis.objects.count(),
            client=(self.crm_client if company == self.company
                    else self.crm_client_autre),
            lead=lead if lead is not None else self.lead,
            roof_layout=layout, roof_image=image,
            etude_params={'puissance_kwc': 9.9})

    def test_toujours_les_deux_cles_sans_devis(self):
        self.assertEqual(conception_pour_lead(self.lead, self.company),
                         {'kwc': None, 'image_url': None})

    def test_kwc_lu_dans_le_calepinage(self):
        self._devis()
        self.assertEqual(
            conception_pour_lead(self.lead, self.company)['kwc'], 7.7)

    def test_repli_sur_la_puissance_de_letude(self):
        self._devis(layout={'zones': []})    # layout sans result.kwc
        self.assertEqual(
            conception_pour_lead(self.lead, self.company)['kwc'], 9.9)

    def test_devis_sans_calepinage_ignore(self):
        self._devis(layout=None)
        self.assertIsNone(
            conception_pour_lead(self.lead, self.company)['kwc'])

    def test_le_plus_recent_gagne(self):
        self._devis(layout={'result': {'kwc': 3.3}})
        self._devis(layout={'result': {'kwc': 8.8}})
        self.assertEqual(
            conception_pour_lead(self.lead, self.company)['kwc'], 8.8)

    def test_scope_societe(self):
        self._devis(company=self.other)
        # Même lead, autre société sur le devis → rien ne remonte.
        self.assertEqual(conception_pour_lead(self.lead, self.company),
                         {'kwc': None, 'image_url': None})

    def test_image_url_presignee(self):
        self._devis(image='ventes/1/rendu.png')
        with mock.patch('apps.ventes.utils.pdf.roof_image_signed_url',
                        return_value='https://minio/signed?x=1') as signe:
            resultat = conception_pour_lead(self.lead, self.company)
        self.assertEqual(resultat['image_url'], 'https://minio/signed?x=1')
        signe.assert_called_once_with('ventes/1/rendu.png')

    def test_stockage_indisponible_ne_casse_rien(self):
        self._devis(image='ventes/1/rendu.png')
        with mock.patch('apps.ventes.utils.pdf.roof_image_signed_url',
                        side_effect=RuntimeError('MinIO down')):
            resultat = conception_pour_lead(self.lead, self.company)
        self.assertIsNone(resultat['image_url'])
        self.assertEqual(resultat['kwc'], 7.7)

    def test_selecteur_crm_passe_plat(self):
        self._devis()
        self.assertEqual(conception_3d_du_lead(self.lead),
                         conception_pour_lead(self.lead, self.company))
        self.assertEqual(conception_3d_du_lead(None),
                         {'kwc': None, 'image_url': None})


class ConceptionSurLaFicheLeadTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv78b-acme")
        self.user = User.objects.create_user(
            username="pv78b_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom="Lead PV78b", telephone="0600000079")
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV78b",
            email="pv78b@example.com")
        Devis.objects.create(
            company=self.company, reference="DV-PV78B-1", lead=self.lead,
            client=self.crm_client, roof_layout=LAYOUT)

    def test_fiche_expose_la_conception(self):
        resp = self.api.get('/api/django/crm/leads/%s/' % self.lead.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('conception', resp.data)
        self.assertEqual(set(resp.data['conception']), {'kwc', 'image_url'})
        self.assertEqual(resp.data['conception']['kwc'], 7.7)

    def test_liste_ne_porte_pas_la_conception(self):
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        lignes = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertTrue(lignes)
        for ligne in lignes:
            self.assertNotIn('conception', ligne)
