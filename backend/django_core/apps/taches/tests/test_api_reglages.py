"""TCH69 — Réglages : `GET` et `PATCH reglages/` en liste blanche ; TCH155 — coupe-circuit `reglages-societe/`.

Base requise (`TestCase`) : joué par la CI. Jour injecté (`services.rythme.aujourdhui`). Chaque test
relit l'état STOCKÉ ; « enregistrer → rouvrir → enregistrer sans toucher » compare l'objet serveur.
"""
import datetime
import re
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.taches.choix import CanalIncitation, ModeRythme, StatutJour, TypeIncitationEcran
from apps.taches.models.journee import PlanJour
from apps.taches.models.presence import ReglagesSociete
from apps.taches.models.rythme import IncitationCoach, ReglagesRythme
from apps.taches.tests import fabriques
from apps.taches.views.base import exemple_de

J = datetime.date(2026, 11, 17)
URL = '/api/django/taches/reglages/'
URL_SOCIETE = '/api/django/taches/reglages-societe/'
INSTANT = datetime.datetime(2026, 11, 17, 14, 5, tzinfo=datetime.timezone.utc)
HEURE = re.compile(r'^\d{2}:\d{2}$')


def carte(compte, type_, cle, **champs):
    return IncitationCoach.objects.create(company=compte.company, proprietaire=compte, type=type_, cle=cle,
                                          canal=CanalIncitation.ECRAN, jour=J, **champs)


class ReglagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = fabriques.societe('a')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.admin = fabriques.compte(cls.a, admin=True, nom='admin')

    def setUp(self):
        horloge = mock.patch('apps.taches.services.rythme.aujourdhui', return_value=J)
        horloge.start()
        self.addCleanup(horloge.stop)
        self.api = APIClient()
        self.api.force_authenticate(self.u1)

    def patch(self, corps):
        return self.api.patch(URL, corps, format='json')

    def test_forme_exacte_et_defauts(self):
        corps = self.api.get(URL).json()
        self.assertEqual(set(corps), set(exemple_de('reglages')))
        self.assertEqual(corps['sollicitations'], {'heure_matin': '08:30', 'relance_jour': '15:00',
                                                   'heure_soir': '18:00', 'heure_limite': '20:00',
                                                   'revue_semaine': 'auto'})
        self.assertEqual(corps['familles_suggestions'], exemple_de('reglages')['familles_suggestions'])
        self.assertFalse(corps['est_admin'])
        self.assertFalse(corps['titres_notifications_demande'])
        self.assertIsNone(corps['raccourci_siri_url'])
        self.assertFalse(ReglagesRythme.objects.exists())  # lire ne crée rien (invariant 29)

    def test_fenetre_de_la_societe_en_heures(self):
        fenetre = self.api.get(URL).json()['fenetre_societe']
        self.assertEqual(set(fenetre), {'debut', 'fin'})
        self.assertRegex(fenetre['debut'], HEURE)
        self.assertLess(fenetre['debut'], fenetre['fin'])

    def test_heures_dites_et_administrateur(self):
        api = APIClient()
        api.force_authenticate(self.admin)
        api.post('/api/django/taches/preferences/', {'cle': 'heure_limite', 'valeur': '19:00'}, format='json')
        corps = api.get(URL).json()
        self.assertEqual(corps['sollicitations']['heure_limite'], '19:00')
        self.assertTrue(corps['est_admin'])

    @override_settings(TACHES_RACCOURCI_SIRI_URL='https://www.icloud.com/shortcuts/abc')
    def test_raccourci_siri_lit_le_reglage(self):
        self.assertEqual(self.api.get(URL).json()['raccourci_siri_url'], 'https://www.icloud.com/shortcuts/abc')

    def test_titre_au_premier_rappel_pose_la_question(self):
        reglages = fabriques.reglages(self.u1)
        corps = self.patch({'titres_notifications': True}).json()
        reglages.refresh_from_db()
        self.assertTrue(reglages.titres_notifications)
        self.assertIsNotNone(reglages.titres_notifications_demande_le)
        self.assertTrue(corps['titres_notifications_demande'])

    def test_hors_liste_blanche_non_modifiable(self):
        reglages = fabriques.reglages(self.u1)
        reponse = self.patch({'mode': 'libre', 'palier': 9, 'titres_tuile': False})
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.json(), {'mode': ['Non modifiable ici.'], 'palier': ['Non modifiable ici.']})
        reglages.refresh_from_db()
        self.assertEqual((reglages.mode, reglages.palier, reglages.titres_tuile), (ModeRythme.POUSSER, None, True))

    def test_suggestions_societe_reservee_a_un_administrateur(self):
        fabriques.reglages(self.u1)
        reponse = self.patch({'suggestions_societe': True})
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(reponse.json(), {'suggestions_societe': ['Réservé à un administrateur.']})
        reglages_admin = fabriques.reglages(self.admin)
        api = APIClient()
        api.force_authenticate(self.admin)
        self.assertEqual(api.patch(URL, {'suggestions_societe': True}, format='json').status_code, 200)
        reglages_admin.refresh_from_db()
        self.assertTrue(reglages_admin.suggestions_societe)

    def test_bornes(self):
        fabriques.reglages(self.u1)
        for corps in ({'projet_arret_jours': 4}, {'projet_arret_jours': 31}, {'familles_suggestions': ['inconnue']},
                      {'titres_tuile': 'oui'}, {'rappel_avant_bloc_min': 0}):
            with self.subTest(corps=corps):
                self.assertEqual(self.patch(corps).status_code, 400)
        self.assertEqual(self.patch({'projet_arret_jours': 30, 'rappel_avant_bloc_min': 10}).status_code, 200)

    def test_enregistrer_rouvrir_enregistrer_sans_toucher(self):
        fabriques.reglages(self.u1)
        self.patch({'messages_sans_delai': True, 'projet_arret_jours': 12,
                    'familles_suggestions': ['devis_accepte', 'visite_validee']})
        premier = self.api.get(URL).json()
        modifiables = {cle: premier[cle] for cle in ('messages_sans_delai', 'projet_arret_jours',
                                                     'familles_suggestions', 'titres_calendrier')}
        self.patch(modifiables)
        self.assertEqual(self.api.get(URL).json(), premier)

    def test_reactiver_un_type_en_pause(self):
        reglages = fabriques.reglages(self.u1, pauses_sollicitations=[{'type': 'plan_matin', 'ignorees': 14},
                                                                      {'type': 'relance', 'ignorees': 14}])
        self.assertEqual(self.patch({'pauses_sollicitations': [{'type': 'relance', 'ignorees': 14}]}).status_code,
                         200)
        reglages.refresh_from_db()
        self.assertEqual(reglages.pauses_sollicitations, [{'type': 'relance', 'ignorees': 14}])
        # une pause ne s'AJOUTE jamais par cette route
        self.assertEqual(self.patch({'pauses_sollicitations': [{'type': 'bilan_soir'}]}).status_code, 400)

    def test_couper_comprendre_mon_rythme_efface_le_profil(self):
        reglages = fabriques.reglages(self.u1, mode=ModeRythme.TENIR, tenir_reference=5, tenir_fixee_le=J,
                                      meilleur_tenu=6, echec_n=1, echec_niveau=7, echec_le=J)
        plan = fabriques.plan(self.u1, J - datetime.timedelta(days=1), statut_jour=StatutJour.EVALUE,
                              compte_rythme=6, plan_prevues=4)
        carte(self.u1, TypeIncitationEcran.CONSTAT, 'C7', donnees={'n': 2})
        carte(self.u1, TypeIncitationEcran.DERIVE_TENIR, 'sous')
        gardee = carte(self.u1, TypeIncitationEcran.PAUSE, 'plan_matin')
        self.assertEqual(self.patch({'comprendre_mon_rythme': False}).status_code, 200)
        reglages.refresh_from_db()
        plan.refresh_from_db()
        self.assertFalse(reglages.comprendre_mon_rythme)
        self.assertEqual((reglages.tenir_reference, reglages.meilleur_tenu, reglages.echec_n, reglages.echec_le),
                         (None, None, 0, None))
        self.assertEqual(reglages.mode, ModeRythme.TENIR)
        self.assertEqual((plan.statut_jour, plan.compte_rythme, plan.plan_prevues), ('', 0, 4))
        self.assertEqual(list(IncitationCoach.objects.values_list('pk', flat=True)), [gardee.pk])

    def test_compte_neuf_le_premier_patch_cree_les_reglages(self):
        reponse = self.patch({'titres_tuile': False})
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.json()['titres_tuile'])
        reglages = ReglagesRythme.objects.get(company=self.a, proprietaire=self.u1)
        self.assertFalse(reglages.titres_tuile)
        self.assertFalse(PlanJour.objects.exists())

    def test_compte_neuf_corps_refuse_ne_cree_rien(self):
        self.assertEqual(self.patch({'projet_arret_jours': 99}).status_code, 400)
        self.assertEqual(self.patch({'suggestions_societe': True}).status_code, 403)
        self.assertFalse(ReglagesRythme.objects.exists())


class ReglagesSocieteTests(TestCase):
    """TCH155 — coupe-circuit `reglages-societe/` (donnees.md §2.21, invariant 39) : administrateur seul,
    absent = actif, lire ne crée rien ; l'instant est injecté (`views.reglages.maintenant`)."""

    @classmethod
    def setUpTestData(cls):
        cls.a = fabriques.societe('a')
        cls.b = fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.admin = fabriques.compte(cls.a, admin=True, nom='admin')
        cls.admin_b = fabriques.compte(cls.b, admin=True, nom='adminb')

    def setUp(self):
        horloge = mock.patch('apps.taches.views.reglages.maintenant', return_value=INSTANT)
        horloge.start()
        self.addCleanup(horloge.stop)

    def client_de(self, compte):
        api = APIClient()
        api.force_authenticate(compte)
        return api

    def test_non_administrateur_403_et_rien_n_est_ecrit(self):
        api = self.client_de(self.u1)
        self.assertEqual(api.get(URL_SOCIETE).status_code, 403)
        self.assertEqual(api.patch(URL_SOCIETE, {'balayage_actif': False}, format='json').status_code, 403)
        self.assertFalse(ReglagesSociete.objects.exists())

    def test_absent_actif_forme_exacte_et_lire_ne_cree_rien(self):
        corps = self.client_de(self.admin).get(URL_SOCIETE).json()
        self.assertEqual(corps, exemple_de('reglages_societe'))
        self.assertFalse(ReglagesSociete.objects.exists())

    def test_couper_puis_rallumer_trace_l_administrateur(self):
        api = self.client_de(self.admin)
        reponse = api.patch(URL_SOCIETE, {'balayage_actif': False}, format='json')
        self.assertEqual(reponse.status_code, 200)
        stocke = ReglagesSociete.objects.get(company=self.a)
        self.assertEqual((stocke.balayage_actif, stocke.modifie_par_id, stocke.modifie_le),
                         (False, self.admin.pk, INSTANT))
        self.assertEqual(reponse.json(), api.get(URL_SOCIETE).json())
        self.assertEqual(set(reponse.json()), set(exemple_de('reglages_societe')))
        self.assertFalse(reponse.json()['balayage_actif'])
        self.assertEqual(reponse.json()['modifie_par'], self.admin.pk)
        self.assertEqual(datetime.datetime.fromisoformat(reponse.json()['modifie_le']), INSTANT)
        self.assertTrue(api.patch(URL_SOCIETE, {'balayage_actif': True}, format='json').json()['balayage_actif'])
        stocke.refresh_from_db()
        self.assertTrue(stocke.balayage_actif)

    def test_enregistrer_rouvrir_enregistrer_sans_toucher(self):
        api = self.client_de(self.admin)
        api.patch(URL_SOCIETE, {'balayage_actif': False}, format='json')
        premier = api.get(URL_SOCIETE).json()
        with mock.patch('apps.taches.views.reglages.maintenant',
                        return_value=INSTANT + datetime.timedelta(hours=1)):
            self.assertEqual(api.patch(URL_SOCIETE, {'balayage_actif': premier['balayage_actif']},
                                       format='json').json(), premier)
        self.assertEqual(api.get(URL_SOCIETE).json(), premier)
        # rallumer une société jamais coupée n'écrit rien (absent = actif)
        self.assertEqual(self.client_de(self.admin_b).patch(URL_SOCIETE, {'balayage_actif': True},
                                                            format='json').status_code, 200)
        self.assertFalse(ReglagesSociete.objects.filter(company=self.b).exists())

    def test_corps_invalide_400_rien_n_est_ecrit(self):
        api = self.client_de(self.admin)
        for corps in ({}, {'balayage_actif': 'non'}, {'balayage_actif': 0}, {'balayage_actif': False, 'autre': 1}):
            with self.subTest(corps=corps):
                self.assertEqual(api.patch(URL_SOCIETE, corps, format='json').status_code, 400)
        self.assertFalse(ReglagesSociete.objects.exists())

    def test_chaque_societe_son_coupe_circuit(self):
        self.client_de(self.admin_b).patch(URL_SOCIETE, {'balayage_actif': False}, format='json')
        self.assertTrue(self.client_de(self.admin).get(URL_SOCIETE).json()['balayage_actif'])
        self.assertFalse(self.client_de(self.admin_b).get(URL_SOCIETE).json()['balayage_actif'])
