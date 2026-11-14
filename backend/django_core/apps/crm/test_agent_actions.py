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
    BROUILLON_SUIVI, CHANGER_ETAPE_LEAD, CHERCHER_LEAD, CREER_LEAD,
    DIGEST_MATIN, JOURNALISER_LEAD, LEADS_A_RELANCER, MESSAGE_VISITE,
    METTRE_A_JOUR_LEAD, NOTER_LEAD, PLANIFIER_VISITE, PREPARER_ENVOI_WHATSAPP,
    PREPARER_TOUCHE, PROPOSER_REPONSE, QUALIFIER_LEAD, RESUME_LEAD,
    _ACTIONS,
    register_crm_actions,
)
from apps.agent.registry import LOT_COPILOTE, LOT_HERITE, all_actions, for_user

User = get_user_model()

# Actions d'ÉCRITURE (crm_creer / crm_modifier) : un rôle lecture seule n'en voit aucune.
_ALL_CRM_KEYS = {
    CREER_LEAD.key, METTRE_A_JOUR_LEAD.key,
    NOTER_LEAD.key, PREPARER_ENVOI_WHATSAPP.key, BROUILLON_SUIVI.key,
}
# Actions de LECTURE (crm_voir) de l'assistant (AIC30+).
_READ_CRM_KEYS = {LEADS_A_RELANCER.key, RESUME_LEAD.key}


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _echantillon(fichier, cle='exemple'):
    """L'échantillon ``cle`` de ``contract_samples/<fichier>`` (contrat des
    lectures CRM de l'assistant) — les tests comparent les CLÉS de la vraie
    réponse à ces échantillons, jamais à un littéral retapé."""
    import json
    import pathlib
    chemin = (pathlib.Path(__file__).resolve().parent / 'contract_samples'
              / fichier)
    return json.loads(chemin.read_text(encoding='utf-8'))[cle]


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
        self.assertEqual(BROUILLON_SUIVI.required_permission, 'crm_modifier')

    def test_inputs_never_include_company(self):
        for action in _ACTIONS:
            props = action.inputs.get('properties', {})
            self.assertNotIn('company', props, action.key)

    def test_actions_copilote_ecriture_invisibles_en_lecture_seule(self):
        """COP — aucune écriture neuve n'est offerte à un rôle lecture seule."""
        ecritures = {a.key for a in _ACTIONS
                     if a.required_permission in ('crm_creer', 'crm_modifier')}
        self.assertTrue({CHANGER_ETAPE_LEAD.key, QUALIFIER_LEAD.key,
                         JOURNALISER_LEAD.key, PLANIFIER_VISITE.key}
                        <= ecritures)
        vus = {a.key for a in for_user(self.readonly)}
        self.assertFalse(vus & ecritures)

    def test_stage_enum_comes_from_stages_module(self):
        # Les valeurs d'étape ne sont pas codées en dur : elles viennent de
        # STAGES.py (via apps.crm.stages), source de vérité unique (règle #2).
        # COP-C5 : SIGNED (acceptation d'un devis) et COLD (parcage, geste de
        # l'écran avec sa raison) n'y figurent JAMAIS ; ``crm.lead.update``
        # ne porte plus d'étape du tout.
        enum = CHANGER_ETAPE_LEAD.inputs['properties']['stage']['enum']
        self.assertEqual(
            list(enum),
            [s for s in stages.STAGES if s not in (stages.SIGNED, stages.COLD)])
        self.assertNotIn(stages.SIGNED, enum)
        self.assertNotIn(stages.COLD, enum)
        self.assertNotIn('stage', METTRE_A_JOUR_LEAD.inputs['properties'])

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

    def test_whatsapp_prepare_laisse_le_devis_brouillon(self):
        """AMSG6 (C-AMSG-007) — l'action d'assistant joue l'APERÇU : devis
        brouillon sans date d'envoi, lead à son étape, aucune trace d'envoi."""
        from apps.audit.models import AuditLog
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        client = Client.objects.create(company=self.company, nom='Client AG6 B')
        devis = Devis.objects.create(
            company=self.company, lead=self.lead, client=client,
            statut='brouillon', reference='DEV-AG6-0002')
        # Le profil société naît (et s'audite) au premier rendu du message :
        # créé AVANT le comptage, il ne passe pas pour une trace d'envoi.
        from apps.parametres.models import CompanyProfile
        CompanyProfile.get(company=self.company)
        etape, audits = self.lead.stage, AuditLog.objects.count()
        activites = self.lead.activites.count()
        resp = auth(self.user).post(
            PREPARER_ENVOI_WHATSAPP.endpoint.format(id=self.lead.id),
            {'devis_ids': [devis.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue({'wa_url', 'message', 'links'} <= set(resp.data))
        devis.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual((devis.statut, devis.date_envoi), ('brouillon', None))
        self.assertEqual(self.lead.stage, etape)
        self.assertEqual(AuditLog.objects.count(), audits)
        self.assertEqual(self.lead.activites.count(), activites)


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


class CrmAgentBrouillonSuiviTest(TestCase):
    """AIC32 — ``crm.lead.brouillon_suivi`` : un texte, jamais un envoi."""

    def setUp(self):
        register_crm_actions()
        self.company = Company.objects.create(nom='AIC32 Co', slug='aic32-co')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'crm_modifier', 'client_pii_voir'])
        self.user = User.objects.create_user(
            username='aic32_com', password='x', role=self.role,
            company=self.company, first_name='Reda')

    def _lead(self, owner_prenom, **kw):
        owner = User.objects.create_user(
            username=f'aic32_{owner_prenom}', password='x', role=self.role,
            company=self.company, first_name=owner_prenom)
        kw.setdefault('telephone', '0600112233')
        return Lead.objects.create(
            company=self.company, nom='Alami', prenom='Karim', owner=owner, **kw)

    def _appel(self, lead, **corps):
        corps = {'canal': 'whatsapp', 'objectif': 'relance_devis', **corps}
        return auth(self.user).post(
            BROUILLON_SUIVI.endpoint.format(id=lead.pk), corps, format='json')

    def test_brouillon_suivi_modele_societe_et_expediteur_variable(self):
        from apps.crm.models_cadence import MessageTemplate
        MessageTemplate.objects.create(
            company=self.company, nom='Relance après devis', langue='fr',
            corps='Bonjour {prenom}, ici {conseiller} : votre devis ?')
        for prenom_owner in ('Salma', 'Youssef'):
            lead = self._lead(prenom_owner)
            resp = self._appel(lead)
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data['modele_source'], 'Relance après devis')
            self.assertIn(f'ici {prenom_owner}', resp.data['texte'])
            self.assertTrue(
                resp.data['lien_wa_me'].startswith('https://wa.me/'))
            self.assertEqual(resp.data['langue_servie'], 'fr')
            self.assertLessEqual(len(resp.data['texte']), 500)

    def test_sans_modele_aucune_phrase_de_repli_et_lien_nu(self):
        """COP-C7 — sans modèle société : texte VIDE (le Guide interdit
        « avez-vous pu le consulter ? »), lien wa.me nu, arabe replié en
        français ; la clé lue par la carte est ``wa_url``."""
        lead = self._lead('Salma')
        for objectif in ('relance_devis', 'apres_visite', 'reveil_froid'):
            with self.subTest(objectif=objectif):
                resp = self._appel(lead, langue='ar', objectif=objectif)
                self.assertEqual(resp.status_code, 200, resp.data)
                self.assertIsNone(resp.data['modele_source'])
                self.assertEqual(resp.data['langue_servie'], 'fr')
                self.assertEqual(resp.data['texte'], '')
                self.assertEqual(resp.data['wa_url'], 'https://wa.me/212600112233')
                self.assertEqual(resp.data['wa_url'], resp.data['lien_wa_me'])
                self.assertNotIn('?text=', resp.data['wa_url'])

    def test_aucune_phrase_de_repli_dans_le_code(self):
        import inspect
        from apps.crm import views_assistant
        source = inspect.getsource(views_assistant).lower()
        # (les commentaires citent la formule interdite : on ne cherche que
        # les anciennes phrases de repli, qui n'existent plus nulle part.)
        for interdit in ("je reviens vers vous au sujet de votre devis",
                         'suite à notre visite, avez-vous',
                         'je reprends contact pour savoir'):
            self.assertNotIn(interdit, source)

    def test_brouillon_rend_wa_url_de_la_carte_et_garde_lien_wa_me(self):
        from apps.crm.models_cadence import MessageTemplate
        MessageTemplate.objects.create(
            company=self.company, nom='Relance devis', langue='fr',
            corps='Bonjour {prenom}.')
        resp = self._appel(self._lead('Salma'))
        self.assertTrue(resp.data['wa_url'].startswith('https://wa.me/2126'))
        self.assertEqual(resp.data['wa_url'], resp.data['lien_wa_me'])
        self.assertIn('?text=', resp.data['wa_url'])
        # Contrat assistant_brouillon_suivi.json : mêmes clés que l'échantillon.
        self.assertEqual(set(resp.data), set(_echantillon(
            'assistant_brouillon_suivi.json', 'exemple')))

    def test_placeholder_vide_omis_jamais_une_accolade(self):
        """ACVI110 — règle MRY13 : une phrase dont le placeholder est vide ou
        inconnu est omise ; jamais « { » ni « je suis  de », repli compris."""
        from apps.crm.models_cadence import MessageTemplate
        MessageTemplate.objects.create(
            company=self.company, nom='Relance devis', langue='fr',
            corps=("Bonjour {prenom}. Je suis {conseiller} de {marque}. "
                   "Votre étude pour {societe}. Valable jusqu'au {date_validite}."))
        lead = self._lead('')
        resp = self._appel(lead, objectif='relance_devis')
        self.assertEqual(resp.status_code, 200, resp.data)
        texte, lien = resp.data['texte'], resp.data['lien_wa_me']
        self.assertTrue(texte.startswith('Bonjour Karim'), texte)
        for interdit in ('{', 'je suis  de', "c'est  de", 'Je suis', "C'est"):
            self.assertNotIn(interdit, texte)
        self.assertNotIn('%7B', lien)
        self.assertNotIn('{', lien)
        self.assertNotIn('Votre étude', texte)
        # COP-C7 : sans modèle pour l'objectif, plus de repli — texte vide.
        sans = self._appel(lead, objectif='reveil_froid')
        self.assertEqual(sans.data['texte'], '')

    def test_lead_oppose_409_sans_lien(self):
        """ACVI103 (D-ACVI-7) — opposé, perdu ou archivé : 409 nommé à chaque
        canal, ni texte ni lien, rien d'écrit ; hors portée : 404 d'abord."""
        oppose = self._lead('Salma', ne_plus_contacter=True)
        avant = LeadActivity.objects.count()
        for canal in ('whatsapp', 'sms', 'email'):
            with self.subTest(canal=canal):
                resp = self._appel(oppose, canal=canal)
                self.assertEqual(resp.status_code, 409, resp.data)
                self.assertEqual(str(resp.data['detail']), 'Message refusé : ne plus contacter.')
                self.assertNotIn('lien_wa_me', resp.data)
                self.assertNotIn('texte', resp.data)
        # ACVI108 — l'empreinte d'opposition couvre le numéro de Salma : le lead
        # perdu/archivé porte un AUTRE numéro pour isoler le motif « perdu/archivé ».
        resp = self._appel(self._lead('Perdu', perdu=True, telephone='0600112255'))
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(str(resp.data['detail']), 'Message refusé : perdu/archivé.')
        # Archivé : hors des leads en portée (404) ou refusé (409) — jamais un brouillon.
        self.assertIn(self._appel(self._lead('Archive', is_archived=True,
                                             telephone='0600112266')).status_code, (404, 409))
        self.assertEqual(LeadActivity.objects.count(), avant)
        autre = Company.objects.create(nom='AIC32 Autre', slug='aic32-autre')
        etranger = Lead.objects.create(company=autre, nom='X', telephone='0600112244',
                                       ne_plus_contacter=True)
        self.assertEqual(self._appel(etranger).status_code, 404)

    def test_objectif_inconnu_est_refuse(self):
        resp = self._appel(self._lead('Salma'), objectif='vendre')
        self.assertEqual(resp.status_code, 400)

    def test_brouillon_ne_rend_jamais_un_envoi(self):
        from unittest import mock
        lead = self._lead('Salma')
        avant = LeadActivity.objects.count()
        with mock.patch('socket.socket.connect',
                        side_effect=AssertionError('appel réseau')):
            resp = self._appel(lead, canal='sms')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['lien_wa_me'])
        self.assertEqual(LeadActivity.objects.count(), avant)


class CrmAgentCatalogueParRoleTest(TestCase):
    """AIC33 — descriptions relues pour le modèle + catalogue vu par rôle."""

    SECTIONS = ('Sert à :', 'Ne pas utiliser pour :', 'Exemple :',
                'Résultat :')
    # Golden LITTÉRAL des clés ``crm.*`` visibles par rôle système (via
    # ``for_user``) : retirer une permission d'une action le fait diverger.
    # COP : les actions du lot « copilote » (servies seulement si le copilote
    # est allumé pour le compte) sont RETIRÉES du relevé ci-dessous — sa
    # forme ne dépend ainsi pas de l'avancement de l'interrupteur côté
    # registre ; ``changer_etape`` (lot None) est servie à tous.
    CRM_COMMERCIAL = {
        'crm.client.create', 'crm.digest_matin', 'crm.lead.brouillon_suivi',
        'crm.lead.changer_etape',
        'crm.lead.create', 'crm.lead.list', 'crm.lead.note', 'crm.lead.resume',
        'crm.lead.update', 'crm.lead.whatsapp_prepare',
        'crm.leads.a_relancer',
    }
    GOLDEN = {
        'Commercial': CRM_COMMERCIAL,
        'Commercial responsable': CRM_COMMERCIAL,
        # Terrain = visites seulement : le digest (ses visites), aucune
        # action du pipeline CRM.
        'Commercial terrain': {'crm.digest_matin'},
    }

    def test_descriptions_quatre_sections(self):
        for action in _ACTIONS:
            with self.subTest(action=action.key):
                position = -1
                for section in self.SECTIONS:
                    suivante = action.description.find(section)
                    self.assertGreater(suivante, position, section)
                    position = suivante
                self.assertLessEqual(len(action.description), 600)
        self.assertIn(
            "n'envoie jamais", PREPARER_ENVOI_WHATSAPP.description)
        self.assertIn('wa.me', PREPARER_ENVOI_WHATSAPP.description)

    def test_catalogue_par_role_commercial(self):
        from django.core.management import call_command
        register_crm_actions()
        company = Company.objects.create(nom='AIC33 Co', slug='aic33-co')
        call_command('init_roles', verbosity=0)
        for nom, attendu in self.GOLDEN.items():
            with self.subTest(role=nom):
                user = User.objects.create_user(
                    username='aic33_' + nom.replace(' ', '_').lower(),
                    password='x', company=company,
                    role=Role.objects.get(company=company, nom=nom))
                vus = {a.key for a in for_user(user)
                       if a.key.startswith('crm.')
                       and a.lot != LOT_COPILOTE}
                self.assertEqual(vus, attendu)


class CrmAgentDigestMatinTest(TestCase):
    """AIC35 — ``crm.digest_matin`` : même compte que les écrans source."""

    def setUp(self):
        register_crm_actions()
        self.company = Company.objects.create(nom='AIC35 Co', slug='aic35-co')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'visites_voir', 'ventes_voir'])
        self.user = User.objects.create_user(
            username='aic35_com', password='x', role=self.role,
            company=self.company)
        self.terrain_role = Role.objects.create(
            company=self.company, nom='Terrain', permissions=['visites_voir'])
        self.terrain = User.objects.create_user(
            username='aic35_ter', password='x', role=self.terrain_role,
            company=self.company)

    def _donnees(self):
        import datetime
        from django.utils import timezone
        from apps.crm.models import Client, RelanceEtape
        from apps.ventes.models import Devis
        from apps.visites.models import VisiteTerrain
        from core.dates import aujourd_hui_local
        today = aujourd_hui_local()
        lead = Lead.objects.create(
            company=self.company, nom='Alami', owner=self.user)
        RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            canal='appel', libelle='Appel', due_date=today)
        VisiteTerrain.objects.create(
            company=self.company, lead=lead, commercial=self.user,
            date_prevue=today)
        client = Client.objects.create(company=self.company, nom='C35')
        ancien = timezone.now() - datetime.timedelta(days=10)
        recent = timezone.now() - datetime.timedelta(days=2)
        for ref, statut, quand in (
                ('DEV-35-ANCIEN', 'envoye', ancien),
                ('DEV-35-RECENT', 'envoye', recent),
                ('DEV-35-ACCEPTE', 'accepte', ancien)):
            Devis.objects.create(
                company=self.company, lead=lead, client=client,
                statut=statut, reference=ref, date_envoi=quand)
        return lead

    def test_digest_matin_egale_les_ecrans_source(self):
        from apps.crm.selectors import relance_etapes_dues
        from apps.visites import selectors as visites
        from apps.visites.models import VisiteTerrain
        from core.dates import aujourd_hui_local
        self._donnees()
        resp = auth(self.user).get(DIGEST_MATIN.endpoint)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['relances']['total'],
            relance_etapes_dues(self.company, self.user, scope='all').count())
        journee = visites.ma_journee(
            VisiteTerrain.objects.filter(
                company=self.company, commercial=self.user),
            aujourdhui=aujourd_hui_local())
        self.assertEqual(
            resp.data['visites']['total'], len(journee['visites']))
        # Sans réponse > 7 jours : l'ancien envoyé seulement (ni le récent
        # ni l'accepté).
        refs = [d['reference']
                for d in resp.data['devis_sans_reponse']['lignes']]
        self.assertEqual(refs, ['DEV-35-ANCIEN'])
        self.assertEqual(resp.data['devis_sans_reponse']['total'], 1)

    def test_manques_signales_hier_compte_seulement(self):
        import datetime
        from apps.agent.models import AssistantEvent
        from django.utils import timezone
        hier = timezone.now() - datetime.timedelta(days=1)
        for intention, autre in (('manque', False), ('manque', False),
                                 ('donnee', False), ('manque', True)):
            ev = AssistantEvent.objects.create(
                company=self.company,
                user=self.terrain if autre else self.user,
                intention=intention, question='q')
            AssistantEvent.objects.filter(pk=ev.pk).update(created_at=hier)
        resp = auth(self.user).get(DIGEST_MATIN.endpoint)
        self.assertEqual(resp.data['manques_signales_hier'], {'total': 2})

    def test_terrain_visites_seules(self):
        self._donnees()
        resp = auth(self.terrain).get(DIGEST_MATIN.endpoint)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), {'visites'})

    def test_lignes_du_digest_egales_aux_echantillons(self):
        """COP-C2 — ``relances.lignes`` = une ligne de la file (avec
        ``touche_id``) ; ``devis_sans_reponse.lignes[]`` porte ``devis_id``."""
        from apps.ventes.models import Devis
        self._donnees()
        exemple = _echantillon('assistant_digest_matin.json')
        resp = auth(self.user).get(DIGEST_MATIN.endpoint)
        self.assertEqual(set(resp.data), set(exemple))
        self.assertEqual(set(resp.data['relances']['lignes'][0]),
                         set(exemple['relances']['lignes'][0]))
        ligne = resp.data['devis_sans_reponse']['lignes'][0]
        self.assertEqual(set(ligne),
                         set(exemple['devis_sans_reponse']['lignes'][0]))
        self.assertEqual(
            ligne['devis_id'],
            Devis.objects.get(reference='DEV-35-ANCIEN').pk)


# ── COP — copilote commercial : les lectures et actions CRM de l'assistant ──


class _CopiloteBase(TestCase):
    """Deux commerciaux (portée « les siens »), un rôle sans coordonnées, une
    société étrangère — le socle des tests COP-C1 à COP-C8."""

    def setUp(self):
        from apps.roles.permissions_registre import SCOPE_SELF
        register_crm_actions()
        self.company = Company.objects.create(nom='COP Co', slug='cop-co')
        self.autre_societe = Company.objects.create(nom='COP X', slug='cop-x')
        perms = ['crm_voir', 'crm_modifier', 'crm_creer', 'visites_voir',
                 'ventes_voir', 'client_pii_voir', SCOPE_SELF]
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=perms)
        self.sans_pii = Role.objects.create(
            company=self.company, nom='Sans coordonnées',
            permissions=[p for p in perms if p != 'client_pii_voir'])
        self.alice = User.objects.create_user(
            username='cop_alice', password='x', role=self.role,
            company=self.company)
        self.bob = User.objects.create_user(
            username='cop_bob', password='x', role=self.role,
            company=self.company)
        self.discret = User.objects.create_user(
            username='cop_discret', password='x', role=self.sans_pii,
            company=self.company)

    def _lead(self, nom='Benali', owner=None, **kw):
        kw.setdefault('telephone', '0661000111')
        return Lead.objects.create(
            company=self.company, nom=nom, prenom=kw.pop('prenom', 'Aziz'),
            owner=owner or self.alice, **kw)

    def _touche(self, lead, canal='whatsapp', cle='identite', jours=0,
                libelle=None, **kw):
        import datetime
        from core.dates import aujourd_hui_local
        from apps.crm.models import RelanceEtape
        kw.setdefault('cadence', 'contact')
        kw.setdefault('ordre', 1)
        return RelanceEtape.objects.create(
            company=lead.company, lead=lead, canal=canal, template_cle=cle,
            libelle=libelle or ("Message d'identité" if canal == 'whatsapp'
                                else "Appel d'ouverture"),
            due_date=aujourd_hui_local() + datetime.timedelta(days=jours),
            **kw)


class CrmAssistantRechercheLeadsTest(_CopiloteBase):
    """COP-C1 — ``crm.lead.chercher`` : compacte, bornée à la portée."""

    URL = CHERCHER_LEAD.endpoint

    def test_cles_egales_aux_echantillons(self):
        lead = self._lead('Alami', ville='Bouskoura')
        self._touche(lead)
        self._lead('Boulangerie', ville='Bouskoura', societe='Boulangerie SARL')
        exemple = _echantillon('assistant_leads_recherche.json')
        resp = auth(self.alice).get(self.URL, {'q': 'bouskoura'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(exemple))
        avec_touche = next(x for x in resp.data['lignes']
                           if x['lead_id'] == lead.pk)
        sans_touche = next(x for x in resp.data['lignes']
                           if x['lead_id'] != lead.pk)
        self.assertEqual(set(avec_touche), set(exemple['lignes'][0]))
        self.assertEqual(set(avec_touche['prochaine_touche']),
                         set(exemple['lignes'][0]['prochaine_touche']))
        self.assertIsNone(sans_touche['prochaine_touche'])
        self.assertEqual(set(sans_touche), set(exemple['lignes'][1]))
        vide = auth(self.alice).get(self.URL, {'q': 'zzz'})
        self.assertEqual(set(vide.data), set(_echantillon(
            'assistant_leads_recherche.json', 'exemple_aucun')))
        self.assertEqual(vide.data['lignes'], [])

    def test_recherche_nom_ville_telephone_et_etape(self):
        a = self._lead('Alami', ville='Bouskoura', telephone='0661234567')
        b = self._lead('Idrissi', ville='Rabat', stage=stages.QUOTE_SENT)
        for q, attendu in (('alami', {a.pk}), ('Rabat', {b.pk}),
                           ('0661234567', {a.pk})):
            ids = {x['lead_id'] for x in auth(self.alice).get(
                self.URL, {'q': q}).data['lignes']}
            self.assertEqual(ids, attendu, q)
        resp = auth(self.alice).get(self.URL, {'etape': stages.QUOTE_SENT})
        self.assertEqual([x['lead_id'] for x in resp.data['lignes']], [b.pk])
        self.assertEqual(resp.data['lignes'][0]['etape_libelle'],
                         stages.STAGE_LABELS[stages.QUOTE_SENT])

    def test_etape_inconnue_et_limite_bornee(self):
        for i in range(30):
            self._lead(f'Lead{i}')
        resp = auth(self.alice).get(self.URL, {'etape': 'PERDU'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('etape', resp.data)
        resp = auth(self.alice).get(self.URL, {'limite': '999'})
        self.assertEqual((resp.data['limite'], len(resp.data['lignes'])),
                         (25, 25))
        self.assertEqual(resp.data['total'], 30)
        self.assertEqual(auth(self.alice).get(
            self.URL).data['limite'], 10)

    def test_portee_deux_commerciaux_et_deux_societes(self):
        mien = self._lead('Mien', owner=self.alice)
        son = self._lead('Sien', owner=self.bob)
        etranger = Lead.objects.create(company=self.autre_societe, nom='Mien X')
        ids = {x['lead_id'] for x in auth(self.alice).get(
            self.URL, {'q': 'ien'}).data['lignes']}
        self.assertEqual(ids, {mien.pk})
        self.assertNotIn(son.pk, ids)
        self.assertNotIn(etranger.pk, ids)

    def test_telephone_masque_et_non_cherchable_sans_droit_pii(self):
        lead = self._lead('Alami', telephone='0661234567', owner=self.discret)
        resp = auth(self.discret).get(self.URL, {'q': 'alami'})
        self.assertEqual(resp.data['lignes'][0]['telephone'], '')
        # Le numéro masqué n'est pas un critère : aucun oracle.
        par_numero = auth(self.discret).get(self.URL, {'q': '0661234567'})
        self.assertEqual(par_numero.data['lignes'], [])
        avec = auth(self.alice).get(self.URL, {'q': 'alami'})
        self.assertEqual(avec.data['total'], 0)  # lead de discret, hors portée
        self.assertEqual(lead.owner, self.discret)

    def test_prochaine_touche_en_une_requete_pour_toutes_les_lignes(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        auth(self.alice).get(self.URL)  # échauffement (caches de droits)

        def requetes(n):
            for i in range(n):
                self._touche(self._lead(f'Q{n}-{i}'))
            with CaptureQueriesContext(connection) as ctx:
                auth(self.alice).get(self.URL, {'q': f'Q{n}-'})
            return len(ctx)
        petit, grand = requetes(2), requetes(8)
        self.assertEqual(petit, grand)

    def test_declaration_de_l_action(self):
        self.assertEqual(
            (CHERCHER_LEAD.carte, CHERCHER_LEAD.lot,
             CHERCHER_LEAD.required_permission, CHERCHER_LEAD.risk),
            ('liste_leads', LOT_COPILOTE, 'crm_voir', 'internal'))
        self.assertEqual(
            CHERCHER_LEAD.inputs['properties']['etape']['enum'],
            list(stages.STAGES))


class CrmAssistantFileEtResumeTest(_CopiloteBase):
    """COP-C2 — la file, le résumé et le matin portent les identifiants."""

    def test_la_file_porte_touche_id_cle_et_cadence(self):
        lead = self._lead()
        etape = self._touche(lead, cle='j1_pdf', cadence='apres_devis')
        exemple = _echantillon('assistant_a_relancer.json')
        resp = auth(self.alice).get(LEADS_A_RELANCER.endpoint)
        self.assertEqual(set(resp.data), set(exemple))
        ligne = resp.data['lignes'][0]
        self.assertEqual(set(ligne), set(exemple['lignes'][0]))
        self.assertEqual(
            (ligne['touche_id'], ligne['touche_cle'], ligne['cadence']),
            (etape.pk, 'j1_pdf', 'apres_devis'))
        # `etape` reste l'étape du FUNNEL, jamais un identifiant de touche.
        self.assertEqual(ligne['etape'], lead.stage)

    def test_le_resume_porte_id_du_devis_et_de_la_touche(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        lead = self._lead()
        etape = self._touche(lead, libelle='Relance J+1', cle='j1_pdf')
        client = Client.objects.create(company=self.company, nom='C COP')
        devis = Devis.objects.create(
            company=self.company, lead=lead, client=client,
            statut='envoye', reference='DEV-COP-0001')
        exemple = _echantillon('assistant_lead_resume.json')
        resp = auth(self.alice).get(
            RESUME_LEAD.endpoint.format(id=lead.pk))
        self.assertEqual(set(resp.data), set(exemple))
        self.assertEqual(set(resp.data['devis'][0]),
                         set(exemple['devis'][0]))
        self.assertEqual(resp.data['devis'][0]['id'], devis.pk)
        touche = resp.data['prochaine_touche']
        self.assertEqual(set(touche), set(exemple['prochaine_touche']))
        self.assertEqual((touche['touche_id'], touche['libelle']),
                         (etape.pk, 'Relance J+1'))
        sans = self._lead('Sans touche')
        vide = auth(self.alice).get(RESUME_LEAD.endpoint.format(id=sans.pk))
        self.assertIsNone(vide.data['prochaine_touche'])
        self.assertEqual(set(vide.data), set(_echantillon(
            'assistant_lead_resume.json', 'exemple_sans_touche')))

    def test_cartes_et_description_des_trois_lectures(self):
        self.assertEqual(LEADS_A_RELANCER.carte, 'file_touches')
        self.assertEqual(DIGEST_MATIN.carte, 'matin')
        self.assertEqual(RESUME_LEAD.carte, 'fiche_lead')
        for action in (LEADS_A_RELANCER, RESUME_LEAD):
            self.assertIn('touche_id', action.description)
            self.assertIn('crm.suivi.preparer_touche', action.description)


class CrmAssistantToucheTest(_CopiloteBase):
    """COP-C3 — ``crm.suivi.preparer_touche`` : le texte VALIDÉ du serveur."""

    def _lire(self, user, etape, **params):
        return auth(user).get(
            PREPARER_TOUCHE.endpoint.format(touche_id=etape.pk), params)

    def test_message_whatsapp_forme_de_l_echantillon(self):
        etape = self._touche(self._lead(whatsapp='0661000111'))
        exemple = _echantillon('assistant_touche.json')
        resp = self._lire(self.alice, etape)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(exemple))
        self.assertEqual(set(resp.data['message']), set(exemple['message']))
        self.assertEqual(set(resp.data['lead']), set(exemple['lead']))
        self.assertEqual(resp.data['touche']['id'], etape.pk)
        self.assertTrue(resp.data['message']['wa_url'].startswith(
            'https://wa.me/212661000111'))
        self.assertIsNone(resp.data['appel'])
        self.assertIsNone(resp.data['refus'])
        self.assertEqual(resp.data['lead']['etape'], stages.NEW)

    def test_message_rendu_par_le_meme_code_que_l_ecran(self):
        etape = self._touche(self._lead())
        ecran = auth(self.alice).get(
            f'/api/django/crm/relance-etapes/{etape.pk}/message/')
        self.assertEqual(ecran.status_code, 200, ecran.data)
        resp = self._lire(self.alice, etape)
        self.assertEqual(resp.data['message'], dict(ecran.data))

    def test_touche_d_appel_script_questions_et_telephone(self):
        etape = self._touche(self._lead(), canal='appel',
                             cle='appel_ouverture')
        exemple = _echantillon('assistant_touche.json', 'exemple_appel')
        resp = self._lire(self.alice, etape)
        self.assertEqual(set(resp.data), set(exemple))
        self.assertIsNone(resp.data['message'])
        self.assertEqual(set(resp.data['appel']), set(exemple['appel']))
        self.assertEqual(set(resp.data['appel']['script']),
                         set(exemple['appel']['script']))
        self.assertEqual(resp.data['appel']['telephone'], '0661000111')

    def test_pii_masquee_sans_droit(self):
        lead = self._lead(owner=self.discret)
        appel = self._touche(lead, canal='appel', cle='appel_ouverture')
        self.assertEqual(self._lire(self.discret, appel).data[
            'appel']['telephone'], '')
        wa = self._touche(lead, ordre=2)
        resp = self._lire(self.discret, wa)
        self.assertIsNone(resp.data['message'])
        self.assertEqual(resp.data['refus']['code'], 'droit_manquant')

    def test_refus_opposition_perdu_et_touche_annulee(self):
        exemple = _echantillon('assistant_touche.json', 'exemple_refus')
        oppose = self._touche(self._lead(ne_plus_contacter=True))
        resp = self._lire(self.alice, oppose)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(exemple))
        self.assertEqual(set(resp.data['refus']), set(exemple['refus']))
        self.assertEqual(resp.data['refus']['code'], 'opposition')
        self.assertIsNone(resp.data['message'])
        self.assertIsNone(resp.data['appel'])
        perdu = self._touche(self._lead('Perdu', perdu=True,
                                        telephone='0661000222'))
        self.assertEqual(self._lire(self.alice, perdu).data[
            'refus']['code'], 'perdu_ou_archive')
        annulee = self._touche(self._lead('Annulee', telephone='0661000333'),
                               statut='annulee')
        self.assertEqual(self._lire(self.alice, annulee).data[
            'refus']['code'], 'touche_annulee')
        # L'opposition vaut aussi pour un appel : aucun script.
        appel = self._touche(
            self._lead('OpposeAppel', ne_plus_contacter=True,
                       telephone='0661000444'),
            canal='appel', cle='appel_ouverture')
        self.assertEqual(self._lire(self.alice, appel).data[
            'refus']['code'], 'opposition')

    def test_portee_societe_et_aucune_ecriture(self):
        from apps.crm.models import RelanceEtape
        etape = self._touche(self._lead(owner=self.alice))
        # Un autre commercial (portée « les siens ») : touche ABSENTE.
        self.assertEqual(self._lire(self.bob, etape).status_code, 404)
        etranger = Lead.objects.create(company=self.autre_societe, nom='X')
        autre = RelanceEtape.objects.create(
            company=self.autre_societe, lead=etranger, cadence='contact',
            ordre=1, canal='appel', libelle='A', due_date=etape.due_date)
        self.assertEqual(self._lire(self.alice, autre).status_code, 404)
        avant = (LeadActivity.objects.count(),
                 RelanceEtape.objects.filter(statut='a_faire').count())
        self.assertEqual(self._lire(self.alice, etape).status_code, 200)
        apres = (LeadActivity.objects.count(),
                 RelanceEtape.objects.filter(statut='a_faire').count())
        self.assertEqual(avant, apres)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, 'a_faire')

    def test_declaration_de_l_action(self):
        self.assertEqual(
            (PREPARER_TOUCHE.carte, PREPARER_TOUCHE.lot, PREPARER_TOUCHE.risk),
            ('touche', LOT_COPILOTE, 'internal'))
        self.assertEqual(
            (PROPOSER_REPONSE.carte, PROPOSER_REPONSE.lot,
             PROPOSER_REPONSE.risk),
            ('touche', LOT_COPILOTE, 'internal'))
        self.assertIn("n'enregistre RIEN", PROPOSER_REPONSE.description)
        self.assertIn('Une seule touche', PROPOSER_REPONSE.description)


class CrmAssistantPropositionTest(_CopiloteBase):
    """COP-C4 — la carte-écho : le serveur VALIDE, ne propose que du valide."""

    def setUp(self):
        super().setUp()
        self.lead = self._lead('Idrissi', prenom='Salma')
        self.appel = self._touche(self.lead, canal='appel',
                                  cle='appel_ouverture')

    def _proposer(self, etape=None, **params):
        etape = etape or self.appel
        return auth(self.alice).get(
            PROPOSER_REPONSE.endpoint.format(touche_id=etape.pk), params)

    def _jeudi(self):
        import datetime
        from core.dates import aujourd_hui_local
        jour = aujourd_hui_local() + datetime.timedelta(days=3)
        return jour

    def test_pas_de_reponse_proposition_et_forme(self):
        exemple = _echantillon('assistant_touche.json', 'exemple_proposition')
        resp = self._proposer(geste='fait', outcome='non_joint')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(exemple))
        prop = resp.data['proposition']
        self.assertEqual(set(prop), set(exemple['proposition']))
        self.assertEqual(prop['geste'], 'fait')
        self.assertEqual(prop['corps'], {'outcome': 'non_joint'})
        self.assertIn('Salma Idrissi', prop['libelle'])
        self.assertIn("Appel d'ouverture", prop['libelle'])
        self.assertTrue(prop['effet'])
        self.assertIsNone(resp.data['proposition_refus'])

    def test_rappel_date_ecrite_en_toutes_lettres_et_corps_exact(self):
        from apps.crm.cadence_messages import _date_visite_francais
        jour = self._jeudi()
        resp = self._proposer(
            geste='fait', outcome='rappel', rappel_le=jour.isoformat(),
            rappel_heure='11:00', note='Demande à être rappelée.')
        prop = resp.data['proposition']
        self.assertEqual(prop['corps'], {
            'outcome': 'rappel', 'rappel_le': jour.isoformat(),
            'rappel_heure': '11:00', 'note': 'Demande à être rappelée.'})
        self.assertIn(_date_visite_francais(jour), prop['libelle'])
        self.assertIn('11:00', prop['libelle'])

    def test_refus_date_passee_issue_obligatoire_et_inconnue(self):
        import datetime
        from core.dates import aujourd_hui_local
        passe = aujourd_hui_local() - datetime.timedelta(days=4)
        cas = (
            {'geste': 'fait', 'outcome': 'rappel',
             'rappel_le': passe.isoformat()},
            # issue obligatoire sur un appel
            {'geste': 'fait'},
            # issue inconnue / non proposée sur ce type de touche
            {'geste': 'fait', 'outcome': 'interesse'},
            # rappel sans date
            {'geste': 'fait', 'outcome': 'rappel'},
            {'geste': 'fait', 'outcome': 'rappel', 'rappel_le': 'demain'},
            {'geste': 'danser'},
        )
        for params in cas:
            with self.subTest(params=params):
                resp = self._proposer(**params)
                self.assertEqual(resp.status_code, 200, resp.data)
                self.assertIsNone(resp.data['proposition'])
                self.assertTrue(resp.data['proposition_refus'])

    def test_reponse_non_permise_pour_ce_type_de_touche(self):
        # « Question de prix » ne vaut que sur un suivi de proposition.
        resp = self._proposer(geste='fait', reponse='question_prix')
        self.assertIsNone(resp.data['proposition'])
        self.assertIn('Question de prix', resp.data['proposition_refus'])
        inconnue = self._proposer(geste='fait', reponse='peut_etre')
        self.assertIsNone(inconnue.data['proposition'])

    def test_reponse_ne_plus_contacter_et_effet_clair(self):
        resp = self._proposer(geste='fait', reponse='ne_plus_contacter')
        prop = resp.data['proposition']
        self.assertEqual(prop['corps'], {'reponse': 'ne_plus_contacter'})
        self.assertIn('ne plus contacter', prop['effet'])
        plus_tard = self._proposer(geste='fait', reponse='plus_tard')
        self.assertIsNone(plus_tard.data['proposition'])  # date obligatoire
        ok = self._proposer(geste='fait', reponse='plus_tard',
                            rappel_le=self._jeudi().isoformat())
        self.assertEqual(ok.data['proposition']['corps'], {
            'reponse': 'plus_tard', 'rappel_le': self._jeudi().isoformat()})

    def test_motif_hors_liste_refuse_motif_de_la_societe_accepte(self):
        from apps.crm.models import MotifPerte
        resp = self._proposer(geste='fait', outcome='refuse',
                              motif_refus='Inexistant')
        self.assertIsNone(resp.data['proposition'])
        self.assertIn('Motif du refus', resp.data['proposition_refus'])
        MotifPerte.objects.create(company=self.company, nom='Trop cher')
        ok = self._proposer(geste='fait', outcome='refuse',
                            motif_refus='trop cher')
        self.assertEqual(ok.data['proposition']['corps'],
                         {'outcome': 'refuse', 'motif_refus': 'Trop cher'})
        sans_refus = self._proposer(geste='fait', outcome='non_joint',
                                    motif_refus='Trop cher')
        self.assertIsNone(sans_refus.data['proposition'])

    def test_reporter_et_sauter(self):
        jour = self._jeudi()
        resp = self._proposer(geste='reporter', rappel_le=jour.isoformat(),
                              rappel_heure='15:30')
        self.assertEqual(resp.data['proposition']['corps'],
                         {'rappel_le': jour.isoformat(),
                          'rappel_heure': '15:30'})
        veille = self._proposer(geste='reporter', rappel_le=jour.isoformat(),
                                mode='veille')
        self.assertEqual(veille.data['proposition']['corps']['mode'], 'veille')
        self.assertIsNone(self._proposer(geste='reporter').data['proposition'])
        self.assertIsNone(self._proposer(
            geste='reporter', rappel_le='2020-01-01').data['proposition'])
        sauter = self._proposer(geste='sauter', note='Doublon')
        self.assertEqual(sauter.data['proposition']['corps'],
                         {'note': 'Doublon'})

    def test_une_tache_ne_se_saute_pas(self):
        from apps.crm.models import RelanceEtape
        lead = self._lead('Tache', telephone='0661000555')
        tache = self._touche(
            lead, canal='appel', cle='', cadence='generique',
            libelle='Préparer et envoyer le devis (ou fixer un rappel)')
        RelanceEtape.objects.filter(pk=tache.pk).update(cle='devis')
        tache.refresh_from_db()
        resp = self._proposer(tache, geste='sauter')
        self.assertIsNone(resp.data['proposition'])
        self.assertIn('tâche', resp.data['proposition_refus'])

    def test_touche_deja_traitee_et_aucune_ecriture(self):
        from apps.crm.models import RelanceEtape
        avant = (LeadActivity.objects.count(),
                 list(RelanceEtape.objects.values_list('pk', 'statut')))
        resp = self._proposer(geste='fait', outcome='non_joint')
        self.assertIsNotNone(resp.data['proposition'])
        apres = (LeadActivity.objects.count(),
                 list(RelanceEtape.objects.values_list('pk', 'statut')))
        self.assertEqual(avant, apres)
        RelanceEtape.objects.filter(pk=self.appel.pk).update(statut='fait')
        close = self._proposer(geste='fait', outcome='non_joint')
        self.assertIsNone(close.data['proposition'])
        self.assertIn('déjà traitée', close.data['proposition_refus'])

    @staticmethod
    def _corps_poste_par_l_ecran(prop):
        """Le corps que la carte poste VRAIMENT (``crmApi``) : ``fait`` =
        le corps entier ; ``reporter`` = ``rappel_le``/``rappel_heure``/``mode``
        seulement ; ``sauter`` = ``note`` seulement."""
        corps = prop['corps']
        gardees = {'reporter': ('rappel_le', 'rappel_heure', 'mode'),
                   'sauter': ('note',)}.get(prop['geste'])
        if gardees is None:
            return corps
        return {k: v for k, v in corps.items() if k in gardees}

    def test_le_corps_propose_est_accepte_par_le_vrai_geste(self):
        """Parité : ce que la carte poste (corps FILTRÉ comme l'écran) passe
        au geste existant (200)."""
        jour = self._jeudi().isoformat()
        for params in ({'geste': 'fait', 'outcome': 'non_joint'},
                       {'geste': 'fait', 'outcome': 'rappel',
                        'rappel_le': jour, 'rappel_heure': '11:00'},
                       {'geste': 'fait', 'outcome': 'joint'},
                       {'geste': 'fait', 'outcome': 'joint',
                        'rappel_le': jour, 'note': 'Rappel convenu'},
                       {'geste': 'reporter', 'rappel_le': jour},
                       {'geste': 'reporter', 'rappel_le': jour,
                        'rappel_heure': '15:30', 'mode': 'veille'},
                       {'geste': 'sauter', 'note': 'Doublon'}):
            with self.subTest(params=params):
                lead = self._lead(f'Parite{len(params)}{params["geste"]}')
                etape = self._touche(lead, canal='appel',
                                     cle='appel_ouverture')
                prop = self._proposer(etape, **params).data['proposition']
                self.assertIsNotNone(prop, params)
                corps = self._corps_poste_par_l_ecran(prop)
                self.assertEqual(corps, prop['corps'], 'clé perdue par l\'écran')
                reel = auth(self.alice).post(
                    f'/api/django/crm/relance-etapes/{etape.pk}/'
                    f'{prop["geste"]}/', corps, format='json')
                self.assertEqual(reel.status_code, 200, reel.data)

    def test_report_jamais_en_due_at(self):
        """F2 — ``due_at`` n'est ni une entrée de l'action ni un paramètre lu :
        le report se propose en ``rappel_le`` + ``rappel_heure`` (Casablanca)."""
        self.assertNotIn('due_at', PROPOSER_REPONSE.inputs['properties'])
        jour = self._jeudi().isoformat()
        seul = self._proposer(geste='reporter',
                              due_at=f'{jour}T11:00:00+01:00')
        self.assertIsNone(seul.data['proposition'])
        self.assertIn('Reporter au', seul.data['proposition_refus'])
        prop = self._proposer(geste='reporter', rappel_le=jour,
                              due_at=f'{jour}T18:00:00+01:00').data['proposition']
        self.assertEqual(prop['corps'],
                         {'rappel_le': jour, 'rappel_heure': '09:00'})

    def test_issue_hors_vocabulaire_de_fait_refusee(self):
        """F3 — une réponse du client ou « sauter » passée en ``outcome`` est
        refusée par la carte comme par ``fait`` (400 « Issue inconnue »)."""
        for outcome in ('sauter', 'ne_plus_contacter', 'plus_tard'):
            with self.subTest(outcome=outcome):
                resp = self._proposer(geste='fait', outcome=outcome)
                self.assertIsNone(resp.data['proposition'])
                self.assertIn("n'est pas proposée",
                              resp.data['proposition_refus'])

    def test_compte_sans_droit_d_enregistrer_aucune_proposition(self):
        """F4 — lecture ouverte à ``crm_voir`` ; proposition refusée à qui ne
        passe pas la garde des vrais gestes."""
        from apps.crm.assistant_touches import MESSAGE_ROLE_SANS_ENREGISTREMENT
        lecteur = User.objects.create_user(
            username='cop_lecteur', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Lecteur CRM',
                permissions=['crm_voir', 'client_pii_voir']))
        etape = self._touche(self._lead('Lecture', owner=lecteur),
                             canal='appel', cle='appel_ouverture')
        url = PROPOSER_REPONSE.endpoint.format(touche_id=etape.pk)
        lu = auth(lecteur).get(url)
        self.assertEqual((lu.status_code, lu.data['touche']['id']),
                         (200, etape.pk))
        resp = auth(lecteur).get(url, {'geste': 'fait', 'outcome': 'non_joint'})
        self.assertIsNone(resp.data['proposition'])
        self.assertEqual(resp.data['proposition_refus'],
                         MESSAGE_ROLE_SANS_ENREGISTREMENT)
        self.assertEqual(auth(lecteur).post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'non_joint'}, format='json').status_code, 403)

    def test_effet_du_rappel_dit_ce_que_fait_le_geste(self):
        """F6 — « À rappeler » sur une étape de visite REPORTE la touche (elle
        n'est pas close) ; une date avec une autre issue place la suivante."""
        from apps.crm.cadence_config import CLE_PLANIFIER
        from apps.crm.models import RelanceEtape
        jour = self._jeudi().isoformat()
        lead = self._lead('Visite', telephone='0661000777')
        visite = self._touche(lead, canal='appel', cle='', cadence='suivi',
                              libelle='Planifier la visite technique')
        RelanceEtape.objects.filter(pk=visite.pk).update(cle=CLE_PLANIFIER)
        visite.refresh_from_db()
        prop = self._proposer(visite, geste='fait', outcome='rappel',
                              rappel_le=jour).data['proposition']
        self.assertTrue(prop['effet'].startswith('La touche est reportée au'),
                        prop['effet'])
        reel = auth(self.alice).post(
            f'/api/django/crm/relance-etapes/{visite.pk}/fait/',
            prop['corps'], format='json')
        self.assertEqual(reel.status_code, 200, reel.data)
        visite.refresh_from_db()
        self.assertEqual(visite.statut, RelanceEtape.Statut.A_FAIRE)
        joint = self._proposer(geste='fait', outcome='joint',
                               rappel_le=jour).data['proposition']
        self.assertIn("La touche suivante, s'il en reste une, est placée au",
                      joint['effet'])

    def test_geste_inconnu_typographie(self):
        resp = self._proposer(geste='danser')
        self.assertTrue(resp.data['proposition_refus'].startswith(
            'Geste inconnu : « danser ». Gestes : fait'),
            resp.data['proposition_refus'])

    def test_vocabulaires_de_l_action_egaux_a_ceux_du_serveur(self):
        from apps.crm.cadence_reponses import (
            RAISONS_ATTENTE_VALEURS, REPONSES_TOUCHE)
        from apps.crm.models import LeadActivity
        from apps.crm.schema_docs import LANGUES_RELANCE
        props = PROPOSER_REPONSE.inputs['properties']
        self.assertEqual(props['geste']['enum'], ['fait', 'reporter', 'sauter'])
        self.assertEqual(
            props['outcome']['enum'],
            [k for k, _ in LeadActivity.OUTCOMES if k])
        self.assertEqual(props['reponse']['enum'], list(REPONSES_TOUCHE))
        self.assertEqual(props['raison_attente']['enum'],
                         list(RAISONS_ATTENTE_VALEURS))
        self.assertEqual(props['langue']['enum'], list(LANGUES_RELANCE))
        self.assertEqual(PROPOSER_REPONSE.inputs['required'],
                         ['touche_id', 'geste'])


class CrmAssistantEcrituresLeadTest(_CopiloteBase):
    """COP-C5 — qualifier, changer d'étape, journaliser : à confirmer."""

    def test_qualifier_liste_blanche_confirmation_et_vocabulaires(self):
        from apps.crm.agent_actions import CHAMPS_QUALIFICATION
        props = QUALIFIER_LEAD.inputs['properties']
        self.assertEqual(set(props), {'id', *CHAMPS_QUALIFICATION})
        for interdit in ('stage', 'owner', 'perdu', 'motif_perte', 'parc_etat',
                         'parc_raison', 'ne_plus_contacter', 'telephone',
                         'whatsapp', 'email', 'company'):
            self.assertNotIn(interdit, props)
        self.assertEqual(QUALIFIER_LEAD.risk, 'outward')
        self.assertEqual(QUALIFIER_LEAD.objets, {'id': 'lead'})
        self.assertEqual(QUALIFIER_LEAD.lot, LOT_COPILOTE)
        # Les choix fermés = ceux du modèle (parité avec le serveur).
        for champ in CHAMPS_QUALIFICATION:
            f = Lead._meta.get_field(champ)
            if f.choices:
                self.assertEqual(
                    props[champ]['enum'],
                    [v for v, _ in f.flatchoices if v != ''], champ)
        self.assertEqual(props['ete_differente']['type'], 'boolean')
        self.assertEqual(props['nb_personnes_foyer']['type'], 'integer')
        self.assertEqual(props['facture_hiver']['type'], 'number')

    def test_qualifier_passe_par_le_patch_de_la_fiche(self):
        lead = self._lead()
        resp = auth(self.alice).patch(
            QUALIFIER_LEAD.endpoint.format(id=lead.pk),
            {'facture_hiver': 1400, 'facture_ete': 2300,
             'ete_differente': True, 'decideur': 'conjoint_famille'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual((lead.ete_differente, lead.decideur),
                         (True, 'conjoint_famille'))

    def test_changer_etape_ni_signed_ni_cold_et_update_sans_etape(self):
        enum = CHANGER_ETAPE_LEAD.inputs['properties']['stage']['enum']
        self.assertNotIn(stages.SIGNED, enum)
        self.assertNotIn(stages.COLD, enum)
        self.assertEqual(set(enum) | {stages.SIGNED, stages.COLD},
                         set(stages.STAGES))
        self.assertEqual(CHANGER_ETAPE_LEAD.risk, 'outward')
        self.assertEqual(CHANGER_ETAPE_LEAD.objets, {'id': 'lead'})
        self.assertIsNone(CHANGER_ETAPE_LEAD.lot)
        self.assertNotIn('stage', METTRE_A_JOUR_LEAD.inputs['properties'])
        self.assertIn('relance_date', METTRE_A_JOUR_LEAD.inputs['properties'])
        lead = self._lead()
        resp = auth(self.alice).patch(
            CHANGER_ETAPE_LEAD.endpoint.format(id=lead.pk),
            {'stage': stages.CONTACTED}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_journaliser_ecrit_le_fil_et_demande_confirmation(self):
        self.assertEqual(
            (JOURNALISER_LEAD.risk, JOURNALISER_LEAD.lot,
             JOURNALISER_LEAD.objets),
            ('outward', LOT_COPILOTE, {'id': 'lead'}))
        lead = self._lead()
        resp = auth(self.alice).post(
            JOURNALISER_LEAD.endpoint.format(id=lead.pk),
            {'kind': 'appel', 'body': 'Rappellera lundi.',
             'outcome': 'non_joint'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind='appel').exists())

    def test_creation_confirmee_une_seule_definition_effective(self):
        self.assertEqual(CREER_LEAD.risk, 'outward')
        self.assertEqual(METTRE_A_JOUR_LEAD.risk, 'outward')
        self.assertEqual(NOTER_LEAD.risk, 'internal')


class CrmAssistantVisiteEtWhatsappTest(_CopiloteBase):
    """COP-C6 / COP-C7 — visite, WhatsApp de devis sans piège."""

    def test_declarations_visite(self):
        self.assertEqual(
            (PLANIFIER_VISITE.risk, PLANIFIER_VISITE.carte,
             PLANIFIER_VISITE.lot, PLANIFIER_VISITE.objets),
            ('outward', 'visite', LOT_COPILOTE,
             {'id': 'lead', 'etape': 'touche'}))
        self.assertEqual(
            (MESSAGE_VISITE.risk, MESSAGE_VISITE.carte, MESSAGE_VISITE.lot),
            ('internal', 'wa_message', LOT_COPILOTE))

    def test_planifier_visite_forme_de_la_carte(self):
        import datetime
        from core.dates import aujourd_hui_local
        lead = self._lead()
        jour = aujourd_hui_local() + datetime.timedelta(days=4)
        resp = auth(self.alice).post(
            PLANIFIER_VISITE.endpoint.format(id=lead.pk),
            {'date_prevue': jour.isoformat()}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(set(resp.data), {'visite', 'prochaine_touche'})

    def test_message_de_visite_forme_de_la_carte_wa_message(self):
        lead = self._lead()
        url = MESSAGE_VISITE.endpoint.format(id=lead.pk)
        resp = auth(self.alice).get(url, {'cle': 'visite_proposition'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(_echantillon(
            'assistant_brouillon_suivi.json', 'exemple')))
        self.assertTrue(resp.data['texte'])
        self.assertTrue(resp.data['wa_url'].startswith('https://wa.me/212661'))
        self.assertEqual(resp.data['wa_url'], resp.data['lien_wa_me'])
        darija = auth(self.alice).get(
            url, {'cle': 'visite_proposition', 'langue': 'darija'})
        self.assertEqual(darija.data['langue_servie'], 'darija')
        self.assertEqual(auth(self.alice).get(
            url, {'cle': 'nimporte'}).status_code, 400)
        self.assertEqual(auth(self.alice).get(
            url, {'cle': 'visite_proposition', 'langue': 'klingon'}
        ).status_code, 400)

    def test_message_de_visite_refuse_oppose_hors_portee_et_sans_pii(self):
        oppose = self._lead('Oppose', ne_plus_contacter=True,
                            telephone='0661000999')
        url = MESSAGE_VISITE.endpoint.format(id=oppose.pk)
        self.assertEqual(auth(self.alice).get(
            url, {'cle': 'visite_proposition'}).status_code, 409)
        self.assertEqual(auth(self.bob).get(
            url, {'cle': 'visite_proposition'}).status_code, 404)
        discret = self._lead('Discret', owner=self.discret)
        resp = auth(self.discret).get(
            MESSAGE_VISITE.endpoint.format(id=discret.pk),
            {'cle': 'visite_proposition'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['wa_url'])

    def test_apercu_wa_devis_porte_lead_id_et_devis_ids_sans_commit(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        lead = self._lead(whatsapp='0661000111')
        client = Client.objects.create(company=self.company, nom='Cl WA')
        devis = Devis.objects.create(
            company=self.company, lead=lead, client=client,
            statut='brouillon', reference='DEV-COP-WA-1')
        resp = auth(self.alice).post(
            PREPARER_ENVOI_WHATSAPP.endpoint.format(id=lead.pk),
            {'devis_ids': [devis.pk]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = set(_echantillon('whatsapp_devis_apercu.json')) | {
            'lead_id', 'devis_ids', 'langue'}
        self.assertEqual(set(resp.data), attendu)
        self.assertEqual(resp.data['lead_id'], lead.pk)
        self.assertEqual(resp.data['devis_ids'], [devis.pk])
        # La langue RENDUE (repli : celle du lead, sinon le français), puis
        # celle demandée : la carte la repasse au commit (même texte journalisé).
        self.assertEqual(resp.data['langue'], lead.langue_preferee or 'fr')
        darija = auth(self.alice).post(
            PREPARER_ENVOI_WHATSAPP.endpoint.format(id=lead.pk),
            {'devis_ids': [devis.pk], 'langue': 'darija'}, format='json')
        self.assertEqual((darija.status_code, darija.data['langue']),
                         (200, 'darija'))
        devis.refresh_from_db()
        self.assertEqual((devis.statut, devis.date_envoi), ('brouillon', None))
        self.assertEqual(PREPARER_ENVOI_WHATSAPP.carte, 'wa_devis')
        # Hors portée : 404 ; opposé : 409.
        self.assertEqual(auth(self.bob).post(
            PREPARER_ENVOI_WHATSAPP.endpoint.format(id=lead.pk),
            {'devis_ids': [devis.pk]}, format='json').status_code, 404)

    def test_brouillon_herite_et_lots_de_chaque_action(self):
        self.assertEqual(
            (BROUILLON_SUIVI.lot, BROUILLON_SUIVI.carte),
            (LOT_HERITE, 'wa_message'))
        attendu = {
            'crm.lead.chercher': LOT_COPILOTE,
            'crm.suivi.preparer_touche': LOT_COPILOTE,
            'crm.suivi.proposer_reponse': LOT_COPILOTE,
            'crm.lead.qualifier': LOT_COPILOTE,
            'crm.lead.changer_etape': None,
            'crm.lead.journaliser': LOT_COPILOTE,
            'crm.visite.planifier': LOT_COPILOTE,
            'crm.visite.message': LOT_COPILOTE,
        }
        par_cle = {a.key: a for a in _ACTIONS}
        for cle, lot in attendu.items():
            self.assertEqual(par_cle[cle].lot, lot, cle)
