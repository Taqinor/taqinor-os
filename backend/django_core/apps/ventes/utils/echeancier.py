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
import logging

logger = logging.getLogger(__name__)

# Ordre canonique des tranches.
TRANCHE_ORDER = ['acompte', 'materiel', 'solde']
TRANCHE_LABELS = {
    'acompte': 'Acompte',
    'materiel': 'Livraison du matériel',
    'solde': 'Solde',
    # CIQ212 — jalons C&I (D-CIQ-13), libellés de ``company_settings``.
    'commande': 'Commande',
    'livraison_materiel': 'Livraison du matériel',
    'mise_en_service': 'Mise en service',
    'reception_definitive': 'Réception définitive',
    'reception_financeur': ("Règlement par l'organisme financeur à la "
                            "réception signée"),
    'liberation_retenue': 'Libération de la retenue de garantie',
}
TRANCHE_TYPE = {
    'acompte': Facture.TypeFacture.ACOMPTE,
    'materiel': Facture.TypeFacture.INTERMEDIAIRE,
    'solde': Facture.TypeFacture.SOLDE,
    # CIQ212 — la réception définitive est un SOLDE.
    'commande': Facture.TypeFacture.ACOMPTE,
    'livraison_materiel': Facture.TypeFacture.INTERMEDIAIRE,
    'mise_en_service': Facture.TypeFacture.INTERMEDIAIRE,
    'reception_definitive': Facture.TypeFacture.SOLDE,
    'reception_financeur': Facture.TypeFacture.SOLDE,
    'liberation_retenue': Facture.TypeFacture.SOLDE,
}
#: CIQ212 — jalons C&I dont la DERNIÈRE tranche est facturée en SOLDE.
JALONS_CI = ('commande', 'livraison_materiel', 'mise_en_service',
             'reception_definitive', 'reception_financeur',
             'liberation_retenue')
PAYEURS = ('client', 'tiers')

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
    # CIQ212 — sans nature, le JALON déclaré nomme la tranche (avant la clé
    # positionnelle d'hier).
    jalon = entree.get('jalon')
    if nature is None and isinstance(jalon, str) and jalon in TRANCHE_LABELS:
        nature = jalon
    key = nature or f'tranche_{index}'
    libelle = entree.get('libelle') or TRANCHE_LABELS.get(key, key)
    sortie = {'key': key, 'libelle': libelle, 'valeur': valeur, 'unite': unite}
    # AGR219 (contrat AGR200) — date prévue FACULTATIVE de la tranche (solde
    # « après récolte »). Absente ⇒ clé absente : un échéancier sans date
    # sort identique à l'octet. Aucune facture n'est datée par elle.
    date_prevue = date_prevue_tranche(entree, index)
    if date_prevue is not None:
        sortie['date_prevue'] = date_prevue
    # CIQ212 — champs FACULTATIFS d'une tranche (contrat
    # ``devis_replace_lines_entete.json``) : absents ⇒ clés absentes, un
    # échéancier d'hier sort identique à l'octet.
    sortie.update(_champs_jalon(entree, index))
    return sortie


def _nombre_tranche(entree, cle, index, *, entier):
    brut = entree.get(cle)
    if brut is None or (isinstance(brut, str) and not brut.strip()):
        return None
    try:
        if isinstance(brut, bool):
            raise ValueError(brut)
        valeur = float(str(brut).replace(',', '.'))
        if valeur != valeur or valeur < 0 or (
                entier and valeur != int(valeur)):
            raise ValueError(brut)
    except (TypeError, ValueError):
        raise EcheancierInvalide(
            f"Tranche n°{index + 1} : « echeancier[{index}].{cle} » doit être "
            f"un nombre {'entier ' if entier else ''}positif (reçu « {brut} »).")
    return int(valeur) if entier or valeur == int(valeur) else valeur


def _champs_jalon(entree, index):
    """CIQ212 / CIQ213 — ``jalon``, ``delai_reglement_jours``,
    ``semaines_indicatives`` et ``payeur`` d'une tranche, validés (refus FR
    nommant ``echeancier[i].<champ>``) ; seulement ceux qui sont présents."""
    from apps.ventes.utils.company_settings import JALONS_CONNUS
    sortie = {}
    jalon = entree.get('jalon')
    if jalon not in (None, ''):
        if jalon not in JALONS_CONNUS:
            raise EcheancierInvalide(
                f"Tranche n°{index + 1} : « echeancier[{index}].jalon » doit "
                f"valoir {' | '.join(JALONS_CONNUS)} (reçu « {jalon} »).")
        sortie['jalon'] = jalon
    delai = _nombre_tranche(entree, 'delai_reglement_jours', index,
                            entier=True)
    if delai is not None:
        sortie['delai_reglement_jours'] = delai
    semaines = _nombre_tranche(entree, 'semaines_indicatives', index,
                               entier=False)
    if semaines is not None:
        sortie['semaines_indicatives'] = semaines
    payeur = entree.get('payeur')
    if payeur not in (None, ''):
        if payeur not in PAYEURS:
            raise EcheancierInvalide(
                f"Tranche n°{index + 1} : « echeancier[{index}].payeur » doit "
                f"valoir client | tiers (reçu « {payeur} »).")
        sortie['payeur'] = payeur
    return sortie


def date_prevue_tranche(entree, index=0):
    """AGR219 — la ``date_prevue`` d'une tranche, ISO ``AAAA-MM-JJ``, ou
    ``None`` (non prévue). Lève ``EcheancierInvalide`` (FR, nommant
    ``echeancier[i].date_prevue``) sur une date illisible."""
    import re
    from datetime import date

    brut = entree.get('date_prevue') if isinstance(entree, dict) else None
    if brut is None or (isinstance(brut, str) and not brut.strip()):
        return None
    try:
        texte = brut.strip() if isinstance(brut, str) else ''
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', texte):
            raise ValueError(texte)
        return date.fromisoformat(texte).isoformat()
    except ValueError:
        raise EcheancierInvalide(
            f"Tranche n°{index + 1} : « echeancier[{index}].date_prevue » "
            f"doit être une date au format AAAA-MM-JJ (reçu « {brut} »).")


#: AGNR12 — tolérance (points de %) de la somme d'un échéancier tout en %.
TOLERANCE_SOMME_PCT = 0.01


def controler_somme_echeancier(entries, tranches):
    """AGNR12 (C-AGNR-008) — un échéancier TOUT EN POURCENTAGES doit faire
    100 % (à :data:`TOLERANCE_SOMME_PCT` près) et ne porter AUCUNE tranche
    vide : 70 / 60 / 10 donnait un solde de −12 780 MAD et un PDF imprimant
    70 / 60 / 10 % pour des montants 70 / 20 / 10 %. Lève
    :class:`EcheancierInvalide` (message FR qui donne le total trouvé)."""
    for i, entree in enumerate(entries or []):
        if not isinstance(entree, dict) or 'pct_or_montant' not in entree:
            continue
        brut = entree.get('pct_or_montant')
        if brut is None or (isinstance(brut, str) and not brut.strip()):
            raise EcheancierInvalide(
                f"Tranche n°{i + 1} : la tranche est vide — saisissez un "
                "pourcentage ou un montant.")
    if tranches and all(t.get('unite') == UNITE_PCT for t in tranches):
        total = sum(float(t.get('valeur') or 0) for t in tranches)
        if abs(total - 100.0) > TOLERANCE_SOMME_PCT:
            total_txt = (f"{total:g}" if total == int(total)
                         else f"{total:.2f}").replace('.', ',')
            raise EcheancierInvalide(
                f"Total des tranches : {total_txt} % — il doit faire 100 %.")


def valider_echeancier(entries, *, controler_somme=True) -> list:
    """Valide un échéancier saisi et renvoie ses tranches normalisées.

    Point d'entrée du sérialiseur (``EcheancierValidationMixin``) : une entrée
    refusée devient un 400 en français. ``None`` / vide = « pas d'échéancier
    personnalisé » (comportement par défaut), jamais une erreur.

    AGNR12 — ``controler_somme`` (défaut) refuse un échéancier tout en % dont
    la somme ≠ 100 % ou qui porte une tranche vide. La LECTURE d'un
    échéancier déjà stocké (:func:`tranches_normalisees`) passe
    ``controler_somme=False`` : une donnée d'hier hors règle reste lisible,
    aucune migration.
    """
    if entries is None or entries == '' or entries == []:
        return []
    if not isinstance(entries, (list, tuple)):
        raise EcheancierInvalide(
            "L'échéancier doit être une liste de tranches "
            "[{libelle, type, pct_or_montant}].")
    tranches = [normaliser_tranche(e, i) for i, e in enumerate(entries)]
    if controler_somme:
        controler_somme_echeancier(entries, tranches)
    return tranches


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
            # AGNR12 — lecture TOLÉRANTE : un échéancier stocké hors règle
            # de somme reste lisible (aucune migration).
            tranches = valider_echeancier(custom, controler_somme=False)
        except EcheancierInvalide:
            tranches = []  # échéancier inexploitable → repli sur le défaut
        if tranches:
            return tranches

    from apps.ventes.utils.company_settings import payment_terms_for
    mode = devis.mode_installation or 'residentiel'
    jalons = payment_terms_for(getattr(devis, 'company', None), mode)
    # CIQ212 — N jalons (liste résolue) ; les trois créneaux historiques
    # sortent identiques à l'octet (mêmes clés, libellés, valeurs).
    sortie = []
    for j in jalons:
        key = j['jalon']
        tranche = {'key': key,
                   'libelle': (TRANCHE_LABELS.get(key, key.capitalize())
                               if key in TRANCHE_ORDER else j['libelle']),
                   'valeur': j['pct'],
                   'unite': UNITE_PCT}
        if key not in TRANCHE_ORDER:
            tranche['jalon'] = key
        sortie.append(tranche)
    return sortie


def figer_echeancier(devis) -> dict:
    """AMET1 (C-AMET-003, D-ECH-FIGE) — fige l'échéancier d'un devis accepté.

    Un devis SANS échéancier propre lit les conditions société EN DIRECT
    (:func:`tranches_normalisees`) : changer les réglages réécrivait les
    tranches d'un devis déjà signé. Ici on COPIE les tranches société du jour
    dans ``devis.echeancier`` (structure d'échéancier négocié, relue telle
    quelle par :func:`tranches_normalisees`). Idempotent : un devis qui porte
    déjà un échéancier propre exploitable n'est pas touché.

    Forme rendue = contrat ``facturation/contract_samples/echeancier_fige.json``.
    """
    from django.utils import timezone
    from apps.ventes.models import Devis
    propre = getattr(devis, 'echeancier', None)
    if propre:
        try:
            if valider_echeancier(propre, controler_somme=False):
                return {'devis': devis.pk, 'deja_fige': True,
                        'jalons': list(propre)}
        except EcheancierInvalide:
            pass  # inexploitable → on fige les conditions société du jour
    fige_le = timezone.now().isoformat()
    jalons = []
    for t in tranches_normalisees(devis):
        entree = {'type': t['key'], 'libelle': t['libelle'],
                  'pct_or_montant': float(t['valeur']), 'unite': UNITE_PCT,
                  'fige_le': fige_le}
        if t.get('jalon'):
            entree['jalon'] = t['jalon']
        jalons.append(entree)
    Devis.objects.filter(pk=devis.pk).update(echeancier=jalons)
    devis.echeancier = jalons
    return {'devis': devis.pk, 'deja_fige': False, 'jalons': jalons}


def pourcentages_echeancier(devis, lignes=None) -> list:
    """PREVIEW-V3-FIX (16/09/2026, audit C3) — LE POIDS DE CHAQUE TRANCHE DE
    CE DEVIS, en pourcentage : ``[{key, libelle, pct}]`` dans l'ordre.

    Le défaut qu'elle ferme : la page publique affichait l'acompte depuis
    l'échéancier RÉEL du devis (``next_tranche``) et, trois lignes plus bas,
    les conditions générales depuis les pourcentages de la SOCIÉTÉ
    (``payment_terms_for``). Sur un devis à échéancier négocié, le client
    lisait « Acompte de 40 % » puis « Acompte à la commande : 30% » — deux
    vérités sur le même écran. Les deux lectures partent désormais d'ici.

    MÊME règle d'unité que :func:`next_tranche` : une tranche en pourcentage
    vaut sa valeur ; une tranche déclarée en DIRHAMS (QJR21) publie son poids
    réel (montant ÷ TTC du devis, au centième). Le TTC n'est lu qu'en présence
    d'une telle tranche — un échéancier en pourcentages ne coûte aucune
    requête de plus.

    NUANCE ASSUMÉE : ``next_tranche`` fait de la DERNIÈRE tranche le RESTE
    exact (pour que la somme des factures égale le devis au centime). Ici on
    publie le poids DÉCLARÉ, identique tant qu'aucune facture n'est encore
    émise — ce qui est toujours le cas quand la page client lit ces
    pourcentages. La PREMIÈRE tranche, elle, est identique dans tous les cas :
    c'est l'invariant dont dépend « jamais deux acomptes à l'écran ».
    """
    tranches = tranches_normalisees(devis)
    total_ttc = None
    out = []
    for tranche in tranches:
        if tranche['unite'] == UNITE_MONTANT:
            if total_ttc is None:
                from apps.ventes.utils.options import option_totaux
                total_ttc = Decimal(
                    str(option_totaux(devis, lignes=lignes)['ttc']))
            pct = (_q(Decimal(str(tranche['valeur'])) / total_ttc * 100)
                   if total_ttc > 0 else Decimal('0'))
        else:
            pct = Decimal(str(tranche['valeur']))
        sortie = {'key': tranche['key'], 'libelle': tranche['libelle'],
                  'pct': pct}
        if tranche.get('jalon'):
            sortie['jalon'] = tranche['jalon']  # CIQ212 (absent sinon)
        out.append(sortie)
    return out


def montants_tranches(total_ttc, pourcentages) -> dict:
    """QJR623 — les MONTANTS d'un échéancier imprimé, au centime, qui SOMMENT
    au total.

    ``pourcentages`` : paires ``(clé, pct)`` ordonnées (ou un dict ordonné).
    Chaque tranche non finale vaut ``total × pct / 100`` quantifié au centime
    (``ROUND_HALF_UP``, la règle de la chaîne canonique) ; la DERNIÈRE reçoit
    le reliquat exact, de sorte que la somme égale ``total_ttc`` au centime.

    Fonction PURE (Decimal, aucune requête). Elle ne lit JAMAIS ``next_tranche``,
    dont la dernière tranche est le reste APRÈS factures émises : un document
    de devis imprime la répartition déclarée, pas l'état de la facturation.
    """
    paires = list(pourcentages.items() if hasattr(pourcentages, 'items')
                  else pourcentages)
    total = _q(Decimal(str(total_ttc or 0)))
    out = {}
    cumul = Decimal('0')
    for i, (cle, pct) in enumerate(paires):
        if i == len(paires) - 1:
            out[cle] = total - cumul
        else:
            montant = _q(total * Decimal(str(pct or 0)) / 100)
            out[cle] = montant
            cumul += montant
    return out


def jalons_paiement_devis(devis, lignes=None) -> list:
    """CIQ212 — les JALONS de paiement d'un devis, source unique que le PDF
    et /proposition imprimeront (D3) : ``[{jalon, libelle, pct, montant_ttc,
    delai_reglement_jours, semaines_indicatives}]``.

    Même règle que :func:`montants_tranches` : chaque jalon non final vaut
    ``TTC × pct`` au centime, le DERNIER reçoit le reliquat (la somme égale le
    TTC de l'option retenue). Délai et semaines : ``None`` quand non déclarés
    (jamais un délai inventé). Fonction de lecture, aucune écriture.
    """
    from apps.ventes.utils.options import option_totaux
    tranches = tranches_normalisees(devis)
    pourcentages = pourcentages_echeancier(devis, lignes=lignes)
    total = option_totaux(devis, lignes=lignes)['ttc']
    montants = montants_tranches(
        total, [(i, p['pct']) for i, p in enumerate(pourcentages)])
    return [{
        'jalon': t.get('jalon') or t['key'],
        'libelle': t['libelle'],
        'pct': pourcentages[i]['pct'],
        'montant_ttc': montants[i],
        'delai_reglement_jours': t.get('delai_reglement_jours'),
        'semaines_indicatives': t.get('semaines_indicatives'),
    } for i, t in enumerate(tranches)]


def dates_prevues_par_creneau(devis):
    """AGR219 — la ``date_prevue`` de chaque créneau ``{acompte, materiel,
    solde}``, par la MÊME correspondance que :func:`termes_paiement_devis`
    (3 tranches → positionnelles ; sinon par clé, la PREMIÈRE tranche est
    l'acompte). ``None`` quand aucune tranche du devis n'en porte : rien à
    rendre, aucune date inventée."""
    if devis is None:
        return None
    try:
        tranches = tranches_normalisees(devis)
    except Exception:  # noqa: BLE001 — best-effort, rendu sans date
        logger.warning("echeancier.dates_prevues_par_creneau : erreur ignorée (mode dégradé)", exc_info=True)
        return None
    if not any(t.get('date_prevue') for t in tranches):
        return None
    dates = {'acompte': None, 'materiel': None, 'solde': None}
    if len(tranches) == 3:
        for cle, tr in zip(('acompte', 'materiel', 'solde'), tranches):
            dates[cle] = tr.get('date_prevue')
    else:
        par_cle = {t['key']: t.get('date_prevue') for t in tranches}
        for cle in ('materiel', 'solde'):
            if cle in par_cle:
                dates[cle] = par_cle[cle]
        dates['acompte'] = tranches[0].get('date_prevue')
    return dates


def termes_paiement_devis(devis, termes_defaut, lignes=None, *,
                          avec_dates=False) -> dict:
    """QJR622 — L'échéancier DU DEVIS rabattu sur les trois créneaux
    ``{acompte, materiel, solde}`` que les conditions imprimées nomment.

    DÉPLACÉ tel quel de ``public_views._conditions_publiques`` (sortie
    octet-identique) pour que la page publique et le PDF (QJR623) lisent UNE
    correspondance :

    * défauts = ``termes_defaut`` (les ``payment_terms`` de la SOCIÉTÉ,
      30 / 60 / 10 quand une clé manque) ;
    * 3 tranches → positionnelles (acompte, matériel, solde), nommées ou non ;
    * sinon → par clé, et la PREMIÈRE tranche EST l'acompte (celle que
      ``next_tranche`` sert au client) ;
    * ``devis`` absent, échéancier vide ou en erreur → la société seule.

    AGR219 — ``avec_dates=True`` ajoute ``dates_prevues`` (la date prévue
    par créneau, :func:`dates_prevues_par_creneau`) SEULEMENT quand une
    tranche en porte une ; sans date (ou sans le drapeau), sortie identique
    à l'octet.
    """
    if avec_dates:
        slots = termes_paiement_devis(devis, termes_defaut, lignes)
        dates = dates_prevues_par_creneau(devis)
        if dates is not None:
            slots['dates_prevues'] = dates
        return slots
    # CIQ212 — les défauts société arrivent en LISTE de jalons
    # (``payment_terms_for``) : rabattus sur trois créneaux (somme par
    # créneau ; trois jalons historiques ⇒ le même dict qu'hier).
    from apps.ventes.utils.company_settings import creneaux_depuis_jalons
    termes = creneaux_depuis_jalons(termes_defaut) if termes_defaut else {}
    slots = {'acompte': termes.get('acompte', 30),
             'materiel': termes.get('materiel', 60),
             'solde': termes.get('solde', 10)}
    if devis is None:
        return slots
    try:
        tranches = pourcentages_echeancier(devis, lignes=lignes)
    except Exception:  # noqa: BLE001 — best-effort, société en repli
        logger.warning("echeancier.termes_paiement_devis : erreur ignorée (mode dégradé)", exc_info=True)
        tranches = []
    if not tranches:
        return slots
    from apps.ventes.domain.regles_calcul import calcul_corrige
    if not calcul_corrige(devis):
        # Décision fondateur 08/10/2026 — devis envoyé avant AMOT70
        # (``regles_calcul = 1``) : la correspondance d'hier, défauts société
        # pour un créneau absent, le client relit ce qu'il a reçu.
        return _termes_paiement_origine(slots, tranches)
    # AMOT70 (C-AMOT-017, volet amont) — UN ÉCHÉANCIER DU DEVIS EST COMPLET :
    # un créneau qu'il ne porte pas vaut 0, jamais le défaut société (qui
    # imprimait « 60 % à la réception du matériel » à côté de 45/55 — 160 %).
    slots = {'acompte': 0, 'materiel': 0, 'solde': 0}
    if len(tranches) == 3:
        # Forme canonique (acompte / matériel / solde), nommée ou simplement
        # positionnelle : les trois créneaux suivent.
        for cle, tr in zip(('acompte', 'materiel', 'solde'), tranches):
            slots[cle] = tr['pct']
        return slots
    from apps.ventes.utils.company_settings import CRENEAU_DU_JALON
    if any(t.get('jalon') in JALONS_CI or t['key'] in JALONS_CI
           for t in tranches):
        # CIQ212 — jalons C&I (4 tranches industrielles…) : somme par créneau
        # imprimé.
        for t in tranches:
            creneau = CRENEAU_DU_JALON.get(t.get('jalon') or t['key'])
            if creneau is not None:
                slots[creneau] = slots[creneau] + t['pct']
    else:
        # Tranches typées : leur créneau ; non typées : la MÊME règle que les
        # cases (``montants_tranches`` / ``repartition_paiement``) — la
        # première est l'acompte, la dernière le solde, celles du milieu le
        # matériel.
        dernier = len(tranches) - 1
        for i, t in enumerate(tranches):
            cle = t['key'] if t['key'] in slots else (
                'acompte' if i == 0 else 'solde' if i == dernier
                else 'materiel')
            slots[cle] = slots[cle] + t['pct']
    # La PREMIÈRE tranche non typée EST l'acompte (rang 0 ci-dessus) ; aucune
    # réaffectation de plus — la somme des créneaux reste celle des tranches.
    return slots


def _termes_paiement_origine(slots, tranches):
    """``termes_paiement_devis`` d'AVANT AMOT70, pour un devis aux règles
    d'origine (décision fondateur 08/10/2026) : ``slots`` porte les défauts
    société ; un créneau que l'échéancier ne nomme pas les garde."""
    slots = dict(slots)
    if len(tranches) == 3:
        for cle, tr in zip(('acompte', 'materiel', 'solde'), tranches):
            slots[cle] = tr['pct']
        return slots
    par_cle = {t['key']: t['pct'] for t in tranches}
    for cle in ('acompte', 'materiel', 'solde'):
        if cle in par_cle:
            slots[cle] = par_cle[cle]
    from apps.ventes.utils.company_settings import CRENEAU_DU_JALON
    sommes = {}
    if any(t.get('jalon') in JALONS_CI or t['key'] in JALONS_CI
           for t in tranches):
        for t in tranches:
            creneau = CRENEAU_DU_JALON.get(t.get('jalon') or t['key'])
            if creneau is not None:
                sommes[creneau] = sommes.get(creneau, 0) + t['pct']
    slots.update(sommes)
    slots['acompte'] = tranches[0]['pct']
    return slots


#: CIQ213 — libellé de la tranche réglée par l'organisme financeur (jamais
#: « crédit-bail » : le mot n'est imprimé qu'après l'avis juridique, CIQ211).
LIBELLE_FINANCEUR = TRANCHE_LABELS['reception_financeur']


def modele_financeur(devis, acompte_client_pct):
    """CIQ213 — l'échéancier « règlement par l'organisme financeur à la
    réception signée » : une tranche CLIENT (acompte DÉCLARÉ, 0 possible —
    alors absente) puis la tranche ``payeur: tiers``, jalon
    ``reception_financeur``, qui porte le reste. Forme ``Devis.echeancier``
    (validée par :func:`valider_echeancier`) ; rien n'est écrit ici.

    Lève ``EcheancierInvalide`` (FR) sur un acompte hors [0, 100].
    """
    del devis  # forme indépendante du devis (le tiers est sur le devis)
    try:
        acompte = Decimal(str(acompte_client_pct))
        if not acompte.is_finite():
            raise ValueError(acompte_client_pct)
    except (TypeError, ValueError, ArithmeticError):
        raise EcheancierInvalide(
            "Acompte client : un pourcentage entre 0 et 100 est attendu.")
    if acompte < 0 or acompte > 100:
        raise EcheancierInvalide(
            "Acompte client : un pourcentage entre 0 et 100 est attendu.")
    valeur = int(acompte) if acompte == int(acompte) else float(acompte)
    reste = 100 - acompte
    reste = int(reste) if reste == int(reste) else float(reste)
    tranches = []
    if acompte > 0:
        tranches.append({'libelle': TRANCHE_LABELS['commande'],
                         'type': 'acompte', 'pct_or_montant': valeur,
                         'jalon': 'commande', 'payeur': 'client'})
    if reste > 0:
        tranches.append({'libelle': LIBELLE_FINANCEUR, 'type': 'solde',
                         'pct_or_montant': reste,
                         'jalon': 'reception_financeur', 'payeur': 'tiers'})
    return tranches


def retenue_de_tranche(devis, ttc_tranche):
    """CIQ214 — ``{taux, montant, phrase}`` de la retenue de garantie d'une
    tranche, ou None (aucune retenue demandée). Montant = taux × TTC de la
    tranche au centime ; la phrase (AUD180) dit qu'elle est retenue sur le
    règlement, sans effet sur la base taxable."""
    retenue = getattr(devis, 'retenue_garantie', None)
    if not isinstance(retenue, dict) or retenue.get('taux_pct') in (None, ''):
        return None
    try:
        taux = Decimal(str(retenue['taux_pct']))
    except (TypeError, ValueError, ArithmeticError):
        return None
    if not taux.is_finite() or taux <= 0:
        return None
    montant = _q(Decimal(str(ttc_tranche)) * taux / 100)
    return {
        'taux': taux,
        'montant': montant,
        'phrase': (f'Retenue de garantie de {taux.normalize():f} % '
                   f'({montant} MAD) retenue sur le règlement, libérée à la '
                   'réception définitive — sans effet sur la base taxable.'),
    }


def schedule_for_devis(devis):
    """Vue historique ``[(clé, pct_or_montant)]`` de ``tranches_normalisees``.

    Conservée pour ses appelants (dont la longueur de l'échéancier dans
    ``solde_devis``) ; l'unité de chaque valeur vit dans la forme normalisée.
    """
    return [(t['key'], t['valeur']) for t in tranches_normalisees(devis)]


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


def _repartir_au_centime(total, poids):
    """CIQ215 — répartit ``total`` (MAD) entre les clés de ``poids`` au
    prorata, méthode du plus fort reste au centime : la somme des parts vaut
    EXACTEMENT ``total``. Poids nuls ⇒ tout sur la dernière clé.

    ATOT6 — le corps vit dans ``apps.facturation.totaux`` (module SANS
    modèle, LE service de ventilation des documents figés) : ce nom reste
    la porte historique de ses appelants."""
    from apps.facturation.totaux import repartir_au_centime
    return repartir_au_centime(total, poids)


def _tranche_type(key, is_last=False):
    """Type Facture d'une tranche : depuis TRANCHE_TYPE ou INTERMEDIAIRE par défaut.

    CIQ212 — la DERNIÈRE tranche d'un échéancier à jalons C&I est un SOLDE
    (mise en service d'un commercial 40/50/10, réception définitive d'un
    industriel) ; les clés historiques gardent leur type d'hier."""
    if is_last and key in JALONS_CI:
        return Facture.TypeFacture.SOLDE
    return TRANCHE_TYPE.get(key, Facture.TypeFacture.INTERMEDIAIRE)


def cles_tranches(tranches) -> list:
    """ATOT5 — la CLÉ unique de chaque tranche normalisée : sa ``key``,
    suffixée ``#2``, ``#3``… quand la même clé se répète (échéancier
    personnalisé à deux tranches « intermédiaire »)."""
    vues = {}
    cles = []
    for t in tranches:
        k = t['key']
        vues[k] = vues.get(k, 0) + 1
        cles.append(k if vues[k] == 1 else f'{k}#{vues[k]}')
    return cles


def next_tranche(devis, lignes=None, option=None):
    """Décrit la prochaine tranche à facturer, ou None si l'échéancier est complet.

    Retourne un dict : key, cle, label, type, pourcentage, ht, tva, ttc,
    is_last (+ ``delai_reglement_jours`` / ``payeur`` quand le jalon les
    déclare).

    VNT17 (Groupe VNT) — ADAPTATEUR de ``vente_facturation.plan_facturation``
    : plus aucun calcul ici. La prochaine tranche est la première tranche
    « à faire » du plan (cibles cumulatives bornées sur le prix convenu, toute
    la chaîne de versions, brouillon = prévu, seuls les avoirs de CORRECTION
    remis — ATOT36), la dernière à faire valant le RESTE exact.
    :func:`tranches_a_venir` en rend toutes les tranches à venir, celle-ci en
    tête : une seule formule pour la facture, la page publique, le mail
    d'acceptation et le PDF.

    ``lignes`` (NPLUS1) et ``option`` (PREVIEW-V3-FIX) sont propagés tels
    quels à ``option_totaux`` : l'acompte annoncé est celui de l'option que
    le client coche ; absents ⇒ option effective, comportement d'hier.
    """
    a_venir = tranches_a_venir(devis, lignes=lignes, option=option)
    if not a_venir:
        return None
    tr = a_venir[0]
    sortie = {
        'key': tr['key'],
        'cle': tr['cle'],
        'label': tr['libelle'],
        # VNT18 — libellé de facture (arbitrage 6) et PART RÉELLE (montant ÷
        # prix convenu) : « Solde 10 % » pour 1 600 sur 49 000 était faux.
        'libelle_facture': libelle_tranche(tr),
        'type': tr['type'],
        'pourcentage': tr['pourcentage'],
        'ht': tr['ht'],
        'tva': tr['tva'],
        'ttc': tr['montant_ttc'],
        'is_last': tr['is_last'],
    }
    # CIQ212 — délai de règlement DÉCLARÉ sur le jalon (clé absente sinon).
    if tr.get('delai_reglement_jours') is not None:
        sortie['delai_reglement_jours'] = tr['delai_reglement_jours']
    # CIQ213 — tranche réglée par un TIERS (organisme financeur).
    if tr.get('payeur') == 'tiers':
        sortie['payeur'] = 'tiers'
    return sortie


def libelle_tranche(tranche) -> str:
    """VNT18 (arbitrage 6) — le libellé d'une facture de tranche : le
    libellé de l'échéancier SEUL (« Acompte », « Solde »), suivi de « <pct> % »
    UNIQUEMENT pour une tranche déclarée en pourcentage, NON dernière, qui
    vaut exactement son pourcentage (« Livraison du matériel 60 % ») ; jamais
    la référence du devis. ``tranche`` = une tranche du plan de facturation."""
    libelle = tranche['libelle']
    if tranche['unite'] == UNITE_MONTANT or tranche['is_last']:
        return libelle
    pct = Decimal(str(tranche['valeur']))
    if _q(pct) != _q(tranche['pourcentage']):
        return libelle
    pct = (pct.quantize(Decimal('1')) if pct == pct.to_integral_value()
           else pct.normalize())
    return f'{libelle} {pct} %'


def tranches_a_venir(devis, lignes=None, option=None) -> list:
    """VNT17 — les tranches « à faire » (montant > 0) du plan de facturation,
    dans l'ordre : ``[{cle, key, libelle, montant_ttc, ht, tva,
    ventilation_tva, pourcentage, ...}]``. :func:`next_tranche` en est le
    premier élément ; le PDF (« Prochaines échéances », VNT41) et
    ``etat_vente.prochaines_echeances`` les lisent ici."""
    from apps.ventes.vente_facturation import plan_facturation
    plan = plan_facturation(devis, option=option, lignes=lignes)
    return [t for t in plan['tranches']
            if t['statut'] == 'a_faire' and t['montant_ttc'] > 0]


def creer_facture_tranche(devis, user, company, create_with_reference):
    """Émet et retourne la prochaine facture de tranche de la vente.

    Lève ValueError (400 chez l'appelant) si le devis n'est pas accepté, si
    l'échéancier est soldé ou si « Facturer la vente » refuse.
    ``company`` / ``create_with_reference`` restent dans la signature
    (appelants inchangés) mais ne sont plus lus.

    VNT65 — ENVELOPPE MINCE de « Facturer la vente »
    (``domain/facturation_vente``) : même verrou de chaîne
    (``verrouiller_vente``), même garde de version (409 ``version_remplacee``
    → ValueError nommée), le brouillon de tranche EN ATTENTE de la vente
    (p. ex. l'acompte automatique VNT62) est émis tel quel, sinon la
    prochaine tranche du plan naît par ``creer_brouillon_tranche`` (tiers
    payeur CIQ213, délai CIQ212, ventilation CIQ215, clé ATOT5) ; l'émission
    passe par ``_emettre`` (LE service d'émission AUD101 : numéro légal,
    sortie de stock VNT21, blocage crédit XFAC28 → ``CreditHoldError``).
    La garde « quatre portes » (ATOT2) refuse une tranche après une facture
    complète, de BC ou consolidée émise."""
    from django.db import transaction

    from apps.ventes.domain.facturation_vente import (
        FacturationVenteRefusee, _emettre, _exiger_vente_en_jeu,
        creer_brouillon_tranche, verrouiller_vente)
    from apps.ventes.selectors_facturation import exiger_devis_facturable
    from apps.ventes.vente_facturation import plan_facturation

    if devis.statut != devis.Statut.ACCEPTE:
        raise ValueError("Le devis doit être au statut « Accepté ».")
    exiger_devis_facturable(devis, 'tranche')
    try:
        with transaction.atomic():
            devis = next(d for d in verrouiller_vente(devis)
                         if d.pk == devis.pk)
            _exiger_vente_en_jeu(devis)
            plan = plan_facturation(devis)
            brouillon = next((t for t in plan['tranches']
                              if t['statut'] == 'brouillon'), None)
            if brouillon is not None:
                facture = Facture.objects.get(pk=brouillon['facture_id'])
            elif plan['prochaine'] is None:
                raise ValueError(
                    "Échéancier soldé : toutes les tranches de l'échéancier "
                    'sont déjà facturées (avoirs compris).')
            else:
                facture = creer_brouillon_tranche(devis, plan['prochaine'],
                                                  user)
            _emettre(facture, user)
    except FacturationVenteRefusee as exc:
        if exc.corps.get('code') == 'credit_hold':
            from apps.ventes.domain.recouvrement import CreditHoldError
            raise CreditHoldError(exc.corps['detail']) from exc
        raise ValueError(exc.corps['detail']) from exc
    facture.refresh_from_db()
    return facture


def solde_devis(devis):
    """Solde du devis : total, facturé, payé, restant (Decimals).

    A3 — le total de référence est celui de l'option acceptée (mêmes lignes que
    les factures de l'échéancier) ; sans vraie deuxième option, total complet.

    QJR24/D9 — AVANT acceptation, un devis à deux options suit le TOTAL
    AFFICHÉ (l'option recommandée / AVEC, cf. ``options.option_effective``) et
    plus jamais la somme des deux paniers : le solde décrivait une vente qui
    n'existe pas.

    AUD104 (FICHE-SOLDE, 03/09/2026) — LE « PAYÉ » N'EST PLUS RECALCULÉ ICI.
    Ce site sommait ``p.montant`` sur ``f.paiements.all()`` avec sa PROPRE
    formule et divergeait de la référence canonique ``Facture.montant_paye``
    sur TROIS termes : elle EXCLUT les paiements rejetés (YLEDG5), AJOUTE les
    escomptes (XFAC12) et AJOUTE les avances ventilées (XFAC1). Trois écarts
    réels en découlaient — un chèque impayé restait compté côté devis alors
    que la facture était correctement rouverte, un devis soldé par escompte
    affichait un restant fantôme, et un devis soldé par une avance ventilée
    affichait « restant = total ». Les avoirs, eux, étaient déjà traités
    ci-dessous : ce n'était pas un oubli global mais une ré-implémentation
    partielle, d'autant plus trompeuse qu'elle est servie sur l'écran devis
    (``serializers.py``), donc potentiellement sous les yeux du client. On LIT
    désormais la propriété — les trois divergences se ferment d'un coup."""
    # VNT19 — PROJECTION SCALAIRE de ``vente_facturation.plan_facturation``
    # (toute la chaîne de versions, les quatre portes) : aucune somme propre.
    # ``facture`` = ÉMIS net des avoirs de CORRECTION (un brouillon est
    # prévu, jamais facturé) ; ``emis`` / ``brouillons`` / ``reste_a_facturer``
    # = clés VNT5 (contrat ``devis_solde.json``).
    from apps.ventes.vente_facturation import STATUTS_EMIS, plan_facturation
    plan = plan_facturation(devis)
    parts = plan['factures_parts']
    zero = Decimal('0')
    emises = [(f, r) for f, r in parts if f.statut in STATUTS_EMIS]
    paye = sum((Decimal(str(f.montant_paye)) * r for f, r in parts), zero)
    # Avoirs (notes de crédit) actifs : réduisent le restant dû.
    avoirs = sum((Decimal(str(a.total_ttc)) * r for f, r in parts
                  for a in f.avoirs.all() if a.statut != 'annulee'), zero)
    # ATOT7 (D-ATOT-4) — le reste DÛ = dû des factures ÉMISES (payé valide,
    # avoirs, notes de débit, retenues, abandon : ``Facture.montant_du``) +
    # ce qui reste à facturer (prix − émis net des corrections, borné à 0)
    # = prix − payé − avoirs de réduction (geste, retour) sur une vente
    # ordinaire. Un brouillon n'y change rien.
    du = sum((Decimal(str(f.montant_du)) * r for f, r in emises), zero)
    a_facturer = plan['prix_convenu_ttc'] - plan['emis_net']
    restant = du + (a_facturer if a_facturer > 0 else zero)
    porte = porte_facturation(devis)
    return {
        'total_ttc': plan['prix_convenu_ttc'],
        'facture': plan['emis_net'],
        'paye': _q(paye),
        'avoirs': _q(avoirs),
        'restant': _q(restant),
        'tranches_total': len(plan['tranches']),
        # ATOT2 / VNT19 — tranches ÉMISES seulement (brouillon exclu ; la
        # complète et la facture de BC ne sont pas des tranches).
        'tranches_facturees': sum(1 for t in plan['tranches']
                                  if t['statut'] == 'emise'),
        'porte_facturation': porte,
        # AMET9 / VNT19 — « plus rien à facturer » : plan plein (émis +
        # brouillons = prix convenu) ou porte « aucune ».
        'facturation_terminee': (porte == 'aucune' or (
            plan['prix_convenu_ttc'] > 0 and plan['reste_a_facturer'] <= 0)),
        'emis': _q(sum((Decimal(str(f.total_ttc)) * r for f, r in emises),
                       zero)),
        'brouillons': plan['brouillons'],
        'reste_a_facturer': plan['reste_a_facturer'],
    }


def porte_facturation(devis, actives=None):
    """ATOT2 — la porte de facturation encore ouverte sur ``devis`` :
    ``'libre'`` (aucune facture active : facturer le devis entier),
    ``'tranche'`` (un échéancier est en cours : seule la tranche suivante),
    ``'aucune'`` (complète, BC, consolidée, ou échéancier soldé).

    Lit les factures PRÉCHARGÉES du devis (liste sans N+1) ; la consolidée (``devis=None``) n'est visible que par
    ``FactureSource`` : une seule requête, et seulement pour un devis accepté
    sans facture directe (seul cas où elle change la réponse).

    VNT20 — la porte suit EXACTEMENT la garde ``exiger_devis_facturable`` :
    elle se lit sur les factures ÉMISES de la vente (chaîne de versions,
    quatre portes) ; un brouillon ne ferme aucune porte. ``actives`` est
    gardé pour la signature (ignoré)."""
    from apps.ventes.vente_facturation import factures_bloquantes
    emises = factures_bloquantes(devis, 'complete')
    if not emises:
        return 'libre'
    from apps.ventes.selectors_facturation import est_facture_de_tranche
    from apps.ventes.vente_facturation import chaine_vente
    ids = {d.pk for d in chaine_vente(devis)}
    if any(f.devis_id not in ids or not est_facture_de_tranche(f)
           for f in emises):
        return 'aucune'
    return 'tranche' if next_tranche(devis) is not None else 'aucune'
