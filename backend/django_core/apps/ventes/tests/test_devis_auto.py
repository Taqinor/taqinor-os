"""Copilote — devis AUTOMATIQUE (résidentiel) + garde-fou « toujours auto ».

``build_devis_auto()`` dimensionne un devis résidentiel depuis la fiche lead
(facture d'hiver ou taille souhaitée) et délègue à ``build_devis_from_layout``.
L'agent n'a plus d'action de création VIDE : seule ``ventes.devis.creer_auto``
subsiste, avec les actions d'édition par chat.

Run:
    python manage.py test apps.ventes.tests.test_devis_auto -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import build_devis_auto, AutoDevisError

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def seed_catalogue(company):
    """Catalogue minimal (mêmes désignations que seed_catalogue)."""
    def mk(nom, sku, prix):
        Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
    mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', f'ONDH-{company.pk}', 17000)
    mk('Batterie Dyness 5 kWh', f'BAT-{company.pk}', 17000)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


AUTO_URL = '/api/django/ventes/devis/auto/'


class BuildDevisAutoServiceTest(TestCase):
    def setUp(self):
        self.company = make_company('auto-co')
        self.user = User.objects.create_user(
            username='autouser', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Auto', prenom='Lead',
            email='auto@ex.com', **extra)

    def test_sizes_from_facture_hiver(self):
        # 1800 / 900 = 2 tranches × 8 = 16 panneaux ; 16×710/1000 = 11.36 kWc.
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800')),
            user=self.user, company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 16)
        # U2 (fondateur 20/08/2026) — le lead ne dit rien de la batterie, donc
        # le devis propose LES DEUX options (et non plus le réseau seul).
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertEqual(devis.etude_params['scenario'],
                         'Les deux (Sans + Avec)')
        self.assertAlmostEqual(
            float(devis.etude_params['puissance_kwc']), 11.36, places=2)

    def test_sizes_from_taille_souhaitee(self):
        # U1 (fondateur 20/08/2026) — le compte de panneaux est un PLAFOND :
        # 6 kWc → ceil(6000 / 710) = 9 panneaux. Avec l'arrondi au plus proche
        # d'hier (8 panneaux = 5,68 kWc), le client payait 6 kWc et recevait
        # moins ; on ne descend JAMAIS sous la puissance vendue.
        devis = build_devis_auto(
            lead=self._lead(taille_souhaitee_kwc=Decimal('6')),
            user=self.user, company=self.company)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 9)

    def test_le_compte_de_panneaux_couvre_toujours_la_taille_demandee(self):
        """U1 — invariant du PLAFOND, sur tout le domaine résidentiel utile.

        Le cas signalé par le fondateur (5 kWc → 8 panneaux, jamais 7) n'est
        qu'un point ; la règle est que la puissance RÉELLEMENT posée n'est
        jamais inférieure à la taille demandée, et jamais gonflée d'un panneau
        entier de trop.
        """
        from apps.ventes.services import _residential_panel_count
        for kwc_x10 in range(10, 205, 5):           # 1,0 → 20,0 kWc
            kwc = Decimal(kwc_x10) / 10
            nb = _residential_panel_count(taille_kwc=kwc)
            pose = nb * 710 / 1000
            self.assertGreaterEqual(
                pose + 1e-9, float(kwc),
                '%s kWc : %d panneaux ne couvrent que %.3f kWc' % (
                    kwc, nb, pose))
            self.assertLess(
                (nb - 1) * 710 / 1000, float(kwc),
                '%s kWc : %d panneaux, un panneau de trop' % (kwc, nb))

    def test_le_plafond_est_stable_par_aller_retour(self):
        """U1 — miroir Python de la garde anti-dérive flottante de solar.js :
        un compte de panneaux repassé par son kWc doit se retrouver À
        L'IDENTIQUE, sans quoi chaque aller-retour ajouterait un panneau."""
        from apps.ventes.services import _residential_panel_count
        for nb in range(1, 61):
            kwc = Decimal(str(nb * 710 / 1000))
            self.assertEqual(
                _residential_panel_count(taille_kwc=kwc), nb,
                'aller-retour instable à %d panneaux' % nb)

    def test_battery_added_when_wanted(self):
        """U2 — un choix EXPLICITE « avec » reste souverain : on ne repropose
        pas au client l'option qu'il vient d'écarter."""
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800'),
                            batterie_souhaitee='avec'),
            user=self.user, company=self.company)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertFalse(any('réseau' in d for d in desigs))
        self.assertEqual(devis.etude_params['scenario'], 'Avec batterie')

    def test_choix_explicite_sans_reste_sans(self):
        """U2 — l'autre moitié du choix explicite : « sans » compose le réseau
        SEUL, sans batterie ni onduleur hybride."""
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800'),
                            batterie_souhaitee='sans'),
            user=self.user, company=self.company)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertFalse(any('hybride' in d for d in desigs))
        self.assertFalse(any('Batterie' in d for d in desigs))
        self.assertEqual(devis.etude_params['scenario'], 'Sans batterie')

    def test_defaut_deux_options_meme_sur_taille_souhaitee(self):
        """U2 — le défaut « les deux » ne dépend PAS du chemin de
        dimensionnement : une taille souhaitée en kWc le donne aussi."""
        devis = build_devis_auto(
            lead=self._lead(taille_souhaitee_kwc=Decimal('6')),
            user=self.user, company=self.company)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertEqual(devis.etude_params['scenario'],
                         'Les deux (Sans + Avec)')

    def test_deux_options_les_deux_paniers_sont_chiffrables(self):
        """U2 — la forme deux options n'a de sens que si CHAQUE panier tient
        debout tout seul : le panier « sans » (tout sauf batterie + hybride) et
        le panier « avec » (tout sauf réseau) doivent chacun porter des
        panneaux ET un onduleur. C'est le découpage exact que lisent l'écran
        (``optionTotalsTTC``) et le moteur PDF."""
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800')),
            user=self.user, company=self.company)
        lignes = list(devis.lignes.all())
        sans = [li for li in lignes
                if 'Batterie' not in li.designation
                and 'hybride' not in li.designation]
        avec = [li for li in lignes if 'réseau' not in li.designation]
        for nom, panier in (('sans', sans), ('avec', avec)):
            self.assertTrue(
                any('Panneau' in li.designation for li in panier),
                'panier « %s » sans panneaux' % nom)
            self.assertTrue(
                any('Onduleur' in li.designation for li in panier),
                'panier « %s » sans onduleur' % nom)
        self.assertTrue(any('Batterie' in li.designation for li in avec))
        self.assertFalse(any('Batterie' in li.designation for li in sans))

    def test_missing_data_raises(self):
        with self.assertRaises(AutoDevisError):
            build_devis_auto(lead=self._lead(), user=self.user,
                             company=self.company)

    def test_low_bill_raises(self):
        with self.assertRaises(AutoDevisError):
            build_devis_auto(lead=self._lead(facture_hiver=Decimal('500')),
                             user=self.user, company=self.company)

    def test_non_residential_raises(self):
        for marche in ('agricole', 'industriel', 'commercial'):
            with self.assertRaises(AutoDevisError):
                build_devis_auto(
                    lead=self._lead(facture_hiver=Decimal('1800'),
                                    type_installation=marche),
                    user=self.user, company=self.company)

    def test_blank_market_treated_residential(self):
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('900')),
            user=self.user, company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)


class AutoEndpointTest(TestCase):
    def setUp(self):
        self.company = make_company('autoep-co')
        self.user = User.objects.create_user(
            username='autoep', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        seed_catalogue(self.company)

    def test_creates_dimensioned_devis(self):
        lead = Lead.objects.create(
            company=self.company, nom='Ep', prenom='Lead',
            facture_hiver=Decimal('1800'))
        resp = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'brouillon')
        self.assertGreater(resp.data['nb_lignes'], 0)
        self.assertTrue(resp.data['reference'].startswith('DEV-'))

    def test_cross_tenant_lead_404(self):
        other = make_company('autoep-other')
        other_lead = Lead.objects.create(
            company=other, nom='Foreign', facture_hiver=Decimal('1800'))
        resp = self.api.post(AUTO_URL, {'lead': other_lead.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)

    def test_non_residential_422(self):
        lead = Lead.objects.create(
            company=self.company, nom='Agri', facture_hiver=Decimal('1800'),
            type_installation='agricole')
        resp = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertEqual(resp.data.get('field'), 'type_installation')

    def test_requires_auth(self):
        lead = Lead.objects.create(
            company=self.company, nom='NoAuth', facture_hiver=Decimal('1800'))
        resp = APIClient().post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertIn(resp.status_code, (401, 403))


class GuardrailTest(TestCase):
    """Le Copilote ne peut PLUS créer un devis vide : seules l'auto-création et
    l'édition par chat subsistent au catalogue."""

    def test_empty_create_actions_gone_auto_present(self):
        from apps.agent.registry import all_actions
        keys = {a.key for a in all_actions()}
        self.assertNotIn('ventes.devis.create', keys)
        self.assertNotIn('ventes.devis.creer', keys)
        self.assertIn('ventes.devis.creer_auto', keys)

    def test_edit_actions_present_with_expected_risk(self):
        from apps.ventes.agent_actions import (
            LIGNE_AJOUTER, LIGNE_MODIFIER, LIGNE_SUPPRIMER, REMISE_DEVIS,
        )
        from apps.agent.registry import RISK_INTERNAL, RISK_OUTWARD
        self.assertEqual(LIGNE_AJOUTER.risk, RISK_INTERNAL)
        self.assertEqual(LIGNE_MODIFIER.risk, RISK_INTERNAL)
        self.assertEqual(REMISE_DEVIS.risk, RISK_INTERNAL)
        # Suppression → confirmation (outward).
        self.assertEqual(LIGNE_SUPPRIMER.risk, RISK_OUTWARD)
        self.assertTrue(LIGNE_SUPPRIMER.confirm_summary)

    def test_creer_auto_inputs_have_no_company(self):
        from apps.ventes.agent_actions import CREER_AUTO
        self.assertNotIn('company', CREER_AUTO.inputs.get('properties', {}))
