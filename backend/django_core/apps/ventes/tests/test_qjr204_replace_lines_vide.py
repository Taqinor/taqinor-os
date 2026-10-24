"""QJR204 — ``POST /replace-lines`` avec ``lignes: []`` REFUSE, il n'efface pas.

TEST ROUGE D'ABORD : l'endpoint traversait ``ecrire_lignes`` →
``domain/lignes.remplacer_lignes``, qui SUPPRIME puis recrée — une liste vide
effaçait donc TOUTES les lignes d'un devis brouillon/envoyé et répondait 200,
là où ``/atomic`` refusait déjà l'ensemble vide par un 400.

LE VERDICT « AUCUN FLUX LÉGITIME », ÉCRIT : le balayage du dépôt ne trouve
qu'UN appelant de production — ``frontend/src/api/ventesApi.js``
``replaceLignesDevis``, invoqué par ``DevisGenerator.jsx`` à l'enregistrement
d'une édition — et l'écran n'offre AUCUN geste « vider le devis » : sa charge
utile est toujours la liste des lignes restantes. Un vidage devra donc se
DÉCLARER (``remplacer_lignes(..., autoriser_vidage=True)``), jamais s'obtenir
par une liste vide.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr204_replace_lines_vide -v 2
"""
from rest_framework.test import APIClient, APITestCase

from apps.ventes.domain.lignes import MSG_REMPLACEMENT_VIDE, remplacer_lignes
from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Onduleur réseau Huawei 10kW', '1', '11700'),
    ('Panneau mono 550W', '14', '1100'),
    ('Installation', '1', '4000'),
]


class TestQJR204(APITestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR204-0001')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _url(self, devis=None):
        return ('/api/django/ventes/devis/%s/replace-lines/'
                % (devis or self.devis).id)

    # ── LE ROUGE ────────────────────────────────────────────────────────────
    def test_liste_vide_refusee_en_400_fr_et_lignes_intactes(self):
        resp = self.api.post(self._url(), {'lignes': []}, format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertEqual(resp.data['detail'], MSG_REMPLACEMENT_VIDE)
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    def test_le_refus_est_le_meme_que_celui_de_atomic(self):
        """``/atomic`` refusait déjà l'ensemble vide : les deux chemins
        d'écriture de l'écran répondent maintenant 400 tous les deux."""
        resp = self.api.post(
            '/api/django/ventes/devis/atomic/',
            {'client': self.client_obj.id, 'lignes': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_devis_envoye_aussi_protege(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        resp = self.api.post(self._url(), {'lignes': []}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    # ── L'ÉCRIVAIN UNIQUE PORTE LA MÊME GARDE ───────────────────────────────
    def test_ecrivain_unique_refuse_la_liste_vide(self):
        with self.assertRaises(ValueError) as leve:
            remplacer_lignes(self.devis, [], self.company)
        self.assertEqual(str(leve.exception), MSG_REMPLACEMENT_VIDE)
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    def test_ecrivain_unique_refuse_composition_none(self):
        """``ecrire_lignes(composition=None)`` traduit en liste vide : le même
        refus le couvre, sans garde séparée."""
        from apps.ventes.domain.pipeline import ecrire_lignes

        with self.assertRaises(ValueError):
            ecrire_lignes(self.devis, None, company=self.company)
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    def test_vidage_explicite_reste_possible(self):
        """Un futur flux de vidage DÉCLARE son intention — il ne l'obtient pas
        par omission."""
        remplacer_lignes(self.devis, [], self.company, autoriser_vidage=True)
        self.assertEqual(self.devis.lignes.count(), 0)

    # ── NON-RÉGRESSION ──────────────────────────────────────────────────────
    def test_remplacement_normal_inchange(self):
        produit = self.devis.lignes.first().produit
        resp = self.api.post(self._url(), {'lignes': [{
            'produit': produit.id, 'designation': 'Panneau mono 550W',
            'quantite': '12', 'prix_unitaire': '1100', 'ordre': 0,
        }]}, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(self.devis.lignes.count(), 1)

    # ── api-fuzz : forme du corps ────────────────────────────────────────────
    def test_corps_qui_n_est_pas_un_objet_400_sans_500(self):
        """``null`` / liste / nombre : ``request.data.get`` levait
        ``AttributeError`` (500). Lignes intactes."""
        for corps in ('null', '[]', '12'):
            with self.subTest(corps=corps):
                resp = self.api.post(self._url(), data=corps,
                                     content_type='application/json')
                self.assertEqual(resp.status_code, 400,
                                 getattr(resp, 'data', resp))
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    def test_etude_params_cle_inconnue_400_et_schema_ferme(self):
        """api-fuzz — une clé inconnue de l'étude est refusée (« le schéma est
        la seule porte ») ET le corps publié le dit : ``etude_params`` est un
        objet fermé (``additionalProperties: false``) dont les propriétés sont
        les entrées d'écran de ``domain/etude_schema``."""
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator
        from apps.ventes.domain import etude_schema

        produit = self.devis.lignes.first().produit
        ligne = {'produit': produit.id, 'designation': 'P',
                 'quantite': '1', 'prix_unitaire': '10', 'ordre': 0}
        resp = self.api.post(self._url(), {
            'lignes': [ligne], 'etude_params': {'cle_inventee': 1}},
            format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

        schema = SchemaGenerator(patterns=[
            path('api/django/ventes/', include('apps.ventes.urls'))
        ]).get_schema(request=None, public=True)
        etude = schema['components']['schemas'][
            'DevisReplaceLinesRequestRequest']['properties']['etude_params']
        self.assertIs(etude['additionalProperties'], False)
        self.assertNotIn('expected_updated_at', etude['properties'])
        ecran = {cle for cle, regle in etude_schema.SCHEMA.items()
                 if regle['nature'] == etude_schema.ENTREE
                 and not regle['exclusif']}
        self.assertEqual(set(etude['properties']), ecran)
        # ``nombre_proprietes`` n'accepte QUE des entiers côté serveur.
        self.assertEqual(etude['properties']['nombre_proprietes']['type'],
                         'integer')

    def test_corps_illisible_400_au_lieu_d_un_corps_vide(self):
        """api-fuzz — ``EntiteScopeMixin.initial`` avalait l'échec de lecture
        du corps : DRF le met alors en cache VIDE et la vue répondait 2xx à des
        octets aléatoires. Le 400 du parseur passe, sur une action sans
        garde de corps (``dupliquer-variante-gamme``) comme ici."""
        for url in (self._url(), '/api/django/ventes/devis/%s/'
                    'dupliquer-variante-gamme/' % self.devis.id):
            with self.subTest(url=url):
                resp = self.api.post(url, data=b'\xef\xbf\xbdq{',
                                     content_type='application/json')
                self.assertEqual(resp.status_code, 400,
                                 getattr(resp, 'data', resp))
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))

    def test_designation_et_textes_publies_sans_caractere_nul(self):
        """api-fuzz — le schéma de ``lignes[]`` publie « pas de caractère nul »
        (``designation``, ``groupe_label``, ``tva_base_legale``) : un nul fait
        refuser la ligne (400) alors que ``\\S`` seul la disait conforme."""
        import re

        from apps.ventes.views.openapi_docs import CORPS_REPLACE_LINES
        from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE

        items = CORPS_REPLACE_LINES[EXTENSION_CORPS_RESSERRE][
            'properties']['lignes']['items']
        for branche in items['anyOf']:
            for champ in ('designation', 'groupe_label'):
                motif = branche['properties'][champ]['pattern']
                self.assertIsNone(re.search(motif, 'a\x00b'), (champ, motif))
                self.assertIsNotNone(re.search(motif, 'Pose'), (champ, motif))
        section = items['anyOf'][0]['properties']['designation']['pattern']
        self.assertIsNone(re.search(section, '   '))
        resp = self.api.post(self._url(), {'lignes': [
            {'type_ligne': 'section', 'designation': 'Lot\x00 A'}]},
            format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertEqual(self.devis.lignes.count(), len(LIGNES))
