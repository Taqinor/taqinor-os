"""TCH127 — le test canari de la confidentialité (reference/regles.md « La confidentialité », test canari ;
reference/donnees.md invariants 8 et 38 ; conception/arbitrages.md A6).

Le monde canari : un projet confidentiel « Canari-7Q9 » (nom, objectif, bilan, risque, domaine, étapes, revue),
ses tâches « Canari-X3K » (titre, notes, « en attente de », lien ERP, check-list, étiquette), une sous-tâche, une
tâche d'« À trier » et une série confidentielles par leur SEUL drapeau, la sous-tâche de l'une d'elles (héritage
par le parent), des tâches supprimées, un rendez-vous externe « Canari-RDV », un geste « En attente de : Canari… »
fait à l'écran, et une tâche ORDINAIRE bloquée par une confidentielle. Les trois `titres_*` sont allumés.

Aucune chaîne servie ne contient « canari » (casse et accents ignorés ; JSON décodé ; .ics déplié) :
1. ASSISTANT : chaque route CONSTRUITE de l'app — la liste fermée de `test_meme_proprietaire` (`CAS`, `SANS_ID`,
   `AUSSI_SANS_ID`) rejouée sur le monde canari, plus les lectures propres au canari (`en_plus`) — et chaque action
   `taches.*` du registre de l'agent (les entrées de `test_agent_actions`), avec l'en-tête `X-Taqinor-Assistant` ;
   une écriture est défaite aussitôt lue. Un texte que l'assistant a lui-même ENVOYÉ et que la réponse répète
   (l'aperçu d'une saisie) n'est pas une fuite : il est retiré avant la recherche.
2. FLUX `.ics` et TUILE, chacun par son jeton.
3. SIRI : la réponse de `capture/` (JSON et texte), rejeu au même `client_id` compris.
4. NOTIFICATIONS du balayage (`balayage.executer`) : titre ET corps stockés des rappels (par chacun des trois
   héritages et le drapeau propre), du plan du matin, des relances échéance, essentiel et projet négligé.
5. `IncitationCoach.donnees` : après chaque appel de l'assistant, chaque balayage et la nuit (`nocturne`).
TÉMOINS : à l'écran (sans l'en-tête), les routes de `VIVANTES` et les actions de `ACTIONS_VIVANTES` voient le
canari ; pour 2-4, le même monde DÉCLASSÉ (drapeaux éteints) le montre. Sans eux, le test ne prouverait rien.

Horloge figée au mardi 17/11/2026 10:00 (Africa/Casablanca) ; le balayage et la nuit reçoivent leur instant.
Aucun accès réseau : la lecture des agendas externes et la vérification d'adresse sont remplacées.
"""
import datetime
import json
import re
import unicodedata
from types import SimpleNamespace
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.taches import agent_actions, balayage, nocturne
from apps.taches import agenda_externe as lecteur
from apps.taches.choix import LienEtat, ModeRythme, Priorite, StatutTache
from apps.taches.models.journee import LignePlanJour
from apps.taches.models.presence import JetonAcces
from apps.taches.models.projets import Projet, RevueProjet
from apps.taches.models.rythme import IncitationCoach, ReglagesRythme
from apps.taches.models.taches import Etiquette, EtiquetteTache, Rappel, Tache
from apps.taches.moteur.ics import RendezVousPur
from apps.taches.tests import fabriques
from apps.taches.tests import test_agent_actions as agent
from apps.taches.tests import test_meme_proprietaire as meme
from apps.taches.tests.test_flux_tuile import _depliees
from testkit.time import frozen

J = datetime.date(2026, 11, 17)  # mardi, jour ouvré
PREFIXE = meme.PREFIXE
MARQUE = 'canari'
PROJET = 'Canari-7Q9'
TACHE = 'Canari-X3K'
RDV = 'Canari-RDV'
ASSISTANT = {'HTTP_X_TAQINOR_ASSISTANT': '1'}
EXTRAIT = re.compile(r'canari[^"\\\r\n]{0,24}')


def a(heure, minute=0, jour=J):
    """Instant local (fuseau de la société) du `jour`."""
    return timezone.make_aware(datetime.datetime.combine(jour, datetime.time(heure, minute)))


#: Routes dont la réponse À L'ÉCRAN montre le canari (témoin : la même route, sans l'en-tête, le voit).
VIVANTES = frozenset({
    ('GET', 'aujourdhui/'), ('GET', 'journee/proposition/'), ('GET', 'recherche/'), ('GET', 'projets/{id}/vue/'),
    ('GET', 'revue/projets/'), ('POST', 'taches/{id}/changement/apercu/'), ('POST', 'saisie-rapide/'),
    ('GET', 'taches/'), ('GET', 'taches/{id}/'), ('GET', 'projets/'), ('GET', 'projets/{id}/'),
    ('GET', 'supprimees/'), ('GET', 'gestes/'), ('GET', 'agenda/'),
})
#: Actions de l'agent dont la route, appelée par l'écran, montre le canari.
ACTIONS_VIVANTES = frozenset({'taches.journee.lire', 'taches.tache.chercher', 'taches.projet.lire'})


# --- Lire une réponse ------------------------------------------------------------------------------

def plier(texte):
    """Casse et accents ignorés (NFKD sans diacritiques, `casefold`)."""
    decompose = unicodedata.normalize('NFKD', texte)
    return ''.join(c for c in decompose if not unicodedata.combining(c)).casefold()


def texte_servi(reponse):
    """Le corps tel qu'un lecteur le reçoit : JSON décodé, `.ics` déplié, texte brut sinon."""
    if not reponse.content:
        return ''
    if 'json' in reponse.get('Content-Type', ''):
        return json.dumps(reponse.json(), ensure_ascii=False)
    return ''.join(_depliees(reponse.content.decode('utf-8')))


def echos(corps):
    """Les textes à canari que la requête ENVOIE elle-même (corps JSON ; les paramètres d'adresse jamais)."""
    if isinstance(corps, str):
        return [corps] if MARQUE in plier(corps) else []
    if isinstance(corps, dict):
        return [e for valeur in corps.values() for e in echos(valeur)]
    if isinstance(corps, (list, tuple)):
        return [e for valeur in corps for e in echos(valeur)]
    return []


def fuites(texte, renvoyes=()):
    """Les extraits « canari… » du texte, une fois retirés les textes que la requête a elle-même envoyés."""
    plie = plier(texte)
    for renvoye in sorted(renvoyes, key=len, reverse=True):
        plie = plie.replace(plier(renvoye), '')
    return EXTRAIT.findall(plie)


def donnees_des_incitations(compte):
    """Les extraits « canari » de `IncitationCoach.donnees` du compte (JSON décodé)."""
    lignes = IncitationCoach.objects.filter(proprietaire=compte).values_list('donnees', flat=True)
    return fuites(json.dumps(list(lignes), ensure_ascii=False))


# --- Le monde canari ---------------------------------------------------------------------------------

def _projet(projet, nom):
    projet.nom = nom
    projet.objectif, projet.bilan, projet.risque = f'{PROJET} objectif', f'{PROJET} bilan', f'{PROJET} risque'
    projet.domaine, projet.confidentiel = f'{PROJET} dom', True
    projet.save()


def _tache(tache, nom, **champs):
    tache.titre, tache.notes = f'{TACHE} {nom}', f'{TACHE} note {nom}'
    tache.en_attente_de = f'{TACHE} attente {nom}'
    for champ, valeur in champs.items():
        setattr(tache, champ, valeur)
    tache.save()


def _canariser(m):
    """Le monde de `test_meme_proprietaire` (mêmes attributs, donc mêmes requêtes) rendu confidentiel, un
    marqueur dans chaque champ de texte."""
    compte = m.compte
    ReglagesRythme.objects.filter(proprietaire=compte).update(
        titres_notifications=True, titres_calendrier=True, titres_tuile=True)
    for projet, nom in ((m.P, PROJET), (m.P2, f'Deuxième {PROJET}'), (m.PD, f'{PROJET} supprimé')):
        _projet(projet, nom)
    for n, section in enumerate((m.S1, m.S2), start=1):
        section.nom = f'{PROJET} étape {n}'
        section.save()
    lead = ContentType.objects.get(app_label='crm', model='lead')
    _tache(m.T, 'T', content_type=lead, object_id=1, lien_libelle=f'{TACHE} lien', lien_etat=LienEtat.OK)
    for nom in ('T2', 'T3', 'D'):  # par leur projet
        _tache(getattr(m, nom), nom)
    for nom in ('B', 'TR'):  # par leur SEUL drapeau (À trier, série)
        _tache(getattr(m, nom), nom, confidentiel=True)
    # L'étiquette n'hérite pas (elle sert plusieurs tâches) : la neutre `E` reste celle des requêtes ; celle-ci,
    # posée sur la seule confidentielle T, n'est jamais servie avec elle.
    m.E_CANARI = Etiquette.objects.create(company=compte.company, proprietaire=compte, nom=f'{TACHE} étiquette')
    EtiquetteTache.objects.create(company=compte.company, tache=m.T, etiquette=m.E_CANARI)
    for n, element in enumerate((m.C1, m.C2), start=1):
        element.libelle = f'{TACHE} check {n}'
        element.save()
    m.SOUS = fabriques.tache(compte, projet=m.P, parent=m.T, titre=f'{TACHE} sous-tâche', jour_prevu=J,
                             notes=f'{TACHE} note sous-tâche')  # par le projet du parent
    m.SOUS_B = fabriques.tache(compte, parent=m.B, titre=f'{TACHE} sous-tâche de B', jour_prevu=J)  # par le parent
    m.BLOQ = fabriques.tache(compte, titre='Ordinaire bloquée', jour_prevu=J, bloquee_par=m.T)
    m.PROPOSEE = fabriques.tache(compte, projet=m.P, titre=f'{TACHE} proposée', jour_prevu=J - datetime.timedelta(1))
    RevueProjet.objects.create(company=compte.company, proprietaire=compte, projet=m.P, semaine=J,
                               intention=f'{PROJET} intention')
    m.AGENDA = fabriques.agenda_externe(compte, url='https://agenda.example/bureau.ics', libelle='Bureau')
    # Le jeton de flux du monde (clair perdu) est révoqué ; le neuf prend sa place dans les requêtes.
    JetonAcces.objects.filter(pk=m.J.pk).update(revoque_le=timezone.now())
    m.J, m.flux = fabriques.jeton(compte, 'flux')
    m.tuile, m.capture = (fabriques.jeton(compte, usage)[1] for usage in ('tuile', 'capture'))
    return m


def rendez_vous(m):
    return (RendezVousPur('1-rdv', m.AGENDA.pk, RDV, datetime.datetime.combine(J, datetime.time(15, 0)),
                          datetime.datetime.combine(J, datetime.time(16, 0)), False),)


def declasser(compte):
    """Témoin : le même monde, drapeaux éteints (les marqueurs restent)."""
    Projet.all_objects.filter(proprietaire=compte).update(confidentiel=False)
    Tache.all_objects.filter(proprietaire=compte).update(confidentiel=False)


def en_plus(m):
    """Lectures propres au canari, en plus de la liste fermée : (méthode, chemin, porte, url, corps)."""
    return (
        ('GET', 'recherche/', '?q=Canari', 'recherche/?q=Canari', None),
        ('GET', 'recherche/', '?q=X3K', 'recherche/?q=X3K', None),
        ('GET', 'recherche/', '?q=7Q9', 'recherche/?q=7Q9', None),
        ('GET', 'taches/', 'liste', 'taches/', None),
        ('GET', 'agenda/', 'semaine', 'agenda/', None),
        ('POST', 'saisie-rapide/', 'aperçu (doublon)', 'saisie-rapide/', {'texte': m.T.titre, 'apercu': True}),
        ('POST', 'saisie-rapide/', 'aperçu (projet)', 'saisie-rapide/',
         {'texte': f'projet {PROJET} réserver le stand', 'apercu': True}),
    )


def requetes(m):
    """Toutes les requêtes du balayage : la liste FERMÉE des routes construites (`test_meme_proprietaire`, chaque
    id pris dans le monde canari) puis `en_plus`."""
    for cas in meme.CAS:
        url, corps = cas.requete(m, m)
        yield cas.methode, cas.chemin, cas.porte, url, corps
    for (methode, chemin), requete in meme.SANS_ID.items():
        yield (methode, chemin, '', *requete(m))
    for methode, chemin, requete in meme.AUSSI_SANS_ID:
        yield (methode, chemin, 'sans id', *requete(m))
    yield from en_plus(m)


class _Canari(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Ni la société ni le compte ne portent le mot (prénom et société sont servis) ; admin : reglages-societe/.
        compte = fabriques.compte(fabriques.societe('oiseau'), nom='moi', admin=True)
        cls.m = _canariser(meme._monde(compte, J))
        ecran = APIClient()
        ecran.force_authenticate(compte)
        geste = ecran.post(f'{PREFIXE}taches/{cls.m.T3.pk}/attendre/', {'en_attente_de': f'{TACHE} attente écran'},
                           format='json')
        assert geste.status_code == 200, geste.content[:300]

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        for cible, valeur in (('lire_agenda_externe', rendez_vous(self.m)), ('verifier_adresse', None)):
            remplacement = mock.patch.object(lecteur, cible, return_value=valeur)
            remplacement.start()
            self.addCleanup(remplacement.stop)
        self.api = APIClient(raise_request_exception=False)
        self.api.force_authenticate(self.m.compte)


# --- 1. L'assistant ----------------------------------------------------------------------------------

@frozen(a(10, 0))
class AssistantTests(_Canari):
    """Sous l'en-tête assistant, aucune route ni action ne sert le canari ; à l'écran, il est vivant."""

    def _appel(self, methode, url, corps, entetes):
        """(texte servi, statut, extraits de `IncitationCoach.donnees`) — l'écriture est défaite ensuite."""
        appel = getattr(self.api, methode.lower())
        with transaction.atomic():
            if methode == 'GET':
                reponse = appel(PREFIXE + url, **entetes)
            else:
                reponse = appel(PREFIXE + url, corps if corps is not None else {}, format='json', **entetes)
            incitations = donnees_des_incitations(self.m.compte)
            transaction.set_rollback(True)
        return texte_servi(reponse), reponse.status_code, incitations

    def test_aucune_route_construite_ne_sert_le_canari_a_l_assistant(self):
        vivantes, appels = set(), 0
        for methode, chemin, porte, url, corps in requetes(self.m):
            with self.subTest(methode=methode, chemin=chemin, porte=porte):
                ecran, _statut, _ = self._appel(methode, url, corps, {})
                if fuites(ecran):
                    vivantes.add((methode, chemin))
                texte, statut, incitations = self._appel(methode, url, corps, ASSISTANT)
                appels += 1
                self.assertLess(statut, 500, texte[:300])
                self.assertEqual(fuites(texte, echos(corps)), [], f'{statut} {texte[:300]}')
                self.assertEqual(incitations, [])
        self.assertGreaterEqual(appels, len(meme.CAS) + len(meme.SANS_ID))
        self.assertEqual(sorted(VIVANTES - vivantes), [], "témoin : l'écran ne voit plus le canari")

    def _entrees(self):
        """Les entrées de `test_agent_actions.CanariTests`, sur les tâches confidentielles du monde canari."""
        taches = [Tache.all_objects.get(pk=t.pk) for t in (self.m.T, self.m.T2, self.m.T3, self.m.B, self.m.TR)]
        return agent.CanariTests._entrees(SimpleNamespace(taches=taches, projet=self.m.P, jour=J))

    def test_aucune_action_de_l_agent_ne_sert_le_canari(self):
        entrees, vivantes = self._entrees(), set()
        self.assertEqual(set(entrees), {action.key for action in agent_actions.ACTIONS})
        client = agent._client(self.m.compte)
        client.raise_request_exception = False
        for action in agent_actions.ACTIONS:
            with self.subTest(cle=action.key):
                for entetes in ({}, ASSISTANT):  # l'écran d'abord : un échec de l'assistant ne cache pas le témoin
                    with transaction.atomic():
                        reponse = agent._appeler(client, action, entrees[action.key], **entetes)
                        incitations = donnees_des_incitations(self.m.compte)
                        transaction.set_rollback(True)
                    texte = texte_servi(reponse)
                    self.assertLess(reponse.status_code, 500, texte[:300])
                    if entetes:
                        self.assertEqual(fuites(texte, echos(entrees[action.key])), [], texte[:300])
                        self.assertEqual(incitations, [])
                    elif fuites(texte):
                        vivantes.add(action.key)
        self.assertEqual(sorted(ACTIONS_VIVANTES - vivantes), [], "témoin : l'écran ne voit plus le canari")


# --- 2. Flux et tuile ; 3. Siri ----------------------------------------------------------------------

@frozen(a(10, 0))
class PresenceTests(_Canari):
    """Le flux, la tuile et Siri ne nomment jamais un objet confidentiel ; déclassé, il est nommé."""

    def _flux(self):
        reponse = APIClient().get(f'{PREFIXE}flux/{self.m.flux}.ics')
        self.assertEqual(reponse.status_code, 200)
        return texte_servi(reponse)

    def _tuile(self):
        """La tuile ne titre que les tâches GARDÉES : la confidentielle T l'est au plan du jour."""
        plan = fabriques.plan(self.m.compte, J, planifie_le=a(8, 0))
        LignePlanJour.objects.create(company=plan.company, plan=plan, tache=self.m.T, prevue_au_plan=True)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {self.m.tuile}')
        reponse = api.get(f'{PREFIXE}tuile/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return texte_servi(reponse)

    def test_flux_et_tuile_sans_canari(self):
        for nom, lire in (('flux', self._flux), ('tuile', self._tuile)):
            with self.subTest(usage=nom):
                texte = lire()
                self.assertEqual(fuites(texte), [])
                self.assertIn('Tâche confidentielle', texte)  # les confidentielles du jour y sont, masquées

    def test_temoin_flux_et_tuile_declasses(self):
        declasser(self.m.compte)
        for nom, lire in (('flux', self._flux), ('tuile', self._tuile)):
            with self.subTest(usage=nom):
                self.assertIn(plier(TACHE), plier(lire()))

    def _capturer(self, phrase, url, client_id):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {self.m.capture}')
        return api.post(f'{PREFIXE}capture/{url}', {'titre': phrase, 'client_id': client_id}, format='json')

    def _siri(self):
        """Les réponses de `capture/` (JSON puis texte, puis rejeu) pour deux phrases dans le projet canari."""
        servies = []
        for n, phrase in enumerate((f'projet {PROJET} {TACHE} appeler demain', f'projet {PROJET} {TACHE} relancer')):
            for url in ('', '?reponse=texte'):
                for _rejeu in range(2):
                    reponse = self._capturer(phrase, url, f'canari-{n}{url and "t"}')
                    self.assertIn(reponse.status_code, (200, 201), reponse.content[:300])
                    servies.append(texte_servi(reponse))
        projets = set(Tache.objects.filter(proprietaire=self.m.compte, source='capture')
                      .values_list('projet_id', flat=True))
        self.assertEqual(projets, {self.m.P.pk})  # la phrase a bien été rangée dans le projet canari
        return servies

    def test_siri_ne_nomme_ni_le_projet_ni_la_tache(self):
        for texte in self._siri():
            with self.subTest(texte=texte):
                self.assertEqual(fuites(texte), [])
                self.assertIn('un projet', texte)

    def test_temoin_siri_declasse(self):
        declasser(self.m.compte)
        for texte in self._siri():
            with self.subTest(texte=texte):
                self.assertIn(plier(PROJET), plier(texte))


# --- 4. Notifications ; 5. IncitationCoach.donnees -------------------------------------------------------

def _rappels(m):
    """Un rappel par voie de confidentialité : projet (T), drapeau propre (B), parent (SOUS_B), projet du parent
    (SOUS) — chacun seul à sa minute, donc titré si le titre est permis."""
    for n, tache in enumerate((m.T, m.B, m.SOUS_B, m.SOUS)):
        Rappel.objects.create(company=m.compte.company, proprietaire=m.compte, tache=tache, jour=J,
                              heure=datetime.time(16, 5 * n))
    return [a(16, 5 * n) for n in range(4)]


def _matin(m):
    return [a(8, 30)]


def _echeance(m):
    Tache.objects.filter(pk=m.T2.pk).update(echeance=J)
    return [a(15, 0)]


def _essentiel(m):
    plan = fabriques.plan(m.compte, J, planifie_le=a(8, 0))
    LignePlanJour.objects.create(company=m.compte.company, plan=plan, tache=m.T, prevue_au_plan=True,
                                 essentielle=True)
    ReglagesRythme.objects.filter(proprietaire=m.compte).update(mode=ModeRythme.POUSSER)
    return [a(15, 0)]


def _neglige(m):
    ReglagesRythme.objects.filter(proprietaire=m.compte).update(mode=ModeRythme.LIBRE)
    Projet.objects.filter(pk=m.P.pk).update(priorite=Priorite.HAUTE, statut_depuis=a(9, 0, J - datetime.timedelta(30)))
    autre = fabriques.projet(m.compte, nom='Ordinaire avancé', priorite=Priorite.BASSE)
    fabriques.tache(m.compte, projet=autre, statut=StatutTache.FAIT, fait_le=a(9, 0, J - datetime.timedelta(2)))
    return [a(15, 0)]


#: Scénario → (préparation qui rend les instants du balayage, nombre de notifications attendues).
SCENARIOS = {'rappels': (_rappels, 4), 'matin': (_matin, 1), 'echeance': (_echeance, 1),
             'essentiel': (_essentiel, 1), 'neglige': (_neglige, 1)}


@frozen(a(3, 0))
class NotificationsTests(_Canari):
    """Titre et corps de chaque notification du balayage, et les `donnees` des incitations : sans canari ;
    déclassé, le canari apparaît dans chaque scénario."""

    def _balayer(self, scenario):
        """Les notifications servies (titre + corps) du scénario, et les extraits des incitations."""
        preparer, attendues = SCENARIOS[scenario]
        with transaction.atomic():
            for instant in preparer(self.m):
                with frozen(instant):
                    balayage.executer(instant)
            servies = [f'{n.title} · {n.body}' for n in Notification.objects.filter(recipient=self.m.compte)]
            incitations = donnees_des_incitations(self.m.compte)
            transaction.set_rollback(True)
        self.assertEqual(len(servies), attendues, servies)
        return servies, incitations

    def test_aucune_notification_ne_porte_le_canari(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                servies, incitations = self._balayer(scenario)
                for texte in servies:
                    self.assertEqual(fuites(texte), [], texte)
                self.assertEqual(incitations, [])

    def test_temoin_declasse_les_notifications_nomment(self):
        declasser(self.m.compte)
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                servies, _incitations = self._balayer(scenario)
                for texte in servies:
                    self.assertNotEqual(fuites(texte), [], texte)

    def test_la_nuit_n_ecrit_aucun_canari_dans_les_incitations(self):
        nocturne.executer(self.m.compte.company_id, J)
        self.assertEqual(donnees_des_incitations(self.m.compte), [])
