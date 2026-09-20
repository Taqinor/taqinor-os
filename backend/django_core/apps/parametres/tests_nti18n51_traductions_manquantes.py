"""NTI18N51 — détection + notification hebdomadaire des traductions manquantes.

Le cœur du critère d'acceptation est l'ANTI-SPAM : une clé réclamée 50 fois
produit UNE ligne en tête d'UNE notification, jamais 50 notifications.

Run :
    python manage.py test \
        apps.parametres.tests_nti18n51_traductions_manquantes -v 2
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.notifications.models import EventType, Notification
from apps.parametres.i18n_labels import variante_absente
from apps.parametres.models_translations import TraductionManquante
from apps.parametres.scheduled import (
    notifier_traductions_manquantes_hebdo,
)
from apps.parametres.selectors import statut_libelle
from apps.parametres.traductions_manquantes import (
    cle_statut,
    cles_a_notifier,
    enregistrer_repli,
    marquer_notifiees,
)
from authentication.models import Company

User = get_user_model()


def _company(slug, nom):
    return Company.objects.create(nom=nom, slug=slug)


class VarianteAbsenteTests(SimpleTestCase):
    """Prédicat pur — aucune base, aucun compteur."""

    def test_statut_catalogue_complet_nest_pas_un_manque(self):
        self.assertFalse(variante_absente('devis', 'brouillon', 'ar'))
        self.assertFalse(variante_absente('devis', 'brouillon', 'en'))

    def test_couple_inconnu_est_un_manque(self):
        self.assertTrue(variante_absente('devis', 'statut-inexistant', 'ar'))

    def test_le_francais_nest_jamais_un_manque(self):
        self.assertFalse(variante_absente('devis', 'statut-inexistant', 'fr'))

    def test_langue_non_supportee_nest_pas_un_manque(self):
        """Une langue hors cadre est traitée comme du français : c'est le
        comportement voulu, pas une lacune de traduction."""
        self.assertFalse(variante_absente('devis', 'statut-inexistant', 'de'))


class CompteurTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n51-co', 'NTI18N51 Co')
        self.cle = cle_statut('devis', 'statut-inexistant')

    def test_premier_repli_cree_la_ligne(self):
        self.assertTrue(enregistrer_repli(self.company, 'ar', self.cle))
        ligne = TraductionManquante.objects.get(
            company=self.company, langue='ar', cle=self.cle)
        self.assertEqual(ligne.occurrences, 1)
        self.assertEqual(ligne.occurrences_notifiees, 0)

    def test_replis_suivants_incrementent_la_meme_ligne(self):
        for _ in range(50):
            enregistrer_repli(self.company, 'ar', self.cle)
        lignes = TraductionManquante.objects.filter(company=self.company)
        self.assertEqual(lignes.count(), 1)
        self.assertEqual(lignes.first().occurrences, 50)

    def test_langue_source_et_societe_absente_ne_comptent_rien(self):
        self.assertFalse(enregistrer_repli(self.company, 'fr', self.cle))
        self.assertFalse(enregistrer_repli(None, 'ar', self.cle))
        self.assertFalse(enregistrer_repli(self.company, 'ar', ''))
        self.assertEqual(TraductionManquante.objects.count(), 0)

    def test_classement_sur_le_delta_de_la_periode(self):
        """Une clé déjà signalée ne doit pas devancer une clé neuve plus
        réclamée sur la période."""
        ancienne = TraductionManquante.objects.create(
            company=self.company, langue='ar', cle='statuts.a',
            occurrences=500, occurrences_notifiees=498)
        neuve = TraductionManquante.objects.create(
            company=self.company, langue='ar', cle='statuts.b',
            occurrences=50, occurrences_notifiees=0)

        classement = cles_a_notifier(self.company)

        self.assertEqual([x.pk for x in classement], [neuve.pk, ancienne.pk])
        self.assertEqual(classement[0].nouvelles_occurrences, 50)

    def test_cle_deja_notifiee_et_sans_nouveau_repli_est_ecartee(self):
        TraductionManquante.objects.create(
            company=self.company, langue='ar', cle='statuts.c',
            occurrences=12, occurrences_notifiees=12)
        self.assertEqual(cles_a_notifier(self.company), [])

    def test_marquer_notifiees_aligne_le_compteur(self):
        ligne = TraductionManquante.objects.create(
            company=self.company, langue='ar', cle='statuts.d', occurrences=7)
        marquer_notifiees([ligne])
        ligne.refresh_from_db()
        self.assertEqual(ligne.occurrences_notifiees, 7)
        self.assertEqual(cles_a_notifier(self.company), [])


class InstrumentationTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n51-inst', 'NTI18N51 Instrumentation')

    def test_statut_traduit_necrit_rien(self):
        libelle = statut_libelle(self.company, 'devis', 'brouillon', 'ar')
        self.assertTrue(libelle)
        self.assertEqual(TraductionManquante.objects.count(), 0)

    def test_repli_sur_le_francais_est_compte(self):
        statut_libelle(self.company, 'devis', 'statut-inexistant', 'ar')
        ligne = TraductionManquante.objects.get(company=self.company)
        self.assertEqual(ligne.langue, 'ar')
        self.assertEqual(ligne.cle, cle_statut('devis', 'statut-inexistant'))
        self.assertEqual(ligne.occurrences, 1)

    def test_le_libelle_sort_quand_meme(self):
        """Le compteur ne doit jamais changer ce que l'écran affiche."""
        self.assertEqual(
            statut_libelle(self.company, 'devis', 'statut-inexistant', 'ar'),
            'statut-inexistant')


class NotificationHebdoTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n51-notif', 'NTI18N51 Notif')
        self.admin = User.objects.create_user(
            username='nti18n51-admin', password='x', role_legacy='admin',
            company=self.company)

    def _notifications(self):
        return Notification.objects.filter(
            recipient=self.admin, event_type=EventType.DIGEST)

    def test_cinquante_occurrences_donnent_une_notification_en_tete(self):
        TraductionManquante.objects.create(
            company=self.company, langue='ar', cle='statuts.devis.tres_chaud',
            occurrences=50)
        TraductionManquante.objects.create(
            company=self.company, langue='ar', cle='statuts.devis.rare',
            occurrences=2)

        resultat = notifier_traductions_manquantes_hebdo()

        self.assertEqual(resultat['societes_notifiees'], 1)
        self.assertEqual(self._notifications().count(), 1)
        corps = self._notifications().first().body
        self.assertLess(corps.index('statuts.devis.tres_chaud'),
                        corps.index('statuts.devis.rare'))
        self.assertIn('50 fois', corps)

    def test_une_seule_notification_puis_plus_rien_sans_nouveau_repli(self):
        TraductionManquante.objects.create(
            company=self.company, langue='ar', cle='statuts.devis.x',
            occurrences=50)

        notifier_traductions_manquantes_hebdo()
        deuxieme = notifier_traductions_manquantes_hebdo()

        self.assertEqual(deuxieme['societes_notifiees'], 0)
        self.assertEqual(self._notifications().count(), 1)

    def test_semaine_sans_manque_ne_notifie_personne(self):
        resultat = notifier_traductions_manquantes_hebdo()
        self.assertEqual(resultat, {'societes_notifiees': 0, 'cles': 0})
        self.assertEqual(self._notifications().count(), 0)

    def test_societe_inactive_nest_pas_balayee(self):
        autre = _company('nti18n51-off', 'NTI18N51 Inactive')
        User.objects.create_user(
            username='nti18n51-off-admin', password='x', role_legacy='admin',
            company=autre)
        TraductionManquante.objects.create(
            company=autre, langue='ar', cle='statuts.devis.y', occurrences=9)
        autre.actif = False
        autre.save(update_fields=['actif'])

        resultat = notifier_traductions_manquantes_hebdo()

        self.assertEqual(resultat['societes_notifiees'], 0)


class TacheAuBeatTests(SimpleTestCase):
    def test_la_tache_est_planifiee_et_routee(self):
        from django.conf import settings

        from erp_agentique.celery import app

        nom = 'parametres.notifier_traductions_manquantes_hebdo'
        planifiees = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn(nom, planifiees)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES[nom]['queue'], 'scheduled')

    def test_la_tache_est_enregistree_apres_autodecouverte(self):
        from erp_agentique.celery import app

        app.loader.import_default_modules()
        self.assertIn('parametres.notifier_traductions_manquantes_hebdo',
                      app.tasks)
