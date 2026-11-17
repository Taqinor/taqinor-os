"""Agendas externes (reference/regles.md « Les agendas externes » ; donnees.md invariant 33 ; api.md §3.4).

Sans base : la garde de lecture (`agenda_externe.telecharger`) contre http, adresses privées,
redirection vers une adresse privée, corps trop grand, délai — le réseau est remplacé par une fausse
connexion, la résolution DNS par une table. Avec base (CI) : les 5 routes, le cache, l'URL jamais
rendue ni journalisée.
"""
import datetime
import io
import json
import socket
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.publicapi.validators import UnsafeWebhookURL
from apps.taches import agenda_externe as lecteur
from apps.taches.choix import EtatAgendaExterne as Etat
from apps.taches.tests import fabriques

PUBLIQUE = '93.184.216.34'
ICS = ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:a1\r\nDTSTART:20261117T100000Z\r\n'
       'DTEND:20261117T110000Z\r\nSUMMARY:Réunion banque\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n')


def exemple(nom):
    chemin = Path(__file__).resolve().parents[1] / 'contract_samples' / f'{nom}.json'
    return json.loads(chemin.read_text(encoding='utf-8'))['exemple']


class FausseReponse:
    def __init__(self, status=200, corps=b'', entetes=None, lever=None):
        self.status, self._corps, self._entetes, self._lever = status, io.BytesIO(corps), entetes or {}, lever

    def getheader(self, nom):
        return self._entetes.get(nom)

    def read(self, n):
        if self._lever is not None:
            raise self._lever
        return self._corps.read(n)


class Reseau:
    """Faux réseau : `dns` = {hôte: [ip]} ; `reponses` = file des réponses ; `ouvertes` garde
    chaque (hôte, ip) vers lequel une connexion a été ouverte."""

    def __init__(self, dns, reponses):
        self.dns, self.reponses, self.ouvertes = dns, list(reponses), []

    def getaddrinfo(self, hote, port, proto=0):
        if hote not in self.dns:
            raise socket.gaierror('inconnu')
        return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', (ip, port)) for ip in self.dns[hote]]

    def ouvrir(self, hote, ip, port, timeout):
        self.ouvertes.append((hote, ip))
        reseau = self

        class Connexion:
            sock = None

            def request(self, methode, chemin, headers=None):
                self.chemin = chemin

            def getresponse(self):
                return reseau.reponses.pop(0)

            def close(self):
                pass
        return Connexion()

    def __enter__(self):
        self._patchs = [mock.patch.object(lecteur.socket, 'getaddrinfo', self.getaddrinfo),
                        mock.patch.object(lecteur, '_ouvrir', self.ouvrir)]
        for p in self._patchs:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patchs:
            p.stop()


class GardeDeLectureTests(SimpleTestCase):
    """Invariant 33, étape par étape : chaque refus dit son état, jamais une exception à l'écran."""

    def etat(self, url, reseau, **options):
        with reseau, self.assertRaises(lecteur.Echec) as refus:
            lecteur.telecharger(url, **options)
        return refus.exception.etat

    def test_http_refuse_sans_connexion(self):
        reseau = Reseau({}, [])
        self.assertEqual(self.etat('http://agenda.example/a.ics', reseau), Etat.PAS_HTTPS)
        self.assertEqual(reseau.ouvertes, [])

    def test_boucle_locale(self):
        self.assertEqual(self.etat('https://127.0.0.1/a.ics', Reseau({}, [])), Etat.ADRESSE_PRIVEE)

    def test_hote_qui_resout_en_10_0_0_0_8(self):
        reseau = Reseau({'agenda.example': ['10.2.3.4']}, [])
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau), Etat.ADRESSE_PRIVEE)
        self.assertEqual(reseau.ouvertes, [])

    def test_toutes_les_adresses_doivent_etre_publiques(self):
        reseau = Reseau({'agenda.example': [PUBLIQUE, '192.168.1.2']}, [])
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau), Etat.ADRESSE_PRIVEE)

    def test_hote_introuvable(self):
        self.assertEqual(self.etat('https://inconnu.example/a.ics', Reseau({}, [])), Etat.INJOIGNABLE)

    def test_redirection_vers_une_adresse_privee(self):
        reseau = Reseau({'agenda.example': [PUBLIQUE], 'interne.example': ['10.0.0.1']},
                        [FausseReponse(302, entetes={'Location': 'https://interne.example/a.ics'})])
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau), Etat.ADRESSE_PRIVEE)
        self.assertEqual(reseau.ouvertes, [('agenda.example', PUBLIQUE)])

    def test_redirection_vers_http(self):
        reseau = Reseau({'agenda.example': [PUBLIQUE]},
                        [FausseReponse(301, entetes={'Location': 'http://agenda.example/a.ics'})])
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau), Etat.PAS_HTTPS)

    def test_plus_de_3_redirections(self):
        sauts = [FausseReponse(307, entetes={'Location': f'/a{n}.ics'}) for n in range(4)]
        reseau = Reseau({'agenda.example': [PUBLIQUE]}, sauts)
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau), Etat.INJOIGNABLE)

    def test_corps_trop_grand(self):
        gros = FausseReponse(200, corps=b'x' * (lecteur.CORPS_MAX + 1))
        self.assertEqual(self.etat('https://agenda.example/a.ics', Reseau({'agenda.example': [PUBLIQUE]}, [gros])),
                         Etat.TROP_GRANDE)

    def test_longueur_annoncee_trop_grande(self):
        annonce = FausseReponse(200, entetes={'Content-Length': str(lecteur.CORPS_MAX + 1)})
        reseau = Reseau({'agenda.example': [PUBLIQUE]}, [annonce])
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau), Etat.TROP_GRANDE)

    def test_delai_de_lecture(self):
        lente = FausseReponse(200, lever=socket.timeout('lent'))
        reseau = Reseau({'agenda.example': [PUBLIQUE]}, [lente])
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau), Etat.DELAI)

    def test_delai_total_epuise(self):
        reseau = Reseau({'agenda.example': [PUBLIQUE]}, [FausseReponse(200, corps=ICS.encode())])
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau, delai=0), Etat.DELAI)

    def test_statut_d_erreur(self):
        reseau = Reseau({'agenda.example': [PUBLIQUE]}, [FausseReponse(500)])
        self.assertEqual(self.etat('https://agenda.example/a.ics', reseau), Etat.INJOIGNABLE)

    def test_succes_connexion_vers_l_adresse_verifiee(self):
        reseau = Reseau({'agenda.example': [PUBLIQUE]}, [FausseReponse(200, corps=ICS.encode())])
        with reseau:
            texte = lecteur.telecharger('https://agenda.example/a.ics?jeton=1')
        self.assertIn('BEGIN:VCALENDAR', texte)
        self.assertEqual(reseau.ouvertes, [('agenda.example', PUBLIQUE)])

    def test_texte_illisible(self):
        with self.assertRaises(lecteur.Echec) as refus:
            lecteur.evenements_du_texte('pas un agenda', 1, datetime.date(2026, 11, 16), datetime.date(2026, 11, 18))
        self.assertEqual(refus.exception.etat, Etat.ILLISIBLE)

    def test_webcal_reecrit_en_https(self):
        self.assertEqual(lecteur.normaliser_url(' webcal://p01.icloud.com/a.ics '), 'https://p01.icloud.com/a.ics')

    def test_connexion_epinglee_garde_le_nom_pour_le_tls(self):
        connexion = lecteur.ConnexionEpinglee('agenda.example', PUBLIQUE, 443, 5)
        self.assertEqual((connexion.host, connexion.ip, connexion.port), ('agenda.example', PUBLIQUE, 443))


class RoutesAgendasExternesTests(TestCase):
    """Les 5 routes `agendas-externes/` : ≤ 3 par compte, URL jamais rendue, état lisible."""

    URL = '/api/django/taches/agendas-externes/'

    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.u = fabriques.compte(cls.societe, nom='u1')

    def setUp(self):
        cache.clear()
        self.client_ = APIClient()
        self.client_.force_authenticate(self.u)
        self.patchs = [mock.patch.object(lecteur, 'verifier_adresse', return_value=None),
                       mock.patch.object(lecteur, 'telecharger', return_value=ICS)]
        self.verifier, self.telecharger = [p.start() for p in self.patchs]

    def tearDown(self):
        for p in self.patchs:
            p.stop()

    def ajouter(self, url, statut=201, libelle='Microsoft 365'):
        reponse = self.client_.post(self.URL, {'url': url, 'libelle': libelle}, format='json')
        self.assertEqual(reponse.status_code, statut, reponse.content[:300])
        return reponse

    def test_ajout_lu_aussitot_forme_sans_url(self):
        reponse = self.ajouter('webcal://outlook.example/owa/calendar/secret/reachcalendar.ics')
        rendu = reponse.json()
        self.assertEqual(set(rendu), set(exemple('agenda_externe')))
        self.assertEqual((rendu['hote'], rendu['dernier_etat']), ('outlook.example', 'ok'))
        self.assertNotIn('secret', reponse.content.decode('utf-8'))
        from apps.taches.models.agenda import AgendaExterne
        stocke = AgendaExterne.objects.get(proprietaire=self.u)
        self.assertTrue(stocke.url.startswith('https://'))

    def test_4e_adresse_400_au_champ_url(self):
        for n in range(3):
            fabriques.agenda_externe(self.u, url=f'https://agenda.example/{n}.ics')
        rendu = self.ajouter('https://agenda.example/4.ics', statut=400).json()
        self.assertEqual(rendu, {'url': ['3 agendas au plus.']})

    def test_doublon_400(self):
        fabriques.agenda_externe(self.u, url='https://agenda.example/a.ics')
        self.assertEqual(self.ajouter('https://agenda.example/a.ics', statut=400).json(),
                         {'url': ['Cet agenda est déjà ajouté.']})

    def test_adresse_non_publique_400(self):
        self.verifier.side_effect = UnsafeWebhookURL('interne')
        self.assertEqual(self.ajouter('https://intranet.local/a.ics', statut=400).json(),
                         {'url': ['Adresse https publique attendue.']})

    def test_liste(self):
        fabriques.agenda_externe(self.u, libelle='Bureau')
        rendu = self.client_.get(self.URL).json()
        self.assertEqual(set(rendu), set(exemple('agendas_externes')))
        self.assertEqual(set(rendu['results'][0]), set(exemple('agenda_externe')))

    def test_patch_delete_et_404_d_un_autre(self):
        agenda = fabriques.agenda_externe(self.u)
        chemin = f'{self.URL}{agenda.pk}/'
        rendu = self.client_.patch(chemin, {'libelle': 'Bureau', 'actif': False}, format='json').json()
        self.assertEqual((rendu['libelle'], rendu['actif']), ('Bureau', False))
        autre = fabriques.compte(self.societe, nom='u2')
        etranger = fabriques.agenda_externe(autre)
        self.assertEqual(self.client_.patch(f'{self.URL}{etranger.pk}/', {'libelle': 'x'}, format='json')
                         .status_code, 404)
        self.assertEqual(self.client_.delete(chemin).status_code, 204)
        self.assertFalse(type(agenda).objects.filter(pk=agenda.pk).exists())

    def test_rafraichir_dit_l_echec(self):
        agenda = fabriques.agenda_externe(self.u)
        self.telecharger.side_effect = lecteur.Echec(Etat.DELAI)
        rendu = self.client_.post(f'{self.URL}{agenda.pk}/rafraichir/').json()
        self.assertEqual(rendu['dernier_etat'], 'delai')

    def test_cache_15_minutes_et_echec_qui_l_efface(self):
        agenda = fabriques.agenda_externe(self.u)
        du, au = datetime.date(2026, 11, 16), datetime.date(2026, 11, 18)
        premiers = lecteur.lire_agenda_externe(agenda, du, au)
        lecteur.lire_agenda_externe(agenda, du, au)
        self.assertEqual(self.telecharger.call_count, 1)
        self.assertEqual([r.titre for r in premiers], ['Réunion banque'])
        self.telecharger.side_effect = lecteur.Echec(Etat.INJOIGNABLE)
        self.assertEqual(lecteur.lire_agenda_externe(agenda, du, au, rafraichir=True), ())
        self.assertIsNone(cache.get(lecteur.cle_cache(agenda)))

    def test_url_jamais_journalisee(self):
        agenda = fabriques.agenda_externe(self.u, url='https://agenda.example/jeton-tres-secret.ics')
        self.telecharger.side_effect = lecteur.Echec(Etat.ILLISIBLE)
        with self.assertLogs('apps.taches.agenda_externe', 'INFO') as journal:
            lecteur.lire_agenda_externe(agenda, datetime.date(2026, 11, 16), datetime.date(2026, 11, 18))
        self.assertNotIn('jeton-tres-secret', '\n'.join(journal.output))
