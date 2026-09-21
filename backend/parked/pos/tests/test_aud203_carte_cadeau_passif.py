"""AUD203 — Carte cadeau au comptoir : la recette était comptée DEUX fois.

Rouge avant correctif : `emettre_carte_cadeau_comptoir` créait une Facture de
vente à l'émission (500 MAD) et `valider_vente` en créait une SECONDE à
l'utilisation (500 MAD) — 1 000 MAD de CA pour 500 MAD réellement vendus, et
aucun passif envers le porteur de la carte.

Vert : l'émission ne crée AUCUNE facture (elle crédite le passif 4421
« Clients — avances et acomptes reçus » et garde le seul encaissement), la
seule recette est la facture des biens livrés (500 MAD), et le passif retombe
à zéro une fois la carte intégralement utilisée.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import LigneEcriture
from apps.crm.models import Client
from apps.pos import services as pos_services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.stock.models import Categorie, Produit
from apps.ventes.models import Facture

User = get_user_model()

COMPTE_PASSIF = pos_services.COMPTE_PASSIF_CARTES_CADEAUX


@override_settings(COMPTA_AUTO_ECRITURES=True)
class Aud203CarteCadeauPassifTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud203', defaults={'nom': 'AUD203 Co'})
        self.user = User.objects.create_user(
            username='aud203-caissier', password='x', company=self.co,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(company=self.co, nom='Porteur')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Chargeur solaire', prix_vente=Decimal('500'),
            prix_achat=Decimal('200'), quantite_stock=10, categorie=categorie)
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)

    # ── outils de mesure ────────────────────────────────────────────────────

    def _ca_facture(self):
        """CA comptabilisé côté registre des ventes : somme TTC des factures."""
        return sum(
            (Decimal(str(f.total_ttc)) for f in Facture.objects.filter(
                company=self.co)),
            Decimal('0'))

    def _solde_passif(self):
        """Solde CRÉDITEUR du compte de dette cartes cadeaux (crédit − débit)."""
        compte = compta_services.get_compte(self.co, COMPTE_PASSIF)
        lignes = LigneEcriture.objects.filter(
            company=self.co, compte=compte)
        return sum(
            (Decimal(str(ligne.credit or 0)) - Decimal(str(ligne.debit or 0))
             for ligne in lignes),
            Decimal('0'))

    def _vente(self, prix='500'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=f'VC-AUD203-{prix}',
            client=self.client_obj, taux_tva=Decimal('20'),
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(prix))
        return vente

    # ── le scénario du constat ──────────────────────────────────────────────

    def test_emission_ne_cree_aucune_facture_mais_un_passif(self):
        carte, facture = pos_services.emettre_carte_cadeau_comptoir(
            company=self.co, montant=Decimal('500'),
            paiement={'mode': 'especes', 'montant': '500'},
            user=self.user, client=self.client_obj)
        self.assertIsNone(facture)
        self.assertEqual(Facture.objects.filter(company=self.co).count(), 0)
        self.assertEqual(self._ca_facture(), Decimal('0'))
        self.assertEqual(self._solde_passif(), Decimal('500.00'))
        self.assertEqual(carte.solde, Decimal('500.00'))

    def test_emission_puis_usage_integral_ca_500_et_passif_solde(self):
        """ROUGE avant AUD203 : CA = 1 000 MAD et aucun passif."""
        carte, _ = pos_services.emettre_carte_cadeau_comptoir(
            company=self.co, montant=Decimal('500'),
            paiement={'mode': 'especes', 'montant': '500'},
            user=self.user, client=self.client_obj)
        vente = self._vente(prix='500')
        pos_services.valider_vente(
            vente=vente,
            paiements=[{'mode': 'carte_cadeau', 'montant': '500',
                        'carte_code': carte.code}],
            user=self.user)

        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.VALIDEE)
        # UNE seule facture : celle des biens réellement livrés.
        self.assertEqual(Facture.objects.filter(company=self.co).count(), 1)
        self.assertEqual(self._ca_facture(), Decimal('500.00'))
        # Passif né à l'émission, soldé par l'usage.
        self.assertEqual(self._solde_passif(), Decimal('0.00'))
        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('0.00'))

    def test_usage_partiel_laisse_le_reste_en_passif(self):
        carte, _ = pos_services.emettre_carte_cadeau_comptoir(
            company=self.co, montant=Decimal('500'),
            paiement={'mode': 'especes', 'montant': '500'},
            user=self.user, client=self.client_obj)
        vente = self._vente(prix='200')
        pos_services.valider_vente(
            vente=vente,
            paiements=[{'mode': 'carte_cadeau', 'montant': '200',
                        'carte_code': carte.code}],
            user=self.user)
        self.assertEqual(self._ca_facture(), Decimal('200.00'))
        self.assertEqual(self._solde_passif(), Decimal('300.00'))

    def test_emission_conserve_le_mouvement_de_caisse_especes(self):
        """« Garder le seul mouvement de caisse » — l'espèce encaissée reste
        tracée dans la session, même sans facture."""
        session = self._session_caisse()
        pos_services.emettre_carte_cadeau_comptoir(
            company=self.co, montant=Decimal('500'),
            paiement={'mode': 'especes', 'montant': '500'},
            user=self.user, client=self.client_obj,
            session_caisse=session)
        from apps.compta.models import MouvementCaisse
        mouvements = MouvementCaisse.objects.filter(
            caisse=session.caisse_comptable)
        self.assertEqual(mouvements.count(), 1)
        self.assertEqual(
            Decimal(str(mouvements.first().montant)), Decimal('500.00'))

    def _session_caisse(self):
        from apps.compta.models import CompteTresorerie
        compte_caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse comptoir',
            compte_comptable=compta_services.get_compte(self.co, '5161'))
        caisse_comptable = compta_services.creer_caisse(
            self.co, compte_caisse, libelle='Caisse POS',
            solde_initial=Decimal('0'))
        return pos_services.ouvrir_session(
            company=self.co, caisse_comptable=caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)
