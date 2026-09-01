"""QJR300 — l'accessoire d'un devis MONO-OPTION est imprimé ET facturé.

TEST ROUGE D'ABORD (ronde 3, constat T1 prouvé par exécution). Le noyau
monnaie ne retire les accessoires Huawei orphelins que dans les paniers NOMMÉS
d'un vrai devis à deux options (``utils.options.option_lines`` court-circuite
dès que ``has_two_options`` est faux). Le moteur PDF, lui, les retirait
INCONDITIONNELLEMENT (``builder._drop_huawei_accessories`` sur ``_sans_paires``
ET ``_avec_paires``, plus le filtrage QJR124 de la liste libre).

Conséquence, sur un devis MONO-OPTION à onduleur réseau non-Huawei portant un
Smart Meter : ``build_quote_data(devis)['display_total']`` valait 1 800 TTC de
MOINS que ``option_totaux(devis)['ttc']`` — donc de moins que l'échéancier, le
solde, la commission et ``Devis.total_ttc``. Deux prix pour la même vente.

Direction tranchée : LE PDF S'ALIGNE SUR LE NOYAU (D12 — les lignes du vendeur
sont souveraines ; zéro-chiffre-inventé — l'argent la compte déjà). QF9 ne
s'applique donc plus que dans le cas DEUX-OPTIONS (non-régression épinglée
ici), et la branche Z1 ``hybride_sans_batterie`` reste intégralement rendue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr300_accessoire_mono_option"
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.echeancier import solde_devis
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, option_lines, option_totaux,
)


#: MONO-OPTION : un seul onduleur, RÉSEAU, non-Huawei (Deye), plus un Smart
#: Meter ajouté à la main par le vendeur. Aucune batterie, aucun hybride → il
#: n'existe pas de seconde option, donc rien à purger.
LIGNES_MONO_RESEAU_DEYE = [
    ('Onduleur réseau Deye 10kW Triphasé', '1', '16666.67'),
    ('Smart Meter', '1', '1500'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Structures acier', '14', '416.67'),
    ('Installation', '1', '5000'),
]

#: DEUX OPTIONS, aucune marque Huawei : la règle QF9 garde tout son sens (elle
#: purge d'un panier les artefacts de l'AUTRE option) — REQUALIFIÉE « voulue ».
LIGNES_DEUX_OPTIONS_DEYE = [
    ('Onduleur réseau Deye 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Smart Meter', '1', '1500'),
    ('Wifi Dongle', '1', '1000'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
    ('Installation', '1', '5000'),
]

#: Z1 — onduleur HYBRIDE sans ligne batterie : le document dégrade en option
#: unique dont la composition est TOUTES les lignes du devis.
LIGNES_HYBRIDE_SANS_BATTERIE = [
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Smart Meter', '1', '1500'),
    ('Wifi Dongle', '1', '1000'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Installation', '1', '5000'),
]


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, lignes, reference, etude_params=None):
        return make_devis(self.company, self.user, self.client_obj, lignes,
                          reference=reference, etude_params=etude_params)

    @staticmethod
    def _data(devis):
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(devis)

    @staticmethod
    def _desigs(items):
        return [it['designation'] for it in items]


class InvariantTroisChiffresMonoOption(_Base):
    """LE ROUGE : document == noyau == échéancier, sur un devis mono-option."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(LIGNES_MONO_RESEAU_DEYE, 'DEV-QJR300-0001',
                                 etude_params={'scenario': 'Sans batterie'})

    def test_le_document_le_noyau_et_le_solde_portent_le_meme_ttc(self):
        """ROUGE AVANT : ``display_total`` était plus bas de 1 800 TTC (le
        Smart Meter), que l'échéancier et le solde facturaient pourtant."""
        data = self._data(self.devis)
        noyau = Decimal(str(option_totaux(self.devis)['ttc']))
        document = Decimal(str(data['display_total']))
        solde = solde_devis(self.devis)['total_ttc']
        self.assertLessEqual(
            abs(document - noyau), Decimal('1'),
            f'total imprimé {document} != total du noyau {noyau}')
        self.assertLessEqual(
            abs(Decimal(str(solde)) - noyau), Decimal('1'),
            f'solde {solde} != total du noyau {noyau}')

    def test_l_accessoire_est_bien_dans_le_document(self):
        """ROUGE AVANT : le Smart Meter disparaissait du panier rendu."""
        data = self._data(self.devis)
        self.assertIn('Smart Meter', self._desigs(data['sans_items']))
        self.assertIn('Smart Meter', self._desigs(data['all_items']))

    def test_le_noyau_le_facture_toujours(self):
        """La moitié noyau ne bouge pas : elle était déjà juste."""
        self.assertIn('Smart Meter',
                      [li.designation for li in option_lines(self.devis)])


class NonRegressionQF9DeuxOptions(_Base):
    """QF9 est PRÉSERVÉE dans le cas deux-options (décision requalifiée)."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(LIGNES_DEUX_OPTIONS_DEYE, 'DEV-QJR300-0002',
                                 etude_params=dict(DEUX_OPTIONS))

    def test_les_deux_paniers_du_document_perdent_l_accessoire(self):
        data = self._data(self.devis)
        for cle in ('sans_items', 'avec_items'):
            desigs = self._desigs(data[cle])
            self.assertNotIn('Smart Meter', desigs, cle)
            self.assertNotIn('Wifi Dongle', desigs, cle)

    def test_les_deux_paniers_du_noyau_perdent_l_accessoire(self):
        for option in (SANS_BATTERIE, AVEC_BATTERIE):
            desigs = [li.designation
                      for li in option_lines(self.devis, option)]
            self.assertNotIn('Smart Meter', desigs, option)
            self.assertNotIn('Wifi Dongle', desigs, option)

    def test_le_document_et_le_noyau_restent_d_accord(self):
        data = self._data(self.devis)
        for option, cle in ((SANS_BATTERIE, 'total_sans'),
                            (AVEC_BATTERIE, 'total_avec')):
            noyau = Decimal(str(option_totaux(self.devis, option)['ttc']))
            self.assertLessEqual(
                abs(noyau - Decimal(str(data[cle]))), Decimal('1'), option)


class Z1HybrideSansBatterieRendToutesSesLignes(_Base):
    """Le rattrapage Z1 n'est NI filtré NI re-filtré."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(LIGNES_HYBRIDE_SANS_BATTERIE,
                                 'DEV-QJR300-0003',
                                 etude_params={'scenario': 'Avec batterie'})

    def test_toutes_les_lignes_sont_rendues(self):
        data = self._data(self.devis)
        attendu = [ligne[0] for ligne in LIGNES_HYBRIDE_SANS_BATTERIE]
        self.assertEqual(sorted(self._desigs(data['sans_items'])),
                         sorted(attendu))
        self.assertEqual(sorted(self._desigs(data['all_items'])),
                         sorted(attendu))

    def test_le_total_du_document_est_le_total_du_devis(self):
        data = self._data(self.devis)
        noyau = Decimal(str(option_totaux(self.devis)['ttc']))
        self.assertLessEqual(
            abs(Decimal(str(data['display_total'])) - noyau), Decimal('1'))
