"""NTRET25 — Arrondi caisse (cash rounding, espèces uniquement).

Couvre : la fonction pure ``arrondir_especes`` (pas 0.05/0.10, arrondi au
plus proche), l'intégration dans ``valider_vente`` (désactivé par défaut =
comportement inchangé ; actif = écart posé UNIQUEMENT sur le montant dû en
espèces, jamais sur carte/virement), et le rendu du ticket (ligne « arrondi
caisse » distincte, jamais fondue dans un prix produit).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import CompteTresorerie
from apps.crm.models import Client
from apps.parametres.models_pos import ParametresPos
from apps.pos import receipt, services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_session_caisse(company, user):
    compta_services.seed_plan_comptable(company)
    compta_services.seed_journaux(company)
    compte_caisse = CompteTresorerie.objects.create(
        company=company, type_compte=CompteTresorerie.Type.CAISSE,
        libelle='Caisse comptoir',
        compte_comptable=compta_services.get_compte(company, '5161'))
    caisse_comptable = compta_services.creer_caisse(
        company, compte_caisse, libelle='Caisse POS', solde_initial=Decimal('0'))
    return services.ouvrir_session(
        company=company, caisse_comptable=caisse_comptable,
        caissier=user, fond_ouverture=Decimal('0'), user=user)


class ArrondirEspecesTests(TestCase):
    """Fonction pure — pas de base de données requise, testable isolément."""

    def test_arrondit_au_pas_0_10_le_plus_proche(self):
        self.assertEqual(
            services.arrondir_especes(Decimal('127.37'), Decimal('0.10')),
            Decimal('127.40'))

    def test_arrondit_au_pas_0_05_le_plus_proche(self):
        self.assertEqual(
            services.arrondir_especes(Decimal('127.37'), Decimal('0.05')),
            Decimal('127.35'))

    def test_montant_deja_multiple_du_pas_inchange(self):
        self.assertEqual(
            services.arrondir_especes(Decimal('127.40'), Decimal('0.10')),
            Decimal('127.40'))

    def test_pas_nul_renvoie_le_montant_quantifie(self):
        self.assertEqual(
            services.arrondir_especes(Decimal('127.371'), Decimal('0')),
            Decimal('127.37'))


class ArrondiCaisseValiderVenteTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret25', 'NTRET25 Co')
        self.user = make_user(self.co, 'caissier-ntret25')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Câble', prix_vente=Decimal('127.37'),
            prix_achat=Decimal('60'), quantite_stock=10, categorie=categorie)
        self.session = make_session_caisse(self.co, self.user)

    def _vente(self, prix='127.37'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=f'VC-AR-{prix}', client=self.client_obj,
            created_by=self.user, session_caisse=self.session)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(prix))
        return vente

    def test_arrondi_desactive_par_defaut_ecart_none(self):
        vente = self._vente()
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'especes', 'montant': '127.37'}],
            user=self.user)
        vente.refresh_from_db()
        self.assertIsNone(vente.ecart_arrondi_especes)

    def test_arrondi_actif_pose_l_ecart_sur_le_montant_du_especes(self):
        params = ParametresPos.get(self.co)
        params.arrondi_caisse_actif = True
        params.arrondi_caisse_pas = Decimal('0.10')
        params.save(update_fields=['arrondi_caisse_actif', 'arrondi_caisse_pas'])

        vente = self._vente()
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'especes', 'montant': '127.37'}],
            user=self.user)
        vente.refresh_from_db()
        self.assertEqual(vente.ecart_arrondi_especes, Decimal('0.03'))

    def test_arrondi_actif_jamais_applique_sur_carte(self):
        """Un règlement 100% carte ne doit JAMAIS être arrondi (aucun
        montant dû en espèces)."""
        params = ParametresPos.get(self.co)
        params.arrondi_caisse_actif = True
        params.save(update_fields=['arrondi_caisse_actif'])

        vente = self._vente()
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '127.37'}],
            user=self.user)
        vente.refresh_from_db()
        self.assertIsNone(vente.ecart_arrondi_especes)

    def test_arrondi_actif_sur_part_especes_dun_paiement_mixte(self):
        """Paiement fractionné (100 carte + 27.37 espèces pour un total de
        127.37) : l'arrondi porte UNIQUEMENT sur la part espèces réellement
        due (27.37, pas sur le total ni sur la part carte)."""
        params = ParametresPos.get(self.co)
        params.arrondi_caisse_actif = True
        params.arrondi_caisse_pas = Decimal('0.10')
        params.save(update_fields=['arrondi_caisse_actif', 'arrondi_caisse_pas'])

        vente = self._vente(prix='127.37')
        services.valider_vente(
            vente=vente,
            paiements=[
                {'mode': 'carte', 'montant': '100.00'},
                {'mode': 'especes', 'montant': '27.37'},
            ],
            user=self.user)
        vente.refresh_from_db()
        # Dû en espèces = 127.37 - 100.00 = 27.37 -> arrondi 27.40 -> écart 0.03
        self.assertEqual(vente.ecart_arrondi_especes, Decimal('0.03'))


class ArrondiCaisseReceiptTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret25-r', 'NTRET25 Receipt Co')
        self.user = make_user(self.co, 'caissier-ntret25-r')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Câble', prix_vente=Decimal('127.37'),
            prix_achat=Decimal('60'), quantite_stock=10, categorie=categorie)
        self.session = make_session_caisse(self.co, self.user)

    def test_ticket_affiche_la_ligne_arrondi_quand_ecart_pose(self):
        params = ParametresPos.get(self.co)
        params.arrondi_caisse_actif = True
        params.arrondi_caisse_pas = Decimal('0.10')
        params.save(update_fields=['arrondi_caisse_actif', 'arrondi_caisse_pas'])

        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-AR-TICKET', client=self.client_obj,
            created_by=self.user, session_caisse=self.session)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal('127.37'))
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'especes', 'montant': '127.37'}],
            user=self.user)
        vente.refresh_from_db()

        html = receipt.receipt_html(vente, paiements=vente.facture.paiements.all())
        self.assertIn('Arrondi caisse', html)
        self.assertIn('0.03', html)

    def test_ticket_sans_ligne_arrondi_quand_desactive(self):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-AR-TICKET-2', client=self.client_obj,
            created_by=self.user, session_caisse=self.session)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal('127.37'))
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'especes', 'montant': '127.37'}],
            user=self.user)
        vente.refresh_from_db()

        html = receipt.receipt_html(vente, paiements=vente.facture.paiements.all())
        self.assertNotIn('Arrondi caisse', html)
