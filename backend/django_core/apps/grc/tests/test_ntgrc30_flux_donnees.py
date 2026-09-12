"""NTGRC30 — cartographie des flux de données personnelles.

Garantie centrale : un flux vers un SOUS-TRAITANT HORS MAROC remonte dans
``flux_hors_maroc`` AVEC sa garantie — et les flux sans garantie déclarée
arrivent EN TÊTE, parce que ce sont eux qu'il faut régulariser.
"""
from django.test import TestCase

from apps.grc.models import FluxDonnees
from apps.grc.selectors import flux_hors_maroc
from authentication.models import Company
from core.models import RegistreTraitement
from testkit.base import TenantAPITestCase


def _flux(company, **kw):
    params = {'source': 'ERP — CRM', 'destination': FluxDonnees.DESTINATION_INTERNE}
    params.update(kw)
    return FluxDonnees.objects.create(company=company, **params)


class SelectorFluxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC30 SA', slug='ntgrc30')

    def test_un_flux_sous_traitant_hors_maroc_remonte_avec_sa_garantie(self):
        flux = _flux(
            self.company,
            destination=FluxDonnees.DESTINATION_SOUS_TRAITANT,
            destinataire='Hébergeur UE',
            transfert_hors_maroc=True, pays_destination='France',
            garanties=FluxDonnees.GARANTIE_CCT)
        resultats = list(flux_hors_maroc(self.company))
        self.assertEqual(resultats, [flux])
        self.assertEqual(resultats[0].garanties, FluxDonnees.GARANTIE_CCT)
        self.assertEqual(resultats[0].pays_destination, 'France')

    def test_un_flux_interne_au_maroc_ne_remonte_pas(self):
        _flux(self.company, destinataire='Service paie')
        self.assertEqual(list(flux_hors_maroc(self.company)), [])

    def test_les_flux_sans_garantie_arrivent_en_tete(self):
        avec = _flux(self.company, source='B', transfert_hors_maroc=True,
                     pays_destination='France',
                     garanties=FluxDonnees.GARANTIE_CCT)
        sans = _flux(self.company, source='A', transfert_hors_maroc=True,
                     pays_destination='Inde')
        resultats = list(flux_hors_maroc(self.company))
        self.assertEqual(resultats, [sans, avec])

    def test_le_selector_est_borne_a_la_societe(self):
        autre = Company.objects.create(nom='Autre', slug='ntgrc30-autre')
        _flux(autre, transfert_hors_maroc=True, pays_destination='France')
        self.assertEqual(list(flux_hors_maroc(self.company)), [])


class EndpointFluxTests(TenantAPITestCase):
    BASE = '/api/django/grc/flux-donnees/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe(self):
        r = self._admin().post(
            self.BASE,
            {'source': 'ERP — Paie', 'destination': 'sous_traitant',
             'destinataire': 'Cabinet comptable',
             'categories_donnees': ['identite', 'salaire']},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        flux = FluxDonnees.objects.get(pk=r.data['id'])
        self.assertEqual(flux.company, self.company)
        self.assertFalse(flux.transfert_hors_maroc)

    def test_une_source_vide_nomme_le_champ(self):
        r = self._admin().post(self.BASE, {'source': '  '}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('source', r.data)

    def test_un_transfert_hors_maroc_doit_nommer_son_pays(self):
        r = self._admin().post(
            self.BASE,
            {'source': 'ERP', 'transfert_hors_maroc': True},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('pays_destination', r.data)

    def test_un_traitement_d_une_autre_societe_est_refuse(self):
        etranger = RegistreTraitement.objects.create(
            company=self.other_company, code='X', finalite='X')
        r = self._admin().post(
            self.BASE,
            {'source': 'ERP', 'traitement_ref': str(etranger.pk)},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('traitement_ref', r.data)

    def test_endpoint_hors_maroc(self):
        _flux(self.company, transfert_hors_maroc=True,
              pays_destination='France',
              destination=FluxDonnees.DESTINATION_SOUS_TRAITANT,
              garanties=FluxDonnees.GARANTIE_CCT)
        _flux(self.company, source='Interne')
        r = self._admin().get(f'{self.BASE}hors-maroc/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['results']), 1)
        self.assertEqual(r.data['results'][0]['garanties'], 'cct')
        self.assertEqual(
            r.data['results'][0]['garanties_libelle'],
            'Clauses contractuelles types')

    def test_liste_scopee_societe(self):
        _flux(self.other_company)
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])
