"""CIQ663 — recette MT : essais de limitation d'injection et de découplage
EXIGÉS quand l'étude du distributeur impose des réglages (décret 2.25.100
art. 27) ou que le devis limite l'injection.

Run :
    python manage.py test apps.installations.tests_ciq663_recette_mt -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import CommissioningRecord, Installation
from apps.installations.services import (
    ESSAIS_RECETTE, ensure_commissioning_record, essais_mt_exiges, seed_stages,
)
from apps.installations.tests_ch3_commissioning import (
    BASE, auth, make_company, make_user,
)
from apps.ventes.models import Devis, RegulatoryDossier

TOUS_VRAIS = {champ: True for champ in ESSAIS_RECETTE}


class RecetteMTTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)
        self.api = auth(make_user(self.company))
        self._n = 0

    def _chantier(self, niveau='mt', reglages=None, etude_params=None):
        self._n += 10
        client = Client.objects.create(
            company=self.company, nom='Usine',
            email=f'ciq663-{self._n}@example.com')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-CIQ663-{self._n}',
            client=client, statut='accepte', taux_tva=Decimal('20'),
            mode_installation='industriel', etude_params=etude_params or {})
        chantier = Installation.objects.create(
            company=self.company, reference=f'CHT-CIQ663-{self._n}',
            devis=devis, type_installation='industriel',
            niveau_tension=niveau, regime_8221='accord_raccordement')
        if reglages is not None:
            RegulatoryDossier.objects.create(
                company=self.company, devis=devis,
                regime_8221='accord_raccordement',
                etude_reglages_imposes=reglages)
        return chantier

    def _patch(self, chantier, corps):
        record = ensure_commissioning_record(chantier)
        r = self.api.patch(
            f'{BASE}/recettes-commissioning/{record.id}/', corps,
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r

    def test_mt_reglages_imposes_decouplage_non_saisi_en_cours(self):
        chantier = self._chantier(reglages=True)
        self.assertTrue(essais_mt_exiges(chantier))
        r = self._patch(chantier, dict(
            TOUS_VRAIS, limitation_injection_etat='ok'))
        self.assertEqual(r.data['resultat'], 'en_cours')

    def test_mt_reglages_imposes_decouplage_ok_conforme(self):
        chantier = self._chantier(reglages=True)
        r = self._patch(chantier, dict(
            TOUS_VRAIS, limitation_injection_etat='ok',
            decouplage_etat='ok'))
        self.assertEqual(r.data['resultat'], 'conforme')

    def test_mt_reglages_imposes_decouplage_ko_non_conforme(self):
        chantier = self._chantier(reglages=True)
        r = self._patch(chantier, dict(
            TOUS_VRAIS, limitation_injection_etat='ok',
            decouplage_etat='non_ok'))
        self.assertEqual(r.data['resultat'], 'non_conforme')

    def test_mt_sans_reglages_imposes_sans_objet_admis(self):
        chantier = self._chantier(reglages=False)
        self.assertFalse(essais_mt_exiges(chantier))
        r = self._patch(chantier, dict(TOUS_VRAIS))
        self.assertEqual(r.data['resultat'], 'conforme')

    def test_mt_sans_dossier_ni_etude_sans_objet_admis(self):
        chantier = self._chantier()
        self.assertFalse(essais_mt_exiges(chantier))
        r = self._patch(chantier, dict(TOUS_VRAIS))
        self.assertEqual(r.data['resultat'], 'conforme')

    def test_mt_injection_limitee_par_le_moteur_exige_les_essais(self):
        chantier = self._chantier(etude_params={
            'etude_ci': {'taille': {'raison_arret': 'plafond_injection'}}})
        self.assertTrue(essais_mt_exiges(chantier))
        r = self._patch(chantier, dict(TOUS_VRAIS))
        self.assertEqual(r.data['resultat'], 'en_cours')

    def test_autre_raison_d_arret_n_exige_rien(self):
        chantier = self._chantier(etude_params={
            'etude_ci': {'taille': {'raison_arret': 'toit'}}})
        self.assertFalse(essais_mt_exiges(chantier))

    def test_chantier_bt_inchange_meme_avec_reglages(self):
        chantier = self._chantier(niveau='bt', reglages=True)
        self.assertFalse(essais_mt_exiges(chantier))
        r = self._patch(chantier, dict(TOUS_VRAIS))
        self.assertEqual(r.data['resultat'], 'conforme')

    def test_non_ok_reste_un_essai_faux_hors_exigence(self):
        chantier = self._chantier(niveau='bt')
        r = self._patch(chantier, dict(TOUS_VRAIS, decouplage_etat='non_ok'))
        self.assertEqual(r.data['resultat'], 'non_conforme')
        self.assertEqual(
            CommissioningRecord.objects.get(installation=chantier).resultat,
            'non_conforme')
