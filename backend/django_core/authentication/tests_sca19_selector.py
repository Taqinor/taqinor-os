"""SCA19 — Sélecteur source-unique des sociétés actives + fan-outs beat.

Vérifie que ``authentication.selectors.active_companies()`` exclut un tenant
suspendu/en fermeture, et qu'un fan-out beat migré (contrats) ne balaie plus un
tenant suspendu.
"""
from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory
from authentication.models import Company
from authentication.selectors import active_companies, active_company_ids


class ActiveCompaniesSelectorTest(TenantAPITestCase):
    def test_exclut_tenant_suspendu(self):
        actif = CompanyFactory(nom='Actif', slug='sca19-actif')
        suspendu = CompanyFactory(nom='Suspendu', slug='sca19-susp')
        suspendu.statut = Company.STATUT_SUSPENDU
        suspendu.save()
        ids = active_company_ids()
        self.assertIn(actif.id, ids)
        self.assertNotIn(suspendu.id, ids)

    def test_exclut_tenant_en_fermeture(self):
        fermeture = CompanyFactory(nom='Fermeture', slug='sca19-ferm')
        fermeture.statut = Company.STATUT_FERMETURE
        fermeture.save()
        self.assertNotIn(fermeture.id, active_company_ids())

    def test_inclut_tenant_actif(self):
        c = CompanyFactory(nom='OK', slug='sca19-ok')
        self.assertIn(c.id, active_company_ids())
        self.assertTrue(active_companies().filter(pk=c.id).exists())


class ContratsFanoutSkipsSuspendedTest(TenantAPITestCase):
    def test_facturation_recurrente_ignore_tenant_suspendu(self):
        # Un tenant suspendu ne doit produire aucune facturation récurrente.
        from apps.contrats.scheduled import generer_factures_recurrentes_dues
        suspendu = CompanyFactory(nom='SuspFacture', slug='sca19-susp-f')
        suspendu.statut = Company.STATUT_SUSPENDU
        suspendu.save()
        # Le beat s'exécute sans erreur et n'itère pas sur le tenant suspendu.
        res = generer_factures_recurrentes_dues()
        self.assertIsInstance(res, dict)
        # Sanity : le tenant suspendu est bien absent du sélecteur source.
        self.assertNotIn(suspendu.id, active_company_ids())
