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

    def _a(self, jour, h, mi=0):
        import datetime
        from apps.crm import horaires
        return datetime.datetime(2026, 10, jour, h, mi,
                                 tzinfo=horaires.CASABLANCA)

    def _nouveau_a(self, instant, **champs):
        from unittest import mock
        with mock.patch('django.utils.timezone.now', return_value=instant):
            return self._nouveau(**champs)

    def test_responsable_par_defaut_inactif_ignore(self):
        # ACVI14 — ni attribution par défaut, ni saisie d'`owner`, ni lot.
        from rest_framework.test import APIClient

        company = Company.objects.create(nom='ACVI14', slug='acvi14-inactif')
        role = Role.objects.create(
            company=company, nom='Commercial',
            permissions=['crm_creer', 'crm_voir', 'crm_modifier', 'crm_reassign'])
        inactif = make_commercial(company, 'acvi14_u', role)
        actif = make_commercial(company, 'acvi14_k', role)
        get_user_model().objects.filter(pk=inactif.pk).update(is_active=False)
        CompanyProfile.objects.create(
            company=company, responsable_defaut_leads=inactif)

        self.assertEqual(default_responsable_for(company), actif)

        lead = Lead.objects.create(company=company, nom='P', owner=actif)
        api = APIClient()
        api.force_authenticate(actif)
        resp = api.patch(f'/api/django/crm/leads/{lead.pk}/',
                         {'owner': inactif.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['owner'], ['Utilisateur inactif.'])

        resp = api.post('/api/django/crm/leads/bulk/', {
            'action': 'reassign', 'ids': [lead.pk], 'owner': inactif.pk},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            [(s['id'], s['reason']) for s in resp.data['skipped']],
            [(lead.pk, 'Responsable inactif.')])
        lead.refresh_from_db()
        self.assertEqual(lead.owner, actif)

    def test_off_comportement_inchange_aucune_attente(self):
        # En journée (jeudi 29/10/2026, 10 h) : rotation directe.
        from apps.crm.models_clients import AttributionEnAttente
        self.equipe.confirmation_responsable = False
        self.equipe.save(update_fields=['confirmation_responsable'])
        lead = self._nouveau_a(self._a(29, 10))
        self.assertIn(lead.owner, (self.a, self.b))
        self.assertFalse(AttributionEnAttente.objects.filter(lead=lead).exists())

    def test_off_le_soir_attend_le_responsable_jusqu_a_l_ouverture(self):
        # Fondateur 30/10/2026 : le soir rien n'est attribué — le lead attend
        # le responsable et ne part tout seul qu'à 8 h 30 le lendemain.
        self.equipe.confirmation_responsable = False
        self.equipe.save(update_fields=['confirmation_responsable'])
        lead = self._nouveau_a(self._a(29, 22))
        lead.refresh_from_db()
        self.assertEqual(lead.owner, self.chef)
        attente = lead.attribution_en_attente
        self.assertIn(attente.proposee, (self.a, self.b))
        self.assertEqual(attente.echeance, self._a(30, 8, 30))

    def test_on_la_nuit_echeance_a_l_ouverture_pile(self):
        lead = self._nouveau_a(self._a(30, 4, 35))
        self.assertEqual(lead.attribution_en_attente.echeance,
                         self._a(30, 8, 30))

    def test_on_en_journee_echeance_apres_le_delai(self):
        lead = self._nouveau_a(self._a(29, 10))
        self.assertEqual(lead.attribution_en_attente.echeance,
                         self._a(29, 10, 5))

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

    def test_la_file_a_prendre_se_prend_une_seule_fois(self):
        # CADV31 (D-CADV-7) : équipe en file « À prendre » (sans confirmation) —
        # un nouveau lead résidentiel attend, tout membre actif se l'attribue,
        # le second reçoit 409 ; un membre ne s'attribue qu'à lui-même ; le
        # lead industriel va au responsable pro sans entrer dans la file.
        from rest_framework.exceptions import PermissionDenied
        from apps.crm import dispatch
        from apps.crm.models import LeadActivity
        from apps.crm.models_clients import AttributionEnAttente
        from core.conflit_etat import ConflitEtat
        self.equipe.confirmation_responsable = False
        self.equipe.file_a_prendre = True
        self.equipe.save(update_fields=['confirmation_responsable',
                                        'file_a_prendre'])
        pro = make_commercial(self.company, 'disp_pro', self.role)
        profil = CompanyProfile.objects.get(company=self.company)
        profil.responsable_leads_pro = pro
        profil.save()
        lead = self._nouveau_a(self._a(29, 10), type_installation='residentiel')
        industriel = self._nouveau_a(self._a(29, 10),
                                     type_installation='industriel')
        industriel.refresh_from_db()
        self.assertEqual(industriel.owner, pro)
        self.assertFalse(
            AttributionEnAttente.objects.filter(lead=industriel).exists())
        self.assertTrue(AttributionEnAttente.objects.filter(lead=lead).exists())
        # La file est listée aux trois membres (responsable compris).
        for user in (self.chef, self.a, self.b):
            fichier = dispatch.file_attente(user)
            self.assertEqual(fichier['en_attente'], 1, user.username)
            self.assertTrue(fichier['equipe']['a_prendre'])
        # Un membre ne s'attribue qu'à lui-même.
        with self.assertRaises(PermissionDenied):
            dispatch.attribuer(self.a, lead.pk, self.b.pk)
        dispatch.attribuer(self.a, lead.pk, self.a.pk)
        lead.refresh_from_db()
        self.assertEqual(lead.owner, self.a)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, body=f'Pris par {dispatch.nom_affiche(self.a)}').exists())
        with self.assertRaises(ConflitEtat):
            dispatch.attribuer(self.b, lead.pk, self.b.pk)
        lead.refresh_from_db()
        self.assertEqual(lead.owner, self.a)

    def test_escalade_de_la_file_requetes_constantes(self):
        # ACVI83 — même coût à 4 et à 12 attentes dont les paliers sont posés.
        from unittest import mock
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.crm import dispatch
        from apps.crm.models import LeadActivity
        self.equipe.confirmation_responsable = False
        self.equipe.file_a_prendre = True
        self.equipe.save(update_fields=['confirmation_responsable',
                                        'file_a_prendre'])

        def creer(nombre):
            for _ in range(nombre):
                lead = self._nouveau_a(self._a(26, 10, 2),
                                       type_installation='residentiel')
                for _m, _p, marqueur in dispatch.PALIERS_FILE:
                    LeadActivity.objects.create(
                        company=self.company, lead=lead,
                        kind=LeadActivity.Kind.NOTE, body=f'{marqueur} — posé')

        def passage():
            with mock.patch('apps.notifications.services.notify_many',
                            return_value=[]) as envoi:
                with CaptureQueriesContext(connection) as ctx:
                    n = dispatch.escalader_file(self._a(29, 12, 0))
            self.assertEqual((n, envoi.call_count), (0, 0))
            return len(ctx)

        creer(4)
        a_quatre = passage()
        creer(8)
        self.assertEqual(passage(), a_quatre)

    def test_les_paliers_de_la_file_notifient_une_fois_et_attribuent_a_t30(self):
        # CADV115 : lead résidentiel arrivé à 10:02 jamais pris — T+5 prévient
        # l'équipe, T+15 la direction (PREMIER_CONTACT_DEPASSE), T+30 attribue
        # au membre le moins chargé ; un passage répété n'envoie rien.
        from unittest import mock
        from apps.crm import dispatch
        from apps.crm.models import LeadActivity
        from apps.notifications.types_evenements import EventType
        self.equipe.confirmation_responsable = False
        self.equipe.file_a_prendre = True
        self.equipe.save(update_fields=['confirmation_responsable',
                                        'file_a_prendre'])
        reda = User.objects.create_user(
            username='disp_reda', password='x', company=self.company,
            role_legacy='admin')
        Lead.objects.create(company=self.company, nom='Charge', owner=self.a)
        lead = self._nouveau_a(self._a(29, 10, 2),
                               type_installation='residentiel')
        attente = lead.attribution_en_attente
        self.assertEqual(attente.echeance, self._a(29, 10, 32))

        def passage(h, mi):
            with mock.patch('apps.notifications.services.notify_many',
                            return_value=[]) as envoi:
                n = dispatch.escalader_file(self._a(29, h, mi))
            return n, envoi

        n, envoi = passage(10, 6)  # T+4
        self.assertEqual((n, envoi.call_count), (0, 0))
        n, envoi = passage(10, 7)  # T+5 : l'équipe
        self.assertEqual((n, envoi.call_count), (1, 1))
        destinataires, evenement = envoi.call_args.args[:2]
        self.assertEqual({u.pk for u in destinataires},
                         {self.chef.pk, self.a.pk, self.b.pk})
        self.assertEqual(evenement, EventType.LEAD_NON_CONTACTE)
        n, envoi = passage(10, 8)  # passage répété : rien
        self.assertEqual((n, envoi.call_count), (0, 0))
        n, envoi = passage(10, 17)  # T+15 : la direction
        self.assertEqual((n, envoi.call_count), (1, 1))
        destinataires, evenement = envoi.call_args.args[:2]
        self.assertIn(reda.pk, {u.pk for u in destinataires})
        self.assertEqual(evenement, EventType.PREMIER_CONTACT_DEPASSE)
        n, envoi = passage(10, 18)
        self.assertEqual((n, envoi.call_count), (0, 0))
        lead.refresh_from_db()
        self.assertEqual(lead.owner, self.chef)  # toujours à prendre
        n, envoi = passage(10, 32)  # T+30 : le moins chargé (b, a a un lead)
        self.assertEqual(n, 1)
        lead.refresh_from_db()
        self.assertEqual(lead.owner, self.b)
        self.assertEqual(LeadActivity.objects.filter(
            lead=lead, body__contains='délai de prise dépassé').count(), 1)
        n, envoi = passage(10, 40)
        self.assertEqual((n, envoi.call_count), (0, 0))
        self.assertEqual(LeadActivity.objects.filter(
            lead=lead, body__startswith='auto — file À prendre').count(), 3)

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
        self._regle(self.a, types_installation=['agricole'])
        self._regle(self.b, ordre=1, sources=['meta_ads'])
        self._regle(self.a, ordre=2, facture_min=Decimal('2000'))
        self.assertEqual(self._nouveau(
            type_installation='agricole').attribution_en_attente.proposee, self.a)
        self.assertEqual(self._nouveau(
            canal='meta_ads').attribution_en_attente.proposee, self.b)
        lead = self._nouveau(facture_hiver=Decimal('2500'))
        self.assertEqual(lead.attribution_en_attente.proposee, self.a)
        self.assertEqual(lead.attribution_en_attente.raison,
                         'Règle : facture 2000–∞ DH')

    def test_regle_plusieurs_types_de_client(self):
        # Fondateur 28/10/2026 — choix multiples : un des types suffit.
        self._regle(self.b, types_installation=['agricole', 'industriel'])
        self.assertEqual(self._nouveau(
            type_installation='industriel').attribution_en_attente.proposee,
            self.b)
        attente = self._nouveau(
            type_installation='agricole').attribution_en_attente
        self.assertEqual(attente.proposee, self.b)
        self.assertEqual(attente.raison, 'Règle : type Agricole, Industriel')
        self.assertEqual(self._nouveau(
            type_installation='residentiel').attribution_en_attente.raison,
            'Rotation équilibrée')

    def test_regle_plusieurs_sources(self):
        self._regle(self.a, sources=['meta_ads', 'site_web'])
        self.assertEqual(self._nouveau(
            canal='site_web').attribution_en_attente.proposee, self.a)
        self.assertEqual(self._nouveau(
            canal='meta_ads').attribution_en_attente.proposee, self.a)
        attente = self._nouveau(canal='telephone').attribution_en_attente
        self.assertEqual(attente.raison, 'Rotation équilibrée')

    def test_listes_vides_tous_les_leads(self):
        self._regle(self.b, types_installation=[], sources=[])
        attente = self._nouveau(
            type_installation='agricole', canal='meta_ads').attribution_en_attente
        self.assertEqual(attente.proposee, self.b)
        self.assertEqual(attente.raison, 'Règle : tous les leads')

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
