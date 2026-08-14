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


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS6 — Unités logistiques (colis / palette) et SSCC GS1
# ═══════════════════════════════════════════════════════════════════════════

# Préfixe entreprise GS1 de repli quand la société n'a pas encore le sien :
# un préfixe INTERNE (indicateur d'extension 0) qui produit un SSCC bien formé
# et unique, sans jamais usurper le préfixe d'un tiers.
PREFIXE_SSCC_INTERNE = '0000000'


def _prochain_sscc(company):
    """SSCC libre pour cette société (référence de série = compteur interne).

    La référence de série vient du plus haut SSCC déjà émis + 1 — JAMAIS
    ``count()+1`` (un colis supprimé rétrécirait le compteur et provoquerait
    une collision, l'incident de production déjà payé).
    """
    from .gs1 import construire_sscc
    from .models_wms import UniteLogistique

    existants = (UniteLogistique.objects
                 .filter(company=company)
                 .values_list('sscc', flat=True))
    plus_haut = 0
    for code in existants:
        code = (code or '').strip()
        if len(code) == 18 and code.isdigit():
            # Les 10 chiffres de référence de série vivent entre le préfixe et
            # la clé de contrôle.
            plus_haut = max(plus_haut, int(code[8:17]))
    return construire_sscc(
        PREFIXE_SSCC_INTERNE, str(plus_haut + 1), extension='0')


def creer_unite_logistique(*, company, type_unite='colis', parent=None,
                           vague=None, poids_kg=None, dimensions=''):
    """Crée un colis ou une palette avec un SSCC GS1 fraîchement attribué.

    Refuse un parent qui n'est pas une PALETTE, un parent d'une autre société,
    et un parent déjà scellé.
    """
    from django.db import IntegrityError, transaction
    from .models_wms import UniteLogistique

    if type_unite not in dict(UniteLogistique.TypeUnite.choices):
        raise ValueError('Type d\'unité logistique inconnu.')
    if parent is not None:
        if parent.company_id != getattr(company, 'id', None):
            raise ValueError('Palette introuvable dans cette société.')
        if parent.type_unite != UniteLogistique.TypeUnite.PALETTE:
            raise ValueError('Seule une palette peut contenir une unité.')
        if parent.est_figee:
            raise ValueError('Cette palette est scellée : contenu figé.')

    derniere_erreur = None
    for _ in range(5):
        try:
            with transaction.atomic():
                return UniteLogistique.objects.create(
                    company=company, type_unite=type_unite,
                    sscc=_prochain_sscc(company), parent=parent, vague=vague,
                    poids_kg=poids_kg, dimensions=dimensions or '')
        except IntegrityError as exc:
            if 'sscc' not in str(exc).lower():
                raise
            derniere_erreur = exc
    raise derniere_erreur


def ajouter_ligne_unite_logistique(*, company, unite, produit, quantite,
                                   lot=None, ligne_picking=None):
    """Ajoute (ou cumule) une ligne de contenu dans une unité NON scellée."""
    from .models_wms import UniteLogistiqueLigne

    if unite.est_figee:
        raise ValueError(
            'Cette unité logistique est scellée : son contenu est figé.')
    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité doit être positive.')
    if produit is None or produit.company_id != getattr(company, 'id', None):
        raise ValueError('Produit introuvable dans cette société.')

    ligne = UniteLogistiqueLigne.objects.filter(
        unite=unite, produit=produit, lot=lot).first()
    if ligne is None:
        return UniteLogistiqueLigne.objects.create(
            company=company, unite=unite, produit=produit, quantite=quantite,
            lot=lot, ligne_picking=ligne_picking)
    ligne.quantite += quantite
    ligne.save(update_fields=['quantite'])
    return ligne


def sceller_unite_logistique(*, unite, user=None):
    """FIGE le contenu d'une unité et rend son étiquette SSCC imprimable.

    Idempotent (une unité déjà scellée n'est jamais re-scellée). Refuse une
    unité vide — un colis sans contenu n'a rien à expédier.
    """
    from django.utils import timezone
    from .models_wms import UniteLogistique

    if unite.est_figee:
        return unite
    a_du_contenu = unite.lignes.exists() or unite.enfants.exists()
    if not a_du_contenu:
        raise ValueError('Une unité logistique vide ne peut pas être scellée.')
    unite.statut = UniteLogistique.Statut.SCELLE
    unite.date_scellage = timezone.now()
    unite.scelle_par = user
    unite.save(update_fields=['statut', 'date_scellage', 'scelle_par'])
    return unite


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS8 — Check-in chauffeur au kiosque de quai (endpoint PUBLIC)
# ═══════════════════════════════════════════════════════════════════════════

def enregistrer_arrivee_chauffeur(*, societe_slug, code):
    """Passe un rendez-vous à ARRIVÉ depuis le kiosque public.

    Renvoie ``{quai, type_quai, heure_rendez_vous, horodatage_arrivee,
    message}`` — STRICTEMENT rien d'autre : ni client, ni transporteur, ni
    contenu de livraison, ni identifiant interne. Renvoie ``None`` (→ 404 côté
    vue) si la société ou le code est inconnu, sans distinguer les deux cas.

    IDEMPOTENT : un chauffeur qui re-valide voit la même réponse, son heure
    d'arrivée d'ORIGINE n'est jamais écrasée. Un rendez-vous ANNULÉ, TERMINÉ ou
    NON PRÉSENTÉ ne peut pas être enregistré.
    """
    from django.utils import timezone
    from authentication.models import Company
    from .models_wms import RendezVousTransporteur

    societe_slug = (str(societe_slug or '')).strip()
    code = (str(code or '')).strip().upper()
    if not societe_slug or not code:
        return None

    company = Company.objects.filter(slug=societe_slug).first()
    if company is None:
        return None

    rdv = (RendezVousTransporteur.objects
           .select_related('quai')
           .filter(company=company, code_checkin=code)
           .first())
    if rdv is None:
        return None
    if rdv.statut in (RendezVousTransporteur.Statut.ANNULE,
                      RendezVousTransporteur.Statut.TERMINE,
                      RendezVousTransporteur.Statut.NO_SHOW):
        return None

    if rdv.statut == RendezVousTransporteur.Statut.PLANIFIE:
        rdv.statut = RendezVousTransporteur.Statut.ARRIVE
        # Horodatage SERVEUR : jamais une heure fournie par le kiosque.
        rdv.date_arrivee = timezone.now()
        # Le créneau ne bouge pas : la garde de chevauchement de `save()`
        # s'exclut elle-même par pk et ne peut donc pas refuser ce passage.
        rdv.save(update_fields=['statut', 'date_arrivee'])

    return {
        'quai': rdv.quai.nom if rdv.quai_id else '',
        'type_quai': rdv.quai.type_quai if rdv.quai_id else '',
        'heure_rendez_vous': rdv.date_heure_debut,
        'horodatage_arrivee': rdv.date_arrivee,
        'message': 'Arrivée enregistrée. Présentez-vous au quai indiqué.',
    }


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS9 — Expédition transporteur : étiquette réelle (gated) ou interne
# ═══════════════════════════════════════════════════════════════════════════

def _stocker_etiquette(company, expedition, pdf_bytes):
    """Dépose l'étiquette dans MinIO et renvoie sa clé.

    Réutilise le client MinIO existant (aucune dépendance nouvelle) et la
    convention de clé PRÉFIXÉE PAR SOCIÉTÉ (SCA42/ERR75) : jamais une clé
    « plate », jamais un ``FileField`` brut (ARC26).
    """
    import uuid

    from apps.ventes.utils.minio_client import (
        ensure_uploads_bucket, get_minio_client,
    )
    from django.conf import settings as django_settings

    cle = (f'stock/{getattr(company, "id", 0) or 0}/etiquettes/'
           f'{uuid.uuid4().hex}.pdf')
    client = get_minio_client()
    ensure_uploads_bucket()
    import io
    client.upload_fileobj(
        io.BytesIO(pdf_bytes), django_settings.MINIO_BUCKET_UPLOADS, cle,
        ExtraArgs={'ContentType': 'application/pdf'})
    return cle


def creer_expedition_transporteur(*, company, unite, provider_code='aucun',
                                  transporteur=None, destination='',
                                  cout_reel=None):
    """Crée une expédition BROUILLON pour une unité logistique SCELLÉE.

    Refuse une unité non scellée : on n'expédie jamais un colis dont le contenu
    peut encore changer.
    """
    from .models_wms import ExpeditionTransporteur, UniteLogistique

    if unite is None or unite.company_id != getattr(company, 'id', None):
        raise ValueError('Unité logistique introuvable dans cette société.')
    if unite.statut == UniteLogistique.Statut.EN_PREPARATION:
        raise ValueError(
            "Scellez l'unité logistique avant de l'expédier.")
    if provider_code not in dict(ExpeditionTransporteur.Provider.choices):
        raise ValueError('Transporteur inconnu.')
    return ExpeditionTransporteur.objects.create(
        company=company, unite_logistique=unite,
        transporteur_provider=provider_code, transporteur=transporteur,
        destination=destination or '', cout_reel=cout_reel)


def generer_etiquette_expedition(*, expedition, user=None):
    """Demande au connecteur son numéro de suivi + son étiquette PDF.

    Le connecteur est résolu par ``providers.provider_pour_societe`` : une
    intégration réelle si (et seulement si) elle est configurée et gated par
    une clé pour cette société, SINON le NoOp (étiquette interne, zéro appel
    réseau). Idempotent : une étiquette déjà générée n'est pas régénérée.
    """
    from django.utils import timezone

    from .models_wms import ExpeditionTransporteur
    from .providers import provider_pour_societe

    if expedition.statut == ExpeditionTransporteur.Statut.ANNULE:
        raise ValueError('Cette expédition est annulée.')
    if expedition.etiquette_pdf_key and expedition.numero_suivi:
        return expedition

    provider = provider_pour_societe(
        expedition.company, expedition.transporteur_provider)
    numero_suivi, pdf_bytes = provider.creer_expedition(
        expedition.unite_logistique)
    expedition.numero_suivi = numero_suivi or ''
    if pdf_bytes:
        expedition.etiquette_pdf_key = _stocker_etiquette(
            expedition.company, expedition, pdf_bytes)
    expedition.statut = ExpeditionTransporteur.Statut.ETIQUETTE
    expedition.date_expedition = timezone.now()
    expedition.save(update_fields=[
        'numero_suivi', 'etiquette_pdf_key', 'statut', 'date_expedition'])
    return expedition


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS11 — Poste d'emballage : contrôle de conformité BLOQUANT
# ═══════════════════════════════════════════════════════════════════════════

def controler_scan_emballage(*, company, unite, produit, quantite=1,
                             user=None):
    """Contrôle qu'un produit scanné APPARTIENT bien à la vague en cours.

    C'est la garde qui empêche d'expédier le mauvais article. Refuse
    (``ValueError``, donc 400 côté API — refus BLOQUANT avant validation du
    colis) :
      * un produit absent des lignes PRÉLEVÉES de la vague de l'unité ;
      * une quantité qui dépasserait ce qui a été réellement prélevé ;
      * une unité déjà scellée ;
      * un produit d'une autre société.

    Une unité SANS vague rattachée n'a pas d'attendu à comparer : le contrôle
    se contente alors d'enregistrer le scan (comportement historique du
    colisage libre), jamais un refus arbitraire.

    En cas de succès, la ligne de contenu est créée/incrémentée et HORODATÉE
    (``scanne_le``/``scanne_par``) pour l'audit.
    """
    from django.utils import timezone
    from .models_wms import LignePicking, UniteLogistiqueLigne

    if unite is None or unite.company_id != getattr(company, 'id', None):
        raise ValueError('Unité logistique introuvable dans cette société.')
    if unite.est_figee:
        raise ValueError(
            'Cette unité logistique est scellée : son contenu est figé.')
    if produit is None or produit.company_id != getattr(company, 'id', None):
        raise ValueError('Produit introuvable dans cette société.')
    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité doit être positive.')

    ligne_picking = None
    if unite.vague_id:
        attendues = LignePicking.objects.filter(
            vague_id=unite.vague_id, produit=produit,
            quantite_prelevee__gt=0)
        ligne_picking = attendues.order_by('ordre_parcours', 'id').first()
        if ligne_picking is None:
            raise ValueError(
                f'« {produit.nom} » n\'appartient pas à la vague en cours '
                f'd\'emballage — colis refusé.')
        total_attendu = sum(
            ligne.quantite_prelevee for ligne in attendues)
        deja_emballe = sum(
            ligne.quantite for ligne in UniteLogistiqueLigne.objects.filter(
                unite__vague_id=unite.vague_id, produit=produit))
        if deja_emballe + quantite > total_attendu:
            raise ValueError(
                f'Quantité emballée supérieure au prélevé pour '
                f'« {produit.nom} » ({total_attendu} prélevé(s)) — colis '
                f'refusé.')

    ligne = UniteLogistiqueLigne.objects.filter(
        unite=unite, produit=produit, lot=None).first()
    if ligne is None:
        ligne = UniteLogistiqueLigne(
            company=company, unite=unite, produit=produit, quantite=0,
            ligne_picking=ligne_picking)
    ligne.quantite += quantite
    ligne.scanne_le = timezone.now()
    ligne.scanne_par = user
    ligne.save()
    return ligne


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS12 — Règles de libération de vague (wave release strategy)
# ═══════════════════════════════════════════════════════════════════════════

def configurer_liberation_vague(*, vague, mode, seuil_lignes=None):
    """Pose le mode de libération d'une vague (et son seuil éventuel).

    Refuse un mode inconnu, un mode AUTO_SEUIL sans seuil positif, et toute
    reconfiguration d'une vague déjà lancée ou terminée (elle est partie : la
    règle de libération n'a plus de sens).
    """
    from .models_wms import VaguePicking

    if vague.statut != VaguePicking.Statut.BROUILLON:
        raise ValueError(
            'Seule une vague en brouillon peut changer de mode de '
            'libération.')
    if mode not in dict(VaguePicking.ModeLiberation.choices):
        raise ValueError('Mode de libération inconnu.')
    if mode == VaguePicking.ModeLiberation.AUTO_SEUIL:
        try:
            seuil_lignes = int(seuil_lignes)
        except (TypeError, ValueError):
            raise ValueError(
                'Le mode AUTO_SEUIL exige un seuil de lignes positif.')
        if seuil_lignes <= 0:
            raise ValueError(
                'Le mode AUTO_SEUIL exige un seuil de lignes positif.')
    else:
        seuil_lignes = None
    vague.mode_liberation = mode
    vague.seuil_lignes = seuil_lignes
    vague.save(update_fields=['mode_liberation', 'seuil_lignes'])
    return vague


def liberer_vagues_planifiees(*, company=None, maintenant=None):
    """Lance les vagues BROUILLON dont la règle de libération est atteinte.

    IDEMPOTENTE : une vague déjà lancée n'est jamais retouchée ; deux passages
    consécutifs produisent le même état. Conçue pour être plannifiée par Celery
    beat comme les autres jobs du module.

      * ``AUTO_HEURE`` — libérée quand l'heure locale a atteint
        ``AchatsParametres.heure_coupure_vagues`` de la société. Sans heure
        configurée : jamais libérée (comportement inchangé).
      * ``AUTO_SEUIL`` — libérée dès que le nombre de lignes atteint
        ``seuil_lignes``.
      * ``MANUEL`` — jamais touchée.

    ``maintenant`` (datetime aware) permet un test DÉTERMINISTE : la fonction
    ne lit jamais l'horloge quand il est fourni.

    Renvoie ``{'liberees': [references…], 'examinees': n}``.
    """
    from django.utils import timezone
    from .models import AchatsParametres
    from .models_wms import VaguePicking

    maintenant = maintenant or timezone.now()
    heure_locale = timezone.localtime(maintenant).time()

    qs = (VaguePicking.objects
          .filter(statut=VaguePicking.Statut.BROUILLON)
          .exclude(mode_liberation=VaguePicking.ModeLiberation.MANUEL)
          .select_related('company'))
    if company is not None:
        qs = qs.filter(company=company)

    liberees, examinees = [], 0
    # Un seul réglage lu par société (jamais un get_or_create par vague).
    parametres = {}
    for vague in qs:
        examinees += 1
        declencher = False
        if vague.mode_liberation == VaguePicking.ModeLiberation.AUTO_HEURE:
            if vague.company_id not in parametres:
                parametres[vague.company_id] = AchatsParametres.for_company(
                    vague.company)
            coupure = parametres[vague.company_id].heure_coupure_vagues
            declencher = bool(coupure) and heure_locale >= coupure
        elif vague.mode_liberation == VaguePicking.ModeLiberation.AUTO_SEUIL:
            seuil = vague.seuil_lignes or 0
            declencher = seuil > 0 and vague.lignes.count() >= seuil
        if not declencher:
            continue
        try:
            lancer_vague(vague)
        except ValueError:
            # Vague sans ligne : on la laisse en brouillon, sans faire échouer
            # tout le lot (le job doit rester idempotent et tolérant).
            continue
        liberees.append(vague.reference)
    return {'liberees': liberees, 'examinees': examinees}


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS13 — Comptage tournant ABC récurrent (cycle counting)
# ═══════════════════════════════════════════════════════════════════════════

# Fenêtre d'analyse de rotation : 12 mois glissants.
FENETRE_ROTATION_JOURS = 365


def assurer_plans_comptage_tournant(company):
    """Crée (idempotent) les trois plans A/B/C par défaut d'une société.

    A = 30 j, B = 90 j, C = 180 j — les fréquences RESTENT configurables
    ensuite ; cette fonction ne les écrase jamais.
    """
    from .models_wms import PlanComptageTournant

    plans = []
    for classe, frequence in PlanComptageTournant.FREQUENCES_DEFAUT.items():
        plan, _cree = PlanComptageTournant.objects.get_or_create(
            company=company, classe_abc=classe,
            defaults={'frequence_jours': frequence})
        plans.append(plan)
    return plans


def generer_comptages_tournants(*, company=None, aujourd_hui=None):
    """Génère les ``InventaireSession`` de comptage tournant DUES.

    Pour chaque plan actif dont l'échéance est atteinte, crée UNE session
    d'inventaire en brouillon contenant les produits de la classe concernée
    (quantité comptée pré-remplie à la quantité théorique : le magasinier n'a
    qu'à corriger les écarts), puis horodate le plan.

    IDEMPOTENTE : rejouée le même jour, elle ne recrée rien (l'échéance vient
    d'être repoussée). ``aujourd_hui`` (date) est FOURNI par l'appelant dans
    les tests — jamais l'horloge, sinon la suite bascule à minuit.

    Renvoie ``{'sessions': [references…], 'plans_dus': n}``.
    """
    import datetime

    from django.db import transaction
    from django.utils import timezone
    from core.numbering import create_with_reference
    from .models import InventaireSession, LigneInventaire, Produit
    from .models_wms import PlanComptageTournant
    from .selectors_wms import classes_abc_produits

    aujourd_hui = aujourd_hui or timezone.localdate()
    depuis = aujourd_hui - datetime.timedelta(days=FENETRE_ROTATION_JOURS)

    plans = PlanComptageTournant.objects.filter(actif=True).select_related(
        'company')
    if company is not None:
        plans = plans.filter(company=company)

    sessions, plans_dus = [], 0
    classes_par_company = {}
    for plan in plans:
        if not plan.est_du(aujourd_hui):
            continue
        plans_dus += 1
        if plan.company_id not in classes_par_company:
            classes_par_company[plan.company_id] = classes_abc_produits(
                plan.company, depuis=depuis, jusqu_a=aujourd_hui)
        classes = classes_par_company[plan.company_id]
        produit_ids = [pid for pid, classe in classes.items()
                       if classe == plan.classe_abc]
        if not produit_ids:
            # Aucun produit dans cette classe : on horodate quand même pour ne
            # pas réexaminer ce plan à chaque passage.
            plan.date_dernier_comptage = aujourd_hui
            plan.save(update_fields=['date_dernier_comptage'])
            continue

        produits = list(Produit.objects.filter(
            company=plan.company, id__in=produit_ids, is_archived=False))
        if not produits:
            plan.date_dernier_comptage = aujourd_hui
            plan.save(update_fields=['date_dernier_comptage'])
            continue

        with transaction.atomic():
            def _save(reference, plan=plan):
                return InventaireSession.objects.create(
                    company=plan.company, reference=reference,
                    motif=f'Comptage tournant — classe {plan.classe_abc} '
                          f'(tous les {plan.frequence_jours} jours)')

            session = create_with_reference(
                InventaireSession, 'INV', plan.company, _save)
            LigneInventaire.objects.bulk_create([
                LigneInventaire(
                    session=session, produit=produit,
                    quantite_theorique=produit.quantite_stock,
                    # Pré-rempli au théorique : valider sans rien toucher
                    # n'émet AUCUN ajustement (une session de comptage ne
                    # doit jamais bouger le stock toute seule).
                    quantite_comptee=produit.quantite_stock)
                for produit in produits
            ])
            plan.date_dernier_comptage = aujourd_hui
            plan.save(update_fields=['date_dernier_comptage'])
        sessions.append(session.reference)
    return {'sessions': sessions, 'plans_dus': plans_dus}


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS15 — Cross-dock (réception → expédition, sans passage en stock rangé)
# ═══════════════════════════════════════════════════════════════════════════

# Statuts de vague qui ATTENDENT encore de la marchandise : seule une vague
# non terminée peut justifier un cross-dock.
STATUTS_VAGUE_EN_ATTENTE = ('brouillon', 'lancee')


def _lignes_picking_en_attente(company, produit_id):
    """Lignes de vague NON servies attendant ce produit, vague la plus
    ancienne d'abord (LECTURE SEULE)."""
    from .models_wms import LignePicking

    return [
        ligne for ligne in (
            LignePicking.objects
            .filter(company=company, produit_id=produit_id,
                    vague__statut__in=STATUTS_VAGUE_EN_ATTENTE)
            .select_related('vague')
            .order_by('vague_id', 'ordre_parcours', 'id'))
        if ligne.reste_a_prelever > 0
    ]


def proposer_cross_dock(reception):
    """Vagues en attente qui MATCHENT les lignes d'une réception.

    Renvoie ``[{ligne_id, produit_id, produit_nom, quantite, deja_affectee,
    vagues: [{ligne_picking_id, vague_id, vague_reference,
    reste_a_prelever}]}]`` — une entrée par ligne reçue, ``vagues`` vide quand
    rien n'attend ce produit (la ligne suit alors le rangement normal,
    NTWMS2). LECTURE SEULE : cette fonction PROPOSE, elle n'écrit rien.
    """
    from .models_wms import AffectationCrossDock

    if reception is None:
        return []
    company = reception.company
    deja = set(
        AffectationCrossDock.objects
        .filter(company=company, reception=reception)
        .values_list('ligne_reception_id', flat=True))

    sorties = []
    for ligne in reception.lignes.select_related('produit').order_by('id'):
        vagues = []
        if ligne.produit_id:
            for lp in _lignes_picking_en_attente(company, ligne.produit_id):
                vagues.append({
                    'ligne_picking_id': lp.id,
                    'vague_id': lp.vague_id,
                    'vague_reference': lp.vague.reference,
                    'reste_a_prelever': lp.reste_a_prelever,
                })
        sorties.append({
            'ligne_id': ligne.id,
            'produit_id': ligne.produit_id,
            'produit_nom': getattr(ligne.produit, 'nom', '') or '',
            'quantite': ligne.quantite or 0,
            'deja_affectee': ligne.id in deja,
            'vagues': vagues,
        })
    return sorties


def reception_est_cross_dock(reception):
    """Vrai quand TOUTES les lignes d'une réception sont routées en cross-dock.

    C'est l'équivalent, du bon côté de la frontière d'apps, du drapeau
    « destiné au cross-dock » : aucune colonne n'est ajoutée à ``achats``, la
    vérité est portée par les affectations de ``stock``.
    """
    from .models_wms import AffectationCrossDock

    if reception is None:
        return False
    lignes = list(reception.lignes.values_list('id', flat=True))
    if not lignes:
        return False
    affectees = set(
        AffectationCrossDock.objects
        .filter(company=reception.company, ligne_reception_id__in=lignes)
        .values_list('ligne_reception_id', flat=True))
    return len(affectees) == len(lignes)


def affecter_reception_cross_dock(*, reception, user=None, lignes=None,
                                  unite=None):
    """Route les lignes reçues qui matchent une vague en attente vers un COLIS.

    ``lignes`` — ids de lignes de réception à router (défaut : toutes celles
    qui matchent). ``unite`` — colis existant à alimenter (défaut : un colis
    ``en_preparation`` créé pour l'occasion, rattaché à la vague matchée).

    Le put-away (NTWMS2) est explicitement SAUTÉ : aucun ``MouvementStock``
    vers un casier de stockage n'est posé ici, la marchandise ne transite
    jamais par un casier. L'entrée en stock reste celle, inchangée, de la
    confirmation de réception.

    Renvoie ``{unite_logistique, sscc, lignes_affectees, lignes_ignorees}``.
    Lève ``ValueError`` si aucune ligne ne matche ou si le colis est scellé.
    """
    from django.db import transaction

    from .models import Produit
    from .models_wms import AffectationCrossDock, LignePicking, VaguePicking

    if reception is None:
        raise ValueError('Réception introuvable.')
    company = reception.company
    filtre = {int(x) for x in (lignes or []) if str(x).isdigit()}
    propositions = [
        p for p in proposer_cross_dock(reception)
        if p['vagues'] and not p['deja_affectee']
        and (not filtre or p['ligne_id'] in filtre)
    ]
    if not propositions:
        raise ValueError(
            'Aucune ligne de cette réception ne correspond à une vague en '
            'attente.')
    if unite is not None and unite.est_figee:
        raise ValueError(
            'Cette unité logistique est scellée : son contenu est figé.')

    produits = {
        p.id: p for p in Produit.objects.filter(
            company=company,
            id__in=[p['produit_id'] for p in propositions])
    }
    affectees, ignorees = [], []
    colis = unite
    with transaction.atomic():
        for proposition in propositions:
            produit = produits.get(proposition['produit_id'])
            quantite = proposition['quantite'] or 0
            if produit is None or quantite <= 0:
                ignorees.append(proposition['ligne_id'])
                continue
            tete = proposition['vagues'][0]
            if colis is None:
                vague = VaguePicking.objects.filter(
                    id=tete['vague_id'], company=company).first()
                colis = creer_unite_logistique(
                    company=company, type_unite='colis', vague=vague)
            ligne_picking = LignePicking.objects.filter(
                id=tete['ligne_picking_id'], company=company).first()
            ajouter_ligne_unite_logistique(
                company=company, unite=colis, produit=produit,
                quantite=quantite, ligne_picking=ligne_picking)
            AffectationCrossDock.objects.create(
                company=company, reception=reception,
                ligne_reception_id=proposition['ligne_id'], produit=produit,
                quantite=quantite, unite_logistique=colis,
                ligne_picking=ligne_picking)
            affectees.append(proposition['ligne_id'])
    logger.info(
        'NTWMS15 cross-dock : réception %s → colis %s (%s ligne(s))',
        getattr(reception, 'reference', reception.pk),
        getattr(colis, 'sscc', None), len(affectees))
    return {
        'unite_logistique': colis.id if colis is not None else None,
        'sscc': colis.sscc if colis is not None else '',
        'lignes_affectees': affectees,
        'lignes_ignorees': ignorees,
        'reception_entierement_cross_dockee': reception_est_cross_dock(
            reception),
    }


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS17 — Rappel produit (recall) : impact immédiat stock + chantiers
# ═══════════════════════════════════════════════════════════════════════════

def impact_rappel(alerte):
    """Portée COMPLÈTE d'un rappel : ce qui reste en casier, ce qui est parti.

    Réutilise la traçabilité NTWMS16 (``tracabilite_produit``) lot par lot —
    aucun deuxième algorithme de traçabilité. Renvoie
    ``{produit, lots, stock_restant, casiers, chantiers, colis}`` ; les
    chantiers/colis sont dédupliqués. LECTURE SEULE.
    """
    from .models import LotEntrepot
    from .selectors_wms import localisation_casiers, tracabilite_produit

    if alerte is None:
        return {}
    company = alerte.company
    produit = alerte.produit
    if alerte.lot_id:
        numeros = [alerte.lot.numero_lot]
    else:
        numeros = list(
            LotEntrepot.objects
            .filter(company=company, produit=produit)
            .values_list('numero_lot', flat=True).distinct())

    lots, chantiers, colis = [], {}, {}
    stock_restant = 0
    for numero in numeros:
        chaine = tracabilite_produit(company, lot=numero)
        if chaine is None:
            continue
        restant = chaine['stock'].get('quantite_restante') or 0
        stock_restant += restant
        lots.append({
            'numero_lot': numero,
            'quantite_restante': restant,
            'fournisseurs': sorted({
                entree.get('fournisseur_nom') for entree in chaine['amont']
                if entree.get('fournisseur_nom')}),
        })
        for entree in chaine['aval']:
            if entree['type'] == 'picking' and entree.get('chantier_id'):
                chantiers[entree['chantier_id']] = {
                    'chantier_id': entree['chantier_id'],
                    'chantier_reference': entree.get('chantier_reference'),
                    'numero_lot': numero,
                }
            elif entree['type'] == 'colis':
                colis[entree['sscc']] = {
                    'sscc': entree['sscc'], 'statut': entree['statut'],
                    'quantite': entree['quantite'], 'numero_lot': numero,
                }

    return {
        'alerte': alerte.id,
        'produit': {'id': produit.id, 'nom': produit.nom,
                    'sku': produit.sku or ''},
        'lots': lots,
        'stock_restant': stock_restant,
        # Le stock ENCORE en rayon : les casiers qui portent le produit.
        'casiers': localisation_casiers(produit),
        'chantiers': list(chantiers.values()),
        'colis': list(colis.values()),
    }


def notifier_rappel(alerte, impact=None):
    """Prévient les responsables qu'un rappel est déclenché (BEST-EFFORT).

    Réutilise strictement ``notifications.services.notify_many`` — jamais un
    canal maison. Le type d'événement est un type EXISTANT du catalogue
    (``INCIDENT_CRITICAL`` : un rappel produit EST un incident critique) ;
    créer un type dédié appartiendrait à ``apps/notifications``, hors
    périmètre de cette app. Toute erreur est avalée et journalisée : une
    notification ne fait JAMAIS échouer la déclaration d'un rappel.
    """
    try:
        from django.contrib.auth import get_user_model
        from apps.notifications.models import EventType
        from apps.notifications.services import notify_many

        impact = impact or impact_rappel(alerte)
        destinataires = list(
            get_user_model().objects
            .filter(company=alerte.company, is_active=True,
                    role_legacy__in=['admin', 'responsable']))
        if not destinataires:
            return []
        return notify_many(
            destinataires, EventType.INCIDENT_CRITICAL,
            f'Rappel produit — {alerte.produit.nom}',
            body=(f"{len(impact.get('chantiers', []))} chantier(s) livré(s), "
                  f"{impact.get('stock_restant', 0)} unité(s) encore en "
                  f"stock. Motif : {alerte.motif}"),
            company=alerte.company)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('NTWMS17 notification de rappel échouée : %s', exc)
        return []


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS24 — Casse / freinte / rebut motivé (et sa valeur de perte)
# ═══════════════════════════════════════════════════════════════════════════

def declarer_mouvement_rebut(*, company, user, produit, quantite, motif,
                             bin_source=None, note=''):
    """Déclare une perte MOTIVÉE et chiffrée.

    Le mouvement de stock réel passe par le service de rebut EXISTANT
    (``rebuter_produit``, type ``REBUT``) : jamais un second chemin
    d'écriture, et la perte reste distincte d'un ajustement d'inventaire.
    La valeur est figée au coût moyen d'achat du moment (INTERNE).
    """
    from decimal import Decimal

    from django.db import transaction

    from .models_wms import MouvementRebut
    from .services import average_cost_with_source, rebuter_produit

    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité de rebut doit être positive.')
    if produit is None or produit.company_id != getattr(company, 'id', None):
        raise ValueError('Produit introuvable dans cette société.')
    if motif not in dict(MouvementRebut.Motif.choices):
        raise ValueError('Motif de rebut invalide.')

    cout, _source = average_cost_with_source(produit)
    valeur = (Decimal(str(cout or 0)) * Decimal(quantite)).quantize(
        Decimal('0.01'))
    with transaction.atomic():
        # `rebuter_produit` (XSTK10) pose le MouvementStock REBUT, applique le
        # garde de stock négatif et renvoie {mouvement, valeur_perdue}.
        resultat = rebuter_produit(
            company=company, produit=produit, quantite=quantite,
            motif=MouvementRebut.MOTIF_MOUVEMENT[motif], user=user)
        return MouvementRebut.objects.create(
            company=company, produit=produit, quantite=quantite, motif=motif,
            bin=bin_source, valeur_perte=valeur,
            mouvement=resultat['mouvement'],
            note=(note or '').strip(), declare_par=user)


def rapport_pertes_entrepot(company, *, debut=None, fin=None):
    """NTWMS24 — valeur totale de perte PAR MOTIF sur une période.

    Nom explicitement distinct de ``rapport_pertes`` (XSTK10, agrégation PAR
    PRODUIT des mouvements REBUT) : les deux coexistent, celui-ci agrège les
    DÉCLARATIONS motivées par motif. Distincte, par construction, des
    ajustements d'inventaire : seules les
    déclarations de rebut (``MouvementRebut``) sont comptées. ``debut``/``fin``
    sont des DATES fournies par l'appelant (bornes incluses). LECTURE SEULE.
    """
    from decimal import Decimal

    from django.db.models import Count, Sum

    from .models_wms import MouvementRebut

    qs = MouvementRebut.objects.filter(company=company)
    if debut:
        qs = qs.filter(created_at__date__gte=debut)
    if fin:
        qs = qs.filter(created_at__date__lte=fin)
    lignes = list(
        qs.values('motif')
        .annotate(nb=Count('id'), quantite=Sum('quantite'),
                  valeur=Sum('valeur_perte'))
        .order_by('-valeur'))
    total = sum((ligne['valeur'] or Decimal('0')) for ligne in lignes)
    libelles = dict(MouvementRebut.Motif.choices)
    return {
        'total_valeur': total,
        'total_quantite': sum((ligne['quantite'] or 0) for ligne in lignes),
        'par_motif': [{
            'motif': ligne['motif'],
            'libelle': libelles.get(ligne['motif'], ligne['motif']),
            'nb_declarations': ligne['nb'],
            'quantite': ligne['quantite'] or 0,
            'valeur': ligne['valeur'] or Decimal('0'),
        } for ligne in lignes],
    }


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS23 — Retours client (RMA) côté entrepôt
# ═══════════════════════════════════════════════════════════════════════════

def creer_retour_client(*, company, user=None, client, chantier=None,
                        ticket=None, motif='', lignes=None):
    """Ouvre un retour client (RMA) avec ses lignes.

    Référence ``RMA-YYYYMM-NNNN`` posée par ``core.numbering`` (jamais
    ``count()+1``), dans la MÊME transaction que les lignes : aucune
    référence vide ne peut être committée.
    """
    from django.db import transaction
    from core.numbering import create_with_reference

    from .models import Produit
    from .models_wms import LigneRetourClient, RetourClient

    if client is None:
        raise ValueError('Client introuvable dans cette société.')
    lignes = list(lignes or [])
    if not lignes:
        raise ValueError('Un retour client doit contenir au moins une ligne.')
    produits = {
        p.id: p for p in Produit.objects.filter(
            company=company,
            id__in=[ligne.get('produit') for ligne in lignes])
    }

    preparees = []
    for ligne in lignes:
        produit = produits.get(ligne.get('produit'))
        try:
            quantite = int(ligne.get('quantite') or 0)
        except (TypeError, ValueError):
            quantite = 0
        if produit is None or quantite <= 0:
            continue
        preparees.append((produit, quantite, ligne.get('etat_constate'),
                          ligne.get('bin')))
    if not preparees:
        raise ValueError('Aucune ligne de retour valide.')

    with transaction.atomic():
        def _save(reference):
            return RetourClient.objects.create(
                company=company, reference=reference, client=client,
                chantier=chantier, ticket=ticket,
                motif=(motif or '').strip(), cree_par=user)

        retour = create_with_reference(RetourClient, 'RMA', company, _save)
        etats = {c for c, _ in LigneRetourClient.EtatConstate.choices}
        LigneRetourClient.objects.bulk_create([
            LigneRetourClient(
                company=company, retour=retour, produit=produit,
                quantite=quantite,
                etat_constate=(
                    etat if etat in etats
                    else LigneRetourClient.EtatConstate.REVENDABLE),
                bin_id=bin_id)
            for produit, quantite, etat, bin_id in preparees
        ])
    return retour


def _reintegrer_ligne_retour(ligne, user=None):
    """Pose l'ENTRÉE de stock d'une ligne REVENDABLE (idempotent)."""
    from .models import MouvementStock, Produit
    from .models_wms import LigneRetourClient
    from .services import record_stock_movement

    if ligne.stock_mouvemente:
        return None
    if ligne.etat_constate != LigneRetourClient.EtatConstate.REVENDABLE:
        return None
    produit = Produit.objects.select_for_update().get(id=ligne.produit_id)
    avant = produit.quantite_stock
    mouvement = record_stock_movement(
        company=ligne.company, produit=produit,
        type_mouvement=MouvementStock.TypeMouvement.ENTREE,
        quantite=ligne.quantite, quantite_avant=avant,
        quantite_apres=avant + ligne.quantite,
        reference=ligne.retour.reference,
        note=f'Retour client {ligne.retour.reference} (revendable)',
        created_by=user, bin_destination=ligne.bin)
    ligne.stock_mouvemente = True
    ligne.save(update_fields=['stock_mouvemente'])
    return mouvement


def _sortir_ligne_retour(ligne, user=None):
    """Ressort du stock une ligne entrée à tort puis déclassée (idempotent)."""
    from .models import MouvementStock, Produit
    from .services import record_stock_movement

    if not ligne.stock_mouvemente:
        return None
    produit = Produit.objects.select_for_update().get(id=ligne.produit_id)
    avant = produit.quantite_stock
    quantite = min(ligne.quantite, avant) if avant > 0 else 0
    mouvement = record_stock_movement(
        company=ligne.company, produit=produit,
        type_mouvement=MouvementStock.TypeMouvement.REBUT,
        quantite=quantite, quantite_avant=avant,
        quantite_apres=avant - quantite,
        reference=ligne.retour.reference,
        note=f'Retour client {ligne.retour.reference} — déclassé après '
             f'inspection',
        created_by=user)
    MouvementStock.objects.filter(id=mouvement.id).update(motif_rebut='autre')
    ligne.stock_mouvemente = False
    ligne.save(update_fields=['stock_mouvemente'])
    return mouvement


def receptionner_retour_client(*, retour, user=None):
    """Réceptionne physiquement le retour.

    Chaque ligne REVENDABLE réintègre le stock vendable ; une ligne
    A_REPARER ou REBUT n'incrémente RIEN. Idempotent : un retour déjà
    réceptionné ne re-crée aucun mouvement.
    """
    from django.db import transaction
    from django.utils import timezone

    from .models_wms import RetourClient

    if retour.statut not in (RetourClient.Statut.DEMANDE,
                             RetourClient.Statut.EN_TRANSIT):
        raise ValueError(
            'Seul un retour demandé ou en transit peut être réceptionné.')
    with transaction.atomic():
        for ligne in retour.lignes.select_related('retour').all():
            _reintegrer_ligne_retour(ligne, user=user)
        retour.statut = RetourClient.Statut.RECEPTIONNE
        retour.date_reception = timezone.now()
        retour.save(update_fields=['statut', 'date_reception'])
    return retour


def inspecter_retour_client(*, retour, lignes=None, user=None):
    """Acte le contrôle qualité : état constaté + casier par ligne.

    ``lignes`` — ``[{ligne, etat_constate, bin, note}]``. Une ligne qui
    DEVIENT revendable entre alors en stock ; une ligne déjà entrée qui
    devient A_REPARER/REBUT en ressort — le stock vendable ne contient jamais
    un rebut.
    """
    from django.db import transaction
    from django.utils import timezone

    from .models_wms import LigneRetourClient, RetourClient

    if retour.statut not in (RetourClient.Statut.RECEPTIONNE,
                             RetourClient.Statut.INSPECTE):
        raise ValueError(
            'Le retour doit être réceptionné avant d\'être inspecté.')
    etats = {c for c, _ in LigneRetourClient.EtatConstate.choices}
    par_id = {ligne.id: ligne
              for ligne in retour.lignes.select_related('retour').all()}
    with transaction.atomic():
        for entree in list(lignes or []):
            ligne = par_id.get(_entier_ou_none(entree.get('ligne')))
            if ligne is None:
                continue
            etat = entree.get('etat_constate')
            if etat not in etats:
                raise ValueError('État constaté invalide.')
            champs = ['etat_constate']
            ligne.etat_constate = etat
            if 'bin' in entree:
                ligne.bin_id = _entier_ou_none(entree.get('bin'))
                champs.append('bin')
            if entree.get('note'):
                ligne.note = entree['note']
                champs.append('note')
            ligne.save(update_fields=champs)
            if etat == LigneRetourClient.EtatConstate.REVENDABLE:
                _reintegrer_ligne_retour(ligne, user=user)
            else:
                _sortir_ligne_retour(ligne, user=user)
        retour.statut = RetourClient.Statut.INSPECTE
        retour.date_inspection = timezone.now()
        retour.save(update_fields=['statut', 'date_inspection'])
    return retour


def _entier_ou_none(valeur):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS21 — Demande de transfert avec workflow d'approbation
# ═══════════════════════════════════════════════════════════════════════════

def seuil_approbation_transfert(company):
    """Seuil de valeur (MAD) au-delà duquel un transfert exige une approbation.

    0 (défaut de toutes les sociétés) = garde DÉSACTIVÉE : le transfert direct
    historique reste strictement inchangé.
    """
    from decimal import Decimal
    from .models import AchatsParametres

    if company is None:
        return Decimal('0')
    parametres = AchatsParametres.for_company(company)
    return Decimal(parametres.seuil_approbation_transfert or 0)


def valeur_transfert(produit, quantite):
    """Valeur INTERNE d'un mouvement (quantité × prix d'achat). Jamais
    client-facing — elle ne sert qu'au seuil d'approbation."""
    from decimal import Decimal

    if produit is None:
        return Decimal('0')
    prix = Decimal(str(produit.prix_achat or 0))
    return (prix * Decimal(int(quantite or 0))).quantize(Decimal('0.01'))


def transfert_exige_approbation(company, produit, quantite):
    """Vrai si CE transfert dépasse le seuil configuré par la société."""
    seuil = seuil_approbation_transfert(company)
    if seuil <= 0:
        return False
    return valeur_transfert(produit, quantite) > seuil


def creer_demande_transfert(*, company, user, produit, quantite,
                            emplacement_source, emplacement_destination,
                            motif=''):
    """Ouvre une demande de transfert (statut DEMANDÉ, valeur figée)."""
    from .models_wms import DemandeTransfert

    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité doit être positive.')
    if produit is None or produit.company_id != getattr(company, 'id', None):
        raise ValueError('Produit introuvable dans cette société.')
    if emplacement_source is None or emplacement_destination is None:
        raise ValueError('Emplacement introuvable dans cette société.')
    if emplacement_source.id == emplacement_destination.id:
        raise ValueError(
            'La source et la destination doivent être différentes.')

    return DemandeTransfert.objects.create(
        company=company, produit=produit, quantite=quantite,
        emplacement_source=emplacement_source,
        emplacement_destination=emplacement_destination,
        motif=(motif or '').strip(), demande_par=user,
        valeur_estimee=valeur_transfert(produit, quantite))


def decider_demande_transfert(*, demande, user, approuver=True):
    """Approuve ou rejette une demande. Seule une demande DEMANDÉE est
    décidable (une demande déjà exécutée n'est jamais rétrogradée)."""
    from django.utils import timezone
    from .models_wms import DemandeTransfert

    if demande.statut != DemandeTransfert.Statut.DEMANDE:
        raise ValueError(
            'Seule une demande en attente peut être approuvée ou rejetée.')
    demande.statut = (DemandeTransfert.Statut.APPROUVE if approuver
                      else DemandeTransfert.Statut.REJETE)
    demande.approuve_par = user
    demande.date_decision = timezone.now()
    demande.save(update_fields=['statut', 'approuve_par', 'date_decision'])
    return demande


def executer_demande_transfert(*, demande, user=None):
    """Crée le ``TransfertStock`` RÉEL d'une demande APPROUVÉE.

    Réutilise le service de transfert existant (jamais un second chemin de
    mouvement de stock) en lui signalant que l'approbation est acquise.
    """
    from django.db import transaction
    from .models_wms import DemandeTransfert
    from .services import transfer_stock

    if demande.statut != DemandeTransfert.Statut.APPROUVE:
        raise ValueError(
            'Seule une demande approuvée peut être exécutée.')
    with transaction.atomic():
        transfert = transfer_stock(
            company=demande.company, user=user or demande.approuve_par,
            produit_id=demande.produit_id,
            source_id=demande.emplacement_source_id,
            destination_id=demande.emplacement_destination_id,
            quantite=demande.quantite, note=demande.motif,
            demande_approuvee=True)
        demande.statut = DemandeTransfert.Statut.EXECUTE
        demande.transfert = transfert
        demande.save(update_fields=['statut', 'transfert'])
    return demande


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS20 — Portail 3PL (lecture seule, tokenisée, scope = UN dépositaire)
# ═══════════════════════════════════════════════════════════════════════════

def resoudre_token_portail_tiers(token):
    """Jeton de portail 3PL VALIDE (non révoqué, non expiré), ou ``None``.

    Marque l'usage (``last_used_at``) — jamais autre chose : ce chemin est
    PUBLIC, il n'écrit aucune donnée métier.
    """
    from django.utils import timezone
    from .models_wms import PortailTiersToken

    token = (token or '').strip()
    if not token:
        return None
    obj = (PortailTiersToken.objects
           .select_related('company')
           .filter(token=token).first())
    if obj is None or not obj.est_valide:
        return None
    PortailTiersToken.objects.filter(id=obj.id).update(
        last_used_at=timezone.now())
    return obj


def solde_portail_tiers(token_obj):
    """Solde du stock DU SEUL dépositaire porteur du jeton.

    Ne remonte QUE les ``StockEmplacement`` posés sur un emplacement
    ``DE_TIERS`` de la société du jeton dont le ``tiers_nom`` correspond
    exactement. Aucun prix, aucune marge, aucun autre dépositaire, aucun
    stock interne : un solde de dépôt-vente, rien d'autre.
    """
    from .models import EmplacementStock, StockEmplacement

    if token_obj is None:
        return None
    lignes = (StockEmplacement.objects
              .filter(company=token_obj.company,
                      emplacement__type_proprietaire=(
                          EmplacementStock.TypeProprietaire.DE_TIERS),
                      emplacement__tiers_nom=token_obj.tiers_nom)
              .select_related('produit', 'emplacement')
              .order_by('produit__nom'))
    return {
        'tiers_nom': token_obj.tiers_nom,
        'lignes': [{
            'produit': ligne.produit.nom,
            'sku': ligne.produit.sku or '',
            'emplacement': ligne.emplacement.nom,
            'quantite': ligne.quantite,
        } for ligne in lignes],
        'total_unites': sum(ligne.quantite or 0 for ligne in lignes),
    }


def cloturer_alerte_rappel(alerte):
    """Clôt un rappel (idempotent : un rappel déjà clos n'est pas rouvert)."""
    from django.utils import timezone
    from .models_wms import AlerteRappel

    if alerte.statut == AlerteRappel.Statut.CLOS:
        return alerte
    alerte.statut = AlerteRappel.Statut.CLOS
    alerte.date_cloture = timezone.now()
    alerte.save(update_fields=['statut', 'date_cloture'])
    return alerte
