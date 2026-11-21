"""ACAL616 — 2 à 3 configurations d'onduleur COMPARABLES (CAP-D3-01).

L'onduleur RETENU du calepinage (désigné, sinon celui du devis lié — même
résolution que l'entrée électrique) et ses deux voisins de puissance du
catalogue de la SOCIÉTÉ, chacun évalué À CHAUD par le moteur existant :

* verdict, bloquants, alertes, manquantes : ``evaluation_electrique`` avec
  ``entree={'onduleur_produit': id}`` — les textes du moteur, jamais
  réécrits ;
* nombre, puissance AC totale, puissance DC, ratio DC/AC :
  ``chaines.evaluer_onduleurs`` (réglages société de la section
  ``electrique_societe``) ;
* entrées MPPT utilisées (entrées distinctes des chaînes conçues) et
  disponibles (``n_mppt`` de la fiche × nombre).

Un nombre non calculable vaut ``None`` (jamais 0). Lecture PURE : rien n'est
écrit. AUCUN prix (l'argent reste dans ``apps/ventes``). Forme du contrat
``contract_samples/calepinage_configurations_onduleur.json`` (ACAL614).
"""
from __future__ import annotations

__all__ = ['configurations_onduleur']

GESTE_ONDULEUR = ("Aucun onduleur désigné : choisissez un onduleur dans "
                  "l'onglet Matériel électrique pour comparer ses voisins.")


def _libelle(produit):
    return ((getattr(produit, 'nom', '') or '').strip()
            or ('Produit %s' % produit.pk))


def _ac_kw(specs):
    from .valeurs import nombre

    valeur = nombre((specs or {}).get('ac_kw'))
    return valeur if valeur and valeur > 0 else None


def _configuration(calepinage, produit, specs, role, reglages):
    from .chaines import evaluer_onduleurs
    from .electrique import conception_du_calepinage, evaluation_electrique
    from .valeurs import nombre

    entree = {'onduleur_produit': produit.pk}
    evaluation = evaluation_electrique(calepinage, entree=entree)
    conception = conception_du_calepinage(calepinage, entree=entree)[0]
    calcul = (None if conception.fiche_incomplete
              else evaluer_onduleurs(conception, reglages=reglages))
    nb = calcul.nombre if calcul is not None and calcul.nombre else None
    ratio = getattr(calcul, 'ratio_dc_ac', None) if nb else None
    n_mppt = nombre((specs or {}).get('n_mppt'))
    entrees = {chaine.mppt for chaine in conception.chaines}
    return {
        'produit_id': produit.pk,
        'libelle': _libelle(produit),
        'marque': (getattr(produit, 'marque', '') or '').strip(),
        'role': role,
        'nombre_onduleurs': nb,
        'puissance_ac_totale_kw': (round(calcul.puissance_ac_kw, 2)
                                   if nb and calcul.ac_kw_unitaire else None),
        'puissance_dc_kwc': (round(calcul.puissance_dc_kwc, 2)
                             if nb else None),
        'ratio_dc_ac': (round(ratio.valeur, 2)
                        if ratio is not None and ratio.valeur is not None
                        else None),
        'mppt_utilises': len(entrees) if nb and entrees else None,
        'mppt_disponibles': (int(n_mppt) * nb if nb and n_mppt else None),
        'verdict': evaluation['verdict'],
        'bloquants': list(evaluation['bloquants']),
        'alertes': list(evaluation['alertes']),
        'manquantes': list(evaluation['manquantes']),
    }


def configurations_onduleur(calepinage):
    """``{retenue, configurations[], fiches_incompletes[], motif_vide}``."""
    from apps.stock.selectors import (
        get_produit_scoped, produits_par_type_fiche_qs, specs_for_produit,
    )

    from .chaines import specs_onduleur
    from .electrique import (
        _reglages_electrique_societe, entree_stockee, resoudre_materiel,
    )

    company = getattr(calepinage, 'company', None)
    materiel = resoudre_materiel(company, entree_stockee(calepinage),
                                 calepinage=calepinage)
    vide = {'retenue': None, 'configurations': [], 'fiches_incompletes': [],
            'motif_vide': GESTE_ONDULEUR}
    retenu_id = materiel['produits'].get('onduleur')
    retenu = (get_produit_scoped(company, retenu_id)
              if company is not None and retenu_id else None)
    if retenu is None:
        return vide
    catalogue, incompletes = [], []
    for produit in produits_par_type_fiche_qs(company, 'onduleur'):
        specs = specs_for_produit(produit) or {}
        manquants = specs_onduleur(specs)[1]
        if manquants or _ac_kw(specs) is None:
            incompletes.append({
                'produit_id': produit.pk, 'libelle': _libelle(produit),
                'champs_manquants': list(manquants) or ['puissance AC']})
        elif produit.pk != retenu.pk:
            catalogue.append((produit, specs, _ac_kw(specs)))
    reglages = _reglages_electrique_societe(calepinage)
    specs_retenu = specs_for_produit(retenu) or {}
    lignes = [_configuration(calepinage, retenu, specs_retenu, 'retenue',
                             reglages)]
    puissance = _ac_kw(specs_retenu)
    motifs = []
    if puissance is None:
        motifs.append("Puissance AC de l'onduleur retenu non renseignée : "
                      "aucun voisin de puissance comparable.")
    else:
        dessus = [c for c in catalogue if c[2] > puissance]
        dessous = [c for c in catalogue if c[2] < puissance]
        for role, choix, texte in (
                ('plus_puissant', min(dessus, key=lambda c: c[2],
                                      default=None), 'plus'),
                ('moins_puissant', max(dessous, key=lambda c: c[2],
                                       default=None), 'moins')):
            if choix is None:
                motifs.append("Aucun onduleur %s puissant dans le catalogue "
                              "de la société." % texte)
            else:
                lignes.append(_configuration(calepinage, choix[0], choix[1],
                                             role, reglages))
    return {'retenue': {'produit_id': retenu.pk, 'libelle': _libelle(retenu)},
            'configurations': lignes, 'fiches_incompletes': incompletes,
            'motif_vide': ' '.join(motifs) or None}
