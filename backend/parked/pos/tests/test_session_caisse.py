"""XPOS4 — Sessions de caisse POS (ouverture/clôture avec contrôle espèces).

Couvre : on ne peut pas encaisser d'espèces sans session ouverte, la clôture
calcule attendu vs compté et poste l'écart dans la caisse compta, Z-report
exact, tests multi-tenant. Couvre aussi XPOS18 (rapprochement TPE additif).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import CompteTresorerie
from apps.crm.models import Client
from apps.pos import services
from apps.pos.models import LigneVenteComptoir, SessionCaisse, VenteComptoir
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class SessionCaisseServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos4', 'XPOS4 Co')
        self.user = make_user(self.co, 'caissier-xpos4')
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)
        self.compte_caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse comptoir',
            compte_comptable=compta_services.get_compte(self.co, '5161'))
        self.caisse_comptable = compta_services.creer_caisse(
            self.co, self.compte_caisse, libelle='Caisse POS',
            solde_initial=Decimal('500'))
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Acc')
        self.produit = Produit.objects.create(
            company=self.co, nom='Produit', prix_vente=Decimal('100'),
            prix_achat=Decimal('40'), quantite_stock=20, categorie=categorie)

    def test_ouvrir_session(self):
        session = services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('200'), user=self.user)
        self.assertEqual(session.statut, SessionCaisse.Statut.OUVERTE)
        self.assertEqual(session.fond_ouverture, Decimal('200'))

    def test_cannot_open_two_sessions_same_caisse(self):
        services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)
        with self.assertRaises(services.SessionCaisseError):
            services.ouvrir_session(
                company=self.co, caisse_comptable=self.caisse_comptable,
                caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)

    def test_especes_sale_requires_open_session(self):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-S1', client=self.client_obj,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation='Produit',
            quantite=1, prix_unitaire_ttc=Decimal('100'))
        with self.assertRaises(services.VenteComptoirError):
            services.valider_vente(
                vente=vente, paiements=[{'mode': 'especes', 'montant': '100'}],
                user=self.user)

    def test_cloture_calcule_ecart_et_poste_dans_compta(self):
        session = services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('500'), user=self.user)

        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-S2', client=self.client_obj,
            created_by=self.user, session_caisse=session)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation='Produit',
            quantite=1, prix_unitaire_ttc=Decimal('100'))
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'especes', 'montant': '100'}],
            user=self.user)

        # Compté = attendu + 5 (excédent volontaire pour vérifier l'écart).
        cloturee = services.cloturer_session(
            session=session, montant_compte=Decimal('605'), user=self.user)
        self.assertEqual(cloturee.statut, SessionCaisse.Statut.CLOTUREE)
        self.assertIsNotNone(cloturee.cloture_caisse_comptable)
        self.assertEqual(cloturee.cloture_caisse_comptable.ecart, Decimal('5.00'))

    def test_rapport_z_totaux_par_mode(self):
        session = services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)
        for mode, montant in (('especes', '100'), ('carte', '50')):
            vente = VenteComptoir.objects.create(
                company=self.co, reference=f'VC-Z-{mode}',
                client=self.client_obj, created_by=self.user,
                session_caisse=session)
            LigneVenteComptoir.objects.create(
                vente=vente, produit=self.produit, designation='Produit',
                quantite=1, prix_unitaire_ttc=Decimal(montant))
            services.valider_vente(
                vente=vente, paiements=[{'mode': mode, 'montant': montant}],
                user=self.user)

        z = services.rapport_z(session)
        self.assertEqual(z['nb_ventes'], 2)
        self.assertEqual(z['par_mode']['especes']['total'], Decimal('100.00'))
        self.assertEqual(z['par_mode']['carte']['total'], Decimal('50.00'))

    def test_cloture_avec_tpe_calcule_ecart_carte(self):
        session = services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-TPE', client=self.client_obj,
            created_by=self.user, session_caisse=session)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation='Produit',
            quantite=1, prix_unitaire_ttc=Decimal('80'))
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '80'}],
            user=self.user)

        cloturee = services.cloturer_session(
            session=session, montant_compte=Decimal('0'),
            montant_tpe_compte=Decimal('75'), user=self.user)
        self.assertEqual(cloturee.montant_tpe_compte, Decimal('75.00'))
        self.assertEqual(cloturee.ecart_tpe, Decimal('-5.00'))

    def test_cannot_cloturer_twice(self):
        session = services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)
        services.cloturer_session(
            session=session, montant_compte=Decimal('0'), user=self.user)
        with self.assertRaises(services.SessionCaisseError):
            services.cloturer_session(
                session=session, montant_compte=Decimal('0'), user=self.user)
