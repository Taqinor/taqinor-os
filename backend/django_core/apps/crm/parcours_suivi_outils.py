"""SUIVI-PARCOURS (30/09/2026) — les OUTILS de la garde de parcours du suivi commercial.

Ordre fondateur (Reda, 30/09/2026) : « test very well all the steps by yourself or make a
testing script that we can reuse afterward ». Les blocages subis étaient des CHAÎNES — une
étape, une réponse, l'étape suivante… — qu'aucun test ne parcourait : la garde CAD17
(``tests_cad17_parite_promesse_effet.py``) insère UNE touche à la main et joue UNE réponse.

Ce module porte la mécanique, ``tests_parcours_suivi.py`` porte les tests. Trois principes :

* la SOURCE DE VÉRITÉ est la table ``frontend/src/features/crm/relances/parcours_suivi.json``,
  LUE ici (jamais recopiée) : pour chaque type d'étape, ses réponses (``modele`` fusionné avec
  l'entrée : ``{**modeles[r.modele], **r}``), ce que chacune ENVOIE (``outcome`` | ``reponse``
  | ``geste``, ``note``, ``date``, ``junk``, ``motif_perte``) et la SUITE attendue ;
* tout passe par l'API RÉELLE (``relance-etapes/<id>/fait/``, ``leads/<id>/visites/planifier/``,
  ``leads/``, ``leads/bulk/``, ``ventes/devis/<id>/accepter/``) et un lead n'arrive à une étape
  que par un CHEMIN réel (``amener``) — aucune ``RelanceEtape`` n'est insérée à la main ;
* le TYPE d'une touche est lu par un oracle INDÉPENDANT du moteur (``type_de``) qui applique la
  ``reconnaissance`` de la table dans son ordre : clé, puis libellé, puis cadence + canal.

La table décrit le comportement CIBLE (spec moteur du 30/09/2026) : la garde est écrite contre
elle, jamais contre le code du moment. Ce module n'est PAS un module de test (aucune méthode
``test_*``, nom hors du motif ``test*.py``) : seul ``tests_parcours_suivi.py`` l'importe.
"""
import datetime
import functools
import itertools
import json
import traceback
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.test import TestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.cadence_config import cle_de
from apps.crm.models import Lead, MotifPerte, RelanceEtape
from apps.notifications.calendar_utils import ajouter_jours_ouvres
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCES_DEFAUT, CLE_CONFIRMATION, CLE_DEBRIEF, CLE_DEVIS, CLE_PLANIFIER,
    Cadence, CadenceRelanceEtape)
from apps.visites.selectors import visites_pour_lead

User = get_user_model()

# ── Les deux fichiers lus (chemins remontés depuis ce fichier, patron CAD17) ────────────────

RACINE = Path(__file__).resolve().parents[4]
_RELANCES = RACINE / 'frontend' / 'src' / 'features' / 'crm' / 'relances'
CHEMIN_TABLE = _RELANCES / 'parcours_suivi.json'
CHEMIN_PHRASES = _RELANCES / 'suite_phrases.json'


@functools.lru_cache(maxsize=None)
def table():
    """La table du parcours, lue UNE fois (paresseusement : importer ce module ne lit rien)."""
    return json.loads(CHEMIN_TABLE.read_text(encoding='utf-8'))


@functools.lru_cache(maxsize=None)
def phrases():
    """Les codes d'effet que l'écran sait dire (``suite_phrases.json``, clé ``effets``)."""
    return json.loads(CHEMIN_PHRASES.read_text(encoding='utf-8'))['effets']


def etapes_de_la_table():
    """``{id: étape}`` dans l'ordre de la table."""
    return {etape['id']: etape for etape in table()['etapes']}


def reponses(etape):
    """Les réponses d'une étape de la table, chacune FUSIONNÉE avec son modèle."""
    modeles = table()['modeles']
    return [{**modeles[r['modele']], **r} for r in etape['reponses']]


def reponses_appel(etape):
    """Les réponses d'APPEL d'une étape (``reponses_appel`` : Répondeur, Occupé, Numéro
    invalide, A bloqué), chacune FUSIONNÉE avec son modèle. Une entrée est un identifiant
    de modèle ou un objet ``{modele, effet, suite…}`` — l'étape générique décrit les
    siennes (critique du 30/09/2026 : elles manquaient au guide et à la garde)."""
    modeles = table()['modeles']
    entrees = [e if isinstance(e, dict) else {'modele': e}
               for e in etape.get('reponses_appel', ())]
    return [{**modeles[e['modele']], **e} for e in entrees]


def reponse_de(type_id, modele):
    """La réponse fusionnée ``modele`` de l'étape ``type_id`` (le modèle est unique par étape —
    la garde de table le vérifie)."""
    for reponse in reponses(etapes_de_la_table()[type_id]):
        if reponse['modele'] == modele:
            return reponse
    raise KeyError(f'aucune réponse « {modele} » sur l’étape « {type_id} » de la table')


# ── Le vocabulaire de la table et de la spec moteur ────────────────────────────────────────

#: Les réponses de touche que la SPEC connaît (``REPONSES_TOUCHE`` + E2 ``perdu``, E4
#: ``visite_abandonnee``, E16 ``joint_telephone``).
REPONSES_SPEC = frozenset({
    'ne_plus_contacter', 'plus_tard', 'question_prix', 'devis_modifie',
    'decision_famille', 'decision_proprietaire', 'perdu', 'visite_abandonnee',
    'joint_telephone',
    # AGR520 — « En attente d'un accord (DPA / banque) ».
    'attente_accord'})
#: AGR533 — les SEULES clés qu'une variante de segment (`variantes_segment`)
#: peut remplacer : ce qui se LIT. Jamais `reponse`, `outcome`, `geste` ni
#: `suite` — la même clé serveur, le même effet. CIQ508 : `message` aussi, le
#: texte d'accusé PROPOSÉ après la réponse (CIQ503), à condition qu'il figure
#: dans ``services.CLES_MESSAGE_REPONSE`` — il n'envoie rien, la commerciale
#: clique.
CLES_VARIANTE_SEGMENT = frozenset({'label', 'precision', 'effet', 'message'})


def refus_variantes_segment(objet):
    """AGR533 — les clés interdites qu'une ``variantes_segment`` de ``objet``
    (modèle de réponse, entrée d'étape ou geste) voudrait changer : ``[]``
    quand tout va bien. La garde de table le vérifie partout."""
    from apps.crm.cadence_reponses import CLES_MESSAGE_REPONSE

    refus = []
    for segment, variante in (objet.get('variantes_segment') or {}).items():
        if not isinstance(variante, dict) or not variante:
            refus.append(f'{segment} : variante vide')
            continue
        for cle in sorted(set(variante) - CLES_VARIANTE_SEGMENT):
            refus.append(f'{segment} : « {cle} » ne peut pas changer')
        message = variante.get('message')
        if message is not None and message not in CLES_MESSAGE_REPONSE:
            refus.append(f'{segment} : « message » {message!r} est inconnu')
    return refus


#: Les gestes qu'une réponse peut ouvrir à la place d'un envoi direct.
GESTES_PLANIFICATION = frozenset({'planification', 'planification_seule', 'replanification'})
#: Les gestes SANS envoi propre : ils n'ont pas de clé de réponse (E14).
GESTES_SANS_CLE = frozenset({'planification_seule', 'replanification'})
#: AGR530 — ``agricole_sans_releve_eau`` : le lead est un pompage dont le
#: point d'eau est inconnu (groupe hydraulique manquant) — la suite annoncée
#: « devis » devient « Planifier la visite — relevé du point d'eau ».
CONTEXTE_AGRICOLE_SANS_RELEVE_EAU = 'agricole_sans_releve_eau'
CONTEXTES_VARIANTE = frozenset({'derniere_touche', 'perdu_junk',
                                CONTEXTE_AGRICOLE_SANS_RELEVE_EAU})
JOURS = frozenset({'aujourdhui', 'demain', 'date_choisie'})
ETATS_FIN = frozenset({'froid', 'perdu', 'ne_plus_contacter'})
#: La clé serveur de la réponse « Fait — passer à la suite » (aucune issue).
CLE_SANS_ISSUE = 'sans_issue'

#: Les barreaux de PROTOCOLE (jamais une étape posée par le moteur à côté du plan).
TYPES_BARREAU = frozenset({'contact_appel', 'contact_message', 'suivi_appel',
                           'suivi_message', 'reveil_appel', 'reveil_message'})
TYPES_SUIVI = frozenset({'suivi_appel', 'suivi_message'})
#: Les cadences RÉACTIVES : une seule touche du protocole ouverte à la fois (I4).
CADENCES_REACTIVES = ('contact', 'apres_devis')
#: Les réponses « Fait » qui valent « devis envoyé » (le dossier passe Devis envoyé).
TYPES_DEVIS_ENVOYE = frozenset({'devis', 'devis_modifie'})
#: Les étapes du RENDEZ-VOUS (E4 : retirées quand la visite est abandonnée).
CLES_RENDEZ_VOUS = (CLE_PLANIFIER, CLE_CONFIRMATION, CLE_DEBRIEF)

#: Famille de la table → suffixe de la méthode de ``ChaqueReponseTests``.
FAMILLES = {
    'Prise de contact': 'prise_de_contact',
    'Après l’appel (avant devis)': 'apres_l_appel',
    'Suivi de proposition (après devis)': 'suivi_de_proposition',
    'Visite technique': 'visite',
    'Réveil (dossier au Froid)': 'reveil',
    'Autres étapes': 'autres',
}

#: Le lead amené à un barreau de protocole y est sur CE rang et dans CETTE cadence : c'est
#: ce que la variante ``derniere_touche`` retouche (Paramètres) pour en faire la dernière.
ORDRE_AMENE = {'contact_message': 1, 'contact_appel': 2, 'suivi_message': 1,
               'suivi_appel': 2, 'reveil_appel': 1, 'reveil_message': 2}
CADENCE_DU_TYPE = {'contact_message': 'contact', 'contact_appel': 'contact',
                   'suivi_message': 'apres_devis', 'suivi_appel': 'apres_devis',
                   'reveil_appel': 'reveil', 'reveil_message': 'reveil'}

#: Les chemins de ``amener`` : type → (type parent, réponse jouée, options). Les cinq types
#: absents (``CHEMINS_SPECIAUX``) ont un chemin écrit en toutes lettres dans ``amener``.
CHEMINS = {
    'contact_appel': ('contact_message', 'pas_de_reponse', {}),
    'devis': ('contact_appel', 'joint', {}),
    'appel_apres_reponse': ('contact_message', 'a_repondu', {}),
    'message_creneau': ('appel_apres_reponse', 'pas_de_reponse', {}),
    'dernier_appel': ('message_creneau', 'fait', {}),
    'rappel_convenu': ('message_creneau', 'rappel', {'jours': 2}),
    'decider_suite': ('contact_appel', 'refus', {}),
    'suivi_appel': ('suivi_message', 'sans_reponse', {}),
    'question_prix': ('suivi_appel', 'question_prix', {}),
    'devis_modifie': ('suivi_appel', 'devis_modifie', {}),
    'planifier': ('contact_appel', 'visite', {'sans_date': True}),
    'confirmation': ('contact_appel', 'visite', {'jours': 5}),
    'debrief': ('confirmation', 'joint', {}),
}
CHEMINS_SPECIAUX = frozenset({'contact_message', 'suivi_message', 'reveil_appel',
                              'reveil_message', 'generique'})

# ── Le temps et les données de la société ──────────────────────────────────────────────────

#: Mercredi 30 septembre 2026, 10 h à Casablanca — le jour de l'ordre fondateur. Un
#: MERCREDI : « demain » est ouvré, et J+5 ouvré tombe le mercredi suivant.
GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
#: L'heure à laquelle l'horloge est posée quand elle avance d'un jour ouvré.
HEURE_DU_JOUR = datetime.time(10, 0)
#: L'heure convenue envoyée avec toute date (hors pause du vendredi, dans les deux fenêtres).
HEURE_CONVENUE = '11:00'
#: Les délais (jours ouvrés) des dates envoyées quand un test n'en impose pas.
JOURS_RAPPEL = 3
JOURS_VISITE = 5
JOURS_REPLANIFICATION = 7

#: Les motifs de perte que la société de chaque classe porte (Paramètres → CRM) : deux JUNK
#: (ceux que la table nomme pour « Numéro invalide » et « A bloqué »), trois commerciaux.
MOTIFS = (('Numéro invalide', True), ('Jamais répondu', True), ('Prix', False),
          ('Concurrent moins cher', False), ('Projet reporté', False))
MOTIF_COMMERCIAL = 'Prix'

A_FAIRE = RelanceEtape.Statut.A_FAIRE
TRAITEES = (RelanceEtape.Statut.FAIT, RelanceEtape.Statut.SAUTEE)

#: Numéros et références UNIQUES (règle du dépôt : jamais un littéral partagé).
_compteur = itertools.count(1)


# ── L'oracle : le type d'une touche, lu dans la table ──────────────────────────────────────

@functools.lru_cache(maxsize=None)
def _cle_par_libelle_defaut():
    """Libellé PAR DÉFAUT → clé, pour une touche posée avant la clé (gabarits « Après l'appel »
    et « Visite technique » de Paramètres — la configuration, pas le moteur)."""
    return {entree['libelle']: entree['cle']
            for cadence in (Cadence.APRES_CONTACT, Cadence.VISITE)
            for entree in CADENCES_DEFAUT[cadence]}


def type_de(etape):
    """Le type de la table de ``etape`` (un modèle, une ligne servie, tout objet portant
    ``cle``/``libelle``/``cadence``/``canal``), ou ``None`` si la table ne la connaît pas.

    Oracle INDÉPENDANT du moteur : il lit la ``reconnaissance`` de la table, dans son ordre —
    la CLÉ d'abord, puis le LIBELLÉ, puis le couple (cadence, canal) ; une reconnaissance sans
    ``canaux`` vaut pour tous les canaux."""
    libelle = (getattr(etape, 'libelle', '') or '').strip()
    cle = ((getattr(etape, 'cle', '') or '').strip()
           or _cle_par_libelle_defaut().get(libelle, ''))
    etapes = table()['etapes']
    if cle:
        for entree in etapes:
            if cle in entree['reconnaissance'].get('cles', ()):
                return entree['id']
    if libelle:
        for entree in etapes:
            if libelle in entree['reconnaissance'].get('libelles', ()):
                return entree['id']
    for entree in etapes:
        reco = entree['reconnaissance']
        if (getattr(etape, 'cadence', None) in reco.get('cadences', ())
                and (not reco.get('canaux') or getattr(etape, 'canal', None) in reco['canaux'])):
            return entree['id']
    return None


def cle_de_reponse(reponse):
    """La clé SERVEUR d'une réponse fusionnée (spec E14) : ``reponse`` si elle en porte une,
    sinon l'issue (``''`` → ``sans_issue``) ; ``None`` pour un geste sans envoi propre."""
    if reponse.get('reponse'):
        return reponse['reponse']
    if 'outcome' not in reponse and reponse.get('geste') in GESTES_SANS_CLE:
        return None
    return reponse.get('outcome') or CLE_SANS_ISSUE


def cles_attendues(type_id, canal):
    """Les clés de réponse qu'une touche de ``type_id`` DOIT servir (I5), dans l'ordre de la
    table ; les ``reponses_appel`` d'une étape générique s'y ajoutent sur un APPEL."""
    etape = etapes_de_la_table()[type_id]
    cles = [cle_de_reponse(r) for r in reponses(etape)]
    if canal == RelanceEtape.Canal.APPEL:
        cles += [cle_de_reponse(r) for r in reponses_appel(etape)]
    vues = []
    for cle in cles:
        if cle is not None and cle not in vues:
            vues.append(cle)
    return vues


# ── Les cas de ``ChaqueReponseTests`` : toute la table, famille par famille ────────────────

@dataclass(frozen=True)
class Cas:
    """UNE réponse de la table, dans UN contexte : ``base`` (la suite ``suite``),
    ``sans_date`` (« date pas encore fixée »), ou le contexte d'une ``variante``."""
    type_id: str
    reponse: dict
    contexte: str
    suite: dict
    #: Une réponse d'APPEL seulement (``reponses_appel``) : la touche amenée doit en être un.
    appel_seulement: bool = False

    @property
    def nom(self):
        return f'{self.type_id} / {self.reponse["modele"]} / {self.contexte}'


def cas_de_la_famille(famille):
    """Chaque réponse de chaque étape de ``famille``, puis sa suite « sans date » et chacune
    de ses variantes — l'ordre de la table."""
    cas = []
    for etape in table()['etapes']:
        if etape['famille'] != famille:
            continue
        for reponse in reponses(etape):
            cas.append(Cas(etape['id'], reponse, 'base', reponse['suite']))
            if 'suite_sans_date' in reponse:
                cas.append(Cas(etape['id'], reponse, 'sans_date', reponse['suite_sans_date']))
            for variante in reponse.get('variantes', ()):
                cas.append(Cas(etape['id'], reponse, variante['contexte'], variante['suite']))
        # Les réponses d'APPEL décrites par la table (suite connue) : jouées aussi.
        for reponse in reponses_appel(etape):
            if 'suite' not in reponse:
                continue
            cas.append(Cas(etape['id'], reponse, 'base', reponse['suite'], True))
            for variante in reponse.get('variantes', ()):
                cas.append(Cas(etape['id'], reponse, variante['contexte'], variante['suite'],
                               True))
    return cas


def _clef_de_tri(etape):
    """L'ordre de ``services._prochaine_touche_a_faire`` : échéance (sans heure en dernier),
    date, rang."""
    return (etape.due_at is None, etape.due_at or GEL, etape.due_date, etape.ordre)


# ── La base de tous les parcours ───────────────────────────────────────────────────────────

class ParcoursBase(TestCase):
    """Société, profil, les 7 gabarits, les motifs de perte, un responsable en Bearer, une
    horloge gelée (mercredi 10 h) — et les gestes du parcours, TOUS par l'API réelle.

    Le temps n'avance que par des blocs ``frozen(...)`` IMBRIQUÉS (``avancer_a``), jamais par
    ``tick``/``move_to`` ; ``cas_isole`` rend l'horloge, les données et les réglages à leur état
    d'avant (point de sauvegarde annulé) : chaque cas part d'un lead neuf, le même mercredi."""

    slug = 'parcours-base'

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom=f'Parcours {cls.slug}', slug=cls.slug)
        if not CompanyProfile.objects.filter(company=cls.company).exists():
            CompanyProfile.objects.create(company=cls.company)
        cls.acteur = User.objects.create_user(
            username=f'{cls.slug}-resp', password='x', role_legacy='responsable',
            company=cls.company)
        # Le conseiller qui REPREND un dossier (touche de passation) : rôle normal, donc hors
        # du tourniquet d'attribution — les leads créés restent au responsable.
        cls.relais = User.objects.create_user(
            username=f'{cls.slug}-relais', password='x', company=cls.company)
        for nom, junk in MOTIFS:
            MotifPerte.objects.create(company=cls.company, nom=nom, est_junk=junk)
        # Comme en production : les 7 gabarits existent (seedés au premier usage).
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(cls.company, cadence)

    def __getstate__(self):
        """Django ``--parallel`` pickle un SOUS-TEST en échec avec son instance de test
        (``RemoteTestResult.addSubTest``) : le client d'API (fermetures de middleware) et
        la pile d'horloges gelées ne se picklent pas — sans ceci, le premier sous-test
        rouge faisait planter le lanceur (« Can't pickle local object … inner », CI du
        30/09/2026) au lieu d'imprimer le chemin du cas. Copie allégée, l'instance vivante
        garde tout. Django envoie AUSSI les instances aux processus (``--parallel`` :
        les sous-suites sont picklées AVANT ``setUp``) : les attributs d'unittest restent
        présents, vidés — sans quoi ``doCleanups`` plantait (« no attribute _cleanups »)."""
        etat = self.__dict__.copy()
        for cle in ('api', '_pile'):
            etat.pop(cle, None)
        if '_cleanups' in etat:
            etat['_cleanups'] = []
        if '_outcome' in etat:
            etat['_outcome'] = None
        return etat

    def setUp(self):
        super().setUp()
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self._pile = ExitStack()
        self.addCleanup(self._refermer_horloge)
        self._instant = GEL
        self._chemin = []
        self.api = APIClient()
        self._jeton()

    # ── l'horloge ──

    def _refermer_horloge(self):
        self._pile.close()

    def _jeton(self):
        """Un jeton frais : il est daté, et l'horloge gelée bouge (sinon il expirerait)."""
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def aujourdhui(self):
        """La date locale (Casablanca) de l'horloge gelée."""
        return timezone.now().astimezone(horaires.CASABLANCA).date()

    def jour_ouvre(self, n):
        """Le n-ième jour ouvré après aujourd'hui (calendrier de la société)."""
        return ajouter_jours_ouvres(self.aujourdhui(), n, self.company)

    def demain(self):
        return self.jour_ouvre(1)

    def avancer_a(self, instant):
        """Avance l'horloge à ``instant`` par un bloc ``frozen`` IMBRIQUÉ (jamais en arrière)."""
        if instant is None or instant <= self._instant:
            return
        self._pile.enter_context(frozen(instant))
        self._instant = instant
        self._jeton()

    def avancer_d_un_jour_ouvre(self):
        self.avancer_a(datetime.datetime.combine(
            self.jour_ouvre(1), HEURE_DU_JOUR, tzinfo=horaires.CASABLANCA))

    @contextmanager
    def cas_isole(self, entete=''):
        """UN cas : un point de sauvegarde ANNULÉ à la fin (données et réglages), une horloge
        repartie de l'instant d'avant, un chemin de rejeu vierge."""
        pile, instant, chemin = self._pile, self._instant, self._chemin
        self._pile = ExitStack()
        self._chemin = [entete] if entete else []
        try:
            with transaction.atomic():
                try:
                    yield
                finally:
                    transaction.set_rollback(True)
        finally:
            self._pile.close()
            self._pile, self._instant, self._chemin = pile, instant, chemin
            self._jeton()

    # ── les messages : toujours le chemin, pour rejouer le cas à la main ──

    def _journal(self, texte):
        self._chemin.append(texte)

    def decrire(self, lead):
        ouvertes = self.ouvertes(lead)
        if not ouvertes:
            return 'aucune'
        return '; '.join(
            f'{type_de(e) or "?"}[{e.cadence}/{e.ordre}/{e.cle or "-"}] « {e.libelle} » '
            f'le {e.due_date:%d/%m/%Y}' for e in ouvertes)

    def msg(self, message, lead=None):
        parties = [message]
        if lead is not None:
            parties.append(f'touches ouvertes : {self.decrire(lead)}')
        if self._chemin:
            parties.append('chemin : ' + ' → '.join(self._chemin))
        return ' — '.join(parties)

    # ── l'API (I1 à chaque appel) ──

    def appel(self, methode, url, corps=None, *, quatre_cents='interdit'):
        """Un appel à l'API réelle. I1 : jamais de 5xx. ``quatre_cents`` : ``interdit`` (un 4xx
        est un échec), ``attendu`` (un 2xx est un échec) ou ``tolere`` ; tout 4xx accepté doit
        porter ``erreurs`` avec un message non vide."""
        try:
            if methode == 'get':
                resp = self.api.get(url)
            else:
                resp = getattr(self.api, methode)(url, corps or {}, format='json')
        except Exception:  # noqa: BLE001 — I1 : le client de test RELÈVE l'erreur serveur
            self.fail(self.msg(f'I1 — {methode.upper()} {url} {corps or ""} : erreur serveur\n'
                               f'{traceback.format_exc()}'))
        donnees = getattr(resp, 'data', None)
        self.assertLess(resp.status_code, 500, self.msg(
            f'I1 — {methode.upper()} {url} {corps or ""} : HTTP {resp.status_code}'))
        if resp.status_code >= 400:
            if quatre_cents == 'interdit':
                self.fail(self.msg(f'{methode.upper()} {url} {corps or ""} refusé : '
                                   f'HTTP {resp.status_code} {donnees}'))
            self.verifier_refus_nomme(resp)
        elif quatre_cents == 'attendu':
            self.fail(self.msg(f'{methode.upper()} {url} {corps or ""} devait être refusé : '
                               f'HTTP {resp.status_code}'))
        return resp

    def verifier_refus_nomme(self, resp):
        """I1 — un refus porte ``erreurs`` : au moins un champ, chacun avec un message."""
        donnees = resp.data if isinstance(resp.data, dict) else {}
        erreurs = donnees.get('erreurs')
        if erreurs is None and donnees:
            # `visites/planifier/` nomme le champ SANS enveloppe (`{champ: [message]}`,
            # contrat `lead_visite_planifier.json`) : la règle « le refus nomme le champ »
            # est tenue, c'est cette forme-là qu'on lit.
            erreurs = {champ: message for champ, message in donnees.items()
                       if champ != 'detail'}
        self.assertIsInstance(erreurs, dict, self.msg(
            f'I1 — refus HTTP {resp.status_code} sans « erreurs » : {resp.data}'))
        self.assertTrue(erreurs, self.msg(f'I1 — « erreurs » vide : {resp.data}'))
        for champ, message in erreurs.items():
            textes = message if isinstance(message, (list, tuple)) else [message]
            self.assertTrue(textes and all(str(t).strip() for t in textes), self.msg(
                f'I1 — « erreurs.{champ} » sans message : {resp.data}'))

    # ── les lectures ──

    def ouvertes(self, lead):
        """Les touches À FAIRE du lead, triées comme ``services._prochaine_touche_a_faire``."""
        return list(lead.relance_etapes.filter(statut=A_FAIRE).order_by(
            F('due_at').asc(nulls_last=True), 'due_date', 'ordre', 'pk'))

    def du_type(self, lead, type_id):
        return [e for e in self.ouvertes(lead) if type_de(e) == type_id]

    def unique(self, lead, type_id):
        """L'UNIQUE touche ouverte de ce type (échec lisible sinon)."""
        trouvees = self.du_type(lead, type_id)
        self.assertEqual(len(trouvees), 1, self.msg(
            f'une (et une seule) touche « {type_id} » ouverte attendue, '
            f'{len(trouvees)} trouvée(s)', lead))
        return trouvees[0]

    def premiere(self, lead, type_id):
        """La PLUS PROCHE touche ouverte de ce type. Pour les réveils, posés ENSEMBLE : un
        gabarit à trois réveils en ouvre deux du même canal à la fois."""
        trouvees = self.du_type(lead, type_id)
        self.assertTrue(trouvees, self.msg(f'aucune touche « {type_id} » ouverte', lead))
        return trouvees[0]

    def suivis_ouverts(self, lead):
        return [e for e in self.ouvertes(lead) if type_de(e) in TYPES_SUIVI]

    def visite_a_venir(self, lead):
        aujourdhui = self.aujourdhui().isoformat()
        return any(v['date_prevue'] and v['date_prevue'] >= aujourdhui
                   for v in visites_pour_lead(lead))

    def ordre_max_actif(self, cadence):
        return max(CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=cadence, actif=True).values_list('ordre', flat=True),
            default=0)

    # ── les gestes (tous par l'API réelle, sauf l'envoi du devis et le retour terrain) ──

    def creer_lead(self):
        """``POST leads/`` (nom et téléphone UNIQUES) : la prise de contact démarre seule."""
        n = next(_compteur)
        resp = self.appel('post', '/api/django/crm/leads/', {
            'nom': f'Parcours {self.slug} {n}', 'telephone': f'+21266{n:07d}'})
        lead = Lead.objects.get(pk=resp.data['id'])
        self._journal(f'lead #{lead.pk} créé le {self.aujourdhui():%d/%m/%Y}')
        self.verifier_invariants(lead)
        return lead

    def corps_de(self, reponse, *, date=None, motif=None, junk=False, motif_refus=None):
        """Le corps du « Fait », construit depuis la réponse FUSIONNÉE de la table."""
        corps = {}
        if reponse.get('reponse'):
            corps['reponse'] = reponse['reponse']
        elif reponse.get('outcome'):
            corps['outcome'] = reponse['outcome']
        if reponse.get('note'):
            corps['note'] = reponse['note']
        if reponse.get('date'):
            corps['rappel_le'] = date.isoformat()
            corps['rappel_heure'] = HEURE_CONVENUE
        if reponse.get('raison'):
            # CIQ508 — la raison d'attente est OBLIGATOIRE : le rejeu envoie la
            # première raison de la liste de la table (jamais une valeur
            # retapée ici).
            corps['raison_attente'] = reponse['raisons'][0]['valeur']
        if reponse.get('motif_perte') and motif:
            corps['motif_perte'] = motif
        if reponse.get('motif_refus') and motif_refus:
            corps['motif_refus'] = motif_refus
        if junk:
            corps['perdu_junk'] = reponse['junk']
        return corps

    def date_par_defaut(self, reponse, sans_date=False):
        """La date qu'un test envoie quand il n'en impose pas (jours OUVRÉS)."""
        geste = reponse.get('geste')
        if reponse.get('date'):
            return self.jour_ouvre(JOURS_RAPPEL)
        if geste == 'replanification':
            return self.jour_ouvre(JOURS_REPLANIFICATION)
        if geste in GESTES_PLANIFICATION and not sans_date:
            return self.jour_ouvre(JOURS_VISITE)
        return None

    def repondre(self, etape, reponse, *, date=None, motif=None, junk=False,
                 motif_refus=None, sans_date=False, quatre_cents='interdit'):
        """Joue ``reponse`` (FUSIONNÉE) sur ``etape`` par l'API réelle ; ``(resp, envoye)``.

        Un ``geste`` de planification poste ``leads/<id>/visites/planifier/`` avec ``etape``,
        ``note_etape`` (et ``replanifier``) — E18 ; « date pas encore fixée » (``sans_date``)
        est le ``fait`` ordinaire avec ``outcome=visite_acceptee`` ; tout le reste est le
        ``fait`` de la touche (``outcome`` | ``reponse``, ``note``, ``rappel_le``,
        ``motif_perte``, ``motif_refus``, ``perdu_junk``)."""
        geste = reponse.get('geste')
        if date is None:
            date = self.date_par_defaut(reponse, sans_date=sans_date)
        envoye = {'modele': reponse['modele'], 'geste': None if sans_date else geste,
                  'date': date, 'date_prevue': None, 'motif': motif, 'sans_date': sans_date}
        fait = f'/api/django/crm/relance-etapes/{etape.pk}/fait/'
        if sans_date:
            url, corps = fait, {'outcome': reponse['outcome']}
        elif geste in GESTES_PLANIFICATION:
            url = f'/api/django/crm/leads/{etape.lead_id}/visites/planifier/'
            corps = {'date_prevue': date.isoformat(), 'etape': etape.pk,
                     'note_etape': f'Garde de parcours — {reponse["label"]}'}
            if geste == 'replanification':
                corps['replanifier'] = True
            envoye['date_prevue'] = date
        else:
            url = fait
            corps = self.corps_de(reponse, date=date, motif=motif, junk=junk,
                                  motif_refus=motif_refus)
            if junk:
                envoye['motif'] = reponse['junk']
        details = ''.join((
            ' (date pas encore fixée)' if sans_date else '',
            f' le {date:%d/%m/%Y}' if date is not None and not sans_date else '',
            ' + perdu (junk)' if junk else '',
            f' motif « {motif} »' if motif and not junk else '',
            f' motif de refus « {motif_refus} »' if motif_refus else ''))
        self._journal(f'[{self.aujourdhui():%d/%m}] {type_de(etape)} « {etape.libelle} » → '
                      f'« {reponse["label"]} »{details}')
        resp = self.appel('post', url, corps, quatre_cents=quatre_cents)
        self._chemin[-1] += f' (HTTP {resp.status_code})'
        return resp, envoye

    def sans_date(self, etape, reponse):
        """« Date pas encore fixée » : le ``fait`` ordinaire avec ``outcome=visite_acceptee``
        (l'étape « Planifier la visite technique convenue » est posée)."""
        return self.repondre(etape, reponse, sans_date=True)

    def jouer(self, lead, etape, modele, *, date=None, motif=None, junk=False,
              motif_refus=None, sans_date=False):
        """La réponse ``modele`` de la table sur ``etape`` — puis les invariants."""
        reponse = reponse_de(type_de(etape), modele)
        if reponse.get('motif_perte') and motif is None:
            motif = MOTIF_COMMERCIAL
        resp, envoye = self.repondre(etape, reponse, date=date, motif=motif, junk=junk,
                                     motif_refus=motif_refus, sans_date=sans_date)
        self.verifier_invariants(lead, resp=resp)
        return resp, envoye

    def envoyer_devis(self, lead):
        """Un devis brouillon (ORM, avec son client) ENVOYÉ depuis l'ERP : le service unique
        ``mark_devis_sent`` émet ``devis_sent`` (patron ``tests_mry34_filet_joint``)."""
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        from apps.ventes.services import mark_devis_sent

        n = next(_compteur)
        client = Client.objects.create(
            company=self.company, nom=f'Client parcours {n}',
            email=f'parcours-{self.slug}-{n}@example.com')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-PARC-{n:05d}', client=client, lead=lead,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20.00'))
        mark_devis_sent(devis=devis, user=self.acteur)
        self._journal(f'[{self.aujourdhui():%d/%m}] devis {devis.reference} envoyé depuis l’ERP')
        self.verifier_invariants(lead)
        return devis

    def signal_proposition_rouverte(self, lead):
        """Le client a ROUVERT sa proposition (signal CAD130, observé par la tâche planifiée
        `apps.ventes.scheduled` qui appelle ce même service) : la touche générique d'APPEL
        « Proposition rouverte — appeler » est posée dans la file, à côté du suivi — le
        chemin réel vers une étape générique qui est un appel (la passation est un message ;
        un rappel demandé pendant un plan en cours DÉPLACE la touche suivante, il n'en pose
        pas)."""
        from apps.crm.services import SIGNAL_PROPOSITION_ROUVERTE, poser_touche_signal

        touche = poser_touche_signal(lead, SIGNAL_PROPOSITION_ROUVERTE, user=self.acteur)
        self.assertIsNotNone(touche, self.msg('le signal « proposition rouverte » n’a rien posé', lead))
        self._journal(f'[{self.aujourdhui():%d/%m}] proposition rouverte par le client (signal)')
        self.verifier_invariants(lead)

    def amener_generique_appel(self):
        """``(lead, touche)`` : un lead en suivi de proposition avec une touche générique
        d'APPEL ouverte (proposition rouverte) — pour les réponses d'appel de l'étape
        générique (Répondeur, Occupé, Numéro invalide, A bloqué)."""
        lead, _suivi = self.amener('suivi_message')
        self.signal_proposition_rouverte(lead)
        appels = [e for e in self.du_type(lead, 'generique')
                  if e.canal == RelanceEtape.Canal.APPEL]
        self.assertEqual(len(appels), 1, self.msg(
            'une (et une seule) touche générique d’APPEL ouverte attendue', lead))
        return lead, appels[0]

    def reattribuer(self, lead):
        """« Réattribuer » (action en masse ``reassign`` de l'API) : le dossier change de
        conseiller, la touche de PASSATION est posée (``poser_touche_passation``) et la file
        recalée — le chemin réel de la passation."""
        lead.refresh_from_db()
        nouveau = self.relais if lead.owner_id != self.relais.pk else self.acteur
        self.appel('post', '/api/django/crm/leads/bulk/', {
            'ids': [lead.pk], 'action': 'reassign', 'owner': nouveau.pk})
        self._journal(f'[{self.aujourdhui():%d/%m}] dossier réattribué à {nouveau.username}')
        self.verifier_invariants(lead)

    def retour_de_visite(self, lead, qualification=None):
        """Le technicien saisit son retour : ``core.events.visite_terminee`` (patron
        ``tests_visite_cadence``), sur la visite du lead."""
        from apps.visites.models import VisiteTerrain
        from core.events import visite_terminee

        lignes = visites_pour_lead(lead)
        self.assertTrue(lignes, self.msg('retour de visite sans visite', lead))
        visite = VisiteTerrain.objects.get(pk=lignes[0]['id'])
        visite_terminee.send(
            sender=VisiteTerrain, visite=visite, lead_id=lead.id, user=self.acteur,
            retour={'notes': 'Retour terrain de la garde de parcours.',
                    'commentaires_photos': [], 'nb_photos': 0},
            qualification=qualification)
        self._journal(f'[{self.aujourdhui():%d/%m}] retour de visite saisi')
        self.verifier_invariants(lead)

    # ── amener : un lead NEUF jusqu'à une étape, par le plus court chemin RÉEL ──

    def amener(self, type_id):
        """``(lead, touche)`` : un lead neuf conduit jusqu'à une touche de ``type_id``.

        Une touche amenée datée d'un jour à venir n'est PAS déplacée : le serveur accepte le
        geste en avance, et c'est ce que la garde prouve. Seuls les réveils avancent
        l'horloge (leur échéance est à des semaines)."""
        if type_id == 'contact_message':
            lead = self.creer_lead()
            return lead, self.unique(lead, 'contact_message')
        if type_id == 'suivi_message':
            lead, _devis = self.amener('devis')
            self.envoyer_devis(lead)
            return lead, self.unique(lead, 'suivi_message')
        if type_id == 'generique':
            lead, _suivi = self.amener('suivi_message')
            self.reattribuer(lead)
            return lead, self.unique(lead, 'generique')
        if type_id == 'reveil_appel':
            lead, _message = self.amener('contact_message')
            self.touches_de_contact_sans_reponse(lead)
            etape = self.premiere(lead, 'reveil_appel')
            self.avancer_a(etape.due_at)
            return lead, etape
        if type_id == 'reveil_message':
            lead, reveil = self.amener('reveil_appel')
            self.jouer(lead, reveil, 'pas_de_reponse')
            etape = self.premiere(lead, 'reveil_message')
            self.avancer_a(etape.due_at)
            return lead, etape
        parent, modele, options = CHEMINS[type_id]
        lead, etape = self.amener(parent)
        date = (self.jour_ouvre(options['jours']) if 'jours' in options else None)
        self.jouer(lead, etape, modele, date=date,
                   sans_date=options.get('sans_date', False))
        return lead, self.unique(lead, type_id)

    def touches_de_contact_sans_reponse(self, lead):
        """Toutes les touches de la prise de contact (onze avec le gabarit livré) closes
        « Pas de réponse », chacune à son échéance : le dossier part au Froid, réveils posés."""
        nombre = CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='contact', actif=True).count()
        for _rang in range(nombre):
            contact = [e for e in self.ouvertes(lead) if e.cadence == 'contact']
            self.assertEqual(len(contact), 1, self.msg(
                'une touche de prise de contact ouverte attendue', lead))
            self.avancer_a(contact[0].due_at)
            self.jouer(lead, contact[0], 'pas_de_reponse')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD, self.msg(
            'prise de contact épuisée sans réponse : le dossier doit partir au Froid', lead))

    # ── les réglages (Paramètres) d'un contexte de variante ──

    def preparer_gabarits(self, type_id, contexte):
        """Rend la touche amenée DERNIÈRE de sa cadence (``derniere_touche``) — ou, pour la
        suite de base d'un barreau, s'assure qu'elle ne l'est PAS — par le gabarit de la
        société (Paramètres → CRM), jamais par une touche insérée. Le point de sauvegarde de
        ``cas_isole`` rend le réglage d'origine."""
        if type_id not in ORDRE_AMENE or contexte == 'sans_date':
            return
        cadence, ordre = CADENCE_DU_TYPE[type_id], ORDRE_AMENE[type_id]
        suivants = CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=cadence, actif=True, ordre__gt=ordre)
        if contexte == 'derniere_touche':
            suivants.update(actif=False)
        elif not suivants.exists():
            # Le gabarit livré fait de ce barreau le dernier (le réveil J60) : un barreau de
            # plus, comme une société peut l'ajouter, pour jouer la suite ordinaire.
            CadenceRelanceEtape.objects.create(
                company=self.company, cadence=cadence, ordre=ordre + 1,
                delai_jours=90, canal='appel', libelle='Réveil J90',
                template_cle='reveil_a1')

    # ── la photo d'avant la réponse ──

    def photo(self, lead, etape):
        lead.refresh_from_db()
        ouvertes = self.ouvertes(lead)
        consommes = [e.ordre for e in lead.relance_etapes.filter(
            cadence='apres_devis', statut__in=TRAITEES) if type_de(e) in TYPES_SUIVI]
        return SimpleNamespace(
            autres={(e.pk, e.due_date) for e in ouvertes if e.pk != etape.pk},
            suivis_ouverts={e.pk for e in ouvertes if type_de(e) in TYPES_SUIVI},
            devis_ouvertes={e.pk for e in ouvertes if cle_de(e) == CLE_DEVIS},
            suivi_consomme=max(consommes, default=0),
            visite_a_venir=self.visite_a_venir(lead))

    def suivi_pendant(self, avant):
        """Un suivi de proposition est-il PENDANT : un barreau ouvert, ou un plan entamé et
        pas allé au bout (il doit alors REPRENDRE, jamais redémarrer) ?"""
        if avant.suivis_ouverts:
            return True
        return 0 < avant.suivi_consomme < self.ordre_max_actif('apres_devis')

    # ── verifier_suite : ce que la table promet, constaté en base ──

    def _jour_attendu(self, jour, envoye):
        if jour == 'aujourdhui':
            return self.aujourdhui()
        if jour == 'demain':
            return self.demain()
        return envoye['date']

    def _verifier_etape_posee(self, lead, ouvertes, suite, envoye, titre):
        if suite.get('id_etape'):
            nom = suite['id_etape']
            posees = [e for e in ouvertes if type_de(e) == nom]
        else:
            nom = suite['cle']
            posees = [e for e in ouvertes if cle_de(e) == nom]
        self.assertEqual(len(posees), 1, self.msg(
            f'{titre} : UNE touche ouverte « {nom} » attendue, {len(posees)} trouvée(s)', lead))
        if suite.get('jour'):
            attendu = self._jour_attendu(suite['jour'], envoye)
            self.assertEqual(posees[0].due_date, attendu, self.msg(
                f'{titre} : « {nom} » attendue le {attendu} ({suite["jour"]})', lead))

    def verifier_suite(self, lead, etape, reponse, suite, avant, envoye, type_id):
        """La suite ``suite`` de la table, après la réponse ``reponse`` sur ``etape``."""
        lead.refresh_from_db()
        etape.refresh_from_db()
        ouvertes = self.ouvertes(lead)
        nature = suite['type']
        titre = f'{type_id} / « {reponse["label"]} » → {nature}'
        # La touche répondue est close — sauf « même étape », et la replanification (la
        # touche de visite suit la nouvelle date : elle reste ouverte).
        if nature != 'meme_etape' and envoye['geste'] != 'replanification':
            self.assertNotEqual(etape.statut, A_FAIRE, self.msg(
                f'{titre} : la touche répondue est restée à faire', lead))
        if reponse.get('note') and not reponse.get('reponse'):
            self.assertIn(reponse['note'], etape.note or '', self.msg(
                f'{titre} : la note « {reponse["note"]} » n’est pas gardée sur la touche'))
        if nature == 'etape':
            self._verifier_etape_posee(lead, ouvertes, suite, envoye, titre)
        elif nature == 'barreau_suivant':
            suivants = [e for e in ouvertes if e.cadence == etape.cadence
                        and e.ordre > etape.ordre and type_de(e) in TYPES_BARREAU]
            self.assertTrue(suivants, self.msg(
                f'{titre} : aucune touche suivante du protocole « {etape.cadence} »', lead))
            if suite.get('jour') == 'date_choisie':
                self.assertTrue(any(e.due_date == envoye['date'] for e in suivants), self.msg(
                    f'{titre} : la touche suivante n’est pas au {envoye["date"]}', lead))
        elif nature == 'meme_etape':
            self.assertEqual(etape.statut, A_FAIRE, self.msg(
                f'{titre} : la même touche devait rester à faire', lead))
            self.assertEqual(etape.due_date, envoye['date'], self.msg(
                f'{titre} : la touche n’est pas déplacée au {envoye["date"]}', lead))
        elif nature == 'suivi_proposition':
            suivis = [e for e in ouvertes
                      if e.cadence == 'apres_devis' and type_de(e) in TYPES_SUIVI]
            self.assertTrue(suivis, self.msg(f'{titre} : aucun suivi de proposition ouvert', lead))
            if avant.suivi_consomme:
                self.assertTrue(all(e.ordre > avant.suivi_consomme for e in suivis), self.msg(
                    f'{titre} : le suivi a REDÉMARRÉ au lieu de reprendre après le barreau '
                    f'{avant.suivi_consomme}', lead))
            if type_id in TYPES_DEVIS_ENVOYE and reponse['modele'] == 'fait':
                self.assertEqual(lead.stage, stages.QUOTE_SENT, self.msg(
                    f'{titre} : le dossier n’est pas « Devis envoyé »', lead))
        elif nature in ('reprise', 'reprise_ou'):
            cle = suite.get('cle', CLE_DEVIS)
            if self.suivi_pendant(avant):
                suivis = {e.pk for e in ouvertes if type_de(e) in TYPES_SUIVI}
                self.assertTrue(suivis, self.msg(f'{titre} : le suivi pendant n’a pas repris', lead))
                self.assertTrue(avant.suivis_ouverts <= suivis, self.msg(
                    f'{titre} : un barreau du suivi ouvert avant la réponse a disparu', lead))
                devis = {e.pk for e in ouvertes if cle_de(e) == CLE_DEVIS}
                self.assertFalse(devis - avant.devis_ouvertes, self.msg(
                    f'{titre} : étape devis ajoutée alors qu’un suivi était pendant', lead))
                if not avant.suivis_ouverts:
                    self.assertTrue(all(
                        e.ordre > avant.suivi_consomme for e in ouvertes
                        if type_de(e) in TYPES_SUIVI), self.msg(
                        f'{titre} : le suivi a redémarré au lieu de reprendre', lead))
            else:
                self._verifier_etape_posee(
                    lead, ouvertes, {'cle': cle, 'jour': suite.get('jour')}, envoye, titre)
        elif nature == 'visite_planifiee':
            self._verifier_visite_planifiee(lead, ouvertes, envoye, titre)
        elif nature == 'inchange':
            self.assertEqual({(e.pk, e.due_date) for e in ouvertes}, avant.autres, self.msg(
                f'{titre} : les autres touches ouvertes ont bougé', lead))
        elif nature == 'fin':
            self._verifier_fin(lead, ouvertes, suite['etat'], envoye, titre)
        else:
            self.fail(f'suite inconnue « {nature} »')
        self._verifier_rendez_vous(lead, ouvertes, reponse, avant, titre)

    def _verifier_visite_planifiee(self, lead, ouvertes, envoye, titre):
        date = envoye.get('date_prevue')
        self.assertIsNotNone(date, self.msg(f'{titre} : aucune date de visite envoyée'))
        visites = visites_pour_lead(lead)
        self.assertTrue(any(v['date_prevue'] == date.isoformat() for v in visites), self.msg(
            f'{titre} : aucune visite au {date} ({visites})', lead))
        if envoye['geste'] == 'replanification':
            self.assertEqual(len(visites), 1, self.msg(
                f'{titre} : la replanification a créé une seconde visite ({visites})', lead))
        for cle in (CLE_CONFIRMATION, CLE_DEBRIEF):
            self.assertEqual(sum(1 for e in ouvertes if cle_de(e) == cle), 1, self.msg(
                f'{titre} : « {cle} » doit être ouverte (une fois)', lead))
        self.assertFalse([e for e in ouvertes if cle_de(e) == CLE_PLANIFIER], self.msg(
            f'{titre} : une étape « planifier » reste ouverte', lead))
        self.assertEqual(lead.visite_prevue_le, date, self.msg(
            f'{titre} : la fiche ne porte pas la date de visite', lead))

    def _verifier_fin(self, lead, ouvertes, etat, envoye, titre):
        if etat == 'froid':
            self.assertEqual(lead.stage, stages.COLD, self.msg(
                f'{titre} : le dossier n’est pas au Froid', lead))
            self.assertFalse([e for e in ouvertes if e.cadence != 'reveil'], self.msg(
                f'{titre} : une touche hors réveil reste ouverte', lead))
            return
        self.assertFalse(ouvertes, self.msg(f'{titre} : une touche reste ouverte', lead))
        if etat == 'perdu':
            self.assertTrue(lead.perdu, self.msg(f'{titre} : le lead n’est pas perdu', lead))
            if envoye.get('motif'):
                self.assertEqual(lead.motif_perte, envoye['motif'], self.msg(
                    f'{titre} : motif de perte « {lead.motif_perte} »', lead))
        else:
            self.assertTrue(lead.ne_plus_contacter, self.msg(
                f'{titre} : la case « ne plus contacter » n’est pas cochée', lead))

    def _verifier_rendez_vous(self, lead, ouvertes, reponse, avant, titre):
        """E4 — « visite abandonnée » : le rendez-vous perd sa date, ses étapes sont retirées.
        E21 — « Refus », « Perdu », « Ne plus me contacter » : un rendez-vous à venir est
        annulé aussi (le technicien ne se déplace pas chez un client qui a refusé)."""
        abandon = reponse.get('reponse') == 'visite_abandonnee'
        arret = (reponse.get('outcome') == 'refuse' and not reponse.get('reponse')) \
            or reponse.get('reponse') in ('ne_plus_contacter', 'perdu')
        if not abandon and not (arret and avant.visite_a_venir):
            return
        self.assertIsNone(lead.visite_prevue_le, self.msg(
            f'{titre} : la fiche garde la date du rendez-vous', lead))
        self.assertFalse([v for v in visites_pour_lead(lead) if v['date_prevue']], self.msg(
            f'{titre} : le rendez-vous garde sa date ({visites_pour_lead(lead)})', lead))
        if abandon:
            self.assertFalse([e for e in ouvertes if cle_de(e) in CLES_RENDEZ_VOUS], self.msg(
                f'{titre} : une étape du rendez-vous reste ouverte', lead))

    # ── les INVARIANTS, après chaque geste ──

    def verifier_invariants(self, lead, resp=None):
        """I1 (à chaque appel, ``appel``) ; I2 à I7 sur l'état du lead ; I7 sur ``resp``, la
        réponse d'un « Fait » ou d'une planification."""
        lead.refresh_from_db()
        ouvertes = self.ouvertes(lead)
        actif = not (lead.perdu or lead.is_archived or lead.ne_plus_contacter
                     or lead.stage in (stages.SIGNED, stages.COLD))
        if actif:
            self.assertTrue(ouvertes, self.msg(
                f'I2 — lead actif ({lead.stage}) sans aucune touche ouverte', lead))
        vues = set()
        for etape in ouvertes:
            cle = cle_de(etape)
            clef = ('clé', cle) if cle else ('libellé', (etape.libelle or '').strip())
            self.assertNotIn(clef, vues, self.msg(
                f'I3 — deux touches ouvertes de même {clef[0]} « {clef[1]} »', lead))
            vues.add(clef)
        for cadence in CADENCES_REACTIVES:
            barreaux = [e for e in ouvertes
                        if e.cadence == cadence and type_de(e) in TYPES_BARREAU]
            self.assertLessEqual(len(barreaux), 1, self.msg(
                f'I4 — {len(barreaux)} barreaux du protocole « {cadence} » ouverts', lead))
        attendue = ouvertes[0].due_date if ouvertes else None
        self.assertEqual(lead.relance_date, attendue, self.msg(
            f'I6 — relance_date {lead.relance_date} ≠ la plus proche touche ({attendue})', lead))
        self._verifier_suites_servies(lead)
        if resp is not None and 200 <= resp.status_code < 300:
            self._verifier_prochaine_touche(lead, resp.data, ouvertes)

    def _verifier_suites_servies(self, lead):
        """I5 — chaque touche ouverte sert, pour CHAQUE réponse de son type dans la table,
        une liste de codes non vide, et chaque code a sa phrase à l'écran."""
        resp = self.appel('get', f'/api/django/crm/relance-etapes/?lead={lead.pk}')
        for ligne in resp.data['results']:
            if ligne['statut'] != A_FAIRE:
                continue
            touche = SimpleNamespace(cle=ligne.get('cle') or '', libelle=ligne['libelle'],
                                     cadence=ligne['cadence'], canal=ligne['canal'])
            type_id = type_de(touche)
            self.assertIsNotNone(type_id, self.msg(
                f'I5 — touche ouverte hors de la table : {ligne["cadence"]}/{ligne["canal"]} '
                f'« {ligne["libelle"]} »', lead))
            suites = ligne.get('suites') or {}
            for cle in cles_attendues(type_id, touche.canal):
                codes = suites.get(cle)
                self.assertTrue(codes, self.msg(
                    f'I5 — {type_id} « {ligne["libelle"]} » : la réponse « {cle} » n’a aucune '
                    f'suite servie (servies : {sorted(suites)})', lead))
                inconnus = [code for code in codes if code not in phrases()]
                self.assertFalse(inconnus, self.msg(
                    f'I5 — {type_id} « {cle} » : codes sans phrase {inconnus}', lead))

    def _verifier_prochaine_touche(self, lead, donnees, ouvertes):
        """I7 — ``prochaine_touche`` désigne la plus proche touche ouverte (``null`` sinon),
        avec son libellé et sa clé (E9)."""
        self.assertIsInstance(donnees, dict, self.msg('I7 — réponse illisible'))
        self.assertIn('prochaine_touche', donnees, self.msg(
            f'I7 — la réponse ne porte pas « prochaine_touche » ({sorted(donnees)})', lead))
        prochaine = donnees['prochaine_touche']
        if not ouvertes:
            self.assertIsNone(prochaine, self.msg(
                f'I7 — prochaine touche annoncée ({prochaine}) sans touche ouverte', lead))
            return
        self.assertIsNotNone(prochaine, self.msg('I7 — aucune prochaine touche annoncée', lead))
        tete = _clef_de_tri(ouvertes[0])
        candidates = [e for e in ouvertes if _clef_de_tri(e) == tete]
        self.assertTrue(any(self._designe(prochaine, e) for e in candidates), self.msg(
            f'I7 — prochaine_touche {prochaine} ne désigne pas la plus proche touche ouverte',
            lead))

    @staticmethod
    def _designe(prochaine, etape):
        due_at = prochaine.get('due_at')
        meme_instant = (due_at is None if etape.due_at is None
                        else bool(due_at) and parse_datetime(due_at) == etape.due_at)
        return (prochaine.get('due_date') == etape.due_date.isoformat() and meme_instant
                and prochaine.get('canal') == etape.canal
                and prochaine.get('libelle') == etape.libelle
                and prochaine.get('cle') == cle_de(etape))

    # ── UN cas de la table ──

    def jouer_cas(self, cas):
        """Lead neuf → ``amener`` → la réponse du cas → HTTP 2xx → ``verifier_suite`` →
        invariants."""
        self.preparer_gabarits(cas.type_id, cas.contexte)
        if cas.appel_seulement:
            # Répondeur, Occupé… ne se proposent que sur un APPEL : la passation
            # (chemin ordinaire de « generique ») est un message.
            lead, etape = self.amener_generique_appel()
        else:
            lead, etape = self.amener(cas.type_id)
        if cas.contexte == CONTEXTE_AGRICOLE_SANS_RELEVE_EAU:
            # AGR530 — le même dossier, devenu un pompage au point d'eau
            # inconnu (aucune donnée hydraulique) : la seule différence.
            Lead.objects.filter(pk=lead.pk).update(type_installation='agricole')
            lead.refresh_from_db()
        avant = self.photo(lead, etape)
        reponse = cas.reponse
        resp, envoye = self.repondre(
            etape, reponse,
            motif=MOTIF_COMMERCIAL if reponse.get('motif_perte') else None,
            motif_refus=MOTIF_COMMERCIAL if reponse.get('motif_refus') else None,
            junk=cas.contexte == 'perdu_junk', sans_date=cas.contexte == 'sans_date')
        self.verifier_suite(lead, etape, reponse, cas.suite, avant, envoye, cas.type_id)
        self.verifier_invariants(lead, resp=resp)

    def jouer_famille(self, famille):
        """Chaque cas de ``famille``, chacun dans son ``subTest`` et son ``cas_isole``."""
        tous = cas_de_la_famille(famille)
        self.assertTrue(tous, f'aucun cas pour la famille « {famille} »')
        for cas in tous:
            with self.subTest(etape=cas.type_id, reponse=cas.reponse['modele'],
                              contexte=cas.contexte):
                with self.cas_isole(entete=cas.nom):
                    self.jouer_cas(cas)
