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
from django.test import TestCase
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
    VENTES_ACTIONS,
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
        for action in (
            ACCEPTER_DEVIS, CONVERTIR_EN_BON_COMMANDE, GENERER_FACTURE,
        ):
            self.assertEqual(
                action.required_permission, 'ventes_valider', action.key)
        # COP-G2 — aligné sur les gardes des routes (test de parité de l'agent).
        self.assertEqual(ENREGISTRER_PAIEMENT.required_permission, 'encaisser')
        self.assertEqual(REMISE_DEVIS.required_permission, 'ventes_modifier')

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
        self.assertEqual(GENERER_FACTURE.risk, RISK_OUTWARD)
        self.assertEqual(ENREGISTRER_PAIEMENT.risk, RISK_IRREVERSIBLE)

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
        # /proposal porte la carte « document ».
        self.assertEqual(
            [a.key for a in VENTES_ACTIONS if a.carte], [GENERER_PDF_DEVIS.key])

    def test_objets_nommes_pour_chaque_identifiant_d_objet(self):
        """COP-G3 — toute entrée qui désigne un devis, une facture, un lead ou un
        client est déclarée dans ``objets`` (aperçu nommé) ; seule la LIGNE de
        devis n'a pas de type."""
        attendu = {
            'ventes.devis.creer_auto': {'lead': 'lead', 'client': 'client'},
            'ventes.devis.ligne_ajouter': {'devis': 'devis'},
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
        for action in (ACCEPTER_DEVIS, CONVERTIR_EN_BON_COMMANDE,
                       GENERER_FACTURE, ENREGISTRER_PAIEMENT):
            self.assertIn(
                'change un statut : proposition puis confirmation obligatoire',
                ventes[action.key].description, action.key)
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
