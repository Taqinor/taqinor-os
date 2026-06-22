"""Tests FG123 — Rapprochement bancaire (relevé ↔ écritures).

Couvre : création d'un rapprochement par compte de trésorerie/période, ajout de
lignes de relevé, pointage relevé ↔ grand livre jusqu'à concordance, synthèse
(solde relevé vs solde GL vs écart), clôture conditionnée à l'écart nul, garde
multi-société (A ne pointe jamais le GL de B) et endpoints API. C'est DISTINCT de
l'import de paiements clients (FG42) : aucune écriture n'est créée par ce module.
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
    CompteTresorerie, LigneReleve, PointageReleve, RapprochementBancaire,
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


def _journal_type(code):
    from apps.compta.models import Journal
    return {
        'VTE': Journal.Type.VENTE, 'ACH': Journal.Type.ACHAT,
        'BNK': Journal.Type.BANQUE, 'CSH': Journal.Type.CAISSE,
        'OD': Journal.Type.OPERATIONS_DIVERSES,
    }[code]


def _ecriture(company, code_journal, lignes_par_numero, *, jour=None):
    """Passe une écriture équilibrée (numero, debit, credit) → lignes GL."""
    journal = services._journal(company, _journal_type(code_journal))
    lignes = []
    for numero, debit, credit in lignes_par_numero:
        lignes.append({
            'compte': services.get_compte(company, numero),
            'debit': Decimal(debit), 'credit': Decimal(credit),
        })
    return services.creer_ecriture(
        company, journal, jour or date(2026, 1, 10), 'Test FG123', lignes)


def ligne_gl(ecriture, numero):
    """Récupère la ligne d'écriture sur le compte ``numero``."""
    return ecriture.lignes.get(compte__numero=numero)


class RapprochementServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg123', 'FG123 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('1000'),
            compte_comptable=services.get_compte(self.co, '5141'))

    def test_creer_rapprochement(self):
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1300'))
        self.assertEqual(rap.statut, RapprochementBancaire.Statut.EN_COURS)
        self.assertEqual(rap.company_id, self.co.id)
        self.assertEqual(rap.solde_releve, Decimal('1300'))
        # date_releve défaut = date_fin.
        self.assertEqual(rap.date_releve, date(2026, 1, 31))

    def test_creer_rapprochement_compte_autre_societe_refuse(self):
        autre = make_company('fg123-autre', 'Autre')
        services.seed_plan_comptable(autre)
        compte_autre = CompteTresorerie.objects.create(
            company=autre, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Autre banque',
            compte_comptable=services.get_compte(autre, '5141'))
        with self.assertRaises(ValidationError):
            services.creer_rapprochement(
                self.co, compte_autre, date_debut=date(2026, 1, 1),
                date_fin=date(2026, 1, 31))

    def test_creer_rapprochement_dates_inversees_refuse(self):
        with self.assertRaises(ValidationError):
            services.creer_rapprochement(
                self.co, self.banque, date_debut=date(2026, 1, 31),
                date_fin=date(2026, 1, 1))

    def test_ajouter_ligne_releve(self):
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1300'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement client', montant=Decimal('300'),
            reference='VIR-1')
        self.assertEqual(ligne.statut, LigneReleve.Statut.NON_POINTEE)
        self.assertEqual(ligne.company_id, self.co.id)
        self.assertEqual(ligne.rapprochement_id, rap.id)

    def test_pointer_concorde_marque_rapprochee(self):
        # Encaissement 300 en banque : débit 5141 / crédit 3421.
        ecr = _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1300'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement client', montant=Decimal('300'))
        gl = ligne_gl(ecr, '5141')
        ligne = services.pointer_ligne_releve(ligne, [gl.id])
        self.assertEqual(ligne.statut, LigneReleve.Statut.RAPPROCHEE)
        self.assertEqual(ligne.montant_pointe, Decimal('300'))
        self.assertEqual(ligne.ecart, Decimal('0'))
        self.assertTrue(ligne.est_concordante)

    def test_pointer_ecart_reste_non_pointee(self):
        ecr = _ecriture(self.co, 'BNK', [
            ('5141', '250', '0'),
            ('3421', '0', '250'),
        ], jour=date(2026, 1, 12))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1250'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement client', montant=Decimal('300'))
        gl = ligne_gl(ecr, '5141')
        ligne = services.pointer_ligne_releve(ligne, [gl.id])
        # GL pointé = 250, relevé = 300 → écart 50, pas concordant.
        self.assertEqual(ligne.statut, LigneReleve.Statut.NON_POINTEE)
        self.assertEqual(ligne.ecart, Decimal('50'))
        self.assertFalse(ligne.est_concordante)

    def test_pointer_plusieurs_lignes_gl(self):
        # Deux encaissements 200 + 100 sur le relevé en une ligne de 300.
        e1 = _ecriture(self.co, 'BNK', [
            ('5141', '200', '0'), ('3421', '0', '200'),
        ], jour=date(2026, 1, 10))
        e2 = _ecriture(self.co, 'BNK', [
            ('5141', '100', '0'), ('3421', '0', '100'),
        ], jour=date(2026, 1, 11))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1300'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Remise groupée', montant=Decimal('300'))
        ligne = services.pointer_ligne_releve(
            ligne, [ligne_gl(e1, '5141').id, ligne_gl(e2, '5141').id])
        self.assertEqual(ligne.montant_pointe, Decimal('300'))
        self.assertTrue(ligne.est_concordante)

    def test_pointer_remplace_pointages(self):
        e1 = _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'), ('3421', '0', '300'),
        ], jour=date(2026, 1, 10))
        e2 = _ecriture(self.co, 'BNK', [
            ('5141', '500', '0'), ('3421', '0', '500'),
        ], jour=date(2026, 1, 11))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1500'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement', montant=Decimal('500'))
        services.pointer_ligne_releve(ligne, [ligne_gl(e1, '5141').id])
        # Re-pointe vers la bonne ligne : remplace, pas additionne.
        ligne = services.pointer_ligne_releve(ligne, [ligne_gl(e2, '5141').id])
        self.assertEqual(ligne.montant_pointe, Decimal('500'))
        self.assertEqual(
            PointageReleve.objects.filter(ligne_releve=ligne).count(), 1)

    def test_pointer_ligne_gl_hors_compte_tresorerie_refuse(self):
        ecr = _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1300'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement client', montant=Decimal('300'))
        # La ligne 3421 n'est pas le compte de trésorerie (5141) → refus.
        gl_3421 = ligne_gl(ecr, '3421')
        with self.assertRaises(ValidationError):
            services.pointer_ligne_releve(ligne, [gl_3421.id])

    def test_resume_solde_releve_vs_gl_vs_ecart(self):
        ecr = _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1300'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement client', montant=Decimal('300'))
        services.pointer_ligne_releve(ligne, [ligne_gl(ecr, '5141').id])
        resume = selectors.resume_rapprochement(rap)
        # Solde GL = 1000 (initial) + 300 (mouvement) = 1300 = solde relevé.
        self.assertEqual(resume['solde_gl'], Decimal('1300'))
        self.assertEqual(resume['solde_releve'], Decimal('1300'))
        self.assertEqual(resume['ecart'], Decimal('0'))
        self.assertEqual(resume['lignes_pointees'], 1)
        self.assertEqual(resume['lignes_non_pointees'], 0)
        self.assertTrue(resume['rapproche'])

    def test_resume_ecart_non_nul(self):
        ecr = _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        # Solde relevé annoncé erroné (1400 au lieu de 1300).
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1400'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement client', montant=Decimal('300'))
        services.pointer_ligne_releve(ligne, [ligne_gl(ecr, '5141').id])
        resume = selectors.resume_rapprochement(rap)
        self.assertEqual(resume['ecart'], Decimal('100'))  # 1400 − 1300
        self.assertFalse(resume['rapproche'])

    def test_cloturer_refuse_si_ecart(self):
        ecr = _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1400'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement', montant=Decimal('300'))
        services.pointer_ligne_releve(ligne, [ligne_gl(ecr, '5141').id])
        with self.assertRaises(ValidationError):
            services.cloturer_rapprochement(rap)
        rap.refresh_from_db()
        self.assertEqual(rap.statut, RapprochementBancaire.Statut.EN_COURS)

    def test_cloturer_ok_quand_tout_concorde(self):
        ecr = _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1300'))
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement', montant=Decimal('300'))
        services.pointer_ligne_releve(ligne, [ligne_gl(ecr, '5141').id])
        services.cloturer_rapprochement(rap)
        rap.refresh_from_db()
        self.assertEqual(rap.statut, RapprochementBancaire.Statut.RAPPROCHE)
        self.assertIsNotNone(rap.date_rapprochement)
        self.assertTrue(rap.est_rapproche)
        # On ne peut plus ajouter de ligne à un rapprochement clôturé.
        with self.assertRaises(ValidationError):
            services.ajouter_ligne_releve(
                rap, date_operation=date(2026, 1, 13),
                libelle='Tardive', montant=Decimal('1'))

    def test_lignes_gl_pointables_drapeau_pointee(self):
        ecr = _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('1300'))
        pointables = selectors.lignes_gl_pointables(rap)
        # Seule la ligne 5141 (compte de trésorerie) est listée.
        self.assertEqual(len(pointables), 1)
        self.assertEqual(pointables[0]['montant'], Decimal('300'))
        self.assertFalse(pointables[0]['pointee'])
        ligne = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 12),
            libelle='Virement', montant=Decimal('300'))
        services.pointer_ligne_releve(ligne, [ligne_gl(ecr, '5141').id])
        pointables = selectors.lignes_gl_pointables(rap)
        self.assertTrue(pointables[0]['pointee'])


class RapprochementIsolationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg123-a', 'FG123 A')
        self.co_b = make_company('fg123-b', 'FG123 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.banque_a = CompteTresorerie.objects.create(
            company=self.co_a, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque A', solde_initial=Decimal('0'),
            compte_comptable=services.get_compte(self.co_a, '5141'))
        self.user_a = make_user(self.co_a, 'fg123-user-a')
        self.user_b = make_user(self.co_b, 'fg123-user-b')

    def test_ne_pointe_jamais_gl_autre_societe(self):
        # Écriture chez B.
        ecr_b = _ecriture(self.co_b, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        rap_a = services.creer_rapprochement(
            self.co_a, self.banque_a, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('300'))
        ligne = services.ajouter_ligne_releve(
            rap_a, date_operation=date(2026, 1, 12),
            libelle='Virement', montant=Decimal('300'))
        gl_b = ecr_b.lignes.get(compte__numero='5141')
        with self.assertRaises(ValidationError):
            services.pointer_ligne_releve(ligne, [gl_b.id])

    def test_endpoint_create_et_resume(self):
        api = auth(self.user_a)
        resp = api.post('/api/django/compta/rapprochements/', {
            'compte_tresorerie': self.banque_a.id,
            'libelle': 'Janvier',
            'date_debut': '2026-01-01',
            'date_fin': '2026-01-31',
            'solde_releve': '300',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rap_id = resp.data['id']
        self.assertEqual(resp.data['statut'], 'en_cours')
        # Une écriture pour avoir du GL à pointer.
        ecr = _ecriture(self.co_a, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        # Ajoute une ligne de relevé via l'endpoint.
        resp_l = api.post(
            f'/api/django/compta/rapprochements/{rap_id}/ligne-releve/', {
                'date_operation': '2026-01-12',
                'libelle': 'Virement', 'montant': '300',
            }, format='json')
        self.assertEqual(resp_l.status_code, 201, resp_l.data)
        ligne_id = resp_l.data['id']
        # Pointe via l'endpoint.
        gl_id = ecr.lignes.get(compte__numero='5141').id
        resp_p = api.post(
            f'/api/django/compta/rapprochements/{rap_id}/pointer/', {
                'ligne_releve': ligne_id, 'lignes_gl': [gl_id],
            }, format='json')
        self.assertEqual(resp_p.status_code, 200, resp_p.data)
        self.assertEqual(resp_p.data['statut'], 'rapprochee')
        # Résumé.
        resp_r = api.get(
            f'/api/django/compta/rapprochements/{rap_id}/resume/')
        self.assertEqual(resp_r.status_code, 200)
        self.assertEqual(Decimal(str(resp_r.data['ecart'])), Decimal('0'))
        self.assertTrue(resp_r.data['rapproche'])
        # Clôture.
        resp_c = api.post(
            f'/api/django/compta/rapprochements/{rap_id}/cloturer/')
        self.assertEqual(resp_c.status_code, 200, resp_c.data)
        self.assertEqual(resp_c.data['statut'], 'rapproche')

    def test_endpoint_lignes_gl_scopees_societe(self):
        # B a une écriture, A n'en a pas : A ne voit aucune ligne GL.
        _ecriture(self.co_b, 'BNK', [
            ('5141', '300', '0'), ('3421', '0', '300'),
        ], jour=date(2026, 1, 12))
        api = auth(self.user_a)
        resp = api.post('/api/django/compta/rapprochements/', {
            'compte_tresorerie': self.banque_a.id,
            'date_debut': '2026-01-01', 'date_fin': '2026-01-31',
            'solde_releve': '0',
        }, format='json')
        rap_id = resp.data['id']
        resp_gl = api.get(
            f'/api/django/compta/rapprochements/{rap_id}/lignes-gl/')
        self.assertEqual(resp_gl.status_code, 200)
        self.assertEqual(len(resp_gl.data), 0)

    def test_endpoint_create_refuse_compte_autre_societe(self):
        # B tente de rapprocher la banque de A.
        api = auth(self.user_b)
        resp = api.post('/api/django/compta/rapprochements/', {
            'compte_tresorerie': self.banque_a.id,
            'date_debut': '2026-01-01', 'date_fin': '2026-01-31',
            'solde_releve': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg123-normal', role='normal')
        resp = auth(normal).get('/api/django/compta/rapprochements/')
        self.assertEqual(resp.status_code, 403)
