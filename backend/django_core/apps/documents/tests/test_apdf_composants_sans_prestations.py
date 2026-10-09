"""APDF33 (D-APDF-4) — les prestations (Installation, Transport) ne sont plus des
composants installés / livrés : exclues du PV et du BL, listées à part sous
« Prestations » SANS garantie constructeur dans le dossier de remise.

Constat C-APDF-014 : PV, BL et dossier de remise listaient « Installation » et
« Transport », la remise avec « Garantie selon conditions constructeur ».
Rendu WeasyPrint RÉEL, texte extrait par fitz, vraies routes HTTP.

Run :
    python manage.py test apps.documents.tests.test_apdf_composants_sans_prestations -v2
"""
import itertools
from decimal import Decimal

import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Categorie, Produit
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/documents/chantiers'


def _texte_pdf(contenu):
    doc = fitz.open(stream=contenu, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


class ComposantsTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'apdf33-co-{n}', nom=f'APDF33 Co {n}')
        self.user = User.objects.create_user(
            username=f'apdf33-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.cat_service = Categorie.objects.create(
            company=self.company, nom='Services',
            type_equipement=Categorie.TypeEquipement.SERVICE)
        self.panneau = self._produit('Panneau 550W', None, '25 ans linéaire')
        self.install = self._produit('Installation', self.cat_service)
        self.transport = self._produit('Transport', self.cat_service)

    def _produit(self, nom, categorie, garantie=''):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'APDF33-{next(_seq)}',
            prix_vente=Decimal('1000.00'), prix_achat=Decimal('500.00'),
            quantite_stock=50, marque='MarqueX', garantie=garantie,
            categorie=categorie)

    def _chantier(self, avec_nature=True):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            telephone='+212600000033')

        def row(produit, qte):
            r = {'produit_id': produit.id, 'designation': produit.nom,
                 'quantite': qte, 'marque': produit.marque}
            if avec_nature:
                r['nature'] = ('service' if produit.categorie_id
                               else 'materiel')
            return r

        return Installation.objects.create(
            company=self.company, reference=f'CH-APDF33-{next(_seq)}',
            client=client, statut=Installation.Statut.INSTALLE,
            bom=[row(self.panneau, 8.0), row(self.install, 1.0),
                 row(self.transport, 1.0)])

    def _get(self, chantier, route):
        r = self.api.get(f'{BASE}/{chantier.pk}/{route}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return _texte_pdf(b''.join(r.streaming_content)
                          if getattr(r, 'streaming', False) else r.content)

    def test_pv(self):
        texte = self._get(self._chantier(), 'pv-reception')
        self.assertIn('Panneau 550W', texte)
        self.assertNotIn('Installation', texte.replace(
            'Installation photovoltaïque', ''))
        self.assertNotIn('Transport', texte)

    def test_bl(self):
        texte = self._get(self._chantier(), 'bon-livraison')
        self.assertIn('Panneau 550W', texte)
        self.assertNotIn('Transport', texte)

    def test_remise_sans_garantie_prestation(self):
        texte = self._get(self._chantier(), 'dossier-remise')
        self.assertIn('25 ans linéaire', texte)
        self.assertIn('Prestations', texte)
        self.assertIn('Transport', texte)
        # Une seule garantie imprimée : celle du panneau, aucune par prestation.
        self.assertNotIn('Garantie selon conditions constructeur', texte)

    def test_bom_ancienne(self):
        """Nomenclature sans nature : filtrée par lecture du produit."""
        chantier = self._chantier(avec_nature=False)
        from apps.documents import builders
        self.assertEqual(
            [c['designation'] for c in builders._composants(chantier)],
            ['Panneau 550W'])
        self.assertEqual(
            [c['designation']
             for c in builders._composants(chantier, services=True)],
            ['Installation', 'Transport'])
