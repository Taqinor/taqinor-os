"""Tests NTPAY23 — `ParametragePaieCompany` : réglages globaux par société.

Couvre : UN SEUL enregistrement par société (contrainte de base), la lecture
qui n'écrit RIEN (défauts en mémoire tant que rien n'est réglé), le jour de
virement qui pré-remplit la date d'exécution du prochain ordre de virement
(critère d'acceptation), le rabat du jour sur le dernier jour du mois, le
seuil d'écart consommé par XPAI15, le compte émetteur par défaut, et
l'endpoint (courant / création / doublon refusé).
"""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import ParametragePaieCompany, PeriodePaie, ProfilPaie
from apps.paie.services import (
    SEUIL_ECART_NET_DEFAUT,
    controle_ecarts,
    date_execution_par_defaut,
    ensure_defaults,
    generer_bulletin,
    generer_ordre_virement,
    parametrage_paie,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class ParametragePaieTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay23')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule='A1', salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, rib='011780000000000000000001',
            affilie_cnss=True, affilie_amo=True)

    # ── Lecture sans écriture ──────────────────────────────────────────────

    def test_lecture_ne_cree_rien(self):
        reglages = parametrage_paie(self.co)
        self.assertIsNone(reglages.pk)
        self.assertIsNone(reglages.jour_virement_defaut)
        self.assertEqual(reglages.devise_defaut, 'MAD')
        self.assertFalse(reglages.rappel_retroactif_automatique)
        self.assertEqual(
            ParametragePaieCompany.objects.filter(company=self.co).count(), 0)

    def test_un_seul_enregistrement_par_societe(self):
        ParametragePaieCompany.objects.create(company=self.co)
        # ``atomic`` imbriqué : une ``IntegrityError`` casse la transaction du
        # test, le point de sauvegarde la contient (patron documenté Django).
        with self.assertRaises(IntegrityError), transaction.atomic():
            ParametragePaieCompany.objects.create(company=self.co)

    # ── Critère d'acceptation : jour de virement pré-rempli ────────────────

    def test_jour_de_virement_prerempli_sur_l_ordre(self):
        profil = self._profil()
        valider_bulletin(generer_bulletin(profil, self.periode))

        # Sans réglage : aucune date pré-remplie (comportement historique).
        ordre = generer_ordre_virement(self.periode)
        self.assertIsNone(ordre.date_execution)

        ParametragePaieCompany.objects.create(
            company=self.co, jour_virement_defaut=26)
        ordre = generer_ordre_virement(self.periode)
        self.assertEqual(ordre.date_execution, date(2026, 6, 26))

    def test_date_explicite_prime_sur_le_reglage(self):
        ParametragePaieCompany.objects.create(
            company=self.co, jour_virement_defaut=26)
        profil = self._profil('B1')
        valider_bulletin(generer_bulletin(profil, self.periode))
        ordre = generer_ordre_virement(
            self.periode, date_execution=date(2026, 6, 5))
        self.assertEqual(ordre.date_execution, date(2026, 6, 5))

    def test_jour_rabattu_sur_le_dernier_jour_du_mois(self):
        ParametragePaieCompany.objects.create(
            company=self.co, jour_virement_defaut=31)
        fevrier = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=2)
        self.assertEqual(
            date_execution_par_defaut(fevrier), date(2026, 2, 28))

    def test_sans_reglage_aucune_date(self):
        self.assertIsNone(date_execution_par_defaut(self.periode))

    # ── Seuil d'écart consommé par XPAI15 ──────────────────────────────────

    def test_seuil_ecart_par_defaut_puis_regle(self):
        profil = self._profil('C1', Decimal('10000'))
        precedente = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=5)
        valider_bulletin(generer_bulletin(profil, precedente))
        # Ce mois-ci, le salaire augmente de 30 % : au-dessus du défaut (20 %).
        profil.salaire_base = Decimal('13000')
        profil.save()
        generer_bulletin(profil, self.periode)

        self.assertEqual(SEUIL_ECART_NET_DEFAUT, Decimal('20'))
        self.assertEqual(len(controle_ecarts(self.periode)['variations_net']),
                         1)
        # Seuil société relevé à 50 % : l'écart ne remonte plus.
        ParametragePaieCompany.objects.create(
            company=self.co, seuil_ecart_net_pct=Decimal('50'))
        self.assertEqual(len(controle_ecarts(self.periode)['variations_net']),
                         0)
        # Un seuil passé EXPLICITEMENT prime toujours sur le réglage.
        self.assertEqual(
            len(controle_ecarts(self.periode,
                                seuil_pct=Decimal('5'))['variations_net']), 1)

    # ── Isolation société ──────────────────────────────────────────────────

    def test_isolation_societe(self):
        autre = make_company('ntpay23-autre')
        ParametragePaieCompany.objects.create(
            company=autre, jour_virement_defaut=10)
        self.assertIsNone(parametrage_paie(self.co).jour_virement_defaut)
        self.assertEqual(
            parametrage_paie(autre).jour_virement_defaut, 10)


class ParametragePaieApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay23-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay23-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = '/api/django/paie/parametrage/'

    def test_courant_rend_les_defauts_sans_rien_creer(self):
        rep = self.api.get(f'{self.url}courant/')
        self.assertEqual(rep.status_code, 200)
        self.assertIsNone(rep.data['id'])
        self.assertIsNone(rep.data['jour_virement_defaut'])
        self.assertEqual(rep.data['devise_defaut'], 'MAD')
        self.assertEqual(
            ParametragePaieCompany.objects.filter(company=self.co).count(), 0)

    def test_creation_puis_modification(self):
        rep = self.api.post(
            self.url, {'jour_virement_defaut': 26}, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        identifiant = rep.data['id']
        self.assertEqual(
            ParametragePaieCompany.objects.get(pk=identifiant).company_id,
            self.co.id)

        rep = self.api.patch(
            f'{self.url}{identifiant}/', {'jour_virement_defaut': 28},
            format='json')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data['jour_virement_defaut'], 28)

    def test_second_enregistrement_refuse_en_400(self):
        self.api.post(self.url, {'jour_virement_defaut': 26}, format='json')
        rep = self.api.post(
            self.url, {'jour_virement_defaut': 5}, format='json')
        self.assertEqual(rep.status_code, 400)

    def test_jour_hors_bornes_est_400(self):
        rep = self.api.post(
            self.url, {'jour_virement_defaut': 45}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('jour_virement_defaut', rep.data)

    def test_devise_invalide_est_400(self):
        rep = self.api.post(
            self.url, {'devise_defaut': 'MADAGASCAR'}, format='json')
        self.assertEqual(rep.status_code, 400)

    def test_parametrage_d_une_autre_societe_invisible(self):
        autre = make_company('ntpay23-api-autre')
        parametrage_autre = ParametragePaieCompany.objects.create(
            company=autre, jour_virement_defaut=10)
        rep = self.api.get(f'{self.url}{parametrage_autre.id}/')
        self.assertEqual(rep.status_code, 404)
