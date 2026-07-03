"""apps.pos.selectors — agrégats LECTURE SEULE pour le reporting POS (XPOS11).

Aucun nouveau modèle : agrège les ``VenteComptoir``/``LigneVenteComptoir``
existants (+ paiements des factures liées, via ``ventes.selectors``). La
marge (via ``produit.prix_achat``) n'apparaît QUE si ``include_marge`` est
vrai (posé par la vue selon la permission ``prix_achat_voir``) et JAMAIS
dans l'export xlsx (toujours client/interne-safe).
"""
from decimal import Decimal

from .models import VenteComptoir


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
