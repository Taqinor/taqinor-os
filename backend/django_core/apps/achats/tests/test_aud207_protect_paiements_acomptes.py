"""AUD207 — CASCADE sur `PaiementFournisseur.facture` et
`AcompteFournisseur.bon_commande` effaçait silencieusement les acomptes et
paiements réellement versés à la suppression d'une FactureFournisseur/d'un
BonCommandeFournisseur, sans aucune garde d'état.

Fix : les deux FK passent en PROTECT (migrations
`achats/0004_aud207_protect_paiementfournisseur_facture` et
`stock/0138_aud207_protect_acomptefournisseur_bon_commande`), doublé d'un
`perform_destroy` explicite sur les deux ViewSets (`FactureFournisseurViewSet`
et `BonCommandeFournisseurViewSet`, tous deux dans `apps.stock.views`) qui
refuse en 400 AVANT d'atteindre la contrainte DB — même patron que l'action
`annuler` de `installations/views/facture_soustraitant.py`.

Run:
    python manage.py test apps.achats.tests.test_aud207_protect_paiements_acomptes -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def make_company(slug='aud207-co', nom='AUD207 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_fournisseur(company, nom='AUD207 Fournisseur'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestAUD207ProtectPaiementFournisseur(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, 'aud207_admin', role='admin')
        self.fournisseur = make_fournisseur(self.company)
        self.api = auth(self.admin)

    def _facture(self, reference='FF-AUD207-0001'):
        from apps.achats.models import FactureFournisseur
        return FactureFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=self.fournisseur, montant_ttc=Decimal('1000.00'))

    def test_facture_avec_paiement_reel_suppression_refusee_400(self):
        """Test ROUGE d'abord (avant AUD207) : ce DELETE renvoyait 204 et
        effaçait en CASCADE le paiement réellement versé — la ligne
        financière disparaissait sans trace. APRÈS : 400 explicite, rien
        n'est supprimé."""
        from apps.achats.models import FactureFournisseur, PaiementFournisseur
        facture = self._facture()
        paiement = PaiementFournisseur.objects.create(
            company=self.company, facture=facture, montant=Decimal('500.00'))

        r = self.api.delete(f'/api/django/stock/factures-fournisseur/{facture.id}/')

        self.assertEqual(r.status_code, 400, r.data)
        self.assertTrue(
            FactureFournisseur.objects.filter(id=facture.id).exists(),
            "la facture a été supprimée malgré un paiement réel")
        self.assertTrue(
            PaiementFournisseur.objects.filter(id=paiement.id).exists(),
            "le paiement a disparu en CASCADE")

    def test_facture_sans_paiement_suppression_toujours_autorisee_204(self):
        """Contrôle négatif : une facture SANS paiement se supprime toujours
        normalement (comportement historique inchangé)."""
        from apps.achats.models import FactureFournisseur
        facture = self._facture(reference='FF-AUD207-0002')

        r = self.api.delete(f'/api/django/stock/factures-fournisseur/{facture.id}/')

        self.assertEqual(r.status_code, 204, r.data)
        self.assertFalse(FactureFournisseur.objects.filter(id=facture.id).exists())

    def test_modele_protect_reel_leve_protectederror_hors_api(self):
        """La contrainte PROTECT est un filet de sécurité RÉEL au niveau
        ORM/collector Django (pas seulement la garde de vue) : un
        `facture.delete()` direct — n'importe quel autre chemin de
        suppression, y compris l'admin Django — est aussi refusé."""
        from apps.achats.models import PaiementFournisseur
        facture = self._facture(reference='FF-AUD207-0003')
        PaiementFournisseur.objects.create(
            company=self.company, facture=facture, montant=Decimal('100.00'))
        with self.assertRaises(ProtectedError):
            facture.delete()


class TestAUD207ProtectAcompteFournisseur(TestCase):
    def setUp(self):
        self.company = make_company(slug='aud207-co-bcf', nom='AUD207 Co BCF')
        self.admin = make_user(self.company, 'aud207_admin_bcf', role='admin')
        self.fournisseur = make_fournisseur(self.company, nom='AUD207 Fournisseur BCF')
        self.api = auth(self.admin)

    def _bcf(self, reference='BCF-AUD207-0001'):
        from apps.achats.models import BonCommandeFournisseur
        return BonCommandeFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=self.fournisseur)

    def test_bcf_avec_acompte_reel_suppression_refusee_400(self):
        """Test ROUGE d'abord (avant AUD207) : ce DELETE renvoyait 204 et
        effaçait en CASCADE l'acompte réellement versé. APRÈS : 400
        explicite, rien n'est supprimé."""
        from apps.achats.models import BonCommandeFournisseur
        from apps.stock.models import AcompteFournisseur
        bcf = self._bcf()
        acompte = AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=Decimal('3000.00'))

        r = self.api.delete(f'/api/django/stock/bons-commande-fournisseur/{bcf.id}/')

        self.assertEqual(r.status_code, 400, r.data)
        self.assertTrue(
            BonCommandeFournisseur.objects.filter(id=bcf.id).exists(),
            "le BCF a été supprimé malgré un acompte réel")
        self.assertTrue(
            AcompteFournisseur.objects.filter(id=acompte.id).exists(),
            "l'acompte a disparu en CASCADE")

    def test_bcf_sans_acompte_suppression_toujours_autorisee_204(self):
        """Contrôle négatif : un BCF SANS acompte se supprime toujours
        normalement (comportement historique inchangé)."""
        from apps.achats.models import BonCommandeFournisseur
        bcf = self._bcf(reference='BCF-AUD207-0002')

        r = self.api.delete(f'/api/django/stock/bons-commande-fournisseur/{bcf.id}/')

        self.assertEqual(r.status_code, 204, r.data)
        self.assertFalse(BonCommandeFournisseur.objects.filter(id=bcf.id).exists())

    def test_modele_protect_reel_leve_protectederror_hors_api(self):
        """Filet de sécurité RÉEL au niveau ORM/collector Django : un
        `bcf.delete()` direct est aussi refusé, pas seulement via la garde
        de vue."""
        from apps.stock.models import AcompteFournisseur
        bcf = self._bcf(reference='BCF-AUD207-0003')
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=Decimal('500.00'))
        with self.assertRaises(ProtectedError):
            bcf.delete()
