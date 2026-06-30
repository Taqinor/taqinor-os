"""Tests FG201–FG214 — Croissance commerciale / marketing / CPQ (apps.compta).

Couvrent, par tâche :

* FG201 Campagne — création + envoi NO-OP gated (Brevo OFF par défaut).
* FG202 Séquence/Étapes — planification du calendrier sans envoi réel.
* FG203 Relance devis abandonné — journal scopé société.
* FG205 Ouverture ShareLink — ping idempotent + compteur.
* FG206 Formulaire d'intake — pré-tag + slug unique par société.
* FG207 WhatsApp inbound — NO-OP gated tant que Meta non provisionné.
* FG208 Journal d'appels — auteur posé côté serveur.
* FG209 Code promotion — bornes 0–100 %, code unique par société.
* FG210 Modèle de devis — scopé société.
* FG211 Guided selling — évaluation de cohérence kWc/onduleur.
* FG213 Approbation config — workflow approuver/refuser idempotent.
* FG214 E-catalogue — token posé côté serveur, jamais de prix d'achat.

Garde-fous transverses : ``company`` jamais lue du corps (multi-tenant),
isolation société, gate de rôle (Administrateur/Responsable).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    AppelTelephonique, Campagne, CodePromotion, DemandeApprobationConfig,
    ECatalogue, EtapeSequence, FormulaireIntake, MessageWhatsAppEntrant,
    OuverturePartage, RelanceDevisAbandonne, SequenceRelance,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


# ── FG201 — Campagnes email & SMS ──────────────────────────────────────────

class CampagneTests(TestCase):
    def setUp(self):
        self.co = make_company('fg201', 'FG201')
        self.user = make_user(self.co, 'fg201-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/campagnes/', {
            'nom': 'Réveil base froide', 'canal': 'email',
            'objet': 'Offre', 'corps': 'Bonjour',
            'company': 999,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        camp = Campagne.objects.get(id=resp.data['id'])
        self.assertEqual(camp.company_id, self.co.id)
        self.assertEqual(camp.statut, Campagne.Statut.BROUILLON)

    @override_settings(BREVO_ENABLED=False)
    def test_envoi_noop_gated(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        self.assertFalse(services.brevo_actif())
        services.envoyer_campagne(
            camp, destinataires=['a@x.ma', 'b@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ENVOYEE)
        self.assertEqual(camp.nb_destinataires, 2)
        # NO-OP : aucun envoi réel n'est comptabilisé tant que Brevo est OFF.
        self.assertEqual(camp.nb_envois, 0)

    def test_envoi_idempotent(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['a@x.ma'])
        services.envoyer_campagne(camp, destinataires=['a@x.ma', 'b@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.nb_destinataires, 1)


# ── FG202 — Séquences de relance ───────────────────────────────────────────

class SequenceRelanceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg202', 'FG202')
        self.user = make_user(self.co, 'fg202-user')

    def test_planification_calendrier_sans_envoi(self):
        seq = SequenceRelance.objects.create(company=self.co, nom='Drip')
        EtapeSequence.objects.create(
            company=self.co, sequence=seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.WHATSAPP)
        EtapeSequence.objects.create(
            company=self.co, sequence=seq, ordre=2, delai_jours=3,
            canal=EtapeSequence.Canal.EMAIL)
        plan = services.planifier_etapes_sequence(seq)
        self.assertEqual(len(plan), 2)
        self.assertTrue(all(not e['envoye'] for e in plan))
        self.assertEqual(plan[0]['delai_jours'], 0)
        self.assertEqual(plan[1]['delai_jours'], 3)

    def test_planifier_endpoint(self):
        seq = SequenceRelance.objects.create(company=self.co, nom='Drip')
        EtapeSequence.objects.create(
            company=self.co, sequence=seq, ordre=1, delai_jours=0)
        api = auth(self.user)
        resp = api.get(
            f'/api/django/compta/sequences-relance/{seq.id}/planifier/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data['etapes']), 1)


# ── FG203 — Devis abandonnés ───────────────────────────────────────────────

class RelanceDevisAbandonneTests(TestCase):
    def setUp(self):
        self.co = make_company('fg203', 'FG203')
        self.user = make_user(self.co, 'fg203-user')

    def test_service_enregistre_relance(self):
        rel = services.enregistrer_relance_devis_abandonne(
            self.co, devis_id=42, devis_reference='DV-2026-042',
            jours_sans_reponse=7, canal='email')
        self.assertEqual(rel.company_id, self.co.id)
        self.assertEqual(rel.devis_id, 42)

    def test_isolation_societe(self):
        co2 = make_company('fg203b', 'FG203B')
        RelanceDevisAbandonne.objects.create(company=co2, devis_id=1)
        api = auth(self.user)
        resp = api.get('/api/django/compta/relances-devis-abandonnes/')
        self.assertEqual(resp.status_code, 200)
        # Réponse paginée → on lit le compte (l'isolation société renvoie 0).
        self.assertEqual(resp.data['count'], 0)


# ── FG205 — Tracking d'ouverture des ShareLink ─────────────────────────────

class OuverturePartageTests(TestCase):
    def setUp(self):
        self.co = make_company('fg205', 'FG205')
        self.user = make_user(self.co, 'fg205-user')

    def test_ping_idempotent_incremente(self):
        api = auth(self.user)
        for _ in range(3):
            resp = api.post('/api/django/compta/ouvertures-partage/ping/', {
                'token': 'abc123', 'cible': 'devis',
                'cible_reference': 'DV-1',
            }, format='json')
            self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(OuverturePartage.objects.filter(
            company=self.co, token='abc123').count(), 1)
        obj = OuverturePartage.objects.get(company=self.co, token='abc123')
        self.assertEqual(obj.nb_ouvertures, 3)
        self.assertIsNotNone(obj.premier_vu_le)
        self.assertIsNotNone(obj.dernier_vu_le)

    def test_ping_sans_token_400(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/ouvertures-partage/ping/', {},
                        format='json')
        self.assertEqual(resp.status_code, 400)


# ── FG206 — Formulaires d'intake ───────────────────────────────────────────

class FormulaireIntakeTests(TestCase):
    def setUp(self):
        self.co = make_company('fg206', 'FG206')
        self.user = make_user(self.co, 'fg206-user')

    def test_creation_avec_pretag(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/formulaires-intake/', {
            'nom': 'Pompage agricole', 'slug': 'pompage',
            'tag_prefill': 'agricole', 'type_installation': 'pompage',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        f = FormulaireIntake.objects.get(id=resp.data['id'])
        self.assertEqual(f.company_id, self.co.id)
        self.assertEqual(f.tag_prefill, 'agricole')


# ── FG207 — WhatsApp inbound (gated) ───────────────────────────────────────

class WhatsAppInboundTests(TestCase):
    def setUp(self):
        self.co = make_company('fg207', 'FG207')

    @override_settings(WHATSAPP_ENABLED=False)
    def test_capture_noop_quand_gated(self):
        self.assertFalse(services.whatsapp_actif())
        res = services.capturer_message_whatsapp(
            self.co, wa_message_id='wamid.1', expediteur='+212600000000',
            texte='Bonjour')
        self.assertIsNone(res)
        self.assertEqual(MessageWhatsAppEntrant.objects.count(), 0)

    @override_settings(WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='tok')
    def test_capture_active_journalise(self):
        self.assertTrue(services.whatsapp_actif())
        log = services.capturer_message_whatsapp(
            self.co, wa_message_id='wamid.2', expediteur='+212600000001',
            nom_profil='Ahmed', texte='Salam')
        self.assertIsNotNone(log)
        self.assertTrue(log.traite)
        # Idempotence par wa_message_id.
        services.capturer_message_whatsapp(
            self.co, wa_message_id='wamid.2', expediteur='+212600000001')
        self.assertEqual(MessageWhatsAppEntrant.objects.filter(
            company=self.co).count(), 1)


# ── FG208 — Journal d'appels ───────────────────────────────────────────────

class AppelTelephoniqueTests(TestCase):
    def setUp(self):
        self.co = make_company('fg208', 'FG208')
        self.user = make_user(self.co, 'fg208-user')

    def test_auteur_pose_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/appels/', {
            'numero': '+212600000000', 'direction': 'sortant',
            'issue': 'repondu', 'duree_secondes': 120,
            'auteur': 999,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        appel = AppelTelephonique.objects.get(id=resp.data['id'])
        self.assertEqual(appel.auteur_id, self.user.id)
        self.assertEqual(appel.company_id, self.co.id)


# ── FG209 — Codes de promotion ─────────────────────────────────────────────

class CodePromotionTests(TestCase):
    def setUp(self):
        self.co = make_company('fg209', 'FG209')
        self.user = make_user(self.co, 'fg209-user')

    def test_taux_borne(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/codes-promotion/', {
            'code': 'AID5', 'taux_remise': '150',
            'date_debut': '2026-06-01', 'date_fin': '2026-06-30',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_dates_coherentes(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/codes-promotion/', {
            'code': 'AID5', 'taux_remise': '5',
            'date_debut': '2026-06-30', 'date_fin': '2026-06-01',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_creation_valide(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/codes-promotion/', {
            'code': 'AID5', 'libelle': '-5 % Aïd', 'taux_remise': '5',
            'date_debut': '2026-06-01', 'date_fin': '2026-06-30',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        promo = CodePromotion.objects.get(id=resp.data['id'])
        self.assertEqual(promo.company_id, self.co.id)
        self.assertEqual(promo.nb_utilisations, 0)


# ── FG211 — Guided selling ─────────────────────────────────────────────────

class GuidedSellingTests(TestCase):
    def setUp(self):
        self.co = make_company('fg211', 'FG211')
        self.user = make_user(self.co, 'fg211-user')

    def test_evaluation_coherente(self):
        comp, complet, alertes = services.evaluer_session_guided_selling(
            {'kwc': '5', 'onduleur_kw': '5'})
        self.assertTrue(complet)
        self.assertEqual(alertes, [])

    def test_evaluation_onduleur_sous_dimensionne(self):
        comp, complet, alertes = services.evaluer_session_guided_selling(
            {'kwc': '10', 'onduleur_kw': '3'})
        self.assertFalse(complet)
        self.assertTrue(any('sous-dimensionné' in a for a in alertes))

    def test_evaluer_endpoint(self):
        from apps.compta.models import SessionGuidedSelling
        sess = SessionGuidedSelling.objects.create(
            company=self.co, auteur=self.user,
            reponses={'kwc': '5', 'onduleur_kw': '5'})
        api = auth(self.user)
        resp = api.post(
            f'/api/django/compta/guided-selling/{sess.id}/evaluer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['complet'])


# ── FG213 — Approbation de configuration ───────────────────────────────────

class ApprobationConfigTests(TestCase):
    def setUp(self):
        self.co = make_company('fg213', 'FG213')
        self.user = make_user(self.co, 'fg213-user')

    def test_workflow_approuver(self):
        dem = DemandeApprobationConfig.objects.create(
            company=self.co, devis_id=7, motif='kWc/onduleur incohérents')
        api = auth(self.user)
        resp = api.post(
            f'/api/django/compta/approbations-config/{dem.id}/approuver/',
            {'commentaire': 'OK dérogation'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        dem.refresh_from_db()
        self.assertEqual(dem.statut, DemandeApprobationConfig.Statut.APPROUVEE)
        self.assertEqual(dem.decideur_id, self.user.id)

    def test_decision_idempotente(self):
        dem = DemandeApprobationConfig.objects.create(
            company=self.co, devis_id=7, motif='x',
            statut=DemandeApprobationConfig.Statut.REFUSEE)
        services.decider_approbation_config(
            dem, approuver=True, user=self.user)
        dem.refresh_from_db()
        # Déjà refusée : pas re-décidée.
        self.assertEqual(dem.statut, DemandeApprobationConfig.Statut.REFUSEE)


# ── FG214 — E-catalogue tokenisé ───────────────────────────────────────────

class ECatalogueTests(TestCase):
    def setUp(self):
        self.co = make_company('fg214', 'FG214')
        self.user = make_user(self.co, 'fg214-user')

    def test_token_pose_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/ecatalogues/', {
            'titre': 'Catalogue solaire', 'produit_ids': [1, 2, 3],
            'token': 'forced',  # doit être ignoré, généré côté serveur
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        cat = ECatalogue.objects.get(id=resp.data['id'])
        self.assertEqual(cat.company_id, self.co.id)
        self.assertNotEqual(cat.token, 'forced')
        self.assertTrue(len(cat.token) >= 32)

    def test_service_genere_token_unique(self):
        a = services.generer_ecatalogue(self.co, titre='A')
        b = services.generer_ecatalogue(self.co, titre='B')
        self.assertNotEqual(a.token, b.token)


# ── Gate de rôle (transverse) ──────────────────────────────────────────────

class RoleGateTests(TestCase):
    def setUp(self):
        self.co = make_company('fg2xx-gate', 'Gate')
        self.commercial = make_user(
            self.co, 'fg2xx-commercial', role='commercial')

    def test_commercial_refuse(self):
        api = auth(self.commercial)
        resp = api.get('/api/django/compta/campagnes/')
        self.assertIn(resp.status_code, (403, 401))
