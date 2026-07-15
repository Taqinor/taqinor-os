"""XSAL5 — Lignes optionnelles sur devis + activation self-service.

Une ligne ``LigneDevis.optionnelle=True`` (add-on : garantie étendue, monitoring,
batterie supplémentaire) est présentée au client HORS totaux ; elle n'entre dans
le HT/TVA/TTC (et les documents avals) qu'une fois ACTIVÉE (optionnelle=False via
``activate_optional_line`` — self-service proposition). Défaut False ⇒ un devis
sans option est octet-identique à aujourd'hui.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal5_options -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()


def make_company(slug='test-xsal5-co'):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Test XSAL5 Co'})
    return c


def make_client_obj(company):
    return Client.objects.create(
        company=company, nom='Opt', prenom='Client',
        email='opt@example.com', telephone='+212600000055')


def _produit(company, desig, sku, pu):
    return Produit.objects.create(
        company=company, nom=desig, sku=sku, prix_vente=Decimal(pu),
        prix_achat=Decimal('7'), quantite_stock=100)


class TestOptionalExcludedFromTotals(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsal5user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = make_client_obj(self.company)

    def _devis(self, reference='D-XSAL5-1'):
        return Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)

    def _ligne(self, devis, desig, sku, pu, qty='1', optionnelle=False):
        return LigneDevis.objects.create(
            devis=devis,
            produit=_produit(self.company, desig, sku, pu),
            designation=desig, quantite=Decimal(qty),
            prix_unitaire=Decimal(pu), remise=Decimal('0'),
            taux_tva=Decimal('20.00'), optionnelle=optionnelle)

    def test_optional_line_excluded_from_totals(self):
        """Un devis à 2 lignes (1 normale 1000, 1 optionnelle 400) ne compte
        que la ligne normale dans HT/TVA/TTC."""
        devis = self._devis()
        self._ligne(devis, 'Onduleur réseau 5kW', 'X5-OND', '1000')
        self._ligne(devis, 'Garantie étendue 5 ans', 'X5-GAR', '400',
                    optionnelle=True)
        self.assertEqual(Decimal(devis.total_ht), Decimal('1000'))
        self.assertEqual(Decimal(devis.total_ttc), Decimal('1200'))

    def test_activation_moves_line_into_totals(self):
        """Après activation, la ligne optionnelle entre dans les totaux."""
        from apps.ventes.services import activate_optional_line
        devis = self._devis('D-XSAL5-2')
        self._ligne(devis, 'Onduleur réseau 5kW', 'X5b-OND', '1000')
        opt = self._ligne(devis, 'Monitoring', 'X5b-MON', '400',
                          optionnelle=True)
        self.assertEqual(Decimal(devis.total_ht), Decimal('1000'))
        activate_optional_line(devis=devis, ligne_id=opt.id, user=self.user)
        opt.refresh_from_db()
        self.assertFalse(opt.optionnelle)
        devis2 = Devis.objects.get(pk=devis.pk)
        self.assertEqual(Decimal(devis2.total_ht), Decimal('1400'))
        self.assertEqual(Decimal(devis2.total_ttc), Decimal('1680'))
        # Chatter : une note d'activation a été consignée.
        self.assertTrue(devis2.activites.filter(
            kind='note', body__icontains='Option activée').exists())

    def test_activation_idempotent(self):
        """Ré-activer une ligne déjà activée est un no-op (aucun 2ᵉ chatter)."""
        from apps.ventes.services import activate_optional_line
        devis = self._devis('D-XSAL5-3')
        opt = self._ligne(devis, 'Batterie +', 'X5c-BAT', '500',
                          optionnelle=True)
        activate_optional_line(devis=devis, ligne_id=opt.id, user=self.user)
        activate_optional_line(devis=devis, ligne_id=opt.id, user=self.user)
        self.assertEqual(devis.activites.filter(
            body__icontains='Option activée').count(), 1)

    def test_activation_on_frozen_devis_refused(self):
        from apps.ventes.services import activate_optional_line, AcceptError
        devis = self._devis('D-XSAL5-4')
        devis.statut = 'accepte'
        devis.save(update_fields=['statut'])
        opt = self._ligne(devis, 'Add-on', 'X5d-ADD', '300', optionnelle=True)
        with self.assertRaises(AcceptError):
            activate_optional_line(devis=devis, ligne_id=opt.id, user=self.user)

    def test_no_option_is_byte_identical(self):
        """Un devis SANS option a exactement les totaux d'avant XSAL5."""
        devis = self._devis('D-XSAL5-5')
        self._ligne(devis, 'Onduleur réseau 5kW', 'X5e-OND', '1000', qty='2')
        self.assertEqual(Decimal(devis.total_ht), Decimal('2000'))
        self.assertEqual(Decimal(devis.total_ttc), Decimal('2400'))
        # Le prédicat de comptage : toutes les lignes comptent.
        self.assertTrue(all(li.compte_dans_totaux for li in devis.lignes.all()))

    def test_selector_canonical_totaux_excludes_optional(self):
        from apps.ventes.selectors import _canonical_totaux
        devis = self._devis('D-XSAL5-6')
        self._ligne(devis, 'Onduleur', 'X5f-OND', '1000')
        self._ligne(devis, 'Option', 'X5f-OPT', '999', optionnelle=True)
        tot = _canonical_totaux(
            list(devis.lignes.all()), remise_globale_pct=Decimal('0'),
            fallback_taux=Decimal('20'))
        self.assertEqual(tot['ht_net'], Decimal('1000.00'))
        self.assertEqual(tot['ttc'], Decimal('1200.00'))


class TestBuilderOptionsBlock(TestCase):
    def setUp(self):
        self.company = make_company('test-xsal5-b-co')
        self.user = User.objects.create_user(
            username='xsal5buser', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = make_client_obj(self.company)

    def _devis(self, reference='D-XSAL5-B1'):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=_produit(
                self.company, 'Onduleur réseau 5kW', f'{reference}-O', '1000'),
            designation='Onduleur réseau 5kW', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def test_options_block_present_and_no_prix_achat(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis()
        LigneDevis.objects.create(
            devis=devis, produit=_produit(
                self.company, 'Garantie étendue', 'D-XSAL5-B1-G', '400'),
            designation='Garantie étendue', quantite=Decimal('1'),
            prix_unitaire=Decimal('400'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'), optionnelle=True)
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertIn('options_proposees', data)
        self.assertEqual(len(data['options_proposees']), 1)
        opt = data['options_proposees'][0]
        self.assertEqual(opt['designation'], 'Garantie étendue')
        self.assertEqual(opt['total_ttc'], 480.0)
        # RULE #4 — jamais de prix d'achat/marge dans la donnée client.
        self.assertNotIn('prix_achat', _flatten_keys(data))

    def test_options_block_absent_without_options(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('D-XSAL5-B2')
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertNotIn('options_proposees', data)


def _flatten_keys(obj, out=None):
    out = out if out is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k))
            _flatten_keys(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _flatten_keys(v, out)
    return out


class TestPublicActivateEndpoint(TestCase):
    def setUp(self):
        self.company = make_company('test-xsal5-p-co')
        self.user = User.objects.create_user(
            username='xsal5puser', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = make_client_obj(self.company)
        self.api = APIClient()

    def _devis_with_option(self):
        devis = Devis.objects.create(
            company=self.company, reference='D-XSAL5-P1', client=self.client_obj,
            statut='envoye', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=_produit(
                self.company, 'Onduleur', 'D-XSAL5-P1-O', '1000'),
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        opt = LigneDevis.objects.create(
            devis=devis, produit=_produit(
                self.company, 'Option', 'D-XSAL5-P1-OPT', '400'),
            designation='Option', quantite=Decimal('1'),
            prix_unitaire=Decimal('400'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'), optionnelle=True)
        return devis, opt

    def test_client_activates_option_via_token(self):
        devis, opt = self._devis_with_option()
        link = ShareLink.for_devis(devis)
        resp = self.api.post(
            f'/api/django/ventes/proposal/{link.token}/activer-option/',
            {'ligne_id': opt.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        opt.refresh_from_db()
        self.assertFalse(opt.optionnelle)
        self.assertEqual(Decimal(Devis.objects.get(pk=devis.pk).total_ht),
                         Decimal('1400'))

    def test_bad_token_404(self):
        resp = self.api.post(
            '/api/django/ventes/proposal/nope-nope-nope/activer-option/',
            {'ligne_id': 1}, format='json')
        self.assertEqual(resp.status_code, 404)
