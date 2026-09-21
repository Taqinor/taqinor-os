"""CAD92 — la durée DÉCLARÉE au registre CNDP et la politique appliquée.

Audit L3 du 21/09/2026, section CAD-I. Le traitement seedé ``leads_clients``
déclare « 3 ans après le dernier contact (prospects) » alors que ``crm``
n'enregistrait au registre de rétention partagé que la purge des
``WebsiteLeadPayload``, celle des ``ChatSessionPublique`` et l'archivage du
chatter (OFF par défaut) : AUCUNE anonymisation du Lead lui-même. Déclarer
une durée qu'on n'applique nulle part est exactement ce qu'un contrôle
compare — et c'est un écart de CODE, vérifiable.

LE test de ce fichier est le premier : il relit la DÉCLARATION seedée, en
extrait la durée, et échoue si elle s'écarte de la fenêtre de la politique.
Les autres verrouillent ce que le balayage ne doit jamais faire : toucher un
lead devenu client, repasser sur une fiche déjà anonymisée, ou détruire quoi
que ce soit tant que le fondateur n'a pas armé l'interrupteur.
"""
import datetime
import re

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from core.management.commands.seed_registre_traitements import TRAITEMENTS
from core.retention import list_retention_policies

from apps.crm import dsr_provider, stages
from apps.crm.models import Client, Lead, LeadActivity
from apps.parametres.models import CompanyProfile


def _declaration_leads_clients():
    for traitement in TRAITEMENTS:
        if traitement['code'] == 'leads_clients':
            return traitement
    raise AssertionError(
        "Le traitement « leads_clients » a disparu du seed du registre CNDP.")


class DeclarationEtPolitiqueTests(SimpleTestCase):
    """LE test de CAD92 : les deux doivent dire la même chose."""

    def test_la_duree_declaree_est_celle_de_la_politique(self):
        declaree = _declaration_leads_clients()['duree_conservation']
        trouve = re.search(r'(\d+)\s*ans?\s*après le dernier contact',
                           declaree)
        self.assertIsNotNone(
            trouve,
            "La déclaration CNDP ne dit plus « N ans après le dernier "
            f"contact » : {declaree!r}. Si la durée change, la politique de "
            "rétention doit changer avec elle (dsr_provider."
            "DUREE_CONSERVATION_PROSPECTS_ANS).")
        self.assertEqual(
            int(trouve.group(1)),
            dsr_provider.DUREE_CONSERVATION_PROSPECTS_ANS,
            "La durée DÉCLARÉE au registre CNDP et la fenêtre APPLIQUÉE par "
            "la politique de rétention divergent.")

    def test_la_declaration_vise_bien_les_prospects_et_pas_les_clients(self):
        """La politique exclut les clients : la déclaration doit le dire."""
        declaree = _declaration_leads_clients()['duree_conservation']
        self.assertIn('prospects', declaree)
        self.assertIn('clients', declaree)

    def test_la_politique_est_enregistree_au_registre_partage(self):
        self.assertIn(dsr_provider.RETENTION_POLICY_PROSPECTS,
                      list_retention_policies())


class BalayageTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='cad92', defaults={'nom': 'cad92'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.now = timezone.now()
        self.vieux = self.now - datetime.timedelta(
            days=dsr_provider.DUREE_CONSERVATION_PROSPECTS_JOURS + 30)

    def _lead(self, nom, *, cree_le=None, **extra):
        lead = Lead.objects.create(
            company=self.company, nom=nom, stage=stages.NEW, **extra)
        if cree_le is not None:
            Lead.objects.filter(pk=lead.pk).update(date_creation=cree_le)
            lead.refresh_from_db(fields=['date_creation'])
        return lead

    def test_un_prospect_hors_duree_est_compte(self):
        self._lead('Vieux prospect', cree_le=self.vieux,
                   telephone='0600000021')
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now), 1)

    def test_un_prospect_dans_la_duree_nest_pas_compte(self):
        self._lead('Prospect récent', telephone='0600000022')
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now), 0)

    def test_le_dernier_contact_prime_sur_la_date_de_creation(self):
        """Un vieux lead rappelé le mois dernier n'est pas hors durée."""
        lead = self._lead('Rappelé', cree_le=self.vieux,
                          telephone='0600000023')
        activite = LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.APPEL,
            body='Appel récent.')
        LeadActivity.objects.filter(pk=activite.pk).update(
            created_at=self.now - datetime.timedelta(days=30))
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now), 0)

    def test_un_lead_devenu_client_est_epargne(self):
        """La déclaration leur oppose la durée légale COMPTABLE, pas 3 ans."""
        client = Client.objects.create(company=self.company, nom='Client')
        self._lead('Ancien prospect signé', cree_le=self.vieux,
                   telephone='0600000024', client=client)
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now), 0)

    def test_un_lead_signe_est_epargne(self):
        lead = self._lead('Signé', cree_le=self.vieux,
                          telephone='0600000025')
        Lead.objects.filter(pk=lead.pk).update(stage=stages.SIGNED)
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now), 0)

    def test_une_fiche_deja_anonymisee_nest_pas_repassee(self):
        self._lead(dsr_provider.LEAD_NOM_ANONYMISE, cree_le=self.vieux)
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now), 0)

    def test_rien_nest_detruit_tant_que_linterrupteur_est_ferme(self):
        """Comportement d'aujourd'hui par défaut : on compte, on n'écrit pas."""
        lead = self._lead('Vieux prospect', cree_le=self.vieux,
                          telephone='0600000026')
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now, apply_=True), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.telephone, '0600000026')
        self.assertNotEqual(lead.nom, dsr_provider.LEAD_NOM_ANONYMISE)

    @override_settings(CRM_LEAD_RETENTION_ACTIF=True)
    def test_arme_et_applique_le_balayage_anonymise(self):
        lead = self._lead('Vieux prospect', cree_le=self.vieux,
                          telephone='0600000027', email='vieux@example.ma')
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now, apply_=True), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.nom, dsr_provider.LEAD_NOM_ANONYMISE)
        self.assertIsNone(lead.telephone)
        self.assertIsNone(lead.email)
        # QW10 — les colonnes de dédup normalisées partent avec les PII.
        self.assertFalse(lead.phone_normalise)
        self.assertFalse(lead.email_normalise)

    @override_settings(CRM_LEAD_RETENTION_ACTIF=True)
    def test_le_mode_dry_run_narme_rien(self):
        lead = self._lead('Vieux prospect', cree_le=self.vieux,
                          telephone='0600000028')
        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now, apply_=False), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.telephone, '0600000028')

    @override_settings(CRM_LEAD_RETENTION_ACTIF=True)
    def test_isolation_entre_societes(self):
        """Chaque lead est anonymisé au nom de SA société, jamais d'une autre."""
        autre, _ = Company.objects.get_or_create(
            slug='cad92-autre', defaults={'nom': 'cad92-autre'})
        CompanyProfile.objects.get_or_create(company=autre)
        voisin = Lead.objects.create(
            company=autre, nom='Voisin', telephone='0600000029',
            stage=stages.NEW)
        Lead.objects.filter(pk=voisin.pk).update(date_creation=self.vieux)
        mien = self._lead('Mien', cree_le=self.vieux, telephone='0600000030')

        self.assertEqual(
            dsr_provider.sweep_retention_prospects(self.now, apply_=True), 2)
        voisin.refresh_from_db()
        mien.refresh_from_db()
        self.assertEqual(voisin.company_id, autre.id)
        self.assertEqual(mien.company_id, self.company.id)
        self.assertIsNone(voisin.telephone)
        self.assertIsNone(mien.telephone)
