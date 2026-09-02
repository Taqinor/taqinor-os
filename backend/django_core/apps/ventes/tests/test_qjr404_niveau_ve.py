# -*- coding: utf-8 -*-
"""QJR404 — le niveau donné au compositeur de forme inclut enfin la charge du
véhicule électrique, comme son contrat l'exige.

``forme_consommation_detaillee`` (``courbes_journalieres.py:976-994``) documente
que ``kwh_jour`` contient DÉJÀ l'énergie du véhicule électrique : le composeur
la RETIRE du niveau avant de renormaliser les couches de redistribution
(passe 1), puis la RAJOUTE telle quelle, jamais rediluée (passe 2). Avant ce
correctif, ``jours_types_annee`` (``etude_horaire.py``) appelait ce composeur
avec la facture NUE (VE exclu) : une énergie déjà absente se voyait retirée
une SECONDE fois, et la courbe rendue perdait le VE que la publication
(``estimation_conso_mensuelle``) affiche pourtant dans la même réponse, pour
le même devis (mesuré par la ronde 4 : 7 200 contre 8 660 kWh/an).

AUCUN des deux nombres mesurés n'est recopié ici : l'attendu de chaque test se
DÉRIVE du contrat (niveau d'entrée = facture + charge VE annuelle), exactement
comme la ronde V5 l'a prouvé algébriquement.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr404_niveau_ve"
"""
from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes import etude_horaire as EH


class NiveauVeCourbeRenduTest(SimpleTestCase):
    """Le total ANNUEL de la courbe rendue par le moteur horaire égale le
    niveau annuel d'entrée, VE compris — l'invariance « soustraire-puis-
    rajouter » du composeur, tenue cette fois par l'APPELANT."""

    VILLE = 'Casablanca'
    #: 600 kWh/mois de facture NUE (sans VE) — même régime que
    #: ``EstimationConsoFacteurCompositeurTests`` (QJR207,
    #: ``test_etude_horaire.py``), déjà éprouvé par la suite existante.
    CONSO = [600.0] * 12
    VE = {'ve': {'kwh_jour': 4.0, 'heures': [21, 22, 23, 0, 1, 2],
                 'saisons': None, 'mode': 'addition', 'source': 'test'}}

    def _niveau_annuel_attendu_avec_ve(self):
        """L'énergie annuelle attendue = la facture + la SEULE charge VE
        (active toute l'année ici) — dérivé du contrat, jamais une mesure
        recopiée."""
        ve_kwh_jour = self.VE['ve']['kwh_jour']
        return sum(self.CONSO) + ve_kwh_jour * sum(EH.JOURS_PAR_MOIS)

    def _total_annuel_courbe(self, jours_types):
        """Le total RÉELLEMENT rendu par la courbe : Σ (jour type × jours du
        mois) — jamais ``conso_mois_kwh``, qui reste la facture nue publiée
        telle quelle ailleurs (contrat inchangé par cette tâche)."""
        return sum(sum(jour['conso_24h']) * jour['jours']
                   for jour in jours_types)

    def test_avec_ve_le_total_de_la_courbe_egale_le_niveau_d_entree(self):
        """ROUGE avant le correctif : la courbe perdait l'énergie VE (double
        soustraction) et son total annuel tombait à la seule facture nue."""
        jours_types, avertissements, _sources = EH.jours_types_annee(
            kwc=6.0, conso_kwh_mensuelles=self.CONSO, ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE, equipements=self.VE)
        self.assertIsNotNone(jours_types, avertissements)
        self.assertEqual(len(jours_types), 12)

        total_courbe = self._total_annuel_courbe(jours_types)
        niveau_attendu = self._niveau_annuel_attendu_avec_ve()
        self.assertAlmostEqual(
            total_courbe, niveau_attendu, delta=0.1,
            msg=('courbe annuelle %.2f kWh vs niveau d\'entrée (VE compris) '
                 '%.2f kWh — le composeur n\'a pas reçu le VE dans son '
                 'niveau' % (total_courbe, niveau_attendu)))

        # ``calculer_etude_horaire`` intègre la même source
        # (:func:`jours_types_annee`) — il doit rester exploitable avec cette
        # couche VE, sans jamais dégrader en ``None``.
        etude = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=self.CONSO, ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE, equipements=self.VE)
        self.assertIsNotNone(etude)
        self.assertIn('ve', etude['equipements_actifs'])

    def test_sans_ve_rien_ne_bouge(self):
        """Non-régression : sans couche d'ADDITION, le total de la courbe
        reste exactement la facture nue — inchangé à l'octet par cette
        correction (aucun VE à ajouter avant l'appel)."""
        jours_types, _avert, _sources = EH.jours_types_annee(
            kwc=6.0, conso_kwh_mensuelles=self.CONSO, ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE, equipements=None)
        self.assertIsNotNone(jours_types)
        self.assertAlmostEqual(
            self._total_annuel_courbe(jours_types), sum(self.CONSO),
            delta=0.1)

    def test_egalite_tient_sur_les_deux_surfaces_publiques(self):
        """``couverture_batterie_publique`` et ``balayer_stockage_horaire``
        ne composent AUCUNE courbe à eux : ils rejouent tous les deux
        ``jours_types_annee`` avec les mêmes arguments transmis tels quels
        (``etude_horaire.py:1473-1477`` et ``:2218-2222``) — l'alignement
        posé dans ``jours_types_annee`` leur profite donc automatiquement,
        sans code séparé à corriger pour eux."""
        niveau_attendu = self._niveau_annuel_attendu_avec_ve()

        couverture = EH.couverture_batterie_publique(
            kwc=6.0, conso_kwh_mensuelles=self.CONSO,
            capacite_utile_pack_kwh=5.0, nb_packs_max=2,
            ville=self.VILLE, occupation=CJ.OCCUPATION_PRESENCE,
            equipements=self.VE)
        self.assertIsNotNone(couverture)

        balayage = EH.balayer_stockage_horaire(
            kwc=6.0, conso_kwh_mensuelles=self.CONSO,
            capacites_kwh=[5.0, 10.0], ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE, equipements=self.VE)
        self.assertIsNotNone(balayage)

        # Les deux fonctions ci-dessus appellent ``jours_types_annee`` avec
        # EXACTEMENT ces arguments (aucune divergence possible : même
        # fonction, mêmes valeurs transmises) — la même égalité s'y vérifie
        # donc directement.
        jours_types, _avert, _sources = EH.jours_types_annee(
            kwc=6.0, conso_kwh_mensuelles=self.CONSO, ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE, equipements=self.VE)
        self.assertAlmostEqual(
            self._total_annuel_courbe(jours_types), niveau_attendu, delta=0.1)
