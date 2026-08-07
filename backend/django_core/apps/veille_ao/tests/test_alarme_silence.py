"""VAO24 — le journal d'exécution et l'ALARME de collecte silencieuse.

La tâche la plus importante du groupe, et pour une raison très concrète : le
portail change, la collecte renvoie vide, l'écran reste calme — et on se croit
couvert pendant des semaines. Ces tests prouvent que ce scénario CRIE.

Le « Done = » de la tâche :
  * un journal écrit à CHAQUE exécution, même échouée ;
  * l'alarme déclenchée sur les DEUX conditions (2 jours muets ; 2 échecs) ;
  * l'écran affiche la dernière collecte réussie ET son ÂGE ;
  * une alarme active est visible sans aller la chercher (endpoint agrégé).
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.notifications.models import EventType, Notification
from apps.roles.models import Role

from apps.veille_ao.models import (
    DeclencheurCollecte, ExecutionCollecte, MotCleVeille, NiveauMotCle,
    SourceVeille, TypeSource, VerdictExecution,
)
from apps.veille_ao.services import (
    collecter, evaluer_alarme, sante, signaler_alarme_si_besoin,
)


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Veille')
        self.source = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)
        MotCleVeille.objects.create(
            company=self.company, libelle='solaire',
            niveau=NiveauMotCle.NOYAU, poids=10, actif=True)

    def _execution(self, *, jours=0, verdict=VerdictExecution.SUCCES,
                   examines=0, nouveaux=0):
        moment = timezone.now() - timedelta(days=jours)
        execution = ExecutionCollecte.objects.create(
            company=self.company, source=self.source, verdict=verdict,
            examines=examines, nouveaux=nouveaux, fin=moment)
        # ``debut`` porte un défaut : on le repositionne explicitement.
        ExecutionCollecte.objects.filter(pk=execution.pk).update(debut=moment)
        execution.refresh_from_db()
        return execution


class JournalTests(_Base):
    def test_une_collecte_reussie_ecrit_sa_ligne_de_journal(self):
        collecter(self.source, self.company,
                  lecteur=lambda s, m: [{'ref_consultation': '1',
                                         'objet': 'Pompage solaire'}])

        journal = ExecutionCollecte.objects.get(company=self.company)
        self.assertEqual(journal.verdict, VerdictExecution.SUCCES)
        self.assertEqual(journal.examines, 1)
        self.assertEqual(journal.nouveaux, 1)
        self.assertEqual(journal.mots_cles_interroges, ['solaire'])
        self.assertIsNotNone(journal.fin)

    def test_une_collecte_ECHOUEE_ecrit_AUSSI_sa_ligne(self):
        """Le cas qui compte : un échec non journalisé est un échec invisible."""
        def lecteur(source, mots_cles):
            raise RuntimeError('portail injoignable')

        collecter(self.source, self.company, lecteur=lecteur)

        journal = ExecutionCollecte.objects.get(company=self.company)
        self.assertEqual(journal.verdict, VerdictExecution.ECHEC)
        self.assertIn('portail injoignable', journal.message)

    def test_le_declencheur_est_conserve(self):
        collecter(self.source, self.company, lecteur=lambda s, m: [],
                  declencheur=DeclencheurCollecte.MANUEL)
        self.assertEqual(ExecutionCollecte.objects.get().declencheur,
                         DeclencheurCollecte.MANUEL)

    def test_le_journal_survit_a_la_suppression_de_sa_source(self):
        collecter(self.source, self.company, lecteur=lambda s, m: [])
        self.source.delete()
        journal = ExecutionCollecte.objects.get(company=self.company)
        self.assertIsNone(journal.source_id)


class AlarmeTests(_Base):
    def test_aucune_alarme_quand_la_veille_ramene_des_avis(self):
        self._execution(jours=0, examines=12, nouveaux=3)
        self._execution(jours=1, examines=9, nouveaux=1)
        active, message = evaluer_alarme(self.company)
        self.assertFalse(active)
        self.assertEqual(message, '')

    def test_alarme_sur_DEUX_JOURS_muets_consecutifs(self):
        self._execution(jours=0, examines=0)
        self._execution(jours=1, examines=0)
        active, message = evaluer_alarme(self.company)
        self.assertTrue(active)
        self.assertIn('2 jours', message)

    def test_un_seul_jour_muet_ne_declenche_PAS_l_alarme(self):
        """Une alarme trop nerveuse finit désactivée — donc inutile."""
        self._execution(jours=0, examines=0)
        self._execution(jours=1, examines=7)
        active, _ = evaluer_alarme(self.company)
        self.assertFalse(active)

    def test_deux_executions_vides_LE_MEME_JOUR_ne_font_pas_deux_jours(self):
        self._execution(jours=0, examines=0)
        self._execution(jours=0, examines=0)
        active, _ = evaluer_alarme(self.company)
        self.assertFalse(active)

    def test_alarme_sur_DEUX_ECHECS_consecutifs(self):
        self._execution(jours=0, verdict=VerdictExecution.ECHEC)
        self._execution(jours=1, verdict=VerdictExecution.ECHEC)
        active, message = evaluer_alarme(self.company)
        self.assertTrue(active)
        self.assertIn('échoué', message)

    def test_un_echec_isole_ne_declenche_pas_l_alarme(self):
        self._execution(jours=0, verdict=VerdictExecution.ECHEC)
        self._execution(jours=1, examines=5, nouveaux=1)
        active, _ = evaluer_alarme(self.company)
        self.assertFalse(active)

    def test_l_alarme_est_scopee_SOCIETE(self):
        autre = Company.objects.create(nom='Autre société')
        for _ in range(2):
            ExecutionCollecte.objects.create(
                company=autre, verdict=VerdictExecution.ECHEC)
        active, _ = evaluer_alarme(self.company)
        self.assertFalse(active)


class NotificationAlarmeTests(_Base):
    def setUp(self):
        super().setUp()
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=['veille_ao_voir', 'veille_ao_gerer'])
        self.directeur = CustomUser.objects.create_user(
            username='dir_veille', password='x', company=self.company,
            role=role)

    def test_l_alarme_notifie_le_directeur_une_seule_fois(self):
        self._execution(jours=1, verdict=VerdictExecution.ECHEC)
        self._execution(jours=0, verdict=VerdictExecution.ECHEC)

        self.assertIsNotNone(signaler_alarme_si_besoin(self.company))
        # Deuxième passage : l'alarme est toujours active mais déjà signalée.
        self.assertIsNone(signaler_alarme_si_besoin(self.company))

        notifications = Notification.objects.filter(
            user=self.directeur,
            event_type=EventType.VEILLE_AO_ALARME_SILENCE)
        self.assertEqual(notifications.count(), 1)
        self.assertIn('ne ramène plus rien', notifications.first().body)

    def test_pas_d_alarme_pas_de_notification(self):
        self._execution(jours=0, examines=5, nouveaux=1)
        self.assertIsNone(signaler_alarme_si_besoin(self.company))
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.VEILLE_AO_ALARME_SILENCE).exists())


class SanteTests(_Base):
    def test_sante_donne_la_derniere_reussite_et_son_AGE(self):
        self._execution(jours=0, examines=4, nouveaux=1)
        etat = sante(self.company)
        self.assertIsNotNone(etat['derniere_collecte_reussie'])
        self.assertIsNotNone(etat['age_heures'])
        self.assertLess(etat['age_heures'], 1)

    def test_une_collecte_ECHOUEE_ne_compte_pas_comme_reussite(self):
        self._execution(jours=0, verdict=VerdictExecution.ECHEC)
        self.assertIsNone(sante(self.company)['derniere_collecte_reussie'])

    def test_avis_examines_HIER_compte_le_jour_calendaire(self):
        self._execution(jours=1, examines=17)
        self._execution(jours=0, examines=3)
        self.assertEqual(sante(self.company)['avis_examines_hier'], 17)

    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=False)
    def test_sante_dit_que_la_collecte_est_DESARMEE(self):
        self.assertFalse(sante(self.company)['collecte_active'])

    def test_l_alarme_est_dans_la_reponse_agregee(self):
        self._execution(jours=0, verdict=VerdictExecution.ECHEC)
        self._execution(jours=1, verdict=VerdictExecution.ECHEC)
        etat = sante(self.company)
        self.assertTrue(etat['alarme_active'])
        self.assertTrue(etat['alarme_message'])


class SanteEndpointTests(_Base):
    def _api(self, permissions):
        role = Role.objects.create(
            company=self.company, nom='Rôle santé',
            permissions=list(permissions))
        user = CustomUser.objects.create_user(
            username='vao_sante', password='x', company=self.company,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_un_lecteur_voit_l_etat_de_la_veille(self):
        api = self._api(['veille_ao_voir'])
        reponse = api.get('/api/django/veille_ao/sante/')
        self.assertEqual(reponse.status_code, 200)
        for cle in ('derniere_collecte_reussie', 'age_heures',
                    'avis_examines_hier', 'alarme_active', 'alarme_message',
                    'collecte_active'):
            self.assertIn(cle, reponse.data, cle)

    def test_un_role_etranger_est_refuse(self):
        api = self._api(['crm_voir'])
        self.assertEqual(
            api.get('/api/django/veille_ao/sante/').status_code, 403)

    def test_le_journal_est_lisible_et_NON_modifiable_par_l_API(self):
        self._execution(jours=0, examines=2)
        api = self._api(['veille_ao_voir', 'veille_ao_gerer'])

        liste = api.get('/api/django/veille_ao/executions/')
        self.assertEqual(liste.status_code, 200)

        creation = api.post('/api/django/veille_ao/executions/', {}, 'json')
        self.assertEqual(creation.status_code, 405)

    def test_le_journal_d_une_AUTRE_societe_est_invisible(self):
        autre = Company.objects.create(nom='Autre société')
        ExecutionCollecte.objects.create(company=autre, examines=99)
        api = self._api(['veille_ao_voir'])

        reponse = api.get('/api/django/veille_ao/executions/')

        corps = reponse.data
        lignes = corps['results'] if isinstance(corps, dict) else corps
        self.assertEqual([ligne['examines'] for ligne in lignes], [])
