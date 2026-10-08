"""APAR25 — pour chaque recette, simulation == exécution.

Constat C-APAR-033 : ``_send_whatsapp`` rendait SUCCESS sans aucun effet
observable (lien seulement journalisé) et lisait un corps vide (clé
``message`` des préréglages ignorée) ; ``CREATE_ACTIVITY`` sur un produit ou
un contrat NOOPait alors que la simulation annonçait « Une activité serait
créée. » ; un SMS simulé « partirait » mais NOOPait ; le client d'un
équipement n'était jamais résolu (ticket SAV préventif jamais créé).

Contrat testé : chaque effet de simulation porte ``statut_prevu`` ; il est
ÉGAL au statut du run réellement journalisé, recette par recette.

Test-du-test : remettre « Une activité serait créée. » inconditionnel dans
``simulation._decrire_activite`` (sans ``statut_prevu`` dérivé) ⇒ rouge.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.automation import actions, engine
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, AutomationStep, TriggerType,
)
from apps.automation.simulation import simuler_regle
from apps.automation.templates import AUTOMATION_TEMPLATES, CATALOGUE_MODELES
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, Facture
from authentication.models import Company


def _actions_de(modele):
    if modele.get('steps'):
        return [(s['action_type'], s.get('action_config') or {})
                for s in modele['steps']]
    return [(modele['action_type'], modele.get('action_config') or {})]


class SimulationEgaleExecutionTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar25-co', defaults={'nom': 'APAR25'})
        self.n = 0

    def _client(self):
        self.n += 1
        return Client.objects.create(
            company=self.co, nom=f'Client{self.n}', prenom='Test',
            email=f'apar25-{self.n}@example.invalid',
            telephone='+212612345678')

    def _instance(self, trigger_type):
        self.n += 1
        n = self.n
        if trigger_type in ('devis_accepted', 'date_echeance_champ'):
            return Devis.objects.create(
                company=self.co, client=self._client(),
                reference=f'DEV-APAR25-{n}', statut='envoye',
                date_validite=date.today())
        if trigger_type == 'facture_overdue':
            return Facture.objects.create(
                company=self.co, client=self._client(),
                reference=f'FAC-APAR25-{n}', statut='emise',
                montant_ttc=Decimal('100'),
                date_echeance=date.today() - timedelta(days=5))
        if trigger_type == 'lead_stage_change':
            return Lead.objects.create(
                company=self.co, nom=f'Lead{n}', stage='NEW',
                email=f'lead-apar25-{n}@example.invalid')
        if trigger_type == 'warranty_expiring':
            from apps.installations.models import Installation
            from apps.sav.models import Equipement
            from apps.stock.models import Produit
            chantier = Installation.objects.create(
                company=self.co, client=self._client(),
                reference=f'CH-APAR25-{n}')
            produit = Produit.objects.create(
                company=self.co, nom=f'Onduleur {n}', prix_vente=0)
            return Equipement.objects.create(
                company=self.co, produit=produit, installation=chantier,
                numero_serie=f'SN-APAR25-{n}',
                statut=Equipement.Statut.EN_SERVICE,
                date_fin_garantie=date.today() + timedelta(days=30))
        if trigger_type == 'maintenance_due':
            from apps.sav.models import ContratMaintenance
            return ContratMaintenance.objects.create(
                company=self.co, client=self._client(), actif=True,
                date_debut=date.today() - timedelta(days=400),
                periodicite='annuel')
        if trigger_type == 'stock_below_threshold':
            from apps.stock.models import Produit
            return Produit.objects.create(
                company=self.co, nom=f'Câble {n}', prix_vente=0)
        raise AssertionError(f'déclencheur sans instance : {trigger_type}')

    def _regle(self, modele, liste):
        premiere_type, premiere_cfg = liste[0]
        regle = AutomationRule.objects.create(
            company=self.co, nom=modele.get('nom', 'r'),
            trigger_type=modele['trigger_type'],
            trigger_config=modele.get('trigger_config') or {},
            action_type=premiere_type, action_config=premiere_cfg,
            enabled=False)
        if modele.get('steps'):
            for i, (action_type, cfg) in enumerate(liste, start=1):
                AutomationStep.objects.create(
                    rule=regle, ordre=i, action_type=action_type,
                    action_config=cfg)
        return regle

    def test_chaque_recette_simulation_egale_execution(self):
        for modele in list(AUTOMATION_TEMPLATES) + list(CATALOGUE_MODELES):
            nom = modele.get('id') or modele.get('code')
            with self.subTest(recette=nom):
                liste = _actions_de(modele)
                instance = self._instance(modele['trigger_type'])
                regle = self._regle(modele, liste)
                effets = simuler_regle(regle, instance, self.co,
                                       journaliser=False)
                with self.captureOnCommitCallbacks(execute=True):
                    engine.run_action(regle, instance, self.co)
                runs = list(AutomationRun.objects.filter(rule=regle)
                            .order_by('id').values_list('status', flat=True))
                self.assertEqual(
                    [e.get('statut_prevu') for e in effets], runs)

    def test_whatsapp_tache_persistee_avec_le_lien(self):
        from apps.records.models import Activity
        preset = next(t for t in AUTOMATION_TEMPLATES
                      if t['id'] == 'whatsapp_on_devis_accepte')
        devis = self._instance('devis_accepted')
        regle = AutomationRule.objects.create(
            company=self.co, nom='WA', trigger_type=TriggerType.DEVIS_ACCEPTED,
            trigger_config={}, action_type=ActionType.SEND_WHATSAPP,
            action_config=preset['action_config'])
        status, _ = engine.run_action(regle, devis, self.co)
        self.assertEqual(status, AutomationRun.Status.SUCCESS)
        tache = Activity.objects.get(
            content_type=ContentType.objects.get_for_model(Devis),
            object_id=devis.pk, summary=actions.RESUME_TACHE_WHATSAPP)
        self.assertIn('wa.me', tache.note)
        self.assertIn('Merci de votre confiance', tache.note)  # corps lu

    def test_sms_simulation_egale_execution_et_creation_refusee(self):
        devis = self._instance('devis_accepted')
        regle = AutomationRule.objects.create(
            company=self.co, nom='SMS', trigger_type=TriggerType.DEVIS_ACCEPTED,
            trigger_config={}, action_type=ActionType.SEND_SMS,
            action_config={'body': 'x'})
        effets = simuler_regle(regle, devis, self.co, journaliser=False)
        status, _ = engine.run_action(regle, devis, self.co)
        self.assertEqual(effets[0]['statut_prevu'], status)
        self.assertEqual(status, AutomationRun.Status.NOOP)
        from apps.automation.serializers import AutomationRuleSerializer
        ser = AutomationRuleSerializer(data={
            'nom': 'SMS', 'trigger_type': TriggerType.DEVIS_ACCEPTED,
            'action_type': ActionType.SEND_SMS, 'action_config': {}})
        self.assertFalse(ser.is_valid())
        self.assertIn('action_type', ser.errors)

    def test_client_d_un_equipement_resolu(self):
        equipement = self._instance('warranty_expiring')
        self.assertEqual(actions._resolve_client(equipement),
                         equipement.installation.client)
