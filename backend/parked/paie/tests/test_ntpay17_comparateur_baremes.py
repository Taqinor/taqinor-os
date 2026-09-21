"""Tests NTPAY17 — Comparateur de barèmes versionnés (aperçu d'impact).

Couvre : l'écart d'IR PAR TÊTE et le delta de masse salariale entre deux
barèmes sur un échantillon de profils, l'ABSENCE TOTALE d'écriture en base,
la complétion automatique de la moitié manquante du jeu (paramètre ↔ barème),
l'endpoint (ancien implicite/explicite, 400/404) et l'isolation société.

Les deux barèmes comparés sont construits DANS le test : aucune valeur légale
n'est inventée, ce sont des jeux de test dont seul l'ÉCART est observé.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import (
    BaremeIR, BulletinPaie, ParametrePaie, ProfilPaie, TrancheIR,
)
from apps.paie.selectors import comparer_baremes
from apps.paie.services import ensure_defaults
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class ComparateurBaremesTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay17')
        ensure_defaults(self.co)
        self.ancien = BaremeIR.objects.get(company=self.co)
        # NOUVEAU barème : une seule tranche à taux PLUS ÉLEVÉ que l'ancien.
        # Seul l'écart compte ici — aucune valeur officielle n'est affirmée.
        self.nouveau = BaremeIR.objects.create(
            company=self.co, libelle='Barème de test 2027',
            date_effet=date(2027, 1, 1))
        TrancheIR.objects.create(
            company=self.co, bareme=self.nouveau, borne_min=Decimal('0'),
            borne_max=None, taux=Decimal('38'),
            somme_a_deduire=Decimal('0'), ordre=1)
        self.profils = [
            self._profil('P1', Decimal('9000')),
            self._profil('P2', Decimal('14000')),
            self._profil('P3', Decimal('22000')),
        ]

    def _profil(self, matricule, salaire):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)

    def test_ecart_d_ir_par_tete_et_delta_de_masse(self):
        rapport = comparer_baremes(
            self.co, self.ancien, self.nouveau, self.profils)
        self.assertEqual(rapport['nombre_profils'], 3)
        self.assertEqual(len(rapport['lignes']), 3)
        for ligne in rapport['lignes']:
            self.assertGreater(ligne['ir_nouveau'], ligne['ir_ancien'])
            self.assertEqual(
                ligne['ecart_ir'], ligne['ir_nouveau'] - ligne['ir_ancien'])
            # Plus d'IR ⇒ moins de net, pour la même masse brute.
            self.assertLess(ligne['ecart_net'], 0)
            self.assertTrue(ligne['matricule'])
        totaux = rapport['totaux']
        self.assertEqual(
            totaux['ecart_ir'], totaux['ir_nouveau'] - totaux['ir_ancien'])
        self.assertGreater(totaux['ecart_ir'], 0)
        self.assertEqual(
            totaux['ir_ancien'],
            sum(ligne['ir_ancien'] for ligne in rapport['lignes']))

    def test_cout_employeur_inchange_quand_seul_l_ir_bouge(self):
        """L'IR est une retenue SALARIALE : il ne change pas le coût chargé."""
        rapport = comparer_baremes(
            self.co, self.ancien, self.nouveau, self.profils)
        self.assertEqual(rapport['totaux']['ecart_cout'], Decimal('0.00'))

    def test_parametre_publie_change_le_cout_employeur(self):
        """Un nouveau PARAMÈTRE (taux patronal) déplace bien la masse."""
        ancien_param = ParametrePaie.objects.get(company=self.co)
        # Daté DANS l'année 2026 : les DEUX jeux se complètent alors avec le
        # MÊME barème IR (celui de 2026), donc seul le taux PATRONAL diffère.
        nouveau_param = ParametrePaie.objects.create(
            company=self.co, date_effet=date(2026, 6, 1),
            plafond_cnss=ancien_param.plafond_cnss,
            taux_cnss_salarial=ancien_param.taux_cnss_salarial,
            taux_cnss_patronal=Decimal(ancien_param.taux_cnss_patronal) * 2,
            taux_amo_salarial=ancien_param.taux_amo_salarial,
            taux_amo_patronal=ancien_param.taux_amo_patronal,
            seuil_frais_pro=ancien_param.seuil_frais_pro,
            taux_frais_pro_bas=ancien_param.taux_frais_pro_bas,
            plafond_frais_pro_bas=ancien_param.plafond_frais_pro_bas,
            taux_frais_pro_haut=ancien_param.taux_frais_pro_haut,
            plafond_frais_pro_haut=ancien_param.plafond_frais_pro_haut)
        rapport = comparer_baremes(
            self.co, ancien_param, nouveau_param, self.profils)
        self.assertGreater(rapport['totaux']['ecart_cout'], 0)
        # Le net du salarié, lui, ne bouge pas : la part est PATRONALE.
        self.assertEqual(rapport['totaux']['ecart_net'], Decimal('0.00'))
        self.assertEqual(rapport['ancien']['objet'], 'parametre_paie')

    def test_moitie_manquante_du_jeu_est_resolue(self):
        rapport = comparer_baremes(
            self.co, self.ancien, self.nouveau, self.profils)
        # Le barème donné est complété par le PARAMÈTRE en vigueur à sa date.
        self.assertEqual(rapport['ancien']['objet'], 'bareme_ir')
        self.assertIsNotNone(rapport['ancien']['parametre_id'])
        self.assertEqual(rapport['nouveau']['bareme_id'], self.nouveau.id)

    def test_echantillon_par_defaut_prend_les_profils_actifs(self):
        rapport = comparer_baremes(self.co, self.ancien, self.nouveau)
        self.assertEqual(rapport['nombre_profils'], 3)
        self.profils[0].actif = False
        self.profils[0].save()
        rapport = comparer_baremes(self.co, self.ancien, self.nouveau)
        self.assertEqual(rapport['nombre_profils'], 2)

    def test_aucune_ecriture_en_base(self):
        avant = (BulletinPaie.objects.count(), BaremeIR.objects.count(),
                 ParametrePaie.objects.count(), ProfilPaie.objects.count())
        comparer_baremes(self.co, self.ancien, self.nouveau, self.profils)
        apres = (BulletinPaie.objects.count(), BaremeIR.objects.count(),
                 ParametrePaie.objects.count(), ProfilPaie.objects.count())
        self.assertEqual(avant, apres)

    def test_isolation_societe(self):
        autre = make_company('ntpay17-autre')
        ensure_defaults(autre)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Z', prenom='P')
        ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('50000'), affilie_cnss=True,
            affilie_amo=True)
        rapport = comparer_baremes(self.co, self.ancien, self.nouveau)
        self.assertEqual(rapport['nombre_profils'], 3)
        for ligne in rapport['lignes']:
            self.assertNotEqual(ligne['brut'], Decimal('50000.00'))


class ComparateurBaremesApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay17-api')
        ensure_defaults(self.co)
        self.ancien = BaremeIR.objects.get(company=self.co)
        self.nouveau = BaremeIR.objects.create(
            company=self.co, libelle='Barème de test 2027',
            date_effet=date(2027, 1, 1))
        TrancheIR.objects.create(
            company=self.co, bareme=self.nouveau, borne_min=Decimal('0'),
            borne_max=None, taux=Decimal('38'),
            somme_a_deduire=Decimal('0'), ordre=1)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='A1', nom='N', prenom='P')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('14000'), affilie_cnss=True,
            affilie_amo=True)
        self.user = User.objects.create_user(
            username='ntpay17-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self, bareme, suffixe=''):
        return f'/api/django/paie/baremes/{bareme.id}/comparer/{suffixe}'

    def test_ancien_implicite(self):
        rep = self.api.get(self._url(self.nouveau))
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data['ancien']['id'], self.ancien.id)
        self.assertEqual(rep.data['nombre_profils'], 1)

    def test_ancien_explicite(self):
        rep = self.api.get(
            self._url(self.nouveau, f'?ancien={self.ancien.id}'))
        self.assertEqual(rep.status_code, 200)
        self.assertGreater(
            Decimal(str(rep.data['totaux']['ecart_ir'])), 0)

    def test_sans_bareme_anterieur_est_400(self):
        rep = self.api.get(self._url(self.ancien))
        self.assertEqual(rep.status_code, 400)

    def test_ancien_inconnu_est_404(self):
        rep = self.api.get(self._url(self.nouveau, '?ancien=999999'))
        self.assertEqual(rep.status_code, 404)

    def test_profils_invalides_est_400(self):
        rep = self.api.get(self._url(self.nouveau, '?profils=abc'))
        self.assertEqual(rep.status_code, 400)
