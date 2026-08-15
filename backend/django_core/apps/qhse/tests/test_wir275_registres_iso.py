"""WIR275 — API des registres ISO QHSE jusqu'ici SANS exposition REST.

Campagnes de rappel produit (XQHS5), certifications + audits externes
(XQHS9), programme d'audit interne (XQHS10), clauses de norme (XQHS11),
réunions / revues de direction (XQHS12), objectifs 6.2 (XQHS13) — plus la
route PDF de l'analyse 5-Pourquoi/8D d'une NCR (XQHS7), dont le service
``rendre_analyse_ncr_pdf`` n'avait AUCUN appelant.

Couvre : CRUD scopé société (``company`` posée serveur, 404 hors société),
``independance_ok`` ADVISORY (avertit sans bloquer), ``atteint`` dérivé au
save, décision de réunion → CAPA, clôture d'une revue de direction refusée
tant que la checklist ISO 9.3 est incomplète.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.qhse.models import (
    AuditPlanifie, Certification, GrilleAudit, NonConformite, ObjectifQhse,
    ProgrammeAudit, ReunionQhse,
)

User = get_user_model()

CERTIFS = '/api/django/qhse/certifications/'
PROGRAMMES = '/api/django/qhse/programmes-audit/'
PLANIFIES = '/api/django/qhse/audits-planifies/'
REUNIONS = '/api/django/qhse/reunions/'
DECISIONS = '/api/django/qhse/decisions-reunion/'
OBJECTIFS = '/api/django/qhse/objectifs/'
REVUES = '/api/django/qhse/revues-objectif/'
CLAUSES = '/api/django/qhse/clauses-norme/'
CAMPAGNES = '/api/django/qhse/campagnes-rappel/'


def _company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def _user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RegistresIsoApiTests(TestCase):
    def setUp(self):
        self.company = _company('wir275-co', 'WIR275 Co')
        self.autre = _company('wir275-autre', 'WIR275 Autre')
        self.user = _user(self.company, 'wir275_user')
        self.user_autre = _user(self.autre, 'wir275_autre')
        self.api = _auth(self.user)
        self.api_autre = _auth(self.user_autre)

    # ── Certifications ───────────────────────────────────────────────────
    def test_certification_creee_avec_company_serveur(self):
        resp = self.api.post(CERTIFS, {
            'referentiel': 'iso_9001', 'organisme': 'IMANOR',
            'numero_certificat': 'MA-9001-1',
            # `company` postée volontairement : elle DOIT être ignorée.
            'company': self.autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        certif = Certification.objects.get(pk=resp.data['id'])
        self.assertEqual(certif.company_id, self.company.id)
        self.assertEqual(resp.data['statut_calcule'], 'valide')

    def test_certification_invisible_hors_societe(self):
        certif = Certification.objects.create(
            company=self.company, referentiel='iso_9001')
        resp = self.api_autre.get(f'{CERTIFS}{certif.id}/')
        self.assertEqual(resp.status_code, 404)

    # ── Programme d'audit + indépendance ADVISORY ────────────────────────
    def test_independance_ok_avertit_sans_bloquer(self):
        programme = ProgrammeAudit.objects.create(
            company=self.company, annee=2026)
        grille = GrilleAudit.objects.create(
            company=self.company, nom='Grille achats')
        resp = self.api.post(PLANIFIES, {
            'programme': programme.id,
            'processus_domaine': 'Achats',
            'grille': grille.id,
            'auditeur': self.user.id,
            'responsable_domaine': self.user.id,
        }, format='json')
        # L'enregistrement PASSE (advisory) mais le drapeau est faux.
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data['independance_ok'])
        self.assertTrue(
            AuditPlanifie.objects.filter(pk=resp.data['id']).exists())

    def test_instancier_audit_planifie_est_idempotent(self):
        programme = ProgrammeAudit.objects.create(
            company=self.company, annee=2027)
        grille = GrilleAudit.objects.create(
            company=self.company, nom='Grille HSE')
        planifie = AuditPlanifie.objects.create(
            company=self.company, programme=programme,
            processus_domaine='HSE', grille=grille)
        premier = self.api.post(f'{PLANIFIES}{planifie.id}/instancier/')
        self.assertEqual(premier.status_code, 200, premier.data)
        audit_id = premier.data['audit']
        self.assertIsNotNone(audit_id)
        second = self.api.post(f'{PLANIFIES}{planifie.id}/instancier/')
        self.assertEqual(second.data['audit'], audit_id)

    def test_programme_hors_societe_refuse_en_ecriture(self):
        programme = ProgrammeAudit.objects.create(
            company=self.autre, annee=2028)
        grille = GrilleAudit.objects.create(
            company=self.company, nom='Grille X')
        resp = self.api.post(PLANIFIES, {
            'programme': programme.id, 'processus_domaine': 'X',
            'grille': grille.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── Réunion / revue de direction ─────────────────────────────────────
    def test_cloture_revue_direction_refusee_si_checklist_incomplete(self):
        reunion = ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.REVUE_DIRECTION,
            checklist_revue_direction={'kpi': True})
        resp = self.api.post(f'{REUNIONS}{reunion.id}/cloturer/')
        self.assertEqual(resp.status_code, 400)
        reunion.refresh_from_db()
        self.assertNotEqual(reunion.statut, ReunionQhse.Statut.CLOTUREE)

    def test_cloture_revue_direction_ok_checklist_complete(self):
        reunion = ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.REVUE_DIRECTION,
            checklist_revue_direction={
                cle: True
                for cle in ReunionQhse.CHECKLIST_REVUE_DIRECTION_CLES},
        )
        resp = self.api.post(f'{REUNIONS}{reunion.id}/cloturer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], ReunionQhse.Statut.CLOTUREE)
        self.assertTrue(resp.data['checklist_9_3_complete'])

    def test_decision_de_reunion_cree_une_capa_idempotente(self):
        reunion = ReunionQhse.objects.create(
            company=self.company,
            type_reunion=ReunionQhse.TypeReunion.REUNION_HSE)
        creation = self.api.post(DECISIONS, {
            'reunion': reunion.id,
            'texte': 'Recruter un second technicien SAV.',
        }, format='json')
        self.assertEqual(creation.status_code, 201, creation.data)
        decision_id = creation.data['id']
        self.assertIsNone(creation.data['capa_id'])

        premier = self.api.post(f'{DECISIONS}{decision_id}/creer-capa/')
        self.assertEqual(premier.status_code, 200, premier.data)
        capa_id = premier.data['capa_id']
        self.assertIsNotNone(capa_id)
        second = self.api.post(f'{DECISIONS}{decision_id}/creer-capa/')
        self.assertEqual(second.data['capa_id'], capa_id)

    # ── Objectifs 6.2 : `atteint` DÉRIVÉ ─────────────────────────────────
    def test_atteint_est_derive_jamais_saisi(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Baisser les accidents',
            valeur_cible=12,
            sens_amelioration=ObjectifQhse.SensAmelioration.BAISSE)
        resp = self.api.post(REVUES, {
            'objectif': objectif.id, 'periode': 'T2 2026',
            'valeur_constatee': '13.10',
            # Mensonge volontaire : le serveur DOIT le recalculer.
            'atteint': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data['atteint'])

        atteinte = self.api.post(REVUES, {
            'objectif': objectif.id, 'periode': 'T3 2026',
            'valeur_constatee': '11.00',
        }, format='json')
        self.assertTrue(atteinte.data['atteint'])

    def test_objectif_expose_sa_derniere_revue(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Satisfaction client',
            valeur_cible=90)
        self.api.post(REVUES, {
            'objectif': objectif.id, 'periode': 'T1',
            'date_revue': '2026-03-31', 'valeur_constatee': '92',
        }, format='json')
        resp = self.api.get(f'{OBJECTIFS}{objectif.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['derniere_revue'])
        self.assertTrue(resp.data['derniere_revue']['atteint'])

    # ── Clauses de norme + campagnes de rappel (scope) ───────────────────
    @staticmethod
    def _rows(response):
        data = response.data
        return data['results'] if isinstance(data, dict) else data

    def test_clause_norme_scopee_societe(self):
        creation = self.api.post(CLAUSES, {
            'referentiel': '9001', 'numero': '8.5.1',
            'intitule': 'Maîtrise de la production',
        }, format='json')
        self.assertEqual(creation.status_code, 201, creation.data)
        self.assertEqual(len(self._rows(self.api.get(CLAUSES))), 1)
        # La société voisine ne voit RIEN de ce référentiel.
        self.assertEqual(len(self._rows(self.api_autre.get(CLAUSES))), 0)

    def test_campagne_rappel_listee_pour_sa_societe(self):
        resp = self.api.get(CAMPAGNES)
        self.assertEqual(resp.status_code, 200)


class AnalyseNcrPdfRouteTests(TestCase):
    """XQHS7 / WIR275 — la route PDF de l'analyse 5-Pourquoi/8D."""

    def setUp(self):
        self.company = _company('wir275-pdf', 'WIR275 PDF')
        self.user = _user(self.company, 'wir275_pdf_user')
        self.api = _auth(self.user)
        self.ncr = NonConformite.objects.create(
            company=self.company, titre='Panneau fissuré',
            description='Constat réception.')

    def test_404_tant_quaucune_analyse_nexiste(self):
        resp = self.api.get(
            f'/api/django/qhse/non-conformites/{self.ncr.id}/analyse/pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_pdf_telechargeable_apres_enregistrement_de_lanalyse(self):
        enregistrement = self.api.post(
            f'/api/django/qhse/non-conformites/{self.ncr.id}/analyse/',
            {'cinq_pourquoi': [
                {'pourquoi': 'Pourquoi fissuré ?', 'reponse': 'Choc'}]},
            format='json')
        self.assertEqual(enregistrement.status_code, 200, enregistrement.data)

        resp = self.api.get(
            f'/api/django/qhse/non-conformites/{self.ncr.id}/analyse/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('analyse-ncr-', resp['Content-Disposition'])
