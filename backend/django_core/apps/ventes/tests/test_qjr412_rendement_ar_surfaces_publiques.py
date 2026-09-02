# -*- coding: utf-8 -*-
"""QJR412 (S3-F3, checked-facts) — le rendement aller-retour SOURCÉ SUR FICHE
est lu par TOUTES les surfaces qui le PUBLIENT.

QJR137 avait créé le chemin sourcé — ``rendement_batterie_des_lignes``
(``etude_horaire.py``) lit ``Produit.rendement_ar_pct`` et étiquette sa
provenance (``RENDEMENT_SOURCE_FICHE`` / ``RENDEMENT_SOURCE_HYPOTHESE``) — et
l'avait câblé dans :func:`calculer_etude_horaire`. Mais DEUX surfaces CLIENT
ne l'empruntaient pas : ``couverture_batterie_publique`` (le curseur « N
batteries ») et ``balayer_stockage_horaire`` (DIM2) simulaient TOUJOURS à la
constante ``pricing.BATTERY_ROUNDTRIP`` (0,90) et la publiaient comme si elle
décrivait la batterie vendue, sans jamais dire que c'était un forfait —
exactement ce que la règle zéro-chiffre-inventé interdit (un chiffre montré
au client doit être réel, dérivé-traçable, ou OMIS).

Ce module épingle que les DEUX fonctions acceptent désormais
``batterie_rendement``/``batterie_rendement_source`` — MÊME contrat que
:func:`calculer_etude_horaire` (QJR137) — et publient LA valeur reçue,
étiquetée. AVANT ce correctif, les deux fonctions n'acceptaient même pas ces
mots-clés : un appel avec ``batterie_rendement=`` levait ``TypeError``, la
preuve la plus directe qu'elles ignoraient la fiche.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr412_rendement_ar_surfaces_publiques"
"""
from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes import etude_horaire as EH

VILLE = 'Casablanca'
#: Même profil de référence, PROUVÉ par ``test_payload_couverture_batterie.py``
#: (villa 8,5 kWc, 900 kWh/mois, pack 4,6 kWh) : Casablanca est dans la table
#: PVGIS de référence, aucun accès réseau n'est nécessaire.
KWC = 8.5
CONSO = [900.0] * 12
CAP_PACK = 4.6

#: Une fiche qui publie un rendement DIFFÉRENT de l'hypothèse de référence —
#: si le moteur retombe sur 0,90, c'est qu'il ignore la fiche.
RENDEMENT_FICHE = 0.95


class CouvertureBatteriePubliqueRendementTest(SimpleTestCase):
    """``couverture_batterie_publique`` — le curseur « N batteries »."""

    def _bloc(self, **overrides):
        params = dict(
            kwc=KWC, conso_kwh_mensuelles=CONSO,
            capacite_utile_pack_kwh=CAP_PACK, nb_packs_max=4,
            ville=VILLE, occupation=CJ.OCCUPATION_PRESENCE)
        params.update(overrides)
        return EH.couverture_batterie_publique(**params)

    def test_rouge_le_rendement_de_fiche_est_rendu_et_etiquete(self):
        """ROUGE avant le correctif : cette signature n'acceptait même pas
        ``batterie_rendement`` (``TypeError``), et le bloc publiait TOUJOURS
        0,90 non étiqueté, quelle que soit la fiche du devis."""
        bloc = self._bloc(
            batterie_rendement=RENDEMENT_FICHE,
            batterie_rendement_source=EH.RENDEMENT_SOURCE_FICHE)
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['rendement'], RENDEMENT_FICHE)
        self.assertEqual(bloc['rendement_source'], EH.RENDEMENT_SOURCE_FICHE)
        self.assertNotEqual(bloc['rendement'], EH.BATTERY_ROUNDTRIP)

    def test_sans_rendement_de_fiche_l_hypothese_est_declaree(self):
        """Le repli reste permis — jamais son SILENCE : sans fiche, le bloc
        publie l'hypothèse de référence ET son étiquette, jamais un chiffre
        nu."""
        bloc = self._bloc()
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['rendement'], EH.BATTERY_ROUNDTRIP)
        self.assertEqual(bloc['rendement_source'],
                         EH.RENDEMENT_SOURCE_HYPOTHESE)

    def test_une_valeur_hors_bornes_ne_passe_jamais_pour_une_fiche(self):
        """Même garde que QJR137 dans ``calculer_etude_horaire`` : un
        rendement illisible ou hors ``]0, 1]`` retombe sur l'hypothèse, il ne
        se fait jamais passer pour une valeur prouvée."""
        bloc = self._bloc(
            batterie_rendement=1.4,
            batterie_rendement_source=EH.RENDEMENT_SOURCE_FICHE)
        self.assertEqual(bloc['rendement'], EH.BATTERY_ROUNDTRIP)
        self.assertEqual(bloc['rendement_source'],
                         EH.RENDEMENT_SOURCE_HYPOTHESE)


class BalayerStockageHoraireRendementTest(SimpleTestCase):
    """``balayer_stockage_horaire`` (DIM2) — même correction, même contrat."""

    def _bloc(self, **overrides):
        params = dict(
            kwc=KWC, conso_kwh_mensuelles=CONSO,
            capacites_kwh=[CAP_PACK, 2 * CAP_PACK], ville=VILLE,
            occupation=CJ.OCCUPATION_PRESENCE)
        params.update(overrides)
        return EH.balayer_stockage_horaire(**params)

    def test_rouge_le_rendement_de_fiche_est_rendu_et_etiquete(self):
        """ROUGE avant le correctif : ``rendement_batterie`` valait TOUJOURS
        0,90 (même appel ``TypeError`` sur ``batterie_rendement`` avant que
        la signature ne l'accepte)."""
        bloc = self._bloc(
            batterie_rendement=RENDEMENT_FICHE,
            batterie_rendement_source=EH.RENDEMENT_SOURCE_FICHE)
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['rendement_batterie'], RENDEMENT_FICHE)
        self.assertEqual(bloc['rendement_batterie_source'],
                         EH.RENDEMENT_SOURCE_FICHE)
        self.assertNotEqual(bloc['rendement_batterie'], EH.BATTERY_ROUNDTRIP)

    def test_sans_rendement_de_fiche_l_hypothese_est_declaree(self):
        bloc = self._bloc()
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['rendement_batterie'], EH.BATTERY_ROUNDTRIP)
        self.assertEqual(bloc['rendement_batterie_source'],
                         EH.RENDEMENT_SOURCE_HYPOTHESE)


class CalculerEtudeHoraireInchangeTest(SimpleTestCase):
    """Troisième garantie du Done : ``calculer_etude_horaire`` — déjà
    correcte depuis QJR137 — reste inchangée au centime par ce correctif."""

    def _commun(self):
        return dict(kwc=KWC, conso_kwh_mensuelles=CONSO, ville=VILLE,
                    occupation=CJ.OCCUPATION_PRESENCE,
                    batterie_kwh_utile=10.0)

    def test_le_repli_muet_garde_sa_forme_historique(self):
        """Sur le repli, AUCUNE clé de plus (QJR137, ``CLES_RACINE_HISTORIQUES``)."""
        etude = EH.calculer_etude_horaire(**self._commun())
        self.assertIsNotNone(etude)
        self.assertNotIn('rendement_batterie', etude)
        self.assertNotIn('rendement_batterie_source', etude)

    def test_avec_fiche_le_rendement_voyage_toujours(self):
        etude = EH.calculer_etude_horaire(
            batterie_rendement=RENDEMENT_FICHE,
            batterie_rendement_source=EH.RENDEMENT_SOURCE_FICHE,
            **self._commun())
        self.assertIsNotNone(etude)
        self.assertEqual(etude['rendement_batterie'], RENDEMENT_FICHE)
        self.assertEqual(etude['rendement_batterie_source'],
                         EH.RENDEMENT_SOURCE_FICHE)
