"""Tests FG125–FG130 — virements internes, prévisionnel de trésorerie roulant,
portefeuille d'effets (à recevoir / à payer), bordereau de remise et impayés.

Couvre :
* FG125 — virement interne à deux jambes (banque↔banque/caisse), écriture
  équilibrée postée dans le journal OD, respect du verrou de période, refus du
  même compte des deux côtés, garde multi-société.
* FG126 — prévisionnel roulant 13 semaines : lignes prévues éditables empilées
  au-dessus de la position + des effets ouverts, flux nets semaine par semaine.
* FG127/FG128 — effets à recevoir/à payer : statut, échéancier, encaissement &
  paiement (écritures équilibrées), totaux ouverts.
* FG129 — bordereau de remise : regroupe des effets → ``remis`` + écriture.
* FG130 — rejet d'effet : réouverture du montant dû + frais de rejet.
Plus les endpoints API + gate de rôle.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    BordereauRemise, CompteTresorerie, EcritureComptable, Effet,
    LignePrevisionnelTresorerie, PeriodeComptable,
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


class _ComptaSetup(TestCase):
    def setUp(self):
        self.co = make_company('fg125', 'FG125 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', compte_comptable=services.get_compte(self.co, '5141'))
        self.caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse', compte_comptable=services.get_compte(self.co, '5161'))


# ── FG125 — Virements internes ─────────────────────────────────────────────

class VirementInterneServiceTests(_ComptaSetup):
    def test_enregistrer_virement_pose_company(self):
        v = services.enregistrer_virement(
            self.co, compte_source=self.banque,
            compte_destination=self.caisse, date_virement=date(2026, 6, 1),
            montant=Decimal('1000'))
        self.assertEqual(v.company_id, self.co.id)
        self.assertFalse(v.posted)

    def test_meme_compte_refuse(self):
        with self.assertRaises(ValidationError):
            services.enregistrer_virement(
                self.co, compte_source=self.banque,
                compte_destination=self.banque, date_virement=date(2026, 6, 1),
                montant=Decimal('500'))

    def test_montant_nul_refuse(self):
        with self.assertRaises(ValidationError):
            services.enregistrer_virement(
                self.co, compte_source=self.banque,
                compte_destination=self.caisse, date_virement=date(2026, 6, 1),
                montant=Decimal('0'))

    def test_compte_autre_societe_refuse(self):
        autre = make_company('fg125-autre', 'Autre')
        services.seed_plan_comptable(autre)
        treso_autre = CompteTresorerie.objects.create(
            company=autre, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Autre', compte_comptable=services.get_compte(autre, '5141'))
        with self.assertRaises(ValidationError):
            services.enregistrer_virement(
                self.co, compte_source=treso_autre,
                compte_destination=self.caisse, date_virement=date(2026, 6, 1),
                montant=Decimal('100'))

    def test_poster_virement_deux_jambes_equilibree(self):
        v = services.enregistrer_virement(
            self.co, compte_source=self.banque,
            compte_destination=self.caisse, date_virement=date(2026, 6, 1),
            montant=Decimal('1000'), poster=True)
        v.refresh_from_db()
        self.assertTrue(v.posted)
        ecr = v.ecriture
        self.assertIsNotNone(ecr)
        self.assertEqual(ecr.lignes.count(), 2)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_debit, Decimal('1000'))
        # Destination (caisse 5161) débitée, source (banque 5141) créditée.
        debit_line = ecr.lignes.filter(debit__gt=0).first()
        self.assertEqual(debit_line.compte.numero, '5161')
        credit_line = ecr.lignes.filter(credit__gt=0).first()
        self.assertEqual(credit_line.compte.numero, '5141')

    def test_poster_idempotent(self):
        v = services.enregistrer_virement(
            self.co, compte_source=self.banque,
            compte_destination=self.caisse, date_virement=date(2026, 6, 1),
            montant=Decimal('1000'))
        e1 = services.poster_virement(v)
        e2 = services.poster_virement(v)
        self.assertEqual(e1.id, e2.id)
        self.assertEqual(EcritureComptable.objects.filter(
            company=self.co, source_type='virement_interne').count(), 1)

    def test_poster_refuse_en_periode_close(self):
        PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 30), verrouillee=True)
        v = services.enregistrer_virement(
            self.co, compte_source=self.banque,
            compte_destination=self.caisse, date_virement=date(2026, 6, 15),
            montant=Decimal('500'))
        with self.assertRaises(ValidationError):
            services.poster_virement(v)


class VirementInterneApiTests(_ComptaSetup):
    def test_create_and_poster_endpoint(self):
        user = make_user(self.co, 'fg125-resp')
        api = auth(user)
        resp = api.post('/api/django/compta/virements/', {
            'compte_source': self.banque.id,
            'compte_destination': self.caisse.id,
            'date_virement': '2026-06-01',
            'montant': '750',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        vid = resp.data['id']
        resp2 = api.post(
            f'/api/django/compta/virements/{vid}/poster/', {}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.content)
        self.assertIsNotNone(resp2.data['ecriture_id'])

    def test_role_gate(self):
        user = make_user(self.co, 'fg125-commercial', role='commercial')
        api = auth(user)
        resp = api.get('/api/django/compta/virements/')
        self.assertEqual(resp.status_code, 403)

    def test_company_scoping_list(self):
        autre = make_company('fg125-co2', 'Co2')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        treso_a = CompteTresorerie.objects.create(
            company=autre, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='A', compte_comptable=services.get_compte(autre, '5141'))
        treso_b = CompteTresorerie.objects.create(
            company=autre, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='B', compte_comptable=services.get_compte(autre, '5161'))
        services.enregistrer_virement(
            autre, compte_source=treso_a, compte_destination=treso_b,
            date_virement=date(2026, 6, 1), montant=Decimal('100'))
        services.enregistrer_virement(
            self.co, compte_source=self.banque, compte_destination=self.caisse,
            date_virement=date(2026, 6, 1), montant=Decimal('200'))
        api = auth(make_user(self.co, 'fg125-scoped'))
        resp = api.get('/api/django/compta/virements/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        montants = {Decimal(v['montant']) for v in rows}
        self.assertEqual(montants, {Decimal('200.00')})


# ── FG126 — Prévisionnel de trésorerie roulant 13 semaines ─────────────────

class PrevisionnelTresorerieTests(_ComptaSetup):
    def test_ligne_montant_nul_refuse(self):
        with self.assertRaises(ValidationError):
            services.creer_ligne_previsionnel(
                self.co, libelle='Nul', date_prevue=date(2026, 6, 1),
                montant=Decimal('0'))

    def test_previsionnel_empile_lignes_prevues(self):
        today = timezone.localdate()
        lundi = today - timedelta(days=today.weekday())
        # Semaine 0 : un crédit (+), semaine 1 : des salaires (−).
        services.creer_ligne_previsionnel(
            self.co, libelle='Crédit', date_prevue=lundi + timedelta(days=1),
            montant=Decimal('5000'),
            categorie=LignePrevisionnelTresorerie.Categorie.CREDIT)
        services.creer_ligne_previsionnel(
            self.co, libelle='Salaires',
            date_prevue=lundi + timedelta(days=8),
            montant=Decimal('-3000'),
            categorie=LignePrevisionnelTresorerie.Categorie.SALAIRE)
        data = selectors.previsionnel_tresorerie(self.co, date_debut=lundi)
        self.assertEqual(len(data['semaines']), 13)
        s0, s1 = data['semaines'][0], data['semaines'][1]
        self.assertEqual(s0['entrees'], Decimal('5000'))
        self.assertEqual(s0['flux_net'], Decimal('5000'))
        self.assertEqual(s1['sorties'], Decimal('3000'))
        self.assertEqual(s1['flux_net'], Decimal('-3000'))
        # Solde cumulé : initial + 5000 puis − 3000.
        self.assertEqual(s1['solde_fin'],
                         data['solde_initial'] + Decimal('2000'))

    def test_previsionnel_inclut_effets_ouverts(self):
        today = timezone.localdate()
        lundi = today - timedelta(days=today.weekday())
        services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal('4000'),
            date_emission=lundi, date_echeance=lundi + timedelta(days=3))
        data = selectors.previsionnel_tresorerie(self.co, date_debut=lundi)
        self.assertEqual(data['semaines'][0]['entrees'], Decimal('4000'))

    def test_api_previsionnel_endpoint(self):
        api = auth(make_user(self.co, 'fg126-resp'))
        resp = api.get(
            '/api/django/compta/etats/previsionnel-tresorerie/?nb_semaines=4')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data['semaines']), 4)

    def test_api_ligne_crud_scoped(self):
        api = auth(make_user(self.co, 'fg126-crud'))
        resp = api.post('/api/django/compta/previsionnel/', {
            'libelle': 'Leasing',
            'categorie': 'leasing',
            'date_prevue': '2026-07-01',
            'montant': '-1500',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            LignePrevisionnelTresorerie.objects.get(
                id=resp.data['id']).company_id, self.co.id)


# ── FG127 / FG128 — Effets à recevoir / à payer ────────────────────────────

class EffetTests(_ComptaSetup):
    def _effet_recevoir(self, montant='2000', statut=None):
        e = services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal(montant),
            date_emission=date(2026, 6, 1), date_echeance=date(2026, 7, 1),
            type_effet=Effet.TypeEffet.TRAITE, numero='TR-1', banque='CIH')
        if statut:
            e.statut = statut
            e.save(update_fields=['statut'])
        return e

    def test_effet_naît_en_portefeuille(self):
        e = self._effet_recevoir()
        self.assertEqual(e.statut, Effet.Statut.PORTEFEUILLE)
        self.assertEqual(e.company_id, self.co.id)

    def test_echeance_avant_emission_refuse(self):
        with self.assertRaises(ValidationError):
            services.enregistrer_effet(
                self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal('100'),
                date_emission=date(2026, 7, 1), date_echeance=date(2026, 6, 1))

    def test_encaisser_effet_portefeuille(self):
        e = self._effet_recevoir('2000')
        e = services.encaisser_effet(e, date_encaissement=date(2026, 7, 2))
        self.assertEqual(e.statut, Effet.Statut.ENCAISSE)
        ecr = EcritureComptable.objects.get(
            company=self.co, source_type='effet_encaissement', source_id=e.id)
        self.assertTrue(ecr.est_equilibree)
        # Banque débitée, effets à recevoir (3425) crédités.
        self.assertEqual(ecr.lignes.filter(debit__gt=0).first().compte.numero,
                         '5141')
        self.assertEqual(ecr.lignes.filter(credit__gt=0).first().compte.numero,
                         '3425')

    def test_encaisser_remis_solde_5113(self):
        e = self._effet_recevoir('2000', statut=Effet.Statut.REMIS)
        e = services.encaisser_effet(e, date_encaissement=date(2026, 7, 2))
        ecr = EcritureComptable.objects.get(
            company=self.co, source_type='effet_encaissement', source_id=e.id)
        self.assertEqual(ecr.lignes.filter(credit__gt=0).first().compte.numero,
                         '5113')

    def test_payer_effet_fournisseur(self):
        e = services.enregistrer_effet(
            self.co, sens=Effet.Sens.PAYER, montant=Decimal('1500'),
            date_emission=date(2026, 6, 1), date_echeance=date(2026, 7, 1),
            numero='CHQ-9')
        e = services.payer_effet(e, date_paiement=date(2026, 7, 1))
        self.assertEqual(e.statut, Effet.Statut.PAYE)
        ecr = EcritureComptable.objects.get(
            company=self.co, source_type='effet_paiement', source_id=e.id)
        self.assertTrue(ecr.est_equilibree)
        # Effets à payer (4415) débités, banque créditée.
        self.assertEqual(ecr.lignes.filter(debit__gt=0).first().compte.numero,
                         '4415')

    def test_encaisser_effet_payer_refuse(self):
        e = services.enregistrer_effet(
            self.co, sens=Effet.Sens.PAYER, montant=Decimal('100'),
            date_emission=date(2026, 6, 1), date_echeance=date(2026, 7, 1))
        with self.assertRaises(ValidationError):
            services.encaisser_effet(e)

    def test_total_effets_ouverts(self):
        self._effet_recevoir('1000')
        self._effet_recevoir('2000')
        e = self._effet_recevoir('500')
        services.encaisser_effet(e, date_encaissement=date(2026, 7, 2))
        total = selectors.total_effets_ouverts(
            self.co, sens=Effet.Sens.RECEVOIR)
        self.assertEqual(total, Decimal('3000'))

    def test_echeancier_filtre(self):
        self._effet_recevoir('1000')
        services.enregistrer_effet(
            self.co, sens=Effet.Sens.PAYER, montant=Decimal('800'),
            date_emission=date(2026, 6, 1), date_echeance=date(2026, 6, 20))
        recevoir = selectors.echeancier_effets(
            self.co, sens=Effet.Sens.RECEVOIR)
        self.assertEqual(len(recevoir), 1)
        self.assertEqual(recevoir[0]['montant'], Decimal('1000'))

    def test_api_create_effet_scoped(self):
        api = auth(make_user(self.co, 'fg127-resp'))
        resp = api.post('/api/django/compta/effets/', {
            'sens': 'recevoir', 'type_effet': 'cheque',
            'montant': '1200', 'date_emission': '2026-06-01',
            'date_echeance': '2026-07-15', 'numero': 'CHQ-100',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['statut'], 'portefeuille')

    def test_api_encaisser_action(self):
        e = self._effet_recevoir('900')
        api = auth(make_user(self.co, 'fg127-enc'))
        resp = api.post(
            f'/api/django/compta/effets/{e.id}/encaisser/',
            {'date_encaissement': '2026-07-02'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'encaisse')


# ── FG129 — Bordereau de remise ────────────────────────────────────────────

class BordereauRemiseTests(_ComptaSetup):
    def _effet(self, montant):
        return services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal(montant),
            date_emission=date(2026, 6, 1), date_echeance=date(2026, 7, 1))

    def test_creer_bordereau_rattache_effets(self):
        e1 = self._effet('1000')
        e2 = self._effet('2000')
        b = services.creer_bordereau(
            self.co, self.banque, date_remise=date(2026, 6, 15),
            effet_ids=[e1.id, e2.id], reference='BR-1')
        self.assertEqual(b.effets.count(), 2)
        self.assertEqual(b.total, Decimal('3000'))

    def test_bordereau_compte_non_banque_refuse(self):
        e = self._effet('500')
        with self.assertRaises(ValidationError):
            services.creer_bordereau(
                self.co, self.caisse, date_remise=date(2026, 6, 15),
                effet_ids=[e.id])

    def test_effet_non_eligible_refuse(self):
        e = self._effet('500')
        e.statut = Effet.Statut.ENCAISSE
        e.save(update_fields=['statut'])
        with self.assertRaises(ValidationError):
            services.creer_bordereau(
                self.co, self.banque, date_remise=date(2026, 6, 15),
                effet_ids=[e.id])

    def test_poster_bordereau_passe_effets_remis(self):
        e1 = self._effet('1000')
        e2 = self._effet('2000')
        b = services.creer_bordereau(
            self.co, self.banque, date_remise=date(2026, 6, 15),
            effet_ids=[e1.id, e2.id])
        ecr = services.poster_bordereau(b)
        b.refresh_from_db()
        self.assertTrue(b.posted)
        self.assertEqual(b.statut, BordereauRemise.Statut.REMIS)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_debit, Decimal('3000'))
        # 5113 débité / 3425 crédité.
        self.assertEqual(ecr.lignes.filter(debit__gt=0).first().compte.numero,
                         '5113')
        e1.refresh_from_db()
        self.assertEqual(e1.statut, Effet.Statut.REMIS)

    def test_poster_bordereau_idempotent(self):
        e = self._effet('1000')
        b = services.creer_bordereau(
            self.co, self.banque, date_remise=date(2026, 6, 15),
            effet_ids=[e.id])
        e1 = services.poster_bordereau(b)
        e2 = services.poster_bordereau(b)
        self.assertEqual(e1.id, e2.id)

    def test_poster_bordereau_vide_refuse(self):
        b = services.creer_bordereau(
            self.co, self.banque, date_remise=date(2026, 6, 15), effet_ids=[])
        with self.assertRaises(ValidationError):
            services.poster_bordereau(b)

    def test_api_create_and_poster(self):
        e1 = self._effet('1000')
        e2 = self._effet('500')
        api = auth(make_user(self.co, 'fg129-resp'))
        resp = api.post('/api/django/compta/bordereaux/', {
            'compte_tresorerie': self.banque.id,
            'date_remise': '2026-06-15',
            'reference': 'BR-API',
            'effet_ids': [e1.id, e2.id],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        bid = resp.data['id']
        self.assertEqual(Decimal(resp.data['total']), Decimal('1500.00'))
        resp2 = api.post(
            f'/api/django/compta/bordereaux/{bid}/poster/', {}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.content)
        self.assertIsNotNone(resp2.data['ecriture_id'])


# ── FG130 — Impayés / rejets d'effets ──────────────────────────────────────

class RejetEffetTests(_ComptaSetup):
    def _effet_remis(self, montant='2000'):
        e = services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal(montant),
            date_emission=date(2026, 6, 1), date_echeance=date(2026, 7, 1))
        b = services.creer_bordereau(
            self.co, self.banque, date_remise=date(2026, 6, 15),
            effet_ids=[e.id])
        services.poster_bordereau(b)
        e.refresh_from_db()
        return e

    def test_rejet_rouvre_montant_du(self):
        e = self._effet_remis('2000')
        self.assertEqual(e.statut, Effet.Statut.REMIS)
        e = services.rejeter_effet(
            e, date_rejet=date(2026, 7, 5), frais_rejet=Decimal('150'))
        self.assertEqual(e.statut, Effet.Statut.IMPAYE)
        self.assertEqual(e.frais_rejet, Decimal('150'))
        # Réouverture : 3425 redébité / 5113 crédité.
        rouv = EcritureComptable.objects.get(
            company=self.co, source_type='effet_rejet', source_id=e.id)
        self.assertTrue(rouv.est_equilibree)
        self.assertEqual(rouv.lignes.filter(debit__gt=0).first().compte.numero,
                         '3425')
        # Frais de rejet : 6147 débité / banque créditée.
        frais = EcritureComptable.objects.get(
            company=self.co, source_type='effet_frais_rejet', source_id=e.id)
        self.assertTrue(frais.est_equilibree)
        self.assertEqual(frais.lignes.filter(debit__gt=0).first().compte.numero,
                         '6147')

    def test_rejet_sans_frais(self):
        e = self._effet_remis('1000')
        e = services.rejeter_effet(e, date_rejet=date(2026, 7, 5))
        self.assertEqual(e.statut, Effet.Statut.IMPAYE)
        self.assertEqual(e.frais_rejet, Decimal('0'))
        self.assertFalse(EcritureComptable.objects.filter(
            company=self.co, source_type='effet_frais_rejet',
            source_id=e.id).exists())

    def test_rejet_effet_solde_refuse(self):
        e = services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal('500'),
            date_emission=date(2026, 6, 1), date_echeance=date(2026, 7, 1))
        services.encaisser_effet(e, date_encaissement=date(2026, 7, 2))
        with self.assertRaises(ValidationError):
            services.rejeter_effet(e)

    def test_rejet_frais_negatif_refuse(self):
        e = self._effet_remis('800')
        with self.assertRaises(ValidationError):
            services.rejeter_effet(e, frais_rejet=Decimal('-10'))

    def test_api_rejeter_action(self):
        e = self._effet_remis('1200')
        api = auth(make_user(self.co, 'fg130-resp'))
        resp = api.post(
            f'/api/django/compta/effets/{e.id}/rejeter/',
            {'date_rejet': '2026-07-05', 'frais_rejet': '200',
             'commentaire': 'Chèque sans provision'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'impaye')
        self.assertEqual(Decimal(resp.data['frais_rejet']), Decimal('200.00'))
