"""Tests ZRH12 — certificat de travail légal (art. 72) — PDF.

Couvre (au niveau HTML, indépendant de WeasyPrint) :
* ``render_certificat_travail_html`` — dates d'entrée/sortie + poste(s)
  corrects ; employé non sorti -> ValueError.
* Endpoint ``employes/{id}/certificat-travail/`` — génération pour un
  employé sorti, 404 pour un actif, isolation tenant, gate admin.
* Aucun doublon avec l'attestation de travail / le reçu STC (contenu
  distinct).
"""
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import activity
from apps.rh.models import DossierEmploye, Poste
from apps.rh.pdf_sortie import render_certificat_travail_html

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


class CertificatTravailHtmlTests(TestCase):
    def setUp(self):
        self.co = make_company('ct', 'CT')
        self.employe_sorti = DossierEmploye.objects.create(
            company=self.co, matricule='CT1', nom='Sorti', prenom='Test',
            cin='AB1234', date_embauche=date(2020, 1, 15),
            date_sortie=date(2026, 3, 1),
            statut=DossierEmploye.Statut.SORTI, poste='Technicien')

    def test_html_dates_et_poste(self):
        html = render_certificat_travail_html(
            self.employe_sorti, today=date(2026, 3, 5))
        self.assertIn('Certificat de travail', html)
        self.assertIn('Sorti Test', html)
        self.assertIn('15 janvier 2020', html)
        self.assertIn('1 mars 2026', html)
        self.assertIn('Technicien', html)
        self.assertIn('article 72', html)

    def test_employe_non_sorti_leve_erreur(self):
        actif = DossierEmploye.objects.create(
            company=self.co, matricule='CT2', nom='Actif', prenom='Test',
            statut=DossierEmploye.Statut.ACTIF)
        with self.assertRaises(ValueError):
            render_certificat_travail_html(actif)

    def test_ne_duplique_pas_stc(self):
        html = render_certificat_travail_html(
            self.employe_sorti, today=date(2026, 3, 5))
        self.assertNotIn('solde de tout compte', html.lower())

    def test_historique_postes_xrh6(self):
        poste1 = Poste.objects.create(company=self.co, intitule='Poseur')
        poste2 = Poste.objects.create(company=self.co, intitule='Chef de chantier')
        employe = DossierEmploye.objects.create(
            company=self.co, matricule='CT3', nom='Multi', prenom='Poste',
            date_embauche=date(2018, 5, 1), date_sortie=date(2026, 1, 10),
            statut=DossierEmploye.Statut.EMBAUCHE, poste_ref=poste1)
        # Simule une promotion : chatter loggé automatiquement.
        old = DossierEmploye.objects.get(pk=employe.pk)
        employe.poste_ref = poste2
        employe.statut = DossierEmploye.Statut.SORTI
        employe.save()
        activity.log_changes(old, employe, None)
        html = render_certificat_travail_html(
            employe, today=date(2026, 1, 15))
        self.assertIn('Poseur', html)
        self.assertIn('Chef de chantier', html)


class CertificatTravailEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cta', 'A')
        self.co_b = make_company('ctb', 'B')
        self.user_a = make_user(self.co_a, 'ct-user-a')
        self.user_b = make_user(self.co_b, 'ct-user-b')
        self.sorti = DossierEmploye.objects.create(
            company=self.co_a, matricule='CTE1', nom='S', prenom='T',
            date_embauche=date(2020, 1, 1), date_sortie=date(2026, 2, 1),
            statut=DossierEmploye.Statut.SORTI)
        self.actif = DossierEmploye.objects.create(
            company=self.co_a, matricule='CTE2', nom='A', prenom='T',
            statut=DossierEmploye.Statut.ACTIF)

    def _url(self, employe):
        return f'/api/django/rh/employes/{employe.id}/certificat-travail/'

    def test_generation_employe_sorti(self):
        with patch(
                'apps.rh.pdf_sortie._html_to_pdf',
                return_value=b'%PDF-1.4 fake'):
            resp = auth(self.user_a).get(self._url(self.sorti))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_404_employe_actif(self):
        resp = auth(self.user_a).get(self._url(self.actif))
        self.assertEqual(resp.status_code, 404)

    def test_isolation_tenant(self):
        resp = auth(self.user_b).get(self._url(self.sorti))
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'ct-normal', role='normal')
        resp = auth(normal).get(self._url(self.sorti))
        self.assertEqual(resp.status_code, 403)
