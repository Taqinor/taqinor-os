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

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


def _guard_periode_emission(facture):
    """AUD101 — refuse l'émission d'une facture datée dans une période
    comptable CLÔTURÉE (YLEDG3/FG115).

    Réplique EXACTEMENT la garde des vues (``FactureViewSet.
    _guard_periode_verrouillee``) mais côté SERVICE, pour que les chemins qui
    n'ont pas de vue (POS, contrats, échéancier, Celery) en héritent aussi.
    Import function-local de ``apps.compta.services`` — cross-app services
    autorisé, jamais un import de ``apps.compta.models``. Société sans app
    compta / sans période verrouillée = garde silencieuse."""
    from django.core.exceptions import ValidationError as DjangoValidationError
    try:
        from apps.compta.services import verifier_facture_modifiable
    except Exception:  # noqa: BLE001 — compta absent = no-op
        return
    try:
        verifier_facture_modifiable(facture)
    except DjangoValidationError as exc:
        raise EmissionRefusee(
            exc.messages[0] if exc.messages else str(exc))


def emettre_facture(facture, *, user=None, source='', exiger_lignes=False,
                    verifier_credit=True):
    """AUD101 — LE SERVICE UNIQUE D'ÉMISSION d'une ``ventes.Facture``.

    AUCUN autre site du domaine ventes ne doit poser ``Facture.Statut.EMISE``
    (test de parité : ``apps/ventes/tests/test_aud101_emission_unique.py``).
    Avant ce service, CINQ chemins basculaient une facture en ÉMISE en silence
    — le bulk ``action=emettre``, la facturation de pénalités, la tranche
    d'échéancier (le chemin acompte→matériel→solde du parcours solaire), la
    facture « classique » consommée par POS/e-commerce/immobilier et la
    consolidation multi-devis. Aucun ne passait par le verrou de période,
    aucun n'appelait le blocage crédit, aucun n'émettait ``facture_emise`` :
    ces factures n'atteignaient donc JAMAIS le grand livre (``compta`` ne
    comptabilise que sur événement, ``apps/compta/receivers.py``).

    Ce que le service fait, dans cet ordre (les REFUS d'abord, pour qu'un
    appelant qui l'enveloppe dans ``transaction.atomic()`` n'écrive rien) :

      1. refuse une facture ANNULÉE ou déjà PAYÉE ;
      2. ``exiger_lignes`` (chemin écran) : refuse une facture vide ;
      3. verrou de période comptable (YLEDG3) ;
      4. blocage crédit dur XFAC28 (``verifier_credit_hold``) — EXEMPTION
         explicite via ``verifier_credit=False`` pour la vente comptoir
         intégralement réglée à l'acte : le hold protège l'encours, il n'a
         aucune raison de refuser du cash immédiat ;
      5. workflow de revue XFAC18 (valideur ≠ créateur, anomalies) ;
      6. dérivation de l'échéance depuis les conditions client (XFAC23), sans
         jamais écraser une échéance saisie ;
      7. pose ``EMISE`` + ``save()`` ;
      8. émet ``facture_emise`` EXACTEMENT une fois.

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

    _guard_periode_emission(facture)

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
    from decimal import Decimal, ROUND_HALF_UP
    from apps.stock.services import (
        mouvement_type_sortie, record_stock_movement,
        sortie_exists_for_reference,
    )
    from apps.ventes.models import BonCommande

    reference = devis.reference

    # Déjà réservé pour ce devis (tranche antérieure de l'échéancier) → no-op.
    if sortie_exists_for_reference(company, reference):
        return False

    # Un BC livré a déjà consommé le stock de ce devis → ne pas re-décompter.
    if BonCommande.objects.filter(
            devis=devis, statut=BonCommande.Statut.LIVRE).exists():
        return False

    moved = False
    for ligne in devis.lignes.select_related('produit'):
        # XSAL5/XSAL14 — ne réserve QUE les lignes produit effectives : pas les
        # options non activées ni les lignes de section/note (sans produit).
        if not ligne.compte_dans_totaux:
            continue
        produit = ligne.produit
        if produit is None:
            continue
        produit.refresh_from_db()
        # Même règle que la livraison BC (ERR15) : on arrondit au plus proche
        # (HALF_UP) au lieu de tronquer, le registre de stock étant en entiers.
        qte = int(Decimal(ligne.quantite).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP))
        if qte <= 0:
            continue
        qte_avant = produit.quantite_stock
        qte_apres = qte_avant - qte
        if qte_apres < 0:
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
            note=f'Facturation directe — devis {reference}',
            created_by=user,
        )
        moved = True
    return moved


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
                        taux_tva=Decimal('20')):
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
    """
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

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


# ── XPRJ4 — Facture d'acompte pour une situation de travaux (décompte BTP) ───

def creer_facture_acompte_situation(*, company, client, user, libelle,
                                    montant_periode_ht,
                                    retenue_garantie_pct=None,
                                    taux_tva=Decimal('20')):
    """XPRJ4 — Crée une Facture BROUILLON d'ACOMPTE pour une situation de
    travaux (décompte progressif BTP).

    Fonction FINE sanctionnée pour ``gestion_projet.services`` (frontière
    cross-app, CLAUDE.md) : reçoit le montant HT DÉJÀ calculé de la PÉRIODE
    (cumulé − antérieur, agrégé côté appelant sur toutes les lignes de la
    situation) et une retenue de garantie optionnelle DÉDUITE du montant
    facturé (le taux, pas le suivi de sa libération — qui vit dans
    ``contrats``, jamais importé ici). Statut BROUILLON + ``type_facture``
    ACOMPTE (chaîne standard devis→factures, réutilisée ici sans devis source).
    Numérotation via ``apps/ventes/utils/references.py`` (jamais
    ``count()+1``). Renvoie la ``Facture`` créée.
    """
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    montant_periode_ht = Decimal(montant_periode_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    rg_pct = Decimal(retenue_garantie_pct or 0)
    montant_rg = (montant_periode_ht * rg_pct / 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_ht_net = montant_periode_ht - montant_rg
    montant_tva = (montant_ht_net * taux_tva / 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_ttc = montant_ht_net + montant_tva

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.ACOMPTE,
            taux_tva=taux_tva,
            montant_ht=montant_ht_net,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            libelle=libelle,
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)
    logger.info(
        'XPRJ4: facture acompte situation %s créée (company %s, montant HT '
        'net %s, RG %s%%)',
        facture.reference, company.id, montant_ht_net, rg_pct)
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
# Thin service exposé pour apps.compta (frontière cross-app, CLAUDE.md) :
# compta connaît le montant/la marge déjà calculés côté frais, jamais les
# détails de facturation — il pousse juste des lignes sur une facture
# EXISTANTE du client. Un produit générique « Frais refacturés » (service,
# sans stock) est créé une fois par société (idempotent) pour porter ces
# lignes, à l'image du produit catalogue utilisé pour les lignes classiques.

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
    'taux_tva'?}`` (montant déjà majoré de la marge, calculé côté appelant —
    ``apps.compta``). Chaque ligne devient une ``LigneFacture`` (quantité=1,
    prix_unitaire=montant_ht) rattachée au produit générique « Frais
    refacturés » de la société de la facture ; les totaux de la facture sont
    recalculés. Renvoie la liste des ``LigneFacture`` créées. Ne vérifie PAS
    l'anti-doublon (fait côté appelant, sur les frais eux-mêmes)."""
    from apps.ventes.models import LigneFacture

    if not lignes:
        return []
    produit = _produit_frais_refactures(facture.company)
    creees = []
    for ligne in lignes:
        creees.append(LigneFacture.objects.create(
            facture=facture,
            produit=produit,
            designation=ligne.get('designation', '') or _PRODUIT_FRAIS_REFACTURES_NOM,
            quantite=Decimal('1'),
            prix_unitaire=Decimal(ligne.get('montant_ht') or 0),
            taux_tva=ligne.get('taux_tva'),
        ))
    _recalculer_totaux_facture(facture)
    return creees


def _recalculer_totaux_facture(facture):
    """Recalcule les totaux HT/TVA/TTC d'une facture depuis ses lignes.

    Réutilisé par XACC28 après ajout de lignes de frais refacturés — même
    logique de sommation que les autres chemins de création de ligne (taux
    TVA par ligne si renseigné, sinon le taux global de la facture)."""
    total_ht = Decimal('0')
    total_tva = Decimal('0')
    for ligne in facture.lignes.all():
        ht_ligne = ligne.total_ht
        taux = ligne.taux_tva if ligne.taux_tva is not None else facture.taux_tva
        total_ht += ht_ligne
        total_tva += (ht_ligne * Decimal(taux or 0) / Decimal('100'))
    facture.montant_ht = total_ht.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    facture.montant_tva = total_tva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    facture.montant_ttc = facture.montant_ht + facture.montant_tva
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
