"""CALX188 — le dispatch batterie branché sur la série AC réelle.

Ce qui est tenu ici :

* sur 8 760 heures, le BILAN FERME :
  ``Σ production = Σ autoconsommé + Σ export + Σ pertes batterie
  + variation de stock`` à 0,1 kWh près ;
* l'état de charge reste entre les bornes de la fiche à CHAQUE heure (0 % et
  100 % de la capacité utile ; jamais sous la réserve saisie en stratégie de
  secours) ;
* une stratégie ``peak_shaving`` SANS seuil saisi OMET le bloc en NOMMANT le
  champ, et aucune stratégie n'est supposée quand aucune n'est choisie ;
* le bloc omis laisse la série INCHANGÉE — aucune colonne à zéro.

Séries de test : une année 2021 SYNTHÉTIQUE, clairement fabriquée pour le
test et ne décrivant AUCUNE installation réelle. Test PUR : aucune base,
aucun réseau.
"""
from __future__ import annotations

import datetime

from django.test import SimpleTestCase

from apps.calepinage.services import chaine_pertes
from apps.calepinage.services.etapes import batterie as bloc

#: Les heures où la série de test porte de la production.
HEURES_DE_PRODUCTION = range(8, 18)

#: La puissance alternative de ces heures-là (kW) — un placeholder assumé.
P_AC_KW = 4.0

#: La consommation de chaque heure de la série de test (kWh).
CONSO_KWH = 1.0


def serie_de_test(*, annee=2021, heures=8760):
    """Une année horaire SYNTHÉTIQUE au format CALX142, côté ALTERNATIF."""
    depart = datetime.datetime(annee, 1, 1)
    points = []
    for rang in range(heures):
        moment = depart + datetime.timedelta(hours=rang)
        points.append({
            'annee': moment.year,
            'mois': moment.month,
            'jour': moment.day,
            'heure': moment.hour,
            'p_ac_kw': (P_AC_KW if moment.hour in HEURES_DE_PRODUCTION
                        else 0.0),
        })
    return {'points': points, 'pas_minutes': 60,
            'colonne_energie': 'p_ac_kw'}


def specs_de_test(*, capacite=10.0, puissance=5.0, rendement=90.0, dod=90.0,
                  packs=1):
    """La forme EXACTE que rend ``services/batterie.py::specs_batterie``."""
    def ligne(valeur):
        return {'valeur': valeur, 'source': 'fiche',
                'mention': 'Lu sur la fiche produit.'}

    return {
        'grandeurs': {
            'kwh_nominal': ligne(capacite / (dod / 100.0)),
            'kwh_usable': ligne(capacite),
            'dod_pct': ligne(dod),
            'rendement_ar_pct': ligne(rendement),
            'cycles_publies': ligne(6000.0),
            'max_charge_kw': ligne(puissance),
            'max_decharge_kw': ligne(puissance),
        },
        'nb_packs': packs,
        'capacite_utile_kwh': capacite,
        'capacite_utile_source': 'fiche',
        'puissance_charge_kw': puissance,
        'puissance_decharge_kw': puissance,
        'borne_onduleur': {'charge_kw': None, 'decharge_kw': None},
        'avertissements': [],
    }


def contexte_de_test(*, strategie='autoconso', heures=8760, **declaration):
    """Un contexte minimal : consommation importée + une banque déclarée."""
    contexte = {
        'consommation': {
            'import_intervalle': {'valeurs': [CONSO_KWH] * heures,
                                  'origine': 'Relevé SYNTHÉTIQUE de test'},
        },
        bloc.CLE_CONTEXTE: {
            'groupes': [{'groupe': 'BAT-TEST-1', 'specs': specs_de_test()}],
        },
    }
    if strategie is not None:
        contexte[bloc.CLE_CONTEXTE]['strategie'] = strategie
    contexte[bloc.CLE_CONTEXTE].update(declaration)
    return contexte


class BilanQuiFermeTest(SimpleTestCase):
    """Le test de propriété : rien ne se perd, rien ne se crée."""

    def test_le_bilan_annuel_ferme_a_un_dixieme_de_kwh(self):
        serie = serie_de_test()
        suite, resultat = bloc.bloc_batterie(serie, contexte_de_test())

        self.assertEqual(resultat['motif_absence'], '')
        energie = resultat['total']['energie']
        somme = (energie['autoconsomme_kwh'] + energie['export_kwh']
                 + energie['pertes_batterie_kwh']
                 + energie['variation_stock_kwh'])
        self.assertAlmostEqual(energie['production_kwh'], somme, delta=0.1)
        self.assertEqual(len(suite['points']), 8760)

    def test_la_production_publiee_est_celle_de_la_serie(self):
        serie = serie_de_test()
        _suite, resultat = bloc.bloc_batterie(serie, contexte_de_test())

        attendue = P_AC_KW * len(HEURES_DE_PRODUCTION) * 365
        self.assertAlmostEqual(resultat['total']['energie']['production_kwh'],
                               attendue, delta=0.1)

    def test_l_autoconsomme_ne_depasse_jamais_les_deux_totaux(self):
        serie = serie_de_test()
        _suite, resultat = bloc.bloc_batterie(serie, contexte_de_test())

        energie = resultat['total']['energie']
        self.assertLessEqual(energie['autoconsomme_kwh'],
                             energie['production_kwh'] + 0.1)
        self.assertLessEqual(energie['autoconsomme_kwh'],
                             energie['consommation_kwh'] + 0.1)


class BornesDeLaFicheTest(SimpleTestCase):
    """L'état de charge reste dans les bornes de la fiche, heure par heure."""

    def test_le_soc_reste_entre_zero_et_cent_pourcent(self):
        serie = serie_de_test()
        suite, resultat = bloc.bloc_batterie(serie, contexte_de_test())

        self.assertEqual(resultat['motif_absence'], '')
        valeurs = [point['batterie_soc_pct'] for point in suite['points']]
        self.assertEqual(len(valeurs), 8760)
        self.assertGreaterEqual(min(valeurs), 0.0)
        self.assertLessEqual(max(valeurs), 100.0)

    def test_la_reserve_de_secours_n_est_jamais_entamee(self):
        serie = serie_de_test()
        # Banque PLEINE au départ : la réserve saisie ne doit alors jamais
        # être franchie vers le bas, à aucune heure de l'année.
        contexte = contexte_de_test(strategie='backup',
                                    reserve_backup_kwh=4.0,
                                    etat_initial_kwh=10.0)
        suite, resultat = bloc.bloc_batterie(serie, contexte)

        self.assertEqual(resultat['motif_absence'], '')
        plancher = 4.0 / 10.0 * 100.0
        valeurs = [point['batterie_soc_pct'] for point in suite['points']]
        self.assertGreaterEqual(min(valeurs), plancher - 0.01)


class ColonnesPoseesTest(SimpleTestCase):
    """Les quatre colonnes du contrat CALX142, et la PURETÉ de la série."""

    def test_les_quatre_colonnes_sont_ecrites_sur_chaque_point(self):
        serie = serie_de_test(heures=48)
        contexte = contexte_de_test(heures=48)
        suite, resultat = bloc.bloc_batterie(serie, contexte)

        self.assertEqual(resultat['motif_absence'], '')
        for point in suite['points']:
            for colonne in bloc.COLONNES_POSEES:
                self.assertIn(colonne, point)

    def test_la_serie_recue_n_est_jamais_modifiee(self):
        serie = serie_de_test(heures=48)
        contexte = contexte_de_test(heures=48)
        bloc.bloc_batterie(serie, contexte)

        for point in serie['points']:
            self.assertNotIn('batterie_soc_pct', point)

    def test_la_charge_ecrite_est_celle_de_la_courbe(self):
        serie = serie_de_test(heures=48)
        suite, _resultat = bloc.bloc_batterie(serie,
                                              contexte_de_test(heures=48))

        self.assertEqual({point['charge_kwh'] for point in suite['points']},
                         {CONSO_KWH})


class OmissionsTest(SimpleTestCase):
    """Rien n'est supposé : chaque absence OMET le bloc en nommant le champ."""

    def test_peak_shaving_sans_seuil_omet_en_nommant_le_champ(self):
        serie = serie_de_test(heures=48)
        contexte = contexte_de_test(strategie='peak_shaving', heures=48)
        suite, resultat = bloc.bloc_batterie(serie, contexte)

        self.assertIsNone(resultat['total'])
        self.assertIn('seuil_effacement_kw', resultat['motif_absence'])
        self.assertIs(suite, serie)

    def test_aucune_strategie_choisie_omet_le_bloc(self):
        serie = serie_de_test(heures=48)
        contexte = contexte_de_test(strategie=None, heures=48)
        _suite, resultat = bloc.bloc_batterie(serie, contexte)

        self.assertIsNone(resultat['total'])
        self.assertIn('strategie', resultat['motif_absence'])

    def test_aucune_batterie_declaree_omet_le_bloc(self):
        serie = serie_de_test(heures=48)
        _suite, resultat = bloc.bloc_batterie(serie, {})

        self.assertIsNone(resultat['total'])
        self.assertIn('groupes', resultat['motif_absence'])

    def test_sans_courbe_de_charge_le_bloc_est_omis(self):
        serie = serie_de_test(heures=48)
        contexte = contexte_de_test(heures=48)
        contexte['consommation'] = {}
        _suite, resultat = bloc.bloc_batterie(serie, contexte)

        self.assertIsNone(resultat['total'])
        self.assertTrue(resultat['motif_absence'])

    def test_sans_fuseau_le_bloc_est_omis_avec_le_motif_de_calx59(self):
        serie = serie_de_test(heures=48)
        contexte = contexte_de_test(heures=48)
        contexte[chaine_pertes.CLE_CROISEMENT_HORAIRE] = {
            'possible': False,
            'motif': chaine_pertes.MOTIF_FUSEAU_ABSENT,
            'champ': 'site.fuseau',
            'blocs_omis': list(chaine_pertes.BLOCS_HORAIRES_OMIS),
        }
        _suite, resultat = bloc.bloc_batterie(serie, contexte)

        self.assertIsNone(resultat['total'])
        self.assertEqual(resultat['motif_absence'],
                         chaine_pertes.MOTIF_FUSEAU_ABSENT)

    def test_sans_colonne_d_energie_le_bloc_est_omis(self):
        serie = serie_de_test(heures=48)
        muette = {'points': [{'annee': 2021, 'mois': 1, 'jour': 1,
                              'heure': rang % 24} for rang in range(48)],
                  'pas_minutes': 60}
        _suite, resultat = bloc.bloc_batterie(muette,
                                              contexte_de_test(heures=48))

        self.assertIsNone(resultat['total'])
        self.assertTrue(resultat['motif_absence'])
        self.assertEqual(len(serie['points']), 48)


class GroupesTest(SimpleTestCase):
    """La banque est UNE : deux groupes ne se répartissent pas au prorata."""

    def test_deux_groupes_n_ont_pas_d_energie_restituee_separee(self):
        serie = serie_de_test(heures=48)
        contexte = contexte_de_test(heures=48)
        contexte[bloc.CLE_CONTEXTE]['groupes'].append(
            {'groupe': 'BAT-TEST-2', 'specs': specs_de_test()})
        _suite, resultat = bloc.bloc_batterie(serie, contexte)

        self.assertEqual(resultat['motif_absence'], '')
        self.assertEqual(len(resultat['groupes']), 2)
        for ligne in resultat['groupes']:
            self.assertIsNone(ligne['energie_restituee_kwh'])
            self.assertIsNone(ligne['cycles_an'])
        self.assertIn(bloc.MENTION_PLUSIEURS_GROUPES,
                      resultat['avertissements'])
        self.assertEqual(resultat['total']['capacite_utile_kwh'], 20.0)

    def test_un_seul_groupe_publie_son_energie_et_ses_cycles(self):
        serie = serie_de_test()
        _suite, resultat = bloc.bloc_batterie(serie, contexte_de_test())

        ligne = resultat['groupes'][0]
        self.assertEqual(ligne['strategie'], 'autoconso')
        self.assertEqual(ligne['profondeur_decharge_pct'], 90.0)
        self.assertEqual(ligne['source'], 'fiche')
        self.assertGreater(ligne['energie_restituee_kwh'], 0.0)
        self.assertGreater(ligne['cycles_an'], 0.0)


class PointeEtReserveServiesTest(SimpleTestCase):
    """ACAL787 — ``total`` sert la pointe (peak_shaving) et la réserve
    déduite des appareils (backup), ``null`` ailleurs."""

    SEUIL_KW = 0.5

    def test_peak_shaving_publie_pointe_et_depassements(self):
        contexte = contexte_de_test(strategie='peak_shaving',
                                    seuil_effacement_kw=self.SEUIL_KW)
        contexte[chaine_pertes.CLE_ANNEES_FENETRE] = 2
        suite, resultat = bloc.bloc_batterie(serie_de_test(), contexte)
        total = resultat['total']
        imports = [p['reseau_import_kwh'] for p in suite['points']]
        # Soutirage sans batterie : 1 kWh les 14 heures sans production.
        self.assertEqual(total['pointe_avant_kw'], CONSO_KWH)
        self.assertEqual(total['pointe_apres_kw'], round(max(imports), 3))
        nuit = 24 - len(HEURES_DE_PRODUCTION)
        self.assertEqual(total['heures_au_dessus_du_seuil'],
                         round(nuit * 365 / 2, 1))
        residuels = sum(1 for kwh in imports if kwh > self.SEUIL_KW + 1e-9)
        self.assertEqual(total['nombre_depassements_residuels'],
                         round(residuels / 2, 1))
        self.assertIsNone(total['reserve_secours'])
        self.assertNotIn('depassements_residuels', total)

    def test_backup_avec_appareils_publie_la_reserve_deduite(self):
        from apps.calepinage.services.batterie import reserve_depuis_appareils

        appareils = [{'nom': 'Réfrigérateur', 'puissance_continue_kw': 0.15,
                      'puissance_pointe_kw': 0.6, 'quantite': 1}]
        contexte = contexte_de_test(strategie='backup', heures=48,
                                    appareils=appareils, duree_secours_h=4)
        _suite, resultat = bloc.bloc_batterie(serie_de_test(heures=48),
                                              contexte)
        self.assertEqual(resultat['total']['reserve_secours'],
                         reserve_depuis_appareils(appareils, duree_h=4))
        self.assertIsNone(resultat['total']['pointe_apres_kw'])

    def test_acal793_faits_de_deux_jours_connus(self):
        # Deux jours : 4 kW de 8 h à 17 h, 1 kWh consommé chaque heure, une
        # banque de 10 kWh vide au départ. Elle se remplit chaque jour, et la
        # plus longue nuit (0 h-7 h, 8 pas) se termine batterie vide les deux
        # jours (14 h de nuit à 1 kWh > 10 kWh).
        suite, resultat = bloc.bloc_batterie(serie_de_test(heures=48),
                                             contexte_de_test(heures=48))
        faits = resultat['total']['faits_serie']
        self.assertEqual(faits['jours_total'], 2.0)
        self.assertEqual(faits['jours_pleine'], 2.0)
        self.assertEqual(faits['nuits_au_plancher'], 2.0)
        # Sans batterie : 20 kWh autoconsommés sur 80 kWh produits.
        self.assertEqual(faits['taux_autoconsommation_sans_batterie'], 0.25)
        export = sum(p['reseau_export_kwh'] for p in suite['points'])
        self.assertAlmostEqual(faits['part_surplus_injecte'],
                               export / (80.0 - 20.0), places=3)

    def test_acal793_nuit_ou_la_batterie_ne_se_vide_pas(self):
        # Mutant « le jour entier au lieu de la nuit » : la fin du jour
        # (23 h) n'est pas la fin de la plus longue nuit (7 h).
        contexte = contexte_de_test(heures=48)
        contexte['consommation']['import_intervalle']['valeurs'] = (
            [0.1] * 48)
        _suite, resultat = bloc.bloc_batterie(serie_de_test(heures=48),
                                              contexte)
        faits = resultat['total']['faits_serie']
        # 0 h-7 h du 1er jour : batterie vide au départ ⇒ plancher ; le 2e
        # jour, 14 h × 0,1 kWh < 10 kWh ⇒ jamais vide.
        self.assertEqual(faits['nuits_au_plancher'], 1.0)

    def test_autres_strategies_null(self):
        _suite, resultat = bloc.bloc_batterie(
            serie_de_test(heures=48), contexte_de_test(heures=48))
        for cle in ('pointe_avant_kw', 'pointe_apres_kw',
                    'heures_au_dessus_du_seuil',
                    'nombre_depassements_residuels', 'reserve_secours'):
            self.assertIsNone(resultat['total'][cle], cle)
