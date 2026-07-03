"""QD2 — Helper unique de nom de fichier des documents téléchargés.

Forme : ``<Société>_<Type>_<Client>_<Référence>.pdf`` (slugifié, segments
manquants omis). Ce module teste le helper PUR ``document_filename`` :

  * nom complet avec société + type + client + référence ;
  * accents et espaces slugifiés (Reda Kasri → Reda-Kasri) ;
  * segments manquants omis (dégrade proprement) ;
  * jamais de caractère dangereux (slash/deux-points) ;
  * un Fournisseur (BCF) est accepté comme segment « client ».
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Fournisseur
from apps.ventes.utils.filenames import document_filename


class DocumentFilenameTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='TAQINOR', slug='taqinor')
        # Le nom du fichier reprend le nom du PROFIL société.
        CompanyProfile.get(company=self.company)

    def test_full_name(self):
        client = Client.objects.create(
            company=self.company, nom='Kasri', prenom='Reda')
        name = document_filename(
            'Facture', 'FAC-202607-0001', client=client, company=self.company)
        self.assertEqual(name, 'TAQINOR_Facture_Reda-Kasri_FAC-202607-0001.pdf')

    def test_accents_and_spaces_slugified(self):
        client = Client.objects.create(
            company=self.company, nom='Benâli', prenom='Amélie')
        name = document_filename(
            'Devis', 'DEV-1', client=client, company=self.company)
        self.assertEqual(name, 'TAQINOR_Devis_Amelie-Benali_DEV-1.pdf')

    def test_missing_client_omitted(self):
        name = document_filename(
            'Facture', 'FAC-1', client=None, company=self.company)
        self.assertEqual(name, 'TAQINOR_Facture_FAC-1.pdf')

    def test_missing_company_omitted(self):
        name = document_filename('Facture', 'FAC-1')
        self.assertEqual(name, 'Facture_FAC-1.pdf')

    def test_missing_reference_falls_back(self):
        name = document_filename('', '', client=None, company=None)
        self.assertEqual(name, 'document.pdf')

    def test_no_dangerous_characters(self):
        client = Client.objects.create(
            company=self.company, nom='A/B:C', prenom='X')
        name = document_filename(
            'Facture', 'FAC/2026:0001', client=client, company=self.company)
        for bad in ('/', ':', '\\', ' '):
            self.assertNotIn(bad, name)
        self.assertTrue(name.endswith('.pdf'))

    def test_fournisseur_accepted_as_client_segment(self):
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Solar Wholesale')
        name = document_filename(
            'Bon-de-commande', 'BCF-1', client=fournisseur,
            company=self.company)
        self.assertEqual(
            name, 'TAQINOR_Bon-de-commande_Solar-Wholesale_BCF-1.pdf')
