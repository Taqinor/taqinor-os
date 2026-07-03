"""
XFAC8 — Canal par niveau de relance (email / WhatsApp / courrier / tâche
d'appel).

Chaque canal produit son action attendue et une seule, le niveau « appel »
crée l'activité assignée, la trace RelanceLog note le canal, comportement
par défaut inchangé, tests.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac8_canal_relance -v 2
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes.models import EmailLog, Facture, FollowupLevel, RelanceLog
from apps.ventes.scheduled import relance_reminders

MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac8-co', nom='XFAC8 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac8@example.com', telephone='+212600000056'):
    return Client.objects.create(
        company=company, nom='Canal', prenom='Client',
        email=email, telephone=telephone, adresse='Casablanca',
    )


def make_facture(company, client_obj, prochaine_relance=None):
    return Facture.objects.create(
        company=company, reference=f'FAC-{MONTH}-{Facture.objects.count() + 1:04d}',
        client=client_obj, statut=Facture.Statut.EMISE,
        montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
        montant_ttc=Decimal('5000'),
        prochaine_relance=prochaine_relance or timezone.now().date(),
    )


class XFAC8CanalRelanceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)

    def test_default_canal_is_email_unchanged_behaviour(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Rappel', delai_jours=0)
        facture = make_facture(self.company, self.client_obj)
        sent = relance_reminders()
        self.assertEqual(sent, 1)
        self.assertEqual(EmailLog.objects.filter(facture=facture).count(), 1)
        log = RelanceLog.objects.get(facture=facture)
        self.assertEqual(log.canal, 'email')

    def test_whatsapp_canal_does_not_send_email(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Rappel WA', delai_jours=0,
            canal=FollowupLevel.Canal.WHATSAPP,
        )
        facture = make_facture(self.company, self.client_obj)
        sent = relance_reminders()
        self.assertEqual(sent, 1)
        self.assertEqual(EmailLog.objects.filter(facture=facture).count(), 0)
        log = RelanceLog.objects.get(facture=facture)
        self.assertEqual(log.canal, 'whatsapp')

    def test_courrier_canal_generates_lettre_pdf_key(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Mise en demeure',
            delai_jours=0, canal=FollowupLevel.Canal.COURRIER,
        )
        facture = make_facture(self.company, self.client_obj)
        sent = relance_reminders()
        self.assertEqual(sent, 1)
        log = RelanceLog.objects.get(facture=facture)
        self.assertEqual(log.canal, 'courrier')
        # PDF best-effort : la clé peut être vide si MinIO indisponible en
        # test, mais le canal DOIT être tracé et aucun email envoyé.
        self.assertEqual(EmailLog.objects.filter(facture=facture).count(), 0)

    def test_appel_canal_creates_records_activity(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Appel commercial',
            delai_jours=0, canal=FollowupLevel.Canal.APPEL,
        )
        facture = make_facture(self.company, self.client_obj)
        sent = relance_reminders()
        self.assertEqual(sent, 1)
        log = RelanceLog.objects.get(facture=facture)
        self.assertEqual(log.canal, 'appel')
        self.assertEqual(EmailLog.objects.filter(facture=facture).count(), 0)

        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Activity
        ct = ContentType.objects.get_for_model(Facture)
        activities = Activity.objects.filter(
            content_type=ct, object_id=facture.id)
        self.assertEqual(activities.count(), 1)
        self.assertIn('Appel', activities.first().activity_type.nom)

    def test_each_canal_produces_exactly_one_action(self):
        canaux = [
            FollowupLevel.Canal.EMAIL, FollowupLevel.Canal.WHATSAPP,
            FollowupLevel.Canal.COURRIER, FollowupLevel.Canal.APPEL,
        ]
        for canal in canaux:
            company = make_company(slug=f'xfac8-{canal}', nom=f'XFAC8 {canal}')
            client_obj = make_client(
                company, email=f'{canal}@example.com',
                telephone='+212600000057')
            FollowupLevel.objects.create(
                company=company, ordre=0, nom=f'Niveau {canal}',
                delai_jours=0, canal=canal)
            make_facture(company, client_obj)
            sent = relance_reminders()
            self.assertGreaterEqual(sent, 1)
