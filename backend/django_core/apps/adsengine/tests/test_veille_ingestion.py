"""VEIL15 — Ingestion idempotente d'une page de résultats + domaine affiché."""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import veille_decouverte as vd
from apps.adsengine.models import (
    VeilleAnnonceur, VeilleDecouverte, VeillePubVue, VeilleRequete,
)

# 20 cas étiquetés à la main : (légende, domaine attendu). Les 8 derniers
# n'ont AUCUN domaine : 0 faux domaine attendu.
CAS_LEGENDES = [
    ('maison-lilas.fr', 'maison-lilas.fr'),
    ('WWW.SHOP.COM', 'shop.com'),
    ('fr.shein.com', 'shein.com'),
    ('shop.example.co.uk', 'example.co.uk'),
    ('https://www.boutique.fr/robes', 'boutique.fr'),
    ('instagram.com/maisonlilas', 'instagram.com'),
    ('Visit us at shop.maison.fr.', 'maison.fr'),
    ('contact@lilas.fr', 'lilas.fr'),
    ('zalando.de', 'zalando.de'),
    ('mode-paris.com.fr', 'mode-paris.com.fr'),
    ('Achetez sur LILAS.STORE !', 'lilas.store'),
    ('marque.co', 'marque.co'),
    ('Shop Now', ''),
    ('Livraison gratuite dès 60€', ''),
    ('3.5 étoiles', ''),
    ('Boutique.Mode', ''),
    ('Nouveautés.Shop', ''),
    ('Sizes S.M.L.XL', ''),
    ('M.A.C cosmetics', ''),
    ('robe.en.ligne', ''),
]


class LegendeVersDomaineTests(SimpleTestCase):
    def test_cas_etiquetes(self):
        self.assertGreaterEqual(len(CAS_LEGENDES), 15)
        self.assertGreaterEqual(
            sum(1 for _l, d in CAS_LEGENDES if not d), 5)
        for legende, attendu in CAS_LEGENDES:
            with self.subTest(legende=legende):
                self.assertEqual(vd.legende_vers_domaine(legende), attendu)

    def test_vide(self):
        self.assertEqual(vd.legende_vers_domaine(None), '')
        self.assertEqual(vd.legende_vers_domaine(''), '')


def pub(ad_id, page_id='p1', nom='Maison Lilas', corps='Robe légère 49 €',
        legende='maison-lilas.fr'):
    return {
        'id': ad_id, 'page_id': page_id, 'page_name': nom,
        'ad_creative_bodies': [corps],
        'ad_creative_link_captions': [legende],
        'ad_creative_link_titles': ['Robes été'],
        'languages': ['fr'], 'publisher_platforms': ['facebook'],
        'ad_delivery_start_time': '2026-09-20',
        'ad_snapshot_url': 'https://www.facebook.com/ads/archive/render_ad/?id=1',
    }


def reponse(pubs, suivant=True, apres='C2'):
    return {'pubs': pubs, 'a_suivant': suivant,
            'after_suivant': apres if suivant else None,
            'usage': {'call_count': 3, 'total_cputime': 1, 'total_time': 1}}


class IngestionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='YB', slug='yb-ingest')
        self.dec = VeilleDecouverte.objects.create(
            company=self.company, plafond_appels=10,
            plafond_pages_par_requete=5,
            mots_cles=[{'texte': 'robe', 'pays': ['FR', 'BE']}])
        self.req_fr = VeilleRequete.objects.create(
            company=self.company, decouverte=self.dec, mot_cle='robe',
            pays='FR')
        self.req_be = VeilleRequete.objects.create(
            company=self.company, decouverte=self.dec, mot_cle='robe',
            pays='BE', ordre=1)

    def _etat(self):
        self.req_fr.refresh_from_db()
        self.dec.refresh_from_db()
        return (self.req_fr.pages_lues, self.req_fr.pubs,
                self.req_fr.nouveaux_annonceurs, self.req_fr.curseur_after,
                self.dec.pages_lues, self.dec.pubs_recues,
                VeillePubVue.objects.count(),
                list(VeilleAnnonceur.objects.values_list(
                    'page_id', 'nb_pubs_vues')))

    def test_rejouer_la_meme_page_ne_change_rien(self):
        rep = reponse([pub('a1'), pub('a2'), pub('b1', page_id='p2')])
        premier = vd.ingerer_page(self.req_fr, rep, 1)
        self.assertFalse(premier['deja_ingeree'])
        self.assertEqual(premier['nouveaux_annonceurs'], 2)
        etat = self._etat()
        second = vd.ingerer_page(self.req_fr, rep, 1)
        self.assertTrue(second['deja_ingeree'])
        self.assertEqual(self._etat(), etat)
        self.assertEqual(etat[0], 1)          # pages lues
        self.assertEqual(etat[1], 3)          # pubs reçues
        self.assertEqual(etat[3], 'C2')       # curseur gardé (lancement)

    def test_pub_vue_par_deux_requetes_compte_une_fois(self):
        vd.ingerer_page(self.req_fr, reponse([pub('a1')]), 1)
        res = vd.ingerer_page(self.req_be, reponse([pub('a1')]), 1)
        annonceur = VeilleAnnonceur.objects.get(page_id='p1')
        self.assertEqual(annonceur.nb_pubs_vues, 1)
        self.assertEqual(annonceur.pays_vus, ['BE', 'FR'])
        self.assertEqual(VeillePubVue.objects.count(), 2)
        # déjà vu dans la découverte : pas un nouvel annonceur pour BE
        self.assertEqual(res['nouveaux_annonceurs'], 0)

    def test_agregats_extraits_et_domaines(self):
        pubs = [pub(f'a{i}', corps=f'Texte {i} ' + 'x' * 300)
                for i in range(7)]
        pubs.append(pub('z', legende='Shop Now', corps='Texte 0 ' + 'x' * 300))
        vd.ingerer_page(self.req_fr, reponse(pubs, suivant=False), 1)
        annonceur = VeilleAnnonceur.objects.get(page_id='p1')
        self.assertEqual(annonceur.nb_pubs_vues, 8)
        self.assertLessEqual(len(annonceur.extraits), 5)
        for extrait in annonceur.extraits:
            self.assertLessEqual(len(extrait['texte']), 200)
        self.assertEqual(annonceur.domaines,
                         [{'domaine': 'maison-lilas.fr', 'nb': 7}])
        self.assertEqual(annonceur.page_name, 'Maison Lilas')
        pv = VeillePubVue.objects.filter(ad_archive_id='a1').get()
        self.assertLessEqual(len(pv.extrait), 500)
        # fin de pagination : curseur EFFACÉ
        self.req_fr.refresh_from_db()
        self.assertEqual(self.req_fr.curseur_after, '')

    def test_erreur_au_milieu_rien_d_ecrit(self):
        rep = reponse([pub('a1'), pub('b1', page_id='p2')])
        with mock.patch.object(vd, 'recalculer_agregats',
                               side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                vd.ingerer_page(self.req_fr, rep, 1)
        self.req_fr.refresh_from_db()
        self.assertEqual(self.req_fr.curseur_after, '')
        self.assertEqual(self.req_fr.pages_lues, 0)
        self.assertEqual(VeillePubVue.objects.count(), 0)
        self.assertEqual(VeilleAnnonceur.objects.count(), 0)

    def test_aucune_url_de_snapshot_stockee(self):
        vd.ingerer_page(self.req_fr, reponse([pub('a1')]), 1)
        for pv in VeillePubVue.objects.all():
            for champ in ('extrait', 'legende', 'domaine'):
                self.assertNotIn('render_ad', getattr(pv, champ))
