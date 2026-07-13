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

from apps.crm import services
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
        moved = services.archiver_anciens(now, 0, apply_=True)
        self.assertEqual(moved, 0)
        self.assertEqual(LeadActivity.objects.count(), 10)
        self.assertEqual(LeadActivityArchive.objects.count(), 0)

    def test_dry_run_counts_without_moving(self):
        _bulk_activities(self.company_a, self.lead_a, 7, age_days=400)
        now = timezone.now()
        would = services.archiver_anciens(now, 90, apply_=False)
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
        moved = services.archiver_anciens(now, 90, apply_=True)

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
        moved = services.archiver_anciens(now, 90, apply_=True)

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
