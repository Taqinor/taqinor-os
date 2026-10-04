"""QJR222 — ``provenance`` cesse d'être écrivable par le navigateur.

TEST ROUGE D'ABORD : ``domain/etude_schema.cles_refusees_pour`` n'appliquait la
vérification de propriétaire QU'AUX clés DÉRIVÉES. ``provenance`` — propriétaire
PIPELINE, l'estampille de dérive DC11 — est une ENTRÉE : elle passait donc par
``PATCH /devis/<id>/etude-params/`` depuis le navigateur, et une forme interne
malformée levait ENSUITE, à l'intérieur du bloc atomique du pipeline, ce qui
cassait durablement tout enregistrement de ligne sur ce devis.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr222_provenance_proprietaire -v 2
"""
from rest_framework.test import APIClient, APITestCase

from apps.ventes.domain import etude_schema as S
from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Onduleur réseau Huawei 10kW', '1', '11700'),
    ('Panneau mono 550W', '14', '1100'),
]

#: Les clés d'ENTRÉE que l'ÉCRAN doit continuer d'écrire — la liste EXPLICITE
#: exigée par le Done de QJR222. Une régression de la garde les ferait rougir.
CLES_ECRAN_LEGITIMES = (
    'scenario',
    'recommended_option',
    'gamme',
    'mode_installation',
    'tension_raccordement',
    'distributeur',
    'categorie_commerciale',
    'nombre_proprietes',
    'factures_mensuelles_reelles',
    'conso_kwh_mensuelles',
    'conso_annuelle',
    'toiture',
    'attribution',
    'debit_souhaite_m3h',
    'heures_pompage',
    'type_pompe',
    'surface_ha',
    'repartition_mt',
)


class GardeDeProprieteTests(APITestCase):
    """La règle elle-même, sans base pour l'essentiel."""

    def test_provenance_est_declaree_exclusive(self):
        self.assertTrue(S.SCHEMA['provenance']['exclusif'])
        self.assertEqual(S.SCHEMA['provenance']['proprietaire'], S.PIPELINE)
        self.assertEqual(S.SCHEMA['provenance']['nature'], S.ENTREE)

    def test_l_ecran_ne_peut_plus_ecrire_provenance(self):
        """LE ROUGE : la garde ne regardait que la NATURE."""
        self.assertEqual(
            S.cles_refusees_pour(S.ECRAN, ['provenance']), ['provenance'])

    def test_le_pipeline_reste_le_seul_a_pouvoir_l_ecrire(self):
        self.assertEqual(S.cles_refusees_pour(S.PIPELINE, ['provenance']), [])

    def test_un_ecrivain_anonyme_non_plus(self):
        self.assertEqual(
            S.cles_refusees_pour(None, ['provenance']), ['provenance'])

    def test_les_entrees_de_l_ecran_restent_ecrivables(self):
        """La liste EXPLICITE : la garde ne doit rien refuser d'autre."""
        self.assertEqual(
            S.cles_refusees_pour(S.ECRAN, CLES_ECRAN_LEGITIMES), [])

    def test_le_calepinage_ecrit_toujours_les_entrees_qu_il_pose(self):
        """Non-régression : ``reconcilier`` fusionne sous ``CALEPINAGE`` des
        entrées dont le propriétaire déclaré est l'ÉCRAN — un contrôle aveugle
        sur « tout propriétaire déclaré » les aurait refusées."""
        self.assertEqual(
            S.cles_refusees_pour(
                S.CALEPINAGE,
                ['scenario', 'toiture', 'resync_apres_envoi']),
            [])

    def test_le_message_de_refus_nomme_la_cle(self):
        with self.assertRaises(ValueError) as leve:
            S.fusionner({}, proprietaire=S.ECRAN, provenance={'x': 1})
        self.assertIn('provenance', str(leve.exception))


class EndpointEtudeParamsTests(APITestCase):
    """Le refus tel que le navigateur le reçoit : 400 FR, aucune écriture."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR222-0001')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.url = ('/api/django/ventes/devis/%s/etude-params/'
                    % self.devis.id)

    def test_patch_provenance_refuse_en_400_fr_sans_ecriture(self):
        """ROUGE AVANT : le PATCH était ACCEPTÉ et rangeait la forme reçue."""
        resp = self.api.patch(
            self.url, {'provenance': {'nimporte': 'quoi'}}, format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertIn('provenance', resp.data['detail'])
        self.devis.refresh_from_db()
        self.assertNotIn('provenance', self.devis.etude_params or {})

    def test_l_enregistrement_de_ligne_reste_intact_apres_le_refus(self):
        """Le déni de service auto-infligé ne peut plus se poser : le devis
        reste enregistrable après la tentative."""
        self.api.patch(self.url, {'provenance': {'nimporte': 'quoi'}},
                       format='json')
        produit = self.devis.lignes.first().produit
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': [{
                'produit': produit.id, 'designation': 'Panneau mono 550W',
                'quantite': '14', 'prix_unitaire': '1100', 'ordre': 0,
            }]}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(self.devis.lignes.count(), 1)

    def test_une_entree_legitime_passe_toujours(self):
        resp = self.api.patch(
            self.url, {'scenario': 'Sans batterie'}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.devis.refresh_from_db()
        self.assertEqual(
            (self.devis.etude_params or {}).get('scenario'), 'Sans batterie')
        self.assertEqual(Devis.objects.get(pk=self.devis.pk).statut,
                         self.devis.statut)
