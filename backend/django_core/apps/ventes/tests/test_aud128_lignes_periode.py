"""AUD128 — les lignes de facture n'échappent plus au verrou de période.

`LigneFactureViewSet._check_immuable` ne consultait que
`CompanyProfile.factures_immuables` (XFAC24, opt-in, défaut OFF) : ni
`perform_create`, ni `perform_update`, ni `perform_destroy` (qui fait un
`delete()` PHYSIQUE) n'appelaient la garde YLEDG3
`verifier_facture_modifiable`, que `FactureViewSet` applique pourtant
systématiquement et qu'`AvoirViewSet` duplique. Le total d'une facture d'un
exercice déjà déclaré à la DGI se modifiait donc ligne par ligne, sans
qu'aucune garde ne s'y oppose et sans que l'écriture GL correspondante bouge.

POST, PATCH et DELETE sur une ligne d'une facture en période verrouillée
sont les trois cas ROUGES ; leurs jumeaux hors période prouvent qu'aucun
comportement légitime n'est cassé.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta.models import PeriodeComptable
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture

User = get_user_model()

URL = '/api/django/ventes/factures-lignes/'


def make_company(slug='aud128-co', nom='AUD128 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestAUD128LignesPeriodeVerrouillee(TestCase):
    def setUp(self):
        from apps.roles.models import ALL_PERMISSIONS, Role
        self.company = make_company()
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='aud128_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD128',
            telephone='+212600000128')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-AUD128',
            prix_vente=Decimal('5000'), quantite_stock=10,
            tva=Decimal('20.00'))
        # Facture émise DATÉE dans février 2026 (date_emission est
        # auto_now_add : on la force par update() comme le fait YLEDG3).
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD128-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        Facture.objects.filter(pk=self.facture.pk).update(
            date_emission=date(2026, 2, 10))
        self.facture.refresh_from_db()
        self.ligne = LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('5000'), taux_tva=Decimal('20.00'))

    def _verrouiller_fevrier(self):
        return PeriodeComptable.objects.create(
            company=self.company, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)

    def _corps_ligne(self):
        return {
            'facture': self.facture.id, 'produit': self.produit.id,
            'designation': 'Ajout', 'quantite': '1',
            'prix_unitaire': '1000', 'taux_tva': '20',
        }

    # ── ROUGES ──
    def test_post_ligne_en_periode_verrouillee_refuse(self):
        self._verrouiller_fevrier()
        avant = LigneFacture.objects.filter(facture=self.facture).count()
        r = self.api.post(URL, self._corps_ligne(), format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(
            LigneFacture.objects.filter(facture=self.facture).count(), avant)

    def test_patch_ligne_en_periode_verrouillee_refuse(self):
        self._verrouiller_fevrier()
        r = self.api.patch(
            f'{URL}{self.ligne.id}/', {'prix_unitaire': '9999'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.prix_unitaire, Decimal('5000.00'))

    def test_delete_ligne_en_periode_verrouillee_refuse(self):
        """Le `delete()` est PHYSIQUE : sans garde, la ligne disparaissait
        d'une facture d'un exercice déjà déclaré."""
        self._verrouiller_fevrier()
        r = self.api.delete(f'{URL}{self.ligne.id}/')
        self.assertEqual(r.status_code, 400)
        self.assertTrue(
            LigneFacture.objects.filter(pk=self.ligne.pk).exists())

    # ── VERTS : hors période close, rien ne change ──
    def test_post_hors_periode_verrouillee_passe(self):
        PeriodeComptable.objects.create(
            company=self.company, date_debut=date(2026, 4, 1),
            date_fin=date(2026, 4, 30), verrouillee=True)
        r = self.api.post(URL, self._corps_ligne(), format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_patch_sans_aucune_periode_passe(self):
        r = self.api.patch(
            f'{URL}{self.ligne.id}/', {'prix_unitaire': '5500'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.prix_unitaire, Decimal('5500.00'))

    def test_delete_sans_aucune_periode_passe(self):
        r = self.api.delete(f'{URL}{self.ligne.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(
            LigneFacture.objects.filter(pk=self.ligne.pk).exists())

    def test_deplacement_vers_une_facture_en_periode_close_refuse(self):
        """Un PATCH qui DÉPLACE la ligne vers une facture d'un exercice
        clôturé écrirait dans cet exercice par la porte de derrière."""
        ouverte = Facture.objects.create(
            company=self.company, reference='FAC-AUD128-0002',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        ligne_ouverte = LigneFacture.objects.create(
            facture=ouverte, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        self._verrouiller_fevrier()
        r = self.api.patch(
            f'{URL}{ligne_ouverte.id}/', {'facture': self.facture.id},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        ligne_ouverte.refresh_from_db()
        self.assertEqual(ligne_ouverte.facture_id, ouverte.id)
