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

    def test_aucun_utc_plus_un_code(self):
        # Le code (commentaires et chaînes exclus) ne porte aucun décalage codé.
        for chemin in (RACINE / 'moteur_ci' / 'charge.py', Path(etude_ci.__file__)):
            jetons = tokenize.generate_tokens(io.StringIO(chemin.read_text(encoding='utf-8')).readline)
            code = ' '.join(t.string for t in jetons
                            if t.type not in (tokenize.COMMENT, tokenize.STRING))
            self.assertNotIn('UTC', code.upper(), chemin)


if __name__ == '__main__':
    unittest.main()
