"""VEIL22 — Tri IA dans l'ERP, ÉTEINT sans clé (httpx, aucun nouveau paquet).

Transport simulé : aucune requête ne sort vers l'API Anthropic.
"""
import json
from unittest import mock

import httpx
from django.test import TestCase, override_settings

from authentication.models import Company

from apps.adsengine import veille_decouverte as vd
from apps.adsengine import veille_ia
from apps.adsengine.models import VeilleAnnonceur

CLE = 'sk-ant-veille-test-0000'


def reponse_modele(objet=None, texte=None, stop='end_turn', entree=200,
                   sortie=40, statut=200):
    contenu = texte if texte is not None else json.dumps(objet)
    return httpx.Response(statut, json={
        'content': [{'type': 'text', 'text': contenu}],
        'stop_reason': stop,
        'usage': {'input_tokens': entree, 'output_tokens': sortie}})


class Transport:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.requetes = []

    def __call__(self, request):
        assert request.url.host == 'api.anthropic.com'
        self.requetes.append(request)
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def _interdit(*a, **k):
    raise AssertionError('aucun appel attendu')


@override_settings(VEILLE_SOCIETES_AUTORISEES=[], VEILLE_IA_CLE_API=CLE,
                   VEILLE_IA_MODELE_TRI='modele-tri',
                   VEILLE_IA_MODELE_AMBIGU='', VEILLE_IA_SEUIL_AMBIGU=0.7)
class VeilleIaTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='YB', slug='yb-ia')
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            dec = vd.creer_decouverte(self.company, None, {
                'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
                'plafond_appels': 5, 'plafond_pages_par_requete': 5})
        vd.ingerer_page(dec.requetes.get(), {'pubs': [{
            'id': '1', 'page_id': 'A', 'page_name': 'Maison Lilas',
            'ad_creative_bodies': ['Robes légères à -60 %'],
            'ad_creative_link_captions': ['maison-lilas.fr'],
            'ad_snapshot_url': 'https://www.facebook.com/ads/archive/'
                               'render_ad/?id=1&access_token=EAAPIEGE'}],
            'a_suivant': False}, 1)
        self.dec = dec
        self.ann = VeilleAnnonceur.objects.get(page_id='A')

    def test_sans_cle_zero_appel_message_fr(self):
        for reglages in ({'VEILLE_IA_CLE_API': ''},
                         {'VEILLE_IA_MODELE_TRI': ''}):
            with self.subTest(**reglages), override_settings(**reglages), \
                    mock.patch('httpx.Client.send', side_effect=_interdit):
                res = veille_ia.trier_annonceur(self.ann)
                self.assertEqual(res['statut'], 'non_configure')
                self.assertEqual(res['message_fr'],
                                 veille_ia.MESSAGE_NON_CONFIGURE)
                self.assertIn('Tri IA non configuré', res['message_fr'])
                self.assertFalse(veille_ia.est_configure())
        self.ann.refresh_from_db()
        self.assertIsNone(self.ann.verdict_courant)

    def test_liste_blanche_des_champs_envoyes(self):
        t = Transport([reponse_modele({'classe': 'vendeur', 'confiance': 0.9,
                                       'dropshipper': 'non', 'indices': []})])
        veille_ia.trier_annonceur(self.ann, http_client=t.client())
        self.assertEqual(len(t.requetes), 1)
        requete = t.requetes[0]
        self.assertEqual(requete.headers['x-api-key'], CLE)
        corps = json.loads(requete.content)
        self.assertEqual(corps['model'], 'modele-tri')
        self.assertEqual(corps['system'], vd.lire_consigne())
        envoye = json.loads(corps['messages'][0]['content'])
        self.assertEqual(tuple(envoye), vd.CHAMPS_FICHE)
        brut = requete.content.decode('utf-8')
        self.assertNotIn('access_token', brut)
        self.assertNotIn('render_ad', brut)
        self.ann.refresh_from_db()
        v = self.ann.verdict_courant
        self.assertEqual((v.decide_par, v.classe, v.modele, v.jetons_entree,
                          v.jetons_sortie), ('ia', 'vendeur', 'modele-tri',
                                             200, 40))

    def test_reponse_invalide_refus_delai_donnent_incertain(self):
        cas = [reponse_modele(texte='je ne sais pas'),
               reponse_modele({'classe': 'vendeur'}, stop='refusal'),
               httpx.ReadTimeout('trop long'),
               reponse_modele({'classe': 'vendeur'}, statut=529)]
        for reponse in cas:
            with self.subTest(reponse=repr(reponse)):
                t = Transport([reponse])
                res = veille_ia.trier_annonceur(self.ann,
                                                http_client=t.client())
                self.assertEqual(res['statut'], 'importe')
                self.assertEqual(res['ligne']['classe'], 'incertain')
                self.ann.refresh_from_db()
                self.assertEqual(self.ann.classe, 'incertain')
                self.assertEqual(self.ann.verdict_courant.decide_par, 'ia')

    def test_motif_ne_cite_que_la_fiche(self):
        t = Transport([reponse_modele({
            'classe': 'vendeur', 'confiance': 0.95, 'dropshipper': 'oui',
            'indices': [
                {'champ': 'textes', 'valeur': '-60 %'},
                {'champ': 'abonnes', 'valeur': '120 000'},
                {'champ': 'domaines', 'valeur': 'site-invente.com'}],
            'motif_fr': 'Le site web montre 120 000 abonnés'})])
        res = veille_ia.trier_annonceur(self.ann, http_client=t.client())
        self.assertEqual(res['ligne']['indices'],
                         [{'champ': 'textes', 'valeur': '-60 %'}])
        motif = self.ann.verdicts.get(decide_par='ia').motif_fr
        self.assertNotIn('abonnés', motif)
        self.assertNotIn('120 000', motif)
        self.assertIn('textes', motif)

    def test_second_modele_sur_cas_ambigu_jetons_cumules(self):
        t = Transport([
            reponse_modele({'classe': 'vendeur', 'confiance': 0.4,
                            'dropshipper': 'non'}, entree=100, sortie=10),
            reponse_modele({'classe': 'hors_sujet', 'confiance': 0.9,
                            'dropshipper': 'non'}, entree=300, sortie=30)])
        with override_settings(VEILLE_IA_MODELE_AMBIGU='modele-ambigu'):
            veille_ia.trier_annonceur(self.ann, http_client=t.client())
        self.assertEqual(len(t.requetes), 2)
        self.assertEqual(json.loads(t.requetes[1].content)['model'],
                         'modele-ambigu')
        self.ann.refresh_from_db()
        v = self.ann.verdict_courant
        self.assertEqual((v.classe, v.modele, v.jetons_entree,
                          v.jetons_sortie),
                         ('hors_sujet', 'modele-ambigu', 400, 40))

    def test_humain_jamais_ecrase(self):
        vd.poser_verdict_humain(self.ann, None, 'pas_vendeur', 'non')
        t = Transport([reponse_modele({'classe': 'vendeur',
                                       'confiance': 0.99})])
        res = veille_ia.trier_annonceur(self.ann, http_client=t.client())
        self.assertEqual(res['statut'], 'ignore')
        self.ann.refresh_from_db()
        self.assertEqual(self.ann.classe, 'pas_vendeur')
