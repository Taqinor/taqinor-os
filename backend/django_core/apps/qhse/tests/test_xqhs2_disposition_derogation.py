"""Tests XQHS2 — Disposition des non-conformités + dérogation à durée limitée.

Couvre :

* la disposition posée sur une NCR (``poser_disposition``, tracée qui/quand) ;
* la disposition ``retouche`` créant une CAPA pré-remplie (optionnel) ;
* la clôture NCR bloquée tant qu'aucune disposition n'est posée ;
* le modèle ``Derogation`` (acceptation en l'état bornée, expiration) ;
* le sélecteur/relance des dérogations à échéance ;
* l'isolation entre sociétés.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    ActionCorrectivePreventive, Derogation, NonConformite,
)
from apps.qhse.services import (
    cloturer_ncr, derogations_a_relancer, poser_disposition,
    relancer_derogations, verifier_efficacite_capa,
)

User = get_user_model()

NCR_URL = '/api/django/qhse/non-conformites/'
DEROGATIONS_URL = '/api/django/qhse/derogations/'


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


def make_ncr(company, **kwargs):
    defaults = {'titre': 'NCR test XQHS2'}
    defaults.update(kwargs)
    return NonConformite.objects.create(company=company, **defaults)


# ── Service : poser_disposition ─────────────────────────────────────────────

class PoserDispositionTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs2', 'CoXqhs2')
        self.user = make_user(self.company, 'resp-xqhs2')

    def test_pose_disposition_trace_qui_quand(self):
        ncr = make_ncr(self.company)
        poser_disposition(
            ncr, NonConformite.Disposition.REBUT, disposition_par=self.user)
        ncr.refresh_from_db()
        self.assertEqual(ncr.disposition, NonConformite.Disposition.REBUT)
        self.assertEqual(ncr.disposition_par, self.user)
        self.assertIsNotNone(ncr.disposition_le)

    def test_disposition_invalide_leve_valueerror(self):
        ncr = make_ncr(self.company)
        with self.assertRaises(ValueError):
            poser_disposition(ncr, 'invalide')

    def test_retouche_cree_capa_si_demande(self):
        ncr = make_ncr(self.company)
        poser_disposition(
            ncr, NonConformite.Disposition.RETOUCHE,
            disposition_par=self.user, creer_capa_retouche=True)
        self.assertEqual(ncr.actions.count(), 1)
        capa = ncr.actions.first()
        self.assertEqual(
            capa.type_action, ActionCorrectivePreventive.Type.CORRECTIVE)

    def test_retouche_sans_flag_ne_cree_pas_capa(self):
        ncr = make_ncr(self.company)
        poser_disposition(
            ncr, NonConformite.Disposition.RETOUCHE, disposition_par=self.user)
        self.assertEqual(ncr.actions.count(), 0)

    def test_cout_disposition_interne(self):
        ncr = make_ncr(self.company)
        poser_disposition(
            ncr, NonConformite.Disposition.REBUT,
            disposition_par=self.user, cout_disposition='150.00')
        ncr.refresh_from_db()
        self.assertEqual(str(ncr.cout_disposition), '150.00')


# ── Clôture NCR conditionnée à la disposition ───────────────────────────────

class ClotureNcrDispositionTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs2-clot', 'CoXqhs2Clot')
        self.user = make_user(self.company, 'resp-xqhs2-clot')

    def test_cloture_refusee_sans_disposition(self):
        ncr = make_ncr(self.company)
        with self.assertRaises(ValueError):
            cloturer_ncr(ncr)

    def test_cloture_ok_avec_disposition_et_capa_vide(self):
        ncr = make_ncr(self.company)
        poser_disposition(
            ncr, NonConformite.Disposition.ACCEPTE_EN_ETAT,
            disposition_par=self.user)
        cloturer_ncr(ncr)
        ncr.refresh_from_db()
        self.assertEqual(ncr.statut, NonConformite.Statut.CLOTUREE)

    def test_cloture_refusee_si_capa_non_verifiee_meme_avec_disposition(self):
        ncr = make_ncr(self.company)
        poser_disposition(
            ncr, NonConformite.Disposition.RETOUCHE,
            disposition_par=self.user, creer_capa_retouche=True)
        capa = ncr.actions.first()
        capa.statut = ActionCorrectivePreventive.Statut.REALISEE
        capa.save(update_fields=['statut'])
        with self.assertRaises(ValueError):
            cloturer_ncr(ncr)

    def test_cloture_ok_apres_disposition_et_capa_verifiee_efficace(self):
        ncr = make_ncr(self.company)
        poser_disposition(
            ncr, NonConformite.Disposition.RETOUCHE,
            disposition_par=self.user, creer_capa_retouche=True)
        capa = ncr.actions.first()
        capa.statut = ActionCorrectivePreventive.Statut.REALISEE
        capa.save(update_fields=['statut'])
        verifier_efficacite_capa(capa, efficace=True)
        cloturer_ncr(ncr)
        ncr.refresh_from_db()
        self.assertEqual(ncr.statut, NonConformite.Statut.CLOTUREE)


# ── Modèle Derogation ────────────────────────────────────────────────────────

class DerogationModelTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs2-derog', 'CoXqhs2Derog')
        self.ncr = make_ncr(self.company)
        self.today = timezone.localdate()

    def test_active_avant_expiration(self):
        derog = Derogation.objects.create(
            company=self.company, non_conformite=self.ncr,
            date_expiration=self.today + timedelta(days=30))
        self.assertEqual(derog.statut, Derogation.Statut.ACTIVE)

    def test_expire_apres_echeance(self):
        derog = Derogation.objects.create(
            company=self.company, non_conformite=self.ncr,
            date_expiration=self.today - timedelta(days=1))
        self.assertEqual(derog.statut, Derogation.Statut.EXPIREE)

    def test_cloturee_reste_figee_meme_expiree(self):
        derog = Derogation.objects.create(
            company=self.company, non_conformite=self.ncr,
            date_expiration=self.today - timedelta(days=1),
            statut=Derogation.Statut.CLOTUREE)
        self.assertEqual(derog.statut, Derogation.Statut.CLOTUREE)


# ── Sélecteur / relance des dérogations ─────────────────────────────────────

class DerogationRelanceTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs2-rel', 'CoXqhs2Rel')
        self.autre = make_company('co-xqhs2-rel-autre', 'CoXqhs2RelAutre')
        self.ncr = make_ncr(self.company)
        self.approbateur = make_user(self.company, 'approb-xqhs2')
        self.today = timezone.localdate()

    def test_retient_expiration_imminente(self):
        derog = Derogation.objects.create(
            company=self.company, non_conformite=self.ncr,
            date_expiration=self.today + timedelta(days=5),
            prealerte_jours=15, approbateur=self.approbateur)
        result = derogations_a_relancer(self.company, today=self.today)
        self.assertIn(derog, result)

    def test_exclut_hors_fenetre_prealerte(self):
        Derogation.objects.create(
            company=self.company, non_conformite=self.ncr,
            date_expiration=self.today + timedelta(days=90),
            prealerte_jours=15)
        result = derogations_a_relancer(self.company, today=self.today)
        self.assertEqual(result, [])

    def test_isolation_societe(self):
        Derogation.objects.create(
            company=self.company, non_conformite=self.ncr,
            date_expiration=self.today + timedelta(days=1))
        result = derogations_a_relancer(self.autre, today=self.today)
        self.assertEqual(result, [])

    def test_relancer_derogations_digest(self):
        Derogation.objects.create(
            company=self.company, non_conformite=self.ncr,
            date_expiration=self.today + timedelta(days=1),
            approbateur=self.approbateur)
        digest = relancer_derogations(self.company, today=self.today)
        self.assertEqual(digest['total'], 1)
        self.assertEqual(digest['notifiees'], 1)


# ── API ──────────────────────────────────────────────────────────────────────

class DispositionApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs2-api', 'CoXqhs2Api')
        self.user = make_user(self.company, 'resp-xqhs2-api')
        self.client = auth_client(self.user)

    def test_poser_disposition_action(self):
        ncr = make_ncr(self.company)
        resp = self.client.post(
            f'{NCR_URL}{ncr.id}/poser-disposition/',
            {'disposition': 'rebut'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['disposition'], 'rebut')

    def test_poser_disposition_sans_valeur_400(self):
        ncr = make_ncr(self.company)
        resp = self.client.post(
            f'{NCR_URL}{ncr.id}/poser-disposition/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_cloturer_sans_disposition_400(self):
        ncr = make_ncr(self.company)
        resp = self.client.post(
            f'{NCR_URL}{ncr.id}/cloturer/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_derogation_creation_scoped_company(self):
        ncr = make_ncr(self.company)
        resp = self.client.post(DEROGATIONS_URL, {
            'non_conformite': ncr.id,
            'justification': 'Client accepte le lot avec suivi renforcé',
            'date_expiration': (
                timezone.localdate() + timedelta(days=10)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        derog = Derogation.objects.get(pk=resp.data['id'])
        self.assertEqual(derog.company, self.company)
