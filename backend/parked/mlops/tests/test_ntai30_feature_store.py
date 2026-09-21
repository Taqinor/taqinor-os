"""NTAI30 — Feature store léger par tenant (matérialisation des signaux).

Couvre :
  * ``recompute_features`` matérialise un ``FeatureVector`` par lead (canal,
    priorité, perdu, signé, ancienneté approximative dérivée du mois de
    création) ;
  * l'appel est IDEMPOTENT (upsert — un second recalcul ne duplique rien,
    met juste à jour) ;
  * ``selectors.feature_vector`` renvoie ``{}`` sans vecteur matérialisé
    (repli — jamais une exception) et les features sinon ;
  * isolation société.
"""
from testkit.base import TenantAPITestCase

from apps.crm import stages as crm_stages
from apps.crm.models import Lead
from apps.mlops.models import FeatureVector
from apps.mlops.selectors import feature_vector
from apps.mlops.services import recompute_features


class RecomputeFeaturesTests(TenantAPITestCase):
    def test_materialise_un_vecteur_par_lead(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead A', stage=crm_stages.NEW,
            canal='recommandation', priorite='haute')
        compte = recompute_features(self.company)
        self.assertEqual(compte, 1)

        vecteur = FeatureVector.objects.get(
            company=self.company, content_type='crm.lead',
            object_id=lead.id)
        self.assertEqual(vecteur.features_json['canal'], 'recommandation')
        self.assertEqual(vecteur.features_json['priorite'], 'haute')
        self.assertFalse(vecteur.features_json['perdu'])
        self.assertFalse(vecteur.features_json['signe'])
        self.assertIsInstance(
            vecteur.features_json['anciennete_jours_approx'], int)
        self.assertGreaterEqual(
            vecteur.features_json['anciennete_jours_approx'], 0)

    def test_idempotent_upsert(self):
        Lead.objects.create(company=self.company, nom='Lead B')
        recompute_features(self.company)
        recompute_features(self.company)
        self.assertEqual(
            FeatureVector.objects.filter(company=self.company).count(), 1)

    def test_signe_et_perdu_reflétés(self):
        gagne = Lead.objects.create(
            company=self.company, nom='Gagné', stage=crm_stages.SIGNED,
            perdu=False)
        perdu = Lead.objects.create(
            company=self.company, nom='Perdu', perdu=True)
        recompute_features(self.company)

        vg = FeatureVector.objects.get(
            company=self.company, object_id=gagne.id)
        vp = FeatureVector.objects.get(
            company=self.company, object_id=perdu.id)
        self.assertTrue(vg.features_json['signe'])
        self.assertTrue(vp.features_json['perdu'])

    def test_isolation_societe(self):
        Lead.objects.create(company=self.other_company, nom='Fuite ?')
        recompute_features(self.company)
        self.assertEqual(
            FeatureVector.objects.filter(company=self.company).count(), 0)


class FeatureVectorSelectorTests(TenantAPITestCase):
    def test_sans_vecteur_renvoie_dict_vide(self):
        self.assertEqual(
            feature_vector(self.company, 'crm.lead', 999), {})

    def test_avec_vecteur_renvoie_les_features(self):
        FeatureVector.objects.create(
            company=self.company, content_type='crm.lead', object_id=1,
            features_json={'canal': 'site'})
        self.assertEqual(
            feature_vector(self.company, 'crm.lead', 1), {'canal': 'site'})

    def test_isolation_societe(self):
        FeatureVector.objects.create(
            company=self.other_company, content_type='crm.lead',
            object_id=1, features_json={'canal': 'fuite'})
        self.assertEqual(feature_vector(self.company, 'crm.lead', 1), {})
