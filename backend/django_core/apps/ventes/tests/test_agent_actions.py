"""AG4/AG5 — Tests des actions agentiques Ventes.

Couvre :
  - les actions du flux (créer le devis AUTO, éditer ses lignes / remise, PDF
    /proposal, accepter, convertir en BC, générer facture, enregistrer paiement)
    sont dans le catalogue AG1 ;
  - elles sont EXPOSÉES à un responsable/admin (qui porte les codes ERP de
    rattachement) et CACHÉES à un utilisateur en lecture seule ;
  - les niveaux de risque sont EXACTS (internal / outward / irreversible) — c'est
    ce qui pilote le garde-fou propose→confirm ;
  - ``company`` n'apparaît JAMAIS dans le schéma ``inputs`` (forcée serveur) ;
  - un devis créé via l'appel RELAYÉ (depuis un lead) force la société serveur ;
  - un paiement enregistré via l'endpoint relayé écrit un Paiement scopé société,
    avec isolation inter-tenant (on ne peut pas encaisser sur la facture d'une
    autre société).

Run :
    python manage.py test apps.ventes.tests.test_agent_actions -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import (
    Devis, Facture, LigneFacture, Paiement,
)
from apps.ventes.agent_actions import (
    CREER_AUTO,
    GENERER_PDF_DEVIS,
    LIGNE_AJOUTER,
    LIGNE_MODIFIER,
    LIGNE_SUPPRIMER,
    REMISE_DEVIS,
    ACCEPTER_DEVIS,
    CONVERTIR_EN_BON_COMMANDE,
    GENERER_FACTURE,
    ENREGISTRER_PAIEMENT,
    ENVOYER_EMAIL_DEVIS,
    EXPLIQUER_DEVIS,
    LIGNES_DEVIS,
    CHERCHER_DEVIS,
    VENTES_ACTIONS,
    VENTES_ACTIONS_COPILOTE,
    register_ventes_actions,
)
from apps.agent.registry import (
    all_actions, for_user, RISK_INTERNAL, RISK_OUTWARD, RISK_IRREVERSIBLE,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class KwcDesOptionsArrondiTest(SimpleTestCase):
    """T4-X6-001 — le kWc servi par option (bandeau « Devis créé ») suit LA
    règle d'arrondi du PDF (``premium_base.kwc_str``) : 49 × 715 W = 35,035
    s'écrit 35,03 partout, jamais 35,04 sur le bandeau."""

    def test_meme_arrondi_que_le_pdf(self):
        from apps.ventes.quote_engine.premium_base import kwc_str
        from apps.ventes.selectors_assistant import _kwc_arrondi
        for kwc in (49 * 0.715, 51 * 0.715, 14 * 0.715, 7.1, 130.125):
            with self.subTest(kwc=kwc):
                self.assertEqual(kwc_str(_kwc_arrondi(kwc)), kwc_str(kwc))
                self.assertEqual(_kwc_arrondi(kwc), round(kwc, 2))
        self.assertEqual(_kwc_arrondi(49 * 0.715), 35.03)
        self.assertIsNone(_kwc_arrondi(None))


class PanneauParDefautPhraseTest(SimpleTestCase):
    """D-ACAL-169 — la phrase du panneau omis ne donne plus un wattage figé : le choix automatique
    suit le panneau par défaut de la société (D-ACAL-169), sinon le catalogue."""

    def test_panneau_omis_ne_dit_plus_un_wattage_fige(self):
        from apps.ventes.agent_actions import COMPOSER_DEVIS
        phrase = COMPOSER_DEVIS.inputs['properties']['panneau_produit_id']['description']
        self.assertIn('panneau par défaut de la société', phrase)
        self.assertNotRegex(phrase, r'\d+\s*Wc')


class VentesAgentCatalogueTest(TestCase):
    """Les actions Ventes sont au catalogue et filtrées par permission ERP."""

    def setUp(self):
        register_ventes_actions()  # idempotent (ready() les pose déjà)
        self.company = Company.objects.create(nom='AG45 Co', slug='ag45-co')
        # Responsable : porte les codes de rattachement (COP-G2 : la remise suit
        # ``ventes_modifier``, l'encaissement ``encaisser`` — gardes des routes).
        self.resp_role = Role.objects.create(
            company=self.company, nom='Responsable Ventes',
            permissions=[
                'ventes_voir', 'ventes_creer', 'ventes_modifier', 'ventes_pdf',
                'ventes_valider', 'encaisser',
            ])
        self.resp = User.objects.create_user(
            username='ag45_resp', password='x', role=self.resp_role,
            company=self.company)
        # Lecture seule : ne porte que ventes_voir → ne voit aucune action.
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['ventes_voir'])
        self.readonly = User.objects.create_user(
            username='ag45_ro', password='x', role=self.readonly_role,
            company=self.company)

    def test_all_actions_registered(self):
        keys = {a.key for a in all_actions()}
        for action in VENTES_ACTIONS:
            self.assertIn(action.key, keys, action.key)

    def test_responsable_sees_all_quote_actions(self):
        keys = {a.key for a in for_user(self.resp)}
        for action in VENTES_ACTIONS:
            self.assertIn(action.key, keys, action.key)

    def test_readonly_user_sees_no_quote_actions(self):
        keys = {a.key for a in for_user(self.readonly)}
        for action in VENTES_ACTIONS:
            self.assertNotIn(action.key, keys, action.key)

    def test_required_permissions(self):
        self.assertEqual(CREER_AUTO.required_permission, 'ventes_creer')
        self.assertEqual(GENERER_PDF_DEVIS.required_permission, 'ventes_pdf')
        for action in (ACCEPTER_DEVIS, CONVERTIR_EN_BON_COMMANDE):
            self.assertEqual(
                action.required_permission, 'ventes_valider', action.key)
        # REP6 — émettre une tranche : contrôle ``PeutEncaisser`` du CORPS.
        self.assertEqual(GENERER_FACTURE.required_permission, 'encaisser')
        # COP-G2 — aligné sur les gardes des routes (test de parité de l'agent).
        self.assertEqual(ENREGISTRER_PAIEMENT.required_permission, 'encaisser')
        self.assertEqual(REMISE_DEVIS.required_permission, 'ventes_modifier')
        # AIC99 — lecture des études / envoi de l'écran (gardes des routes).
        self.assertEqual(EXPLIQUER_DEVIS.required_permission, 'ventes_voir')
        self.assertEqual(ENVOYER_EMAIL_DEVIS.required_permission, 'ventes_modifier')

    def test_risk_levels_exact(self):
        # AG4
        self.assertEqual(CREER_AUTO.risk, RISK_INTERNAL)
        self.assertEqual(GENERER_PDF_DEVIS.risk, RISK_INTERNAL)
        # COP-G3 — tout ce qui CHANGE un montant du devis passe par une
        # proposition à confirmer (remise, prix/quantité de ligne, ajout, retrait).
        for action in (REMISE_DEVIS, LIGNE_AJOUTER, LIGNE_MODIFIER,
                       LIGNE_SUPPRIMER):
            self.assertEqual(action.risk, RISK_OUTWARD, action.key)
            self.assertTrue(action.confirm_summary, action.key)
        self.assertEqual(ACCEPTER_DEVIS.risk, RISK_OUTWARD)
        # AG5
        self.assertEqual(CONVERTIR_EN_BON_COMMANDE.risk, RISK_OUTWARD)
        self.assertEqual(GENERER_FACTURE.risk, RISK_IRREVERSIBLE)
        self.assertEqual(ENREGISTRER_PAIEMENT.risk, RISK_IRREVERSIBLE)
        # AIC99 — expliquer LIT ; l'e-mail part chez le client : à confirmer.
        self.assertEqual(EXPLIQUER_DEVIS.risk, RISK_INTERNAL)
        self.assertEqual(ENVOYER_EMAIL_DEVIS.risk, RISK_OUTWARD)
        self.assertTrue(ENVOYER_EMAIL_DEVIS.confirm_summary)

    def test_expliquer_et_envoi_email_declares(self):
        """AIC99 — deux actions du lot copilote sur les routes EXISTANTES :
        ``expliquer`` lit l'étude du marché (economie, economie-ci,
        economie-pompage, etude-params ; jamais un prix d'achat) ;
        ``envoyer_email`` est la route de l'écran en proposition à confirmer
        (``objets`` nomme le devis). Copilote éteint : absentes du catalogue."""
        from django.urls import resolve
        from apps.agent.registry import LOT_COPILOTE
        cles = {a.key for a in all_actions()}
        # COP2 — chaque action du lot nomme les objets qu'elle désigne ; la
        # recherche catalogue n'en désigne aucun.
        objets_attendus = {
            'ventes.devis.expliquer': {'id': 'devis'},
            'ventes.devis.envoyer_email': {'id': 'devis'},
            'ventes.catalogue.chercher': {},
            'ventes.devis.composer': {'lead': 'lead', 'client': 'client'},
            'ventes.devis.lignes': {'id': 'devis'},
            # Copilote vague 2 (lane VAD).
            'ventes.vente.etat': {'id': 'devis'},
            'ventes.impayes.lister': {'client': 'client'},
            'ventes.facture.chercher': {'client': 'client'},
            'ventes.devis.prolonger': {'id': 'devis'},
            'ventes.devis.refuser': {'id': 'devis'},
            'ventes.devis.reviser': {'id': 'devis'},
            'ventes.devis.taille_apercu': {'id': 'devis'},
            'ventes.devis.taille': {'id': 'devis'},
            'ventes.facture.whatsapp_relance': {'id': 'facture'},
            'ventes.vente.facturer': {'id': 'devis'},
            'ventes.devis.ligne_remplacer': {'id': 'devis'},
            # L4 (21/11/2026) — recherche de devis : ne désigne aucun objet.
            'ventes.devis.chercher': {},
        }
        for action in VENTES_ACTIONS_COPILOTE:
            self.assertIn(action.key, cles)
            self.assertEqual((action.lot, action.objets),
                             (LOT_COPILOTE, objets_attendus[action.key]), action.key)
            self.assertNotIn('company', action.inputs['properties'], action.key)
            for interdit in ('prix_achat', 'marge'):
                self.assertNotIn(interdit, (action.description + str(action.inputs)).lower())
        blocs = EXPLIQUER_DEVIS.inputs['properties']['bloc']['enum']
        self.assertEqual(set(blocs), {'economie', 'economie-ci', 'economie-pompage', 'etude-params'})
        for bloc in blocs:  # chaque bloc est une route existante (aucune route neuve)
            chemin = EXPLIQUER_DEVIS.endpoint.format(id=1, bloc=bloc)
            self.assertEqual(resolve(chemin).func.actions.get('get'),
                             bloc.replace('-', '_'), chemin)
        self.assertEqual(EXPLIQUER_DEVIS.method, 'GET')
        self.assertEqual(
            (ENVOYER_EMAIL_DEVIS.endpoint, ENVOYER_EMAIL_DEVIS.method),
            ('/api/django/ventes/devis/{id}/envoyer-email/', 'POST'))
        self.assertNotIn('corps', ENVOYER_EMAIL_DEVIS.inputs['properties'])
        self.assertNotIn('sujet', ENVOYER_EMAIL_DEVIS.inputs['properties'])
        with self.settings(ASSISTANT_COPILOTE='aucun'):
            vus = {a.key for a in for_user(self.resp)}
        self.assertFalse(vus & {a.key for a in VENTES_ACTIONS_COPILOTE})
        with self.settings(ASSISTANT_COPILOTE='tous'):
            vus = {a.key for a in for_user(self.resp)}
        self.assertLessEqual({a.key for a in VENTES_ACTIONS_COPILOTE}, vus)

    def test_rep6_emission_irreversible_herite_et_modes_exacts(self):
        """REP6 — ``generer_facture`` ÉMET la tranche avec son numéro légal
        (irréversible, l'aperçu le dit) ; lot ``herite`` : copilote éteint
        seulement ; l'Admin Ventes (``ventes_valider`` sans ``encaisser``)
        ne la voit plus. Les modes de paiement sont ceux du modèle ;
        ``composer`` ne fait jamais une V2."""
        from apps.agent.registry import LOT_HERITE
        self.assertEqual(GENERER_FACTURE.lot, LOT_HERITE)
        self.assertIn('avoir', GENERER_FACTURE.label)
        self.assertIn('numéro légal', GENERER_FACTURE.confirm_summary)
        admin_ventes = User.objects.create_user(
            username='ag45_av', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Admin Ventes',
                permissions=['ventes_voir', 'ventes_creer', 'ventes_valider']))
        self.assertNotIn(GENERER_FACTURE.key,
                         {a.key for a in for_user(admin_ventes)})
        with self.settings(ASSISTANT_COPILOTE='tous'):
            self.assertNotIn(GENERER_FACTURE.key,
                             {a.key for a in for_user(self.resp)})
        self.assertIn(GENERER_FACTURE.key, {a.key for a in for_user(self.resp)})
        mode = ENREGISTRER_PAIEMENT.inputs['properties']['mode']
        self.assertEqual(mode['enum'], list(Paiement.Mode.values))
        self.assertNotIn('è', mode['description'])
        from apps.ventes.agent_actions import COMPOSER_DEVIS
        self.assertIn('V2', COMPOSER_DEVIS.description)

    def test_inputs_never_include_company(self):
        for action in VENTES_ACTIONS:
            props = action.inputs.get('properties', {})
            self.assertNotIn('company', props, action.key)

    def test_creer_auto_accepts_lead(self):
        # Le client est résolu serveur depuis le lead → lead doit être un input.
        self.assertIn('lead', CREER_AUTO.inputs['properties'])

    def test_creer_auto_dit_vrai_et_declare_les_entrees_de_la_route(self):
        """COP-G3 — la route sert les QUATRE marchés (selon le type du lead) et
        accepte ``target_kwc`` / ``scenario`` : l'action les déclare avec les
        valeurs que la route accepte, rien d'autre que le corps publié."""
        from apps.ventes.domain.creation_auto import SCENARIOS_DEMANDABLES
        from apps.ventes.views.openapi_docs import (
            AutoDevisRequest, TARGET_KWC_MAX)
        props = CREER_AUTO.inputs['properties']
        self.assertLessEqual(set(props), set(AutoDevisRequest.fields))
        self.assertEqual(props['target_kwc']['type'], 'number')
        self.assertIn(str(TARGET_KWC_MAX).replace('_', ''),
                      props['target_kwc']['description'].replace(' ', ''))
        self.assertEqual(tuple(props['scenario']['enum']), SCENARIOS_DEMANDABLES)
        for marche in ('résidentiel', 'commercial', 'industriel', 'agricole'):
            self.assertIn(marche, CREER_AUTO.description)
        self.assertNotIn('uniquement', CREER_AUTO.description.lower())

    def test_composer_kit_impose_lot_copilote_et_corps_publie(self):
        """COP2-V4 — ``ventes.devis.composer`` : la route ``devis/auto/`` au
        kit imposé, lot copilote, carte « devis créé », entrées = sous-ensemble
        du corps publié, ni remise ni puissance cible ; hors ``VENTES_ACTIONS``
        (copilote éteint = catalogue identique)."""
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import COMPOSER_DEVIS
        from apps.ventes.views.openapi_docs import AutoDevisRequest
        props = COMPOSER_DEVIS.inputs['properties']
        self.assertLessEqual(set(props), set(AutoDevisRequest.fields))
        self.assertNotIn('remise_globale', props)
        self.assertNotIn('target_kwc', props)
        self.assertEqual((COMPOSER_DEVIS.endpoint, COMPOSER_DEVIS.method),
                         (CREER_AUTO.endpoint, 'POST'))
        self.assertEqual((COMPOSER_DEVIS.lot, COMPOSER_DEVIS.risk,
                          COMPOSER_DEVIS.carte,
                          COMPOSER_DEVIS.required_permission),
                         (LOT_COPILOTE, RISK_INTERNAL, 'devis_cree',
                          'ventes_creer'))
        self.assertNotIn(COMPOSER_DEVIS, VENTES_ACTIONS)
        self.assertNotIn('ventes.devis.composer', CREER_AUTO.description)
        desc = COMPOSER_DEVIS.description
        self.assertLessEqual(len(desc), 600)
        for section in ('Sert à :', 'Ne pas utiliser pour :', 'Exemple :',
                        'Résultat :'):
            self.assertIn(section, desc)
        self.assertIn('10 panneaux solaires avec onduleur triphasé', desc)

    def test_pdf_action_ses_options_arrivent_au_moteur(self):
        """COP-G3 — carte « document » (le relais rend le lien /proposal) ; CHAQUE
        option déclarée par l'action est lue par la route et arrive au moteur
        (route réelle, moteur de rendu simulé). ``payment_mode`` et
        ``custom_acompte`` ne l'étaient jamais : ils ne sont plus déclarés."""
        from unittest import mock
        self.assertEqual(GENERER_PDF_DEVIS.carte, 'document')
        self.assertEqual(GENERER_PDF_DEVIS.method, 'GET')
        envoyees = {'pdf_mode': 'onepage', 'include_etude': 'true',
                    'include_calepinage': 'true', 'langue': 'en',
                    'show_monthly': 'false', 'devis_final': 'true'}
        self.assertEqual(
            set(GENERER_PDF_DEVIS.inputs['properties']) - {'id'}, set(envoyees))
        client = Client.objects.create(
            company=self.company, nom='PDF', email='pdf@example.com',
            telephone='+212600000012', adresse='Rabat')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{self.company.id}009',
            client=client, taux_tva=Decimal('20.00'))
        with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                        return_value='cle') as moteur, \
                mock.patch('apps.ventes.utils.pdf.download_pdf',
                           return_value=b'%PDF-1.4 essai'):
            resp = auth(self.resp).get(
                GENERER_PDF_DEVIS.endpoint.format(id=devis.pk), envoyees)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(moteur.call_args.args[0], devis.pk)
        options = moteur.call_args.args[1]
        lues = ('pdf_mode', 'include_etude', 'include_calepinage',
                'show_monthly', 'devis_final', 'langue_sortie')
        self.assertEqual({cle: options.get(cle) for cle in lues}, {
            'pdf_mode': 'onepage', 'include_etude': True,
            'include_calepinage': True, 'show_monthly': False,
            'devis_final': True, 'langue_sortie': 'en'})
        # Aucune autre action du flux ne rend un PDF : seule la lecture de
        # /proposal porte la carte « document ». COP2-V4 — la création
        # automatique se rend en carte « devis créé » (écran seulement).
        self.assertEqual(
            {a.key: a.carte for a in VENTES_ACTIONS if a.carte},
            {GENERER_PDF_DEVIS.key: 'document', CREER_AUTO.key: 'devis_cree'})

    def test_objets_nommes_pour_chaque_identifiant_d_objet(self):
        """COP-G3 — toute entrée qui désigne un devis, une facture, un lead ou un
        client est déclarée dans ``objets`` (aperçu nommé) ; seule la LIGNE de
        devis n'a pas de type."""
        attendu = {
            'ventes.devis.creer_auto': {'lead': 'lead', 'client': 'client'},
            # 20/11/2026 — les trois actions de ligne visent le DEVIS par
            # ``id`` (route ``devis/{id}/assistant-lignes/...``).
            'ventes.devis.ligne_ajouter': {'id': 'devis'},
            'ventes.devis.ligne_modifier': {'id': 'devis'},
            'ventes.devis.ligne_supprimer': {'id': 'devis'},
            'ventes.devis.remise': {'id': 'devis'},
            'ventes.devis.generer_pdf': {'id': 'devis'},
            'ventes.devis.accepter': {'id': 'devis'},
            'ventes.devis.convertir_bc': {'id': 'devis'},
            'ventes.devis.generer_facture': {'id': 'devis'},
            'ventes.facture.enregistrer_paiement': {'id': 'facture'},
        }
        for action in VENTES_ACTIONS:
            self.assertEqual(action.objets, attendu.get(action.key, {}), action.key)
            self.assertLessEqual(set(action.objets),
                                 set(action.inputs['properties']), action.key)

    def test_catalogue_endpoint_lists_actions_for_responsable(self):
        api = auth(self.resp)
        resp = api.get('/api/django/agent/actions/')
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        for action in VENTES_ACTIONS:
            self.assertIn(action.key, keys, action.key)

    def test_descriptions_quatre_sections_regle_4_et_sans_prix_achat(self):
        # AIC40 — le modèle choisit ses outils sur ces textes.
        ventes = {a.key: a for a in for_user(self.resp)
                  if a.key in {v.key for v in VENTES_ACTIONS}}
        self.assertEqual(len(ventes), 10)
        sections = ('Sert à :', 'Ne pas utiliser pour :', 'Exemple :', 'Résultat :')
        for key, action in ventes.items():
            desc = action.description
            self.assertLessEqual(len(desc), 600, key)
            for section in sections:
                self.assertIn(section, desc, f'{key} : {section}')
            self.assertNotIn('prix_achat', desc, key)
            self.assertNotIn('marge', desc.lower(), key)
            # COP-G3 — ni dans les entrées déclarées (clés et descriptions).
            entrees = str(action.inputs).lower()
            self.assertNotIn('prix_achat', entrees, key)
            self.assertNotIn('marge', entrees, key)
        pdf = ventes[GENERER_PDF_DEVIS.key].description
        self.assertIn('/proposal', pdf)
        self.assertIn('règle #4', pdf)
        # D-COP-5 — facture et paiement gardent la carte ; accepter et convertir
        # sont directs (carte seulement après une lecture de données, B3) et ne
        # se font que sur une demande claire.
        for action in (GENERER_FACTURE, ENREGISTRER_PAIEMENT):
            self.assertIn(
                'change un statut : proposition puis confirmation obligatoire',
                ventes[action.key].description, action.key)
        for action in (ACCEPTER_DEVIS, CONVERTIR_EN_BON_COMMANDE):
            self.assertIn('change un statut : seulement sur', ventes[action.key].description,
                          action.key)
        for action in (ACCEPTER_DEVIS, CONVERTIR_EN_BON_COMMANDE,
                       GENERER_FACTURE, ENREGISTRER_PAIEMENT):
            self.assertTrue(ventes[action.key].confirm_summary, action.key)

    def test_register_is_idempotent(self):
        before = len(all_actions())
        register_ventes_actions()
        register_ventes_actions()
        self.assertEqual(len(all_actions()), before)


class CreerAutoRelayedCallTest(TestCase):
    """Un devis créé via l'auto-devis relayé (depuis un lead) force la société et
    n'est JAMAIS vide quand le profil lead est dimensionnable."""

    def _seed_catalogue(self, company):
        def mk(nom, sku, prix):
            Produit.objects.create(
                company=company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)
        mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
        mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)
        # QJR82 (30/08/2026) — l'étape `verifier` du pipeline refuse désormais,
        # AVANT toute écriture, une composition « Les deux » sans onduleur
        # hybride tarifé (le même refus FR que le chemin 3D). Le scénario par
        # défaut de l'auto-devis compose les deux options : le catalogue de la
        # fixture doit donc porter un hybride avec prix, comme un vrai
        # catalogue — sans lui le 201 attendu ici devient un 422 légitime.
        mk('Onduleur hybride Deye 5kW Monophasé', f'ONDH-{company.pk}', 16000)
        # ... et une batterie tarifée, pour la même raison (le refus QJR82 se
        # déroule composant par composant : hybride, puis batterie).
        mk('Batterie Dyness 5.12 kWh', f'BAT-{company.pk}', 9500)

    def setUp(self):
        self.company = Company.objects.create(nom='AG45 Relay', slug='ag45-relay')
        self.other = Company.objects.create(nom='AG45 Other', slug='ag45-other')
        self.user = User.objects.create_user(
            username='ag45_relay', password='x', role_legacy='responsable',
            company=self.company)
        self._seed_catalogue(self.company)

    def test_auto_from_lead_forces_company_and_is_not_empty(self):
        lead = Lead.objects.create(
            company=self.company, nom='Relay', prenom='Lead',
            telephone='+212600000010', ville='Casablanca',
            facture_hiver=1800, ete_differente=False)
        api = auth(self.user)
        resp = api.post(CREER_AUTO.endpoint, {
            'lead': lead.id,
            'taux_tva': '20.00',
            'remise_globale': '0',
            # Tentative d'injection : la société est ignorée côté serveur.
            'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        # Société forcée à celle du caller (jamais celle envoyée dans le corps).
        self.assertEqual(devis.company_id, self.company.id)
        # Client résolu serveur depuis le lead (sans doublon).
        self.assertEqual(devis.lead_id, lead.id)
        self.assertIsNotNone(devis.client_id)
        self.assertEqual(devis.client.company_id, self.company.id)
        # JAMAIS un devis vide : l'auto-devis a dimensionné des lignes.
        self.assertGreater(devis.lignes.count(), 0)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_auto_missing_data_returns_409_no_devis(self):
        # CI #1003 — donnée de la fiche manquante sur un corps valide = refus
        # d'ÉTAT, 409 (ENF11, /devis/auto/ publie 409 ErreurComposition).
        lead = Lead.objects.create(
            company=self.company, nom='Vide', prenom='Lead')
        api = auth(self.user)
        resp = api.post(
            CREER_AUTO.endpoint, {'lead': lead.id}, format='json')
        # CI #997 fuzz (3dc8d2879) : donnée de la fiche manquante = refus
        # d'ÉTAT publié en 409 par devis/auto/ (ErreurComposition).
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data.get('field'), 'facture_hiver')
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)


class EnregistrerPaiementRelayedCallTest(TestCase):
    """L'enregistrement d'un paiement écrit un Paiement scopé société + isole
    les tenants."""

    def _facture(self, company, client, total_ttc=Decimal('1200')):
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{MONTH}-{company.id}001',
            client=client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'))
        produit = Produit.objects.create(
            company=company, nom='Panneau', sku=f'PV-{company.id}',
            prix_vente=Decimal('1000'), quantite_stock=100)
        facture = Facture.objects.create(
            company=company, reference=f'FAC-{MONTH}-{company.id}001',
            client=client, devis=devis, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return facture

    def setUp(self):
        self.company = Company.objects.create(nom='AG45 Pay', slug='ag45-pay')
        self.other = Company.objects.create(
            nom='AG45 PayOther', slug='ag45-pay-other')
        self.user = User.objects.create_user(
            username='ag45_pay', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Payeur', email='p@example.com',
            telephone='+212600000011', adresse='Casablanca')
        self.facture = self._facture(self.company, self.client_obj)

    def test_payment_writes_company_scoped_paiement(self):
        api = auth(self.user)
        endpoint = ENREGISTRER_PAIEMENT.endpoint.format(id=self.facture.id)
        resp = api.post(endpoint, {
            'montant': '300.00',
            'date_paiement': timezone.now().date().isoformat(),
            'mode': Paiement.Mode.VIREMENT,
            # Injection : la société est ignorée côté serveur.
            'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = Paiement.objects.get(facture=self.facture)
        # Société forcée = celle de la facture (jamais celle du corps).
        self.assertEqual(paiement.company_id, self.company.id)
        self.assertEqual(paiement.montant, Decimal('300.00'))
        self.assertEqual(paiement.created_by_id, self.user.id)

    def test_zero_amount_rejected(self):
        api = auth(self.user)
        endpoint = ENREGISTRER_PAIEMENT.endpoint.format(id=self.facture.id)
        resp = api.post(endpoint, {
            'montant': '0',
            'date_paiement': timezone.now().date().isoformat(),
            'mode': Paiement.Mode.ESPECES,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(Paiement.objects.filter(facture=self.facture).exists())

    def test_cross_tenant_payment_blocked(self):
        # Une facture d'une AUTRE société est invisible (404) — pas d'encaissement
        # cross-tenant possible via l'endpoint relayé.
        other_client = Client.objects.create(
            company=self.other, nom='Autre', email='o@example.com',
            telephone='+212600000012', adresse='Rabat')
        foreign_facture = self._facture(self.other, other_client)
        api = auth(self.user)
        endpoint = ENREGISTRER_PAIEMENT.endpoint.format(id=foreign_facture.id)
        resp = api.post(endpoint, {
            'montant': '100.00',
            'date_paiement': timezone.now().date().isoformat(),
            'mode': Paiement.Mode.ESPECES,
        }, format='json')
        self.assertEqual(resp.status_code, 404, getattr(resp, 'data', resp))
        self.assertFalse(
            Paiement.objects.filter(facture=foreign_facture).exists())


class LignesAssistantTest(TestCase):
    """COP2-V5 — ``GET devis/<pk>/lignes-assistant/`` : forme du contrat
    ``assistant_devis_lignes.json``, portée de ``get_object`` (société +
    rôle), prix TTC seulement — jamais un prix d'achat."""

    def setUp(self):
        from apps.ventes.models import LigneDevis
        self.company = Company.objects.create(nom='COP2 Lg', slug='cop2-lg')
        self.autre = Company.objects.create(nom='COP2 Lg2', slug='cop2-lg2')
        self.user = User.objects.create_user(
            username='cop2_lg', password='x', role_legacy='responsable',
            company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Lg', email='lg@example.com',
            telephone='+212600000013', adresse='Rabat')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{self.company.id}451',
            client=client, taux_tva=Decimal('20.00'), created_by=self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie Dyness 5 kWh', sku='LG-BAT',
            prix_vente=Decimal('10000'), prix_achat=Decimal('777.77'))
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation='Batterie Dyness 5 kWh', quantite=Decimal('2'),
            prix_unitaire=Decimal('10000'), ordre=0)

    def test_forme_du_contrat_ttc_et_jamais_d_achat(self):
        url = LIGNES_DEVIS.endpoint.format(id=self.devis.pk)
        resp = auth(self.user).get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), {'devis_id', 'reference', 'statut',
                                          'total_ttc', 'lignes', 'options'})
        # D-COP-5 — le total option par option, lisible en une lecture.
        self.assertEqual([o['total_ttc'] for o in resp.data['options']], ['24000.00'])
        ligne = resp.data['lignes'][0]
        self.assertEqual(set(ligne), {
            'ligne_id', 'produit_id', 'designation', 'quantite',
            'prix_unitaire_ttc', 'total_ttc', 'variante'})
        self.assertEqual((ligne['ligne_id'], ligne['produit_id'],
                          ligne['quantite']), (self.ligne.pk, self.produit.pk, 2))
        self.assertEqual(ligne['prix_unitaire_ttc'], '12000.00')
        self.assertEqual(ligne['total_ttc'], '24000.00')
        texte = str(resp.data).lower()
        self.assertNotIn('777.77', texte)
        self.assertNotIn('prix_achat', texte)

    def test_total_de_ligne_arrondi_comme_le_prix_ttc_affiche(self):
        """VAD7 — 8 × 1 400,00 TTC (HT 1 166,67) = 11 200,00, pas 11 200,03 :
        le total part du prix unitaire TTC arrondi, celui qui est affiché."""
        from apps.ventes.models import LigneDevis
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation='Panneau Canadien Solar 710W', quantite=Decimal('8'),
            prix_unitaire=Decimal('1166.67'), ordre=1)
        resp = auth(self.user).get(LIGNES_DEVIS.endpoint.format(id=self.devis.pk))
        panneau = [li for li in resp.data['lignes']
                   if li['designation'].startswith('Panneau')][0]
        self.assertEqual((panneau['prix_unitaire_ttc'], panneau['total_ttc']),
                         ('1400.00', '11200.00'))

    def test_devis_d_une_autre_societe_404(self):
        autre_user = User.objects.create_user(
            username='cop2_lg_autre', password='x', role_legacy='responsable',
            company=self.autre)
        resp = auth(autre_user).get(
            LIGNES_DEVIS.endpoint.format(id=self.devis.pk))
        self.assertEqual(resp.status_code, 404)

    def test_action_lot_copilote_garde_reelle(self):
        from apps.agent.registry import LOT_COPILOTE
        self.assertEqual((LIGNES_DEVIS.lot, LIGNES_DEVIS.risk,
                          LIGNES_DEVIS.required_permission, LIGNES_DEVIS.objets),
                         (LOT_COPILOTE, RISK_INTERNAL, 'ventes_voir',
                          {'id': 'devis'}))


class CatalogueAssistantTest(TestCase):
    """COP2-V1/V2 — ``GET ventes/assistant/catalogue/`` : le classement du
    résolveur unique (celui de la composition imposée), des bornes publiées,
    jamais un prix d'achat ni une quantité en stock — même pour un
    superutilisateur."""

    URL = '/api/django/ventes/assistant/catalogue/'

    def setUp(self):
        self.company = Company.objects.create(nom='COP2 Cat', slug='cop2-cat')
        self.autre = Company.objects.create(nom='COP2 Autre', slug='cop2-autre')
        self.admin = User.objects.create_user(
            username='cop2_cat_su', password='x', company=self.company,
            is_superuser=True, is_staff=True)
        self.lecture = User.objects.create_user(
            username='cop2_cat_ro', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Ventes RO',
                                     permissions=['ventes_voir']))

        def mk(nom, prix, stock=10, company=None, **extra):
            return Produit.objects.create(
                company=company or self.company, nom=nom,
                sku='C2-%s' % Produit.objects.count(),
                prix_vente=Decimal(prix), prix_achat=Decimal('123.45'),
                quantite_stock=stock, **extra)
        self.panneau = mk('Panneau Canadien Solar 710W', '1400')
        mk('Panneau Jinko 710W', '1300')
        self.hybride = mk('Onduleur hybride Deye 10kW Triphasé', '28000',
                          marque='Deye')
        mk('Onduleur réseau Huawei 10kW Triphasé', '20000')
        self.batterie = mk('Batterie Dyness 5 kWh', '14000')
        mk('Batterie Dyness 10 kWh', '26000', stock=0)
        mk('Batterie Lithium 5 kWh', '15500', company=self.autre)
        mk('Onduleur hybride Deye 10kW Triphasé sans prix', '0')

    def _get(self, user, **params):
        return auth(user).get(self.URL, params)

    def test_batterie_5_kwh_unique_et_jamais_d_achat_meme_superuser(self):
        resp = self._get(self.admin, genre='batterie', kwh=5)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), {'q', 'genre', 'total', 'limite',
                                          'statut', 'raison', 'lignes'})
        self.assertEqual(resp.data['statut'], 'unique')
        self.assertEqual([li['produit_id'] for li in resp.data['lignes']],
                         [self.batterie.pk])
        ligne = resp.data['lignes'][0]
        self.assertEqual(set(ligne), {
            'produit_id', 'nom', 'marque', 'genre', 'kw', 'kwh', 'wc',
            'phase', 'famille', 'prix_ttc', 'en_stock'})
        self.assertIs(ligne['en_stock'], True)
        texte = str(resp.data).lower()
        for interdit in ('prix_achat', 'marge', '123.45', 'quantite'):
            self.assertNotIn(interdit, texte)

    def test_onduleur_deux_familles_ambigu_puis_hybride_unique(self):
        ambigu = self._get(self.lecture, genre='onduleur', kw=10,
                           phase='triphase')
        self.assertEqual(ambigu.status_code, 200, ambigu.data)
        self.assertEqual(ambigu.data['statut'], 'ambigu')
        unique = self._get(self.lecture, genre='onduleur', kw=10,
                           phase='triphase', famille='hybride')
        self.assertEqual(unique.data['statut'], 'unique')
        self.assertEqual(unique.data['lignes'][0]['produit_id'],
                         self.hybride.pk)
        self.assertEqual(unique.data['lignes'][0]['famille'], 'hybride')
        self.assertEqual(unique.data['lignes'][0]['phase'], 'triphase')

    def test_panneau_canadien_passe_devant_comme_le_compositeur(self):
        resp = self._get(self.lecture, genre='panneau', wc=710)
        self.assertEqual(resp.data['statut'], 'unique')
        self.assertEqual(resp.data['lignes'][0]['produit_id'], self.panneau.pk)

    def test_batterie_7_kwh_aucun_nomme_les_tailles_proches(self):
        resp = self._get(self.lecture, genre='batterie', kwh=7)
        self.assertEqual(resp.data['statut'], 'aucun')
        self.assertEqual(resp.data['lignes'], [])
        self.assertIn('5 kWh', resp.data['raison'])

    def test_autre_societe_et_sans_prix_jamais_servis(self):
        resp = self._get(self.lecture, limite=25)
        noms = [li['nom'] for li in resp.data['lignes']]
        self.assertNotIn('Batterie Lithium 5 kWh', noms)
        self.assertFalse(any('sans prix' in n for n in noms))

    def test_parametre_inconnu_ou_hors_borne_400_nomme(self):
        for params, champ in (({'inconnu': 1}, 'inconnu'),
                              ({'kw': 500}, 'kw'), ({'limite': 99}, 'limite'),
                              ({'genre': 'cable'}, 'genre')):
            with self.subTest(params=params):
                resp = self._get(self.lecture, **params)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(champ, str(resp.data))

    def test_action_chercher_lot_copilote_et_garde_reelle(self):
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import CHERCHER_CATALOGUE
        self.assertEqual((CHERCHER_CATALOGUE.lot, CHERCHER_CATALOGUE.risk,
                          CHERCHER_CATALOGUE.required_permission),
                         (LOT_COPILOTE, RISK_INTERNAL, 'ventes_voir'))
        self.assertLessEqual(len(CHERCHER_CATALOGUE.description), 600)
        for section in ('Sert à :', 'Ne pas utiliser pour :', 'Exemple :',
                        'Résultat :'):
            self.assertIn(section, CHERCHER_CATALOGUE.description)


def _exemple_contrat(nom, cle='exemple'):
    """L'exemple d'un contrat ``apps/ventes/contract_samples/<nom>`` (donnée
    JSON partagée avec l'écran — jamais une source Python lue comme texte)."""
    import json
    from pathlib import Path
    chemin = Path(__file__).resolve().parent.parent / 'contract_samples' / nom
    return json.loads(chemin.read_text(encoding='utf-8'))[cle]


class _BaseVenteAssistant(TestCase):
    """Copilote vague 2 (lane VAD) — une société, un responsable ventes, un
    devis ENVOYÉ d'un client au téléphone connu (qui ne doit jamais sortir)."""

    TEL = '+212600004242'

    def setUp(self):
        self.company = Company.objects.create(nom='VAD Co', slug='vad-co')
        self.autre = Company.objects.create(nom='VAD Autre', slug='vad-autre')
        self.user = User.objects.create_user(
            username='vad_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_ = Client.objects.create(
            company=self.company, nom='Lahlou', prenom='Driss',
            email='lahlou@example.com', telephone=self.TEL, adresse='Rabat')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{self.company.id}502',
            client=self.client_, taux_tva=Decimal('20.00'),
            created_by=self.user, statut=Devis.Statut.ENVOYE)

    def _hors_societe(self):
        return User.objects.create_user(
            username='vad_autre', password='x', role_legacy='responsable',
            company=self.autre)

    def _facture(self, rang, *, ht='1000', statut=Facture.Statut.EMISE,
                 retard_jours=10, **extra):
        """Une facture de ``self.devis`` (TTC = HT × 1,2), échue de
        ``retard_jours`` jours."""
        from datetime import timedelta
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'VAD-{rang}',
            prix_vente=Decimal(ht), quantite_stock=10)
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-{self.company.id}{rang}',
            client=self.client_, devis=self.devis, statut=statut,
            taux_tva=Decimal('20.00'), created_by=self.user,
            date_echeance=timezone.localdate() - timedelta(days=retard_jours),
            **extra)
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal(ht),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return facture


class VenteEtatAssistantTest(_BaseVenteAssistant):
    """VAD1 — ``GET devis/<pk>/vente-assistant/`` : forme du contrat
    ``assistant_vente_etat.json``, ``a_faire`` fermé, portée ``get_object``,
    jamais le téléphone ni l'e-mail du client."""

    def test_forme_du_contrat_et_rien_du_client_hors_son_nom(self):
        from apps.ventes.agent_actions import VENTE_ETAT
        resp = auth(self.user).get(VENTE_ETAT.endpoint.format(id=self.devis.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data),
                         set(_exemple_contrat('assistant_vente_etat.json')))
        self.assertEqual(resp.data['client'], 'Lahlou Driss')
        self.assertEqual(resp.data['lien'], f'/ventes/devis?devis={self.devis.pk}')
        self.assertIn(resp.data['a_faire'], {
            'facturer', 'emettre_brouillon', 'encaisser', 'reviser', 'rien'})
        # Un devis envoyé (non accepté) n'a rien à facturer.
        self.assertEqual(resp.data['a_faire'], 'rien')
        self.assertEqual(resp.data['factures'], [])
        texte = str(resp.data)
        for interdit in (self.TEL, 'lahlou@example.com', 'prix_achat', 'marge'):
            self.assertNotIn(interdit, texte)

    def test_devis_d_une_autre_societe_404(self):
        from apps.ventes.agent_actions import VENTE_ETAT
        resp = auth(self._hors_societe()).get(
            VENTE_ETAT.endpoint.format(id=self.devis.pk))
        self.assertEqual(resp.status_code, 404)

    def test_action_lecture_lot_copilote_carte_vente_etat(self):
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import VENTE_ETAT
        self.assertEqual(
            (VENTE_ETAT.lot, VENTE_ETAT.risk, VENTE_ETAT.required_permission,
             VENTE_ETAT.carte, VENTE_ETAT.objets),
            (LOT_COPILOTE, RISK_INTERNAL, 'ventes_voir', 'vente_etat',
             {'id': 'devis'}))


class ImpayesAssistantTest(_BaseVenteAssistant):
    """VAD2 — ``GET ventes/assistant/impayes/`` : forme du contrat
    ``assistant_impayes.json``, contestée comptée, plus en retard d'abord,
    portée société, jamais de téléphone."""

    URL = '/api/django/ventes/assistant/impayes/'

    def test_forme_totaux_ordre_et_a_faire(self):
        recente = self._facture('01', ht='1000', retard_jours=5)
        ancienne = self._facture('02', ht='2000', retard_jours=40)
        contestee = self._facture('03', ht='500', retard_jours=70,
                                  contestee_le=timezone.localdate())
        self._facture('04', ht='9000', statut=Facture.Statut.BROUILLON)
        resp = auth(self.user).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data),
                         set(_exemple_contrat('assistant_impayes.json')))
        self.assertEqual(resp.data['nb_factures'], 3)
        self.assertEqual(resp.data['total_du'], '4200.00')
        self.assertEqual(resp.data['tranches'], {
            'b0_30': '1200.00', 'b31_60': '2400.00', 'b61_90': '600.00',
            'b90_plus': '0.00'})
        ids = [li['facture_id'] for li in resp.data['lignes']]
        self.assertEqual(ids, [contestee.pk, ancienne.pk, recente.pk])
        ligne = resp.data['lignes'][0]
        exemple = _exemple_contrat('assistant_impayes.json')['lignes'][0]
        self.assertEqual(set(ligne), set(exemple))
        self.assertEqual((ligne['contestee'], ligne['a_faire']),
                         (True, 'traiter_contestation'))
        self.assertEqual(resp.data['lignes'][1]['a_faire'], 'relancer')
        self.assertEqual(ligne['lien'], f'/ventes/factures?facture={contestee.pk}')
        self.assertNotIn(self.TEL, str(resp.data))

    def test_filtres_limite_et_parametre_inconnu_400(self):
        self._facture('05', retard_jours=3)
        self._facture('06', retard_jours=8)
        resp = auth(self.user).get(self.URL, {'limite': 1, 'q': 'lahlou'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual((resp.data['nb_factures'], len(resp.data['lignes'])),
                         (2, 1))
        vide = auth(self.user).get(self.URL, {'q': 'zzz'})
        self.assertEqual(vide.data['lignes'], [])
        self.assertEqual(vide.data['total_du'], '0.00')
        for params, champ in (({'inconnu': 1}, 'inconnu'), ({'limite': 99}, 'limite'),
                              ({'mes_relances': 'peut-etre'}, 'mes_relances'),
                              ({'client': 'x'}, 'client')):
            with self.subTest(params=params):
                refus = auth(self.user).get(self.URL, params)
                self.assertEqual(refus.status_code, 400)
                self.assertIn(champ, str(refus.data))

    def test_autre_societe_ne_voit_rien(self):
        self._facture('07', retard_jours=12)
        resp = auth(self._hors_societe()).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual((resp.data['nb_factures'], resp.data['lignes']), (0, []))

    def test_action_lecture_lot_copilote_carte_liste_impayes(self):
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import IMPAYES_LISTER
        self.assertEqual(
            (IMPAYES_LISTER.lot, IMPAYES_LISTER.risk,
             IMPAYES_LISTER.required_permission, IMPAYES_LISTER.carte),
            (LOT_COPILOTE, RISK_INTERNAL, 'ventes_voir', 'liste_impayes'))
        self.assertNotIn('telephone', str(IMPAYES_LISTER.inputs))


class FacturesAssistantTest(_BaseVenteAssistant):
    """VAD3 — ``GET ventes/assistant/factures/`` : forme du contrat
    ``assistant_factures.json``, recherche par référence / nom / téléphone
    (jamais rendu), statut fermé, portée société."""

    URL = '/api/django/ventes/assistant/factures/'

    def test_forme_par_nom_et_par_telephone_sans_le_rendre(self):
        brouillon = self._facture('11', statut=Facture.Statut.BROUILLON)
        emise = self._facture('12', retard_jours=4)
        for q in ('lahlou', '06 00 00 42 42'):
            with self.subTest(q=q):
                resp = auth(self.user).get(self.URL, {'q': q})
                self.assertEqual(resp.status_code, 200, resp.data)
                self.assertEqual(set(resp.data),
                                 set(_exemple_contrat('assistant_factures.json')))
                self.assertEqual(resp.data['total'], 2)
                par_id = {li['facture_id']: li for li in resp.data['lignes']}
                self.assertEqual(set(par_id), {brouillon.pk, emise.pk})
                self.assertEqual(par_id[brouillon.pk]['a_faire'], 'emettre')
                self.assertEqual(par_id[brouillon.pk]['montant_du'], '0.00')
                self.assertEqual(par_id[emise.pk]['a_faire'], 'relancer')
                self.assertEqual(par_id[emise.pk]['montant_du'], '1200.00')
                self.assertNotIn('600004242', str(resp.data))
        exemple = _exemple_contrat('assistant_factures.json')['lignes'][0]
        self.assertEqual(set(resp.data['lignes'][0]), set(exemple))

    def test_statut_filtre_et_valeur_hors_liste_400(self):
        self._facture('13', statut=Facture.Statut.BROUILLON)
        self._facture('14')
        resp = auth(self.user).get(self.URL, {'statut': 'brouillon'})
        self.assertEqual(resp.data['total'], 1)
        refus = auth(self.user).get(self.URL, {'statut': 'perdue'})
        self.assertEqual(refus.status_code, 400)
        self.assertIn('statut', str(refus.data))

    def test_autre_societe_ne_voit_rien(self):
        self._facture('15')
        resp = auth(self._hors_societe()).get(self.URL, {'q': 'lahlou'})
        self.assertEqual((resp.data['total'], resp.data['lignes']), (0, []))

    def test_action_statuts_du_modele_et_lot_copilote(self):
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import FACTURE_CHERCHER, STATUTS_FACTURE
        self.assertEqual(set(STATUTS_FACTURE), set(Facture.Statut.values))
        self.assertEqual(
            (FACTURE_CHERCHER.lot, FACTURE_CHERCHER.risk,
             FACTURE_CHERCHER.required_permission, FACTURE_CHERCHER.carte),
            (LOT_COPILOTE, RISK_INTERNAL, 'ventes_voir', 'liste_factures'))


class CycleDevisAssistantTest(_BaseVenteAssistant):
    """VAD4-VAD6 — prolonger, refuser, réviser : les routes EXISTANTES de
    l'écran, appelées comme le relais les appelle (JWT de l'utilisateur, corps
    = entrées de l'action) ; propositions à confirmer, objet nommé."""

    def _ecriture_copilote(self, action, permission):
        from apps.agent.registry import LOT_COPILOTE
        self.assertEqual(
            (action.lot, action.risk, action.required_permission, action.objets),
            (LOT_COPILOTE, RISK_OUTWARD, permission, {'id': 'devis'}))
        self.assertTrue(action.confirm_summary)
        self.assertFalse(action.inputs.get('additionalProperties', True))
        self.assertLessEqual(len(action.description), 600)

    def test_prolonger_un_envoye_puis_refus_d_un_expire(self):
        from apps.ventes.agent_actions import PROLONGER_DEVIS
        self._ecriture_copilote(PROLONGER_DEVIS, 'ventes_modifier')
        url = PROLONGER_DEVIS.endpoint.format(id=self.devis.pk)
        resp = auth(self.user).post(url, {'date': '2030-01-15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['date_validite'], '2030-01-15')
        Devis.objects.filter(pk=self.devis.pk).update(statut=Devis.Statut.EXPIRE)
        refus = auth(self.user).post(url, {}, format='json')
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertIn('réviser', refus.data['detail'])

    def test_refuser_motif_de_la_liste_lead_perdu_requis_accepte_409(self):
        from apps.crm.models import MotifPerte
        from apps.ventes.agent_actions import REFUSER_DEVIS
        self._ecriture_copilote(REFUSER_DEVIS, 'ventes_valider')
        self.assertIn('marquer_lead_perdu', REFUSER_DEVIS.inputs['required'])
        self.assertNotIn('date', REFUSER_DEVIS.inputs['properties'])
        MotifPerte.objects.create(company=self.company, nom='Prix')
        url = REFUSER_DEVIS.endpoint.format(id=self.devis.pk)
        inconnu = auth(self.user).post(url, {
            'motif': 'Météo', 'marquer_lead_perdu': False}, format='json')
        self.assertEqual(inconnu.status_code, 409, inconnu.data)
        resp = auth(self.user).post(url, {
            'motif': 'prix', 'note': 'trop cher', 'marquer_lead_perdu': False},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual((self.devis.statut, self.devis.motif_refus),
                         (Devis.Statut.REFUSE, 'Prix'))
        Devis.objects.filter(pk=self.devis.pk).update(statut=Devis.Statut.ACCEPTE)
        accepte = auth(self.user).post(url, {
            'motif': 'Prix', 'marquer_lead_perdu': False}, format='json')
        self.assertEqual(accepte.status_code, 409, accepte.data)

    def test_reviser_un_accepte_cree_la_v2_brouillon_un_brouillon_409(self):
        from apps.ventes.agent_actions import REVISER_DEVIS
        self._ecriture_copilote(REVISER_DEVIS, 'ventes_creer')
        Devis.objects.filter(pk=self.devis.pk).update(statut=Devis.Statut.ACCEPTE)
        resp = auth(self.user).post(
            REVISER_DEVIS.endpoint.format(id=self.devis.pk), {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        v2 = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(v2.statut, Devis.Statut.BROUILLON)
        brouillon = auth(self.user).post(
            REVISER_DEVIS.endpoint.format(id=v2.pk), {}, format='json')
        self.assertEqual(brouillon.status_code, 409, brouillon.data)


def _taille_simulee(quantite):
    """Remplace ``taille_assistant._appliquer`` (le moteur « réconcilier »,
    couvert par les tests des offres de taille) : la ligne panneau passe à
    ``quantite`` — l'effet que l'aperçu doit ANNULER et l'écriture garder."""
    from apps.ventes.models import LigneDevis

    def appliquer(devis, nb, modules, utilisateur, ttc_avant):
        LigneDevis.objects.filter(devis=devis).update(quantite=Decimal(quantite))
        return {'panneaux_avant': 10, 'panneaux': quantite, 'avertissements': []}
    return appliquer


class TailleAssistantTest(_BaseVenteAssistant):
    """VAD7 (D-W2-Q1) — l'aperçu n'écrit RIEN ; l'écriture exige l'ancien et
    le nouveau total de l'aperçu ; un accepté se révise d'abord ; formes des
    contrats ``assistant_devis_taille_apercu.json`` / ``assistant_devis_taille.json``."""

    def setUp(self):
        from apps.ventes.models import LigneDevis
        super().setUp()
        produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='VAD-PV710', prix_vente=Decimal('1400'),
            prix_achat=Decimal('555.55'))
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=produit,
            designation='Panneau Canadien Solar 710W', quantite=Decimal('10'),
            prix_unitaire=Decimal('1166.67'), ordre=0)

    def _url(self, apercu=False):
        from apps.ventes.agent_actions import TAILLE_APERCU, TAILLE_DEVIS
        action = TAILLE_APERCU if apercu else TAILLE_DEVIS
        return action.endpoint.format(id=self.devis.pk)

    def test_apercu_annule_puis_ecriture_confirmee_et_apercu_perime(self):
        from unittest import mock
        with mock.patch('apps.ventes.domain.taille_assistant._appliquer',
                        _taille_simulee(12)):
            apercu = auth(self.user).get(self._url(apercu=True), {'nb_panneaux': 12})
            self.assertEqual(apercu.status_code, 200, apercu.data)
            self.assertEqual(set(apercu.data), set(_exemple_contrat(
                'assistant_devis_taille_apercu.json')))
            self.ligne.refresh_from_db()
            self.assertEqual(self.ligne.quantite, Decimal('10'))  # rien d'écrit
            self.assertTrue(apercu.data['corrige_apres_envoi'])
            self.assertEqual(apercu.data['a_faire'], 'proposer')
            self.assertNotEqual(apercu.data['ancien_total_ttc'],
                                apercu.data['nouveau_total_ttc'])
            perime = auth(self.user).post(self._url(), {
                'nb_panneaux': 12, 'ancien_total_ttc': apercu.data['ancien_total_ttc'],
                'nouveau_total_ttc': '1.00'}, format='json')
            self.assertEqual(perime.status_code, 409, perime.data)
            self.assertEqual(perime.data['code'], 'apercu_perime')
            self.ligne.refresh_from_db()
            self.assertEqual(self.ligne.quantite, Decimal('10'))
            resp = auth(self.user).post(self._url(), {
                'nb_panneaux': 12,
                'ancien_total_ttc': apercu.data['ancien_total_ttc'],
                'nouveau_total_ttc': apercu.data['nouveau_total_ttc']},
                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(_exemple_contrat(
            'assistant_devis_taille.json')))
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite, Decimal('12'))
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)  # règle #4
        self.assertEqual(resp.data['composition'][0]['total_ttc'], '16800.00')
        self.assertNotIn('555.55', str(resp.data))

    def test_devis_compose_sur_demande_le_refus_dit_de_recomposer(self):
        """Un devis composé sur demande se recompose EN PLACE (classe
        ``TailleComposeeSurDemandeTest``) ; seul un marqueur SANS ses produits
        enregistrés ne le peut pas : le refus nomme le geste qui marche (un
        nouveau devis). Chemin réel, aucun moteur simulé."""
        from apps.ventes.domain.composition_imposee import poser_marqueur
        poser_marqueur(self.devis, {'demande': {'nb_panneaux': 10}})
        apercu = auth(self.user).get(self._url(apercu=True), {'nb_panneaux': 12})
        self.assertEqual(apercu.status_code, 409, apercu.data)
        self.assertEqual(apercu.data['code'], 'composition_imposee')
        self.assertIn('composez un nouveau devis', apercu.data['detail'])
        self.assertIn('12 panneaux', apercu.data['detail'])
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite, Decimal('10'))

    def test_devis_sans_marqueur_passe_par_les_offres_de_taille(self):
        """Sans marqueur, la taille passe TOUJOURS par les offres de taille
        (moteur réel) : sans étude de consommation, leur refus en clair."""
        apercu = auth(self.user).get(self._url(apercu=True), {'nb_panneaux': 12})
        self.assertEqual(apercu.status_code, 409, apercu.data)
        self.assertEqual((apercu.data['code'], apercu.data['field']),
                         ('taille_impossible', 'nb_panneaux'))
        self.assertIn('dériver des tailles', apercu.data['detail'])
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite, Decimal('10'))

    def test_accepte_refuse_avec_la_phrase_de_revision_sans_rien_ecrire(self):
        Devis.objects.filter(pk=self.devis.pk).update(statut=Devis.Statut.ACCEPTE)
        for reponse in (
                auth(self.user).get(self._url(apercu=True), {'nb_panneaux': 12}),
                auth(self.user).post(self._url(), {
                    'nb_panneaux': 12, 'ancien_total_ttc': '1.00',
                    'nouveau_total_ttc': '2.00'}, format='json')):
            self.assertEqual(reponse.status_code, 409, reponse.data)
            self.assertEqual((reponse.data['code'], reponse.data['field']),
                             ('revision_possible', 'statut'))
            self.assertIn('réviser', reponse.data['detail'])
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite, Decimal('10'))

    def test_parametres_bornes_et_devis_hors_societe_404(self):
        for params in ({}, {'nb_panneaux': 0}, {'nb_panneaux': 201},
                       {'nb_panneaux': 12, 'batterie_nb_modules': 0},
                       {'nb_panneaux': 12, 'forcer': 1}):
            with self.subTest(params=params):
                resp = auth(self.user).get(self._url(apercu=True), params)
                self.assertEqual(resp.status_code, 400, resp.data)
        hors = auth(self._hors_societe()).get(self._url(apercu=True),
                                              {'nb_panneaux': 12})
        self.assertEqual(hors.status_code, 404)

    def test_apercu_perime_compare_les_deux_totaux_au_centime(self):
        from apps.ventes.domain.taille_assistant import (
            TailleRefusee, exiger_apercu_a_jour)
        mesure = {'ancien_total_ttc': '73000.00', 'nouveau_total_ttc': '76400.00'}
        self.assertIsNone(exiger_apercu_a_jour(mesure, {
            'ancien_total_ttc': '73000', 'nouveau_total_ttc': '76400.0'}))
        with self.assertRaises(TailleRefusee) as refus:
            exiger_apercu_a_jour(mesure, {'ancien_total_ttc': '73000.00',
                                          'nouveau_total_ttc': '76800.00'})
        self.assertEqual(refus.exception.corps['code'], 'apercu_perime')

    def test_actions_lecture_puis_ecriture_confirmee_sans_prix_ni_forcage(self):
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import TAILLE_APERCU, TAILLE_DEVIS
        self.assertEqual((TAILLE_APERCU.risk, TAILLE_APERCU.required_permission,
                          TAILLE_APERCU.lot), (RISK_INTERNAL, 'ventes_modifier', LOT_COPILOTE))
        self.assertEqual((TAILLE_DEVIS.risk, TAILLE_DEVIS.required_permission,
                          TAILLE_DEVIS.lot, TAILLE_DEVIS.objets),
                         (RISK_OUTWARD, 'ventes_modifier', LOT_COPILOTE, {'id': 'devis'}))
        self.assertEqual(set(TAILLE_DEVIS.inputs['properties']), {
            'id', 'nb_panneaux', 'batterie_nb_modules', 'ancien_total_ttc',
            'nouveau_total_ttc'})
        self.assertLessEqual({'ancien_total_ttc', 'nouveau_total_ttc'},
                             set(TAILLE_DEVIS.inputs['required']))


class TailleComposeeSurDemandeTest(_BaseVenteAssistant):
    """Copilote vague 2B — un devis COMPOSÉ SUR DEMANDE (``POST devis/auto/``
    à composition imposée, sans étude de consommation) change de taille EN
    PLACE par les deux routes réelles : même onduleur, même batterie,
    structures et socles suivent, marqueur mis à jour, statut gardé. Aucun
    moteur simulé : le devis est composé par le vrai chemin imposé."""

    PRIX = {'Panneau Canadien Solar 710W': '1400',
            'Panneau Jinko 550W': '1100',
            'Onduleur hybride Deye 5kW Monophasé': '17000',
            'Onduleur réseau Huawei 5kW Monophasé': '14000',
            'Batterie Dyness 5 kWh': '14000',
            'Structures acier': '500', 'Socles': '80'}
    DEMANDE = {'nb_panneaux': 9, 'onduleur_kw': 5,
               'onduleur_phase': 'monophase', 'batterie_kwh': 5}
    PANNEAU, HYBRIDE, BATTERIE = ('Panneau Canadien Solar 710W',
                                  'Onduleur hybride Deye 5kW Monophasé',
                                  'Batterie Dyness 5 kWh')

    def setUp(self):
        super().setUp()
        self.produits = {
            nom: Produit.objects.create(
                company=self.company, nom=nom, sku='VADC-%d' % rang,
                prix_vente=Decimal(prix), prix_achat=Decimal('123.45'),
                quantite_stock=100)
            for rang, (nom, prix) in enumerate(self.PRIX.items())}
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Sara',
            ville='Casablanca')

    def _composer(self, demande=None):
        resp = auth(self.user).post('/api/django/ventes/devis/auto/', {
            'lead': self.lead.id, **(demande or self.DEMANDE)}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return Devis.objects.get(pk=resp.data['id'])

    def _url(self, devis, apercu=False):
        from apps.ventes.agent_actions import TAILLE_APERCU, TAILLE_DEVIS
        action = TAILLE_APERCU if apercu else TAILLE_DEVIS
        return action.endpoint.format(id=devis.pk)

    def _apercu(self, devis, nb=12, **params):
        return auth(self.user).get(self._url(devis, apercu=True),
                                   {'nb_panneaux': nb, **params})

    def _ecrire(self, devis, apercu, nb=12, **corps):
        return auth(self.user).post(self._url(devis), {
            'nb_panneaux': nb,
            'ancien_total_ttc': apercu.data['ancien_total_ttc'],
            'nouveau_total_ttc': apercu.data['nouveau_total_ttc'], **corps},
            format='json')

    @staticmethod
    def _quantites(devis):
        return {li.designation: int(li.quantite) for li in devis.lignes.all()}

    def _rien_ecrit(self, devis, quantites, nb_marqueur=9):
        devis.refresh_from_db()
        self.assertEqual(self._quantites(devis), quantites)
        self.assertEqual(devis.etude_params['composition_imposee']['demande']
                         ['nb_panneaux'], nb_marqueur)

    def test_apercu_annule_puis_ecriture_recompose_en_place(self):
        from apps.ventes.domain.modifiabilite import ttc_du_devis
        from core.money import quantize_mad
        devis = self._composer()
        avant = self._quantites(devis)
        self.assertEqual((avant[self.PANNEAU], avant['Structures acier']), (9, 9))
        apercu = self._apercu(devis)
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertEqual(set(apercu.data), set(_exemple_contrat(
            'assistant_devis_taille_apercu.json')))
        self.assertEqual((apercu.data['nb_panneaux_avant'],
                          apercu.data['nb_panneaux']), (9, 12))
        self.assertFalse(apercu.data['corrige_apres_envoi'])
        # Essai vraie clé du 19/11 : ni la phrase de la conception 3D (il n'y
        # en a pas ici), ni la même alerte dite deux fois.
        messages = [alerte['message'] for alerte in apercu.data['alertes']]
        self.assertFalse([m for m in messages if m.startswith('La conception 3D')])
        self.assertEqual(len(messages), len(set(messages)), messages)
        self.assertEqual(apercu.data['a_faire'], 'proposer')
        self.assertNotEqual(apercu.data['ancien_total_ttc'],
                            apercu.data['nouveau_total_ttc'])
        # 12 × 710 Wc sur 5 kW : l'alerte du chemin imposé, pas un refus.
        self.assertIn('ratio_dc_ac', {a.get('code') for a in apercu.data['alertes']})
        self._rien_ecrit(devis, avant)
        perime = self._ecrire(devis, apercu, nouveau_total_ttc='1.00')
        self.assertEqual((perime.status_code, perime.data['code']),
                         (409, 'apercu_perime'))
        self._rien_ecrit(devis, avant)
        resp = self._ecrire(devis, apercu)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(_exemple_contrat(
            'assistant_devis_taille.json')))
        devis.refresh_from_db()
        apres = self._quantites(devis)
        self.assertEqual((apres[self.PANNEAU], apres['Structures acier'],
                          apres['Socles']), (12, 12, 24))
        self.assertEqual((apres[self.HYBRIDE], apres[self.BATTERIE]), (1, 1))
        self.assertNotIn('Onduleur réseau Huawei 5kW Monophasé', apres)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)  # règle #4
        self.assertEqual(resp.data['nouveau_total_ttc'],
                         apercu.data['nouveau_total_ttc'])
        self.assertEqual(Decimal(resp.data['nouveau_total_ttc']),
                         quantize_mad(ttc_du_devis(devis)))
        marqueur = devis.etude_params['composition_imposee']
        self.assertEqual(marqueur['demande']['nb_panneaux'], 12)
        self.assertIn('onduleur_kw', marqueur['demande'])
        self.assertEqual((marqueur['produits']['onduleur'],
                          marqueur['produits']['batterie'],
                          marqueur['par']),
                         (self.produits[self.HYBRIDE].pk,
                          self.produits[self.BATTERIE].pk, self.user.pk))
        self.assertNotIn('123.45', str(resp.data) + str(apercu.data))

    def test_envoye_corrige_en_place_statut_garde(self):
        devis = self._composer()
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
        apercu = self._apercu(devis, nb=10)
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertTrue(apercu.data['corrige_apres_envoi'])
        resp = self._ecrire(devis, apercu, nb=10)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['corrige_apres_envoi'])
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(self._quantites(devis)[self.PANNEAU], 10)

    def test_accepte_refuse_avec_la_phrase_de_revision(self):
        devis = self._composer()
        avant = self._quantites(devis)
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ACCEPTE)
        refus = self._apercu(devis)
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertEqual((refus.data['code'], refus.data['field']),
                         ('revision_possible', 'statut'))
        self.assertIn('réviser', refus.data['detail'])
        self._rien_ecrit(devis, avant)

    def test_refus_du_chemin_impose_meme_refus_rien_ecrit(self):
        """La batterie imposée n'est plus vendable : le chemin imposé refuse
        en nommant son champ ; rien n'est écrit, aucun remplaçant choisi."""
        devis = self._composer()
        avant = self._quantites(devis)
        Produit.objects.filter(pk=self.produits[self.BATTERIE].pk).update(
            prix_vente=Decimal('0'))
        for reponse in (self._apercu(devis), auth(self.user).post(
                self._url(devis), {'nb_panneaux': 12, 'ancien_total_ttc': '1.00',
                                   'nouveau_total_ttc': '2.00'}, format='json')):
            self.assertEqual(reponse.status_code, 409, reponse.data)
            self.assertEqual((reponse.data['code'], reponse.data['field']),
                             ('composition_impossible', 'batterie_produit_id'))
        self._rien_ecrit(devis, avant)

    def test_composition_changee_a_la_main_409_nomme(self):
        from apps.ventes.models import LigneDevis
        devis = self._composer()
        LigneDevis.objects.filter(
            devis=devis, produit=self.produits[self.PANNEAU]).update(
                produit=self.produits['Panneau Jinko 550W'],
                designation='Panneau Jinko 550W')
        avant = self._quantites(devis)
        refus = self._apercu(devis)
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertEqual(refus.data['code'], 'composition_modifiee')
        self.assertIn('écran du devis', refus.data['detail'])
        self._rien_ecrit(devis, avant)

    def test_modules_de_la_batterie_imposee_et_refus_sans_batterie(self):
        devis = self._composer()
        apercu = self._apercu(devis, batterie_nb_modules=2)
        self.assertEqual(apercu.status_code, 200, apercu.data)
        resp = self._ecrire(devis, apercu, batterie_nb_modules=2)
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(self._quantites(devis)[self.BATTERIE], 2)
        self.assertEqual(devis.etude_params['composition_imposee']['produits']
                         ['batterie_nombre'], 2)
        sans = self._composer({'nb_panneaux': 9, 'onduleur_kw': 5,
                               'onduleur_phase': 'monophase', 'scenario': 'sans'})
        refus = self._apercu(sans, batterie_nb_modules=2)
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertEqual((refus.data['code'], refus.data['field']),
                         ('batterie_non_imposee', 'batterie_nb_modules'))

    def test_auto_et_taille_disent_chaque_option(self):
        """20/11/2026 (DEV-202611-0090 : « je ne peux pas dire à quelle
        option il correspond ») — la réponse de ``devis/auto/`` (composer /
        creer_auto) et celles de la taille portent ``options`` : une entrée
        par option, total de ``option_totaux`` (la chaîne du PDF)."""
        from apps.ventes.utils.options import option_totaux
        resp = auth(self.user).post('/api/django/ventes/devis/auto/', {
            'lead': self.lead.id, **self.DEMANDE}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(len(resp.data['options']), 1, resp.data['options'])
        option = resp.data['options'][0]
        self.assertEqual((option['variante'], option['nb_panneaux']), ('', 9))
        self.assertEqual(option['total_ttc'],
                         str(option_totaux(devis)['ttc'].quantize(Decimal('0.01'))))
        apercu = self._apercu(devis)
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertEqual(apercu.data['options'][0]['total_ttc'],
                         apercu.data['nouveau_total_ttc'])
        self.assertEqual(apercu.data['options'][0]['nb_panneaux'], 12)
        ecrit = self._ecrire(devis, apercu)
        self.assertEqual(ecrit.status_code, 200, ecrit.data)
        self.assertEqual(ecrit.data['options'], apercu.data['options'])
        self.assertNotIn('123.45', str(resp.data) + str(ecrit.data))


class RelanceWhatsappAssistantTest(_BaseVenteAssistant):
    """VAD8 — le WhatsApp de relance : modèle « relance » validé forcé, lien
    wa.me, trace au chatter ; personne opposée, contestée, brouillon refusés
    (409 nommé, rien de tracé) ; portée société."""

    def _url(self, facture):
        from apps.ventes.agent_actions import WHATSAPP_RELANCE
        return WHATSAPP_RELANCE.endpoint.format(id=facture.pk)

    def _traces(self, facture):
        from apps.ventes.models_facturation import FactureActivity
        return FactureActivity.objects.filter(facture=facture).count()

    def test_relance_preparee_texte_valide_et_trace(self):
        facture = self._facture('21', retard_jours=9)
        resp = auth(self.user).post(self._url(facture), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), {'facture_id', 'reference', 'texte',
                                          'wa_url', 'langue_servie', 'lien'})
        self.assertTrue(resp.data['wa_url'].startswith('https://wa.me/'))
        self.assertEqual(resp.data['langue_servie'], 'fr')
        self.assertEqual(self._traces(facture), 1)

    def test_opposition_contestee_et_brouillon_refuses_sans_trace(self):
        lead = Lead.objects.create(company=self.company, nom='Lahlou',
                                   prenom='Driss', ne_plus_contacter=True)
        opposee = self._facture('22', retard_jours=9, lead=lead)
        contestee = self._facture('23', retard_jours=9,
                                  contestee_le=timezone.localdate())
        brouillon = self._facture('24', statut=Facture.Statut.BROUILLON)
        for facture, code in ((opposee, 'opposition'),
                              (contestee, 'non_relancable'),
                              (brouillon, 'non_relancable')):
            with self.subTest(code=code, facture=facture.reference):
                resp = auth(self.user).post(self._url(facture), {}, format='json')
                self.assertEqual(resp.status_code, 409, resp.data)
                self.assertEqual(resp.data['code'], code)
                self.assertEqual(self._traces(facture), 0)

    def test_autre_societe_404_et_langue_hors_liste_400(self):
        facture = self._facture('25', retard_jours=9)
        hors = auth(self._hors_societe()).post(self._url(facture), {}, format='json')
        self.assertEqual(hors.status_code, 404)
        refus = auth(self.user).post(self._url(facture), {'langue': 'en'},
                                     format='json')
        self.assertEqual(refus.status_code, 400)

    def test_action_interne_texte_jamais_ecrit_par_le_modele(self):
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import WHATSAPP_RELANCE
        self.assertEqual(
            (WHATSAPP_RELANCE.risk, WHATSAPP_RELANCE.required_permission,
             WHATSAPP_RELANCE.carte, WHATSAPP_RELANCE.lot, WHATSAPP_RELANCE.objets),
            (RISK_INTERNAL, 'ventes_modifier', 'wa_message', LOT_COPILOTE,
             {'id': 'facture'}))
        self.assertEqual(set(WHATSAPP_RELANCE.inputs['properties']), {'id', 'langue'})


class FacturerVenteAssistantTest(_BaseVenteAssistant):
    """VAD9 (D-W2-Q2 = BROUILLON_SEULEMENT) — « facture l'acompte » prépare un
    BROUILLON par la route de l'écran ; le schéma de l'action est FERMÉ : ni
    émission, ni paiement, ni forçage ne peuvent y être posés."""

    INTERDITES = ('emettre', 'paiements', 'utiliser_avances',
                  'remplacer_brouillons', 'override_credit',
                  'override_avertissement', 'libelle', 'company')

    def test_schema_ferme_aucune_emission_ni_forcage(self):
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import FACTURER_VENTE, NATURES_FACTURE
        from apps.ventes.domain.facturation_vente import NATURES
        self.assertEqual(NATURES_FACTURE, NATURES)
        self.assertIs(FACTURER_VENTE.inputs['additionalProperties'], False)
        proprietes = set(FACTURER_VENTE.inputs['properties'])
        self.assertEqual(proprietes & set(self.INTERDITES), set())
        self.assertEqual(proprietes, {'id', 'nature', 'pourcentage',
                                      'montant_ttc', 'cle_attendue'})
        self.assertEqual(
            (FACTURER_VENTE.risk, FACTURER_VENTE.required_permission,
             FACTURER_VENTE.carte, FACTURER_VENTE.lot, FACTURER_VENTE.objets),
            (RISK_OUTWARD, 'ventes_valider', 'facture_brouillon', LOT_COPILOTE,
             {'id': 'devis'}))
        self.assertIn('BROUILLON', FACTURER_VENTE.confirm_summary)

    def test_brouillon_prepare_sans_numero_legal_forme_du_contrat(self):
        from apps.ventes.agent_actions import FACTURER_VENTE, VENTE_ETAT
        from apps.ventes.models import LigneDevis
        produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='VAD-KIT',
            prix_vente=Decimal('10000'))
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Kit solaire',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'), ordre=0)
        Devis.objects.filter(pk=self.devis.pk).update(statut=Devis.Statut.ACCEPTE)
        etat = auth(self.user).get(VENTE_ETAT.endpoint.format(id=self.devis.pk))
        self.assertEqual(etat.data['a_faire'], 'facturer', etat.data)
        echeance = etat.data['prochaines_echeances'][0]
        resp = auth(self.user).post(
            FACTURER_VENTE.endpoint.format(id=self.devis.pk), {
                'nature': etat.data['prochaine_action'],
                'montant_ttc': echeance['montant_ttc'],
                'cle_attendue': echeance['cle']}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(set(resp.data), set(_exemple_contrat(
            'devis_facturer.json', 'exemple_brouillon_assistant')))
        self.assertEqual(resp.data['facture']['statut'], 'brouillon')
        facture = Facture.objects.get(pk=resp.data['facture']['id'])
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        apres = auth(self.user).get(VENTE_ETAT.endpoint.format(id=self.devis.pk))
        self.assertEqual(apres.data['a_faire'], 'emettre_brouillon')


class BriefVentesTest(_BaseVenteAssistant):
    """VAD10 — ``selectors_assistant.brief_ventes(user, aujourdhui)`` : le bloc
    ``impayes`` du point du matin (forme de l'échantillon du digest), cinq
    lignes au plus, compteurs sur tout ; absent (None) sans lecture des
    factures."""

    def _exemple_bloc(self):
        import json
        from pathlib import Path
        chemin = (Path(__file__).resolve().parents[2] / 'crm' / 'contract_samples'
                  / 'assistant_digest_matin.json')
        return json.loads(chemin.read_text(encoding='utf-8'))[
            'vague2']['exemple_copilote']['impayes']

    def test_forme_cinq_lignes_compteurs_sur_tout(self):
        from apps.ventes.selectors_assistant import brief_ventes
        for rang in range(6):
            self._facture(f'3{rang}', ht='100', retard_jours=10 + rang)
        bloc = brief_ventes(self.user, timezone.localdate())
        exemple = self._exemple_bloc()
        self.assertEqual(set(bloc), set(exemple))
        self.assertEqual((bloc['nb_factures'], bloc['total_du']), (6, '720.00'))
        self.assertEqual(len(bloc['lignes']), 5)
        self.assertEqual(set(bloc['lignes'][0]), set(exemple['lignes'][0]))
        retards = [li['jours_retard'] for li in bloc['lignes']]
        self.assertEqual(retards, sorted(retards, reverse=True))
        self.assertNotIn(self.TEL, str(bloc))

    def test_absent_sans_lecture_des_factures(self):
        from apps.ventes.selectors_assistant import brief_ventes
        crm_seul = User.objects.create_user(
            username='vad_crm', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='CRM seul',
                                     permissions=['crm_voir']))
        self.assertIsNone(brief_ventes(crm_seul, timezone.localdate()))


class PermissionsVenteAssistantTest(_BaseVenteAssistant):
    """VAD11 — qui voit les outils de la lane VAD (copilote allumé), rôles
    CANONIQUES du registre ; l'Admin Ventes (``ventes_valider`` sans
    ``encaisser``) prépare un brouillon de facture mais n'émet ni n'encaisse ;
    une route d'écriture refuse le lecteur seul (403) — catalogue et garde de
    la route disent la même chose."""

    LECTURES = {'ventes.vente.etat', 'ventes.impayes.lister',
                'ventes.facture.chercher'}
    ECRITURES = {'ventes.devis.prolonger', 'ventes.devis.refuser',
                 'ventes.devis.reviser', 'ventes.devis.taille',
                 'ventes.devis.taille_apercu',
                 'ventes.facture.whatsapp_relance', 'ventes.vente.facturer'}

    def _compte(self, nom, permissions):
        return User.objects.create_user(
            username=f'vad11_{nom}', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom=f'VAD11 {nom}',
                                     permissions=list(permissions)))

    def _vus(self, user):
        with self.settings(ASSISTANT_COPILOTE='tous'):
            return {a.key for a in for_user(user)}

    def test_catalogue_par_role_canonique(self):
        from apps.roles import permissions_registre as R
        toutes = self.LECTURES | self.ECRITURES
        for nom, permissions, attendu in (
                ('admin_ventes', R.ADMIN_VENTES_PERMISSIONS, toutes),
                ('commercial', R.COMMERCIAL_PERMISSIONS, toutes),
                ('lecture', R.VIEWER_PERMISSIONS, self.LECTURES),
                ('technicien', R.TECHNICIEN_PERMISSIONS, set()),
                ('admin_rh', R.ADMIN_RH_PERMISSIONS, set())):
            with self.subTest(role=nom):
                self.assertEqual(self._vus(self._compte(nom, permissions)) & toutes,
                                 attendu)

    def test_admin_ventes_brouillon_oui_emission_et_encaissement_non(self):
        from apps.roles import permissions_registre as R
        admin_ventes = self._compte('av', R.ADMIN_VENTES_PERMISSIONS)
        vus = self._vus(admin_ventes)
        self.assertIn('ventes.vente.facturer', vus)
        self.assertNotIn(GENERER_FACTURE.key, vus)
        self.assertNotIn(ENREGISTRER_PAIEMENT.key, vus)

    def test_lecteur_seul_route_d_ecriture_403_lecture_200(self):
        from apps.roles import permissions_registre as R
        from apps.ventes.agent_actions import PROLONGER_DEVIS, VENTE_ETAT
        lecteur = self._compte('ro', R.VIEWER_PERMISSIONS)
        self.devis.created_by = lecteur
        self.devis.save(update_fields=['created_by'])
        ecriture = auth(lecteur).post(
            PROLONGER_DEVIS.endpoint.format(id=self.devis.pk), {}, format='json')
        self.assertEqual(ecriture.status_code, 403, ecriture.data)
        lecture = auth(lecteur).get(VENTE_ETAT.endpoint.format(id=self.devis.pk))
        self.assertEqual(lecture.status_code, 200, lecture.data)


class LignesAssistantEcritureTest(_BaseVenteAssistant):
    """20/11/2026 (incident prod : ``ventes.devis.ligne_ajouter`` répondait
    400 à chaque appel — quantité en nombre JSON refusée, désignation exigée)
    — ``POST devis/<pk>/assistant-lignes/<operation>/`` : produit du
    CATALOGUE (désignation, prix de vente), quantité en nombre JSON, options
    « sans » / « avec » batterie d'un devis à deux options ; contrat
    ``assistant_devis_lignes_modifier.json``. Moteur réel, rien de simulé."""

    PRIX = {'Panneau Canadien Solar 710W': '1000',
            'Onduleur réseau Huawei 5kW Monophasé': '10000',
            'Onduleur hybride Deye 5kW Monophasé': '15000',
            'Batterie Dyness 5 kWh': '12000',
            'Pergola aluminium': '2000',
            'Structure acier galvanisé': '1500'}

    def setUp(self):
        from apps.ventes.models import LigneDevis
        from apps.ventes.utils.options import deux_options_declarees
        super().setUp()
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.BROUILLON)
        self.devis.refresh_from_db()
        self.p = {nom: Produit.objects.create(
            company=self.company, nom=nom, sku='VADL-%d' % rang,
            prix_vente=Decimal(prix), prix_achat=Decimal('777.77'))
            for rang, (nom, prix) in enumerate(self.PRIX.items())}
        lignes = (('Panneau Canadien Solar 710W', 6, ''),
                  ('Onduleur réseau Huawei 5kW Monophasé', 1, 'sans'),
                  ('Onduleur hybride Deye 5kW Monophasé', 1, 'avec'),
                  ('Batterie Dyness 5 kWh', 1, 'avec'),
                  ('Pergola aluminium', 1, 'sans'),
                  ('Pergola aluminium', 1, 'avec'))
        self.lignes = [LigneDevis.objects.create(
            devis=self.devis, produit=self.p[nom], designation=nom,
            quantite=Decimal(qte), prix_unitaire=self.p[nom].prix_vente,
            variante=variante, ordre=rang)
            for rang, (nom, qte, variante) in enumerate(lignes)]
        self.pergola_sans, self.pergola_avec = self.lignes[4], self.lignes[5]
        self.acier = self.p['Structure acier galvanisé']
        self.assertTrue(deux_options_declarees(self.devis))

    def _post(self, operation, corps, user=None):
        return auth(user or self.user).post(
            f'/api/django/ventes/devis/{self.devis.pk}/assistant-lignes/'
            f'{operation}/', corps, format='json')

    @staticmethod
    def _par_option(resp, cle='total_ttc'):
        return {o['variante']: Decimal(o[cle]) for o in resp.data['options']}

    def test_accessoire_huawei_seulement_dans_l_option_huawei(self):
        """Essai réel du 21/11 — 2 Smart Meter « au devis » : l'option avec
        batterie (onduleur Deye) ne les compte ni ne les imprime (QF9) ; ils ne
        vont que dans l'option Huawei et l'alerte le dit ; demandés pour
        l'option Deye seule : 409 qui le dit, rien d'écrit."""
        meter = Produit.objects.create(
            company=self.company, nom='Smart Meter', sku='VADL-SM',
            prix_vente=Decimal('1500'), prix_achat=Decimal('777.77'))
        resp = self._post('ajouter', {'produit': meter.pk, 'quantite': 2})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(self.devis.lignes.filter(produit=meter)
                              .values_list('variante', flat=True)), ['sans'])
        self.assertEqual([a['code'] for a in resp.data['alertes']
                          if a['code'] == 'accessoire_huawei'], ['accessoire_huawei'])
        apres, avant = self._par_option(resp), self._par_option(resp, 'ancien_total_ttc')
        self.assertEqual(apres['sans'] - avant['sans'], Decimal('3600'))
        refus = self._post('ajouter', {'produit': meter.pk, 'quantite': 1, 'variante': 'avec'})
        self.assertEqual((refus.status_code, refus.data.get('code')), (409, 'accessoire_huawei'))
        self.assertEqual(self.devis.lignes.filter(produit=meter).count(), 1)

    def test_ajouter_entier_aux_deux_options_depuis_le_catalogue(self):
        resp = self._post('ajouter', {'produit': self.acier.pk, 'quantite': 10})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(_exemple_contrat(
            'assistant_devis_lignes_modifier.json')))
        ajoutees = self.devis.lignes.filter(produit=self.acier)
        self.assertEqual(sorted(ajoutees.values_list('variante', flat=True)),
                         ['avec', 'sans'])
        for ligne in ajoutees:
            self.assertEqual((ligne.designation, ligne.quantite,
                              ligne.prix_unitaire),
                             (self.acier.nom, Decimal('10'), Decimal('1500')))
        # 10 × 1 500 HT × 1,2 = 18 000 TTC de plus dans CHAQUE option.
        apres = self._par_option(resp)
        avant = self._par_option(resp, 'ancien_total_ttc')
        self.assertEqual(set(apres), {'sans', 'avec'})
        for variante in ('sans', 'avec'):
            self.assertEqual(apres[variante] - avant[variante], Decimal('18000'))
        self.assertEqual(Decimal(resp.data['nouveau_total_ttc'])
                         - Decimal(resp.data['ancien_total_ttc']), Decimal('18000'))
        self.assertEqual({li['etat'] for li in resp.data['lignes_touchees']},
                         {'ajoutee'})
        texte = str(resp.data)
        self.assertNotIn('777.77', texte)
        self.assertNotIn('prix_achat', texte)

    def test_ajouter_a_une_option_quantite_en_texte(self):
        resp = self._post('ajouter', {'produit': self.acier.pk,
                                      'quantite': '2', 'variante': 'avec'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(self.devis.lignes.filter(produit=self.acier)
                              .values_list('variante', flat=True)), ['avec'])
        avant = self._par_option(resp, 'ancien_total_ttc')
        apres = self._par_option(resp)
        self.assertEqual(apres['sans'], avant['sans'])
        self.assertEqual(apres['avec'] - avant['avec'], Decimal('3600'))

    def test_modifier_quantite_deux_options_puis_une(self):
        resp = self._post('modifier', {'ligne': self.pergola_sans.pk,
                                       'quantite': 3})
        self.assertEqual(resp.status_code, 200, resp.data)
        for ligne in (self.pergola_sans, self.pergola_avec):
            ligne.refresh_from_db()
            self.assertEqual(ligne.quantite, Decimal('3'))
        resp = self._post('modifier', {'ligne': self.pergola_avec.pk,
                                       'quantite': 5, 'variante': 'sans'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.pergola_sans.refresh_from_db()
        self.pergola_avec.refresh_from_db()
        self.assertEqual((self.pergola_sans.quantite, self.pergola_avec.quantite),
                         (Decimal('5'), Decimal('3')))

    def test_supprimer_des_deux_options_et_ligne_commune_separee(self):
        resp = self._post('supprimer', {'ligne': self.pergola_sans.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(self.devis.lignes.filter(
            produit=self.p['Pergola aluminium']).exists())
        self.assertEqual([li['etat'] for li in resp.data['lignes_touchees']],
                         ['retiree', 'retiree'])
        panneau = self.lignes[0]
        resp = self._post('supprimer', {'ligne': panneau.pk, 'variante': 'sans'})
        self.assertEqual(resp.status_code, 200, resp.data)
        # La ligne commune reste celle de l'option « avec » seulement.
        restantes = self.devis.lignes.filter(produit=panneau.produit)
        self.assertEqual(list(restantes.values_list('variante', 'quantite')),
                         [('avec', Decimal('6'))])

    def test_remplacer_la_pergola_par_la_structure_acier(self):
        resp = self._post('remplacer', {'ligne': self.pergola_sans.pk,
                                        'produit': self.acier.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(self.devis.lignes.filter(
            produit=self.p['Pergola aluminium']).exists())
        acier = self.devis.lignes.filter(produit=self.acier).order_by('variante')
        self.assertEqual(list(acier.values_list('variante', 'quantite', 'ordre',
                                                'designation')),
                         [('avec', Decimal('1'), 5, self.acier.nom),
                          ('sans', Decimal('1'), 4, self.acier.nom)])
        # 2 000 → 1 500 HT : 600 TTC de moins dans chaque option.
        avant = self._par_option(resp, 'ancien_total_ttc')
        apres = self._par_option(resp)
        for variante in ('sans', 'avec'):
            self.assertEqual(avant[variante] - apres[variante], Decimal('600'))

    def test_envoye_corrige_en_place_statut_garde(self):
        Devis.objects.filter(pk=self.devis.pk).update(statut=Devis.Statut.ENVOYE)
        resp = self._post('ajouter', {'produit': self.acier.pk, 'quantite': 1})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['corrige_apres_envoi'])
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)  # règle #4

    def test_accepte_409_qui_dit_de_reviser_sans_rien_ecrire(self):
        Devis.objects.filter(pk=self.devis.pk).update(statut=Devis.Statut.ACCEPTE)
        avant = list(self.devis.lignes.order_by('pk').values())
        for operation, corps in (
                ('ajouter', {'produit': self.acier.pk, 'quantite': 1}),
                ('remplacer', {'ligne': self.pergola_sans.pk,
                               'produit': self.acier.pk})):
            resp = self._post(operation, corps)
            self.assertEqual(resp.status_code, 409, resp.data)
            self.assertEqual((resp.data['code'], resp.data['field']),
                             ('revision_possible', 'statut'))
            self.assertIn('réviser', resp.data['detail'])
        self.assertEqual(list(self.devis.lignes.order_by('pk').values()), avant)

    def test_autre_societe_404_et_quantite_invalide_400(self):
        resp = self._post('ajouter', {'produit': self.acier.pk, 'quantite': 1},
                          user=self._hors_societe())
        self.assertEqual(resp.status_code, 404)
        # api-fuzz #1516 : 10 001 et 10^8 refusés (débordement de la marge figée).
        for quantite in (0, -1, True, 'abc', 10001, 99999999):
            with self.subTest(quantite=quantite):
                resp = self._post('ajouter', {'produit': self.acier.pk,
                                              'quantite': quantite})
                self.assertEqual(resp.status_code, 400, resp.data)
        inconnu = self._post('ajouter', {'produit': 2 ** 31 - 2, 'quantite': 1})
        self.assertEqual((inconnu.status_code, inconnu.data['code']),
                         (404, 'produit_inconnu'))
        self.assertFalse(self.devis.lignes.filter(produit=self.acier).exists())

    def test_actions_de_ligne_pointent_vers_les_routes_de_l_assistant(self):
        from django.urls import resolve
        from apps.agent.registry import LOT_COPILOTE
        from apps.ventes.agent_actions import LIGNE_REMPLACER
        for action, operation in ((LIGNE_AJOUTER, 'ajouter'),
                                  (LIGNE_MODIFIER, 'modifier'),
                                  (LIGNE_SUPPRIMER, 'supprimer'),
                                  (LIGNE_REMPLACER, 'remplacer')):
            with self.subTest(action=action.key):
                chemin = action.endpoint.format(id=self.devis.pk)
                self.assertEqual(resolve(chemin).func.actions.get('post'),
                                 f'assistant_lignes_{operation}')
                self.assertEqual((action.method, action.risk,
                                  action.required_permission),
                                 ('POST', RISK_OUTWARD, 'ventes_modifier'))
                self.assertNotIn('confirmation obligatoire', action.description)
                self.assertNotIn('designation', action.inputs['properties'])
                self.assertNotIn('prix_unitaire', action.inputs['properties'])
        self.assertEqual(LIGNE_AJOUTER.inputs['properties']['quantite']['type'],
                         'number')
        self.assertEqual(LIGNE_REMPLACER.lot, LOT_COPILOTE)


class DevisChercherAssistantTest(TestCase):
    """21/11/2026 — ``GET devis/assistant-liste/`` (action
    ``ventes.devis.chercher``) : la portée EXACTE de l'écran des devis (un
    Commercial « mes enregistrements » ne voit que les siens), filtres statut /
    période / texte, jamais un prix d'achat ni une marge, plafond de 50."""

    URL = CHERCHER_DEVIS.endpoint

    def setUp(self):
        import datetime
        from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
        from apps.ventes.models import LigneDevis
        self.company = Company.objects.create(nom='CHD Co', slug='chd-co')
        self.autre = Company.objects.create(nom='CHD Autre', slug='chd-autre')
        role_soi = Role.objects.create(
            company=self.company, nom='Commercial soi',
            permissions=COMMERCIAL_PERMISSIONS + ['records_scope_soi'],
            est_systeme=False)
        self.moi = User.objects.create_user(
            username='chd_moi', password='x', role=role_soi,
            role_legacy='commercial', company=self.company)
        self.collegue = User.objects.create_user(
            username='chd_collegue', password='x', role_legacy='responsable',
            company=self.company)
        self.client_a = Client.objects.create(
            company=self.company, nom='Benali', prenom='Karim',
            email='chd-a@example.com', telephone='+212600000081',
            adresse='Rabat')
        self.client_b = Client.objects.create(
            company=self.company, nom='Lahlou', prenom='Sara',
            email='chd-b@example.com', telephone='+212600000082',
            adresse='Fès')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie CHD', sku='CHD-BAT',
            prix_vente=Decimal('1000'), prix_achat=Decimal('654.32'))
        self.aujourdhui = timezone.now().date()

        def creer(ref, client, auteur, statut):
            d = Devis.objects.create(
                company=self.company, reference=ref, client=client,
                statut=statut, taux_tva=Decimal('20.00'), created_by=auteur)
            LigneDevis.objects.create(
                devis=d, produit=self.produit, designation='Batterie CHD',
                quantite=Decimal('1'), prix_unitaire=Decimal('1000'), ordre=0)
            return d
        self.brouillon = creer('CHD-001', self.client_a, self.moi,
                               Devis.Statut.BROUILLON)
        self.accepte = creer('CHD-002', self.client_b, self.moi,
                             Devis.Statut.ACCEPTE)
        self.du_collegue = creer('CHD-003', self.client_a, self.collegue,
                                 Devis.Statut.BROUILLON)
        # Un devis accepté il y a 60 jours : créé et accepté hors du mois.
        self.ancien = creer('CHD-004', self.client_b, self.moi,
                            Devis.Statut.ACCEPTE)
        ancien = timezone.now() - datetime.timedelta(days=60)
        Devis.objects.filter(pk=self.ancien.pk).update(
            date_creation=ancien, date_acceptation=ancien.date())
        Devis.objects.filter(pk=self.accepte.pk).update(
            date_acceptation=self.aujourdhui)
        autre_client = Client.objects.create(
            company=self.autre, nom='Benali', email='chd-x@example.com',
            telephone='+212600000083', adresse='Agadir')
        Devis.objects.create(
            company=self.autre, reference='CHD-AUTRE', client=autre_client,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20.00'))

    def _refs(self, user, **params):
        resp = auth(user).get(self.URL, params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return {ligne['reference'] for ligne in resp.data['lignes']}, resp

    def test_commercial_portee_soi_ne_voit_que_les_siens(self):
        refs, resp = self._refs(self.moi)
        self.assertEqual(refs, {'CHD-001', 'CHD-002', 'CHD-004'})
        self.assertEqual(resp.data['total'], 3)
        self.assertEqual(set(resp.data), {'total', 'limite', 'lignes'})
        # Le responsable (portée « tout ») voit aussi ceux du collègue.
        refs, _ = self._refs(self.collegue)
        self.assertIn('CHD-001', refs)
        self.assertIn('CHD-003', refs)

    def test_filtre_statut_brouillon_et_forme_de_la_ligne(self):
        refs, resp = self._refs(self.moi, statut='brouillon')
        self.assertEqual(refs, {'CHD-001'})
        ligne = resp.data['lignes'][0]
        self.assertEqual(set(ligne), {
            'devis_id', 'reference', 'statut', 'client', 'lead_id',
            'total_ttc', 'cree_le', 'envoye_le', 'accepte_le', 'lien'})
        self.assertEqual((ligne['client'], ligne['total_ttc'],
                          ligne['statut']),
                         ('Benali Karim', '1200.00', 'brouillon'))

    def test_acceptes_ce_mois_ci_suit_la_date_d_acceptation(self):
        debut = self.aujourdhui.replace(day=1).isoformat()
        refs, resp = self._refs(self.moi, statut='accepte', depuis=debut)
        self.assertEqual(refs, {'CHD-002'})
        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['lignes'][0]['accepte_le'],
                         self.aujourdhui.isoformat())
        refs, _ = self._refs(self.moi, statut='accepte', jusqu_a=debut)
        self.assertEqual(refs, {'CHD-004'})

    def test_recherche_texte_client_et_reference(self):
        refs, _ = self._refs(self.moi, q='lahlou')
        self.assertEqual(refs, {'CHD-002', 'CHD-004'})
        refs, _ = self._refs(self.moi, q='CHD-001')
        self.assertEqual(refs, {'CHD-001'})
        # « Benali » : les siens seulement, jamais celui du collègue ni de
        # l'autre société.
        refs, _ = self._refs(self.moi, q='Benali')
        self.assertEqual(refs, {'CHD-001'})

    def test_autre_societe_jamais_listee(self):
        for user in (self.moi, self.collegue):
            refs, _ = self._refs(user)
            self.assertNotIn('CHD-AUTRE', refs)

    def test_aucun_prix_d_achat_ni_marge(self):
        _, resp = self._refs(self.collegue)
        texte = str(resp.data).lower()
        for interdit in ('654.32', 'prix_achat', 'marge', 'telephone',
                         '+212600000081'):
            self.assertNotIn(interdit, texte)

    def test_limite_plafonnee_a_50_et_parametres_invalides_400(self):
        resp = auth(self.moi).get(self.URL, {'limite': 51})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('limite', resp.data)
        resp = auth(self.moi).get(self.URL, {'limite': 1})
        self.assertEqual((resp.status_code, resp.data['limite'],
                          len(resp.data['lignes']), resp.data['total']),
                         (200, 1, 1, 3))
        for params in ({'statut': 'inconnu'}, {'depuis': '21/11/2026'},
                       {'lead': 1}):
            with self.subTest(params=params):
                self.assertEqual(
                    auth(self.moi).get(self.URL, params).status_code, 400)

    def test_action_declaree_comme_la_route(self):
        from apps.agent.registry import LOT_COPILOTE
        self.assertEqual((CHERCHER_DEVIS.lot, CHERCHER_DEVIS.risk,
                          CHERCHER_DEVIS.required_permission,
                          CHERCHER_DEVIS.method),
                         (LOT_COPILOTE, RISK_INTERNAL, 'ventes_voir', 'GET'))
        self.assertLessEqual(len(CHERCHER_DEVIS.description), 600)
        self.assertIn(CHERCHER_DEVIS, VENTES_ACTIONS_COPILOTE)
