"""PUB62 — leads_ville_rows : matière première (ville/signé) de la carte
chaleur ville adsengine (jamais une ville vide fabriquée)."""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.selectors import leads_ville_rows
from apps.crm.stages import COLD, SIGNED


class LeadsVilleRowsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB62 CRM Co')

    def test_lead_without_ville_absent(self):
        Lead.objects.create(company=self.company, nom='Sans ville')
        self.assertEqual(leads_ville_rows(self.company), [])

    def test_lead_with_ville_present_and_signed_flag(self):
        Lead.objects.create(
            company=self.company, nom='Signé Casa', ville='Casablanca',
            stage=SIGNED)
        Lead.objects.create(
            company=self.company, nom='Froid Rabat', ville='Rabat',
            stage=COLD)
        rows = {r['ville']: r for r in leads_ville_rows(self.company)}
        self.assertTrue(rows['Casablanca']['signed'])
        self.assertFalse(rows['Rabat']['signed'])

    def test_perdu_lead_never_counted_signed_even_if_stage_signed(self):
        Lead.objects.create(
            company=self.company, nom='Perdu', ville='Marrakech',
            stage=SIGNED, perdu=True)
        rows = leads_ville_rows(self.company)
        self.assertFalse(rows[0]['signed'])

    def test_archived_lead_excluded(self):
        Lead.objects.create(
            company=self.company, nom='Archivé', ville='Fès',
            is_archived=True)
        self.assertEqual(leads_ville_rows(self.company), [])

    def test_ville_is_stripped(self):
        Lead.objects.create(
            company=self.company, nom='Espace', ville='  Tanger  ')
        rows = leads_ville_rows(self.company)
        self.assertEqual(rows[0]['ville'], 'Tanger')

    def test_filtre_canal_et_fenetre(self):
        """AACQ10 — canaux + fenêtre de création, défaut inchangé.

        AACQ106 — chaque borne est isolée par un lead du MÊME canal hors
        fenêtre (Rabat avant ``date_start``, Fès après ``date_end``) : ignorer
        ``date_start`` ⇒ 9 au lieu de 6, ignorer ``date_end`` ⇒ 8 au lieu de 6."""
        import datetime
        from django.utils import timezone
        hier = timezone.localdate() - datetime.timedelta(days=1)

        def creer(n, nom, ville, canal, il_y_a_jours):
            for i in range(n):
                lead = Lead.objects.create(
                    company=self.company, nom=f'{nom} {i}', ville=ville,
                    canal=canal)
                if il_y_a_jours:
                    Lead.objects.filter(pk=lead.pk).update(
                        date_creation=timezone.now()
                        - datetime.timedelta(days=il_y_a_jours))

        creer(6, 'Meta', 'Settat', 'meta_ads', 1)
        creer(3, 'Meta ancien', 'Rabat', 'meta_ads', 700)
        creer(2, 'Meta du jour', 'Fès', 'meta_ads', 0)
        creer(4, 'Web', 'Casablanca', 'site_web', 700)
        autre = Company.objects.create(nom='PUB62 autre', slug='pub62-autre')

        def villes(**filtres):
            rows = leads_ville_rows(self.company, **filtres)
            return len(rows), {r['ville'] for r in rows}

        meta = {'canaux': ['meta_ads']}
        self.assertEqual(villes(date_start=hier, date_end=hier, **meta),
                         (6, {'Settat'}))
        self.assertEqual(villes(date_start=hier, **meta),
                         (8, {'Settat', 'Fès'}))
        self.assertEqual(villes(date_end=hier, **meta),
                         (9, {'Settat', 'Rabat'}))
        self.assertEqual(villes()[0], 15)
        self.assertEqual(leads_ville_rows(autre, canaux=['meta_ads'],
                                          date_start=hier, date_end=hier), [])
