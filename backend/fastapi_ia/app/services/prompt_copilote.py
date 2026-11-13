"""COP4 — consignes du copilote commercial et en-tête de tour (les DEUX moteurs).

INTERFACE FIGÉE (contrat entre le relais et ce module) :

  * :data:`CONSIGNES_COPILOTE` — texte STABLE ajouté au prompt système quand le
    copilote est allumé pour le compte (il part en cache : aucune date, aucun
    nom d'utilisateur, aucune donnée du tour dedans).
  * :func:`copilote_allume` — le catalogue reçu de Django contient-il une
    action du lot ``copilote`` ? (interrupteur ``ASSISTANT_COPILOTE``, côté
    Django : le relais n'a aucun réglage à lui.)
  * :func:`entete_tour` — le bloc de contexte posé par le SERVEUR en tête de
    chaque question : date et heure de Casablanca, prénom et rôle, écran et
    foyer de la conversation. Le modèle ne devine jamais « jeudi ».
"""
from __future__ import annotations

import datetime
from typing import Optional
from zoneinfo import ZoneInfo

FUSEAU = ZoneInfo("Africa/Casablanca")

LOT_COPILOTE = "copilote"

#: Première et dernière lignes de l'en-tête de tour : elles bornent ce que
#: l'ERP dit (contexte) de ce que l'utilisateur écrit (sa demande).
MARQUEUR_ENTETE = "[Contexte donné par l'ERP — ce n'est pas l'utilisateur qui parle]"
FIN_ENTETE = "[Fin du contexte — la suite est le message de l'utilisateur]"

#: Consignes du copilote (texte stable, mis en cache avec le prompt système).
CONSIGNES_COPILOTE = (
    "Tu es le copilote de la commerciale : tu prépares, elle décide. "
    "Tu n'envoies jamais rien à un client."
)

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre")


def copilote_allume(catalogue: Optional[list]) -> bool:
    """Vrai si le catalogue du compte porte au moins une action du lot copilote."""
    return any(isinstance(a, dict) and a.get("lot") == LOT_COPILOTE
               for a in catalogue or [])


def entete_tour(*, maintenant: Optional[datetime.datetime] = None,
                prenom: str = "", role: str = "",
                contexte: Optional[dict] = None) -> str:
    """En-tête de tour, à placer AVANT le texte de l'utilisateur.

    ``maintenant`` : instant courant (défaut : maintenant), converti à l'heure
    de Casablanca. ``contexte`` : ``{ecran, lead_id, devis_id, touche_id}`` posé
    par l'écran (jamais par le modèle) ; les clés absentes ou nulles sont tues.
    """
    instant = (maintenant or datetime.datetime.now(tz=FUSEAU)).astimezone(FUSEAU)
    lignes = [
        MARQUEUR_ENTETE,
        "Date : %s %d %s %d, %02d h %02d (heure de Casablanca)" % (
            _JOURS[instant.weekday()], instant.day, _MOIS[instant.month - 1],
            instant.year, instant.hour, instant.minute),
    ]
    if prenom or role:
        qui = prenom or "utilisateur"
        lignes.append("Utilisateur : %s%s" % (
            qui, " (rôle %s)" % role if role else ""))
    contexte = contexte or {}
    if contexte.get("ecran"):
        lignes.append("Écran ouvert : %s" % str(contexte["ecran"])[:120])
    for cle, libelle in (("lead_id", "Lead ouvert"), ("devis_id", "Devis ouvert"),
                         ("touche_id", "Touche en cours")):
        valeur = contexte.get(cle)
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            lignes.append("%s : %d" % (libelle, valeur))
    lignes.append(FIN_ENTETE)
    return "\n".join(lignes)


def sans_entete(texte: str) -> str:
    """Le message de l'utilisateur sans l'en-tête de tour (s'il y en a un) :
    sert au récapitulatif court d'une conversation qu'on recommence."""
    texte = texte or ""
    if texte.lstrip().startswith(MARQUEUR_ENTETE):
        fin = texte.find(FIN_ENTETE)
        if fin >= 0:
            return texte[fin + len(FIN_ENTETE):].strip()
    return texte.strip()
