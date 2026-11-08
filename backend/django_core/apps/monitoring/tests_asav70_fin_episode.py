"""ASAV70 — un épisode de sous-performance a une fin : quand l'évaluation
devient impossible (aucune donnée, données périmées, référence retirée, site
retiré), le drapeau ouvert est fermé avec le motif « données indisponibles ».

Run :
    python manage.py test apps.monitoring.tests_asav70_fin_episode -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring import services
from apps.monitoring.models import (
    MonitoringConfig, ProductionReading, UnderperformanceFlag,
)
from apps.monitoring.selectors import fleet_overview
from authentication.models import Company


class FinEpisodeTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav70-co', defaults={'nom': 'ASAV70 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV70')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV70', client=client,
            puissance_installee_kwc=Decimal('5.00'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        self.today = timezone.localdate()
        for i in range(30):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=self.today - timedelta(days=i), period_days=1,
                energy_kwh=Decimal('5'))
        res = services.evaluate_underperformance(
            self.inst, today=self.today)
        self.assertTrue(res['underperforming'])
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 1)

    def _drapeau(self):
        return UnderperformanceFlag.objects.get(installation=self.inst)

    def _ferme_avec_motif(self):
        drapeau = self._drapeau()
        self.assertFalse(drapeau.is_open)
        self.assertEqual(drapeau.motif_cloture, 'donnees_indisponibles')
        self.assertTrue(drapeau.note_cloture)
        self.assertIsNotNone(drapeau.date_cloture)

    def test_sans_donnees_ferme(self):
        ProductionReading.objects.filter(installation=self.inst).delete()
        services.evaluate_underperformance(self.inst, today=self.today)
        self._ferme_avec_motif()
        ov = fleet_overview(self.company, today=self.today)
        self.assertEqual(ov['open_alerts'], 0)

    def test_reference_retiree_ferme(self):
        MonitoringConfig.objects.filter(pk=self.config.pk).update(
            expected_annual_kwh=None)
        services.evaluate_underperformance(self.inst, today=self.today)
        self._ferme_avec_motif()

    def test_donnees_perimees_ferme(self):
        services.evaluate_underperformance(
            self.inst, today=self.today + timedelta(days=400))
        self._ferme_avec_motif()

    def test_site_retire_ferme(self):
        Installation.objects.filter(pk=self.inst.pk).update(parc_actif=False)
        self.inst.refresh_from_db()
        services.evaluate_underperformance(self.inst, today=self.today)
        self._ferme_avec_motif()

    def test_resiliation_ferme_et_n_evalue_plus(self):
        """AMON10 — la résiliation (sans abonnement actif restant) clôt
        l'épisode ; le système n'est plus évalué ni sous SLA. Le système
        manuel jamais abonné (``enabled`` faux) a bien été évalué au setUp."""
        from apps.monitoring.models import SlaDisponibilite
        from apps.monitoring.selectors import disponibilite_vs_garantie
        from apps.sav.models import Ticket

        self.assertFalse(self.config.enabled)
        abonnement = services.creer_abonnement_monitoring(
            self.company, installation_id=self.inst.pk,
            periodicite='mensuel', montant=Decimal('100'))
        services.resilier_abonnement_monitoring(abonnement, motif='Fin')
        drapeau = self._drapeau()
        self.assertFalse(drapeau.is_open)
        self.assertEqual(drapeau.motif_cloture, 'supervision_resiliee')
        tickets_avant = Ticket.objects.filter(company=self.company).count()
        for jours in (90, 120):
            res = services.evaluate_underperformance(
                self.inst, today=self.today + timedelta(days=jours))
            self.assertEqual(res['data_status'], 'supervision_resiliee')
            self.assertFalse(res['underperforming'])
        self.assertEqual(
            UnderperformanceFlag.objects.filter(installation=self.inst).count(),
            1)
        self.assertEqual(
            Ticket.objects.filter(company=self.company).count(), tickets_avant)
        SlaDisponibilite.objects.create(
            company=self.company, installation=self.inst,
            disponibilite_garantie_pct=Decimal('98'))
        ecart = disponibilite_vs_garantie(self.inst, today=self.today)
        self.assertFalse(ecart['sous_garantie'])
        self.assertIsNone(ecart['penalite_mad'])
        self.assertIsNone(ecart['ecart_pct'])

    def _remplacer_onduleur(self):
        """AMON4 — T1 sur le drapeau ouvert, puis l'onduleur est remplacé."""
        from core.events import equipement_remplace

        from apps.monitoring.models import MonitoringSettings
        from apps.sav.models import Equipement, Ticket
        from apps.stock.models import Produit
        reglages = MonitoringSettings.get(self.company)
        reglages.auto_create_ticket = True
        reglages.save()
        services.evaluate_underperformance(self.inst, today=self.today)
        t1 = self._drapeau().ticket
        self.assertIsNotNone(t1)
        Ticket.objects.filter(pk=t1.pk).update(statut=Ticket.Statut.RESOLU)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-AMON4',
            prix_achat=1, prix_vente=2)
        onduleur = Equipement.objects.create(
            company=self.company, produit=produit, installation=self.inst)
        equipement_remplace.send(sender=None, equipement=onduleur, ticket=t1,
                                 company=self.company, user=None)
        drapeau = self._drapeau()
        self.assertFalse(drapeau.is_open)
        self.assertEqual(drapeau.motif_cloture, 'equipement_remplace')
        return t1

    def _releves_apres(self, facteur):
        for i in range(1, 31):
            jour = self.today + timedelta(days=i)
            ProductionReading.objects.create(
                company=self.company, installation=self.inst, date=jour,
                period_days=1, energy_kwh=(services.attendu_entre(
                    Decimal('12000'), jour, jour) * facteur).quantize(
                        Decimal('0.01')))

    def test_remplacement_ferme_et_repart(self):
        t1 = self._remplacer_onduleur()
        self._releves_apres(Decimal('0.4'))
        res = services.evaluate_underperformance(
            self.inst, today=self.today + timedelta(days=30))
        self.assertTrue(res['underperforming'])
        neuf = UnderperformanceFlag.objects.get(
            installation=self.inst, is_open=True)
        self.assertIsNotNone(neuf.ticket_id)
        self.assertNotEqual(neuf.ticket_id, t1.pk)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(installation=self.inst).count(),
            2)

    def test_remplacement_puis_releves_sains(self):
        self._remplacer_onduleur()
        self._releves_apres(Decimal('1'))
        res = services.evaluate_underperformance(
            self.inst, today=self.today + timedelta(days=30))
        self.assertFalse(res['underperforming'])
        self.assertFalse(UnderperformanceFlag.objects.filter(
            installation=self.inst, is_open=True).exists())

    def test_ouverture_notifie_les_responsables_une_fois(self):
        """AMON87 — une notification à l'ouverture d'un épisode, aucune à la
        réévaluation du même épisode (module test : `tests.py` à 2 000 l.)."""
        from django.contrib.auth import get_user_model

        from apps.notifications.models import Notification
        get_user_model().objects.create_user(
            username='amon87_resp', password='x', role_legacy='responsable',
            company=self.company)
        UnderperformanceFlag.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            services.evaluate_underperformance(self.inst, today=self.today)
        with self.captureOnCommitCallbacks(execute=True):
            services.evaluate_underperformance(self.inst, today=self.today)
        notifs = Notification.objects.filter(
            company=self.company, event_type='monitoring_sous_performance')
        self.assertEqual(notifs.count(), 1)
        self.assertIn('CHT-ASAV70', notifs.first().title)

    def test_nouvel_episode(self):
        ProductionReading.objects.filter(installation=self.inst).delete()
        services.evaluate_underperformance(self.inst, today=self.today)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 0)
        for i in range(30):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=self.today - timedelta(days=i), period_days=1,
                energy_kwh=Decimal('5'))
        services.evaluate_underperformance(self.inst, today=self.today)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(is_open=True).count(), 1)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(installation=self.inst).count(),
            2)

    def test_classer_drapeau_par_le_personnel(self):
        """AMON24 — liste des drapeaux (tout rôle) et classement par le
        personnel : motif obligatoire, auteur tracé, sortie des compteurs."""
        import json
        from pathlib import Path

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.monitoring.selectors import (
            underperformance_flags_client_portail,
        )
        User = get_user_model()

        def api_de(username, role, company):
            api = APIClient()
            api.force_authenticate(User.objects.create_user(
                username=username, password='x', role_legacy=role,
                company=company))
            return api
        resp = api_de('amon24_resp', 'responsable', self.company)
        commercial = api_de('amon24_com', 'commercial', self.company)
        autre_co, _ = Company.objects.get_or_create(
            slug='amon24-b', defaults={'nom': 'AMON24 B'})
        autre = api_de('amon24_b', 'admin', autre_co)
        url = '/api/django/monitoring/drapeaux/'
        drapeau = self._drapeau()

        lst = commercial.get(url, {'is_open': 'true'})
        self.assertEqual(lst.status_code, 200, lst.data)
        contrat = json.loads((Path(__file__).resolve().parent
                              / 'contract_samples'
                              / 'drapeaux_sous_performance.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(lst.data['results'][0]),
                         set(contrat['exemple']['results'][0]))
        self.assertEqual(lst.data['results'][0]['reference'], 'CHT-ASAV70')
        classer = f'{url}{drapeau.id}/classer/'
        self.assertEqual(commercial.post(
            classer, {'motif': 'x'}, format='json').status_code, 403)
        self.assertEqual(autre.post(
            classer, {'motif': 'x'}, format='json').status_code, 404)
        r = resp.post(classer, {'motif': '  '}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('motif', r.data)

        r = resp.post(classer, {'motif': 'Relevés en retard'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data),
                         set(contrat['exemple_classement']['reponse']))
        drapeau.refresh_from_db()
        self.assertFalse(drapeau.is_open)
        self.assertEqual(drapeau.motif_cloture, 'classe_manuellement')
        self.assertEqual(drapeau.note_cloture, 'Relevés en retard')
        self.assertEqual(drapeau.cloture_par.username, 'amon24_resp')
        self.assertEqual(
            fleet_overview(self.company, today=self.today)['open_alerts'], 0)
        self.assertFalse(underperformance_flags_client_portail(
            self.company, self.inst.client_id).exists())
        self.assertEqual(resp.post(
            classer, {'motif': 'encore'}, format='json').status_code, 409)
        self.assertEqual(commercial.get(
            url, {'is_open': 'true'}).data['count'], 0)
