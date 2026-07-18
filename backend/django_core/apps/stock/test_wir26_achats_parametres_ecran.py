"""WIR26 — Écran Paramètres → Achats (`AchatsParametres`) + statut de blocage
fournisseur exposé sur la fiche.

`AchatsParametres` (XPUR1 blocage conformité, XPUR2 `ras_tva_actif` LF2024,
XPUR10 tolérances 3-voies) n'avait AUCUN écran : la RAS-TVA était inactivable
sans accès DB, faute d'exposition API des champs. Le blocage fournisseur
(XPUR4) était déjà appliqué et testé côté serveur (`test_xpur4_statut_
fournisseur.py`) mais n'avait aucun sélecteur en façade.

Couvre le bout-en-bout que le NOUVEL écran/sélecteur emprunte réellement :
  * GET `/stock/achats-parametres/` expose désormais `ras_tva_actif` et les
    3 tolérances XPUR10 (jusqu'ici absentes du serializer) ;
  * PATCH `/stock/achats-parametres/<id>/` bascule `ras_tva_actif` → la
    retenue s'applique au paiement suivant (même chaîne que le futur
    écran) ;
  * PATCH `/stock/fournisseurs/<id>/` (le nouveau sélecteur statut +
    motif_blocage) bloque ensuite la création d'un BCF/paiement — la
    même garde déjà testée par XPUR4, mais déclenchée ici via une mise à
    jour de fiche plutôt qu'à la création.

Run:
    python manage.py test apps.stock.test_wir26_achats_parametres_ecran -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import AchatsParametres, FactureFournisseur, Fournisseur, Produit

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Wir26Base(TestCase):
    def setUp(self):
        self.company = _company('wir26-co')
        self.user = _user(
            self.company, 'wir26-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur WIR26', sku='OND-WIR26',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur WIR26')


class TestAchatsParametresApi(Wir26Base):
    def test_get_expose_ras_tva_et_tolerances(self):
        resp = self.api.get('/api/django/stock/achats-parametres/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for field in (
            'bloquer_paiement_conformite_expiree', 'ras_tva_actif',
            'tolerance_prix_pct', 'tolerance_prix_absolu_mad',
            'tolerance_quantite_pct',
        ):
            self.assertIn(field, resp.data)
        # Défauts inchangés (comportement historique) tant que rien n'est
        # basculé côté écran.
        self.assertFalse(resp.data['ras_tva_actif'])

    def test_patch_active_ras_tva_et_persiste(self):
        get_resp = self.api.get('/api/django/stock/achats-parametres/')
        pk = get_resp.data['id']
        patch_resp = self.api.patch(
            f'/api/django/stock/achats-parametres/{pk}/',
            {'ras_tva_actif': True}, format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)
        self.assertTrue(patch_resp.data['ras_tva_actif'])
        self.assertTrue(
            AchatsParametres.objects.get(company=self.company).ras_tva_actif)

    def test_patch_tolerances_xpur10_persiste(self):
        get_resp = self.api.get('/api/django/stock/achats-parametres/')
        pk = get_resp.data['id']
        patch_resp = self.api.patch(
            f'/api/django/stock/achats-parametres/{pk}/',
            {
                'tolerance_prix_pct': '5.00',
                'tolerance_prix_absolu_mad': '50.00',
                'tolerance_quantite_pct': '2.00',
            }, format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)
        obj = AchatsParametres.objects.get(company=self.company)
        self.assertEqual(obj.tolerance_prix_pct, Decimal('5.00'))
        self.assertEqual(obj.tolerance_prix_absolu_mad, Decimal('50.00'))
        self.assertEqual(obj.tolerance_quantite_pct, Decimal('2.00'))

    def test_patch_refuse_sans_permission(self):
        readonly_user = _user(self.company, 'wir26-lecture', permissions=[])
        api = _api(readonly_user)
        get_resp = self.api.get('/api/django/stock/achats-parametres/')
        pk = get_resp.data['id']
        resp = api.patch(
            f'/api/django/stock/achats-parametres/{pk}/',
            {'ras_tva_actif': True}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)


class TestRasTvaBoutEnBoutViaEcran(Wir26Base):
    """Le futur écran ne fait qu'un PATCH sur `achats-parametres/<id>/` —
    preuve que ce PATCH (et pas seulement l'objet créé directement en base,
    déjà couvert par test_xpur2_ras_tva.py) déclenche bien la retenue."""

    def test_toggle_via_api_applique_la_retenue_au_paiement_suivant(self):
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-WIR26-1',
            fournisseur=self.fournisseur,
            type_achat=FactureFournisseur.TypeAchat.SERVICES,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))

        # Avant activation : aucune retenue (comportement historique).
        resp_avant = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp_avant.status_code, 201, resp_avant.data)
        self.assertEqual(Decimal(resp_avant.data['montant_ras_tva']), Decimal('0'))

        # Bascule EXACTEMENT comme le fera l'écran : GET puis PATCH par id.
        get_resp = self.api.get('/api/django/stock/achats-parametres/')
        pk = get_resp.data['id']
        patch_resp = self.api.patch(
            f'/api/django/stock/achats-parametres/{pk}/',
            {'ras_tva_actif': True}, format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)

        facture2 = FactureFournisseur.objects.create(
            company=self.company, reference='FF-WIR26-2',
            fournisseur=self.fournisseur,
            type_achat=FactureFournisseur.TypeAchat.SERVICES,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        resp_apres = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture2.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp_apres.status_code, 201, resp_apres.data)
        # Services sans ARF valide → retenue 100 % de la TVA (200.00).
        self.assertEqual(
            Decimal(resp_apres.data['montant_ras_tva']), Decimal('200.00'))


class TestStatutFournisseurViaFiche(Wir26Base):
    """Le nouveau sélecteur statut + motif_blocage de la fiche fournisseur
    n'est qu'un PATCH sur `/stock/fournisseurs/<id>/` — preuve que basculer
    le statut PAR CE CHEMIN (mise à jour de fiche, pas création directe en
    base) bloque bien BCF/paiement ensuite (garde XPUR4 déjà testée à la
    création dans test_xpur4_statut_fournisseur.py)."""

    def test_bloquer_commandes_depuis_la_fiche_refuse_le_bcf_suivant(self):
        patch_resp = self.api.patch(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/',
            {
                'statut': Fournisseur.Statut.BLOQUE_COMMANDES,
                'motif_blocage': 'Retard qualité répété',
            }, format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)
        self.fournisseur.refresh_from_db()
        self.assertEqual(
            self.fournisseur.statut, Fournisseur.Statut.BLOQUE_COMMANDES)

        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 1,
                'prix_achat_unitaire': '100',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Retard qualité répété', resp.data['detail'])

    def test_bloquer_paiements_depuis_la_fiche_refuse_le_paiement_suivant(self):
        self.api.patch(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/',
            {'statut': Fournisseur.Statut.BLOQUE_PAIEMENTS}, format='json')
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-WIR26-3',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_repasser_actif_depuis_la_fiche_debloque(self):
        self.fournisseur.statut = Fournisseur.Statut.BLOQUE_TOTAL
        self.fournisseur.save(update_fields=['statut'])
        self.api.patch(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/',
            {'statut': Fournisseur.Statut.ACTIF}, format='json')
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 1,
                'prix_achat_unitaire': '100',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
