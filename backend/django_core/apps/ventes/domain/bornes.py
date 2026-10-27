"""ATOT21 — LA garde unique des saisies d'argent (pourcentage, montant).

Déplacée de ``views/devis_gardes`` (ACAL278) pour que le sérialiseur et
l'écrivain unique ``domain/lignes`` la partagent SANS importer une vue
(contrat import-linter « CRM never imports apps.ventes.views », atteint
transitivement par ``ventes.services``). ``views/devis_gardes`` la
re-exporte sous ses noms historiques (``_pourcentage_saisi``).
"""

#: ENF11 (api-fuzz « rejected schema-compliant request ») — un montant
#: d'encaissement est STRICTEMENT positif (``"0"`` refusé « Le montant doit
#: être positif. ») : la règle est publiée dans le motif du décimal-chaîne
#: (drf-spectacular n'émet ni minimum ni maximum pour une chaîne), 12 chiffres
#: dont 2 décimales. Ici (domaine) pour que le schéma des vues
#: (``views/openapi_docs``) ET les sérialiseurs le partagent.
MOTIF_MONTANT_POSITIF = (r'^0*(?:[1-9]\d{0,9}(?:\.\d{0,2})?'
                         r'|\.(?:[1-9]\d?|0[1-9]))$')


def pourcentage_saisi(donnees, champ, defaut):
    """ACAL278 (C-ACAL-142) — lit un pourcentage du corps (``taux_tva``,
    ``remise_globale``) : ``(Decimal, None)`` si valide, ``(None, {champ:
    message})`` sinon — l'appelant répond 400 NOMMÉ, jamais un 500.

    Remplace les deux ``def _dec`` imbriqués de ``from-layout`` et ``auto``,
    qui laissaient passer ``'150'``, ``'NaN'`` ou ``'1e999'`` jusqu'à la
    contrainte ``ck_devis_remise_globale_0_100`` (IntegrityError → 500).
    Règle : absent/vide → ``defaut`` ; sinon fini, entre 0 et 100, au plus
    2 décimales (``DecimalField(max_digits=5, decimal_places=2)``)."""
    from decimal import Decimal, InvalidOperation
    brut = donnees.get(champ)
    if brut in (None, ''):
        return defaut, None
    try:
        valeur = Decimal(str(brut))
    except (InvalidOperation, ValueError, TypeError):
        valeur = None
    if valeur is None or not valeur.is_finite():
        return None, {champ: f'« {champ} » doit être un nombre fini.'}
    if valeur < 0 or valeur > 100:
        return None, {champ: f'« {champ} » doit être compris entre 0 et 100.'}
    if valeur.normalize().as_tuple().exponent < -2:
        return None, {champ: f'« {champ} » : au plus 2 décimales.'}
    return valeur, None


def montant_saisi(valeur, champ):
    """ATOT21 — jumeau de :func:`pourcentage_saisi` pour une quantité ou un
    prix (``DecimalField(decimal_places=2)``) : ``(Decimal, None)`` si fini,
    positif ou nul, au plus 2 décimales ; ``(None, {champ: message})`` sinon.
    ``None`` / vide → ``(None, None)`` (ligne de section/note)."""
    from decimal import Decimal, InvalidOperation
    if valeur in (None, ''):
        return None, None
    try:
        nombre = Decimal(str(valeur))
    except (InvalidOperation, ValueError, TypeError):
        nombre = None
    if nombre is None or not nombre.is_finite():
        return None, {champ: f'« {champ} » doit être un nombre fini.'}
    if nombre < 0:
        return None, {champ: f'« {champ} » doit être positif ou nul.'}
    if nombre.normalize().as_tuple().exponent < -2:
        return None, {champ: f'« {champ} » : au plus 2 décimales.'}
    return nombre, None


def total_ligne_hors_capacite(quantite, prix_unitaire, remise):
    """api-fuzz — vrai si le total d'une ligne (HT, remise déduite) ne tient
    plus dans le champ qui le sert (``total_ht``, ``DecimalField(max_digits=10,
    decimal_places=2)`` : ``99999999.995`` arrondit à 10 chiffres entiers).
    Quantité et prix valent chacun jusqu'à 8 chiffres entiers : leur produit,
    lui, peut dépasser, et la sérialisation de la ligne DÉJÀ écrite levait
    ``InvalidOperation`` (500). ``None`` (section/note) ou valeur illisible →
    faux ; ``remise`` absente vaut 0."""
    from decimal import Decimal, InvalidOperation
    try:
        if quantite is None or prix_unitaire is None:
            return False
        total = (Decimal(str(quantite)) * Decimal(str(prix_unitaire))
                 * (1 - Decimal(str(remise or 0)) / 100))
    except (InvalidOperation, ValueError, TypeError):
        return False
    return abs(total) >= Decimal('99999999.995')


def arrondi_si_nombre_json(brut):
    """api-fuzz — un NOMBRE JSON (``17.05983349296445``, flottant) est arrondi
    au centième (``core.money.quantize_mad``, demi supérieur) avant la garde :
    la garde refuse « au plus 2 décimales » une CHAÎNE saisie à la main, mais
    un flottant porte toujours du bruit binaire (``0.1 + 0.2``) — comme
    ``DecimalSouple``, le nombre est lu, jamais refusé pour sa queue. Chaîne,
    booléen, ``None`` et flottant hors capacité sont rendus tels quels (la
    garde les juge)."""
    from decimal import InvalidOperation
    from core.money import quantize_mad
    if isinstance(brut, bool) or not isinstance(brut, float):
        return brut
    try:
        return quantize_mad(brut)
    except InvalidOperation:  # NaN, infini, ou plus de 28 chiffres
        return brut
