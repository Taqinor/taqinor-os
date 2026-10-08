"""Facturation — les créateurs de facture et ce qui les entoure.

Les SIX chemins de création d'une facture (contrat, régie, acompte/situation,
classique, ticket SAV, intervention), la réservation de stock qui les précède,
les frais refacturés, le recalcul des totaux, le calcul d'échéance et la liste
des facturables d'un devis.

QJR69 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.
"""
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger("apps.ventes.services")


class StockInsuffisantError(Exception):
    """Levée quand une réservation de stock dépasserait le disponible (U9)."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class EmissionRefusee(Exception):
    """AUD101 — l'émission d'une facture est refusée (message FR, prêt 400).

    Porte ``motif`` (le message français) pour que les vues le renvoient tel
    quel dans un 400 sans jamais reformuler la règle métier."""

    def __init__(self, motif, champ=None):
        super().__init__(motif)
        self.motif = motif
        # CIQ217 — le champ fautif (p. ex. ``client.ice``), pour l'afficher
        # sous le champ ; None pour les refus qui ne visent aucun champ.
        self.champ = champ


MOTIF_ICE_MANQUANT = (
    "ICE du client manquant (client.ice) : une facture à un client "
    "entreprise ne peut pas être émise sans son ICE. Renseignez l'ICE sur la "
    "fiche client — la facture reste en brouillon.")


def verifier_ice_client_entreprise(facture):
    """CIQ217 (D-CIQ-11) — refuse l'émission d'une facture dont le client
    est une ENTREPRISE sans ICE. Indépendant de l'interrupteur de
    transmission DGI (qui reste éteint) ; un particulier n'est pas concerné ;
    le DEVIS n'est jamais bloqué (seule l'émission de la facture l'est)."""
    client = facture.client if facture.client_id else None
    if client is None:
        return
    if getattr(client, 'type_client', None) != 'entreprise':
        return
    if (getattr(client, 'ice', '') or '').strip():
        return
    raise EmissionRefusee(MOTIF_ICE_MANQUANT, champ='client.ice')


def emettre_facture(facture, *, user=None, source='', exiger_lignes=False,
                    verifier_credit=True):
    """AUD101 — LE SERVICE UNIQUE D'ÉMISSION d'une ``ventes.Facture``.

    AUCUN autre site du domaine ventes ne doit poser ``Facture.Statut.EMISE``
    (test de parité : ``apps/ventes/tests/test_aud101_emission_unique.py``).
    Avant ce service, CINQ chemins basculaient une facture en ÉMISE en silence
    — le bulk ``action=emettre``, la facturation de pénalités, la tranche
    d'échéancier (le chemin acompte→matériel→solde du parcours solaire), la
    facture « classique » consommée par POS/immobilier et la consolidation
    multi-devis. Aucun n'appelait le blocage crédit, aucun n'émettait
    ``facture_emise``.

    Ce que le service fait, dans cet ordre (les REFUS d'abord, pour qu'un
    appelant qui l'enveloppe dans ``transaction.atomic()`` n'écrive rien) :

      1. refuse une facture ANNULÉE ou déjà PAYÉE ;
      2. ``exiger_lignes`` (chemin écran) : refuse une facture vide ;
      3. blocage crédit dur XFAC28 (``verifier_credit_hold``) — EXEMPTION
         explicite via ``verifier_credit=False`` pour la vente comptoir
         intégralement réglée à l'acte : le hold protège l'encours, il n'a
         aucune raison de refuser du cash immédiat ;
      4. workflow de revue XFAC18 (valideur ≠ créateur, anomalies) ;
      5. dérivation de l'échéance depuis les conditions client (XFAC23), sans
         jamais écraser une échéance saisie ;
      6. pose ``EMISE`` + ``save()`` ;
      7. émet ``facture_emise`` EXACTEMENT une fois.

    RÈGLE #4 : ce service ne touche QUE le statut de la Facture (et le
    ``revue_statut``/``date_echeance`` qui l'accompagnent) ; il ne rend aucun
    document et ne connaît pas le moteur de devis.

    Renvoie la liste des anomalies de revue (vide hors XFAC18). Lève
    ``EmissionRefusee`` (message FR) ou ``CreditHoldError``.
    """
    from apps.ventes.models import Facture

    statut = facture.statut
    if statut == Facture.Statut.ANNULEE:
        raise EmissionRefusee("Une facture annulée ne peut pas être émise.")
    if statut == Facture.Statut.PAYEE:
        raise EmissionRefusee("Une facture payée ne peut pas être émise.")
    if exiger_lignes and not facture.lignes.exists() and not facture.libelle:
        raise EmissionRefusee(
            'La facture doit contenir au moins une ligne.')
    verifier_ice_client_entreprise(facture)

    if verifier_credit and facture.client_id:
        from apps.ventes.domain.recouvrement import verifier_credit_hold
        verifier_credit_hold(
            facture.client, user=user,
            contexte=(source or 'émission de facture'))

    anomalies = []
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.get(company=facture.company)
    if getattr(profile, 'revue_factures_active', False) and \
            facture.revue_statut == Facture.RevueStatut.A_VALIDER:
        if user is not None and facture.created_by_id == getattr(
                user, 'id', None):
            raise EmissionRefusee(
                'Cette facture doit être validée par un responsable/admin '
                'différent du créateur.')
        from apps.ventes.domain.recouvrement import anomalies_emission_facture
        anomalies = anomalies_emission_facture(facture)
        facture.revue_statut = Facture.RevueStatut.VALIDEE

    if not facture.date_echeance:
        derivee = calculer_date_echeance(
            client=facture.client, date_emission=facture.date_emission)
        if derivee is not None:
            facture.date_echeance = derivee

    facture.statut = Facture.Statut.EMISE
    facture.save()

    from core.events import facture_emise
    facture_emise.send(
        sender=Facture, instance=facture, company=facture.company)
    logger.info(
        'AUD101: facture %s émise (source=%s, company=%s)',
        facture.reference, source or 'inconnue',
        getattr(facture.company, 'id', '?'))
    return anomalies


def decompter_stock_lignes(*, lignes, company, user, reference, note,
                           multiplicateur=1, manquants=None, sorties=None):
    """AUD116 — LE DÉCOMPTEUR UNIQUE de stock des lignes d'un devis.

    Il existait DEUX décompteurs pour le MÊME panier, et ils ne faisaient pas
    le même travail : ``reserver_stock_devis_facture`` (facturation directe)
    sautait les lignes sans produit et les lignes hors ``compte_dans_totaux``,
    alors que ``bon_commande.marquer_livre`` itérait ``bc.devis.lignes`` NU et
    appelait ``verrouiller_produit(ligne.produit_id)`` sans jamais tester
    ``produit is None`` — alors que ``LigneDevis.produit`` est nullable depuis
    XSAL14. Pire : ni l'un ni l'autre n'appliquait ``option_lines``, si bien
    qu'un devis accepté « sans batterie » livrait les DEUX kits et le stock
    physique divergeait du stock ERP du montant d'une batterie.

    Les appelants passent désormais le MÊME panier que la facture et que la
    nomenclature du chantier (``option_lines``), et cette fonction est la
    seule à savoir décompter. Elle lève ``StockInsuffisantError`` (message FR
    identique des deux côtés) ; à appeler dans la transaction de l'appelant.
    Renvoie ``True`` si au moins un mouvement a été posé.

    ERR-QAC-MULTIVILLA-MATERIEL-XN — ``multiplicateur`` = N du devis « ×N
    villas identiques » (``multivilla.nombre_proprietes``) : les lignes
    décrivent UNE villa mais le projet (facturé ×N) en consomme N fois le
    matériel. Défaut 1 = comportement historique strictement inchangé.

    ``manquants`` (liste, facultatif) — mode NON BLOQUANT (facturation,
    fondateur 05/10/2026) : au lieu de lever ``StockInsuffisantError``, la
    sortie est posée quand même (le stock ERP passe sous zéro) et chaque
    manque est ajouté à la liste ``(nom, disponible, requis)`` pour être
    signalé. ``None`` = garde bloquante historique (livraison BC).

    ``sorties`` (dict, facultatif) — ASTK135 : reçoit ``{produit_id: qte}``
    des quantités réellement sorties, pour que l'appelant SOLDE la
    réservation du chantier (``solder_reservations_chantier_vente``).
    """
    from decimal import Decimal, ROUND_HALF_UP
    from apps.stock.services import (
        mouvement_type_sortie, record_stock_movement,
        verrouiller_produit, check_negative_stock_guard,
    )

    moved = False
    for ligne in lignes:
        # XSAL5/XSAL14 — ne décompte QUE les lignes produit effectives : ni
        # option non activée, ni ligne de section/note (sans produit).
        if not ligne.compte_dans_totaux or ligne.produit_id is None:
            continue
        # AUD216 — VERROU de ligne produit AVANT la lecture de
        # `quantite_stock` : `refresh_from_db()` relisait sans verrouiller, et
        # la garde « stock insuffisant » ci-dessous décidait donc sur une
        # valeur qu'une transaction concurrente pouvait déjà avoir consommée
        # (survente). Verrou pris par le thin service stock — jamais d'import
        # des models stock ici.
        produit = verrouiller_produit(ligne.produit_id)
        if produit is None or ligne.quantite is None:
            continue
        # ERR15 — ne PAS tronquer la quantité décimale (int() perdait la partie
        # fractionnaire : 3,5 → 3, dérive silencieuse du stock sur les lignes
        # au mètre/câble). Le registre de stock est en entiers : on arrondit au
        # plus proche (HALF_UP) au lieu de tronquer, donc 3,5 → 4.
        qte = int((Decimal(ligne.quantite) * int(multiplicateur or 1)).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP))
        if qte <= 0:
            continue
        qte_avant = produit.quantite_stock
        qte_apres = qte_avant - qte
        # AUD228 — route par la garde paramétrable (société) plutôt qu'un
        # blocage en dur : `stock_negatif_autorise` (AchatsParametres) est
        # respecté ici. Message INCHANGÉ quand le réglage refuse (défaut).
        try:
            check_negative_stock_guard(company, qte_avant, qte_apres)
        except ValueError:
            if manquants is not None:
                manquants.append((produit.nom, qte_avant, qte))
            else:
                raise StockInsuffisantError(
                    f'Stock insuffisant pour « {produit.nom} » '
                    f'(disponible : {qte_avant}, requis : {qte}).')
        record_stock_movement(
            company=company,
            produit=produit,
            type_mouvement=mouvement_type_sortie(),
            quantite=qte,
            quantite_avant=qte_avant,
            quantite_apres=qte_apres,
            reference=reference,
            note=note,
            created_by=user,
        )
        if sorties is not None:
            sorties[produit.id] = sorties.get(produit.id, 0) + qte
        moved = True
    return moved


def solder_reservations_chantier_vente(*, devis, company, sorties, reference,
                                       user=None):
    """ASTK135 (C-ASTK-028) — « une vente = une sortie ».

    Le matériel d'une vente SORTI par la facture directe ou par la livraison
    d'un BC (toggle OFF) SOLDE la réservation N14 du chantier du devis, sinon
    « Installé » le sortait une seconde fois. Service UNIQUE du propriétaire
    chantiers (ASTK120), appelé via ``apps.installations`` (doctrine
    cross-app, imports fonction-locaux) DANS la transaction de la sortie ;
    idempotent par (référence, produit). No-op sans chantier ou sans sortie.
    """
    if devis is None or not sorties:
        return 0
    from apps.installations.selectors import installation_for_devis
    from apps.installations.services import solder_reservations_vente
    installation = installation_for_devis(devis, company=company)
    if installation is None:
        return 0
    return solder_reservations_vente(
        installation, sorties, reference, user=user)


def reserver_stock_devis_facture(*, devis, user, company):
    """U9 — réserve/consomme le stock matériel d'un devis facturé EN DIRECT.

    Le chemin bon-commande (``bon_commande.marquer_livre``) décrémente déjà le
    stock à la livraison. Mais un devis accepté puis facturé directement via
    l'échéancier (``generer-facture``) court-circuite le bon de commande et ne
    réservait donc AUCUN stock — d'où une survente possible entre devis. Cette
    fonction reproduit EXACTEMENT la réservation de la livraison BC (mêmes
    lignes du devis, même arrondi HALF_UP du décimal vers l'entier du registre,
    même garde de stock insuffisant), mais branchée sur la première facture
    d'échéancier.

    Garde anti-double-comptage : on ne réserve qu'UNE fois par devis. On ne
    fait RIEN si
      * un mouvement SORTIE référence déjà ce devis (réservation déjà posée par
        une tranche antérieure de l'échéancier), ou
      * un bon de commande de ce devis a déjà été livré (stock déjà consommé par
        le chemin BC).
    Écriture du mouvement déléguée au service stock (jamais d'import direct des
    models stock). À appeler dans la transaction de l'appelant.

    Lève ``StockInsuffisantError`` si une ligne dépasse le disponible (la
    transaction de l'appelant est alors annulée, comme côté BC).
    """
    from apps.stock.services import sortie_exists_for_reference
    from apps.ventes.models import BonCommande
    from apps.ventes.utils.options import option_lines

    reference = devis.reference

    # Déjà réservé pour ce devis (tranche antérieure de l'échéancier) → no-op.
    if sortie_exists_for_reference(company, reference):
        return False

    # Un BC livré a déjà consommé le stock de ce devis → ne pas re-décompter.
    if BonCommande.objects.filter(
            devis=devis, statut=BonCommande.Statut.LIVRE).exists():
        return False

    # AUD116 — MÊME PANIER que la facture (`option_lines`) et que la
    # nomenclature du chantier, MÊME décompteur que la livraison BC.
    # ERR-QAC-MULTIVILLA-MATERIEL-XN — un devis ×N villas facturé ×N consomme
    # le matériel de N villas (N=1 inchangé).
    from apps.ventes.multivilla import nombre_proprietes
    # Fondateur 05/10/2026 — une facture n'est JAMAIS bloquée par le compteur
    # de stock ERP : le matériel est souvent déjà posé chez le client quand on
    # facture. La sortie est posée quand même (stock ERP sous zéro) et le
    # manque est noté sur le devis pour recompter le stock.
    manquants = []
    sorties = {}
    moved = decompter_stock_lignes(
        lignes=option_lines(devis),
        company=company,
        user=user,
        reference=reference,
        note=f'Facturation directe — devis {reference}',
        multiplicateur=nombre_proprietes(devis),
        manquants=manquants,
        sorties=sorties,
    )
    # ASTK135 — la sortie de la vente solde la réservation du chantier (même
    # transaction : un échec de la sortie annule aussi le solde).
    solder_reservations_chantier_vente(
        devis=devis, company=company, sorties=sorties, reference=reference,
        user=user)
    if manquants:
        from apps.ventes import activity
        detail = ' ; '.join(
            f'{nom} (stock ERP {dispo}, facturé {requis})'
            for nom, dispo, requis in manquants)
        activity.log_devis_note(
            devis, user,
            'Facturé malgré un stock ERP insuffisant — stock à recompter : '
            f'{detail}.')
    return moved


def entete_facture_depuis_devis(devis, *, ttc=None):
    """AUD113 — champs d'EN-TÊTE qu'une facture reprend de son devis à la
    création (``Facture.objects.create(**entete)``).

    Le taux de TÊTE est le REPLI des lignes sans taux, et les deux chaînes de
    repli pointent vers des objets DIFFÉRENTS : ``LigneDevis.taux_tva_effectif``
    retombe sur ``devis.taux_tva``, ``LigneFacture.taux_tva_effectif`` sur
    ``facture.taux_tva``. Sans ce transport, un devis à 10 % dont les lignes
    portent un taux NULL était facturé au défaut 20 %.

    ATOT4 (C-ATOT-002) — l'en-tête porte AUSSI, quelle que soit la porte
    (tranche, BC, complète, consolidée) :
      * ``reference_commande_client`` du devis (CIQ216) ;
      * la retenue de garantie demandée sur le devis (CIQ214) : taux × ``ttc``
        de CETTE facture (``ttc`` absent ⇒ TTC de l'option effective du
        devis, celui d'une facture complète/BC), calculée par LE geste
        partagé ``echeancier.retenue_de_tranche`` → ``retenue_garantie_mad``
        + la phrase AUD180 dans ``conditions_paiement``. Sans retenue : clés
        absentes (facture d'hier)."""
    entete = {}
    if devis is None:
        return entete
    if devis.taux_tva is not None:
        entete['taux_tva'] = devis.taux_tva
    entete['reference_commande_client'] = (
        getattr(devis, 'reference_commande_client', '') or '')
    from apps.ventes.utils.echeancier import retenue_de_tranche
    if ttc is None and isinstance(getattr(devis, 'retenue_garantie', None),
                                  dict):
        from apps.ventes.utils.options import option_totaux
        ttc = option_totaux(devis)['ttc']
    retenue = retenue_de_tranche(devis, ttc) if ttc is not None else None
    if retenue is not None:
        entete['retenue_garantie_mad'] = retenue['montant']
        entete['conditions_paiement'] = retenue['phrase']
    return entete


def copier_devis_sur_facture(facture, devis):
    """Recopie sur ``facture`` (déjà créée) le PANIER du devis : remise globale,
    palier d'arrondi et lignes de l'option retenue — LE geste partagé par la
    facture de bon de commande (``bon_commande.creer_facture``) et la facture
    complète d'un devis accepté (``facturer_devis_complet``).

    Extrait tel quel de ``views/bon_commande.creer_facture`` :

    * ERR16 — n'inclure QUE les lignes de l'option retenue à l'acceptation
      (« Sans batterie » / « Avec batterie »), comme l'échéancier. Sans vraie
      deuxième option, ``option_lines`` renvoie TOUTES les lignes ;
    * QX1 — la remise GLOBALE du devis est PERSISTÉE sur
      ``Facture.remise_globale`` (``Facture.total_*`` la lit via la même chaîne
      canonique que le devis) ;
    * ERR-QAC-MULTIVILLA-TOTAL-XN — un devis « ×N villas identiques » se
      facture au total ×N : chaque quantité est reprise ×N (N=1 inchangé) ;
    * ARRONDI-100 — la facture reprend le palier du devis signé (jamais plus
      que lui), appliqué par villa (``arrondi_unites``).
    """
    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    from apps.ventes.models import LigneFacture
    from apps.ventes.selectors import nombre_proprietes

    g = Decimal(str(devis.remise_globale or 0))
    if g:
        facture.remise_globale = g
        facture.save(update_fields=['remise_globale'])
    n_prop = nombre_proprietes(devis)
    facture.arrondi_pas = int(PAS_ARRONDI_DEVIS)
    facture.arrondi_unites = n_prop
    facture.save(update_fields=['arrondi_pas', 'arrondi_unites'])
    for champs in lignes_facture_du_devis(devis):
        LigneFacture.objects.create(facture=facture, **champs)
    return facture


def lignes_facture_du_devis(devis, *, taux_effectif=False):
    """LE PANIER d'un devis tel qu'une facture le recopie (liste de champs
    ``LigneFacture``) : lignes de l'option effective (``option_lines`` —
    lignes produit COMPTÉES seulement : ni section/note, ni option non
    activée), quantité ×N villas, prix, remise de ligne et taux de la ligne.

    Partagé par ``copier_devis_sur_facture`` (BC, facture complète) et par la
    facture consolidée (ATOT3 : sa boucle ``d.lignes.all()`` recopiait les
    sections — 500 —, les options non activées et les deux options).
    ``taux_effectif=True`` reporte ``taux_tva_effectif`` (taux du devis pour
    une ligne sans taux) : obligatoire quand le repli de la facture n'est pas
    le taux du devis (consolidée de plusieurs devis)."""
    from apps.ventes.selectors import nombre_proprietes
    from apps.ventes.utils.options import option_lines

    n_prop = nombre_proprietes(devis)
    return [{
        'produit': ligne.produit,
        'designation': ligne.designation,
        'quantite': ligne.quantite * n_prop,
        'prix_unitaire': ligne.prix_unitaire,
        'remise': ligne.remise,
        # Reporte le taux TVA de la ligne de devis (10/20), pour que la
        # facture reproduise fidèlement la TVA.
        'taux_tva': (ligne.taux_tva_effectif if taux_effectif
                     else ligne.taux_tva),
    } for ligne in option_lines(devis)]


def ventiler_document_depuis_facture(document, facture, *, partiel=False,
                                     lignes_saisies=None):
    """ATOT6 (C-ATOT-004) — un avoir / une note de débit d'une facture
    VENTILÉE (tranche à taux mixtes, CIQ215) porte autant de paniers TVA que
    sa facture, au prorata exact au centime (``ventilation_document_fige``).

    * document TOTAL (lignes de la facture recopiées, ou montants figés) :
      la ventilation de la facture, à l'identique ;
    * document PARTIEL dont les lignes saisies ne déclarent AUCUN taux (elles
      héritaient du « taux mélangé » de tête, qui n'existe pas) : son TTC est
      réparti au prorata des paniers de la facture et ses montants FIGÉS ;
      une ligne qui déclare son taux garde la chaîne de ses lignes.

    Facture non ventilée (mono-taux, à lignes) : no-op, document d'hier.
    Renvoie True si une ventilation a été posée."""
    from apps.facturation.totaux import ventilation_document_fige

    ventilation = getattr(facture, 'ventilation_tva', None)
    if not ventilation or len(ventilation) < 2:
        return False
    if partiel and any(li.get('taux_tva') is not None
                       for li in (lignes_saisies or [])):
        return False
    if partiel:
        ttc = Decimal(str(document.total_ttc))
        vent = ventilation_document_fige(ventilation, ttc)
    else:
        ttc = Decimal(str(facture.total_ttc))
        vent = ventilation_document_fige(
            ventilation, ttc, ht=Decimal(str(facture.total_ht)),
            tva=Decimal(str(facture.total_tva)))
    if not vent:
        return False
    ht = sum((Decimal(b['base_ht']) for b in vent), Decimal('0'))
    tva = sum((Decimal(b['montant']) for b in vent), Decimal('0'))
    document.montant_ht = ht
    document.montant_tva = tva
    document.montant_ttc = ht + tva
    document.ventilation_tva = vent
    document.save(update_fields=[
        'montant_ht', 'montant_tva', 'montant_ttc', 'ventilation_tva'])
    return True


class FacturationRefusee(Exception):
    """Refus métier de « Facturer » un devis (message FR, prêt pour un 400)."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


#: Nombre maximal de paiements déjà reçus saisis en une fois (« Facturer »).
MAX_PAIEMENTS_SAISIS = 5


def valider_paiements_saisis(paiements, *, aujourdhui=None):
    """Valide la liste des paiements DÉJÀ reçus saisie au moment de facturer.

    0 à ``MAX_PAIEMENTS_SAISIS`` entrées ``{montant, date_paiement,
    mode_paiement, reference?}`` : montant décimal > 0 (2 décimales au plus),
    date ISO jamais dans le futur, mode parmi ``Paiement.Mode``. Renvoie la
    liste normalisée ``[{montant: Decimal, date_paiement: date, mode: str,
    reference: str}]`` ; lève ``FacturationRefusee`` (message FR) sinon.
    """
    import datetime
    from decimal import InvalidOperation

    from django.utils import timezone

    from core.money import quantize_mad

    from apps.ventes.models import Paiement

    if paiements is None:
        return []
    if not isinstance(paiements, (list, tuple)):
        raise FacturationRefusee(
            'Les paiements doivent être une liste (0 à '
            f'{MAX_PAIEMENTS_SAISIS} lignes).')
    if len(paiements) > MAX_PAIEMENTS_SAISIS:
        raise FacturationRefusee(
            f'Au plus {MAX_PAIEMENTS_SAISIS} paiements peuvent être saisis '
            'en une fois.')
    aujourdhui = aujourdhui or timezone.localdate()
    modes = {valeur: libelle for valeur, libelle in Paiement.Mode.choices}
    normalises = []
    for numero, brut in enumerate(paiements, start=1):
        if not isinstance(brut, dict):
            raise FacturationRefusee(f'Paiement n°{numero} : ligne illisible.')
        try:
            montant = Decimal(str(brut.get('montant', '')).strip()
                              .replace(',', '.'))
        except (InvalidOperation, ValueError):
            raise FacturationRefusee(
                f'Paiement n°{numero} : montant invalide.')
        if not montant.is_finite() or montant <= 0:
            raise FacturationRefusee(
                f'Paiement n°{numero} : le montant doit être positif.')
        if montant != quantize_mad(montant):
            raise FacturationRefusee(
                f'Paiement n°{numero} : le montant a plus de deux décimales.')
        brut_date = brut.get('date_paiement')
        try:
            date_paiement = datetime.date.fromisoformat(str(brut_date or ''))
        except ValueError:
            raise FacturationRefusee(
                f'Paiement n°{numero} : date de paiement invalide '
                '(format attendu AAAA-MM-JJ).')
        if date_paiement > aujourdhui:
            raise FacturationRefusee(
                f'Paiement n°{numero} : la date de paiement ne peut pas être '
                'dans le futur.')
        mode = str(brut.get('mode_paiement') or '').strip()
        if mode not in modes:
            raise FacturationRefusee(
                f'Paiement n°{numero} : mode de paiement inconnu '
                f'(attendu : {", ".join(modes)}).')
        reference = str(brut.get('reference') or '').strip()
        if len(reference) > 120:
            raise FacturationRefusee(
                f'Paiement n°{numero} : référence trop longue (120 caractères '
                'au plus).')
        normalises.append({
            'montant': quantize_mad(montant),
            'date_paiement': date_paiement,
            'mode': mode,
            'reference': reference,
        })
    return normalises


def facturer_devis_complet(*, devis, user, company, paiements=None):
    """« Facturer » un devis ACCEPTÉ en UN geste atomique (fondateur, 05/10).

    Cas réel : un client a signé et déjà payé ~90 % en 1 à 3 versements, et il
    n'existait aucun chemin simple pour émettre SA facture. Ce service :

      1. refuse un devis non accepté, ou déjà facturé (échéancier OU bon de
         commande, consolidée — LA garde ``exiger_devis_facturable``, ATOT2), en
         nommant les références existantes ;
      2. valide les paiements déjà reçus (``valider_paiements_saisis``) ;
      3. dans UNE transaction : réserve le stock comme la facturation directe
         (U9, garde anti-double-comptage incluse), crée la facture COMPLÈTE
         (100 %, lignes du devis recopiées par ``copier_devis_sur_facture`` —
         le même geste que la facture de BC), la rattache au bon de commande
         du devis s'il en a un sans facture, l'ÉMET par le service unique
         ``emettre_facture`` (numéro définitif déjà posé par
         ``create_numbered``), refuse une somme de paiements > total TTC, puis
         consigne chaque paiement par ``encaisser_sur_facture`` — le MÊME code
         que ``factures/{id}/enregistrer-paiement/``.

    Tout refus annule TOUT (aucune facture, aucun numéro consommé, aucun
    paiement). Lève ``FacturationRefusee``, ``EncaissementRefuse``,
    ``EmissionRefusee``, ``StockInsuffisantError`` ou ``CreditHoldError``.
    Renvoie ``(facture, [paiements créés])``.
    """
    from django.db import transaction

    from apps.ventes.domain.encaissements import encaisser_sur_facture
    from apps.ventes.models import BonCommande, Facture
    from apps.ventes.selectors_facturation import (
        DevisDejaFacture, exiger_devis_facturable,
    )
    from apps.ventes.utils.company_settings import create_numbered

    if devis.statut != devis.Statut.ACCEPTE:
        raise FacturationRefusee(
            'Seul un devis accepté peut être facturé : ce devis est au statut '
            f'« {devis.get_statut_display()} ».')
    # ATOT2 — LA garde unique des quatre portes (consolidée comprise).
    try:
        exiger_devis_facturable(devis, 'complete')
    except DevisDejaFacture as exc:
        raise FacturationRefusee(exc.motif) from exc
    saisis = valider_paiements_saisis(paiements)

    # Le bon de commande du devis est rattaché s'il n'a encore AUCUNE facture
    # (``Facture.bon_commande`` est un OneToOne : même une facture annulée
    # occupe la place) et n'est pas annulé.
    bc = BonCommande.objects.filter(devis=devis).first()
    if bc is not None and (
            bc.statut == BonCommande.Statut.ANNULE
            or Facture.objects.filter(bon_commande=bc).exists()):
        bc = None

    with transaction.atomic():
        reserver_stock_devis_facture(devis=devis, user=user, company=company)

        def _create(ref):
            facture = Facture.objects.create(
                reference=ref,
                devis=devis,
                bon_commande=bc,
                client=devis.client,
                statut=Facture.Statut.BROUILLON,
                type_facture=Facture.TypeFacture.COMPLETE,
                created_by=user,
                company=company,
                **entete_facture_depuis_devis(devis),
            )
            return copier_devis_sur_facture(facture, devis)

        facture = create_numbered(Facture, company, 'facture', _create)
        emettre_facture(facture, user=user, source='facturer_devis_complet')
        facture.refresh_from_db()

        total_ttc = Decimal(str(facture.total_ttc))
        somme = sum((p['montant'] for p in saisis), Decimal('0'))
        if somme - total_ttc > Decimal('0.01'):
            raise FacturationRefusee(
                f'Les paiements saisis ({somme:.2f} MAD) dépassent le total '
                f'TTC de la facture ({total_ttc:.2f} MAD).')

        crees = []
        for donnees in saisis:
            facture, paiement = encaisser_sur_facture(
                facture=facture, donnees=donnees, user=user)
            crees.append(paiement)
        facture.refresh_from_db()
    logger.info(
        'facturer_devis_complet: facture %s émise depuis devis %s avec %d '
        'paiement(s) (company=%s)', facture.reference, devis.reference,
        len(crees), getattr(company, 'id', '?'))
    return facture, crees


def creer_facture_contrat(*, contrat, user, company):
    """FG40 — Crée une Facture de maintenance récurrente depuis un ContratMaintenance.

    Appelé par sav.maintenance (action `facturer`) ; jamais depuis un template
    ou une vue directement.

    Règles :
      - Le contrat doit avoir `facturation_active=True` et `prix` renseigné.
      - La facture porte le libellé "Maintenance — contrat #<pk>" + périodicité.
      - TVA 20 % (taux standard, configurable en dur ici — pas de multi-TVA sur
        les forfaits de maintenance).
      - Statut EMISE directement (facture manuelle de redevance).
      - Après création, `derniere_facturation` du contrat est avancée à aujourd'hui.

    XCTR22 (AUDV18) — le débit du mandat de prélèvement actif n'est PAS
    déclenché ICI volontairement : le SEUL appelant (`sav.services.
    facturer_contrat_maintenance`) ajoute encore la ligne d'usage XCTR16
    APRÈS ce retour (AUD151, montant final recalculé depuis les lignes) —
    débiter ici sous-facturerait tout contrat à tarif d'usage. Le branchement
    vit donc dans l'appelant, une fois le montant définitif connu.

    Lève ValueError si les pré-conditions ne sont pas remplies.
    Renvoie la Facture créée.
    """
    from django.utils import timezone
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    if not contrat.facturation_active:
        raise ValueError(
            f"La facturation n'est pas activée sur le contrat #{contrat.pk}.")
    if not contrat.prix:
        raise ValueError(
            f"Le prix est absent sur le contrat #{contrat.pk}. "
            "Renseignez un prix avant d'émettre une facture.")
    if not contrat.actif:
        raise ValueError(f"Le contrat #{contrat.pk} n'est pas actif.")

    tva_pct = Decimal('20')
    prix_ttc = Decimal(str(contrat.prix))
    prix_ht = (prix_ttc / (1 + tva_pct / 100)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (prix_ttc - prix_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    periodicite_label = (
        contrat.get_periodicite_display()
        if hasattr(contrat, 'get_periodicite_display')
        else contrat.periodicite
    )
    libelle = f'Maintenance — contrat #{contrat.pk} ({periodicite_label})'

    # YSUBS9 — période de service couverte par CETTE facture : du dernier
    # cycle facturé (ou date_debut si jamais facturé) à aujourd'hui + la
    # durée de la périodicité (mois, table MONTHS déjà utilisée pour les
    # visites). Best-effort : une périodicité/date absente laisse les deux
    # champs à NULL (comportement actuel intact).
    periode_debut = contrat.derniere_facturation or contrat.date_debut
    periode_fin = None
    if periode_debut is not None:
        mois = getattr(contrat, 'MONTHS', {}).get(contrat.periodicite)
        if mois:
            periode_fin = _add_months(periode_debut, mois)

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=contrat.client,
            statut=Facture.Statut.BROUILLON,
            taux_tva=tva_pct,
            montant_ht=prix_ht,
            montant_tva=montant_tva,
            montant_ttc=prix_ttc,
            libelle=libelle,
            created_by=user,
            periode_service_debut=periode_debut,
            periode_service_fin=periode_fin,
        )

    # AUD101 — la facture naît BROUILLON puis passe par LE service d'émission
    # (verrou de période + blocage crédit + `facture_emise` une seule fois).
    # YSUBS6 reste satisfait : l'événement est bien émis, mais par le seul
    # site qui a le droit de poser EMISE. La transaction garantit qu'un refus
    # (période close, hold crédit) ne laisse AUCUN brouillon orphelin.
    from django.db import transaction
    with transaction.atomic():
        facture = create_with_reference(Facture, 'FAC', company, _create)
        emettre_facture(facture, user=user, source='contrat_maintenance')

        # Avancer la date de dernière facturation.
        today = timezone.localdate()
        contrat.derniere_facturation = today
        contrat.save(update_fields=['derniere_facturation'])

    logger.info(
        'FG40: facture %s créée pour contrat #%s (company %s)',
        facture.reference, contrat.pk, company.id)
    return facture


# ── XPRJ3 — Facturation en régie (T&M) depuis gestion_projet ─────────────────

def creer_facture_regie(*, company, client, user, libelle, montant_ht,
                        taux_tva=None):
    """XPRJ3 — Crée une Facture BROUILLON « en régie » (temps & matériel).

    Fonction FINE sanctionnée pour ``gestion_projet.services.facturer_temps_
    projet`` (frontière cross-app, CLAUDE.md) : ce module ne connaît AUCUN
    détail de gestion_projet (pas de timesheet, pas de tâche) — il reçoit juste
    un montant HT déjà calculé (heures × taux de facturation, agrégées côté
    appelant) et un libellé. Le client est résolu côté APPELANT (jamais importé
    ici) et passé en instance ``crm.Client``.

    Statut BROUILLON (contrairement à ``creer_facture_contrat`` qui émet
    directement) : une facture de régie doit rester éditable/relisible avant
    envoi. Numérotation via ``apps/ventes/utils/references.py`` (jamais
    ``count()+1``). Renvoie la ``Facture`` créée.

    AUD181 — ``taux_tva=None`` (et non plus ``Decimal('20')`` figé) résout le
    KNOB SOCIÉTÉ ``CompanyProfile.tva_standard`` comme le font déjà les deux
    fonctions frères de ce module : un tenant réglé à 14 % ne voyait 14 % que
    sur ses factures SAV, et 20 % sur sa régie. Le défaut du knob reste 20 %,
    donc le comportement est inchangé tant que rien n'est édité.
    """
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    from ..utils.company_settings import tva_standard

    taux_tva = (Decimal(str(taux_tva)) if taux_tva is not None
                else tva_standard(company))
    montant_ht = Decimal(montant_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (montant_ht * taux_tva / 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_ttc = montant_ht + montant_tva

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.COMPLETE,
            taux_tva=taux_tva,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            libelle=libelle,
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)
    logger.info(
        'XPRJ3: facture régie %s créée (company %s, montant HT %s)',
        facture.reference, company.id, montant_ht)
    return facture


# ── ASTK197 — Facture d'une consommation de dépôt de consignation ──────────

#: Préfixe du marqueur d'origine porté par ``Facture.note`` (aucun champ
#: « référence d'origine » n'existe sur Facture : note libre, nommée ici).
MARQUEUR_ORIGINE_CONSIGNATION = '[origine:'


def _marqueur_origine(reference_origine):
    return f'{MARQUEUR_ORIGINE_CONSIGNATION}{reference_origine}]'


def creer_facture_consignation(*, company, client, user, lignes,
                               reference_origine):
    """ASTK197 (C-ASTK-047) — Facture BROUILLON d'une consommation déclarée
    sur un dépôt de consignation (appelant : ``stock.services_consignation.
    declarer_consommation``, ASTK198, via ``apps.ventes.services``).

    * ``client`` : ``crm.Client`` résolu par l'APPELANT ; ``lignes`` :
      itérable de ``{'produit': Produit, 'quantite': n}`` (produits déjà
      résolus côté appelant ; un produit d'une autre société est refusé) ;
    * chaque ligne au PRIX DE VENTE catalogue HT (``Produit.prix_vente``,
      même lecture que les factures classiques SAV/intervention — jamais
      ``prix_achat``), TVA du produit, sinon le knob société
      ``tva_standard`` (comme ``creer_facture_regie``, AUD181) ;
    * totaux NON figés (``montant_*`` NULL) : la chaîne Sous-total → TVA →
      TTC est calculée sur les lignes, la facture reste éditable ;
    * numérotation ``apps/ventes/utils/references.py`` (jamais count()+1) ;
    * IDEMPOTENTE par ``reference_origine`` (ex. ``CONSIGNATION-<id>``) :
      Facture n'a pas de champ « référence d'origine », le marqueur
      ``[origine:<ref>]`` est porté par ``Facture.note`` et relu (société +
      client, facture non annulée) sous la même transaction.

    Lève ``ValueError`` si le client ou un produit n'appartient pas à
    ``company``, ou si ``reference_origine`` est vide. Renvoie la Facture.
    """
    from django.db import transaction

    from apps.ventes.models import Facture, LigneFacture
    from apps.ventes.utils.references import create_with_reference

    from ..utils.company_settings import tva_standard

    reference_origine = str(reference_origine or '').strip()
    if not reference_origine:
        raise ValueError('reference_origine est obligatoire.')
    if client is None or client.company_id != company.id:
        raise ValueError("Le client n'appartient pas à cette société.")
    lignes = list(lignes or [])
    for ligne in lignes:
        produit = ligne.get('produit')
        if produit is None or produit.company_id != company.id:
            raise ValueError(
                "Un produit de la consignation n'appartient pas à cette "
                'société.')

    marqueur = _marqueur_origine(reference_origine)
    with transaction.atomic():
        existante = (Facture.objects.select_for_update()
                     .filter(company=company, client=client,
                             note__contains=marqueur)
                     .exclude(statut=Facture.Statut.ANNULEE)
                     .order_by('id').first())
        if existante is not None:
            return existante

        taux_defaut = tva_standard(company)

        def _create(ref):
            return Facture.objects.create(
                reference=ref, company=company, client=client,
                statut=Facture.Statut.BROUILLON,
                type_facture=Facture.TypeFacture.COMPLETE,
                taux_tva=taux_defaut,
                libelle=f'Consommation de consignation {reference_origine}',
                note=marqueur,
                created_by=user,
            )

        facture = create_with_reference(Facture, 'FAC', company, _create)
        for ligne in lignes:
            produit = ligne['produit']
            quantite = Decimal(str(ligne.get('quantite') or 0))
            if quantite <= 0:
                continue
            LigneFacture.objects.create(
                facture=facture, produit=produit, designation=produit.nom,
                quantite=quantite,
                prix_unitaire=Decimal(str(produit.prix_vente or 0)),
                taux_tva=(produit.tva if produit.tva is not None
                          else taux_defaut),
            )
    logger.info(
        'ASTK197: facture consignation %s créée (company %s, origine %s)',
        facture.reference, company.id, reference_origine)
    return facture


# ── XPRJ4 — Facture d'acompte pour une situation de travaux (décompte BTP) ───

def creer_facture_acompte_situation(*, company, client, user, libelle,
                                    montant_periode_ht,
                                    retenue_garantie_pct=None,
                                    taux_tva=None):
    """XPRJ4 — Crée une Facture BROUILLON d'ACOMPTE pour une situation de
    travaux (décompte progressif BTP).

    Fonction FINE sanctionnée pour ``gestion_projet.services`` (frontière
    cross-app, CLAUDE.md) : reçoit le montant HT DÉJÀ calculé de la PÉRIODE
    (cumulé − antérieur, agrégé côté appelant sur toutes les lignes de la
    situation) et une retenue de garantie optionnelle (le taux, pas le suivi de
    sa libération — qui vit dans ``contrats``, jamais importé ici). Statut
    BROUILLON + ``type_facture`` ACOMPTE (chaîne standard devis→factures,
    réutilisée ici sans devis source). Numérotation via
    ``apps/ventes/utils/references.py`` (jamais ``count()+1``). Renvoie la
    ``Facture`` créée.

    AUD180 — DÉCISION FONDATEUR du 03/09/2026 : l'ASSIETTE est le
    ``montant_periode`` COMPLET. La retenue de garantie est une modalité de
    PAIEMENT (un montant retenu sur le RÈGLEMENT), pas une réduction de
    l'assiette taxable : ni ``montant_ht`` ni ``montant_tva`` ne sont diminués
    du pourcentage retenu. Auparavant la retenue était déduite du HT ET servait
    de base à la TVA (``montant_ht_net``), ce qui sous-déclarait la TVA.
    Elle est désormais tracée dans ``conditions_paiement``, seul endroit où
    elle a sa place ; à contre-valider par le comptable, sans bloquer.

    AUD181 — ``taux_tva=None`` résout le knob société ``tva_standard`` (défaut
    20 %) au lieu de figer 20 %, comme les deux fonctions frères de ce module.
    """
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    from ..utils.company_settings import tva_standard

    taux_tva = (Decimal(str(taux_tva)) if taux_tva is not None
                else tva_standard(company))
    montant_periode_ht = Decimal(montant_periode_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    rg_pct = Decimal(retenue_garantie_pct or 0)
    montant_rg = (montant_periode_ht * rg_pct / 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    # Assiette = période COMPLÈTE (la RG ne la réduit jamais).
    montant_tva = (montant_periode_ht * taux_tva / 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_ttc = montant_periode_ht + montant_tva
    conditions_paiement = ''
    if montant_rg > 0:
        conditions_paiement = (
            f'Retenue de garantie de {rg_pct.normalize():f} % '
            f'({montant_rg} MAD) retenue sur le règlement — '
            'sans effet sur la base taxable.')

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.ACOMPTE,
            taux_tva=taux_tva,
            montant_ht=montant_periode_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            libelle=libelle,
            conditions_paiement=conditions_paiement,
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)
    logger.info(
        'XPRJ4: facture acompte situation %s créée (company %s, montant HT '
        '%s, RG %s%% = %s retenue au règlement)',
        facture.reference, company.id, montant_periode_ht, rg_pct, montant_rg)
    return facture


# ── XPOS1/XPOS6 — Thin services exposés pour apps.pos (vente comptoir) ─────
# apps.pos ne peut PAS importer apps.ventes.models directement (règle de
# modularité CLAUDE.md) : ces fonctions sont son unique porte d'entrée pour
# créer une facture classique et enregistrer/lire des paiements.

def creer_facture_classique(*, company, client, user, taux_tva, montant_ht,
                            montant_tva, montant_ttc, libelle='',
                            reglee_a_l_acte=False):
    """Crée une ``Facture`` classique (sans devis/BC), montants figés.

    Utilisé par ``apps.pos.services.valider_vente`` pour la facture légale
    d'une vente comptoir. ``company``/``client`` doivent déjà être validés par
    l'appelant (scoping multi-tenant). Numérotation collision-proof (jamais
    count()+1).

    AUD101 — la facture naît BROUILLON et passe par ``emettre_facture`` : elle
    hérite donc du verrou de période, du blocage crédit XFAC28 et de
    l'événement ``facture_emise`` (donc de l'écriture au grand livre), qu'elle
    n'avait jamais. ``reglee_a_l_acte=True`` est l'EXEMPTION explicite de
    blocage crédit : une vente comptoir intégralement réglée à l'acte encaisse
    du cash immédiat, le hold d'encours n'a aucune raison de la refuser."""
    from django.db import transaction
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.COMPLETE,
            taux_tva=taux_tva,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            libelle=libelle,
            created_by=user,
        )

    with transaction.atomic():
        facture = create_with_reference(Facture, 'FAC', company, _create)
        emettre_facture(
            facture, user=user, source='facture_classique',
            verifier_credit=not reglee_a_l_acte)
    return facture


# ── XACC28 — Refacturation des frais au client (billable expenses) ────────
# Thin service exposé aux autres apps (frontière cross-app, CLAUDE.md) :
# l'appelant (SAV, hôtellerie) connaît le montant/la marge déjà calculés de son
# côté, jamais les détails de facturation — il pousse juste des lignes sur une
# facture EXISTANTE du client. Un produit générique « Frais refacturés »
# (service, sans stock) est créé une fois par société (idempotent) pour porter
# ces lignes, à l'image du produit catalogue des lignes classiques.

_PRODUIT_FRAIS_REFACTURES_NOM = 'Frais refacturés'


def _produit_frais_refactures(company):
    """Produit de service « Frais refacturés » de la société — un seul, jamais
    deux.

    COURSE FERMÉE (29/08/2026). C'était un ``get_or_create(company=…, nom=…)``
    sur un couple SANS contrainte d'unicité : deux appels concurrents (webhook,
    tâche Celery, double validation) créaient DEUX fiches homonymes. Depuis
    ``stock.0135``, un UNIQUE conditionnel couvre exactement ce couple pour les
    produits ACTIFS SANS SKU — et ce site applique le patron maison
    ``lecture -> création dans un point de sauvegarde -> relecture sur
    IntegrityError`` (même idiome que ``ventes.utils.references``), qui :

      * rend la course inoffensive (le perdant relit la fiche du gagnant) ;
      * ne casse JAMAIS la transaction englobante (le ``atomic()`` interne est
        un savepoint) ;
      * survit à une base historique où plusieurs homonymes coexisteraient
        encore — ``.first()`` déterministe (plus petit ``pk``) là où
        ``get_or_create`` aurait levé ``MultipleObjectsReturned``.

    Les produits ARCHIVÉS sont ignorés (ils sortent du périmètre de la
    contrainte) : archiver l'ancienne fiche en fait naître une neuve, jamais un
    conflit."""
    from django.db import IntegrityError, transaction

    from apps.stock.models import Produit

    def _lire():
        return Produit.objects.filter(
            company=company, nom=_PRODUIT_FRAIS_REFACTURES_NOM,
            is_archived=False).order_by('pk').first()

    produit = _lire()
    if produit is not None:
        return produit
    try:
        with transaction.atomic():
            return Produit.objects.create(
                company=company, nom=_PRODUIT_FRAIS_REFACTURES_NOM,
                prix_vente=Decimal('0'), quantite_stock=0, seuil_alerte=0)
    except IntegrityError:
        produit = _lire()
        if produit is None:
            raise
        return produit


def ajouter_lignes_frais_refactures(*, facture, lignes, user=None):
    """Ajoute des lignes de frais refacturés sur une ``Facture`` EXISTANTE.

    ``lignes`` est une liste de dicts ``{'designation', 'montant_ht',
    'taux_tva'?}`` (montant déjà majoré de la marge, calculé côté appelant).
    Chaque ligne devient une ``LigneFacture`` (quantité=1,
    prix_unitaire=montant_ht) rattachée au produit générique « Frais
    refacturés » de la société de la facture ; les totaux de la facture sont
    recalculés. Renvoie la liste des ``LigneFacture`` créées. Ne vérifie PAS
    l'anti-doublon (fait côté appelant, sur les frais eux-mêmes)."""
    from apps.ventes.models import LigneFacture

    if not lignes:
        return []
    produit = _produit_frais_refactures(facture.company)
    # ERR-QAC-FACTURE-RECALCUL-REMISE — état « figé » lu AVANT l'ajout : une
    # facture d'échéancier porte des montants figés sans lignes produit, que le
    # recalcul depuis les seules lignes écraserait.
    figee = facture.montant_ht is not None
    frais_ht = Decimal('0')
    frais_tva = Decimal('0')
    creees = []
    for ligne in lignes:
        montant_ht = Decimal(ligne.get('montant_ht') or 0)
        taux = ligne.get('taux_tva')
        creees.append(LigneFacture.objects.create(
            facture=facture,
            produit=produit,
            designation=ligne.get('designation', '') or _PRODUIT_FRAIS_REFACTURES_NOM,
            quantite=Decimal('1'),
            prix_unitaire=montant_ht,
            taux_tva=taux,
        ))
        frais_ht += montant_ht
        frais_tva += montant_ht * Decimal(
            taux if taux is not None else (facture.taux_tva or 0)
        ) / Decimal('100')
    _recalculer_totaux_facture(
        facture, frais_figes=(frais_ht, frais_tva) if figee else None)
    return creees


def _recalculer_totaux_facture(facture, *, frais_figes=None):
    """Recalcule les totaux HT/TVA/TTC d'une facture.

    Réutilisé par XACC28 après ajout de lignes de frais refacturés.

    ERR-QAC-FACTURE-RECALCUL-REMISE :
      * facture NON figée → LA chaîne canonique (``TotauxDocumentMixin``,
        remise globale incluse) sur ses lignes — plus de re-somme brute qui
        ignorait ``remise_globale`` ;
      * facture figée (tranche d'échéancier) → ``frais_figes=(ht, tva)`` est
        AJOUTÉ aux montants figés au lieu de les remplacer par la somme des
        seules lignes de frais. Sans ``frais_figes``, une facture figée est
        laissée telle quelle."""
    q = Decimal('0.01')
    if facture.montant_ht is not None:
        if not frais_figes:
            return facture
        ht_ajout, tva_ajout = frais_figes
        tva_base = facture.montant_tva
        if tva_base is None:
            tva_base = (facture.montant_ht * Decimal(facture.taux_tva or 0)
                        / Decimal('100'))
        facture.montant_ht = (facture.montant_ht + ht_ajout).quantize(
            q, rounding=ROUND_HALF_UP)
        facture.montant_tva = (tva_base + tva_ajout).quantize(
            q, rounding=ROUND_HALF_UP)
        facture.montant_ttc = facture.montant_ht + facture.montant_tva
    else:
        totaux = facture.totaux_affichage
        facture.montant_ht = totaux['ht_net']
        facture.montant_ttc = totaux['ttc']
        facture.montant_tva = facture.montant_ttc - facture.montant_ht
    facture.save(update_fields=['montant_ht', 'montant_tva', 'montant_ttc'])
    return facture


def calculer_date_echeance(*, client, date_emission):
    """XFAC23 — dérive la date d'échéance depuis les conditions de paiement du
    client (délai en jours + report fin de mois).

    Renvoie ``None`` quand le client n'a pas de délai négocié (``crm.Client.
    delai_paiement_jours`` vide) — l'appelant retombe alors sur le comportement
    historique (repli +30 j calculé ailleurs, ex. ``scheduled.
    _echeance_effective``). Ne calcule JAMAIS à la place d'une échéance déjà
    saisie manuellement — c'est à l'appelant de ne pas écraser une valeur
    existante (input freedom).

    Cross-app lecture seule via ``apps.crm.selectors`` (jamais d'import de
    ``apps.crm.models``).
    """
    if client is None or date_emission is None:
        return None
    from apps.crm.selectors import delai_paiement_client
    reglage = delai_paiement_client(client)
    delai = reglage.get('delai_jours')
    if not delai:
        return None
    from datetime import timedelta
    echeance = date_emission + timedelta(days=int(delai))
    if reglage.get('fin_de_mois'):
        import calendar
        last_day = calendar.monthrange(echeance.year, echeance.month)[1]
        echeance = echeance.replace(day=last_day)
    return echeance


def get_facture_or_none(*, company, facture_id):
    """Facture scopée société, ou None (thin service pour apps.pos XPOS6)."""
    from apps.ventes.models import Facture
    return Facture.objects.filter(company=company, id=facture_id).first()


def facturables_pour_devis(*, company, query=''):
    """Factures émises/en retard avec solde restant dû, scopées société (thin
    selector pour apps.pos XPOS6 — recherche comptoir par référence)."""
    from apps.ventes.models import Facture
    qs = Facture.objects.filter(
        company=company,
        statut__in=(Facture.Statut.EMISE, Facture.Statut.EN_RETARD))
    if query:
        qs = qs.filter(reference__icontains=query)
    return [f for f in qs.select_related('client', 'devis') if f.montant_du > 0]


# ── XFSM1 — Facturation SAV hors garantie depuis le ticket ──────────────────
# apps.sav ne peut PAS importer apps.ventes.models directement (règle de
# modularité CLAUDE.md) : cette fonction est son unique porte d'entrée pour
# générer une facture brouillon depuis un ticket SAV.

def _main_oeuvre_produit(company):
    """Produit catalogue (service, non stocké) porteur de la ligne
    main-d'œuvre SAV — get-or-create idempotent, un seul par société.
    Jamais décrémenté (aucun mouvement de stock ne le référence)."""
    from apps.stock.models import Produit
    produit, _created = Produit.objects.get_or_create(
        company=company, sku='SAV-MO', defaults={
            'nom': "Main-d'œuvre SAV",
            'prix_vente': Decimal('0'),
            'quantite_stock': 0,
        })
    return produit


def generer_facture_ticket_sav(*, ticket, sous_garantie, pieces, user):
    """XFSM1 — construit une ``Facture`` BROUILLON pour un ticket SAV hors
    garantie (réels → facture) : lignes pièces (prix de VENTE catalogue,
    jamais ``prix_achat``) + ligne main-d'œuvre (taux horaire
    ``CompanyProfile.taux_horaire_sav`` × ``ticket.heures_main_oeuvre``).

    Quand ``sous_garantie`` est vrai (ticket sous garantie ou contrat actif
    couvrant), TOUTES les lignes sont posées à 0 DH avec la mention
    « couvert garantie/contrat » dans leur désignation — le document reste
    traçable sans jamais facturer un client couvert.

    ``pieces`` : itérable d'objets exposant ``produit`` (stock.Produit) et
    ``quantite`` (déjà scopés société par l'appelant — sav.views). Référence
    via ``apps.ventes.utils.references`` (jamais count()+1).

    IDEMPOTENT : si ``ticket.facture_id_ext`` pointe déjà vers une facture
    non annulée, la renvoie telle quelle plutôt que d'en créer une seconde.
    Renvoie la ``Facture`` créée (ou réutilisée)."""
    from ..models import Facture, LigneFacture
    from ..utils.company_settings import tva_standard
    from ..utils.references import create_with_reference

    if ticket.facture_id_ext:
        existante = Facture.objects.filter(
            pk=ticket.facture_id_ext, company=ticket.company
        ).exclude(statut=Facture.Statut.ANNULEE).first()
        if existante is not None:
            return existante

    company = ticket.company
    taux_tva_defaut = tva_standard(company)

    def _create(ref):
        return Facture.objects.create(
            reference=ref, company=company, client=ticket.client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.COMPLETE,
            libelle=f'SAV {ticket.reference} — hors garantie',
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)

    suffixe_couvert = ' (couvert garantie/contrat)' if sous_garantie else ''

    for piece in pieces:
        produit = piece.produit
        quantite = piece.quantite
        prix_unitaire = (
            Decimal('0') if sous_garantie
            else Decimal(str(produit.prix_vente or 0)))
        LigneFacture.objects.create(
            facture=facture, produit=produit,
            designation=f'{produit.nom}{suffixe_couvert}',
            quantite=quantite, prix_unitaire=prix_unitaire,
            taux_tva=(produit.tva if produit.tva is not None
                      else taux_tva_defaut),
        )

    heures = ticket.heures_main_oeuvre
    if heures:
        profile_taux = None
        try:
            from apps.parametres.models import CompanyProfile
            profile_taux = CompanyProfile.get(company).taux_horaire_sav
        except Exception:  # pragma: no cover - défensif
            profile_taux = None
        taux_horaire = (
            Decimal('0') if sous_garantie
            else Decimal(str(profile_taux)) if profile_taux is not None
            else None)
        if taux_horaire is not None:
            mo_produit = _main_oeuvre_produit(company)
            LigneFacture.objects.create(
                facture=facture, produit=mo_produit,
                designation=f"Main-d'œuvre{suffixe_couvert}",
                quantite=heures, prix_unitaire=taux_horaire,
                taux_tva=taux_tva_defaut,
            )

    ticket.facture_id_ext = facture.id
    ticket.save(update_fields=['facture_id_ext'])
    return facture


# ── ZFSM4 — Facturation directe d'une intervention hors contrat/ticket ──────
# apps.installations ne peut PAS importer apps.ventes.models directement
# (règle de modularité CLAUDE.md) : cette fonction est son unique porte
# d'entrée pour générer une facture brouillon depuis une intervention payante
# (dépannage résidentiel facturé sur place, prestation ponctuelle) — DISTINCT
# de XFSM1/XCTR4 qui facturent depuis un TICKET SAV.

def generer_facture_intervention(*, intervention, user):
    """ZFSM4 — construit une ``Facture`` BROUILLON pour une intervention hors
    contrat/ticket : lignes matériel depuis ``ConsommationLigne`` (prix de
    VENTE catalogue, JAMAIS ``prix_achat``) + ligne main-d'œuvre (durée F15
    ``field_capture.crew_time`` × ``CompanyProfile.taux_horaire_sav``, le
    taux horaire paramétrable réutilisé de XFSM1 — pas de nouveau champ).

    Référence via ``apps.ventes.utils.references`` (jamais count()+1). PDF
    legacy (pas ``/proposal`` — règle #4 : ce chemin ne touche jamais le
    moteur de devis client).

    IDEMPOTENT : si ``intervention.facture_id`` pointe déjà vers une facture
    non annulée, la renvoie telle quelle plutôt que d'en créer une seconde.
    Renvoie la ``Facture`` créée (ou réutilisée)."""
    from ..models import Facture, LigneFacture
    from ..utils.company_settings import tva_standard
    from ..utils.references import create_with_reference

    if intervention.facture_id:
        existante = Facture.objects.filter(
            pk=intervention.facture_id, company=intervention.company
        ).exclude(statut=Facture.Statut.ANNULEE).first()
        if existante is not None:
            return existante

    installation = intervention.installation
    if installation is None or installation.client_id is None:
        raise ValueError(
            "generer_facture_intervention requires an intervention attached "
            "to a chantier with a resolved client")
    client = installation.client
    company = intervention.company or installation.company
    taux_tva_defaut = tva_standard(company)

    def _create(ref):
        return Facture.objects.create(
            reference=ref, company=company, client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.COMPLETE,
            libelle=(f'Intervention {intervention.get_type_intervention_display()} '
                     f'— {installation.reference}'),
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)

    consommation = getattr(intervention, 'consommation', None)
    if consommation is not None:
        for ligne in consommation.lignes.all():
            produit = ligne.produit
            quantite = ligne.quantite_utilisee
            if produit is None or not quantite:
                continue
            LigneFacture.objects.create(
                facture=facture, produit=produit,
                designation=ligne.designation or produit.nom,
                quantite=quantite,
                prix_unitaire=Decimal(str(produit.prix_vente or 0)),
                taux_tva=(produit.tva if produit.tva is not None
                          else taux_tva_defaut),
            )

    from apps.installations import field_capture
    heures_min = field_capture.crew_time(intervention).get('duree_sur_site_min')
    if heures_min:
        profile_taux = None
        try:
            from apps.parametres.models import CompanyProfile
            profile_taux = CompanyProfile.get(company).taux_horaire_sav
        except Exception:  # pragma: no cover - défensif
            profile_taux = None
        if profile_taux is not None:
            heures = (Decimal(heures_min) / Decimal(60)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            mo_produit = _main_oeuvre_produit(company)
            LigneFacture.objects.create(
                facture=facture, produit=mo_produit,
                designation="Main-d'œuvre",
                quantite=heures, prix_unitaire=Decimal(str(profile_taux)),
                taux_tva=taux_tva_defaut,
            )

    intervention.facture_id = facture.id
    intervention.save(update_fields=['facture_id'])
    logger.info(
        'ZFSM4: facture %s créée depuis intervention %s (company %s)',
        facture.reference, intervention.id, getattr(company, 'id', '?'))
    return facture


# ── QJR76 : l'arithmétique de date rejoint son SEUL lecteur ─────────────────
# `_add_months` sert uniquement `calculer_date_echeance` (plus haut) : ce
# module l'importait par un pont, qui disparaît avec ce déplacement.
def _add_months(d, months):
    """YSUBS9 — `d` décalée de `months` mois (jour recadré fin de mois).

    Fonction pure stdlib (pas de dépendance ajoutée), même calcul que
    `apps.sav.dateutils.add_months` mais gardée locale pour ne pas coupler
    `ventes` à `sav` pour une simple arithmétique de date."""
    if d is None or months is None:
        return None
    import calendar
    total = d.month - 1 + int(months)
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    from datetime import date
    return date(year, month, day)


# ── AFAC27 (C-AFAC-024) : LE constructeur unique d'avoir client ─────────────
class AvoirRefuse(Exception):
    """AFAC27 — refus métier de création d'avoir (message FR, prêt 400)."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


def _quantites_retour(facture):
    """(vendu, déjà retourné) par produit — lus sur la facture VERROUILLÉE.

    Déjà retourné = lignes des avoirs ÉMIS (un avoir annulé rend ses unités
    retournables à nouveau)."""
    from ..models import Avoir
    vendu, deja = {}, {}
    for lig in facture.lignes.all():
        if lig.produit_id:
            vendu[lig.produit_id] = (
                vendu.get(lig.produit_id, Decimal('0')) + lig.quantite)
    for a in facture.avoirs.filter(statut=Avoir.Statut.EMISE):
        for lig in a.lignes.all():
            if lig.produit_id:
                deja[lig.produit_id] = (
                    deja.get(lig.produit_id, Decimal('0')) + lig.quantite)
    return vendu, deja


def _lignes_retour(facture, company, demandes):
    """Valide les lignes d'un retour CONTRE la facture verrouillée et les
    complète des prix/remise/TVA FACTURÉS. Renvoie ``(lignes, epuise)`` où
    ``epuise`` dit si ce retour rend TOUTES les unités vendues."""
    from decimal import InvalidOperation

    from apps.stock.selectors import get_produit_scoped
    vendu, deja = _quantites_retour(facture)
    retour = {}
    lignes = []
    for i, ligne in enumerate(demandes, start=1):
        if not isinstance(ligne, dict):
            raise AvoirRefuse(f'Ligne {i} invalide.')
        produit_id = ligne.get('produit') or None
        if produit_id is None:
            raise AvoirRefuse(f'Ligne {i} : produit requis.')
        produit = get_produit_scoped(company, produit_id)
        if produit is None:
            raise AvoirRefuse(f'Ligne {i} : produit inconnu.')
        produit_id = produit.id
        try:
            qte = Decimal(str(ligne.get('quantite')))
        except (InvalidOperation, TypeError, ValueError):
            raise AvoirRefuse(f'Ligne {i} : quantité numérique requise.')
        if qte <= 0:
            raise AvoirRefuse(f'Ligne {i} : quantité > 0 requise.')
        disponible = (vendu.get(produit_id, Decimal('0'))
                      - deja.get(produit_id, Decimal('0'))
                      - retour.get(produit_id, Decimal('0')))
        if qte > disponible:
            raise AvoirRefuse(
                f'Ligne {i} : quantité retournée ({qte}) supérieure à la '
                f'quantité vendue restant retournable ({disponible}) pour '
                f'« {produit.nom} ».')
        retour[produit_id] = retour.get(produit_id, Decimal('0')) + qte
        f_ligne = next((lig for lig in facture.lignes.all()
                        if lig.produit_id == produit_id), None)
        lignes.append({
            'produit': produit, 'produit_id': produit_id,
            'designation': (f_ligne.designation if f_ligne
                            else produit.nom)[:255],
            'quantite': qte,
            'prix_unitaire': (f_ligne.prix_unitaire if f_ligne
                              else Decimal('0')),
            'remise': f_ligne.remise if f_ligne else Decimal('0'),
            'taux_tva': f_ligne.taux_tva if f_ligne else None,
        })
    epuise = bool(vendu) and all(
        deja.get(pid, Decimal('0')) + retour.get(pid, Decimal('0')) >= q
        for pid, q in vendu.items())
    return lignes, epuise


def _figer_avoir_retour(avoir, facture, *, epuise, reste_creditable):
    """Palier d'arrondi de la facture repris AU PRORATA sur un avoir de retour.

    La facture arrondie au palier (ARRONDI-100) facture moins que la somme de
    ses lignes ; un retour au prix des lignes créditait donc plus que ce qui
    a été facturé pour ces unités. TTC de l'avoir = TTC facturé × (valeur
    des unités retournées / valeur non arrondie de la facture) ; le retour
    qui ÉPUISE les quantités porte le SOLDE au centime (Σ avoirs = TTC
    facturé). Sans palier, seul le dernier retour absorbe un écart d'arrondi
    de quelques centimes."""
    from core.money import quantize_mad
    from ..selectors import _canonical_totaux

    naturel = Decimal(str(avoir.total_ttc))
    pas = getattr(facture, 'arrondi_pas', 0) or 0
    if pas:
        if epuise:
            cible = reste_creditable
        else:
            brut = Decimal(str(_canonical_totaux(
                list(facture.lignes.all()),
                remise_globale_pct=facture.remise_globale,
                fallback_taux=facture.taux_tva, arrondi_pas=0)['ttc']))
            if not brut:
                return
            cible = Decimal(str(facture.total_ttc)) * naturel / brut
    elif epuise and abs(naturel - reste_creditable) <= Decimal('0.05'):
        cible = reste_creditable
    else:
        return
    cible = quantize_mad(cible)
    if cible == naturel:
        return
    ttc_f = Decimal(str(facture.total_ttc))
    tva = (quantize_mad(cible * Decimal(str(facture.total_tva)) / ttc_f)
           if ttc_f else Decimal('0'))
    avoir.montant_ht = cible - tva
    avoir.montant_tva = tva
    avoir.montant_ttc = cible
    avoir.save(update_fields=['montant_ht', 'montant_tva', 'montant_ttc'])


def creer_avoir_facture(*, facture, user, motif, mode='correction',
                        lignes_saisies=None, retour_lignes=None,
                        restocker=False):
    """AFAC27 (C-AFAC-024) — LE constructeur unique d'un avoir client.

    Appelé par ``creer-avoir`` (correction totale/partielle, contre-
    passation) ET ``retour-client`` : il n'existe plus deux ``_create``
    locaux qui ne savaient pas la même chose (le retour ne reprenait ni la
    remise globale ni le palier d'arrondi de la facture, lisait son plafond
    hors transaction et n'émettait pas ``avoir_cree``).

    Dans UNE transaction, facture VERROUILLÉE (``select_for_update``) :
    validation des quantités retournables (retour), numérotation, lignes,
    remise globale et palier repris (au prorata pour un retour, le dernier
    retour portant le solde au centime), ventilation TVA (ATOT6), garde du
    plafond, re-stockage, chatter, ``avoir_cree``, recalcul du statut de
    paiement (ATOT8). Lève ``AvoirRefuse`` (400) — rien n'est alors écrit.
    Renvoie l'avoir (PDF généré par l'appelant, hors transaction)."""
    from django.db import transaction

    from apps.stock.services import (
        mouvement_type_entree, record_stock_movement,
    )
    from core.events import avoir_cree

    from .. import activity
    from ..models import Avoir, Facture, LigneAvoir
    from ..utils.company_settings import create_numbered
    from .encaissements import recalculer_statut_paiement

    company = facture.company
    est_retour = retour_lignes is not None
    with transaction.atomic():
        locked = Facture.objects.select_for_update().get(pk=facture.pk)
        epuise = False
        if est_retour:
            lignes, epuise = _lignes_retour(locked, company, retour_lignes)
        else:
            lignes = lignes_saisies or None
        reste_creditable = locked.total_ttc - locked.avoirs_total

        def _create(ref):
            avoir = Avoir.objects.create(
                company=company, reference=ref, facture=locked,
                client=locked.client, statut=Avoir.Statut.EMISE,
                motif=motif, motif_retour=motif if est_retour else '',
                restocke=bool(restocker and est_retour),
                taux_tva=locked.taux_tva,
                # AUD106 / AFAC27 — la remise globale de la facture SUIT
                # sur TOUT avoir (le retour ne la reprenait pas : sur-crédit).
                remise_globale=locked.remise_globale,
                # ARRONDI-100 — l'avoir TOTAL reprend le palier ; un avoir
                # partiel n'arrondit pas (un retour le reprend au prorata,
                # `_figer_avoir_retour`).
                arrondi_pas=(0 if lignes
                             else getattr(locked, 'arrondi_pas', 0) or 0),
                arrondi_unites=(1 if lignes
                                else getattr(locked, 'arrondi_unites', 1) or 1),
                created_by=user)
            if lignes:
                for ligne in lignes:
                    LigneAvoir.objects.create(
                        avoir=avoir, produit_id=ligne['produit_id'],
                        designation=ligne['designation'],
                        quantite=ligne['quantite'],
                        prix_unitaire=ligne['prix_unitaire'],
                        remise=ligne['remise'], taux_tva=ligne['taux_tva'])
            else:
                f_lignes = list(locked.lignes.all())
                if f_lignes:
                    for ligne in f_lignes:
                        LigneAvoir.objects.create(
                            avoir=avoir, produit=ligne.produit,
                            designation=ligne.designation,
                            quantite=ligne.quantite,
                            prix_unitaire=ligne.prix_unitaire,
                            remise=ligne.remise, taux_tva=ligne.taux_tva)
                else:
                    # Facture de tranche sans lignes : montants figés.
                    avoir.montant_ht = locked.total_ht
                    avoir.montant_tva = locked.total_tva
                    avoir.montant_ttc = locked.total_ttc
                    avoir.save(update_fields=[
                        'montant_ht', 'montant_tva', 'montant_ttc'])
            # ATOT6 — autant de paniers TVA que la facture d'origine ; à
            # défaut, un retour reprend le palier de la facture au prorata.
            ventile = ventiler_document_depuis_facture(
                avoir, locked, partiel=bool(lignes), lignes_saisies=lignes)
            if est_retour and not ventile:
                _figer_avoir_retour(avoir, locked, epuise=epuise,
                                    reste_creditable=reste_creditable)
            return avoir

        avoir = create_numbered(Avoir, company, 'avoir', _create)
        # Garde plafond (au centime) — SOUS le verrou : deux avoirs/retours
        # concurrents ne lisent plus chacun l'ancien reste. AFAC34 — plafond
        # = TTC + notes de débit − avoirs − abandons ACTIFS : une facture
        # abandonnée ne se crédite plus une seconde fois.
        plafond = (reste_creditable + locked.notes_debit_total
                   - (locked.abandon_montant or Decimal('0')))
        if avoir.total_ttc - plafond > Decimal('0.01'):
            raise AvoirRefuse(
                ('Le retour dépasse' if est_retour else "L'avoir dépasse")
                + f' le montant restant de la facture '
                  f'({max(plafond, Decimal("0")):.2f} MAD).')
        if restocker and est_retour:
            for ligne in lignes:
                produit = ligne['produit']
                produit.refresh_from_db()
                qte_entiere = int(Decimal(ligne['quantite']).quantize(
                    Decimal('1'), rounding=ROUND_HALF_UP))
                qte_avant = produit.quantite_stock
                record_stock_movement(
                    company=company, produit=produit,
                    type_mouvement=mouvement_type_entree(),
                    quantite=qte_entiere, quantite_avant=qte_avant,
                    quantite_apres=qte_avant + qte_entiere,
                    reference=avoir.reference,
                    note=(f'Retour client — {motif} '
                          f'(facture {locked.reference})'),
                    created_by=user)
        activity.log_facture_avoir(locked, user, avoir)
        if mode == 'contre_passation':
            # ZFAC5 — annulation NETTE : la facture d'origine passe annulee,
            # avec un FactureActivity liant les deux pièces.
            from ..models import FactureActivity
            ancien_statut = locked.statut
            locked.statut = Facture.Statut.ANNULEE
            locked.save(update_fields=['statut'])
            FactureActivity.objects.create(
                company=company, facture=locked, user=user,
                kind=FactureActivity.Kind.MODIFICATION,
                field='statut', field_label='Statut',
                old_value=ancien_statut,
                new_value=Facture.Statut.ANNULEE,
                body=(f"Facture annulée par contre-passation — avoir "
                      f"miroir {avoir.reference}."),
            )
        # YLEDG1 — événement documentaire (compta.ecriture_pour_avoir) :
        # émis pour TOUT avoir, retour compris (il ne l'était pas).
        avoir_cree.send(sender=Avoir, instance=avoir, company=company)
        # ATOT8 / AFAC29 — le statut de paiement suit le reste dû (un retour
        # qui solde la facture la passe PAYÉE).
        if mode != 'contre_passation':
            recalculer_statut_paiement(locked, user=user, source='avoir')
    return avoir


# ── AFAC32 (C-AFAC-026, D-AFAC-C4) : annulation d'une note de débit ─────────
def notes_debit_actives(facture):
    """Notes de débit ÉMISES de la facture qu'aucun avoir de note de débit
    actif ne neutralise encore (D-AFAC-C4 : une ND s'annule par avoir)."""
    from ..models import Avoir, NoteDebit
    return [
        nd for nd in facture.notes_debit.filter(
            statut=NoteDebit.Statut.EMISE).order_by('id')
        if not nd.avoirs_annulation.filter(
            statut=Avoir.Statut.EMISE).exists()
    ]


def annuler_note_debit_par_avoir(*, note_debit, user):
    """AFAC32 — LA voie d'annulation d'une note de débit émise (D-AFAC-C4,
    option a : par AVOIR, jamais en place) : un avoir sur la facture d'origine,
    miroir exact de la ND (lignes, remise globale, montants figés, paniers
    TVA), lié par ``Avoir.note_debit``. Le reste dû revient à ce qu'il était
    avant la ND ; chatter tracé, ``avoir_cree`` émis, statut de paiement
    re-dérivé (ATOT8).

    IDEMPOTENTE : une ND déjà neutralisée renvoie son avoir actif, sans en
    créer un second. Renvoie ``(avoir, cree)``. Lève ``AvoirRefuse`` si la ND
    n'est pas émise."""
    from django.db import transaction

    from core.events import avoir_cree

    from .. import activity
    from ..models import Avoir, Facture, FactureActivity, LigneAvoir, NoteDebit
    from ..utils.company_settings import create_numbered
    from .encaissements import recalculer_statut_paiement

    with transaction.atomic():
        locked_facture = Facture.objects.select_for_update().get(
            pk=note_debit.facture_id)
        nd = NoteDebit.objects.select_for_update().get(pk=note_debit.pk)
        existant = nd.avoirs_annulation.filter(
            statut=Avoir.Statut.EMISE).order_by('id').first()
        if existant is not None:
            return existant, False
        if nd.statut != NoteDebit.Statut.EMISE:
            raise AvoirRefuse(
                'Seule une note de débit émise peut être annulée.')
        company = nd.company or locked_facture.company
        nd_lignes = list(nd.lignes.all())

        def _create(ref):
            avoir = Avoir.objects.create(
                company=company, reference=ref, facture=locked_facture,
                client=nd.client, statut=Avoir.Statut.EMISE,
                motif=f'Annulation de la note de débit {nd.reference}',
                taux_tva=nd.taux_tva, remise_globale=nd.remise_globale,
                note_debit=nd, created_by=user)
            for ligne in nd_lignes:
                LigneAvoir.objects.create(
                    avoir=avoir, produit_id=ligne.produit_id,
                    designation=ligne.designation, quantite=ligne.quantite,
                    prix_unitaire=ligne.prix_unitaire, remise=ligne.remise,
                    taux_tva=ligne.taux_tva)
            if (nd.montant_ttc is not None or not nd_lignes
                    or nd.ventilation_tva):
                # Montants FIGÉS de la ND (saisie par montant, paniers TVA) :
                # l'avoir porte exactement les mêmes.
                avoir.montant_ht = nd.total_ht
                avoir.montant_tva = nd.total_tva
                avoir.montant_ttc = nd.total_ttc
                avoir.ventilation_tva = nd.ventilation_tva
                avoir.save(update_fields=[
                    'montant_ht', 'montant_tva', 'montant_ttc',
                    'ventilation_tva'])
            return avoir

        avoir = create_numbered(Avoir, company, 'avoir', _create)
        activity.log_facture_avoir(locked_facture, user, avoir)
        FactureActivity.objects.create(
            company=company, facture=locked_facture, user=user,
            kind=FactureActivity.Kind.MODIFICATION,
            field='note_debit', field_label='Note de débit',
            old_value=nd.reference, new_value=avoir.reference,
            body=(f"Note de débit {nd.reference} annulée par l'avoir "
                  f"{avoir.reference} ({avoir.total_ttc} MAD TTC)."))
        avoir_cree.send(sender=Avoir, instance=avoir, company=company)
        recalculer_statut_paiement(
            locked_facture, user=user, source='annulation_note_debit')
    return avoir, True
