"""Tests XQHS1 — Workflow complet déclaration AT/MP (loi 18-12).

Couvre :

* la checklist d'étapes légales datées (``EtapeDeclarationAt``) instanciée à
  la création d'une déclaration CNSS, avec échéances calculées côté serveur
  (48 h pour l'avis employeur, 5 j pour le dossier assureur / l'information
  de l'inspection / le certificat médical initial) ;
* les transitions de statut (à faire / fait / hors délai) ;
* le sélecteur ``etapes_at_a_echeance`` (fenêtre de rappel) ;
* le volet maladie professionnelle (déclarable, mêmes échéances) ;
* l'isolation entre sociétés ;
* le gating de rôle sur le viewset.
"""
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import DeclarationCnss, EtapeDeclarationAt
from apps.qhse.selectors import etapes_at_a_echeance
from apps.qhse.services import (
    instancier_etapes_at, marquer_etape_faite, relancer_etapes_at_en_retard,
)
from apps.rh.models import AccidentTravail, DossierEmploye

User = get_user_model()

LIST_URL = '/api/django/qhse/declarations-cnss/'
ETAPES_URL = '/api/django/qhse/etapes-declaration-at/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return (data['results']
            if isinstance(data, dict) and 'results' in data else data)


def make_accident(company, reference, jour):
    employe = DossierEmploye.objects.create(
        company=company, matricule=f'M-{reference}', nom='Test', prenom='X')
    return AccidentTravail.objects.create(
        company=company, employe=employe, reference=reference,
        date_accident=jour)


def make_declaration(company, accident, date_accident, **kwargs):
    return DeclarationCnss.objects.create(
        company=company, accident_travail=accident,
        date_accident=date_accident, **kwargs)


# ── Service : instanciation de la checklist ─────────────────────────────────

class InstancierEtapesAtTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs1', 'CoXqhs1')
        self.jour = date(2026, 6, 10)
        self.acc = make_accident(self.company, 'AT-XQHS1-0001', self.jour)
        self.decl = make_declaration(self.company, self.acc, self.jour)

    def test_instancie_les_etapes_standard(self):
        etapes = instancier_etapes_at(self.decl)
        types = {e.type_etape for e in etapes}
        self.assertEqual(types, {
            EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            EtapeDeclarationAt.TypeEtape.DOSSIER_ASSUREUR,
            EtapeDeclarationAt.TypeEtape.INFORMATION_INSPECTION,
            EtapeDeclarationAt.TypeEtape.CERTIFICAT_MEDICAL,
            EtapeDeclarationAt.TypeEtape.SUIVI_ITT,
            EtapeDeclarationAt.TypeEtape.CERTIFICAT_GUERISON,
        })

    def test_conciliation_non_instanciee_par_defaut(self):
        etapes = instancier_etapes_at(self.decl)
        types = {e.type_etape for e in etapes}
        self.assertNotIn(EtapeDeclarationAt.TypeEtape.CONCILIATION, types)

    def test_conciliation_instanciee_si_requise(self):
        self.decl.conciliation_statut = (
            DeclarationCnss.ConciliationStatut.A_FAIRE)
        self.decl.save(update_fields=['conciliation_statut'])
        etapes = instancier_etapes_at(self.decl)
        types = {e.type_etape for e in etapes}
        self.assertIn(EtapeDeclarationAt.TypeEtape.CONCILIATION, types)

    def test_echeance_avis_employeur_48h(self):
        instancier_etapes_at(self.decl)
        etape = self.decl.etapes.get(
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR)
        base = timezone.make_aware(datetime.combine(self.jour, time.min))
        self.assertEqual(etape.echeance, base + timedelta(hours=48))

    def test_echeance_dossier_assureur_5_jours(self):
        instancier_etapes_at(self.decl)
        etape = self.decl.etapes.get(
            type_etape=EtapeDeclarationAt.TypeEtape.DOSSIER_ASSUREUR)
        base = timezone.make_aware(datetime.combine(self.jour, time.min))
        self.assertEqual(etape.echeance, base + timedelta(days=5))

    def test_echeance_information_inspection_5_jours(self):
        instancier_etapes_at(self.decl)
        etape = self.decl.etapes.get(
            type_etape=EtapeDeclarationAt.TypeEtape.INFORMATION_INSPECTION)
        base = timezone.make_aware(datetime.combine(self.jour, time.min))
        self.assertEqual(etape.echeance, base + timedelta(days=5))

    def test_etapes_sans_delai_fixe_restent_sans_echeance(self):
        instancier_etapes_at(self.decl)
        etape = self.decl.etapes.get(
            type_etape=EtapeDeclarationAt.TypeEtape.SUIVI_ITT)
        self.assertIsNone(etape.echeance)

    def test_idempotent_ne_duplique_pas(self):
        instancier_etapes_at(self.decl)
        nb_avant = self.decl.etapes.count()
        instancier_etapes_at(self.decl)
        self.assertEqual(self.decl.etapes.count(), nb_avant)


# ── Modèle : statut calculé de l'étape ──────────────────────────────────────

class EtapeStatutTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs1-statut', 'CoXqhs1Statut')
        self.jour = date(2026, 1, 1)
        self.acc = make_accident(self.company, 'AT-XQHS1-0002', self.jour)
        self.decl = make_declaration(self.company, self.acc, self.jour)

    def test_a_faire_avant_echeance(self):
        etape = EtapeDeclarationAt.objects.create(
            company=self.company, declaration=self.decl,
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            echeance=timezone.now() + timedelta(days=5))
        self.assertEqual(etape.statut, EtapeDeclarationAt.Statut.A_FAIRE)

    def test_hors_delai_apres_echeance(self):
        etape = EtapeDeclarationAt.objects.create(
            company=self.company, declaration=self.decl,
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            echeance=timezone.now() - timedelta(days=1))
        self.assertEqual(etape.statut, EtapeDeclarationAt.Statut.HORS_DELAI)

    def test_fait_fige_meme_hors_delai(self):
        etape = EtapeDeclarationAt.objects.create(
            company=self.company, declaration=self.decl,
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            echeance=timezone.now() - timedelta(days=1))
        marquer_etape_faite(etape)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, EtapeDeclarationAt.Statut.FAIT)


# ── Sélecteur : fenêtre de rappel ───────────────────────────────────────────

class EtapesAtAEcheanceTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs1-sel', 'CoXqhs1Sel')
        self.autre = make_company('co-xqhs1-autre', 'CoXqhs1Autre')
        self.jour = date(2026, 3, 1)
        self.acc = make_accident(self.company, 'AT-XQHS1-0003', self.jour)
        self.decl = make_declaration(self.company, self.acc, self.jour)

    def test_retient_echeance_imminente(self):
        etape = EtapeDeclarationAt.objects.create(
            company=self.company, declaration=self.decl,
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            echeance=timezone.now() + timedelta(hours=10))
        qs = etapes_at_a_echeance(self.company, within_hours=48)
        self.assertIn(etape, list(qs))

    def test_exclut_deja_faite(self):
        etape = EtapeDeclarationAt.objects.create(
            company=self.company, declaration=self.decl,
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            echeance=timezone.now() + timedelta(hours=1),
            fait_le=timezone.now())
        qs = etapes_at_a_echeance(self.company, within_hours=48)
        self.assertNotIn(etape, list(qs))

    def test_inclut_deja_hors_delai(self):
        etape = EtapeDeclarationAt.objects.create(
            company=self.company, declaration=self.decl,
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            echeance=timezone.now() - timedelta(days=1))
        qs = etapes_at_a_echeance(self.company, within_hours=48)
        self.assertIn(etape, list(qs))

    def test_isolation_societe(self):
        EtapeDeclarationAt.objects.create(
            company=self.company, declaration=self.decl,
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            echeance=timezone.now() + timedelta(hours=1))
        qs = etapes_at_a_echeance(self.autre, within_hours=48)
        self.assertEqual(qs.count(), 0)

    def test_relancer_etapes_at_en_retard_digest(self):
        EtapeDeclarationAt.objects.create(
            company=self.company, declaration=self.decl,
            type_etape=EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
            echeance=timezone.now() - timedelta(hours=1))
        digest = relancer_etapes_at_en_retard(self.company)
        self.assertEqual(digest['total'], 1)
        self.assertIn('items', digest)


# ── API : viewset ────────────────────────────────────────────────────────────

class EtapeDeclarationAtApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs1-api', 'CoXqhs1Api')
        self.autre = make_company('co-xqhs1-api-autre', 'CoXqhs1ApiAutre')
        self.user = make_user(self.company, 'resp-xqhs1', role='responsable')
        self.client = auth_client(self.user)
        self.jour = date(2026, 4, 1)
        self.acc = make_accident(self.company, 'AT-XQHS1-API-0001', self.jour)

    def test_creation_declaration_instancie_checklist(self):
        resp = self.client.post(LIST_URL, {
            'accident_travail': self.acc.id,
            'date_accident': self.jour.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        decl = DeclarationCnss.objects.get(pk=resp.data['id'])
        self.assertGreaterEqual(decl.etapes.count(), 6)

    def test_generer_etapes_action_idempotente(self):
        decl = make_declaration(self.company, self.acc, self.jour)
        instancier_etapes_at(decl)
        nb_avant = decl.etapes.count()
        resp = self.client.post(
            f'{LIST_URL}{decl.id}/generer-etapes/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(decl.etapes.count(), nb_avant)

    def test_marquer_fait_action(self):
        decl = make_declaration(self.company, self.acc, self.jour)
        instancier_etapes_at(decl)
        etape = decl.etapes.first()
        resp = self.client.post(
            f'{ETAPES_URL}{etape.id}/marquer-fait/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, EtapeDeclarationAt.Statut.FAIT)
        self.assertIsNotNone(etape.fait_le)

    def test_isolation_societe_sur_liste(self):
        decl = make_declaration(self.company, self.acc, self.jour)
        instancier_etapes_at(decl)
        autre_user = make_user(
            self.autre, 'resp-xqhs1-autre', role='responsable')
        autre_client = auth_client(autre_user)
        resp = autre_client.get(ETAPES_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_gating_role_normal_refuse(self):
        vendeur = make_user(self.company, 'vendeur-xqhs1', role='vendeur')
        vendeur_client = auth_client(vendeur)
        resp = vendeur_client.get(ETAPES_URL)
        self.assertEqual(resp.status_code, 403)

    def test_declaration_porte_volet_mp(self):
        resp = self.client.post(LIST_URL, {
            'accident_travail': self.acc.id,
            'date_accident': self.jour.isoformat(),
            'est_maladie_professionnelle': True,
            'type_maladie_professionnelle': 'Tableau 3 — affections cutanées',
            'exposition_mp': 'Exposition solvants, 2 ans, poste peinture',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['est_maladie_professionnelle'])
        self.assertEqual(
            resp.data['type_maladie_professionnelle'],
            'Tableau 3 — affections cutanées')
