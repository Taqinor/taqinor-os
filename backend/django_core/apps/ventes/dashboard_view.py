"""FG45 — Tableau de bord Quote-to-Cash (ventes).

Agrégation LECTURE SEULE, scopée société, sans aucune écriture. Renvoie :
  - Taux de conversion devis (envoyé → accepté → facturé → encaissé)
  - Cycle quote-to-cash moyen (jours entre création devis et paiement)
  - DSO (Days Sales Outstanding) — encours / CA facturé × 30
  - Encaissé vs facturé (mois en cours ou période paramétrée)
  - Pipeline par commercial (décompte + valeur totale des devis actifs)
"""
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole


def _period_filter(request):
    """Renvoie un filtre Django (date__range) selon ?start=&end= ou ?month=."""
    params = request.query_params
    start = params.get('start')
    end = params.get('end')
    month = params.get('month')

    if start and end:
        return Q(date_creation__date__range=[start, end])
    if month:
        from datetime import date
        try:
            y, m = int(month[:4]), int(month[5:7])
            import calendar
            last_day = calendar.monthrange(y, m)[1]
            s = date(y, m, 1).isoformat()
            e = date(y, m, last_day).isoformat()
            return Q(date_creation__date__range=[s, e])
        except (ValueError, IndexError):
            pass
    # Défaut : 12 derniers mois.
    from datetime import timedelta
    end_d = timezone.now().date()
    start_d = end_d - timedelta(days=365)
    return Q(date_creation__date__range=[start_d.isoformat(), end_d.isoformat()])


def _ttc_affiche(devis):
    """QJR203 — LE TTC de ce devis, par la chaîne canonique. Rien d'autre.

    C'est la MÊME porte que `Devis.total_ttc` et que le `total_affiche` de la
    liste : `domain.argent.totaux(Vue.AFFICHAGE)` applique la remise globale,
    exclut les lignes qui ne comptent pas dans les totaux
    (`ligne_compte_dans_totaux`), suit l'option EFFECTIVE d'un devis à deux
    options (D9 — jamais la somme des deux paniers) et rend la TVA par taux
    réel, jamais 20 % en dur. Le tableau de bord ne recompose donc plus sa
    propre arithmétique : la couche reporting PORTE la chaîne monétaire.
    """
    from .domain.argent import Vue, totaux
    return totaux(devis, vue=Vue.AFFICHAGE).ttc_affiche


def _cle_commercial(devis):
    """(username, prénom, nom) du créateur — la clé de regroupement.

    Reprend MOT POUR MOT le repli de la version groupée qu'elle remplace : un
    devis sans créateur se regroupe sous « ? ».
    """
    auteur = devis.created_by
    if auteur is None:
        return ('?', '', '')
    return (auteur.username or '?',
            (auteur.first_name or '').strip(),
            (auteur.last_name or '').strip())


@api_view(['GET'])
@permission_classes([IsAnyRole])
def dashboard_quote_to_cash(request):
    """GET /ventes/dashboard/

    Tableau de bord Quote-to-Cash scopé société. Tous les montants en MAD TTC.

    Paramètres optionnels :
      - ?month=YYYY-MM     : filtre sur un mois
      - ?start=&end=       : filtre sur une plage de dates (ISO AAAA-MM-JJ)
      (défaut : 12 derniers mois)

    Réponse :
    {
      "devis": {
        "total":    int,  # tous statuts
        "envoyes":  int,
        "acceptes": int,
        "refuses":  int,
        "expires":  int,
        "taux_acceptation_pct": float | null,  # acceptés / envoyés × 100
        "valeur_pipeline": str,   # TTC des devis envoyés encore ouverts
      },
      "factures": {
        "total":       int,
        "emises":      int,
        "payees":      int,
        "en_retard":   int,
        "annulees":    int,
        "montant_facture": str,   # TTC total des factures émises/payées
        "montant_encaisse": str,  # Total des paiements de la période
      },
      "conversion": {
        "devis_envoye_vers_accepte_pct": float | null,
        "devis_accepte_vers_facture_pct": float | null,
        "devis_envoye_vers_facture_pct":  float | null,
      },
      "dso_jours": float | null,   # Days Sales Outstanding
      "cycle_moyen_jours": float | null,   # création devis → dernier paiement
      "par_commercial": [
        {
          "commercial": str,
          "devis_actifs": int,
          "valeur_pipeline": str,
        }
      ]
    }
    """
    from .models import Devis, Facture, Paiement
    company = request.user.company
    periode = _period_filter(request)

    # ── Devis ────────────────────────────────────────────────────────────────
    devis_qs = Devis.objects.filter(company=company).filter(periode)
    agg_devis = devis_qs.aggregate(
        total=Count('id'),
        envoyes=Count('id', filter=Q(statut='envoye')),
        acceptes=Count('id', filter=Q(statut='accepte')),
        refuses=Count('id', filter=Q(statut='refuse')),
        expires=Count('id', filter=Q(statut='expire')),
    )

    # ── Pipeline : UN SEUL LOT, LA CHAÎNE CANONIQUE (QJR203 / décision DV2) ──
    #
    # CE QUI ÉTAIT FAUX. Les deux montants « valeur pipeline » (global et par
    # commercial) étaient une somme SQL de lignes
    # (`quantite × prix_unitaire × (1 − remise/100)`) suivie d'une TVA 20 %
    # CODÉE EN DUR. Cette expression :
    #   * ignorait `Devis.remise_globale` (le devis remisé était sur-évalué) ;
    #   * ignorait `ligne_compte_dans_totaux` (lignes optionnelles non
    #     activées, sections et notes comptées quand même) ;
    #   * additionnait LES DEUX OPTIONS d'un devis à deux options — un montant
    #     qui n'existe dans aucun document et que le client ne paiera jamais ;
    #   * appliquait 20 % à un devis à 10 % (ou à taux mixtes).
    # Et `par_commercial` n'appliquait même pas `periode` : le sélecteur de
    # période changeait les compteurs, jamais les montants.
    #
    # CE QUI EST FAIT. Les devis du pipeline sont lus en UN LOT BORNÉ (une
    # requête + le prefetch de leurs lignes), et chaque TTC passe par
    # `domain.argent.totaux(Vue.AFFICHAGE)` — LA chaîne canonique, la même que
    # `Devis.total_ttc` et que le `total_affiche` de la liste : remise globale,
    # `ligne_compte_dans_totaux` et option effective (D9) honorés. Le tableau
    # de bord affiche donc, au centime, ce que la liste affiche.
    #
    # LE N+1 QUE SCA40 PROTÈGE RESTE FERMÉ : il n'y a plus UNE REQUÊTE PAR
    # COMMERCIAL (le défaut d'origine) ni une agrégation par devis — un lot,
    # puis de l'arithmétique Python. Un devis à DEUX options paie le même
    # prédicat partagé (`deux_options_declarees`) que la liste paie déjà pour
    # la même ligne ; un devis mono-option, l'écrasante majorité, ne paie rien
    # de plus (ses lignes viennent du prefetch).
    devis_pipeline = list(
        Devis.objects.filter(company=company, statut='envoye')
        .filter(periode)
        .select_related('created_by')
        .prefetch_related('lignes')
    )
    valeur_pipeline = Decimal('0')
    pipeline_par_commercial = {}
    for devis_ouvert in devis_pipeline:
        ttc = _ttc_affiche(devis_ouvert)
        valeur_pipeline += ttc
        cle = _cle_commercial(devis_ouvert)
        ligne_comm = pipeline_par_commercial.setdefault(
            cle, {'devis_actifs': 0, 'valeur': Decimal('0')})
        ligne_comm['devis_actifs'] += 1
        ligne_comm['valeur'] += ttc

    # ── Factures ─────────────────────────────────────────────────────────────
    # On filtre sur date_emission et date_creation (les deux peuvent exister).
    factures_qs = Facture.objects.filter(company=company)
    agg_fac = factures_qs.aggregate(
        total=Count('id'),
        emises=Count('id', filter=Q(statut='emise')),
        payees=Count('id', filter=Q(statut='payee')),
        en_retard=Count('id', filter=Q(statut='en_retard')),
        annulees=Count('id', filter=Q(statut='annulee')),
    )

    # Montant facturé (TTC) : montant_ttc quand figé, sinon on utilise montant_ttc.
    # Pour les factures avec lignes non figées, une agrégation SQL exacte nécessiterait
    # de joindre les lignes — on utilise la somme des montant_ttc quand disponible.
    montant_facture_q = factures_qs.filter(
        statut__in=('emise', 'payee', 'en_retard')
    ).aggregate(s=Sum('montant_ttc'))
    montant_facture = montant_facture_q['s'] or Decimal('0')

    # Paiements encaissés.
    paiements_qs = Paiement.objects.filter(company=company)
    montant_encaisse_q = paiements_qs.aggregate(s=Sum('montant'))
    montant_encaisse = montant_encaisse_q['s'] or Decimal('0')

    # ── Taux de conversion ───────────────────────────────────────────────────
    n_envoyes = agg_devis['envoyes']
    n_acceptes = agg_devis['acceptes']
    # Devis acceptés avec au moins une facture.
    devis_avec_facture = (
        Devis.objects.filter(company=company, statut='accepte')
        .filter(factures__isnull=False)
        .distinct().count()
    )

    def _pct(num, den):
        if den and den > 0:
            return round(num / den * 100, 1)
        return None

    # ── DSO ──────────────────────────────────────────────────────────────────
    # DSO = encours TTC / (CA facturé / 30)
    encours_ttc = factures_qs.filter(
        statut__in=('emise', 'en_retard')
    ).aggregate(s=Sum('montant_ttc'))['s'] or Decimal('0')
    dso = None
    if montant_facture > 0:
        dso = round(float(encours_ttc) / float(montant_facture) * 30, 1)

    # ── Cycle moyen quote-to-cash ─────────────────────────────────────────────
    # Jours entre creation du devis et date du dernier paiement.
    # Calcul approximatif côté Python (pas de DeltaField SQL).
    cycle_list = []
    accepted_with_pmt = (
        Devis.objects.filter(company=company, statut='accepte')
        .prefetch_related('factures__paiements')
        .select_related('created_by')
    )[:200]  # cap pour éviter un scan complet
    for d in accepted_with_pmt:
        pmt_dates = [
            p.date_paiement
            for f in d.factures.all()
            for p in f.paiements.all()
        ]
        if pmt_dates:
            delta = (max(pmt_dates) - d.date_creation.date()).days
            if delta >= 0:
                cycle_list.append(delta)
    cycle_moyen = round(sum(cycle_list) / len(cycle_list), 1) if cycle_list else None

    # ── Par commercial ────────────────────────────────────────────────────────
    # SCA40 — le défaut d'origine était un `aggregate()` LigneDevis PAR
    # COMMERCIAL dans une boucle Python (N+1 non borné, croissait avec
    # l'équipe). Il reste fermé : ce bloc ne fait plus AUCUNE requête — il
    # relit le lot déjà chargé plus haut. `devis_actifs` compte les DEVIS (un
    # devis sans ligne compte pour 1, valeur nulle), exactement comme le
    # `Count('id', distinct=True)` qu'il remplace.
    #
    # QJR203 / DV2 — deux corrections de FOND par rapport à la version
    # groupée : le montant est celui de la chaîne canonique (plus une somme de
    # lignes × 1,20), et `periode` s'applique enfin ici aussi — ce bloc lisait
    # `Devis.objects.filter(company=..., statut='envoye')` SANS période, si
    # bien que le sélecteur de période bougeait les compteurs mais pas les
    # montants.
    par_commercial = []
    for (uname, fname, lname), agg in pipeline_par_commercial.items():
        display = f'{fname} {lname}'.strip() or uname
        par_commercial.append({
            'commercial': display,
            'devis_actifs': agg['devis_actifs'],
            'valeur_pipeline': str(round(float(agg['valeur']), 2)),
        })
    par_commercial.sort(key=lambda ligne: ligne['commercial'])

    return Response({
        'devis': {
            'total': agg_devis['total'],
            'envoyes': n_envoyes,
            'acceptes': n_acceptes,
            'refuses': agg_devis['refuses'],
            'expires': agg_devis['expires'],
            'taux_acceptation_pct': _pct(n_acceptes, n_envoyes),
            'valeur_pipeline': str(round(float(valeur_pipeline), 2)),
        },
        'factures': {
            'total': agg_fac['total'],
            'emises': agg_fac['emises'],
            'payees': agg_fac['payees'],
            'en_retard': agg_fac['en_retard'],
            'annulees': agg_fac['annulees'],
            'montant_facture': str(round(montant_facture, 2)),
            'montant_encaisse': str(round(montant_encaisse, 2)),
        },
        'conversion': {
            'devis_envoye_vers_accepte_pct': _pct(n_acceptes, n_envoyes),
            'devis_accepte_vers_facture_pct': _pct(devis_avec_facture, n_acceptes),
            'devis_envoye_vers_facture_pct': _pct(devis_avec_facture, n_envoyes),
        },
        'dso_jours': dso,
        'cycle_moyen_jours': cycle_moyen,
        'par_commercial': par_commercial,
    })
