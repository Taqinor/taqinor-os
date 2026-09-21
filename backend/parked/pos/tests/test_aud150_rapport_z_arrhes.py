"""AUD150 — Rapport X/Z : les ventes en arrhes réglées dans la session étaient
ignorées, jusqu'à une FAUSSE alerte d'écart TPE.

`rapport_z` (pos/services.py) filtrait `statut=VALIDEE`, excluant toute vente
`EN_ATTENTE_SOLDE`. Or `encaisser_arrhes` crée une facture RÉELLE et enregistre
un vrai `Paiement`, de n'importe quel mode — carte comprise — DANS LA MÊME
SESSION. `cloturer_session` calcule `attendu_carte` exclusivement depuis
`rapport_z(...)['par_mode']['carte']['total']` : une vente prise en arrhes par
carte à 3 000 MAD faisait donc apparaître à la clôture un excédent TPE de
3 000 MAD non expliqué, et le caissier était mis en cause.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import CompteTresorerie
from apps.crm.models import Client
from apps.pos import services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.stock.models import Categorie, Produit

User = get_user_model()


class Aud150RapportZArrhesTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud150', defaults={'nom': 'AUD150 Co'})
        self.user = User.objects.create_user(
            username='aud150-caissier', password='x', company=self.co,
            role_legacy='responsable')
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)
        compte_caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse comptoir',
            compte_comptable=compta_services.get_compte(self.co, '5161'))
        self.caisse_comptable = compta_services.creer_caisse(
            self.co, compte_caisse, libelle='Caisse POS',
            solde_initial=Decimal('0'))
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Acc')
        self.produit = Produit.objects.create(
            company=self.co, nom='Produit', prix_vente=Decimal('100'),
            prix_achat=Decimal('40'), quantite_stock=50, categorie=categorie)
        self.session = services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)

    def _vente(self, reference, prix):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=reference, client=self.client_obj,
            taux_tva=Decimal('20'), session_caisse=self.session,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(prix))
        return vente

    # ── le scénario du constat ──────────────────────────────────────────────

    def test_rapport_z_inclut_les_arrhes_de_la_session(self):
        """ROUGE avant AUD150 : les 3 000 MAD carte n'apparaissaient pas."""
        vente_cash = self._vente('VC-AUD150-A', '1000')
        services.valider_vente(
            vente=vente_cash,
            paiements=[{'mode': 'especes', 'montant': '1000'}],
            user=self.user)
        vente_arrhes = self._vente('VC-AUD150-B', '5000')
        services.encaisser_arrhes(
            vente=vente_arrhes, montant_arrhes=Decimal('3000'),
            paiement={'mode': 'carte', 'montant': '3000'}, user=self.user)

        z = services.rapport_z(self.session)
        self.assertEqual(
            z['par_mode']['carte']['total'], Decimal('3000.00'))
        self.assertEqual(
            z['par_mode']['especes']['total'], Decimal('1000.00'))
        self.assertEqual(z['nb_ventes'], 2)
        self.assertEqual(z['total'], Decimal('4000.00'))
        # Rapport X = même agrégat, sans effet de bord.
        self.assertEqual(
            services.rapport_x(self.session)['par_mode']['carte']['total'],
            Decimal('3000.00'))

    def test_cloture_ne_signale_aucun_ecart_tpe_fantome(self):
        """ROUGE avant AUD150 : écart TPE de +3 000 MAD imputé au caissier."""
        vente_cash = self._vente('VC-AUD150-C', '1000')
        services.valider_vente(
            vente=vente_cash,
            paiements=[{'mode': 'especes', 'montant': '1000'}],
            user=self.user)
        vente_arrhes = self._vente('VC-AUD150-D', '5000')
        services.encaisser_arrhes(
            vente=vente_arrhes, montant_arrhes=Decimal('3000'),
            paiement={'mode': 'carte', 'montant': '3000'}, user=self.user)

        session = services.cloturer_session(
            session=self.session, montant_compte=Decimal('1000'),
            montant_tpe_compte=Decimal('3000'), user=self.user)
        self.assertEqual(session.ecart_tpe, Decimal('0.00'))

    def test_vente_brouillon_sans_facture_reste_hors_rapport(self):
        """Le rapport ne compte que des ventes PORTANT une facture."""
        self._vente('VC-AUD150-E', '700')  # brouillon, jamais encaissée
        z = services.rapport_z(self.session)
        self.assertEqual(z['nb_ventes'], 0)
        self.assertEqual(z['total'], Decimal('0'))
