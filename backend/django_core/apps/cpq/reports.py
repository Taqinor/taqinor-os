"""Rapports CPQ qui LISENT le domaine Ventes (NTCPQ19/23/24/25).

Module SÉPARÉ de ``selectors.py`` À DESSEIN : ``ventes.models`` importe
``cpq.selectors`` (NTCPQ8, propriété ``approbation_remise_en_attente``) ; si
ces lectures vivaient dans ``selectors.py``, la chaîne
``ventes.models -> cpq.selectors -> ventes.selectors`` rouvrirait le cycle
inter-domaines verrouillé par le contrat import-linter M1. Ici, rien n'importe
ce module depuis ``ventes`` — le contrat reste intact.

Toutes les lectures cross-app passent par ``apps.ventes.selectors`` (jamais
``ventes.models``) et restent scopées société.
"""
from .models import ContrainteCompatibilite, EtapeApprobationDevis
from .selectors import devis_marge_sous_seuil, etat_configuration_devis


def rapport_approbations(company, *, approbateur_id=None):
    """NTCPQ25 — Historique des approbations de remise (NTCPQ7) sur TOUTE
    la société, une ligne par ``EtapeApprobationDevis``.

    ``remise_demandee`` reflète la remise globale COURANTE du devis (aucun
    snapshot de la remise au moment de l'étape n'existe côté modèle — la
    remise réelle qui a déclenché l'étape peut donc différer si le devis a
    été modifié depuis). ``delai_traitement_heures`` = ``decision_le -
    date_creation`` en heures (arrondi 2 décimales), ``None`` tant que
    l'étape est ``en_attente``. ``motif_rejet`` = ``commentaire`` de
    l'étape UNIQUEMENT quand ``statut == rejete`` (vide sinon — le
    commentaire d'une approbation n'est pas un motif de rejet).

    ``?approbateur_id=`` filtre strictement sur les étapes assignées à CET
    approbateur (une étape sans ``approbateur`` — jamais réclamée — n'est
    listée que sans ce filtre). Renvoie une liste de dicts JSON-safe,
    triée par date de création décroissante."""
    qs = (EtapeApprobationDevis.objects
          .filter(company=company)
          .select_related('devis', 'approbateur', 'regle')
          .order_by('-date_creation', 'id'))
    if approbateur_id:
        qs = qs.filter(approbateur_id=approbateur_id)

    lignes = []
    for etape in qs:
        devis = etape.devis
        delai_heures = None
        if etape.decision_le is not None:
            delta = etape.decision_le - etape.date_creation
            delai_heures = round(delta.total_seconds() / 3600, 2)
        lignes.append({
            'etape_id': etape.id,
            'devis_id': devis.id if devis is not None else None,
            'devis_reference': getattr(devis, 'reference', ''),
            'niveau': etape.niveau,
            'niveau_approbation': etape.niveau_approbation,
            'remise_demandee': (
                str(devis.remise_globale) if devis is not None
                and devis.remise_globale is not None else None),
            'approbateur': (
                getattr(etape.approbateur, 'username', None)
                if etape.approbateur_id else None),
            'statut': etape.statut,
            'date_creation': etape.date_creation.isoformat(),
            'decision_le': (
                etape.decision_le.isoformat()
                if etape.decision_le else None),
            'delai_traitement_heures': delai_heures,
            'motif_rejet': (
                etape.commentaire
                if etape.statut == EtapeApprobationDevis.Statut.REJETE
                else ''),
        })
    return lignes


_APPROBATIONS_COLONNES = [
    ('devis_reference', 'Devis'), ('niveau', 'Niveau'),
    ('niveau_approbation', "Palier d'approbation"),
    ('remise_demandee', 'Remise (%)'), ('approbateur', 'Approbateur'),
    ('statut', 'Statut'), ('date_creation', 'Créée le'),
    ('decision_le', 'Décidée le'),
    ('delai_traitement_heures', 'Délai de traitement (h)'),
    ('motif_rejet', 'Motif de rejet'),
]


def rapport_approbations_xlsx(lignes):
    """NTCPQ25 — classeur .xlsx de ``rapport_approbations`` (openpyxl direct,
    même patron auto-suffisant que ``apps.ventes.exports`` — jamais un
    passage par ``apps/dataimport``, hors périmètre de cette app)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from django.http import HttpResponse

    wb = Workbook()
    ws = wb.active
    ws.title = 'Historique approbations'
    bold = Font(bold=True)
    ws.append([label for _, label in _APPROBATIONS_COLONNES])
    for c in ws[1]:
        c.font = bold
    for ligne in lignes:
        ws.append([ligne.get(champ) for champ, _ in _APPROBATIONS_COLONNES])

    resp = HttpResponse(content_type=(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
    resp['Content-Disposition'] = (
        'attachment; filename="historique-approbations.xlsx"')
    wb.save(resp)
    return resp


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
