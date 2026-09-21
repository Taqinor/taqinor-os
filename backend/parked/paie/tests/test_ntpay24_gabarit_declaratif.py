"""Tests NTPAY24 — Gabarits de fichiers réglementaires versionnés.

Couvre : la NON-RÉGRESSION stricte (sans gabarit actif, le fichier SIMT et le
fichier de télépaiement CNSS sortent EXACTEMENT comme avant), l'effet d'un
gabarit custom ACTIF sur la structure générée, l'ignorance d'un gabarit
INACTIF ou pas encore en vigueur, le REPLI sur le codé en dur quand la
structure est mal formée, la validation API de la structure et l'isolation
société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import (
    GabaritDeclaratif, PeriodePaie, ProfilPaie,
)
from apps.paie.services import (
    GABARIT_SIMT_ENTETE,
    GABARIT_SIMT_LIGNE,
    GABARIT_TELEPAIEMENT_CNSS_ENTETE,
    ensure_defaults,
    fichier_telepaiement_cnss,
    fichier_virement_paie_simt,
    gabarit_actif,
    generer_bulletin,
    generer_ordre_virement,
    structure_gabarit,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


#: Structure CUSTOM de test — volontairement plus courte que le gabarit
#: standard, pour que la différence de longueur soit indiscutable.
STRUCTURE_SIMT_CUSTOM = {
    'entete': [
        ['type_enregistrement', 1, 'L'],
        ['rib_emetteur', 10, 'L'],
        ['total_centimes', 12, 'R'],
    ],
    'ligne': [
        ['type_enregistrement', 1, 'L'],
        ['rib_beneficiaire', 10, 'L'],
        ['montant_centimes', 12, 'R'],
    ],
}


class GabaritDeclaratifTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay24')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='A1', nom='N', prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib='011780000000000000000001',
            affilie_cnss=True, affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, self.periode))
        self.ordre = generer_ordre_virement(self.periode)

    def _activer_simt(self, **kwargs):
        params = dict(
            company=self.co, type_fichier=GabaritDeclaratif.TYPE_SIMT,
            version='banque-2027', structure_json=STRUCTURE_SIMT_CUSTOM,
            actif=True, date_effet=date(2020, 1, 1))
        params.update(kwargs)
        return GabaritDeclaratif.objects.create(**params)

    # ── Non-régression ─────────────────────────────────────────────────────

    def test_sans_gabarit_actif_le_simt_est_inchange(self):
        fichier = fichier_virement_paie_simt(self.ordre)
        longueur_entete = sum(lg for _c, lg, _r in GABARIT_SIMT_ENTETE)
        longueur_ligne = sum(lg for _c, lg, _r in GABARIT_SIMT_LIGNE)
        self.assertEqual(len(fichier['lignes'][0]), longueur_entete)
        self.assertEqual(len(fichier['lignes'][1]), longueur_ligne)

    def test_sans_gabarit_actif_le_telepaiement_est_inchange(self):
        fichier = fichier_telepaiement_cnss(self.periode)
        longueur = sum(
            lg for _c, lg, _r in GABARIT_TELEPAIEMENT_CNSS_ENTETE)
        self.assertEqual(len(fichier['lignes'][0]), longueur)

    def test_structure_gabarit_rend_les_defauts_sans_gabarit(self):
        entete, ligne = structure_gabarit(
            self.co, GabaritDeclaratif.TYPE_SIMT,
            GABARIT_SIMT_ENTETE, GABARIT_SIMT_LIGNE)
        self.assertIs(entete, GABARIT_SIMT_ENTETE)
        self.assertIs(ligne, GABARIT_SIMT_LIGNE)

    # ── Gabarit custom actif ───────────────────────────────────────────────

    def test_gabarit_custom_change_la_structure_du_fichier(self):
        avant = fichier_virement_paie_simt(self.ordre)
        self._activer_simt()
        apres = fichier_virement_paie_simt(self.ordre)

        self.assertEqual(len(apres['lignes'][0]), 1 + 10 + 12)
        self.assertEqual(len(apres['lignes'][1]), 1 + 10 + 12)
        self.assertNotEqual(apres['lignes'][0], avant['lignes'][0])
        # Les MONTANTS ne bougent pas : seul le FORMAT change.
        self.assertEqual(apres['total'], avant['total'])
        self.assertEqual(apres['nb_lignes'], avant['nb_lignes'])
        self.assertTrue(apres['lignes'][0].startswith('E'))
        self.assertTrue(apres['lignes'][1].startswith('D'))

    def test_gabarit_inactif_est_ignore(self):
        self._activer_simt(actif=False)
        fichier = fichier_virement_paie_simt(self.ordre)
        self.assertEqual(
            len(fichier['lignes'][0]),
            sum(lg for _c, lg, _r in GABARIT_SIMT_ENTETE))

    def test_gabarit_pas_encore_en_vigueur_est_ignore(self):
        self._activer_simt(date_effet=date(2099, 1, 1))
        self.assertIsNone(
            gabarit_actif(self.co, GabaritDeclaratif.TYPE_SIMT,
                          le_jour=date(2026, 6, 30)))

    def test_le_plus_recent_en_vigueur_gagne(self):
        ancien = self._activer_simt(
            version='v1', date_effet=date(2020, 1, 1))
        recent = self._activer_simt(
            version='v2', date_effet=date(2026, 1, 1))
        resolu = gabarit_actif(self.co, GabaritDeclaratif.TYPE_SIMT,
                               le_jour=date(2026, 6, 30))
        self.assertEqual(resolu.id, recent.id)
        self.assertNotEqual(resolu.id, ancien.id)

    # ── Repli sur structure invalide ───────────────────────────────────────

    def test_structure_mal_formee_retombe_sur_le_code_en_dur(self):
        self._activer_simt(structure_json={'entete': [['champ', 0, 'X']]})
        fichier = fichier_virement_paie_simt(self.ordre)
        self.assertEqual(
            len(fichier['lignes'][0]),
            sum(lg for _c, lg, _r in GABARIT_SIMT_ENTETE))

    def test_bloc_ligne_absent_garde_le_defaut(self):
        self._activer_simt(structure_json={
            'entete': STRUCTURE_SIMT_CUSTOM['entete']})
        fichier = fichier_virement_paie_simt(self.ordre)
        self.assertEqual(len(fichier['lignes'][0]), 1 + 10 + 12)
        self.assertEqual(
            len(fichier['lignes'][1]),
            sum(lg for _c, lg, _r in GABARIT_SIMT_LIGNE))

    def test_champ_inconnu_sort_vide_jamais_invente(self):
        self._activer_simt(structure_json={
            'entete': [['type_enregistrement', 1, 'L'],
                       ['champ_qui_nexiste_pas', 5, 'L']],
        })
        fichier = fichier_virement_paie_simt(self.ordre)
        self.assertEqual(fichier['lignes'][0], 'E' + ' ' * 5)

    # ── Isolation société ──────────────────────────────────────────────────

    def test_isolation_societe(self):
        autre = make_company('ntpay24-autre')
        GabaritDeclaratif.objects.create(
            company=autre, type_fichier=GabaritDeclaratif.TYPE_SIMT,
            structure_json=STRUCTURE_SIMT_CUSTOM, actif=True,
            date_effet=date(2020, 1, 1))
        fichier = fichier_virement_paie_simt(self.ordre)
        self.assertEqual(
            len(fichier['lignes'][0]),
            sum(lg for _c, lg, _r in GABARIT_SIMT_ENTETE))


class GabaritDeclaratifApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay24-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay24-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = '/api/django/paie/gabarits-declaratifs/'

    def test_creation(self):
        rep = self.api.post(self.url, {
            'type_fichier': GabaritDeclaratif.TYPE_SIMT,
            'version': 'banque-2027',
            'structure_json': STRUCTURE_SIMT_CUSTOM,
            'actif': True, 'date_effet': '2027-01-01',
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertEqual(
            GabaritDeclaratif.objects.get(pk=rep.data['id']).company_id,
            self.co.id)

    def test_structure_invalide_est_400(self):
        rep = self.api.post(self.url, {
            'type_fichier': GabaritDeclaratif.TYPE_SIMT,
            'structure_json': {'entete': [['champ', -1, 'Z']]},
            'date_effet': '2027-01-01',
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('structure_json', rep.data)

    def test_liste_ne_montre_que_sa_societe(self):
        autre = make_company('ntpay24-api-autre')
        GabaritDeclaratif.objects.create(
            company=autre, type_fichier=GabaritDeclaratif.TYPE_SIMT,
            actif=True, date_effet=date(2027, 1, 1))
        rep = self.api.get(self.url)
        self.assertEqual(rep.status_code, 200)
        resultats = rep.data.get('results', rep.data)
        self.assertEqual(len(resultats), 0)
