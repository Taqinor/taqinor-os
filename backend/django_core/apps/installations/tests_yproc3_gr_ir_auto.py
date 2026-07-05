"""
YPROC3 — GR/IR automatique : provision à la confirmation de réception,
lettrage à la facturation.

Couvre :
  * la confirmation d'une réception fournisseur (avec BCF) crée automatiquement
    sa provision GR/IR (montant = Σ qte reçue × prix_achat_unitaire) ;
  * une réception déjà provisionnée (à la main ou automatiquement) n'est
    jamais doublée (idempotence) ;
  * une réception sans BCF ne provisionne rien (no-op) ;
  * la création d'une facture fournisseur (``facturer_reception``) lettre
    automatiquement la provision ouverte du même bon de commande ;
  * le lettrage ne touche jamais une provision d'un autre bon de commande ;
  * re-facturer / re-confirmer ne double/relance jamais le lettrage ;
  * isolation multi-tenant.

Run :
    python manage.py test apps.installations.tests_yproc3_gr_ir_auto -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations.models_gr_ir import ReceptionNonFacturee
from apps.installations.services import (
    lettrer_gr_ir_facture, provisionner_gr_ir_reception,
)
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur, facturer_reception

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_produit(company, nom, prix_vente=100):
    return Produit.objects.create(company=company, nom=nom, prix_vente=prix_vente)


def make_fournisseur(company, nom):
    return Fournisseur.objects.create(company=company, nom=nom)


def make_reception_confirmee(company, produit, user, quantite=5, prix=10):
    fournisseur = make_fournisseur(company, f'Fourn-{produit.id}')
    bc = BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur, reference=f'BC-{produit.id}')
    ligne_cmd = LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc, produit=produit, quantite=quantite,
        prix_achat_unitaire=prix)
    reception = ReceptionFournisseur.objects.create(
        company=company, reference=f'REC-{produit.id}', bon_commande=bc)
    LigneReceptionFournisseur.objects.create(
        reception=reception, ligne_commande=ligne_cmd, produit=produit,
        quantite=quantite)
    confirm_reception_fournisseur(reception, user)
    reception.refresh_from_db()
    return reception, bc


class ProvisionAutoALaReceptionTests(TestCase):
    def setUp(self):
        self.company = make_company('co-yproc3-prov', 'CoYproc3Prov')
        self.user = make_user(self.company, 'resp-yproc3-prov')
        self.produit = make_produit(self.company, 'Onduleur X')

    def test_confirmation_cree_la_provision(self):
        reception, bc = make_reception_confirmee(
            self.company, self.produit, self.user, quantite=5, prix=10)
        provs = ReceptionNonFacturee.objects.filter(reception=reception)
        self.assertEqual(provs.count(), 1)
        prov = provs.first()
        self.assertEqual(prov.montant_provision, Decimal('50'))
        self.assertEqual(prov.bon_commande_id, bc.id)
        self.assertFalse(prov.lettre)

    def test_idempotent_ne_double_pas(self):
        reception, _ = make_reception_confirmee(
            self.company, self.produit, self.user)
        # Ré-appel direct du service (simule une seconde émission de
        # l'événement) : idempotent, ne recrée jamais de seconde provision.
        provisionner_gr_ir_reception(
            reception=reception, company=self.company, user=self.user)
        self.assertEqual(
            ReceptionNonFacturee.objects.filter(reception=reception).count(),
            1)

    def test_provision_manuelle_prealable_pas_doublee(self):
        fournisseur = make_fournisseur(self.company, 'Four-manuel')
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=fournisseur, reference='BC-M1')
        ligne_cmd = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=3,
            prix_achat_unitaire=20)
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-M1', bon_commande=bc)
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=ligne_cmd,
            produit=self.produit, quantite=3)
        # Provision créée à la main AVANT la confirmation (cas hors flux).
        ReceptionNonFacturee.objects.create(
            company=self.company, reception=reception, bon_commande=bc,
            montant_provision=Decimal('999'))
        confirm_reception_fournisseur(reception, self.user)
        provs = ReceptionNonFacturee.objects.filter(reception=reception)
        self.assertEqual(provs.count(), 1)
        # La provision manuelle existante est conservée telle quelle.
        self.assertEqual(provs.first().montant_provision, Decimal('999'))

    def test_sans_bon_de_commande_aucune_provision(self):
        result = provisionner_gr_ir_reception(
            reception=None, company=self.company, user=self.user)
        self.assertIsNone(result)


class LettrageAutoALaFactureTests(TestCase):
    def setUp(self):
        self.company = make_company('co-yproc3-lettre', 'CoYproc3Lettre')
        self.user = make_user(self.company, 'resp-yproc3-lettre')
        self.produit = make_produit(self.company, 'Panneau Y')

    def test_facturer_reception_lettre_la_provision(self):
        reception, bc = make_reception_confirmee(
            self.company, self.produit, self.user, quantite=4, prix=25)
        prov = ReceptionNonFacturee.objects.get(reception=reception)
        self.assertFalse(prov.lettre)
        ff = facturer_reception(self.company, self.user, reception)
        prov.refresh_from_db()
        self.assertTrue(prov.lettre)
        self.assertEqual(prov.facture_id, ff.id)
        self.assertIsNotNone(prov.date_lettrage)
        self.assertEqual(prov.montant_a_provisionner, Decimal('0'))

    def test_lettrage_ne_touche_pas_autre_bcf(self):
        reception, bc = make_reception_confirmee(
            self.company, self.produit, self.user, quantite=2, prix=15)
        autre_produit = make_produit(self.company, 'Batterie Z')
        autre_reception, autre_bc = make_reception_confirmee(
            self.company, autre_produit, self.user, quantite=2, prix=15)
        facturer_reception(self.company, self.user, reception)
        prov_autre = ReceptionNonFacturee.objects.get(reception=autre_reception)
        self.assertFalse(prov_autre.lettre)

    def test_refacturer_ne_relance_pas_le_lettrage(self):
        reception, bc = make_reception_confirmee(
            self.company, self.produit, self.user, quantite=2, prix=15)
        prov = ReceptionNonFacturee.objects.get(reception=reception)
        facturer_reception(self.company, self.user, reception)
        prov.refresh_from_db()
        date_initiale = prov.date_lettrage
        facture_id_initiale = prov.facture_id
        # facturer_reception lève ValueError sur une réception déjà facturée
        # (garde existante) — le lettrage n'a de toute façon lieu qu'une fois.
        with self.assertRaises(ValueError):
            facturer_reception(self.company, self.user, reception)
        prov.refresh_from_db()
        self.assertEqual(prov.date_lettrage, date_initiale)
        self.assertEqual(prov.facture_id, facture_id_initiale)

    def test_lettrer_direct_service_idempotent(self):
        reception, bc = make_reception_confirmee(
            self.company, self.produit, self.user, quantite=2, prix=15)
        ff = facturer_reception(self.company, self.user, reception)
        prov = ReceptionNonFacturee.objects.get(reception=reception)
        self.assertTrue(prov.lettre)
        # Ré-appel direct du service de lettrage (simule une seconde émission
        # de l'événement) : la provision déjà lettrée n'est pas retraitée.
        lettres = lettrer_gr_ir_facture(
            facture=ff, company=self.company, user=self.user)
        self.assertEqual(lettres, [])

    def test_sans_bon_de_commande_aucun_lettrage(self):
        result = lettrer_gr_ir_facture(
            facture=None, company=self.company, user=self.user)
        self.assertEqual(result, [])


class IsolationSocieteTests(TestCase):
    def test_provision_scopee_societe(self):
        co1 = make_company('co-yproc3-t1', 'CoYproc3T1')
        co2 = make_company('co-yproc3-t2', 'CoYproc3T2')
        user1 = make_user(co1, 'resp-yproc3-t1')
        produit1 = make_produit(co1, 'Prod1')
        make_produit(co2, 'Prod2')
        reception, _ = make_reception_confirmee(co1, produit1, user1)
        self.assertEqual(
            ReceptionNonFacturee.objects.filter(company=co2).count(), 0)
        self.assertEqual(
            ReceptionNonFacturee.objects.filter(
                company=co1, reception=reception).count(), 1)
