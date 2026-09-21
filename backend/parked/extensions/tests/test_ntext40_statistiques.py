"""NTEXT40 — statistiques d'usage de la plateforme (cockpit admin).

``GET extensions/statistiques/`` renvoie, PAR SOCIÉTÉ, un tableau chiffré de ce
que la plateforme fait tourner : objets custom + enregistrements, règles
actives + runs 30 j (succès/échec), rapports + abonnements, packages installés.
Read-only : aucune écriture, aucun nouveau modèle.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)
from apps.customfields.models import (
    CustomFieldDef, CustomObjectDef, CustomRecord,
)
from apps.extensions.models import ExtensionInstall, ExtensionPackage
from apps.reporting.models import RapportAbonnement, RapportDefinition

User = get_user_model()

URL = '/api/django/extensions/statistiques/'


class StatistiquesPlateformeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT40 Co')
        self.autre = Company.objects.create(nom='NTEXT40 Autre')
        self.admin = User.objects.create_user(
            username='ntext40_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

        # ── Objets personnalisés ───────────────────────────────────────────
        objet = CustomObjectDef.objects.create(
            company=self.company, code='visites', libelle='Visites')
        CustomObjectDef.objects.create(
            company=self.company, code='cles', libelle='Clés', actif=False)
        CustomFieldDef.objects.create(
            company=self.company, module=objet.field_module, code='lieu',
            libelle='Lieu', type='text')
        CustomRecord.objects.create(
            company=self.company, objet=objet, data={'lieu': 'Casa'})
        CustomRecord.objects.create(
            company=self.company, objet=objet, data={'lieu': 'Rabat'})

        # ── Automatisations ────────────────────────────────────────────────
        self.regle = AutomationRule.objects.create(
            company=self.company, nom='Relance', enabled=True,
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SET_FIELD, action_config={})
        AutomationRule.objects.create(
            company=self.company, nom='Dormante', enabled=False,
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SET_FIELD, action_config={})
        AutomationRun.objects.create(
            company=self.company, rule=self.regle,
            status=AutomationRun.Status.SUCCESS)
        AutomationRun.objects.create(
            company=self.company, rule=self.regle,
            status=AutomationRun.Status.FAILED)
        vieux = AutomationRun.objects.create(
            company=self.company, rule=self.regle,
            status=AutomationRun.Status.SUCCESS)
        AutomationRun.objects.filter(pk=vieux.pk).update(
            timestamp=timezone.now() - timedelta(days=60))

        # ── Rapports ───────────────────────────────────────────────────────
        rapport = RapportDefinition.objects.create(
            company=self.company, titre='CA', dataset='vitals', spec={})
        RapportAbonnement.objects.create(
            company=self.company, rapport_def=rapport, cron='0 8 * * 1')

        # ── Packages ───────────────────────────────────────────────────────
        package = ExtensionPackage.objects.create(
            code='ntext40-pack', nom='Pack NTEXT40')
        ExtensionInstall.objects.create(
            company=self.company, package=package, statut='installe')

        # ── Bruit d'une AUTRE société (jamais compté) ──────────────────────
        CustomObjectDef.objects.create(
            company=self.autre, code='hors', libelle='Hors société')
        AutomationRule.objects.create(
            company=self.autre, nom='Hors', enabled=True,
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SET_FIELD, action_config={})

    def test_tableau_de_bord_chiffre(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        data = res.data

        self.assertEqual(data['fenetre_jours'], 30)

        objets = data['objets_personnalises']
        self.assertEqual(objets['total'], 2)
        self.assertEqual(objets['actifs'], 1)
        self.assertEqual(objets['champs'], 1)
        self.assertEqual(objets['enregistrements'], 2)

        auto = data['automatisations']
        self.assertEqual(auto['regles'], 2)
        self.assertEqual(auto['regles_actives'], 1)
        # Le run de 60 jours est hors fenêtre.
        self.assertEqual(auto['runs_30j'], 2)
        self.assertEqual(auto['runs_30j_succes'], 1)
        self.assertEqual(auto['runs_30j_echecs'], 1)

        rapports = data['rapports']
        self.assertEqual(rapports['definitions'], 1)
        self.assertEqual(rapports['abonnements'], 1)
        self.assertEqual(rapports['abonnements_actifs'], 1)

        self.assertEqual(data['extensions']['packages_installes'], 1)

    def test_lecture_seule_aucune_ecriture(self):
        avant = (CustomRecord.objects.count(), AutomationRun.objects.count(),
                 ExtensionInstall.objects.count())
        self.api.get(URL)
        self.assertEqual(
            (CustomRecord.objects.count(), AutomationRun.objects.count(),
             ExtensionInstall.objects.count()), avant)

    def test_reserve_au_palier_admin_responsable(self):
        commercial = User.objects.create_user(
            username='ntext40_com', password='x', role_legacy='normal',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(commercial)}')
        self.assertEqual(api.get(URL).status_code, 403)
