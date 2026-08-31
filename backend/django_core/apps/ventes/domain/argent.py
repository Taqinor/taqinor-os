"""QJR49 — L'ARGENT D'UN DEVIS : une façade, deux VUES NOMMÉES.

CE QUE CE MODULE EST. L'audit L3 du 29/08/2026 a trouvé SEPT chaînes monétaires
qui recomposent chacune HT → remise → TVA → TTC à leur façon et rendent parfois
TROIS réponses différentes pour le MÊME devis. Le travail n'est PAS d'écrire une
huitième chaîne : le noyau CORRECT existe déjà
(``apps.ventes.selectors._canonical_totaux``) et il n'est pas touché ici. Le
travail est de NOMMER les vues — pourquoi ce total-ci diffère de celui-là — pour
que les six autres implémentations puissent être SUPPRIMÉES une par une, chacune
remplacée par un appel qui DIT quelle vue elle voulait.

QJR242 (31/08/2026) — DEUX VUES ONT ÉTÉ SUPPRIMÉES, arbitrage « câbler ou
supprimer » = SUPPRIMER.

* ``Vue.BRUT`` existait pour que la bascule QJR51 (``Devis.total_*`` du brut
  vers le net) soit un changement d'UN mot. Ce mot a été changé le 29/08 ; la
  vue n'a plus jamais eu d'appelant de production, et aucun document client
  n'aurait dû la lire de toute façon.
* ``Vue.PAR_OPTION`` était CASSÉE : ``totaux(vue=PAR_OPTION, option=X,
  lignes=Y)`` jetait l'option nommée EN SILENCE et rendait les totaux de tout
  le jeu de lignes fourni — exactement la seule chose qu'elle existait pour
  empêcher. La question « totaux d'un panier d'option » est posée en plusieurs
  endroits, et tous passent par ``utils.options.option_totaux`` : c'est LÀ
  qu'elle vit, correctement, depuis toujours.

Le noyau reste donc honnête à DEUX vues VIVANTES. Aucune valeur monétaire ne
change : ``NET`` et ``AFFICHAGE`` sont intouchées.

LES DEUX VUES, ET CE QUI LES SÉPARE.

* :attr:`Vue.NET` — la chaîne CANONIQUE de CE devis : ``remise_globale``
  honorée ET l'option EFFECTIVE (``utils.options.option_effective``, décision
  fondateur D9) — jamais la somme des deux options. C'est le total que le
  document lui-même porte.
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

    NET = 'net'
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

    ``avec_produit`` — ``select_related('produit')`` n'est demandé QUE quand un
    FILTRE D'OPTION va réellement s'appliquer, car lui seul lit le NOM du
    produit lié (``utils.options._blob``). Sinon on lit ``devis.lignes.all()``
    mot pour mot, la SEULE forme que le gestionnaire de relation sert depuis
    ``_prefetched_objects_cache`` : c'est ce qui laisse RÉUTILISER le
    ``prefetch_related('devis__lignes')`` de la liste des leads. Chaîner
    ``select_related`` construit un nouveau queryset, ignore ce cache et
    transforme chaque total de la liste en requête supplémentaire (N+1).

    NPLUS1 (29/08/2026, QJR51) — c'était la MOITIÉ de la régression « 23 (5
    leads) → 33 (10 leads) » : depuis que ``Devis.total_ttc`` lit :attr:`Vue.NET`
    (décision D2), ce chemin passait par la branche ``select_related`` pour TOUS
    les devis, y compris les mono-option qui n'ont AUCUN filtre à appliquer et
    donc aucun besoin du produit. L'appelant décide maintenant sur pièce
    (``totaux`` passe ``avec_produit=bool(option)``) : un devis à deux options
    paie la même requête qu'hier, un devis mono-option n'en paie plus aucune.
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


# QJR242 — ``_totaux_brut`` A ÉTÉ SUPPRIMÉE avec ``Vue.BRUT`` : elle bâtissait
# la chaîne d'AVANT la bascule QJR51 (``selectors.tva_buckets``, remise globale
# ignorée, aucun filtre d'option) pour que cette bascule ne soit qu'un
# changement d'UN mot. Le mot a été changé ; plus personne ne l'appelait.


def _totaux_canoniques(devis, lignes, option):
    """La chaîne CANONIQUE — celle d'``utils.options.option_totaux``, au
    centime, avec la remise globale et le filtre d'option.

    QJR200 — LE FILTRE D'OPTION PORTE AUSSI LA RÈGLE QF9 (accessoires Huawei
    orphelins retirés du panier dont l'onduleur n'est pas Huawei) : elle est
    déclarée UNE SEULE FOIS, dans ``utils.options.retirer_accessoires_huawei``,
    et appliquée par ``filter_lines_for_option`` ci-dessous. Le noyau n'en
    porte donc aucune copie — c'est ce qui garantit que le total imprimé et le
    total du noyau décrivent le même panier.
    """
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

    ``option`` — ``utils.options.SANS_BATTERIE`` / ``AVEC_BATTERIE``. ``None``
    (le cas de tous les appelants) ⇒ l'option EFFECTIVE du devis
    (``option_effective``, décision fondateur D9 : l'option acceptée, sinon
    celle du total affiché — jamais la somme des deux). QJR242 — pour les
    totaux d'une option NOMMÉE, l'appel se fait à
    ``utils.options.option_totaux`` : c'est la chaîne que les documents
    empruntent, et la vue ``PAR_OPTION`` qui prétendait la doubler ici était
    cassée (elle jetait l'option dès qu'on lui fournissait des lignes).

    ``lignes`` — lignes déjà chargées par l'appelant (aucune requête de plus).
    **QJR53 — DES LIGNES FOURNIES SONT LA POPULATION DE L'APPELANT** : aucun
    filtre d'option n'est alors ré-appliqué, et l'option effective n'est même
    pas résolue. Deux raisons, toutes deux dures :

    * filtrer une seconde fois une liste déjà découpée n'a aucun sens ;
    * ``option_effective`` interroge le prédicat « deux options », qui lit les
      lignes du devis — et l'appelant qui fournit ses lignes est justement, la
      plupart du temps, le moteur PDF lui-même (``quote_engine.builder``), qui
      les a déjà découpées. Le laisser re-résoudre l'option lui ferait poser
      une question à laquelle il vient de répondre.

    LECTURE PURE : n'écrit rien, ne change aucun statut, ne porte aucun
    ``prix_achat`` ni aucune marge (règle #4).
    """
    if not isinstance(vue, Vue):
        raise TypeError(
            'argent.totaux exige une Vue nommée (NET, AFFICHAGE), reçu %r.'
            % (vue,))

    if lignes is not None:
        return _totaux_canoniques(devis, list(lignes), option=None)
    if not option:
        from apps.ventes.utils.options import option_effective
        option = option_effective(devis)
    # NPLUS1 — le NOM du produit n'est lu (``utils.options._blob``) que si un
    # filtre d'option s'applique, c'est-à-dire seulement quand ``option`` est
    # non vide (cf. ``_totaux_canoniques`` juste au-dessus). Sans option
    # effective — tout devis mono-option, l'écrasante majorité d'une liste —
    # aucun ``select_related`` n'est justifié, et les lignes viennent alors du
    # prefetch de l'appelant sans une seule requête.
    return _totaux_canoniques(
        devis,
        _lignes_du_devis(devis, lignes, avec_produit=bool(option)),
        option)
