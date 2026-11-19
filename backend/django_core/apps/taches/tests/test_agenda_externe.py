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
from apps.taches.tests.test_api_saisie import champs

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


class Horloge:
    """Horloge simulée (secondes), avancée par le faux transport et les tests."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class SocketGoutte:
    """Faux socket TLS : rend chaque segment (octets, secondes par octet) UN octet par `recv_into`,
    en avançant l'horloge ; respecte `settimeout` comme un vrai socket (un octet plus lent que le
    délai d'appel → l'horloge avance du délai et `socket.timeout`)."""

    def __init__(self, horloge, *segments):
        self.horloge, self.timeout = horloge, None
        self.octets = [(octet, pas) for donnees, pas in segments for octet in donnees]

    def settimeout(self, valeur):
        self.timeout = valeur

    def sendall(self, donnees, *args):
        pass

    def recv_into(self, tampon):
        if not self.octets:
            return 0
        octet, pas = self.octets[0]
        if self.timeout is not None and pas > self.timeout:
            self.horloge.t += self.timeout
            raise socket.timeout('lent')
        self.horloge.t += pas
        self.octets.pop(0)
        tampon[0] = octet
        return 1

    def close(self):
        pass


class FauxCache:
    """Cache en mémoire dont l'expiration suit l'horloge simulée."""

    def __init__(self, horloge):
        self.horloge, self.valeurs = horloge, {}

    def get(self, cle):
        valeur, expire = self.valeurs.get(cle, (None, 0))
        return valeur if self.horloge() < expire else None

    def set(self, cle, valeur, duree):
        self.valeurs[cle] = (valeur, self.horloge() + duree)

    def delete(self, cle):
        self.valeurs.pop(cle, None)


class EcheanceAbsolueTests(SimpleTestCase):
    """Revue F2 #5/#6 : le délai total d'une lecture est une ÉCHÉANCE (pas un délai par `recv`), un
    écran borne ses 3 agendas ensemble, et un échec est retenu 15 min — sans réseau ni base."""

    DU, AU = datetime.date(2026, 11, 16), datetime.date(2026, 11, 18)

    def setUp(self):
        self.h = Horloge()
        self.sockets, self.etats = [], []
        self.cache = FauxCache(self.h)
        reseau = Reseau({'agenda.example': [PUBLIQUE]}, [])
        patchs = [mock.patch.object(lecteur, 'horloge', self.h),
                  mock.patch.object(lecteur, 'cache', self.cache),
                  mock.patch.object(lecteur, '_connecter', self.connecter),
                  mock.patch.object(lecteur, '_poser_etat', lambda agenda, etat: self.etats.append((agenda.pk, etat))),
                  mock.patch.object(lecteur.socket, 'getaddrinfo', reseau.getaddrinfo)]
        for p in patchs:
            p.start()
            self.addCleanup(p.stop)

    def connecter(self, ip, port, hote, contexte, fin):
        return self.sockets.pop(0)

    def agenda(self, pk):
        from apps.taches.models.agenda import AgendaExterne
        return AgendaExterne(pk=pk, company_id=1, proprietaire_id=1, url=f'https://agenda.example/{pk}.ics',
                             hote='agenda.example', libelle=f'A{pk}', actif=True)

    def test_en_tetes_au_goutte_a_goutte_abandonnes_dans_le_delai_total(self):
        # Un octet toutes les 9 s : sous le délai PAR appel (10 s), la lecture ne finirait jamais.
        self.sockets.append(SocketGoutte(self.h, (b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nBEGIN', 9)))
        debut = self.h.t
        with self.assertRaises(lecteur.Echec) as refus:
            lecteur.telecharger('https://agenda.example/a.ics')
        self.assertEqual(refus.exception.etat, Etat.DELAI)
        self.assertLessEqual(self.h.t - debut, lecteur.DELAI_MAX + 1e-6)

    def test_redirection_puis_corps_lent_bornes_ensemble(self):
        saut = b'HTTP/1.1 302 Found\r\nLocation: /b.ics\r\nContent-Length: 0\r\n\r\n'
        entetes = f'HTTP/1.1 200 OK\r\nContent-Length: {len(ICS.encode())}\r\n\r\n'.encode()
        self.sockets += [SocketGoutte(self.h, (saut, 0.05)),
                         SocketGoutte(self.h, (entetes, 0), (ICS.encode(), 2))]
        debut = self.h.t
        with self.assertRaises(lecteur.Echec) as refus:
            lecteur.telecharger('https://agenda.example/a.ics')
        self.assertEqual(refus.exception.etat, Etat.DELAI)
        self.assertEqual(self.sockets, [])  # les deux sauts ont été faits
        self.assertLessEqual(self.h.t - debut, lecteur.DELAI_MAX + 1e-6)

    def test_lecture_rapide_toujours_lue(self):
        corps = ICS.encode()
        self.sockets.append(SocketGoutte(self.h, (f'HTTP/1.1 200 OK\r\nContent-Length: {len(corps)}\r\n\r\n'
                                                  .encode() + corps, 0.001)))
        self.assertIn('BEGIN:VCALENDAR', lecteur.telecharger('https://agenda.example/a.ics'))

    def test_echec_retenu_15_minutes_sans_seconde_lecture(self):
        agenda = self.agenda(1)
        with mock.patch.object(lecteur, 'telecharger', side_effect=lecteur.Echec(Etat.DELAI)) as lecture:
            self.assertEqual(lecteur.lire_agenda_externe(agenda, self.DU, self.AU), ())
            self.h.t += lecteur.CACHE_SECONDES - 1
            self.assertEqual(lecteur.lire_agenda_externe(agenda, self.DU, self.AU), ())
            self.assertEqual(lecture.call_count, 1)
            self.assertEqual(self.etats, [(1, Etat.DELAI)])  # aucune écriture en base pendant l'échec retenu
            self.h.t += 2
            lecteur.lire_agenda_externe(agenda, self.DU, self.AU)
            self.assertEqual(lecture.call_count, 2)
            lecteur.lire_agenda_externe(agenda, self.DU, self.AU, rafraichir=True)  # Réessayer
            self.assertEqual(lecture.call_count, 3)

    def test_echec_remplace_les_anciens_rendez_vous(self):
        agenda = self.agenda(1)
        with mock.patch.object(lecteur, 'telecharger', return_value=ICS):
            self.assertEqual(len(lecteur.lire_agenda_externe(agenda, self.DU, self.AU)), 1)
        with mock.patch.object(lecteur, 'telecharger', side_effect=lecteur.Echec(Etat.INJOIGNABLE)):
            self.assertEqual(lecteur.lire_agenda_externe(agenda, self.DU, self.AU, rafraichir=True), ())
            self.assertEqual(lecteur.lire_agenda_externe(agenda, self.DU, self.AU), ())

    def test_trois_agendas_lents_temps_total_borne(self):
        from types import SimpleNamespace

        from apps.taches.selectors.journee import rendez_vous_pour
        lent = b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nBEGIN'
        self.sockets += [SocketGoutte(self.h, (lent, 9)) for _ in range(3)]
        agendas = [self.agenda(pk) for pk in (1, 2, 3)]
        debut = self.h.t
        with mock.patch.object(lecteur, 'agendas_actifs', return_value=agendas):
            evenements, libelles = rendez_vous_pour(SimpleNamespace(company_id=1, pk=1), self.DU, self.AU)
        self.assertEqual(evenements, ())
        self.assertEqual(set(libelles), {1, 2, 3})
        self.assertLessEqual(self.h.t - debut, lecteur.DELAI_ECRAN + 1e-6)
        self.assertEqual(len(self.sockets), 2)  # seul le 1er a été lu ; les autres attendent la requête suivante
        self.assertEqual(self.etats, [(1, Etat.DELAI)])


class MessagesDAjoutTests(SimpleTestCase):
    """R2-127 sans base : la garde d'AJOUT refuse AVANT toute lecture en base, avec le message du vrai motif."""

    def refus(self, brute, *, leve=None):
        from rest_framework.exceptions import ValidationError

        from apps.taches.views import agenda_externe as vue
        with mock.patch.object(lecteur, 'verifier_adresse', side_effect=leve):
            with self.assertRaises(ValidationError) as contexte:
                vue._url_acceptee(object(), brute)
        return [str(m) for m in contexte.exception.detail['url']]

    def test_ce_n_est_pas_une_adresse(self):
        for brute in ('mon agenda du bureau', '', 'agenda.example/a.ics', 'https://'):
            with self.subTest(brute=brute):
                self.assertEqual(self.refus(brute), ["Ce n'est pas une adresse : colle le lien de ton agenda."])

    def test_il_faut_https(self):
        for brute in ('http://agenda.example/a.ics', 'ftp://agenda.example/a.ics'):
            with self.subTest(brute=brute):
                self.assertEqual(self.refus(brute), ["L'adresse doit commencer par https."])

    def test_webcal_est_lu_comme_https(self):
        self.assertEqual(self.refus('webcal://agenda.example/a.ics', leve=UnsafeWebhookURL('interne')),
                         ['Adresse injoignable : vérifie le lien.'])

    def test_hote_introuvable_ou_interne_est_injoignable(self):
        motifs = ("L'hôte du webhook est introuvable (DNS).",
                  "L'URL du webhook pointe vers une adresse interne interdite.")
        for motif in motifs:
            with self.subTest(motif=motif):
                self.assertEqual(self.refus('https://agenda.example/a.ics', leve=UnsafeWebhookURL(motif)),
                                 ['Adresse injoignable : vérifie le lien.'])


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
        self.assertEqual(champs(rendu), {'url': ['3 agendas au plus.']})

    def test_doublon_400(self):
        fabriques.agenda_externe(self.u, url='https://agenda.example/a.ics')
        self.assertEqual(champs(self.ajouter('https://agenda.example/a.ics', statut=400).json()),
                         {'url': ['Cet agenda est déjà ajouté.']})

    def test_adresse_non_publique_400(self):
        self.verifier.side_effect = UnsafeWebhookURL('interne')
        self.assertEqual(champs(self.ajouter('https://intranet.local/a.ics', statut=400).json()),
                         {'url': ['Adresse injoignable : vérifie le lien.']})

    def test_r2_127_trois_refus_trois_messages(self):
        """F2 n°18 : « pas une adresse », « il faut https », « injoignable » ne se disent plus d'une seule phrase."""
        self.assertEqual(champs(self.ajouter('mon agenda du bureau', statut=400).json()),
                         {'url': ["Ce n'est pas une adresse : colle le lien de ton agenda."]})
        self.assertEqual(champs(self.ajouter('http://agenda.example/a.ics', statut=400).json()),
                         {'url': ["L'adresse doit commencer par https."]})
        self.verifier.side_effect = UnsafeWebhookURL("L'hôte du webhook est introuvable (DNS).")
        self.assertEqual(champs(self.ajouter('https://agenda-introuvable.example/a.ics', statut=400).json()),
                         {'url': ['Adresse injoignable : vérifie le lien.']})

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

    def test_cache_15_minutes_et_echec_retenu(self):
        agenda = fabriques.agenda_externe(self.u)
        du, au = datetime.date(2026, 11, 16), datetime.date(2026, 11, 18)
        premiers = lecteur.lire_agenda_externe(agenda, du, au)
        lecteur.lire_agenda_externe(agenda, du, au)
        self.assertEqual(self.telecharger.call_count, 1)
        self.assertEqual([r.titre for r in premiers], ['Réunion banque'])
        self.telecharger.side_effect = lecteur.Echec(Etat.INJOIGNABLE)
        self.assertEqual(lecteur.lire_agenda_externe(agenda, du, au, rafraichir=True), ())
        # L'échec REMPLACE le texte (jamais d'anciens rendez-vous) et n'est pas relu avant 15 min.
        self.assertEqual(cache.get(lecteur.cle_cache(agenda)), {lecteur.CLE_ECHEC: Etat.INJOIGNABLE})
        self.assertEqual(lecteur.lire_agenda_externe(agenda, du, au), ())
        self.assertEqual(self.telecharger.call_count, 2)
        agenda.refresh_from_db()
        self.assertEqual(agenda.dernier_etat, Etat.INJOIGNABLE)
        # Réessayer (rafraichir/) relit aussitôt.
        self.telecharger.side_effect = None
        self.assertEqual(len(lecteur.lire_agenda_externe(agenda, du, au, rafraichir=True)), 1)
        self.assertEqual(self.telecharger.call_count, 3)

    def test_url_jamais_journalisee(self):
        agenda = fabriques.agenda_externe(self.u, url='https://agenda.example/jeton-tres-secret.ics')
        self.telecharger.side_effect = lecteur.Echec(Etat.ILLISIBLE)
        with self.assertLogs('apps.taches.agenda_externe', 'INFO') as journal:
            lecteur.lire_agenda_externe(agenda, datetime.date(2026, 11, 16), datetime.date(2026, 11, 18))
        self.assertNotIn('jeton-tres-secret', '\n'.join(journal.output))


# --- TCH122 : rendez-vous servis dans aujourdhui/ et agenda/ ---------------------------------------

def ics_du_jour(jour, debut='110000', fin='120000', titre='Réunion banque'):
    return ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:rdv-1\r\n'
            f'DTSTART;TZID=Africa/Casablanca:{jour:%Y%m%d}T{debut}\r\n'
            f'DTEND;TZID=Africa/Casablanca:{jour:%Y%m%d}T{fin}\r\n'
            f'SUMMARY:{titre}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n')


class RendezVousServisTests(TestCase):
    """Invariant 35 : temps disponible = capacité − rendez-vous ; RENDEZ_VOUS dans Aujourd'hui et
    l'Agenda, « Rendez-vous » sous l'en-tête assistant, jamais dans la pastille ; cache chaud = 0
    requête de plus."""

    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.u = fabriques.compte(cls.societe, nom='u1')
        cls.sans_agenda = fabriques.compte(cls.societe, nom='u2')

    def setUp(self):
        from django.utils import timezone
        cache.clear()
        self.T = timezone.localdate()
        self.patch = mock.patch.object(lecteur, 'telecharger', return_value=ics_du_jour(self.T))
        self.telecharger = self.patch.start()
        self.agenda = fabriques.agenda_externe(self.u, libelle='Microsoft 365')

    def tearDown(self):
        self.patch.stop()

    def get(self, compte, chemin, entetes=None, **params):
        client = APIClient()
        client.force_authenticate(compte)
        reponse = client.get(f'/api/django/taches/{chemin}', params, **(entetes or {}))
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json()

    def test_aujourdhui_retranche_l_heure_de_reunion(self):
        rendu = self.get(self.u, 'aujourdhui/')
        self.assertEqual(len(rendu['rendez_vous']), 1)
        rdv = rendu['rendez_vous'][0]
        self.assertEqual(set(rdv), set(exemple('rendez_vous')['results'][0]))
        self.assertEqual((rdv['titre'], rdv['agenda'], rdv['journee_entiere']),
                         ('Réunion banque', 'Microsoft 365', False))
        progression = rendu['progression']
        self.assertEqual((progression['capacite_minutes'], progression['rendez_vous_minutes'],
                          progression['disponible_minutes']), (240, 60, 180))
        self.assertEqual(rendu['propose']['charge']['disponible_minutes'], 180)

    def test_sous_l_entete_assistant_le_titre_est_masque(self):
        rendu = self.get(self.u, 'aujourdhui/', entetes={'HTTP_X_TAQINOR_ASSISTANT': '1'})
        self.assertEqual(rendu['rendez_vous'][0]['titre'], 'Rendez-vous')

    def test_agenda_externes_du_jour(self):
        rendu = self.get(self.u, 'agenda/', du=self.T.isoformat(), au=self.T.isoformat(), vue='jour')
        externes = rendu['jours'][0]['externes']
        self.assertEqual([r['titre'] for r in externes], ['Réunion banque'])

    def test_jamais_dans_la_pastille(self):
        self.assertEqual(self.get(self.u, 'badge/')['n'], 0)

    def test_agenda_inactif_ne_compte_pas(self):
        self.agenda.actif = False
        self.agenda.save()
        self.assertEqual(self.get(self.u, 'aujourdhui/')['progression']['rendez_vous_minutes'], 0)

    def test_cache_chaud_zero_requete_de_plus(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        mesures = {}
        for compte in (self.u, self.sans_agenda):
            self.get(compte, 'aujourdhui/')  # chauffe : index des agendas et texte ICS en cache
            with CaptureQueriesContext(connection) as requetes:
                self.get(compte, 'aujourdhui/')
            mesures[compte.pk] = len(requetes)
        self.assertEqual(mesures[self.u.pk], mesures[self.sans_agenda.pk])
        self.assertEqual(self.telecharger.call_count, 1)
