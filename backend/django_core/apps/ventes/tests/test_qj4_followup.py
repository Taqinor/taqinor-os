"""QJ4 — Tests de la relance automatique cadencée des devis envoyés.

Garanties testées :
  1. Cadence : un devis envoyé depuis exactement j+2 déclenche le niveau 0
     (le premier palier), mais pas le niveau 1 (j+5) ni 2 (j+10).
  2. Idempotence : ré-exécuter le job sur un devis dont le niveau 0 a déjà un
     DevisNudgeLog ne crée pas de doublon et renvoie 0 nudges.
  3. Arrêt sur accepté : un devis « accepté » n'est PAS relancé.
  4. Arrêt sur refusé : un devis « refusé » n'est PAS relancé.
  5. Brouillon ignoré : un devis « brouillon » n'est pas traité.
  6. Multi-tenant : deux sociétés distinctes, les nudges restent scoped (les
     logs de la société A ne contaminent pas la société B).
  7. Sans date_envoi : un devis ENVOYE sans date_envoi est ignoré.
  8. Email canal : quand le backend email est configuré (locmem) ET que le
     vendeur a un email, le DevisNudgeLog indique canal=email.
  9. WA draft canal : sans backend email configuré, le canal est wa_draft.
 10. La tâche Celery ``devis_followup_nudges`` appelle le service correctement
     (smoke test via appel direct sans worker Celery).

Run :
    python manage.py test apps.ventes.tests.test_qj4_followup -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisNudgeLog
from apps.ventes.services import send_devis_followup_nudges

User = get_user_model()
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
CONSOLE = 'django.core.mail.backends.console.EmailBackend'


def make_company(slug='qj4-co', nom='QJ4 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username='qj4_vendeur', email='vendeur@taqinor.ma'):
    return User.objects.get_or_create(
        username=username,
        defaults=dict(
            password='x',
            role_legacy='responsable',
            company=company,
            email=email,
            phone_number='+212600000099',
        ),
    )[0]


def make_produit(company):
    return Produit.objects.get_or_create(
        company=company,
        sku='QJ4-P',
        defaults=dict(
            nom='Panneau QJ4',
            prix_vente=Decimal('5000'),
            quantite_stock=10,
            tva=Decimal('20.00'),
        ),
    )[0]


def make_devis(company, user, statut=Devis.Statut.ENVOYE, days_ago=2):
    """Crée un Devis ENVOYE dont date_envoi est il y a ``days_ago`` jours."""
    ref = f'DEV-QJ4-{statut[:3].upper()}-{days_ago}'
    date_envoi = timezone.now() - timedelta(days=days_ago)
    return Devis.objects.create(
        company=company,
        reference=ref,
        client=Client.objects.get_or_create(
            company=company,
            nom='Client QJ4',
            defaults=dict(email='client@qj4.ma'),
        )[0],
        statut=statut,
        taux_tva=Decimal('20.00'),
        date_envoi=date_envoi if statut == Devis.Statut.ENVOYE else None,
        created_by=user,
    )


@override_settings(EMAIL_BACKEND=CONSOLE, DEVIS_NUDGE_DAYS=[2, 5, 10])
class QJ4CadenceTests(TestCase):
    """Tests de la cadence de relance (canal wa_draft par défaut)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        make_produit(self.company)

    def _devis_at(self, days_ago, statut=Devis.Statut.ENVOYE):
        ref = f'DEV-QJ4-{days_ago}-{statut}'
        try:
            return Devis.objects.get(reference=ref)
        except Devis.DoesNotExist:
            date_envoi = timezone.now() - timedelta(days=days_ago)
            return Devis.objects.create(
                company=self.company,
                reference=ref,
                client=Client.objects.get_or_create(
                    company=self.company,
                    nom='Client QJ4 C',
                    defaults=dict(email='c@qj4.ma'),
                )[0],
                statut=statut,
                taux_tva=Decimal('20.00'),
                date_envoi=date_envoi if statut == Devis.Statut.ENVOYE else None,
                created_by=self.user,
            )

    def test_niveau_0_declenche_a_j2(self):
        """Un devis envoyé il y a 2 jours déclenche exactement le niveau 0."""
        devis = self._devis_at(2)
        count = send_devis_followup_nudges()
        self.assertEqual(count, 1)
        logs = DevisNudgeLog.objects.filter(devis=devis)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.niveau, 0)
        self.assertEqual(log.jours, 2)

    def test_niveau_1_declenche_a_j5(self):
        """Un devis envoyé il y a 5 jours déclenche les niveaux 0 et 1."""
        devis = self._devis_at(5)
        count = send_devis_followup_nudges()
        self.assertGreaterEqual(count, 2)
        niveaux = set(
            DevisNudgeLog.objects.filter(devis=devis).values_list('niveau', flat=True)
        )
        self.assertIn(0, niveaux)
        self.assertIn(1, niveaux)

    def test_niveau_2_declenche_a_j10(self):
        """Un devis envoyé il y a 10 jours déclenche les 3 niveaux (0, 1, 2)."""
        devis = self._devis_at(10)
        count = send_devis_followup_nudges()
        self.assertGreaterEqual(count, 3)
        niveaux = set(
            DevisNudgeLog.objects.filter(devis=devis).values_list('niveau', flat=True)
        )
        self.assertIn(0, niveaux)
        self.assertIn(1, niveaux)
        self.assertIn(2, niveaux)

    def test_pas_de_nudge_avant_j2(self):
        """Un devis envoyé il y a 1 jour ne déclenche aucun nudge."""
        self._devis_at(1)
        count = send_devis_followup_nudges()
        self.assertEqual(count, 0)

    def test_idempotence_deuxieme_run(self):
        """Ré-exécuter le job après qu'un niveau a déjà été logué renvoie 0."""
        devis = self._devis_at(2)
        # Premier passage : déclenche niveau 0.
        first = send_devis_followup_nudges()
        self.assertEqual(first, 1)
        # Deuxième passage : rien à faire.
        second = send_devis_followup_nudges()
        self.assertEqual(second, 0)
        # Toujours un seul log.
        self.assertEqual(DevisNudgeLog.objects.filter(devis=devis).count(), 1)

    def test_arret_sur_accepte(self):
        """Un devis « accepté » n'est pas relancé même si date_envoi est ancienne."""
        devis = self._devis_at(2, statut=Devis.Statut.ACCEPTE)
        count = send_devis_followup_nudges()
        self.assertEqual(count, 0)
        self.assertEqual(DevisNudgeLog.objects.filter(devis=devis).count(), 0)

    def test_arret_sur_refuse(self):
        """Un devis « refusé » n'est pas relancé."""
        devis = self._devis_at(2, statut=Devis.Statut.REFUSE)
        count = send_devis_followup_nudges()
        self.assertEqual(count, 0)
        self.assertEqual(DevisNudgeLog.objects.filter(devis=devis).count(), 0)

    def test_brouillon_ignore(self):
        """Un devis « brouillon » n'est pas relancé (filtre statut=ENVOYE)."""
        devis = self._devis_at(2, statut=Devis.Statut.BROUILLON)
        # Brouillon n'a pas date_envoi (make_devis le met à None hors ENVOYE)
        count = send_devis_followup_nudges()
        self.assertEqual(count, 0)
        self.assertEqual(DevisNudgeLog.objects.filter(devis=devis).count(), 0)

    def test_sans_date_envoi_ignore(self):
        """Un devis ENVOYE sans date_envoi est ignoré."""
        devis = Devis.objects.create(
            company=self.company,
            reference='DEV-QJ4-NODATE',
            client=Client.objects.get_or_create(
                company=self.company,
                nom='Client ND',
                defaults=dict(email='nd@qj4.ma'),
            )[0],
            statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=None,
            created_by=self.user,
        )
        count = send_devis_followup_nudges()
        self.assertEqual(count, 0)
        self.assertEqual(DevisNudgeLog.objects.filter(devis=devis).count(), 0)

    def test_canal_wa_draft_par_defaut(self):
        """Sans backend email, le canal consigné est wa_draft."""
        devis = self._devis_at(2)
        send_devis_followup_nudges()
        log = DevisNudgeLog.objects.get(devis=devis, niveau=0)
        self.assertEqual(log.canal, DevisNudgeLog.Canal.WA_DRAFT)


@override_settings(EMAIL_BACKEND=LOCMEM, DEVIS_NUDGE_DAYS=[2, 5, 10])
class QJ4EmailCanalTests(TestCase):
    """Tests avec backend email configuré (locmem) → canal doit être email."""

    def setUp(self):
        self.company = make_company(slug='qj4-email-co', nom='QJ4 Email Co')
        self.user = make_user(
            self.company, username='qj4_email_v', email='vendeur_email@taqinor.ma')
        make_produit(self.company)

    def test_canal_email_quand_configure(self):
        """Avec backend locmem ET vendeur avec email, canal = email."""
        # is_email_configured returns False for locmem — email is "test-only".
        # We override is_email_configured to return True to simulate Brevo/prod.
        from unittest.mock import patch
        devis = Devis.objects.create(
            company=self.company,
            reference='DEV-QJ4-EMAIL',
            client=Client.objects.get_or_create(
                company=self.company,
                nom='Client Email',
                defaults=dict(email='cli@email.ma'),
            )[0],
            statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=timezone.now() - timedelta(days=2),
            created_by=self.user,
        )
        with patch('apps.ventes.services.is_email_configured', return_value=True):
            count = send_devis_followup_nudges()
        self.assertEqual(count, 1)
        log = DevisNudgeLog.objects.get(devis=devis, niveau=0)
        self.assertEqual(log.canal, DevisNudgeLog.Canal.EMAIL)


@override_settings(EMAIL_BACKEND=CONSOLE, DEVIS_NUDGE_DAYS=[2, 5, 10])
class QJ4MultiTenantTests(TestCase):
    """Tests de scoping multi-tenant."""

    def setUp(self):
        self.co_a = make_company(slug='qj4-co-a', nom='Co A')
        self.co_b = make_company(slug='qj4-co-b', nom='Co B')
        self.user_a = make_user(self.co_a, username='qj4_u_a', email='a@a.ma')
        self.user_b = make_user(self.co_b, username='qj4_u_b', email='b@b.ma')

    def _make_devis(self, company, user, ref_suffix, days_ago):
        return Devis.objects.create(
            company=company,
            reference=f'DEV-QJ4-MT-{ref_suffix}',
            client=Client.objects.get_or_create(
                company=company,
                nom=f'Client MT {ref_suffix}',
                defaults=dict(email=f'{ref_suffix}@mt.ma'),
            )[0],
            statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=timezone.now() - timedelta(days=days_ago),
            created_by=user,
        )

    def test_deux_societes_deux_nudges_independants(self):
        """Deux devis, deux sociétés — chacun reçoit son propre nudge log."""
        devis_a = self._make_devis(self.co_a, self.user_a, 'A', 2)
        devis_b = self._make_devis(self.co_b, self.user_b, 'B', 2)
        count = send_devis_followup_nudges()
        self.assertEqual(count, 2)
        # Chaque devis a bien son propre log (company scopé).
        self.assertEqual(DevisNudgeLog.objects.filter(devis=devis_a).count(), 1)
        self.assertEqual(DevisNudgeLog.objects.filter(devis=devis_b).count(), 1)
        log_a = DevisNudgeLog.objects.get(devis=devis_a, niveau=0)
        log_b = DevisNudgeLog.objects.get(devis=devis_b, niveau=0)
        self.assertEqual(log_a.company, self.co_a)
        self.assertEqual(log_b.company, self.co_b)

    def test_idempotence_multi_tenant(self):
        """Idempotence préservée en multi-tenant : le second passage renvoie 0."""
        self._make_devis(self.co_a, self.user_a, 'A2', 2)
        self._make_devis(self.co_b, self.user_b, 'B2', 2)
        send_devis_followup_nudges()
        second = send_devis_followup_nudges()
        self.assertEqual(second, 0)


@override_settings(EMAIL_BACKEND=CONSOLE, DEVIS_NUDGE_DAYS=[2, 5, 10])
class QJ4CeleryTaskTests(TestCase):
    """Smoke test : la tâche Celery wrappée appelle bien le service."""

    def setUp(self):
        self.company = make_company(slug='qj4-task-co', nom='QJ4 Task Co')
        self.user = make_user(self.company, username='qj4_t', email='t@qj4.ma')

    def test_celery_task_appelle_service(self):
        """La tâche ``devis_followup_nudges`` s'exécute et renvoie un entier."""
        from apps.ventes.scheduled import devis_followup_nudges
        # Crée un devis à relancer.
        Devis.objects.create(
            company=self.company,
            reference='DEV-QJ4-TASK',
            client=Client.objects.get_or_create(
                company=self.company,
                nom='Client Task',
                defaults=dict(email='task@qj4.ma'),
            )[0],
            statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=timezone.now() - timedelta(days=2),
            created_by=self.user,
        )
        # Appel direct (sans worker Celery).
        result = devis_followup_nudges()
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)
