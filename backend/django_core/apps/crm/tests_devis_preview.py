"""
Régression FEATURE 0 — aperçu devis sur la fiche lead.

Deux symptômes rapportés par le fondateur :
  1. Le PDF du devis fraîchement généré s'affiche en « fichier cassé » au lieu
     de se rendre dans l'aperçu inline.
  2. Le devis fraîchement généré n'apparaît PAS dans la liste des devis du lead
     sans recharger la page.

Ce test vérifie côté serveur les deux invariants qui sous-tendent ces symptômes :
  - le chemin canonique /proposal (CLAUDE.md règle #4) SERT bien le PDF (200,
    application/pdf, octets non vides) pour un devis tout juste créé sur un lead ;
  - le détail du lead (GET /crm/leads/<id>/) renvoie immédiatement le nouveau
    devis dans sa liste `devis` (la source de la liste rafraîchie côté front).

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_devis_preview -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug='preview-co', nom='Preview Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDevisPreviewOnLead(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='preview_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        # Lead résidentiel prêt (facture renseignée) — devis auto possible.
        self.lead = Lead.objects.create(
            company=self.company, nom='Aperçu', prenom='Lead',
            email='apercu@example.com', telephone='0612345678',
            type_installation='residentiel', facture_hiver=700)
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550W',
            prix_achat=0, prix_vente=1200, quantite_stock=100)
        # Onduleur réseau : reconnu par le moteur premium (règle « options »
        # exige un onduleur réseau/injection) — devis « plein système » réaliste.
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau 5kW',
            prix_achat=0, prix_vente=8000, quantite_stock=20)

    def _create_devis_on_lead(self):
        """Crée un devis rattaché au lead + lignes (flux réel du panneau)."""
        resp = self.api.post('/api/django/ventes/devis/', {
            'lead': self.lead.id, 'statut': 'brouillon',
            'taux_tva': '20.00', 'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis_id = resp.data['id']
        for prod, desig, qte, pu in (
            (self.panneau, 'Panneau 550W', '10', '1200'),
            (self.onduleur, 'Onduleur réseau 5kW', '1', '8000'),
        ):
            ligne = self.api.post('/api/django/ventes/devis-lignes/', {
                'devis': devis_id, 'produit': prod.id,
                'designation': desig, 'quantite': qte,
                'prix_unitaire': pu, 'remise': '0',
            }, format='json')
            self.assertEqual(ligne.status_code, 201, ligne.data)
        return devis_id

    def test_proposal_serves_pdf_for_fresh_devis(self):
        """Symptôme 1 : /proposal renvoie un vrai PDF (pas une erreur)."""
        devis_id = self._create_devis_on_lead()
        resp = self.api.get(
            f'/api/django/ventes/devis/{devis_id}/proposal/?pdf_mode=full')
        self.assertEqual(resp.status_code, 200,
                         getattr(resp, 'data', resp.content[:300]))
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        content = b''.join(resp.streaming_content) if getattr(
            resp, 'streaming', False) else resp.content
        self.assertTrue(content.startswith(b'%PDF'), 'pas un PDF')
        self.assertGreater(len(content), 1000)

    def test_proposal_onepage_serves_pdf(self):
        devis_id = self._create_devis_on_lead()
        resp = self.api.get(
            f'/api/django/ventes/devis/{devis_id}/proposal/?pdf_mode=onepage')
        self.assertEqual(resp.status_code, 200,
                         getattr(resp, 'data', resp.content[:300]))
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_fresh_devis_appears_in_lead_detail(self):
        """Symptôme 2 : le devis apparaît tout de suite dans lead.devis."""
        devis_id = self._create_devis_on_lead()
        resp = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(resp.status_code, 200)
        ids = [d['id'] for d in resp.data['devis']]
        self.assertIn(devis_id, ids)
        row = [d for d in resp.data['devis'] if d['id'] == devis_id][0]
        self.assertTrue(row['reference'])
        self.assertEqual(row['statut'], 'brouillon')

    def test_proposal_company_scoped(self):
        """Un autre tenant ne peut pas servir le PDF d'un devis étranger."""
        devis_id = self._create_devis_on_lead()
        other = make_company(slug='preview-other', nom='Other')
        intruder = User.objects.create_user(
            username='preview_intruder', password='x',
            role_legacy='responsable', company=other)
        resp = make_api(intruder).get(
            f'/api/django/ventes/devis/{devis_id}/proposal/')
        self.assertEqual(resp.status_code, 404)
        # Sanity: le devis existe bien dans le bon tenant.
        self.assertTrue(Devis.objects.filter(pk=devis_id).exists())
