"""Tests FG124 — Caisse / petty cash (journal d'espèces).

Couvre : création d'une caisse rattachée à un compte de trésorerie de type
caisse (refus sinon), entrées/sorties d'espèces avec justificatif/pièce, solde
courant théorique + journal cumulé, posting au grand livre (écriture équilibrée
dans le journal CSH, respect du verrou de période FG115), clôture de caisse
(comptage physique, écart compté − théorique) qui fige les mouvements antérieurs
(immutabilité d'audit), garde multi-société (A ne touche jamais la caisse de B)
et endpoints API + gate de rôle.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    Caisse, CompteTresorerie, MouvementCaisse, PeriodeComptable,
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


class CaisseServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg124', 'FG124 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.compte_caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse terrain',
            compte_comptable=services.get_compte(self.co, '5161'))
        self.compte_banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE',
            compte_comptable=services.get_compte(self.co, '5141'))

    def _caisse(self, solde_initial='500'):
        return services.creer_caisse(
            self.co, self.compte_caisse, libelle='Caisse 1',
            solde_initial=Decimal(solde_initial))

    def test_creer_caisse(self):
        caisse = self._caisse()
        self.assertEqual(caisse.company_id, self.co.id)
        self.assertEqual(caisse.solde_initial, Decimal('500'))
        self.assertTrue(caisse.actif)

    def test_creer_caisse_compte_non_caisse_refuse(self):
        with self.assertRaises(ValidationError):
            services.creer_caisse(
                self.co, self.compte_banque, libelle='Mauvaise caisse')

    def test_creer_caisse_compte_autre_societe_refuse(self):
        autre = make_company('fg124-autre', 'Autre')
        services.seed_plan_comptable(autre)
        compte_autre = CompteTresorerie.objects.create(
            company=autre, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse autre',
            compte_comptable=services.get_compte(autre, '5161'))
        with self.assertRaises(ValidationError):
            services.creer_caisse(
                self.co, compte_autre, libelle='Vol')

    def test_mouvement_entree_et_sortie_solde(self):
        caisse = self._caisse('500')
        services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.ENTREE, montant=Decimal('200'),
            date_mouvement=date(2026, 2, 1), motif='Appoint')
        services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.SORTIE, montant=Decimal('120'),
            date_mouvement=date(2026, 2, 2), motif='Achat visserie',
            justificatif='TICKET-12')
        # 500 + 200 − 120 = 580
        self.assertEqual(services.solde_caisse(caisse), Decimal('580'))
        self.assertEqual(selectors.solde_caisse_a(caisse), Decimal('580'))

    def test_mouvement_montant_negatif_refuse(self):
        caisse = self._caisse()
        with self.assertRaises(ValidationError):
            services.enregistrer_mouvement_caisse(
                caisse, sens=MouvementCaisse.Sens.SORTIE,
                montant=Decimal('-10'), date_mouvement=date(2026, 2, 1),
                motif='Négatif')

    def test_montant_signe(self):
        caisse = self._caisse('0')
        entree = services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.ENTREE, montant=Decimal('50'),
            date_mouvement=date(2026, 2, 1), motif='E')
        sortie = services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.SORTIE, montant=Decimal('30'),
            date_mouvement=date(2026, 2, 2), motif='S')
        self.assertEqual(entree.montant_signe, Decimal('50'))
        self.assertEqual(sortie.montant_signe, Decimal('-30'))

    def test_journal_solde_cumule(self):
        caisse = self._caisse('100')
        services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.ENTREE, montant=Decimal('40'),
            date_mouvement=date(2026, 2, 1), motif='E')
        services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.SORTIE, montant=Decimal('25'),
            date_mouvement=date(2026, 2, 2), motif='S')
        journal = selectors.journal_caisse(caisse)
        self.assertEqual(len(journal), 2)
        self.assertEqual(journal[0]['solde_courant'], Decimal('140'))
        self.assertEqual(journal[1]['solde_courant'], Decimal('115'))

    def test_poster_mouvement_entree_equilibre(self):
        caisse = self._caisse('0')
        ventes = services.get_compte(self.co, '7121')
        mvt = services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.ENTREE, montant=Decimal('300'),
            date_mouvement=date(2026, 2, 1), motif='Recette',
            compte_contrepartie=ventes, poster=True)
        mvt.refresh_from_db()
        self.assertTrue(mvt.posted)
        self.assertIsNotNone(mvt.ecriture)
        ecr = mvt.ecriture
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.journal.type_journal, 'CSH')
        # Caisse débitée (5161), ventes crédité.
        ligne_caisse = ecr.lignes.get(compte__numero='5161')
        self.assertEqual(ligne_caisse.debit, Decimal('300'))
        ligne_ventes = ecr.lignes.get(compte__numero='7121')
        self.assertEqual(ligne_ventes.credit, Decimal('300'))

    def test_poster_mouvement_sortie_charge(self):
        caisse = self._caisse('500')
        charge = services.get_compte(self.co, '6125')
        mvt = services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.SORTIE, montant=Decimal('80'),
            date_mouvement=date(2026, 2, 3), motif='Achat terrain',
            compte_contrepartie=charge, poster=True)
        ecr = mvt.ecriture
        self.assertTrue(ecr.est_equilibree)
        # Charge débitée, caisse créditée.
        self.assertEqual(
            ecr.lignes.get(compte__numero='6125').debit, Decimal('80'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='5161').credit, Decimal('80'))

    def test_poster_idempotent(self):
        caisse = self._caisse('0')
        mvt = services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.ENTREE, montant=Decimal('100'),
            date_mouvement=date(2026, 2, 1), motif='E', poster=True)
        ecr1 = mvt.ecriture
        ecr2 = services.poster_mouvement_caisse(mvt)
        self.assertEqual(ecr1.id, ecr2.id)

    def test_poster_refuse_periode_verrouillee(self):
        caisse = self._caisse('0')
        PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)
        mvt = services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.ENTREE, montant=Decimal('50'),
            date_mouvement=date(2026, 2, 10), motif='E')
        with self.assertRaises(ValidationError):
            services.poster_mouvement_caisse(mvt)

    def test_cloturer_caisse_ecart(self):
        caisse = self._caisse('500')
        services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.SORTIE, montant=Decimal('120'),
            date_mouvement=date(2026, 2, 2), motif='Achat')
        # Théorique = 380 ; on compte 375 → manquant de 5.
        cloture = services.cloturer_caisse(
            caisse, date_cloture=date(2026, 2, 28),
            solde_compte=Decimal('375'), commentaire='Comptage fin février')
        self.assertEqual(cloture.solde_theorique, Decimal('380'))
        self.assertEqual(cloture.solde_compte, Decimal('375'))
        self.assertEqual(cloture.ecart, Decimal('-5'))
        self.assertEqual(cloture.company_id, self.co.id)

    def test_cloture_fige_mouvements_anterieurs(self):
        caisse = self._caisse('500')
        mvt = services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.SORTIE, montant=Decimal('100'),
            date_mouvement=date(2026, 2, 5), motif='Achat')
        services.cloturer_caisse(
            caisse, date_cloture=date(2026, 2, 28),
            solde_compte=Decimal('400'))
        # Le mouvement antérieur à la clôture est immuable.
        mvt.motif = 'Modifié'
        with self.assertRaises(ValidationError):
            mvt.save()
        with self.assertRaises(ValidationError):
            mvt.delete()
        # On ne peut plus saisir un mouvement daté avant ou à la clôture.
        with self.assertRaises(ValidationError):
            services.enregistrer_mouvement_caisse(
                caisse, sens=MouvementCaisse.Sens.ENTREE,
                montant=Decimal('10'), date_mouvement=date(2026, 2, 20),
                motif='Tardive')

    def test_mouvement_apres_cloture_autorise(self):
        caisse = self._caisse('500')
        services.cloturer_caisse(
            caisse, date_cloture=date(2026, 2, 28),
            solde_compte=Decimal('500'))
        # Un mouvement après la date de clôture passe.
        mvt = services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.ENTREE, montant=Decimal('60'),
            date_mouvement=date(2026, 3, 1), motif='Mars')
        self.assertEqual(mvt.company_id, self.co.id)

    def test_cloture_date_anterieure_refuse(self):
        caisse = self._caisse('0')
        services.cloturer_caisse(
            caisse, date_cloture=date(2026, 2, 28),
            solde_compte=Decimal('0'))
        with self.assertRaises(ValidationError):
            services.cloturer_caisse(
                caisse, date_cloture=date(2026, 2, 15),
                solde_compte=Decimal('0'))

    def test_resume_caisse(self):
        caisse = self._caisse('100')
        services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.ENTREE, montant=Decimal('200'),
            date_mouvement=date(2026, 2, 1), motif='E')
        services.enregistrer_mouvement_caisse(
            caisse, sens=MouvementCaisse.Sens.SORTIE, montant=Decimal('50'),
            date_mouvement=date(2026, 2, 2), motif='S')
        resume = selectors.resume_caisse(caisse)
        self.assertEqual(resume['solde_initial'], Decimal('100'))
        self.assertEqual(resume['total_entrees'], Decimal('200'))
        self.assertEqual(resume['total_sorties'], Decimal('50'))
        self.assertEqual(resume['nb_mouvements'], 2)
        self.assertEqual(resume['solde_courant'], Decimal('250'))


class CaisseApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg124-a', 'FG124 A')
        self.co_b = make_company('fg124-b', 'FG124 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.treso_a = CompteTresorerie.objects.create(
            company=self.co_a, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse A',
            compte_comptable=services.get_compte(self.co_a, '5161'))
        self.user_a = make_user(self.co_a, 'fg124-user-a')
        self.user_b = make_user(self.co_b, 'fg124-user-b')

    def test_endpoint_create_et_mouvement_et_resume(self):
        api = auth(self.user_a)
        resp = api.post('/api/django/compta/caisses/', {
            'compte_tresorerie': self.treso_a.id,
            'libelle': 'Caisse terrain',
            'solde_initial': '500',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        caisse_id = resp.data['id']
        # Solde courant = solde initial à la création.
        self.assertEqual(Decimal(str(resp.data['solde_courant'])),
                         Decimal('500'))
        # Entrée puis sortie via l'endpoint mouvement.
        resp_e = api.post(
            f'/api/django/compta/caisses/{caisse_id}/mouvement/', {
                'sens': 'entree', 'montant': '200',
                'date_mouvement': '2026-02-01', 'motif': 'Appoint',
            }, format='json')
        self.assertEqual(resp_e.status_code, 201, resp_e.data)
        resp_s = api.post(
            f'/api/django/compta/caisses/{caisse_id}/mouvement/', {
                'sens': 'sortie', 'montant': '120',
                'date_mouvement': '2026-02-02', 'motif': 'Achat',
                'justificatif': 'TICKET-9',
            }, format='json')
        self.assertEqual(resp_s.status_code, 201, resp_s.data)
        # Journal d'espèces (GET).
        resp_j = api.get(
            f'/api/django/compta/caisses/{caisse_id}/mouvement/')
        self.assertEqual(resp_j.status_code, 200)
        self.assertEqual(len(resp_j.data), 2)
        # Résumé : solde courant = 580.
        resp_r = api.get(
            f'/api/django/compta/caisses/{caisse_id}/resume/')
        self.assertEqual(resp_r.status_code, 200)
        self.assertEqual(Decimal(str(resp_r.data['solde_courant'])),
                         Decimal('580'))

    def test_endpoint_montant_negatif_refuse(self):
        api = auth(self.user_a)
        caisse = services.creer_caisse(
            self.co_a, self.treso_a, libelle='C')
        resp = api.post(
            f'/api/django/compta/caisses/{caisse.id}/mouvement/', {
                'sens': 'sortie', 'montant': '-5',
                'date_mouvement': '2026-02-01', 'motif': 'Bad',
            }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_cloturer(self):
        api = auth(self.user_a)
        caisse = services.creer_caisse(
            self.co_a, self.treso_a, libelle='C',
            solde_initial=Decimal('300'))
        resp = api.post(
            f'/api/django/compta/caisses/{caisse.id}/cloturer/', {
                'date_cloture': '2026-02-28', 'solde_compte': '290',
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(str(resp.data['ecart'])), Decimal('-10'))
        # GET liste les clôtures.
        resp_g = api.get(
            f'/api/django/compta/caisses/{caisse.id}/cloturer/')
        self.assertEqual(resp_g.status_code, 200)
        self.assertEqual(len(resp_g.data), 1)

    def test_endpoint_create_refuse_compte_non_caisse(self):
        banque = CompteTresorerie.objects.create(
            company=self.co_a, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque A',
            compte_comptable=services.get_compte(self.co_a, '5141'))
        api = auth(self.user_a)
        resp = api.post('/api/django/compta/caisses/', {
            'compte_tresorerie': banque.id, 'libelle': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_isolation_societe(self):
        # A crée une caisse ; B ne la voit pas.
        services.creer_caisse(self.co_a, self.treso_a, libelle='Privée A')
        resp = auth(self.user_b).get('/api/django/compta/caisses/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(
            data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 0)

    def test_endpoint_create_refuse_compte_autre_societe(self):
        # B tente de créer une caisse sur le compte de trésorerie de A.
        api = auth(self.user_b)
        resp = api.post('/api/django/compta/caisses/', {
            'compte_tresorerie': self.treso_a.id, 'libelle': 'Vol',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg124-normal', role='normal')
        resp = auth(normal).get('/api/django/compta/caisses/')
        self.assertEqual(resp.status_code, 403)

    def test_company_forced_server_side(self):
        # Un corps tentant d'injecter company est ignoré (posée côté serveur).
        api = auth(self.user_a)
        resp = api.post('/api/django/compta/caisses/', {
            'compte_tresorerie': self.treso_a.id, 'libelle': 'C',
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        caisse = Caisse.objects.get(id=resp.data['id'])
        self.assertEqual(caisse.company_id, self.co_a.id)
