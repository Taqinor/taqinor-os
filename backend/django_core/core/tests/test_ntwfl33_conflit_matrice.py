"""Tests NTWFL33 — conflit de règles de matrice détecté à la sauvegarde.

Acceptance criteria couverte : créer une 2ᵉ règle IDENTIQUE en portée à une
règle existante déclenche un avertissement explicite qui NOMME la règle en
conflit, et la sauvegarde reste possible (l'admin tranche).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company, CustomUser
from testkit.base import TenantAPITestCase

from core.models import MatriceApprobation

URL = '/api/django/core/matrices-approbation/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_matrice(company, **kwargs):
    defaults = {
        'type_objet': 'purchase_order',
        'departement': 'Achats',
        'montant_min': Decimal('50000'),
        'montant_max': Decimal('200000'),
        'chaine_paliers': [{'palier': 1, 'role_requis': 'responsable'}],
        'actif': True,
    }
    defaults.update(kwargs)
    return MatriceApprobation.objects.create(company=company, **defaults)


class ConflitDePorteeModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl33', 'NTWFL33')
        cls.autre = make_company('ntwfl33-autre', 'NTWFL33 Autre')

    def test_portee_identique_est_en_conflit_et_nommee(self):
        premiere = make_matrice(self.company)
        seconde = make_matrice(self.company)

        conflits = seconde.conflits_de_portee()
        self.assertEqual([c.pk for c in conflits], [premiere.pk])
        messages = seconde.avertissements_de_conflit()
        self.assertEqual(len(messages), 1)
        self.assertIn(f'#{premiere.pk}', messages[0])
        self.assertIn('Conflit de portée', messages[0])
        # Le conflit est SYMÉTRIQUE : la première le voit aussi.
        self.assertEqual(
            [c.pk for c in premiere.conflits_de_portee()], [seconde.pk])

    def test_departement_insensible_a_la_casse_et_aux_espaces(self):
        premiere = make_matrice(self.company, departement='Achats')
        seconde = make_matrice(self.company, departement='  achats ')
        self.assertEqual(
            [c.pk for c in seconde.conflits_de_portee()], [premiere.pk])

    def test_departement_different_pas_de_conflit(self):
        make_matrice(self.company, departement='Achats')
        autre = make_matrice(self.company, departement='RH')
        self.assertEqual(autre.conflits_de_portee(), [])

    def test_plage_de_montant_differente_pas_de_conflit(self):
        make_matrice(self.company, montant_min=Decimal('50000'),
                     montant_max=Decimal('200000'))
        autre = make_matrice(self.company, montant_min=Decimal('50000'),
                             montant_max=Decimal('200001'))
        self.assertEqual(autre.conflits_de_portee(), [])

    def test_bornes_ouvertes_identiques_sont_en_conflit(self):
        premiere = make_matrice(self.company, montant_min=None,
                                montant_max=None)
        seconde = make_matrice(self.company, montant_min=None,
                               montant_max=None)
        self.assertEqual(
            [c.pk for c in seconde.conflits_de_portee()], [premiere.pk])

    def test_type_objet_different_pas_de_conflit(self):
        make_matrice(self.company, type_objet='purchase_order')
        autre = make_matrice(self.company, type_objet='expense')
        self.assertEqual(autre.conflits_de_portee(), [])

    def test_regle_inactive_ne_conflite_pas(self):
        active = make_matrice(self.company)
        inactive = make_matrice(self.company, actif=False)
        # Une règle inactive ne participe pas à la résolution : ni comme
        # sujet, ni comme cible du conflit.
        self.assertEqual(inactive.conflits_de_portee(), [])
        self.assertEqual(active.conflits_de_portee(), [])

    def test_isolation_tenant(self):
        make_matrice(self.autre)
        mienne = make_matrice(self.company)
        self.assertEqual(mienne.conflits_de_portee(), [])

    def test_instance_non_enregistree_voit_le_conflit_avant_sauvegarde(self):
        existante = make_matrice(self.company)
        brouillon = MatriceApprobation(
            company=self.company,
            type_objet=existante.type_objet,
            departement=existante.departement,
            montant_min=existante.montant_min,
            montant_max=existante.montant_max,
            actif=True)
        self.assertEqual(
            [c.pk for c in brouillon.conflits_de_portee()], [existante.pk])


class ConflitDePorteeApiTests(TenantAPITestCase):
    def _payload(self, **kwargs):
        corps = {
            'type_objet': 'purchase_order',
            'departement': 'Achats',
            'montant_min': '50000.00',
            'montant_max': '200000.00',
            'chaine_paliers': [{'palier': 1, 'role_requis': 'responsable'}],
            'actif': True,
        }
        corps.update(kwargs)
        return corps

    def test_creation_dun_doublon_avertit_sans_bloquer(self):
        existante = make_matrice(self.company)
        avant = MatriceApprobation.objects.filter(
            company=self.company).count()

        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            URL, self._payload(), format='json')

        # La sauvegarde RESTE possible — l'avertissement ne bloque jamais.
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual(
            MatriceApprobation.objects.filter(company=self.company).count(),
            avant + 1)
        self.assertEqual(len(body['avertissements']), 1)
        self.assertIn(f'#{existante.pk}', body['avertissements'][0])

    def test_creation_sans_chevauchement_naverti_pas(self):
        make_matrice(self.company, departement='Achats')
        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            URL, self._payload(departement='RH'), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['avertissements'], [])

    def test_liste_expose_les_avertissements(self):
        premiere = make_matrice(self.company)
        seconde = make_matrice(self.company)

        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        par_id = {ligne['id']: ligne for ligne in r.json()}
        self.assertIn(f'#{seconde.pk}', par_id[premiere.pk]['avertissements'][0])
        self.assertIn(f'#{premiere.pk}', par_id[seconde.pk]['avertissements'][0])

    def test_desactiver_une_regle_leve_lavertissement(self):
        premiere = make_matrice(self.company)
        seconde = make_matrice(self.company)
        client = self.client_as(role=CustomUser.ROLE_ADMIN)

        r = client.patch(f'{URL}{seconde.pk}/', {'actif': False},
                         format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['avertissements'], [])
        premiere.refresh_from_db()
        self.assertEqual(premiere.avertissements_de_conflit(), [])

    def test_avertissements_est_en_lecture_seule(self):
        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            URL, self._payload(avertissements=['injecté']), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['avertissements'], [])
