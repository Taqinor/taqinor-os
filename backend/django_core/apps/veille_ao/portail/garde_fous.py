"""VAO19 — les garde-fous : ce que le fichier de risque PROMET, en CODE.

Le fichier de risque du portail public national (sous ``tos_risk/``) engage
Taqinor sur neuf mitigations. Une
mitigation écrite dans un fichier et absente du code n'est pas une mitigation :
c'est une intention. Ce module les rend exécutables, et
``tests/test_garde_fous.py`` donne à chacune son test.

=== La mitigation ================================ Ce module ==================
1. User-Agent honnête, arrêt définitif sur 403     ``verifier_identite_honnete``
                                                   (+ ``client._erreur_de_statut``)
2. Requête toujours restreinte par mots-clés       ``exiger_mot_cle_restrictif``
3. < 10 requêtes/jour, ≤ 1 requête / 2 s           ``GardeFous.avant_requete``
4. Aucune page authentifiée, aucun compte          garde de grep (test)
5. Aucun DCE en masse                              ``detail.enrichir`` (VAO18)
6. Interrupteur d'arrêt                            ``collecte_armee``
7. Aucune republication                            hors code (usage interne)
8. Journal d'exécution auditable                   ``GardeFous.journal``
9. Aucun contournement de contrôle d'accès         ``MaquillageRefuse``
================================================== ===========================

**Ce module est le SEUL du paquet autorisé à écrire des chaînes d'User-Agent
de navigateur** — il les nomme pour les INTERDIRE. Le test de grep balaie tout
``portail/`` sauf ce fichier : si « Mozilla » réapparaît ailleurs, il rougit.

Deux limites, écrites franchement plutôt que sous-entendues
-----------------------------------------------------------
* Le compteur de quota et le verrou sont **par processus**. Ils empêchent un
  emballement dans le worker qui collecte, ce qui est le risque réel ici (un
  seul beat, une seule tâche quotidienne). Pour une garantie inter-processus,
  ``compteurs``/``verrous`` sont injectables : un jour, un magasin partagé
  (cache Django, Redis) s'y branche sans toucher au reste.
* L'interrupteur est lu dans l'ENVIRONNEMENT (``os.environ``), pas dans les
  réglages Django : ce paquet doit rester testable sans Django. La tâche
  planifiée (VAO22) lit en plus ``settings.VEILLE_AO_COLLECTE_ACTIVE`` — les
  deux gardes sont **redondantes par conception** (ceinture et bretelles), et
  toutes deux DÉSARMÉES par défaut.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import ErreurPortail

logger = logging.getLogger(__name__)

#: Le fuseau qui décide de la JOURNÉE du quota. À Casablanca, pas à UTC :
#: sinon le quota se remet à zéro en pleine matinée marocaine une partie de
#: l'année.
CASABLANCA = ZoneInfo('Africa/Casablanca')

#: L'interrupteur d'arrêt. Absent ou à « 0 » = DÉSARMÉ. C'est le défaut, et
#: l'armement est une décision fondateur datée (règle #5, tâche VAO4).
DRAPEAU = 'VEILLE_AO_COLLECTE_ACTIVE'
VALEURS_ARMEES = frozenset({'1', 'true', 'vrai', 'oui', 'yes', 'on'})

#: 10, et non 20 : c'est le chiffre que le fichier de risque promet
#: (« moins de 10 requêtes par jour »). Un plafond plus haut que la promesse
#: écrite serait une promesse non tenue.
QUOTA_QUOTIDIEN = 10

#: Une requête toutes les 2 secondes au minimum.
CADENCE_MINIMALE = 2.0

#: Longueur minimale d'un mot-clé restrictif, et les jokers qui déguisent un
#: balayage en recherche.
LONGUEUR_MOT_CLE_MINIMALE = 3
JOKERS = ('*', '%')

#: Les jetons d'un User-Agent de navigateur. Écrits ICI, et NULLE PART
#: AILLEURS dans ``portail/`` — c'est la garde anti-maquillage.
JETONS_NAVIGATEUR = (
    'mozilla', 'applewebkit', 'chrome', 'safari', 'firefox', 'gecko',
    'edg/', 'opera', 'trident', 'webkit', 'khtml',
)

#: La comparaison se fait sur des MOTS, pas sur des sous-chaînes : sans cela
#: « InvalidOperation » contiendrait « opera » et une adresse de contact
#: « operations@… » serait refusée comme un déguisement. Une fausse alerte sur
#: une garde de sécurité, c'est la garde qu'on finit par désactiver.
_MOTIF_NAVIGATEUR = re.compile(
    r'(?<![a-z])(?:' + '|'.join(re.escape(j) for j in JETONS_NAVIGATEUR)
    + r')(?![a-z])', re.IGNORECASE)

#: Les marques d'un accès authentifié. Interdites dans tout ``portail/`` sauf
#: ici. ``PHPSESSID`` n'y figure PAS et c'est délibéré : c'est le cookie que
#: le serveur pose de lui-même sur une visite ANONYME, que httpx transporte
#: sans qu'on le fabrique — ce n'est pas une session UTILISATEUR, et le
#: dispositif n'ouvre aucun compte (mitigation n°4).
MARQUES_D_AUTHENTIFICATION = (
    'password', 'passwd', 'motdepasse', 'mot_de_passe', 'authorization',
    'basicauth', 'auth=', 'login=', 'identifiant=', 'entrepriselogin',
    'credential', 'jeton_utilisateur',
)


class CollecteDesarmee(ErreurPortail):
    """L'interrupteur est fermé : aucun appel réseau n'est permis.

    Ce n'est pas une panne. C'est l'état NORMAL du dispositif tant que le
    fondateur n'a pas daté son accord (règle #5, VAO4).
    """


class QuotaDepasse(ErreurPortail):
    """Le plafond quotidien est atteint — on s'arrête, on ne « continue quand
    même ». Dépasser le volume promis au fichier de risque invaliderait
    l'analyse de risque elle-même."""


class CollecteConcurrente(ErreurPortail):
    """Une collecte tourne déjà pour cette société.

    Deux collectes simultanées, c'est le double du volume promis et des
    écritures concurrentes sur les mêmes avis.
    """


class MaquillageRefuse(ErreurPortail):
    """On a tenté de partir sous une identité de navigateur. Jamais."""


class RechercheNonRestreinte(ErreurPortail):
    """Recherche sans mot-clé restrictif = balayage du portail. Refusé."""


# ─────────────────────────────────────────────────────────────────────────
# Mitigation 6 — l'interrupteur d'arrêt
# ─────────────────────────────────────────────────────────────────────────


def collecte_armee(environnement=None):
    """``True`` seulement si l'interrupteur est explicitement armé.

    Relu à CHAQUE appel, jamais mis en cache au chargement du module : le
    fondateur doit pouvoir désarmer sans redéployer.
    """
    source = os.environ if environnement is None else environnement
    return str(source.get(DRAPEAU, '0')).strip().lower() in VALEURS_ARMEES


def exiger_collecte_armee(environnement=None):
    """Lève ``CollecteDesarmee`` tant que l'interrupteur est fermé."""
    if not collecte_armee(environnement):
        raise CollecteDesarmee(
            f'Collecte désarmée ({DRAPEAU}=0) : aucun appel réseau, y compris '
            "sur déclenchement manuel. L'armement est une décision fondateur "
            'datée (règle #5, tâche VAO4) — aucun agent ne peut le poser.')
    return True


# ─────────────────────────────────────────────────────────────────────────
# Mitigations 1 et 9 — identité honnête, aucun contournement
# ─────────────────────────────────────────────────────────────────────────


def verifier_identite_honnete(ua):
    """Lève ``MaquillageRefuse`` si l'identité ressemble à un navigateur.

    Le pare-feu du portail refuse les clients scriptés. Se déguiser pour
    passer, c'est contourner un refus explicite de l'exploitant : hors
    périmètre. Le repli d'un 403 est le canal officiel (alertes du portail,
    VAO44) et la saisie manuelle.
    """
    trouve = _MOTIF_NAVIGATEUR.search(ua or '')
    if trouve:
        raise MaquillageRefuse(
            f'Identité de navigateur refusée (« {trouve.group(0)} ») : le '
            'collecteur ne se déguise jamais pour contourner un refus du '
            'portail. Le repli est le canal officiel, pas le maquillage.')
    return ua


# ─────────────────────────────────────────────────────────────────────────
# Mitigation 2 — la requête est TOUJOURS restreinte
# ─────────────────────────────────────────────────────────────────────────


def exiger_mot_cle_restrictif(mot_cle):
    """Refuse tout ce qui n'est pas une recherche métier restreinte.

    Un balayage des ~3 380 avis ouverts représenterait ~338 POST par jour —
    précisément la forme de trafic qu'un pare-feu attrape. Il doit être
    impossible à ÉCRIRE, pas seulement déconseillé.
    """
    propre = (mot_cle or '').strip()
    if not propre:
        raise RechercheNonRestreinte(
            'Recherche sans mot-clé refusée : elle ramènerait les ~3 380 avis '
            'ouverts du portail (~338 requêtes/jour). La veille interroge des '
            'mots-clés métier, jamais le portail entier.')
    if any(joker in propre for joker in JOKERS):
        raise RechercheNonRestreinte(
            f'Mot-clé « {propre} » refusé : un joker est un balayage déguisé.')
    if len(propre) < LONGUEUR_MOT_CLE_MINIMALE:
        raise RechercheNonRestreinte(
            f'Mot-clé « {propre} » refusé : trop court pour restreindre '
            f'(minimum {LONGUEUR_MOT_CLE_MINIMALE} caractères).')
    return propre


# ─────────────────────────────────────────────────────────────────────────
# Mitigation 3 — cadence et quota ; verrou de société
# ─────────────────────────────────────────────────────────────────────────

#: {(clé, jour ISO): nombre de requêtes}. Volontairement au niveau du module :
#: le quota doit tenir sur TOUT le processus, pas sur un objet qu'on
#: recréerait à chaque appel pour repartir de zéro.
_COMPTEURS = {}
_VERROUS = {}
_MUTEX = threading.Lock()


def reinitialiser(cle=None):
    """Remet les compteurs et verrous à zéro. Réservé aux tests.

    En production, la journée qui change suffit : la clé de comptage porte la
    date, donc les compteurs de la veille ne bloquent jamais aujourd'hui.
    """
    with _MUTEX:
        if cle is None:
            _COMPTEURS.clear()
            _VERROUS.clear()
            return
        for existante in [k for k in _COMPTEURS if k[0] == cle]:
            _COMPTEURS.pop(existante, None)
        _VERROUS.pop(cle, None)


def jour_courant():
    """La date du jour à Casablanca, au format ISO."""
    return datetime.now(CASABLANCA).date().isoformat()


class GardeFous:
    """La garde branchée sur CHAQUE requête du client.

    ``horloge``/``dormir`` sont injectables : les tests vérifient la cadence
    sans attendre deux secondes pour de vrai.
    """

    def __init__(self, cle='defaut', quota=QUOTA_QUOTIDIEN,
                 cadence=CADENCE_MINIMALE, horloge=time.monotonic,
                 dormir=time.sleep, compteurs=None, jour=None,
                 environnement=None):
        self.cle = str(cle or 'defaut')
        self.quota = int(quota)
        self.cadence = float(cadence)
        self.horloge = horloge
        self.dormir = dormir
        self.compteurs = _COMPTEURS if compteurs is None else compteurs
        self._jour = jour
        self.environnement = environnement
        self.dernier_appel = None
        self.journal = []
        self._verrou_tenu = False

    # ── comptage ─────────────────────────────────────────────────────────
    @property
    def jour(self):
        return self._jour or jour_courant()

    @property
    def _cle_du_jour(self):
        return (self.cle, self.jour)

    @property
    def consommees(self):
        return self.compteurs.get(self._cle_du_jour, 0)

    @property
    def restantes(self):
        return max(0, self.quota - self.consommees)

    # ── la garde elle-même ───────────────────────────────────────────────
    def avant_requete(self, description=''):
        """Autorise (ou refuse) UNE requête. Appelée par le client.

        L'ordre des contrôles n'est pas indifférent : l'interrupteur d'abord
        (le moins coûteux et le plus impératif), le quota ensuite (refuser
        AVANT d'attendre), la cadence en dernier — attendre deux secondes pour
        se voir refuser serait absurde.
        """
        exiger_collecte_armee(self.environnement)

        with _MUTEX:
            consommees = self.compteurs.get(self._cle_du_jour, 0)
            if consommees >= self.quota:
                raise QuotaDepasse(
                    f'Quota quotidien atteint ({consommees}/{self.quota} '
                    f'requêtes le {self.jour}) pour « {self.cle} ». La '
                    'collecte S\'ARRÊTE : le fichier de risque promet moins de '
                    '10 requêtes par jour, et un plafond qu\'on dépasse n\'est '
                    'pas un plafond. Restreindre les mots-clés, ou attendre '
                    'demain.')
            self.compteurs[self._cle_du_jour] = consommees + 1

        self._respecter_la_cadence()
        self.journal.append({
            'jour': self.jour, 'cle': self.cle, 'description': description,
            'numero': consommees + 1,
        })
        logger.info('veille_ao.portail : requête %s/%s (%s) — %s',
                    consommees + 1, self.quota, self.cle, description)
        return consommees + 1

    def _respecter_la_cadence(self):
        maintenant = self.horloge()
        if self.dernier_appel is not None:
            attente = self.cadence - (maintenant - self.dernier_appel)
            if attente > 0:
                self.dormir(attente)
                maintenant = self.horloge()
        self.dernier_appel = maintenant

    # ── verrou de société ────────────────────────────────────────────────
    def __enter__(self):
        with _MUTEX:
            if _VERROUS.get(self.cle):
                raise CollecteConcurrente(
                    f'Une collecte tourne déjà pour « {self.cle} ». Deux '
                    'collectes simultanées, c\'est le double du volume promis '
                    'et des écritures concurrentes sur les mêmes avis.')
            _VERROUS[self.cle] = True
            self._verrou_tenu = True
        return self

    def __exit__(self, *exc):
        if self._verrou_tenu:
            with _MUTEX:
                _VERROUS.pop(self.cle, None)
            self._verrou_tenu = False
        return False


def cle_de_societe(source):
    """La clé de quota/verrou d'une source : SA SOCIÉTÉ.

    Le plafond est par société (multi-tenant) : la société A ne doit pas
    consommer le quota de la société B, et deux sociétés peuvent collecter
    en parallèle sans se bloquer.
    """
    company = getattr(source, 'company_id', None)
    if company is None:
        company = getattr(getattr(source, 'company', None), 'pk', None)
    identifiant = getattr(source, 'pk', None) or getattr(source, 'id', None)
    return f'societe:{company or "?"}:source:{identifiant or "?"}'


__all__ = [
    'CADENCE_MINIMALE', 'CASABLANCA', 'CollecteConcurrente', 'CollecteDesarmee',
    'DRAPEAU', 'GardeFous', 'JETONS_NAVIGATEUR', 'JOKERS',
    'LONGUEUR_MOT_CLE_MINIMALE', 'MARQUES_D_AUTHENTIFICATION',
    'MaquillageRefuse', 'QUOTA_QUOTIDIEN', 'QuotaDepasse',
    'RechercheNonRestreinte', 'cle_de_societe', 'collecte_armee',
    'exiger_collecte_armee', 'exiger_mot_cle_restrictif', 'jour_courant',
    'reinitialiser', 'verifier_identite_honnete',
]
