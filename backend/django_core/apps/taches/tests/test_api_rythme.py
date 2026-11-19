"""TCH66-TCH68 — Mon rythme côté serveur : `rythme/`, `propositions/{id}/repondre/`, `preferences/`,
`coach/entete/`.

Base requise (`TestCase`) : joué par la CI. Jour injecté (`services.rythme.aujourdhui`), jamais
d'horloge vivante. Chaque test relit l'état STOCKÉ (réglages, plan du jour, cartes, préférences).
"""
import datetime
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches.choix import (
    CanalIncitation, ModeRythme, SourceObjectif, StatutJour, StatutTache, TypeIncitationEcran,
)
from apps.taches.models.rythme import IncitationCoach, Preference, ReglagesRythme
from apps.taches.models.taches import RegleRecurrence
from apps.taches.services.gestes import annuler_geste
from apps.taches.tests import fabriques
from apps.taches.views.base import exemple_de

J = datetime.date(2026, 11, 17)  # mardi
URL = '/api/django/taches/rythme/'


def jours_evalues(compte, comptes, *, jusquau=J, statut=StatutJour.EVALUE):
    """Un `PlanJour` clos par compte, les jours qui PRÉCÈDENT `jusquau` (le dernier = veille)."""
    for rang, faites in enumerate(reversed(comptes), start=1):
        fabriques.plan(compte, jusquau - datetime.timedelta(days=rang), statut_jour=statut,
                       compte_rythme=faites, objectif_du_jour=5)


def carte(compte, type_, cle, donnees, **champs):
    champs.setdefault('jour', J)
    champs.setdefault('expire_le', J + datetime.timedelta(days=7))
    return IncitationCoach.objects.create(
        company=compte.company, proprietaire=compte, type=type_, cle=cle,
        canal=CanalIncitation.ECRAN, donnees=donnees, **champs)


class SerieDesJoursTravaillesTests(SimpleTestCase):
    """R2-120 sans base : `serializers.rythme._serie` sur des lignes en mémoire (calendrier remplacé)."""

    LUN_A_VEN = [datetime.date(2026, 11, n) for n in (2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 16)]

    def ligne(self, jour, statut=StatutJour.EVALUE, faites=4):
        return SimpleNamespace(jour=datetime.date(2026, 11, jour), statut_jour=statut, compte_rythme=faites,
                               objectif_du_jour=5, essentiels_faits=0, essentiels_choisis=0, plan_faites=0,
                               plan_prevues=0)

    def serie(self, plans, travailles=None):
        from apps.taches.serializers import rythme as forme
        jours = set(travailles or self.LUN_A_VEN)

        def calendrier(_user, du, au):
            return {jour for jour in jours if du <= jour <= au}

        with mock.patch.object(forme, 'jours_travailles_de', side_effect=calendrier):
            return forme._serie(object(), plans, J)

    def test_les_jours_travailles_sans_ligne_sont_sans_donnees_et_la_serie_en_garde_dix(self):
        plans = [self.ligne(3, faites=6), self.ligne(5), self.ligne(6), self.ligne(11, faites=5)]
        serie = self.serie(plans)
        self.assertEqual(len(serie), 10)
        self.assertEqual([b['jour'][-2:] for b in serie], ['03', '04', '05', '06', '09', '10', '11', '12', '13', '16'])
        self.assertEqual([b['statut_jour'] for b in serie],
                         ['evalue', 'sans_donnees', 'evalue', 'evalue', 'sans_donnees', 'sans_donnees', 'evalue',
                          'sans_donnees', 'sans_donnees', 'sans_donnees'])
        self.assertEqual([b['faites'] for b in serie], [6, 0, 4, 4, 0, 0, 5, 0, 0, 0])

    def test_une_ligne_sans_statut_sur_un_jour_travaille_est_sans_donnees(self):
        serie = self.serie([self.ligne(12, statut='', faites=0), self.ligne(13)])
        self.assertEqual([(b['jour'][-2:], b['statut_jour']) for b in serie],
                         [('12', 'sans_donnees'), ('13', 'evalue'), ('16', 'sans_donnees')])

    def test_un_jour_ferie_ou_en_conge_n_a_pas_de_barre(self):
        serie = self.serie([self.ligne(12), self.ligne(13, statut=StatutJour.NON_OUVRE),
                            self.ligne(16, statut=StatutJour.CONGE)])
        self.assertEqual([b['jour'][-2:] for b in serie], ['12'])

    def test_sans_aucune_ligne_pas_de_serie(self):
        self.assertEqual(self.serie([]), [])


class BaseRythme(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def setUp(self):
        horloge = mock.patch('apps.taches.services.rythme.aujourdhui', return_value=J)
        horloge.start()
        self.addCleanup(horloge.stop)
        self.api = APIClient()
        self.api.force_authenticate(self.u1)

    def reglages(self, **champs):
        return fabriques.reglages(self.u1, **champs)


class RythmeLectureTests(BaseRythme):
    def test_forme_exacte_de_l_echantillon(self):
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J - datetime.timedelta(days=12))
        jours_evalues(self.u1, [5, 6, 4, 5, 7, 5, 3, 6, 5, 4])
        reponse = self.api.get(URL)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(set(reponse.json()), set(exemple_de('rythme')))

    def test_trace_au_singulier_a_un_jour(self):
        """« 1 jour sur 3 », jamais « 1 jours » (textes.md, Trace)."""
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J - datetime.timedelta(days=3))
        jours_evalues(self.u1, [2, 6, 3])
        self.assertEqual(self.api.get(URL).json()['trace'], '5 faites ou plus 1 jour sur 3')

    def test_trace_au_singulier_a_zero_jour(self):
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J - datetime.timedelta(days=2))
        jours_evalues(self.u1, [2, 3])
        self.assertEqual(self.api.get(URL).json()['trace'], '5 faites ou plus 0 jour sur 2')

    def test_objectif_serie_trace_et_repere_calcules_des_plans(self):
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J - datetime.timedelta(days=8))
        jours_evalues(self.u1, [3, 4, 5, 5, 5, 6, 6, 7, 8])
        corps = self.api.get(URL).json()
        self.assertEqual(corps['objectif'], {'nb': 5, 'source': 'accepte', 'mode': 'pousser', 'zone': None})
        self.assertEqual(len(corps['serie']), 9)
        self.assertEqual(corps['serie'][-1]['jour'], (J - datetime.timedelta(days=1)).isoformat())
        self.assertEqual(corps['serie'][-1]['faites'], 8)
        self.assertEqual(corps['trace'], '5 faites ou plus 7 jours sur 9')
        # regles.md §6.5 point 8 : [3,4,5,5,5,6,6,7,8] → 5,8 sur 9 jours.
        self.assertEqual(corps['repere'], {'p60': 5.8, 'jours': 9})
        # Bloc ouvert à J−8 : [4,5,5,5,6,6,7,8], 7 jours à 5 ou plus.
        self.assertEqual(corps['bloc'], {'jours': 8, 'tenus': 7, 'sur': 10})
        self.assertIsNone(corps['geste_id'])

    def test_la_serie_sert_les_dix_jours_travailles_dont_ceux_sans_donnees(self):
        """R2-120 : 10 barres, un jour travaillé sans ligne est servi `sans_donnees` (jamais absent) ; un samedi ou
        un dimanche n'a pas de barre. J = mardi 17/11 ; lignes aux 03, 04, 05, 06, 11 et 12/11 (+ week-ends)."""
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J - datetime.timedelta(days=14))
        for jour, faites in ((3, 6), (4, 5), (5, 5), (6, 4), (11, 5), (12, 4)):
            fabriques.plan(self.u1, datetime.date(2026, 11, jour), statut_jour=StatutJour.EVALUE,
                           compte_rythme=faites, objectif_du_jour=5)
        for jour in (7, 8, 14):  # samedi, dimanche, samedi : posés `non_ouvre` par la nuit
            fabriques.plan(self.u1, datetime.date(2026, 11, jour), statut_jour=StatutJour.NON_OUVRE)
        corps = self.api.get(URL).json()
        self.assertEqual([(b['jour'][-2:], b['statut_jour'], b['faites']) for b in corps['serie']], [
            ('03', 'evalue', 6), ('04', 'evalue', 5), ('05', 'evalue', 5), ('06', 'evalue', 4),
            ('09', 'sans_donnees', 0), ('10', 'sans_donnees', 0), ('11', 'evalue', 5), ('12', 'evalue', 4),
            ('13', 'sans_donnees', 0), ('16', 'sans_donnees', 0)])
        vide = corps['serie'][4]
        self.assertEqual((vide['objectif'], vide['essentiel_faites'], vide['plan_lignes']), (None, 0, 0))
        self.assertEqual(corps['trace'], '5 faites ou plus 5 jours sur 10')

    def test_la_serie_ne_remonte_pas_avant_le_premier_jour_evalue(self):
        """Un compte récent n'a pas de barres vides pour les jours d'avant son premier jour lu."""
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE)
        fabriques.plan(self.u1, datetime.date(2026, 11, 12), statut_jour=StatutJour.EVALUE,
                       compte_rythme=4, objectif_du_jour=5)
        serie = self.api.get(URL).json()['serie']
        self.assertEqual([b['jour'][-2:] for b in serie], ['12', '13', '16'])
        self.assertEqual([b['statut_jour'] for b in serie], ['evalue', 'sans_donnees', 'sans_donnees'])

    def test_un_jour_de_conge_dit_n_a_pas_de_barre_vide(self):
        """Un jour en congé (préférence) n'est pas un jour travaillé : pas de barre synthétisée."""
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE)
        fabriques.plan(self.u1, datetime.date(2026, 11, 12), statut_jour=StatutJour.EVALUE,
                       compte_rythme=4, objectif_du_jour=5)
        Preference.objects.create(company=self.a, proprietaire=self.u1, cle='conges',
                                  valeur=[{'du': '2026-11-13', 'au': '2026-11-13'}])
        serie = self.api.get(URL).json()['serie']
        self.assertEqual([b['jour'][-2:] for b in serie], ['12', '16'])

    def test_moins_de_9_jours_repere_nul(self):
        self.reglages()
        jours_evalues(self.u1, [5, 5, 5])
        self.assertIsNone(self.api.get(URL).json()['repere'])

    def test_un_jour_conge_n_a_pas_de_barre(self):
        self.reglages()
        jours_evalues(self.u1, [4], jusquau=J - datetime.timedelta(days=1))
        fabriques.plan(self.u1, J - datetime.timedelta(days=1), statut_jour=StatutJour.CONGE)
        serie = self.api.get(URL).json()['serie']
        self.assertEqual([j['statut_jour'] for j in serie], ['evalue'])

    def test_sans_reglages_les_defauts_sans_rien_creer(self):
        corps = self.api.get(URL).json()
        self.assertEqual(corps['objectif'], {'nb': 5, 'source': 'defaut', 'mode': 'pousser', 'zone': None})
        self.assertEqual(corps['mode'], 'pousser')
        self.assertFalse(ReglagesRythme.objects.exists())

    def test_proposition_et_constat_rendus_a_la_lecture(self):
        self.reglages(palier=5)
        carte(self.u1, TypeIncitationEcran.PROPOSITION_PALIER, 'monter', {'N': 5, 'N1': 6, 'tenus': 7})
        carte(self.u1, TypeIncitationEcran.CONSTAT, 'C3', {'jour': 4, 'm1': 3.1, 'm2': 5.2})
        corps = self.api.get(URL).json()
        attendu = exemple_de('proposition')
        self.assertEqual(corps['proposition']['texte'], attendu['texte'])
        self.assertEqual(corps['proposition']['boutons'], attendu['boutons'])
        self.assertEqual(corps['constats'][0]['texte'], exemple_de('rythme')['constats'][0]['texte'])

    def test_tenir_rend_la_zone(self):
        self.reglages(mode=ModeRythme.TENIR, tenir_reference=5, tenir_fixee_le=J - datetime.timedelta(days=3))
        corps = self.api.get(URL).json()
        self.assertEqual(corps['objectif'], {'nb': 5, 'source': 'calcule', 'mode': 'tenir', 'zone': [4, 6]})
        self.assertFalse(corps['tenir']['provisoire'])
        self.assertIsNone(corps['bloc'])

    def test_les_cartes_d_un_autre_compte_ne_sont_jamais_lues(self):
        self.reglages()
        carte(self.ailleurs, TypeIncitationEcran.PROPOSITION_PALIER, 'monter', {'N': 5, 'N1': 6, 'tenus': 7})
        self.assertIsNone(self.api.get(URL).json()['proposition'])


class RythmeEcritureTests(BaseRythme):
    def test_objectif_dit_s_applique_aujourd_hui(self):
        reglages = self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE)
        plan = fabriques.plan(self.u1, J, objectif_du_jour=5)
        reponse = self.api.post(URL, {'mode': 'pousser', 'objectif': 7}, format='json')
        self.assertEqual(reponse.status_code, 200)
        reglages.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.palier_source), (7, SourceObjectif.DIT))
        self.assertEqual(plan.objectif_du_jour, 7)
        self.assertEqual(reponse.json()['objectif']['nb'], 7)
        self.assertIsNotNone(reponse.json()['geste_id'])

    def test_un_jour_clos_ne_change_pas(self):
        self.reglages(palier=5)
        plan = fabriques.plan(self.u1, J, objectif_du_jour=5, cloture_le=datetime.datetime(
            2026, 11, 17, 18, 0, tzinfo=datetime.timezone.utc))
        self.api.post(URL, {'mode': 'pousser', 'objectif': 8}, format='json')
        plan.refresh_from_db()
        self.assertEqual(plan.objectif_du_jour, 5)

    def test_plus_et_moins_plancher_et_plafond(self):
        reglages = self.reglages(palier=1, palier_source=SourceObjectif.DIT)
        self.api.post(URL, {'mode': 'pousser', 'sens': 'moins'}, format='json')
        reglages.refresh_from_db()
        self.assertEqual(reglages.palier, 1)
        self.api.post(URL, {'mode': 'pousser', 'sens': 'plus'}, format='json')
        reglages.refresh_from_db()
        self.assertEqual(reglages.palier, 2)

    def test_hors_1_12_400(self):
        reglages = self.reglages(palier=5)
        for valeur in (15, 0, 'sept', True):
            with self.subTest(valeur=valeur):
                reponse = self.api.post(URL, {'mode': 'pousser', 'objectif': valeur}, format='json')
                self.assertEqual(reponse.status_code, 400)
                self.assertEqual(reponse.json(), {'objectif': ['Entre 1 et 12.']})
        reglages.refresh_from_db()
        self.assertEqual(reglages.palier, 5)

    def test_objectif_hors_des_flottants_400(self):
        """Revue F2 tour 2 #12 : `1e400` (lu comme l'infini) → 400 au champ, jamais 500."""
        self.reglages()
        reponse = self.api.post(URL, '{"mode": "pousser", "objectif": 1e400}', content_type='application/json')
        self.assertEqual((reponse.status_code, reponse.json()), (400, {'objectif': ['Entre 1 et 12.']}))

    def test_mode_inconnu_400(self):
        self.reglages()
        reponse = self.api.post(URL, {'mode': 'turbo'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json(), {'mode': ['Valeur inconnue.']})

    def test_bascule_vers_tenir_abandonne_la_proposition(self):
        reglages = self.reglages(palier=6, palier_source=SourceObjectif.ACCEPTE)
        jours_evalues(self.u1, [5] * 14)
        ancienne = carte(self.u1, TypeIncitationEcran.PROPOSITION_PALIER, 'monter', {'N': 6, 'N1': 7, 'tenus': 5})
        corps = self.api.post(URL, {'mode': 'tenir'}, format='json').json()
        reglages.refresh_from_db()
        self.assertEqual(reglages.mode, ModeRythme.TENIR)
        self.assertEqual(float(reglages.tenir_reference), 5.0)
        self.assertEqual(reglages.tenir_fixee_le, J)
        self.assertIsNone(corps['proposition'])
        ancienne.refresh_from_db()
        self.assertLess(ancienne.expire_le, J)

    def test_annuler_restaure_le_palier(self):
        reglages = self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE)
        geste_id = self.api.post(URL, {'mode': 'pousser', 'objectif': 9}, format='json').json()['geste_id']
        annuler_geste(self.u1, geste_id)
        reglages.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.palier_source), (5, SourceObjectif.ACCEPTE))

    def test_le_mode_ne_change_que_par_cette_route(self):
        reglages = self.reglages()
        self.api.get(URL)
        reglages.refresh_from_db()
        self.assertEqual(reglages.mode, ModeRythme.POUSSER)
        self.api.post(URL, {'mode': 'libre'}, format='json')
        reglages.refresh_from_db()
        self.assertEqual(reglages.mode, ModeRythme.LIBRE)
        self.assertIsNone(self.api.get(URL).json()['objectif']['nb'])

    def test_r2_122_aller_retour_des_modes_rend_l_objectif_d_avant(self):
        """F2 n°5 : Garder ce rythme → Sans objectif → En faire plus rend « 6 » (dit), pas la valeur par défaut."""
        self.reglages(palier=6, palier_source=SourceObjectif.DIT)
        for mode in ('tenir', 'libre', 'pousser'):
            corps = self.api.post(URL, {'mode': mode}, format='json').json()
        self.assertEqual(corps['objectif'], {'nb': 6, 'source': 'dit', 'mode': 'pousser', 'zone': None})

    def test_compte_neuf_dit_son_objectif_avant_sa_premiere_tache(self):
        """Parcours « compte neuf → aujourdhui/ → dire son objectif → première tâche » : la lecture ne
        crée rien, le geste crée les réglages, la première tâche les retrouve (une seule ligne)."""
        aujourdhui = '/api/django/taches/aujourdhui/'
        self.assertEqual(self.api.get(aujourdhui, {'jour': J.isoformat()}).status_code, 200)
        self.assertFalse(ReglagesRythme.objects.exists())
        reponse = self.api.post(URL, {'mode': 'pousser', 'objectif': 6}, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()['objectif']['nb'], 6)
        reglages = ReglagesRythme.objects.get(company=self.a, proprietaire=self.u1)
        self.assertEqual((reglages.palier, reglages.palier_source), (6, SourceObjectif.DIT))
        lignes = [{'index': 0, 'titre': 'Appeler Karim', 'jour_prevu': J.isoformat()}]
        cree = self.api.post('/api/django/taches/saisie-rapide/', {'lignes': lignes}, format='json')
        self.assertEqual(cree.status_code, 201, cree.content[:300])
        self.assertEqual(ReglagesRythme.objects.filter(proprietaire=self.u1).count(), 1)
        self.assertEqual(self.api.get(aujourdhui, {'jour': J.isoformat()}).json()['objectif']['nb'], 6)

    def test_garder_ce_rythme_sous_un_par_jour_jamais_zero(self):
        """Revue F2 tour 2 #9 : 4 tâches en 14 jours évalués → objectif 1 (0 à 1) partout : `rythme/`,
        le toast, le plan du jour, Aujourd'hui et l'en-tête du Copilote — jamais « 0 » ni « -1 »."""
        from apps.taches.models.gestes import GesteAnnulable
        self.reglages()
        plan = fabriques.plan(self.u1, J)
        jours_evalues(self.u1, [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1])
        corps = self.api.post(URL, {'mode': 'tenir'}, format='json').json()
        self.assertEqual(corps['objectif'], {'nb': 1, 'source': 'calcule', 'mode': 'tenir', 'zone': [0, 1]})
        self.assertEqual(GesteAnnulable.objects.get(pk=corps['geste_id']).message,
                         'Garder ce rythme : environ 1 tâche par jour (0 à 1). '
                         "Je ne te pousse plus ; je te préviens seulement si tu t'en éloignes.")
        plan.refresh_from_db()
        self.assertEqual(plan.objectif_du_jour, 1)
        jour = self.api.get('/api/django/taches/aujourdhui/', {'jour': J.isoformat()}).json()
        self.assertEqual((jour['objectif']['nb'], jour['objectif']['zone']), (1, [0, 1]))
        self.assertIn('objectif 1 (calculé) · 0 sur 1',
                      self.api.get('/api/django/taches/coach/entete/').json()['lignes'][0])

    def test_corps_refuse_ne_cree_pas_les_reglages(self):
        reponse = self.api.post(URL, {'mode': 'pousser', 'objectif': 40}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertFalse(ReglagesRythme.objects.exists())


class RepondreTests(BaseRythme):
    """TCH67 — `propositions/{id}/repondre/` : réponses permises par clé, 409, refus sous verrou."""

    def repondre(self, carte_, reponse):
        return self.api.post(f'{URL}propositions/{carte_.pk}/repondre/', {'reponse': reponse}, format='json')

    def monter(self, refus=1, n=5, **champs):
        return carte(self.u1, TypeIncitationEcran.PROPOSITION_PALIER, 'monter',
                     {'N': n, 'N1': n + 1, 'tenus': 7, 'refus': refus}, **champs)

    def test_monter_oui_un_cran_et_forme_repondue(self):
        reglages = self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J)
        carte_ = self.monter()
        reponse = self.repondre(carte_, 'oui')
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('proposition_repondue')))
        self.assertEqual(corps['proposition']['boutons'], [])
        self.assertEqual(corps['geste_id'], corps['rythme']['geste_id'])
        reglages.refresh_from_db()
        carte_.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.palier_source, reglages.essai_restant),
                         (6, SourceObjectif.ACCEPTE, True))
        self.assertEqual(carte_.reponse, 'oui')
        self.assertIsNotNone(carte_.repondu_le)

    def test_refus_1_2_puis_4_blocs_sautes(self):
        reglages = self.reglages(palier=5, bloc_debut=J)
        for rang, attendu in ((1, 1), (2, 2), (3, 4)):
            self.repondre(self.monter(refus=rang, jour=J - datetime.timedelta(days=10 * (3 - rang))),
                          'pas_maintenant')
            reglages.refresh_from_db()
            self.assertEqual((reglages.refus_montee, reglages.blocs_a_sauter, reglages.palier), (rang, attendu, 5))

    def test_garder_ce_rythme_seulement_au_3e_refus(self):
        reglages = self.reglages(palier=5, refus_montee=2)
        tot = self.monter(refus=1, jour=J - datetime.timedelta(days=1))
        reponse = self.repondre(tot, 'garder_ce_rythme')
        self.assertEqual((reponse.status_code, reponse.json()), (400, {'reponse': ['Réponse inconnue.']}))
        self.assertEqual(self.repondre(self.monter(refus=3), 'garder_ce_rythme').status_code, 200)
        reglages.refresh_from_db()
        self.assertEqual(reglages.mode, ModeRythme.TENIR)

    def test_baisse_jamais_imposee(self):
        reglages = self.reglages(palier=6, palier_source=SourceObjectif.ACCEPTE)
        baisser = carte(self.u1, TypeIncitationEcran.PROPOSITION_PALIER, 'baisser', {'N': 6, 'N_1': 5, 'tenus': 2})
        self.repondre(baisser, 'garder')
        reglages.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.baisse_refusee), (6, True))
        autre = carte(self.u1, TypeIncitationEcran.PROPOSITION_PALIER, 'baisser', {'N': 6, 'N_1': 5, 'tenus': 1},
                      jour=J - datetime.timedelta(days=1))
        self.repondre(autre, 'oui')
        reglages.refresh_from_db()
        self.assertEqual(reglages.palier, 5)

    def test_premier_oui_prend_la_journee_type(self):
        reglages = self.reglages(bloc_debut=J)
        self.repondre(carte(self.u1, TypeIncitationEcran.PROPOSITION_PALIER, 'premier', {'type': 3}), 'oui')
        reglages.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.palier_source), (3, SourceObjectif.ACCEPTE))

    def test_vaut_le_jour_meme_avant_le_plan_sinon_le_lendemain(self):
        reglages = self.reglages(palier=5, bloc_debut=J)
        plan = fabriques.plan(self.u1, J, objectif_du_jour=5)
        self.repondre(self.monter(), 'oui')
        plan.refresh_from_db()
        self.assertEqual(plan.objectif_du_jour, 6)
        plan.planifie_le = datetime.datetime(2026, 11, 17, 8, 0, tzinfo=datetime.timezone.utc)
        plan.save(update_fields=['planifie_le'])
        # Une carte calculée depuis le palier courant (6 → 7) : le palier monte, le plan validé de J garde 6.
        self.assertEqual(self.repondre(self.monter(n=6, jour=J - datetime.timedelta(days=1)), 'oui').status_code, 200)
        plan.refresh_from_db()
        reglages.refresh_from_db()
        self.assertEqual((plan.objectif_du_jour, reglages.palier), (6, 7))

    def test_apres_le_plan_valide_l_objectif_du_jour_reste_celui_du_plan_partout(self):
        """regles.md §6.5 point 6 : une réponse donnée APRÈS la validation du plan vaut le lendemain. Le jour
        même, Aujourd'hui et l'en-tête du Copilote gardent l'objectif du plan validé (5), comme le bilan — le
        palier, lui, est monté (6) et vaudra demain (revue F2 tour 2 #3, suite)."""
        reglages = self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J)
        plan = fabriques.plan(self.u1, J, objectif_du_jour=5,
                              planifie_le=datetime.datetime(2026, 11, 17, 8, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(self.repondre(self.monter(), 'oui').status_code, 200)
        plan.refresh_from_db()
        reglages.refresh_from_db()
        self.assertEqual((plan.objectif_du_jour, reglages.palier), (5, 6))
        jour = self.api.get('/api/django/taches/aujourdhui/', {'jour': J.isoformat()}).json()
        self.assertEqual(jour['objectif']['nb'], 5)
        self.assertIn(' · 0 sur 5', self.api.get('/api/django/taches/coach/entete/').json()['lignes'][0])

    def test_reponse_inconnue_ou_reservee_a_la_nuit_400(self):
        self.reglages()
        carte_ = self.monter()
        for reponse in ('expiree', 'ignoree', 'peut-etre', 'garder'):
            with self.subTest(reponse=reponse):
                self.assertEqual(self.repondre(carte_, reponse).json(), {'reponse': ['Réponse inconnue.']})
        carte_.refresh_from_db()
        self.assertEqual(carte_.reponse, '')

    def test_reponse_liste_ou_objet_400(self):
        """Revue F2 tour 2 #12 : `reponse` liste ou objet → 400 « Réponse inconnue. », jamais 500."""
        self.reglages()
        carte_ = self.monter()
        for reponse in (['oui'], {'oui': 1}):
            with self.subTest(reponse=reponse):
                self.assertEqual((self.repondre(carte_, reponse).status_code, self.repondre(carte_, reponse).json()),
                                 (400, {'reponse': ['Réponse inconnue.']}))

    def test_expiree_ou_deja_repondue_409(self):
        reglages = self.reglages(palier=5)
        expiree = self.monter(expire_le=J - datetime.timedelta(days=1))
        reponse = self.repondre(expiree, 'pas_maintenant')
        self.assertEqual((reponse.status_code, reponse.json()['code']), (409, 'proposition_expiree'))
        self.assertEqual(reponse.json()['detail'], exemple_de('erreurs')['proposition_expiree']['detail'])
        ouverte = self.monter(jour=J - datetime.timedelta(days=1))
        self.assertEqual(self.repondre(ouverte, 'pas_maintenant').status_code, 200)
        self.assertEqual(self.repondre(ouverte, 'pas_maintenant').status_code, 409)
        reglages.refresh_from_db()
        self.assertEqual(reglages.refus_montee, 1)  # le second refus n'est jamais compté

    def test_carte_d_un_autre_compte_404(self):
        self.reglages()
        etrangere = carte(self.ailleurs, TypeIncitationEcran.PROPOSITION_PALIER, 'monter',
                          {'N': 5, 'N1': 6, 'tenus': 7})
        self.assertEqual(self.repondre(etrangere, 'oui').status_code, 404)
        etrangere.refresh_from_db()
        self.assertEqual(etrangere.reponse, '')

    def test_constat_c3_oui_ajoute_le_jour_court(self):
        self.reglages()
        constat = carte(self.u1, TypeIncitationEcran.CONSTAT, 'C3', {'jour': 4, 'm1': 3.1, 'm2': 5.2})
        self.repondre(constat, 'oui')
        corps = self.api.get(URL).json()
        self.assertEqual([(p['cle'], p['valeur'], p['source']) for p in corps['preferences']],
                         [('jours_courts', [4], 'carte')])
        self.assertEqual(corps['constats'], [])

    def test_c5_n_admet_que_ok(self):
        self.reglages()
        c5 = carte(self.u1, TypeIncitationEcran.CONSTAT, 'C5', {'p': 40, 'n': 30, 'h1': 10, 'h2': 12})
        self.assertEqual(self.repondre(c5, 'oui').status_code, 400)
        self.assertEqual(self.repondre(c5, 'ok').status_code, 200)

    def test_pause_reactiver_retire_le_type(self):
        reglages = self.reglages(pauses_sollicitations=[{'type': 'plan_matin', 'ignorees': 14}])
        pause = carte(self.u1, TypeIncitationEcran.PAUSE, 'plan_matin', {'type_pause': 'plan_matin', 'ignorees': 14})
        self.repondre(pause, 'reactiver')
        reglages.refresh_from_db()
        self.assertEqual(reglages.pauses_sollicitations, [])

    def test_objectif_dit_puis_monter_ne_saute_jamais_deux_crans(self):
        """Revue F2 tour 2 #5 : l'objectif dit (8) abandonne la carte « Monter à 6 » ; répondue quand
        même (écran périmé), elle ne change rien — jamais 9."""
        reglages = self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J)
        carte_ = self.monter()
        corps = self.api.post(URL, {'mode': 'pousser', 'objectif': 8}, format='json').json()
        self.assertIsNone(corps['proposition'])
        self.assertEqual(self.repondre(carte_, 'oui').status_code, 409)  # abandonnée, comme à une bascule
        reglages.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.palier_source), (8, SourceObjectif.DIT))

    def test_moins_puis_descendre_un_seul_cran(self):
        """#5 : « − » (6 → 5) puis le bouton « Descendre à 5 » d'une carte calculée à 6 : palier 5,
        jamais 4 (§6.5 « jamais plus d'un cran »)."""
        reglages = self.reglages(palier=6, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J)
        baisser = carte(self.u1, TypeIncitationEcran.PROPOSITION_PALIER, 'baisser', {'N': 6, 'N_1': 5, 'tenus': 2})
        self.api.post(URL, {'mode': 'pousser', 'sens': 'moins'}, format='json')
        self.repondre(baisser, 'oui')
        reglages.refresh_from_db()
        self.assertEqual(reglages.palier, 5)

    def test_apres_plus_la_carte_n_est_plus_servie(self):
        """#5 (a) : « + » abandonne la proposition de palier ouverte : ni `rythme/` ni la carte du moment."""
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J)
        carte_ = self.monter()
        self.assertEqual(self.api.get(URL).json()['proposition']['id'], carte_.pk)
        self.api.post(URL, {'mode': 'pousser', 'sens': 'plus'}, format='json')
        self.assertIsNone(self.api.get(URL).json()['proposition'])
        moment = self.api.get('/api/django/taches/aujourdhui/', {'jour': J.isoformat()}).json()['carte_du_moment']
        self.assertFalse(moment and (moment.get('proposition') or {}).get('id') == carte_.pk)

    def test_oui_repart_le_bloc(self):
        """#8 : « Oui » six jours après la carte : les jours faits à 5 ne comptent pas contre 6."""
        reglages = self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE,
                                 bloc_debut=J - datetime.timedelta(days=6))
        jours_evalues(self.u1, [5] * 6)
        self.assertEqual(self.api.get(URL).json()['bloc'], {'jours': 6, 'tenus': 6, 'sur': 10})
        self.repondre(self.monter(jour=J - datetime.timedelta(days=6)), 'oui')
        reglages.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.essai_restant, reglages.bloc_debut),
                         (6, True, J + datetime.timedelta(days=1)))
        self.assertEqual(self.api.get(URL).json()['bloc'], {'jours': 0, 'tenus': 0, 'sur': 10})

    def test_carte_perimee_close_sans_changer_le_palier(self):
        """#5 (b) : une carte calculée d'un autre palier que le courant (5 → 6, palier déjà 7) est close
        par la réponse ; « Oui » n'applique jamais un autre nombre que celui de la carte."""
        reglages = self.reglages(palier=7, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J)
        carte_ = self.monter()
        reponse = self.repondre(carte_, 'oui')
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.json()['rythme']['proposition'])
        reglages.refresh_from_db()
        carte_.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.essai_restant), (7, False))
        self.assertEqual(carte_.reponse, 'oui')

    def test_annuler_la_reponse_rouvre_la_carte_et_le_palier(self):
        reglages = self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE, bloc_debut=J)
        carte_ = self.monter()
        geste_id = self.repondre(carte_, 'oui').json()['geste_id']
        annuler_geste(self.u1, geste_id)
        reglages.refresh_from_db()
        carte_.refresh_from_db()
        self.assertEqual((reglages.palier, carte_.reponse, carte_.repondu_le), (5, '', None))


class PreferencesTests(BaseRythme):
    """TCH68 — `preferences/` : 11 clés validées, anciens noms refusés, retirer, annuler."""

    URL_PREF = '/api/django/taches/preferences/'

    def poser(self, cle, valeur, **entetes):
        return self.api.post(self.URL_PREF, {'cle': cle, 'valeur': valeur}, format='json', **entetes)

    def test_poser_rend_rythme_avec_la_preference(self):
        self.reglages()
        reponse = self.poser('heure_limite', '19:00')
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('rythme')))
        self.assertEqual([(p['cle'], p['valeur'], p['source']) for p in corps['preferences']],
                         [('heure_limite', '19:00', 'ecran')])
        self.assertIsNotNone(corps['geste_id'])
        from apps.taches.models.gestes import GesteAnnulable
        # textes.md §2.15 : « Noté : {phrase de la préférence} · Annuler ».
        self.assertEqual(GesteAnnulable.objects.get(pk=corps['geste_id']).message,
                         "Noté : sollicitations jusqu'à 19:00")

    def test_sous_l_entete_assistant_la_source_est_le_copilote(self):
        self.poser('heure_limite', '19:00', HTTP_X_TAQINOR_ASSISTANT='1')
        self.assertEqual(self.api.get(URL).json()['preferences'][0]['source'], 'copilote')

    def test_les_onze_cles_et_leurs_valeurs(self):
        valeurs = {
            'capacite_jour_min': 300, 'jours_travailles': '1111100', 'jours_courts': [4],
            'conges': [{'du': '2026-12-20', 'au': '2027-01-03'}], 'heure_matin': 'off',
            'relance_jour': '15:30', 'heure_soir': '18:00', 'heure_limite': '20:00', 'revue_semaine': 'auto',
            'essentiel_le_matin': True, 'note_libre': ['Pas de rendez-vous le lundi matin'],
        }
        for cle, valeur in valeurs.items():
            with self.subTest(cle=cle):
                self.assertEqual(self.poser(cle, valeur).status_code, 200)
        dites = {p['cle']: p['valeur'] for p in self.api.get(URL).json()['preferences']}
        self.assertEqual(dites, valeurs)

    def test_heure_attendue(self):
        for valeur in ('19h', '25:00', 7, ''):
            with self.subTest(valeur=valeur):
                reponse = self.poser('heure_limite', valeur)
                self.assertEqual((reponse.status_code, reponse.json()),
                                 (400, {'valeur': ['Heure attendue (HH:MM).']}))
        self.assertEqual(self.poser('heure_limite', 'off').status_code, 400)  # la limite ne s'éteint pas

    def test_heure_suivie_d_un_saut_de_ligne_refusee(self):
        """Revue F3 #8 : `$` acceptait un saut de ligne final (« 08:30\\n ») que le balayage ne sait pas lire."""
        for cle in ('heure_matin', 'relance_jour', 'heure_soir', 'heure_limite'):
            with self.subTest(cle=cle):
                reponse = self.poser(cle, '08:30\n')
                self.assertEqual((reponse.status_code, reponse.json()),
                                 (400, {'valeur': ['Heure attendue (HH:MM).']}))

    def test_anciens_noms_refuses(self):
        for cle in ('jours_off', 'vendredi', 'conges_du', 'conges_au', 'heure_plan_matin', 'rappel_journee',
                    'heure_bilan_soir', 'heure_limite_rappels', 'semaine_revue', 'mode', 'palier'):
            with self.subTest(cle=cle):
                self.assertEqual(self.poser(cle, '19:00').json(), {'cle': ['Clé inconnue.']})

    def test_cle_liste_ou_objet_400(self):
        """Revue F2 tour 2 #12 : `cle` liste ou objet → 400 « Clé inconnue. », jamais 500."""
        for cle in (['heure_soir'], {'heure_soir': 1}):
            with self.subTest(cle=cle):
                reponse = self.poser(cle, '19:00')
                self.assertEqual((reponse.status_code, reponse.json()), (400, {'cle': ['Clé inconnue.']}))

    def test_bornes_des_valeurs(self):
        cas = (('capacite_jour_min', 20, 'Entre 30 et 720 minutes.'),
               ('conges', [{'du': '2026-12-20', 'au': '2026-12-01'}], 'La date de fin précède la date de début.'),
               ('jours_travailles', '0000000', 'Garde au moins un jour travaillé.'),
               ('note_libre', ['x'] * 11, '10 phrases au plus.'),
               ('note_libre', ['x' * 201], '200 caractères au plus.'),
               ('note_libre', ['a\x00b'], 'Valeur inconnue.'),
               ('revue_semaine', 'lundi', 'Choisis un jour, Auto ou Éteinte.'))
        for cle, valeur, message in cas:
            with self.subTest(cle=cle, valeur=valeur):
                self.assertEqual(self.poser(cle, valeur).json(), {'valeur': [message]})
        self.assertEqual(self.api.get(URL).json()['preferences'], [])

    def test_retirer_puis_annuler(self):
        self.poser('heure_limite', '19:00')
        reponse = self.api.delete(f'{self.URL_PREF}heure_limite/')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()['preferences'], [])
        self.assertEqual(self.api.delete(f'{self.URL_PREF}heure_limite/').status_code, 404)
        self.assertEqual(self.api.delete(f'{self.URL_PREF}jours_off/').status_code, 404)
        annuler_geste(self.u1, reponse.json()['geste_id'])
        self.assertEqual([p['valeur'] for p in self.api.get(URL).json()['preferences']], ['19:00'])

    def test_le_mode_ne_passe_jamais_par_une_preference(self):
        reglages = self.reglages()
        self.poser('mode', 'libre')
        reglages.refresh_from_db()
        self.assertEqual(reglages.mode, ModeRythme.POUSSER)


class EnteteCoachTests(BaseRythme):
    """TCH68 — `coach/entete/` : deux lignes, 300 caractères au plus, aucune note ni titre."""

    URL_ENTETE = '/api/django/taches/coach/entete/'
    URL_PREF = '/api/django/taches/preferences/'

    def test_deux_lignes_calculees(self):
        self.reglages(palier=5, palier_source=SourceObjectif.ACCEPTE)
        fait_le = timezone.make_aware(datetime.datetime(2026, 11, 17, 10, 0))
        fabriques.tache(self.u1, titre='Titre secret', statut=StatutTache.FAIT, fait_le=fait_le)
        regle = RegleRecurrence.objects.create(company=self.a, proprietaire=self.u1, frequence='quotidien',
                                               date_debut=J)
        fabriques.tache(self.u1, statut=StatutTache.FAIT, fait_le=fait_le, recurrence=regle)  # routine : 0
        for cle, valeur in (('heure_limite', '19:00'), ('jours_courts', [4]), ('note_libre', ['Note privée'])):
            self.api.post(self.URL_PREF, {'cle': cle, 'valeur': valeur}, format='json')
        corps = self.api.get(self.URL_ENTETE).json()
        self.assertEqual(set(corps), set(exemple_de('coach_entete')))
        self.assertEqual(corps['lignes'], [
            'Rythme : En faire plus · objectif 5 (accepté) · 1 sur 5',
            "Préférences dites : sollicitations jusqu'à 19:00 · jour court : vendredi"])
        self.assertNotIn('Note privée', ''.join(corps['lignes']))
        self.assertNotIn('Titre secret', ''.join(corps['lignes']))

    def test_trois_cents_caracteres_au_plus(self):
        self.reglages()
        conges = [{'du': f'2027-0{m}-01', 'au': f'2027-0{m}-02'} for m in range(1, 10)]
        self.api.post(self.URL_PREF, {'cle': 'conges', 'valeur': conges}, format='json')
        self.api.post(self.URL_PREF, {'cle': 'jours_travailles', 'valeur': '1111111'}, format='json')
        lignes = self.api.get(self.URL_ENTETE).json()['lignes']
        self.assertLessEqual(sum(len(ligne) for ligne in lignes), 300)
        self.assertEqual(len(lignes), 2)

    def test_sans_preference_une_ligne(self):
        self.assertEqual(self.api.get(self.URL_ENTETE).json()['lignes'],
                         ['Rythme : En faire plus · objectif 5 (par défaut) · 0 sur 5'])
