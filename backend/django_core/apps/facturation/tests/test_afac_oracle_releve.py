"""AFAC97 (C-AFAC-031 + C-AFAC-049) — l'oracle ``oracles_releve`` tient sur
chaque surface : relevé API, relevé PDF (PyMuPDF), relevé du portail et bloc
« Déjà payé / Reste » du PDF facture — Facturé + Notes de débit − Payé −
Avoirs − RAS − Abandons = Solde dû, au centime, chaque terme = le service
unique ``decomposition_du``.

Rejoue la sonde FCOR-8 (facture 100 000 + ND 10 000 :
`{facture 100000.00, paye 0.00, avoirs 0.00, du 110000.00}`). Documents
créés par les services réels (API) ; seul l'upload MinIO est neutralisé.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_oracle_releve"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facturation.tests import oracles_releve

User = get_user_model()
BASE = '/api/django/ventes/factures/'


def _texte(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class OracleReleveTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(nom='AFAC97', slug='afac97-co')
        self.admin = User.objects.create_user(
            username='afac97_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Oracle', prenom='AFAC97',
            email='afac97@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Geste', sku='AFAC97-G',
            prix_vente=Decimal('0'))
        p_up = patch('apps.ventes.utils.pdf._upload_pdf')
        p_up.start()
        self.addCleanup(p_up.stop)
        self.factures = self._scenario()

    def _facture(self, ttc):
        from apps.ventes.models import Facture
        n = Facture.objects.filter(company=self.company).count() + 1
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC97-{n:04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=ttc / Decimal('1.2'),
            montant_tva=ttc / Decimal('6'), montant_ttc=ttc)

    def _post(self, url, corps):
        r = self.api.post(url, corps, format='json')
        self.assertIn(r.status_code, (200, 201), (url, r.data))
        return r

    def _scenario(self):
        jour = str(timezone.localdate())
        # F1 : 100 000 + note de débit 10 000 (la ND AUGMENTE le dû).
        f1 = self._facture(Decimal('100000'))
        self._post(f'{BASE}{f1.id}/creer-note-debit/', {
            'motif': 'Complément', 'montant': '10000', 'taux_tva': '0'})
        # F2 : 12 000, paiement 2 000, avoir partiel 1 200 TTC.
        f2 = self._facture(Decimal('12000'))
        self._post(f'{BASE}{f2.id}/enregistrer-paiement/', {
            'montant': '2000', 'date_paiement': jour, 'mode': 'virement'})
        self._post(f'{BASE}{f2.id}/creer-avoir/', {
            'motif': 'Geste', 'lignes': [{
                'designation': 'Geste', 'quantite': '1',
                'prix_unitaire': '1000', 'produit': self.produit.id,
                'taux_tva': '20'}]})
        # F3 : 12 000, paiement 10 000 + RAS-TVA 75 % (1 500), abandon du
        # reliquat (500).
        f3 = self._facture(Decimal('12000'))
        self._post(f'/api/django/ventes/paiements/factures/{f3.id}/'
                   'paiement-avec-retenue/', {
                       'montant': '10000', 'date_paiement': jour,
                       'mode': 'virement', 'type_retenue': 'ras_tva',
                       'taux': '75'})
        self._post(f'{BASE}{f3.id}/abandonner-solde/',
                   {'motif': 'geste_commercial'})
        return [f1, f2, f3]

    def test_identite_releve_api(self):
        r = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/releve/')
        self.assertEqual(r.status_code, 200, r.data)
        lus = oracles_releve.verifier_decomposition_du(
            r.data['totaux'], self.client_obj, 'relevé API')
        self.assertEqual(lus['notes_debit'], Decimal('10000.00'))
        self.assertEqual(lus['du'], Decimal('118800.00'))
        for ligne in r.data['lignes']:
            oracles_releve.verifier_identite(
                {**ligne, 'facture': ligne['total_ttc']},
                f'ligne {ligne["reference"]}')

    def test_identite_releve_pdf(self):
        from apps.ventes.selectors_facturation import releve_client_pdf_bytes
        texte = _texte(releve_client_pdf_bytes(self.client_obj))
        oracles_releve.verifier_decomposition_du(
            oracles_releve.totaux_releve_pdf(texte), self.client_obj,
            'relevé PDF')

    def test_identite_portail(self):
        from apps.ventes.selectors_facturation import releve_client_portail
        data = releve_client_portail(self.client_obj)
        oracles_releve.verifier_decomposition_du(
            data['totaux'], self.client_obj, 'portail')
        self.assertEqual(Decimal(data['solde_courant']),
                         Decimal(data['totaux']['du']))

    def test_bloc_reste_pdf_facture(self):
        for facture in self.factures[1:]:
            oracles_releve.verifier_bloc_reste_facture(facture)
