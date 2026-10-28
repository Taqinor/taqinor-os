"""AG6 — Tests des actions agentiques CRM (lead).

Couvre :
  - les quatre actions CRM (créer / mettre à jour / noter / préparer WhatsApp)
    sont enregistrées dans le catalogue AG1 et exposées à un utilisateur qui
    porte la permission ERP requise ;
  - ``company`` n'apparaît jamais dans le schéma ``inputs`` (forcée serveur) ;
  - les valeurs d'étape de ``mettre_a_jour_lead`` proviennent de STAGES.py
    (jamais codées en dur) ;
  - création d'un lead via l'endpoint relayé → société forcée côté serveur ;
  - une note POSTée via l'endpoint relayé atterrit dans le chatter du lead avec
    l'acteur + la société posés côté serveur (jamais lus du corps) ;
  - la préparation WhatsApp renvoie {wa_url, message, links} pour un devis.

Run :
    python manage.py test apps.crm.test_agent_actions -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Lead, LeadActivity
from apps.crm import stages
from apps.crm.agent_actions import (
    CREER_LEAD, LEADS_A_RELANCER, METTRE_A_JOUR_LEAD, NOTER_LEAD,
    PREPARER_ENVOI_WHATSAPP, RESUME_LEAD, register_crm_actions,
)
from apps.agent.registry import all_actions, for_user

User = get_user_model()

# Actions d'ÉCRITURE (crm_creer / crm_modifier) : un rôle lecture seule n'en voit aucune.
_ALL_CRM_KEYS = {
    CREER_LEAD.key, METTRE_A_JOUR_LEAD.key,
    NOTER_LEAD.key, PREPARER_ENVOI_WHATSAPP.key,
}
# Actions de LECTURE (crm_voir) de l'assistant (AIC30+).
_READ_CRM_KEYS = {LEADS_A_RELANCER.key, RESUME_LEAD.key}


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CrmAgentActionsCatalogueTest(TestCase):
    """Les actions CRM sont dans le catalogue et filtrées par permission."""

    def setUp(self):
        # ready() les enregistre déjà au démarrage ; idempotent ici aussi.
        register_crm_actions()
        self.company = Company.objects.create(nom='AG6 Co', slug='ag6-co')
        # Commercial : porte crm_creer + crm_modifier (les codes d'écriture).
        self.commercial_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'])
        self.commercial = User.objects.create_user(
            username='ag6_com', password='x', role=self.commercial_role,
            company=self.company)
        # Lecture seule : ne porte que crm_voir → ne voit aucune action d'écriture.
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='ag6_ro', password='x', role=self.readonly_role,
            company=self.company)

    def test_all_actions_registered_in_catalogue(self):
        keys = {a.key for a in all_actions()}
        self.assertTrue((_ALL_CRM_KEYS | _READ_CRM_KEYS).issubset(keys))

    def test_permitted_user_sees_all_actions(self):
        keys = {a.key for a in for_user(self.commercial)}
        self.assertTrue(_ALL_CRM_KEYS.issubset(keys))

    def test_readonly_user_sees_no_write_actions(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertFalse(keys & _ALL_CRM_KEYS)
        self.assertEqual(keys & _READ_CRM_KEYS, _READ_CRM_KEYS)

    def test_actions_required_permissions(self):
        self.assertEqual(CREER_LEAD.required_permission, 'crm_creer')
        self.assertEqual(METTRE_A_JOUR_LEAD.required_permission, 'crm_modifier')
        self.assertEqual(NOTER_LEAD.required_permission, 'crm_modifier')
        self.assertEqual(
            PREPARER_ENVOI_WHATSAPP.required_permission, 'crm_modifier')
        self.assertEqual(LEADS_A_RELANCER.required_permission, 'crm_voir')
        self.assertEqual(RESUME_LEAD.required_permission, 'crm_voir')

    def test_inputs_never_include_company(self):
        for action in (CREER_LEAD, METTRE_A_JOUR_LEAD, NOTER_LEAD,
                       PREPARER_ENVOI_WHATSAPP, LEADS_A_RELANCER,
                       RESUME_LEAD):
            props = action.inputs.get('properties', {})
            self.assertNotIn('company', props, action.key)

    def test_stage_enum_comes_from_stages_module(self):
        # Les valeurs d'étape ne sont pas codées en dur : elles viennent de
        # STAGES.py (via apps.crm.stages), source de vérité unique (règle #2).
        enum = METTRE_A_JOUR_LEAD.inputs['properties']['stage']['enum']
        self.assertEqual(list(enum), list(stages.STAGES))

    def test_catalogue_endpoint_lists_actions_for_permitted_user(self):
        api = auth(self.commercial)
        resp = api.get('/api/django/agent/actions/')
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        self.assertTrue(_ALL_CRM_KEYS.issubset(keys))


class CrmAgentActionRelayedCallTest(TestCase):
    """Création + note via l'endpoint relayé : société/acteur forcés serveur."""

    def setUp(self):
        register_crm_actions()
        self.company = Company.objects.create(nom='AG6 Relay Co', slug='ag6-relay')
        self.other = Company.objects.create(nom='AG6 Other', slug='ag6-other')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='ag6_relay', password='x', role=self.role,
            company=self.company)

    def test_create_lead_posts_through_endpoint_with_company_forced(self):
        api = auth(self.user)
        resp = api.post(CREER_LEAD.endpoint, {
            'nom': 'Prospect AG6',
            'telephone': '0600000000',
            # Tentative d'injection : la société est ignorée côté serveur.
            'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(nom='Prospect AG6')
        # Société forcée à celle du caller (jamais celle envoyée dans le corps).
        self.assertEqual(lead.company_id, self.company.id)

    def test_note_posts_to_lead_chatter_with_actor_and_company_forced(self):
        lead = Lead.objects.create(company=self.company, nom='Lead à noter')
        api = auth(self.user)
        endpoint = NOTER_LEAD.endpoint.format(id=lead.id)
        resp = api.post(endpoint, {
            'body': 'Appel passé — client intéressé.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # La note atterrit dans le chatter du lead, acteur + société serveur.
        # (QJ7 ajoute aussi une activité « modification » d'étape — on cible la NOTE.)
        act = LeadActivity.objects.filter(lead=lead, kind='note').order_by('-id').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.user_id, self.user.id)
        self.assertEqual(act.company_id, self.company.id)
        self.assertIn('client intéressé', act.body)


class CrmAgentWhatsappPrepareTest(TestCase):
    """La préparation WhatsApp renvoie {wa_url, message, links} pour un devis."""

    def setUp(self):
        register_crm_actions()
        self.company = Company.objects.create(nom='AG6 WA Co', slug='ag6-wa')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            # ACRM4 — le partage WhatsApp rend le numéro du client : il exige
            # ``client_pii_voir`` (que le rôle Commercial réel porte).
            permissions=['crm_voir', 'crm_creer', 'crm_modifier',
                         'ventes_voir', 'client_pii_voir'])
        self.user = User.objects.create_user(
            username='ag6_wa', password='x', role=self.role,
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead WhatsApp',
            telephone='0600112233', whatsapp='0600112233')

    def test_whatsapp_prepare_returns_wa_url_message_links(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        client = Client.objects.create(company=self.company, nom='Client AG6')
        devis = Devis.objects.create(
            company=self.company, lead=self.lead, client=client,
            statut='brouillon', reference='DEV-AG6-0001')
        api = auth(self.user)
        endpoint = PREPARER_ENVOI_WHATSAPP.endpoint.format(id=self.lead.id)
        resp = api.post(endpoint, {
            'devis_ids': [devis.id],
            'langue': 'fr',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # Carte de résultat : exactement les clés attendues par l'agent.
        self.assertIn('wa_url', resp.data)
        self.assertIn('message', resp.data)
        self.assertIn('links', resp.data)
        self.assertTrue(resp.data['wa_url'])


class CrmAgentARelancerTest(TestCase):
    """AIC30 — ``crm.leads.a_relancer`` sert la file du cockpit, pas une copie."""

    def setUp(self):
        register_crm_actions()
        self.company = Company.objects.create(nom='AIC30 Co', slug='aic30-co')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='aic30_com', password='x', role=self.role,
            company=self.company)
        # Commercial terrain : visites seulement, aucun accès CRM.
        self.terrain_role = Role.objects.create(
            company=self.company, nom='Terrain', permissions=['visites_voir'])
        self.terrain = User.objects.create_user(
            username='aic30_ter', password='x', role=self.terrain_role,
            company=self.company)

    def _touche(self, nom, jours, canal='appel'):
        import datetime
        from core.dates import aujourd_hui_local
        from apps.crm.models import RelanceEtape
        lead = Lead.objects.create(
            company=self.company, nom=nom, owner=self.user)
        due = aujourd_hui_local() + datetime.timedelta(days=jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            canal=canal, libelle=f'Touche {nom}', due_date=due)

    def test_a_relancer_egale_la_file_du_cockpit(self):
        from apps.crm.selectors import relance_etapes_dues
        for jours in (-9, -2, 0, 0):
            self._touche(f'L{jours}', jours)
        for portee, scope in (('aujourd_hui', 'today'), ('retard', 'overdue'),
                              ('semaine', 'week')):
            resp = auth(self.user).get(
                LEADS_A_RELANCER.endpoint, {'portee': portee})
            self.assertEqual(resp.status_code, 200, resp.data)
            attendu = list(relance_etapes_dues(
                self.company, self.user, scope=scope))
            self.assertEqual(resp.data['total'], len(attendu), portee)
            self.assertEqual(
                [ligne['lead_id'] for ligne in resp.data['lignes']],
                [e.lead_id for e in attendu], portee)

    def test_retard_en_jours_ouvres_et_champs_servis(self):
        self._touche('Retard', -9, canal='whatsapp')
        resp = auth(self.user).get(
            LEADS_A_RELANCER.endpoint, {'portee': 'retard'})
        ligne = resp.data['lignes'][0]
        self.assertEqual(ligne['canal'], 'whatsapp')
        self.assertGreaterEqual(ligne['retard_jours_ouvres'], 1)
        for cle in ('nom', 'etape', 'touche_prevue', 'dernier_contact'):
            self.assertIn(cle, ligne)

    def test_portee_inconnue_nomme_le_champ(self):
        resp = auth(self.user).get(
            LEADS_A_RELANCER.endpoint, {'portee': 'hier'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('portee', resp.data)

    def test_terrain_sans_pipeline(self):
        # Le catalogue ne la montre pas au terrain ET la route la refuse.
        self.assertNotIn(
            LEADS_A_RELANCER.key, {a.key for a in for_user(self.terrain)})
        resp = auth(self.terrain).get(LEADS_A_RELANCER.endpoint)
        self.assertEqual(resp.status_code, 403)


class CrmAgentResumeLeadTest(TestCase):
    """AIC31 — ``crm.lead.resume`` : blocs lus chez leur propriétaire."""

    def setUp(self):
        register_crm_actions()
        self.company = Company.objects.create(nom='AIC31 Co', slug='aic31-co')
        self.other = Company.objects.create(nom='AIC31 Autre', slug='aic31-x')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'crm_modifier', 'client_pii_voir'])
        self.user = User.objects.create_user(
            username='aic31_com', password='x', role=self.role,
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alami', prenom='Karim',
            ville='Casablanca', telephone='0600112233', owner=self.user)
        for i in range(7):
            LeadActivity.objects.create(
                company=self.company, lead=self.lead, kind='note',
                body=f'Note {i}', user=self.user)

    def _devis(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        client = Client.objects.create(company=self.company, nom='Client 31')
        return Devis.objects.create(
            company=self.company, lead=self.lead, client=client,
            statut='envoye', reference='DEV-AIC31-0001')

    def test_resume_lead_blocs_et_societe(self):
        self._devis()
        resp = auth(self.user).get(
            RESUME_LEAD.endpoint.format(id=self.lead.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        for cle in ('identite', 'etape', 'chatter', 'devis', 'visites',
                    'prochaine_touche', 'alertes'):
            self.assertIn(cle, resp.data)
        self.assertEqual(len(resp.data['chatter']), 5)
        self.assertEqual(resp.data['devis'][0]['reference'], 'DEV-AIC31-0001')
        self.assertEqual(resp.data['identite']['nom'], 'Alami')
        # Lead d'une autre société : 404, aucune fuite.
        autre = Lead.objects.create(company=self.other, nom='Autre')
        resp = auth(self.user).get(RESUME_LEAD.endpoint.format(id=autre.pk))
        self.assertEqual(resp.status_code, 404)

    def test_resume_sans_prix_achat(self):
        import json
        self._devis()
        resp = auth(self.user).get(
            RESUME_LEAD.endpoint.format(id=self.lead.pk))
        brut = json.dumps(resp.data, default=str).lower()
        self.assertNotIn('prix_achat', brut)
        self.assertNotIn('marge', brut)
