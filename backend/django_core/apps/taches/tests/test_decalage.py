"""TCH32 — décalage de projet et modèles (spec-4 §B, §G) : unittest pur, sans base ni Django."""
import unittest
from dataclasses import dataclass, field
from datetime import date, timedelta

from apps.taches.moteur.decalage import decaler, figer_modele, instancier

J = date(2026, 11, 17)  # mardi


def ouvre(d):
    """Samedi et dimanche → lundi suivant."""
    return d + timedelta(days=(7 - d.weekday()) if d.weekday() >= 5 else 0)


@dataclass
class P:
    id: int = 3
    date_debut: date = None
    echeance: date = None
    objectif: str = 'Stand monté'
    priorite: int = 2


@dataclass
class S:
    id: int
    nom: str = 'Préparation'
    date_debut: date = None
    date_fin: date = None


@dataclass
class T:
    id: int
    titre: str = 'Tâche'
    statut: str = 'a_faire'
    jour_prevu: date = None
    echeance: date = None
    section_id: int = None
    priorite: int = 0
    jalon: bool = False
    parent_id: int = None
    bloquee_par: int = None
    checklist: tuple = field(default_factory=tuple)
    notes: str = ''


class DecalerTests(unittest.TestCase):
    def test_delta_7(self):
        projet = P(date_debut=date(2026, 11, 16), echeance=date(2026, 11, 22))
        sections = [S(1, date_debut=date(2026, 11, 16), date_fin=date(2026, 11, 20))]
        taches = [T(41, jour_prevu=date(2026, 11, 20), echeance=date(2026, 11, 27))]
        r = decaler(7, J, projet, sections, taches, ouvre)
        self.assertIsNone(r.refus)
        self.assertEqual(r.changements, (
            {'objet': 'projet', 'id': 3, 'champ': 'date_debut', 'avant': '2026-11-16', 'apres': '2026-11-23'},
            # dim. 22/11 + 7 = dim. 29/11 → lun. 30/11
            {'objet': 'projet', 'id': 3, 'champ': 'echeance', 'avant': '2026-11-22', 'apres': '2026-11-30'},
            {'objet': 'section', 'id': 1, 'champ': 'date_debut', 'avant': '2026-11-16', 'apres': '2026-11-23'},
            {'objet': 'section', 'id': 1, 'champ': 'date_fin', 'avant': '2026-11-20', 'apres': '2026-11-27'},
            {'objet': 'tache', 'id': 41, 'champ': 'jour_prevu', 'avant': '2026-11-20', 'apres': '2026-11-27'},
            {'objet': 'tache', 'id': 41, 'champ': 'echeance', 'avant': '2026-11-27', 'apres': '2026-12-04'},
        ))

    def test_refus_deux_taches_avant_aujourdhui(self):
        taches = [T(1, jour_prevu=date(2026, 11, 18)), T(2, jour_prevu=date(2026, 11, 17)),
                  T(3, jour_prevu=date(2026, 11, 30))]
        r = decaler(-2, J, P(), [], taches, ouvre)
        self.assertEqual(r.refus, "2 tâches passeraient avant aujourd'hui.")
        self.assertEqual(r.nb_avant, 2)
        self.assertEqual(r.changements, ())

    def test_refus_singulier(self):
        r = decaler(-2, J, P(), [], [T(1, jour_prevu=date(2026, 11, 18))], ouvre)
        self.assertEqual(r.refus, "1 tâche passerait avant aujourd'hui.")

    def test_en_retard_reste_en_retard_pas_de_refus(self):
        r = decaler(-2, J, P(), [], [T(1, jour_prevu=date(2026, 11, 10))], ouvre)
        self.assertIsNone(r.refus)
        self.assertEqual(r.changements[0]['apres'], '2026-11-09')

    def test_echeance_seule_pas_de_refus(self):
        r = decaler(-30, J, P(), [], [T(1, echeance=date(2026, 11, 20))], ouvre)
        self.assertIsNone(r.refus)

    def test_faites_et_annulees_intactes(self):
        taches = [T(1, statut='fait', jour_prevu=date(2026, 11, 20)),
                  T(2, statut='annule', jour_prevu=date(2026, 11, 20)),
                  T(3, statut='en_attente', jour_prevu=date(2026, 11, 20))]
        r = decaler(7, J, P(), [], taches, ouvre)
        self.assertEqual([c['id'] for c in r.changements], [3])

    def test_delta_nul_et_dates_absentes(self):
        self.assertEqual(decaler(0, J, P(), [], [T(1, jour_prevu=date(2026, 11, 20))], ouvre).changements, ())
        self.assertEqual(decaler(7, J, P(), [S(1)], [T(1)], ouvre).changements, ())


def projet_salon():
    projet = P(date_debut=date(2026, 11, 23), echeance=date(2026, 12, 7))
    sections = [S(1, date_debut=date(2026, 11, 23), date_fin=date(2026, 12, 7))]
    taches = [
        T(10, 'Réserver le stand', jour_prevu=date(2026, 11, 23), echeance=date(2026, 11, 30), section_id=1,
          priorite=3, checklist=('Prix',), notes='Appeler'),
        T(11, 'Contrat', jour_prevu=date(2026, 11, 24), section_id=1, parent_id=10, bloquee_par=10),
        T(12, 'Faite', statut='fait', jour_prevu=date(2026, 11, 25), jalon=True),
        T(13, 'Abandonnée', statut='annule', jour_prevu=date(2026, 11, 25)),
        T(14, 'Sous-tâche d\'une abandonnée', parent_id=13),
        T(15, 'Après', bloquee_par=13, jour_prevu=date(2026, 12, 1)),
    ]
    return projet, sections, taches


class ModeleTests(unittest.TestCase):
    def test_figer_contenu_v1(self):
        projet, sections, taches = projet_salon()
        c = figer_modele(projet, sections, taches)
        self.assertEqual(c['v'], 1)
        self.assertEqual((c['objectif'], c['priorite']), ('Stand monté', 2))
        self.assertEqual(c['sections'], [{'nom': 'Préparation', 'decalage_debut': 0, 'decalage_fin': 14}])
        self.assertEqual([t['titre'] for t in c['taches']], ['Réserver le stand', 'Contrat', 'Faite', 'Après'])
        premiere = c['taches'][0]
        self.assertEqual((premiere['decalage_jour'], premiere['decalage_echeance']), (0, 7))
        self.assertEqual((premiere['section_index'], premiere['priorite'], premiere['checklist']), (0, 3, ['Prix']))
        sous = c['taches'][1]
        self.assertEqual((sous['parent_index'], sous['bloquee_par_index']), (0, 0))
        self.assertTrue(c['taches'][2]['jalon'])
        self.assertIsNone(c['taches'][3]['bloquee_par_index'])  # prérequis abandonné : lien perdu
        self.assertNotIn('notes', premiere)

    def test_notes_seulement_si_demandees(self):
        projet, sections, taches = projet_salon()
        c = figer_modele(projet, sections, taches, inclure_notes=True)
        self.assertEqual(c['taches'][0]['notes'], 'Appeler')

    def test_origine_sans_date_debut_est_la_plus_petite_date(self):
        projet, sections, taches = projet_salon()
        projet.date_debut = None
        sections[0].date_debut = None
        c = figer_modele(projet, sections, taches)
        self.assertEqual(c['sections'][0]['decalage_debut'], None)
        self.assertEqual(c['taches'][0]['decalage_jour'], 0)  # 23/11 est la plus petite date

    def test_aucune_date_decalages_nuls(self):
        c = figer_modele(P(), [S(1)], [T(1, section_id=1)])
        self.assertEqual(c['sections'][0], {'nom': 'Préparation', 'decalage_debut': None, 'decalage_fin': None})
        self.assertEqual((c['taches'][0]['decalage_jour'], c['taches'][0]['decalage_echeance']), (None, None))

    def test_instancier_exemple_de_la_reference(self):
        contenu = {'v': 1, 'objectif': 'Stand monté', 'priorite': 2,
                   'sections': [{'nom': 'Préparation', 'decalage_debut': 0, 'decalage_fin': 14}],
                   'taches': [{'titre': 'Réserver le stand', 'section_index': 0, 'priorite': 3, 'jalon': False,
                               'decalage_jour': 0, 'decalage_echeance': 5, 'parent_index': None,
                               'bloquee_par_index': None, 'checklist': [], 'notes': ''}]}
        r = instancier(contenu, 'Salon', date(2026, 11, 23), ouvre)
        self.assertEqual(r['projet'], {'nom': 'Salon', 'objectif': 'Stand monté', 'priorite': 2})
        self.assertEqual(r['sections'], [{'nom': 'Préparation', 'date_debut': '2026-11-23',
                                          'date_fin': '2026-12-07'}])
        t = r['taches'][0]
        # J+5 = sam. 28/11 → lun. 30/11
        self.assertEqual(
            (t['titre'], t['jour_prevu'], t['echeance']),
            ('Réserver le stand', '2026-11-23', '2026-11-30'))
        self.assertEqual(t['notes'], '')

    def test_instancier_decalage_nul_ou_absent(self):
        contenu = {'v': 1, 'sections': [], 'taches': [{'titre': 'x', 'decalage_jour': None,
                                                       'decalage_echeance': 0}]}
        t = instancier(contenu, 'N', date(2026, 11, 23), ouvre)['taches'][0]
        self.assertEqual((t['jour_prevu'], t['echeance']), (None, '2026-11-23'))
        self.assertNotIn('notes', t)

    def test_version_inconnue(self):
        with self.assertRaises(ValueError):
            instancier({'v': 2}, 'N', J, ouvre)

    def test_aller_retour_figer_puis_instancier(self):
        projet, sections, taches = projet_salon()
        c = figer_modele(projet, sections, taches, inclure_notes=True)
        r = instancier(c, 'Salon bis', projet.date_debut, ouvre)
        self.assertEqual([(t['jour_prevu'], t['echeance']) for t in r['taches']],
                         [('2026-11-23', '2026-11-30'), ('2026-11-24', None), ('2026-11-25', None),
                          ('2026-12-01', None)])
        self.assertEqual(r['sections'][0]['date_fin'], '2026-12-07')
        self.assertEqual([t['parent_index'] for t in r['taches']], [None, 0, None, None])
        self.assertEqual(figer_modele(_projet_de(r, projet), _sections_de(r), _taches_de(r),
                                      inclure_notes=True)['taches'], c['taches'])

    def test_instancier_decale_au_lancement_suivant(self):
        projet, sections, taches = projet_salon()
        c = figer_modele(projet, sections, taches)
        r = instancier(c, 'Plus tard', date(2026, 12, 7), ouvre)
        self.assertEqual(r['taches'][0]['jour_prevu'], '2026-12-07')
        self.assertEqual(r['taches'][0]['echeance'], '2026-12-14')


def _projet_de(r, projet):
    return P(date_debut=date.fromisoformat(r['sections'][0]['date_debut']), objectif=r['projet']['objectif'],
             priorite=r['projet']['priorite'])


def _sections_de(r):
    s = r['sections'][0]
    return [S(1, s['nom'], date.fromisoformat(s['date_debut']), date.fromisoformat(s['date_fin']))]


def _taches_de(r):
    def d(v):
        return date.fromisoformat(v) if v else None
    rendu = []
    for i, t in enumerate(r['taches']):
        pere = r['taches'][t['parent_index']] if t['parent_index'] is not None else None
        rendu.append(T(100 + i, t['titre'], jour_prevu=d(t['jour_prevu']), echeance=d(t['echeance']),
                       section_id=1 if t['section_index'] == 0 else None, priorite=t['priorite'],
                       jalon=t['jalon'], parent_id=100 + t['parent_index'] if pere else None,
                       bloquee_par=(100 + t['bloquee_par_index']) if t['bloquee_par_index'] is not None else None,
                       checklist=tuple(t['checklist']), notes=t.get('notes', '')))
    return rendu


if __name__ == '__main__':
    unittest.main()
