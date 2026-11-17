"""Flux de calendrier et tuile (regles.md §10) — unittest pur, sans base ni horloge."""
import unittest
from datetime import date, datetime, time, timedelta

from apps.taches.moteur.classement import ItemPur, LignePure, PlanPur
from apps.taches.moteur.flux import evenements_flux, tuile_pure

J = date(2026, 11, 17)  # mardi ; le 18/11 est férié
REGLAGES = object()


def _travailles():
    jours, d = set(), date(2026, 11, 1)
    while d <= date(2027, 1, 31):
        if d.weekday() < 5 and d != date(2026, 11, 18):
            jours.add(d)
        d += timedelta(days=1)
    return frozenset(jours)


TRAVAILLES = _travailles()


def tache(id, **champs):
    champs.setdefault('projet_id', 3)
    champs.setdefault('created_at', datetime(2026, 11, 1, 8, 0))
    return ItemPur(id=id, **champs)


class NomPour:
    """`nom_pour` de l'appelant : enregistre chaque usage, rend « titre-<id> »."""

    def __init__(self):
        self.appels = []

    def __call__(self, item, usage, reglages):
        self.appels.append((item.id, usage, reglages))
        return 'Tâche confidentielle' if item.confidentielle else f'titre-{item.id}'


def flux(taches, nom_pour=None):
    return evenements_flux(taches, J, REGLAGES, nom_pour or NomPour(), TRAVAILLES)


class FluxTests(unittest.TestCase):
    def test_horodate_et_journee_entiere(self):
        evts = flux([tache(1, jour_prevu=J, heure_debut=time(10, 0), estimation_minutes=45),
                     tache(2, jour_prevu=J, heure_debut=time(14, 0)),
                     tache(3, jour_prevu=J)])
        self.assertEqual([(e.uid, e.debut, e.fin, e.journee_entiere) for e in evts], [
            ('tache-1', datetime(2026, 11, 17, 10, 0), datetime(2026, 11, 17, 10, 45), False),
            ('tache-2', datetime(2026, 11, 17, 14, 0), datetime(2026, 11, 17, 14, 30), False),
            ('tache-3', J, date(2026, 11, 18), True),
        ])

    def test_echeance_heure_ne_place_jamais(self):
        e, = flux([tache(1, jour_prevu=J, echeance=J, echeance_heure=time(9, 0))])
        self.assertTrue(e.journee_entiere)

    def test_fenetre_j_a_j_plus_14(self):
        evts = flux([tache(1, jour_prevu=J - timedelta(days=1)), tache(2, jour_prevu=J),
                     tache(3, jour_prevu=J + timedelta(days=14)), tache(4, jour_prevu=J + timedelta(days=15)),
                     tache(5)])
        self.assertEqual([e.uid for e in evts], ['tache-2', 'tache-3'])

    def test_exclusions(self):
        exclues = [
            tache(1, jour_prevu=J, statut='fait', fait_le=datetime(2026, 11, 17, 9, 0)),
            tache(2, jour_prevu=J, statut='en_attente'),
            tache(3, jour_prevu=J, projet_id=None),  # À trier
            tache(4, jour_prevu=J, quelque_jour=True),  # En réserve
            tache(5, jour_prevu=J, bloquee_par=9),
            tache(6, jour_prevu=J, parent_id=9),  # sous-tâche
            ItemPur(type='activite', id=7, jour_prevu=J),
            tache(8, jour_prevu=J, reports=3),  # À revoir : reportée 3 fois
            tache(10, jour_prevu=date(2026, 11, 20), echeance=date(2026, 11, 1)),  # À revoir : retard ancien
        ]
        self.assertEqual(flux(exclues), ())

    def test_sans_projet_triee_emise(self):
        t = tache(1, jour_prevu=J, projet_id=None, triee_le=datetime(2026, 11, 2, 9, 0))
        self.assertEqual([e.uid for e in flux([t])], ['tache-1'])

    def test_8_journees_entieres_puis_n_autres(self):
        taches = [tache(i, jour_prevu=J, priorite=i % 4, created_at=datetime(2026, 11, 1, 8, i))
                  for i in range(1, 12)]
        evts = flux(taches)
        self.assertEqual(len(evts), 9)
        attendu = sorted(taches, key=lambda t: (-t.priorite, t.created_at))[:8]
        self.assertEqual([e.uid for e in evts[:8]], [f'tache-{t.id}' for t in attendu])
        dernier = evts[8]
        self.assertEqual((dernier.uid, dernier.titre, dernier.journee_entiere),
                         ('taches-autres-20261117', '+ 3 autres tâches', True))

    def test_une_autre_au_singulier(self):
        evts = flux([tache(i, jour_prevu=J) for i in range(1, 10)])
        self.assertEqual(evts[-1].titre, '+ 1 autre tâche')

    def test_horodatees_hors_plafond_des_journees(self):
        taches = [tache(i, jour_prevu=J) for i in range(1, 9)]
        taches += [tache(100 + h, jour_prevu=J, heure_debut=time(h, 0)) for h in range(8, 12)]
        self.assertEqual(len(flux(taches)), 12)

    def test_rang_jour_puis_cle_tri_a_priorite_egale(self):
        taches = [tache(1, jour_prevu=J, rang_jour=2048), tache(2, jour_prevu=J, rang_jour=1024),
                  tache(3, jour_prevu=J, echeance=J)]
        self.assertEqual([e.uid for e in flux(taches)], ['tache-2', 'tache-1', 'tache-3'])

    def test_200_au_plus_dernier_jour_tronque(self):
        taches = [tache(1000 * k + h, jour_prevu=J + timedelta(days=k), heure_debut=time(h, 0))
                  for k in range(15) for h in range(6, 21)]  # 15 jours × 15 = 225
        evts = flux(taches)
        self.assertEqual(len(evts), 200)
        derniers = [e for e in evts if e.debut.date() == J + timedelta(days=13)]
        self.assertEqual(len(derniers), 5)

    def test_titres_par_nom_pour_usage_flux(self):
        nom_pour = NomPour()
        evts = flux([tache(1, jour_prevu=J), tache(2, jour_prevu=J, confidentielle=True)], nom_pour)
        self.assertEqual({e.titre for e in evts}, {'titre-1', 'Tâche confidentielle'})
        self.assertEqual({(u, r) for _, u, r in nom_pour.appels}, {('flux', REGLAGES)})


PROGRESSION = {'faites': 1, 'prevues': 4, 'essentiel_faites': 0, 'essentiel_prevues': 1}


def tuile(items, plan=None, nom_pour=None, objectif=5):
    return tuile_pure(items, J, plan, objectif, PROGRESSION, REGLAGES, nom_pour or NomPour(), TRAVAILLES)


class TuileTests(unittest.TestCase):
    def test_echantillon_tuile_json(self):
        items = [
            tache(20, jour_prevu=J, heure_debut=time(10, 0), echeance=date(2026, 11, 19), priorite=2),
            ItemPur(type='activite', id=101, jour_prevu=J),
        ]
        corps = tuile(items)
        self.assertEqual(corps, {
            'faites': 1, 'prevues': 4, 'objectif': 5, 'essentiel': {'faites': 0, 'prevues': 1},
            'top': [{'id': 20, 'titre': 'titre-20', 'heure': '10:00', 'priorite': 2}],
            'reste': 1,
            'prochaine_echeance': {'titre': 'titre-20', 'jour': '2026-11-19', 'heure': None},
        })

    def test_top_6_dans_l_ordre_de_l_ecran_jamais_propose(self):
        plan = PlanPur(jour=J, lignes=(LignePure(tache_id=1, essentielle=True),))
        items = [
            tache(9, jour_prevu=J, moment='soir'),
            tache(1, jour_prevu=J),  # essentielle
            tache(2, jour_prevu=J), tache(3, jour_prevu=J, heure_debut=time(11, 0)),
            tache(4, jour_prevu=J, heure_debut=time(9, 0)), tache(5, jour_prevu=J, echeance=J),
            tache(6, jour_prevu=J), tache(7, jour_prevu=J),
            tache(30, echeance=date(2026, 11, 19)),  # Proposé : jamais sur la tuile
        ]
        corps = tuile(items, plan)
        self.assertEqual([t['id'] for t in corps['top']], [1, 4, 3, 5, 2, 6])
        self.assertEqual(corps['reste'], 2)  # pastille 8 (sans Proposé) − 6 montrés

    def test_activite_comptee_jamais_titree(self):
        nom_pour = NomPour()
        corps = tuile([ItemPur(type='activite', id=101, jour_prevu=J)], nom_pour=nom_pour)
        self.assertEqual((corps['top'], corps['reste'], nom_pour.appels), ([], 1, []))

    def test_faites_a_revoir_en_attente_hors_tuile(self):
        items = [tache(1, jour_prevu=J, statut='fait', fait_le=datetime(2026, 11, 17, 9, 0)),
                 tache(2, jour_prevu=date(2026, 11, 13), reports=3),
                 tache(3, jour_prevu=J, statut='en_attente')]
        corps = tuile(items)
        self.assertEqual((corps['top'], corps['reste']), ([], 0))

    def test_prochaine_echeance(self):
        items = [tache(1, echeance=date(2026, 11, 16)),  # passée
                 tache(2, echeance=date(2026, 11, 20), echeance_heure=time(9, 0)),
                 tache(3, echeance=date(2026, 11, 20), echeance_heure=time(8, 0)),
                 tache(4, echeance=date(2026, 11, 20)),
                 tache(5, echeance=date(2026, 11, 19), statut='fait', fait_le=datetime(2026, 11, 17, 8, 0)),
                 tache(6, echeance=date(2026, 11, 19), quelque_jour=True)]
        self.assertEqual(tuile(items)['prochaine_echeance'],
                         {'titre': 'titre-3', 'jour': '2026-11-20', 'heure': '08:00'})
        self.assertIsNone(tuile([])['prochaine_echeance'])

    def test_titres_par_nom_pour_usage_tuile(self):
        nom_pour = NomPour()
        corps = tuile([tache(1, jour_prevu=J, confidentielle=True)], nom_pour=nom_pour)
        self.assertEqual(corps['top'][0]['titre'], 'Tâche confidentielle')
        self.assertEqual({(u, r) for _, u, r in nom_pour.appels}, {('tuile', REGLAGES)})

    def test_objectif_libre_nul(self):
        self.assertIsNone(tuile([], objectif=None)['objectif'])

    def test_pastille_plafonnee_a_99(self):
        corps = tuile([tache(i, jour_prevu=J) for i in range(1, 121)])
        self.assertEqual((len(corps['top']), corps['reste']), (6, 93))


if __name__ == '__main__':
    unittest.main()
