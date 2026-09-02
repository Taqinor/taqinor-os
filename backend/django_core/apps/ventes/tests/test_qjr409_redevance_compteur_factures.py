"""QJR409 — la redevance de compteur réglée par la société est honorée par les
DEUX modèles de « Facture actuelle », pas seulement par l'horaire.

TEST ROUGE D'ABORD. ``TariffSettings.redevance_compteur_mad_mois`` n'avait
qu'UN seul lecteur dans tout le backend — ``etude_horaire._reglages_tarifaires``
— et ``quote_engine/bareme.py`` documente noir sur blanc que ce réglage
REMPLACE les charges fixes par défaut.

**La branche « factures » qui laissait tomber le réglage est NOMMÉE** :
``pricing.calculate_savings_roi``, ses deux appels à ``two_bills_savings``
(bloc « QF2 — modèle deux factures »). Ils ne passaient NI
``charges_fixes_mad`` ni rien qui en tienne lieu, alors que
``two_bills_savings`` accepte ce paramètre depuis QJR157 et le transmet à
``bareme.facture_mad``. Le même client voyait donc DEUX « Facture actuelle »
différentes selon le modèle qui gagne — la classe de défaut que QJR157
existait pour fermer.

(L'ancre citée par la ronde, ``builder.py:1775``, était FAUSSE : cette ligne
est le bloc ``roi_kwargs = dict(`` et ``redevance_compteur`` n'apparaît nulle
part dans ``builder.py``.)

Correction : le réglage est branché via le lecteur EXISTANT — jamais un second
— et transmis par ``builder`` dans ``roi_kwargs``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr409_redevance_compteur_factures"
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.quote_engine import bareme, pricing


#: Une redevance NETTEMENT différente du défaut sourcé (39,94 MAD TTC/mois) :
#: si le réglage n'est pas honoré, l'écart se voit au dirham.
REDEVANCE = 120.0

COMMUN = dict(
    production_kwh=12000,
    conso_annuelle_kwh=9000,
    autoconso_ratio=0.6,
    utility='onee',
)


class LaBrancheFacturesHonoreLeReglage(TestCase):
    """Le modèle « factures » compte les MÊMES lignes fixes que l'horaire."""

    @staticmethod
    def _facture_horaire(charges_fixes_mad):
        """La « Facture actuelle » du modèle HORAIRE : douze mois au barème,
        lignes fixes de la société comprises (``bareme.facture_mad``, le même
        moteur que ``etude_horaire``)."""
        table, _ = pricing._resolve_tranches('onee', None)
        mensuel = bareme.facture_mad(
            COMMUN['conso_annuelle_kwh'] / 12.0,
            jours=bareme.TPPAN_JOURS_REFERENCE,
            tranches=table, charges_fixes_mad=charges_fixes_mad)
        return round(mensuel['total_mad'] * 12.0)

    def test_les_deux_factures_actuelles_sont_egales(self):
        """ROUGE AVANT : ``two_bills_savings`` était appelé SANS
        ``charges_fixes_mad`` — le modèle « factures » comptait les lignes
        fixes par défaut pendant que l'horaire comptait celles de la
        société."""
        factures = pricing.two_bills_savings(
            **COMMUN, charges_fixes_mad=REDEVANCE)
        self.assertIsNotNone(factures)
        self.assertEqual(factures['facture_sans'],
                         self._facture_horaire(REDEVANCE))

    def test_le_roi_transmet_le_reglage_au_modele_factures(self):
        """Le paramètre traverse ``calculate_savings_roi`` — c'est la branche
        qui le laissait tomber."""
        roi = pricing.calculate_savings_roi(
            10.0, 150000, 190000,
            conso_annuelle_kwh=COMMUN['conso_annuelle_kwh'],
            utility='onee', charges_fixes_mad=REDEVANCE)
        self.assertEqual(roi['savings_model'], 'factures')
        defaut = pricing.calculate_savings_roi(
            10.0, 150000, 190000,
            conso_annuelle_kwh=COMMUN['conso_annuelle_kwh'],
            utility='onee')
        self.assertNotEqual(roi['facture_sans'], defaut['facture_sans'])
        self.assertEqual(roi['facture_sans'], self._facture_horaire(REDEVANCE))


class SansReglageRienNeChange(TestCase):
    """Une société qui n'a pas relevé ses lignes fixes garde les défauts."""

    def test_les_defauts_du_bareme_continuent_de_s_appliquer(self):
        sans_arg = pricing.two_bills_savings(**COMMUN)
        avec_none = pricing.two_bills_savings(**COMMUN,
                                              charges_fixes_mad=None)
        self.assertEqual(sans_arg, avec_none)

    def test_le_roi_est_inchange_sans_reglage(self):
        avant = pricing.calculate_savings_roi(
            10.0, 150000, 190000, conso_annuelle_kwh=9000, utility='onee')
        apres = pricing.calculate_savings_roi(
            10.0, 150000, 190000, conso_annuelle_kwh=9000, utility='onee',
            charges_fixes_mad=None)
        self.assertEqual(avant['facture_sans'], apres['facture_sans'])
        self.assertEqual(avant['eco_s_ann'], apres['eco_s_ann'])


class UnSeulLecteurDuReglage(TestCase):
    """Le réglage n'est LU qu'à un seul endroit ; le builder le TRANSMET."""

    def test_le_builder_passe_par_le_lecteur_existant(self):
        from apps.ventes.etude_horaire import _reglages_tarifaires
        from apps.parametres.models_tariff import TariffSettings
        from apps.ventes.tests._quote_engine_common import make_company

        company = make_company()
        reglages = TariffSettings.get(company=company)
        reglages.redevance_compteur_mad_mois = Decimal(str(REDEVANCE))
        reglages.save(update_fields=['redevance_compteur_mad_mois'])

        _, charges = _reglages_tarifaires(company)
        self.assertEqual(charges, REDEVANCE)
