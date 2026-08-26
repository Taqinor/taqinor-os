# -*- coding: utf-8 -*-
"""BATHOMO (fondateur 26/08/2026) — une banque de batteries est TOUJOURS
HOMOGÈNE : N modules du MÊME calibre, jamais un mélange de calibres.

CONTEXTE. Le simulateur composait la cible de stockage en modules Dyness
10 kWh + un 5 kWh d'appoint (``services.composition_residentielle``,
``nb10 = cible // 10`` + ``nb5 = 1`` si le reste ≥ 5) : une cible de 15 kWh
sortait 1×10 + 1×5 EN PARALLÈLE, un mélange électriquement interdit (des
modules de calibres différents ne s'équilibrent pas en banque). C'est ce
mélange, composé côté serveur, qui a fait retirer le Dyness 10 kWh
(``BAT-DEY-10``) du stock de production le 26/08/2026.

CE QUE CES TESTS VERROUILLENT :
1. Catalogue avec LES DEUX calibres (5 ET 10 kWh) : pour toute cible balayée,
   ``composition_residentielle`` ne compose JAMAIS les deux à la fois — au
   plus un des deux compteurs (``nb_batteries_5``/``nb_batteries_10``, lus
   par ``dimensionnement._compter_modules_batterie`` sur la composition
   réelle) est non nul.
2. Catalogue avec SEULEMENT le calibre 5 kWh (l'état RÉEL du stock du
   fondateur après le retrait du 10 kWh) : la composition continue de
   fonctionner, en multiples de 5, sans jamais essayer le 10 kWh absent.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_bathomo_banque_homogene -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.ventes import services
from apps.ventes.dimensionnement import _compter_modules_batterie, _lire_composition
from authentication.models import Company

User = get_user_model()


class _Base(TestCase):
    """Un catalogue minimal mais électriquement cohérent : panneau, onduleur
    réseau, onduleur hybride (plage batterie 40-60 V déclarée — SANS elle le
    garde ``_batterie_compatible`` retombe sur un mot-clé qui n'est pas ce que
    ce test veut épingler), et les modules de batterie du montage.

    ``BATTERIE_SKUS`` — les calibres portés par CE montage ; une sous-classe
    ne pose que ``('5',)`` pour rejouer l'état réel du stock du fondateur.
    """

    slug = 'bathomo-co'
    BATTERIE_SKUS = ('5', '10')

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': 'BATHOMO'})
        self.user = User.objects.create_user(
            username='bathomo-%s' % self.slug, password='x',
            role_legacy='responsable', company=self.company)
        self.produits = {}

        self.produits['PAN'] = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W',
            sku='PAN-%s' % self.slug, prix_vente=Decimal('1100'),
            prix_achat=Decimal('1'), quantite_stock=500)
        FicheTechnique.objects.create(
            company=self.company, produit=self.produits['PAN'],
            type_fiche='module',
            pmax_wc=Decimal('550.00'), voc_v=Decimal('49.90'),
            isc_a=Decimal('14.02'), vmp_v=Decimal('41.80'),
            imp_a=Decimal('13.16'),
            temp_coeff_voc_pct_c=Decimal('-0.270'),
            temp_coeff_pmax_pct_c=Decimal('-0.350'))

        self.produits['ONDR'] = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW Monophasé',
            sku='ONDR-%s' % self.slug, prix_vente=Decimal('14000'),
            prix_achat=Decimal('1'), quantite_stock=500)
        self.produits['ONDH'] = Produit.objects.create(
            company=self.company, nom='Onduleur hybride Deye 5kW Monophasé',
            sku='ONDH-%s' % self.slug, prix_vente=Decimal('17000'),
            prix_achat=Decimal('1'), quantite_stock=500)
        FicheTechnique.objects.create(
            company=self.company, produit=self.produits['ONDR'],
            type_fiche='onduleur',
            ond_ac_kw=Decimal('5.00'), ond_phases=1, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('90.0'), ond_mppt_v_max=Decimal('560.0'),
            ond_v_max_abs=Decimal('600.0'), ond_i_max_mppt_a=Decimal('13.5'),
            ond_rendement_euro_pct=Decimal('97.0'), ond_bat_aucune=True)
        FicheTechnique.objects.create(
            company=self.company, produit=self.produits['ONDH'],
            type_fiche='onduleur',
            ond_ac_kw=Decimal('5.00'), ond_phases=1, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('90.0'), ond_mppt_v_max=Decimal('560.0'),
            ond_v_max_abs=Decimal('600.0'), ond_i_max_mppt_a=Decimal('13.5'),
            ond_rendement_euro_pct=Decimal('97.0'), ond_bat_aucune=False,
            ond_bat_v_min=Decimal('40.0'), ond_bat_v_max=Decimal('60.0'))

        for calibre in self.BATTERIE_SKUS:
            sku = 'BAT%s' % calibre
            produit = Produit.objects.create(
                company=self.company, nom='Batterie Dyness %s kWh' % calibre,
                sku='%s-%s' % (sku, self.slug),
                prix_vente=Decimal('16000') if calibre == '5' else Decimal('30000'),
                prix_achat=Decimal('1'), quantite_stock=500)
            self.produits[sku] = produit
            FicheTechnique.objects.create(
                company=self.company, produit=produit, type_fiche='batterie',
                bat_kwh_nominal=Decimal(calibre), bat_kwh_usable=Decimal(calibre),
                bat_dod_pct=Decimal('90.0'), bat_v_nominal=Decimal('51.2'),
                bat_max_charge_kw=Decimal('3.84'))

    def _compose(self, *, cible_kwh=None, kwc=30.0, nb_panneaux=None,
                 module_kwh=None):
        """Une composition « avec batterie », et son décompte homogène
        ``(nb_batteries_5, nb_batteries_10)`` — lu par la MÊME fonction que
        ``dimensionnement.echelle_paliers_batterie``."""
        produits = services.catalogue_de_la_societe(self.company)
        lignes = services.composition_residentielle(
            produits, kwc=kwc, panel_watt=550,
            nb_panneaux=nb_panneaux or max(1, int(kwc * 1000 / 550)),
            avec_batterie=True, batterie_cible_kwh=cible_kwh,
            batterie_module_kwh=module_kwh)
        vue = _lire_composition(lignes, Decimal('20'))
        cinq, dix = _compter_modules_batterie(vue['lignes'])
        return cinq, dix, vue


class BanqueHomogeneCatalogueMixte(_Base):
    """Catalogue portant LES DEUX calibres (l'état d'AVANT le retrait)."""

    slug = 'bathomo-mixte'
    BATTERIE_SKUS = ('5', '10')

    def test_jamais_les_deux_calibres_a_la_fois(self):
        """LE CŒUR DU CORRECTIF — pour un large balayage de cibles, incluant
        toutes celles qui, sous l'ANCIEN calcul (10 kWh de bloc + 5 kWh de
        reste), auraient mélangé les deux calibres (15, 25, 35, 45 kWh…)."""
        for cible in (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60):
            with self.subTest(cible_kwh=cible):
                cinq, dix, _vue = self._compose(cible_kwh=cible, kwc=40.0)
                self.assertFalse(
                    cinq > 0 and dix > 0,
                    'banque mélangée à %s kWh : %s modules de 5 ET %s de 10'
                    % (cible, cinq, dix))
                # Une banque a été composée (le vivier n'est pas vide) : au
                # moins un des deux calibres a servi.
                self.assertTrue(cinq > 0 or dix > 0, 'aucune batterie composée')

    def test_15_kwh_devient_trois_modules_de_5_jamais_1x10_plus_1x5(self):
        """LE SCÉNARIO EXACT DE L'INCIDENT : 15 kWh visés. L'ancien calcul
        rendait 1×10 + 1×5 (mélangé) ; le correctif rend 3×5 (homogène, même
        capacité nominale, un match EXACT alors que passer par le 10 kWh
        seul ne le pourrait pas)."""
        cinq, dix, vue = self._compose(cible_kwh=15, kwc=40.0)
        self.assertEqual((cinq, dix), (3, 0))
        self.assertAlmostEqual(vue['batterie_kwh'], 15.0, places=2)

    def test_25_kwh_devient_cinq_modules_de_5_jamais_2x10_plus_1x5(self):
        cinq, dix, vue = self._compose(cible_kwh=25, kwc=40.0)
        self.assertEqual((cinq, dix), (5, 0))
        self.assertAlmostEqual(vue['batterie_kwh'], 25.0, places=2)

    def test_multiples_de_10_preferent_le_plus_gros_calibre(self):
        """Sur un multiple EXACT de 10 (aucune perte quel que soit le
        calibre), la préférence historique du simulateur — le plus gros
        module d'abord — est CONSERVÉE : 10 kWh ⇒ 1×10, 20 kWh ⇒ 2×10."""
        self.assertEqual(self._compose(cible_kwh=10, kwc=40.0)[:2], (0, 1))
        self.assertEqual(self._compose(cible_kwh=20, kwc=40.0)[:2], (0, 2))

    def test_cible_implicite_derivee_du_kwc_reste_homogene(self):
        """Sans ``batterie_cible_kwh`` explicite (règle historique kWc/5) :
        même garde, même invariant — la source de la cible ne change rien à
        l'homogénéité de la banque."""
        for kwc in (14.9, 24.9, 34.9, 44.9):
            with self.subTest(kwc=kwc):
                cinq, dix, _vue = self._compose(cible_kwh=None, kwc=kwc)
                self.assertFalse(cinq > 0 and dix > 0)


class BanqueHomogeneCatalogueSeulement5(_Base):
    """Catalogue portant SEULEMENT le 5 kWh — l'état RÉEL du stock du
    fondateur depuis le retrait du Dyness 10 kWh (``BAT-DEY-10`` archivé,
    cf. ``apps.stock.management.commands.seed_catalogue``)."""

    slug = 'bathomo-5seul'
    BATTERIE_SKUS = ('5',)

    def test_les_echelles_et_compositions_fonctionnent_encore(self):
        """Aucune régression : sans le moindre module 10 kWh au catalogue, le
        stockage se compose toujours, exclusivement en multiples de 5."""
        for cible in (5, 10, 15, 20, 25, 30, 45, 60):
            with self.subTest(cible_kwh=cible):
                cinq, dix, vue = self._compose(cible_kwh=cible, kwc=40.0)
                self.assertEqual(dix, 0, 'le 10 kWh est absent du catalogue')
                self.assertGreater(cinq, 0)
                self.assertEqual(cinq * 5, cible)
                self.assertAlmostEqual(vue['batterie_kwh'], float(cible), places=2)

    def test_batterie_dyness_10_absente_ne_bloque_jamais_la_composition(self):
        """Le vivier ne tombe JAMAIS vide du seul fait de l'absence du
        10 kWh : le 5 kWh sert seul, la composition ne part pas sans
        batterie ni ne lève."""
        avertissements = []
        produits = services.catalogue_de_la_societe(self.company)
        lignes = services.composition_residentielle(
            produits, kwc=40.0, panel_watt=550, nb_panneaux=72,
            avec_batterie=True, batterie_cible_kwh=30,
            avertissements=avertissements)
        self.assertTrue(any(
            (getattr(li, 'produit', None) is not None
             and 'batterie' in (li.designation or '').lower())
            for li in lignes))
        self.assertEqual(avertissements, [])


class CalibreImposeSuitToujoursLeModuleDuDevis(_Base):
    """``batterie_module_kwh`` (fondateur 26/08/2026) — « the battery-related
    features in the quote web page should ALWAYS use the quote items — if the
    quote has 5 kWh batteries the web page should only show 5 kWh batteries ;
    and we can go up to 30 or 40 kWh using 5 kWh batteries, no problem. »

    Sans calibre imposé, l'égalité de coût (0 perte, quel que soit le
    calibre) sur un multiple de 10 fait normalement préférer le plus GROS
    module — exactement ce qu'un appelant qui connaît le module engagé par un
    devis à 5 kWh ne veut JAMAIS voir se produire en explorant son échelle."""

    slug = 'bathomo-impose'
    BATTERIE_SKUS = ('5', '10')

    def test_calibre_5_impose_jamais_de_10_meme_sur_un_multiple_de_10(self):
        """SANS le paramètre, 10/20/30/40 kWh préfèrent le module 10 (tie-
        break historique) — AVEC ``module_kwh=5``, ils restent en modules de
        5, jusqu'à 8 packs pour 40 kWh."""
        for cible, attendu in ((10, 2), (20, 4), (30, 6), (40, 8)):
            with self.subTest(cible_kwh=cible):
                cinq, dix, vue = self._compose(
                    cible_kwh=cible, kwc=40.0, module_kwh=5)
                self.assertEqual((cinq, dix), (attendu, 0))
                self.assertAlmostEqual(vue['batterie_kwh'], float(cible),
                                       places=2)

    def test_calibre_10_impose_jamais_de_5(self):
        cinq, dix, vue = self._compose(cible_kwh=15, kwc=40.0, module_kwh=10)
        self.assertEqual((cinq, dix), (0, 2))  # 2×10 = 20, le plus proche en 10 seul
        self.assertAlmostEqual(vue['batterie_kwh'], 20.0, places=2)

    def test_calibre_impose_absent_du_catalogue_replie_sur_le_plus_proche(self):
        """Le catalogue de ce montage porte les DEUX calibres : imposer un
        calibre absent (ex. 15, qui n'existe pas) ne peut PAS composer une
        banque vide — repli sur le choix « au plus proche » normal."""
        cinq, dix, _vue = self._compose(cible_kwh=15, kwc=40.0, module_kwh=15)
        self.assertTrue(cinq > 0 or dix > 0)
        self.assertFalse(cinq > 0 and dix > 0)

    def test_par_defaut_sans_calibre_impose_comportement_inchange(self):
        """``module_kwh`` absent (défaut) : le tie-break historique
        (plus gros calibre d'abord) décide toujours seul — aucune régression
        pour les appelants existants qui ne connaissent pas encore ce
        paramètre (ex. le devis automatique)."""
        self.assertEqual(self._compose(cible_kwh=20, kwc=40.0)[:2], (0, 2))


class CalibreImposeCatalogueSeulement5(_Base):
    """Le catalogue RÉEL du fondateur (10 kWh archivé) : imposer 5 EST déjà
    le seul chemin possible, et imposer 10 (absent) ne casse rien."""

    slug = 'bathomo-impose-5seul'
    BATTERIE_SKUS = ('5',)

    def test_calibre_10_impose_mais_absent_replie_sur_le_5_seul_disponible(self):
        cinq, dix, vue = self._compose(cible_kwh=30, kwc=40.0, module_kwh=10)
        self.assertEqual((cinq, dix), (6, 0))
        self.assertAlmostEqual(vue['batterie_kwh'], 30.0, places=2)
