"""
Tests for QJ16 — Reusable quote presets (DevisPreset model + services).

Covers:
  - save_devis_as_preset: creates a DevisPreset with correct company scoping
  - save_devis_as_preset: lines snapshot is correct (designation, qty, pu, remise, taux_tva)
  - save_devis_as_preset: etude_params are snapshotted when present
  - QJR546 — POST apply-preset is GONE (404, lines untouched): a preset is
    applied ON SCREEN by the generator, then persisted by replace-lines
  - DevisPreset.company always forced (never from request body in service layer)
  - Migration 0033 is additive: model can be created in a test with no errors

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qj16_presets -v 2
"""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, DevisPreset
from apps.ventes.services import save_devis_as_preset

User = get_user_model()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_company(slug='test-qj16'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Test QJ16'},
    )
    return company


def make_user(company):
    username = f'qj16_{company.slug}'
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return User.objects.create_user(
            username=username, password='x',
            role_legacy='responsable', company=company,
        )


def make_client(company):
    return Client.objects.create(
        company=company, nom='Rachidi', prenom='Omar',
        email=f'o_{company.slug}@example.com', telephone='+212622000000',
    )


def make_produit(company, nom, sku, prix_vente, prix_achat='1'):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_vente=Decimal(str(prix_vente)),
        prix_achat=Decimal(str(prix_achat)),
        quantite_stock=50,
    )


def make_devis(company, user, client, ref='DEV-QJ16-001', mode='residentiel',
               taux_tva='20.00', remise='0.00', etude_params=None):
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', taux_tva=Decimal(taux_tva),
        remise_globale=Decimal(remise),
        mode_installation=mode,
        created_by=user,
        etude_params=etude_params,
    )


def add_ligne(devis, produit, designation, quantite='1', pu='2000', remise='0', taux_tva=None):
    kwargs = dict(
        devis=devis, produit=produit,
        designation=designation,
        quantite=Decimal(str(quantite)),
        prix_unitaire=Decimal(str(pu)),
        remise=Decimal(str(remise)),
    )
    if taux_tva is not None:
        kwargs['taux_tva'] = Decimal(str(taux_tva))
    return LigneDevis.objects.create(**kwargs)


# ─── Model creation ───────────────────────────────────────────────────────────

class TestDevisPresetModel(TestCase):
    """Basic model creation + company scoping."""

    def setUp(self):
        self.company = make_company('qj16-mdl')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_create_preset_directly(self):
        snapshot = [{'designation': 'Panneau 550W', 'quantite': '6',
                     'prix_unitaire': '2000', 'remise': '0',
                     'produit_id': None, 'taux_tva': None}]
        preset = DevisPreset.objects.create(
            company=self.company,
            nom='Modèle test',
            lignes_snapshot=snapshot,
        )
        self.assertIsNotNone(preset.pk)
        self.assertEqual(preset.nom, 'Modèle test')
        self.assertEqual(preset.company, self.company)

    def test_preset_str_includes_nom(self):
        preset = DevisPreset.objects.create(
            company=self.company,
            nom='Standard 6 kWc',
            lignes_snapshot=[],
        )
        self.assertIn('Standard 6 kWc', str(preset))

    def test_preset_ordering_by_nom(self):
        DevisPreset.objects.create(
            company=self.company, nom='Zéro', lignes_snapshot=[])
        DevisPreset.objects.create(
            company=self.company, nom='Alpha', lignes_snapshot=[])
        names = list(
            DevisPreset.objects.filter(company=self.company).values_list('nom', flat=True))
        self.assertEqual(names, sorted(names))


# ─── save_devis_as_preset ─────────────────────────────────────────────────────

class TestSaveDevisAsPreset(TestCase):

    def setUp(self):
        self.company = make_company('qj16-save')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_creates_preset_with_correct_company(self):
        devis = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ16-S1')
        p1 = make_produit(self.company, 'Panneau 550W', 'PANEL-550', '2000')
        add_ligne(devis, p1, 'Panneau mono 550W', quantite='8', pu='2000')

        preset = save_devis_as_preset(devis, 'Mon modèle 8 panneaux', user=self.user)

        self.assertIsNotNone(preset.pk)
        self.assertEqual(preset.company, self.company)
        self.assertEqual(preset.nom, 'Mon modèle 8 panneaux')

    def test_snapshot_captures_lines_correctly(self):
        devis = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ16-S2')
        p1 = make_produit(self.company, 'Panneau 550W', 'PANEL-550B', '1500')
        p2 = make_produit(self.company, 'Onduleur réseau 6kW', 'INV-6K', '12000')
        add_ligne(devis, p1, 'Panneau mono 550W', quantite='10', pu='1500', remise='5')
        add_ligne(devis, p2, 'Onduleur réseau 6kW', quantite='1', pu='12000')

        preset = save_devis_as_preset(devis, 'Test snapshot')

        snapshot = preset.lignes_snapshot
        self.assertEqual(len(snapshot), 2)
        panneau = next(s for s in snapshot if 'Panneau' in s['designation'])
        self.assertEqual(panneau['quantite'], '10')
        self.assertEqual(panneau['prix_unitaire'], '1500')
        self.assertEqual(panneau['remise'], '5')

    def test_snapshot_per_line_taux_tva_captured(self):
        devis = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ16-S3')
        p1 = make_produit(self.company, 'Panneau 710W', 'PANEL-710C', '1400')
        add_ligne(devis, p1, 'Panneau 710W', taux_tva='10')

        preset = save_devis_as_preset(devis, 'Test taux_tva')
        snap = preset.lignes_snapshot[0]
        self.assertEqual(snap['taux_tva'], '10')

    def test_etude_params_snapshotted_when_present(self):
        etude = {'production_annuelle': 8000, 'economies_annuelles': 9600}
        devis = make_devis(
            self.company, self.user, self.client_obj, 'DEV-QJ16-S4',
            etude_params=etude)
        p1 = make_produit(self.company, 'Panneau 550W', 'PANEL-550D', '2000')
        add_ligne(devis, p1, 'Panneau 550W')

        preset = save_devis_as_preset(devis, 'Avec étude')
        self.assertEqual(preset.etude_params_snapshot['production_annuelle'], 8000)

    def test_no_company_raises(self):
        devis = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ16-S5')
        devis.company = None
        p1 = make_produit(self.company, 'Panneau 550W', 'PANEL-550E', '2000')
        add_ligne(devis, p1, 'Panneau 550W')
        with self.assertRaises(ValueError):
            save_devis_as_preset(devis, 'No company')

    def test_company_forced_from_devis_not_user(self):
        """Company always comes from devis, never user-supplied."""
        company2 = make_company('qj16-co2')
        devis = make_devis(self.company, self.user, self.client_obj, 'DEV-QJ16-S6')
        p1 = make_produit(self.company, 'Panneau 550W', 'PANEL-550F', '2000')
        add_ligne(devis, p1, 'Panneau 550W')

        preset = save_devis_as_preset(devis, 'Company forced', user=self.user)
        # Preset company is devis.company, not company2
        self.assertEqual(preset.company, self.company)
        self.assertNotEqual(preset.company, company2)


# ─── QJR546 — apply-preset supprimé ─────────────────────────────────────────

class TestApplyPresetSupprime(TestCase):
    """QJR546 — l'ancien POST apply-preset AJOUTAIT des lignes en base, sans
    garde de statut, et l'écran n'en recevait aucune : il est supprimé. Un
    modèle s'applique à l'ÉCRAN, persisté par replace-lines."""

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        self.company = make_company('qj16-apply')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_route_apply_preset_supprimee(self):
        p1 = make_produit(self.company, 'Panneau 550W', 'PANEL-550G', '2000')
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ16-A01')
        add_ligne(devis, p1, 'Panneau 550W', quantite='2', pu='2000')
        preset = DevisPreset.objects.create(
            company=self.company, nom='Preset', mode_installation='residentiel',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0.00'),
            lignes_snapshot=[{'produit_id': p1.pk, 'designation': 'X',
                              'quantite': '9', 'prix_unitaire': '2000',
                              'remise': '0', 'taux_tva': '20'}])
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/apply-preset/',
            {'preset_id': preset.id}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(devis.lignes.count(), 1)

    def test_service_supprime(self):
        from apps.ventes import services
        self.assertFalse(hasattr(services, 'apply_preset_to_devis'))


# ─── Company isolation ────────────────────────────────────────────────────────

class TestPresetCompanyIsolation(TestCase):
    """Presets from one company must not be visible or applicable to another."""

    def setUp(self):
        self.co1 = make_company('qj16-iso1')
        self.co2 = make_company('qj16-iso2')
        self.u1 = make_user(self.co1)
        self.u2 = make_user(self.co2)
        self.c1 = make_client(self.co1)
        self.c2 = make_client(self.co2)

    def test_presets_are_company_scoped(self):
        d1 = make_devis(self.co1, self.u1, self.c1, 'DEV-ISO-1')
        p1 = make_produit(self.co1, 'Panneau', 'PANEL-ISO1', '2000')
        add_ligne(d1, p1, 'Panneau', pu='2000')
        save_devis_as_preset(d1, 'Preset co1', user=self.u1)

        d2 = make_devis(self.co2, self.u2, self.c2, 'DEV-ISO-2')
        p2 = make_produit(self.co2, 'Panneau', 'PANEL-ISO2', '2000')
        add_ligne(d2, p2, 'Panneau', pu='2000')
        save_devis_as_preset(d2, 'Preset co2', user=self.u2)

        co1_presets = DevisPreset.objects.filter(company=self.co1)
        co2_presets = DevisPreset.objects.filter(company=self.co2)

        # Each company sees only its own preset
        self.assertEqual(co1_presets.count(), 1)
        self.assertEqual(co2_presets.count(), 1)
        self.assertFalse(co1_presets.filter(company=self.co2).exists())
        self.assertFalse(co2_presets.filter(company=self.co1).exists())
