# -*- coding: utf-8 -*-
"""QJR-OFFGRID (incident fondateur 01/09/2026) — L'ONDULEUR HORS RÉSEAU.

CE QUI S'EST PASSÉ. Le fondateur ajoute au catalogue un onduleur AUTONOME
(site isolé). Le moteur de devis ne connaissait que DEUX familles d'onduleur —
réseau et hybride — et le piège est FRANÇAIS : « hors réseau » CONTIENT
« réseau ». Deux défauts, selon le nom donné au produit :

* « Onduleur hors réseau 5kW » était classé RÉSEAU. Le devis servait alors une
  option « Sans batterie » FANTÔME, que le système ne peut pas livrer ;
* « Onduleur Off-Grid 5kW » n'était classé NULLE PART. Aucune option n'était
  servable : le PDF à options était REFUSÉ (« aucune option ne contient
  d'onduleur ») et le compte de panneaux disparaissait de la page client.

Ce module verrouille les trois moitiés de la correction :
  1. la table de classification unique (``solar_design``) + la catégorie
     catalogue (``domain.catalogue.classer_produit``) ;
  2. le découpage en options du moteur PDF (``quote_engine.builder``) ;
  3. la composition hors réseau (onduleur autonome + batterie OBLIGATOIRE),
     et son REFUS français quand le catalogue ne sait pas la servir.

Le fil rouge est la règle fondateur des chiffres vérifiés : aucun onduleur
hybride n'est JAMAIS substitué à un autonome — on refuse plutôt que de coter
un composant que ce client ne peut pas exploiter.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_offgrid_hors_reseau -v 2
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.stock.models import Produit
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. LA TABLE DE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════
class TestClassificationHorsReseau(SimpleTestCase):
    """``solar_design`` — la SEULE table backend (QJR78)."""

    def test_offgrid_reconnu_dans_ses_trois_orthographes(self):
        from apps.ventes import solar_design as sd
        for nom in ('Onduleur Off-Grid 5kW',
                    'Onduleur off grid 5kW',
                    'Onduleur OFFGRID 5kW',
                    'Onduleur autonome 5kW'):
            self.assertTrue(sd.is_offgrid_inverter(nom), nom)
            self.assertFalse(sd.is_reseau_inverter(nom), nom)
            self.assertFalse(sd.is_hybrid_inverter(nom), nom)
            self.assertTrue(sd.is_any_inverter(nom), nom)

    def test_hors_reseau_francais_nest_plus_un_onduleur_reseau(self):
        """LE défaut de l'incident : « hors réseau » contient « réseau »."""
        from apps.ventes import solar_design as sd
        for nom in ('Onduleur hors réseau 3kW', 'Onduleur hors reseau 3kW'):
            self.assertTrue(sd.is_offgrid_inverter(nom), nom)
            self.assertFalse(sd.is_reseau_inverter(nom), nom)

    def test_hybride_lemporte_sur_offgrid(self):
        """PRÉCÉDENCE : un hybride sait faire les deux — il reste HYBRIDE, donc
        il garde le panier « avec » que sa règle lui garantit déjà."""
        from apps.ventes import solar_design as sd
        nom = 'Onduleur Hybride Off-Grid 8kW'
        self.assertTrue(sd.is_hybrid_inverter(nom))
        self.assertFalse(sd.is_offgrid_inverter(nom))
        self.assertFalse(sd.is_reseau_inverter(nom))

    def test_les_deux_familles_historiques_sont_intactes(self):
        """LA BARRE DE NON-RÉGRESSION : rien ne bouge sans mot-clé autonome."""
        from apps.ventes import solar_design as sd
        for nom in ('Onduleur réseau Huawei 5kW Monophasé',
                    'Onduleur reseau 8kW', 'Onduleur injection 10kW'):
            self.assertTrue(sd.is_reseau_inverter(nom), nom)
            self.assertFalse(sd.is_offgrid_inverter(nom), nom)
        for nom in ('Onduleur hybride Deye 5kW Monophasé',
                    'Onduleur Hybride 8kW'):
            self.assertTrue(sd.is_hybrid_inverter(nom), nom)
            self.assertFalse(sd.is_offgrid_inverter(nom), nom)
        for nom in ('Batterie Dyness 5 kWh', 'Panneau Jinko 550W'):
            self.assertFalse(sd.is_any_inverter(nom), nom)

    def test_raccordement_aucun_est_inerte_pour_le_filtre_de_phase(self):
        """Le lead d'un site isolé déclare ``raccordement='aucun'`` (crm). Pour
        la COMPOSITION, cette valeur ne restreint AUCUN vivier d'onduleurs —
        exactement comme « inconnu » ; seul le prédicat de site isolé la
        distingue, et c'est lui qui déclenche le mode hors réseau."""
        from apps.ventes.compatibilites import est_site_isole, normaliser_phase
        self.assertIsNone(normaliser_phase('aucun'))
        self.assertIsNone(normaliser_phase('inconnu'))
        self.assertTrue(est_site_isole('aucun'))
        self.assertFalse(est_site_isole('inconnu'))
        self.assertFalse(est_site_isole('monophase'))
        self.assertFalse(est_site_isole(None))

    def test_categorie_catalogue_de_composition(self):
        """``classer_produit`` est l'autre lecteur : même rang, même piège."""
        from apps.ventes.domain.catalogue import classer_produit
        self.assertEqual(classer_produit('Onduleur Off-Grid 5kW'),
                         'onduleur_offgrid')
        self.assertEqual(classer_produit('Onduleur hors réseau 5kW'),
                         'onduleur_offgrid')
        self.assertEqual(classer_produit('Onduleur hybride Deye 5kW'),
                         'onduleur_hybride')
        self.assertEqual(classer_produit('Onduleur réseau Huawei 5kW'),
                         'onduleur_reseau')


# ═══════════════════════════════════════════════════════════════════════════
# 2. LE DÉCOUPAGE EN OPTIONS DU MOTEUR PDF
# ═══════════════════════════════════════════════════════════════════════════
class TestBuilderOptionHorsReseau(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_devis_site_isole_sert_lunique_option_avec(self):
        """(a) autonome + batterie + panneaux : ``avec_ok``, une seule variante
        servable, et le PDF à options n'est PAS refusé."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Jinko 550W', '10', '1100'),
            ('Onduleur Off-Grid 5kW', '1', '15000'),
            ('Batterie Dyness 5 kWh', '2', '16000'),
        ], reference='DEV-OFFG-0001')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertTrue(data['avec_ok'])
        self.assertFalse(data['sans_ok'])
        self.assertEqual(data['variantes_servables'], ['avec'])
        self.assertEqual(data['scenario'], 'Avec batterie')
        # L'onduleur autonome est DANS l'option « avec » et JAMAIS dans
        # « sans » (l'option fantôme de l'incident).
        avec = [it['designation'] for it in data['avec_items']]
        sans = [it['designation'] for it in data['sans_items']]
        self.assertIn('Onduleur Off-Grid 5kW', avec)
        self.assertNotIn('Onduleur Off-Grid 5kW', sans)
        # Les panneaux, eux, restent dans les DEUX paniers (invariant).
        self.assertIn('Panneau Jinko 550W', avec)
        self.assertIn('Panneau Jinko 550W', sans)
        # Le compte de panneaux ne disparaît plus.
        self.assertEqual(data['nb_panneaux'], 10)

    def test_meme_devis_nomme_en_francais(self):
        """« hors réseau » : le devis qui servait une option fantôme sert
        désormais la seule option qu'il peut livrer."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Jinko 550W', '8', '1100'),
            ('Onduleur hors réseau 3kW', '1', '12000'),
            ('Batterie Dyness 5 kWh', '1', '16000'),
        ], reference='DEV-OFFG-0002')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertTrue(data['avec_ok'])
        self.assertFalse(data['sans_ok'])
        self.assertEqual(data['variantes_servables'], ['avec'])

    def test_autonome_sans_batterie_reste_rendu_en_option_unique(self):
        """Z1 étendu — un devis autonome SANS batterie ne se voit pas refuser
        le document au motif qu'il n'aurait « aucun onduleur » : il en a un.
        Aucune batterie n'est fabriquée pour autant."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Jinko 550W', '8', '1100'),
            ('Onduleur Off-Grid 5kW', '1', '15000'),
        ], reference='DEV-OFFG-0003')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertTrue(data['sans_ok'])
        self.assertFalse(data['avec_ok'])
        for panier in ('sans_items', 'avec_items'):
            self.assertFalse(
                any('batterie' in it['designation'].lower()
                    for it in data[panier]),
                'une batterie fabriquée a survécu dans %s' % panier)

    def test_regression_devis_reseau_seul_inchange(self):
        """LA BARRE : un devis réseau se comporte exactement comme avant."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Jinko 550W', '8', '1100'),
            ('Onduleur réseau Huawei 5kW Monophasé', '1', '14000'),
        ], reference='DEV-OFFG-0004')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertTrue(data['sans_ok'])
        self.assertFalse(data['avec_ok'])
        self.assertEqual(data['variantes_servables'], ['sans'])
        self.assertEqual(data['scenario'], 'Sans batterie')

    def test_regression_devis_deux_options_inchange(self):
        """LA BARRE : le document à deux options déclaré reste à deux options,
        et l'onduleur réseau reste hors du panier « avec »."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Jinko 550W', '14', '1100'),
            ('Onduleur réseau Huawei 5kW Monophasé', '1', '14000'),
            ('Onduleur hybride Deye 5kW Monophasé', '1', '17000'),
            ('Batterie Dyness 5 kWh', '1', '16000'),
        ], reference='DEV-OFFG-0005', etude_params=DEUX_OPTIONS)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertTrue(data['sans_ok'])
        self.assertTrue(data['avec_ok'])
        self.assertEqual(data['variantes_servables'], ['sans', 'avec'])
        sans = [it['designation'] for it in data['sans_items']]
        avec = [it['designation'] for it in data['avec_items']]
        self.assertIn('Onduleur réseau Huawei 5kW Monophasé', sans)
        self.assertNotIn('Onduleur réseau Huawei 5kW Monophasé', avec)
        self.assertIn('Onduleur hybride Deye 5kW Monophasé', avec)
        self.assertNotIn('Onduleur hybride Deye 5kW Monophasé', sans)


# ═══════════════════════════════════════════════════════════════════════════
# 3. LA COMPOSITION HORS RÉSEAU
# ═══════════════════════════════════════════════════════════════════════════
#: Catalogue MINIMAL du site isolé : l'autonome, ses concurrents raccordés
#: (pour prouver qu'aucun n'est substitué), une batterie et un panneau.
CATALOGUE_ISOLE = [
    ('Panneau Jinko 550W', 'OFFG-PAN550', '1100'),
    ('Onduleur Off-Grid 5kW', 'OFFG-ONDA5', '15000'),
    ('Onduleur réseau Huawei 5kW Monophasé', 'OFFG-ONDR5', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', 'OFFG-ONDH5', '17000'),
    ('Batterie Dyness 5 kWh', 'OFFG-BAT5', '16000'),
    ('Structures acier', 'OFFG-STR', '500'),
]


class TestCompositionHorsReseau(TestCase):
    def setUp(self):
        self.company = make_company()

    def _seed(self, catalogue):
        for nom, sku, prix in catalogue:
            Produit.objects.create(
                company=self.company, nom=nom,
                sku='%s-%s' % (sku, self.company.pk),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)

    def test_dry_run_compose_lautonome_et_sa_batterie(self):
        from apps.ventes.services import composer_devis_residentiel
        self._seed(CATALOGUE_ISOLE)
        resultat = composer_devis_residentiel(
            company=self.company, kwc=5, panel_watt=550, hors_reseau=True)
        roles = [ligne['role'] for ligne in resultat['lignes']]
        designations = [ligne['designation'] for ligne in resultat['lignes']]
        self.assertIn('onduleur_offgrid', roles)
        self.assertIn('batterie', roles)
        self.assertIn('Onduleur Off-Grid 5kW', designations)
        # AUCUNE substitution : ni réseau, ni hybride, alors qu'ils sont au
        # catalogue et tarifés (règle fondateur des chiffres vérifiés).
        self.assertNotIn('onduleur_reseau', roles)
        self.assertNotIn('onduleur_hybride', roles)

    def test_dry_run_raccorde_reste_inchange(self):
        """LA BARRE : sans le drapeau, le dry-run compose ce qu'il composait."""
        from apps.ventes.services import composer_devis_residentiel
        self._seed(CATALOGUE_ISOLE)
        resultat = composer_devis_residentiel(
            company=self.company, kwc=5, panel_watt=550)
        roles = [ligne['role'] for ligne in resultat['lignes']]
        self.assertIn('onduleur_reseau', roles)
        self.assertIn('onduleur_hybride', roles)
        self.assertNotIn('onduleur_offgrid', roles)

    def test_sans_onduleur_autonome_tarife_le_dry_run_refuse_en_francais(self):
        """Le catalogue ne sert PAS le site isolé : refus FRANÇAIS qui NOMME la
        référence manquante — jamais un hybride substitué en silence."""
        from apps.ventes.domain.taille import AutoDevisError
        from apps.ventes.services import composer_devis_residentiel
        self._seed([c for c in CATALOGUE_ISOLE
                    if c[1] != 'OFFG-ONDA5'])
        with self.assertRaises(AutoDevisError) as capture:
            composer_devis_residentiel(
                company=self.company, kwc=5, panel_watt=550, hors_reseau=True)
        message = str(capture.exception)
        self.assertIn('hors réseau', message)
        self.assertIn('catalogue', message)

    def test_onduleur_autonome_sans_prix_nest_jamais_cote(self):
        """La garde « jamais un produit sans prix » vaut aussi ici : un
        autonome à 0 MAD ne sauve pas la composition, elle refuse."""
        from apps.ventes.domain.taille import AutoDevisError
        from apps.ventes.services import composer_devis_residentiel
        self._seed([c for c in CATALOGUE_ISOLE if c[1] != 'OFFG-ONDA5'])
        Produit.objects.create(
            company=self.company, nom='Onduleur Off-Grid 5kW',
            sku='OFFG-ONDA5-NOPRIX-%s' % self.company.pk,
            prix_vente=Decimal('0'), prix_achat=Decimal('0'),
            quantite_stock=100)
        with self.assertRaises(AutoDevisError):
            composer_devis_residentiel(
                company=self.company, kwc=5, panel_watt=550, hors_reseau=True)

    def test_sans_batterie_tarifee_le_dry_run_refuse_aussi(self):
        """Un site isolé SANS stockage n'a pas d'électricité la nuit : la
        batterie n'est pas une option ici, c'est une exigence."""
        from apps.ventes.domain.taille import AutoDevisError
        from apps.ventes.services import composer_devis_residentiel
        self._seed([c for c in CATALOGUE_ISOLE if c[1] != 'OFFG-BAT5'])
        with self.assertRaises(AutoDevisError):
            composer_devis_residentiel(
                company=self.company, kwc=5, panel_watt=550, hors_reseau=True)
