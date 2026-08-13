"""Rapports CPQ qui LISENT le domaine Ventes (NTCPQ19/23/24).

Module SÉPARÉ de ``selectors.py`` À DESSEIN : ``ventes.models`` importe
``cpq.selectors`` (NTCPQ8, propriété ``approbation_remise_en_attente``) ; si
ces lectures vivaient dans ``selectors.py``, la chaîne
``ventes.models -> cpq.selectors -> ventes.selectors`` rouvrirait le cycle
inter-domaines verrouillé par le contrat import-linter M1. Ici, rien n'importe
ce module depuis ``ventes`` — le contrat reste intact.

Toutes les lectures cross-app passent par ``apps.ventes.selectors`` (jamais
``ventes.models``) et restent scopées société.
"""
from .models import ContrainteCompatibilite
from .selectors import devis_marge_sous_seuil, etat_configuration_devis


def suggestions_produit(*, company, produit_id, limite=3):
    """NTCPQ19 — Suggestions de vente croisée / montée en gamme (max 3).

    Deux sources, dans cet ordre :

      1. les contraintes ``RECOMMANDE`` (NTCPQ1) déclarées pour ce produit —
         volonté explicite du bureau d'études ;
      2. la FRÉQUENCE DE CO-ACHAT calculée en lecture seule sur l'historique des
         devis ACCEPTÉS de la société (via ``ventes.selectors.frequence_co_achat``
         — jamais un import de ``ventes.models``).

    Purement SUGGESTIF : aucune ligne n'est ajoutée, aucun prix n'est modifié.
    Renvoie ``[{produit_id, nom, source, occurrences}, ...]``."""
    from apps.ventes.selectors import frequence_co_achat
    from apps.stock.models import Produit

    try:
        produit_id = int(produit_id)
    except (TypeError, ValueError):
        return []

    ordonnes = []
    vus = set()
    recommandes = ContrainteCompatibilite.objects.filter(
        company=company, produit_a_id=produit_id,
        type=ContrainteCompatibilite.TypeContrainte.RECOMMANDE
    ).order_by('id').values_list('produit_b_id', flat=True)
    for pid in recommandes:
        if pid in vus or pid == produit_id:
            continue
        vus.add(pid)
        ordonnes.append((pid, 'recommande', 0))

    if len(ordonnes) < limite:
        for pid, occurrences in frequence_co_achat(
                company, produit_id, limite=limite * 5):
            if pid in vus or pid == produit_id:
                continue
            vus.add(pid)
            ordonnes.append((pid, 'co_achat', occurrences))
            if len(ordonnes) >= limite:
                break

    ordonnes = ordonnes[:limite]
    noms = dict(Produit.objects.filter(
        company=company, id__in=[p for p, _, _ in ordonnes]
    ).values_list('id', 'nom'))
    return [{
        'produit_id': pid,
        'nom': noms.get(pid, ''),
        'source': source,
        'occurrences': occurrences,
    } for pid, source, occurrences in ordonnes if pid in noms]


def rapport_conformite_configurations(company, *, date_debut=None,
                                      date_fin=None, commercial_id=None):
    """NTCPQ24 — Taux de CONFORMITÉ des configurations sur une période.

    Pour chaque devis ENVOYÉ de la période : la configuration est-elle exempte
    de violation (NTCPQ1 compatibilité + NTCPQ2 règles, cf. NTCPQ21) ? Renvoie
    ::

        {'total', 'conformes', 'non_conformes', 'taux_conformite_pct',
         'lignes': [{devis_id, reference, date_envoi, commercial, conforme,
                     bloquant, nb_violations}, ...]}

    Usage INTERNE (bureau d'études / direction commerciale) — jamais un
    document client. NB : l'état est évalué sur la configuration COURANTE du
    devis (le badge n'est pas historisé), ce que le rapport assume."""
    from apps.ventes.selectors import devis_envoyes_periode

    lignes = []
    conformes = 0
    for devis in devis_envoyes_periode(
            company, date_debut=date_debut, date_fin=date_fin,
            commercial_id=commercial_id):
        etat = etat_configuration_devis(devis)
        if etat['configuration_valide']:
            conformes += 1
        lignes.append({
            'devis_id': devis.id,
            'reference': devis.reference,
            'date_envoi': (devis.date_envoi.date().isoformat()
                           if devis.date_envoi else None),
            'commercial': (getattr(devis.created_by, 'username', None)
                           if devis.created_by_id else None),
            'conforme': etat['configuration_valide'],
            'bloquant': etat['bloquant'],
            'nb_violations': len(etat['violations']),
        })

    total = len(lignes)
    return {
        'total': total,
        'conformes': conformes,
        'non_conformes': total - conformes,
        'taux_conformite_pct': (
            round(conformes * 100.0 / total, 2) if total else 0.0),
        'lignes': lignes,
    }


def devis_sous_seuil_marge(company, *, commercial_id=None, famille=None):
    """NTCPQ23 — Devis EN COURS dont au moins une ligne est sous son seuil de
    marge (NTCPQ6). Usage INTERNE staff strict — ne quitte jamais l'ERP.

    Seuls les devis non encore acceptés sont listés : dès qu'une ligne repasse
    au-dessus du seuil (ou que le devis est accepté), il disparaît de la liste.
    Filtres optionnels : ``commercial_id`` (créateur du devis) et ``famille``
    (nom de catégorie concernée). Lecture cross-app ventes via son
    ``selectors`` (jamais un import de ses modèles)."""
    from apps.ventes.selectors import devis_en_cours

    resultats = []
    for devis in devis_en_cours(company):
        if commercial_id and str(devis.created_by_id or '') != str(commercial_id):
            continue
        if not devis_marge_sous_seuil(devis):
            continue
        familles = sorted({
            ligne.produit.categorie.nom
            for ligne in devis.lignes.all()
            if ligne.produit_id and ligne.produit.categorie_id})
        if famille and famille not in familles:
            continue
        resultats.append({
            'devis_id': devis.id,
            'reference': devis.reference,
            'statut': devis.statut,
            'client_nom': getattr(devis.client, 'nom', None),
            'commercial_id': devis.created_by_id,
            'commercial': (getattr(devis.created_by, 'username', None)
                           if devis.created_by_id else None),
            'familles': familles,
            'total_ht': str(devis.total_ht),
        })
    return resultats
