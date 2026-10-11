"""ATOT21 — LA garde unique des saisies d'argent (pourcentage, montant).

Déplacée de ``views/devis_gardes`` (ACAL278) pour que le sérialiseur et
l'écrivain unique ``domain/lignes`` la partagent SANS importer une vue
(contrat import-linter « CRM never imports apps.ventes.views », atteint
transitivement par ``ventes.services``). ``views/devis_gardes`` la
re-exporte sous ses noms historiques (``_pourcentage_saisi``).
"""


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
