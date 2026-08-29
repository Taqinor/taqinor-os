"""QJR49 — L'ARGENT D'UN DEVIS : une façade, quatre VUES NOMMÉES.

CE QUE CE MODULE EST. L'audit L3 du 29/08/2026 a trouvé SEPT chaînes monétaires
qui recomposent chacune HT → remise → TVA → TTC à leur façon et rendent parfois
TROIS réponses différentes pour le MÊME devis. Le travail n'est PAS d'écrire une
huitième chaîne : le noyau CORRECT existe déjà
(``apps.ventes.selectors._canonical_totaux``) et il n'est pas touché ici. Le
travail est de NOMMER les vues — pourquoi ce total-ci diffère de celui-là — pour
que les six autres implémentations puissent être SUPPRIMÉES une par une, chacune
remplacée par un appel qui DIT quelle vue elle voulait.

LES QUATRE VUES, ET CE QUI LES SÉPARE.

* :attr:`Vue.BRUT` — la somme de TOUTES les lignes comptées, remise de LIGNE
  honorée, ``remise_globale`` IGNORÉE, et aucun filtre d'option. C'est,
  MOT POUR MOT, ce que ``models.Devis.total_ht/total_tva/total_ttc`` rendent
  aujourd'hui — y compris son arrondi mono-taux non quantifié
  (``selectors.tva_buckets``). Elle existe pour que la bascule QJR51 soit un
  changement d'UN mot, et pour rien d'autre : aucun document client ne devrait
  la lire.
* :attr:`Vue.NET` — la chaîne CANONIQUE de CE devis : ``remise_globale``
  honorée ET l'option EFFECTIVE (``utils.options.option_effective``, décision
  fondateur D9) — jamais la somme des deux options. C'est le total que le
  document lui-même porte.
* :attr:`Vue.PAR_OPTION` — la même chaîne pour une option NOMMÉE
  (``option='sans_batterie'`` / ``'avec_batterie'``), celle qu'on veut quand on
  compare A / B ou qu'on facture une option acceptée.
* :attr:`Vue.AFFICHAGE` — la vue de ce qui est IMPRIMÉ. Elle porte le même
  argent que :attr:`Vue.NET` et se distingue par ``ttc_affiche``, le SEUL
  endroit du dépôt où un arrondi d'affichage a le droit d'exister. Aujourd'hui
  AUCUNE vue n'arrondit : ``ttc_affiche == ttc`` partout, au centime (c'est
  précisément le défaut que QJR53 supprime — ``builder._canonical_totaux``
  arrondissait le TTC au dirham entier pendant que les factures de tranche
  restaient au centime, si bien que le devis du client ne s'additionnait pas).

CE QUE CE MODULE NE FAIT PAS. Il ne modifie AUCUN appelant (QJR49 est une
création pure), il n'écrit rien, il ne change aucun statut (règle #4), et il ne
porte JAMAIS ``prix_achat`` ni aucune marge — cette façade ne rend que des
montants CLIENT.

Forme rendue : :class:`Totaux`, conforme à
``apps/ventes/contract_samples/devis_totaux.json`` (``ht_brut`` → ``remise`` →
``ht_net`` → ``tva_par_taux`` → ``tva`` → ``ttc`` → ``ttc_affiche``). Les
entrées de ``tva_par_taux`` portent ``{taux, base, montant}``, exactement le
contrat — ``base`` étant la part de ``ht_net`` imposée à CE taux.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple


class Vue(Enum):
    """Le CONTEXTE qui demande l'argent — voir la docstring du module."""

    BRUT = 'brut'
    NET = 'net'
    PAR_OPTION = 'par_option'
    AFFICHAGE = 'affichage'


@dataclass(frozen=True)
class Totaux:
    """La chaîne monétaire d'un devis, dans l'ORDRE où elle se dérive.

    GELÉ : chaque étage est dérivé du précédent DANS CETTE VUE — un appelant ne
    recalcule jamais un étage de son côté (c'est exactement ce que faisaient les
    sept chaînes que cette façade remplace).

    ``tva_par_taux`` est un tuple d'entrées ``{'taux', 'base', 'montant'}``
    triées par taux CROISSANT, une par taux RÉELLEMENT présent sur les lignes de
    cette vue — jamais une entrée à zéro pour un taux absent.
    """

    ht_brut: Decimal
    remise: Decimal
    ht_net: Decimal
    tva_par_taux: Tuple[dict, ...]
    tva: Decimal
    ttc: Decimal
    ttc_affiche: Decimal


def _lignes_du_devis(devis, lignes, *, avec_produit):
    """Les lignes à considérer — celles fournies, sinon celles du devis.

    NPLUS1 : un appelant qui a DÉJÀ chargé ses lignes (patron YOPSB13) les
    passe et ne paie pas une seconde requête, exactement comme
    ``utils.options.option_totaux``.

    ``avec_produit`` — ``select_related('produit')`` n'est demandé QUE par les
    vues canoniques, dont le filtre d'option lit le NOM du produit lié
    (``utils.options._blob``). :attr:`Vue.BRUT` s'en passe et lit
    ``devis.lignes.all()`` mot pour mot comme ``Devis.total_ht`` : c'est ce qui
    lui laisse RÉUTILISER un ``prefetch_related('lignes')` de la liste des
    devis. Ajouter un ``select_related`` ici transformerait chaque total de la
    liste en requête supplémentaire (N+1).
    """
    if lignes is not None:
        return list(lignes)
    if avec_produit:
        return list(devis.lignes.select_related('produit').all())
    return list(devis.lignes.all())


def _entrees_tva(paniers):
    """Les paniers du noyau, rendus à la forme du CONTRAT ``{taux, base,
    montant}``.

    Le noyau expose historiquement ``ht_net``/``base_ht`` (deux alias de la même
    base, pour ses consommateurs UBL/PDF facture) : on ne renomme rien chez lui,
    on TRADUIT ici — la façade est le seul endroit qui connaît le contrat.
    """
    entrees = []
    for panier in paniers:
        base = panier.get('base_ht')
        if base is None:
            base = panier.get('ht_net')
        entrees.append({
            'taux': panier['taux'],
            'base': base,
            'montant': panier['montant'],
        })
    return tuple(entrees)


def _totaux_brut(devis, lignes):
    """:attr:`Vue.BRUT` — le comportement ACTUEL de ``Devis.total_*``, au bit.

    Volontairement bâtie sur ``selectors.tva_buckets`` et NON sur
    ``_canonical_totaux`` : les deux divergent sur un devis MONO-TAUX (le noyau
    canonique quantifie la TVA au centime, ``tva_buckets`` applique la formule
    d'origine HT × taux sans arrondi). Passer par le noyau ferait donc bouger
    des montants — ce que QJR50 interdit explicitement.
    """
    from apps.ventes.selectors import ligne_compte_dans_totaux, tva_buckets

    comptees = [li for li in lignes if ligne_compte_dans_totaux(li)]
    ht_brut = sum((Decimal(str(li.total_ht)) for li in comptees), Decimal('0'))
    paniers = tva_buckets(lignes, fallback_taux=devis.taux_tva)
    tva = sum((panier['montant'] for panier in paniers), Decimal('0'))
    ttc = ht_brut + tva
    return Totaux(
        ht_brut=ht_brut, remise=Decimal('0'), ht_net=ht_brut,
        tva_par_taux=_entrees_tva(paniers), tva=tva,
        ttc=ttc, ttc_affiche=ttc)


def _totaux_canoniques(devis, lignes, option):
    """La chaîne CANONIQUE — celle d'``utils.options.option_totaux``, au
    centime, avec la remise globale et le filtre d'option."""
    from apps.ventes.selectors import _canonical_totaux
    from apps.ventes.utils.options import (
        filter_lines_for_option, has_two_options,
    )

    if option and has_two_options(devis):
        lignes = filter_lines_for_option(lignes, option)
    noyau = _canonical_totaux(
        lignes,
        remise_globale_pct=getattr(devis, 'remise_globale', 0) or 0,
        fallback_taux=devis.taux_tva)
    return Totaux(
        ht_brut=noyau['ht_brut'], remise=noyau['remise'],
        ht_net=noyau['ht_net'], tva_par_taux=_entrees_tva(noyau['tva_par_taux']),
        tva=noyau['tva'], ttc=noyau['ttc'],
        # AUCUNE vue n'arrondit aujourd'hui : ``ttc_affiche`` est le SLOT prévu
        # pour un futur arrondi d'affichage, jamais une seconde source.
        ttc_affiche=noyau['ttc'])


def totaux(devis, *, vue: Vue, option: Optional[str] = None,
           lignes=None) -> Totaux:
    """L'argent de ``devis`` dans la vue DEMANDÉE — l'unique porte.

    ``vue`` est OBLIGATOIRE et NOMMÉ : un appelant doit dire quelle question il
    pose. C'est tout l'objet de cette façade — les sept chaînes qu'elle remplace
    donnaient des réponses différentes sans que personne ne puisse dire
    laquelle était censée être laquelle.

    ``option`` — ``utils.options.SANS_BATTERIE`` / ``AVEC_BATTERIE``. Requis
    (au sens : c'est son seul intérêt) pour :attr:`Vue.PAR_OPTION` ; ``None``
    sur :attr:`Vue.NET` / :attr:`Vue.AFFICHAGE` ⇒ l'option EFFECTIVE du devis
    (``option_effective``, décision fondateur D9 : l'option acceptée, sinon
    celle du total affiché — jamais la somme des deux). Ignoré par
    :attr:`Vue.BRUT`, qui n'a par définition aucun filtre.

    ``lignes`` — lignes déjà chargées par l'appelant (aucune requête de plus).

    LECTURE PURE : n'écrit rien, ne change aucun statut, ne porte aucun
    ``prix_achat`` ni aucune marge (règle #4).
    """
    if not isinstance(vue, Vue):
        raise TypeError(
            'argent.totaux exige une Vue nommée (BRUT, NET, PAR_OPTION, '
            'AFFICHAGE), reçu %r.' % (vue,))

    if vue is Vue.BRUT:
        return _totaux_brut(
            devis, _lignes_du_devis(devis, lignes, avec_produit=False))

    if not option:
        from apps.ventes.utils.options import option_effective
        option = option_effective(devis)
    return _totaux_canoniques(
        devis, _lignes_du_devis(devis, lignes, avec_produit=True), option)
