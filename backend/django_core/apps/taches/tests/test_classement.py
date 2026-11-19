"""Classement et Proposé (regles.md §3, §4.2) — unittest pur, sans base ni horloge."""
import random
import unittest
from datetime import date, datetime, timedelta

from apps.taches.choix import MotifRevoir, RaisonPropose as R, SectionJournee as S
from apps.taches.moteur.classement import (
    ItemPur, LignePure, PlanPur, cle_tri_pour, placer, trier)

J = date(2026, 11, 17)  # mardi ; le 18/11 est férié
TRIEE = datetime(2026, 11, 1, 9, 0)


def jours_travailles(du, au, feries=(date(2026, 11, 18), date(2027, 1, 1))):
    """Lundi-vendredi entre `du` et `au`, fériés ôtés."""
    jours, d = set(), du
    while d <= au:
        if d.weekday() < 5 and d not in feries:
            jours.add(d)
        d += timedelta(days=1)
    return frozenset(jours)


TRAVAILLES = jours_travailles(date(2026, 10, 1), date(2027, 6, 30))


def tache(id, **champs):
    champs.setdefault('created_at', datetime(2026, 11, 1, 8, 0))
    if champs.get('projet_id') is None:
        champs.setdefault('triee_le', TRIEE)
    return ItemPur(id=id, **champs)


def jeu_cle_tri():
    """Jeu de §3.3 (J = mar. 17/11/2026)."""
    return [
        tache(7, echeance=date(2026, 11, 16), priorite=3, projet_id=1, projet_priorite=2),
        tache(12, echeance=date(2026, 11, 17), priorite=1, projet_id=4, projet_priorite=2),
        ItemPur(type='activite', id=101, jour_prevu=date(2026, 11, 17),
                created_at=datetime(2026, 11, 10, 9, 0)),
        tache(15, echeance=date(2026, 11, 17), created_at=datetime(2026, 11, 14, 9, 0)),
        tache(20, echeance=date(2026, 11, 19), priorite=2, projet_id=3, projet_priorite=3),
        tache(21, echeance=date(2026, 11, 20), priorite=3),
        tache(30, projet_id=7, projet_priorite=3),
        tache(40, echeance=date(2026, 11, 7), priorite=1),
        tache(31, echeance=date(2027, 4, 15), priorite=3),
        tache(41, jour_prevu=date(2026, 11, 12), created_at=datetime(2026, 11, 5, 9, 0)),
        tache(42, jour_prevu=J, created_at=datetime(2026, 11, 6, 9, 0)),
        tache(43, jour_prevu=J, created_at=datetime(2026, 11, 7, 9, 0)),
        tache(44, jour_prevu=J, created_at=datetime(2026, 11, 7, 9, 0)),
    ]


def jeu_hors_cle_tri():
    """Lignes « — » de §3.3."""
    return [
        tache(50, jour_prevu=date(2026, 11, 13), reports=3),
        tache(51, statut='en_attente', jour_prevu=J),
        tache(52, quelque_jour=True),
        tache(53, jour_prevu=date(2026, 11, 19)),
    ]


ORDRE_CLE_TRI = [7, 12, 101, 15, 20, 21, 30, 40, 31, 41, 42, 43, 44]
BANDES = {7: 1, 12: 1, 101: 1, 15: 1, 20: 2, 21: 2, 30: 2, 40: 3, 31: 3, 41: 3, 42: 3, 43: 3, 44: 3}


class CleTriTests(unittest.TestCase):
    def test_ordre_du_jeu(self):
        self.assertEqual([i.id for i in trier(jeu_cle_tri(), J, TRAVAILLES)], ORDRE_CLE_TRI)

    def test_bandes(self):
        cle = cle_tri_pour(J, TRAVAILLES)
        self.assertEqual({i.id: cle(i)[0] for i in jeu_cle_tri()}, BANDES)

    def test_jours_travailles_jusqua_l_echeance(self):
        # 18/11 férié : 19 (n = 1), 20 (n = 2), 23 (n = 3).
        from apps.taches.moteur.classement import n_travailles
        self.assertEqual([n_travailles(J, date(2026, 11, d), TRAVAILLES) for d in (18, 19, 20, 23)],
                         [0, 1, 2, 3])

    def test_cles_toutes_distinctes(self):
        cle = cle_tri_pour(J, TRAVAILLES)
        cles = [cle(i) for i in jeu_cle_tri()]
        self.assertEqual(len(set(cles)), len(cles))

    def test_300_permutations_meme_ordre(self):
        hasard = random.Random(20261117)
        items = jeu_cle_tri()
        ordres = set()
        for _ in range(300):
            hasard.shuffle(items)
            ordres.add(tuple(i.id for i in trier(items, J, TRAVAILLES)))
        self.assertEqual(ordres, {tuple(ORDRE_CLE_TRI)})

    def test_identiques_departages_par_id(self):
        a = tache(44, jour_prevu=J)
        b = tache(43, jour_prevu=J)
        self.assertEqual([i.id for i in trier([a, b], J, TRAVAILLES)], [43, 44])

    def test_tache_avant_activite_a_cle_egale(self):
        t = tache(5, echeance=J, created_at=datetime(2026, 11, 1))
        a = ItemPur(type='activite', id=5, jour_prevu=J, created_at=datetime(2026, 11, 1))
        self.assertEqual([i.type for i in trier([a, t], J, TRAVAILLES)], ['tache', 'activite'])

    def test_projet_de_la_semaine_vaut_haute(self):
        t = tache(9, projet_id=2, projet_priorite=1, focus=True)
        self.assertEqual(cle_tri_pour(J, TRAVAILLES)(t)[:4], (2, date.max, -3, 0))

    def test_haute_echeance_lointaine_en_bande_3(self):
        t = tache(9, priorite=3, echeance=J + timedelta(days=15))
        self.assertEqual(cle_tri_pour(J, TRAVAILLES)(t)[0], 3)


class PlacerTests(unittest.TestCase):
    """Colonne « À l'écran le 17/11 » de §3.3, puis les cas de §4.2."""

    ATTENDU = {
        7: (S.PROPOSE, R.ECHEANCE_PASSEE),
        12: (S.JOURNEE, None),
        101: (S.JOURNEE, None),
        15: (S.JOURNEE, None),
        20: (S.PROPOSE, R.ECHEANCE_PROCHE),
        21: (S.PROPOSE, R.ECHEANCE_PROCHE),
        30: (S.PROPOSE, None),
        40: (S.A_DECIDER, MotifRevoir.RETARD_ANCIEN),
        31: (S.PROPOSE, None),
        41: (S.PROPOSE, R.RETARD),
        42: (S.JOURNEE, None),
        43: (S.JOURNEE, None),
        44: (S.JOURNEE, None),
        50: (S.A_DECIDER, MotifRevoir.REPORTEE_3_FOIS),
        51: (S.EN_ATTENTE, None),
        52: None,
        53: None,
    }

    def place(self, item, plan=None):
        p = placer(item, J, plan, TRAVAILLES)
        return None if p is None else (p.section, p.code)

    def test_colonne_a_l_ecran(self):
        obtenu = {i.id: self.place(i) for i in jeu_cle_tri() + jeu_hors_cle_tri()}
        self.assertEqual(obtenu, self.ATTENDU)

    def test_ordre_prevu_et_a_revoir(self):
        items = jeu_cle_tri() + jeu_hors_cle_tri()
        prevu = [i for i in items if self.place(i) == (S.JOURNEE, None)]
        revoir = [i for i in items if self.place(i) and self.place(i)[0] == S.A_DECIDER]
        self.assertEqual([i.id for i in trier(prevu, J, TRAVAILLES)], [12, 101, 15, 42, 43, 44])
        self.assertEqual([i.id for i in trier(revoir, J, TRAVAILLES)], [40, 50])

    def test_faite_aujourdhui_reste_essentielle(self):
        t = tache(1, statut='fait', jour_prevu=J, fait_le=datetime(2026, 11, 17, 10, 0))
        plan = PlanPur(jour=J, lignes=(LignePure(tache_id=1, essentielle=True),))
        p = placer(t, J, plan, TRAVAILLES)
        self.assertEqual((p.section, p.essentielle), (S.FAITES, True))

    def test_faite_hier_absente(self):
        t = tache(1, statut='fait', fait_le=datetime(2026, 11, 16, 18, 0))
        self.assertIsNone(self.place(t))

    def test_en_attente_sans_date_absente(self):
        self.assertIsNone(self.place(tache(1, statut='en_attente')))
        self.assertEqual(self.place(tache(1, statut='en_attente', echeance=J)), (S.EN_ATTENTE, None))

    def test_reportee_3_fois_avant_le_jour(self):
        t = tache(1, jour_prevu=J, reports=4, reports_tranches=1)
        self.assertEqual(self.place(t), (S.A_DECIDER, MotifRevoir.REPORTEE_3_FOIS))
        t = tache(1, jour_prevu=J, reports=4, reports_tranches=2)
        self.assertEqual(self.place(t), (S.JOURNEE, None))

    def test_essentiel_puis_ce_soir_puis_prevu(self):
        plan = PlanPur(jour=J, lignes=(LignePure(tache_id=1, essentielle=True),))
        self.assertEqual(self.place(tache(1, jour_prevu=J, moment='soir'), plan), (S.ESSENTIEL, None))
        self.assertEqual(self.place(tache(2, jour_prevu=J, moment='soir'), plan), (S.CE_SOIR, None))
        self.assertEqual(self.place(tache(3, echeance=J), plan), (S.JOURNEE, None))

    def test_retard_ancien_par_echeance(self):
        t = tache(1, echeance=date(2026, 11, 9))
        self.assertEqual(self.place(t), (S.A_DECIDER, MotifRevoir.RETARD_ANCIEN))

    def test_retard_de_7_jours_au_plus_reste_dans_propose(self):
        self.assertEqual(self.place(tache(1, jour_prevu=date(2026, 11, 10))), (S.PROPOSE, R.RETARD))
        self.assertEqual(self.place(tache(1, echeance=date(2026, 11, 10))), (S.PROPOSE, R.ECHEANCE_PASSEE))

    def test_echeance_proche_deja_prevue_avant_n_est_pas_pressee(self):
        t = tache(1, echeance=date(2026, 11, 20), jour_prevu=date(2026, 11, 19))
        self.assertIsNone(self.place(t))
        t = tache(1, echeance=date(2026, 11, 19), jour_prevu=date(2026, 11, 23))
        self.assertEqual(self.place(t), (S.PROPOSE, R.ECHEANCE_PROCHE))

    def test_echeance_au_dela_de_2_jours_travailles(self):
        self.assertEqual(self.place(tache(1, echeance=date(2026, 11, 23))), (S.PROPOSE, None))

    def test_activite_passee(self):
        a = ItemPur(type='activite', id=9, jour_prevu=date(2026, 11, 16))
        self.assertEqual(self.place(a), (S.A_DECIDER, MotifRevoir.ACTIVITE_PASSEE))
        self.assertIsNone(self.place(ItemPur(type='activite', id=9, jour_prevu=date(2026, 11, 19))))

    def test_hors_prefiltre_absentes(self):
        self.assertIsNone(self.place(ItemPur(id=1)))  # À trier : sans projet, non triée
        self.assertIsNone(self.place(tache(1, parent_id=2)))
        self.assertIsNone(self.place(tache(1, bloquee_par=2)))
        self.assertIsNone(self.place(tache(1, statut='annule')))


# --- Proposé (regles.md §3.4) ---------------------------------------------

VENTES, MAISON, POLY, ADMIN, SALON = 10, 11, 12, 13, 14
PROJETS = {VENTES: (3, 1024), MAISON: (2, 1024), POLY: (2, 2048), ADMIN: (1, 1024), SALON: (3, 2048)}
EN_PAUSE = {SALON}


def dans(projet, id, rang, **champs):
    priorite, rang_p = PROJETS[projet]
    return tache(id, projet_id=projet, projet_priorite=priorite, projet_rang=rang_p,
                 rang_projet=rang, **champs)


def jeu_propose():
    """Jeu de §3.4 : 30 tâches, 5 projets (Salon en pause) + sans projet ; NOMS[id] = titre."""
    items = [dans(VENTES, 100 + k, 1024 * k) for k in range(1, 13)]
    items += [
        dans(VENTES, 113, 13 * 1024, jour_prevu=date(2026, 11, 13), reports=3),  # R4
        dans(MAISON, 201, 1024, jour_prevu=date(2026, 11, 16)),  # R1
        dans(MAISON, 202, 2048, jour_prevu=date(2026, 11, 20)),  # M1
        dans(MAISON, 203, 3072), dans(MAISON, 204, 4096),  # M2, M3
        dans(POLY, 301, 1024, echeance=date(2026, 11, 12)),  # R2
        dans(POLY, 302, 2048, quelque_jour=True),  # D1 pour plus tard
        dans(POLY, 303, 3072, bloquee_par=304),  # D2 bloquée
        dans(POLY, 304, 4096), dans(POLY, 305, 5120),  # D3, D4
        dans(ADMIN, 401, 1024, echeance=date(2026, 11, 19)),  # A1
        dans(ADMIN, 402, 2048), dans(ADMIN, 403, 3072),  # A2, A3
        dans(ADMIN, 404, 4096, jour_prevu=date(2026, 11, 5)),  # R3
        dans(SALON, 501, 1024), dans(SALON, 502, 2048),
        tache(601, rang_projet=1024), tache(602, rang_projet=2048),  # S1, S2
    ]
    return items


NOMS = {100 + k: f'V{k}' for k in range(1, 13)}
NOMS.update({113: 'R4', 201: 'R1', 202: 'M1', 203: 'M2', 204: 'M3', 301: 'R2', 302: 'D1', 303: 'D2',
             304: 'D3', 305: 'D4', 401: 'A1', 402: 'A2', 403: 'A3', 404: 'R3', 501: 'Salon1',
             502: 'Salon2', 601: 'S1', 602: 'S2'})


def prefiltre(items):
    """Ce que le sélecteur `taches_de_la_journee` retire (inv. 10) : les projets en pause."""
    return [i for i in items if i.projet_id not in EN_PAUSE]


def lignes(plan_propose):
    return [(NOMS[i.id], r) for i, r in plan_propose.pour_objectif]


def proposer(n, items=None, **options):
    from apps.taches.moteur.classement import proposer_plan
    items = prefiltre(jeu_propose()) if items is None else items
    return proposer_plan(items, J, TRAVAILLES, n, 0, 0, **options)


PRESSE = [('R1', R.RETARD), ('R2', R.ECHEANCE_PASSEE), ('A1', R.ECHEANCE_PROCHE)]
TOUR_1 = [(nom, R.PROCHAINE_ACTION) for nom in ('V1', 'M2', 'D3', 'A2', 'S1')]
TOUR_2 = [(nom, R.ACTION_SUIVANTE) for nom in ('V2', 'M3', 'D4', 'A3', 'S2')]


class ProposeTests(unittest.TestCase):
    def test_jeu_de_30_taches(self):
        self.assertEqual(len(jeu_propose()), 30)

    def test_n_2_ce_qui_presse_reste_entier(self):
        self.assertEqual(lignes(proposer(2)), PRESSE)

    def test_n_3(self):
        self.assertEqual(lignes(proposer(3)), PRESSE)

    def test_n_5(self):
        self.assertEqual(lignes(proposer(5)), PRESSE + TOUR_1[:2])

    def test_n_8(self):
        self.assertEqual(lignes(proposer(8)), PRESSE + TOUR_1)

    def test_n_13(self):
        self.assertEqual(lignes(proposer(13)), PRESSE + TOUR_1 + TOUR_2)

    def test_reste_du_tour(self):
        # tour complet : 12 (Ventes) + 2 + 2 + 2 + 2 (sans projet) = 20 ; 2 prises à N = 5.
        self.assertEqual(proposer(5).reste_nb, 18)

    def test_a_revoir_et_absentes(self):
        par_nom = {NOMS[i.id]: i for i in jeu_propose()}
        self.assertEqual(placer(par_nom['R3'], J, None, TRAVAILLES).code, MotifRevoir.RETARD_ANCIEN)
        self.assertEqual(placer(par_nom['R4'], J, None, TRAVAILLES).code, MotifRevoir.REPORTEE_3_FOIS)
        pris = {nom for nom, _ in lignes(proposer(30))}
        self.assertFalse(pris & {'Salon1', 'Salon2', 'D1', 'D2', 'M1', 'R3', 'R4'})

    def test_prevue_plus_tard_dans_la_suite_depliee(self):
        suite = dict(proposer(5).suite_par_projet)
        self.assertEqual([NOMS[i.id] for i in suite[MAISON]], ['M1', 'M3'])
        self.assertEqual([p for p, _ in proposer(5).suite_par_projet], [VENTES, MAISON, POLY, ADMIN, None])

    def test_monopole_de_l_ancien_cle_tri(self):
        from apps.taches.moteur.classement import est_candidate, raison_presse
        pool = [i for i in prefiltre(jeu_propose()) if est_candidate(i, J)
                and raison_presse(i, J, TRAVAILLES) is None and i.jour_prevu is None]
        self.assertEqual([NOMS[i.id] for i in trier(pool, J, TRAVAILLES)[:5]], ['V1', 'V2', 'V3', 'V4', 'V5'])
        self.assertEqual([nom for nom, _ in lignes(proposer(8))[3:]], ['V1', 'M2', 'D3', 'A2', 'S1'])

    def test_un_projet_haute_de_30_taches_une_place_par_tour(self):
        items = [tache(1000 + k, projet_id=1, projet_priorite=3, projet_rang=1024, rang_projet=k)
                 for k in range(30)]
        items += [tache(2000, projet_id=2, projet_priorite=1, projet_rang=1024, rang_projet=1),
                  tache(2001, projet_id=2, projet_priorite=1, projet_rang=1024, rang_projet=2),
                  tache(3000, rang_projet=1)]
        pris = [i.id for i, _ in proposer(4, items).pour_objectif]
        self.assertEqual(pris, [1000, 2000, 3000, 1001])

    def test_aucun_projet_deux_fois_avant_les_autres(self):
        from apps.taches.moteur.classement import tour_des_projets
        hasard = random.Random(34)
        tailles = (25, 8, 5, 2)  # un gros projet prioritaire, trois petits
        items = [tache(100 * p + k, projet_id=p, projet_priorite=3 - p, rang_projet=k)
                 for p, taille in enumerate(tailles) for k in range(taille)]
        for _ in range(50):
            hasard.shuffle(items)
            vus, tours = {}, []
            for item, _ in tour_des_projets(items):
                vus[item.projet_id] = vus.get(item.projet_id, 0) + 1
                tours.append(vus[item.projet_id])
            self.assertEqual(tours, sorted(tours))

    def test_ordre_du_17_11_n_nul_ce_qui_presse_montre(self):
        from apps.taches.moteur.classement import proposer_plan
        items = jeu_cle_tri() + jeu_hors_cle_tri()
        plan = proposer_plan(items, J, TRAVAILLES, 5, 0, 6)
        self.assertEqual([(i.id, r) for i, r in plan.pour_objectif],
                         [(41, R.RETARD), (7, R.ECHEANCE_PASSEE), (20, R.ECHEANCE_PROCHE),
                          (21, R.ECHEANCE_PROCHE)])
        self.assertEqual(plan.reste_nb, 2)  # 30 et 31 : le tour n'a rien pris

    def test_n_objectif_moins_faites_moins_gardees(self):
        from apps.taches.moteur.classement import places
        self.assertEqual([places(5, 0, 2), places(5, 3, 2), places(5, 4, 3), places(None, 1, 0)], [3, 0, 0, 4])

    def test_journee_allegee_replie_et_vide(self):
        plan = PlanPur(jour=J, allege_le=datetime(2026, 11, 17, 11, 0))
        sortie = proposer(8, plan=plan)
        self.assertEqual((sortie.pour_objectif, sortie.reste_nb, sortie.replie), ((), 0, True))

    def test_inclure_en_tete_du_tour_meme_au_dela_de_n(self):
        nom = {v: k for k, v in NOMS.items()}
        self.assertEqual(lignes(proposer(3, inclure=[nom['V7']])), PRESSE + [('V7', R.ACTION_SUIVANTE)])

    def test_exclure_retire(self):
        nom = {v: k for k, v in NOMS.items()}
        self.assertEqual(lignes(proposer(5, exclure=[nom['R2'], nom['V1']])),
                         [PRESSE[0], PRESSE[2], ('V2', R.PROCHAINE_ACTION), ('M2', R.PROCHAINE_ACTION),
                          ('D3', R.PROCHAINE_ACTION)])

    def test_charge(self):
        items = [tache(1, jour_prevu=J, estimation_minutes=120), tache(2, estimation_minutes=45),
                 tache(3), tache(4, estimation_minutes=30)]
        charge = proposer(5, items, disponible_minutes=180).charge
        self.assertEqual(charge, {'minutes_estimees': 195, 'sans_estimation': 1, 'surcharge': True,
                                  'non_calculable': False})
        charge = proposer(5, [tache(1), tache(2), tache(3, estimation_minutes=10)]).charge
        self.assertEqual((charge['surcharge'], charge['non_calculable']), (False, True))

    def test_prochaine_action(self):
        from apps.taches.moteur.classement import prochaine_action
        projet = [dans(MAISON, 9, 1024, statut='fait'), dans(MAISON, 8, 2048, bloquee_par=7),
                  dans(MAISON, 7, 3072, quelque_jour=True), dans(MAISON, 6, 4096, parent_id=1),
                  dans(MAISON, 5, 5120, jour_prevu=date(2026, 11, 26)), dans(MAISON, 4, 5120)]
        self.assertEqual(prochaine_action(projet).id, 4)
        self.assertIsNone(prochaine_action(projet[:4]))

    def test_scenario_du_24_11_les_3_proposees_du_matin(self):
        """SCENARIO.md §3 « 08:30 » : prochaine action de chaque projet, dans l'ordre de priorité des
        projets puis de leur rang : rails (Benali, Haute), fournisseur (Salon, Haute), fiche de poste
        (Recrutement, Moyenne) ; le contrat (Administratif, Basse) vient après et n'est pas proposé."""
        from apps.taches.moteur.classement import proposer_plan
        jour = date(2026, 11, 24)
        items, titres = scenario_24_11()
        plan = proposer_plan(items, jour, TRAVAILLES, 5, 0, 2)
        self.assertEqual([titres[i.id] for i, _ in plan.pour_objectif],
                         ['Commander les rails de fixation', 'Appeler le fournisseur',
                          'Rédiger la fiche de poste'])


def scenario_24_11():
    """SCENARIO.md §1-§2 au matin du mar. 24/11, 08:30 (avant « Garder ces 3 »)."""
    d = date
    benali, salon, recru, admin, site = 1, 2, 3, 4, 5
    prio = {benali: (3, 1024), salon: (3, 2048), recru: (2, 3072), admin: (1, 4096), site: (2, 5120)}
    lignes_ = [
        (benali, 'Envoyer le devis révisé', dict(jour_prevu=d(2026, 11, 24), echeance=d(2026, 11, 25), priorite=3)),
        (benali, 'Commander les rails de fixation', {}),
        (benali, 'Valider le plan de calepinage', dict(jour_prevu=d(2026, 11, 25), echeance=d(2026, 11, 26))),
        (benali, 'Réceptionner les 16 panneaux', dict(jour_prevu=d(2026, 11, 26))),
        (benali, 'Poser la structure', dict(bloquee_par=4)),
        (benali, 'Mise en service', dict(jour_prevu=d(2026, 12, 3), jalon=True)),
        (salon, 'Confirmer la réservation du stand', dict(jour_prevu=d(2026, 11, 24), echeance=d(2026, 11, 24))),
        (salon, 'Préparer le matériel du stand', dict(jour_prevu=d(2026, 11, 26))),
        (salon, "Imprimer les badges de l'équipe", dict(jour_prevu=d(2026, 11, 27))),
        (salon, 'Imprimer les kakémonos', dict(jour_prevu=d(2026, 11, 25))),
        (salon, "Comparer deux devis d'impression", dict(quelque_jour=True)),
        (salon, 'Appeler le fournisseur', dict(priorite=3)),
        (salon, 'Préparer la démo onduleur hybride', {}),
        (salon, "Réserver l'hôtel du salon", {}),
        (recru, 'Trier les CV reçus', dict(jour_prevu=d(2026, 11, 25))),
        (recru, 'Rédiger la fiche de poste', {}),
        (recru, 'Planifier les entretiens', dict(bloquee_par=15)),
        (recru, "Préparer les questions d'entretien", {}),
        (recru, 'Appeler les candidats retenus', dict(bloquee_par=17)),
        (admin, 'Relire le contrat de maintenance', dict(moment='soir')),
        (admin, 'Préparer la déclaration de TVA', dict(jour_prevu=d(2026, 11, 27))),
        (admin, "Payer l'assurance du camion", dict(jour_prevu=d(2026, 11, 27))),
        (site, 'Lister les pages du site', {}), (site, "Choisir l'hébergeur", {}),
        (site, "Rédiger la page d'accueil", {}), (site, 'Photographier trois chantiers', {}),
    ]
    items, titres = [], {}
    for n, (projet, titre, champs) in enumerate(lignes_, start=1):
        p, r = prio[projet]
        items.append(tache(n, projet_id=projet, projet_priorite=p, projet_rang=r, rang_projet=1024 * n, **champs))
        titres[n] = titre
    # À revoir toute la journée (sans projet, prévues lun. 23) : seul « reportée 3 fois » les y met en rév. 3.
    for n, titre in ((90, 'Mettre à jour le planning des poses'), (91, 'Rappeler le bureau de contrôle')):
        items.append(tache(n, jour_prevu=d(2026, 11, 23), reports=3))
        titres[n] = titre
    return items, titres


class PrioritesTests(unittest.TestCase):
    """« Aide-moi à prioriser » (regles.md §12)."""

    TETE = ['R1', 'R2', 'A1', 'V1', 'M2', 'D3', 'A2', 'S1', 'V2', 'M3', 'D4', 'A3', 'S2'] + [
        f'V{k}' for k in range(3, 13)]

    def classer(self, n=5, items=None, **options):
        from apps.taches.moteur.classement import classer_priorites
        items = prefiltre(jeu_propose()) if items is None else items
        return classer_priorites(items, J, TRAVAILLES, n, 0, 0, **options)

    def test_tete_puis_tour_sans_limite(self):
        sortie = self.classer()
        self.assertEqual([NOMS[i.id] for i, _ in sortie.lignes[:23]], self.TETE)
        self.assertEqual(sortie.garder_n, 5)

    def test_a_revoir_en_fin_avec_son_motif(self):
        fin = {(NOMS[i.id], code) for i, code in self.classer().lignes[23:]}
        self.assertEqual(fin, {('R3', MotifRevoir.RETARD_ANCIEN), ('R4', MotifRevoir.REPORTEE_3_FOIS)})

    def test_ordre_complet_de_la_reference(self):
        """regles.md §12 : la tête, puis À revoir dans l'ordre de `cle_tri` (§3.1) : R4 (Ventes, priorité
        haute) avant R3 (Admin, basse)."""
        self.assertEqual([NOMS[i.id] for i, _ in self.classer().lignes], self.TETE + ['R4', 'R3'])

    def test_une_raison_par_ligne(self):
        sortie = self.classer()
        self.assertEqual(len(sortie.lignes), 25)
        self.assertTrue(all(code for _, code in sortie.lignes))
        raisons = [code for _, code in sortie.lignes[:23]]
        self.assertEqual(raisons[:3], [R.RETARD, R.ECHEANCE_PASSEE, R.ECHEANCE_PROCHE])
        self.assertEqual(set(raisons[3:8]), {R.PROCHAINE_ACTION})
        self.assertEqual(set(raisons[8:]), {R.ACTION_SUIVANTE})

    def test_ordre_de_l_echantillon_priorites_json(self):
        items = [
            tache(21, priorite=3, echeance=date(2026, 11, 19), projet_id=4, projet_priorite=1,
                  estimation_minutes=30),
            tache(30, projet_id=7, projet_priorite=3, estimation_minutes=45),
            tache(50, priorite=1, jour_prevu=date(2026, 11, 13), reports=3, projet_id=9, projet_priorite=2),
        ]
        from apps.taches.moteur.classement import classer_priorites
        sortie = classer_priorites(items, J, TRAVAILLES, 5, 1, 2)
        self.assertEqual([(i.id, code) for i, code in sortie.lignes],
                         [(21, R.ECHEANCE_PROCHE), (30, R.PROCHAINE_ACTION), (50, MotifRevoir.REPORTEE_3_FOIS)])
        self.assertEqual((sortie.garder_n, sortie.plus_tard), (2, date(2026, 11, 19)))

    def test_au_plus_3_essentiels(self):
        self.assertEqual(len(self.classer(8).essentiels), 3)
        deux = (LignePure(tache_id=999, essentielle=True), LignePure(tache_id=998, essentielle=True))
        plan = PlanPur(jour=J, lignes=deux)
        self.assertEqual(len(self.classer(8, plan=plan).essentiels), 1)
        self.assertEqual(self.classer(0, items=[]).essentiels, ())

    def test_plus_tard(self):
        from apps.taches.moteur.classement import plus_tard
        self.assertEqual(plus_tard(date(2026, 11, 17), TRAVAILLES), date(2026, 11, 19))
        self.assertEqual(plus_tard(date(2026, 11, 20), TRAVAILLES), date(2026, 11, 23))
        self.assertEqual(plus_tard(date(2026, 11, 19), TRAVAILLES), date(2026, 11, 20))


class CapaciteTests(unittest.TestCase):
    def test_reglage_historique_defaut(self):
        from apps.taches.moteur.classement import capacite
        neuf = [150, 180, 200, 210, 240, 250, 260, 300, 320]
        self.assertEqual(capacite(300, neuf, 20), (300, 'reglage'))
        self.assertEqual(capacite(None, neuf, 20), (240, 'historique'))
        self.assertEqual(capacite(None, neuf, 4), (240, 'defaut'))
        self.assertEqual(capacite(None, [100, 200, 300, 400, 500, 600], 6), (350, 'historique'))
        self.assertEqual(capacite(None, neuf, 20, comprendre=False), (240, 'defaut'))

    def test_mediane_paire_demie_vers_le_bas(self):
        from apps.taches.moteur.classement import capacite
        self.assertEqual(capacite(None, [100, 101, 102, 103, 104, 105], 6), (102, 'historique'))

    def test_temps_disponible(self):
        from apps.taches.moteur.classement import temps_disponible
        # Table de §3.6 : (rendez-vous en minutes, disponible) pour une capacité de 240.
        for rdv, dispo in ((60, 180), (120, 120), (30, 210), (0, 240), (300, 0), (30, 210)):
            self.assertEqual(temps_disponible(240, rdv), dispo)

    def test_charge_du_jour_une_seule_regle(self):
        """R4-01 (M1) — la charge d'un jour : ce qui RESTE à faire ce jour-là, durées dites seulement. Jeu du 17/11 :
        prévue 30 min + prévue sans durée + échéance du jour sans jour prévu 60 min + ★ reportée demain gardée par
        son échéance du jour 45 min comptent ; la faite (90), Ce soir (20), en attente (15), plus tard (10), reportée
        3 fois (25), prévue demain (40) ne comptent pas. Calcul à la main : 30 + 60 + 45 = 135 restantes, 1 sans
        durée, 4 tâches ; disponible = 240 − 60 = 180 ; déborde 0. Demain : la prévue demain (40) et la ★ (45, prévue
        demain) — 85 ; l'échéance d'après-demain prévue demain ne compte qu'une fois (demain)."""
        from apps.taches.moteur.classement import charge_du_jour
        demain, apres = J + timedelta(days=1), J + timedelta(days=2)
        items = [
            tache(1, jour_prevu=J, estimation_minutes=30), tache(2, jour_prevu=J),
            tache(3, echeance=J, estimation_minutes=60),
            tache(4, jour_prevu=demain, echeance=J, estimation_minutes=45),
            tache(5, jour_prevu=J, statut='fait', fait_le=datetime(2026, 11, 17, 9, 0), estimation_minutes=90),
            tache(6, jour_prevu=J, moment='soir', estimation_minutes=20),
            tache(7, jour_prevu=J, statut='en_attente', estimation_minutes=15),
            tache(8, quelque_jour=True, echeance=J, estimation_minutes=10),
            tache(9, jour_prevu=J, reports=3, estimation_minutes=25),
            tache(10, jour_prevu=demain, echeance=apres, estimation_minutes=40),
        ]
        self.assertEqual(charge_du_jour(items, J, J, 240, 60), {
            'taches': 4, 'restantes_minutes': 135, 'sans_duree': 1, 'capacite_minutes': 240,
            'rendez_vous_minutes': 60, 'disponible_minutes': 180, 'deborde_minutes': 0})
        self.assertEqual(charge_du_jour(items, demain, J, 240, 0)['restantes_minutes'], 85)
        self.assertEqual(charge_du_jour(items, apres, J, 240, 0)['restantes_minutes'], 0)
        # 4 h 30 restantes pour 4 h : 30 min de trop
        longue = [tache(1, jour_prevu=J, estimation_minutes=270)]
        self.assertEqual(charge_du_jour(longue, J, J, 240, 0)['deborde_minutes'], 30)


class ExplicationTests(unittest.TestCase):
    """Faits (codes) des exemples d'`api.md` ; le texte est rendu par les gabarits (TCH30)."""

    def faits(self, item):
        from apps.taches.moteur.classement import explication
        return [code for code, _ in explication(item, J, TRAVAILLES)]

    def test_exemples(self):
        cas = [
            (tache(20, jour_prevu=J, echeance=date(2026, 11, 19), priorite=2, projet_id=3, projet_priorite=3),
             ['echeance_proche', 'projet_prioritaire']),
            (tache(42, jour_prevu=J), ['prevue_aujourdhui']),
            (ItemPur(type='activite', id=101, jour_prevu=J), ['activite_du_jour']),
            (tache(60, jour_prevu=J, moment='soir', projet_id=5, projet_priorite=2), ['prevue_ce_soir']),
            (tache(50, jour_prevu=date(2026, 11, 13), reports=3, priorite=1, projet_id=9, projet_priorite=2),
             ['reportee_3_fois']),
            (tache(51, statut='en_attente', jour_prevu=J), ['en_attente']),
            (tache(12, jour_prevu=J, echeance=J, priorite=1, projet_id=4, projet_priorite=1),
             ['echeance_aujourdhui']),
            (tache(22, projet_id=3, projet_priorite=1), ['dans_projet']),
            (tache(23), ['sans_projet']),
        ]
        for item, attendu in cas:
            self.assertEqual(self.faits(item), attendu, item.id)

    def test_au_plus_3_faits(self):
        from apps.taches.moteur.classement import explication
        t = tache(1, echeance=date(2027, 1, 20), priorite=3, focus=True, projet_id=2)
        self.assertLessEqual(len(explication(t, J, TRAVAILLES)), 3)
        self.assertEqual(self.faits(t), ['echeance_lointaine', 'projet_de_la_semaine'])


if __name__ == '__main__':
    unittest.main()
