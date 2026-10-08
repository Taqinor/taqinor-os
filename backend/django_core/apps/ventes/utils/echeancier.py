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

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from apps.ventes.models import Facture

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
        tranches = []
    if not tranches:
        return slots
    if len(tranches) == 3:
        # Forme canonique (acompte / matériel / solde), nommée ou simplement
        # positionnelle : les trois créneaux suivent.
        for cle, tr in zip(('acompte', 'materiel', 'solde'), tranches):
            slots[cle] = tr['pct']
    else:
        par_cle = {t['key']: t['pct'] for t in tranches}
        for cle in ('acompte', 'materiel', 'solde'):
            if cle in par_cle:
                slots[cle] = par_cle[cle]
        # CIQ212 — jalons C&I (4 tranches industrielles…) : somme par créneau
        # imprimé ; sans jalon C&I, rien ne change.
        from apps.ventes.utils.company_settings import CRENEAU_DU_JALON
        sommes = {}
        if any(t.get('jalon') in JALONS_CI or t['key'] in JALONS_CI
               for t in tranches):
            for t in tranches:
                creneau = CRENEAU_DU_JALON.get(t.get('jalon') or t['key'])
                if creneau is not None:
                    sommes[creneau] = sommes.get(creneau, 0) + t['pct']
        slots.update(sommes)
        # La PREMIÈRE tranche EST l'acompte, quel que soit son nom.
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


def _repartir_au_centime(total, poids):
    """CIQ215 — répartit ``total`` (MAD) entre les clés de ``poids`` au
    prorata, méthode du plus fort reste au centime : la somme des parts vaut
    EXACTEMENT ``total``. Poids nuls ⇒ tout sur la dernière clé."""
    cles = list(poids)
    centimes = int((Decimal(str(total)) * 100).to_integral_value())
    somme = sum((Decimal(str(poids[c])) for c in cles), Decimal('0'))
    if somme == 0:
        parts = {c: 0 for c in cles}
        parts[cles[-1]] = centimes
    else:
        exactes = {c: Decimal(centimes) * Decimal(str(poids[c])) / somme
                   for c in cles}
        parts = {c: int(exactes[c].to_integral_value(rounding=ROUND_FLOOR))
                 for c in cles}
        reste = centimes - sum(parts.values())
        ordre = sorted(cles, key=lambda c: (exactes[c] - parts[c], -cles.index(c)),
                       reverse=True)
        for c in ordre[:reste]:
            parts[c] += 1
    return {c: Decimal(parts[c]) / 100 for c in cles}


def ventilation_tva_tranche(devis, tranche, existantes=None):
    """CIQ215 — ventilation ``[{taux, base_ht, montant}]`` (chaînes) d'une
    tranche, ou None quand l'option retenue n'a qu'un taux (facture d'hier,
    octet-identique).

    Bases et TVA de la tranche réparties au prorata des bases (resp. des TVA)
    par taux de l'option retenue (``option_totaux``), au centime par le plus
    fort reste. La DERNIÈRE tranche prend le reste de CHAQUE taux, pour que
    la somme des factures égale la ventilation du devis au centime. Aucun
    taux ne change (convention 12)."""
    from apps.ventes.utils.options import option_totaux
    paniers = option_totaux(devis).get('tva_par_taux') or []
    if len(paniers) < 2:
        return None
    taux = [Decimal(str(b['taux'])) for b in paniers]
    bases_devis = {t: Decimal(str(b['base_ht'])) for t, b in zip(taux, paniers)}
    tva_devis = {t: Decimal(str(b['montant'])) for t, b in zip(taux, paniers)}
    ht, tva = Decimal(str(tranche['ht'])), Decimal(str(tranche['tva']))
    bases = tvas = None
    if tranche.get('is_last'):
        precedentes = list(existantes if existantes is not None
                           else factures_actives(devis))
        if all(f.ventilation_tva for f in precedentes):
            deja_b = {t: Decimal('0') for t in taux}
            deja_t = {t: Decimal('0') for t in taux}
            for f in precedentes:
                for b in f.ventilation_tva:
                    t = Decimal(str(b['taux']))
                    if t in deja_b:
                        deja_b[t] += Decimal(str(b['base_ht']))
                        deja_t[t] += Decimal(str(b['montant']))
            bases = {t: _q(bases_devis[t] - deja_b[t]) for t in taux}
            tvas = {t: _q(tva_devis[t] - deja_t[t]) for t in taux}
            if sum(bases.values()) != ht or sum(tvas.values()) != tva:
                bases = tvas = None
    if bases is None:
        # ATOT6 — LE service unique de ventilation d'un document figé.
        from apps.facturation.totaux import ventilation_document_fige
        return ventilation_document_fige(
            [{'taux': t, 'base_ht': bases_devis[t], 'montant': tva_devis[t]}
             for t in taux], ttc=ht + tva, ht=ht, tva=tva)
    return [{'taux': str(t), 'base_ht': str(_q(bases[t])),
             'montant': str(_q(tvas[t]))} for t in taux]


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

    Retourne un dict : key, label, type, pourcentage, ht, tva, ttc, is_last.

    NPLUS1 (27/08/2026) — ``lignes`` (optionnel) est propagé tel quel à
    ``option_totaux`` : un appelant qui a déjà les lignes en main (chemin
    d'acceptation) évite une requête de plus. Absent ⇒ comportement d'hier.

    PREVIEW-V3-FIX (16/09/2026) — ``option`` (optionnel) est propagé tel quel
    à ``option_totaux`` : la page publique doit annoncer l'acompte de l'option
    que le client est en train de COCHER, pas seulement celui de l'option
    effective. Un seul arrondi existe donc toujours — celui d'ici — au lieu
    d'une seconde règle recopiée côté vue (le défaut C1 de l'audit : la page
    devinait l'option et pouvait afficher l'acompte de l'AUTRE). ``None``
    (tous les appelants historiques) ⇒ ``option_effective``, inchangé.

    QJR21 — une tranche qui DÉCLARE un montant vaut ce montant TTC ; son
    ``pourcentage`` est alors DÉRIVÉ (montant ÷ total TTC), jamais la valeur
    brute lue comme un pourcentage. Une tranche en pourcentage (tout
    l'existant) est calculée exactement comme hier.
    """
    tranches = tranches_normalisees(devis)
    existantes = list(factures_actives(devis))
    # ATOT5 — la tranche suivante est la PREMIÈRE CLÉ non couverte par une
    # facture active de même clé (plus jamais ``tranches[len(existantes)]`` :
    # annuler l'acompte puis régénérer refacturait le matériel). Une facture
    # sans clé (historique) occupe, dans l'ordre, la première clé libre.
    cles = cles_tranches(tranches)
    couvertes = {f.cle_tranche for f in existantes if f.cle_tranche}
    sans_cle = sum(1 for f in existantes if not f.cle_tranche)
    libres = [i for i, c in enumerate(cles) if c not in couvertes][sans_cle:]
    if not libres:
        return None
    index = libres[0]

    tranche = tranches[index]
    key, valeur, unite = tranche['key'], tranche['valeur'], tranche['unite']
    # Le type suit la position déclarée (CIQ212) ; le RESTE exact va à la
    # dernière tranche RESTANTE (Σ factures − avoirs = total du devis).
    is_last_position = index == len(tranches) - 1
    is_last = len(libres) == 1

    # A3 — l'option acceptée est autoritative : on facture UNIQUEMENT les lignes
    # de l'option retenue (batterie exclue/incluse selon le choix), au centime.
    # Sans vraie deuxième option, ce sont les totaux complets — inchangé.
    # QJR24/D9 — avant acceptation, ce sont les totaux du TOTAL AFFICHÉ
    # (option recommandée / AVEC), jamais la somme des deux options.
    from apps.ventes.utils.options import option_totaux
    opt = option_totaux(devis, option=option, lignes=lignes)
    total_ht = Decimal(str(opt['ht']))
    total_tva = Decimal(str(opt['tva']))
    total_ttc = Decimal(str(opt['ttc']))

    pourcentage = Decimal(str(valeur))
    if is_last:
        # Le solde = reste exact pour que la somme égale le total du devis.
        # ATOT5 — net des AVOIRS actifs des factures existantes (un avoir de
        # révision rend du « facturable ») ; un reste nul ou négatif =
        # échéancier soldé (None), jamais une facture <= 0 (contrainte
        # ck_facture_montants_positifs -> 500).
        avoirs = [a for f in existantes for a in f.avoirs.all()
                  if a.statut != 'annulee']
        zero = Decimal('0')
        deja_ht = (sum((Decimal(str(f.total_ht)) for f in existantes), zero)
                   - sum((Decimal(str(a.total_ht)) for a in avoirs), zero))
        deja_tva = (sum((Decimal(str(f.total_tva)) for f in existantes), zero)
                    - sum((Decimal(str(a.total_tva)) for a in avoirs), zero))
        deja_ttc = (sum((Decimal(str(f.total_ttc)) for f in existantes), zero)
                    - sum((Decimal(str(a.total_ttc)) for a in avoirs), zero))
        ht = _q(total_ht - deja_ht)
        tva = _q(total_tva - deja_tva)
        ttc = _q(total_ttc - deja_ttc)
        if ttc <= 0:
            return None
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
        ttc = _q(montant) if total_ttc > 0 else Decimal('0.00')
        # ERR-QAH-VENTES-ACOMPTE-TTC-CENTIME — la TVA est le COMPLÉMENT
        # (TTC − HT), jamais un troisième arrondi séparé : le document
        # s'additionne toujours au centime (HT + TVA = TTC).
        tva = ttc - ht
        pourcentage = _q(frac * 100)
    else:
        frac = Decimal(str(valeur)) / Decimal('100')
        ht = _q(total_ht * frac)
        ttc = _q(total_ttc * frac)
        # ERR-QAH-VENTES-ACOMPTE-TTC-CENTIME — FAC-202606-0003 (acompte 30 %,
        # taux mixte 17,15 %) : trois arrondis séparés donnaient HT + TVA =
        # TTC − 0,01. Le TTC annoncé (acompte des conditions/e-mails) reste
        # celui d'hier ; la TVA en devient le complément exact.
        tva = ttc - ht

    sortie = {
        'key': key,
        'cle': cles[index],
        'label': tranche['libelle'],
        'type': _tranche_type(key, is_last_position),
        'pourcentage': pourcentage,
        'ht': ht,
        'tva': tva,
        'ttc': ttc,
        'is_last': is_last,
    }
    # CIQ212 — délai de règlement DÉCLARÉ sur le jalon (clé absente sinon).
    if tranche.get('delai_reglement_jours') is not None:
        sortie['delai_reglement_jours'] = tranche['delai_reglement_jours']
    # CIQ213 — tranche réglée par un TIERS (organisme financeur).
    if tranche.get('payeur') == 'tiers':
        sortie['payeur'] = 'tiers'
    return sortie


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

    # AUD112 — LES DEUX PORTES SE VOIENT ENFIN. `factures_actives` compte les
    # tranches via `devis.factures`, qui ne voit AUCUNE facture de la chaîne
    # BON DE COMMANDE : un devis converti en BC puis facturé pouvait être
    # facturé une SECONDE fois ici, et le client recevait deux fois la même
    # vente. Le prédicat est partagé avec l'autre porte (`selectors`), donc il
    # n'existe qu'UNE définition de « déjà facturé ».
    # ATOT2 — LES QUATRE PORTES : la garde unique refuse aussi une tranche
    # après la facture COMPLÈTE ou une CONSOLIDÉE (qui n'étaient vues par
    # personne : complète puis tranche = 240 000 facturés pour 150 000).
    # ``DevisDejaFacture`` est une ValueError → 400 chez l'appelant.
    from apps.ventes.selectors_facturation import exiger_devis_facturable
    exiger_devis_facturable(devis, 'tranche')

    tr = next_tranche(devis)
    if tr is None:
        raise ValueError(
            "Échéancier soldé : toutes les tranches de l'échéancier sont déjà "
            "facturées (avoirs compris).")

    # CIQ213 — une tranche ``payeur: tiers`` est facturée à l'organisme
    # financeur du devis (``Facture.client`` = financeur) ; ``Facture.devis``
    # garde le lien au client final. Sans tiers posé : refus en français.
    destinataire = devis.client
    if tr.get('payeur') == 'tiers':
        destinataire = getattr(devis, 'tiers_payeur', None)
        if destinataire is None:
            raise ValueError(
                "Cette tranche est réglée par un organisme financeur : "
                "renseignez le tiers payeur du devis avant de la facturer.")

    pct_label = int(tr['pourcentage']) if tr['pourcentage'] == int(tr['pourcentage']) \
        else tr['pourcentage']
    libelle = f"{tr['label']} {pct_label} % — devis {devis.reference}"

    # CIQ212 — un délai de règlement DÉCLARÉ sur le jalon fixe l'échéance
    # (émission + délai) AVANT l'émission, qui ne l'écrase pas ; sinon le
    # repli XFAC23 d'hier (délai du client). Aucun délai légal codé.
    echeance = None
    if tr.get('delai_reglement_jours') is not None:
        from datetime import timedelta
        from django.utils import timezone
        echeance = timezone.localdate() + timedelta(
            days=int(tr['delai_reglement_jours']))

    # CIQ214 — retenue de garantie DEMANDÉE par le client (D-CIQ-14) : taux ×
    # TTC de la tranche, au centime, retenue sur le RÈGLEMENT — ni le HT ni
    # la TVA ne baissent (phrase AUD180). Sans retenue : facture d'hier.
    # ATOT4 — retenue et réf. client par LE geste partagé des quatre portes
    # (`entete_facture_depuis_devis`, sur le TTC de la tranche) ; le taux de
    # tête d'une tranche reste le taux mélangé de l'option (ci-dessous).
    from apps.ventes.domain.facturation_ops import entete_facture_depuis_devis
    entete = entete_facture_depuis_devis(devis, ttc=tr['ttc'])
    entete.pop('taux_tva', None)
    # CIQ215 — TVA ventilée par taux (devis à taux mixtes) ; None sinon.
    ventilation = ventilation_tva_tranche(devis, tr)

    def _create(ref):
        extra = {} if echeance is None else {'date_echeance': echeance}
        extra.update(entete)
        return Facture.objects.create(
            **extra,
            reference=ref,
            devis=devis,
            client=destinataire,
            statut=Facture.Statut.BROUILLON,
            type_facture=tr['type'],
            pourcentage=tr['pourcentage'],
            libelle=libelle,
            montant_ht=tr['ht'],
            montant_tva=tr['tva'],
            montant_ttc=tr['ttc'],
            taux_tva=blended_tva_pct(devis),
            ventilation_tva=ventilation,
            # ATOT5 — la tranche est identifiée par sa CLÉ.
            cle_tranche=tr['cle'],
            created_by=user,
            company=company,
        )

    from django.db import transaction
    from apps.ventes.domain.facturation_ops import (
        EmissionRefusee, emettre_facture,
    )
    from apps.ventes.utils.company_settings import numbering_config
    cfg = numbering_config(company, 'facture')
    try:
        with transaction.atomic():
            facture = create_with_reference(
                Facture, cfg['prefix'], company, _create,
                padding=cfg['padding'], period=cfg['period'])
            emettre_facture(facture, user=user, source='echeancier_tranche')
    except EmissionRefusee as exc:
        # CIQ217 — un refus d'émission (p. ex. client entreprise sans ICE)
        # annule la tranche entière : rien n'est écrit, et l'appelant le
        # rend en 400 français comme ses autres refus (ValueError).
        raise ValueError(exc.motif) from exc
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
    from apps.ventes.utils.options import option_totaux
    actives = factures_actives(devis)
    total = Decimal(str(option_totaux(devis)['ttc']))
    facture = sum((Decimal(str(f.total_ttc)) for f in actives), Decimal('0'))
    paye = sum(
        (Decimal(str(f.montant_paye)) for f in actives),
        Decimal('0'),
    )
    # Avoirs (notes de crédit) actifs : réduisent le restant dû. Aucun avoir
    # → 0 → solde historique strictement inchangé.
    avoirs = sum(
        (Decimal(str(a.total_ttc))
         for f in actives for a in f.avoirs.all() if a.statut != 'annulee'),
        Decimal('0'),
    )
    # ATOT7 (C-ATOT-005) — LA définition unique du reste (D-ATOT-4) : le dû
    # des factures actives (``Facture.montant_du`` : payé valide, avoirs,
    # notes de débit, retenues subies, abandon) + ce qui reste à FACTURER
    # (TTC du devis − facturé net des avoirs, borné à 0). L'ancienne formule
    # ``total − payé − avoirs`` comptait deux fois un avoir de révision
    # (déjà sorti du total révisé) et ignorait notes de débit et RAS.
    du = sum((Decimal(str(f.montant_du)) for f in actives), Decimal('0'))
    a_facturer = total - (facture - avoirs)
    restant = du + (a_facturer if a_facturer > 0 else Decimal('0'))
    # ATOT2 — ``tranches_facturees`` ne compte plus que les factures de
    # TRANCHE (la complète et la facture de BC n'en sont pas) ; la porte
    # suivante est DITE par le serveur (contrat ``devis_solde.json``).
    from apps.ventes.selectors_facturation import est_facture_de_tranche
    tranches = [f for f in actives if est_facture_de_tranche(f, devis)]
    return {
        'total_ttc': _q(total),
        'facture': _q(facture),
        'paye': _q(paye),
        'avoirs': _q(avoirs),
        'restant': _q(restant),
        'tranches_total': len(schedule_for_devis(devis)),
        'tranches_facturees': len(tranches),
        'porte_facturation': porte_facturation(devis, actives=actives),
    }


def porte_facturation(devis, actives=None):
    """ATOT2 — la porte de facturation encore ouverte sur ``devis`` :
    ``'libre'`` (aucune facture active : facturer le devis entier),
    ``'tranche'`` (un échéancier est en cours : seule la tranche suivante),
    ``'aucune'`` (complète, BC, consolidée, ou échéancier soldé).

    Lit les factures PRÉCHARGÉES du devis (``factures_actives``, liste sans
    N+1) ; la consolidée (``devis=None``) n'est visible que par
    ``FactureSource`` : une seule requête, et seulement pour un devis accepté
    sans facture directe (seul cas où elle change la réponse)."""
    from apps.ventes.selectors_facturation import est_facture_de_tranche
    if actives is None:
        actives = factures_actives(devis)
    if any(not est_facture_de_tranche(f, devis) for f in actives):
        return 'aucune'
    if actives:
        return 'tranche' if next_tranche(devis) is not None else 'aucune'
    if devis.statut == devis.Statut.ACCEPTE:
        from apps.ventes.selectors_facturation import factures_du_devis
        if factures_du_devis(devis).exists():
            return 'aucune'
    return 'libre'
