"""Lane E9 (constat T4-X5-010) — AVANT « Générer le devis » : ce que le devis PORTERA.

La composition que « Générer le devis » écrirait (``generer_devis`` →
``build_devis_from_layout``) est rejouée À BLANC par le MÊME chemin
(``build_devis_from_layout(a_blanc=True)`` : étapes 1-4 du pipeline, aucune écriture,
aucune seconde composition), et l'étape Documents lit, par option, le module et
l'onduleur que le devis portera. Quand un produit DÉSIGNÉ à l'étape Électrique n'est
pas celui-là, une phrase le dit et dit pourquoi : la raison rangée par la conception
(``designations_ecartees``) quand elle existe, sinon le fait — le devis de l'atelier
compose son matériel depuis la pose, la désignation électrique n'y entre pas.
Aucune règle n'est inventée sur ce que la désignation DEVRAIT faire (non tranché).
Lecture seule ; aucun prix servi.
"""
from __future__ import annotations

#: Les deux rôles désignables à l'étape Électrique (clés de l'entrée stockée).
ROLES_DESIGNES = (('module_produit', 'module', 'Le module'), ('onduleur_produit', 'onduleur', "L'onduleur"))
#: Les codes de supposition de la conception qui écartent une désignation (relecture E6 B2).
CODES_ECARTEES = ('designation_hors_catalogue', 'designation_ecartee')
RAISON_PAR_DEFAUT = ('le devis généré depuis l’atelier compose son matériel d’après la pose du toit : '
                     'la désignation de l’étape Électrique n’y entre pas')
MESSAGE_ECART = '%s désigné à l’étape Électrique (« %s ») n’est pas celui que le devis portera (« %s ») : %s'
LIBELLE_OPTION = {'': 'Devis', 'sans': 'Sans batterie', 'avec': 'Avec batterie'}


def _materiel_par_option(specs):
    """``[{option, libelle, module, onduleur, module_produit, onduleur_produit}]`` lus sur
    les lignes composées : une ligne sans variante vaut pour chaque option."""
    variantes = sorted({s.get('variante') or '' for s in specs} - {''}) or ['']
    options = []
    for variante in variantes:
        lignes = [s for s in specs if (s.get('variante') or '') in ('', variante)]
        module = next((s for s in lignes if s.get('role_devis') == 'panneau'), {})
        onduleur = next((s for s in lignes if str(s.get('role_devis') or '').startswith('onduleur_')), {})
        options.append({'option': variante or None, 'libelle': LIBELLE_OPTION.get(variante, variante),
                        'module': module.get('designation') or None, 'onduleur': onduleur.get('designation') or None,
                        'module_produit': module.get('produit'), 'onduleur_produit': onduleur.get('produit')})
    return options


def _ecarts(calepinage, options):
    """Une phrase par produit désigné à l'étape Électrique qu'une option ne portera pas."""
    from apps.stock.selectors import get_produit_scoped

    from .devis_retenu import conception_du_calepinage
    from .electrique import entree_stockee

    entree = entree_stockee(calepinage)
    rangees = [s for s in ((conception_du_calepinage(calepinage) or {}).get('suppositions') or ())
               if s.get('code') in CODES_ECARTEES]
    phrases = []
    for champ, cle, sujet in ROLES_DESIGNES:
        designe = entree.get(champ)
        if designe in (None, ''):
            continue
        portes = [o for o in options if str(o[f'{cle}_produit']) != str(designe)]
        if not portes:
            continue
        try:
            produit = get_produit_scoped(calepinage.company, int(designe))
        except (TypeError, ValueError):
            produit = None
        raison = next((s.get('message') for s in rangees if s.get('champ') == champ), None)
        porte = ' / '.join(sorted({o[cle] or 'aucun' for o in portes}))
        nom = getattr(produit, 'nom', None) or 'produit inconnu'
        motif = (raison or RAISON_PAR_DEFAUT).rstrip('. ') + '.'
        phrases.append({'champ': champ, 'message': MESSAGE_ECART % (sujet, nom, porte, motif)})
    return phrases


def apercu_materiel_du_devis(calepinage):
    """``{options, ecarts, refus}`` : par option, le module et l'onduleur que « Générer le
    devis » porterait (dry-run de LA composition), les désignations électriques qu'il ne
    portera pas (phrase et raison) ; ``refus`` = la phrase de la composition (ou de
    l'absence de toit) quand rien ne se compose. N'écrit rien."""
    from .devis import DevisRefuse, _exiger_layout, _lead_et_client
    from .equipements import composition_a_blanc

    build_devis_from_layout, AutoDevisError = composition_a_blanc()

    try:
        layout = _exiger_layout(calepinage)
        lead, _client = _lead_et_client(calepinage)
        specs = build_devis_from_layout(layout=layout, user=None, company=calepinage.company, lead=lead,
                                        a_blanc=True)
    except (AutoDevisError, DevisRefuse) as refus:
        return {'options': [], 'ecarts': [], 'refus': getattr(refus, 'message', None) or str(refus)}
    options = _materiel_par_option(specs)
    ecarts = _ecarts(calepinage, options)
    for option in options:
        option.pop('module_produit')
        option.pop('onduleur_produit')
    return {'options': options, 'ecarts': ecarts, 'refus': None}
