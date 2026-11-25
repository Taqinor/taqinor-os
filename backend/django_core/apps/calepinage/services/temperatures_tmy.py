"""CALX61 — le fournisseur de températures TMY que la chaîne électrique attend.

LE CONSTAT
----------
``services/electrique.py`` (CAL123) sait déjà dériver les températures de
dimensionnement d'un site depuis une année météo TYPE : il lit un FOURNISSEUR
enregistré (``enregistrer_fournisseur_temperatures``) et publie
``source='tmy'`` avec la base et la fenêtre d'années citées. Et
``services/pvgis_serie.py`` (CAL136) sait déjà rendre cette année type avec
ses extrêmes de ``T2m`` (``ClientPvgis.tmy``).

Les deux moitiés existaient ; PERSONNE ne les reliait. ``_FOURNISSEUR``
restait ``None`` — « enregistré par la lane production », jamais posé — donc
les bornes de tension (``core/electrique/chaines.py``) tournaient toujours
soit sur une température SAISIE, soit sur les valeurs de repli du noyau avec
la mention « températures de référence, non sourcées ». Ce module est le
chaînon manquant, et rien d'autre : il ne calcule aucune température, il
TRANSPORTE celles que PVGIS a mesurées.

CE QUE CE MODULE GARANTIT
-------------------------
1. **Aucun chiffre inventé** (D-CALX 7). Les deux températures sont les
   extrêmes de la série ``T2m`` REÇUE de PVGIS, telles quelles. La base de
   rayonnement et la fenêtre d'années sont republiées telles que PVGIS les
   nomme, et voyagent jusqu'à ``TemperaturesSite.detail``. Aucune valeur de
   repli n'est fabriquée ici : quand PVGIS ne répond pas, ce module rend
   ``None`` et le repli MENTIONNÉ du noyau reprend la main.
2. **Aucun appel réseau à l'import ni au démarrage.** ``apps.py::ready()``
   enregistre l'APPELABLE ; PVGIS n'est interrogé que le jour où une
   conception sans température saisie demande ses bornes de tension. Importer
   ce module ne fait rien d'autre que définir une fonction.
3. **Jamais une erreur.** PVGIS injoignable, surchargé, ou répondant une
   année type inexploitable ⇒ ``None``, c'est-à-dire EXACTEMENT le
   comportement d'aujourd'hui (aucun fournisseur enregistré). Un service
   météo en panne ne doit pas empêcher de rendre un verdict de tension, il
   doit seulement empêcher de le présenter comme sourcé.
4. **La saisie prime toujours.** Ce module n'a pas à le savoir :
   ``temperatures_site`` ne consulte le fournisseur QUE lorsque rien n'est
   saisi. C'est la discipline CAL123, et elle n'est pas recodée ici.
5. **Le cache et le limiteur de cadence sont ceux du client existant.** Le
   cache est le cache PARTAGÉ du module (défaut de ``ClientPvgis``) : deux
   conceptions sur le même point ne paient pas deux appels. Le limiteur, lui,
   est per-instance chez ``ClientPvgis`` — on en partage donc un SEUL ici,
   sinon la cadence PVGIS (30 appels/s) ne serait bornée par personne.

POURQUOI UN CLIENT NEUF PAR APPEL (ET UN LIMITEUR PARTAGÉ)
-----------------------------------------------------------
``ClientPvgis`` journalise dans ``self.urls_appelees`` CHAQUE appel, cache
compris, et ne purge jamais cette liste : un client-singleton de longue vie
la ferait croître sans borne dans un worker. On construit donc un client par
appel — une allocation, aucun réseau — en lui passant le limiteur partagé et
en laissant le cache partagé par défaut.
"""
from __future__ import annotations

import contextlib
import contextvars

from .pvgis_serie import (
    BASE_PAR_DEFAUT, ClientPvgis, EntreeInvalide, PvgisIndisponible,
    _Limiteur,
)
from .valeurs import nombre as _nombre

__all__ = ['temperatures_sans_reseau', 'temperatures_tmy']

#: Le limiteur de cadence PARTAGÉ par tous les appels TMY de ce fournisseur
#: (cf. la docstring du module). Sa construction n'ouvre aucune connexion.
_LIMITEUR = _Limiteur()

#: Lane I4 (api-fuzz : ``a-traiter/`` en délai dépassé) — l'état du mode
#: « sans réseau » en cours, ou ``None`` hors de ce mode.
_SANS_RESEAU = contextvars.ContextVar('temperatures_sans_reseau', default=None)


class _EtatSansReseau:
    """Ce que le mode a constaté : ``manques`` = années types ABSENTES du
    cache, donc non demandées à PVGIS."""

    def __init__(self):
        self.manques = 0

    def refuser(self, url, timeout_s):
        """Le transport du mode : compte le manque, n'ouvre aucune connexion."""
        self.manques += 1
        raise OSError('mode sans réseau : année type absente du cache')


@contextlib.contextmanager
def temperatures_sans_reseau():
    """Lane I4 — sous ce mode, :func:`temperatures_tmy` répond du cache SEUL.

    Une année type en cache est servie comme aujourd'hui ; absente, AUCUNE
    requête n'est faite (le transport du client refuse, par le chemin du client
    lui-même : ``ClientPvgis._appeler`` lit d'abord le cache), le manque est
    compté sur l'état rendu (``etat.manques``) et la réponse est ``None``. Une
    LISTE s'y place : elle ne touche jamais le réseau (même patron que
    ``devis_retenu.lecture_de_liste``)."""
    etat = _EtatSansReseau()
    jeton = _SANS_RESEAU.set(etat)
    try:
        yield etat
    finally:
        _SANS_RESEAU.reset(jeton)


def temperatures_tmy(lat, lon, *, client=None, base=BASE_PAR_DEFAUT):
    """Les températures de dimensionnement d'un point, depuis le TMY PVGIS.

    C'est la forme EXACTE qu'attend ``enregistrer_fournisseur_temperatures``
    (``services/electrique.py``) : appelée ``fournisseur(lat, lon)``, elle
    rend soit ``None``, soit un dict portant les deux températures et de quoi
    citer leur provenance. Les trois informations utiles — le froid, le chaud
    et le détail (base, fenêtre d'années) — sont celles que
    ``TemperaturesSite`` republiera dans ``source='tmy'`` et ``detail``.

    Args:
        lat, lon: le point du site, en degrés décimaux.
        client: ``ClientPvgis`` à employer — injectable pour les tests, qui
            rejouent une réponse ENREGISTRÉE et ne touchent jamais le réseau.
        base: base de rayonnement demandée (``PVGIS-SARAH3`` par défaut :
            c'est la base qui couvre le Maroc, CAL136). La base RÉELLEMENT
            employée est celle que PVGIS renvoie, jamais celle demandée.

    Returns:
        ``{'temperature_min_c', 'temperature_max_c', 'base',
        'fenetre_annees'}`` — ou ``None`` quand PVGIS est injoignable, quand
        le point est inexploitable, ou quand l'année type reçue ne porte
        aucune température. ``None`` = « aucune donnée pour ce point », le
        comportement d'avant CALX61 : le calcul continue, sans source.
    """
    sans_reseau = _SANS_RESEAU.get()
    if sans_reseau is not None:
        # Lane I4 — le MÊME cache (celui du client injecté, sinon le partagé),
        # un transport qui refuse et un limiteur neuf (aucune attente).
        client = ClientPvgis(sans_reseau.refuser, limiteur=_Limiteur(),
                             cache=getattr(client, 'cache', None))
    elif client is None:
        # Cache : celui, PARTAGÉ, de ``ClientPvgis`` (défaut). Limiteur : le
        # nôtre, partagé — voir la docstring du module.
        client = ClientPvgis(limiteur=_LIMITEUR)
    try:
        annee_type = client.tmy(lat=lat, lon=lon, base=base)
    except (PvgisIndisponible, EntreeInvalide):
        # Le seul comportement admissible : se taire. Toute autre exception
        # est neutralisée un cran plus haut par ``_depuis_fournisseur``, qui
        # ne laisse JAMAIS un adaptateur faire tomber un calcul de tension.
        return None

    if not isinstance(annee_type, dict):
        return None
    froid = _nombre(annee_type.get('temperature_min_c'))
    chaud = _nombre(annee_type.get('temperature_max_c'))
    if froid is None or chaud is None or froid >= chaud:
        # Une année type sans T2m lisible — ou dont les extrêmes se
        # confondent — ne dimensionne rien. On ne complète pas le manquant
        # avec une constante : on rend « aucune donnée ».
        return None

    return {
        'temperature_min_c': froid,
        'temperature_max_c': chaud,
        # Republiées telles que PVGIS les nomme : c'est ce qui rend le
        # chiffre défendable devant un bureau d'études.
        'base': annee_type.get('base') or '',
        'fenetre_annees': annee_type.get('fenetre_annees') or '',
    }
