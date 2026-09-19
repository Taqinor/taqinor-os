"""NTAI27 — Registre de modèles ML par tenant.

Couvre :
  * ``selectors.params_actifs`` renvoie les défauts SANS version active
    (comportement inchangé pour un scorer qui n'appelle jamais ce module) et
    les paramètres de la version active sinon ;
  * ``services.activer_version`` désactive toute AUTRE version du même
    scorer (au plus une active) et refuse une activation cross-société ;
  * la contrainte base ``uniq_mlops_modele_actif`` : deux versions actives
    d'un même scorer, pour la même société, sont impossibles ;
  * l'endpoint ``POST modeles/<id>/activer/`` (réservé Responsable/Admin) et
    l'isolation société.
"""
from django.db import IntegrityError, transaction

from authentication.models import CustomUser
from testkit.base import TenantAPITestCase

from apps.mlops.models import ModeleML
from apps.mlops.selectors import params_actifs, version_active
from apps.mlops.services import activer_version


class ParamsActifsTests(TenantAPITestCase):
    def test_sans_version_active_renvoie_les_defauts(self):
        self.assertEqual(
            params_actifs(self.company, 'churn', defauts={'seuil': 0.7}),
            {'seuil': 0.7})

    def test_avec_version_active_renvoie_ses_parametres(self):
        ModeleML.objects.create(
            company=self.company, nom=ModeleML.Nom.CHURN, version=1,
            params_json={'seuil': 0.5}, actif=True)
        self.assertEqual(
            params_actifs(self.company, 'churn', defauts={'seuil': 0.7}),
            {'seuil': 0.5})

    def test_isolation_societe(self):
        ModeleML.objects.create(
            company=self.other_company, nom=ModeleML.Nom.CHURN, version=1,
            params_json={'seuil': 0.1}, actif=True)
        self.assertEqual(
            params_actifs(self.company, 'churn', defauts={'seuil': 0.7}),
            {'seuil': 0.7})

    def test_sans_nom_renvoie_les_defauts(self):
        self.assertEqual(params_actifs(self.company, '', defauts={'x': 1}),
                         {'x': 1})


class ActiverVersionTests(TenantAPITestCase):
    def test_active_une_seule_version_a_la_fois(self):
        v1 = ModeleML.objects.create(
            company=self.company, nom=ModeleML.Nom.CHURN, version=1,
            params_json={}, actif=True)
        v2 = ModeleML.objects.create(
            company=self.company, nom=ModeleML.Nom.CHURN, version=2,
            params_json={})

        activee = activer_version(self.company, v2.id)
        self.assertEqual(activee.id, v2.id)
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertFalse(v1.actif)
        self.assertTrue(v2.actif)
        self.assertEqual(version_active(self.company, 'churn').id, v2.id)

    def test_refuse_une_activation_cross_societe(self):
        etrangere = ModeleML.objects.create(
            company=self.other_company, nom=ModeleML.Nom.CHURN, version=1,
            params_json={})
        self.assertIsNone(activer_version(self.company, etrangere.id))

    def test_contrainte_base_une_active_par_scorer(self):
        ModeleML.objects.create(
            company=self.company, nom=ModeleML.Nom.CHURN, version=1,
            params_json={}, actif=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ModeleML.objects.create(
                    company=self.company, nom=ModeleML.Nom.CHURN, version=2,
                    params_json={}, actif=True)


class ModeleMLEndpointTests(TenantAPITestCase):
    BASE = '/api/django/mlops/modeles/'

    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def test_activer_via_endpoint(self):
        v1 = ModeleML.objects.create(
            company=self.company, nom=ModeleML.Nom.CHURN, version=1,
            params_json={}, actif=True)
        v2 = ModeleML.objects.create(
            company=self.company, nom=ModeleML.Nom.CHURN, version=2,
            params_json={'seuil': 0.9})

        resp = self._admin().post(f'{self.BASE}{v2.id}/activer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        v1.refresh_from_db()
        self.assertFalse(v1.actif)
        self.assertTrue(resp.data['actif'])

    def test_non_admin_refuse(self):
        resp = self.client_as().get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_sur_activer(self):
        etrangere = ModeleML.objects.create(
            company=self.other_company, nom=ModeleML.Nom.CHURN, version=1,
            params_json={})
        resp = self._admin().post(f'{self.BASE}{etrangere.id}/activer/')
        self.assertEqual(resp.status_code, 404)
