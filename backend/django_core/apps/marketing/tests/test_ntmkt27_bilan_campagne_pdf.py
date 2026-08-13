"""NTMKT27 — Rapport imprimable « Bilan de campagne » (PDF interne).

Jamais un devis client (règle #4 — le PDF client reste ``/proposal`` +
``quote_engine``) : ce PDF interne agrège entonnoir / top liens / coût-ROI,
jamais ``Produit.prix_achat`` (hors sujet ici de toute façon).
"""
from unittest.mock import patch

from django.test import TestCase, tag
from django.contrib.auth import get_user_model

from authentication.models import Company

from apps.marketing import services as mkt_services
from apps.marketing.models import Campagne, EnvoiCampagne, LienTrackee

User = get_user_model()


class RapportCampagneDonneesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt27', nom='NTMKT27')
        self.campagne = Campagne.objects.create(
            company=self.co, nom='Bilan Test', nb_envois=10, nb_ouvertures=6,
            nb_clics=3, cout_reel_mad=200)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=self.campagne, destinataire='a@b.ma',
            statut=EnvoiCampagne.Statut.ENVOYE)
        LienTrackee.objects.create(
            company=self.co, campagne=self.campagne,
            token='tok-ntmkt27', url_cible='https://taqinor.ma/x', nb_clics=5)

    def test_donnees_contiennent_les_4_sections(self):
        donnees = mkt_services.rapport_campagne_donnees(self.campagne)
        self.assertEqual(donnees['entonnoir']['envoyes'], 10)
        self.assertEqual(donnees['entonnoir']['ouverts'], 6)
        self.assertEqual(donnees['entonnoir']['cliques'], 3)
        self.assertEqual(len(donnees['top_liens']), 1)
        self.assertEqual(donnees['top_liens'][0]['nb_clics'], 5)
        self.assertIn('cout_mad', donnees['roi'])

    @tag('weasyprint')
    def test_pdf_ne_leve_pas_et_produit_des_octets(self):
        pdf_bytes = mkt_services.rapport_campagne_pdf(self.campagne)
        self.assertTrue(pdf_bytes)


@tag('weasyprint')
class RapportCampagnePdfEndpointTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt27b', nom='NTMKT27b')
        self.user = User.objects.create_user(
            username='ntmkt27_user', password='x', role_legacy='responsable',
            company=self.co)
        self.campagne = Campagne.objects.create(company=self.co, nom='C')

    def test_endpoint_exige_une_authentification(self):
        res = self.client.get(
            f'/api/django/marketing/campagnes/{self.campagne.id}/rapport-pdf/')
        self.assertIn(res.status_code, (401, 403))

    def test_endpoint_renvoie_un_pdf(self):
        self.client.force_login(self.user)
        with patch('apps.marketing.services.rapport_campagne_pdf',
                   return_value=b'%PDF-1.4 stub'):
            res = self.client.get(
                f'/api/django/marketing/campagnes/{self.campagne.id}'
                '/rapport-pdf/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')

    def test_scoping_societe_404_sur_campagne_etrangere(self):
        autre = Company.objects.create(slug='ntmkt27c', nom='Autre')
        campagne_autre = Campagne.objects.create(company=autre, nom='C2')
        self.client.force_login(self.user)
        res = self.client.get(
            f'/api/django/marketing/campagnes/{campagne_autre.id}'
            '/rapport-pdf/')
        self.assertEqual(res.status_code, 404)
