"""Tests N43 — suggestion configurable du régime loi 82-21."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.installations.models import Installation
from apps.installations.regime import suggest_regime_8221, suggest_for_company
from apps.installations.services import create_installation_from_devis
from apps.installations.tests import make_company, auth, make_accepted_devis

User = get_user_model()


class TestSuggestRegimePure(TestCase):
    """Cœur pur de la suggestion (sans Django/DB)."""

    def test_small_is_declaration(self):
        self.assertEqual(suggest_regime_8221(6.5), 'declaration_bt')
        self.assertEqual(suggest_regime_8221(10.99), 'declaration_bt')

    def test_medium_is_accord(self):
        self.assertEqual(suggest_regime_8221(11), 'accord_raccordement')
        self.assertEqual(suggest_regime_8221(500), 'accord_raccordement')
        self.assertEqual(suggest_regime_8221(1000), 'accord_raccordement')

    def test_large_is_autorisation_from_5_mw(self):
        # CIQ613 — seuil sourcé (décret 2.25.100 art. 5, 18) : autorisation
        # à partir de 5 MW ; 1 à 5 MW = accord de raccordement.
        self.assertEqual(suggest_regime_8221(1000.01), 'accord_raccordement')
        self.assertEqual(suggest_regime_8221(2500), 'accord_raccordement')
        self.assertEqual(suggest_regime_8221(5000), 'autorisation_anre')

    def test_industriel_inconnu_a_qualifier(self):
        # CIQ613 — jamais « non concerné » par défaut pour un C&I.
        self.assertEqual(
            suggest_regime_8221(None, type_installation='industriel'),
            'a_qualifier')
        self.assertEqual(suggest_regime_8221(None), 'non_concerne')

    def test_max_dc_ac(self):
        # Puissance retenue = max(kWc DC, kW AC) (noyau CIQ612).
        self.assertEqual(suggest_regime_8221(8, kw_ac=12),
                         'accord_raccordement')

    def test_mt_sous_seuil_a_qualifier(self):
        self.assertEqual(
            suggest_regime_8221(8, niveau='mt', type_installation='industriel'),
            'a_qualifier')

    def test_libelles_sans_seuil_ni_anre(self):
        labels = dict(Installation.Regime8221.choices)
        self.assertEqual(labels['declaration_bt'], 'Déclaration')
        self.assertEqual(labels['accord_raccordement'],
                         'Accord de raccordement')
        self.assertEqual(labels['autorisation_anre'], 'Autorisation (ministère)')
        self.assertEqual(labels['a_qualifier'], 'À qualifier')
        for label in labels.values():
            self.assertNotIn('ANRE', label)
            # Aucun seuil dans un libellé (l'article de loi reste permis).
            self.assertNotRegex(label, r'kW|MW|[<>]')

    def test_unknown_is_non_concerne(self):
        self.assertEqual(suggest_regime_8221(None), 'non_concerne')
        self.assertEqual(suggest_regime_8221(0), 'non_concerne')
        self.assertEqual(suggest_regime_8221('pas un nombre'), 'non_concerne')

    def test_custom_thresholds(self):
        # Seuil déclaration relevé à 20 kWc → 15 kWc retombe en déclaration.
        self.assertEqual(
            suggest_regime_8221(15, seuil_declaration=20, seuil_anre=1000),
            'declaration_bt')


class TestRegimeOnChantierCreation(TestCase):
    def setUp(self):
        self.company = make_company(slug='reg-co', nom='Reg Co')
        self.user = User.objects.create_user(
            username='reg_user', password='x', role_legacy='responsable',
            company=self.company)

    def test_creation_sets_suggested_regime(self):
        # make_accepted_devis → etude_params puissance 7.2 kWc → déclaration.
        devis, _client, _lead = make_accepted_devis(self.company)
        inst, created = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertTrue(created)
        self.assertEqual(inst.regime_8221, 'declaration_bt')

    def test_company_thresholds_applied(self):
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company=self.company)
        prof.seuil_regime_declaration_kwc = Decimal('5')  # 7.2 > 5 → accord
        prof.save()
        self.assertEqual(
            suggest_for_company(Decimal('7.2'), self.company),
            'accord_raccordement')


class TestRegimeSuggestionEndpoint(TestCase):
    def setUp(self):
        self.company = make_company(slug='reg-ep-co', nom='Reg EP Co')
        self.user = User.objects.create_user(
            username='reg_ep_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_endpoint_returns_suggestion(self):
        url = '/api/django/installations/chantiers/regime-suggestion/'
        r = self.api.get(url, {'kwc': '6'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['code'], 'declaration_bt')
        self.assertIn('label', r.data)
        r2 = self.api.get(url, {'kwc': '300'})
        self.assertEqual(r2.data['code'], 'accord_raccordement')
        r3 = self.api.get(url, {'kwc': '5000'})
        self.assertEqual(r3.data['code'], 'autorisation_anre')

    def test_endpoint_kw_ac_et_type(self):
        url = '/api/django/installations/chantiers/regime-suggestion/'
        r = self.api.get(url, {'kwc': '12', 'kw_ac': '10'})
        self.assertEqual(r.data['code'], 'accord_raccordement')
        r2 = self.api.get(url, {'type_installation': 'industriel'})
        self.assertEqual(r2.data['code'], 'a_qualifier')
        self.assertEqual(r2.data['label'], 'À qualifier')

    def test_serializer_exposes_regime_suggere(self):
        devis, _client, _lead = make_accepted_devis(
            self.company, with_lead=False)
        devis.etude_params = {'puissance_kwc': 250}
        devis.save()
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            Installation.objects.get(pk=inst.id).regime_8221,
            'accord_raccordement')
        self.assertEqual(r.data['regime_suggere']['code'], 'accord_raccordement')


class TestRegimeHorsReseauAGR602(TestCase):
    """AGR602 — loi 82-21, art. 3 : toute installation non raccordée relève
    d'une déclaration, sans seuil de puissance."""

    def setUp(self):
        self.company = make_company(slug='reg-hr-co', nom='Reg HR Co')
        self.user = User.objects.create_user(
            username='reg_hr_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_pure_hors_reseau_any_power(self):
        for kwc in (None, 0, 5, 10.65, 42, 5000):
            self.assertEqual(
                suggest_regime_8221(kwc, hors_reseau=True),
                'declaration_hors_reseau')
        # Sans le drapeau : comportement historique octet-identique.
        self.assertEqual(suggest_regime_8221(10.65), 'declaration_bt')
        self.assertEqual(suggest_regime_8221(42), 'accord_raccordement')

    def test_agricole_devis_gives_hors_reseau_chantier(self):
        # 15 panneaux de 710 W = 10,65 kWc ; devis agricole accepté.
        devis, _client, lead = make_accepted_devis(self.company)
        lead.type_installation = 'agricole'
        lead.save()
        devis.mode_installation = 'agricole'
        devis.etude_params = {'puissance_kwc': 15 * 0.71}
        devis.save()
        inst, created = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertTrue(created)
        self.assertEqual(inst.type_installation, 'agricole')
        self.assertEqual(inst.regime_8221, 'declaration_hors_reseau')
        self.assertEqual(inst.raccordement_reseau, 'hors_reseau')
        r = self.api.get(f'/api/django/installations/chantiers/{inst.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data['regime_suggere']['code'], 'declaration_hors_reseau')

    def test_agricole_switched_to_raccorde_gets_kwc_suggestion(self):
        devis, _client, _lead = make_accepted_devis(self.company)
        devis.mode_installation = 'agricole'
        devis.etude_params = {'puissance_kwc': 42}
        devis.save()
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        r = self.api.patch(
            f'/api/django/installations/chantiers/{inst.id}/',
            {'raccordement_reseau': 'raccorde'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            r.data['regime_suggere']['code'], 'accord_raccordement')

    def test_residentiel_and_industriel_unchanged(self):
        devis, _client, _lead = make_accepted_devis(self.company)
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertEqual(inst.regime_8221, 'declaration_bt')
        self.assertIsNone(inst.raccordement_reseau)
        devis2, _c, _l = make_accepted_devis(self.company, with_lead=False)
        devis2.mode_installation = 'industriel'
        devis2.etude_params = {'puissance_kwc': 250}
        devis2.save()
        inst2, _ = create_installation_from_devis(
            devis2, self.user, self.company)
        self.assertEqual(inst2.regime_8221, 'accord_raccordement')
        self.assertIsNone(inst2.raccordement_reseau)

    def test_endpoint_hors_reseau(self):
        url = '/api/django/installations/chantiers/regime-suggestion/'
        r = self.api.get(url, {'kwc': '10', 'hors_reseau': '1'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['code'], 'declaration_hors_reseau')
        r2 = self.api.get(url, {'kwc': '10'})
        self.assertEqual(r2.data['code'], 'declaration_bt')


class TestRegimeCIQ613(TestCase):
    """CIQ613 — chantier C&I : régime du noyau sourcé, « à qualifier » au lieu
    de « non concerné », gate dossier bloqué tant que le régime est inconnu."""

    def setUp(self):
        self.company = make_company(slug='reg-ciq613', nom='Reg CIQ613')
        self.user = User.objects.create_user(
            username='reg_ciq613', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def _devis_industriel(self, etude):
        devis, _client, lead = make_accepted_devis(self.company)
        lead.type_installation = 'industriel'
        lead.save()
        devis.mode_installation = 'industriel'
        devis.etude_params = etude
        devis.save()
        return devis

    def test_industriel_1200_kwc_accord(self):
        devis = self._devis_industriel({'puissance_kwc': 1200})
        inst, created = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertTrue(created)
        self.assertEqual(inst.regime_8221, 'accord_raccordement')

    def test_industriel_puissance_inconnue_a_qualifier_et_gate(self):
        from apps.installations.services import (
            RAISON_REGIME_A_QUALIFIER, _gate_check_dossier)
        devis = self._devis_industriel({})
        devis.lead.taille_souhaitee_kwc = None
        devis.lead.save()
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        self.assertEqual(inst.regime_8221, 'a_qualifier')
        self.assertEqual(_gate_check_dossier(inst), RAISON_REGIME_A_QUALIFIER)
        # Même un statut « approuvé » saisi ne franchit pas un régime inconnu.
        inst.dossier_statut = Installation.DossierStatut.APPROUVE
        self.assertEqual(_gate_check_dossier(inst), RAISON_REGIME_A_QUALIFIER)
        r = self.api.get(f'/api/django/installations/chantiers/{inst.id}/')
        self.assertEqual(r.data['regime_suggere']['code'], 'a_qualifier')

    def test_kw_ac_des_onduleurs_de_la_nomenclature(self):
        from apps.stock.models import Produit
        from apps.stock.models_fiche_technique import FicheTechnique
        onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau', sku='OND-613',
            prix_vente=Decimal('1000'), quantite_stock=5)
        FicheTechnique.objects.create(
            company=self.company, produit=onduleur, type_fiche='onduleur',
            ond_ac_kw=Decimal('6'))
        devis = self._devis_industriel({'puissance_kwc': 8})
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        inst.bom = [{'produit_id': onduleur.id, 'designation': 'Onduleur',
                     'quantite': 2, 'marque': None}]
        inst.save()
        r = self.api.get(f'/api/django/installations/chantiers/{inst.id}/')
        # max(8 kWc DC, 2 × 6 kW AC) = 12 kW → accord de raccordement.
        self.assertEqual(r.data['regime_suggere']['code'],
                         'accord_raccordement')

    def test_residentiel_identique(self):
        devis, _client, _lead = make_accepted_devis(self.company)
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        self.assertEqual(inst.regime_8221, 'declaration_bt')
