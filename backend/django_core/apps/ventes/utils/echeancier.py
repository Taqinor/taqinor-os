"""Échéancier devis → factures.

Une seule source pour les pourcentages : ``PAYMENT_TERMS_BY_MODE`` du moteur de
devis (déjà utilisé par tous les PDF). À partir d'un devis ACCEPTÉ on génère, à
la demande, des factures de tranche séparément numérotées et postées :

    Résidentiel / Agricole : 30 % acompte · 60 % matériel · 10 % solde
    Industriel / Commercial : 50 % acompte · 40 % matériel · 10 % solde

Règles :
  * chaque tranche non finale vaut EXACTEMENT son pourcentage du TTC du devis ;
  * la DERNIÈRE tranche (solde) vaut le RESTE (total devis − déjà facturé) afin
    que la somme des factures égale toujours le total du devis, au centime près ;
  * le TVA/HT de chaque tranche est le total devis × pourcentage, ce qui
    conserve le poids du split 10/20 ; le taux affiché est le taux mélangé.

QJR201 (31/08/2026) — CE MODULE NE CALCULE AUCUN PANIER. Les trois lectures
d'argent (``blended_tva_pct``, ``next_tranche``, ``solde_devis``) passent par
``utils.options.option_totaux`` : elles héritent donc SANS RECÂBLAGE de la
règle QF9 rapatriée dans le noyau par QJR200 (les accessoires Huawei orphelins
ne sont plus facturés sur une option dont l'onduleur n'est pas Huawei).
L'invariant « total imprimé == somme des tranches == total affiché » est
épinglé par ``tests/test_qjr_solde_deux_options`` et
``tests/test_qjr201_chaine_aval_panier``.

QJR21 (29/08/2026) — ``pct_or_montant`` PORTE SON UNITÉ. Le champ s'appelle
« pct OU montant » mais était TOUJOURS lu comme un pourcentage : une tranche
saisie en dirhams (p. ex. 5000) produisait une facture de 5000 % du devis. Une
tranche déclare donc désormais son unité (``pct`` / ``montant``) et toute
valeur AMBIGUË — au-delà de 100 sans déclaration — est refusée en 400 à
l'écriture (``valider_echeancier``, câblé au sérialiseur). Rétro-compatible :
sans déclaration et ≤ 100, la valeur reste un pourcentage, mot pour mot.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.ventes.models import Facture

# Ordre canonique des tranches.
TRANCHE_ORDER = ['acompte', 'materiel', 'solde']
TRANCHE_LABELS = {
    'acompte': 'Acompte',
    'materiel': 'Livraison du matériel',
    'solde': 'Solde',
}
TRANCHE_TYPE = {
    'acompte': Facture.TypeFacture.ACOMPTE,
    'materiel': Facture.TypeFacture.INTERMEDIAIRE,
    'solde': Facture.TypeFacture.SOLDE,
}

# ── QJR21 — unité d'une tranche ─────────────────────────────────────────────
#: Les deux unités qu'une tranche peut déclarer.
UNITE_PCT = 'pct'
UNITE_MONTANT = 'montant'

#: Mots acceptés pour DÉCLARER l'unité. La clé dédiée ``unite`` est lue en
#: premier ; la clé historique ``type`` (qui porte la NATURE de la tranche —
#: 'acompte' / 'intermediaire' / 'solde') vaut aussi déclaration d'unité quand
#: sa valeur est l'un de ces mots. Une nature reste une nature : 'acompte' ne
#: déclare RIEN, la règle rétro-compatible ci-dessous s'applique alors.
_MOTS_PCT = frozenset({'pct', 'pourcentage', 'pourcent', 'percent', '%'})
_MOTS_MONTANT = frozenset({'montant', 'mad', 'dh', 'dhs', 'amount', 'fixe'})


class EcheancierInvalide(ValueError):
    """Échéancier refusé. Le message porté est en FRANÇAIS, prêt pour un 400."""


def _mot_unite(valeur):
    """Unité portée par une chaîne, ou None si ce n'en est pas une."""
    if not isinstance(valeur, str):
        return None
    mot = valeur.strip().lower()
    if mot in _MOTS_PCT:
        return UNITE_PCT
    if mot in _MOTS_MONTANT:
        return UNITE_MONTANT
    return None


def unite_declaree(entree):
    """Unité DÉCLARÉE d'une tranche, ou ``None`` quand rien n'est déclaré."""
    for clef in ('unite', 'type'):
        unite = _mot_unite(entree.get(clef))
        if unite is not None:
            return unite
    return None


def normaliser_tranche(entree, index=0) -> dict:
    """Valide UNE tranche et renvoie sa forme normalisée.

    Renvoie ``{key, libelle, valeur, unite}``. Lève ``EcheancierInvalide``
    (message FR) sur une tranche non exploitable :

      * ce n'est pas un objet, ou ``pct_or_montant`` n'est pas un nombre ;
      * la valeur est négative ;
      * un POURCENTAGE déclaré dépasse 100 ;
      * la valeur dépasse 100 SANS unité déclarée — le cœur de QJR21 : une
        telle valeur ne peut pas être un pourcentage, et la lire comme tel
        facturait des centaines de fois le devis.
    """
    if not isinstance(entree, dict):
        raise EcheancierInvalide(
            f"Tranche n°{index + 1} : chaque tranche doit être un objet "
            "{libelle, type, pct_or_montant}.")

    brut = entree.get('pct_or_montant', 0)
    if brut is None or brut == '':
        brut = 0
    if isinstance(brut, bool):  # True/False n'est pas un montant
        raise EcheancierInvalide(
            f"Tranche n°{index + 1} : « pct_or_montant » doit être un nombre.")
    try:
        valeur = float(brut)
    except (TypeError, ValueError):
        raise EcheancierInvalide(
            f"Tranche n°{index + 1} : « pct_or_montant » doit être un nombre "
            f"(reçu « {brut} »).")
    if valeur != valeur or valeur in (float('inf'), float('-inf')):
        raise EcheancierInvalide(
            f"Tranche n°{index + 1} : « pct_or_montant » doit être un nombre.")
    if valeur < 0:
        raise EcheancierInvalide(
            f"Tranche n°{index + 1} : « pct_or_montant » ne peut pas être "
            "négatif.")

    unite = unite_declaree(entree)
    if unite == UNITE_PCT and valeur > 100:
        raise EcheancierInvalide(
            f"Tranche n°{index + 1} : un pourcentage ne peut pas dépasser 100 "
            f"(reçu {valeur:g}). Pour un montant en dirhams, déclarez "
            "« type » : « montant ».")
    if unite is None:
        if valeur > 100:
            raise EcheancierInvalide(
                f"Tranche n°{index + 1} : la valeur {valeur:g} est ambiguë — "
                "au-delà de 100 elle ne peut pas être un pourcentage. "
                "Déclarez « type » : « montant » pour un montant en dirhams, "
                "ou « pct » pour un pourcentage (≤ 100).")
        # Rétro-compatibilité stricte : sans déclaration et ≤ 100, la valeur
        # reste un POURCENTAGE — toutes les données d'hier sont inchangées.
        unite = UNITE_PCT

    # Nature de la tranche ('acompte' / 'intermediaire' / 'solde'). Une valeur
    # de ``type`` consommée comme UNITÉ n'est pas une nature : on retombe alors
    # sur la clé positionnelle, comme une tranche sans ``type``.
    nature = entree.get('type')
    if not isinstance(nature, str) or not nature.strip() \
            or _mot_unite(nature) is not None:
        nature = None
    key = nature or f'tranche_{index}'
    libelle = entree.get('libelle') or TRANCHE_LABELS.get(key, key)
    return {'key': key, 'libelle': libelle, 'valeur': valeur, 'unite': unite}


def valider_echeancier(entries) -> list:
    """Valide un échéancier saisi et renvoie ses tranches normalisées.

    Point d'entrée du sérialiseur (``EcheancierValidationMixin``) : une entrée
    refusée devient un 400 en français. ``None`` / vide = « pas d'échéancier
    personnalisé » (comportement par défaut), jamais une erreur.
    """
    if entries is None or entries == '' or entries == []:
        return []
    if not isinstance(entries, (list, tuple)):
        raise EcheancierInvalide(
            "L'échéancier doit être une liste de tranches "
            "[{libelle, type, pct_or_montant}].")
    return [normaliser_tranche(e, i) for i, e in enumerate(entries)]


def _q(amount) -> Decimal:
    return Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def tranches_normalisees(devis) -> list:
    """SOURCE UNIQUE des tranches d'un devis : ``[{key, libelle, valeur, unite}]``.

    Si le devis porte un ``echeancier`` JSON personnalisé (FG46), il prend le
    dessus ; sinon on lit l'échéancier éditable de la société (Paramètres →
    Devis), avec repli sur PAYMENT_TERMS_BY_MODE (comportement historique).

    LECTURE TOLÉRANTE, ÉCRITURE STRICTE : un échéancier stocké non exploitable
    (malformé, ou porteur d'une valeur ambiguë > 100 antérieure à la garde
    QJR21) retombe sur l'échéancier par défaut au lieu de facturer un montant
    absurde — la garde 400 empêche d'en créer de nouveaux.
    """
    custom = getattr(devis, 'echeancier', None)
    if custom:
        try:
            tranches = valider_echeancier(custom)
        except EcheancierInvalide:
            tranches = []  # échéancier inexploitable → repli sur le défaut
        if tranches:
            return tranches

    from apps.ventes.utils.company_settings import payment_terms_for
    mode = devis.mode_installation or 'residentiel'
    terms = payment_terms_for(getattr(devis, 'company', None), mode)
    return [{'key': key,
             'libelle': TRANCHE_LABELS.get(key, key.capitalize()),
             'valeur': terms[key],
             'unite': UNITE_PCT}
            for key in TRANCHE_ORDER]


def schedule_for_devis(devis):
    """Vue historique ``[(clé, pct_or_montant)]`` de ``tranches_normalisees``.

    Conservée pour ses appelants (dont la longueur de l'échéancier dans
    ``solde_devis``) ; l'unité de chaque valeur vit dans la forme normalisée.
    """
    return [(t['key'], t['valeur']) for t in tranches_normalisees(devis)]


def factures_actives(devis):
    """Factures de tranche non annulées du devis, dans l'ordre de création.

    YOPSB13 — filtre en Python la relation ``factures`` PRÉCHARGÉE (prefetch de
    DevisViewSet) au lieu de ``.exclude().order_by()`` : ce dernier clone le
    manager, IGNORE le cache prefetch et ré-exécute une requête par appel (N+1
    en liste), en perdant au passage les prefetch imbriqués paiements/avoirs.
    Renvoie une liste — les 3 appelants la consomment déjà en liste/itération.
    Hors liste (cache absent) : un seul SELECT, comportement inchangé."""
    factures = sorted(devis.factures.all(), key=lambda f: f.id)
    return [f for f in factures if f.statut != Facture.Statut.ANNULEE]


def blended_tva_pct(devis) -> Decimal:
    """Taux de TVA mélangé du devis (TVA/HT×100), pour l'étiquette du PDF.

    A3 — sur un devis à deux options accepté, le taux est celui de l'option
    retenue (mêmes lignes que la facture)."""
    from apps.ventes.utils.options import option_totaux
    opt = option_totaux(devis)
    ht = Decimal(str(opt['ht']))
    if ht <= 0:
        return Decimal(str(devis.taux_tva))
    return _q(Decimal(str(opt['tva'])) / ht * 100)


def _tranche_type(key):
    """Type Facture d'une tranche : depuis TRANCHE_TYPE ou INTERMEDIAIRE par défaut."""
    return TRANCHE_TYPE.get(key, Facture.TypeFacture.INTERMEDIAIRE)


def next_tranche(devis, lignes=None):
    """Décrit la prochaine tranche à facturer, ou None si l'échéancier est complet.

    Retourne un dict : key, label, type, pourcentage, ht, tva, ttc, is_last.

    NPLUS1 (27/08/2026) — ``lignes`` (optionnel) est propagé tel quel à
    ``option_totaux`` : un appelant qui a déjà les lignes en main (chemin
    d'acceptation) évite une requête de plus. Absent ⇒ comportement d'hier.

    QJR21 — une tranche qui DÉCLARE un montant vaut ce montant TTC ; son
    ``pourcentage`` est alors DÉRIVÉ (montant ÷ total TTC), jamais la valeur
    brute lue comme un pourcentage. Une tranche en pourcentage (tout
    l'existant) est calculée exactement comme hier.
    """
    tranches = tranches_normalisees(devis)
    existantes = list(factures_actives(devis))
    index = len(existantes)
    if index >= len(tranches):
        return None

    tranche = tranches[index]
    key, valeur, unite = tranche['key'], tranche['valeur'], tranche['unite']
    is_last = index == len(tranches) - 1

    # A3 — l'option acceptée est autoritative : on facture UNIQUEMENT les lignes
    # de l'option retenue (batterie exclue/incluse selon le choix), au centime.
    # Sans vraie deuxième option, ce sont les totaux complets — inchangé.
    # QJR24/D9 — avant acceptation, ce sont les totaux du TOTAL AFFICHÉ
    # (option recommandée / AVEC), jamais la somme des deux options.
    from apps.ventes.utils.options import option_totaux
    opt = option_totaux(devis, lignes=lignes)
    total_ht = Decimal(str(opt['ht']))
    total_tva = Decimal(str(opt['tva']))
    total_ttc = Decimal(str(opt['ttc']))

    pourcentage = Decimal(str(valeur))
    if is_last:
        # Le solde = reste exact pour que la somme égale le total du devis.
        deja_ht = sum((Decimal(str(f.total_ht)) for f in existantes), Decimal('0'))
        deja_tva = sum((Decimal(str(f.total_tva)) for f in existantes), Decimal('0'))
        deja_ttc = sum((Decimal(str(f.total_ttc)) for f in existantes), Decimal('0'))
        ht = _q(total_ht - deja_ht)
        tva = _q(total_tva - deja_tva)
        ttc = _q(total_ttc - deja_ttc)
        if unite == UNITE_MONTANT:
            # Un montant déclaré n'est PAS un pourcentage : la dernière tranche
            # vaut le reste, on n'en publie donc que le poids réel.
            pourcentage = _q(ttc / total_ttc * 100) if total_ttc > 0 \
                else Decimal('0')
    elif unite == UNITE_MONTANT:
        # QJR21 — montant TTC déclaré : HT/TVA suivent au prorata pour que la
        # somme des tranches égale toujours le total, au centime.
        montant = Decimal(str(valeur))
        frac = montant / total_ttc if total_ttc > 0 else Decimal('0')
        ht = _q(total_ht * frac)
        tva = _q(total_tva * frac)
        ttc = _q(montant) if total_ttc > 0 else Decimal('0.00')
        pourcentage = _q(frac * 100)
    else:
        frac = Decimal(str(valeur)) / Decimal('100')
        ht = _q(total_ht * frac)
        tva = _q(total_tva * frac)
        ttc = _q(total_ttc * frac)

    return {
        'key': key,
        'label': tranche['libelle'],
        'type': _tranche_type(key),
        'pourcentage': pourcentage,
        'ht': ht,
        'tva': tva,
        'ttc': ttc,
        'is_last': is_last,
    }


def creer_facture_tranche(devis, user, company, create_with_reference):
    """Crée et retourne la prochaine facture de tranche (postée/Émise).

    Lève ValueError si le devis n'est pas accepté ou si l'échéancier est complet.
    ``create_with_reference`` est injecté (utils.references) pour la numérotation
    sans collision, identique au reste du module ventes.

    AUD101 — la tranche naît BROUILLON puis passe par LE service d'émission
    (``domain.facturation_ops.emettre_facture``). C'était le plus grave des
    cinq chemins muets : la chaîne acompte → matériel → solde du parcours
    solaire posait ``EMISE`` sans émettre ``facture_emise``, donc sans jamais
    atteindre le grand livre, alors que ``core/events.py`` affirmait le
    contraire. Elle hérite désormais du verrou de période, du blocage crédit
    XFAC28 et de l'événement, exactement comme l'émission depuis l'écran.
    """
    if devis.statut != devis.Statut.ACCEPTE:
        raise ValueError("Le devis doit être au statut « Accepté ».")

    tr = next_tranche(devis)
    if tr is None:
        raise ValueError("Toutes les tranches de l'échéancier sont déjà facturées.")

    pct_label = int(tr['pourcentage']) if tr['pourcentage'] == int(tr['pourcentage']) \
        else tr['pourcentage']
    libelle = f"{tr['label']} {pct_label} % — devis {devis.reference}"

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            devis=devis,
            client=devis.client,
            statut=Facture.Statut.BROUILLON,
            type_facture=tr['type'],
            pourcentage=tr['pourcentage'],
            libelle=libelle,
            montant_ht=tr['ht'],
            montant_tva=tr['tva'],
            montant_ttc=tr['ttc'],
            taux_tva=blended_tva_pct(devis),
            created_by=user,
            company=company,
        )

    from django.db import transaction
    from apps.ventes.domain.facturation_ops import emettre_facture
    from apps.ventes.utils.company_settings import numbering_config
    cfg = numbering_config(company, 'facture')
    with transaction.atomic():
        facture = create_with_reference(
            Facture, cfg['prefix'], company, _create,
            padding=cfg['padding'], period=cfg['period'])
        emettre_facture(facture, user=user, source='echeancier_tranche')
    return facture


def solde_devis(devis):
    """Solde du devis : total, facturé, payé, restant (Decimals).

    A3 — le total de référence est celui de l'option acceptée (mêmes lignes que
    les factures de l'échéancier) ; sans vraie deuxième option, total complet.

    QJR24/D9 — AVANT acceptation, un devis à deux options suit le TOTAL
    AFFICHÉ (l'option recommandée / AVEC, cf. ``options.option_effective``) et
    plus jamais la somme des deux paniers : le solde décrivait une vente qui
    n'existe pas."""
    from apps.ventes.utils.options import option_totaux
    actives = factures_actives(devis)
    total = Decimal(str(option_totaux(devis)['ttc']))
    facture = sum((Decimal(str(f.total_ttc)) for f in actives), Decimal('0'))
    paye = sum(
        (Decimal(str(p.montant)) for f in actives for p in f.paiements.all()),
        Decimal('0'),
    )
    # Avoirs (notes de crédit) actifs : réduisent le restant dû. Aucun avoir
    # → 0 → solde historique strictement inchangé.
    avoirs = sum(
        (Decimal(str(a.total_ttc))
         for f in actives for a in f.avoirs.all() if a.statut != 'annulee'),
        Decimal('0'),
    )
    restant = total - paye - avoirs
    return {
        'total_ttc': _q(total),
        'facture': _q(facture),
        'paye': _q(paye),
        'avoirs': _q(avoirs),
        'restant': _q(restant),
        'tranches_total': len(schedule_for_devis(devis)),
        'tranches_facturees': len(actives),
    }
