"""Tests des correctifs du backlog d'erreurs (ERR7-8, 13-16, 33-36, 71-74).

Couvre les gardes tenant (injection IDOR de lignes / mass-assignment), la
quantité décimale au stock, le respect de l'option acceptée par la voie legacy
BC→Facture, la garde de statut à l'acceptation, la validation bruyante des
lignes d'avoir, la séquence de relance multi-niveaux, la TVA devis quantizée,
le verrou anti-surpaiement et la portée de visibilité du relevé.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.roles.models import Role, ALL_PERMISSIONS, RESPONSABLE_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes.models import (
    Avoir, BonCommande, Devis, LigneDevis, Facture, LigneFacture,
    FollowupLevel, RelanceLog,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug, nom=None):
    return Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom or slug})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_client(company, email='c@example.com', nom='Client'):
    return Client.objects.create(
        company=company, nom=nom, prenom='X', email=email,
        telephone='+212600000001', adresse='Casablanca')


class TestTenantLineInjection(TestCase):
    """ERR7 — poster une ligne sur le devis/facture d'une AUTRE société est
    rejeté (pas d'injection IDOR en écriture)."""

    @classmethod
    def setUpTestData(cls):
        cls.co_a = make_company('idor-a')
        cls.co_b = make_company('idor-b')
        cls.user_a = User.objects.create_user(
            username='idor_a', password='x', role_legacy='responsable',
            company=cls.co_a)
        cls.client_b = make_client(cls.co_b, email='b@example.com')
        cls.devis_b = Devis.objects.create(
            company=cls.co_b, reference=f'DEV-{MONTH}-7001',
            client=cls.client_b, statut=Devis.Statut.BROUILLON)
        cls.facture_b = Facture.objects.create(
            company=cls.co_b, reference=f'FAC-{MONTH}-7001',
            client=cls.client_b, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'))
        cls.produit_a = Produit.objects.create(
            company=cls.co_a, nom='Panneau', sku='P-A',
            prix_vente=Decimal('1000'), quantite_stock=10)

    def setUp(self):
        self.api = auth(self.user_a)

    def test_cannot_inject_ligne_devis_on_other_company(self):
        r = self.api.post('/api/django/ventes/devis-lignes/', {
            'devis': self.devis_b.id, 'produit': self.produit_a.id,
            'designation': 'Inject', 'quantite': '1',
            'prix_unitaire': '1000', 'remise': '0',
        }, format='json')
        self.assertIn(r.status_code, (400, 403), r.data)
        self.assertEqual(LigneDevis.objects.filter(devis=self.devis_b).count(), 0)

    def test_cannot_inject_ligne_facture_on_other_company(self):
        r = self.api.post('/api/django/ventes/factures-lignes/', {
            'facture': self.facture_b.id, 'produit': self.produit_a.id,
            'designation': 'Inject', 'quantite': '1',
            'prix_unitaire': '1000', 'remise': '0',
        }, format='json')
        self.assertIn(r.status_code, (400, 403), r.data)
        self.assertEqual(
            LigneFacture.objects.filter(facture=self.facture_b).count(), 0)


class TestDevisUpdateTenant(TestCase):
    """ERR8 — un PATCH ne peut pas re-pointer un devis vers le client/lead
    d'une autre société."""

    @classmethod
    def setUpTestData(cls):
        cls.co_a = make_company('upd-a')
        cls.co_b = make_company('upd-b')
        cls.user_a = User.objects.create_user(
            username='upd_a', password='x', role_legacy='responsable',
            company=cls.co_a)
        cls.client_a = make_client(cls.co_a, email='a@example.com')
        cls.client_b = make_client(cls.co_b, email='b2@example.com')
        cls.lead_b = Lead.objects.create(company=cls.co_b, nom='LeadB')
        cls.devis = Devis.objects.create(
            company=cls.co_a, reference=f'DEV-{MONTH}-8001',
            client=cls.client_a, statut=Devis.Statut.BROUILLON)

    def setUp(self):
        self.api = auth(self.user_a)

    def test_cannot_repoint_to_other_company_client(self):
        r = self.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/',
            {'client': self.client_b.id}, format='json')
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.client_id, self.client_a.id)

    def test_cannot_repoint_to_other_company_lead(self):
        r = self.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/',
            {'lead': self.lead_b.id}, format='json')
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.devis.refresh_from_db()
        self.assertIsNone(self.devis.lead_id)


class TestBonCommandeFactureTenant(TestCase):
    """ERR13/ERR14 — créer un BC/une facture lié à un enregistrement d'un autre
    tenant est rejeté."""

    @classmethod
    def setUpTestData(cls):
        cls.co_a = make_company('bc-a')
        cls.co_b = make_company('bc-b')
        cls.user_a = User.objects.create_user(
            username='bc_a', password='x', role_legacy='responsable',
            company=cls.co_a)
        cls.client_a = make_client(cls.co_a, email='bca@example.com')
        cls.client_b = make_client(cls.co_b, email='bcb@example.com')

    def setUp(self):
        self.api = auth(self.user_a)

    def test_bc_rejects_other_company_client(self):
        r = self.api.post('/api/django/ventes/bons-commande/', {
            'client': self.client_b.id, 'statut': 'en_attente',
        }, format='json')
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.assertEqual(
            BonCommande.objects.filter(client=self.client_b).count(), 0)

    def test_facture_rejects_other_company_client(self):
        r = self.api.post('/api/django/ventes/factures/', {
            'client': self.client_b.id, 'taux_tva': '20.00',
        }, format='json')
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.assertEqual(
            Facture.objects.filter(client=self.client_b).count(), 0)


class TestMarquerLivreDecimal(TestCase):
    """ERR15 — marquer-livre n'utilise plus int() qui tronquait la quantité
    décimale (3,5 → 3) ; on arrondit (3,5 → 4)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('liv-co')
        cls.user = User.objects.create_user(
            username='liv_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = make_client(cls.company, email='liv@example.com')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Câble 6mm', sku='CABLE-6',
            prix_vente=Decimal('100'), quantite_stock=10)
        cls.devis = Devis.objects.create(
            company=cls.company, reference=f'DEV-{MONTH}-1501',
            client=cls.client_obj, statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=cls.devis, produit=cls.produit, designation='Câble 6mm',
            quantite=Decimal('3.5'), prix_unitaire=Decimal('100'))
        cls.bc = BonCommande.objects.create(
            company=cls.company, reference=f'BC-{MONTH}-1501',
            devis=cls.devis, client=cls.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def setUp(self):
        self.api = auth(self.user)

    def test_fractional_quantity_not_truncated(self):
        from apps.stock.models import MouvementStock
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/marquer-livre/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        self.produit.refresh_from_db()
        # 3,5 arrondi HALF_UP → 4 décrémentés (pas 3, l'ancien int()).
        self.assertEqual(self.produit.quantite_stock, 6)
        mv = MouvementStock.objects.get(produit=self.produit)
        self.assertEqual(mv.quantite, 4)
        self.assertEqual(mv.quantite_apres, 6)


class TestLegacyFactureHonorsOption(TestCase):
    """ERR16 — la voie legacy BC→Facture ne facture QUE les lignes de l'option
    retenue (« Sans batterie » / « Avec batterie »), pas les deux."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('opt-co')
        admin_role = Role.objects.create(
            company=cls.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        cls.admin = User.objects.create_user(
            username='opt_admin', password='x', role=admin_role,
            role_legacy='admin', company=cls.company)
        cls.client_obj = make_client(cls.company, email='opt@example.com')
        # Devis à DEUX options : onduleur réseau + (onduleur hybride + batterie).
        cls.devis = Devis.objects.create(
            company=cls.company, reference=f'DEV-{MONTH}-1601',
            client=cls.client_obj, statut=Devis.Statut.ACCEPTE,
            option_acceptee=Devis.OptionAcceptee.SANS_BATTERIE)
        for desig, qty, pu in [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ]:
            produit = Produit.objects.create(
                company=cls.company, nom=desig, sku=f'OPT-{desig[:10]}',
                prix_vente=Decimal(pu), quantite_stock=100,
                tva=Decimal('20.00'))
            LigneDevis.objects.create(
                devis=cls.devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                taux_tva=Decimal('20.00'))
        cls.bc = BonCommande.objects.create(
            company=cls.company, reference=f'BC-{MONTH}-1601',
            devis=cls.devis, client=cls.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def setUp(self):
        self.api = auth(self.admin)

    def test_creer_facture_excludes_unchosen_option_lines(self):
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/creer-facture/')
        self.assertEqual(r.status_code, 201, getattr(r, 'data', r))
        facture = Facture.objects.get(pk=r.data['id'])
        designations = set(
            facture.lignes.values_list('designation', flat=True))
        # « Sans batterie » exclut la batterie ET l'onduleur hybride.
        self.assertNotIn('Batterie 5 kWh', designations)
        self.assertNotIn('Onduleur hybride', designations)
        self.assertIn('Onduleur réseau', designations)
        # Strictement moins de lignes que le devis complet (5).
        self.assertLess(facture.lignes.count(), 5)


class TestAccepterStatusGuard(TestCase):
    """ERR33 — accepter un devis refusé/expiré/déjà accepté est rejeté."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('acc-guard-co')
        cls.user = User.objects.create_user(
            username='accg_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = make_client(cls.company, email='accg@example.com')

    def setUp(self):
        self.api = auth(self.user)

    def _devis(self, num, statut):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-33{num:02d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    def _accepter(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-13'}, format='json')

    def test_cannot_accept_refused(self):
        devis = self._devis(1, Devis.Statut.REFUSE)
        r = self._accepter(devis)
        self.assertEqual(r.status_code, 409, getattr(r, 'data', r))
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.REFUSE)

    def test_cannot_accept_expired(self):
        devis = self._devis(2, Devis.Statut.EXPIRE)
        self.assertEqual(self._accepter(devis).status_code, 409)

    def test_cannot_reaccept_accepted(self):
        devis = self._devis(3, Devis.Statut.ACCEPTE)
        self.assertEqual(self._accepter(devis).status_code, 409)

    def test_can_accept_envoye(self):
        devis = self._devis(4, Devis.Statut.ENVOYE)
        self.assertEqual(self._accepter(devis).status_code, 200)


class TestAvoirLineValidation(TestCase):
    """ERR34 — creer-avoir valide les lignes et échoue bruyamment (400) au lieu
    d'avaler les lignes invalides en silence."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('avo-val-co')
        admin_role = Role.objects.create(
            company=cls.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        cls.admin = User.objects.create_user(
            username='avoval_admin', password='x', role=admin_role,
            role_legacy='admin', company=cls.company)
        cls.client_obj = make_client(cls.company, email='avoval@example.com')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Onduleur', sku='OND-V',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20'))
        cls.facture = Facture.objects.create(
            company=cls.company, reference=f'FAC-{MONTH}-3401',
            client=cls.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=cls.facture, produit=cls.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def setUp(self):
        self.api = auth(self.admin)

    def _avoir(self, lignes):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'lignes': lignes}, format='json')

    def test_null_designation_fails_loudly(self):
        r = self._avoir([
            {'designation': None, 'quantite': '1', 'prix_unitaire': '100'}])
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.assertEqual(Avoir.objects.count(), 0)

    def test_invalid_quantite_fails_loudly(self):
        r = self._avoir([
            {'designation': 'X', 'quantite': 'abc', 'prix_unitaire': '100'}])
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.assertEqual(Avoir.objects.count(), 0)

    def test_valid_line_still_works(self):
        # DC10 — une ligne d'avoir valide porte désormais un produit.
        r = self._avoir([
            {'produit': self.produit.id, 'designation': 'Remboursement',
             'quantite': '1', 'prix_unitaire': '100', 'taux_tva': '20'}])
        self.assertEqual(r.status_code, 201, getattr(r, 'data', r))
        self.assertEqual(Avoir.objects.count(), 1)
        self.assertEqual(Avoir.objects.first().lignes.count(), 1)

    def test_dc10_line_without_produit_rejected(self):
        # DC10 — une nouvelle ligne d'avoir SANS produit est refusée (400).
        r = self._avoir([
            {'designation': 'Sans produit', 'quantite': '1',
             'prix_unitaire': '100', 'taux_tva': '20'}])
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.assertEqual(Avoir.objects.count(), 0)


class TestRelanceMultiLevel(TestCase):
    """ERR36 — relance_reminders avance niveau par niveau au lieu de tirer une
    seule fois et de sauter au niveau le plus dur."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('rel-co')
        for ordre, nom, delai in [
            (0, 'Rappel', 7), (1, 'Relance', 15), (2, 'Mise en demeure', 30),
        ]:
            FollowupLevel.objects.create(
                company=cls.company, ordre=ordre, nom=nom, delai_jours=delai)
        cls.client_obj = make_client(cls.company, email='rel@example.com')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Onduleur', sku='OND-REL',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20'))
        # Facture due, échéance dépassée de 40 jours, prochaine_relance échue.
        cls.facture = Facture.objects.create(
            company=cls.company, reference='FAC-REL-0001',
            client=cls.client_obj, statut=Facture.Statut.EN_RETARD,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=40),
            prochaine_relance=date.today())
        LigneFacture.objects.create(
            facture=cls.facture, produit=cls.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def test_advances_level_by_level(self):
        from apps.ventes.scheduled import relance_reminders
        # 1er passage : niveau 0 (Rappel), prochaine_relance avancée (pas nulle).
        relance_reminders()
        self.facture.refresh_from_db()
        logs = list(RelanceLog.objects.filter(
            facture=self.facture).order_by('id'))
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].niveau_nom, 'Rappel')
        self.assertIsNotNone(self.facture.prochaine_relance)
        # Forcer l'échéance de la prochaine relance pour rejouer le job.
        self.facture.prochaine_relance = date.today()
        self.facture.save(update_fields=['prochaine_relance'])
        # 2e passage : niveau 1 (Relance) — PAS un saut direct au plus dur.
        relance_reminders()
        self.facture.refresh_from_db()
        logs = list(RelanceLog.objects.filter(
            facture=self.facture).order_by('id'))
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[1].niveau_nom, 'Relance')
        # 3e passage : dernier niveau (Mise en demeure), date effacée → stop.
        self.facture.prochaine_relance = date.today()
        self.facture.save(update_fields=['prochaine_relance'])
        relance_reminders()
        self.facture.refresh_from_db()
        logs = list(RelanceLog.objects.filter(
            facture=self.facture).order_by('id'))
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[2].niveau_nom, 'Mise en demeure')
        self.assertIsNone(self.facture.prochaine_relance)


class TestDevisTvaQuantize(TestCase):
    """ERR71 — Devis.total_tva quantize par panier de taux comme Facture, donc
    devis et facture s'accordent au centime sur un devis à taux mixtes."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('tva-co')
        cls.client_obj = make_client(cls.company, email='tva@example.com')

    def test_devis_total_tva_matches_facture_per_bucket(self):
        # Lignes choisies pour faire apparaître un centime sur un taux mixte.
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-7101',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'))
        p1 = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PV-71',
            prix_vente=Decimal('333.33'), quantite_stock=100, tva=Decimal('10'))
        p2 = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-71',
            prix_vente=Decimal('333.33'), quantite_stock=100, tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=p1, designation='Panneau',
            quantite=Decimal('3'), prix_unitaire=Decimal('333.33'),
            taux_tva=Decimal('10.00'))
        LigneDevis.objects.create(
            devis=devis, produit=p2, designation='Onduleur',
            quantite=Decimal('3'), prix_unitaire=Decimal('333.33'),
            taux_tva=Decimal('20.00'))
        # La TVA devis doit être la somme quantizée par panier (centime).
        from decimal import ROUND_HALF_UP

        def q(x):
            return Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        base10 = Decimal('999.99')  # 3 × 333.33
        base20 = Decimal('999.99')
        expected = q(base10 * Decimal('10') / Decimal('100')) + \
            q(base20 * Decimal('20') / Decimal('100'))
        self.assertEqual(q(devis.total_tva), q(expected))
        # Cohérence devis ↔ facture : une facture aux mêmes lignes a la même TVA.
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-7101',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        for li in devis.lignes.all():
            LigneFacture.objects.create(
                facture=facture, produit=li.produit,
                designation=li.designation, quantite=li.quantite,
                prix_unitaire=li.prix_unitaire, taux_tva=li.taux_tva)
        self.assertEqual(q(devis.total_tva), q(facture.total_tva))


class TestPaiementRowLock(TestCase):
    """ERR72 — la garde sur-paiement lit le reste sous verrou (select_for_update)
    et reste correcte (comportement fonctionnel inchangé, sérialisé)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('lock-co')
        cls.user = User.objects.create_user(
            username='lock_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = make_client(cls.company, email='lock@example.com')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Onduleur', sku='OND-L',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20'))
        cls.facture = Facture.objects.create(
            company=cls.company, reference='FAC-LOCK-0001',
            client=cls.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=cls.facture, produit=cls.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))  # 6000 TTC

    def setUp(self):
        self.api = auth(self.user)

    def _pay(self, montant):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': montant, 'date_paiement': '2026-06-13',
             'mode': 'virement'}, format='json')

    def test_overpayment_rejected_under_lock(self):
        r = self._pay('7000')  # > 6000 TTC
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r))
        self.assertIn('dépasse', r.data['detail'])

    def test_partial_then_remaining_settles(self):
        self.assertEqual(self._pay('4000').status_code, 201)
        r = self._pay('2000')  # solde exact
        self.assertEqual(r.status_code, 201, getattr(r, 'data', r))
        self.assertEqual(r.data['statut'], 'payee')

    def test_second_overpayment_rejected(self):
        self.assertEqual(self._pay('4000').status_code, 201)
        r = self._pay('3000')  # reste 2000 → refusé
        self.assertEqual(r.status_code, 400)


class TestReleveOwnerScope(TestCase):
    """ERR73 — le relevé client applique la portée de visibilité (un rôle
    restreint ne voit que ses propres factures, l'isolation société tenant
    déjà)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('releve-co')
        # Rôle restreint à l'équipe (records_scope_equipe).
        team_role = Role.objects.create(
            company=cls.company, nom='Commercial',
            permissions=RESPONSABLE_PERMISSIONS + ['records_scope_equipe'],
            est_systeme=False)
        cls.restricted = User.objects.create_user(
            username='releve_team', password='x', role=team_role,
            role_legacy='responsable', company=cls.company)
        cls.other = User.objects.create_user(
            username='releve_other', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = make_client(cls.company, email='releve@example.com')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Onduleur', sku='OND-RV',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20'))
        # Facture créée par UN AUTRE utilisateur (hors portée du restreint).
        cls.facture_other = Facture.objects.create(
            company=cls.company, reference='FAC-REL-OTHER',
            client=cls.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), created_by=cls.other)
        LigneFacture.objects.create(
            facture=cls.facture_other, produit=cls.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('5000'), taux_tva=Decimal('20.00'))
        # Facture créée par le restreint lui-même (dans sa portée).
        cls.facture_mine = Facture.objects.create(
            company=cls.company, reference='FAC-REL-MINE',
            client=cls.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), created_by=cls.restricted)
        LigneFacture.objects.create(
            facture=cls.facture_mine, produit=cls.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('5000'), taux_tva=Decimal('20.00'))

    def setUp(self):
        self.api = auth(self.restricted)

    def test_releve_excludes_out_of_scope_factures(self):
        r = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/releve/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        refs = {li['reference'] for li in r.data['lignes']}
        self.assertIn('FAC-REL-MINE', refs)
        self.assertNotIn('FAC-REL-OTHER', refs)


class TestProposalNoPersist(TestCase):
    """ERR74 — /proposal (GET sûr) ne ré-écrit pas fichier_pdf à chaque appel."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('prop-co')
        cls.user = User.objects.create_user(
            username='prop_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = make_client(cls.company, email='prop@example.com')
        cls.devis = Devis.objects.create(
            company=cls.company, reference='DEV-PROP-0001',
            client=cls.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'))

    def setUp(self):
        self.api = auth(self.user)

    def test_proposal_does_not_persist_fichier_pdf(self):
        from unittest import mock
        self.assertFalse(self.devis.fichier_pdf)
        with mock.patch(
            'apps.ventes.quote_engine.generate_devis_premium.'
            'generate_premium_pdf',
        ), mock.patch(
            'apps.ventes.quote_engine.builder._ensure_pdf_bucket',
        ), mock.patch(
            'apps.ventes.utils.pdf._upload_pdf',
        ), mock.patch(
            'apps.ventes.quote_engine.builder.Path',
        ), mock.patch(
            'apps.ventes.utils.pdf.download_pdf',
            return_value=b'%PDF-1.4 fake',
        ):
            resp = self.api.get(
                f'/api/django/ventes/devis/{self.devis.id}/proposal/'
                '?pdf_mode=onepage')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.devis.refresh_from_db()
        # Le GET sûr n'a PAS persisté la clé sur le modèle.
        self.assertFalse(self.devis.fichier_pdf)
