"""XPLT6 — alertes de seuil sur KPI agrégés (dédup + CRUD + isolation tenant)."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.reporting.kpi_alertes import evaluate_kpi_alerte
from apps.reporting.models import KpiAlerte
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


class KpiAlerteBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='xplt6-co', defaults={'nom': 'XPLT6 Co'})[0]
        self.other_company = Company.objects.get_or_create(
            slug='xplt6-other', defaults={'nom': 'XPLT6 Other'})[0]
        self.user = User.objects.create_user(
            username='xplt6_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class TestKpiAlerteCrud(KpiAlerteBase):
    def test_create_and_list_scoped(self):
        resp = self.api.post('/api/django/reporting/kpi-alertes/', {
            'nom': 'Stock trop élevé', 'kpi': KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            'operateur': KpiAlerte.Operateur.SUP, 'seuil': '60',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        alerte = KpiAlerte.objects.get(id=resp.data['id'])
        self.assertEqual(alerte.company_id, self.company.id)

    def test_other_company_alertes_not_visible(self):
        KpiAlerte.objects.create(
            company=self.other_company, kpi=KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('60'))
        resp = self.api.get('/api/django/reporting/kpi-alertes/')
        self.assertEqual(resp.status_code, 200)
        ids = [a['id'] for a in resp.data.get('results', resp.data)]
        self.assertEqual(ids, [])

    def test_gated_to_responsable_or_admin(self):
        limited = User.objects.create_user(
            username='limited_kpi', password='x', company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(limited)}')
        resp = api.get('/api/django/reporting/kpi-alertes/')
        self.assertEqual(resp.status_code, 403)


class TestKpiAlerteEvaluationDedup(KpiAlerteBase):
    def test_threshold_crossed_notifies_once_then_rearms(self):
        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('60'))
        alerte.destinataires_utilisateurs.add(self.user)

        with mock.patch(
                'apps.reporting.kpi_alertes._compute_valeur_stock_totale',
                return_value=Decimal('75')), \
            mock.patch(
                'apps.notifications.services.notify') as mock_notify:
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertEqual(valeur, Decimal('75'))
        self.assertTrue(franchi)
        self.assertTrue(notifie)
        mock_notify.assert_called_once()
        alerte.refresh_from_db()
        self.assertTrue(alerte.deja_notifie)

        # Toujours au-dessus du seuil → PAS de re-notification (dédup).
        with mock.patch(
                'apps.reporting.kpi_alertes._compute_valeur_stock_totale',
                return_value=Decimal('80')), \
            mock.patch(
                'apps.notifications.services.notify') as mock_notify2:
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertTrue(franchi)
        self.assertFalse(notifie)
        mock_notify2.assert_not_called()

        # Repasse sous le seuil → ré-armement (deja_notifie retombe à False).
        with mock.patch(
                'apps.reporting.kpi_alertes._compute_valeur_stock_totale',
                return_value=Decimal('30')):
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertFalse(franchi)
        self.assertFalse(notifie)
        alerte.refresh_from_db()
        self.assertFalse(alerte.deja_notifie)

        # Re-franchit le seuil → RE-notifie.
        with mock.patch(
                'apps.reporting.kpi_alertes._compute_valeur_stock_totale',
                return_value=Decimal('90')), \
            mock.patch(
                'apps.notifications.services.notify') as mock_notify3:
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertTrue(franchi)
        self.assertTrue(notifie)
        mock_notify3.assert_called_once()

    def test_erreur_de_calcul_ne_rearme_pas_la_dedup(self):
        """ACEL37 — un calcul qui lève un jour ne vaut pas « repassé du bon
        côté » : la dédup reste armée, le lendemain au-delà du seuil = 0 envoi."""
        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('60'),
            deja_notifie=True)
        alerte.destinataires_utilisateurs.add(self.user)
        cible = 'apps.reporting.kpi_alertes._compute_valeur_stock_totale'
        with mock.patch(cible, side_effect=RuntimeError('source HS')), \
                mock.patch('apps.notifications.services.notify') as envoi:
            self.assertEqual(evaluate_kpi_alerte(alerte), (None, False, False))
        alerte.refresh_from_db()
        self.assertTrue(alerte.deja_notifie)
        self.assertIsNotNone(alerte.derniere_evaluation_le)
        self.assertIsNone(alerte.derniere_valeur)
        with mock.patch(cible, return_value=Decimal('75')), \
                mock.patch('apps.notifications.services.notify') as envoi2:
            evaluate_kpi_alerte(alerte)
        envoi.assert_not_called()
        envoi2.assert_not_called()

    def test_tache_enregistree_sans_controles_django(self):
        """ACEL38 — un worker démarré avec CELERY_SKIP_CHECKS=1 (aucun import
        des URLs) connaît quand même ``reporting.evaluate_kpi_alertes``."""
        import os
        import subprocess
        import sys
        from django.conf import settings
        code = (
            'import sys\n'
            'from erp_agentique.celery import app\n'
            'app.loader.import_default_modules()\n'
            "print('reporting.evaluate_kpi_alertes' in app.tasks, "
            "'erp_agentique.urls' in sys.modules)\n")
        env = dict(os.environ, CELERY_SKIP_CHECKS='1')
        sortie = subprocess.run(
            [sys.executable, '-c', code], cwd=str(settings.BASE_DIR), env=env,
            capture_output=True, text=True, timeout=300)
        self.assertEqual(sortie.returncode, 0, sortie.stderr[-2000:])
        self.assertEqual(sortie.stdout.strip().splitlines()[-1], 'True False')

    def test_valeur_stock_totale_real_selector(self):
        Produit.objects.create(
            company=self.company, nom='Panneau', sku='XPLT6-1',
            prix_vente=Decimal('1000'), quantite_stock=10)
        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('5000'))
        valeur, franchi, _ = evaluate_kpi_alerte(alerte)
        self.assertEqual(valeur, Decimal('10000'))
        self.assertTrue(franchi)

    def test_tenant_isolation_in_evaluation(self):
        """Le calcul du stock d'une société n'inclut jamais celui d'une autre."""
        Produit.objects.create(
            company=self.other_company, nom='AutreStock', sku='XPLT6-OTHER',
            prix_vente=Decimal('99999'), quantite_stock=100)
        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('1'))
        valeur, franchi, _ = evaluate_kpi_alerte(alerte)
        self.assertEqual(valeur, Decimal('0'))
        self.assertFalse(franchi)

    def test_inactive_alerte_not_evaluated_by_batch(self):
        from apps.reporting.kpi_alertes import evaluate_all_kpi_alertes
        KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('1'), actif=False)
        results = evaluate_all_kpi_alertes(now=timezone.now())
        self.assertEqual(results, [])

    def test_societe_suspendue_non_evaluee(self):
        # APFS122 — B suspendue (hors active_companies()) : son alerte n'est
        # jamais évaluée par le balayage ; A active : évaluée.
        from apps.reporting.kpi_alertes import evaluate_all_kpi_alertes
        suspendue = Company.objects.create(nom='Suspendue APFS122', actif=False)
        alertes = [KpiAlerte.objects.create(
            company=co, kpi=KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('1'))
            for co in (self.company, suspendue)]
        results = evaluate_all_kpi_alertes(now=timezone.now())
        self.assertEqual([r['alerte_id'] for r in results], [alertes[0].id])


class TestChampsStrictsFuzzR12(KpiAlerteBase):
    """api-fuzz r12 (CI #956) — ``actif: 0`` (POST/PATCH/PUT) → 400 comme le
    schéma le déclare ; ``metric_cle`` est servie aussi sur un PATCH (DRF
    sautait la clé à ``default`` en réponse partielle → schéma violé)."""

    def _alerte(self):
        return KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('60'))

    def test_actif_entier_refuse_en_400(self):
        corps = {'kpi': KpiAlerte.Kpi.VALEUR_STOCK_TOTALE, 'operateur': 'sup',
                 'seuil': '0', 'actif': 0}
        resp = self.api.post('/api/django/reporting/kpi-alertes/', corps, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('actif', resp.data)
        alerte = self._alerte()
        url = f'/api/django/reporting/kpi-alertes/{alerte.id}/'
        self.assertEqual(self.api.patch(url, {'actif': 0}, format='json').status_code, 400)
        self.assertEqual(self.api.put(url, corps, format='json').status_code, 400)
        resp = self.api.put(url, {**corps, 'actif': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_patch_sert_metric_cle(self):
        alerte = self._alerte()
        resp = self.api.patch(
            f'/api/django/reporting/kpi-alertes/{alerte.id}/', {'nom': 'x'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data.get('metric_cle', 'ABSENTE'), '')

    def test_destinataires_objet_refuse_et_regle_publiee(self):
        """ERR-ENF11-FUZZ-REPORTING — ``destinataires_utilisateurs: {}`` (un
        OBJET) était lu comme une liste vide : 400 ; la création publie la
        règle « KPI du catalogue OU métrique nommée »."""
        from drf_spectacular.generators import SchemaGenerator
        from django.urls import include, path

        from apps.reporting import urls as reporting_urls

        corps = {'kpi': KpiAlerte.Kpi.VALEUR_STOCK_TOTALE, 'operateur': 'sup',
                 'seuil': '1', 'destinataires_utilisateurs': {}}
        url = '/api/django/reporting/kpi-alertes/'
        resp = self.api.post(url, corps, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('destinataires_utilisateurs', resp.data)
        alerte = self._alerte()
        resp = self.api.patch(f'{url}{alerte.id}/', {
            'destinataires_utilisateurs': {}}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.post(url, {**corps, 'destinataires_utilisateurs': []},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        chemins = SchemaGenerator(patterns=[
            path('api/django/reporting/', include(reporting_urls)),
        ]).get_schema(request=None, public=True)['paths']
        schema = chemins['/api/django/reporting/kpi-alertes/']['post'][
            'requestBody']['content']['application/json']['schema']
        self.assertIn('anyOf', schema['allOf'][1])

    def test_regle_croisee_en_modification(self):
        """ERR-ENF11-FUZZ-REPORTING — PATCH : la règle se lit sur la fiche
        enregistrée -> 409 (plus 400) ; PUT : règle publiée au schéma, 400 au
        champ."""
        from drf_spectacular.generators import SchemaGenerator
        from django.urls import include, path

        from apps.reporting import urls as reporting_urls

        alerte = self._alerte()
        url = f'/api/django/reporting/kpi-alertes/{alerte.id}/'
        resp = self.api.patch(url, {'mode_detection': 'variation'},
                              format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        resp = self.api.patch(url, {'source': 'metrique'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        resp = self.api.put(url, {'source': 'metrique', 'seuil': '1',
                                  'operateur': 'sup'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('metric_definition', resp.data)
        chemins = SchemaGenerator(patterns=[
            path('api/django/reporting/', include(reporting_urls)),
        ]).get_schema(request=None, public=True)['paths']
        schema = chemins['/api/django/reporting/kpi-alertes/{id}/']['put'][
            'requestBody']['content']['application/json']['schema']
        self.assertIn('anyOf', schema['allOf'][1])
