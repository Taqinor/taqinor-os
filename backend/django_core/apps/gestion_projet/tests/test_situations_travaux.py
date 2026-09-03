"""Tests des situations de travaux — décomptes progressifs BTP (XPRJ4).

Couvre : le décompte n°N reprend le cumul antérieur du n°N-1, montants
période = cumulé − antérieur, la facture n'est générée qu'une seule fois
(idempotent), la retenue de garantie est déduite, numérotation incrémentale
PAR PROJET (jamais count()+1).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.gestion_projet import services
from apps.gestion_projet.models import (
    LigneSituation, Projet, SituationTravaux)
from apps.ventes.models import Facture

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


class SituationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-situ-svc', 'S')
        self.client_crm = Client.objects.create(company=self.co, nom='Client BTP')
        self.projet = Projet.objects.create(
            company=self.co, code='P-SIT', nom='S', client_id=self.client_crm.id)
        self.user = make_user(self.co, 'situ-svc')

    def test_numerotation_incrementale(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        self.assertEqual(s1.numero, 1)
        self.assertEqual(s2.numero, 2)

    def test_numerotation_ignore_trous(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        s2.delete()
        s3 = services.creer_situation(self.projet, periode=date(2026, 3, 1))
        self.assertEqual(s1.numero, 1)
        self.assertEqual(s3.numero, 2)

    def test_montant_periode_situation_1_egale_cumule(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        ligne = services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        self.assertEqual(ligne.montant_cumule, Decimal('30000.00'))
        self.assertEqual(ligne.montant_cumule_anterieur, Decimal('0'))
        self.assertEqual(ligne.montant_periode, Decimal('30000.00'))

    def test_situation_2_reprend_cumul_anterieur(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        ligne2 = services.ajouter_ligne_situation(
            s2, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('70'))
        self.assertEqual(ligne2.montant_cumule, Decimal('70000.00'))
        self.assertEqual(ligne2.montant_cumule_anterieur, Decimal('30000.00'))
        self.assertEqual(ligne2.montant_periode, Decimal('40000.00'))

    def test_nouveau_lot_sans_precedent_anterieur_zero(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        ligne_nouveau_lot = services.ajouter_ligne_situation(
            s2, libelle='Électricité', montant_marche_ht=Decimal('50000'),
            avancement_cumule_pct=Decimal('20'))
        self.assertEqual(
            ligne_nouveau_lot.montant_cumule_anterieur, Decimal('0'))
        self.assertEqual(ligne_nouveau_lot.montant_periode, Decimal('10000.00'))

    def test_valider_genere_facture_une_seule_fois(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s1 = services.valider_situation(s1, user=self.user)
        self.assertEqual(s1.statut, SituationTravaux.Statut.FACTUREE)
        self.assertIsNotNone(s1.facture_id)
        with self.assertRaises(services.SituationTravauxError):
            services.valider_situation(s1, user=self.user)
        self.assertEqual(
            Facture.objects.filter(company=self.co).count(), 1)

    def test_retenue_garantie_deduite(self):
        s1 = services.creer_situation(
            self.projet, periode=date(2026, 1, 1),
            retenue_garantie_pct=Decimal('10'))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s1 = services.valider_situation(s1, user=self.user)
        facture = Facture.objects.get(id=s1.facture_id)
        # 30000 HT, RG 10% => 3000 déduits => 27000 HT net.
        self.assertEqual(facture.montant_ht, Decimal('27000.00'))

    def test_valider_sans_ligne_refuse(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        with self.assertRaises(services.SituationTravauxError):
            services.valider_situation(s1, user=self.user)

    def test_ajouter_ligne_sur_situation_facturee_refuse(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s1 = services.valider_situation(s1, user=self.user)
        with self.assertRaises(services.SituationTravauxError):
            services.ajouter_ligne_situation(
                s1, libelle='Autre', montant_marche_ht=Decimal('1000'),
                avancement_cumule_pct=Decimal('10'))


class SituationProjetAnnuleTests(TestCase):
    """AUD179 — un projet ANNULÉ ne se facture plus par situation.

    ``valider_situation`` ne vérifiait que ``situation.statut``, jamais
    ``situation.projet.statut`` : un chantier abandonné consommait une
    référence FAC réelle et basculait la situation en FACTUREE.
    """
    BASE = '/api/django/gestion-projet/situations/'

    def setUp(self):
        self.co = make_company('gp-situ-annule', 'N')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client annulé BTP')
        self.user = make_user(self.co, 'situ-annule')
        self.projet = Projet.objects.create(
            company=self.co, code='P-SITN', nom='N',
            client_id=self.client_crm.id)
        self.situation = services.creer_situation(
            self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            self.situation, libelle='Terrassement',
            montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))

    def _annuler(self):
        self.projet.statut = Projet.Statut.ANNULE
        self.projet.save(update_fields=['statut'])

    def test_service_refuse_projet_annule(self):
        self._annuler()
        with self.assertRaises(services.SituationTravauxError):
            services.valider_situation(self.situation, user=self.user)
        self.situation.refresh_from_db()
        self.assertEqual(
            self.situation.statut, SituationTravaux.Statut.BROUILLON)
        self.assertIsNone(self.situation.facture_id)
        self.assertEqual(Facture.objects.filter(company=self.co).count(), 0)

    def test_endpoint_refuse_projet_annule_400(self):
        self._annuler()
        api = auth(self.user)
        resp = api.post(f'{self.BASE}{self.situation.id}/valider/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.situation.refresh_from_db()
        self.assertIsNone(self.situation.facture_id)
        self.assertEqual(Facture.objects.filter(company=self.co).count(), 0)

    def test_projet_actif_reste_facturable(self):
        api = auth(self.user)
        resp = api.post(f'{self.BASE}{self.situation.id}/valider/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'facturee')


class LigneSituationUniciteTests(TestCase):
    """AUD178 — un lot n'apparaît qu'UNE fois par situation.

    La docstring de ``ajouter_ligne_situation`` promettait « ajoute (ou
    remplace) » mais créait inconditionnellement une seconde ligne : corriger
    un avancement en rappelant l'action facturait le lot DEUX fois.
    """
    BASE = '/api/django/gestion-projet/situations/'

    def setUp(self):
        self.co = make_company('gp-situ-uniq', 'U')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client BTP unique')
        self.user = make_user(self.co, 'situ-uniq')
        self.projet = Projet.objects.create(
            company=self.co, code='P-SITU', nom='U',
            client_id=self.client_crm.id)

    def test_ajouter_ligne_deux_fois_remplace_et_facture_une_fois(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'periode': '2026-01-01',
        }, format='json')
        situation_id = resp.data['id']

        # Saisie initiale erronée : 30 %.
        resp = api.post(
            f'{self.BASE}{situation_id}/ajouter-ligne/', {
                'libelle': 'Terrassement',
                'montant_marche_ht': '100000',
                'avancement_cumule_pct': '30',
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # Correction : même libellé, 40 %.
        resp = api.post(
            f'{self.BASE}{situation_id}/ajouter-ligne/', {
                'libelle': 'Terrassement',
                'montant_marche_ht': '100000',
                'avancement_cumule_pct': '40',
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        lignes = LigneSituation.objects.filter(situation_id=situation_id)
        self.assertEqual(lignes.count(), 1)
        ligne = lignes.get()
        self.assertEqual(ligne.avancement_cumule_pct, Decimal('40.00'))
        self.assertEqual(ligne.montant_cumule, Decimal('40000.00'))
        self.assertEqual(ligne.montant_periode, Decimal('40000.00'))

        resp = api.post(f'{self.BASE}{situation_id}/valider/')
        self.assertEqual(resp.status_code, 200, resp.data)
        facture = Facture.objects.get(id=resp.data['facture_id'])
        # Le lot est facturé UNE fois (40 000), pas 30 000 + 40 000.
        self.assertEqual(facture.montant_ht, Decimal('40000.00'))

    def test_cumul_suivant_repart_du_montant_corrige(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('40'))
        services.valider_situation(s1, user=self.user)

        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        ligne2 = services.ajouter_ligne_situation(
            s2, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('70'))
        # Repart du montant CORRIGÉ (40 %), pas de la saisie erronée (30 %).
        self.assertEqual(ligne2.montant_cumule_anterieur, Decimal('40000.00'))
        self.assertEqual(ligne2.montant_periode, Decimal('30000.00'))

    def test_contrainte_db_bloque_le_doublon_direct(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LigneSituation.objects.create(
                    company=self.co, situation=s1, libelle='Terrassement',
                    montant_marche_ht=Decimal('100000'),
                    avancement_cumule_pct=Decimal('50'))

    def test_libelles_distincts_coexistent(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        services.ajouter_ligne_situation(
            s1, libelle='Électricité', montant_marche_ht=Decimal('50000'),
            avancement_cumule_pct=Decimal('20'))
        self.assertEqual(s1.lignes.count(), 2)


class SituationApiTests(TestCase):
    BASE = '/api/django/gestion-projet/situations/'

    def setUp(self):
        self.co = make_company('gp-situ-api', 'A')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client API BTP')
        self.user = make_user(self.co, 'situ-api')
        self.projet = Projet.objects.create(
            company=self.co, code='P-SITA', nom='A',
            client_id=self.client_crm.id)

    def test_creation_pose_numero(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'periode': '2026-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['numero'], 1)

    def test_workflow_ligne_puis_validation(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'periode': '2026-01-01',
        }, format='json')
        situation_id = resp.data['id']

        resp = api.post(
            f'{self.BASE}{situation_id}/ajouter-ligne/', {
                'libelle': 'Terrassement',
                'montant_marche_ht': '100000',
                'avancement_cumule_pct': '30',
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_periode'], '30000.00')

        resp = api.post(f'{self.BASE}{situation_id}/valider/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'facturee')
        self.assertIsNotNone(resp.data['facture_id'])

    def test_isolation_tenant(self):
        co_b = make_company('gp-situ-b', 'B')
        user_b = make_user(co_b, 'situ-b')
        api_owner = auth(self.user)
        resp = api_owner.post(self.BASE, {
            'projet': self.projet.id, 'periode': '2026-01-01',
        }, format='json')
        situation_id = resp.data['id']
        api_b = auth(user_b)
        resp = api_b.post(f'{self.BASE}{situation_id}/valider/')
        self.assertEqual(resp.status_code, 404)


class SituationFigeeApiTests(TestCase):
    """AUD177 — une situation VALIDÉE/FACTURÉE est gelée (ni DELETE ni PATCH).

    Sans la garde, supprimer la situation intermédiaire d'une chaîne
    30 %/60 %/90 % fait repartir le cumul antérieur de la suivante à 30 %,
    et la tranche de 60 % déjà encaissée est facturée une SECONDE fois.
    """
    BASE = '/api/django/gestion-projet/situations/'
    LIGNES = '/api/django/gestion-projet/lignes-situation/'

    def setUp(self):
        self.co = make_company('gp-situ-fige', 'F')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client BTP figé')
        self.user = make_user(self.co, 'situ-fige')
        self.projet = Projet.objects.create(
            company=self.co, code='P-SITF', nom='F',
            client_id=self.client_crm.id)
        self.api = auth(self.user)

    def _situation_facturee(self, periode, pct):
        situation = services.creer_situation(self.projet, periode=periode)
        services.ajouter_ligne_situation(
            situation, libelle='Terrassement',
            montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal(pct))
        return services.valider_situation(situation, user=self.user)

    def test_suppression_situation_facturee_refusee_et_cumul_preserve(self):
        s1 = self._situation_facturee(date(2026, 1, 1), '30')
        s2 = self._situation_facturee(date(2026, 2, 1), '60')

        resp = self.api.delete(f'{self.BASE}{s2.id}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(
            SituationTravaux.objects.filter(pk=s2.id).exists())

        s3 = services.creer_situation(self.projet, periode=date(2026, 3, 1))
        ligne3 = services.ajouter_ligne_situation(
            s3, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('90'))
        # Le cumul antérieur reste celui de la situation n°2 (60 %).
        self.assertEqual(ligne3.montant_cumule_anterieur, Decimal('60000.00'))
        self.assertEqual(ligne3.montant_periode, Decimal('30000.00'))
        services.valider_situation(s3, user=self.user)

        # Le cumul facturé n'excède JAMAIS le montant du marché.
        total_facture = sum(
            Facture.objects.get(id=s.facture_id).montant_ht
            for s in (s1, s2, s3))
        self.assertEqual(total_facture, Decimal('90000.00'))
        self.assertLessEqual(total_facture, Decimal('100000'))

    def test_patch_situation_facturee_refuse(self):
        s1 = self._situation_facturee(date(2026, 1, 1), '30')
        resp = self.api.patch(
            f'{self.BASE}{s1.id}/', {'retenue_garantie_pct': '50'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        s1.refresh_from_db()
        self.assertIsNone(s1.retenue_garantie_pct)

    def test_patch_ligne_de_situation_facturee_refuse(self):
        s1 = self._situation_facturee(date(2026, 1, 1), '30')
        ligne = s1.lignes.first()
        resp = self.api.patch(
            f'{self.LIGNES}{ligne.id}/',
            {'avancement_cumule_pct': '90'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.avancement_cumule_pct, Decimal('30.00'))

    def test_suppression_ligne_de_situation_facturee_refusee(self):
        s1 = self._situation_facturee(date(2026, 1, 1), '30')
        ligne = s1.lignes.first()
        resp = self.api.delete(f'{self.LIGNES}{ligne.id}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(LigneSituation.objects.filter(pk=ligne.id).exists())

    def test_suppression_brouillon_toujours_204(self):
        situation = services.creer_situation(
            self.projet, periode=date(2026, 4, 1))
        resp = self.api.delete(f'{self.BASE}{situation.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(
            SituationTravaux.objects.filter(pk=situation.id).exists())

    def test_patch_brouillon_toujours_autorise(self):
        situation = services.creer_situation(
            self.projet, periode=date(2026, 5, 1))
        resp = self.api.patch(
            f'{self.BASE}{situation.id}/', {'retenue_garantie_pct': '10'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        situation.refresh_from_db()
        self.assertEqual(situation.retenue_garantie_pct, Decimal('10.00'))
