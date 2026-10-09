"""Garde du résolveur de tables de parcours (``core/parcours.py``, METHODE v3 §D.1).

Sans base ni Django : des chemins et du texte. Les tables réelles (PA2, PA5, PA6, PA7…)
ont chacune leur garde chez leur pilote ; ici on prouve le résolveur lui-même.
"""

import unittest

from core import parcours


def _etape_complete(**extra):
    base = {
        'id': 'E1',
        'nom': 'Étape de preuve',
        'proprietaire': 'deploy',
        'declencheur': {'type': 'evenement', 'source': 'core/parcours.py::resoudre_symbole'},
        'fonction_entree': 'core/parcours.py::problemes_de_l_etape',
        'checkpoint': {'modifiable': False, 'champs': [], 'persistance': 'core/parcours.py::charger_table'},
        'regle_aval': ['reference'],
    }
    base.update(extra)
    return base


class ResolutionSymboleTests(unittest.TestCase):
    def test_fichier_seul_et_symbole_de_module(self):
        self.assertEqual(parcours.resoudre_symbole('core/parcours.py'), (True, ''))
        self.assertEqual(parcours.resoudre_symbole('core/parcours.py::REGLES_AVAL'), (True, ''))
        self.assertEqual(parcours.resoudre_symbole('backend/django_core/core/parcours.py::etapes'), (True, ''))

    def test_methode_de_classe_et_symbole_absent(self):
        ok, motif = parcours.resoudre_symbole('core/tests/test_parcours.py::ResolutionSymboleTests.test_methode_de_classe_et_symbole_absent')
        self.assertTrue(ok, motif)
        ok, motif = parcours.resoudre_symbole('core/parcours.py::symbole_qui_n_existe_pas')
        self.assertFalse(ok)
        self.assertIn('introuvable', motif)
        ok, motif = parcours.resoudre_symbole('core/nulle_part.py::x')
        self.assertFalse(ok)
        self.assertIn('fichier introuvable', motif)

    def test_fichier_non_python_resolu_par_le_texte(self):
        ok, motif = parcours.resoudre_symbole('frontend/src/features/crm/relances/parcours_suivi.json::legende_suite')
        self.assertTrue(ok, motif)
        ok, _ = parcours.resoudre_symbole('frontend/src/features/crm/relances/parcours_suivi.json::cleAbsenteXyz')
        self.assertFalse(ok)

    def test_reference_reconnue_contre_texte_libre(self):
        self.assertTrue(parcours.est_une_reference('apps/sav/services.py::ouvrir_ticket'))
        self.assertTrue(parcours.est_une_reference('frontend/src/pages/sav/Tickets.jsx::Tickets'))
        self.assertFalse(parcours.est_une_reference('n/a'))
        self.assertFalse(parcours.est_une_reference('clic sur « Convertir en BC »'))


class ProblemesEtapeTests(unittest.TestCase):
    def test_etape_complete_sans_probleme(self):
        self.assertEqual(parcours.problemes_de_l_etape(_etape_complete()), [])

    def test_chaque_manquement_est_nomme_en_francais(self):
        etape = _etape_complete(
            declencheur={'type': 'clic', 'source': 'core/parcours.py::absent'},
            fonction_entree='texte libre',
            checkpoint={'modifiable': True, 'champs': ['x']},
            regle_aval=['inconnue'],
        )
        erreurs = parcours.problemes_de_l_etape(etape)
        self.assertTrue(any('declencheur.source' in e and 'introuvable' in e for e in erreurs), erreurs)
        self.assertTrue(any('fonction_entree' in e for e in erreurs), erreurs)
        self.assertTrue(any('checkpoint.persistance' in e for e in erreurs), erreurs)
        self.assertTrue(any('règle aval `inconnue`' in e for e in erreurs), erreurs)

    def test_declencheur_manuel_accepte_un_texte_et_les_champs_manquants_sont_listes(self):
        manuel = _etape_complete(declencheur={'type': 'manuel', 'source': 'Meryem appelle le client'})
        self.assertEqual(parcours.problemes_de_l_etape(manuel), [])
        vide = {'id': 'E9'}
        erreurs = parcours.problemes_de_l_etape(vide)
        for champ in ('nom', 'proprietaire', 'declencheur', 'fonction_entree', 'checkpoint', 'regle_aval'):
            self.assertTrue(any(f'`{champ}` manquant' in e for e in erreurs), (champ, erreurs))


class ProblemesTableTests(unittest.TestCase):
    def test_table_valide_puis_mutant(self):
        table = {'etapes': [_etape_complete(), _etape_complete(id='E2')], 'portes': ['core/parcours.py::charger_table']}
        self.assertEqual(parcours.problemes_de_la_table(table), [])
        mutant = {'etapes': [_etape_complete(), _etape_complete()], 'portes': []}
        erreurs = parcours.problemes_de_la_table(mutant)
        self.assertTrue(any('identifiant en double' in e for e in erreurs), erreurs)
        self.assertTrue(any('portes' in e for e in erreurs), erreurs)
        self.assertEqual(parcours.problemes_de_la_table({}), ['table sans étape', '`portes[]` vide : lister les entrées de création du parcours'])
