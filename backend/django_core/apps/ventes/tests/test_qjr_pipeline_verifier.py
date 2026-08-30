# -*- coding: utf-8 -*-
"""QJR82 — l'étape `verifier` s'applique aux chemins de création, et sait dire
« deux options ».

CE QUE CES TESTS VERROUILLENT, ET POURQUOI.

Constat QB82 (audit L3 du 29/08/2026), vérifié en code : la pré-vérification
``validate_composition_for_layout`` était

  1. **câblée sur UN SEUL des cinq chemins de création** — le calepinage 3D
     (``views/devis.py::from_layout``). Le devis AUTOMATIQUE et le TUNNEL
     créaient des devis sans elle : un catalogue amputé de son onduleur
     hybride laissait donc naître un devis « Les deux » que rien ne pouvait
     servir, et le trou se découvrait à la génération du PDF ;
  2. **MONO-SCÉNARIO** — elle ne savait dire que « avec batterie » OU
     « réseau ». Le cas à DEUX OPTIONS, qui est pourtant le DÉFAUT du devis
     automatique (U2), n'était pas exprimable : elle ne vérifiait jamais que
     les DEUX moitiés de la comparaison promise au client existaient.

Depuis QJR82, l'étape vit dans ``domain/pipeline.verifier`` et les messages
français n'ont qu'UN seul point de définition. ``validate_composition_for_
layout`` n'est plus qu'un adaptateur layout → intention, et
``build_devis_auto`` (donc le devis automatique ET le tunnel) l'appelle AVANT
toute écriture.

Le test qui compte est ``test_le_tunnel_refuse_avec_le_meme_message_que_la_3d``.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_pipeline_verifier -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.domain import geometrie, pipeline

User = get_user_model()


# ── La moitié PURE : aucune base, tout est exécutable en l'état ──────────────

class _CatalogueFictif:
    """Remplace les trois lectures catalogue de l'étape, le temps d'un test."""

    def __init__(self, *, reseau=True, hybride=True, batterie=True,
                 plage=None):
        self.reseau, self.hybride = reseau, hybride
        self.batterie, self.plage = batterie, plage
        self._anciens = {}

    def __enter__(self):
        def _pick(company, predicat, *, role=None, gamme=None, **_):
            if role == 'onduleur_reseau':
                return object() if self.reseau else None
            if role == 'onduleur_hybride':
                return object() if self.hybride else None
            return None

        self._anciens = {
            '_pick_product': pipeline._pick_product,
            '_pick_batterie': pipeline._pick_batterie,
            '_plage_batterie_de_l_onduleur':
                pipeline._plage_batterie_de_l_onduleur,
        }
        pipeline._pick_product = _pick
        pipeline._pick_batterie = (
            lambda company, onduleur=None: object() if self.batterie else None)
        pipeline._plage_batterie_de_l_onduleur = lambda onduleur: self.plage
        return self

    def __exit__(self, *exc):
        for nom, valeur in self._anciens.items():
            setattr(pipeline, nom, valeur)
        return False


class LEtapeVerifierParleLesTroisScenarios(SimpleTestCase):
    """La généralisation elle-même — sans base, donc sans excuse."""

    def _verifier(self, scenario, **catalogue):
        with _CatalogueFictif(**catalogue):
            return pipeline.verifier(pipeline.IntentionComposition(
                company=None, nb_panneaux=9, kwc=6.39, scenario=scenario))

    def test_scenario_sans_exige_le_reseau_et_lui_seul(self):
        self.assertIsNone(self._verifier('sans', hybride=False,
                                         batterie=False))
        self.assertEqual(self._verifier('sans', reseau=False),
                         [pipeline.MSG_SANS_ONDULEUR_RESEAU])

    def test_scenario_avec_exige_hybride_et_batterie(self):
        self.assertIsNone(self._verifier('avec', reseau=False))
        self.assertEqual(self._verifier('avec', hybride=False),
                         [pipeline.MSG_SANS_ONDULEUR_HYBRIDE])
        self.assertEqual(self._verifier('avec', batterie=False),
                         [pipeline.MSG_SANS_BATTERIE])

    def test_scenario_les_deux_exige_LES_DEUX_moities(self):
        """LA généralisation : un devis à deux options qui ne sait servir
        qu'une moitié promet au client une comparaison qui n'existe pas.
        Avant QJR82 ce cas n'était pas exprimable."""
        self.assertIsNone(self._verifier('les_deux'))
        # Le réseau manque : le scénario « avec » seul ne l'aurait jamais vu.
        self.assertEqual(self._verifier('les_deux', reseau=False),
                         [pipeline.MSG_SANS_ONDULEUR_RESEAU])
        # L'hybride manque : le scénario « sans » seul ne l'aurait jamais vu.
        self.assertEqual(self._verifier('les_deux', hybride=False),
                         [pipeline.MSG_SANS_ONDULEUR_HYBRIDE])
        # Les deux moitiés manquent : les DEUX manques sont nommés.
        self.assertEqual(
            self._verifier('les_deux', reseau=False, hybride=False,
                           batterie=False),
            [pipeline.MSG_SANS_ONDULEUR_RESEAU,
             pipeline.MSG_SANS_ONDULEUR_HYBRIDE,
             pipeline.MSG_SANS_BATTERIE])

    def test_batterie_incompatible_dit_la_plage_de_l_onduleur(self):
        """PVOND — « aucune batterie » et « aucune batterie COMPATIBLE »
        n'appellent pas le même geste."""
        erreurs = self._verifier('avec', batterie=False, plage=(160, 700))
        self.assertEqual(len(erreurs), 1)
        self.assertIn('160-700 V', erreurs[0])

    def test_sans_panneau_ni_puissance_rien_a_composer(self):
        with _CatalogueFictif():
            erreurs = pipeline.verifier(pipeline.IntentionComposition(
                company=None, scenario='sans'))
        self.assertEqual(erreurs, [pipeline.MSG_AUCUN_PANNEAU])


class LeScenarioSeLitDansLeLayout(SimpleTestCase):
    """L'adaptateur 3D traduit un layout dans le vocabulaire du pipeline."""

    def test_les_trois_lectures(self):
        self.assertEqual(geometrie.scenario_du_layout({}), 'sans')
        self.assertEqual(geometrie.scenario_du_layout({'scenario': 'reseau'}),
                         'sans')
        self.assertEqual(
            geometrie.scenario_du_layout({'scenario': 'avec_batterie'}),
            'avec')
        self.assertEqual(geometrie.scenario_du_layout({'scenario': 'hybride'}),
                         'avec')
        self.assertEqual(geometrie.scenario_du_layout({'battery': True}),
                         'avec')
        self.assertEqual(geometrie.scenario_du_layout({'scenario': 'les_deux'}),
                         'les_deux')

    def test_layout_invalide_reste_refuse_en_francais(self):
        self.assertEqual(
            geometrie.validate_composition_for_layout('pas-un-dict', None),
            ['Layout invalide — impossible de valider la composition.'])


# ── La moitié BOUT-EN-BOUT : le tunnel et la 3D, même catalogue amputé ──────

#: Catalogue AMPUTÉ de son onduleur hybride ET de sa batterie : l'option
#: « avec » — donc la moitié « avec » de tout devis à deux options — n'est pas
#: servable. Tout le reste est présent et tarifé.
CATALOGUE_SANS_HYBRIDE = [
    ('Panneau Canadien Solar 710W', 'V82-PAN', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', 'V82-ONDR', '14000'),
    ('Structures acier', 'V82-STR', '500'),
    ('Socles', 'V82-SOC', '80'),
    ('Accessoires', 'V82-ACC', '2000'),
    ('Tableau De Protection AC/DC', 'V82-TAB', '2000'),
    ('Installation', 'V82-INST', '4800'),
    ('Transport', 'V82-TRANS', '1000'),
]


class LesCinqCheminsDisentLaMemePhrase(TestCase):
    """Le test de QJR82 : le tunnel refuse ce que la 3D refuse, MOT POUR MOT."""

    def setUp(self):
        from authentication.models import Company

        self.company, _ = Company.objects.get_or_create(
            slug='qjr82-verifier', defaults={'nom': 'qjr82-verifier'})
        self.user = User.objects.create_user(
            username='qjr82', password='x', company=self.company,
            role_legacy='admin')
        for nom, sku, prix in CATALOGUE_SANS_HYBRIDE:
            Produit.objects.create(
                company=self.company, nom=nom,
                sku='%s-%s' % (sku, self.company.pk),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500)

    def _lead(self):
        return Lead.objects.create(
            company=self.company, nom='Tunnel', prenom='QJR82',
            email='qjr82@example.com', type_installation='residentiel',
            taille_souhaitee_kwc=Decimal('6'))

    def test_le_chemin_3d_refuse_la_composition_impossible(self):
        erreurs = geometrie.validate_composition_for_layout(
            {'result': {'panels': 9, 'kwc': 6.39},
             'scenario': 'avec_batterie'}, self.company)
        self.assertEqual(erreurs[0], pipeline.MSG_SANS_ONDULEUR_HYBRIDE)

    def test_le_chemin_3d_deux_options_voit_les_deux_moities(self):
        """Un layout DÉCLARÉ « les deux » : l'étape vérifie désormais les DEUX
        onduleurs. Le réseau est là, l'hybride non — c'est lui qui est nommé."""
        erreurs = geometrie.validate_composition_for_layout(
            {'result': {'panels': 9, 'kwc': 6.39},
             'scenario': 'les_deux'}, self.company)
        self.assertIn(pipeline.MSG_SANS_ONDULEUR_HYBRIDE, erreurs)

    def test_le_tunnel_refuse_avec_le_meme_message_que_la_3d(self):
        """LE test de QJR82. Le lead du tunnel ne dit rien de sa batterie :
        le devis automatique compose donc « les deux » (U2). L'option « avec »
        n'est pas servable ⇒ AUCUN devis n'est créé, et la note d'abstention
        posée sur le lead porte EXACTEMENT la phrase que la 3D affiche."""
        from apps.ventes.domain.creation import (
            creer_devis_automatique_depuis_lead)
        from apps.ventes.models import Devis

        lead = self._lead()
        message_3d = geometrie.validate_composition_for_layout(
            {'result': {'panels': 9, 'kwc': 6.39},
             'scenario': 'les_deux'}, self.company)[0]

        devis = creer_devis_automatique_depuis_lead(
            lead_id=lead.id, company_id=self.company.id)

        self.assertIsNone(devis, 'le tunnel a créé un devis que le catalogue '
                                 'ne sait pas servir')
        self.assertFalse(Devis.objects.filter(company=self.company).exists())

        from apps.crm.models import LeadActivity
        notes = ' | '.join(
            LeadActivity.objects.filter(lead=lead).values_list('body',
                                                               flat=True))
        self.assertIn(message_3d, notes,
                      'le tunnel ne dit pas la même phrase que la 3D')

    def test_le_devis_auto_refuse_aussi_en_422(self):
        """Même étape, même phrase, sur l'endpoint du commercial."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))
        lead = self._lead()
        resp = api.post('/api/django/ventes/devis/auto/',
                        {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertIn(pipeline.MSG_SANS_ONDULEUR_HYBRIDE, str(resp.data))

    def test_un_catalogue_complet_ne_refuse_rien(self):
        """Le témoin négatif : rien ne change pour une société équipée."""
        for nom, sku, prix in (
                ('Onduleur hybride Deye 5kW Monophasé', 'V82-ONDH', '17000'),
                ('Batterie Dyness 5 kWh', 'V82-BAT', '16000')):
            Produit.objects.create(
                company=self.company, nom=nom,
                sku='%s-%s' % (sku, self.company.pk),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500)
        self.assertIsNone(geometrie.validate_composition_for_layout(
            {'result': {'panels': 9, 'kwc': 6.39}, 'scenario': 'les_deux'},
            self.company))

        from apps.ventes.domain.creation import (
            creer_devis_automatique_depuis_lead)
        devis = creer_devis_automatique_depuis_lead(
            lead_id=self._lead().id, company_id=self.company.id)
        self.assertIsNotNone(devis)
