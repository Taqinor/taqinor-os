"""QJR543 — le « Devis automatique » agricole / industriel / commercial se
crée en UN appel ``POST /devis/atomic/`` qui porte son étude et son scénario.

Avant : ``createDevis`` (POST /devis/, où ``etude_params`` est en lecture
seule — QJR67 — donc IGNORÉ) puis N ``addLigneDevis``. ``m3_jour``,
``taux_autoconso``, ``payback`` et SURTOUT ``scenario`` n'atteignaient jamais
le devis ; sans scénario, un panier réseau + hybride + batterie était lu
mono-option et l'argent devenait la SOMME des deux paniers.

Ce test épingle le côté serveur du chemin désormais emprunté : l'étude
projetée (clés ECRAN seulement, QJR542) survit à la transaction ET au
rafraîchissement des études qui la suit, et le scénario « Sans batterie »
fait suivre au total UNE option.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis

User = get_user_model()
ATOMIC = '/api/django/ventes/devis/atomic/'


class AutoQuoteAtomiqueEtudeTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr543-co', defaults={'nom': 'QJR543 Co'})
        self.user = User.objects.create_user(
            username='qjr543_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        def produit(nom, sku, prix):
            return Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), quantite_stock=100)

        self.commun = produit('Kit commun QJR543', 'QJR543-COM', '1000')
        self.reseau = produit('Onduleur réseau QJR543', 'QJR543-RES', '2000')
        self.hybride = produit('Onduleur hybride QJR543', 'QJR543-HYB', '3000')
        self.batterie = produit('Batterie QJR543', 'QJR543-BAT', '2000')

    def _lead(self, type_installation, tel):
        return Lead.objects.create(
            company=self.company, nom='Lead', prenom='QJR543',
            telephone=tel, type_installation=type_installation)

    def _ligne(self, prod, prix, ordre):
        return {'produit': prod.id, 'designation': prod.nom, 'quantite': '1',
                'prix_unitaire': prix, 'remise': '0', 'taux_tva': '20',
                'ordre': ordre}

    def test_agricole_etude_projetee_conservee(self):
        lead = self._lead('agricole', '+212600005431')
        etude = {
            'pompe_cv': 5.5, 'pompe_kw': 4, 'debit_hmt_m3h': 12.4,
            'm3_jour': 86.8, 'champ_kwc': 5.68, 'hmt_m': 60,
            'debit_souhaite_m3h': 12, 'heures_pompage': 7,
            'type_pompe': 'immergee', 'alim': 'tri', 'distance_m': 20,
        }
        rep = self.api.post(ATOMIC, {
            'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00',
            'remise_globale': '0', 'mode_installation': 'agricole',
            'etude_params': etude,
            'lignes': [self._ligne(self.commun, '1000', 0)],
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        devis = Devis.objects.get(id=rep.data['id'])
        ep = devis.etude_params or {}
        self.assertEqual(ep.get('m3_jour'), 86.8)
        self.assertEqual(ep.get('pompe_cv'), 5.5)
        self.assertEqual(ep.get('heures_pompage'), 7)

    def test_industriel_sans_batterie_total_d_une_seule_option(self):
        lead = self._lead('industriel', '+212600005432')
        rep = self.api.post(ATOMIC, {
            'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00',
            'remise_globale': '0', 'mode_installation': 'industriel',
            'etude_params': {
                'scenario': 'Sans batterie', 'taux_autoconso': 82.5,
                'taux_couverture': 61.0, 'payback': 4.2,
                'part_diurne_pct': 80,
            },
            'lignes': [
                self._ligne(self.commun, '1000', 0),
                self._ligne(self.reseau, '2000', 1),
                self._ligne(self.hybride, '3000', 2),
                self._ligne(self.batterie, '2000', 3),
            ],
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        devis = Devis.objects.get(id=rep.data['id'])
        ep = devis.etude_params or {}
        self.assertEqual(ep.get('scenario'), 'Sans batterie')
        self.assertEqual(ep.get('taux_autoconso'), 82.5)
        self.assertEqual(ep.get('payback'), 4.2)
        # UNE option (« sans » : kit commun + onduleur réseau = 3 000 HT),
        # jamais la somme des deux paniers (8 000 HT → 9 600 TTC).
        self.assertNotEqual(devis.total_ttc, Decimal('9600.00'))
        self.assertEqual(devis.total_ttc, Decimal('3600.00'))
        self.assertEqual(Decimal(str(rep.data['total_ttc'])), Decimal('3600.00'))

    def test_cle_brute_hors_schema_refusee_sans_rien_creer(self):
        """Une étude BRUTE (kwc, prix_kwc…) n'est jamais acceptée : c'est
        pourquoi l'écran ne l'envoie que projetée (QJR542)."""
        lead = self._lead('industriel', '+212600005433')
        rep = self.api.post(ATOMIC, {
            'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00',
            'mode_installation': 'industriel',
            'etude_params': {'scenario': 'Sans batterie', 'prix_kwc': 7000},
            'lignes': [self._ligne(self.commun, '1000', 0)],
        }, format='json')
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertIn('etude_params', rep.data)
        self.assertFalse(Devis.objects.filter(lead=lead).exists())
