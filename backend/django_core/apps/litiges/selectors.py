"""Sélecteurs (lecture seule) du module ``apps.litiges``.

Fonctions utilitaires que d'autres apps peuvent importer **via import local**
(dans le corps d'une fonction, jamais au niveau module) pour éviter les
dépendances cycliques et respecter les contrats d'import CI-enforced.
"""
from decimal import Decimal


def relances_suspendues_pour_facture(facture_id: int, company) -> bool:
    """Retourne True si au moins un litige ouvert bloque les relances pour
    cette facture.

    LITIGE3 — utilisé par ``ventes.scheduled.relance_reminders`` (via import
    local) pour court-circuiter l'envoi sur les factures en litige financier
    bloquant.

    Critères :
    - source_type == 'facture'
    - source_id == facture_id
    - company == company (isolation multi-tenant)
    - statut pas terminal (pas 'resolue' ni 'rejetee')
    - bloque_relances == True

    Args:
        facture_id: PK de la Facture à vérifier.
        company: instance ``authentication.Company`` de la société.

    Returns:
        True si un litige bloquant est actif, False sinon.
    """
    from .models import Reclamation

    STATUTS_OUVERTS = (
        Reclamation.Statut.OUVERTE,
        Reclamation.Statut.EN_TRAITEMENT,
    )
    return Reclamation.objects.filter(
        company=company,
        source_type='facture',
        source_id=facture_id,
        statut__in=STATUTS_OUVERTS,
        bloque_relances=True,
    ).exists()


def tableau_bord_litiges(company, debut=None, fin=None):
    """Tableau de bord des réclamations & litiges (LITIGE6, lecture seule).

    Agrégation pure sur les ``Reclamation`` existantes — aucun nouveau modèle.
    Multi-société : tout est scopé sur ``company`` (jamais lu du corps de
    requête côté API).

    Args:
        company: instance ``authentication.Company`` à scoper.
        debut: ``datetime.date`` ou chaîne ISO (``YYYY-MM-DD``) — borne basse
            INCLUSIVE sur ``date_creation`` (None = pas de borne basse).
        fin: ``datetime.date`` ou chaîne ISO (``YYYY-MM-DD``) — borne haute
            INCLUSIVE sur ``date_creation`` (None = pas de borne haute).

    Returns:
        dict sérialisable :
            {
                'ouvertes': int,
                'en_traitement': int,
                'resolues': int,
                'rejetees': int,
                'total': int,
                'montant_conteste_total': str,   # Decimal sérialisé
                'delai_resolution_moyen_jours': float | None,
                'delai_resolution_moyen_heures': float | None,
                'nb_resolues_avec_delai': int,
                'debut': str | None,             # ISO ou None
                'fin': str | None,
            }

    Le délai de résolution est calculé à partir des entrées « chatter »
    (``ReclamationActivity`` de type LOG dont ``new_value == 'resolue'``) :
    horodatage de résolution − ``date_creation`` de la réclamation. Si aucune
    réclamation résolue n'a de log de résolution exploitable, la moyenne vaut
    ``None`` (jamais de division par zéro).
    """
    import datetime as _dt

    from django.db.models import Count, Q, Sum
    from django.utils import timezone as _tz

    from .models import Reclamation, ReclamationActivity

    def _coerce_date(value):
        """date | 'YYYY-MM-DD' | None → date | None (chaîne invalide → None)."""
        if value is None or value == '':
            return None
        if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
            return value
        if isinstance(value, _dt.datetime):
            return value.date()
        from django.utils.dateparse import parse_date
        return parse_date(str(value))

    def _to_aware(d):
        return _tz.make_aware(
            _dt.datetime.combine(d, _dt.time.min), _tz.get_current_timezone())

    d_debut = _coerce_date(debut)
    d_fin = _coerce_date(fin)

    qs = Reclamation.objects.filter(company=company)
    if d_debut is not None:
        qs = qs.filter(date_creation__gte=_to_aware(d_debut))
    if d_fin is not None:
        # Borne haute INCLUSIVE → < lendemain à minuit.
        qs = qs.filter(
            date_creation__lt=_to_aware(d_fin) + _dt.timedelta(days=1))

    S = Reclamation.Statut
    compte = qs.aggregate(
        ouvertes=Count('id', filter=Q(statut=S.OUVERTE)),
        en_traitement=Count('id', filter=Q(statut=S.EN_TRAITEMENT)),
        resolues=Count('id', filter=Q(statut=S.RESOLUE)),
        rejetees=Count('id', filter=Q(statut=S.REJETEE)),
        total=Count('id'),
        montant=Sum('montant_conteste'),
    )

    # ── Délai de résolution moyen ────────────────────────────────────────────
    # Horodatage de résolution = date_creation du log LOG → 'resolue' le plus
    # récent de chaque réclamation résolue (dans la fenêtre + société).
    resolues_ids = list(
        qs.filter(statut=S.RESOLUE).values_list('id', 'date_creation'))
    creation_par_id = {rid: dc for rid, dc in resolues_ids}

    logs = (
        ReclamationActivity.objects.filter(
            company=company,
            reclamation_id__in=creation_par_id.keys(),
            type=ReclamationActivity.Kind.LOG,
            new_value=S.RESOLUE,
        )
        .order_by('reclamation_id', '-date_creation')
        .values_list('reclamation_id', 'date_creation')
    )
    resolution_par_id = {}
    for rid, dc in logs:
        # Premier vu par réclamation = le plus récent (tri -date_creation).
        if rid not in resolution_par_id:
            resolution_par_id[rid] = dc

    total_secondes = 0.0
    nb_delai = 0
    for rid, date_resolution in resolution_par_id.items():
        date_creation = creation_par_id.get(rid)
        if date_creation is None or date_resolution is None:
            continue
        delta = (date_resolution - date_creation).total_seconds()
        if delta < 0:
            continue
        total_secondes += delta
        nb_delai += 1

    if nb_delai:
        moyenne_secondes = total_secondes / nb_delai
        delai_jours = round(moyenne_secondes / 86400.0, 2)
        delai_heures = round(moyenne_secondes / 3600.0, 2)
    else:
        delai_jours = None
        delai_heures = None

    return {
        'ouvertes': compte['ouvertes'] or 0,
        'en_traitement': compte['en_traitement'] or 0,
        'resolues': compte['resolues'] or 0,
        'rejetees': compte['rejetees'] or 0,
        'total': compte['total'] or 0,
        'montant_conteste_total': str(compte['montant'] or Decimal('0')),
        'delai_resolution_moyen_jours': delai_jours,
        'delai_resolution_moyen_heures': delai_heures,
        'nb_resolues_avec_delai': nb_delai,
        'debut': d_debut.isoformat() if d_debut else None,
        'fin': d_fin.isoformat() if d_fin else None,
    }


def analyse_concurrents_perte(company):
    """LITIGE5 — Intelligence concurrentielle des litiges sur deals perdus.

    Agrégation pure (lecture seule) sur les ``Reclamation`` de la société qui
    portent un concurrent gagnant saisi (``concurrent_nom`` non vide). Étend le
    concept FG242 (concurrent/motif sur deal perdu) au niveau du litige, sans
    jamais importer ``apps.crm`` : le lead d'origine reste référencé par le
    couple lâche ``source_type='lead'`` / ``source_id`` porté par la réclamation.

    Multi-société : tout est scopé sur ``company`` (jamais lu du corps de
    requête côté API).

    Args:
        company: instance ``authentication.Company`` à scoper.

    Returns:
        dict sérialisable ::

            {
                'total_litiges_avec_concurrent': int,
                'par_concurrent': [          # trié, plus fréquent d'abord
                    {
                        'concurrent': str,
                        'nombre': int,
                        'prix_moyen': str | None,   # Decimal sérialisé ou None
                        'devise': str | None,       # devise majoritaire
                    },
                    ...
                ],
                'par_motif': [               # trié, plus fréquent d'abord
                    {'motif': str, 'nombre': int},
                    ...
                ],
            }

    Le prix moyen par concurrent ignore les prix non renseignés (None) ; si
    aucun prix n'est connu pour un concurrent, ``prix_moyen`` vaut ``None``
    (jamais de division par zéro). Les motifs vides sont ignorés.
    """
    from collections import Counter

    from .models import Reclamation

    qs = Reclamation.objects.filter(company=company).exclude(
        concurrent_nom='')

    # Agrégation côté Python : robuste, lisible, et le volume des litiges avec
    # concurrent saisi reste modeste.
    par_concurrent = {}      # nom -> {'nombre', 'somme_prix', 'nb_prix', devises}
    motifs = Counter()
    total = 0
    for nom, prix, devise, motif in qs.values_list(
            'concurrent_nom', 'concurrent_prix', 'concurrent_devise',
            'motif_perte'):
        total += 1
        bucket = par_concurrent.setdefault(
            nom, {'nombre': 0, 'somme_prix': Decimal('0'), 'nb_prix': 0,
                  'devises': Counter()})
        bucket['nombre'] += 1
        if prix is not None:
            bucket['somme_prix'] += prix
            bucket['nb_prix'] += 1
        if devise:
            bucket['devises'][devise] += 1
        if motif:
            motifs[motif] += 1

    par_concurrent_liste = []
    for nom, b in par_concurrent.items():
        prix_moyen = (
            str((b['somme_prix'] / b['nb_prix']).quantize(Decimal('0.01')))
            if b['nb_prix'] else None)
        devise = b['devises'].most_common(1)[0][0] if b['devises'] else None
        par_concurrent_liste.append({
            'concurrent': nom,
            'nombre': b['nombre'],
            'prix_moyen': prix_moyen,
            'devise': devise,
        })
    # Tri : plus fréquent d'abord, puis nom (déterministe).
    par_concurrent_liste.sort(key=lambda d: (-d['nombre'], d['concurrent']))

    par_motif_liste = [
        {'motif': m, 'nombre': n}
        for m, n in sorted(motifs.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    return {
        'total_litiges_avec_concurrent': total,
        'par_concurrent': par_concurrent_liste,
        'par_motif': par_motif_liste,
    }
