"""COP5 — moteur NATIF de l'assistant (boucle d'outils sur l'API Messages d'Anthropic).

INTERFACE FIGÉE (contrat entre le relais et le moteur) — ce module ne connaît
NI le catalogue d'actions, NI Django, NI l'utilisateur : le relais
(``sql_agent_service``) lui remet des outils déjà prêts (schéma + fonction
d'exécution qui alimente SON collecteur de cartes), le prompt système et le
texte de la question (en-tête de tour compris). Le moteur ne fait qu'une
chose : tenir la conversation avec le modèle.

  * ``executer``  — un tour : question -> appels d'outils -> réponse finale.
  * ``reprendre`` — après une confirmation : le relais remet le résultat de
    l'ERP (déjà mis sous enveloppe « non fiable ») et le modèle CONTINUE la
    tâche là où il s'était arrêté.
  * ``effacer``   — oublie une conversation.

La conversation (blocs d'outils compris) est gardée par le moteur sous la clé
``conversation`` fournie par le relais (« société:utilisateur »), 48 h au plus.

Éteint par défaut : le relais ne l'appelle que si ``ASSISTANT_MOTEUR=natif``
ET que le copilote est allumé pour le compte.

Choix de construction (COP-M1) — chaque hypothèse sur l'API est citée :
  * SDK ``anthropic`` 0.125.0 (figé par ``langchain-anthropic<1.0``) : il
    précède Sonnet 5.5, donc requêtes NON streamées et réponse lue en JSON BRUT
    (``with_raw_response``) ; les blocs sont gardés comme des dicts tels que
    reçus, un type de bloc inconnu est renvoyé inchangé
    (l3/web_anthropic.verif-refute.md #40 ; l3/web_anthropic.verif-omissions.md F13).
  * Aucun message système en cours de conversation : le contexte du tour est
    dans le texte de la question (mid-conversation-system-messages : « Not a
    place for untrusted content » ; l3/web_anthropic.verif-omissions.md F8/F9).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: Valeurs de ``arret`` dans le retour de :func:`executer` / :func:`reprendre`.
ARRET_FIN = "fin"          # le modèle a terminé son tour
ARRET_LIMITE = "limite"    # nombre maximal d'itérations ou de tokens atteint
ARRET_REFUS = "refus"      # le modèle a refusé (stop_reason « refusal »)
ARRET_ERREUR = "erreur"    # erreur du fournisseur après les reprises prévues

#: Reprises courtes faites par le SDK lui-même (408/409/429/5xx, réseau).
REPRISES_SDK = 2
#: Délai d'UN appel non streamé (s) ; ``max_tokens`` du relais = 4 096.
DELAI_APPEL_S = 60.0
#: Budget d'un tour (s) : nginx coupe ``/sql-agent/`` à 300 s.
DUREE_MAX_TOUR_S = 240.0

# 400 « pensée / historique » : signature d'un bloc de pensée invalide après une
# édition du préfixe (claude-api shared/error-codes.md : « Invalid signature in
# thinking block ... bound to a different conversation »).
_RE_400_PENSEE = re.compile(r"thinking|signature|prefix|redacted", re.I)
_TYPES_PENSEE = ("thinking", "redacted_thinking")


class MoteurIndisponible(RuntimeError):
    """Le moteur natif ne peut pas servir ce tour (clé absente, SDK absent,
    fournisseur en panne franche) : le relais retombe sur le moteur LangChain."""


@dataclass(frozen=True)
class OutilNatif:
    """Un outil remis au modèle.

    ``executer`` reçoit les arguments déjà décodés (dict) et rend le TEXTE
    remis au modèle (résultat, proposition en attente de confirmation, ou
    refus expliqué). Il ne lève pas pour un refus métier ; s'il lève quand
    même, le moteur rend au modèle un message d'erreur court et continue.
    """

    nom: str                       # ^[a-zA-Z0-9_-]{1,64}$
    description: str
    schema: dict                   # JSON Schema de type « object »
    executer: Callable[[dict], str]


class _ErreurFournisseur(Exception):
    """L'appel au modèle a échoué après les reprises du SDK."""


@dataclass
class _Tour:
    """État d'un tour : la conversation complète (passé + tour en cours)."""

    messages: list
    outils: dict                   # nom -> OutilNatif
    corps: dict                    # paramètres fixes de la requête
    modele: str
    appeles: list = field(default_factory=list)
    textes: list = field(default_factory=list)
    pensee_retiree: bool = False
    tokens: dict = field(default_factory=lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0})


# ── Client et appel ─────────────────────────────────────────────────────────

def _client():
    """Client du SDK, ou :class:`MoteurIndisponible` (clé ou SDK absents)."""
    from app.core import config
    if not config.CLAUDE_API_KEY:
        raise MoteurIndisponible("Clé du fournisseur claude absente.")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dépendance de l'image
        raise MoteurIndisponible("SDK anthropic absent.") from exc
    return anthropic.Anthropic(api_key=config.CLAUDE_API_KEY,
                               max_retries=REPRISES_SDK, timeout=DELAI_APPEL_S)


def _corps(systeme: list[dict], outils: list[OutilNatif], modele: str,
           effort: str, max_tokens: int) -> dict:
    """Paramètres fixes d'une requête (identiques à chaque appel du tour)."""
    tools = [{"name": o.nom, "description": o.description,
              "input_schema": o.schema} for o in outils]
    # Pensée adaptive : non désactivable sur Sonnet 5.5, `budget_tokens` y est
    # un 400 (claude-api shared/model-migration.md, Sonnet 5.5 changement 1).
    corps = {"model": modele, "max_tokens": max_tokens,
             "thinking": {"type": "adaptive"},
             "output_config": {"effort": (effort or "low").lower()}}
    if systeme:
        corps["system"] = [dict(b) for b in systeme]
    if tools:
        # `tool_choice` forcé = 400 avec la pensée sur Sonnet 5.5 : `auto`
        # (claude-api python/claude-api/tool-use.md « Tool Choice »).
        corps["tools"] = tools
        corps["tool_choice"] = {"type": "auto"}
    return corps


def _cumuler(tokens: dict, usage: Any) -> None:
    """Usage CUMULÉ du tour (``input_tokens`` = part hors cache,
    claude-api shared/prompt-caching.md « Verifying cache hits »)."""
    usage = usage if isinstance(usage, dict) else {}
    for cle, champ in (("input", "input_tokens"), ("output", "output_tokens"),
                       ("cache_read", "cache_read_input_tokens"),
                       ("cache_write", "cache_creation_input_tokens")):
        tokens[cle] += int(usage.get(champ) or 0)


def _poster(client, tour: _Tour) -> dict:
    brut = client.messages.with_raw_response.create(
        **tour.corps, messages=tour.messages)
    reponse = brut.http_response.json()
    _cumuler(tour.tokens, reponse.get("usage"))
    return reponse


def _est_400_pensee(exc: BaseException) -> bool:
    return (getattr(exc, "status_code", None) == 400
            and bool(_RE_400_PENSEE.search(str(exc))))


def _sans_pensees(messages: list) -> list:
    """Copie de la conversation sans AUCUN bloc de pensée (les retirer tous
    est permis : « leave out ... all of them » — l3/web_anthropic.verif-omissions.md F2)."""
    sortie = []
    for msg in messages:
        contenu = msg.get("content")
        if msg.get("role") != "assistant" or not isinstance(contenu, list):
            sortie.append(msg)
            continue
        garde = [b for b in contenu if not (
            isinstance(b, dict) and b.get("type") in _TYPES_PENSEE)]
        sortie.append(dict(msg, content=garde or [
            {"type": "text", "text": "(réflexion retirée)"}]))
    return sortie


def _appeler(client, tour: _Tour) -> dict:
    """Un appel au modèle. Sur un 400 lié à la pensée : retire TOUS les blocs
    de pensée et réessaie UNE fois ; le retrait est gardé (« Once a block is
    out, keep it out » — preserved-thinking). Échec -> :class:`_ErreurFournisseur`."""
    try:
        return _poster(client, tour)
    except Exception as exc:  # erreur du fournisseur (SDK, réseau, statut)
        reessayer = (_est_400_pensee(exc) and not tour.pensee_retiree
                     and _sans_pensees(tour.messages) != tour.messages)
        if not reessayer:
            raise _ErreurFournisseur(str(exc)[:300]) from exc
        logger.warning("Moteur natif : 400 lié à la pensée, blocs retirés, "
                       "nouvel essai unique (%s)", str(exc)[:200])
    tour.messages[:] = _sans_pensees(tour.messages)
    tour.pensee_retiree = True
    try:
        return _poster(client, tour)
    except Exception as exc:
        raise _ErreurFournisseur(str(exc)[:300]) from exc


# ── Outils ──────────────────────────────────────────────────────────────────

def _blocs(contenu: list, genre: str) -> list[dict]:
    return [b for b in contenu or [] if isinstance(b, dict) and b.get("type") == genre]


def _texte(contenu: list) -> str:
    """Texte final = blocs ``text`` seulement, jamais la pensée."""
    return "".join(str(b.get("text") or "") for b in _blocs(contenu, "text")).strip()


def _trouver_outil(nom: Any, outils: dict) -> Optional[OutilNatif]:
    """Nom exact, sinon correspondance UNIQUE à la casse près (Sonnet 5.5
    « Tolerant tool-call handling », claude-api shared/model-migration.md)."""
    if nom in outils:
        return outils[nom]
    proches = [o for n, o in outils.items()
               if isinstance(nom, str) and n.lower() == nom.lower()]
    return proches[0] if len(proches) == 1 else None


def _resultat(bloc: dict, texte: str, erreur: bool = False) -> dict:
    res = {"type": "tool_result", "tool_use_id": bloc.get("id"), "content": texte}
    if erreur:
        res["is_error"] = True
    return res


def _executer_outils(contenu: list, tour: _Tour) -> list[dict]:
    """TOUS les ``tool_use`` de la réponse, dans l'ordre -> UN message de
    ``tool_result`` (mêmes identifiants, résultats d'abord — handle-tool-calls)."""
    resultats = []
    for bloc in _blocs(contenu, "tool_use"):
        outil = _trouver_outil(bloc.get("name"), tour.outils)
        if outil is None:
            resultats.append(_resultat(bloc, "Outil inconnu « %s » : utilise "
                                       "seulement les outils déclarés."
                                       % str(bloc.get("name"))[:64], True))
            continue
        tour.appeles.append(outil.nom)
        entrees = bloc.get("input") if isinstance(bloc.get("input"), dict) else {}
        try:
            texte, erreur = str(outil.executer(dict(entrees))), False
        except Exception as exc:  # l'outil ne doit pas faire tomber le tour
            logger.warning("Outil %s : %s", outil.nom, exc)
            texte, erreur = ("L'outil « %s » a échoué (%s). Ne réessaie pas à "
                             "l'identique : dis ce qui n'a pas pu être fait."
                             % (outil.nom, type(exc).__name__)), True
        resultats.append(_resultat(bloc, texte, erreur))
    return resultats


# ── La boucle ───────────────────────────────────────────────────────────────

def _deja_fait(tour: _Tour) -> str:
    if not tour.appeles:
        return "Aucune action n'a été lancée."
    vus = list(dict.fromkeys(tour.appeles))
    return "Déjà fait pendant ce tour : %s." % ", ".join(vus)


def _fermer(tour: _Tour, arret: str, texte: str) -> tuple[str, str, str]:
    """Clôt le tour par un texte de l'assistant (point sûr : aucun
    ``tool_use`` sans son ``tool_result``)."""
    if tour.messages and tour.messages[-1].get("role") == "user":
        tour.messages.append({"role": "assistant",
                              "content": [{"type": "text", "text": texte}]})
    return arret, texte, "tour"


def _message_limite(tour: _Tour) -> str:
    lignes = ["Je me suis arrêté avant la fin : trop d'étapes pour une seule demande.",
              _deja_fait(tour)]
    if tour.textes:
        lignes.append("Où j'en étais : %s" % tour.textes[-1][:300])
    lignes.append("Le reste n'est pas fait. Dis « continue » pour la suite, "
                  "ou précise ta demande.")
    return "\n".join(lignes)


def _terminer(tour: _Tour, stop: Any, contenu: list,
              reponse: dict) -> tuple[str, str, str]:
    """Fin du tour selon ``stop_reason`` -> (arret, answer, garde)."""
    if stop == "refusal":
        # HTTP 200 + stop_reason « refusal » : ne pas rejouer le même historique
        # (claude-api shared/model-migration.md, Safeguards and fallback).
        logger.warning("Moteur natif : refus (%s)",
                       (reponse.get("stop_details") or {}).get("category"))
        return ARRET_REFUS, ("Je ne peux pas traiter cette demande telle quelle. "
                             "Reformule-la autrement. " + _deja_fait(tour)), "rien"
    if stop == "model_context_window_exceeded":
        return ARRET_LIMITE, ("La conversation est devenue trop longue : je "
                              "repars de zéro. Repose ta question."), "effacer"
    texte = _texte(contenu)
    if _blocs(contenu, "tool_use") or not texte:
        # réponse coupée en plein appel d'outil (jamais exécuté), ou vide.
        arret = ARRET_LIMITE if stop == "max_tokens" else ARRET_FIN
        return _fermer(tour, arret, "Je n'ai pas pu terminer ma réponse. "
                       + _deja_fait(tour) + " Peux-tu préciser ta demande ?")
    tour.messages.append({"role": "assistant", "content": contenu})
    if stop == "max_tokens":
        return ARRET_LIMITE, texte + "\n\n(Réponse coupée : trop longue.)", "tour"
    return ARRET_FIN, texte, "tour"


def _boucle(client, tour: _Tour, max_iterations: int) -> tuple[str, str, str]:
    """Appel -> tant que ``stop_reason == "tool_use"`` : outils -> rappel."""
    debut = time.monotonic()
    iterations = max(1, int(max_iterations))
    for i in range(iterations):
        reponse = _appeler(client, tour)
        contenu = reponse.get("content") if isinstance(reponse.get("content"), list) else []
        tour.modele = reponse.get("model") or tour.modele
        stop = reponse.get("stop_reason")
        if stop != "tool_use" or not _blocs(contenu, "tool_use"):
            return _terminer(tour, stop, contenu, reponse)
        if i == iterations - 1 or time.monotonic() - debut > DUREE_MAX_TOUR_S:
            break  # dernier appel : ses outils ne sont PAS exécutés
        tour.messages.append({"role": "assistant", "content": contenu})
        if _texte(contenu):
            tour.textes.append(_texte(contenu))
        tour.messages.append({"role": "user",
                              "content": _executer_outils(contenu, tour)})
    return _fermer(tour, ARRET_LIMITE, _message_limite(tour))


def _jouer(client, tour: _Tour, max_iterations: int) -> tuple[str, str, str]:
    """La boucle, ou — erreur du fournisseur — :class:`MoteurIndisponible`
    tant qu'aucun outil n'a tourné (le relais rejoue sur LangChain sans
    doublon), sinon une fin honnête ``ARRET_ERREUR``."""
    try:
        return _boucle(client, tour, max_iterations)
    except _ErreurFournisseur as exc:
        if not tour.appeles:
            raise MoteurIndisponible("Fournisseur claude indisponible : %s"
                                     % exc) from exc
        logger.warning("Moteur natif : erreur après outils : %s", exc)
        return _fermer(tour, ARRET_ERREUR, "Le service d'IA ne répond plus. "
                       + _deja_fait(tour) + " Vérifie la fiche avant de redemander.")


def _servir(*, question: str, passe: list, systeme: list[dict],
            outils: list[OutilNatif], modele: str, effort: str,
            max_tokens: int, max_iterations: int) -> tuple[dict, _Tour, str]:
    client = _client()
    tour = _Tour(messages=list(passe) + [{"role": "user", "content": [
                     {"type": "text", "text": question}]}],
                 outils={o.nom: o for o in outils}, modele=modele,
                 corps=_corps(systeme, outils, modele, effort, max_tokens))
    arret, answer, garde = _jouer(client, tour, max_iterations)
    retour = {"answer": answer, "outils_appeles": list(tour.appeles),
              "tokens": dict(tour.tokens), "arret": arret, "modele": tour.modele}
    return retour, tour, garde


def executer(*, question: str, systeme: list[dict], outils: list[OutilNatif],
             conversation: str, modele: str, effort: str = "low",
             max_tokens: int = 4096, max_iterations: int = 10) -> dict[str, Any]:
    """Un tour complet. Rend ``{"answer": str, "outils_appeles": [nom, ...],
    "tokens": {"input", "output", "cache_read", "cache_write"},
    "arret": ARRET_*, "modele": str}``.

    ``systeme`` : blocs ``{"type": "text", "text": ...}`` dans un ordre STABLE
    (le moteur pose lui-même les points de cache). ``question`` : le texte de
    l'utilisateur précédé de l'en-tête de tour (``prompt_copilote.entete_tour``).
    Lève :class:`MoteurIndisponible` si le tour ne peut pas être servi du tout.
    """
    retour, _tour, _garde = _servir(
        question=question, passe=[], systeme=systeme, outils=outils,
        modele=modele, effort=effort, max_tokens=max_tokens,
        max_iterations=max_iterations)
    return retour


def reprendre(*, conversation: str, message: str, systeme: list[dict],
              outils: list[OutilNatif], modele: str, effort: str = "low",
              max_tokens: int = 4096,
              max_iterations: int = 10) -> Optional[dict[str, Any]]:
    """Après une confirmation : ajoute ``message`` (résultat de l'ERP sous
    enveloppe, rédigé par le relais) à la conversation et laisse le modèle
    continuer. Même retour qu':func:`executer`, ou ``None`` s'il n'y a aucune
    conversation à reprendre (expirée, effacée, autre moteur)."""
    return None


def effacer(conversation: str) -> None:
    """Oublie la conversation (bouton « Effacer » de l'écran)."""
    return None
