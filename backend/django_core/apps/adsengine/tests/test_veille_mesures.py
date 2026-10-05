"""VEIL18 — Mesures automatiques d'une découverte.

Fixture : 3 requêtes × 4 pages, valeurs calculées À LA MAIN (détail dans les
commentaires). Une valeur non calculable vaut ``None`` + motif, jamais 0.
"""
import datetime
import json
import pathlib

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import veille_decouverte as vd
from apps.adsengine import veille_mesures
from apps.adsengine.models import (
    CompetitorPage, VeilleAnnonceur, VeilleDecouverte,
)

User = get_user_model()
MAINTENANT = timezone.make_aware(datetime.datetime(2026, 10, 5, 12, 0))
ANCIEN, RECENT = '2026-09-20', '2026-10-03'

# (ad_id, page_id, légende, début) par page, pour chaque requête.
R1 = [  # robe / FR
    [('a1', 'A', 'a.fr', ANCIEN), ('a2', 'B', 'b.fr', ANCIEN)],
    [('a3', 'A', 'a.fr', ANCIEN), ('a4', 'C', 'Shop Now', ANCIEN)],
    [('a5', 'D', 'd.fr', ANCIEN)],
    [('a6', 'B', 'b.fr', ANCIEN)],
]
R2 = [  # robe / BE
    [('b1', 'A', 'a.fr', ANCIEN)],
    [('b2', 'E', 'a.fr', ANCIEN)],
    [('b3', 'B', 'b.fr', ANCIEN)],
    [('b4', 'F', 'Livraison offerte', ANCIEN)],
]
R3 = [  # sac / FR
    [('c1', 'G', 'g.fr', RECENT), ('c2', 'A', 'a.fr', RECENT)],
    [('c3', 'G', 'g.fr', RECENT)],
    [('c4', 'H', 'h.fr', RECENT)],
    [('c5', 'G', 'g.fr', RECENT)],
]


def _pub(ad_id, page_id, legende, debut):
    nom = 'Maison Lilas' if page_id == 'D' else f'Boutique {page_id}'
    return {'id': ad_id, 'page_id': page_id, 'page_name': nom,
            'ad_creative_bodies': [f'Texte {ad_id}'],
            'ad_creative_link_captions': [legende],
            'ad_delivery_start_time': debut}


@override_settings(VEILLE_SOCIETES_AUTORISEES=[])
class MesuresTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='YB', slug='yb-mesures')
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            self.dec = vd.creer_decouverte(self.company, None, {
                'mots_cles': [{'texte': 'robe', 'pays': ['FR', 'BE']},
                              {'texte': 'sac', 'pays': ['FR']}],
                'plafond_appels': 50, 'plafond_pages_par_requete': 10})
        requetes = list(self.dec.requetes.order_by('ordre'))
        for requete, pages in zip(requetes, (R1, R2, R3)):
            for numero, contenu in enumerate(pages, start=1):
                vd.ingerer_page(requete, {
                    'pubs': [_pub(*p) for p in contenu],
                    'a_suivant': numero < 4,
                    'after_suivant': f'C{numero}'}, numero)

    def calculer(self):
        return veille_mesures.calculer(self.dec, maintenant=MAINTENANT)

    def test_forme_du_contrat(self):
        contrat = json.loads(
            (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
             / 'veille_mesures.json').read_text(encoding='utf-8'))['exemple']
        mesures = self.calculer()
        self.assertEqual(set(mesures), set(contrat))
        for cle in ('annonceurs_distincts', 'pubs_par_appel', 'saturation',
                    'rappel_concurrents_nommes', 'doublons',
                    'taux_remplissage_domaine', 'part_dropshipper'):
            self.assertEqual(set(mesures[cle]), set(contrat[cle]), cle)

    def test_annonceurs_distincts(self):
        # robe : R1 {A,B,C,D} ∪ R2 {A,E,B,F} = 6 ; sac : {G,A,H} = 3.
        # FR : R1 ∪ R3 = {A,B,C,D,G,H} = 6 ; BE : {A,E,B,F} = 4 ; total 8.
        self.assertEqual(self.calculer()['annonceurs_distincts'], {
            'par_mot_cle': [{'mot_cle': 'robe', 'valeur': 6},
                            {'mot_cle': 'sac', 'valeur': 3}],
            'par_pays': [{'pays': 'FR', 'valeur': 6},
                         {'pays': 'BE', 'valeur': 4}],
            'total': 8})

    def test_pubs_par_appel_et_appels(self):
        # pubs par page : 2,2,1,1 | 1,1,1,1 | 2,1,1,1 → 15 / 12 = 1.25
        m = self.calculer()
        self.assertEqual(m['pubs_par_appel'], {
            'moyenne': 1.25, 'mediane': 1, 'min': 1, 'max': 2,
            'motif_fr': None})
        self.assertEqual(m['appels_par_mot_cle'], [
            {'mot_cle': 'robe', 'appels': 8}, {'mot_cle': 'sac', 'appels': 4}])

    def test_saturation(self):
        sat = self.calculer()['saturation']
        cumul = [p['nouveaux_page_id_cumules'] for p in sat['global']]
        self.assertEqual(cumul, [3, 5, 7, 8])
        courbes = {(c['mot_cle'], c['pays']):
                   [p['nouveaux_page_id_cumules'] for p in c['courbe']]
                   for c in sat['par_requete']}
        self.assertEqual(courbes, {('robe', 'FR'): [2, 3, 4, 4],
                                   ('robe', 'BE'): [1, 2, 3, 4],
                                   ('sac', 'FR'): [2, 2, 3, 3]})

    def test_rappel_concurrents_nommes(self):
        CompetitorPage.objects.create(company=self.company, name='Comp A',
                                      page_id='A')          # par page_id
        CompetitorPage.objects.create(company=self.company,
                                      name='Maison  LILAS')  # par nom
        CompetitorPage.objects.create(company=self.company, name='Hachette',
                                      website='https://www.h.fr')  # domaine
        CompetitorPage.objects.create(company=self.company, name='Absente')
        self.assertEqual(self.calculer()['rappel_concurrents_nommes'], {
            'trouves': 3, 'total': 4, 'absents': ['Absente'],
            'motif_fr': None})

    def test_rappel_sans_concurrent_null_jamais_zero(self):
        rappel = self.calculer()['rappel_concurrents_nommes']
        self.assertIsNone(rappel['trouves'])
        self.assertTrue(rappel['motif_fr'])

    def test_doublons_domaine_et_actives(self):
        m = self.calculer()
        # A (3 requêtes) et B (2) sur 8 → 0.25 ; multi-pays A, B → 2 ;
        # a.fr partagé par A et E → 1.
        self.assertEqual(m['doublons'], {
            'recouvrement_entre_requetes': 0.25, 'annonceurs_multi_pays': 2,
            'domaines_partages': 1, 'motif_fr': None})
        # 15 pubs, 2 sans domaine (a4, b4) → 13/15
        self.assertEqual(m['taux_remplissage_domaine'],
                         {'valeur': 0.8667, 'motif_fr': None})
        # R1 + R2 = 10 pubs depuis le 20/09 (≥ 5 j), R3 = 5 depuis le 03/10
        self.assertEqual(m['part_pubs_actives_5_jours'], 0.6667)

    def test_parts_par_classe_et_dropshipper(self):
        VeilleAnnonceur.objects.filter(page_id__in=['A', 'B']).update(
            classe='vendeur')
        VeilleAnnonceur.objects.filter(page_id='G').update(
            classe='place_de_marche')
        m = self.calculer()
        parts = {p['classe']: p['part'] for p in m['part_par_classe']}
        self.assertEqual(parts, {'vendeur': 0.25, 'place_de_marche': 0.125,
                                 'hors_sujet': 0.0, 'pas_vendeur': 0.0,
                                 'doublon': 0.0, 'incertain': 0.625})
        self.assertEqual(m['part_dropshipper']['valeur'], None)
        self.assertTrue(m['part_dropshipper']['motif_fr'])
        VeilleAnnonceur.objects.filter(page_id='A').update(
            dropshipper_probable='oui', dropshipper_decide_par='regle')
        VeilleAnnonceur.objects.filter(page_id='B').update(
            dropshipper_probable='non', dropshipper_decide_par='regle')
        self.assertEqual(self.calculer()['part_dropshipper'],
                         {'valeur': 0.5, 'motif_fr': None})


class MesuresVidesTests(TestCase):
    def test_decouverte_vide_null_et_motifs(self):
        company = Company.objects.create(nom='V', slug='v-mesures')
        dec = VeilleDecouverte.objects.create(
            company=company, plafond_appels=1, plafond_pages_par_requete=1)
        m = veille_mesures.calculer(dec, maintenant=MAINTENANT)
        self.assertIsNone(m['pubs_par_appel']['moyenne'])
        self.assertTrue(m['pubs_par_appel']['motif_fr'])
        self.assertIsNone(m['taux_remplissage_domaine']['valeur'])
        self.assertIsNone(m['doublons']['recouvrement_entre_requetes'])
        self.assertIsNone(m['part_pubs_actives_5_jours'])
        self.assertEqual(m['part_par_classe'], [])
        self.assertEqual(m['annonceurs_distincts']['total'], 0)


class MesuresApiTests(TestCase):
    def test_route_mesures(self):
        company = Company.objects.create(nom='API', slug='api-mesures')
        role = Role.objects.create(company=company, nom='r-mes',
                                   permissions=['adsengine_view'])
        user = User.objects.create_user(username='mes_l', password='x',
                                        company=company, role_legacy='normal',
                                        role=role)
        dec = VeilleDecouverte.objects.create(
            company=company, plafond_appels=1, plafond_pages_par_requete=1)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(
            f'/api/django/adsengine/veille/decouvertes/{dec.pk}/mesures/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['decouverte_id'], dec.pk)
