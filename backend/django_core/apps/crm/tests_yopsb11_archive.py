"""YOPSB11 — Archivage par lots de `LeadActivity` (chatter à forte croissance).

Le chatter est append-only et grossit sans borne. `services.archiver_anciens`
DÉPLACE les entrées plus vieilles que N jours vers `LeadActivityArchive` par
lots de 5 000 (un commit par lot — jamais de transaction géante) puis les
supprime de la table vive. Couvre :

  - sans fenêtre (jours=0/OFF) rien ne bouge (comportement inchangé) ;
  - avec une fenêtre, les entrées anciennes migrent par lots (12 000 lignes →
    plusieurs lots) et le total archivé est exact ;
  - les comptages agrégés par société survivent dans l'archive ;
  - isolation société : l'archivage d'une société ne touche pas les entrées
    d'une autre, et les entrées RÉCENTES restent vives ;
  - dry-run (`apply_=False`) : compte sans rien déplacer.

Run :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_yopsb11_archive -v 2
"""
from django.test import TestCase
from django.utils import timezone

from apps.crm import fiche_archivage
from apps.crm.models import (
    Lead, LeadActivity, LeadActivityArchive,
)


def _make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def _bulk_activities(company, lead, n, age_days):
    """Crée `n` LeadActivity pour (company, lead) horodatées `age_days` en
    arrière. `created_at` est `auto_now_add` → on force la date via un
    `update()` après le bulk_create (contourne l'horodatage automatique)."""
    now = timezone.now()
    LeadActivity.objects.bulk_create([
        LeadActivity(company=company, lead=lead, kind=LeadActivity.Kind.NOTE,
                     body=f'n{i}')
        for i in range(n)
    ])
    if age_days is not None:
        stamp = now - timezone.timedelta(days=age_days)
        (LeadActivity.objects
         .filter(company=company, lead=lead)
         .filter(new_value__isnull=True, body__startswith='n')
         .update(created_at=stamp))


class Yopsb11ArchiveTests(TestCase):
    def setUp(self):
        self.company_a = _make_company('yopsb11-a', 'Société A')
        self.company_b = _make_company('yopsb11-b', 'Société B')
        self.lead_a = Lead.objects.create(
            company=self.company_a, nom='A', prenom='Lead', stage='NEW')
        self.lead_b = Lead.objects.create(
            company=self.company_b, nom='B', prenom='Lead', stage='NEW')

    def test_off_by_default_archives_nothing(self):
        _bulk_activities(self.company_a, self.lead_a, 10, age_days=400)
        now = timezone.now()
        # jours=0 → OFF (défaut) : rien ne bouge.
        moved = fiche_archivage.archiver_anciens(now, 0, apply_=True)
        self.assertEqual(moved, 0)
        self.assertEqual(LeadActivity.objects.count(), 10)
        self.assertEqual(LeadActivityArchive.objects.count(), 0)

    def test_dry_run_counts_without_moving(self):
        _bulk_activities(self.company_a, self.lead_a, 7, age_days=400)
        now = timezone.now()
        would = fiche_archivage.archiver_anciens(now, 90, apply_=False)
        self.assertEqual(would, 7)
        # Rien n'a bougé en dry-run.
        self.assertEqual(LeadActivity.objects.count(), 7)
        self.assertEqual(LeadActivityArchive.objects.count(), 0)

    def test_archives_old_rows_in_batches(self):
        # 12 000 anciennes (> plusieurs lots de 5 000) + 3 récentes qui restent.
        _bulk_activities(self.company_a, self.lead_a, 12000, age_days=400)
        recent = LeadActivity.objects.create(
            company=self.company_a, lead=self.lead_a,
            kind=LeadActivity.Kind.NOTE, body='recent1')
        LeadActivity.objects.create(
            company=self.company_a, lead=self.lead_a,
            kind=LeadActivity.Kind.NOTE, body='recent2')
        LeadActivity.objects.create(
            company=self.company_a, lead=self.lead_a,
            kind=LeadActivity.Kind.NOTE, body='recent3')

        now = timezone.now()
        moved = fiche_archivage.archiver_anciens(now, 90, apply_=True)

        self.assertEqual(moved, 12000)
        # Les 3 récentes restent vives ; les 12 000 anciennes sont parties.
        self.assertEqual(LeadActivity.objects.count(), 3)
        self.assertTrue(
            LeadActivity.objects.filter(pk=recent.pk).exists())
        # Archive contient exactement les 12 000 déplacées.
        self.assertEqual(LeadActivityArchive.objects.count(), 12000)
        # La copie froide conserve les données + le lien société dénormalisé.
        sample = LeadActivityArchive.objects.first()
        self.assertEqual(sample.company_id, self.company_a.id)
        self.assertEqual(sample.lead_id, self.lead_a.id)
        self.assertEqual(sample.kind, LeadActivity.Kind.NOTE)

    def test_company_isolation_and_aggregate_counts_survive(self):
        _bulk_activities(self.company_a, self.lead_a, 6000, age_days=400)
        _bulk_activities(self.company_b, self.lead_b, 4000, age_days=400)
        # Une entrée récente de B qui NE doit PAS être archivée.
        LeadActivity.objects.create(
            company=self.company_b, lead=self.lead_b,
            kind=LeadActivity.Kind.NOTE, body='recent_b')

        now = timezone.now()
        moved = fiche_archivage.archiver_anciens(now, 90, apply_=True)

        self.assertEqual(moved, 10000)
        # B garde son entrée récente vive.
        self.assertEqual(
            LeadActivity.objects.filter(company=self.company_b).count(), 1)
        self.assertEqual(
            LeadActivity.objects.filter(company=self.company_a).count(), 0)
        # Comptages agrégés par société PRÉSERVÉS dans l'archive.
        self.assertEqual(
            LeadActivityArchive.objects.filter(
                company_id=self.company_a.id).count(), 6000)
        self.assertEqual(
            LeadActivityArchive.objects.filter(
                company_id=self.company_b.id).count(), 4000)


class Ntplt38ArchiveUnionTests(TestCase):
    """NTPLT38 — ``?archive=1`` sur /leads/<id>/historique/ : UNION vif +
    archive, keyset, scoping société ; sans le paramètre, comportement
    inchangé (live seul, liste brute)."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        self.company = _make_company('ntplt38-a', 'Société 38 A')
        self.autre = _make_company('ntplt38-b', 'Société 38 B')
        user = get_user_model().objects.create_user(
            username='ntplt38_admin', password='x', role_legacy='admin',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='L', prenom='38', stage='NEW')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        self.url = f'/api/django/crm/leads/{self.lead.id}/historique/'
        now = timezone.now()
        # 3 vives récentes + 4 déplacées vers l'archive (plus anciennes).
        # Les anciennes D'ABORD : le vieillissement de ``_bulk_activities``
        # touche toutes les notes ``n*`` du lead, il vieillissait aussi les 3
        # récentes (7 archivées, 0 vive).
        _bulk_activities(self.company, self.lead, 4, age_days=400)
        _bulk_activities(self.company, self.lead, 3, age_days=None)
        fiche_archivage.archiver_anciens(now, 90, apply_=True)
        # Archive d'une AUTRE société pour le même id de lead : jamais vue.
        LeadActivityArchive.objects.create(
            original_id=999999, company_id=self.autre.id,
            lead_id=self.lead.id, kind='note', body='intrus',
            created_at=now - timezone.timedelta(days=500))

    def test_sans_archive_comportement_inchange(self):
        resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)
        self.assertEqual(len(resp.json()), 3)

    def test_archive_union_complete_et_scopee(self):
        resp = self.api.get(self.url + '?archive=1')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['results']), 7)
        self.assertEqual(sum(1 for r in data['results'] if r['archive']), 4)
        self.assertNotIn('intrus', [r['body'] for r in data['results']])
        self.assertFalse(data['has_next'])
        dates = [r['created_at'] for r in data['results']]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_archive_pagination_keyset_sans_doublon(self):
        vus = []
        url = self.url + '?archive=1&page_size=3'
        while True:
            data = self.api.get(url).json()
            vus += [r['id'] for r in data['results']]
            if not data['has_next']:
                break
            url = (self.url + '?archive=1&page_size=3&cursor='
                   + data['next_cursor'])
        self.assertEqual(len(vus), 7)
        self.assertEqual(len(set(vus)), 7)
