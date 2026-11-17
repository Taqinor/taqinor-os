"""TCH66-TCH68 — Mon rythme côté serveur : `rythme/`, `propositions/{id}/repondre/`, `preferences/`,
`coach/entete/`.

Base requise (`TestCase`) : joué par la CI. Jour injecté (`services.rythme.aujourdhui`), jamais
d'horloge vivante. Chaque test relit l'état STOCKÉ (réglages, plan du jour, cartes, préférences).
"""
import datetime
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.taches.choix import (
    CanalIncitation, ModeRythme, SourceObjectif, StatutJour, TypeIncitationEcran,
)
from apps.taches.models.rythme import IncitationCoach, ReglagesRythme
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

    def test_sans_reglages_404_et_rien_cree(self):
        reponse = self.api.post(URL, {'mode': 'pousser', 'objectif': 6}, format='json')
        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(ReglagesRythme.objects.exists())
