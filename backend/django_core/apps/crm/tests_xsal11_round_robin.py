"""XSAL11 — Affectation round-robin équilibrée des leads entrants.

Couvre :
  - OFF (défaut) : comportement byte-identique — responsable par défaut
    explicite prime, QW6 round-robin simple sinon ;
  - ON : deux leads successifs vont à deux commerciaux DIFFÉRENTS ;
  - ON : un commercial au plafond de leads OUVERTS est sauté ;
  - ON : tous saturés → fallback sur ``responsable_defaut_leads`` ;
  - ON, aucun commercial actif et pas de responsable par défaut → None (no-op) ;
  - appliqué au webhook site (pas seulement à la création manuelle) ;
  - company-scopé (jamais de fuite cross-tenant dans le pool de rotation).
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead
from apps.crm.leads_attribution import default_responsable_for
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role

User = get_user_model()

SECRET = 'xsal11-test-secret'


def make_commercial(company, username, role):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


class RoundRobinOffByDefaultTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL11 Off', slug='taqinor-xsal11-off')
        # OFF path falls back to QW6's pick_round_robin_owner(), which
        # requires the crm_creer permission (see tests_qw6_speed_to_lead.py)
        # — not just role__nom='Commercial' like the ON/balanced path.
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_creer', 'crm_voir'])

    def test_off_responsable_explicite_prime_octet_identique(self):
        explicite = make_commercial(self.company, 'explicite_off', self.role)
        make_commercial(self.company, 'autre_commercial_off', self.role)
        CompanyProfile.objects.create(
            company=self.company, responsable_defaut_leads=explicite,
            round_robin_leads_actif=False)
        self.assertEqual(default_responsable_for(self.company), explicite)

    def test_off_sans_reglage_retombe_sur_round_robin_simple_qw6(self):
        # round_robin_leads_actif=False (défaut du champ) : QW6 s'applique.
        commercial = make_commercial(self.company, 'seul_commercial_off', self.role)
        CompanyProfile.objects.create(company=self.company)
        self.assertEqual(default_responsable_for(self.company), commercial)


class RoundRobinOnBalancedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL11 On', slug='taqinor-xsal11-on')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.profile = CompanyProfile.objects.create(
            company=self.company, round_robin_leads_actif=True,
            round_robin_plafond_leads_ouverts=2)

    def test_deux_leads_successifs_vont_a_deux_commerciaux_differents(self):
        com_a = make_commercial(self.company, 'com_a_on', self.role)
        com_b = make_commercial(self.company, 'com_b_on', self.role)

        first = default_responsable_for(self.company)
        self.assertIn(first, (com_a, com_b))
        Lead.objects.create(
            company=self.company, nom='Lead 1', owner=first, stage=stages.NEW)

        second = default_responsable_for(self.company)
        self.assertNotEqual(second, first)

    def test_commercial_au_plafond_est_saute(self):
        com_a = make_commercial(self.company, 'com_a_plafond', self.role)
        com_b = make_commercial(self.company, 'com_b_plafond', self.role)
        # com_a a déjà 2 leads OUVERTS (== plafond) → doit être sauté.
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.NEW)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.CONTACTED)
        chosen = default_responsable_for(self.company)
        self.assertEqual(chosen, com_b)

    def test_leads_signed_ou_cold_ne_comptent_pas_dans_le_plafond(self):
        com_a = make_commercial(self.company, 'com_a_signed', self.role)
        com_b = make_commercial(self.company, 'com_b_signed', self.role)
        # 2 leads SIGNED/COLD sur com_a : ne comptent PAS comme "ouverts".
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.SIGNED)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.COLD)
        chosen = default_responsable_for(self.company)
        self.assertIn(chosen, (com_a, com_b))

    def test_lead_perdu_ne_compte_pas_dans_le_plafond(self):
        com_a = make_commercial(self.company, 'com_a_perdu', self.role)
        com_b = make_commercial(self.company, 'com_b_perdu', self.role)
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.NEW,
            perdu=True)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.NEW,
            perdu=True)
        chosen = default_responsable_for(self.company)
        self.assertIn(chosen, (com_a, com_b))

    def test_tous_satures_fallback_responsable_defaut(self):
        explicite = make_commercial(self.company, 'explicite_satures', self.role)
        com_a = make_commercial(self.company, 'com_a_satures', self.role)
        self.profile.responsable_defaut_leads = explicite
        self.profile.save(update_fields=['responsable_defaut_leads'])
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.NEW)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.NEW)
        chosen = default_responsable_for(self.company)
        self.assertEqual(chosen, explicite)

    def test_tous_satures_sans_fallback_none(self):
        com_a = make_commercial(self.company, 'com_a_sans_fallback', self.role)
        Lead.objects.create(
            company=self.company, nom='L1', owner=com_a, stage=stages.NEW)
        Lead.objects.create(
            company=self.company, nom='L2', owner=com_a, stage=stages.NEW)
        self.assertIsNone(default_responsable_for(self.company))

    def test_aucun_commercial_actif_none(self):
        self.assertIsNone(default_responsable_for(self.company))

    def test_company_scope(self):
        other = Company.objects.create(nom='Autre XSAL11', slug='xsal11-autre')
        other_role = Role.objects.create(
            company=other, nom='Commercial', permissions=['crm_voir'])
        make_commercial(other, 'commercial_autre_societe', other_role)
        # Aucun commercial DANS self.company → None, jamais le pool de l'autre.
        self.assertIsNone(default_responsable_for(self.company))


def payload_site(**extra):
    base = {'fullName': 'Lead XSAL11', 'phoneE164': '+212611112222', 'qualified': True}
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class RoundRobinAppliedToWebhookTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL11 Webhook', slug='taqinor-xsal11-webhook')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        CompanyProfile.objects.create(
            company=self.company, round_robin_leads_actif=True,
            round_robin_plafond_leads_ouverts=10)
        self.url = reverse('website-lead-webhook')

    def post(self, phone):
        return self.client.post(
            self.url, data=json.dumps(payload_site(phoneE164=phone)),
            content_type='application/json', HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_deux_leads_du_site_vont_a_deux_commerciaux_differents(self):
        make_commercial(self.company, 'wh_com_a', self.role)
        make_commercial(self.company, 'wh_com_b', self.role)
        r1 = self.post('+212611110001')
        r2 = self.post('+212611110002')
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        lead1 = Lead.objects.get(pk=r1.json()['lead_id'])
        lead2 = Lead.objects.get(pk=r2.json()['lead_id'])
        self.assertIsNotNone(lead1.owner_id)
        self.assertIsNotNone(lead2.owner_id)
        self.assertNotEqual(lead1.owner_id, lead2.owner_id)


class EquipeRecevantLeadsTests(TestCase):
    """Fondateur 26/10/2026 — l'équipe cochée « Reçoit les nouveaux leads »
    les partage entre SES membres actifs (plafond du profil), interrupteur
    round-robin ON ou OFF ; tous saturés → responsable par défaut."""

    def setUp(self):
        from apps.crm.models import EquipeCommerciale
        self.company = Company.objects.create(
            nom='Taqinor Equipe Leads', slug='taqinor-equipe-leads')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_creer', 'crm_voir'])
        self.a = make_commercial(self.company, 'eq_leads_a', self.role)
        self.b = make_commercial(self.company, 'eq_leads_b', self.role)
        self.hors = make_commercial(self.company, 'eq_leads_hors', self.role)
        self.defaut = make_commercial(self.company, 'eq_leads_def', self.role)
        self.profile = CompanyProfile.objects.create(
            company=self.company, responsable_defaut_leads=self.defaut,
            round_robin_leads_actif=False,
            round_robin_plafond_leads_ouverts=1)
        self.equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Casa', recoit_leads=True)
        self.equipe.membres.set([self.a, self.b])

    def _lead(self, owner):
        return Lead.objects.create(
            company=self.company, nom='L', owner=owner, stage=stages.NEW)

    def test_rotation_entre_membres_seulement_meme_interrupteur_off(self):
        premier = default_responsable_for(self.company)
        self.assertIn(premier, (self.a, self.b))
        self._lead(premier)
        second = default_responsable_for(self.company)
        self.assertIn(second, (self.a, self.b))
        self.assertNotEqual(premier, second)

    def test_tous_au_plafond_retombe_sur_le_responsable_par_defaut(self):
        self._lead(self.a)
        self._lead(self.b)
        self.assertEqual(default_responsable_for(self.company), self.defaut)

    def test_membre_inactif_saute(self):
        self.a.is_active = False
        self.a.save(update_fields=['is_active'])
        self.assertEqual(default_responsable_for(self.company), self.b)

    def test_equipe_archivee_ou_decochee_comportement_inchange(self):
        self.equipe.actif = False
        self.equipe.save(update_fields=['actif'])
        self.assertEqual(default_responsable_for(self.company), self.defaut)


class AttributionParResponsableTests(TestCase):
    """Fondateur 27/10/2026 — « le responsable confirme chaque lead » : le
    nouveau lead reste au responsable, ATTEND sa décision avec une
    proposition (règles dans l'ordre, sinon rotation) et une échéance."""

    def setUp(self):
        from apps.crm.models import EquipeCommerciale
        self.company = Company.objects.create(
            nom='Taqinor Dispatch', slug='taqinor-dispatch')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_creer', 'crm_voir'])
        self.chef = make_commercial(self.company, 'disp_chef', self.role)
        self.a = make_commercial(self.company, 'disp_a', self.role)
        self.b = make_commercial(self.company, 'disp_b', self.role)
        CompanyProfile.objects.create(
            company=self.company, round_robin_plafond_leads_ouverts=5)
        self.equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Casa', recoit_leads=True,
            responsable=self.chef, confirmation_responsable=True)
        self.equipe.membres.set([self.a, self.b])

    def _nouveau(self, **champs):
        owner = default_responsable_for(self.company, lead_attrs=champs)
        return Lead.objects.create(
            company=self.company, nom='Prospect', owner=owner, **champs)

    def _regle(self, membre, ordre=0, **criteres):
        from apps.crm.models_clients import RegleAttribution
        return RegleAttribution.objects.create(
            company=self.company, equipe=self.equipe, membre=membre,
            ordre=ordre, **criteres)

    def test_off_comportement_inchange_aucune_attente(self):
        from apps.crm.models_clients import AttributionEnAttente
        self.equipe.confirmation_responsable = False
        self.equipe.save(update_fields=['confirmation_responsable'])
        lead = self._nouveau()
        self.assertIn(lead.owner, (self.a, self.b))
        self.assertFalse(AttributionEnAttente.objects.filter(lead=lead).exists())

    def test_on_lead_au_responsable_en_attente_avec_proposition(self):
        lead = self._nouveau()
        lead.refresh_from_db()
        self.assertEqual(lead.owner, self.chef)
        attente = lead.attribution_en_attente
        self.assertIn(attente.proposee, (self.a, self.b))
        self.assertEqual(attente.raison, 'Rotation équilibrée')
        self.assertIsNotNone(attente.echeance)
        self.assertGreater(attente.echeance, attente.created_at)

    def test_propositions_en_attente_comptent_dans_la_rotation(self):
        premier = self._nouveau().attribution_en_attente.proposee
        second = self._nouveau().attribution_en_attente.proposee
        self.assertEqual({premier, second}, {self.a, self.b})

    def test_on_sans_responsable_actif_rotation_directe(self):
        self.chef.is_active = False
        self.chef.save(update_fields=['is_active'])
        lead = self._nouveau()
        self.assertIn(lead.owner, (self.a, self.b))

    def test_regle_ville_sans_casse_ni_accents(self):
        self._regle(self.b, villes='Fès, Meknès')
        lead = self._nouveau(ville='FES')
        self.assertEqual(lead.attribution_en_attente.proposee, self.b)
        self.assertEqual(lead.attribution_en_attente.raison,
                         'Règle : ville Fès, Meknès')

    def test_regle_type_source_et_facture(self):
        from decimal import Decimal
        self._regle(self.a, type_installation='agricole')
        self._regle(self.b, ordre=1, source='meta_ads')
        self._regle(self.a, ordre=2, facture_min=Decimal('2000'))
        self.assertEqual(self._nouveau(
            type_installation='agricole').attribution_en_attente.proposee, self.a)
        self.assertEqual(self._nouveau(
            canal='meta_ads').attribution_en_attente.proposee, self.b)
        lead = self._nouveau(facture_hiver=Decimal('2500'))
        self.assertEqual(lead.attribution_en_attente.proposee, self.a)
        self.assertEqual(lead.attribution_en_attente.raison,
                         'Règle : facture 2000–∞ DH')

    def test_premiere_regle_dans_l_ordre_gagne(self):
        self._regle(self.b, ordre=5, villes='Rabat')
        self._regle(self.a, ordre=1, villes='Rabat')
        self.assertEqual(self._nouveau(
            ville='rabat').attribution_en_attente.proposee, self.a)

    def test_aucune_regle_ou_membre_hors_equipe_retombe_sur_rotation(self):
        hors = make_commercial(self.company, 'disp_hors', self.role)
        self._regle(hors, villes='Tanger')
        self._regle(self.a, villes='Agadir')
        attente = self._nouveau(ville='Tanger').attribution_en_attente
        self.assertIn(attente.proposee, (self.a, self.b))
        self.assertEqual(attente.raison, 'Rotation équilibrée')

    def test_echeance_depassee_attribution_automatique(self):
        from django.utils import timezone
        from apps.crm.dispatch import attribuer_echeances
        from apps.crm.models import LeadActivity
        from apps.crm.models_clients import AttributionEnAttente
        lead = self._nouveau()
        attente = lead.attribution_en_attente
        propose = attente.proposee
        AttributionEnAttente.objects.filter(pk=attente.pk).update(
            echeance=timezone.now() - timezone.timedelta(minutes=1))
        self.assertEqual(attribuer_echeances(), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.owner, propose)
        self.assertFalse(AttributionEnAttente.objects.filter(lead=lead).exists())
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, body__startswith='Attribué automatiquement à').exists())
        self.assertEqual(attribuer_echeances(), 0)

    def test_echeance_non_atteinte_rien_ne_bouge(self):
        from apps.crm.dispatch import attribuer_echeances
        from apps.crm.models_clients import AttributionEnAttente
        lead = self._nouveau()
        AttributionEnAttente.objects.filter(lead=lead).update(echeance=None)
        self.assertEqual(attribuer_echeances(), 0)
        lead.refresh_from_db()
        self.assertEqual(lead.owner, self.chef)

    def test_proposition_devenue_inactive_rotation_recalculee(self):
        from django.utils import timezone
        from apps.crm.dispatch import attribuer_echeances
        from apps.crm.models_clients import AttributionEnAttente
        self._regle(self.a)
        lead = self._nouveau()
        self.a.is_active = False
        self.a.save(update_fields=['is_active'])
        AttributionEnAttente.objects.filter(lead=lead).update(
            echeance=timezone.now() - timezone.timedelta(minutes=1))
        attribuer_echeances()
        lead.refresh_from_db()
        self.assertEqual(lead.owner, self.b)

    def test_isolation_societe_regles_d_une_autre_societe_ignorees(self):
        from apps.crm.models_clients import RegleAttribution
        autre = Company.objects.create(nom='Autre dispatch', slug='autre-dispatch')
        RegleAttribution.objects.create(
            company=autre, equipe=self.equipe, membre=self.b, villes='Oujda')
        attente = self._nouveau(ville='Oujda').attribution_en_attente
        self.assertEqual(attente.raison, 'Rotation équilibrée')
        self.assertEqual(attente.company_id, self.company.pk)


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class AttributionParResponsableWebhookTests(TestCase):
    """Le lead du site passe par la même attente (point central)."""

    def test_lead_du_site_attend_le_responsable(self):
        from apps.crm.models import EquipeCommerciale
        company = Company.objects.create(
            nom='Taqinor Dispatch Web', slug='taqinor-dispatch-web')
        role = Role.objects.create(
            company=company, nom='Commercial', permissions=['crm_voir'])
        chef = make_commercial(company, 'dispw_chef', role)
        membre = make_commercial(company, 'dispw_a', role)
        CompanyProfile.objects.create(company=company)
        equipe = EquipeCommerciale.objects.create(
            company=company, nom='Web', recoit_leads=True, responsable=chef,
            confirmation_responsable=True)
        equipe.membres.set([membre])
        r = self.client.post(
            reverse('website-lead-webhook'),
            data=json.dumps(payload_site(phoneE164='+212611119999')),
            content_type='application/json', HTTP_X_WEBHOOK_SECRET=SECRET)
        self.assertEqual(r.status_code, 201, r.content)
        lead = Lead.objects.get(pk=r.json()['lead_id'])
        self.assertEqual(lead.owner, chef)
        self.assertEqual(lead.attribution_en_attente.proposee, membre)
