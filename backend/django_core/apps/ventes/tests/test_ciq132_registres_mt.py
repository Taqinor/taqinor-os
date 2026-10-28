"""CIQ132 — industriel MT : la courbe de charge se construit depuis les
registres pointe / pleines / creuses de la facture, sur les plages OFFICIELLES
ONEE « Tarif Général (MT) » (``tarifs_officiels.poste_horaire``, heures GMT),
et contrôle les équipes déclarées. Module pur (aucune base).
"""
import io
import tokenize
import unittest
from pathlib import Path

from apps.parametres.tarifs_officiels import poste_horaire
from apps.ventes.domain import etude_ci
from apps.ventes.moteur_ci.charge import courbe_declaree, courbe_registres_mt
from apps.ventes.tests.test_ciq122_cas_reference import _etudier

RACINE = Path(__file__).resolve().parent.parent
ANNEE = 2025
POSTES = ('pointe', 'pleines', 'creuses')


def _registres(pointe=1800, pleines=9000, creuses=3200):
    return [{'pointe_kwh': pointe, 'pleines_kwh': pleines + 50 * m,
             'creuses_kwh': creuses} for m in range(12)]


def _par_poste(jours, mois):
    totaux = dict.fromkeys(POSTES, 0.0)
    for jt in jours:
        if jt['mois'] != mois:
            continue
        for h, valeur in enumerate(jt['charge_kwh']):
            totaux[poste_horaire(mois, h)] += valeur * jt['nb_jours']
    return totaux


class RegistresMtTests(unittest.TestCase):

    def test_somme_par_poste_egale_au_registre(self):
        registres = _registres()
        jours, prov, _al = courbe_registres_mt(
            {'jours_ouverts': [True] * 6 + [False], 'equipes': '2x8', 'debut_equipe_h': 6},
            registres, annee_reference=ANNEE)
        self.assertEqual(prov['methode'], 'registres_mt')
        self.assertEqual(prov['niveau_donnees'], 'declare')
        for mois in range(1, 13):
            totaux = _par_poste(jours, mois)
            for p in POSTES:
                self.assertAlmostEqual(totaux[p], registres[mois - 1]['%s_kwh' % p], delta=1e-6)

    def test_jours_fermes_au_talon_des_heures_creuses(self):
        jours, prov, _al = courbe_registres_mt(
            {'jours_ouverts': [True] * 5 + [False, False]}, _registres(),
            annee_reference=ANNEE)
        ferme = next(j for j in jours if j['mois'] == 1 and j['type_jour'] == 'ferme')
        self.assertEqual(len(set(round(v, 9) for v in ferme['charge_kwh'])), 1)
        self.assertAlmostEqual(ferme['charge_kwh'][0], prov['talon']['valeur']['kw_par_mois'][0],
                               places=5)

    def test_1x8_avec_creuses_superieures_aux_pleines_drapeau(self):
        _j, _p, alertes = courbe_registres_mt(
            {'jours_ouverts': [True] * 5 + [False, False], 'equipes': '1x8',
             'debut_equipe_h': 8}, _registres(pleines=2000, creuses=9000),
            annee_reference=ANNEE)
        self.assertIn('incoherence_equipes_registres', [a['code'] for a in alertes])
        self.assertTrue(all(a['niveau'] != 'bloquant' for a in alertes))

    def test_3x8_sans_creuses_drapeau(self):
        _j, _p, alertes = courbe_registres_mt(
            {'jours_ouverts': [True] * 7, 'equipes': '3x8', 'debut_equipe_h': 6},
            _registres(creuses=0), annee_reference=ANNEE)
        self.assertIn('incoherence_equipes_registres', [a['code'] for a in alertes])

    def test_sans_registres_methode_declare_inchangee(self):
        jours, prov, _al = courbe_declaree(
            {'jours_ouverts': [True] * 6 + [False], 'plages': {'ouvre': [[7, 19]]},
             'talon': {'kw': 2}}, [10000] * 12, annee_reference=ANNEE)
        self.assertEqual(prov['methode'], 'declare')
        e = _etudier(mode='industriel', tension='mt', tarif={'contrat': 'mt_general'},
                     rythme={'jours_ouverts': [True] * 6 + [False], 'plages': {'ouvre': [[7, 19]]},
                             'talon': {'kw': 2}}, taille_explicite_kwc=50)
        self.assertEqual(e['profil_charge']['methode'], 'declare')

    def test_orchestrateur_prend_les_registres(self):
        e = _etudier(mode='industriel', tension='mt', tarif={'contrat': 'mt_general'},
                     consommation={'kwh_mensuels': None, 'registres_mt': _registres()},
                     rythme={'jours_ouverts': [True] * 6 + [False], 'equipes': '2x8',
                             'debut_equipe_h': 6},
                     taille_explicite_kwc=50)
        self.assertEqual(e['profil_charge']['methode'], 'registres_mt')
        conso = sum(m['consommation_kwh'] for m in e['bilan']['par_mois'])
        attendu = sum(sum(r['%s_kwh' % p] for p in POSTES) for r in _registres())
        self.assertAlmostEqual(conso, attendu, delta=12)

    def test_mois_sans_jour_ouvert_les_registres_ne_se_perdent_pas(self):
        # CLD5 — juillet fermé en entier : creuses 1 000 / pointe 2 000 /
        # pleines 3 000 se répartissent sur les heures de CHAQUE poste.
        registres = [{'pointe_kwh': 2000, 'pleines_kwh': 3000, 'creuses_kwh': 1000}
                     for _ in range(12)]
        rythme = {'jours_ouverts': [True] * 5 + [False, False],
                  'fermetures': [{'du': '%d-07-01' % ANNEE, 'au': '%d-07-31' % ANNEE}]}
        jours, _p, alertes = courbe_registres_mt(rythme, registres, annee_reference=ANNEE,
                                                 feries=[])
        totaux = _par_poste(jours, 7)
        self.assertAlmostEqual(sum(totaux.values()), 6000, delta=1e-6)
        for poste, attendu in (('pointe', 2000), ('pleines', 3000), ('creuses', 1000)):
            self.assertAlmostEqual(totaux[poste], attendu, delta=1e-6)
        alerte = next(a for a in alertes if a['code'] == 'registre_hors_ouverture')
        self.assertTrue(alerte['interne'])

    def test_aucun_jour_ouvert_toute_l_annee_somme_des_registres(self):
        registres = [{'pointe_kwh': 2000, 'pleines_kwh': 3000, 'creuses_kwh': 1000}
                     for _ in range(12)]
        jours, _p, alertes = courbe_registres_mt({'jours_ouverts': [False] * 7}, registres,
                                                 annee_reference=ANNEE, feries=[])
        total = sum(jt['nb_jours'] * sum(jt['charge_kwh']) for jt in jours)
        self.assertAlmostEqual(total, 72000, delta=1e-5)
        self.assertEqual(sum(1 for a in alertes if a['code'] == 'registre_hors_ouverture'), 12)

    def test_mois_mixte_nuit_forte_energie_conservee(self):
        # CLD14 — creuses fortes, jours fermés sam-dim : le talon plat est
        # plafonné par le plus petit registre rapporté à ses heures ; la courbe
        # ne crée aucune énergie (avant : +17,1 %/an).
        registres = [{'pointe_kwh': 2000, 'pleines_kwh': 10000, 'creuses_kwh': 40000}
                     for _ in range(12)]
        rythme = {'jours_ouverts': [True] * 5 + [False, False]}
        jours, prov, alertes = courbe_registres_mt(rythme, registres, annee_reference=ANNEE,
                                                   feries=[])
        total = sum(jt['nb_jours'] * sum(jt['charge_kwh']) for jt in jours)
        self.assertAlmostEqual(total, 624000, delta=1e-4)
        for mois in range(1, 13):
            totaux = _par_poste(jours, mois)
            for p in POSTES:
                self.assertAlmostEqual(totaux[p], registres[mois - 1]['%s_kwh' % p], delta=1e-6)
        plafonnees = [a for a in alertes if a['code'] == 'talon_plafonne_au_registre']
        self.assertEqual(len(plafonnees), 12)
        self.assertTrue(all(a['interne'] for a in plafonnees))
        self.assertFalse([a for a in alertes if a['code'] == 'talon_au_dela_du_registre'])
        # talon plat gardé : un seul niveau sur 24 h des jours fermés
        ferme = next(j for j in jours if j['mois'] == 1 and j['type_jour'] == 'ferme')
        self.assertEqual(len(set(round(v, 9) for v in ferme['charge_kwh'])), 1)

    def test_mois_mixte_pointe_nulle_talon_zero_dit(self):
        registres = [{'pointe_kwh': 0, 'pleines_kwh': 30000, 'creuses_kwh': 9000}
                     for _ in range(12)]
        jours, prov, alertes = courbe_registres_mt(
            {'jours_ouverts': [True] * 5 + [False, False]}, registres,
            annee_reference=ANNEE, feries=[])
        total = sum(jt['nb_jours'] * sum(jt['charge_kwh']) for jt in jours)
        self.assertAlmostEqual(total, 12 * 39000, delta=1e-4)
        ferme = next(j for j in jours if j['mois'] == 1 and j['type_jour'] == 'ferme')
        self.assertEqual(max(ferme['charge_kwh']), 0.0)
        alerte = next(a for a in alertes if a['code'] == 'talon_plafonne_au_registre')
        self.assertIn('pointe', alerte['message'])
        self.assertIn('0', alerte['message'])

    def test_aucun_utc_plus_un_code(self):
        # Le code (commentaires et chaînes exclus) ne porte aucun décalage codé.
        for chemin in (RACINE / 'moteur_ci' / 'charge.py', Path(etude_ci.__file__)):
            jetons = tokenize.generate_tokens(io.StringIO(chemin.read_text(encoding='utf-8')).readline)
            code = ' '.join(t.string for t in jetons
                            if t.type not in (tokenize.COMMENT, tokenize.STRING))
            self.assertNotIn('UTC', code.upper(), chemin)


if __name__ == '__main__':
    unittest.main()
