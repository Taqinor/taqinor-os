"""VEIL20 — Règles gratuites (zéro jeton) : classes, doublons, indices dropshipper.

31 cas en fixture (chaque classe + l'étiquette dropshipper), déterminisme,
ZÉRO appel réseau, et une décision humaine ou IA jamais écrasée.
"""
import datetime
import random
import socket
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from authentication.models import Company

from apps.adsengine import veille_decouverte as vd
from apps.adsengine import veille_regles as vr
from apps.adsengine.models import VeilleAnnonceur, VeilleVerdict

MAINTENANT = timezone.make_aware(datetime.datetime(2026, 10, 5, 12, 0))
IL_Y_A_30_J = MAINTENANT - datetime.timedelta(days=30)
_COMPTEUR = [0]


def p(texte, legende='', payeurs=(), titres=(), debut=None, fin=None):
    _COMPTEUR[0] += 1
    return {'ad_archive_id': f'{1000 + _COMPTEUR[0]}', 'texte': texte,
            'titres': list(titres), 'legende': legende,
            'domaine': vd.legende_vers_domaine(legende),
            'payeurs': list(payeurs), 'debut': debut, 'fin': fin}


def f(page_id, nom, *pubs):
    return {'page_id': page_id, 'page_name': nom, 'pubs': list(pubs)}


# (fiche, classe attendue, dropshipper attendu, doublon_de attendu)
CAS = [
    # ── vendeurs (6 langues) ────────────────────────────────────────────
    (f('v1', 'Maison Lilas', p("Nouvelle collection de robes d'été, "
                               "livraison offerte dès 60 €",
                               'maison-lilas.fr')),
     'vendeur', 'incertain', None),
    (f('v2', 'Brick Lane Boots', p('Handmade leather boots, free shipping',
                                   'brickboots.co.uk')),
     'vendeur', 'incertain', None),
    (f('v3', 'Taschenwerk', p('Handtaschen aus Leder – jetzt kaufen',
                              'taschenwerk.de')),
     'vendeur', 'incertain', None),
    (f('v4', 'Calzados Ruiz', p('Zapatos de piel, envio gratis',
                                'calzadosruiz.es')),
     'vendeur', 'incertain', None),
    (f('v5', 'Borse Atelier Bianchi', p('Borse in pelle, spedizione gratuita',
                                        'borsebianchi.it')),
     'vendeur', 'incertain', None),
    (f('v6', 'Jurkjes Anna', p('Zomerse jurken, gratis verzending',
                               'annajurken.nl')),
     'vendeur', 'incertain', None),
    # ── places de marché et géants (D-VEIL-1) ──────────────────────────
    (f('m1', 'SHEIN FR', p('Robes à petits prix', 'fr.shein.com')),
     'place_de_marche', 'incertain', None),
    (f('m2', 'Amazon Mode', p('Sacs et chaussures', 'amazon.fr')),
     'place_de_marche', 'incertain', None),
    (f('m3', 'Zalando', p('Neue Schuhe', 'zalando.de')),
     'place_de_marche', 'incertain', None),
    (f('m4', 'Vinted', p('Vendez vos vêtements', 'vinted.fr')),
     'place_de_marche', 'incertain', None),
    # ── pas un vendeur ─────────────────────────────────────────────────
    (f('e1', 'Mode Magazine', p('Lisez notre article sur les tendances'),
       p('Écoutez notre podcast')),
     'pas_vendeur', 'incertain', None),
    (f('e2', 'StyleCast', p('Download the app and subscribe')),
     'pas_vendeur', 'incertain', None),
    (f('e3', 'Modeblog Berlin', p('Neuer Artikel im Blog')),
     'pas_vendeur', 'incertain', None),
    (f('e4', 'Agencia Luz', p('Descargar la aplicacion')),
     'pas_vendeur', 'incertain', None),
    # ── hors sujet (D-VEIL-3) ──────────────────────────────────────────
    (f('h1', 'Bijoux Lou', p('Colliers et bracelets en or, livraison '
                             'offerte', 'bijouxlou.fr')),
     'hors_sujet', 'incertain', None),
    (f('h2', 'Glow Lab', p('Vitamin C serum for radiant skin'),
       p('Discover our perfume')),
     'hors_sujet', 'incertain', None),
    (f('h3', 'Orologi Roma', p('Orologi di lusso'), p('Nuovi orologi')),
     'hors_sujet', 'incertain', None),
    (f('h4', 'Woonhuis', p('Meubels en woondecoratie')),
     'hors_sujet', 'incertain', None),
    # ── doublons ───────────────────────────────────────────────────────
    (f('d1', 'Lilas Mode', p('Robes en lin, livraison offerte',
                             'lilas-mode.fr')),
     'vendeur', 'incertain', None),
    (f('d2', 'Lilas Mode Bis', p('Jupes en lin, livraison offerte',
                                 'www.lilas-mode.fr')),
     'doublon', 'incertain', 'd1'),
    (f('d3', 'Atelier Rouge', p('Vestes en laine, livraison',
                                'atelierrouge.fr', payeurs=['ACME SAS'])),
     'vendeur', 'incertain', None),
    (f('d4', 'Rouge Paris', p('Manteaux chauds, livraison',
                              'rougeparis.fr', payeurs=['ACME SAS'])),
     'doublon', 'incertain', 'd3'),
    (f('d5', 'Lin et Coton', p('Robe fluide en lin, livraison offerte '
                               'partout en France')),
     'incertain', 'incertain', None),
    (f('d6', 'Coton et Lin', p('Robe fluide en lin, livraison offerte '
                               'partout en France')),
     'doublon', 'incertain', 'd5'),
    # ── incertains (pour l'IA) ─────────────────────────────────────────
    (f('i1', 'Les Copines', p('Découvrez notre blog')),
     'incertain', 'incertain', None),
    (f('i2', 'Noir Total', p('Robe noire', 'Shop Now')),
     'incertain', 'incertain', None),
    (f('i3', 'Insta Robes', p('Robes, commandez en message privé',
                              'instagram.com/instarobes')),
     'incertain', 'incertain', None),
    (f('i4', 'Bonjour', p('Bonjour à tous')),
     'incertain', 'incertain', None),
    (f('i5', 'Temps Libre', p('Nouvelle montre')),
     'incertain', 'incertain', None),
    # ── étiquette dropshipper (attribut, jamais une classe) ────────────
    (f('s1', 'Trendy Shop', p("Robes à -70 % aujourd'hui seulement, "
                              'livraison gratuite', 'trendyshop.store',
                              debut=IL_Y_A_30_J)),
     'vendeur', 'oui', None),
    (f('s2', 'Best Deals Store', p('Sacs à -60 %, livraison gratuite',
                                   'bestdeals.shop')),
     'vendeur', 'oui', None),
    (f('s3', 'Lilas', p('Robes -50 %, livraison', 'lilas.fr')),
     'vendeur', 'incertain', None),
]


def _interdit(*a, **k):
    raise AssertionError('appel réseau interdit dans les règles')


class ReglesFixtureTests(SimpleTestCase):
    def _resultats(self):
        return vr.classer_tout([c[0] for c in CAS], maintenant=MAINTENANT)

    def test_au_moins_30_cas_et_chaque_classe(self):
        self.assertGreaterEqual(len(CAS), 30)
        classes = {c[1] for c in CAS}
        self.assertEqual(classes, {'vendeur', 'place_de_marche', 'hors_sujet',
                                   'pas_vendeur', 'doublon', 'incertain'})
        self.assertIn('oui', {c[2] for c in CAS})

    def test_chaque_cas(self):
        with mock.patch.object(socket.socket, 'connect', _interdit), \
                mock.patch('httpx.Client.send', side_effect=_interdit):
            resultats = self._resultats()
        for fiche, classe, drop, doublon in CAS:
            res = resultats[fiche['page_id']]
            with self.subTest(page=fiche['page_id'], nom=fiche['page_name']):
                self.assertEqual(res['classe'], classe, res)
                self.assertEqual(res['dropshipper']['probable'], drop, res)
                self.assertEqual(res['doublon_de'], doublon)
                self.assertTrue(res['motif_fr'])
                for preuve in res['preuves']:
                    self.assertEqual(set(preuve),
                                     {'champ', 'valeur', 'ad_archive_id'})
                if res['classe'] not in ('incertain',):
                    self.assertTrue(res['preuves'], res)

    def test_dropshipper_est_un_attribut_avec_indices(self):
        res = self._resultats()['s1']
        champs = {i['champ'] for i in res['dropshipper']['indices']}
        self.assertTrue({'ad_creative_bodies', 'ad_delivery_start_time',
                         'page_name', 'ad_creative_link_captions'} <= champs)
        self.assertEqual(res['classe'], 'vendeur')

    def test_deterministe(self):
        premier = self._resultats()
        self.assertEqual(premier, self._resultats())
        # l'ordre des pubs dans une fiche ne change rien
        fiche = f('x', 'Maison Lilas',
                  p('Robes légères, livraison offerte', 'maison-lilas.fr'),
                  p('Jupes plissées en promo', 'maison-lilas.fr'))
        melange = dict(fiche, pubs=list(reversed(fiche['pubs'])))
        random.Random(1).shuffle(melange['pubs'])
        self.assertEqual(vr.classer(fiche), vr.classer(melange))


@override_settings(VEILLE_SOCIETES_AUTORISEES=[])
class AppliquerReglesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='YB', slug='yb-regles')
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            self.dec = vd.creer_decouverte(self.company, None, {
                'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
                'plafond_appels': 5, 'plafond_pages_par_requete': 5})
        pubs = [
            {'id': '1', 'page_id': 'A', 'page_name': 'Maison Lilas',
             'ad_creative_bodies': ['Robes légères, livraison offerte'],
             'ad_creative_link_captions': ['maison-lilas.fr']},
            {'id': '2', 'page_id': 'B', 'page_name': 'SHEIN',
             'ad_creative_bodies': ['Robes'],
             'ad_creative_link_captions': ['shein.com']},
            {'id': '3', 'page_id': 'C', 'page_name': 'Blog Mode',
             'ad_creative_bodies': ['Lisez notre article de blog']},
        ]
        vd.ingerer_page(self.dec.requetes.get(),
                        {'pubs': pubs, 'a_suivant': False}, 1)

    def test_applique_sans_reseau_et_idempotent(self):
        with mock.patch('httpx.Client.send', side_effect=_interdit):
            compte = vr.appliquer_regles(self.dec, maintenant=MAINTENANT)
        self.assertEqual(compte, {'vendeur': 1, 'place_de_marche': 1,
                                  'pas_vendeur': 1})
        classes = dict(VeilleAnnonceur.objects.values_list('page_id',
                                                           'classe'))
        self.assertEqual(classes, {'A': 'vendeur', 'B': 'place_de_marche',
                                   'C': 'pas_vendeur'})
        n = VeilleVerdict.objects.count()
        vr.appliquer_regles(self.dec, maintenant=MAINTENANT)
        self.assertEqual(VeilleVerdict.objects.count(), n)
        a = VeilleAnnonceur.objects.get(page_id='A')
        self.assertEqual(a.verdict_courant.decide_par, 'regle')
        self.assertEqual(a.verdict_courant.version_consigne, 'regles-v1')

    def test_correction_humaine_jamais_ecrasee(self):
        a = VeilleAnnonceur.objects.get(page_id='A')
        vd.poser_verdict_humain(a, None, 'hors_sujet', 'non')
        vr.appliquer_regles(self.dec, maintenant=MAINTENANT)
        a.refresh_from_db()
        self.assertEqual(a.classe, 'hors_sujet')
        self.assertEqual(a.verdict_courant.decide_par, 'humain')
        self.assertEqual(a.dropshipper_decide_par, 'humain')
