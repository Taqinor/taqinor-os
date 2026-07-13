"""Tests FG229–FG244 — Portail client, partenaires, fidélité & abonnements.

Couvrent, par tâche (tous scopés société, ``company`` jamais lue du corps) :

* FG229 Acceptation/e-signature de devis (portail) — signature horodatée + IP.
* FG230 Paiement en ligne de facture (portail) — NO-OP gated (CMI OFF défaut).
* FG231 Dépôt de documents/factures ONEE par le client.
* FG232 Suivi d'avancement chantier côté client — jalons lecture-seule.
* FG233 Ticket SAV depuis le portail — création/suivi.
* FG234 Portail apporteurs / sous-revendeurs — soumission de leads + statut.
* FG235 Suivi des commissions partenaires.
* FG236 Gestion des territoires / zones commerciales.
* FG237 Annuaire & onboarding des installateurs partenaires.
* FG238 Enquêtes NPS / satisfaction — NO-OP gated + score consolidé.
* FG239 Capture d'avis + push Google Reviews — NO-OP gated.
* FG240 Programme de fidélité / parrainage étendu (points/paliers).
* FG241 Moteur d'upsell / cross-sell.
* FG244 Abonnements de monitoring (revenu récurrent).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    AcceptationDevisPortail, PaiementFacturePortail, DocumentClientPortail,
    JalonChantierPortail, DemandeTicketPortail,
    Partenaire, SoumissionLeadPartenaire, CommissionPartenaire,
    TerritoireCommercial, EnqueteNPS, AvisClient,
    CompteFidelite, MouvementFidelite, RegleUpsell,
    AbonnementMonitoring,
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


# ── FG229 — Acceptation / e-signature de devis (portail) ───────────────────

class AcceptationDevisPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('fg229', 'FG229')
        self.user = make_user(self.co, 'fg229-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/acceptations-devis-portail/', {
            'devis_id': 41001, 'option_choisie': 'Hybride 5 kWc',
            'nom_signataire': 'Reda K.',
            'company': 99999,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        acc = AcceptationDevisPortail.objects.get(id=resp.data['id'])
        self.assertEqual(acc.company_id, self.co.id)
        self.assertFalse(acc.accepte)
        self.assertIsNone(acc.signe_le)

    def test_signer_horodate_et_capture_ip(self):
        api = auth(self.user)
        acc = AcceptationDevisPortail.objects.create(
            company=self.co, devis_id=41002, nom_signataire='Sami')
        resp = api.post(
            f'/api/django/compta/acceptations-devis-portail/{acc.id}/signer/',
            {'nom_signataire': 'Sami B.'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        acc.refresh_from_db()
        self.assertTrue(acc.accepte)
        self.assertIsNotNone(acc.signe_le)
        self.assertEqual(acc.nom_signataire, 'Sami B.')
        self.assertIsNotNone(acc.signature_ip)

    def test_signer_idempotent(self):
        acc = AcceptationDevisPortail.objects.create(
            company=self.co, devis_id=41003, nom_signataire='X')
        services.signer_acceptation_devis(acc, nom='Premier', ip='10.0.0.1')
        premier_horodatage = acc.signe_le
        services.signer_acceptation_devis(acc, nom='Second', ip='10.0.0.2')
        acc.refresh_from_db()
        # Pas resigné : nom & horodatage figés à la première signature.
        self.assertEqual(acc.nom_signataire, 'Premier')
        self.assertEqual(acc.signe_le, premier_horodatage)

    def test_isolation_societe(self):
        autre = make_company('fg229-b', 'FG229B')
        AcceptationDevisPortail.objects.create(
            company=autre, devis_id=41004, nom_signataire='Autre')
        api = auth(self.user)
        resp = api.get('/api/django/compta/acceptations-devis-portail/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)


# ── FG230 — Paiement en ligne des factures (portail, gated CMI) ────────────

class PaiementFacturePortailTests(TestCase):
    def setUp(self):
        self.co = make_company('fg230', 'FG230')
        self.user = make_user(self.co, 'fg230-user')

    def test_creation_pose_company_et_reference(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/paiements-facture-portail/', {
            'facture_id': 42001, 'montant': '12500.00', 'methode': 'carte',
            'company': 88888,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pf = PaiementFacturePortail.objects.get(id=resp.data['id'])
        self.assertEqual(pf.company_id, self.co.id)
        self.assertEqual(pf.statut, PaiementFacturePortail.Statut.INITIE)
        # initier_paiement_facture pose une référence locale.
        self.assertTrue(pf.reference)

    @override_settings(CMI_ENABLED=False)
    def test_cmi_inactif_par_defaut(self):
        self.assertFalse(services.cmi_actif())

    def test_rapprocher_marque_paye(self):
        api = auth(self.user)
        pf = PaiementFacturePortail.objects.create(
            company=self.co, facture_id=42002, montant=999,
            methode=PaiementFacturePortail.Methode.VIREMENT)
        resp = api.post(
            f'/api/django/compta/paiements-facture-portail/{pf.id}/rapprocher/',
            {'reference': 'VIR-2026-001'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        pf.refresh_from_db()
        self.assertEqual(pf.statut, PaiementFacturePortail.Statut.PAYE)
        self.assertIsNotNone(pf.paye_le)
        self.assertEqual(pf.reference, 'VIR-2026-001')

    def test_rapprocher_idempotent(self):
        pf = PaiementFacturePortail.objects.create(
            company=self.co, facture_id=42003, montant=100)
        services.rapprocher_paiement_facture(pf, reference='A')
        premier = pf.paye_le
        services.rapprocher_paiement_facture(pf, reference='B')
        pf.refresh_from_db()
        self.assertEqual(pf.reference, 'A')
        self.assertEqual(pf.paye_le, premier)


# ── FG231 — Dépôt de documents / factures ONEE par le client ───────────────

class DocumentClientPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('fg231', 'FG231')
        self.user = make_user(self.co, 'fg231-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/documents-client-portail/', {
            'client_id': 43001, 'type_document': 'facture_onee',
            'libelle': 'Facture ONEE janvier',
            'company': 77777,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        doc = DocumentClientPortail.objects.get(id=resp.data['id'])
        self.assertEqual(doc.company_id, self.co.id)
        self.assertFalse(doc.traite)

    def test_marquer_traite(self):
        api = auth(self.user)
        doc = DocumentClientPortail.objects.create(
            company=self.co, client_id=43002)
        resp = api.post(
            f'/api/django/compta/documents-client-portail/{doc.id}'
            '/marquer_traite/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        doc.refresh_from_db()
        self.assertTrue(doc.traite)

    def test_isolation_societe(self):
        autre = make_company('fg231-b', 'FG231B')
        DocumentClientPortail.objects.create(company=autre, client_id=43003)
        api = auth(self.user)
        resp = api.get('/api/django/compta/documents-client-portail/')
        self.assertEqual(resp.data['count'], 0)


# ── FG232 — Suivi d'avancement du chantier côté client ─────────────────────

class JalonChantierPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('fg232', 'FG232')
        self.user = make_user(self.co, 'fg232-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/jalons-chantier-portail/', {
            'chantier_id': 44001, 'libelle': 'Installation', 'ordre': 3,
            'company': 66666,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        jalon = JalonChantierPortail.objects.get(id=resp.data['id'])
        self.assertEqual(jalon.company_id, self.co.id)
        self.assertFalse(jalon.atteint)

    def test_marquer_atteint_pose_date(self):
        api = auth(self.user)
        jalon = JalonChantierPortail.objects.create(
            company=self.co, chantier_id=44002, libelle='Réception')
        resp = api.post(
            f'/api/django/compta/jalons-chantier-portail/{jalon.id}'
            '/marquer_atteint/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        jalon.refresh_from_db()
        self.assertTrue(jalon.atteint)
        self.assertIsNotNone(jalon.date_jalon)

    def test_timeline_ordonnee(self):
        JalonChantierPortail.objects.create(
            company=self.co, chantier_id=44003, libelle='B', ordre=2)
        JalonChantierPortail.objects.create(
            company=self.co, chantier_id=44003, libelle='A', ordre=1)
        api = auth(self.user)
        resp = api.get(
            '/api/django/compta/jalons-chantier-portail/?ordering=ordre')
        self.assertEqual(resp.data['count'], 2)
        libelles = [r['libelle'] for r in resp.data['results']]
        self.assertEqual(libelles, ['A', 'B'])

    def test_isolation_societe(self):
        autre = make_company('fg232-b', 'FG232B')
        JalonChantierPortail.objects.create(
            company=autre, chantier_id=44004, libelle='X')
        api = auth(self.user)
        resp = api.get('/api/django/compta/jalons-chantier-portail/')
        self.assertEqual(resp.data['count'], 0)


# ── FG233 — Ouverture de ticket SAV depuis le portail ──────────────────────

class DemandeTicketPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('fg233', 'FG233')
        self.user = make_user(self.co, 'fg233-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/demandes-ticket-portail/', {
            'client_id': 45001, 'sujet': 'Onduleur en défaut',
            'description': 'Voyant rouge depuis hier',
            'company': 55555,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        d = DemandeTicketPortail.objects.get(id=resp.data['id'])
        self.assertEqual(d.company_id, self.co.id)
        self.assertEqual(d.statut, DemandeTicketPortail.Statut.SOUMISE)

    def test_prendre_en_charge_reference_ticket(self):
        api = auth(self.user)
        d = DemandeTicketPortail.objects.create(
            company=self.co, client_id=45002, sujet='X')
        resp = api.post(
            f'/api/django/compta/demandes-ticket-portail/{d.id}'
            '/prendre_en_charge/', {'ticket_id': 909}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        d.refresh_from_db()
        self.assertEqual(d.statut, DemandeTicketPortail.Statut.PRISE_EN_CHARGE)
        self.assertEqual(d.ticket_id, 909)

    def test_isolation_societe(self):
        autre = make_company('fg233-b', 'FG233B')
        DemandeTicketPortail.objects.create(
            company=autre, client_id=45003, sujet='Y')
        api = auth(self.user)
        resp = api.get('/api/django/compta/demandes-ticket-portail/')
        self.assertEqual(resp.data['count'], 0)


# ── XSAV22 — Déflection KB sur le formulaire d'ouverture de ticket ─────────

class Xsav22KbDeflectionActionsTests(TestCase):
    def setUp(self):
        from apps.kb.models import KbArticle
        self.co = make_company('xsav22', 'XSAV22')
        self.user = make_user(self.co, 'xsav22-user')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Onduleur en défaut — que faire ?',
            corps='Vérifiez le code erreur.',
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)
        self.hidden = KbArticle.objects.create(
            company=self.co, titre='Onduleur — note interne',
            statut=KbArticle.Statut.PUBLIE, visible_portail=False)

    def test_suggestions_kb_returns_only_flagged_articles(self):
        api = auth(self.user)
        resp = api.get(
            '/api/django/compta/demandes-ticket-portail/suggestions-kb/'
            '?q=onduleur')
        self.assertEqual(resp.status_code, 200, resp.content)
        ids = {s['id'] for s in resp.data['suggestions']}
        self.assertEqual(ids, {self.article.id})

    def test_suggestions_kb_isolated_by_company(self):
        autre = make_company('xsav22-b', 'XSAV22B')
        autre_user = make_user(autre, 'xsav22-b-user')
        api = auth(autre_user)
        resp = api.get(
            '/api/django/compta/demandes-ticket-portail/suggestions-kb/'
            '?q=onduleur')
        self.assertEqual(resp.data['suggestions'], [])

    def test_consulter_article_kb_increments_counter(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/compta/demandes-ticket-portail/'
            'consulter-article-kb/',
            {'article_id': self.article.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['enregistre'])
        self.article.refresh_from_db()
        self.assertEqual(self.article.consultations_portail_ticket, 1)

    def test_consulter_article_kb_requires_article_id(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/compta/demandes-ticket-portail/'
            'consulter-article-kb/', {}, format='json')
        self.assertEqual(resp.status_code, 400)


# ── FG234 — Portail apporteurs / sous-revendeurs ───────────────────────────

class PartenaireTests(TestCase):
    def setUp(self):
        self.co = make_company('fg234', 'FG234')
        self.user = make_user(self.co, 'fg234-user')

    def test_creation_pose_company_et_token(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/partenaires/', {
            'nom': 'Apporteur Rabat', 'type_partenaire': 'apporteur',
            'taux_commission': '5.00',
            'company': 33333, 'token_acces': 'tricher',  # ignorés
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        p = Partenaire.objects.get(id=resp.data['id'])
        self.assertEqual(p.company_id, self.co.id)
        self.assertTrue(p.token_acces)
        self.assertNotEqual(p.token_acces, 'tricher')

    def test_soumission_lead_pose_company(self):
        api = auth(self.user)
        p = Partenaire.objects.create(
            company=self.co, nom='P', token_acces='tok-fg234-a')
        resp = api.post(
            '/api/django/compta/soumissions-lead-partenaire/', {
                'partenaire': p.id, 'nom_prospect': 'M. Client',
                'ville': 'Casablanca',
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        s = SoumissionLeadPartenaire.objects.get(id=resp.data['id'])
        self.assertEqual(s.company_id, self.co.id)
        self.assertEqual(s.statut, SoumissionLeadPartenaire.Statut.SOUMIS)

    def test_soumission_partenaire_autre_societe_rejetee(self):
        autre = make_company('fg234-b', 'FG234B')
        p_autre = Partenaire.objects.create(
            company=autre, nom='PA', token_acces='tok-fg234-b')
        api = auth(self.user)
        resp = api.post(
            '/api/django/compta/soumissions-lead-partenaire/', {
                'partenaire': p_autre.id, 'nom_prospect': 'X',
            }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_qualifier_reference_lead(self):
        api = auth(self.user)
        p = Partenaire.objects.create(
            company=self.co, nom='P', token_acces='tok-fg234-c')
        s = SoumissionLeadPartenaire.objects.create(
            company=self.co, partenaire=p, nom_prospect='Y')
        resp = api.post(
            '/api/django/compta/soumissions-lead-partenaire/'
            f'{s.id}/qualifier/', {'lead_id': 707}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        s.refresh_from_db()
        self.assertEqual(s.statut, SoumissionLeadPartenaire.Statut.QUALIFIE)
        self.assertEqual(s.lead_id, 707)

    def test_isolation_societe(self):
        autre = make_company('fg234-c', 'FG234C')
        Partenaire.objects.create(
            company=autre, nom='Z', token_acces='tok-fg234-d')
        api = auth(self.user)
        resp = api.get('/api/django/compta/partenaires/')
        self.assertEqual(resp.data['count'], 0)


# ── FG235 — Suivi des commissions partenaires ──────────────────────────────

class CommissionPartenaireTests(TestCase):
    def setUp(self):
        self.co = make_company('fg235', 'FG235')
        self.user = make_user(self.co, 'fg235-user')
        self.p = Partenaire.objects.create(
            company=self.co, nom='P235', taux_commission=Decimal('4.00'),
            token_acces='tok-fg235-a')

    def test_creation_calcule_montant(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/commissions-partenaire/', {
            'partenaire': self.p.id, 'devis_id': 46001,
            'base_ht': '100000.00', 'taux': '5.00',
            'company': 22222,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        c = CommissionPartenaire.objects.get(id=resp.data['id'])
        self.assertEqual(c.company_id, self.co.id)
        self.assertEqual(c.montant, Decimal('5000.00'))

    def test_taux_defaut_du_partenaire(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/commissions-partenaire/', {
            'partenaire': self.p.id, 'base_ht': '50000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        c = CommissionPartenaire.objects.get(id=resp.data['id'])
        # taux non fourni → celui du partenaire (4 %) : 50000×4% = 2000.
        self.assertEqual(c.montant, Decimal('2000.00'))

    def test_marquer_payee(self):
        api = auth(self.user)
        c = CommissionPartenaire.objects.create(
            company=self.co, partenaire=self.p, base_ht=1000, taux=10,
            montant=100)
        resp = api.post(
            '/api/django/compta/commissions-partenaire/'
            f'{c.id}/marquer_payee/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        c.refresh_from_db()
        self.assertEqual(c.statut, CommissionPartenaire.Statut.PAYEE)
        self.assertIsNotNone(c.paye_le)

    def test_releve_agrege_par_partenaire(self):
        CommissionPartenaire.objects.create(
            company=self.co, partenaire=self.p, base_ht=1000, taux=10,
            montant=Decimal('100'),
            statut=CommissionPartenaire.Statut.DUE)
        CommissionPartenaire.objects.create(
            company=self.co, partenaire=self.p, base_ht=2000, taux=10,
            montant=Decimal('200'),
            statut=CommissionPartenaire.Statut.PAYEE)
        api = auth(self.user)
        resp = api.get('/api/django/compta/commissions-partenaire/releve/')
        self.assertEqual(resp.status_code, 200, resp.content)
        entry = next(r for r in resp.data if r['partenaire'] == self.p.id)
        self.assertEqual(entry['due'], 100)
        self.assertEqual(entry['payee'], 200)
        self.assertEqual(entry['total'], 300)

    def test_isolation_societe(self):
        autre = make_company('fg235-b', 'FG235B')
        p2 = Partenaire.objects.create(
            company=autre, nom='PB', token_acces='tok-fg235-b')
        CommissionPartenaire.objects.create(
            company=autre, partenaire=p2, base_ht=1, taux=1, montant=1)
        api = auth(self.user)
        resp = api.get('/api/django/compta/commissions-partenaire/')
        self.assertEqual(resp.data['count'], 0)


# ── FG236 — Gestion des territoires / zones commerciales ───────────────────

class TerritoireCommercialTests(TestCase):
    def setUp(self):
        self.co = make_company('fg236', 'FG236')
        self.user = make_user(self.co, 'fg236-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/territoires-commerciaux/', {
            'nom': 'Grand Casablanca',
            'villes': ['Casablanca', 'Mohammedia'],
            'owner_user_id': 12, 'priorite': 5,
            'company': 11111,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        t = TerritoireCommercial.objects.get(id=resp.data['id'])
        self.assertEqual(t.company_id, self.co.id)

    def test_affecter_matche_ville(self):
        TerritoireCommercial.objects.create(
            company=self.co, nom='Nord', villes=['Tanger', 'Tétouan'],
            owner_user_id=7, priorite=1)
        TerritoireCommercial.objects.create(
            company=self.co, nom='Casa', villes=['Casablanca'],
            owner_user_id=9, priorite=10)
        api = auth(self.user)
        resp = api.get(
            '/api/django/compta/territoires-commerciaux/affecter/'
            '?ville=Casablanca')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['owner_user_id'], 9)

    def test_affecter_priorite_gagne(self):
        TerritoireCommercial.objects.create(
            company=self.co, nom='Large', villes=['maroc'], owner_user_id=1,
            priorite=1)
        TerritoireCommercial.objects.create(
            company=self.co, nom='Precis', villes=['maroc'], owner_user_id=2,
            priorite=99)
        t = services.affecter_territoire(self.co, 'Maroc')
        self.assertEqual(t.owner_user_id, 2)

    def test_affecter_sans_match_renvoie_none(self):
        api = auth(self.user)
        resp = api.get(
            '/api/django/compta/territoires-commerciaux/affecter/'
            '?ville=Inconnue')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['territoire'])

    def test_isolation_societe(self):
        autre = make_company('fg236-b', 'FG236B')
        TerritoireCommercial.objects.create(
            company=autre, nom='Z', villes=['x'])
        api = auth(self.user)
        resp = api.get('/api/django/compta/territoires-commerciaux/')
        self.assertEqual(resp.data['count'], 0)


# ── FG237 — Annuaire & onboarding des installateurs partenaires ────────────

class OnboardingPartenaireTests(TestCase):
    def setUp(self):
        self.co = make_company('fg237', 'FG237')
        self.user = make_user(self.co, 'fg237-user')

    def test_creation_defaut_prospect(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/partenaires/', {
            'nom': 'Installateur Fès', 'type_partenaire': 'installateur',
            'numero_agrement': 'AGR-2026-01', 'zone': 'Fès-Meknès',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        p = Partenaire.objects.get(id=resp.data['id'])
        self.assertEqual(p.statut_onboarding, 'prospect')
        self.assertEqual(p.numero_agrement, 'AGR-2026-01')

    def test_activer_pose_agree_et_date(self):
        api = auth(self.user)
        p = Partenaire.objects.create(
            company=self.co, nom='I', type_partenaire='installateur',
            token_acces='tok-fg237-a', statut_onboarding='en_cours')
        resp = api.post(
            f'/api/django/compta/partenaires/{p.id}/activer/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        p.refresh_from_db()
        self.assertEqual(p.statut_onboarding, 'agree')
        self.assertTrue(p.actif)
        self.assertIsNotNone(p.date_activation)


# ── FG238 — Enquêtes NPS / satisfaction post-installation ──────────────────

class EnqueteNPSTests(TestCase):
    def setUp(self):
        self.co = make_company('fg238', 'FG238')
        self.user = make_user(self.co, 'fg238-user')

    @override_settings(BREVO_ENABLED=False)
    def test_creation_envoi_noop(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/enquetes-nps/', {
            'client_id': 47001, 'chantier_id': 88,
            'company': 12321,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        e = EnqueteNPS.objects.get(id=resp.data['id'])
        self.assertEqual(e.company_id, self.co.id)
        self.assertEqual(e.statut, EnqueteNPS.Statut.ENVOYEE)
        # NO-OP gated : pas d'envoi réel tant que Brevo est OFF.
        self.assertFalse(e.envoi_reel)

    def test_repondre_borne_score_et_categorie(self):
        api = auth(self.user)
        e = EnqueteNPS.objects.create(company=self.co, client_id=47002)
        resp = api.post(
            f'/api/django/compta/enquetes-nps/{e.id}/repondre/',
            {'score': 15, 'commentaire': 'Excellent'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        e.refresh_from_db()
        # borné à 10.
        self.assertEqual(e.score, 10)
        self.assertEqual(e.statut, EnqueteNPS.Statut.REPONDUE)
        self.assertEqual(e.categorie, 'promoteur')

    def test_score_consolide(self):
        # 3 promoteurs, 1 détracteur → NPS = (3-1)/4*100 = 50.
        for _ in range(3):
            e = EnqueteNPS.objects.create(company=self.co, client_id=1)
            services.repondre_enquete_nps(e, score=10)
        e = EnqueteNPS.objects.create(company=self.co, client_id=2)
        services.repondre_enquete_nps(e, score=3)
        api = auth(self.user)
        resp = api.get('/api/django/compta/enquetes-nps/score/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['total'], 4)
        self.assertEqual(resp.data['nps'], 50)

    def test_isolation_societe(self):
        autre = make_company('fg238-b', 'FG238B')
        EnqueteNPS.objects.create(company=autre, client_id=47003)
        api = auth(self.user)
        resp = api.get('/api/django/compta/enquetes-nps/')
        self.assertEqual(resp.data['count'], 0)


# ── FG239 — Capture d'avis + push Google Reviews ───────────────────────────

class AvisClientTests(TestCase):
    def setUp(self):
        self.co = make_company('fg239', 'FG239')
        self.user = make_user(self.co, 'fg239-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/avis-clients/', {
            'client_id': 48001,
            'company': 32123,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        a = AvisClient.objects.get(id=resp.data['id'])
        self.assertEqual(a.company_id, self.co.id)
        self.assertEqual(a.statut, AvisClient.Statut.SOLLICITE)

    def test_recevoir_borne_note(self):
        api = auth(self.user)
        a = AvisClient.objects.create(company=self.co, client_id=48002)
        resp = api.post(
            f'/api/django/compta/avis-clients/{a.id}/recevoir/',
            {'note': 9, 'temoignage': 'Super équipe'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        a.refresh_from_db()
        self.assertEqual(a.note, 5)  # borné à 5.
        self.assertEqual(a.statut, AvisClient.Statut.RECU)

    @override_settings(GOOGLE_REVIEW_URL='')
    def test_push_google_noop_sans_url(self):
        api = auth(self.user)
        a = AvisClient.objects.create(
            company=self.co, client_id=48003,
            statut=AvisClient.Statut.RECU)
        resp = api.post(
            f'/api/django/compta/avis-clients/{a.id}/pousser_google/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        a.refresh_from_db()
        # NO-OP : pas d'URL configurée → statut inchangé, pas de lien.
        self.assertEqual(a.statut, AvisClient.Statut.RECU)
        self.assertEqual(a.google_review_url, '')

    @override_settings(GOOGLE_REVIEW_URL='https://g.page/r/abc/review')
    def test_push_google_route_quand_configure(self):
        api = auth(self.user)
        a = AvisClient.objects.create(
            company=self.co, client_id=48004,
            statut=AvisClient.Statut.RECU)
        resp = api.post(
            f'/api/django/compta/avis-clients/{a.id}/pousser_google/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        a.refresh_from_db()
        self.assertEqual(a.statut, AvisClient.Statut.PUBLIE_GOOGLE)
        self.assertTrue(a.google_review_url)

    def test_isolation_societe(self):
        autre = make_company('fg239-b', 'FG239B')
        AvisClient.objects.create(company=autre, client_id=48005)
        api = auth(self.user)
        resp = api.get('/api/django/compta/avis-clients/')
        self.assertEqual(resp.data['count'], 0)


# ── FG240 — Programme de fidélité / parrainage étendu ──────────────────────

class FideliteTests(TestCase):
    def setUp(self):
        self.co = make_company('fg240', 'FG240')
        self.user = make_user(self.co, 'fg240-user')

    def test_creation_compte_pose_company(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/comptes-fidelite/', {
            'client_id': 49001,
            'company': 21212, 'points': 9999,  # ignorés (read-only)
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        c = CompteFidelite.objects.get(id=resp.data['id'])
        self.assertEqual(c.company_id, self.co.id)
        self.assertEqual(c.points, 0)
        self.assertEqual(c.palier, 'bronze')

    def test_crediter_recalcule_palier(self):
        api = auth(self.user)
        c = CompteFidelite.objects.create(company=self.co, client_id=49002)
        resp = api.post(
            f'/api/django/compta/comptes-fidelite/{c.id}/crediter/',
            {'points': 2500, 'motif': 'Parrainage réussi'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        c.refresh_from_db()
        self.assertEqual(c.points, 2500)
        self.assertEqual(c.palier, 'or')  # 2000–4999.

    def test_mouvement_via_endpoint_recalcule_solde(self):
        api = auth(self.user)
        c = CompteFidelite.objects.create(
            company=self.co, client_id=49003, points=600, palier='argent')
        resp = api.post('/api/django/compta/mouvements-fidelite/', {
            'compte': c.id, 'points': -100, 'motif': 'Remise convertie',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        c.refresh_from_db()
        self.assertEqual(c.points, 500)
        self.assertEqual(c.palier, 'argent')
        # Un SEUL mouvement créé (pas de double insertion).
        self.assertEqual(
            MouvementFidelite.objects.filter(compte=c).count(), 1)

    def test_solde_ne_descend_pas_sous_zero(self):
        c = CompteFidelite.objects.create(
            company=self.co, client_id=49004, points=50)
        services.appliquer_mouvement_fidelite(c, points=-500, motif='x')
        c.refresh_from_db()
        self.assertEqual(c.points, 0)

    def test_mouvement_compte_autre_societe_rejete(self):
        autre = make_company('fg240-b', 'FG240B')
        c_autre = CompteFidelite.objects.create(
            company=autre, client_id=49005)
        api = auth(self.user)
        resp = api.post('/api/django/compta/mouvements-fidelite/', {
            'compte': c_autre.id, 'points': 10,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe(self):
        autre = make_company('fg240-c', 'FG240C')
        CompteFidelite.objects.create(company=autre, client_id=49006)
        api = auth(self.user)
        resp = api.get('/api/django/compta/comptes-fidelite/')
        self.assertEqual(resp.data['count'], 0)


# ── FG241 — Moteur d'upsell / cross-sell ───────────────────────────────────

class RegleUpsellTests(TestCase):
    def setUp(self):
        self.co = make_company('fg241', 'FG241')
        self.user = make_user(self.co, 'fg241-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/regles-upsell/', {
            'declencheur': 'sans_batterie',
            'produit_suggere': 'Batterie LiFePO4 5 kWh',
            'message': 'Stockez votre surplus', 'priorite': 5,
            'company': 13131,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        r = RegleUpsell.objects.get(id=resp.data['id'])
        self.assertEqual(r.company_id, self.co.id)

    def test_suggestions_matche_contexte(self):
        RegleUpsell.objects.create(
            company=self.co, declencheur='sans_batterie',
            produit_suggere='Batterie', priorite=10)
        RegleUpsell.objects.create(
            company=self.co, declencheur='sans_contrat_om',
            produit_suggere='Contrat O&M', priorite=5)
        RegleUpsell.objects.create(
            company=self.co, declencheur='site_unique',
            produit_suggere='2e site', actif=False)
        api = auth(self.user)
        resp = api.post('/api/django/compta/regles-upsell/suggestions/', {
            'contexte': {
                'sans_batterie': True, 'sans_contrat_om': True,
                'site_unique': True,  # règle inactive → exclue
            },
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        produits = [r['produit_suggere'] for r in resp.data]
        # Triées par priorité décroissante ; règle inactive exclue.
        self.assertEqual(produits, ['Batterie', 'Contrat O&M'])

    def test_suggestions_contexte_vide(self):
        RegleUpsell.objects.create(
            company=self.co, declencheur='sans_batterie',
            produit_suggere='Batterie')
        regles = services.suggestions_upsell(self.co, {})
        self.assertEqual(regles, [])

    def test_isolation_societe(self):
        autre = make_company('fg241-b', 'FG241B')
        RegleUpsell.objects.create(
            company=autre, declencheur='sans_batterie',
            produit_suggere='X')
        api = auth(self.user)
        resp = api.get('/api/django/compta/regles-upsell/')
        self.assertEqual(resp.data['count'], 0)


# ── FG244 — Abonnements de monitoring (revenu récurrent) ───────────────────

class AbonnementMonitoringTests(TestCase):
    def setUp(self):
        self.co = make_company('fg244', 'FG244')
        self.user = make_user(self.co, 'fg244-user')

    def test_creation_pose_company_et_echeance(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/abonnements-monitoring/', {
            'client_id': 50001, 'installation_id': 12,
            'periodicite': 'mensuel', 'montant': '199.00',
            'company': 41414,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        a = AbonnementMonitoring.objects.get(id=resp.data['id'])
        self.assertEqual(a.company_id, self.co.id)
        self.assertEqual(a.statut, AbonnementMonitoring.Statut.ACTIF)
        # 1re échéance calculée à la création.
        self.assertIsNotNone(a.prochaine_echeance)
        self.assertIsNotNone(a.date_debut)

    def test_prochaine_echeance_mensuel_vs_annuel(self):
        from datetime import date
        m = services.prochaine_echeance_abonnement(
            date(2026, 1, 31), 'mensuel')
        self.assertEqual(m, date(2026, 2, 28))  # borné fin de mois.
        a = services.prochaine_echeance_abonnement(
            date(2026, 3, 15), 'annuel')
        self.assertEqual(a, date(2027, 3, 15))

    def test_renouveler_avance_echeance(self):
        from datetime import date
        api = auth(self.user)
        a = AbonnementMonitoring.objects.create(
            company=self.co, client_id=50002, periodicite='mensuel',
            date_debut=date(2026, 1, 1),
            prochaine_echeance=date(2030, 1, 1))
        avant = a.prochaine_echeance
        resp = api.post(
            f'/api/django/compta/abonnements-monitoring/{a.id}/renouveler/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        a.refresh_from_db()
        self.assertGreater(a.prochaine_echeance, avant)

    def test_suspendre_bloque_renouvellement(self):
        api = auth(self.user)
        a = AbonnementMonitoring.objects.create(
            company=self.co, client_id=50003, periodicite='mensuel')
        api.post(
            f'/api/django/compta/abonnements-monitoring/{a.id}/suspendre/',
            {}, format='json')
        a.refresh_from_db()
        self.assertEqual(a.statut, AbonnementMonitoring.Statut.SUSPENDU)
        # Renouveler un abonnement non-actif est un NO-OP.
        avant = a.prochaine_echeance
        services.renouveler_abonnement_monitoring(a)
        a.refresh_from_db()
        self.assertEqual(a.prochaine_echeance, avant)

    def test_a_echeance_liste_les_proches(self):
        from datetime import date, timedelta
        from django.utils import timezone
        today = timezone.localdate()
        AbonnementMonitoring.objects.create(
            company=self.co, client_id=50004, periodicite='mensuel',
            prochaine_echeance=today + timedelta(days=5))
        AbonnementMonitoring.objects.create(
            company=self.co, client_id=50005, periodicite='mensuel',
            prochaine_echeance=date(2099, 1, 1))
        api = auth(self.user)
        resp = api.get(
            '/api/django/compta/abonnements-monitoring/a_echeance/?within=30')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['count'], 1)

    def test_isolation_societe(self):
        autre = make_company('fg244-b', 'FG244B')
        AbonnementMonitoring.objects.create(
            company=autre, client_id=50006, periodicite='mensuel')
        api = auth(self.user)
        resp = api.get('/api/django/compta/abonnements-monitoring/')
        self.assertEqual(resp.data['count'], 0)
