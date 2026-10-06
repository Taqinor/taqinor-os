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


def _tranche_type(key, is_last=False):
    """Type Facture d'une tranche : depuis TRANCHE_TYPE ou INTERMEDIAIRE par défaut.

    CIQ212 — la DERNIÈRE tranche d'un échéancier à jalons C&I est un SOLDE
    (mise en service d'un commercial 40/50/10, réception définitive d'un
    industriel) ; les clés historiques gardent leur type d'hier."""
    if is_last and key in JALONS_CI:
        return Facture.TypeFacture.SOLDE
    return TRANCHE_TYPE.get(key, Facture.TypeFacture.INTERMEDIAIRE)


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
    opt = option_totaux(devis, option=option, lignes=lignes)
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
        'label': tranche['libelle'],
        'type': _tranche_type(key, is_last),
        'pourcentage': pourcentage,
        'ht': ht,
        'tva': tva,
        'ttc': ttc,
        'is_last': is_last,
    }
    # CIQ212 — délai de règlement DÉCLARÉ sur le jalon (clé absente sinon).
    if tranche.get('delai_reglement_jours') is not None:
        sortie['delai_reglement_jours'] = tranche['delai_reglement_jours']
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
    from apps.ventes.selectors import factures_via_bon_commande
    if factures_via_bon_commande(devis).exists():
        raise ValueError(
            "Ce devis est déjà facturé par son bon de commande : générer une "
            "tranche d'échéancier facturerait la même vente une seconde fois.")

    tr = next_tranche(devis)
    if tr is None:
        raise ValueError("Toutes les tranches de l'échéancier sont déjà facturées.")

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

    def _create(ref):
        extra = {} if echeance is None else {'date_echeance': echeance}
        return Facture.objects.create(
            **extra,
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
