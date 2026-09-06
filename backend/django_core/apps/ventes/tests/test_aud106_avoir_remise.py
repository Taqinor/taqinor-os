"""AUD106 — l'Avoir honore enfin ``remise_globale``.

``creer_avoir`` ne reprenait JAMAIS ``remise_globale`` de la facture, et
aucune des trois propriétés de totaux de l'``Avoir`` ne la lisait : l'avoir
TOTAL recopiait les lignes BRUTES alors que la facture facture le NET.
Le champ ``Avoir.remise_globale`` existait pourtant depuis sa migration
d'origine — grep sur tout ``apps/`` : jamais lu, jamais posé. Un champ
d'argent MORT sur un document client, qui donnait l'illusion que la remise
était gérée (FAC-16).

Scénario : facture remisée à 15 % — 20 400 TTC facturés, 24 000 TTC crédités,
soit 3 600 MAD offerts au client.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, LigneFacture
from apps.ventes.utils.pdf import _company_context, _render_html
from apps.ventes.tests.test_aud105_pdf_facture_remise import montant
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def valeurs_totaux_avoir(html):
    """Les lignes du bloc « Totaux » de l'AVOIR rendu : {libellé: Decimal}."""
    import re
    bloc = html.split('<div class="totaux">', 1)[1]
    bloc = bloc.split('<div class="footer"', 1)[0]
    return {
        lib: montant(val)
        for lib, val in re.findall(
            r'<span>([^<]*)</span>\s*<span>([^<]*)</span>', bloc)
        if 'MAD' in val
    }


class TestAvoirRemiseGlobale(TestCase):
    def setUp(self):
        from apps.roles.models import ALL_PERMISSIONS, Role

        self.company = Company.objects.create(
            nom='AUD106 Co', slug=f'aud106-{_nxt()}')
        role = Role.objects.create(
            company=self.company, nom=f'Admin {_nxt()}',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username=f'aud106_{_nxt()}', password='x', role=role,
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD106', prenom='Client',
            telephone='+212600000107')
        self.p1 = Produit.objects.create(
            company=self.company, nom='Kit', sku=f'AUD106A-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=50)
        self.p2 = Produit.objects.create(
            company=self.company, nom='Pose', sku=f'AUD106B-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=50)
        # 20 000 HT brut (2 × 10 000), remise 15 %, TVA 20 %
        # → HT net 17 000, TVA 3 400, TTC 20 400.
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD106-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('15.00'))
        self.l1 = LigneFacture.objects.create(
            facture=self.facture, produit=self.p1, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20.00'))
        self.l2 = LigneFacture.objects.create(
            facture=self.facture, produit=self.p2, designation='Pose',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20.00'))

    def _url(self):
        return f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/'

    def test_avoir_total_credite_exactement_le_ttc_facture(self):
        self.assertEqual(self.facture.total_ttc, Decimal('20400.00'))
        resp = self.api.post(self._url(), {'motif': 'Retour'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(pk=resp.data['id'])
        self.assertEqual(avoir.remise_globale, Decimal('15.00'))
        self.assertEqual(avoir.total_ttc, self.facture.total_ttc)
        self.assertEqual(avoir.total_ht, Decimal('17000.00'))

    def test_avoir_partiel_credite_la_part_remisee(self):
        resp = self.api.post(self._url(), {
            'motif': 'Geste',
            'lignes': [{
                'designation': 'Kit', 'quantite': '1',
                'prix_unitaire': '10000', 'taux_tva': '20',
                'produit': self.p1.id,
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(pk=resp.data['id'])
        # 10 000 brut − 15 % = 8 500 HT net, TVA 1 700 → 10 200 TTC.
        self.assertEqual(avoir.total_ht, Decimal('8500.00'))
        self.assertEqual(avoir.total_ttc, Decimal('10200.00'))

    def test_le_pdf_avoir_se_reconcilie_au_centime(self):
        resp = self.api.post(self._url(), {'motif': 'Retour'}, format='json')
        avoir = Avoir.objects.get(pk=resp.data['id'])
        ctx = _company_context(company=self.company)
        ctx['avoir'] = avoir
        html = _render_html('avoir.html', ctx)
        valeurs = valeurs_totaux_avoir(html)
        sous_total = next(v for lib, v in valeurs.items()
                          if 'Sous-total' in lib)
        remise = next(v for lib, v in valeurs.items() if 'Remise' in lib)
        tva = sum(v for lib, v in valeurs.items() if lib.startswith('TVA'))
        ttc = next(v for lib, v in valeurs.items() if 'TTC' in lib)
        self.assertEqual(sous_total, Decimal('20000.00'))
        self.assertEqual(remise, Decimal('-3000.00'))
        self.assertEqual(sous_total + remise + tva, ttc)
        self.assertEqual(ttc, Decimal('20400.00'))

    def test_avoir_sans_remise_reste_inchange(self):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD106-N{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.p1, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20.00'))
        resp = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/',
            {'motif': 'Retour'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        avoir = Avoir.objects.get(pk=resp.data['id'])
        self.assertEqual(avoir.remise_globale, Decimal('0'))
        self.assertEqual(avoir.total_ht, Decimal('10000.00'))
        self.assertEqual(avoir.total_ttc, Decimal('12000.00'))


class TestMixinPartage(TestCase):
    """Le mixin est bien LE seul propriétaire de la chaîne, sur les 2 modèles."""

    def test_facture_et_avoir_partagent_le_mixin(self):
        from apps.facturation.models import (
            Avoir as AvoirModel, Facture as FactureModel,
            TotauxDocumentMixin,
        )
        self.assertTrue(issubclass(FactureModel, TotauxDocumentMixin))
        self.assertTrue(issubclass(AvoirModel, TotauxDocumentMixin))
        for nom in ('total_ht', 'total_tva', 'tva_par_taux', 'total_ttc',
                    'totaux_affichage', '_remise_globale_active'):
            self.assertIs(
                getattr(FactureModel, nom), getattr(TotauxDocumentMixin, nom),
                f'Facture.{nom} ne vient plus du mixin partagé.')
            self.assertIs(
                getattr(AvoirModel, nom), getattr(TotauxDocumentMixin, nom),
                f'Avoir.{nom} ne vient plus du mixin partagé.')
