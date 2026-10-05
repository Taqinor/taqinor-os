"""Validations de l'enregistrement du profil entreprise.

L769 — garde-fou TVA : un taux ne peut pas être laissé VIDE et re-snappé
silencieusement au défaut (20/10) ; un 0 DÉLIBÉRÉ est préservé.
L788 — commission : la valeur est obligatoire dès qu'un mode actif est choisi.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


class ProfileValidationBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='val-co', defaults={'nom': 'Val Co'})[0]
        self.admin = User.objects.create_user(
            username='val_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestTvaGuard(ProfileValidationBase):
    def test_empty_tva_rejected_not_resnapped(self):
        # Champ vide → erreur de validation (au lieu d'un re-snap silencieux).
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'tva_standard': '', 'tva_panneaux': 10}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tva_standard', resp.data)

    def test_deliberate_zero_preserved(self):
        # 0 délibéré (exonéré) est valide et préservé tel quel.
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'tva_standard': 0, 'tva_panneaux': 0}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['tva_standard']), '0.00')
        self.assertEqual(str(resp.data['tva_panneaux']), '0.00')

    def test_out_of_range_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'tva_standard': 150}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tva_standard', resp.data)

    def test_normal_value_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'tva_standard': 20, 'tva_panneaux': 10}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['tva_standard']), '20.00')


class TestCommissionRequiresValue(ProfileValidationBase):
    def test_active_mode_requires_value(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'pct_devis', 'commission_valeur': None},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('commission_valeur', resp.data)

    def test_active_mode_with_value_ok(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'par_kwc', 'commission_valeur': '500'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['commission_mode'], 'par_kwc')

    def test_off_mode_allows_empty_value(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'off', 'commission_valeur': None},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_patch_mode_only_uses_stored_value(self):
        # Mode actif posé avec une valeur, puis re-PATCH du seul mode : la
        # valeur déjà enregistrée satisfait la contrainte (PATCH partiel).
        self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'pct_devis', 'commission_valeur': '5'},
            format='json')
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'par_kwc'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class TestCompanyReadOnly(ProfileValidationBase):
    """ERR25 — `company` est read-only : un PATCH ne peut pas repointer le
    profil de l'appelant vers une autre société."""

    def test_company_field_ignored_on_patch(self):
        other = Company.objects.get_or_create(
            slug='val-other', defaults={'nom': 'Other Co'})[0]
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(self.company)
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'company': other.id, 'nom': 'Renommé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        profile.refresh_from_db()
        # Le FK société est inchangé (non détourné), seul `nom` a été pris.
        self.assertEqual(profile.company_id, self.company.id)
        self.assertEqual(profile.nom, 'Renommé')


class TestThresholdRanges(ProfileValidationBase):
    """ERR55 — bornes [0, 100] sur les pourcentages éditables et non-négativité
    des seuils kWc ; un NULL reste accepté (champ optionnel)."""

    def test_negative_remise_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'remise_max_pct': -5}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('remise_max_pct', resp.data)

    def test_over_100_remise_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'remise_max_pct': 120}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('remise_max_pct', resp.data)

    def test_discount_threshold_out_of_range_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'discount_approval_threshold': 150}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('discount_approval_threshold', resp.data)

    def test_negative_overage_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'overage_seuil_pct': -1}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('overage_seuil_pct', resp.data)

    def test_negative_regime_threshold_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'seuil_regime_declaration_kwc': -3}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('seuil_regime_declaration_kwc', resp.data)

    def test_valid_threshold_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'remise_max_pct': 15, 'discount_approval_threshold': 10},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['remise_max_pct']), '15.00')

    def test_null_remise_allowed(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'remise_max_pct': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class TestJsonShapeValidation(ProfileValidationBase):
    """ERR55 — forme des champs JSON doc_prefixes / doc_numbering /
    payment_terms ; NULL reste accepté (repli sur le défaut historique)."""

    def test_doc_prefixes_must_be_object(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_prefixes': ['DEV', 'FAC']}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('doc_prefixes', resp.data)

    def test_doc_prefixes_unknown_key_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_prefixes': {'inconnu': 'X'}}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('doc_prefixes', resp.data)

    def test_doc_prefixes_valid_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_prefixes': {'devis': 'DV', 'facture': 'FC'}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['doc_prefixes']['devis'], 'DV')

    def test_doc_numbering_bad_padding_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_numbering': {'devis': {'padding': 99, 'reset': 'monthly'}}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('doc_numbering', resp.data)

    def test_doc_numbering_bad_reset_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_numbering': {'devis': {'padding': 4, 'reset': 'hourly'}}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('doc_numbering', resp.data)

    def test_doc_numbering_valid_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_numbering': {'facture': {'padding': 5, 'reset': 'yearly'}}},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_payment_terms_must_be_object(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'payment_terms': [30, 60, 10]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('payment_terms', resp.data)

    def test_payment_terms_over_100_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'payment_terms': {'reseau': {'acompte': 60, 'materiel': 60,
                                          'solde': 10}}}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('payment_terms', resp.data)

    def test_payment_terms_non_numeric_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'payment_terms': {'reseau': {'acompte': 'beaucoup'}}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('payment_terms', resp.data)

    def test_payment_terms_valid_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'payment_terms': {'reseau': {'acompte': 30, 'materiel': 60,
                                          'solde': 10}}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class TestEcartRecettePompage(ProfileValidationBase):
    """AGR606 — écart de recette pompage toléré (%), SANS défaut : vide =
    écart affiché sans verdict ; sinon 0 < x ≤ 100, refus 400 en français."""

    URL = '/api/django/parametres/update/'
    CHAMP = 'recette_pompage_ecart_max_pct'

    def test_get_initial_null(self):
        resp = self.api.get('/api/django/parametres/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn(self.CHAMP, resp.data)
        self.assertIsNone(resp.data[self.CHAMP])

    def test_patch_12_5_accepte(self):
        resp = self.api.patch(self.URL, {self.CHAMP: 12.5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data[self.CHAMP]), '12.50')

    def test_valeurs_hors_bornes_refusees_en_francais(self):
        for valeur in (-3, 150, 0):
            with self.subTest(valeur=valeur):
                resp = self.api.patch(self.URL, {self.CHAMP: valeur},
                                      format='json')
                self.assertEqual(resp.status_code, 400)
                self.assertIn(self.CHAMP, resp.data)
                self.assertIn('écart de recette', str(resp.data[self.CHAMP]))

    def test_null_accepte(self):
        self.api.patch(self.URL, {self.CHAMP: 10}, format='json')
        resp = self.api.patch(self.URL, {self.CHAMP: None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data[self.CHAMP])

    def test_enregistrer_rouvrir_enregistrer_identique(self):
        self.api.patch(self.URL, {self.CHAMP: '7.25'}, format='json')
        premier = self.api.get('/api/django/parametres/').data[self.CHAMP]
        resp = self.api.patch(self.URL, {self.CHAMP: premier}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            self.api.get('/api/django/parametres/').data[self.CHAMP], premier)

    def test_expose_a_cote_des_seuils_8221(self):
        from apps.parametres.views_config import PROFILE_CONFIG_FIELDS
        self.assertIn(self.CHAMP, PROFILE_CONFIG_FIELDS)


class TestSeuils8221Surcharge(ProfileValidationBase):
    """CIQ614 — les seuils 82-21 sont ceux des textes (noyau
    ``core.reglementaire``) ; la société ne saisit qu'une SURCHARGE (NULL par
    défaut). L'API expose ``seuils_sources`` (valeur + article)."""

    URL = '/api/django/parametres/update/'
    CHAMPS = ('seuil_regime_declaration_kwc', 'seuil_regime_anre_kwc')

    def test_get_initial_surcharges_null_et_seuils_sources(self):
        resp = self.api.get('/api/django/parametres/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for champ in self.CHAMPS:
            self.assertIn(champ, resp.data)
            self.assertIsNone(resp.data[champ])
        sources = resp.data['seuils_sources']
        self.assertEqual(sources['declaration']['valeur_kw'], 11)
        self.assertEqual(sources['autorisation']['valeur_kw'], 5000)
        self.assertIn('décret 2.25.100 art. 5',
                      sources['declaration']['source'])
        self.assertIn('art. 5, 18', sources['autorisation']['source'])

    def test_surcharge_saisie_puis_videe(self):
        resp = self.api.patch(
            self.URL, {'seuil_regime_anre_kwc': 2000}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['seuil_regime_anre_kwc']), '2000.00')
        # La référence sourcée ne bouge pas avec la surcharge.
        self.assertEqual(
            resp.data['seuils_sources']['autorisation']['valeur_kw'], 5000)
        resp = self.api.patch(
            self.URL, {'seuil_regime_anre_kwc': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['seuil_regime_anre_kwc'])

    def test_surcharge_negative_refusee_en_francais(self):
        resp = self.api.patch(
            self.URL, {'seuil_regime_anre_kwc': -1}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ne peut pas être négatif',
                      str(resp.data['seuil_regime_anre_kwc']))

    def test_seuils_sources_lecture_seule(self):
        resp = self.api.patch(
            self.URL, {'seuils_sources': {'declaration': {'valeur_kw': 1}}},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['seuils_sources']['declaration']['valeur_kw'], 11)

    def test_enregistrer_rouvrir_enregistrer_identique(self):
        self.api.patch(self.URL, {'seuil_regime_declaration_kwc': '9.5'},
                       format='json')
        premier = self.api.get('/api/django/parametres/').data
        corps = {c: premier[c] for c in self.CHAMPS}
        resp = self.api.patch(self.URL, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        second = self.api.get('/api/django/parametres/').data
        for cle in self.CHAMPS + ('seuils_sources',):
            self.assertEqual(second[cle], premier[cle])

    def _migration(self):
        import importlib
        return importlib.import_module(
            'apps.parametres.migrations.0118_ciq614_seuils_8221_surcharge')

    def _profil(self, decl, anre):
        from decimal import Decimal
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=prof.pk).update(
            seuil_regime_declaration_kwc=Decimal(decl),
            seuil_regime_anre_kwc=Decimal(anre))
        return prof

    def test_migration_ancien_defaut_passe_a_null(self):
        from django.apps import apps as django_apps
        from apps.parametres.models import CompanyProfile
        prof = self._profil('11', '1000')
        self._migration().anciens_defauts_vers_null(django_apps, None)
        prof = CompanyProfile.objects.get(pk=prof.pk)
        self.assertIsNone(prof.seuil_regime_declaration_kwc)
        self.assertIsNone(prof.seuil_regime_anre_kwc)

    def test_migration_choix_delibere_conserve(self):
        from decimal import Decimal
        from django.apps import apps as django_apps
        from apps.parametres.models import CompanyProfile
        prof = self._profil('8', '2000')
        self._migration().anciens_defauts_vers_null(django_apps, None)
        prof = CompanyProfile.objects.get(pk=prof.pk)
        self.assertEqual(prof.seuil_regime_declaration_kwc, Decimal('8'))
        self.assertEqual(prof.seuil_regime_anre_kwc, Decimal('2000'))

    def test_migration_reversible(self):
        from decimal import Decimal
        from django.apps import apps as django_apps
        from apps.parametres.models import CompanyProfile
        prof = self._profil('11', '2000')
        mig = self._migration()
        mig.anciens_defauts_vers_null(django_apps, None)
        mig.null_vers_anciens_defauts(django_apps, None)
        prof = CompanyProfile.objects.get(pk=prof.pk)
        self.assertEqual(prof.seuil_regime_declaration_kwc, Decimal('11'))
        self.assertEqual(prof.seuil_regime_anre_kwc, Decimal('2000'))
