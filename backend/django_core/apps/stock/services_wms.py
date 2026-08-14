"""Groupe NTWMS — services ÉCRITURE/orchestration de la couche entrepôt.

Ré-exporté par ``apps/stock/services.py`` (fin de fichier) : les appelants
continuent d'écrire ``from apps.stock.services import …``.

FRONTIÈRE INTER-APPS. Les casiers (``BinLocation``, FG319) et les règles de
rangement (``RegleRangement``/``CategorieStockage``, ZSTK9) vivent dans
``installations`` : ce module les LIT via ``apps.installations.selectors``
(jamais un import de ses modèles, jamais un modèle parallèle dans ``stock``).
"""
import logging

logger = logging.getLogger('stock.wms')


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS2 — Rangement guidé (put-away) proposé à la confirmation d'une réception
# ═══════════════════════════════════════════════════════════════════════════

def suggestions_rangement_reception(reception):
    """Casier SUGGÉRÉ pour chaque ligne d'une réception, AVANT validation.

    Une ligne = ``{ligne_id, produit_id, produit_nom, quantite,
    emplacement_id, emplacement_nom, bin_id, bin_code, bin_zone,
    source}`` — ``source`` vaut ``'regle'`` quand une règle de rangement
    (ZSTK9) ou un casier déjà affecté a tranché, ``'aucun'`` quand aucun
    casier n'est proposable (le magasinier range librement : comportement
    historique). Le casier reste MODIFIABLE côté client : cette fonction
    PROPOSE, elle n'écrit rien.

    La suggestion réutilise ``installations.selectors.suggerer_bin_putaway``
    (FG320/ZSTK9) : règle active → casier déjà affecté au produit → premier
    casier libre par ordre de parcours, chacun sous garde de capacité.
    """
    from apps.installations.selectors import suggerer_bin_putaway

    if reception is None:
        return []
    company = reception.company
    bon = reception.bon_commande
    emplacement = getattr(bon, 'emplacement_destination', None)
    emplacement_id = getattr(bon, 'emplacement_destination_id', None)

    lignes = (reception.lignes
              .select_related('produit')
              .order_by('id'))
    out = []
    for ligne in lignes:
        produit = ligne.produit
        entree = {
            'ligne_id': ligne.id,
            'produit_id': ligne.produit_id,
            'produit_nom': getattr(produit, 'nom', '') or '',
            'quantite': ligne.quantite,
            'emplacement_id': emplacement_id,
            'emplacement_nom': getattr(emplacement, 'nom', '') or '',
            'bin_id': None,
            'bin_code': '',
            'bin_zone': '',
            'source': 'aucun',
        }
        if ligne.produit_id:
            bin_loc = suggerer_bin_putaway(
                company, ligne.produit_id, emplacement_id,
                ligne.quantite or 0)
            if bin_loc is not None:
                entree.update({
                    'bin_id': bin_loc.id,
                    'bin_code': bin_loc.code,
                    'bin_zone': bin_loc.zone or '',
                    'source': 'regle',
                })
        out.append(entree)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS4 — Vagues de prélèvement multi-source, ordonnées par le parcours
# ═══════════════════════════════════════════════════════════════════════════

def _casier_pour_ligne(produit, quantite):
    """(bin, lot, ordre) résolus par la stratégie de picking du produit
    (NTWMS3). ``ordre`` est le rang de parcours du casier retenu — le tri
    zone → allée → casier vit dans ``BinLocation.ordre`` (FG319)."""
    from .selectors_wms import resoudre_allocation_picking

    plan = resoudre_allocation_picking(produit, quantite)
    if not plan:
        return None, None, 1000
    tete = plan[0]
    ordre = 1000
    if tete['bin_id']:
        # Le rang de parcours vient du casier lui-même (jamais recalculé ici).
        from .selectors_wms import localisation_casiers
        for casier in localisation_casiers(produit):
            if casier['bin_id'] == tete['bin_id']:
                ordre = casier['ordre']
                break
    return tete['bin_id'], tete['lot_id'], ordre


def creer_vague_depuis_besoins(*, company, user=None, besoins=None,
                               installations=None, note=''):
    """Crée UNE vague regroupant plusieurs besoins, ordonnée par le parcours.

    ``besoins`` — liste explicite ``[{produit_id, quantite, installation_id?,
    bon_commande_id?}]``. ``installations`` — liste d'ids de chantiers dont les
    réservations actives non consommées sont ajoutées automatiquement (lues via
    ``installations.selectors.own_reservation_map``, jamais un import de ses
    modèles).

    Les lignes sont triées par ordre de parcours du casier résolu (NTWMS3),
    JAMAIS par ordre de création. Lève ``ValueError`` si aucun besoin.
    """
    from django.db import transaction
    from core.numbering import create_with_reference
    from .models import Produit
    from .models_wms import LignePicking, VaguePicking

    besoins = list(besoins or [])

    if installations:
        from apps.installations.selectors import own_reservation_map
        # Le modèle Installation est atteint par l'accesseur de NOTRE propre
        # string-FK : aucune importation de `apps.installations.models`.
        modele_installation = (
            LignePicking._meta.get_field('installation').related_model)
        chantiers = modele_installation.objects.filter(
            id__in=list(installations), company=company)
        for chantier in chantiers:
            for produit_id, quantite in own_reservation_map(chantier).items():
                if quantite and quantite > 0:
                    besoins.append({
                        'produit_id': produit_id,
                        'quantite': quantite,
                        'installation_id': chantier.id,
                    })

    if not besoins:
        raise ValueError('Aucun besoin à regrouper dans cette vague.')

    # Regroupement multi-source : un même produit demandé par deux sources
    # reste DEUX lignes (chaque source doit être servie et tracée), mais la
    # tournée est unique et ordonnée.
    produits = {
        p.id: p for p in Produit.objects.filter(
            company=company,
            id__in=[b.get('produit_id') for b in besoins if b.get('produit_id')])
    }

    preparees = []
    for besoin in besoins:
        produit = produits.get(besoin.get('produit_id'))
        if produit is None:
            continue
        try:
            quantite = int(besoin.get('quantite') or 0)
        except (TypeError, ValueError):
            continue
        if quantite <= 0:
            continue
        bin_id, lot_id, ordre = _casier_pour_ligne(produit, quantite)
        preparees.append({
            'produit': produit, 'quantite': quantite, 'bin_id': bin_id,
            'lot_id': lot_id, 'ordre': ordre,
            'installation_id': besoin.get('installation_id'),
            'bon_commande_id': besoin.get('bon_commande_id'),
        })

    if not preparees:
        raise ValueError('Aucun besoin valide à regrouper dans cette vague.')

    preparees.sort(key=lambda ligne: (ligne['ordre'], ligne['produit'].nom))

    with transaction.atomic():
        def _save(reference):
            return VaguePicking.objects.create(
                company=company, reference=reference, cree_par=user,
                note=note or '')

        vague = create_with_reference(VaguePicking, 'VAG', company, _save)
        LignePicking.objects.bulk_create([
            LignePicking(
                company=company, vague=vague, produit=ligne['produit'],
                quantite_demandee=ligne['quantite'], bin_id=ligne['bin_id'],
                lot_id=ligne['lot_id'],
                installation_id=ligne['installation_id'],
                bon_commande_id=ligne['bon_commande_id'],
                ordre_parcours=rang)
            for rang, ligne in enumerate(preparees, start=1)
        ])
    return vague


def lancer_vague(vague):
    """Passe une vague de BROUILLON à LANCÉE (idempotent : une vague déjà
    lancée ou terminée n'est jamais rétrogradée). Lève ``ValueError`` sur une
    vague sans ligne."""
    from django.utils import timezone
    from .models_wms import VaguePicking

    if vague.statut != VaguePicking.Statut.BROUILLON:
        return vague
    if not vague.lignes.exists():
        raise ValueError('Une vague sans ligne ne peut pas être lancée.')
    vague.statut = VaguePicking.Statut.LANCEE
    vague.date_lancement = timezone.now()
    vague.save(update_fields=['statut', 'date_lancement'])
    return vague


def prelever_ligne_picking(*, ligne, quantite, user=None):
    """Enregistre un prélèvement sur une ligne de vague.

    Refuse (``ValueError``) une quantité non positive, un dépassement du reste
    à prélever, ou une vague non LANCÉE. Clôture automatiquement la vague quand
    toutes ses lignes sont servies.
    """
    from django.db import transaction
    from django.utils import timezone
    from .models_wms import VaguePicking

    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité prélevée doit être positive.')
    vague = ligne.vague
    if vague.statut != VaguePicking.Statut.LANCEE:
        raise ValueError(
            'La vague doit être lancée avant tout prélèvement.')
    if quantite > ligne.reste_a_prelever:
        raise ValueError(
            f'Il ne reste que {ligne.reste_a_prelever} unité(s) à prélever '
            f'sur cette ligne.')

    with transaction.atomic():
        ligne.quantite_prelevee += quantite
        ligne.save(update_fields=['quantite_prelevee'])
        vague.refresh_from_db()
        if vague.est_terminee:
            vague.statut = VaguePicking.Statut.TERMINEE
            vague.date_cloture = timezone.now()
            vague.save(update_fields=['statut', 'date_cloture'])
    return ligne


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS5 — Mouvement de stock posé depuis le poste scanner (casiers tracés)
# ═══════════════════════════════════════════════════════════════════════════

# Un scan ne peut poser que ces trois natures de mouvement : le rebut (motivé)
# et l'ajustement d'inventaire gardent leurs chemins dédiés et leurs gardes.
TYPES_MOUVEMENT_SCANNABLES = ('entree', 'sortie', 'transfert')


def enregistrer_mouvement_scanne(*, company, user, produit_id, type_mouvement,
                                 quantite, bin_source_id=None,
                                 bin_destination_id=None, reference='SCAN',
                                 note=''):
    """Pose UN ``MouvementStock`` scanné, casiers source/destination tracés.

    Réutilise ``record_stock_movement`` (jamais un chemin d'écriture
    parallèle). Un TRANSFERT ne change pas le total du produit : il ne fait que
    tracer le déplacement d'un casier vers un autre. Lève ``ValueError`` sur
    quantité non positive, produit/casier hors société, type inconnu, ou sortie
    supérieure au stock.
    """
    from django.db import transaction
    from .models import MouvementStock, Produit
    from .models_wms import LignePicking
    from .services import record_stock_movement

    if type_mouvement not in TYPES_MOUVEMENT_SCANNABLES:
        raise ValueError('Type de mouvement non scannable.')
    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité doit être positive.')

    produit = Produit.objects.filter(id=produit_id, company=company).first()
    if produit is None:
        raise ValueError('Produit introuvable dans cette société.')

    modele_bin = LignePicking._meta.get_field('bin').related_model

    def _casier(bin_id):
        if not bin_id:
            return None
        casier = modele_bin.objects.filter(id=bin_id, company=company).first()
        if casier is None:
            raise ValueError('Casier introuvable dans cette société.')
        return casier

    bin_source = _casier(bin_source_id)
    bin_destination = _casier(bin_destination_id)

    with transaction.atomic():
        verrouille = Produit.objects.select_for_update().get(id=produit.id)
        avant = verrouille.quantite_stock
        if type_mouvement == 'entree':
            apres = avant + quantite
        elif type_mouvement == 'sortie':
            if quantite > avant:
                raise ValueError(
                    f'Stock insuffisant ({avant} disponible).')
            apres = avant - quantite
        else:  # transfert : déplacement physique, total inchangé
            apres = avant
        return record_stock_movement(
            company=company, produit=verrouille,
            type_mouvement=getattr(
                MouvementStock.TypeMouvement, type_mouvement.upper()),
            quantite=quantite, quantite_avant=avant, quantite_apres=apres,
            reference=reference, note=note, created_by=user,
            bin_source=bin_source, bin_destination=bin_destination)
