"""Introspection du bus d'événements (YEVNT7).

Fournit les briques factuelles qu'un test de couverture utilise pour garantir
que le bus ``core.events`` et l'énumération ``notifications.EventType`` ne
laissent AUCUN orphelin silencieux :

* chaque ``Signal`` déclaré dans ``core/events.py`` a au moins un récepteur
  enregistré (ou est explicitement réservé dans ``ALLOWED_UNCONSUMED``) ;
* chaque membre ``EventType`` a au moins un producteur ``notify(EventType.X)``
  dans le code source (ou est explicitement réservé dans
  ``ALLOWED_UNPRODUCED``) ;
* chaque récepteur câblé (``@receiver(events.<signal>)``) pointe vers un signal
  qui existe réellement dans ``core.events``.

``core`` reste une app de FONDATION : ce module n'importe AUCUNE app métier au
niveau module. La liste des ``EventType`` et le recensement des producteurs se
font par un SCAN de fichiers (comme ``scripts/check_stages.py``), pas par un
``import apps.notifications`` — l'introspection des signaux et de leurs
récepteurs se fait, elle, sur ``core.events`` (même package fondation).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import django.dispatch

from core import events

# Racine ``backend/django_core`` (…/core/event_coverage.py -> parents[1]).
DJANGO_CORE_ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = DJANGO_CORE_ROOT / "apps"
CORE_ROOT = DJANGO_CORE_ROOT / "core"
EVENTTYPE_FILE = APPS_ROOT / "notifications" / "models.py"

# --- Listes blanches EXPLICITES (un orphelin non listé fait échouer le test) --

# Signaux de ``core.events`` volontairement SANS abonné dans ce repo (« seams »
# posés pour un découplage aval futur). Tout signal orphelin non listé ici est
# une régression (ex. YEVNT1/3/4 avaient laissé s'accumuler des orphelins).
ALLOWED_UNCONSUMED = {
    # Destiné à l'app comptable (matérialiser un Paiement / rapprocher la
    # facture) ; core n'importe jamais l'app comptable — abonné à venir.
    "payment_captured",
    # ARC36 — ``facture_payee``/``bon_commande_cree`` (YEVNT6) et
    # ``abonnement_monitoring_resilie`` (YSUBS4) ont désormais des abonnés
    # métier (compta lettrage + notifications vendeur/magasinier ;
    # apps/monitoring/receivers.py) : RETIRÉS de cette liste. ``facture_paid``
    # (YDOCF4) reste ici : signal FRÈRE de ``facture_payee`` (même fait,
    # résiduel→0) — DÉPRÉCIÉ pour l'abonnement (voir docstring du bus) afin
    # de ne jamais réagir deux fois au même règlement ; ne PAS s'y abonner.
    "facture_paid",
    # ARC35 — ``contrat_signe``/``contrat_actif`` (CONTRAT16/17, YDOCF5) ont
    # désormais un abonné réel (``apps/contrats/receivers.py`` : chatter ARC8
    # + dépôt GED du contrat signé ; ``apps/notifications/signals.py`` pour
    # ``contrat_signe``) : RETIRÉS de cette liste.
    # SCA30 — ``document_statut_change`` : seam GÉNÉRIQUE émis par le kit
    # ``core.documents`` au changement de statut d'un document métier (voir la
    # docstring du signal dans ``core.events`` : « aucun abonné obligatoire —
    # pose du seam pour audit/notifications/KPI d'un futur type de document »).
    # Volontairement sans abonné aujourd'hui (aucun consommateur métier requis),
    # donc réservé ici plutôt que d'être un orphelin — comme les seams ci-dessus.
    "document_statut_change",
    # NTFPA29 — ``budget_cycle_clos`` : seam émis à la clôture d'un cycle
    # budgétaire FP&A. Aucun abonné requis dans le lot NTFPA (pose du crochet
    # pour un futur module paie/reporting), comme les seams ci-dessus.
    "budget_cycle_clos",
    # NTADM40 — ``entite_created``/``entite_deactivated`` : seams émis par
    # ``apps/entites/services.py`` à la création/désactivation d'une ``Entite``
    # (hiérarchie intra-tenant), pour permettre à d'autres apps de réagir sans
    # import direct (ex. invalidation d'un cache d'agrégats par entité). Aucun
    # abonné métier requis aujourd'hui — réservés ici plutôt qu'orphelins,
    # comme les seams ci-dessus.
    "entite_created",
    "entite_deactivated",
}

# Membres ``EventType`` déclarés mais sans producteur ``notify()`` encore câblé
# (leur sweep/producteur serait planifié séparément). VIDE aujourd'hui : chaque
# EventType déclaré a au moins un producteur. Tout nouvel EventType sans
# producteur DOIT être soit câblé, soit ajouté ici avec une justification.
ALLOWED_UNPRODUCED: set[str] = {
    # ZSAV3 — activité SAV planifiée à échéance : EventType déclaré comme seam
    # de notification ; son producteur (balayage cron des activités SAV échues)
    # est planifié séparément et n'est pas câblé dans ce repo.
    "SAV_ACTIVITE_DUE",
}


def declared_signals():
    """{nom -> Signal} pour chaque ``Signal`` déclaré dans ``core.events``."""
    return {
        name: obj
        for name, obj in vars(events).items()
        if isinstance(obj, django.dispatch.Signal)
    }


def signal_has_receiver(signal: django.dispatch.Signal) -> bool:
    """True si au moins un récepteur est enregistré (connecté) sur ``signal``.

    Les récepteurs sont câblés dans les ``apps.py`` ``ready()`` exécutés par
    ``django.setup()`` avant les tests, donc ``signal.receivers`` est peuplé
    dès qu'un abonné existe. On ne compte pas les seuls lookups morts (weakref
    déjà collectée) : dans un process de test frais il n'y en a pas, mais on
    reste prudent en exigeant au moins une entrée.
    """
    return len(signal.receivers) > 0


def _eventtype_members() -> dict[str, str]:
    """{NOM_MEMBRE -> valeur_str} de l'énum ``EventType`` — lus par AST.

    ``EventType`` est une ``TextChoices`` : chaque membre vaut soit
    ``'valeur'``, soit ``('valeur', 'Libellé')``. On relève le NOM du membre et
    sa VALEUR chaîne (le premier élément) pour pouvoir détecter un producteur
    référençant soit ``EventType.NOM`` soit la chaîne ``'valeur'``.
    """
    tree = ast.parse(EVENTTYPE_FILE.read_text(encoding="utf-8"))
    members: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "EventType":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and stmt.targets:
                    tgt = stmt.targets[0]
                else:
                    continue
                if not (isinstance(tgt, ast.Name) and tgt.id.isupper()):
                    continue
                value = stmt.value
                str_value = ""
                if isinstance(value, ast.Tuple) and value.elts:
                    first = value.elts[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        str_value = first.value
                elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                    str_value = value.value
                members[tgt.id] = str_value
    return members


_PRODUCER_RE = re.compile(r"EventType\.([A-Z_]+)")
_STRING_RE = re.compile(r"['\"]([a-z0-9_]+)['\"]")


def _produced_eventtypes() -> set[str]:
    """Membres ``EventType`` RÉFÉRENCÉS (produits) dans le code source.

    Balaie tous les ``.py`` sous ``apps/`` et ``core/`` HORS fichiers de test,
    HORS migrations et HORS le fichier de définition de l'énum, puis relève :

    * chaque ``EventType.<NOM>`` (accès par attribut), et
    * chaque littéral chaîne correspondant à la VALEUR d'un membre (les
      producteurs QJ2 passent la valeur ``'lead_new'``/``'devis_opened'`` à
      ``notify_many()`` plutôt que ``EventType.LEAD_NEW``).

    Un membre référencé de l'une ou l'autre façon compte comme produit.
    """
    members = _eventtype_members()
    value_to_name = {v: n for n, v in members.items() if v}
    produced: set[str] = set()
    for root in (APPS_ROOT, CORE_ROOT):
        for path in root.rglob("*.py"):
            parts = set(path.parts)
            if "migrations" in parts:
                continue
            name = path.name
            if name.startswith("test") or name.startswith("tests"):
                continue
            if path == EVENTTYPE_FILE:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            produced.update(_PRODUCER_RE.findall(text))
            for literal in _STRING_RE.findall(text):
                if literal in value_to_name:
                    produced.add(value_to_name[literal])
    return produced


def _referenced_signal_names() -> set[str]:
    """Noms de signaux ``events.<name>`` passés à ``@receiver(...)``.

    Balaie tous les ``receivers.py`` sous ``apps/`` et relève les décorateurs
    ``@receiver(<sig>, ...)`` dont le premier argument est ``events.<name>`` ou
    un ``<name>`` importé depuis ``core.events`` — pour vérifier ensuite qu'ils
    pointent un signal réellement déclaré.
    """
    names: set[str] = set()
    for path in APPS_ROOT.rglob("receivers.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        # Noms importés depuis core.events (from core.events import X [as Y]) :
        # on mappe le nom LOCAL (l'alias Y, ou X sans alias) vers le nom RÉEL de
        # l'attribut dans core.events (X) — un import aliasé
        # (``import incident_declared as incident_declared_bus``) pointe bien un
        # signal existant : c'est le nom D'ORIGINE qu'il faut vérifier, pas
        # l'alias local (sinon le scan crée un faux « signal inexistant »).
        imported_from_events: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "core.events":
                for alias in node.names:
                    imported_from_events[alias.asname or alias.name] = alias.name
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not (isinstance(deco, ast.Call)
                        and isinstance(deco.func, ast.Name)
                        and deco.func.id == "receiver"):
                    continue
                if not deco.args:
                    continue
                first = deco.args[0]
                if (isinstance(first, ast.Attribute)
                        and isinstance(first.value, ast.Name)
                        and first.value.id == "events"):
                    names.add(first.attr)
                elif (isinstance(first, ast.Name)
                        and first.id in imported_from_events):
                    names.add(imported_from_events[first.id])
    return names


def eventtype_coverage():
    """Renvoie (noms_declares, noms_produits) — deux ``set[str]``."""
    return set(_eventtype_members()), _produced_eventtypes()


def orphan_signals() -> set[str]:
    """Signaux sans récepteur ET non listés dans ALLOWED_UNCONSUMED."""
    return {
        name
        for name, sig in declared_signals().items()
        if not signal_has_receiver(sig) and name not in ALLOWED_UNCONSUMED
    }


def unproduced_eventtypes() -> set[str]:
    """EventTypes sans producteur ET non listés dans ALLOWED_UNPRODUCED."""
    members, produced = eventtype_coverage()
    return {m for m in members if m not in produced and m not in ALLOWED_UNPRODUCED}


def dangling_receiver_signals() -> set[str]:
    """Signaux référencés par un @receiver mais absents de core.events."""
    declared = set(declared_signals())
    return {n for n in _referenced_signal_names() if n not in declared}


# --- NTPLT12 — couverture du CATALOGUE d'événements -------------------------


def uncatalogued_events() -> set[str]:
    """Signaux déclarés dans ``core.events`` mais ABSENTS de
    ``core.event_catalog.CATALOG``.

    Un ensemble non vide fait échouer le test de couverture NTPLT12 : tout
    nouvel événement émis DOIT être documenté au catalogue (contrat
    d'intégration stable pour les équipes IT du client)."""
    from core import event_catalog
    return set(declared_signals()) - event_catalog.catalog_names()


def catalogued_but_undeclared() -> set[str]:
    """Entrées du catalogue qui ne correspondent à AUCUN signal déclaré.

    Détecte un catalogue qui référence un événement supprimé/renommé du bus —
    l'autre sens de la dérive."""
    from core import event_catalog
    return event_catalog.catalog_names() - set(declared_signals())


# --- WIR139 — parité clés cataloguées / kwargs réels des émetteurs -----------

# Signaux déclarés dont AUCUN émetteur statique (`<signal>.send(...)`) n'existe
# dans le code (« seams » posés côté récepteur seul) : la parité de payload ne
# peut donc pas être vérifiée par introspection du source. Leur entrée au
# catalogue reste purement documentaire tant qu'un producteur n'existe pas.
NO_STATIC_EMITTER = {
    # ``document_produit`` : signal générique consommé par ged/receivers, jamais
    # émis directement aujourd'hui (voir apps/ged/services.py — « jamais appelé
    # directement par l'app »).
    "document_produit",
    # ``lead_erased`` (PUB100) : « seam » posé côté récepteur seul — adsengine
    # (on_lead_erased) anonymise ses miroirs sur effacement CNDP d'un lead CRM,
    # mais aucun producteur ne l'émet encore dans le code (le flux d'effacement
    # CRM viendra dans une tâche ultérieure). Son entrée au catalogue reste
    # documentaire tant qu'un émetteur statique n'existe pas.
    "lead_erased",
}


def emitter_payload_keys() -> dict:
    """{nom_signal -> set(kwargs)} relevés sur les appels ``<signal>.send(...)``.

    Balaie tous les ``.py`` de ``apps/`` et ``core/`` HORS tests/migrations et,
    pour chaque appel ``send`` porté par un signal de ``core.events`` (importé
    directement, aliasé, ou accédé via ``events.<name>``), relève les NOMS des
    arguments nommés (hors ``sender``). Un signal émis à plusieurs endroits
    reçoit l'UNION de ses clés — le catalogue documente donc toutes les clés que
    l'événement peut porter. C'est le pendant « émetteur » d'``uncatalogued_events``
    (couverture des NOMS) : il vérifie la parité des CLÉS de payload (WIR139).
    """
    declared = set(declared_signals())
    keys: dict = {name: set() for name in declared}
    for root in (APPS_ROOT, CORE_ROOT):
        for path in root.rglob("*.py"):
            if "migrations" in path.parts:
                continue
            if path.name.startswith("test"):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            # nom local (alias éventuel) -> nom réel du signal dans core.events.
            alias: dict = {}
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                is_events = node.module == "core.events" or (
                    node.module == "events" and (node.level or 0) >= 1)
                if is_events:
                    for a in node.names:
                        alias[a.asname or a.name] = a.name
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "send"):
                    continue
                obj = node.func.value
                sig = None
                if isinstance(obj, ast.Name) and obj.id in alias:
                    sig = alias[obj.id]
                elif (isinstance(obj, ast.Attribute)
                      and isinstance(obj.value, ast.Name)
                      and obj.value.id == "events"):
                    sig = obj.attr
                if sig in declared:
                    keys[sig] |= {
                        kw.arg for kw in node.keywords
                        if kw.arg and kw.arg != "sender"
                    }
    return keys


def catalog_payload_mismatches() -> dict:
    """{nom_signal -> (clés_cataloguées, clés_réelles)} pour chaque divergence.

    Pour tout signal DÉCLARÉ, CATALOGUÉ et doté d'au moins un émetteur statique
    (hors ``NO_STATIC_EMITTER``), compare l'ensemble des clés de payload du
    catalogue à l'union des kwargs réellement envoyés. Un dict non vide fait
    échouer le test de parité WIR139 : un émetteur qui change ses kwargs sans
    mettre le catalogue à jour (ou l'inverse) casse le build au lieu de laisser
    le contrat d'intégration dériver silencieusement."""
    from core import event_catalog
    emitted = emitter_payload_keys()
    mismatches: dict = {}
    for name in set(declared_signals()) & event_catalog.catalog_names():
        if name in NO_STATIC_EMITTER:
            continue
        real = emitted.get(name, set())
        if not real:
            # Aucun émetteur trouvé (ni listé NO_STATIC_EMITTER) : signalé pour
            # forcer soit un émetteur, soit une réservation explicite.
            mismatches[name] = (set(event_catalog.entry(name)["payload"]), set())
            continue
        catalogued = set(event_catalog.entry(name)["payload"])
        if catalogued != real:
            mismatches[name] = (catalogued, real)
    return mismatches
