"""Tests NTPAY3 — API « Plan comptable paie » (schéma de ventilation).

Couvre : le CRUD de ``schemas-comptables-paie/``, le RBAC fin
(``paie_voir`` lit / ``paie_gerer`` édite), les actions ``seed-standard`` et
``reinitialiser``, l'effet réel sur l'écriture de paie suivante, les 400
explicites (cible ambiguë, doublon) et l'isolation société.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import (
    ElementVariable, PeriodePaie, ProfilPaie, Rubrique, SchemaComptablePaie,
)
from apps.paie.services import (
    ensure_defaults, generer_bulletin, journal_de_paie, valider_bulletin,
)
from apps.rh.models import DossierEmploye

URL = '/api/django/paie/schemas-comptables-paie/'


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PlanComptableApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay3')
        ensure_defaults(self.co)
        self.user = make_user(self.co, 'ntpay3-resp')
        self.api = auth(self.user)
        self.rubrique = Rubrique.objects.create(
            company=self.co, code='PRIME_TRANSPORT',
            libelle='Prime de transport', type=Rubrique.TYPE_GAIN)

    def test_seed_standard_puis_liste(self):
        rep = self.api.post(URL + 'seed-standard/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data['lignes'], 6)
        liste = self.api.get(URL)
        self.assertEqual(liste.status_code, 200)
        donnees = liste.data.get('results', liste.data)
        self.assertEqual(len(donnees), 6)

    def test_creation_ligne_rubrique(self):
        rep = self.api.post(URL, {
            'rubrique': self.rubrique.id, 'compte_debit': '6144',
            'ordre': 10,
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        ligne = SchemaComptablePaie.objects.get(pk=rep.data['id'])
        self.assertEqual(ligne.company_id, self.co.id)
        self.assertEqual(ligne.compte_debit, '6144')
        self.assertEqual(rep.data['rubrique_code'], 'PRIME_TRANSPORT')

    def test_cible_ambigue_refusee_en_400(self):
        rep = self.api.post(URL, {
            'code_systeme': 'brut', 'rubrique': self.rubrique.id,
            'compte_debit': '6171',
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('code_systeme', rep.data)

    def test_cible_absente_refusee_en_400(self):
        rep = self.api.post(URL, {'compte_debit': '6171'}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('code_systeme', rep.data)

    def test_doublon_refuse_en_400(self):
        self.api.post(URL, {'code_systeme': 'brut', 'compte_debit': '6171'},
                      format='json')
        rep = self.api.post(URL, {'code_systeme': 'brut',
                                  'compte_debit': '6144'}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('code_systeme', rep.data)

    def test_company_jamais_lue_du_corps(self):
        autre = make_company('ntpay3-autre')
        rep = self.api.post(URL, {
            'code_systeme': 'net', 'compte_credit': '4432',
            'company': autre.id,
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertEqual(
            SchemaComptablePaie.objects.get(pk=rep.data['id']).company_id,
            self.co.id)

    def test_rubrique_d_une_autre_societe_refusee(self):
        autre = make_company('ntpay3-autre2')
        rubrique_autre = Rubrique.objects.create(
            company=autre, code='X', libelle='X', type=Rubrique.TYPE_GAIN)
        rep = self.api.post(URL, {
            'rubrique': rubrique_autre.id, 'compte_debit': '6144',
        }, format='json')
        self.assertEqual(rep.status_code, 400)

    def test_isolation_liste(self):
        autre = make_company('ntpay3-autre3')
        SchemaComptablePaie.objects.create(
            company=autre, code_systeme='brut', compte_debit='6171')
        liste = self.api.get(URL)
        donnees = liste.data.get('results', liste.data)
        self.assertEqual(donnees, [])

    def test_reinitialiser_rejoue_le_standard(self):
        self.api.post(URL + 'seed-standard/')
        ligne = SchemaComptablePaie.objects.get(
            company=self.co, code_systeme='brut')
        self.api.patch(f'{URL}{ligne.id}/', {'compte_debit': '6144'},
                       format='json')
        rep = self.api.post(URL + 'reinitialiser/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data['lignes'], 6)
        self.assertEqual(
            SchemaComptablePaie.objects.get(
                company=self.co, code_systeme='brut').compte_debit, '6171')

    def test_edition_ecran_change_l_ecriture_suivante(self):
        """Le gestionnaire édite un compte → l'écriture suivante le reflète."""
        self.api.post(URL, {
            'rubrique': self.rubrique.id, 'compte_debit': '6144', 'ordre': 10,
        }, format='json')
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='N', prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'),
            affilie_cnss=True, affilie_amo=True)
        ElementVariable.objects.create(
            company=self.co, periode=periode, profil=profil,
            type=ElementVariable.TYPE_PRIME, rubrique=self.rubrique,
            libelle='Prime de transport', montant=Decimal('600'))
        valider_bulletin(generer_bulletin(profil, periode))

        ecriture = journal_de_paie(periode)
        numeros = {
            ligne.compte.numero: ligne.debit
            for ligne in ecriture.lignes.all() if ligne.debit > 0
        }
        self.assertIn('6144', numeros)
        self.assertEqual(numeros['6144'], Decimal('600.00'))


class PlanComptableRbacTests(TestCase):
    """XPAI7 — ``paie_voir`` lit, ``paie_gerer`` édite."""

    def setUp(self):
        self.co = make_company('ntpay3-rbac')
        ensure_defaults(self.co)

    def _user_avec(self, username, codes):
        from apps.roles.models import Role

        role = Role.objects.create(
            company=self.co, nom=f'role-{username}', permissions=list(codes))
        return User.objects.create_user(
            username=username, password='x', role=role, company=self.co)

    def test_lecteur_lit_mais_n_edite_pas(self):
        lecteur = self._user_avec('ntpay3-lecteur', ['paie_voir'])
        api = auth(lecteur)
        self.assertEqual(api.get(URL).status_code, 200)
        rep = api.post(URL, {'code_systeme': 'brut', 'compte_debit': '6171'},
                       format='json')
        self.assertEqual(rep.status_code, 403)

    def test_gestionnaire_edite(self):
        gestionnaire = self._user_avec(
            'ntpay3-gest', ['paie_voir', 'paie_gerer'])
        api = auth(gestionnaire)
        rep = api.post(URL, {'code_systeme': 'brut', 'compte_debit': '6171'},
                       format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
