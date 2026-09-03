"""QJR408 — le tableau imprimé somme au total imprimé : la seconde passe de
classification du moteur de rendu est SUPPRIMÉE.

TEST ROUGE D'ABORD. QJR301 avait fait du garde-fou legacy un consommateur de la
règle du noyau, mais ``builder`` retire la clé interne ``_produit_nom`` des
items JUSTE AVANT de les remettre au générateur (``# Strip the internal helper
key before handing items to the generator.``), alors que la classification qui
s'appuie sur cette clé se fait au bloc précédent. Le garde-fou legacy
(``generate_devis_premium._guard_huawei_accessories``, armé quand
``nb_options == 2``) ne classait donc plus que sur la DÉSIGNATION SEULE.

Chemin atteignable : un devis dont l'identité HUAWEI de l'onduleur ne vit que
dans le NOM DU PRODUIT LIÉ (désignation muette, champ ``marque`` vide). Le
builder voit « panier Huawei » et CONSERVE le Smart Meter — donc le COMPTE
dans le total figé ; le garde-fou legacy voit « panier non-Huawei » et RETIRE
la ligne du tableau imprimé. Le client lit un tableau dont la somme ne fait pas
le total. Cette seconde passe ne pouvait que SOUS-compter le tableau.

Issue retenue : SUPPRESSION de la passe redondante (le builder l'applique déjà
aux deux paniers dans le cas ``deux_options``, EXACTEMENT la condition qui
armait le garde-fou, et il le fait AVANT le retrait de la clé). Le code mort
part dans le même commit.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr408_garde_legacy_produit_nom"
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_company, make_user,
)
from apps.ventes.utils.options import AVEC_BATTERIE, SANS_BATTERIE, option_totaux


#: (désignation, nom du produit lié, marque, quantité, PU HT)
#: L'identité HUAWEI de l'onduleur réseau ne vit QUE dans le nom du produit :
#: la désignation est muette et le champ ``marque`` est vide.
LIGNES = [
    ('Onduleur réseau 10 kW triphasé', 'Huawei SUN2000-10KTL-M1', '',
     '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', 'Deye SUN-10K-SG04LP3', 'Deye',
     '1', '23333.33'),
    ('Batterie Dyness 10 kWh', 'Dyness Powerbox 10', 'Dyness', '1', '25000'),
    ('Smart Meter DTSU666-H', 'Compteur DTSU666-H', '', '1', '1500'),
    ('Panneau Canadian Solar 710W', 'CS7N-710MS', 'Canadian Solar',
     '14', '1166.67'),
    ('Installation', 'Prestation pose', '', '1', '5000'),
]


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Karim',
            email='k@example.com', telephone='+212600000000',
            adresse='Hay Riad, Rabat')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR408-0001',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, etude_params=dict(DEUX_OPTIONS))
        for desig, nom, marque, qty, pu in LIGNES:
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=f'QJR408-{nom[:12]}',
                marque=marque, prix_vente=Decimal(pu),
                prix_achat=Decimal('1'), quantite_stock=100)
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))

    @staticmethod
    def _html(devis):
        """Le HTML que le moteur de rendu produit — sans passer par WeasyPrint
        (patron éprouvé de ``test_qf9_huawei_accessories``)."""
        from apps.ventes.quote_engine import generate_devis_premium as moteur
        data = build_quote_data(devis)
        capture = {}
        original = moteur._render_pdf_weasyprint
        moteur._render_pdf_weasyprint = (
            lambda html, out: capture.update(html=html))
        try:
            moteur.generate_premium_pdf(data, '/tmp/_qjr408.pdf')
        finally:
            moteur._render_pdf_weasyprint = original
        return capture['html']

    @staticmethod
    def _somme_ttc(items):
        total = Decimal('0')
        for it in items:
            total += (Decimal(str(it['quantite']))
                      * Decimal(str(it['prix_unit_ht']))
                      * (Decimal('1')
                         + Decimal(str(it['taux_tva'])) / Decimal('100')))
        return total


class UneSeulePasseDeClassification(_Base):

    def test_le_moteur_de_rendu_ne_reclasse_plus_les_items(self):
        """ROUGE AVANT : ``_guard_huawei_accessories`` existait et
        re-classifiait les deux listes par option APRÈS le retrait de
        ``_produit_nom`` — une seconde passe, sur un texte plus pauvre."""
        from apps.ventes.quote_engine import generate_devis_premium as moteur
        self.assertFalse(
            hasattr(moteur, '_guard_huawei_accessories'),
            'une seconde passe de classification subsiste sur ce chemin')

    def test_le_tableau_imprime_somme_au_total_imprime(self):
        """Le panier remis au moteur de rendu EST celui que le total compte."""
        data = build_quote_data(self.devis)
        self.assertEqual(data['nb_options'], 2)
        for cle_items, cle_total in (('sans_items', 'totaux_sans'),
                                     ('avec_items', 'totaux_avec')):
            somme = self._somme_ttc(data[cle_items])
            total = Decimal(str(data[cle_total]['ttc']))
            self.assertLessEqual(
                abs(somme - total), Decimal('1'),
                '%s : somme du tableau %s != total imprimé %s'
                % (cle_items, somme, total))

    def test_l_accessoire_au_nom_de_produit_muet_est_bien_imprime(self):
        """L'onduleur est Huawei par le NOM DU PRODUIT : son Smart Meter reste
        dans le panier « sans » — le total le compte, le tableau le montre."""
        data = build_quote_data(self.devis)
        self.assertIn('Smart Meter DTSU666-H',
                      [it['designation'] for it in data['sans_items']])

    def test_le_document_rendu_imprime_la_ligne_qu_il_facture(self):
        """LE ROUGE FONCTIONNEL : le garde-fou legacy retirait cette ligne du
        TABLEAU IMPRIMÉ alors que le total figé la compte — le client lisait
        un tableau dont la somme ne fait pas le total."""
        html = self._html(self.devis)
        self.assertIn('DTSU666-H', html,
                      'la ligne comptée dans le total a disparu du tableau')

    def test_le_tableau_egale_option_totaux_du_noyau(self):
        data = build_quote_data(self.devis)
        for option, cle in ((SANS_BATTERIE, 'total_sans'),
                            (AVEC_BATTERIE, 'total_avec')):
            noyau = Decimal(str(option_totaux(self.devis, option)['ttc']))
            self.assertLessEqual(
                abs(noyau - Decimal(str(data[cle]))), Decimal('1'), option)
