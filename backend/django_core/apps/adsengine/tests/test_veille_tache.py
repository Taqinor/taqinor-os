"""VEIL16 — Lancement à la demande : une tâche = UN appel, garde de quota,
reprise au même curseur, plafonds obligatoires, aucune entrée au beat.

Le transport HTTP est simulé (``httpx.MockTransport``) : aucune requête ne sort.
"""
import datetime
import json
from unittest import mock

import httpx
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from authentication.models import Company

from apps.adsengine import veille_acces
from apps.adsengine import veille_decouverte as vd
from apps.adsengine.api_version import GRAPH_VERSION
from apps.adsengine.models import VeilleDecouverte, VeilleRequete

User = get_user_model()
JETON = 'EAAJETONTACHE0000'


class Transport:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.requetes = []

    def __call__(self, request):
        assert request.url.host == 'graph.facebook.com'
        assert request.url.path == f'/{GRAPH_VERSION}/ads_archive'
        self.requetes.append(request)
        if not self.reponses:
            raise AssertionError('appel en trop')
        return self.reponses.pop(0)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def page(ids, suivant=True, apres='C', page_id='p1', usage=None):
    corps = {'data': [{'id': i, 'page_id': page_id, 'page_name': 'B'}
                      for i in ids],
             'paging': {'cursors': {'after': apres}}}
    if suivant:
        corps['paging']['next'] = 'https://graph.facebook.com/x'
    entetes = {'x-app-usage': json.dumps(usage)} if usage else {}
    return httpx.Response(200, json=corps, headers=entetes)


def quota(code=613):
    return httpx.Response(400, json={'error': {'code': code, 'message': 'q'}})


class BaseTache(TestCase):
    def setUp(self):
        cache.delete(veille_acces.CLE_CACHE_VERIFICATION)
        self.company = Company.objects.create(nom='YanBow', slug='yb-tache')
        self.user = User.objects.create_user(
            username='yb_tache', password='x', company=self.company)
        self.reglages = override_settings(
            META_AD_LIBRARY_ENABLED=True, META_AD_LIBRARY_ACCESS_TOKEN=JETON,
            META_AD_LIBRARY_FIXTURES_DIR='',
            VEILLE_SOCIETES_AUTORISEES=[self.company.id],
            VEILLE_PAUSE_USAGE_PCT=75)
        self.reglages.enable()
        self.addCleanup(self.reglages.disable)
        self.now = timezone.make_aware(datetime.datetime(2026, 10, 5, 9, 0))

    def creer(self, **kw):
        donnees = {'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
                   'plafond_appels': 50, 'plafond_pages_par_requete': 10}
        donnees.update(kw)
        return vd.creer_decouverte(self.company, self.user, donnees)

    def etape(self, dec, transport, now=None, etape=None):
        dec.refresh_from_db()
        return vd.executer_etape(
            dec.pk, etape=dec.numero_etape if etape is None else etape,
            http_client=transport.client(), now=now or self.now)


class QuotaEtRepriseTests(BaseTache):
    def test_613_pause_sans_appel_avant_reprise_puis_meme_curseur(self):
        dec = self.creer()
        t = Transport([page(['a1'], apres='CUR2'), quota(613),
                       page(['a2'], suivant=False)])
        self.assertEqual(self.etape(dec, t)['action'], 'continuer')
        res = self.etape(dec, t)
        self.assertEqual(res['action'], 'attendre')
        self.assertEqual(res['countdown'], 300)
        self.assertEqual(len(t.requetes), 2)
        dec.refresh_from_db()
        self.assertEqual(dec.statut, 'en_pause_quota')
        self.assertEqual(dec.reprise_a,
                         self.now + datetime.timedelta(seconds=300))
        self.assertEqual(dec.erreurs[-1]['code'], 613)
        # Avant reprise_a : AUCUN appel.
        res = self.etape(dec, t, now=self.now + datetime.timedelta(
            seconds=100))
        self.assertEqual(res['action'], 'attendre')
        self.assertEqual(len(t.requetes), 2)
        # Après reprise_a : reprise au MÊME curseur.
        res = self.etape(dec, t, now=self.now + datetime.timedelta(
            seconds=301))
        self.assertEqual(len(t.requetes), 3)
        self.assertEqual(t.requetes[2].url.params['after'], 'CUR2')
        self.assertEqual(res['action'], 'fin')
        dec.refresh_from_db()
        self.assertEqual(dec.statut, 'termine')
        requete = dec.requetes.get()
        self.assertEqual(requete.statut, 'terminee')
        self.assertEqual(requete.curseur_after, '')   # curseur effacé

    def test_613_une_seule_requete_http(self):
        dec = self.creer()
        t = Transport([quota(613)])
        self.etape(dec, t)
        self.assertEqual(len(t.requetes), 1)

    def test_paliers_progressifs_toujours_sous_une_heure(self):
        dec = self.creer()
        t = Transport([quota(4), quota(17), quota(32), quota(613), quota(4)])
        attendus = [300, 600, 1200, 1800, 1800]
        maintenant = self.now
        for attendu in attendus:
            res = self.etape(dec, t, now=maintenant)
            self.assertEqual(res['countdown'], attendu)
            self.assertLess(res['countdown'], 3600)
            maintenant = maintenant + datetime.timedelta(seconds=attendu + 1)
        self.assertEqual(len(t.requetes), 5)

    def test_usage_au_dessus_du_seuil_pause_preventive(self):
        dec = self.creer()
        t = Transport([page(['a1'], usage={'call_count': 80,
                                           'total_cputime': 10,
                                           'total_time': 10})])
        res = self.etape(dec, t)
        self.assertEqual(res['action'], 'attendre')
        dec.refresh_from_db()
        self.assertEqual(dec.statut, 'en_pause_quota')
        self.assertEqual(dec.dernier_usage_app['call_count'], 80)


class PlafondsEtIdempotenceTests(BaseTache):
    def test_plafond_pages_3_sur_10_disponibles(self):
        dec = self.creer(plafond_pages_par_requete=3)
        t = Transport([page([f'a{i}'], apres=f'C{i}') for i in range(10)])
        for _ in range(6):
            if self.etape(dec, t)['action'] == 'fin':
                break
        self.assertEqual(len(t.requetes), 3)
        dec.refresh_from_db()
        self.assertEqual(dec.statut, 'termine')
        self.assertEqual(dec.requetes.get().statut, 'plafond')

    def test_plafond_appels_3(self):
        dec = self.creer(plafond_appels=3)
        t = Transport([page([f'a{i}'], apres=f'C{i}') for i in range(10)])
        for _ in range(6):
            if self.etape(dec, t)['action'] == 'fin':
                break
        self.assertEqual(len(t.requetes), 3)
        dec.refresh_from_db()
        self.assertEqual(dec.appels_consommes, 3)

    def test_etape_relivree_ne_change_rien(self):
        dec = self.creer()
        t = Transport([page(['a1'], apres='C2'), page(['a2'])])
        self.etape(dec, t, etape=0)
        dec.refresh_from_db()
        avant = (dec.appels_consommes, dec.pubs_recues, dec.pages_lues)
        res = vd.executer_etape(dec.pk, etape=0, http_client=t.client(),
                                now=self.now)
        self.assertEqual(res['action'], 'ignore')
        dec.refresh_from_db()
        self.assertEqual((dec.appels_consommes, dec.pubs_recues,
                          dec.pages_lues), avant)
        self.assertEqual(len(t.requetes), 1)

    def test_une_etape_un_appel(self):
        dec = self.creer(mots_cles=[{'texte': 'robe', 'pays': ['FR', 'BE']}])
        t = Transport([page(['a1']), page(['b1']), page(['c1'])])
        for attendu in (1, 2, 3):
            self.etape(dec, t)
            self.assertEqual(len(t.requetes), attendu)

    def test_vide_avec_next_puis_pleine(self):
        dec = self.creer()
        t = Transport([page([], suivant=True, apres='C2'),
                       page(['a1', 'a2'], suivant=False)])
        self.etape(dec, t)
        res = self.etape(dec, t)
        self.assertEqual(len(t.requetes), 2)
        self.assertEqual(res['action'], 'fin')
        requete = dec.requetes.get()
        self.assertEqual(requete.statut, 'terminee')
        self.assertEqual(requete.pages_lues, 2)

    def test_vide_sans_next_des_la_premiere_page(self):
        dec = self.creer()
        t = Transport([page([], suivant=False)])
        self.etape(dec, t)
        self.assertEqual(dec.requetes.get().statut, 'vide')

    def test_annuler_avant_l_appel(self):
        dec = self.creer()
        vd.annuler(dec)
        t = Transport([])
        res = self.etape(dec, t)
        self.assertEqual(res['action'], 'fin')
        self.assertEqual(t.requetes, [])


class ErreursTests(BaseTache):
    def test_190_echec_acces_invalide(self):
        dec = self.creer()
        t = Transport([quota(190)])
        res = self.etape(dec, t)
        self.assertEqual(res['action'], 'fin')
        dec.refresh_from_db()
        self.assertEqual(dec.statut, 'echec')
        self.assertIn('invalide', dec.erreurs[-1]['message_fr'])

    def test_autre_4xx_requete_en_erreur_le_lancement_continue(self):
        dec = self.creer(mots_cles=[{'texte': 'robe', 'pays': ['FR', 'BE']}])
        t = Transport([quota(100), page(['b1'], suivant=False)])
        self.assertEqual(self.etape(dec, t)['action'], 'continuer')
        self.assertEqual(self.etape(dec, t)['action'], 'fin')
        statuts = dict(dec.requetes.values_list('pays', 'statut'))
        self.assertEqual(statuts, {'FR': 'erreur', 'BE': 'terminee'})

    def test_jeton_absent_echec_zero_appel(self):
        dec = self.creer()
        t = Transport([])
        with override_settings(META_AD_LIBRARY_ACCESS_TOKEN=''):
            res = self.etape(dec, t)
        self.assertEqual(res['action'], 'fin')
        self.assertEqual(t.requetes, [])
        dec.refresh_from_db()
        self.assertEqual(dec.statut, 'echec')
        self.assertIn('non configuré', dec.erreurs[-1]['message_fr'])


class CreationTests(BaseTache):
    def test_plafonds_obligatoires(self):
        for manquant in ('plafond_appels', 'plafond_pages_par_requete'):
            donnees = {'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
                       'plafond_appels': 5, 'plafond_pages_par_requete': 5}
            donnees.pop(manquant)
            with self.subTest(manquant=manquant):
                with self.assertRaises(vd.LancementRefuse) as ctx:
                    vd.creer_decouverte(self.company, self.user, donnees)
                self.assertEqual(ctx.exception.statut_http, 400)
        self.assertEqual(VeilleDecouverte.objects.count(), 0)

    def test_societe_hors_liste_403(self):
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[]):
            with self.assertRaises(vd.LancementRefuse) as ctx:
                self.creer()
        self.assertEqual(ctx.exception.statut_http, 403)

    def test_mot_cle_trop_long_et_pays_refuses(self):
        for mots in ([{'texte': 'x' * 101, 'pays': ['FR']}],
                     [{'texte': 'robe', 'pays': ['MA']}],
                     [{'texte': 'robe', 'pays': ['UK']}],
                     [{'texte': 'robe', 'pays': []}]):
            with self.subTest(mots=mots):
                with self.assertRaises(vd.LancementRefuse):
                    self.creer(mots_cles=mots)

    def test_requetes_creees_par_couple(self):
        dec = self.creer(mots_cles=[{'texte': 'robe', 'pays': ['fr', 'BE']},
                                    {'texte': 'sac', 'pays': ['FR']}])
        self.assertEqual(
            list(VeilleRequete.objects.filter(decouverte=dec).values_list(
                'mot_cle', 'pays')),
            [('robe', 'FR'), ('robe', 'BE'), ('sac', 'FR')])

    def test_lancer_par_core_jobs(self):
        dec = self.creer()
        with mock.patch('core.jobs.current_app.send_task') as envoi:
            job = vd.lancer(dec, self.user)
        dec.refresh_from_db()
        self.assertEqual(dec.background_job_id, job.pk)
        nom, = envoi.call_args.args
        self.assertEqual(nom, 'adsengine.veille_etape')
        self.assertEqual(envoi.call_args.kwargs['kwargs']['decouverte_id'],
                         dec.pk)


class AucunBeatTests(SimpleTestCase):
    def test_aucune_entree_veille_au_beat(self):
        from erp_agentique.celery import app
        taches = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertFalse([t for t in taches
                          if t.startswith('adsengine.veille')])

    def test_tache_enregistree_et_routee(self):
        from django.conf import settings
        from erp_agentique.celery import app
        import apps.adsengine.tasks  # noqa: F401 — enregistre la tâche
        self.assertIn('adsengine.veille_etape', app.tasks)
        self.assertIn('adsengine.veille_etape', settings.CELERY_TASK_ROUTES)


def _interdit(*a, **k):
    raise AssertionError('connexion réseau ouverte en mode rejeu')


class RejeuDecouverteTests(BaseTache):
    """AACQ36 — mode rejeu (fixtures posées, réseau coupé) atteignable depuis
    ``executer_etape`` : seule la société autorisée est exigée, 0 socket."""

    def setUp(self):
        super().setUp()
        import pathlib
        import tempfile
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        (pathlib.Path(self.dossier.name) / 'robe_FR_1.json').write_text(
            json.dumps({'data': [
                {'id': 'r1', 'page_id': 'p1', 'page_name': 'Boutique A'},
                {'id': 'r2', 'page_id': 'p2', 'page_name': 'Boutique B'}],
                'paging': {}}), encoding='utf-8')

    def _rejeu(self, **extra):
        return override_settings(
            META_AD_LIBRARY_FIXTURES_DIR=self.dossier.name,
            META_AD_LIBRARY_ENABLED=False, META_AD_LIBRARY_ACCESS_TOKEN='',
            **extra)

    def _derouler(self, dec):
        import socket
        with mock.patch.object(socket.socket, 'connect', _interdit), \
                mock.patch('httpx.Client.send', side_effect=_interdit):
            for _ in range(10):
                dec.refresh_from_db()
                res = vd.executer_etape(dec.pk, etape=dec.numero_etape,
                                        now=self.now)
                if res['action'] == 'fin':
                    break
        dec.refresh_from_db()
        return dec

    def test_rejeu_sans_jeton_ingere_les_fixtures_sans_reseau(self):
        from apps.adsengine.models import VeillePubVue
        with self._rejeu():
            dec = self._derouler(self.creer())
        self.assertEqual(dec.statut, 'termine')
        self.assertEqual(
            set(VeillePubVue.objects.filter(company=self.company)
                .values_list('ad_archive_id', flat=True)), {'r1', 'r2'})
        # Persistance : relire la découverte → même statut.
        self.assertEqual(VeilleDecouverte.objects.get(pk=dec.pk).statut,
                         'termine')

    def test_rejeu_societe_non_autorisee_refusee(self):
        dec = self.creer()
        with self._rejeu(VEILLE_SOCIETES_AUTORISEES=[]):
            dec = self._derouler(dec)
        self.assertEqual(dec.statut, 'echec')
        self.assertEqual(
            dec.erreurs[-1]['message_fr'],
            veille_acces.MESSAGES_FR[veille_acces.NON_AUTORISE])

    def test_matrice_acces_sans_rejeu_inchangee(self):
        attendus = {('', False): veille_acces.NON_CONFIGURE,
                    ('', True): veille_acces.NON_CONFIGURE,
                    (JETON, False): veille_acces.DESACTIVE,
                    (JETON, True): veille_acces.PRET}
        for (jeton, actif), etat_attendu in attendus.items():
            with self.subTest(jeton=bool(jeton), actif=actif), \
                    override_settings(META_AD_LIBRARY_FIXTURES_DIR='',
                                      META_AD_LIBRARY_ENABLED=actif,
                                      META_AD_LIBRARY_ACCESS_TOKEN=jeton):
                self.assertEqual(veille_acces.etat(self.company)['etat'],
                                 etat_attendu)
                if etat_attendu == veille_acces.PRET:
                    self.assertIsNotNone(
                        veille_acces.exiger_utilisable_ou_rejeu(self.company))
                else:
                    with self.assertRaises(veille_acces.AccesRefuse) as ctx:
                        veille_acces.exiger_utilisable_ou_rejeu(self.company)
                    self.assertEqual(ctx.exception.etat, etat_attendu)
        # Fixtures posées MAIS interrupteur vrai : pas de rejeu, jeton exigé.
        with override_settings(META_AD_LIBRARY_FIXTURES_DIR=self.dossier.name,
                               META_AD_LIBRARY_ENABLED=True,
                               META_AD_LIBRARY_ACCESS_TOKEN=''):
            with self.assertRaises(veille_acces.AccesRefuse) as ctx:
                veille_acces.exiger_utilisable_ou_rejeu(self.company)
            self.assertEqual(ctx.exception.etat, veille_acces.NON_CONFIGURE)
        # Rejeu actif : ``etat()`` inchangé (aucun état nouveau).
        with self._rejeu():
            self.assertEqual(veille_acces.etat(self.company)['etat'],
                             veille_acces.NON_CONFIGURE)
