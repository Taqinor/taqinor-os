"""AUD521 — N+1 ``SavSlaSettings.get()`` dans les trois scans quotidiens SLA.

Constat d'audit (le ROUGE figé ici) : ``SavSlaSettings.get`` fait un
``get_or_create`` par appel, et les trois scans (``scan_sla_breaches``,
``scan_sla_pre_alerts_and_escalations``, ``scan_auto_cloture_tickets_resolus``)
l'appelaient DANS leur boucle sur toute la queryset Ticket multi-société — une
requête supplémentaire PAR TICKET, jamais mise en cache sur la durée du scan.

Ces tests prouvent la PLATITUDE : le nombre de requêtes des scans ne doit plus
augmenter avec le nombre de tickets d'une même société (au plus une requête de
réglages par société distincte).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_aud521 -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import SavSlaSettings, Ticket

User = get_user_model()


class AUD521ScansSlaSansNPlusUnTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self._compteur = 0
        self.societes = []
        for i in range(3):
            company, _ = Company.objects.get_or_create(
                slug=f'sav-aud521-{i}', defaults={'nom': f'Sav AUD521 {i}'})
            reglage = SavSlaSettings.get(company)
            reglage.sla_breach_enabled = True
            reglage.auto_cloture_jours = 0  # OFF : on mesure les requêtes
            reglage.save(update_fields=[
                'sla_breach_enabled', 'auto_cloture_jours'])
            client = Client.objects.create(
                company=company, nom=f'Client {i}', prenom='AUD521',
                email=f'aud521-{i}@example.invalid')
            self.societes.append((company, client))

    def _tickets(self, par_societe):
        """Crée ``par_societe`` tickets OUVERTS en dépassement par société."""
        for company, client in self.societes:
            for _ in range(par_societe):
                self._compteur += 1
                Ticket.objects.create(
                    company=company, reference=f'SAV-AUD521-{self._compteur}',
                    client=client, statut=Ticket.Statut.NOUVEAU,
                    date_ouverture=self.today - timedelta(days=30),
                    sla_due_at=self.today - timedelta(days=10))
        return self._compteur

    def _requetes_reglages(self, queries):
        table = SavSlaSettings._meta.db_table.lower()
        return [q for q in queries if table in q['sql'].lower()]

    def test_scan_sla_breaches_plat(self):
        from apps.sav.views import scan_sla_breaches

        self._tickets(par_societe=2)
        with CaptureQueriesContext(connection) as petit:
            scan_sla_breaches()
        Ticket.objects.update(sla_breach=False)
        self._tickets(par_societe=6)
        with CaptureQueriesContext(connection) as grand:
            scan_sla_breaches()

        # Au plus une requête de réglages par société distincte (3), quel que
        # soit le nombre de tickets — avant AUD521 : une par ticket.
        self.assertLessEqual(
            len(self._requetes_reglages(petit.captured_queries)),
            len(self.societes))
        self.assertLessEqual(
            len(self._requetes_reglages(grand.captured_queries)),
            len(self.societes))

    def test_scan_pre_alertes_plat(self):
        from apps.sav.views import scan_sla_pre_alerts_and_escalations

        self._tickets(par_societe=2)
        with CaptureQueriesContext(connection) as petit:
            scan_sla_pre_alerts_and_escalations()
        self._tickets(par_societe=6)
        with CaptureQueriesContext(connection) as grand:
            scan_sla_pre_alerts_and_escalations()

        self.assertLessEqual(
            len(self._requetes_reglages(petit.captured_queries)),
            len(self.societes))
        self.assertLessEqual(
            len(self._requetes_reglages(grand.captured_queries)),
            len(self.societes))

    def test_scan_auto_cloture_plat(self):
        from apps.sav.views import scan_auto_cloture_tickets_resolus

        self._tickets(par_societe=6)
        Ticket.objects.update(statut=Ticket.Statut.RESOLU)
        with CaptureQueriesContext(connection) as ctx:
            scan_auto_cloture_tickets_resolus()
        self.assertLessEqual(
            len(self._requetes_reglages(ctx.captured_queries)),
            len(self.societes))

    def test_reglages_toujours_lus_correctement(self):
        """Non-régression : le scan continue de respecter le réglage société —
        une société qui n'a pas activé le SLA n'est jamais marquée en breach."""
        from apps.sav.views import scan_sla_breaches

        company_off, client_off = self.societes[0]
        reglage = SavSlaSettings.get(company_off)
        reglage.sla_breach_enabled = False
        reglage.save(update_fields=['sla_breach_enabled'])
        t_off = Ticket.objects.create(
            company=company_off, reference='SAV-AUD521-OFF', client=client_off,
            statut=Ticket.Statut.NOUVEAU,
            date_ouverture=self.today - timedelta(days=30),
            sla_due_at=self.today - timedelta(days=10))
        company_on, client_on = self.societes[1]
        t_on = Ticket.objects.create(
            company=company_on, reference='SAV-AUD521-ON', client=client_on,
            statut=Ticket.Statut.NOUVEAU,
            date_ouverture=self.today - timedelta(days=30),
            sla_due_at=self.today - timedelta(days=10))

        self.assertEqual(scan_sla_breaches(), 1)
        t_off.refresh_from_db()
        t_on.refresh_from_db()
        self.assertFalse(t_off.sla_breach)
        self.assertTrue(t_on.sla_breach)

    def test_societe_sans_reglage_enregistre_reste_servie(self):
        """Une société sans ligne ``SavSlaSettings`` retombe sur ``get()``
        (get_or_create) — le repli reste en place."""
        company, _ = Company.objects.get_or_create(
            slug='sav-aud521-neuve', defaults={'nom': 'Sav AUD521 neuve'})
        SavSlaSettings.objects.filter(company=company).delete()
        client = Client.objects.create(
            company=company, nom='Neuve', prenom='AUD521',
            email='aud521-neuve@example.invalid')
        Ticket.objects.create(
            company=company, reference='SAV-AUD521-NEUVE', client=client,
            statut=Ticket.Statut.NOUVEAU,
            date_ouverture=self.today - timedelta(days=30),
            sla_due_at=self.today - timedelta(days=10))
        from apps.sav.views import scan_sla_breaches
        # sla_breach_enabled est False par défaut → aucun breach posé, mais
        # le scan ne doit pas exploser sur la société sans réglage.
        self.assertEqual(scan_sla_breaches(), 0)
        self.assertTrue(SavSlaSettings.objects.filter(company=company).exists())
