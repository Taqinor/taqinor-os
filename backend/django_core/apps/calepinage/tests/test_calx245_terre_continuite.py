"""CALX245 — la continuité MESURÉE de l'existant dans la check-list de terre.

CE QUE CE FICHIER GARDE
-----------------------
1. **Trois lignes SAISIES de plus**, chacune citant la référence que le noyau
   cite déjà (NF C 15-100 §542 pour la prise, §542.4 pour
   l'équipotentialité) : point et date de mesure de la prise, continuité
   structure ↔ barrette, continuité barrette ↔ masses des coffrets.
2. **Une mesure saisie SANS sa date est REFUSÉE en nommant le champ** — une
   mesure sans date n'est opposable à personne.
3. **Aucune saisie ⇒ la garde de publication refuse comme aujourd'hui** :
   CALX245 ajoute des lignes, il ne change RIEN à la règle de publication.
4. **Aucune résistance n'est jamais inventée** : sans saisie, la ligne dit
   « non mesurée », et aucune valeur cible n'est ajoutée — les seuils restent
   ceux que le noyau cite.

Aucune base de données : le noyau pur.

Run :
    python manage.py test apps.calepinage.tests.test_calx245_terre_continuite
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import temperatures_site
from apps.calepinage.services.norme import norme_applicable
from apps.calepinage.services.terre import (
    LIGNES_MESUREES, TerreInvalide, checklist_terre, garde_terre,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}
NORME_FR = norme_applicable({'imagerie': {'pays': 'fr'},
                             'norme_electrique': {}})
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-A', 'geometry': {'count': 12, 'azimuthDeg': 180.0,
                                    'tiltDeg': 15.0}}]}

CODES_MESURES = [code for code, *_reste in LIGNES_MESUREES]

#: Les trois mesures SAISIES, chacune avec sa date — valeurs du cas de test,
#: aucune n'est posée par le code du dépôt.
SAISIE_COMPLETE = {
    'point_mesure_prise': 'barrette de coupure, local technique',
    'date_mesure_prise': '2026-09-18',
    'continuite_structure_barrette_ohm': 0.12,
    'date_continuite_structure_barrette': '2026-09-18',
    'continuite_barrette_coffrets_ohm': 0.08,
    'date_continuite_barrette_coffrets': '2026-09-18',
}


def _conception(prise_vendue=False):
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        inclure_prise_terre=prise_vendue)


def _lignes(checklist):
    return {ligne['code']: ligne for ligne in checklist['lignes']}


class TroisLignesSaisiesTest(SimpleTestCase):
    """Les trois mesures sont publiées telles quelles, avec leur référence."""

    def test_les_trois_lignes_saisies_sont_publiees(self):
        lignes = _lignes(checklist_terre(
            _conception(), decisions=dict(SAISIE_COMPLETE), norme=NORME_FR))

        for code in CODES_MESURES:
            self.assertTrue(lignes[code]['fait'], code)
            self.assertIn('2026-09-18', lignes[code]['valeur'], code)

    def test_chaque_ligne_cite_la_reference_du_noyau(self):
        lignes = _lignes(checklist_terre(
            _conception(), decisions=dict(SAISIE_COMPLETE), norme=NORME_FR))

        self.assertIn('§542', lignes['point_date_mesure_prise']['reference'])
        self.assertIn('542.4',
                      lignes['continuite_structure_barrette']['reference'])
        self.assertIn('542.4',
                      lignes['continuite_barrette_coffrets']['reference'])

    def test_les_ohms_sont_publies_en_francais_et_datees(self):
        lignes = _lignes(checklist_terre(
            _conception(), decisions=dict(SAISIE_COMPLETE), norme=NORME_FR))

        self.assertIn('0,12 Ω',
                      lignes['continuite_structure_barrette']['valeur'])
        self.assertIn('mesurés le 2026-09-18',
                      lignes['continuite_barrette_coffrets']['valeur'])

    def test_les_mesures_saisies_sont_publiees_telles_quelles(self):
        mesures = checklist_terre(
            _conception(), decisions=dict(SAISIE_COMPLETE),
            norme=NORME_FR)['mesures_saisies']

        self.assertEqual(mesures['continuite_structure_barrette'],
                         {'valeur': 0.12, 'date': '2026-09-18'})

    def test_les_quatre_lignes_historiques_gardent_leur_rang(self):
        codes = [ligne['code'] for ligne in checklist_terre(
            _conception(), norme=NORME_FR)['lignes']]

        self.assertEqual(codes[:4], ['liaison_equipotentielle',
                                     'section_conducteur', 'piquet_barrette',
                                     'mesure_continuite'])
        self.assertEqual(codes[4:], CODES_MESURES)


class RefusSansDateTest(SimpleTestCase):
    """Une mesure sans date est refusée — et le champ fautif est NOMMÉ."""

    def test_continuite_sans_date_refusee(self):
        with self.assertRaises(TerreInvalide) as refus:
            checklist_terre(
                _conception(), norme=NORME_FR,
                decisions={'continuite_structure_barrette_ohm': 0.12})

        self.assertEqual(refus.exception.champ,
                         'terre.date_continuite_structure_barrette')
        self.assertIn('date', str(refus.exception))

    def test_point_de_mesure_sans_date_refuse(self):
        with self.assertRaises(TerreInvalide) as refus:
            checklist_terre(_conception(), norme=NORME_FR,
                            decisions={'point_mesure_prise': 'barrette'})

        self.assertEqual(refus.exception.champ, 'terre.date_mesure_prise')

    def test_date_illisible_refusee_en_nommant_le_champ(self):
        with self.assertRaises(TerreInvalide) as refus:
            checklist_terre(
                _conception(), norme=NORME_FR,
                decisions={'continuite_barrette_coffrets_ohm': 0.08,
                           'date_continuite_barrette_coffrets': 'hier'})

        self.assertEqual(refus.exception.champ,
                         'terre.date_continuite_barrette_coffrets')

    def test_continuite_illisible_refusee_en_nommant_le_champ(self):
        with self.assertRaises(TerreInvalide) as refus:
            checklist_terre(
                _conception(), norme=NORME_FR,
                decisions={'continuite_structure_barrette_ohm': 'faible',
                           'date_continuite_structure_barrette':
                               '2026-09-18'})

        self.assertEqual(refus.exception.champ,
                         'terre.continuite_structure_barrette_ohm')


class AucuneSaisieTest(SimpleTestCase):
    """Sans saisie : rien d'inventé, et la garde refuse comme aujourd'hui."""

    def test_sans_saisie_la_garde_refuse_comme_aujourd_hui(self):
        checklist = checklist_terre(_conception(prise_vendue=False),
                                    norme=NORME_FR)

        with self.assertRaises(TerreInvalide) as refus:
            garde_terre(checklist)

        self.assertEqual(refus.exception.champ,
                         'terre.justification_continuite')

    def test_les_trois_lignes_restent_presentes_et_non_faites(self):
        lignes = _lignes(checklist_terre(_conception(), norme=NORME_FR))

        for code in CODES_MESURES:
            self.assertIn(code, lignes)
            self.assertFalse(lignes[code]['fait'], code)
            self.assertIn('non mesurée', lignes[code]['valeur'], code)

    def test_aucune_valeur_cible_n_est_ajoutee(self):
        lignes = _lignes(checklist_terre(_conception(), norme=NORME_FR))

        for code in CODES_MESURES:
            # Ni seuil, ni « ≤ », ni ordre de grandeur suggéré : ce module
            # publie ce qui a été mesuré, il ne propose aucune cible.
            self.assertNotIn('≤', lignes[code]['valeur'], code)
            self.assertNotIn('Ω', lignes[code]['valeur'], code)

    def test_les_mesures_saisies_sont_vides_sans_saisie(self):
        mesures = checklist_terre(_conception(),
                                  norme=NORME_FR)['mesures_saisies']

        for code in CODES_MESURES:
            self.assertEqual(mesures[code], {'valeur': None, 'date': None})

    def test_les_trois_mesures_seules_ne_dispensent_pas_de_la_justification(
            self):
        # La continuité MESURÉE ne remplace pas la justification cochée :
        # CALX245 documente, il ne dé-garde rien.
        checklist = checklist_terre(_conception(prise_vendue=False),
                                    decisions=dict(SAISIE_COMPLETE),
                                    norme=NORME_FR)

        with self.assertRaises(TerreInvalide):
            garde_terre(checklist)
