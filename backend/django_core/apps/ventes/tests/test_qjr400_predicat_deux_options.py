"""QJR400 — UN SEUL prédicat « devis à deux options », celui du NOYAU.

TEST ROUGE D'ABORD. Il en existait DEUX et ils se contredisaient dans les DEUX
sens :

* noyau — ``utils.options.deux_options_declarees`` : court-circuit à ``True``
  dès qu'une ligne porte une variante, sinon ``etude_params['scenario']``
  (LU DANS LE CHAMP, jamais dans le registre de surcharges) + réseau +
  **hybride** + batterie ;
* document — ``builder.build_quote_data`` : ``sans_ok = has_reseau``,
  ``avec_ok = (has_hybride or has_offgrid) and has_batterie`` (il accepte
  l'**off-grid**, le noyau non), ``alternative_declaree`` sur le scénario
  RÉSOLU PAR LE REGISTRE, et aucun équivalent du court-circuit variante.

Quatre formes de divergence PROUVÉES, une classe chacune :

1. devis OFF-GRID déclaré deux options (réseau + hors-réseau + batterie) ;
2. devis à VARIANTES dont le scénario stocké est perdu ;
3. devis à VARIANTES dont le scénario stocké vaut « Sans batterie » ;
4. devis dont le scénario est posé UNIQUEMENT par ``overrides.effectif``.

Pour chacune : noyau et document s'accordent sur ``nb_options`` **et** sur les
totaux PAR OPTION. S'y ajoute S8-F5 (le panier « sans » du noyau et celui du
document contiennent les mêmes lignes sur un devis off-grid) et la
non-régression QF9 / mono-option (QJR300) au centime.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr400_predicat_deux_options"
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, deux_options_declarees,
    filter_lines_for_option, lignes_avec_produit, option_effective,
    option_totaux, totaux_affichage_repli,
)


#: Forme (1) — SITE ISOLÉ déclaré deux options : onduleur RÉSEAU d'un côté,
#: onduleur HORS RÉSEAU + batterie de l'autre. Le document sert les deux
#: (``avec_ok`` accepte l'off-grid depuis QJR-OFFGRID) ; le noyau exigeait un
#: onduleur HYBRIDE et rendait donc « mono-option ».
LIGNES_OFFGRID = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hors réseau Deye 8kW', '1', '21000'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Installation', '1', '5000'),
]

#: Formes (2) et (3) — devis à VARIANTES (deux champs PV : 12 panneaux sans
#: batterie, 16 avec). Les lignes portent ``variante`` : c'est la composition
#: qui a DÉJÀ distingué les deux options.
LIGNES_VARIANTES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', 'sans'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', 'avec'),
    ('Batterie Dyness 10 kWh', '1', '25000', 'avec'),
    ('Panneau Canadian Solar 710W', '12', '1166.67', 'sans'),
    ('PV Panneau Canadian Solar 710W', '16', '1166.67', 'avec'),
    ('Installation', '1', '5000', ''),
]

#: Forme (4) — devis SANS scénario stocké : la déclaration n'existe QUE dans
#: le registre de surcharges (chemin ``scenario``), posé par l'endpoint livré.
LIGNES_DEUX_FAMILLES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Installation', '1', '5000'),
]

#: Non-régression QJR300 — devis MONO-OPTION à onduleur réseau non-Huawei.
LIGNES_MONO_RESEAU_DEYE = [
    ('Onduleur réseau Deye 10kW Triphasé', '1', '16666.67'),
    ('Smart Meter', '1', '1500'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Installation', '1', '5000'),
]

#: Non-régression QF9 — deux options, aucune marque Huawei : les accessoires
#: orphelins partent des DEUX paniers, document comme noyau.
LIGNES_QF9_DEYE = [
    ('Onduleur réseau Deye 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Smart Meter', '1', '1500'),
    ('Wifi Dongle', '1', '1000'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
    ('Installation', '1', '5000'),
]


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self._seq = 0

    def _devis(self, lignes, etude_params=None, variantes=False):
        self._seq += 1
        reference = 'DEV-QJR400-%04d' % self._seq
        brutes = [ligne[:3] for ligne in lignes]
        devis = make_devis(self.company, self.user, self.client_obj, brutes,
                           reference=reference, etude_params=etude_params)
        if variantes:
            for ligne, source in zip(devis.lignes.order_by('id'), lignes):
                ligne.variante = source[3]
                ligne.save(update_fields=['variante'])
        return devis

    @staticmethod
    def _data(devis):
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(devis, {'pdf_mode': 'onepage'})

    def _assert_accord(self, devis):
        """Le noyau et le document s'accordent sur ``nb_options`` ET sur les
        totaux PAR OPTION (pas seulement sur le total global)."""
        data = self._data(devis)
        repli = totaux_affichage_repli(devis)
        self.assertEqual(
            repli['nb_options'], data['nb_options'],
            'nb_options : noyau %s != document %s'
            % (repli['nb_options'], data['nb_options']))
        for option, cle in ((SANS_BATTERIE, 'total_sans'),
                            (AVEC_BATTERIE, 'total_avec')):
            noyau = Decimal(str(option_totaux(devis, option)['ttc']))
            document = Decimal(str(data[cle]))
            self.assertLessEqual(
                abs(noyau - document), Decimal('1'),
                '%s : noyau %s != document %s' % (option, noyau, document))
        # Le total AFFICHÉ (liste, échéancier, solde) suit l'option que le
        # document met en avant.
        noyau_effectif = Decimal(str(option_totaux(devis)['ttc']))
        self.assertLessEqual(
            abs(noyau_effectif - Decimal(str(data['display_total']))),
            Decimal('1'),
            'total affiché : noyau %s != document %s'
            % (noyau_effectif, data['display_total']))


class Forme1DevisOffGrid(_Base):
    """(1) réseau + hors-réseau + batterie + scénario déclaré."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(LIGNES_OFFGRID,
                                 etude_params=dict(DEUX_OPTIONS))

    def test_le_noyau_voit_les_deux_options(self):
        """ROUGE AVANT : le noyau exigeait un onduleur HYBRIDE."""
        self.assertTrue(deux_options_declarees(self.devis))

    def test_noyau_et_document_s_accordent(self):
        self._assert_accord(self.devis)

    def test_s8_f5_le_panier_sans_exclut_l_onduleur_hors_reseau(self):
        """ROUGE AVANT : ``_garder_dans_sans`` excluait batterie + hybride mais
        PAS l'off-grid, là où ``ok_sans`` du document exclut les trois."""
        data = self._data(self.devis)
        noyau = sorted(
            li.designation for li in filter_lines_for_option(
                lignes_avec_produit(self.devis), SANS_BATTERIE))
        document = sorted(it['designation'] for it in data['sans_items'])
        self.assertEqual(noyau, document)


class Forme2VariantesSansScenario(_Base):
    """(2) devis à variantes dont le ``scenario`` stocké est perdu."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(LIGNES_VARIANTES, etude_params={},
                                 variantes=True)

    def test_noyau_et_document_s_accordent(self):
        """ROUGE AVANT : le noyau court-circuitait à ``True`` (variantes)
        pendant que le document prenait le chemin ARTEFACT PV86 (une seule
        présentation portant TOUTES les lignes)."""
        self._assert_accord(self.devis)

    def test_le_document_rend_bien_deux_options(self):
        self.assertEqual(self._data(self.devis)['nb_options'], 2)


class Forme3VariantesScenarioSansBatterie(_Base):
    """(3) devis à variantes dont le ``scenario`` vaut « Sans batterie »."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(LIGNES_VARIANTES,
                                 etude_params={'scenario': 'Sans batterie'},
                                 variantes=True)

    def test_noyau_et_document_s_accordent(self):
        """ROUGE AVANT : le document rétrécissait à l'option « sans » (QF6)
        pendant que le noyau facturait l'option « avec »."""
        self._assert_accord(self.devis)

    def test_l_argent_suit_l_option_titree(self):
        self.assertEqual(option_effective(self.devis), SANS_BATTERIE)


class Forme4ScenarioPoseParSurcharge(_Base):
    """(4) scénario posé UNIQUEMENT par le registre de surcharges."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(LIGNES_DEUX_FAMILLES, etude_params={})
        from apps.ventes.domain import overrides as registre
        registre.ecrire_colonne(
            self.devis,
            registre.fusionner(
                self.devis,
                {'scenario': {'valeur': 'Les deux (Sans + Avec)'}},
                utilisateur=self.user))

    def test_le_noyau_lit_le_scenario_du_registre(self):
        """ROUGE AVANT : le noyau ne lisait que ``etude_params['scenario']``,
        donc un scénario posé par l'endpoint de surcharges — livré — n'était
        JAMAIS relu par lui."""
        self.assertTrue(deux_options_declarees(self.devis))

    def test_noyau_et_document_s_accordent(self):
        self._assert_accord(self.devis)


class NonRegressionMonoOptionEtQF9(_Base):
    """QJR300 (mono-option) et QF9 (deux options) restent au centime."""

    def test_mono_option_inchange(self):
        devis = self._devis(LIGNES_MONO_RESEAU_DEYE,
                            etude_params={'scenario': 'Sans batterie'})
        self.assertFalse(deux_options_declarees(devis))
        self.assertEqual(option_effective(devis), '')
        data = self._data(devis)
        noyau = Decimal(str(option_totaux(devis)['ttc']))
        self.assertLessEqual(
            abs(noyau - Decimal(str(data['display_total']))), Decimal('1'))
        self.assertIn('Smart Meter',
                      [it['designation'] for it in data['all_items']])

    def test_qf9_deux_options_inchange(self):
        devis = self._devis(LIGNES_QF9_DEYE, etude_params=dict(DEUX_OPTIONS))
        data = self._data(devis)
        for cle in ('sans_items', 'avec_items'):
            desigs = [it['designation'] for it in data[cle]]
            self.assertNotIn('Smart Meter', desigs, cle)
            self.assertNotIn('Wifi Dongle', desigs, cle)
        self._assert_accord(devis)
