"""L-ECO — la silhouette de consommation suit la SAISON et le RAMADAN.

AVANT cette couche, une SEULE silhouette servait les douze mois : ``saison=``
n'activait que les couches d'équipement. Ces tests épinglent les deux
propriétés qui rendent la variation honnête :

1. **AUCUN CHIFFRE N'EST INVENTÉ.** La forme d'hiver est une PERMUTATION de la
   forme d'été (fenêtre de pointe ONEE reculée d'une heure) : mêmes valeurs,
   même somme. La modulation de Ramadan reprend VERBATIM les trois facteurs
   déjà appliqués sous les yeux du client par la page
   (``apps/web/src/lib/proposalCurve.ts``) et re-normalise.
2. **LE NIVEAU NE BOUGE JAMAIS.** Quelle que soit la saison ou la part de
   Ramadan, la journée type somme EXACTEMENT au kWh de la facture du mois : ces
   couches déplacent l'énergie dans la journée, elles n'en fabriquent pas.

Aucune base de données, aucun réseau (Casablanca est dans la table PVGIS de
référence) : ce sont des fonctions pures.
"""
from datetime import date

from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes import ramadan as RM
from apps.ventes.etude_horaire import jours_types_annee

# Une plage de Ramadan de la table, et une date qui tombe DEDANS.
_PLAGE_2028 = date(2028, 2, 11)
# Après la fin de la table (2033) : le moteur doit alors ne rien affirmer.
_HORS_TABLE = date(2050, 6, 1)


class SilhouetteSaisonniereTest(SimpleTestCase):
    """La pointe du soir recule d'une heure l'hiver — et rien d'autre ne bouge."""

    def test_sans_saison_la_forme_est_celle_d_avant(self):
        """Tous les appelants historiques restent BYTE-IDENTIQUES."""
        for cle in CJ.SILHOUETTES_OCCUPATION:
            with self.subTest(occupation=cle):
                attendu = CJ._normaliser_a_un(CJ.SILHOUETTES_OCCUPATION[cle])
                self.assertEqual(CJ.silhouette_occupation(cle), attendu)

    def test_chaque_saison_somme_toujours_a_un(self):
        for cle in CJ.SILHOUETTES_OCCUPATION:
            for saison in ('hiver', 'mi_saison', 'ete'):
                with self.subTest(occupation=cle, saison=saison):
                    forme = CJ.silhouette_occupation(cle, saison=saison)
                    self.assertAlmostEqual(sum(forme), 1.0, places=9)

    def test_ete_et_mi_saison_gardent_la_fenetre_la_plus_tardive(self):
        """La grille ONEE ne publie que deux fenêtres ; la mi-saison prend la
        plus tardive — celle qui croise le MOINS de soleil, donc jamais un
        défaut qui flatterait l'autoconsommation."""
        for cle in CJ.SILHOUETTES_OCCUPATION:
            base = CJ.silhouette_occupation(cle)
            with self.subTest(occupation=cle):
                self.assertEqual(CJ.silhouette_occupation(cle, saison='ete'),
                                 base)
                self.assertEqual(
                    CJ.silhouette_occupation(cle, saison='mi_saison'), base)

    def test_hiver_est_une_permutation_exacte_de_l_ete(self):
        """ZÉRO chiffre nouveau : les mêmes 24 valeurs, dans un autre ordre."""
        for cle in CJ.SILHOUETTES_OCCUPATION:
            ete = CJ.silhouette_occupation(cle, saison='ete')
            hiver = CJ.silhouette_occupation(cle, saison='hiver')
            with self.subTest(occupation=cle):
                self.assertNotEqual(hiver, ete)
                self.assertEqual(sorted(round(v, 12) for v in hiver),
                                 sorted(round(v, 12) for v in ete))
                self.assertAlmostEqual(sum(hiver), sum(ete), places=12)

    def test_hiver_recule_la_pointe_du_soir_d_une_heure(self):
        """Fenêtre ONEE : 18h-23h l'été, 17h-22h l'hiver (one.org.ma)."""
        for cle in CJ.SILHOUETTES_OCCUPATION:
            ete = CJ.silhouette_occupation(cle, saison='ete')
            hiver = CJ.silhouette_occupation(cle, saison='hiver')
            with self.subTest(occupation=cle):
                pointe_ete = max(range(24), key=lambda h: ete[h])
                pointe_hiver = max(range(24), key=lambda h: hiver[h])
                self.assertEqual(pointe_hiver, pointe_ete - 1)

    def test_hors_du_bloc_du_soir_rien_ne_change(self):
        """La journée (nuit, matin, après-midi) est INTACTE : la source ne
        parle que de la fenêtre de pointe, on ne touche donc qu'à elle."""
        for cle in CJ.SILHOUETTES_OCCUPATION:
            ete = CJ.silhouette_occupation(cle, saison='ete')
            hiver = CJ.silhouette_occupation(cle, saison='hiver')
            for heure in range(24):
                if heure in CJ.BLOC_POINTE_SAISONNIER:
                    continue
                with self.subTest(occupation=cle, heure=heure):
                    self.assertAlmostEqual(hiver[heure], ete[heure], places=12)

    def test_le_niveau_facture_est_preserve_dans_chaque_saison(self):
        for saison in ('hiver', 'mi_saison', 'ete'):
            with self.subTest(saison=saison):
                forme = CJ.forme_consommation_kwh(
                    20.0, CJ.OCCUPATION_PRESENCE, saison=saison)
                self.assertAlmostEqual(sum(forme), 20.0, places=6)


class FenetreRamadanTest(SimpleTestCase):
    """La fenêtre est CALCULÉE par date et par GPS, jamais codée en dur."""

    def test_hors_table_on_n_affirme_rien(self):
        self.assertIsNone(RM.plage_ramadan_pour(_HORS_TABLE))
        self.assertIsNone(RM.fenetre_ramadan(_HORS_TABLE))
        self.assertIsNone(RM.part_ramadan_par_mois(_HORS_TABLE))
        self.assertIsNone(CJ.contexte_ramadan_du_mois(_HORS_TABLE))

    def test_une_date_dans_le_ramadan_est_reconnue_comme_telle(self):
        plage, dedans = RM.plage_ramadan_pour(_PLAGE_2028)
        self.assertTrue(dedans)
        self.assertEqual(plage['hijri'], 1449)
        fenetre = RM.fenetre_ramadan(_PLAGE_2028)
        self.assertTrue(fenetre['dedans'])
        self.assertEqual(fenetre['jour_reference'], _PLAGE_2028.isoformat())

    def test_hors_ramadan_on_prend_le_jour_median_de_la_prochaine_plage(self):
        fenetre = RM.fenetre_ramadan(date(2027, 6, 1))
        self.assertFalse(fenetre['dedans'])
        self.assertEqual(fenetre['hijri'], 1449)
        plage = [p for p in RM.RAMADAN_PLAGES if p['hijri'] == 1449][0]
        self.assertGreaterEqual(fenetre['jour_reference'],
                                plage['debut'].isoformat())
        self.assertLessEqual(fenetre['jour_reference'],
                             plage['fin'].isoformat())

    def test_l_iftar_est_servi_dans_le_repere_civil_du_moteur(self):
        """Le pays passe à UTC+0 pendant le Ramadan, la production PVGIS reste
        en heure civile UTC+1 : la bosse d'iftar DOIT être décalée d'une heure,
        sinon elle serait posée en plein soleil et ferait gagner une
        autoconsommation qui n'existe pas."""
        soleil = RM.heures_soleil(_PLAGE_2028, RM.DEFAUT_LAT, RM.DEFAUT_LON,
                                  RM.RAMADAN_FUSEAU_UTC)
        self.assertIsNotNone(soleil)
        _lever, coucher = soleil
        fenetre = RM.fenetre_ramadan(_PLAGE_2028)
        self.assertAlmostEqual(
            fenetre['iftar_h'],
            coucher / 60.0 + RM.DECALAGE_FUSEAU_VERS_CIVIL_H, places=9)
        self.assertLess(fenetre['imsak_h'], fenetre['iftar_h'])

    def test_les_parts_mensuelles_comptent_les_vrais_jours(self):
        """Ramadan 1449 = 28/01/2028 → 25/02/2028 : 4 jours en janvier,
        25 en février, zéro ailleurs."""
        parts = RM.part_ramadan_par_mois(_PLAGE_2028)
        self.assertAlmostEqual(parts[0], 4 / 31.0, places=9)
        self.assertAlmostEqual(parts[1], 25 / 28.0, places=9)
        self.assertEqual([round(p, 9) for p in parts[2:]], [0.0] * 10)

    def test_le_contexte_ne_porte_que_les_mois_concernes(self):
        contexte = CJ.contexte_ramadan_du_mois(_PLAGE_2028)
        self.assertEqual(sorted(contexte), [1, 2])
        for bloc in contexte.values():
            self.assertGreater(bloc['part'], 0)
            self.assertIn('imsak_h', bloc['fenetre'])


class SilhouetteRamadanTest(SimpleTestCase):
    """Le Ramadan DÉPLACE l'énergie ; il n'en crée ni n'en supprime."""

    def _contexte(self, part):
        fenetre = RM.fenetre_ramadan(_PLAGE_2028)
        return {'part': part, 'fenetre': fenetre}

    def test_part_nulle_ne_change_rien(self):
        base = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver')
        for ramadan in (None, {}, self._contexte(0.0), {'part': 0.4}):
            with self.subTest(ramadan=ramadan):
                self.assertEqual(
                    CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver',
                                       ramadan=ramadan),
                    base)

    def test_un_mois_entierement_en_ramadan_change_la_forme(self):
        base = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver')
        jeune = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver',
                                   ramadan=self._contexte(1.0))
        self.assertNotEqual(jeune, base)
        self.assertAlmostEqual(sum(jeune), 1.0, places=9)

    def test_la_bosse_d_iftar_tombe_bien_a_l_heure_de_la_rupture(self):
        fenetre = RM.fenetre_ramadan(_PLAGE_2028)
        heure_iftar = int(fenetre['iftar_h'])
        base = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver')
        jeune = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver',
                                   ramadan=self._contexte(1.0))
        self.assertGreater(jeune[heure_iftar], base[heure_iftar])

    def test_une_part_partielle_reste_entre_les_deux(self):
        """La journée type d'un mois à moitié en Ramadan est la MOYENNE
        pondérée par les jours réels, pas un troisième comportement."""
        base = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver')
        jeune = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver',
                                   ramadan=self._contexte(1.0))
        moitie = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver',
                                    ramadan=self._contexte(0.5))
        self.assertAlmostEqual(sum(moitie), 1.0, places=9)
        for heure in range(24):
            borne_basse = min(base[heure], jeune[heure])
            borne_haute = max(base[heure], jeune[heure])
            with self.subTest(heure=heure):
                self.assertGreaterEqual(moitie[heure], borne_basse - 1e-12)
                self.assertLessEqual(moitie[heure], borne_haute + 1e-12)

    def test_le_niveau_facture_est_preserve(self):
        forme = CJ.forme_consommation_kwh(
            18.5, CJ.OCCUPATION_ABSENCE, saison='hiver',
            ramadan=self._contexte(1.0))
        self.assertAlmostEqual(sum(forme), 18.5, places=6)

    def test_une_fenetre_illisible_retombe_sur_la_forme_ordinaire(self):
        """Jamais d'exception, jamais un Ramadan inventé."""
        base = CJ.silhouette_jour(CJ.OCCUPATION_PRESENCE, saison='hiver')
        for fenetre in ({}, {'imsak_h': None, 'iftar_h': 19.0},
                        {'imsak_h': float('nan'), 'iftar_h': 19.0}, 'texte'):
            with self.subTest(fenetre=fenetre):
                self.assertEqual(
                    CJ.silhouette_jour(
                        CJ.OCCUPATION_PRESENCE, saison='hiver',
                        ramadan={'part': 1.0, 'fenetre': fenetre}),
                    base)


class MoteurIntegreLaVariationTest(SimpleTestCase):
    """Le jour type du moteur porte RÉELLEMENT la saison et le Ramadan."""

    CONSO = [420.0] * 12

    def _jours(self, jour_reference):
        jours, _avertissements, _sources = jours_types_annee(
            kwc=5.0, conso_kwh_mensuelles=self.CONSO, ville='Casablanca',
            occupation=CJ.OCCUPATION_PRESENCE, jour_reference=jour_reference)
        return {j['mois']: j for j in jours}

    def test_les_mois_d_hiver_et_d_ete_n_ont_plus_la_meme_silhouette(self):
        """À consommation mensuelle ÉGALE (420 kWh partout), janvier et juillet
        doivent quand même différer de forme : c'est exactement ce que le
        moteur ne faisait pas avant."""
        jours = self._jours(date(2026, 7, 1))
        janvier = jours[1]['conso_24h']
        juillet = jours[7]['conso_24h']
        self.assertAlmostEqual(sum(janvier), sum(juillet), places=6)
        self.assertNotEqual([round(v, 6) for v in janvier],
                            [round(v, 6) for v in juillet])

    def test_le_ramadan_ne_touche_que_les_mois_de_sa_plage(self):
        jours = self._jours(_PLAGE_2028)
        temoin = self._jours(_HORS_TABLE)
        for mois in range(1, 13):
            avec = [round(v, 6) for v in jours[mois]['conso_24h']]
            sans = [round(v, 6) for v in temoin[mois]['conso_24h']]
            with self.subTest(mois=mois):
                if mois in (1, 2):
                    self.assertNotEqual(avec, sans)
                else:
                    self.assertEqual(avec, sans)

    def test_aucun_kwh_n_est_cree_ni_perdu(self):
        for reference in (_PLAGE_2028, _HORS_TABLE):
            jours = self._jours(reference)
            for mois, jour in jours.items():
                with self.subTest(reference=reference, mois=mois):
                    self.assertAlmostEqual(sum(jour['conso_24h']),
                                           jour['conso_jour_kwh'], places=6)
