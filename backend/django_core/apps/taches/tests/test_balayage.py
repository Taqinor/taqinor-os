"""TCH98 — le balayage de chaque minute `balayage.executer(maintenant)` (reference/api.md §9 ; regles.md
« Les sollicitations », « Activation par étapes et coupe-circuit »).

Base requise (`TestCase`). Horloge injectée (`maintenant`), jamais vivante ; J = mardi 17/11/2026, jour
ouvré, fenêtre des messages de la société 08:30-20:00 (défauts de `crm.horaires`). Chaque test relit
l'état STOCKÉ (`Notification`, `Rappel`, `IncitationCoach`) — jamais un espion à la place du résultat.
"""
import datetime
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.taches import balayage, sweeps
from apps.taches.choix import CanalIncitation, StatutRappel
from apps.taches.models.presence import ReglagesSociete
from apps.taches.models.rythme import IncitationCoach, Preference
from apps.taches.models.taches import Rappel
from apps.taches.moteur import sollicitations as regles
from apps.taches.tests import fabriques

J = datetime.date(2026, 11, 17)
CANARI = 'Canari-X3K'
TYPES_TACHES = (EventType.TACHES_PLAN_DU_JOUR, EventType.TACHES_BILAN_SOIR, EventType.TACHES_RELANCE,
                EventType.TACHES_RAPPEL)


def a(heure, minute=0, jour=J):
    """Instant local (fuseau de la société) du jour `jour`."""
    return timezone.make_aware(datetime.datetime.combine(jour, datetime.time(heure, minute)))


class BalayageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.u1 = fabriques.compte(cls.societe, nom='u1')
        cls.reglages = fabriques.reglages(cls.u1)

    # --- aides ------------------------------------------------------------------------------------

    def notifications(self, *types):
        return Notification.objects.filter(recipient=self.u1, event_type__in=types or TYPES_TACHES)

    def rappel(self, heure, minute=0, *, jour=J, tache=None):
        tache = tache or fabriques.tache(self.u1, jour_prevu=jour)
        return Rappel.objects.create(company=self.societe, proprietaire=self.u1, tache=tache, jour=jour,
                                     heure=datetime.time(heure, minute))

    def dire(self, cle, valeur):
        Preference.objects.create(company=self.societe, proprietaire=self.u1, cle=cle, valeur=valeur)

    def marqueur(self, type_, jour=J):
        return IncitationCoach.objects.create(company=self.societe, proprietaire=self.u1, type=type_, jour=jour,
                                              cle='', canal=CanalIncitation.PUSH, montre_le=a(8, 30, jour))

    def couper(self, actif=False):
        ReglagesSociete.objects.update_or_create(company=self.societe, defaults={'balayage_actif': actif})

    # --- rappels posés -----------------------------------------------------------------------------

    def test_rappel_du_envoye_une_fois_rejouer_n_envoie_rien_de_plus(self):
        rappel = self.rappel(15, 0)
        self.assertEqual(balayage.executer(a(14, 59))['rappels'], 0)
        self.assertFalse(self.notifications().exists())
        balayage.executer(a(15, 0))
        balayage.executer(a(15, 0))
        balayage.executer(a(15, 1))
        rappel.refresh_from_db()
        self.assertEqual((rappel.statut, rappel.envoye_le), (StatutRappel.ENVOYE, a(15, 0)))
        notification = self.notifications(EventType.TACHES_RAPPEL).get()
        self.assertEqual(notification.title, 'Rappel')
        self.assertEqual(notification.link, f'/taches/aujourdhui?tache={rappel.tache_id}')

    def test_rappels_de_la_meme_minute_groupes(self):
        premier, second = self.rappel(15, 0), self.rappel(15, 0)
        self.assertEqual(balayage.executer(a(15, 0))['rappels'], 1)
        notification = self.notifications(EventType.TACHES_RAPPEL).get()
        self.assertEqual(notification.body, "C'est l'heure : 2 tâches à 15 h.")  # variante(17/11) = 2
        self.assertEqual(notification.link, '/taches/aujourdhui')
        self.assertEqual(set(Rappel.objects.filter(pk__in=[premier.pk, second.pk]).values_list('statut', flat=True)),
                         {StatutRappel.ENVOYE})

    def test_rappel_manque_au_dela_de_deux_heures_jamais_envoye(self):
        en_retard, juste = self.rappel(12, 59), self.rappel(13, 0)
        resultat = balayage.executer(a(15, 0))
        en_retard.refresh_from_db()
        juste.refresh_from_db()
        self.assertEqual((resultat['manques'], en_retard.statut), (1, StatutRappel.MANQUE))
        self.assertEqual(juste.statut, StatutRappel.ENVOYE)  # retard de 2 h pile : pas « plus de 2 h »
        self.assertEqual(self.notifications(EventType.TACHES_RAPPEL).count(), 1)

    def test_corps_sans_titre_par_defaut(self):
        tache = fabriques.tache(self.u1, titre=CANARI, jour_prevu=J)
        self.rappel(15, 0, tache=tache)
        balayage.executer(a(15, 0))
        notification = self.notifications(EventType.TACHES_RAPPEL).get()
        self.assertNotIn('Canari', notification.title + notification.body)
        self.assertEqual(notification.body, "C'est l'heure : 1 tâche à 15 h.")

    def test_titre_seulement_si_demande_et_jamais_pour_une_confidentielle(self):
        self.reglages.titres_notifications = True
        self.reglages.save(update_fields=['titres_notifications'])
        ordinaire = fabriques.tache(self.u1, titre=CANARI, jour_prevu=J)
        confidentielle = fabriques.tache(self.u1, titre='Canari-Secret', jour_prevu=J, confidentiel=True)
        self.rappel(15, 0, tache=ordinaire)
        self.rappel(15, 5, tache=confidentielle)
        balayage.executer(a(15, 0))
        balayage.executer(a(15, 5))
        corps = list(self.notifications(EventType.TACHES_RAPPEL).order_by('pk').values_list('body', flat=True))
        self.assertEqual(corps[0], f'« {CANARI} » · 15 h')  # le canari est vivant
        self.assertNotIn('Canari', corps[1])

    def test_compte_inactif_rien(self):
        self.rappel(15, 0)
        self.u1.is_active = False
        self.u1.save(update_fields=['is_active'])
        balayage.executer(a(8, 30))
        balayage.executer(a(15, 0))
        self.assertFalse(Notification.objects.filter(recipient=self.u1).exists())

    # --- coupe-circuit (invariant 39) -------------------------------------------------------------

    def test_coupe_circuit_rien_puis_aucune_rafale_a_la_remise_en_marche(self):
        fabriques.tache(self.u1, jour_prevu=J)
        tot, tard = self.rappel(15, 0), self.rappel(16, 30)
        self.couper()
        balayage.executer(a(8, 30))
        balayage.executer(a(16, 30))
        self.assertEqual(set(Rappel.objects.filter(pk__in=[tot.pk, tard.pk]).values_list('statut', flat=True)),
                         {StatutRappel.EN_ATTENTE})  # coupé : rien, pas même `manque`
        self.assertFalse(self.notifications().exists())
        self.assertFalse(IncitationCoach.objects.filter(canal=CanalIncitation.PUSH).exists())
        self.couper(actif=True)  # relu au passage suivant, sans redéploiement
        balayage.executer(a(17, 30))
        tot.refresh_from_db()
        tard.refresh_from_db()
        self.assertEqual((tot.statut, tard.statut), (StatutRappel.MANQUE, StatutRappel.ENVOYE))
        self.assertEqual(self.notifications().count(), 1)

    # --- sollicitations (invariant 22) ------------------------------------------------------------

    def test_plan_du_matin_marqueur_et_notification_une_seule_fois(self):
        fabriques.tache(self.u1, jour_prevu=J)
        self.assertEqual(balayage.executer(a(8, 30))['sollicitations'], 1)
        for minute in (31, 44):
            balayage.executer(a(8, minute))
        notification = self.notifications(EventType.TACHES_PLAN_DU_JOUR).get()
        self.assertEqual((notification.title, notification.link, notification.programmee_pour),
                         ("Aujourd'hui", '/taches/aujourdhui', None))
        marqueur = IncitationCoach.objects.get(proprietaire=self.u1, canal=CanalIncitation.PUSH)
        self.assertEqual((marqueur.type, marqueur.jour, marqueur.montre_le), (regles.PLAN_MATIN, J, a(8, 30)))
        self.assertTrue(all(isinstance(v, (int, float)) for v in marqueur.donnees.values()))

    def test_rien_a_proposer_rien_envoye(self):
        balayage.executer(a(8, 30))
        self.assertFalse(self.notifications().exists())

    def test_hors_fenetre_saute_jamais_differe(self):
        fabriques.tache(self.u1, jour_prevu=J)
        self.dire('heure_matin', '07:00')  # avant l'ouverture des messages (08:30)
        balayage.executer(a(7, 0))
        balayage.executer(a(8, 30))
        balayage.executer(a(9, 0))
        self.assertFalse(self.notifications().exists())

    def test_jour_non_travaille_et_conge(self):
        fabriques.tache(self.u1, jour_prevu=J)
        dimanche = datetime.date(2026, 11, 22)
        balayage.executer(a(8, 30, dimanche))
        self.dire('conges', [{'du': J.isoformat(), 'au': J.isoformat()}])
        balayage.executer(a(8, 30))
        self.assertFalse(self.notifications().exists())

    def test_apres_l_heure_limite_saute(self):
        fabriques.tache(self.u1, jour_prevu=J)
        fabriques.plan(self.u1, J, planifie_le=a(8, 0))
        self.dire('heure_limite', '17:00')
        balayage.executer(a(18, 0))
        self.assertFalse(self.notifications().exists())

    def test_bilan_du_soir_envoye_dans_la_fenetre(self):
        fabriques.tache(self.u1, jour_prevu=J)
        fabriques.plan(self.u1, J, planifie_le=a(8, 0))
        self.assertEqual(balayage.executer(a(18, 0))['sollicitations'], 1)
        notification = self.notifications(EventType.TACHES_BILAN_SOIR).get()
        self.assertEqual((notification.title, notification.link), ('Bilan du soir', '/taches/aujourdhui?ouvrir=bilan'))

    def test_plafond_trois_par_jour(self):
        self.dire('revue_semaine', J.weekday())
        for type_ in (regles.PLAN_MATIN, regles.RELANCE):
            self.marqueur(type_)
        self.assertEqual(balayage.executer(a(18, 0))['sollicitations'], 1)  # la revue, 3e envoi
        self.assertEqual(self.notifications(EventType.TACHES_BILAN_SOIR).get().link, '/taches/revue')
        IncitationCoach.objects.filter(type=regles.REVUE_SEMAINE).delete()
        Notification.objects.all().delete()
        self.marqueur(regles.BILAN_SOIR)  # trois envois déjà partis
        balayage.executer(a(18, 1))
        self.assertFalse(self.notifications().exists())

    def test_deux_types_au_meme_tick_l_autre_est_saute(self):
        fabriques.tache(self.u1, jour_prevu=J, echeance=J)
        self.dire('relance_jour', '08:30')
        balayage.executer(a(8, 30))
        balayage.executer(a(8, 31))
        self.assertEqual(self.notifications().count(), 1)
        self.assertTrue(self.notifications(EventType.TACHES_PLAN_DU_JOUR).exists())


class TachePlanifieeBalayageTests(SimpleTestCase):
    """TCH174 — `taches.balayer` (sweeps.py) chaque minute ; le rappel posé part sans délai."""

    def test_planifiee_chaque_minute_et_expire_apres_sa_periode(self):
        from erp_agentique.celery import app
        entree = app.conf.beat_schedule['taches-balayer']
        self.assertEqual(entree['task'], 'taches.balayer')
        self.assertEqual((entree['schedule'].hour, entree['schedule'].minute), (set(range(24)), set(range(60))))
        self.assertEqual(entree['options'], {'expires': 60})
        self.assertEqual(list(app.conf.beat_schedule)[-1], 'taches-balayer')

    def test_la_tache_appelle_un_passage(self):
        with mock.patch.object(balayage, 'executer', return_value={'societes': 1}) as executer:
            self.assertEqual(sweeps.balayer(), {'societes': 1})
        executer.assert_called_once_with()
        self.assertEqual(sweeps.balayer.name, 'taches.balayer')

    def test_rappel_toujours_immediat_par_defaut(self):
        self.assertIn(EventType.TACHES_RAPPEL, settings.NOTIFICATIONS_TOUJOURS_IMMEDIATES)
