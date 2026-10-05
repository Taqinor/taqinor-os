"""VEIL17 — Endpoints de la veille : découvertes, annonceurs, verdict humain,
étiquette de mesure, échantillon, export CSV.

Les réponses sont comparées aux contrats ``contract_samples/veille_*.json``
(clés EXACTES). Aucun appel réseau : la tâche n'est jamais réellement envoyée
(``send_task`` simulé) et les pages sont ingérées directement.
"""
import json
import pathlib
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import veille_decouverte as vd
from apps.adsengine.models import (
    VeilleAnnonceur, VeilleDecouverte, VeilleVerdict,
)

User = get_user_model()
BASE = '/api/django/adsengine/veille/'
CONTRATS = pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'


def contrat(nom):
    return json.loads((CONTRATS / nom).read_text(encoding='utf-8'))


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def pub(ad_id, page_id, nom='Boutique', corps='Robe 49 €',
        legende='boutique.fr'):
    return {'id': ad_id, 'page_id': page_id, 'page_name': nom,
            'ad_creative_bodies': [corps],
            'ad_creative_link_captions': [legende],
            'ad_snapshot_url':
                f'https://www.facebook.com/ads/archive/render_ad/?id={ad_id}'
                '&access_token=EAAPIEGE'}


def _interdit(*a, **k):
    raise AssertionError('aucune requête réseau attendue')


class BaseApi(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='YanBow', slug='yb-api')
        self.b = Company.objects.create(nom='Autre', slug='autre-api')
        self.gest = make_user(self.a, 'yb_gest',
                              ['adsengine_view', 'adsengine_manage'])
        self.lecteur = make_user(self.a, 'yb_lect', ['adsengine_view'])
        self.gest_b = make_user(self.b, 'b_gest',
                                ['adsengine_view', 'adsengine_manage'])
        self.reglages = override_settings(
            VEILLE_SOCIETES_AUTORISEES=[self.a.id],
            META_AD_LIBRARY_ENABLED=True,
            META_AD_LIBRARY_ACCESS_TOKEN='EAAJETONAPI',
            META_AD_LIBRARY_FIXTURES_DIR='')
        self.reglages.enable()
        self.addCleanup(self.reglages.disable)

    def decouverte(self, pubs, mots=None):
        dec = vd.creer_decouverte(self.a, self.gest, {
            'mots_cles': mots or [{'texte': 'robe', 'pays': ['FR']}],
            'plafond_appels': 10, 'plafond_pages_par_requete': 5})
        requete = dec.requetes.first()
        vd.ingerer_page(requete, {'pubs': pubs, 'a_suivant': False}, 1)
        return dec


class DecouverteApiTests(BaseApi):
    def test_post_lance_202_company_du_corps_ignoree(self):
        corps = {'company': self.b.id,
                 'mots_cles': [{'texte': 'robe', 'pays': ['FR', 'BE']}],
                 'plafond_appels': 20, 'plafond_pages_par_requete': 4}
        with mock.patch('core.jobs.current_app.send_task') as envoi:
            resp = auth(self.gest).post(BASE + 'decouvertes/', corps,
                                        format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        dec = VeilleDecouverte.objects.get(pk=resp.data['id'])
        self.assertEqual(dec.company_id, self.a.id)
        self.assertIsNotNone(dec.background_job_id)
        self.assertEqual(envoi.call_args.args[0], 'adsengine.veille_etape')
        attendu = contrat('veille_decouverte.json')['exemple']
        self.assertEqual(set(resp.data), set(attendu))
        self.assertEqual(set(resp.data['requetes'][0]),
                         set(attendu['requetes'][0]))
        self.assertEqual(len(resp.data['requetes']), 2)

    def test_post_sans_plafond_400(self):
        resp = auth(self.gest).post(BASE + 'decouvertes/', {
            'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
            'plafond_appels': 20}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(VeilleDecouverte.objects.count(), 0)

    def test_403_sans_adsengine_manage(self):
        resp = auth(self.lecteur).post(BASE + 'decouvertes/', {
            'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
            'plafond_appels': 2, 'plafond_pages_par_requete': 2},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_societe_hors_liste_403_zero_appel(self):
        with mock.patch('httpx.Client.send', side_effect=_interdit), \
                mock.patch('core.jobs.current_app.send_task') as envoi:
            resp = auth(self.gest_b).post(BASE + 'decouvertes/', {
                'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
                'plafond_appels': 2, 'plafond_pages_par_requete': 2},
                format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('autorisée', resp.data['detail'])
        envoi.assert_not_called()
        self.assertEqual(VeilleDecouverte.objects.count(), 0)

    def test_societe_b_404_sur_lancement_de_a(self):
        dec = self.decouverte([pub('1', 'p1')])
        resp = auth(self.gest_b).get(f'{BASE}decouvertes/{dec.pk}/')
        self.assertEqual(resp.status_code, 404)
        resp = auth(self.gest).get(f'{BASE}decouvertes/{dec.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['annonceurs_distincts'], 1)

    def test_annuler_puis_reprendre_refuse(self):
        dec = self.decouverte([pub('1', 'p1')])
        resp = auth(self.gest).post(f'{BASE}decouvertes/{dec.pk}/annuler/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'annule')
        resp = auth(self.gest).post(f'{BASE}decouvertes/{dec.pk}/reprendre/')
        self.assertEqual(resp.status_code, 400)


class AnnonceurApiTests(BaseApi):
    def test_detail_au_format_du_contrat_sans_jeton(self):
        dec = self.decouverte([pub('11', 'p1'), pub('12', 'p1')])
        ann = VeilleAnnonceur.objects.get(page_id='p1')
        resp = auth(self.lecteur).get(f'{BASE}annonceurs/{ann.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = contrat('veille_annonceur.json')['exemple']
        self.assertEqual(set(resp.data), set(attendu))
        self.assertEqual(resp.data['nb_pubs_vues'], 2)
        self.assertEqual(resp.data['lien_bibliotheque'],
                         'https://www.facebook.com/ads/library/?id=11')
        self.assertEqual([c['cle'] for c in resp.data['classes_disponibles']],
                         [c['cle'] for c in attendu['classes_disponibles']])
        self.assertNotIn('access_token', resp.content.decode('utf-8'))
        liste = auth(self.lecteur).get(
            f'{BASE}annonceurs/?decouverte={dec.pk}')
        self.assertEqual(liste.data['count'], 1)

    def test_verdict_humain_contrat_et_historique(self):
        self.decouverte([pub('11', 'p1')])
        ann = VeilleAnnonceur.objects.get(page_id='p1')
        regle = VeilleVerdict.objects.create(
            company=self.a, annonceur=ann, classe='vendeur',
            decide_par='regle', motif_fr='Boutique en ligne.')
        ann.verdict_courant = regle
        ann.classe = 'vendeur'
        ann.save()
        resp = auth(self.gest).post(
            f'{BASE}annonceurs/{ann.pk}/verdict/',
            contrat('veille_verdict.json')['corps'], format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = contrat('veille_verdict.json')['exemple']
        self.assertEqual(set(resp.data), set(attendu))
        self.assertEqual(set(resp.data['verdict']), set(attendu['verdict']))
        self.assertEqual(resp.data['classe'], 'place_de_marche')
        self.assertEqual(resp.data['verdict']['decide_par'], 'humain')
        self.assertEqual(resp.data['dropshipper']['probable'], 'non')
        self.assertEqual(resp.data['historique'][0]['decide_par'], 'regle')
        self.assertEqual(set(resp.data['historique'][0]),
                         set(attendu['historique'][0]))
        # relecture serveur identique
        relu = auth(self.gest).get(f'{BASE}annonceurs/{ann.pk}/')
        self.assertEqual(relu.data, resp.data)

    def test_verdict_sans_classe_400(self):
        self.decouverte([pub('11', 'p1')])
        ann = VeilleAnnonceur.objects.get(page_id='p1')
        resp = auth(self.gest).post(f'{BASE}annonceurs/{ann.pk}/verdict/',
                                    {'dropshipper': 'oui'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_verdict_humain_survit_a_une_nouvelle_decouverte(self):
        self.decouverte([pub('11', 'p1')])
        ann = VeilleAnnonceur.objects.get(page_id='p1')
        auth(self.gest).post(f'{BASE}annonceurs/{ann.pk}/verdict/',
                             {'classe': 'pas_vendeur'}, format='json')
        self.decouverte([pub('99', 'p1')],
                        mots=[{'texte': 'sac', 'pays': ['FR']}])
        ann.refresh_from_db()
        self.assertEqual(ann.classe, 'pas_vendeur')
        self.assertEqual(ann.verdict_courant.decide_par, 'humain')
        self.assertEqual(ann.nb_pubs_vues, 2)

    def test_verdict_societe_hors_liste_403(self):
        self.decouverte([pub('11', 'p1')])
        ann = VeilleAnnonceur.objects.get(page_id='p1')
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[]):
            resp = auth(self.gest).post(
                f'{BASE}annonceurs/{ann.pk}/verdict/',
                {'classe': 'vendeur'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_creation_directe_interdite(self):
        resp = auth(self.gest).post(f'{BASE}annonceurs/',
                                    {'page_id': 'x'}, format='json')
        self.assertEqual(resp.status_code, 405)


class EchantillonEtAveugleTests(BaseApi):
    def setUp(self):
        super().setUp()
        self.dec = self.decouverte(
            [pub(str(i), f'p{i}') for i in range(20)])

    def test_tirage_disjoint_gele_et_contrat(self):
        url = f'{BASE}decouvertes/{self.dec.pk}/echantillon/'
        resp = auth(self.gest).post(
            url, contrat('veille_echantillon.json')['corps'], format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data),
                         set(contrat('veille_echantillon.json')['exemple']))
        self.assertEqual(len(resp.data['etalonnage']), 5)
        self.assertEqual(len(resp.data['test']), 10)
        self.assertFalse(set(resp.data['etalonnage']) & set(resp.data['test']))
        self.assertFalse(resp.data['deja_tire'])
        second = auth(self.gest).post(url, {'taille_etalonnage': 1,
                                            'taille_test': 1}, format='json')
        self.assertTrue(second.data['deja_tire'])
        self.assertEqual(second.data['test'], resp.data['test'])

    def test_tirage_trop_grand_400(self):
        resp = auth(self.gest).post(
            f'{BASE}decouvertes/{self.dec.pk}/echantillon/',
            {'taille_etalonnage': 15, 'taille_test': 10}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_mode_aveugle_aucun_verdict_machine(self):
        tirage = vd.tirer_echantillon(self.dec, 2, 3)
        cible = VeilleAnnonceur.objects.get(pk=tirage['test'][0])
        verdict = VeilleVerdict.objects.create(
            company=self.a, annonceur=cible, classe='vendeur',
            decide_par='ia', motif_fr='MOTIF IA SECRET', modele='haiku')
        cible.verdict_courant = verdict
        cible.classe = 'vendeur'
        cible.save()
        resp = auth(self.gest).get(
            f'{BASE}annonceurs/?jeu=test&sans_etiquette=1')
        self.assertEqual(resp.data['count'], 3)
        for ligne in resp.data['results']:
            self.assertIsNone(ligne['classe'])
            self.assertIsNone(ligne['verdict'])
            self.assertIsNone(ligne['dropshipper'])
            self.assertIsNone(ligne['etiquette_mesure'])
            self.assertEqual(ligne['historique'], [])
        self.assertNotIn('MOTIF IA SECRET', resp.content.decode('utf-8'))

    def test_etiquette_ne_touche_pas_le_verdict_courant(self):
        tirage = vd.tirer_echantillon(self.dec, 1, 2)
        cible = VeilleAnnonceur.objects.get(pk=tirage['test'][0])
        resp = auth(self.gest).post(
            f'{BASE}annonceurs/{cible.pk}/etiquette/',
            {'classe': 'hors_sujet', 'dropshipper': 'non'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['classe'])          # aveugle
        cible.refresh_from_db()
        self.assertIsNone(cible.verdict_courant)
        self.assertEqual(cible.classe, 'incertain')
        etiquette = cible.verdicts.get(est_etiquette_mesure=True)
        self.assertEqual((etiquette.jeu, etiquette.decide_par,
                          etiquette.auteur_id), ('test', 'humain',
                                                 self.gest.id))
        restants = auth(self.gest).get(
            f'{BASE}annonceurs/?jeu=test&sans_etiquette=1')
        self.assertEqual(restants.data['count'], 1)

    def test_etiquette_hors_echantillon_400(self):
        hors = VeilleAnnonceur.objects.filter(jeu__isnull=True).first()
        resp = auth(self.gest).post(
            f'{BASE}annonceurs/{hors.pk}/etiquette/',
            {'classe': 'vendeur', 'dropshipper': 'oui'}, format='json')
        self.assertEqual(resp.status_code, 400)


class ExportCsvTests(BaseApi):
    def test_csv_memes_lignes_que_la_liste_filtree(self):
        self.decouverte([pub('1', 'p1'), pub('2', 'p2'), pub('3', 'p3')])
        VeilleAnnonceur.objects.filter(page_id='p2').update(classe='vendeur')
        liste = auth(self.gest).get(f'{BASE}annonceurs/?classe=vendeur')
        resp = auth(self.gest).get(
            f'{BASE}annonceurs/export-csv/?classe=vendeur')
        self.assertEqual(resp.status_code, 200)
        texte = resp.content.decode('utf-8')
        self.assertTrue(texte.startswith('﻿'))
        lignes = [x for x in texte.lstrip('﻿').splitlines() if x]
        self.assertEqual(len(lignes) - 1, liste.data['count'])
        self.assertIn(';', lignes[0])
        self.assertNotIn('access_token', texte)

    def test_csv_exige_gestionnaire(self):
        resp = auth(self.lecteur).get(f'{BASE}annonceurs/export-csv/')
        self.assertEqual(resp.status_code, 403)
