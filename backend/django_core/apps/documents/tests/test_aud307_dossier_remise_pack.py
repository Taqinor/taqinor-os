"""AUD307 — le PDF « dossier de remise » (N23) lit enfin le pack CH4.

Défaut : deux « dossiers de remise » indépendants coexistaient. Le PDF client
(`generate_dossier_remise`) se construisait depuis `_composants` + un texte
statique (`DEFAULT_OPERATING_GUIDANCE`) sans jamais lire
`chantier.handover_pack` — le `HandoverPack` (as-built, datasheets, garanties,
certificat de recette IEC 62446-1, dossier 82-21, accès monitoring) dont
`complet` gate pourtant la remise. Une équipe pouvait donc confirmer
`pack_remise.complet=True` puis remettre au client un PDF ne contenant AUCUNE
des pièces validées.

Run :
    docker compose exec django_core python manage.py test \
        apps.documents.tests.test_aud307_dossier_remise_pack -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import HandoverPack, Installation
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

PIECES = [
    {'type': 'as_built', 'libelle': 'Dossier as-built / schémas',
     'reference': 'ASB-2026-014', 'present': True},
    {'type': 'recette', 'libelle': 'Certificat de recette IEC 62446-1',
     'reference': 'REC-2026-009', 'present': True},
    {'type': 'dossier_82_21', 'libelle': 'Dossier réglementaire loi 82-21',
     'reference': 'DOS-82-21-77', 'present': True},
    {'type': 'garanties', 'libelle': 'Garanties équipements',
     'reference': '', 'present': False},
]


def _company():
    return Company.objects.get_or_create(
        slug='aud307-co', defaults={'nom': 'AUD307 Co'})[0]


def _chantier(company, ref):
    client = Client.objects.create(
        company=company, nom='Chraibi', prenom='Youssef',
        telephone='+212600000307', adresse='7 rue Test, Marrakech')
    produit = Produit.objects.create(
        company=company, nom='Onduleur hybride 5kW', sku=f'OND-{ref}',
        prix_vente=Decimal('9000.00'), prix_achat=Decimal('555.55'),
        quantite_stock=4, marque='Deye', garantie='10 ans')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{ref}', client=client,
        statut='accepte', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'))
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Onduleur hybride 5kW',
        quantite=Decimal('1'), prix_unitaire=Decimal('9000.00'),
        remise=Decimal('0'))
    return Installation.objects.create(
        company=company, reference=ref, client=client, devis=devis,
        puissance_installee_kwc=Decimal('5.00'),
        date_mise_en_service='2026-06-01', date_pose_reelle='2026-05-28',
        site_adresse='7 rue Test', site_ville='Marrakech')


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class DossierRemisePackTests(TestCase):
    def setUp(self):
        self.company = _company()

    def _html(self, mock_pdf, chantier):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        builders.generate_dossier_remise(chantier)
        return mock_pdf.call_args[0][0]

    def test_sans_pack_le_document_reste_inchange(self, mock_pdf, _dl):
        from apps.documents import builders
        chantier = _chantier(self.company, 'CH-AUD307-NOPACK')

        html = self._html(mock_pdf, chantier)

        self.assertIsNone(builders._handover_pack_summary(chantier))
        self.assertNotIn('Pièces du dossier de remise', html)
        # Le corps historique est intact.
        self.assertIn('Exploitation', html)
        self.assertIn('DOSSIER DE REMISE', html)

    def test_pack_complet_liste_ses_pieces_dans_le_pdf(self, mock_pdf, _dl):
        """LE scénario de la fiche : `complet=True` doit se voir dans le PDF."""
        chantier = _chantier(self.company, 'CH-AUD307-FULL')
        HandoverPack.objects.create(
            company=self.company, installation=chantier, pieces=PIECES,
            complet=True, monitoring_acces='https://monitoring.example.com/abc')

        html = self._html(mock_pdf, chantier)

        self.assertIn('Pièces du dossier de remise (3/4)', html)
        self.assertIn('dossier complet', html)
        self.assertIn('Certificat de recette IEC 62446-1', html)
        self.assertIn('REC-2026-009', html)
        self.assertIn('Dossier réglementaire loi 82-21', html)
        self.assertIn('Dossier as-built', html)
        self.assertIn('https://monitoring.example.com/abc', html)

    def test_pack_incomplet_est_annonce_comme_tel(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AUD307-PART')
        HandoverPack.objects.create(
            company=self.company, installation=chantier,
            pieces=[PIECES[0], PIECES[3]], complet=False)

        html = self._html(mock_pdf, chantier)

        self.assertIn('Pièces du dossier de remise (1/2)', html)
        self.assertIn('dossier incomplet', html)

    def test_pieces_malformees_ignorees_sans_casser_la_generation(
            self, mock_pdf, _dl):
        from apps.documents import builders
        chantier = _chantier(self.company, 'CH-AUD307-BAD')
        HandoverPack.objects.create(
            company=self.company, installation=chantier,
            pieces=['pas-un-dict', None, PIECES[1]], complet=False)

        resume = builders._handover_pack_summary(chantier)
        html = self._html(mock_pdf, chantier)

        self.assertEqual(resume['total'], 1)
        self.assertIn('Certificat de recette IEC 62446-1', html)

    def test_aucun_prix_achat_ne_fuit(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AUD307-LEAK')
        HandoverPack.objects.create(
            company=self.company, installation=chantier, pieces=PIECES,
            complet=True)

        html = self._html(mock_pdf, chantier)

        self.assertNotIn('555.55', html)
        self.assertNotIn('prix_achat', html)
