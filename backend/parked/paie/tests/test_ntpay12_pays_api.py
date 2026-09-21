"""Tests NTPAY12 — API « Pays de paie » + sélection du pays sur le profil.

Couvre : le CRUD ``pays-paie/`` et son ``seed-standard`` ; ``moteur_disponible``
dit par le serveur (les packs FR/SN/CI sont gatés, donc non livrés) ; activer
MA (défaut) ne change rien ; affecter un pays activé à un profil route son
calcul vers le bon moteur ; un pays désactivé ou sans pack livré est REFUSÉ en
400 ; le badge pays est exposé sur le bulletin ; RBAC et isolation société.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import PaysPaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    MOTEURS_PAYS,
    calculer_bulletin,
    calculer_bulletin_ma,
    ensure_defaults,
    ensure_pays_paie_standard,
    generer_bulletin,
)
from apps.rh.models import DossierEmploye

URL = '/api/django/paie/pays-paie/'


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PaysPaieApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay12')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay12-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = auth(self.user)

    def test_seed_standard_ne_seme_que_le_maroc(self):
        rep = self.api.post(URL + 'seed-standard/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data['pays'], 1)
        liste = self.api.get(URL)
        donnees = liste.data.get('results', liste.data)
        self.assertEqual([p['code_iso'] for p in donnees], ['MA'])
        self.assertTrue(donnees[0]['moteur_disponible'])
        self.assertTrue(donnees[0]['actif'])

    def test_pack_gate_declare_mais_non_livre(self):
        rep = self.api.post(URL, {
            'code_iso': 'FR', 'libelle': 'France', 'devise': 'EUR',
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertFalse(rep.data['moteur_disponible'])

    def test_doublon_de_pays_refuse_en_400(self):
        self.api.post(URL + 'seed-standard/')
        rep = self.api.post(URL, {
            'code_iso': 'MA', 'libelle': 'Maroc', 'devise': 'MAD',
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('code_iso', rep.data)

    def test_company_jamais_lue_du_corps(self):
        autre = make_company('ntpay12-autre')
        rep = self.api.post(URL, {
            'code_iso': 'SN', 'libelle': 'Sénégal', 'devise': 'XOF',
            'company': autre.id,
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertEqual(
            PaysPaie.objects.get(pk=rep.data['id']).company_id, self.co.id)

    def test_isolation_liste(self):
        autre = make_company('ntpay12-iso')
        PaysPaie.objects.create(
            company=autre, code_iso='MA', libelle='Maroc', devise='MAD')
        liste = self.api.get(URL)
        self.assertEqual(liste.data.get('results', liste.data), [])


class SelectionPaysProfilTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay12-profil')
        ensure_defaults(self.co)
        ensure_pays_paie_standard(self.co)
        self.pays_ma = PaysPaie.objects.get(
            company=self.co, code_iso=PaysPaie.CODE_MA)
        self.user = User.objects.create_user(
            username='ntpay12-gest', password='x', company=self.co,
            role_legacy='responsable')
        self.api = auth(self.user)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _dossier(self, matricule):
        return DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')

    def test_affecter_le_pays_ma_laisse_tout_inchange(self):
        dossier = self._dossier('P1')
        rep = self.api.post('/api/django/paie/profils/', {
            'employe': dossier.id, 'pays': self.pays_ma.id,
            'type_remuneration': 'mensuel',
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        profil = ProfilPaie.objects.get(pk=rep.data['id'])
        profil.salaire_base = Decimal('10000')
        profil.save(update_fields=['salaire_base'])
        self.assertEqual(profil.pays_id, self.pays_ma.id)
        # Le calcul passe bien par le moteur marocain.
        direct = calculer_bulletin_ma(profil, self.periode)
        via = calculer_bulletin(profil, self.periode)
        self.assertEqual(via['net_a_payer'], direct['net_a_payer'])

    def test_pays_sans_pack_livre_refuse_en_400(self):
        pays_fr = PaysPaie.objects.create(
            company=self.co, code_iso=PaysPaie.CODE_FR, libelle='France',
            devise='EUR')
        self.assertNotIn('FR', MOTEURS_PAYS)
        dossier = self._dossier('P2')
        rep = self.api.post('/api/django/paie/profils/', {
            'employe': dossier.id, 'pays': pays_fr.id,
            'type_remuneration': 'mensuel',
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('pays', rep.data)

    def test_pays_desactive_refuse_en_400(self):
        self.pays_ma.actif = False
        self.pays_ma.save(update_fields=['actif'])
        dossier = self._dossier('P3')
        rep = self.api.post('/api/django/paie/profils/', {
            'employe': dossier.id, 'pays': self.pays_ma.id,
            'type_remuneration': 'mensuel',
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('pays', rep.data)

    def test_pays_d_une_autre_societe_refuse(self):
        autre = make_company('ntpay12-autre2')
        pays_autre = PaysPaie.objects.create(
            company=autre, code_iso='MA', libelle='Maroc', devise='MAD')
        dossier = self._dossier('P4')
        rep = self.api.post('/api/django/paie/profils/', {
            'employe': dossier.id, 'pays': pays_autre.id,
            'type_remuneration': 'mensuel',
        }, format='json')
        self.assertEqual(rep.status_code, 400)

    def test_badge_pays_sur_le_bulletin(self):
        dossier = self._dossier('P5')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier, pays=self.pays_ma,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        bulletin = generer_bulletin(profil, self.periode)
        rep = self.api.get(f'/api/django/paie/bulletins/{bulletin.id}/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data['pays_code'], 'MA')
        self.assertEqual(rep.data['pays_devise'], 'MAD')

    def test_badge_vide_pour_un_profil_sans_pays(self):
        dossier = self._dossier('P6')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        bulletin = generer_bulletin(profil, self.periode)
        rep = self.api.get(f'/api/django/paie/bulletins/{bulletin.id}/')
        self.assertEqual(rep.data['pays_code'], '')


class PaysPaieRbacTests(TestCase):
    """XPAI7 — ``paie_voir`` lit, ``paie_gerer`` édite."""

    def setUp(self):
        self.co = make_company('ntpay12-rbac')
        ensure_defaults(self.co)

    def _user_avec(self, username, codes):
        from apps.roles.models import Role

        role = Role.objects.create(
            company=self.co, nom=f'role-{username}', permissions=list(codes))
        return User.objects.create_user(
            username=username, password='x', role=role, company=self.co)

    def test_lecteur_lit_mais_n_edite_pas(self):
        api = auth(self._user_avec('ntpay12-lect', ['paie_voir']))
        self.assertEqual(api.get(URL).status_code, 200)
        rep = api.post(URL, {
            'code_iso': 'MA', 'libelle': 'Maroc', 'devise': 'MAD',
        }, format='json')
        self.assertEqual(rep.status_code, 403)

    def test_gestionnaire_edite(self):
        api = auth(self._user_avec(
            'ntpay12-gere', ['paie_voir', 'paie_gerer']))
        rep = api.post(URL, {
            'code_iso': 'MA', 'libelle': 'Maroc', 'devise': 'MAD',
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
