"""ASG5 — Format de semis YAML + validateur de l'arbre d'hypothèses (§4).

Le CONTRAT du point de contact IA « au début » (§4) : au jour 0, Claude + le
fondateur SÈMENT l'arbre (nœuds, priors en pseudo-comptes, liens d'invalidation)
via UN fichier YAML — après quoi le moteur tourne sans IA. Ce module lit ce
fichier, le VALIDE (refus avec raisons FR), et l'importe de façon IDEMPOTENTE
(double import = même état).

Format (voir ``docs/engine/seed-format.md`` pour le contrat complet) ::

    version: 1
    nodes:
      - key: hook_facture              # identité LOCALE au fichier (références)
        classe: creatif                # creatif | angle | audience_structure
        enonce_fr: "Le hook facture convertit mieux."
        enjeux_s: 0.7                   # ∈ [0,1]
        pertinence_r: 0.8              # ∈ [0,1]
        tags_saison: [ramadan]         # optionnel
        parent: null                   # key d'un autre nœud (optionnel)
        invalidation_links: [audience_urbain]   # keys (optionnel)
        prior: {alpha0: 3, beta0: 2}   # pseudo-comptes (optionnel, déf. 1/1)
        demi_vie_semaines: 8           # override optionnel (déf. = classe)
        statut: assumed                # optionnel (déf. assumed)

**Identité idempotente = ``(company, classe, enonce_fr)``.** Le modèle ne porte
PAS de champ ``key`` (hors périmètre de cette lane) : ``key`` sert UNIQUEMENT aux
références internes au fichier (parent / invalidation_links). Réimporter le même
énoncé le RETROUVE et le met à jour en place — jamais un doublon. Le posterior
appris (``alpha``/``beta``) et le cycle de vie (``statut``) NE sont PAS écrasés à
la réimport : seules les propriétés DÉFINITIONNELLES (S/R/tags/prior/demi-vie)
sont rafraîchies. Un énoncé RÉÉCRIT est une hypothèse NEUVE (nouvel identifiant) —
c'est voulu.

Préflight (§4 / ADSENG38 étendu) : ``preflight`` vérifie que l'arbre est
exploitable — ≥ N nœuds testables ET au moins une hypothèse créatif testable
(sinon le backlog créatif n'a aucune hypothèse à alimenter). C'est de la LOGIQUE
d'agrégation pure (pas de vue HTTP). Multi-tenant : la société est toujours passée
explicitement, jamais élargie.
"""
from __future__ import annotations

import logging

import yaml

logger = logging.getLogger(__name__)

SEED_VERSION = 1

# Préflight (§4) : plancher de nœuds testables pour un arbre exploitable. §1 :
# « 2 à 4 nœuds vivants » à budget actuel — 2 est le plancher d'un arbre utile.
SEED_MIN_TESTABLE_NODES = 2


class SeedValidationError(Exception):
    """Semis invalide : porte la liste FR de TOUTES les raisons de refus."""

    def __init__(self, reasons_fr):
        self.reasons_fr = list(reasons_fr)
        super().__init__("Semis invalide : " + " ; ".join(self.reasons_fr))


# ── Chargement + validation ───────────────────────────────────────────────────
def load(seed):
    """Charge un semis en dict depuis une chaîne YAML ou un dict déjà parsé."""
    if isinstance(seed, dict):
        return seed
    return yaml.safe_load(seed) or {}


def _valid_classes():
    from .models import AssumptionNode
    return {c.value for c in AssumptionNode.Classe}


def _valid_statuts():
    from .models import AssumptionNode
    return {s.value for s in AssumptionNode.Statut}


def validate(seed):
    """Valide un semis et renvoie le dict parsé, ou lève ``SeedValidationError``.

    Collecte TOUTES les raisons FR d'un coup (jamais un échec à la fois) : version,
    liste de nœuds non vide, et par nœud — clé unique, classe/statut légaux, énoncé
    non vide, S/R ∈ [0,1], tags liste, priors > 0, demi-vie entière positive,
    parent/invalidation_links référençant des clés existantes, pas d'auto-parent.
    """
    data = load(seed)
    reasons = []
    classes = _valid_classes()
    statuts = _valid_statuts()

    version = data.get('version')
    if version != SEED_VERSION:
        reasons.append(
            f"Version de semis inattendue ({version!r}) : attendu {SEED_VERSION}.")

    nodes = data.get('nodes')
    if not isinstance(nodes, list) or not nodes:
        reasons.append("Le semis doit contenir une liste « nodes » non vide.")
        raise SeedValidationError(reasons)

    keys = set()
    for i, node in enumerate(nodes):
        label = f"nœud #{i + 1}"
        if not isinstance(node, dict):
            reasons.append(f"{label} : doit être un objet (clé/valeur).")
            continue
        key = node.get('key')
        if not key or not isinstance(key, str):
            reasons.append(f"{label} : « key » manquante ou invalide.")
        elif key in keys:
            reasons.append(f"{label} : clé « {key} » dupliquée.")
        else:
            keys.add(key)
        label = f"nœud « {key} »" if key else label

        classe = node.get('classe')
        if classe not in classes:
            reasons.append(
                f"{label} : classe « {classe} » invalide "
                f"(attendu : {', '.join(sorted(classes))}).")

        enonce = node.get('enonce_fr')
        if not enonce or not str(enonce).strip():
            reasons.append(f"{label} : « enonce_fr » manquant ou vide.")

        for field in ('enjeux_s', 'pertinence_r'):
            val = node.get(field)
            if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
                reasons.append(
                    f"{label} : « {field} » doit être un nombre dans [0, 1] "
                    f"(reçu {val!r}).")

        tags = node.get('tags_saison', [])
        if tags and not isinstance(tags, list):
            reasons.append(f"{label} : « tags_saison » doit être une liste.")

        prior = node.get('prior')
        if prior is not None:
            if not isinstance(prior, dict):
                reasons.append(f"{label} : « prior » doit être un objet.")
            else:
                for pk_field in ('alpha0', 'beta0'):
                    pv = prior.get(pk_field)
                    if pv is not None and (
                            not isinstance(pv, (int, float)) or pv <= 0):
                        reasons.append(
                            f"{label} : prior « {pk_field} » doit être > 0.")

        hl = node.get('demi_vie_semaines')
        if hl is not None and (not isinstance(hl, int) or hl <= 0):
            reasons.append(
                f"{label} : « demi_vie_semaines » doit être un entier > 0.")

        statut = node.get('statut')
        if statut is not None and statut not in statuts:
            reasons.append(f"{label} : statut « {statut} » invalide.")

        parent = node.get('parent')
        if parent is not None and parent == key:
            reasons.append(f"{label} : un nœud ne peut pas être son propre parent.")

    # Références (parent / invalidation_links) : doivent pointer une clé connue.
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        key = node.get('key')
        label = f"nœud « {key} »" if key else f"nœud #{i + 1}"
        parent = node.get('parent')
        if parent is not None and parent not in keys:
            reasons.append(f"{label} : parent « {parent} » introuvable.")
        for link in (node.get('invalidation_links') or []):
            if link not in keys:
                reasons.append(
                    f"{label} : lien d'invalidation « {link} » introuvable.")

    if reasons:
        raise SeedValidationError(reasons)
    return data


# ── Import idempotent ─────────────────────────────────────────────────────────
def import_seed(company, seed, *, validate_first=True):
    """Importe (idempotent) un semis dans l'arbre d'une société.

    Valide d'abord (sauf ``validate_first=False``), puis upsert chaque nœud par
    ``(company, classe, enonce_fr)`` et câble parent + invalidation_links. Le
    posterior appris et le ``statut`` ne sont PAS écrasés à la réimport (seules les
    propriétés définitionnelles le sont). Double import = même état. Renvoie
    ``{'created', 'updated', 'nodes': {key: pk}}``.
    """
    from django.db import transaction

    from .models import AssumptionNode

    data = validate(seed) if validate_first else load(seed)
    created = updated = 0
    key_to_node = {}

    with transaction.atomic():
        # Passe 1 — upsert des nœuds (sans relations).
        for spec in data['nodes']:
            prior = spec.get('prior') or {}
            alpha0 = float(prior.get('alpha0', 1.0))
            beta0 = float(prior.get('beta0', 1.0))
            defn = {
                'enjeux_s': float(spec['enjeux_s']),
                'pertinence_r': float(spec['pertinence_r']),
                'tags_saison': list(spec.get('tags_saison') or []),
                'alpha0': alpha0,
                'beta0': beta0,
                'demi_vie_semaines': spec.get('demi_vie_semaines'),
            }
            node = AssumptionNode.objects.filter(
                company=company, classe=spec['classe'],
                enonce_fr=spec['enonce_fr']).first()
            if node is None:
                node = AssumptionNode.objects.create(
                    company=company, classe=spec['classe'],
                    enonce_fr=spec['enonce_fr'],
                    statut=spec.get('statut',
                                    AssumptionNode.Statut.ASSUMED),
                    # Le posterior DÉMARRE au prior (démarrage à froid §3.4).
                    alpha=alpha0, beta=beta0, **defn)
                created += 1
            else:
                # Réimport : on NE touche PAS alpha/beta (appris) ni statut (cycle
                # de vie) — seulement les propriétés définitionnelles.
                for field, value in defn.items():
                    setattr(node, field, value)
                node.save(update_fields=[*defn.keys(), 'updated_at'])
                updated += 1
            key_to_node[spec['key']] = node

        # Passe 2 — relations (parent + invalidation_links).
        for spec in data['nodes']:
            node = key_to_node[spec['key']]
            parent_key = spec.get('parent')
            new_parent = key_to_node[parent_key] if parent_key else None
            if node.parent_id != (new_parent.pk if new_parent else None):
                node.parent = new_parent
                node.save(update_fields=['parent', 'updated_at'])
            link_keys = spec.get('invalidation_links') or []
            node.invalidation_links.set(
                [key_to_node[k] for k in link_keys])

    logger.info(
        'seeding.import_seed: société=%s créés=%s mis à jour=%s',
        company.pk, created, updated)
    return {
        'created': created, 'updated': updated,
        'nodes': {k: n.pk for k, n in key_to_node.items()},
    }


# ── Préflight de semis (§4 / ADSENG38 étendu) ─────────────────────────────────
def _testable_nodes(company):
    """Nœuds testables d'une société : non retirés, avec S>0 et R>0 (un nœud à
    enjeux ou pertinence nuls n'est jamais mis en file — §3.3)."""
    from .models import AssumptionNode
    return AssumptionNode.objects.filter(
        company=company, enjeux_s__gt=0, pertinence_r__gt=0).exclude(
        statut=AssumptionNode.Statut.RETIRED)


def preflight(company):
    """Préflight de l'arbre semé (§4) : renvoie ``{'ready', 'checks', 'missing_fr'}``.

    Deux portes (ADSENG38 étendu) :
      * ``tree_testable`` — l'arbre porte ≥ ``SEED_MIN_TESTABLE_NODES`` nœuds
        testables (sinon rien à ordonnancer) ;
      * ``backlog_compatible`` — au moins une hypothèse de classe CRÉATIF testable
        existe (sinon le backlog créatif n'a aucune hypothèse à alimenter).
    """
    from .models import AssumptionNode

    testable = _testable_nodes(company)
    testable_count = testable.count()
    tree_ok = testable_count >= SEED_MIN_TESTABLE_NODES
    creatif_ok = testable.filter(
        classe=AssumptionNode.Classe.CREATIF).exists()

    checks = [
        {
            'key': 'tree_testable', 'ok': tree_ok,
            'detail_fr': '' if tree_ok else (
                f"Arbre insuffisant : {testable_count} nœud(s) testable(s) "
                f"(minimum {SEED_MIN_TESTABLE_NODES})."),
        },
        {
            'key': 'backlog_compatible', 'ok': creatif_ok,
            'detail_fr': '' if creatif_ok else (
                "Aucune hypothèse créatif testable : le backlog créatif n'a "
                "aucune hypothèse à alimenter."),
        },
    ]
    missing = [c['detail_fr'] for c in checks if not c['ok']]
    return {'ready': not missing, 'checks': checks, 'missing_fr': missing}
