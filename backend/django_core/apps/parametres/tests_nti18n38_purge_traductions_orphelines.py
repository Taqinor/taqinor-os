"""NTI18N38 — purge mensuelle des traductions de contenu orphelines.

Run :
    python manage.py test \
        apps.parametres.tests_nti18n38_purge_traductions_orphelines -v 2
"""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from apps.audit.models import AuditLog
from apps.parametres.models_translations import TranslationOverride
from apps.parametres.scheduled import purger_traductions_orphelines
from apps.stock.models import Produit
from authentication.models import Company
from core.i18n_content import set_translation
from core.models import ContentTranslation


def _company(slug, nom):
    return Company.objects.create(nom=nom, slug=slug)


def _produit(company, nom):
    return Produit.objects.create(
        company=company, nom=nom, prix_achat=Decimal('0'),
        prix_vente=Decimal('100.00'), quantite_stock=0, seuil_alerte=0)


class TacheAuBeatTests(SimpleTestCase):
    """Une tâche absente du beat (ou du routage) ne tourne jamais en prod —
    c'est l'incident du 14/09/2026."""

    def test_la_tache_est_planifiee_et_routee(self):
        from django.conf import settings

        from erp_agentique.celery import app

        nom = 'parametres.purger_traductions_orphelines'
        planifiees = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn(nom, planifiees)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES[nom]['queue'], 'scheduled')

    def test_la_tache_est_enregistree_apres_autodecouverte(self):
        from erp_agentique.celery import app

        app.loader.import_default_modules()
        self.assertIn('parametres.purger_traductions_orphelines', app.tasks)


class PurgeOrphelinesTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n38-co', 'NTI18N38 Co')
        self.produit_vivant = _produit(self.company, 'Panneau vivant')
        self.produit_supprime = _produit(self.company, 'Panneau retiré')
        set_translation(self.produit_vivant, 'nom', 'ar', 'لوح شمسي')
        set_translation(self.produit_supprime, 'nom', 'ar', 'لوح محذوف')
        self.ct_produit = ContentType.objects.get_for_model(Produit)
        self.id_supprime = str(self.produit_supprime.pk)

    def _orphelines_restantes(self):
        return ContentTranslation.objects.filter(
            company=self.company, content_type=self.ct_produit,
            object_id=self.id_supprime).count()

    def test_traduction_orpheline_purgee_au_run_suivant(self):
        self.produit_supprime.delete()
        self.assertEqual(self._orphelines_restantes(), 1)

        resultat = purger_traductions_orphelines()

        self.assertEqual(resultat['supprimees'], 1)
        self.assertEqual(self._orphelines_restantes(), 0)

    def test_traduction_dun_objet_vivant_conservee(self):
        self.produit_supprime.delete()
        purger_traductions_orphelines()
        self.assertTrue(
            ContentTranslation.objects.filter(
                company=self.company, content_type=self.ct_produit,
                object_id=str(self.produit_vivant.pk)).exists())

    def test_purge_tracable_dans_le_journal_daudit(self):
        self.produit_supprime.delete()
        purger_traductions_orphelines()

        entree = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.DELETE,
            object_repr='Traductions de contenu orphelines').first()
        self.assertIsNotNone(entree)
        self.assertIn('NTI18N38', entree.detail)
        self.assertIsNone(entree.user_id)

    def test_aucune_ligne_daudit_quand_rien_a_purger(self):
        avant = AuditLog.objects.count()
        resultat = purger_traductions_orphelines()
        self.assertEqual(resultat['supprimees'], 0)
        self.assertEqual(AuditLog.objects.count(), avant)

    def test_id_non_convertible_traite_comme_orphelin(self):
        """``object_id`` est une ``CharField`` : une valeur qui ne se convertit
        pas au type de la clé primaire cible ne peut désigner aucune ligne — et
        ne doit jamais faire échouer la requête d'existence."""
        ContentTranslation.objects.create(
            company=self.company, content_type=self.ct_produit,
            object_id='pas-un-entier', locale='ar', field='nom',
            value='قيمة')

        purger_traductions_orphelines()

        self.assertFalse(
            ContentTranslation.objects.filter(
                company=self.company, object_id='pas-un-entier').exists())

    def test_les_surcharges_dinterface_ne_sont_jamais_touchees(self):
        """``TranslationOverride`` ne porte AUCUN pointeur d'objet (colonnes
        ``company/locale/key/value``) : aucune « source supprimée » ne peut
        être détectée pour ces lignes, et les purger effacerait du texte saisi
        par le tenant."""
        TranslationOverride.objects.create(
            company=self.company, locale='ar', key='nav.stock', value='مخزون')
        self.produit_supprime.delete()

        purger_traductions_orphelines()

        self.assertTrue(
            TranslationOverride.objects.filter(
                company=self.company, key='nav.stock').exists())


class IsolationParSocieteTests(TestCase):
    def test_une_societe_inactive_nest_pas_balayee(self):
        company = _company('nti18n38-off', 'NTI18N38 Inactive')
        produit = _produit(company, 'Panneau société inactive')
        set_translation(produit, 'nom', 'ar', 'قيمة')
        produit_id = str(produit.pk)
        produit.delete()
        company.actif = False
        company.save(update_fields=['actif'])

        resultat = purger_traductions_orphelines()

        self.assertEqual(resultat['supprimees'], 0)
        self.assertTrue(
            ContentTranslation.objects.filter(
                company=company, object_id=produit_id).exists())
