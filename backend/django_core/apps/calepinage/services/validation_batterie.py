"""ACAL633 — la forme de la déclaration de batterie (validation).

Extraite de ``services/electrique.py`` : ``electrique`` ré-importe le module
(``_validation_batterie.valider_batterie``), jamais un alias de la fonction.
"""
from .valeurs import nombre as _nombre


def valider_batterie(saisie, calepinage=None, fusionnee=None):
    """ACAL166 — la FORME de la déclaration de batterie, refusée en NOMMANT
    le champ (``batterie.<champ>``). Aucune stratégie n'est supposée : une
    stratégie absente reste absente, et la simulation OMET le bloc en le
    disant. Les grandeurs de la batterie viennent de la FICHE du produit,
    jamais de cette saisie."""
    from .batterie import COUPLAGES, MOTIVATIONS, STRATEGIES
    from .batterie_declaration import CLES_BATTERIE
    from .electrique import _fini, _refus_champ

    if saisie is None:
        return
    if not isinstance(saisie, dict):
        _refus_champ("« batterie » doit être un objet {strategie, packs, "
                     "couplage…} (reçu : %s)." % type(saisie).__name__,
                     'batterie')
    inconnues = sorted(set(saisie) - set(CLES_BATTERIE))
    if inconnues:
        _refus_champ("Champ de la batterie inconnu : « %s ». Champs admis : "
                     "%s." % (inconnues[0], ', '.join(CLES_BATTERIE)),
                     'batterie.%s' % inconnues[0])
    for cle, admis in (('strategie', STRATEGIES), ('couplage', COUPLAGES),
                       ('motivation', tuple(MOTIVATIONS))):
        valeur = saisie.get(cle)
        if valeur not in (None, '') and valeur not in admis:
            _refus_champ("« %s » : « %s » n'est pas admis. Valeurs admises : "
                         "%s." % (cle, valeur, ', '.join(admis)),
                         'batterie.%s' % cle)
    packs = saisie.get('packs')
    if packs not in (None, ''):
        nombre = _nombre(packs)
        if (not _fini(nombre) or nombre < 1 or nombre != int(nombre)):
            _refus_champ("« packs » : saisissez un nombre entier de packs "
                         "supérieur ou égal à 1 (reçu : « %s »)." % packs,
                         'batterie.packs')
    for cle in ('seuil_effacement_kw', 'reserve_backup_kwh',
                'etat_initial_kwh'):
        brut = saisie.get(cle)
        if brut in (None, ''):
            continue
        nombre = _nombre(brut)
        if not _fini(nombre) or nombre < 0:
            _refus_champ("« %s » : saisissez un nombre positif ou nul, ou "
                         "laissez le champ vide (reçu : « %s »)."
                         % (cle, brut), 'batterie.%s' % cle)
    for cle in ('heures_charge', 'heures_decharge'):
        heures = saisie.get(cle)
        if heures in (None, ''):
            continue
        if (not isinstance(heures, (list, tuple))
                or any(isinstance(h, bool) or not isinstance(h, int)
                       or not 0 <= h <= 23 for h in heures)):
            _refus_champ("« %s » doit être une liste d'heures entières "
                         "comprises entre 0 et 23." % cle, 'batterie.%s' % cle)
    if calepinage is not None:  # D-ACAL-157 — la désignation d'un produit batterie (écriture de l'entrée)
        _valider_batterie_designee(calepinage, fusionnee or {}, {'batterie': saisie})


def drapeau_hybride(role, resolu):
    """D-ACAL-157 — ``{'hybride': bool}`` pour le rôle ``onduleur`` (décidé par le SERVEUR, ``ratio_devis.
    onduleur_designe_est_hybride``), ``{}`` pour les autres rôles : le matériel servi n'a la clé que sur l'onduleur."""
    from .ratio_devis import onduleur_designe_est_hybride

    if role != 'onduleur':
        return {}
    return {'hybride': onduleur_designe_est_hybride(
        resolu.get(role), (resolu.get('designations') or {}).get(role), (resolu.get('familles') or {}).get(role))}


def _valider_batterie_designee(calepinage, fusionnee, postee):
    """D-ACAL-157 — ``batterie.produit`` POSTÉ : un produit de la société (jamais celui d'une autre : même
    message qu'un id absent) ET membre de la MÊME liste que les candidats servis (``produits_par_type_fiche_qs``
    « batterie » : fiche batterie, actif) — un câble ou un produit sans fiche ne passe plus pour une batterie. Une
    désignation INCHANGÉE (le ``produit`` déjà stocké) n'est pas rejugée : une entrée ou une fixture qui porte une
    batterie sans fiche reste réenregistrable. AUCUN jugement sur l'onduleur à l'écriture : une batterie derrière son
    propre onduleur-chargeur, sur un onduleur réseau, est une configuration légitime et modélisée
    (``services/batterie.py`` : couplage ``ac`` par défaut) ; D-ACAL-157 ne demande que de PROPOSER le sélecteur
    pour un hybride (garde d'ÉCRAN). Un refus NOMME ``batterie.produit`` ; ``None`` / ``''`` effacent."""
    from apps.stock.selectors import get_produit_scoped, produits_par_type_fiche_qs

    from .electrique import EntreeInvalide, entree_stockee

    saisie = (postee or {}).get('batterie')
    identifiant = saisie.get('produit') if isinstance(saisie, dict) else None
    if identifiant in (None, ''):
        return
    deja = (entree_stockee(calepinage).get('batterie') or {}).get('produit')
    if deja not in (None, '') and str(deja) == str(identifiant):
        return
    company = getattr(calepinage, 'company', None)
    try:
        produit = get_produit_scoped(company, identifiant)
    except (TypeError, ValueError):
        produit = None
    if produit is None:
        raise EntreeInvalide('Produit introuvable dans votre catalogue (#%s).' % identifiant,
                             champ='batterie.produit', introuvable=True)
    if not produits_par_type_fiche_qs(company, 'batterie').filter(pk=produit.pk).exists():
        raise EntreeInvalide("« %s » n'est pas une batterie du catalogue : choisissez un produit actif de la catégorie "
                             "Batterie." % (getattr(produit, 'nom', '') or identifiant), champ='batterie.produit')
