"""CHT27 — Cockpit KPI chantier (cycle time, taux de reprise post-MES,
chantiers en retard)."""
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, InstallationActivity, Intervention
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/reports/chantier/'


class ChantierReportBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cht27-co', defaults={'nom': 'CHT27 Co'})[0]
        self.user = User.objects.create_user(
            username='cht27_u', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientCHT27')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _installation(self, **kwargs):
        defaults = dict(
            company=self.company, client=self.client_obj,
            reference=f'CH-CHT27-{Installation.objects.count() + 1}')
        defaults.update(kwargs)
        return Installation.objects.create(**defaults)

    def _transition(self, inst, old_label, new_label, when):
        """Simule une ligne de chatter 'statut' (comme `activity.log_changes`
        l'écrirait) horodatée à `when` — le chatter stocke des LIBELLÉS
        affichés, jamais les clés brutes."""
        act = InstallationActivity.objects.create(
            company=inst.company, installation=inst, user=self.user,
            kind=InstallationActivity.Kind.MODIFICATION,
            field='statut', field_label='Statut',
            old_value=old_label, new_value=new_label)
        InstallationActivity.objects.filter(pk=act.pk).update(created_at=when)
        return act


class TestCycleTimeChantiers(ChantierReportBase):
    def test_requires_responsable_or_admin(self):
        limited = User.objects.create_user(
            username='cht27_limited', password='x', company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(limited)}')
        resp = api.get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_segment_deltas_from_simulated_transitions(self):
        t0 = datetime(2026, 1, 1, 8, 0, 0)
        inst = self._installation()
        Installation.objects.filter(pk=inst.pk).update(date_creation=t0)
        inst.refresh_from_db()

        self._transition(inst, 'Signé', 'Planifié', t0 + timedelta(days=2))
        self._transition(inst, 'Planifié', 'En cours', t0 + timedelta(days=5))
        self._transition(inst, 'En cours', 'Installé', t0 + timedelta(days=9))
        self._transition(inst, 'Installé', 'Réceptionné', t0 + timedelta(days=10))

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        segments = {
            (s['de'], s['vers']): s for s in resp.data['cycle_time']['segments']
        }
        self.assertEqual(segments[('signe', 'planifie')]['jours_moyen'], 2.0)
        self.assertEqual(segments[('planifie', 'en_cours')]['jours_moyen'], 3.0)
        self.assertEqual(segments[('en_cours', 'installe')]['jours_moyen'], 4.0)
        self.assertEqual(segments[('installe', 'receptionne')]['jours_moyen'], 1.0)
        for seg in segments.values():
            self.assertEqual(seg['n'], 1)

    def test_median_across_several_chantiers(self):
        t0 = datetime(2026, 1, 1, 8, 0, 0)
        for jours in (2, 4, 6):
            inst = self._installation()
            Installation.objects.filter(pk=inst.pk).update(date_creation=t0)
            inst.refresh_from_db()
            self._transition(inst, 'Signé', 'Planifié', t0 + timedelta(days=jours))

        resp = self.api.get(URL)
        segments = {
            (s['de'], s['vers']): s for s in resp.data['cycle_time']['segments']
        }
        seg = segments[('signe', 'planifie')]
        self.assertEqual(seg['n'], 3)
        self.assertEqual(seg['jours_median'], 4.0)
        self.assertEqual(seg['jours_moyen'], 4.0)

    def test_legacy_labels_resolve_to_canonical_keys(self):
        """'À planifier' et 'Posé' sont des LIBELLÉS HÉRITÉS — ils doivent se
        résoudre sur leurs clés canoniques (SIGNE, INSTALLE) exactement comme
        les libellés du funnel N1, jamais un parsing du français brut."""
        t0 = datetime(2026, 1, 1, 8, 0, 0)
        inst = self._installation()
        Installation.objects.filter(pk=inst.pk).update(date_creation=t0)
        inst.refresh_from_db()

        # Départ légataire 'À planifier' (canonique SIGNE) → 'En cours', puis
        # 'Posé' (canonique INSTALLE, alias hérité) 3 jours plus tard.
        self._transition(inst, 'À planifier', 'En cours', t0 + timedelta(days=1))
        self._transition(inst, 'En cours', 'Posé', t0 + timedelta(days=4))

        resp = self.api.get(URL)
        segments = {
            (s['de'], s['vers']): s for s in resp.data['cycle_time']['segments']
        }
        self.assertEqual(segments[('signe', 'planifie')]['n'], 0)
        self.assertEqual(segments[('en_cours', 'installe')]['n'], 1)
        self.assertEqual(segments[('en_cours', 'installe')]['jours_moyen'], 3.0)

    def test_grouped_by_type_installation(self):
        t0 = datetime(2026, 1, 1, 8, 0, 0)
        inst_r = self._installation(type_installation=Installation.TypeInstallation.RESIDENTIEL)
        Installation.objects.filter(pk=inst_r.pk).update(date_creation=t0)
        inst_r.refresh_from_db()
        self._transition(inst_r, 'Signé', 'Planifié', t0 + timedelta(days=1))

        inst_i = self._installation(type_installation=Installation.TypeInstallation.INDUSTRIEL)
        Installation.objects.filter(pk=inst_i.pk).update(date_creation=t0)
        inst_i.refresh_from_db()
        self._transition(inst_i, 'Signé', 'Planifié', t0 + timedelta(days=7))

        resp = self.api.get(URL)
        par_type = {
            p['type_installation']: p for p in resp.data['cycle_time']['par_type_installation']
        }
        seg_r = next(s for s in par_type['residentiel']['segments'] if s['de'] == 'signe')
        seg_i = next(s for s in par_type['industriel']['segments'] if s['de'] == 'signe')
        self.assertEqual(seg_r['jours_moyen'], 1.0)
        self.assertEqual(seg_i['jours_moyen'], 7.0)

    def test_multi_tenant_scoping(self):
        other_co = Company.objects.create(slug='cht27-other', nom='Autre Co')
        other_client = Client.objects.create(company=other_co, nom='Autre client')
        other_inst = Installation.objects.create(
            company=other_co, client=other_client, reference='CH-OTHER-1')
        t0 = datetime(2026, 1, 1, 8, 0, 0)
        Installation.objects.filter(pk=other_inst.pk).update(date_creation=t0)
        other_inst.refresh_from_db()
        other_act = InstallationActivity.objects.create(
            company=other_co, installation=other_inst,
            kind=InstallationActivity.Kind.MODIFICATION,
            field='statut', old_value='Signé', new_value='Planifié')
        InstallationActivity.objects.filter(pk=other_act.pk).update(
            created_at=t0 + timedelta(days=1))

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        segments = {
            (s['de'], s['vers']): s for s in resp.data['cycle_time']['segments']
        }
        # Aucun chantier de CETTE société — tout est à 0/None.
        self.assertEqual(segments[('signe', 'planifie')]['n'], 0)
        self.assertIsNone(segments[('signe', 'planifie')]['jours_moyen'])


class TestTauxRepriseMES(ChantierReportBase):
    def test_reprise_within_window_counts(self):
        aujourd_hui = date.today()
        inst = self._installation(
            date_mise_en_service=aujourd_hui - timedelta(days=60))
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.DEPANNAGE,
            date_realisee=aujourd_hui - timedelta(days=45))

        resp = self.api.get(URL)
        taux = resp.data['taux_reprise_post_mes']
        self.assertEqual(taux['nb_eligibles'], 1)
        self.assertEqual(taux['nb_avec_reprise'], 1)
        self.assertEqual(taux['taux_pct'], 100.0)

    def test_depannage_outside_window_excluded(self):
        aujourd_hui = date.today()
        inst = self._installation(
            date_mise_en_service=aujourd_hui - timedelta(days=90))
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.DEPANNAGE,
            date_realisee=aujourd_hui - timedelta(days=40))  # > 30 jours après MES

        resp = self.api.get(URL)
        taux = resp.data['taux_reprise_post_mes']
        self.assertEqual(taux['nb_eligibles'], 1)
        self.assertEqual(taux['nb_avec_reprise'], 0)
        self.assertEqual(taux['taux_pct'], 0.0)

    def test_mes_too_recent_excluded_from_denominator(self):
        aujourd_hui = date.today()
        # MES il y a 10 jours seulement : la fenêtre de 30 jours n'est pas
        # écoulée → hors dénominateur (ne doit PAS compter « sans reprise »).
        self._installation(date_mise_en_service=aujourd_hui - timedelta(days=10))

        resp = self.api.get(URL)
        taux = resp.data['taux_reprise_post_mes']
        self.assertEqual(taux['nb_eligibles'], 0)
        self.assertIsNone(taux['taux_pct'])

    def test_est_recidive_not_duplicated(self):
        """Le taux de reprise chantier est un signal DISTINCT : il ne lit ni
        n'écrit `sav.Ticket.est_recidive`."""
        from apps.sav.models import Ticket
        aujourd_hui = date.today()
        self._installation(
            date_mise_en_service=aujourd_hui - timedelta(days=60))
        Ticket.objects.create(
            company=self.company, reference='T-CHT27-1',
            client=self.client_obj, est_recidive=True)

        resp = self.api.get(URL)
        taux = resp.data['taux_reprise_post_mes']
        # Le ticket récidivant seul (sans intervention DEPANNAGE réalisée sur
        # CE chantier) ne doit PAS faire compter de reprise.
        self.assertEqual(taux['nb_eligibles'], 1)
        self.assertEqual(taux['nb_avec_reprise'], 0)


class TestChantiersEnRetard(ChantierReportBase):
    def test_late_chantier_not_yet_installed(self):
        aujourd_hui = date.today()
        self._installation(
            statut=Installation.Statut.PLANIFIE,
            date_pose_prevue=aujourd_hui - timedelta(days=5))

        resp = self.api.get(URL)
        retard = resp.data['chantiers_en_retard']
        self.assertEqual(retard['total'], 1)
        self.assertEqual(retard['items'][0]['jours_retard'], 5)

    def test_installed_chantier_not_late(self):
        aujourd_hui = date.today()
        self._installation(
            statut=Installation.Statut.INSTALLE,
            date_pose_prevue=aujourd_hui - timedelta(days=5))

        resp = self.api.get(URL)
        self.assertEqual(resp.data['chantiers_en_retard']['total'], 0)

    def test_future_pose_date_not_late(self):
        aujourd_hui = date.today()
        self._installation(
            statut=Installation.Statut.PLANIFIE,
            date_pose_prevue=aujourd_hui + timedelta(days=5))

        resp = self.api.get(URL)
        self.assertEqual(resp.data['chantiers_en_retard']['total'], 0)

    def test_legacy_statut_pose_en_cours_treated_as_en_cours(self):
        """Alias hérité (canonique EN_COURS, < INSTALLE) : doit compter
        comme « pas encore posé », donc en retard si sa date est dépassée."""
        aujourd_hui = date.today()
        self._installation(
            statut=Installation.Statut.POSE_EN_COURS,
            date_pose_prevue=aujourd_hui - timedelta(days=2))

        resp = self.api.get(URL)
        self.assertEqual(resp.data['chantiers_en_retard']['total'], 1)

    def test_annule_excluded(self):
        aujourd_hui = date.today()
        self._installation(
            statut=Installation.Statut.PLANIFIE, annule=True,
            motif_annulation='test',
            date_pose_prevue=aujourd_hui - timedelta(days=5))

        resp = self.api.get(URL)
        self.assertEqual(resp.data['chantiers_en_retard']['total'], 0)
