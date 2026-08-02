"""AOF131 — lettre de soumission.

La pièce qui ENGAGE : c'est elle que la commission lit en premier et c'est
elle qui porte le montant sur lequel l'offre est jugée. Trois exigences, toutes
mécaniques :

1. **Le montant est celui du bordereau, au centime.** Il n'est pas re-saisi :
   la lettre part des MÊMES lignes et des MÊMES fonctions de total
   (`ordonnancement.py`). `controler_vs_bordereau()` le prouve. C'est
   exactement le défaut réel du dossier — une lettre à 5 413 680 et un
   bordereau frère resté à 5 219 280 — rendu impossible.
2. **La clause de réserve est IDENTIQUE à celle du bordereau**, au caractère
   près (contrôle AOF126) : la lettre et le bordereau ne peuvent pas porter
   deux versions d'un même engagement.
3. **Chiffres ET lettres, recalculés** (AOF125), y compris la durée de
   validité de l'offre.

Aucun rendu ici : le module produit le contexte de gabarit ; l'appel
`core.pdf.render_pdf` (ARC11) appartient à la couche Django.
"""
from __future__ import annotations

from decimal import Decimal

from core.formats_fr import formater_date

from ..clauses import CLAUSE_RESERVE_QUANTITES
from ..montants import (arrete, controler_concordance, duree_en_lettres,
                        en_chiffres, en_lettres)
from ..ordonnancement import totaux
from ..styles import contexte_style

NOM_GABARIT = 'ao/lettre_soumission.html'
TITRE_PIECE = 'Lettre de soumission'

#: Validité par défaut d'une offre quand la consultation ne l'impose pas.
VALIDITE_DEFAUT_JOURS = 75


def contexte_gabarit(lignes, contexte, *, texte_clause=None,
                     taux_tva=Decimal('20'), devise='DH'):
    """Le contexte du gabarit `ao/lettre_soumission.html`."""
    calcules = totaux(lignes, taux_defaut=taux_tva)
    marche = contexte.get('marche') or {}
    dates = contexte.get('dates') or {}
    validite = marche.get('validite_offre_jours') or VALIDITE_DEFAUT_JOURS
    delai = marche.get('delai_execution_jours')

    donnees = {
        'piece_titre': TITRE_PIECE,
        'contexte': contexte,
        'total_ht_texte': en_chiffres(calcules.total_ht, devise=devise),
        'tva_texte': en_chiffres(calcules.tva, devise=devise),
        'total_ttc_texte': en_chiffres(calcules.total_ttc, devise=devise),
        'total_ttc_lettres': en_lettres(calcules.total_ttc),
        'arrete': arrete(calcules.total_ttc),
        'taux_tva': taux_tva,
        'totaux': calcules,
        'validite_jours': validite,
        'validite_lettres': duree_en_lettres(validite),
        'delai_jours': delai,
        'delai_lettres': duree_en_lettres(delai) if delai else '',
        'date_offre_texte': formater_date(dates.get('offre')),
        'clause_reserve': texte_clause or CLAUSE_RESERVE_QUANTITES,
    }
    donnees.update(contexte_style())
    return donnees


def valeurs_de_controle(donnees):
    """Les montants PORTÉS par la lettre."""
    return {'total_ht': donnees['totaux'].total_ht,
            'tva': donnees['totaux'].tva,
            'total_ttc': donnees['totaux'].total_ttc}


def controler_vs_bordereau(donnees_lettre, valeurs_bordereau):
    """La lettre et le bordereau disent-ils le MÊME montant, au centime ?"""
    portes = valeurs_de_controle(donnees_lettre)
    ecarts = []
    for cle in ('total_ht', 'tva', 'total_ttc'):
        if portes.get(cle) != valeurs_bordereau.get(cle):
            ecarts.append('%s : lettre %s, bordereau %s'
                          % (cle, portes.get(cle), valeurs_bordereau.get(cle)))
    return tuple(ecarts)


def controler_clause(donnees_lettre, texte_bordereau):
    """La clause de la lettre est-elle celle du bordereau, au caractère près ?"""
    from ..clauses import controler
    return controler({'bordereau': texte_bordereau,
                      'lettre_soumission': donnees_lettre['clause_reserve']})


def controler_montants_rendus(texte_rendu, donnees):
    """Concordance lettres/chiffres SUR LE TEXTE RENDU (AOF125)."""
    return controler_concordance(texte_rendu,
                                 {'total TTC': donnees['totaux'].total_ttc})
