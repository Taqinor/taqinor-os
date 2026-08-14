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
