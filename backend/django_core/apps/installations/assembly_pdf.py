"""ZMFG10 — Bon d'assemblage imprimable (worksheet atelier PDF).

Odoo imprime un document d'ordre de fabrication + une feuille d'opération
pour l'atelier. L'ordre d'assemblage (`installations.OrdreAssemblage`) n'a
aucun imprimable jusqu'ici : le magasinier travaille à l'écran.

Rendu à la volée via le MÊME pipeline que les autres PDF (apps.ventes.utils.pdf
: identité société + template Jinja2 + WeasyPrint). Non stocké.

STRICTEMENT INTERNE : AUCUN prix — jamais `prix_achat` ni un prix de vente.
Dégrade proprement si XMFG14 (étapes) ou XMFG7 (séries) sont absents (aucune
section vide affichée)."""
from apps.ventes.utils.pdf import _company_context, _html_to_pdf, _render_html


def _composants_payload(ordre):
    """Nomenclature à préparer — désignation, quantité, emplacement/dispo
    (XMFG2/XMFG6). Jamais de prix."""
    from . import services
    dispo_par_produit = {
        d['produit_id']: d
        for d in services.disponibilite_par_ligne(ordre)
        if d.get('produit_id')
    }
    lignes = list(ordre.lignes.select_related('produit').all())
    if not lignes:
        # Repli BOM du kit (ordres créés avant XMFG6, rétro-compatible).
        composants = list(ordre.kit.composants.select_related('produit').all())
        out = []
        for c in composants:
            d = dispo_par_produit.get(c.produit_id, {})
            out.append({
                'designation': c.produit.nom if c.produit_id else '—',
                'quantite': (c.quantite or 0) * ordre.quantite,
                'disponible': d.get('disponible'),
                'statut': d.get('statut'),
            })
        return out
    out = []
    for li in lignes:
        d = dispo_par_produit.get(li.produit_id, {})
        out.append({
            'designation': li.designation or (
                li.produit.nom if li.produit_id else '—'),
            'quantite': li.quantite,
            'disponible': d.get('disponible'),
            'statut': d.get('statut'),
        })
    return out


def _etapes_payload(ordre):
    """XMFG14 — étapes de la gamme (instructions + case à cocher). Liste vide
    si le kit n'a pas de gamme définie (dégrade proprement, aucune section
    vide affichée par le template)."""
    return [
        {
            'ordre': e.ordre,
            'libelle': e.libelle,
            'instructions': e.instructions,
        }
        for e in ordre.kit.etapes_assemblage.all().order_by('ordre', 'id')
    ]


def _series_attendues(ordre):
    """XMFG7 — nombre de zones de saisie de n° de série à prévoir (une par
    unité produite). Purement indicatif (case à remplir sur papier)."""
    return list(range(1, (ordre.quantite or 1) + 1))


def bon_assemblage_pdf(ordre):
    """Génère le bon d'assemblage (PDF, octets) d'un `OrdreAssemblage`.
    STRICTEMENT INTERNE : ne rend jamais un prix (aucune clé `prix*` dans le
    contexte)."""
    context = _company_context(company=ordre.company)
    context.update({
        'reference': ordre.reference,
        'kit_nom': ordre.kit.nom if ordre.kit_id else '—',
        'quantite': ordre.quantite,
        'date_prevue': getattr(ordre, 'date_prevue', None),
        'responsable': getattr(
            getattr(ordre, 'responsable', None), 'username', None),
        'statut': ordre.get_statut_display(),
        'composants': _composants_payload(ordre),
        'etapes': _etapes_payload(ordre),
        'series_attendues': _series_attendues(ordre),
    })
    html = _render_html('bon_assemblage.html', context)
    return _html_to_pdf(html)
