"""QJR202 — ``/variante`` cesse de publier l'étude de la taille SOURCE.

TEST ROUGE D'ABORD : ``views/devis.dupliquer_variante`` recopiait
``etude_params`` VERBATIM sur des devis dont il venait de multiplier les
quantités par 0,8 / 1,2. Les copies publiaient donc la production, les
économies et l'étude horaire d'une AUTRE taille d'installation — jusque dans le
PDF client (classe CS4-CS6, fermée par QJR117 sur les trois chemins du domaine
avec ``domain/etudes.etude_params_pour_copie`` + rafraîchissement forcé ;
``/variante`` était resté dehors).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr202_variante_etude -v 2
"""
from decimal import Decimal

from rest_framework.test import APIClient, APITestCase

from apps.ventes.domain.etudes import CLES_NON_COPIEES
from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

#: Les chiffres DÉRIVÉS de la taille source — ceux qui ne doivent jamais
#: atterrir tels quels sur une copie mise à l'échelle.
PROD_SOURCE = 14086
ECO_SOURCE = 20953

ETUDE_SOURCE = {
    'scenario': 'Les deux (Sans + Avec)',
    'puissance_kwc': 9.94,
    'production_annuelle': PROD_SOURCE,
    'economies_annuelles': ECO_SOURCE,
    'payback': 4.7,
    'etude_horaire': {'couches': [{'nom': 'base', 'kwh': 1234}]},
    'dimensionnement': {'paliers': [{'kwc': 9.94, 'cout_ttc': 100000}]},
    'profils_comparatifs': {'profils': []},
    # Une clé de CONFIGURATION : elle, se recopie.
    'tension_raccordement': 'bt',
}

LIGNES = [
    ('Onduleur réseau Huawei 10kW', '1', '11700'),
    ('Onduleur hybride Deye 10kW', '1', '24000'),
    ('Panneau mono 550W', '14', '1100'),
    ('Batterie 5 kWh', '1', '14000'),
    ('Installation', '1', '4000'),
]


class TestQJR202VarianteEtude(APITestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.source = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR202-0001', etude_params=dict(ETUDE_SOURCE))
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _variantes(self, pct=20):
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.source.id}/dupliquer-variante/',
            {'variante_pct': pct}, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        return [Devis.objects.get(pk=item['id']) for item in resp.data]

    def _mise_a_lechelle(self, variantes):
        """La variante 1,2× — celle dont les quantités ont RÉELLEMENT bougé."""
        source_qte = sum(li.quantite for li in self.source.lignes.all())
        for v in variantes:
            if sum(li.quantite for li in v.lignes.all()) > source_qte:
                return v
        self.fail('aucune variante agrandie produite')

    def test_la_variante_ne_publie_plus_la_production_de_la_source(self):
        """LE ROUGE : la copie 1,2× portait ``production_annuelle`` = 14 086,
        la production de l'installation SOURCE."""
        agrandie = self._mise_a_lechelle(self._variantes())
        params = agrandie.etude_params or {}
        self.assertNotEqual(params.get('production_annuelle'), PROD_SOURCE)
        self.assertNotEqual(params.get('economies_annuelles'), ECO_SOURCE)

    def test_toutes_les_cles_derivees_de_la_source_sont_purgees(self):
        """Le jeu de clés purgées est celui du domaine — pas une liste locale
        (un test qui rougit si une clé y est ajoutée sans être purgée ici)."""
        agrandie = self._mise_a_lechelle(self._variantes())
        params = agrandie.etude_params or {}
        for cle in CLES_NON_COPIEES:
            valeur_source = ETUDE_SOURCE.get(cle)
            if valeur_source is None:
                continue
            self.assertNotEqual(
                params.get(cle), valeur_source,
                f"la variante publie « {cle} » de la taille SOURCE")

    def test_la_configuration_se_recopie(self):
        """Purger n'est pas oublier : la CONFIGURATION du source suit."""
        agrandie = self._mise_a_lechelle(self._variantes())
        params = agrandie.etude_params or {}
        self.assertEqual(params.get('tension_raccordement'), 'bt')
        self.assertEqual(params.get('scenario'), 'Les deux (Sans + Avec)')

    def test_la_source_nest_pas_mutee(self):
        """Le bloc de la source est INTACT — la copie ne partage plus sa
        référence (piège nommé par ``etude_params_pour_copie``)."""
        self._variantes()
        self.source.refresh_from_db()
        self.assertEqual(
            (self.source.etude_params or {}).get('production_annuelle'),
            PROD_SOURCE)

    def test_les_echelles_de_quantite_sont_inchangees(self):
        """Non-régression : QJR202 ne touche QUE l'étude."""
        variantes = self._variantes()
        self.assertEqual(len(variantes), 3)
        panneaux_source = next(
            li.quantite for li in self.source.lignes.all()
            if li.designation.startswith('Panneau'))
        quantites = sorted(
            next(li.quantite for li in v.lignes.all()
                 if li.designation.startswith('Panneau'))
            for v in variantes)
        self.assertEqual(quantites, [
            (panneaux_source * Decimal('0.8')).quantize(Decimal('0.01')),
            panneaux_source,
            (panneaux_source * Decimal('1.2')).quantize(Decimal('0.01')),
        ])
