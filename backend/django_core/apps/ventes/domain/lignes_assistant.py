"""Les LIGNES d'un devis changées par l'assistant : ajouter, modifier la
quantité, retirer, remplacer un produit par un autre.

Incident du 20/11/2026 (prod) : l'action ``ventes.devis.ligne_ajouter`` visait
``POST devis-lignes/`` (le sérialiseur de l'écran) avec le corps du relais
``{"devis": 566, "produit": 56, "quantite": 10}`` : 400 à chaque fois —
``quantite`` décimal-CHAÎNE (``DecimalStricte`` refuse un nombre JSON) et
``designation`` obligatoire alors que l'action ne la demandait pas. Et l'action
ignorait les deux OPTIONS d'un devis (lignes ``variante`` « sans » / « avec »).

Ici, la désignation et le prix viennent TOUJOURS du CATALOGUE (prix de vente
HT ``prix_vente``, ou le barème au panneau d'un forfait — la convention de la
composition ; jamais ``prix_achat``), la quantité est lue en nombre JSON OU en
texte, et l'option est explicite :

* devis à DEUX options — ``variante`` absente ou ``les_deux`` : les deux
  options (une ligne par option si le devis porte déjà des lignes d'option,
  sinon une ligne commune, la convention de ce devis) ; ``sans`` / ``avec`` :
  cette option seulement (une ligne commune est d'abord SÉPARÉE en deux
  lignes d'option, l'autre option garde la sienne intacte) ;
* devis à UNE option — la ligne est commune (``variante=''``), comme toutes
  les autres ; une option demandée est dite dans ``alertes``.

LE GESTE EST CELUI DE L'ÉCRAN (``views/ligne_devis.py``) : garde de statut
(prédicat unique ``modifiabilite`` geste LIGNES — brouillon et envoyé ;
accepté/refusé/expiré → 409 qui dit de réviser), écrivain unique
``creer_ligne`` / ``supprimer_ligne`` (marqueur ``kit_retire``), forfaits au
panneau re-tarifés, échéancier re-basé (409 ``echeancier``), garde T17 d'un
envoyé, études et caches rafraîchis, instantané de configuration, et un
ENVOYÉ corrigé en place tracé « corrigé après envoi » (décision du 19/11 :
l'assistant corrige un envoyé ; statut jamais écrit — règle #4). Aucun PDF.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging

from django.db import transaction
from django.db.models import Max, Q

logger = logging.getLogger(__name__)

AJOUTER, MODIFIER, SUPPRIMER, REMPLACER = (
    'ajouter', 'modifier', 'supprimer', 'remplacer')
OPERATIONS = (AJOUTER, MODIFIER, SUPPRIMER, REMPLACER)
SANS, AVEC, LES_DEUX = 'sans', 'avec', 'les_deux'
VARIANTES = (SANS, AVEC, LES_DEUX)
#: Bornes de la quantité demandée (``LigneDevis.quantite`` : 10 chiffres, 2
#: décimales) ; au-delà de deux décimales, arrondi au centième.
#: CI de la file d'attente #1516 (api-fuzz) — une quantité démesurée (≈ 10^8)
#: faisait déborder `marge_snapshot` (12 chiffres) au geste suivant sur le devis
#: (500 sur reappliquer-lead). Aucune ligne d'un devis solaire n'approche 10 000.
QUANTITE_MIN, QUANTITE_MAX = Decimal('0.01'), Decimal('10000')
_CENTIEME = Decimal('0.01')
_LIBELLES_CLOS = {'accepte': 'accepté', 'refuse': 'refusé', 'expire': 'expiré'}
_LIBELLES_OPTION = {SANS: 'sans batterie', AVEC: 'avec batterie'}


class LignesRefusees(Exception):
    """Un refus : ``corps = {detail, field, code}`` au statut HTTP ``statut``
    (409 par défaut : l'état du devis s'oppose ; 404 : objet introuvable)."""

    def __init__(self, detail, *, field, code, statut=409):
        super().__init__(detail)
        self.corps = {'detail': detail, 'field': field, 'code': code}
        self.statut = statut


# ── Entrées ──────────────────────────────────────────────────────────────────

def lire_quantite(valeur):
    """La quantité demandée, en ``Decimal`` au centième : nombre JSON OU texte
    décimal (``10``, ``2.5``, ``"10"``). ``None`` si absente. Un booléen, un
    texte illisible, zéro, un négatif ou un nombre démesuré → 400 nommé."""
    if valeur is None:
        return None
    nombre = None
    if not isinstance(valeur, bool) and isinstance(valeur, (int, float, str, Decimal)):
        try:
            nombre = Decimal(str(valeur).strip())
        except (InvalidOperation, ValueError):
            nombre = None
    if nombre is not None and nombre.is_finite():
        nombre = nombre.quantize(_CENTIEME, rounding=ROUND_HALF_UP)
        if QUANTITE_MIN <= nombre <= QUANTITE_MAX:
            return nombre
    raise LignesRefusees(
        'quantite : un nombre strictement positif, au plus 10 000 et deux '
        'décimales, par exemple 10 ou 2.5.', field='quantite', code='quantite_invalide',
        statut=400)


def refus_de_statut(devis):
    """Le refus d'un devis dont les lignes ne se modifient plus (geste LIGNES
    du prédicat unique), avec le geste qui marche ; ``None`` si modifiable."""
    from .modifiabilite import LIGNES, verdict

    if verdict(devis, LIGNES)['modifiable']:
        return None
    ref = devis.reference
    if not devis.is_active:
        return LignesRefusees(
            f'Devis {ref} remplacé par une nouvelle version : ses lignes ne se '
            'modifient plus. Travaillez sur la version en cours.',
            field='statut', code='version_remplacee')
    libelle = _LIBELLES_CLOS.get(devis.statut, devis.get_statut_display())
    return LignesRefusees(
        f'Devis {ref} {libelle} : ses lignes ne se modifient plus. Proposez de '
        'le réviser (nouvelle version V2 en brouillon), puis changez les '
        'lignes sur la V2.', field='statut', code='revision_possible')


def produit_vendable(devis, produit_id):
    """Le produit du catalogue de la société (ou du catalogue global), non
    archivé et TARIFÉ ; sinon un refus nommé (404 introuvable, 409 sinon)."""
    from apps.stock.selectors import produits_qs

    # Lecteurs aval (constat 6) — la fiche jointe : l'écrivain unique range le
    # rôle qu'elle prouve (``lignes._role_de_la_fiche``), comme le générateur.
    produit = produits_qs().select_related('fiche_technique').filter(
        Q(company_id=devis.company_id) | Q(company__isnull=True),
        pk=produit_id).first()
    if produit is None:
        raise LignesRefusees(
            f'Produit {produit_id} introuvable dans le catalogue : cherchez-le '
            'dans le catalogue de la société.', field='produit',
            code='produit_inconnu', statut=404)
    if getattr(produit, 'is_archived', False):
        raise LignesRefusees(
            f'Le produit « {produit.nom} » est archivé : il ne se vend plus.',
            field='produit', code='produit_archive')
    if not produit.prix_vente or Decimal(str(produit.prix_vente)) <= 0:
        raise LignesRefusees(
            f'Le produit « {produit.nom} » n\'a pas de prix de vente au '
            'catalogue : renseignez son prix avant de l\'ajouter au devis.',
            field='produit', code='produit_sans_prix')
    return produit


# ── Options et lignes visées ─────────────────────────────────────────────────

def _autre(variante):
    return AVEC if variante == SANS else SANS


def _lignes_produit(devis):
    return devis.lignes.filter(type_ligne='produit')


def variantes_a_poser(devis, variante, deux):
    """Les valeurs de ``variante`` des lignes à CRÉER (voir la docstring)."""
    if not deux:
        return ['']
    if variante in (SANS, AVEC):
        return [variante]
    if _lignes_produit(devis).exclude(variante='').exists():
        return [SANS, AVEC]
    return ['']


def lignes_visees(devis, ligne_id, variante, deux):
    """``[(ligne, option_a_separer)]`` : la ligne désignée et, sur un devis à
    deux options sans option précise, sa jumelle de l'autre option (même
    produit) ; avec une option précise, la ligne de CETTE option — une ligne
    commune est rendue avec l'option à séparer."""
    ligne = _lignes_produit(devis).filter(pk=ligne_id).first()
    if ligne is None:
        raise LignesRefusees(
            f'Ligne {ligne_id} introuvable sur le devis {devis.reference} : '
            'relisez les lignes du devis.', field='ligne',
            code='ligne_inconnue', statut=404)
    propre = ligne.variante or ''
    if not deux or variante not in (SANS, AVEC):
        visees = [(ligne, None)]
        if deux and propre and ligne.produit_id:
            jumelle = _lignes_produit(devis).filter(
                produit_id=ligne.produit_id, variante=_autre(propre)).first()
            if jumelle is not None:
                visees.append((jumelle, None))
        return visees
    if propre == variante:
        return [(ligne, None)]
    if not propre:
        return [(ligne, variante)]
    jumelle = (_lignes_produit(devis).filter(
        produit_id=ligne.produit_id, variante=variante).first()
        if ligne.produit_id else None)
    if jumelle is None:
        raise LignesRefusees(
            f'La ligne « {ligne.designation} » n\'est que dans l\'option '
            f'{_LIBELLES_OPTION[propre]} : rien à changer dans l\'option '
            f'{_LIBELLES_OPTION[variante]}.', field='variante',
            code='ligne_hors_option')
    return [(jumelle, None)]


def separer(ligne, variante):
    """Une ligne COMMUNE devient la ligne de l'AUTRE option ; sa copie
    exacte (écrivain unique) devient celle de ``variante``, qui est rendue."""
    from .lignes import CHAMPS_CLONES, creer_ligne

    champs = {champ: getattr(ligne, champ) for champ in CHAMPS_CLONES}
    ligne.variante = _autre(variante)
    ligne.save(update_fields=['variante'])
    return creer_ligne(ligne.devis, **{**champs, 'variante': variante})


# ── Écritures ────────────────────────────────────────────────────────────────

def _prix_catalogue_ht(produit, devis, variante):
    """Le prix HT d'une ligne catalogue : le barème au panneau d'un forfait
    (compte de panneaux de l'option), sinon ``prix_vente``."""
    from .lignes import comptes_panneaux_du_devis, prix_forfait_ht

    comptes = comptes_panneaux_du_devis(devis) or {}
    nb = comptes.get(variante or '', comptes.get(''))
    bareme = prix_forfait_ht(produit, nb) if nb is not None else None
    return bareme if bareme is not None else Decimal(str(produit.prix_vente))


def _ordre_suivant(devis):
    plus_haut = devis.lignes.aggregate(m=Max('ordre'))['m']
    return (plus_haut if plus_haut is not None else -1) + 1


def _nouvelle_ligne(devis, produit, quantite, variante, **reprises):
    from .lignes import creer_ligne, noter_ligne_ajoutee

    champs = {'ordre': _ordre_suivant(devis), 'quantite_manuelle': True,
              **reprises}
    ligne = creer_ligne(
        devis, produit=produit, designation=produit.nom[:255],
        quantite=quantite,
        prix_unitaire=_prix_catalogue_ht(produit, devis, variante),
        variante=variante, prix_manuel=False, ligne_composee=False, **champs)
    noter_ligne_ajoutee(ligne)
    return ligne


def _touchee(etat, ligne):
    """``(etat, pk, ligne)`` — le pk lu AVANT une suppression (Django le
    remet à ``None``)."""
    return etat, ligne.pk, ligne


def options_hors_huawei(devis, produit, deux):
    """Essai réel du 21/11 — les options dont le panier N'IMPRIME ni ne
    COMPTE ``produit`` : un accessoire Huawei (Smart Meter, clé Wi-Fi) dans
    une option à onduleur non-Huawei (règle QF9, ``utils.options``). Écrite
    là, la ligne restait hors du total et du PDF, en silence."""
    from ..utils.options import (
        AVEC_BATTERIE, SANS_BATTERIE, _blob, _blob_marque,
        _panier_sert_huawei, est_accessoire_huawei, filter_lines_for_option,
        lignes_avec_produit)

    if not deux or not est_accessoire_huawei(produit.nom or ''):
        return set()
    lignes = lignes_avec_produit(devis)
    hors = set()
    for variante, option in ((SANS, SANS_BATTERIE), (AVEC, AVEC_BATTERIE)):
        panier = filter_lines_for_option(lignes, option, devis=devis)
        if not _panier_sert_huawei(panier, _blob, _blob_marque):
            hors.add(variante)
    return hors


def ajouter(devis, *, produit, quantite, variante, deux, exclues=()):
    return [_touchee('ajoutee', _nouvelle_ligne(
        devis, produit, quantite or Decimal('1'), v))
        for v in variantes_a_poser(devis, variante, deux) if v not in exclues]


def _visees_separees(devis, ligne_id, variante, deux):
    return [separer(ligne, option) if option else ligne
            for ligne, option in lignes_visees(devis, ligne_id, variante, deux)]


def modifier(devis, *, ligne_id, quantite, variante, deux):
    touchees = []
    for ligne in _visees_separees(devis, ligne_id, variante, deux):
        ligne.quantite, ligne.quantite_manuelle = quantite, True
        ligne.save(update_fields=['quantite', 'quantite_manuelle'])
        touchees.append(_touchee('modifiee', ligne))
    return touchees


def supprimer(devis, *, ligne_id, variante, deux):
    from .lignes import supprimer_ligne

    touchees = []
    for ligne in _visees_separees(devis, ligne_id, variante, deux):
        touchees.append(_touchee('retiree', ligne))
        supprimer_ligne(ligne)
    return touchees


def remplacer(devis, *, ligne_id, produit, quantite, variante, deux):
    """Chaque ligne visée est retirée (marqueur de kit) puis remplacée À SA
    PLACE (même ordre, option, groupe, lot) par le produit du catalogue ; la
    quantité reste celle de la ligne remplacée sauf ``quantite``."""
    from .lignes import supprimer_ligne

    touchees = []
    for ancienne in _visees_separees(devis, ligne_id, variante, deux):
        reprises = {
            'ordre': ancienne.ordre, 'groupe_index': ancienne.groupe_index,
            'groupe_label': ancienne.groupe_label,
            'optionnelle': ancienne.optionnelle, 'lot_id': ancienne.lot_id,
            'quantite_manuelle': bool(quantite) or ancienne.quantite_manuelle}
        option, qte = ancienne.variante or '', quantite or ancienne.quantite
        touchees.append(_touchee('retiree', ancienne))
        supprimer_ligne(ancienne)
        touchees.append(_touchee('ajoutee', _nouvelle_ligne(
            devis, produit, qte, option, **reprises)))
    return touchees


# ── Le geste complet ─────────────────────────────────────────────────────────

def _texte(valeur):
    from apps.ventes.selectors_assistant import texte_montant
    return texte_montant(valeur)


def _options_avec_ancien(avant, apres):
    """Le bloc ``options`` (``selectors_assistant.options_du_devis``, une
    entrée par option) de l'APRÈS, chaque entrée portant aussi le total de
    son option AVANT le geste (``None`` si l'option n'existait pas)."""
    anciens = {o['variante']: o['total_ttc'] for o in avant}
    return [{**option, 'ancien_total_ttc': anciens.get(option['variante'])}
            for option in apres]


def _ecrire(devis, operation, entrees, deux, utilisateur, alertes):
    """Les écritures + re-tarification + échéancier + garde T17 d'un envoyé,
    sous UNE transaction (un refus annule tout)."""
    from .lignes import comptes_panneaux_du_devis, retarifer_forfaits_par_panneau
    from .modifiabilite import rebaser_echeancier_ou_409, ttc_du_devis
    from .tarification import (
        RemiseNonApprouvee, profondeur_remise_effective,
        reverifier_remise_apres_correction)

    comptes_avant = comptes_panneaux_du_devis(devis)
    ttc_avant = ttc_du_devis(devis)
    envoye = devis.statut == 'envoye'
    profondeur_avant = profondeur_remise_effective(devis) if envoye else None
    with transaction.atomic():
        touchees = _OPERATIONS[operation](devis, deux=deux, **entrees)
        try:
            with transaction.atomic():  # savepoint : re-tarification best-effort
                messages = retarifer_forfaits_par_panneau(
                    devis, comptes_avant=comptes_avant)
        except Exception:  # noqa: BLE001 — best-effort, comme l'écran (D-ENF22-BLE001)
            logger.warning('lignes_assistant : re-tarification ignorée '
                           '(mode dégradé)', exc_info=True)
            messages = []
        alertes.extend({'code': 'forfait', 'message': str(m)} for m in messages)
        rebaser_echeancier_ou_409(devis, ttc_avant=ttc_avant)
        if envoye:
            devis.refresh_from_db()
            try:
                reverifier_remise_apres_correction(
                    devis, utilisateur, avant=profondeur_avant)
            except RemiseNonApprouvee as erreur:
                raise LignesRefusees(erreur.message, field='remise',
                                     code='remise_non_approuvee') from erreur
    return touchees, ttc_avant


def _apres_ecriture(devis, utilisateur, avant_geste):
    """Hors transaction, comme l'écran : études + caches (pipeline
    RAFRAICHIR), instantané de configuration, trace « corrigé après envoi »."""
    from .historique_config import instantane_de_geste
    from .modifiabilite import fin_de_geste_devis
    from .pipeline import MODE_RAFRAICHIR, ORIGINE_ECRAN, IntentionDevis, appliquer

    appliquer(devis, IntentionDevis(
        origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR, company=devis.company))
    instantane_de_geste(devis, user=utilisateur)
    fin_de_geste_devis(devis, utilisateur, avant=avant_geste, objet='ligne')


def _lignes_rendues(touchees, avant, apres):
    """``lignes_touchees`` : la ligne relue (ou, retirée, telle qu'elle était),
    prix de VENTE TTC seulement."""
    rendu = []
    for etat, pk, ligne in touchees:
        lue = (avant if etat == 'retiree' else apres).get(pk) or {}
        rendu.append({
            'ligne_id': pk, 'etat': etat,
            'designation': lue.get('designation', ligne.designation),
            'quantite': lue.get('quantite', 0),
            'variante': lue.get('variante', ligne.variante or ''),
            'total_ttc': lue.get('total_ttc', '0.00'),
        })
    return rendu


def appliquer_operation(devis, operation, corps, *, utilisateur=None):
    """Joue ``operation`` (``corps`` validé : ``produit``, ``ligne``,
    ``quantite``, ``variante``) sur ``devis`` et rend le résultat compact
    (contrat ``assistant_devis_lignes_modifier.json``). Lève
    :class:`LignesRefusees` (rien n'est écrit)."""
    from apps.ventes.selectors_assistant import options_du_devis
    from apps.ventes.utils.options import deux_options_declarees
    from .composition_imposee import lignes_ttc
    from .modifiabilite import debut_de_geste_devis, ttc_du_devis

    refus = refus_de_statut(devis)
    if refus is not None:
        raise refus
    deux = deux_options_declarees(devis)
    entrees = _entrees(devis, operation, corps)
    alertes, statut = [], devis.statut
    if not deux and entrees['variante'] in (SANS, AVEC):
        alertes.append({'code': 'option_unique', 'message': (
            'Ce devis n\'a qu\'une option : la ligne vaut pour tout le devis.')})
    if operation == 'ajouter':
        _exclure_options_hors_huawei(devis, entrees, deux, alertes)
    elif operation == 'remplacer' and options_hors_huawei(devis, entrees['produit'], deux):
        # Revue adverse du 21/11 (N5) — remplacer par un accessoire Huawei dans
        # une option à onduleur non-Huawei écrivait la ligne hors total et hors PDF.
        raise LignesRefusees(
            f'« {entrees["produit"].nom} » est un accessoire de l’onduleur Huawei : il ne '
            'compte que dans l’option à onduleur Huawei. Ajoutez-le (geste « ajouter ») '
            'au lieu de remplacer une ligne.', field='produit', code='accessoire_huawei')
    options_avant = options_du_devis(devis)
    avant = {li['ligne_id']: li for li in lignes_ttc(devis, avec_ids=True)}
    avant_geste = debut_de_geste_devis(devis, utilisateur)
    touchees, ttc_avant = _ecrire(devis, operation, entrees, deux,
                                  utilisateur, alertes)
    _apres_ecriture(devis, utilisateur, avant_geste)
    devis.refresh_from_db()
    apres = {li['ligne_id']: li for li in lignes_ttc(devis, avec_ids=True)}
    options_apres = options_du_devis(devis)
    return {
        'devis_id': devis.pk,
        'reference': devis.reference,
        'statut': statut,
        'operation': operation,
        'corrige_apres_envoi': statut == 'envoye',
        'ancien_total_ttc': _texte(ttc_avant),
        'nouveau_total_ttc': _texte(ttc_du_devis(devis)),
        'options': _options_avec_ancien(options_avant, options_apres),
        'lignes_touchees': _lignes_rendues(touchees, avant, apres),
        'alertes': alertes,
    }


def _exclure_options_hors_huawei(devis, entrees, deux, alertes):
    """Un accessoire Huawei ne va pas dans une option à onduleur non-Huawei :
    option demandée -> 409 qui le dit ; les deux options -> seulement celle
    qui le compte, et l'alerte le dit."""
    hors = options_hors_huawei(devis, entrees['produit'], deux)
    if not hors:
        return
    nom = entrees['produit'].nom
    demandee = entrees['variante'] if entrees['variante'] in (SANS, AVEC) else None
    if demandee in hors or hors == {SANS, AVEC}:
        cible = _LIBELLES_OPTION[demandee] if demandee else 'aucune option'
        raise LignesRefusees(
            f'« {nom} » est un accessoire de l’onduleur Huawei : l’option '
            f'{cible} n’a pas d’onduleur Huawei, il n’y serait ni compté ni '
            'imprimé. Ajoutez-le à une option à onduleur Huawei.',
            field='variante', code='accessoire_huawei')
    entrees['exclues'] = hors
    for variante in sorted(hors):
        alertes.append({'code': 'accessoire_huawei', 'message': (
            f'« {nom} » n’est pas ajouté à l’option '
            f'{_LIBELLES_OPTION[variante]} : son onduleur n’est pas Huawei '
            '(il n’y serait ni compté ni imprimé).')})


def _entrees(devis, operation, corps):
    """Les arguments de l'opération, le produit résolu au catalogue."""
    variante = corps.get('variante') or None
    if variante is not None and variante not in VARIANTES:
        raise LignesRefusees('variante : sans, avec ou les_deux.',
                             field='variante', code='variante_invalide',
                             statut=400)
    entrees = {'variante': variante}
    if operation in (AJOUTER, REMPLACER):
        entrees['produit'] = produit_vendable(devis, corps['produit'])
    if operation in (MODIFIER, SUPPRIMER, REMPLACER):
        entrees['ligne_id'] = corps['ligne']
    if operation != SUPPRIMER:
        entrees['quantite'] = lire_quantite(corps.get('quantite'))
    if operation == MODIFIER and entrees['quantite'] is None:
        raise LignesRefusees('quantite : obligatoire pour modifier une ligne.',
                             field='quantite', code='quantite_invalide',
                             statut=400)
    return entrees


_OPERATIONS = {
    AJOUTER: ajouter,
    MODIFIER: modifier,
    SUPPRIMER: supprimer,
    REMPLACER: remplacer,
}
