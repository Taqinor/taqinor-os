"""ENF20 — noyau d'argent PUR des documents client (aucun import d'app).

Déplacé tel quel depuis ``apps.ventes.selectors`` (qui le ré-exporte : tous les
appelants historiques restent valides). Ce module n'importe AUCUN module du
projet — seulement ``decimal``, en local — si bien que ``facturation.totaux``
(``TotauxDocumentMixin``) et ``ventes.domain.argent`` lisent la chaîne
HT → remise → TVA → TTC sans tirer ``ventes.selectors`` et ses lectures
inter-domaines : les arêtes ``-> apps.ventes.selectors`` que ``.importlinter``
élaguait pour eux n'existent plus (contrat M1 ``core-domain-models-decoupled``
et ``facturation-models-decoupled`` sans exception pour ces deux façades).
"""


def ligne_compte_dans_totaux(li):
    """XSAL5/XSAL14 — une ligne entre-t-elle dans les totaux d'un devis ?

    Est comptée UNIQUEMENT une ligne PRODUIT non optionnelle. Sont exclues des
    totaux (HT/TVA/TTC) : les lignes optionnelles non activées (XSAL5) et les
    lignes de section/note sans prix (XSAL14). Robuste par ``getattr`` : une
    ligne d'un autre modèle (LigneFacture/LigneAvoir, dépourvue de ces
    attributs) est TOUJOURS comptée → factures/avoirs strictement inchangés.
    """
    if getattr(li, 'optionnelle', False):
        return False
    return getattr(li, 'type_ligne', 'produit') == 'produit'


def tva_buckets(lignes, *, fallback_taux, frozen=None):
    """Ventilation TVA canonique (DC23). UNE seule implémentation partagée.

    Args:
        lignes: itérable de lignes exposant ``total_ht`` (Decimal-coercible) et
            ``taux_tva_effectif`` (taux %).
        fallback_taux: taux à utiliser quand il n'y a aucune ligne (mono-taux du
            document).
        frozen: tuple optionnel ``(taux, base_ht, montant)`` pour un montant figé
            (facture de tranche / acompte) — renvoyé tel quel en un seul panier.

    Returns: liste de paniers ``{'taux', 'base_ht', 'montant'}``. Mono-taux :
        formule d'origine (HT × taux, aucun arrondi par panier). Taux mixtes :
        un panier par taux, chaque TVA arrondie au centime.
    """
    from decimal import Decimal, ROUND_HALF_UP
    if frozen is not None:
        taux, base_ht, montant = frozen
        return [{'taux': taux, 'base_ht': base_ht, 'montant': montant}]

    # XSAL5/XSAL14 — exclut les lignes optionnelles non activées et section/note.
    lignes = [li for li in lignes if ligne_compte_dans_totaux(li)]
    buckets = {}
    for ligne in lignes:
        rate = Decimal(str(ligne.taux_tva_effectif))
        buckets[rate] = buckets.get(rate, Decimal('0')) + Decimal(ligne.total_ht)

    def q(x):
        return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    if len(buckets) <= 1:
        rate = next(iter(buckets), Decimal(str(fallback_taux)))
        base = sum((Decimal(li.total_ht) for li in lignes), Decimal('0'))
        # AUD189 — LA MÊME POLITIQUE QUE LA CHAÎNE CANONIQUE. Cette branche
        # rendait `base × taux` NON quantifié, en déléguant l'arrondi à
        # l'affichage : DEUX chaînes d'arrondi coexistaient donc sur la MÊME
        # facture (celle-ci et `_canonical_totaux`, qui quantifie en
        # ROUND_HALF_UP). La branche multi-taux ci-dessous quantifiait déjà ;
        # seul le mono-taux ne le faisait pas. Une seule politique, partout.
        return [{'taux': rate, 'base_ht': q(base),
                 'montant': q(base * rate / Decimal('100'))}]
    return [
        {'taux': rate, 'base_ht': q(buckets[rate]),
         'montant': q(buckets[rate] * rate / Decimal('100'))}
        for rate in sorted(buckets)
    ]


def _absorber_arrondi(tva_par_taux, ttc, pas):
    """ARRONDI-100 (fondateur, 02/10/2026) — « tous mes devis finissent par
    deux zéros, sans centimes : garde les prix des articles, baisse juste le
    total au palier de 100 DH inférieur ».

    Le TTC ``ttc`` est ramené au multiple de ``pas`` INFÉRIEUR (jamais
    au-dessus : l'arrondi ne fait que baisser le prix). La baisse est une
    réduction de HT sur les paniers de TVA, dont la TVA est recalculée par la
    règle de la chaîne (``q(base × taux / 100)``) : ``ht_net + tva == ttc``
    tient donc toujours, au centime, et aucune ligne ne change de prix.

    ORDRE D'ESSAI (déterministe — l'écran le rejoue à l'identique) : le panier
    au taux le PLUS ÉLEVÉ absorbe ; à un seul taux, certains TTC ne sont
    atteints par AUCUNE base au centime (p. ex. 500,00 à 10 %), donc un autre
    panier peut céder de 1 à ``_ARRONDI_CENTIMES_CEDES`` centimes de HT en
    plus ; puis le panier suivant absorbe ; en dernier recours, le palier
    d'en dessous (un devis mono-taux 10 % seulement, une fois sur onze). Aucun
    palier atteignable ⇒ ``None`` (le total reste exact). Un TTC inférieur à
    ``pas`` n'est jamais ramené à zéro.

    Rend ``(paniers, arrondi_ht)`` ou ``None`` quand il n'y a rien à faire.
    MIROIR EXACT : ``frontend/src/features/ventes/remise.js``
    (``absorberArrondi``) — même ordre d'essai, même règle d'arrondi.
    """
    from decimal import Decimal as D, ROUND_FLOOR, ROUND_HALF_UP as RH

    pas = D(str(pas or 0))
    if pas <= 0 or ttc < pas:
        return None
    cible = (ttc / pas).to_integral_value(rounding=ROUND_FLOOR) * pas
    if cible == ttc:
        return None
    centime = D('0.01')

    def tva_de(base, taux):
        return (base * taux / D('100')).quantize(centime, rounding=RH)

    taux = [D(str(p['taux'])) for p in tva_par_taux]
    bases = [p['ht_net'] for p in tva_par_taux]
    ordre = sorted(range(len(bases)), key=lambda k: taux[k], reverse=True)
    for essai in (cible, cible - pas):
        if essai <= 0:
            break
        for i in ordre:
            # (autre panier qui cède, centimes cédés) — (None, 0) d'abord.
            cessions = [(None, 0)] + [
                (j, d) for j in ordre if j != i
                for d in range(1, _ARRONDI_CENTIMES_CEDES + 1)]
            for j, d in cessions:
                nouvelles = list(bases)
                if j is not None:
                    nouvelles[j] = bases[j] - d * centime
                    if nouvelles[j] < 0:
                        continue
                autres = sum((nouvelles[k] + tva_de(nouvelles[k], taux[k])
                              for k in range(len(bases)) if k != i), D('0'))
                reste = essai - autres      # le TTC que le panier i porte
                if reste < 0:
                    continue
                x0 = (reste * 100 / (100 + taux[i])).quantize(
                    centime, rounding=ROUND_FLOOR)
                for k in (-2, -1, 0, 1, 2):
                    x = x0 + k * centime
                    if x < 0 or x > bases[i]:
                        continue
                    if x + tva_de(x, taux[i]) == reste:
                        nouvelles[i] = x
                        paniers = [dict(p) for p in tva_par_taux]
                        for k, p in enumerate(paniers):
                            p.update(ht_net=nouvelles[k], base_ht=nouvelles[k],
                                     montant=tva_de(nouvelles[k], taux[k]))
                        return paniers, (sum(bases, D('0'))
                                         - sum(nouvelles, D('0')))
    return None


#: ARRONDI-100 — centimes de HT qu'un second panier de TVA peut céder pour que
#: le palier soit atteint exactement (2 suffisent sur 20 000 devis 10 %/20 %
#: simulés ; 5 laisse de la marge). Miroir : ``remise.js``.
_ARRONDI_CENTIMES_CEDES = 5


def _canonical_totaux(lignes, *, remise_globale_pct, fallback_taux,
                      arrondi_pas=None):
    """QJ29 — chaîne HT → remise → TVA (par taux) → TTC pour un lot de lignes.

    ``lignes`` : itérable de LigneDevis (expose ``total_ht`` et
    ``taux_tva_effectif``). Renvoie un dict {ht_brut, remise, arrondi, ht_net,
    tva, tva_par_taux, ttc}. La remise globale s'applique proportionnellement à
    chaque panier de taux (comme le builder), réconcilié au centime.

    ARRONDI-100 — ``arrondi_pas`` (MAD, p. ex. 100) ramène le TTC au palier
    inférieur (:func:`_absorber_arrondi`) ; ``arrondi`` est la baisse de HT
    correspondante, entre la remise et le HT net. Absent / 0 (factures
    saisies, avoirs, lots, villas) ⇒ ``arrondi == 0`` et chiffres inchangés.
    """
    from decimal import Decimal as D, ROUND_HALF_UP as RH
    # XSAL5/XSAL14 — exclut les lignes optionnelles non activées et section/note.
    lignes = [li for li in lignes if ligne_compte_dans_totaux(li)]
    disc = D(str(remise_globale_pct or 0))

    def q(x):
        return x.quantize(D('0.01'), rounding=RH)

    ht_brut = sum((D(str(li.total_ht)) for li in lignes), D('0'))
    remise = q(ht_brut * disc / D('100')) if disc > 0 else D('0')
    # ERR-QAH-PROP-TOTAUX-REMISE-100-NEGATIF — un HT brut à demi-centime
    # (0,005) et une remise de 100 % arrondie AU-DESSUS (0,01) donnaient un HT
    # net de q(-0,005) = -0,01, donc un TTC négatif : le HT net est borné à 0
    # (une remise ne rend jamais un document négatif). Aucun effet ailleurs :
    # hors ce cas limite, ``ht_brut - remise`` est toujours ≥ 0.
    ht_net = max(q(ht_brut - remise), D('0.00'))

    buckets = {}
    for li in lignes:
        rate = D(str(li.taux_tva_effectif
                     if li.taux_tva_effectif is not None else fallback_taux))
        buckets[rate] = buckets.get(rate, D('0')) + D(str(li.total_ht))

    # Chaque panier expose ``ht_net`` ET ``base_ht`` (alias) : ``base_ht`` est la
    # clé qu'attendent les consommateurs de ``tva_buckets`` (UBL, PDF facture),
    # ``ht_net`` reste pour les appelants historiques — les deux valent la base
    # HT nette (après remise) du panier, pour un drop-in compatible (QX1/QX2).
    if len(buckets) <= 1:
        rate = next(iter(buckets), D(str(fallback_taux)))
        tva_amt = q(ht_net * rate / D('100'))
        tva_par_taux = [{'taux': rate, 'montant': tva_amt,
                         'ht_net': ht_net, 'base_ht': ht_net}]
    else:
        rates = sorted(buckets)
        nets = {r: q(buckets[r] * (D('1') - disc / D('100'))) for r in rates}
        residu = q(ht_net - sum(nets.values(), D('0')))
        nets[rates[-1]] = q(nets[rates[-1]] + residu)
        tva_par_taux = [
            {'taux': r, 'montant': q(nets[r] * r / D('100')),
             'ht_net': nets[r], 'base_ht': nets[r]}
            for r in rates
        ]
        tva_amt = q(sum((b['montant'] for b in tva_par_taux), D('0')))

    ttc = q(ht_net + tva_amt)
    arrondi = D('0.00')
    absorbe = _absorber_arrondi(tva_par_taux, ttc, arrondi_pas)
    if absorbe is not None:
        tva_par_taux, arrondi = absorbe
        ht_net = q(ht_net - arrondi)
        tva_amt = q(sum((b['montant'] for b in tva_par_taux), D('0')))
        ttc = q(ht_net + tva_amt)
    return {
        'ht_brut': q(ht_brut), 'remise': remise, 'arrondi': arrondi,
        'ht_net': ht_net, 'tva': tva_amt, 'tva_par_taux': tva_par_taux,
        'ttc': ttc,
    }


def totaux_multi_proprietes(totaux, n):
    """ERR-QAC-MULTIVILLA-TOTAL-XN — met un dict de totaux canoniques (sortie
    de :func:`_canonical_totaux`) à l'échelle ×N villas identiques.

    DÉCISION FONDATEUR (30/09/2026, « ×N everywhere ») : la facturation suit le
    total ×N IMPRIMÉ. Le document multiplie le total d'UNE villa (lignes =
    une villa) par N, étage par étage (``builder._scale_tot``) ; on fait
    EXACTEMENT la même chose ici, en Decimal : chaque étage au centime × un
    entier reste au centime, donc ``ht_net + tva == ttc`` tient toujours et le
    ×N de l'ERP est au centime celui du PDF. N=1 → le dict est rendu tel quel
    (chemin mono-système inchangé au bit près).
    """
    if n <= 1 or not isinstance(totaux, dict):
        return totaux
    out = dict(totaux)
    for k in ('ht_brut', 'remise', 'arrondi', 'ht_net', 'tva', 'ttc'):
        if out.get(k) is not None:
            out[k] = out[k] * n
    if isinstance(out.get('tva_par_taux'), list):
        paniers = []
        for b in out['tva_par_taux']:
            b = dict(b)
            for k in ('montant', 'ht_net', 'base_ht'):
                if b.get(k) is not None:
                    b[k] = b[k] * n
            paniers.append(b)
        out['tva_par_taux'] = paniers
    return out
