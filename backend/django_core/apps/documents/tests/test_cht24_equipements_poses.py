"""CHT24 — Dossier de remise : le matériel RÉELLEMENT posé.

Défaut corrigé : `generate_dossier_remise` (documents/builders.py) lisait
uniquement les lignes du DEVIS (`_composants`) — l'intention commerciale, pas
ce qui a été réellement installé. Cette tâche ajoute une section « Équipements
posés » depuis le parc réel (`sav.Equipement`, related_name `equipements`
vérifié sur `Equipement.installation`) : n° de série, marque, modèle, dates
de garantie CALCULÉES (`date_fin_garantie`/`date_fin_garantie_production`),
un résumé de recette (`CommissioningRecord`) et le compte de photos.

GARDE-FOU ABSOLU : `prix_achat` (et tout montant d'achat) ne doit JAMAIS
pouvoir apparaître dans le PDF généré — test dédié `test_aucun_prix_achat_ne_fuit`.

Run :
    docker compose exec django_core python manage.py test \
        apps.documents.tests.test_cht24_equipements_poses -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.models_chantier import (
    CommissioningIVReading, CommissioningRecord,
)
from apps.sav.models import Equipement
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company


def _company():
    return Company.objects.get_or_create(
        slug='cht24-co', defaults={'nom': 'CHT24 Co'})[0]


def _chantier(company, ref):
    client = Client.objects.create(
        company=company, nom='Benali', prenom='Karim',
        telephone='+212600000324', adresse='12 rue Test, Casablanca')
    produit = Produit.objects.create(
        company=company, nom='Onduleur hybride 5kW', sku=f'OND-{ref}',
        prix_vente=Decimal('9000.00'), prix_achat=Decimal('4321.99'),
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
        site_adresse='12 rue Test', site_ville='Casablanca')


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class EquipementsPosesTests(TestCase):
    def setUp(self):
        self.company = _company()

    def _html(self, mock_pdf, chantier):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        builders.generate_dossier_remise(chantier)
        return mock_pdf.call_args[0][0]

    def test_sans_equipement_le_pdf_est_inchange(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-CHT24-NOEQ')

        html = self._html(mock_pdf, chantier)

        self.assertNotIn('Équipements posés', html)
        self.assertNotIn('Recette de mise en service', html)
        # Le corps historique est intact.
        self.assertIn('DOSSIER DE REMISE', html)
        self.assertIn('Exploitation', html)

    def test_chantier_avec_series_affiche_la_section(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-CHT24-EQ')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 450W', sku='PAN-CHT24',
            prix_vente=Decimal('1200.00'), prix_achat=Decimal('654.32'),
            quantite_stock=20, marque='Jinko', garantie='25 ans linéaire')
        Equipement.objects.create(
            company=self.company, produit=produit, installation=chantier,
            numero_serie='SN-CHT24-0001',
            date_pose='2026-05-28',
            date_fin_garantie='2051-05-28',
            date_fin_garantie_production='2051-05-28')
        record = CommissioningRecord.objects.create(
            company=self.company, installation=chantier,
            resultat=CommissioningRecord.Resultat.CONFORME)
        CommissioningIVReading.objects.create(
            company=self.company, record=record, string_label='String 1',
            voc_mesure_v=Decimal('620.00'), isc_mesure_a=Decimal('9.80'),
            pmax_mesure_w=Decimal('4500.00'), defaut_detecte=False)

        html = self._html(mock_pdf, chantier)

        self.assertIn('Équipements posés', html)
        self.assertIn('SN-CHT24-0001', html)
        self.assertIn('Jinko', html)
        self.assertIn('Panneau 450W', html)
        self.assertIn('28/05/2051', html)
        self.assertIn('Recette de mise en service', html)
        self.assertIn('Conforme', html)
        self.assertIn('String 1', html)
        self.assertIn('Photos du chantier au dossier', html)
        # Le texte libre `Produit.garantie` n'est PAS celui affiché ici
        # (seules les horloges calculées le sont) — comportement voulu.
        self.assertNotIn('25 ans linéaire', html)

    def test_aucun_prix_achat_ne_fuit(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-CHT24-LEAK')
        produit = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', sku='BAT-CHT24',
            prix_vente=Decimal('15000.00'), prix_achat=Decimal('9999.99'),
            quantite_stock=3, marque='Pylontech', garantie='10 ans')
        Equipement.objects.create(
            company=self.company, produit=produit, installation=chantier,
            numero_serie='SN-CHT24-LEAK-0001',
            date_pose='2026-05-28', date_fin_garantie='2036-05-28')

        html = self._html(mock_pdf, chantier)

        self.assertIn('Équipements posés', html)
        self.assertNotIn('9999.99', html)
        self.assertNotIn('prix_achat', html)
