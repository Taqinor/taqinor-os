"""AMOT30 (C-AMOT-031) — les cartes Éco/Max, le tableau de dimensionnement et
l'échelle de paliers appellent le moteur horaire avec LES MÊMES arguments que
le devis (barème société, charges fixes, jour de référence) via le
constructeur unique ``etude_horaire.kwargs_moteur_horaire`` ; ``tranches`` /
``charges_fixes_mad`` sont OBLIGATOIRES dans ``calculer_etude_horaire``.

Moteur réel. Test-du-test : retirer ``tranches`` de ``kwargs_moteur_horaire``
⇒ ``test_constructeur_porte_le_bareme`` et ``test_cartes_lisent_le_
constructeur`` échouent.
"""
import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes import etude_horaire as EH
from apps.ventes import offres_tailles as ot
from apps.ventes.domain.entrees import EntreesMoteur
from apps.ventes.horaire import conso as HC
from apps.ventes.quote_engine.pricing import ONEE_TRANCHES, TrancheTable

# Barème SOCIÉTÉ = grille nationale +20 % (la sonde VB).
_TRANCHES = TrancheTable(
    [(borne, round(prix * 1.2, 6)) for borne, prix in ONEE_TRANCHES],
    selective_threshold=ONEE_TRANCHES.selective_threshold,
    boundary_tolerance=ONEE_TRANCHES.boundary_tolerance)
_JOUR = datetime.date(2026, 3, 15)


def _entrees():
    conso, _s, _d = HC.profil_depuis_factures(facture_hiver_mad=900)
    return EntreesMoteur(conso_kwh_mensuelles=conso, ville='Casablanca',
                         tranches=_TRANCHES, charges_fixes_mad=31.5,
                         jour_reference=_JOUR, source_conso='facture_hiver')


class KwargsMoteurTests(SimpleTestCase):
    def test_tranches_obligatoires(self):
        conso, _s, _d = HC.profil_depuis_factures(facture_hiver_mad=900)
        with self.assertRaises(TypeError):
            EH.calculer_etude_horaire(kwc=5.0, conso_kwh_mensuelles=conso,
                                      ville='Casablanca')

    def test_constructeur_porte_le_bareme(self):
        kw = EH.kwargs_moteur_horaire(_entrees())
        self.assertEqual(kw['tranches'], _TRANCHES)
        self.assertEqual(kw['charges_fixes_mad'], 31.5)
        self.assertEqual(kw['jour_reference'], _JOUR)
        self.assertEqual(kw['ville'], 'Casablanca')
        self.assertNotIn('source_conso', kw)
        # Un mapping de mêmes clés donne le même résultat.
        self.assertEqual(EH.kwargs_moteur_horaire(dict(_entrees().__dict__)),
                         kw)

    def test_cartes_lisent_le_constructeur(self):
        contexte = SimpleNamespace(entrees=_entrees())
        kw = ot._Contexte.etude_kwargs.fget(contexte)
        self.assertEqual(kw, EH.kwargs_moteur_horaire(_entrees()))

    def test_a_kwc_egal_meme_economie(self):
        """À kWc égal, la carte (arguments du constructeur) et le devis
        (arguments complets) chiffrent la MÊME économie au barème société."""
        entrees = _entrees()
        carte = EH.calculer_etude_horaire(
            kwc=5.0, batterie_kwh_utile=0,
            source_conso=entrees['source_conso'],
            **EH.kwargs_moteur_horaire(entrees))
        devis = EH.calculer_etude_horaire(
            kwc=5.0, batterie_kwh_utile=0,
            conso_kwh_mensuelles=entrees['conso_kwh_mensuelles'],
            ville='Casablanca', tranches=_TRANCHES, charges_fixes_mad=31.5,
            jour_reference=_JOUR, source_conso='facture_hiver')
        if carte is None or devis is None:
            self.skipTest('PVGIS non résolu dans cet environnement')
        self.assertEqual(carte['annuel']['economie_sans_mad'],
                         devis['annuel']['economie_sans_mad'])
        national = EH.calculer_etude_horaire(
            kwc=5.0, batterie_kwh_utile=0,
            conso_kwh_mensuelles=entrees['conso_kwh_mensuelles'],
            ville='Casablanca', tranches=None, charges_fixes_mad=None,
            jour_reference=_JOUR, source_conso='facture_hiver')
        self.assertNotEqual(national['annuel']['economie_sans_mad'],
                            carte['annuel']['economie_sans_mad'])
