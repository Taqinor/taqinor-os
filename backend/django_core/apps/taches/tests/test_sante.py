"""TCH31 — santé d'un projet (regles.md §5) : unittest pur, sans base ni Django.

J = mar. 17/11/2026, N = 10, jours travaillés lun-ven.
"""
import unittest
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from apps.taches.moteur import sante

J = date(2026, 11, 17)


def jours_travailles(feries=(), conges=()):
    d, rendu = date(2026, 9, 1), set()
    while d <= date(2026, 12, 31):
        if d.weekday() < 5 and d not in feries:
            rendu.add(d)
        d += timedelta(days=1)
    for debut, fin in conges:
        rendu = {x for x in rendu if not debut <= x <= fin}
    return frozenset(rendu)


@dataclass
class T:
    statut: str = 'a_faire'
    parent_id: int = None
    quelque_jour: bool = False
    bloquee_par: int = None
    jour_prevu: date = None
    echeance: date = None
    fait_le: datetime = None
    created_at: datetime = datetime(2026, 11, 3, 9, 0)
    annule_le: datetime = None


def faite(jour, **kw):
    return T(statut='fait', fait_le=datetime(2026, 11, jour, 15, 0), **kw)


def projet(**kw):
    base = dict(id=1, nom='Ventes', priorite=3, rang=1, statut_depuis=date(2026, 11, 3))
    base.update(kw)
    return sante.ProjetSante(**base)


class CasDuTableau(unittest.TestCase):
    def test_01_projet_neuf(self):
        p = projet(statut_depuis=J)
        self.assertEqual(sante.avancement([]).barre, False)
        self.assertIsNone(sante.a_l_arret([], p, J, jours_travailles()))
        self.assertIsNone(sante.sans_prochaine_action([]))
        self.assertIsNone(sante.tout_fait([]))
        self.assertIsNone(sante.echeance_menacee([], p, J, jours_travailles()))
        self.assertTrue(sante.a_planifier(p, 0))

    def test_02_neuf_reste_vide_10_jours(self):
        p = projet()
        self.assertIsNone(sante.a_l_arret([], p, J, jours_travailles()))
        self.assertIsNone(sante.sans_prochaine_action([]))
        self.assertTrue(sante.a_planifier(p, 0))

    def test_03_neuf_avec_taches_rien_fait(self):
        taches = [T(), T(), T()]
        s = sante.a_l_arret(taches, projet(), J, jours_travailles())
        self.assertEqual(s.code, 'a_l_arret')
        self.assertEqual(s.donnees, {'jours': 10, 'depuis': '2026-11-03'})
        self.assertEqual(s.phrase, 'Rien de fait depuis 10 jours travaillés.')
        self.assertFalse(sante.a_planifier(projet(), 3))

    def test_04_deux_taches(self):
        taches = [faite(3), T()]
        self.assertEqual(sante.avancement(taches).texte, '1 sur 2')
        self.assertEqual(sante.avancement(taches).derniere_faite, date(2026, 11, 3))
        self.assertIsNotNone(sante.a_l_arret(taches, projet(), J, jours_travailles()))
        p = projet(echeance=date(2026, 12, 8))
        self.assertIsNone(sante.echeance_menacee(taches, p, J, jours_travailles(), rythme=True))

    def test_05_deux_taches_ferie(self):
        taches = [faite(3), T()]
        trav = jours_travailles(feries={date(2026, 11, 6)})
        self.assertIsNone(sante.a_l_arret(taches, projet(), J, trav))

    def test_06_sans_echeance(self):
        taches = [T(jour_prevu=date(2030, 1, 1))]
        self.assertIsNone(sante.echeance_menacee(taches, projet(echeance=None), J, jours_travailles(), True))

    def test_07_echeance_tenable(self):
        trav = jours_travailles()
        ech = date(2026, 12, 8)  # 15 jours travaillés dans ]17/11, 08/12]
        ouvertes = [T() for _ in range(12)]
        faites_8 = [faite(d) for d in (2, 3, 4, 5, 6, 9, 10, 11)]
        s = sante.echeance_menacee(ouvertes + faites_8, projet(echeance=ech), J, trav, rythme=True)
        self.assertEqual((s.code, s.donnees['signal']), ('echeance_menacee', 'd'))
        self.assertEqual((s.donnees['besoin'], s.donnees['reste']), (30, 15))
        # R2-034 — la conséquence d'abord, chaque chiffre calculé (rythme F28/J28, ouvertes, échéance)
        self.assertEqual(s.phrase, 'À ce rythme, pas prêt pour le mar. 8 déc. : il faudrait 30 jours travaillés, '
                                   'il en reste 15 (8 faites en 20 jours travaillés ces 4 dernières semaines).')
        self.assertEqual(s.donnees['echeance'], '2026-12-08')
        faites_4 = [faite(d) for d in (2, 3, 4, 5)]
        self.assertIsNone(sante.echeance_menacee(ouvertes + faites_4, projet(echeance=ech), J, trav, rythme=True))
        # rythme éteint : signal (d) absent même avec F28 = 8
        self.assertIsNone(sante.echeance_menacee(ouvertes + faites_8, projet(echeance=ech), J, trav))
        # échéance proche : le jour se dit comme partout (« jeu. 26 », « demain »)
        proche = sante.echeance_menacee(ouvertes + faites_8, projet(echeance=date(2026, 11, 26)), J, trav, rythme=True)
        self.assertTrue(proche.phrase.startswith('À ce rythme, pas prêt pour le jeu. 26 : '), proche.phrase)
        demain = sante.echeance_menacee(ouvertes + faites_8, projet(echeance=date(2026, 11, 18)), J, trav, rythme=True)
        self.assertTrue(demain.phrase.startswith('À ce rythme, pas prêt pour demain : '), demain.phrase)

    def test_08_retour_de_conge(self):
        trav = jours_travailles(feries={date(2026, 11, 6)}, conges=[(date(2026, 11, 2), date(2026, 11, 13))])
        taches = [faite(2), T()]
        taches[0].fait_le = datetime(2026, 10, 30, 11, 0)
        self.assertEqual(sante._jours_travailles(trav, date(2026, 10, 30), J), 2)
        self.assertIsNone(sante.a_l_arret(taches, projet(statut_depuis=date(2026, 10, 1)), J, trav))

    def test_09_tout_en_reserve(self):
        taches = [T(quelque_jour=True), T(quelque_jour=True)]
        s = sante.sans_prochaine_action(taches)
        self.assertEqual(s.donnees['cause'], 'reserve')
        self.assertEqual(s.phrase, 'Rien à faire maintenant : tout est en réserve.')

    def test_10_tout_fait(self):
        taches = [faite(d) for d in (3, 4, 5, 6, 9)]
        s = sante.tout_fait(taches)
        self.assertEqual(s.phrase, 'Tout est fait : terminer le projet ?')
        self.assertIsNone(sante.sans_prochaine_action(taches))
        self.assertIsNone(sante.a_l_arret(taches, projet(), J, jours_travailles()))

    def test_11_neglige(self):
        a, b, c = self._trois((3, 0), (2, 4), (1, 1))
        res = sante.neglige([a, b, c], {1: 0, 2: 4, 3: 1}, J)
        self.assertEqual(list(res), [1])
        self.assertEqual(res[1].donnees['autre'], 'B')
        self.assertEqual(res[1].donnees['d'], 4)
        self.assertEqual(
            res[1].phrase,
            '« A » (haute) n\'a rien vu avancer en 14 jours ; « B » (moyenne) : 4 faites.')

    def test_12_neglige_en_chaine(self):
        a, b, c = self._trois((3, 0), (2, 0), (1, 1))
        res = sante.neglige([a, b, c], {1: 0, 2: 0, 3: 1}, J)
        self.assertEqual(sorted(res), [1, 2])
        self.assertEqual(res[1].donnees['autre'], 'C')
        self.assertEqual(res[2].donnees['autre'], 'C')
        self.assertTrue(res[2].phrase.endswith('« C » (basse) : 1 faite.'))

    def test_13_tous_a_zero(self):
        a, b, c = self._trois((3, 0), (2, 0), (1, 0))
        self.assertEqual(sante.neglige([a, b, c], {1: 0, 2: 0, 3: 0}, J), {})

    @staticmethod
    def _trois(*prios):
        noms = 'ABC'
        return [projet(id=i + 1, nom=noms[i], priorite=p, rang=i + 1,
                       statut_depuis=date(2026, 10, 28), actionnables=1)
                for i, (p, _) in enumerate(prios)]


class AutresRegles(unittest.TestCase):
    def test_avancement_ignore_sous_taches_et_annulees(self):
        taches = [faite(3), T(), T(statut='annule'), T(parent_id=9), faite(5, parent_id=9)]
        av = sante.avancement(taches)
        self.assertEqual((av.faites, av.total, av.barre), (1, 2, True))

    def test_a_l_arret_compte_les_sous_taches_faites(self):
        taches = [T(), faite(16, parent_id=9)]
        self.assertIsNone(sante.a_l_arret(taches, projet(), J, jours_travailles()))

    def test_neglige_exige_14_jours_et_une_actionnable(self):
        a, b, c = CasDuTableau._trois((3, 0), (2, 4), (1, 1))
        recent = projet(id=1, nom='A', priorite=3, statut_depuis=date(2026, 11, 4), actionnables=1)
        self.assertEqual(sante.neglige([recent, b, c], {1: 0, 2: 4, 3: 1}, J), {})
        vide = projet(id=1, nom='A', priorite=3, statut_depuis=date(2026, 10, 28), actionnables=0)
        self.assertEqual(sante.neglige([vide, b, c], {1: 0, 2: 4, 3: 1}, J), {})

    def test_neglige_egalite_priorite_puis_rang(self):
        a = projet(id=1, nom='A', priorite=3, statut_depuis=date(2026, 10, 1), actionnables=1)
        b = projet(id=2, nom='B', priorite=1, rang=5)
        c = projet(id=3, nom='C', priorite=2, rang=9)
        d = projet(id=4, nom='D', priorite=2, rang=2)
        res = sante.neglige([a, b, c, d], {1: 0, 2: 3, 3: 3, 4: 3}, J)
        self.assertEqual(res[1].donnees['autre'], 'D')

    def test_echeance_signaux_a_b_c(self):
        trav = jours_travailles()
        p = projet(echeance=date(2026, 11, 20))
        self.assertEqual(sante.echeance_menacee([T()], projet(echeance=date(2026, 11, 10)), J, trav).phrase,
                         'Échéance dépassée le 10/11.')
        deux = [T(jour_prevu=date(2026, 11, 25)), T(echeance=date(2026, 11, 30))]
        s = sante.echeance_menacee(deux, p, J, trav)
        self.assertEqual(s.phrase, '2 tâches sont prévues après l\'échéance.')
        un = sante.echeance_menacee([T(jour_prevu=date(2026, 11, 25))], p, J, trav)
        self.assertEqual(un.phrase, '1 tâche est prévue après l\'échéance.')
        p_etape = projet(echeance=date(2026, 11, 20), etapes=(('Pose', date(2026, 11, 27)),))
        self.assertEqual(sante.echeance_menacee([T()], p_etape, J, trav).phrase,
                         'L\'étape « Pose » finit après l\'échéance.')
        self.assertIsNone(sante.echeance_menacee([T()], p, J, trav))

    def test_sans_prochaine_action_causes(self):
        self.assertEqual(sante.sans_prochaine_action([T(statut='en_attente'), T(bloquee_par=4)]).donnees['cause'],
                         'attend')
        self.assertEqual(sante.sans_prochaine_action([T(quelque_jour=True), T(statut='en_attente')]).donnees['cause'],
                         'mixte')
        self.assertIsNone(sante.sans_prochaine_action([T(), T(quelque_jour=True)]))

    def test_burnup(self):
        taches = [
            T(created_at=datetime(2026, 11, 3, 9, 0), fait_le=datetime(2026, 11, 12, 9, 0), statut='fait'),
            T(created_at=datetime(2026, 11, 10, 9, 0)),
            T(created_at=datetime(2026, 11, 4, 9, 0), statut='annule', annule_le=datetime(2026, 11, 9, 9, 0)),
        ]
        b = sante.burnup(taches, J)
        self.assertEqual([(p.fin, p.total, p.faites) for p in b.points],
                         [(date(2026, 11, 8), 2, 0), (date(2026, 11, 15), 2, 1)])
        self.assertEqual(b.legende, 'reconstruit depuis les dates actuelles')
        une = sante.burnup(taches[:1], date(2026, 11, 10))
        self.assertEqual(len(une.points), 1)
        self.assertEqual(une.legende, '')
        self.assertEqual(sante.burnup([], J).points, ())

    def test_constat_projets(self):
        c = sante.constat_projets([1, 2, 3, 4, 5, 6, 7], {1: 2, 2: 1, 3: 1})
        self.assertEqual(c['phrase'], '7 projets actifs, 3 ont avancé ces 7 jours')
        self.assertEqual(sante.constat_projets([1], {1: 1})['phrase'], '1 projet actif, 1 a avancé ces 7 jours')
        self.assertEqual(sante.constat_projets([], {})['phrase'], '0 projet actif, 0 a avancé ces 7 jours')


if __name__ == '__main__':
    unittest.main()
