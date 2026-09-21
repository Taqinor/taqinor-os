# -*- coding: utf-8 -*-
"""CAD165 — quatre correctifs du moteur horaire, tous visibles sur le chiffre client.

Audit L3 du 21/09/2026, section CAD-M. Cette tâche CHANGE des chiffres déjà
envoyés à des clients : chaque correctif porte donc ici son test, ET son test de
NON-RÉGRESSION (ce qui ne doit pas bouger).

1. **Le créneau déclaré sans chargeur n'est plus ignoré** (CAD171). La fenêtre
   n'était resserrée que lorsque la puissance du chargeur était connue : « je
   recharge le jour » ne changeait pas un kWh. Elle s'étale désormais sur TOUT
   le créneau déclaré — aucune durée inventée, la réponse enfin respectée.
2. **Le créneau « jour » se cale au milieu de la journée.** Quand le chargeur
   est connu, la recharge n'occupe qu'une partie du créneau ; elle était posée
   sur ses PREMIÈRES heures, donc à 9 h, avant le gros de la production d'un
   champ plein sud.
3. **Un « non » sur le chauffe-eau empêche enfin sa couche.** La paire
   puissance + créneau composait sans jamais regarder le booléen, contrairement
   aux trois autres couches. ``None`` (jamais posée) garde le comportement
   d'avant : vide ≠ Non, et un lead jamais interrogé garde son chiffre.
4. **L'autoconsommation SANS batterie est bornée comme celle AVEC.** Seule
   l'option avec batterie l'était : l'option sans pouvait annoncer une
   autoconsommation supérieure à la consommation de référence du client.

Tous ces tests sont des ``SimpleTestCase`` : ils n'interrogent que des
fonctions pures (composition des couches, moteur horaire) — aucune base.
"""
from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes import etude_horaire as EH


def _ve(**extra):
    base = {'voiture_electrique': True, 've_km_semaine': 300}
    base.update(extra)
    return base


class CreneauDeclareSansChargeur(SimpleTestCase):
    """Correctif 1 (CAD171) — la réponse « je recharge le jour » compte."""

    def test_le_creneau_jour_seul_etale_la_recharge_sur_TOUT_le_creneau(self):
        couches = CJ.composer_equipements(_ve(ve_creneau='jour'))
        self.assertEqual(couches['ve']['heures'],
                         list(CJ.VE_CRENEAUX['jour']))
        self.assertIn('equip_ve_creneau', couches['ve']['source'])

    def test_avant_le_correctif_c_etait_la_fenetre_de_NUIT_par_defaut(self):
        """Le défaut exact que ce correctif ferme : sans chargeur, la fenêtre
        21h-6h survivait à la réponse du client."""
        couches = CJ.composer_equipements(_ve(ve_creneau='jour'))
        self.assertNotEqual(couches['ve']['heures'], list(CJ.VE_HEURES))

    def test_le_creneau_soir_seul_est_respecte_aussi(self):
        couches = CJ.composer_equipements(_ve(ve_creneau='soir'))
        self.assertEqual(couches['ve']['heures'],
                         list(CJ.VE_CRENEAUX['soir']))

    def test_SANS_creneau_ni_chargeur_rien_ne_bouge(self):
        """Non-régression : un lead qui n'a répondu ni l'un ni l'autre garde
        EXACTEMENT la fenêtre heures-creuses d'avant."""
        couches = CJ.composer_equipements(_ve())
        self.assertEqual(couches['ve']['heures'], list(CJ.VE_HEURES))
        self.assertNotIn('equip_ve_creneau', couches['ve']['source'])

    def test_l_energie_journaliere_ne_change_pas_avec_le_creneau(self):
        """Seule la RÉPARTITION bouge : les kWh/jour restent ceux de la
        conversion ADEME, identiques dans les deux cas."""
        sans = CJ.composer_equipements(_ve())['ve']['kwh_jour']
        avec = CJ.composer_equipements(_ve(ve_creneau='jour'))['ve']['kwh_jour']
        self.assertEqual(sans, avec)


class CreneauJourCaleSurLeMilieuDeLaJournee(SimpleTestCase):
    """Correctif 2 — la recharge « jour » ne commence plus à 9 h."""

    def _heures(self, chargeur_kw, creneau='jour', km=70):
        couches = CJ.composer_equipements(
            _ve(ve_km_semaine=km, ve_chargeur_kw=chargeur_kw,
                ve_creneau=creneau))
        return couches['ve']['heures']

    def test_la_fenetre_retenue_est_centree_dans_le_creneau_jour(self):
        fenetre = CJ.VE_CRENEAUX['jour']
        heures = self._heures(chargeur_kw=3.7)
        n = len(heures)
        self.assertLess(n, len(fenetre))
        debut = (len(fenetre) - n) // 2
        self.assertEqual(heures, list(fenetre[debut:debut + n]))

    def test_elle_ne_commence_plus_a_la_PREMIERE_heure_du_creneau(self):
        """Le défaut exact : la recharge tombait à 9 h, avant le gros de la
        production d'un champ plein sud."""
        heures = self._heures(chargeur_kw=3.7)
        self.assertNotEqual(heures[0], CJ.VE_CRENEAUX['jour'][0])

    def test_elle_reste_ENTIEREMENT_dans_le_creneau_declare(self):
        """Aucune heure inventée : la fenêtre ne déborde jamais du créneau."""
        for chargeur in (2.3, 3.7, 7.4, 11.0):
            heures = self._heures(chargeur_kw=chargeur)
            self.assertTrue(set(heures) <= set(CJ.VE_CRENEAUX['jour']),
                            f'{chargeur} kW : {heures}')

    def test_la_NUIT_garde_ses_premieres_heures(self):
        """Non-régression : il n'y a pas de soleil à viser la nuit — le
        comportement d'avant est conservé tel quel."""
        heures = self._heures(chargeur_kw=3.7, creneau='nuit')
        fenetre = CJ.VE_CRENEAUX['nuit']
        self.assertEqual(heures, list(fenetre[:len(heures)]))

    def test_le_SOIR_garde_ses_premieres_heures(self):
        heures = self._heures(chargeur_kw=7.4, creneau='soir')
        fenetre = CJ.VE_CRENEAUX['soir']
        self.assertEqual(heures, list(fenetre[:len(heures)]))


class LeChauffeEauEstGateParSonBooleen(SimpleTestCase):
    """Correctif 3 — répondre « non » empêche enfin la couche."""

    PAIRE = {'chauffe_eau_kw': 2.2, 'chauffe_eau_creneau': 'nuit'}

    def test_un_NON_explicite_supprime_la_couche(self):
        couches = CJ.composer_equipements(
            dict(self.PAIRE, chauffe_eau_electrique=False))
        self.assertNotIn('chauffe_eau', couches)

    def test_un_OUI_la_compose_comme_avant(self):
        couches = CJ.composer_equipements(
            dict(self.PAIRE, chauffe_eau_electrique=True))
        self.assertIn('chauffe_eau', couches)
        self.assertEqual(couches['chauffe_eau']['heures'],
                         list(CJ.CHAUFFE_EAU_CRENEAUX['nuit']))

    def test_une_question_JAMAIS_POSEE_ne_change_AUCUN_chiffre(self):
        """Non-régression, et c'est le cœur du garde-fou de cette tâche :
        ``None`` veut dire « la question n'a pas été posée » (vide ≠ Non).
        Un lead jamais interrogé garde exactement la couche qu'il avait."""
        couches = CJ.composer_equipements(dict(self.PAIRE))
        self.assertIn('chauffe_eau', couches)

    def test_le_NON_ne_touche_a_AUCUNE_autre_couche(self):
        entree = dict(self.PAIRE, chauffe_eau_electrique=False,
                      piscine=True, piscine_pompe_kw=1.1)
        couches = CJ.composer_equipements(entree)
        self.assertNotIn('chauffe_eau', couches)
        self.assertIn('piscine', couches)


class AutoconsommationSansBatterieBornee(SimpleTestCase):
    """Correctif 4 — l'autoconsommation ne dépasse JAMAIS la référence.

    Le cas mesuré par l'audit fait entrer une grosse couche véhicule
    électrique : elle s'AJOUTE à la courbe (mode addition) alors que la
    consommation de référence publiée reste la facture. Sans borne, l'option
    SANS batterie pouvait annoncer plus d'autoconsommation que de
    consommation."""

    VILLE = 'Casablanca'
    CONSO = [600.0] * 12
    #: Couche VE volontairement lourde, sur les heures de soleil : c'est la
    #: combinaison qui faisait déborder le chiffre.
    VE_LOURD = {'ve': {'kwh_jour': 30.0, 'heures': list(range(9, 18)),
                       'saisons': None, 'mode': 'addition',
                       'source': 'test'}}

    def _etude(self, **extra):
        return EH.calculer_etude_horaire(
            kwc=20.0, conso_kwh_mensuelles=self.CONSO, ville=self.VILLE,
            equipements=self.VE_LOURD, **extra)

    def test_l_autoconsommation_ne_depasse_jamais_la_consommation(self):
        etude = self._etude()
        self.assertIsNotNone(etude)
        for mois in etude['mois']:
            self.assertLessEqual(
                round(mois['autoconsomme_sans_kwh'], 6),
                round(mois['consommation_kwh'], 6),
                f"mois {mois['mois']}")
        self.assertLessEqual(
            round(etude['annuel']['autoconsomme_sans_kwh'], 6),
            round(etude['annuel']['consommation_kwh'], 6))

    def test_elle_ne_depasse_jamais_la_production_non_plus(self):
        etude = self._etude()
        for mois in etude['mois']:
            self.assertLessEqual(
                round(mois['autoconsomme_sans_kwh'], 6),
                round(mois['production_kwh'], 6),
                f"mois {mois['mois']}")

    def test_l_option_AVEC_batterie_reste_bornee_elle_aussi(self):
        etude = self._etude(batterie_kwh_utile=10.0)
        for mois in etude['mois']:
            self.assertLessEqual(
                round(mois['autoconsomme_avec_kwh'], 6),
                round(mois['consommation_kwh'], 6),
                f"mois {mois['mois']}")

    def test_avec_reste_toujours_au_moins_egal_a_SANS(self):
        """La borne ne doit pas inverser l'ordre des deux options."""
        etude = self._etude(batterie_kwh_utile=10.0)
        for mois in etude['mois']:
            self.assertGreaterEqual(
                round(mois['autoconsomme_avec_kwh'], 6),
                round(mois['autoconsomme_sans_kwh'], 6),
                f"mois {mois['mois']}")

    def test_un_cas_ordinaire_n_est_PAS_touche_par_la_borne(self):
        """Non-régression : sans couche qui déborde, la borne ne mord pas et
        les surplus/imports restent cohérents avec l'autoconsommation."""
        etude = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=self.CONSO, ville=self.VILLE)
        self.assertIsNotNone(etude)
        for mois in etude['mois']:
            self.assertAlmostEqual(
                mois['import_sans_kwh'],
                max(0.0, mois['consommation_kwh']
                    - mois['autoconsomme_sans_kwh']),
                places=6)
