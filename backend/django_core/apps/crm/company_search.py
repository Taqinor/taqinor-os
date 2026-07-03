"""QC1 — Recherche d'entreprise sur les DONNÉES PROPRES de la société.

Autocomplete « à la Odoo » sans coût ni risque ToS : on suggère des
correspondances tirées des enregistrements que la société possède déjà
(clients + fournisseurs + leads), filtrés à sa propre société, sur une
recherche floue de ``nom``/``ice``.

PROVIDER SEAM (pour QC2) : la recherche passe par ``search_companies`` qui
délègue au provider actif. Par défaut, le provider « own-data » (ci-dessous)
n'interroge que la base locale. QC2 pourra enregistrer un provider basé sur un
registre licencié (Inforisk/Charika/OMPIC) derrière un flag, sans toucher à
l'appelant : il suffira de fournir un autre ``provider`` à ``search_companies``
ou de changer le provider par défaut. Aucun scraping — rule #5.

Fonctions pures côté données (pas d'I/O réseau) : sûr à appeler dans une vue.
"""
from __future__ import annotations


# Nombre maximum de suggestions renvoyées (léger : autocomplete, pas une liste).
MAX_RESULTS = 12


def _norm(value) -> str:
    return (str(value or '')).strip().lower()


def _client_hit(obj) -> dict:
    return {
        'source': 'client',
        'id': obj.id,
        'nom': obj.nom,
        'ice': obj.ice or '',
        'if_fiscal': obj.if_fiscal or '',
        'rc': obj.rc or '',
        'adresse': obj.adresse or '',
        'telephone': obj.telephone or '',
        'email': obj.email or '',
    }


def _fournisseur_hit(obj) -> dict:
    # Le fournisseur ne porte pas d'identifiants légaux (ICE/IF/RC) dans le
    # modèle : on renvoie les champs disponibles, le reste vide.
    return {
        'source': 'fournisseur',
        'id': obj.id,
        'nom': obj.nom,
        'ice': '',
        'if_fiscal': '',
        'rc': '',
        'adresse': obj.adresse or '',
        'telephone': obj.telephone or '',
        'email': obj.email or '',
    }


def _lead_hit(obj) -> dict:
    # Un lead peut porter une raison sociale (``societe``) distincte du nom du
    # contact ; on privilégie ``societe`` pour l'autocomplete entreprise.
    return {
        'source': 'lead',
        'id': obj.id,
        'nom': (obj.societe or obj.nom or ''),
        'ice': '',
        'if_fiscal': '',
        'rc': '',
        'adresse': obj.adresse or '',
        'telephone': obj.telephone or '',
        'email': obj.email or '',
    }


def own_data_search(company, q: str, *, limit: int = MAX_RESULTS) -> list[dict]:
    """Provider par défaut : recherche floue sur les données PROPRES de la
    société (clients + fournisseurs + leads), scopée à ``company``.

    Match insensible à la casse sur ``nom``/``societe``/``ice``. Retourne une
    liste de dicts normalisés (voir ``_*_hit``), dédupliquée grossièrement par
    (nom, ice) pour ne pas proposer trois fois la même entreprise.
    """
    # Imports paresseux : company_search est une brique de bas niveau, on évite
    # d'importer les modèles au chargement du module (cycles / coût). Le
    # référentiel fournisseur (autre app) est lu via son SÉLECTEUR, jamais en
    # important apps.stock.models directement (règle de frontière cross-app).
    from django.db.models import Q
    from .models import Client, Lead
    from apps.stock.selectors import search_fournisseurs

    q = (q or '').strip()
    if not q or company is None:
        return []

    clients = list(
        Client.objects.filter(company=company)
        .filter(Q(nom__icontains=q) | Q(ice__icontains=q))
        .order_by('nom')[:limit])
    fournisseurs = search_fournisseurs(company, q, limit=limit)
    leads = list(
        Lead.objects.filter(company=company)
        .filter(Q(nom__icontains=q) | Q(societe__icontains=q))
        .order_by('nom')[:limit])

    hits = (
        [_client_hit(c) for c in clients]
        + [_fournisseur_hit(f) for f in fournisseurs]
        + [_lead_hit(le) for le in leads]
    )

    # Déduplication grossière : (nom normalisé, ice) — on garde la 1re
    # occurrence (les clients passent en premier, donc priorité au client
    # existant qui porte le plus d'identifiants légaux).
    seen = set()
    deduped = []
    for h in hits:
        key = (_norm(h['nom']), _norm(h['ice']))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)
        if len(deduped) >= limit:
            break
    return deduped


def search_companies(company, q: str, *, provider=None, limit: int = MAX_RESULTS) -> list[dict]:
    """Point d'entrée unique de l'autocomplete entreprise (PROVIDER SEAM).

    ``provider`` est une fonction ``(company, q, *, limit) -> list[dict]`` ;
    par défaut ``own_data_search`` (données propres). QC2 branchera ici un
    provider registre-licencié derrière un flag, sans changer l'appelant.
    """
    provider = provider or own_data_search
    return provider(company, q, limit=limit)
