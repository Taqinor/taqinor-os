"""apps.pos.selectors — agrégats LECTURE SEULE pour le reporting POS (XPOS11).

Aucun nouveau modèle : agrège les ``VenteComptoir``/``LigneVenteComptoir``
existants (+ paiements des factures liées, via ``ventes.selectors``). La
marge (via ``produit.prix_achat``) n'apparaît QUE si ``include_marge`` est
vrai (posé par la vue selon la permission ``prix_achat_voir``) et JAMAIS
dans l'export xlsx (toujours client/interne-safe).
"""
from decimal import Decimal

from .models import PrixParEmplacement, VenteComptoir


def vente_par_uuid_client(company, uuid_client):
    """NTRET1 — vente déjà créée pour cet ``uuid_client`` (mode offline), ou
    None. Utilisé pour la dédup serveur au rejeu (jamais de doublon)."""
    if not uuid_client:
        return None
    return VenteComptoir.objects.filter(
        company=company, uuid_client=uuid_client).first()


# ── NTRET29 — Grille tarifaire par boutique/emplacement ─────────────────────

def prix_applicable(company, produit, boutique):
    """NTRET29 — prix TTC applicable à ``produit`` pour ``boutique``
    (``parametres.BoutiquePos``) : l'override ``PrixParEmplacement`` s'il
    existe, sinon le prix catalogue (``produit.prix_vente``) — REPLI
    rétro-compatible pour toute boutique/produit sans override. ``boutique``
    None (session sans boutique renseignée) renvoie toujours le prix
    catalogue, comportement historique inchangé."""
    if boutique is not None:
        override = PrixParEmplacement.objects.filter(
            company=company, produit=produit, boutique=boutique).first()
        if override is not None:
            return override.prix_ttc
    return produit.prix_vente


def _date_filtered(qs, date_debut, date_fin):
    if date_debut:
        qs = qs.filter(date_validation__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_validation__date__lte=date_fin)
    return qs


def dashboard_data(*, company, date_debut=None, date_fin=None,
                   include_marge=False):
    """Tableau de bord POS : 6 axes + drill-down (XPOS11).

    Axes : ventes par jour, par session, par caissier, par mode de paiement,
    par produit/catégorie, panier moyen + taux de retour + comparatif
    espèces vs carte. ``include_marge`` n'ajoute la marge (prix_achat) que si
    vrai — jamais exposée sans la permission.
    """
    ventes_qs = VenteComptoir.objects.filter(
        company=company, statut=VenteComptoir.Statut.VALIDEE)
    ventes_qs = _date_filtered(ventes_qs, date_debut, date_fin)
    ventes_qs = ventes_qs.select_related('caissier', 'session_caisse')

    ventes = list(ventes_qs.prefetch_related('lignes__produit__categorie'))
    nb_ventes = len(ventes)
    total_ttc = sum((v.total_ttc for v in ventes), Decimal('0'))
    panier_moyen = (total_ttc / nb_ventes) if nb_ventes else Decimal('0')

    par_jour = {}
    par_session = {}
    par_caissier = {}
    par_produit = {}
    par_categorie = {}
    for v in ventes:
        jour = v.date_validation.date().isoformat() if v.date_validation else ''
        par_jour[jour] = par_jour.get(jour, Decimal('0')) + v.total_ttc

        sess_key = v.session_caisse_id or 0
        par_session.setdefault(sess_key, Decimal('0'))
        par_session[sess_key] += v.total_ttc

        caissier_key = getattr(v.caissier, 'username', '—') if v.caissier_id else '—'
        par_caissier.setdefault(caissier_key, Decimal('0'))
        par_caissier[caissier_key] += v.total_ttc

        for ligne in v.lignes.all():
            produit = ligne.produit
            key = produit.nom
            row = par_produit.setdefault(
                key, {'total': Decimal('0'), 'quantite': Decimal('0')})
            row['total'] += ligne.total_ttc
            row['quantite'] += ligne.quantite
            if include_marge:
                marge_unitaire = (
                    ligne.prix_unitaire_ttc - (produit.prix_achat or Decimal('0')))
                row.setdefault('marge', Decimal('0'))
                row['marge'] += marge_unitaire * ligne.quantite

            cat = getattr(produit.categorie, 'nom', None) or 'Sans catégorie'
            par_categorie[cat] = par_categorie.get(cat, Decimal('0')) + ligne.total_ttc

    # Comparatif espèces vs carte + mode — via ventes.selectors (jamais
    # d'import direct de ventes.models.Paiement).
    from apps.ventes.selectors import paiements_totaux_par_mode
    facture_ids = [v.facture_id for v in ventes if v.facture_id]
    par_mode_rows = paiements_totaux_par_mode(facture_ids)
    par_mode = {
        row['mode']: str(row['total'] or Decimal('0')) for row in par_mode_rows}

    # Taux de retour : ventes annulées / total tenté (annulées + validées).
    nb_annulees = VenteComptoir.objects.filter(
        company=company, statut=VenteComptoir.Statut.ANNULEE).count()
    total_tentees = nb_ventes + nb_annulees
    taux_retour = (
        Decimal(nb_annulees) / Decimal(total_tentees) * 100
        if total_tentees else Decimal('0'))

    result = {
        'nb_ventes': nb_ventes,
        'total_ttc': str(total_ttc),
        'panier_moyen': str(panier_moyen),
        'taux_retour_pct': str(taux_retour.quantize(Decimal('0.01'))),
        'par_jour': {k: str(v) for k, v in par_jour.items()},
        'par_session': {str(k): str(v) for k, v in par_session.items()},
        'par_caissier': {k: str(v) for k, v in par_caissier.items()},
        'par_mode_paiement': par_mode,
        'par_produit': {
            k: {kk: str(vv) for kk, vv in row.items()}
            for k, row in par_produit.items()
        },
        'par_categorie': {k: str(v) for k, v in par_categorie.items()},
    }
    return result


# ── NTRET16 — Tableau de bord retail ────────────────────────────────────────

def _surface_totale_boutiques(company):
    """Surface totale (m²) des boutiques actives avec surface renseignée
    (NTRET8 ``parametres.BoutiquePos.surface_m2``). ``parametres`` est une
    app de FONDATION (exemptée de la règle selectors.py cross-app, CLAUDE.md)
    — import direct autorisé. Renvoie None si aucune boutique n'a de surface
    renseignée (le KPI ventes/m² est alors omis, jamais une division par 0)."""
    from django.db.models import Sum

    from apps.parametres.models import BoutiquePos
    total = BoutiquePos.objects.filter(
        company=company, actif=True, surface_m2__isnull=False,
    ).aggregate(total=Sum('surface_m2'))
    return total['total']


def dashboard_retail(*, company, date_debut=None, date_fin=None, boutique=None,
                     include_marge=False, top_n=10):
    """Tableau de bord retail (NTRET16) : panier moyen, taux de
    transformation, ventes/m², top produits/catégories/vendeurs, comparatif
    boutique vs boutique (multi-sites).

    ``boutique`` filtre sur le LIBELLÉ de la caisse comptable (XPOS4) — ex.
    « Caisse showroom Casablanca ». NOTE HONNÊTE (limite de donnée actuelle) :
    les « paniers parqués » de l'écran caisse (XPOS2, ``pos.js``) sont
    PUREMENT client-side (localStorage), sans aucune trace serveur — le taux
    de transformation utilise donc, en lieu et place, les ``VenteComptoir``
    en statut BROUILLON (créées puis jamais validées) comme meilleur proxy
    serveur disponible d'un panier non converti. De même, aucun champ ne relie
    aujourd'hui ``VenteComptoir``/``SessionCaisse`` à une ``BoutiquePos``
    précise : le comparatif « boutique vs boutique » groupe donc par le
    LIBELLÉ de la caisse comptable (déjà nommé par site en pratique dans un
    multi-boutiques), et le KPI ventes/m² divise le CA total de la société
    par la surface CUMULÉE des boutiques actives (pas encore un vrai
    ventilé par boutique — la marge (``prix_achat``) reste masquée sans
    ``prix_achat_voir``, jamais exposée dans l'export xlsx.
    """
    ventes_qs = VenteComptoir.objects.filter(
        company=company, statut=VenteComptoir.Statut.VALIDEE)
    ventes_qs = _date_filtered(ventes_qs, date_debut, date_fin)
    ventes_qs = ventes_qs.select_related(
        'caissier', 'session_caisse__caisse_comptable')
    if boutique:
        ventes_qs = ventes_qs.filter(
            session_caisse__caisse_comptable__libelle=boutique)

    ventes = list(ventes_qs.prefetch_related('lignes__produit__categorie'))
    nb_ventes = len(ventes)
    total_ttc = sum((v.total_ttc for v in ventes), Decimal('0'))
    panier_moyen = (total_ttc / nb_ventes) if nb_ventes else Decimal('0')

    # Taux de transformation — proxy BROUILLON (cf. docstring ci-dessus).
    brouillons_qs = VenteComptoir.objects.filter(
        company=company, statut=VenteComptoir.Statut.BROUILLON)
    if date_debut:
        brouillons_qs = brouillons_qs.filter(date_creation__date__gte=date_debut)
    if date_fin:
        brouillons_qs = brouillons_qs.filter(date_creation__date__lte=date_fin)
    nb_brouillons = brouillons_qs.count()
    total_paniers = nb_ventes + nb_brouillons
    taux_transformation = (
        Decimal(nb_ventes) / Decimal(total_paniers) * 100
        if total_paniers else Decimal('0'))

    # Ventes / m² — surface cumulée des boutiques actives (NTRET8).
    surface_totale = _surface_totale_boutiques(company)
    ventes_par_m2 = (
        (total_ttc / surface_totale) if surface_totale else None)

    par_produit = {}
    par_categorie = {}
    par_caissier = {}
    par_boutique = {}
    for v in ventes:
        caissier_key = getattr(v.caissier, 'username', '—') if v.caissier_id else '—'
        par_caissier.setdefault(caissier_key, Decimal('0'))
        par_caissier[caissier_key] += v.total_ttc

        caisse = getattr(v.session_caisse, 'caisse_comptable', None)
        boutique_key = getattr(caisse, 'libelle', None) or 'Sans boutique'
        par_boutique.setdefault(boutique_key, Decimal('0'))
        par_boutique[boutique_key] += v.total_ttc

        for ligne in v.lignes.all():
            produit = ligne.produit
            row = par_produit.setdefault(
                produit.nom, {'total': Decimal('0'), 'quantite': Decimal('0')})
            row['total'] += ligne.total_ttc
            row['quantite'] += ligne.quantite
            if include_marge:
                marge_unitaire = (
                    ligne.prix_unitaire_ttc - (produit.prix_achat or Decimal('0')))
                row.setdefault('marge', Decimal('0'))
                row['marge'] += marge_unitaire * ligne.quantite

            cat = getattr(produit.categorie, 'nom', None) or 'Sans catégorie'
            par_categorie[cat] = par_categorie.get(cat, Decimal('0')) + ligne.total_ttc

    def _top_montants(d, n):
        """Top ``n`` d'un dict ``{cle: Decimal}`` (caissiers/boutiques)."""
        return [
            {'nom': k, 'total': str(v2)}
            for k, v2 in sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]
        ]

    def _top_lignes(d, n):
        """Top ``n`` d'un dict ``{cle: {'total': Decimal, ...}}`` (produits)."""
        return [
            {'nom': k, 'total': str(row['total'])}
            for k, row in sorted(
                d.items(), key=lambda kv: kv[1]['total'], reverse=True)[:n]
        ]

    return {
        'nb_ventes': nb_ventes,
        'total_ttc': str(total_ttc),
        'panier_moyen': str(panier_moyen),
        'taux_transformation_pct': str(taux_transformation.quantize(Decimal('0.01'))),
        'ventes_par_m2': (
            str(ventes_par_m2.quantize(Decimal('0.01')))
            if ventes_par_m2 is not None else None),
        'top_produits': _top_lignes(par_produit, top_n),
        'top_categories': _top_montants(par_categorie, top_n),
        'top_vendeurs': _top_montants(par_caissier, top_n),
        'comparatif_boutiques': {k: str(v) for k, v in par_boutique.items()},
    }


# ── NTRET30 — Commission vendeur sur vente comptoir ─────────────────────────

def commissions_ventes_comptoir(company, *, date_debut=None, date_fin=None):
    """NTRET30 — ventes comptoir VALIDÉES agrégées par caissier (CA HT),
    point d'entrée cross-app pour ``apps.reporting.insights.commissions``
    (import fonction-local depuis reporting, jamais l'inverse — règle de
    modularité). Renvoie ``{caissier_id: {'caissier': CustomUser,
    'total_ht': Decimal, 'count': int}}`` — une vente sans caissier (NULL,
    ex. import) n'est jamais comptée."""
    ventes_qs = VenteComptoir.objects.filter(
        company=company, statut=VenteComptoir.Statut.VALIDEE,
        caissier__isnull=False)
    ventes_qs = _date_filtered(ventes_qs, date_debut, date_fin)
    ventes_qs = ventes_qs.select_related('caissier').prefetch_related('lignes')

    agg = {}
    for vente in ventes_qs:
        slot = agg.setdefault(vente.caissier_id, {
            'caissier': vente.caissier, 'total_ht': Decimal('0'), 'count': 0})
        slot['total_ht'] += vente.total_ht
        slot['count'] += 1
    return agg


def export_dashboard_retail_xlsx(*, company, date_debut=None, date_fin=None):
    """Export xlsx du tableau de bord retail (NTRET16) — jamais de
    prix_achat/marge (export client/interne-safe par construction)."""
    from apps.records.xlsx import build_xlsx_response

    data = dashboard_retail(
        company=company, date_debut=date_debut, date_fin=date_fin)
    headers = ['Indicateur', 'Valeur']
    rows = [
        ['Nombre de ventes', data['nb_ventes']],
        ['Total TTC', data['total_ttc']],
        ['Panier moyen', data['panier_moyen']],
        ['Taux de transformation (%)', data['taux_transformation_pct']],
        ['Ventes / m²', data['ventes_par_m2'] or 'N/A'],
    ]
    for boutique, total in data['comparatif_boutiques'].items():
        rows.append([f'Boutique — {boutique}', total])
    return build_xlsx_response(
        'pos-dashboard-retail.xlsx', headers, rows, sheet_title='Tableau de bord retail')


def export_dashboard_xlsx(*, company):
    """Export xlsx du dashboard POS (INTERNE, jamais de prix_achat/marge —
    export client-safe par construction)."""
    from apps.records.xlsx import build_xlsx_response

    ventes_qs = VenteComptoir.objects.filter(
        company=company, statut=VenteComptoir.Statut.VALIDEE
    ).select_related('client', 'caissier').order_by('-date_validation')

    headers = ['Référence', 'Date', 'Client', 'Caissier', 'Total TTC']
    rows = [[
        v.reference,
        v.date_validation.strftime('%d/%m/%Y %H:%M') if v.date_validation else '',
        str(v.client) if v.client_id else '',
        getattr(v.caissier, 'username', '') if v.caissier_id else '',
        str(v.total_ttc),
    ] for v in ventes_qs]
    return build_xlsx_response(
        'pos-dashboard.xlsx', headers, rows, sheet_title='Ventes comptoir')
