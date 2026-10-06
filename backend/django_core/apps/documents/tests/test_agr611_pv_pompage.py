"""AGR611 — PV de réception et dossier de remise d'un chantier POMPAGE :
mesures de la recette (cadre IEC 62253:2011) et formalité loi 82-21, art. 3.

Tests sur le HTML RENDU (``_html_to_pdf`` intercepté), jamais une regex sur
le source. PV et dossier de remise d'un chantier non agricole restent
OCTET-IDENTIQUES (fragment vide).

Run :
    docker compose exec django_core python manage.py test \
        apps.documents.tests.test_agr611_pv_pompage -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation, RecettePompage
from apps.installations.models_chantier import ChantierChecklistItem
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

ART3 = ("Loi 82-21, art. 3 : une installation non raccordée au réseau est "
        "soumise à déclaration auprès de l&#x27;administration ; modalités "
        "fixées par voie réglementaire.")


def _chantier(company, ref, type_installation='agricole'):
    client = Client.objects.create(
        company=company, nom='Ferme', prenom='Saïd',
        telephone='+212600000611', adresse='Douar Test, Taroudant')
    produit = Produit.objects.create(
        company=company, nom='Pompe immergée 5,5 kW', sku=f'P-{ref}',
        prix_vente=Decimal('15000.00'), prix_achat=Decimal('8765.43'),
        role_pompage='pompe', marque='OSP')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{ref}', client=client,
        statut='accepte', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), mode_installation=type_installation,
        etude_params={'debit_hmt_m3h': 20.0, 'hmt_m': 60.0})
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation=produit.nom,
        quantite=Decimal('1'), prix_unitaire=Decimal('15000.00'),
        remise=Decimal('0'))
    return Installation.objects.create(
        company=company, reference=ref, client=client, devis=devis,
        type_installation=type_installation,
        bom=[{'produit_id': produit.id, 'designation': produit.nom,
              'quantite': 1, 'marque': 'OSP'}],
        site_adresse='Douar Test', site_ville='Taroudant')


def _recette(chantier, **champs):
    valeurs = dict(
        company=chantier.company, installation=chantier,
        date_essai='2026-11-18', niveau_statique_m=32.4,
        niveau_dynamique_m=41.1, hmt_mesuree_m=60.2, debit_mesure_m3h=17.0,
        courant_plaque_a=16.0, courant_phase_1_a=14.8,
        courant_phase_2_a=14.9, courant_phase_3_a=14.7,
        frequence_variateur_hz=49.2, irradiance_wm2=870,
        source_irradiance='mesuree', isolement_moteur_mohm=250.0,
        isolement_ok=True, sens_rotation_ok=True, test_marche_a_sec_ok=True,
        resultat='conforme', commentaire_ecart='Forage colmaté.',
        promesse={'debit_hmt_m3h': 20.0, 'hmt_m': 60.0, 'm3_jour': None,
                  'heures_pompage': None, 'devis_reference': 'DEV-X',
                  'figee_le': '2026-11-02'})
    valeurs.update(champs)
    return RecettePompage.objects.create(**valeurs)


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class PvPompageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='agr611-co', defaults={'nom': 'AGR611 Co'})[0]

    def _rendu(self, mock_pdf, generateur, chantier):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        getattr(builders, generateur)(chantier)
        return mock_pdf.call_args[0][0]

    def test_pv_agricole_porte_les_mesures_et_l_art_3(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AGR611-01')
        _recette(chantier)
        html = self._rendu(mock_pdf, 'generate_pv_reception', chantier)
        self.assertIn('Recette pompage — mesures', html)
        self.assertIn('Cadre des essais : IEC 62253:2011', html)
        self.assertIn('<td>HMT mesurée (m)</td><td>60,2</td>', html)
        self.assertIn('<td>Débit mesuré (m³/h)</td><td>17</td>', html)
        self.assertIn('<td>Débit promis au devis (m³/h)</td><td>20</td>', html)
        self.assertIn('<td>Écart de débit (%)</td><td>-15</td>', html)
        self.assertIn('Forage colmaté.', html)
        self.assertIn('14,8 / 14,9 / 14,7 / plaque 16', html)
        self.assertIn('870 (mesurée)', html)
        self.assertIn('<td>Test de marche à sec</td><td>Oui</td>', html)
        self.assertIn('Formalités', html)
        self.assertIn(ART3, html)
        # Pas de guichet, de pièces, de délai, ni de promesse de dépôt.
        self.assertNotIn('Formation du client', html)

    def test_dossier_de_remise_porte_le_meme_bloc(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AGR611-02')
        _recette(chantier)
        html = self._rendu(mock_pdf, 'generate_dossier_remise', chantier)
        self.assertIn('Recette pompage — mesures', html)
        self.assertIn('Cadre des essais : IEC 62253:2011', html)
        self.assertIn(ART3, html)

    def test_recette_non_conforme_imprimee_telle_quelle(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AGR611-03')
        _recette(chantier, resultat='non_conforme', isolement_ok=False)
        html = self._rendu(mock_pdf, 'generate_pv_reception', chantier)
        self.assertIn('<td>Résultat</td><td>Non conforme</td>', html)
        self.assertIn('conforme : Non', html)

    def test_formation_du_client_seulement_si_cochee(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AGR611-04')
        _recette(chantier)
        ChantierChecklistItem.objects.create(
            company=self.company, installation=chantier, cle='client_forme',
            libelle='Client formé', fait=False)
        html = self._rendu(mock_pdf, 'generate_pv_reception', chantier)
        self.assertNotIn('Formation du client : faite', html)
        ChantierChecklistItem.objects.filter(
            installation=chantier, cle='client_forme').update(fait=True)
        html = self._rendu(mock_pdf, 'generate_pv_reception', chantier)
        self.assertIn('Formation du client : faite', html)

    def test_aucun_prix_achat_ne_fuit(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AGR611-05')
        _recette(chantier)
        for generateur in ('generate_pv_reception', 'generate_dossier_remise'):
            html = self._rendu(mock_pdf, generateur, chantier)
            self.assertNotIn('8765', html)
            self.assertNotIn('prix_achat', html)

    def test_chantier_residentiel_octet_identique(self, mock_pdf, _dl):
        """Fragment VIDE hors agricole : le rendu est celui du gabarit seul."""
        from apps.documents import builders
        chantier = _chantier(self.company, 'CH-AGR611-06',
                             type_installation='residentiel')
        self.assertEqual(builders._recette_pompage_fragment(chantier), '')
        # Fragment vide ⇒ ``_inject_before`` est un no-op STRICT : le HTML
        # est exactement celui que rend le gabarit.
        html_pv = self._rendu(mock_pdf, 'generate_pv_reception', chantier)
        self.assertEqual(
            builders._inject_before(html_pv, '<div class="signature-section">',
                                    ''), html_pv)
        self.assertNotIn('Formalités', html_pv)
        self.assertNotIn('IEC 62253', html_pv)
        html_dr = self._rendu(mock_pdf, 'generate_dossier_remise', chantier)
        self.assertNotIn('Recette pompage', html_dr)
        self.assertNotIn('Formalités', html_dr)
