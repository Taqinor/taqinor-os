"""L-NIV — deux niveaux d'affichage RÉVOCABLES pour le lien public de
proposition (ShareLink.niveau : 'standard' | 'confiance').

Founder-designed feature (24/08/2026): protects engineering know-how on the
publicly shared quote page while keeping every money figure identical.
Covered here:
  (a) model/migration — default 'standard' for freshly-created links.
  (b) share-link action — accepts/returns niveau + otp_lecture, never
      regenerates the token when changing the level.
  (c) proposal_data payload — 'confiance' stays byte-identical to
      pre-L-NIV behaviour (roof_layout present, full sld_svg, full
      conception_electrique); 'standard' degrades exactly the three
      surfaces this chantier owns (sld_svg without
      the nomenclature table, conception_electrique without
      calibre/cables) while brand/model strings and every money figure
      stay identical between the two levels.
      NOTE L-SECT (fondateur 24/08/2026) — roof_layout n'est PLUS dégradé au
      niveau standard : le calepinage 3D est servi AUX DEUX NIVEAUX par défaut
      (« le client ne voit pas ses panneaux sur son toit »), et ne se retire
      que par la case explicite ``sections['roof3d'] = False``
      (voir test_l_sect_sections.py).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_l_niv_niveau -v 2
"""
import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()


def make_company(slug):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'lniv_{company.slug}_{role}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='LNIV', prenom='Test',
        email=f'lniv_{company.slug}@ex.com', telephone='+212600000010')


def make_devis(company, user, client, reference, roof_layout=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='envoye', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, roof_layout=roof_layout)
    # Vocabulaire du classifieur d'options (builder.py : réseau/hybride) — un
    # « Onduleur » nu ne tombe dans AUCUNE option → refus sécurité → 404.
    for desig, qty, pu in [('Onduleur réseau Deye 8kW', '1', '14000'),
                           ('Panneau Canadian Solar 550W', '10', '1400')]:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{reference[-6:]}-{desig[:8]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('9999'),
            quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


def add_kit_lines(devis):
    """Lignes fixation/câblage/protection — celles que le niveau standard
    doit AGRÉGER en une seule ligne « Kit de fixation, câblage et protection
    complet », au sous-total EXACT."""
    for desig, qty, pu in [
        ('Rail de fixation aluminium', '20', '35'),
        ('Câble DC 6mm² rouge/noir', '30', '4.5'),
        ('Disjoncteur AC 20A tétrapolaire', '1', '180'),
    ]:
        produit = Produit.objects.create(
            company=devis.company, nom=desig,
            sku=f'{devis.reference[-6:]}-K-{desig[:6]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('1'),
            quantite_stock=99)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


def sample_layout():
    return {
        'version': 1, 'scenario': 'reseau',
        'result': {'panels': 16, 'kwc': 8.8, 'annualKwh': 14000},
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud',
            'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
            'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 30,
            'facingAzimuthDeg': 0, 'neededPanels': 12,
        }],
        '_pans_geometry': [{
            'label': 'Pan Sud', 'orientation': 'Sud', 'azimut_deg': 0,
            'inclinaison_deg': 30, 'nb_panneaux': 12, 'kwc': 6.6,
            'roof_type': 'pitched',
        }],
    }


# ═══════════════════════════════════════════════════════════════════════════
# (a) Model / migration default
# ═══════════════════════════════════════════════════════════════════════════

class TestNiveauDefault(TestCase):
    def test_freshly_created_link_defaults_to_standard(self):
        company = make_company('lniv-mdl')
        user = make_user(company)
        client_obj = make_client(company)
        devis = make_devis(company, user, client_obj, 'DEV-LNIV-MDL1')
        link = ShareLink.objects.create(company=company, devis=devis)
        self.assertEqual(link.niveau, ShareLink.NIVEAU_STANDARD)
        self.assertFalse(link.otp_lecture)


# ═══════════════════════════════════════════════════════════════════════════
# (b) share-link action
# ═══════════════════════════════════════════════════════════════════════════

class TestShareLinkActionNiveau(TestCase):
    def setUp(self):
        self.company = make_company('lniv-act')
        self.user = make_user(self.company, role='admin')
        self.client_obj = make_client(self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _devis(self, ref):
        return make_devis(self.company, self.user, self.client_obj, ref)

    def test_share_link_default_is_standard_and_returned(self):
        devis = self._devis('DEV-LNIV-A1')
        resp = self.api.post(f'/api/django/ventes/devis/{devis.id}/share-link/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['niveau'], 'standard')
        self.assertFalse(resp.data['otp_lecture'])

    def test_share_link_switches_level_without_regenerating_token(self):
        devis = self._devis('DEV-LNIV-A2')
        first = self.api.post(f'/api/django/ventes/devis/{devis.id}/share-link/')
        token = first.data['token']
        second = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/share-link/',
            {'niveau': 'confiance', 'otp_lecture': True}, format='json')
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['token'], token)  # SAME token — revocable
        self.assertEqual(second.data['niveau'], 'confiance')
        self.assertTrue(second.data['otp_lecture'])
        link = ShareLink.objects.get(token=token)
        self.assertEqual(link.niveau, 'confiance')
        self.assertTrue(link.otp_lecture)

    def test_share_link_revoke_back_to_standard_same_token(self):
        devis = self._devis('DEV-LNIV-A3')
        first = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/share-link/',
            {'niveau': 'confiance'}, format='json')
        token = first.data['token']
        second = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/share-link/',
            {'niveau': 'standard'}, format='json')
        self.assertEqual(second.data['token'], token)
        self.assertEqual(second.data['niveau'], 'standard')

    def test_share_link_rejects_invalid_niveau(self):
        devis = self._devis('DEV-LNIV-A4')
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/share-link/',
            {'niveau': 'bogus'}, format='json')
        self.assertEqual(resp.status_code, 400)


# ═══════════════════════════════════════════════════════════════════════════
# (c) proposal_data payload — confiance pinned, standard degraded
# ═══════════════════════════════════════════════════════════════════════════

class TestProposalDataNiveau(TestCase):
    def setUp(self):
        self.company = make_company('lniv-pub')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _payload(self, devis, niveau):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=devis, token=token, niveau=niveau)
        resp = DjangoClient().get(f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_confiance_payload_matches_niveau_key(self):
        devis = self._devis_no_layout()
        payload = self._payload(devis, ShareLink.NIVEAU_CONFIANCE)
        self.assertEqual(payload['niveau'], 'confiance')

    def test_confiance_roof_layout_present_when_devis_has_one(self):
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-LNIV-C1', roof_layout=sample_layout())
        payload = self._payload(devis, ShareLink.NIVEAU_CONFIANCE)
        self.assertIsNotNone(payload['roof_layout'])

    def test_standard_sert_aussi_le_calepinage_3d(self):
        """DÉCISION FONDATEUR 24/08/2026 (L-SECT) — RENVERSE le comportement
        L-NIV d'origine (« standard omet roof_layout »).

        Constat du fondateur : « le client ne voit pas ses panneaux sur son
        toit ». Le calepinage 3D est un VISUEL de vente, pas du savoir-faire
        d'ingénierie : il est désormais servi AUX DEUX NIVEAUX par défaut. Seule
        une décision explicite du commercial (case « Calepinage 3D » décochée →
        ``sections['roof3d'] = False``) le retire — voir
        ``test_l_sect_sections.py``. Ce qui reste dégradé au niveau standard est
        inchangé : sld_svg sans nomenclature, conception_electrique sans
        calibres/câbles, kit agrégé (tests ci-dessous)."""
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-LNIV-S1', roof_layout=sample_layout())
        payload = self._payload(devis, ShareLink.NIVEAU_STANDARD)
        self.assertIsNotNone(payload['roof_layout'])

    def test_brand_names_stay_visible_in_both_levels(self):
        """Founder rule: brands/models exact stay VISIBLE in BOTH levels."""
        devis = self._devis_no_layout()
        confiance = self._payload(devis, ShareLink.NIVEAU_CONFIANCE)
        standard = self._payload(devis, ShareLink.NIVEAU_STANDARD)
        for payload in (confiance, standard):
            blob = json.dumps(payload)
            self.assertIn('Deye', blob)
            self.assertIn('Canadian Solar', blob)

    def test_money_totals_identical_across_levels(self):
        """Founder rule: money figures IDENTICAL in both levels, always."""
        devis = self._devis_no_layout()
        confiance = self._payload(devis, ShareLink.NIVEAU_CONFIANCE)
        standard = self._payload(devis, ShareLink.NIVEAU_STANDARD)
        # Clés réelles du payload public : total_sans/total_avec (TTC) +
        # display_total — pas de total_ht/total_ttc à ce niveau.
        for key in ('total_sans', 'total_avec', 'display_total'):
            self.assertEqual(confiance['quote'][key], standard['quote'][key])

    def _devis_no_layout(self, ref='DEV-LNIV-NOLAY'):
        return make_devis(self.company, self.user, self.client_obj, ref)


# ═══════════════════════════════════════════════════════════════════════════
# (d) chantier 3 — agrégation des lignes kit (fixation/câblage/protection)
# ═══════════════════════════════════════════════════════════════════════════

class TestKitLineAggregation(TestCase):
    def setUp(self):
        self.company = make_company('lniv-kit')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _payload(self, devis, niveau):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=devis, token=token, niveau=niveau)
        resp = DjangoClient().get(f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def _kit_designations(self):
        return {'Rail de fixation aluminium',
                'Câble DC 6mm² rouge/noir',
                'Disjoncteur AC 20A tétrapolaire'}

    def _items(self, payload):
        return (payload['quote'].get('sans_items')
                or payload['quote'].get('avec_items') or [])

    def test_standard_aggregates_kit_lines_into_one(self):
        devis = add_kit_lines(make_devis(
            self.company, self.user, self.client_obj, 'DEV-LNIV-KIT1'))
        payload = self._payload(devis, ShareLink.NIVEAU_STANDARD)
        items = self._items(payload)
        designations = {it['designation'] for it in items}
        self.assertIn('Kit de fixation, câblage et protection complet',
                      designations)
        self.assertFalse(designations & self._kit_designations(),
                         "les lignes kit individuelles ne doivent plus "
                         "apparaître au niveau standard")

    def test_confiance_keeps_kit_lines_separate(self):
        devis = add_kit_lines(make_devis(
            self.company, self.user, self.client_obj, 'DEV-LNIV-KIT2'))
        payload = self._payload(devis, ShareLink.NIVEAU_CONFIANCE)
        designations = {it['designation'] for it in self._items(payload)}
        self.assertTrue(self._kit_designations() <= designations)
        self.assertNotIn('Kit de fixation, câblage et protection complet',
                         designations)

    def test_aggregated_line_subtotal_equals_exact_sum(self):
        devis = add_kit_lines(make_devis(
            self.company, self.user, self.client_obj, 'DEV-LNIV-KIT3'))
        confiance = self._payload(devis, ShareLink.NIVEAU_CONFIANCE)
        standard = self._payload(devis, ShareLink.NIVEAU_STANDARD)
        kit_names = self._kit_designations()
        somme_ht_attendue = sum(
            it['quantite'] * it['prix_unit_ht']
            for it in self._items(confiance) if it['designation'] in kit_names)
        agregee = next(
            it for it in self._items(standard)
            if it['designation'] == 'Kit de fixation, câblage et protection complet')
        self.assertAlmostEqual(
            agregee['quantite'] * agregee['prix_unit_ht'],
            somme_ht_attendue, places=2)

    def test_overall_total_unaffected_by_aggregation(self):
        devis = add_kit_lines(make_devis(
            self.company, self.user, self.client_obj, 'DEV-LNIV-KIT4'))
        confiance = self._payload(devis, ShareLink.NIVEAU_CONFIANCE)
        standard = self._payload(devis, ShareLink.NIVEAU_STANDARD)
        for key in ('total_sans', 'total_avec', 'display_total'):
            self.assertEqual(confiance['quote'][key], standard['quote'][key])
