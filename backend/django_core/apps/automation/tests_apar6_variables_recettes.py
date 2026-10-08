"""APAR6 — les e-mails des recettes d'automatisation sont lisibles par le client.

Constat C-APAR-006 : les préréglages/recettes écrivent ``{client_nom}``,
``{reference}`` mais aucun émetteur ne fournit ces clés ; le sujet n'était
jamais substitué (« Facture en retard – {reference} ») et la signature
« L'équipe Taqinor » partait chez tous les tenants. Désormais UN résolveur
(``actions.rendre_texte``) part de l'INSTANCE déclencheuse ; une variable non
résoluble fait SKIPPED, jamais un envoi avec accolades.

Test-du-test : retirer le rendu du sujet dans ``actions._send_email`` ⇒
``test_sujet_substitue`` rouge.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase

from apps.automation import actions, engine
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)
from apps.automation.templates import AUTOMATION_TEMPLATES, CATALOGUE_MODELES
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, Facture
from authentication.models import Company

CLES_TEXTE = ('subject', 'body', 'description', 'message')


def _actions_de(modele):
    if modele.get('steps'):
        return [(s['action_type'], s.get('action_config') or {})
                for s in modele['steps']]
    return [(modele['action_type'], modele.get('action_config') or {})]


class VariablesRecettesTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar6-co', defaults={'nom': 'APAR6 SARL'})
        self.cli = Client.objects.create(
            company=self.co, nom='Alaoui', prenom='Karim',
            email='k.alaoui@example.invalid')

    def _instance(self, trigger_type):
        self.n = getattr(self, 'n', 0) + 1
        n = self.n
        if trigger_type in ('devis_accepted', 'date_echeance_champ'):
            return Devis.objects.create(
                company=self.co, client=self.cli, reference=f'DEV-APAR6-{n}',
                statut='envoye', date_validite=date.today())
        if trigger_type == 'facture_overdue':
            return Facture.objects.create(
                company=self.co, client=self.cli, reference='FAC-APAR6',
                statut='emise', montant_ttc=Decimal('500'),
                date_echeance=date.today() - timedelta(days=10))
        if trigger_type == 'lead_stage_change':
            return Lead.objects.create(
                company=self.co, nom='Bennani', prenom='Sara', stage='NEW',
                email=f's.bennani{n}@example.invalid')
        if trigger_type == 'warranty_expiring':
            from apps.installations.models import Installation
            from apps.sav.models import Equipement
            from apps.stock.models import Produit
            chantier = Installation.objects.create(
                company=self.co, client=self.cli, reference=f'CH-APAR6-{n}')
            produit = Produit.objects.create(
                company=self.co, nom=f'Onduleur APAR6 {n}', prix_vente=0)
            return Equipement.objects.create(
                company=self.co, produit=produit, installation=chantier,
                numero_serie=f'SN-APAR6-{n}',
                statut=Equipement.Statut.EN_SERVICE,
                date_fin_garantie=date.today() + timedelta(days=30))
        if trigger_type == 'maintenance_due':
            from apps.sav.models import ContratMaintenance
            return ContratMaintenance.objects.create(
                company=self.co, client=self.cli, actif=True,
                date_debut=date.today() - timedelta(days=400),
                periodicite='annuel')
        if trigger_type == 'stock_below_threshold':
            from apps.stock.models import Produit
            return Produit.objects.create(
                company=self.co, nom=f'Câble APAR6 {n}', prix_vente=0)
        raise AssertionError(f'déclencheur sans instance de test : {trigger_type}')

    def test_chaque_recette_se_rend_sans_accolade(self):
        for modele in list(AUTOMATION_TEMPLATES) + list(CATALOGUE_MODELES):
            nom = modele.get('id') or modele.get('code')
            instance = self._instance(modele['trigger_type'])
            for _action, cfg in _actions_de(modele):
                for cle in CLES_TEXTE:
                    texte = cfg.get(cle)
                    if not texte:
                        continue
                    with self.subTest(recette=nom, cle=cle):
                        rendu, manquantes = actions.rendre_texte(
                            texte, instance, self.co, {})
                        self.assertEqual(manquantes, [])
                        self.assertNotIn('{', rendu)
                        self.assertNotIn('Taqinor', rendu)

    def test_sujet_substitue(self):
        preset = next(t for t in AUTOMATION_TEMPLATES
                      if t['id'] == 'email_on_facture_overdue')
        facture = self._instance('facture_overdue')
        regle = AutomationRule.objects.create(
            company=self.co, nom='Relance', enabled=True,
            trigger_type=TriggerType.FACTURE_OVERDUE, trigger_config={},
            action_type=ActionType.SEND_EMAIL,
            action_config=preset['action_config'])
        mail.outbox = []
        # APAR10 — l'e-mail part (et se journalise) au COMMIT.
        with self.captureOnCommitCallbacks(execute=True):
            engine.run_action(regle, facture, self.co)
        self.assertEqual(len(mail.outbox), 1)
        envoi = mail.outbox[0]
        self.assertEqual(envoi.subject, 'Facture en retard – FAC-APAR6')
        self.assertIn('Bonjour Karim Alaoui', envoi.body)
        self.assertIn('Votre facture FAC-APAR6', envoi.body)
        self.assertIn("L'équipe APAR6 SARL", envoi.body)
        self.assertNotIn('{', envoi.subject + envoi.body)
        run = AutomationRun.objects.get(rule=regle)
        self.assertEqual(run.status, AutomationRun.Status.SUCCESS)

    def test_variable_inconnue_skipped(self):
        devis = self._instance('devis_accepted')
        regle = AutomationRule.objects.create(
            company=self.co, nom='Inconnue', enabled=True,
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL,
            action_config={'subject': 'Devis {reference}',
                           'body': 'Bonjour {inconnue}'})
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            engine.run_action(regle, devis, self.co)
        self.assertEqual(len(mail.outbox), 0)
        run = AutomationRun.objects.get(rule=regle)
        self.assertEqual(run.status, AutomationRun.Status.SKIPPED)
        self.assertIn('{inconnue}', run.message)
