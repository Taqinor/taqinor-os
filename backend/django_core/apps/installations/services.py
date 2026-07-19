"""
Création d'un chantier À PARTIR D'UN DEVIS — pré-remplissage + anti-doublon.

Le chantier hérite : client, adresse du SITE (depuis le lead, éditable ensuite),
puissance (depuis l'étude du devis sinon la taille souhaitée du lead),
raccordement GELÉ (depuis le lead), type d'installation (depuis le devis).
Référence sans collision via l'utilitaire commun (jamais count()+1).
"""
from apps.ventes.utils.references import create_with_reference
from .models import (
    Installation, ChecklistTemplate, ChecklistEtapeModele,
    ChantierChecklistItem, StageModele, StockReservation,
    DemandeTransfert,
)


def default_installer_for(company):
    """Installateur (technicien) par défaut configuré pour la société (N66).

    Renvoie l'utilisateur paramétré dans CompanyProfile.default_installer, ou
    None si rien n'est configuré (comportement actuel : repli sur le créateur).
    """
    if company is None:
        return None
    try:
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company)
        return prof.default_installer if prof else None
    except Exception:
        return None


# ── ZSTK11 — méthode de réservation du stock (réglage société) ─────────────
# Défaut 'confirmation' = comportement actuel byte-identique (réservation
# semée à la création du chantier). 'manuelle' = SEUL le déclencheur devient
# conditionnel ; le service `seed_reservations` reste inchangé et n'est
# jamais dupliqué.
METHODE_RESERVATION_MANUELLE = 'manuelle'


def methode_reservation_stock(company):
    """Valeur configurée `CompanyProfile.methode_reservation_stock` pour la
    société ('confirmation' par défaut — comportement historique si le
    profil est absent ou en erreur)."""
    if company is None:
        return 'confirmation'
    try:
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company)
        return getattr(prof, 'methode_reservation_stock', 'confirmation') \
            if prof else 'confirmation'
    except Exception:  # pragma: no cover - défensif
        return 'confirmation'


# Étapes de checklist d'exécution par défaut (N4). `capture_serie` marque les
# étapes où l'on relève des n° de série (N9). Toutes « système » (protégées).
DEFAULT_CHECKLIST_ETAPES = [
    ('materiel_recu', 'Matériel reçu', False),
    ('structure_posee', 'Structure posée', False),
    ('panneaux_poses', 'Panneaux posés', True),
    ('onduleur_raccorde', 'Onduleur raccordé', True),
    ('mise_en_service', 'Mise en service', False),
    ('photos_prises', 'Photos prises', False),
    ('pv_reception_signe', 'PV de réception signé', False),
]

# N74 — nom du template de repli, sélectionné quand aucun template ne
# correspond au type d'installation du chantier.
DEFAULT_TEMPLATE_NOM = 'Défaut'


def ensure_default_template(company):
    """N74 — garantit l'existence du template « Défaut » de la société et qu'il
    porte les étapes de checklist d'aujourd'hui (idempotent, additif).

    Préserve le comportement historique : si la société a déjà des étapes
    « orphelines » (template=NULL, amorcées avant N74), on les RATTACHE au
    template « Défaut » plutôt que d'en créer de nouvelles — la checklist d'un
    chantier reste donc identique. Sinon on amorce les étapes par défaut sous
    ce template. Renvoie le template « Défaut »."""
    if company is None:
        return None
    # Le « Défaut » canonique est le template PROTÉGÉ (un seul par société).
    # On le cible par `protege=True` pour ne jamais le confondre avec un
    # éventuel template utilisateur sans type d'installation.
    template = ChecklistTemplate.objects.filter(
        company=company, protege=True).order_by('ordre', 'id').first()
    if template is None:
        template = ChecklistTemplate.objects.create(
            company=company, type_installation=None,
            nom=DEFAULT_TEMPLATE_NOM, ordre=0, protege=True, actif=True)
    # Rattache les étapes historiques (sans template) au template « Défaut ».
    orphelines = ChecklistEtapeModele.objects.filter(
        company=company, template__isnull=True)
    if orphelines.exists():
        orphelines.update(template=template)
    # Aucune étape sous le Défaut (ni rattachée ni amorcée) → on amorce les
    # étapes système par défaut. Idempotent : ne touche rien si déjà présent.
    if not template.etapes.exists():
        for i, (cle, libelle, capture) in enumerate(DEFAULT_CHECKLIST_ETAPES):
            ChecklistEtapeModele.objects.get_or_create(
                company=company, template=template, cle=cle,
                defaults={'libelle': libelle, 'ordre': i,
                          'capture_serie': capture, 'protege': True})
    return template


def seed_checklist_etapes(company):
    """Amorce le template « Défaut » et ses étapes par défaut (idempotent,
    additif). Conservé pour l'amorçage à l'affichage des Paramètres (N4)."""
    ensure_default_template(company)


def template_for_installation(installation):
    """N74 — template de checklist auto-sélectionné pour un chantier :
    celui (actif) dont `type_installation` correspond au type du chantier ;
    sinon le template « Défaut » (actif), sinon n'importe quel « Défaut ».

    Garantit toujours un template « Défaut » avec ses étapes (comportement
    historique préservé pour un chantier sans type spécifique)."""
    company = installation.company
    if company is None:
        return None
    default = ensure_default_template(company)
    type_install = installation.type_installation
    if type_install:
        match = ChecklistTemplate.objects.filter(
            company=company, type_installation=type_install, actif=True
        ).order_by('ordre', 'id').first()
        if match is not None:
            return match
    return default


def ensure_checklist_items(installation):
    """Matérialise les étapes de checklist d'un chantier depuis le template
    auto-sélectionné par son type d'installation (N74) — création paresseuse,
    sans doublon. À défaut de template typé, c'est le template « Défaut » (donc
    les étapes d'aujourd'hui) : comportement préservé. Renvoie la liste
    ordonnée des items du chantier."""
    company = installation.company
    template = template_for_installation(installation)
    existing = {it.cle for it in installation.checklist.all()}
    modeles = ChecklistEtapeModele.objects.filter(
        company=company, actif=True)
    if template is not None:
        modeles = modeles.filter(template=template)
    for m in modeles:
        if m.cle not in existing:
            ChantierChecklistItem.objects.create(
                company=company, installation=installation, cle=m.cle,
                libelle=m.libelle, ordre=m.ordre, capture_serie=m.capture_serie)
    return list(installation.checklist.all())


def _devis_bon_commande(devis):
    """Le bon de commande lié au devis, ou None (reverse one-to-one)."""
    try:
        return devis.bon_commande
    except Exception:
        return None


def _puissance_from(devis, lead):
    params = devis.etude_params or {}
    for key in ('puissance_kwc', 'puissance_installee_kwc', 'puissance'):
        val = params.get(key)
        if val:
            return val
    if lead is not None and lead.taille_souhaitee_kwc:
        return lead.taille_souhaitee_kwc
    return None


def _freeze_bom(devis):
    """Nomenclature gelée depuis les lignes du devis (N1) : composants +
    quantités, pour le résumé système et la base parc. Ignore les lignes
    libres (sans produit catalogue).

    A3 — pour un devis à deux options accepté, ne gèle QUE les lignes de
    l'option retenue (batterie exclue/incluse selon le choix) ; un devis à
    option unique garde toutes ses lignes (comportement inchangé)."""
    bom = []
    try:
        from apps.ventes.utils.options import option_lines
        lignes = option_lines(devis)
    except Exception:
        return bom
    for ligne in lignes:
        produit = getattr(ligne, 'produit', None)
        try:
            qte = float(ligne.quantite)
        except (TypeError, ValueError):
            qte = None
        bom.append({
            'produit_id': produit.id if produit else None,
            'designation': getattr(ligne, 'designation', None)
            or (produit.nom if produit else ''),
            'quantite': qte,
            'marque': getattr(produit, 'marque', None) if produit else None,
        })
    return bom


def create_installation_from_devis(devis, user, company):
    """Retourne (installation, created).

    IDEMPOTENT : si un chantier existe déjà pour ce devis, on le RETOURNE tel
    quel (created=False) sans en créer un second. C'est ce garde-fou qui rend
    sûre l'auto-création sur l'événement ``devis_accepted`` (cf.
    ``apps/installations/receivers.py``) : ré-accepter un devis ou ré-émettre
    l'événement ne duplique jamais le chantier. Le chantier porte la société du
    devis (``company``), jamais une valeur issue d'une requête.
    """
    # Ce service est câblé au signal PARTAGÉ ``devis_accepted`` : un émetteur
    # d'un autre domaine (ex. la séquence d'inscription XMKT1) peut envoyer un
    # objet devis MINIMAL non persisté (sans pk). Un chantier ne peut exister
    # que pour un vrai devis enregistré — on ignore proprement le stub plutôt
    # que de laisser ``filter(devis=<objet non-modèle>)`` lever un TypeError.
    if getattr(devis, 'pk', None) is None:
        return None, False
    existing = Installation.objects.filter(
        devis=devis, company=company).first()
    if existing is not None:
        return existing, False

    lead = devis.lead
    type_install = devis.mode_installation or (
        lead.type_installation if lead else None)
    # Le lead peut porter 'commercial' (taxonomie CRM) ; le chantier ne connaît
    # que residentiel/industriel/agricole → on rabat 'commercial' sur industriel.
    if type_install == 'commercial':
        type_install = Installation.TypeInstallation.INDUSTRIEL
    valid_types = set(Installation.TypeInstallation.values)
    if type_install not in valid_types:
        type_install = None

    raccordement = lead.raccordement if lead else None
    if raccordement not in set(Installation.Raccordement.values):
        raccordement = None

    # N43 — régime loi 82-21 proposé comme DÉFAUT MODIFIABLE depuis la
    # puissance (seuils éditables en Paramètres). Reste 'non_concerne' si la
    # puissance est inconnue ; l'utilisateur peut toujours le changer ensuite.
    from .regime import suggest_for_company
    regime_suggere = suggest_for_company(
        _puissance_from(devis, lead), company)

    # Installateur par défaut (N66) : celui configuré en Paramètres, sinon le
    # créateur du chantier (comportement actuel). « Signé » est le 1er jalon de
    # l'entonnoir N1 ; la date de signature reprend la date d'acceptation du
    # devis quand elle existe.
    date_signature = getattr(devis, 'date_acceptation', None) or None
    installer = default_installer_for(company) or user

    def _create(ref):
        return Installation.objects.create(
            reference=ref,
            company=company,
            client=devis.client,
            devis=devis,
            bon_commande=_devis_bon_commande(devis),
            lead=lead,
            site_adresse=(lead.adresse if lead else None),
            site_ville=(lead.ville if lead else None),
            gps_lat=(lead.gps_lat if lead else None),
            gps_lng=(lead.gps_lng if lead else None),
            puissance_installee_kwc=_puissance_from(devis, lead),
            raccordement=raccordement,
            type_installation=type_install,
            regime_8221=regime_suggere,
            statut=Installation.Statut.SIGNE,
            date_signature=date_signature,
            bom=_freeze_bom(devis),
            technicien_responsable=installer,
            created_by=user,
        )

    inst = create_with_reference(Installation, 'CHT', company, _create)
    # N14/ZSTK11 — réserve le stock des SKU de la nomenclature gelée (robuste
    # si le BOM est vide : aucune réservation, aucun plantage) — SEULEMENT en
    # mode 'confirmation' (défaut, byte-identique). En mode 'manuelle', le
    # déclencheur devient conditionnel : un bouton explicite
    # (`reserver-stock`) appelle le MÊME service, aucune logique dupliquée.
    if methode_reservation_stock(company) != METHODE_RESERVATION_MANUELLE:
        seed_reservations(inst)
    # VX213 (a) — handoff AVAL : le plus gros transfert de l'entreprise
    # (chantier assigné à un technicien) n'est plus silencieux. Notify UNIQUEMENT
    # à la création (created=True) ; ré-accepter le devis retourne le chantier
    # existant (created=False) plus haut sans repasser ici — pas de doublon.
    _notifier_chantier_assigne(inst, inst.technicien_responsable)
    return inst, True


def _notifier_chantier_assigne(inst, technicien):
    """VX213 (a)/(b) — notifie (best-effort, ne lève jamais) le technicien
    assigné à un chantier (création depuis devis, ou réassignation). No-op si
    aucun technicien. La société est celle du chantier (jamais d'une requête)."""
    if technicien is None or not getattr(technicien, 'pk', None):
        return
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
        client_nom = getattr(getattr(inst, 'client', None), 'nom', '') or ''
        titre = f"Nouveau chantier assigné — {inst.reference}"
        corps = (f"Le chantier « {inst.reference} »"
                 + (f" (client : {client_nom})" if client_nom else '')
                 + " vous est assigné.")
        notify(
            technicien, EventType.CHANTIER_ASSIGNE, titre,
            body=corps, link=f'/installations?installation={inst.pk}',
            company=inst.company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── N14 — Réservation de stock sur chantier → consommation à « Installé » ─────
# La réservation ENGAGE le stock (le « disponible » d'un produit en tient
# compte) sans le décrémenter. Au passage à « Installé » la réservation est
# CONSOMMÉE (un seul MouvementStock SORTIE par SKU, idempotent). À
# l'annulation/clôture, la réservation NON consommée est LIBÉRÉE. On RÉUTILISE
# le mécanisme de mouvement de stock existant (MouvementStock SORTIE).

def _bom_quantities(installation):
    """Quantités requises par produit (entier ≥ 1) depuis la nomenclature gelée
    du chantier (`Installation.bom`). Ignore les lignes sans produit catalogue
    et les quantités nulles/illisibles. Renvoie {produit_id: quantite}."""
    besoins = {}
    for ligne in (installation.bom or []):
        if not isinstance(ligne, dict):
            continue
        produit_id = ligne.get('produit_id')
        if not produit_id:
            continue
        try:
            qte = int(round(float(ligne.get('quantite') or 0)))
        except (TypeError, ValueError):
            continue
        if qte <= 0:
            continue
        besoins[produit_id] = besoins.get(produit_id, 0) + qte
    return besoins


def seed_reservations(installation):
    """N14 — réserve le stock des SKU de la nomenclature gelée du chantier.

    Idempotent et additif : une réservation par (chantier, produit), créée ou
    mise à jour à la quantité du BOM. Ne touche JAMAIS une réservation déjà
    CONSOMMÉE (le stock a déjà été décrémenté). Robuste au BOM vide (ne crée
    rien). Renvoie la liste des réservations actives du chantier."""
    from apps.stock.selectors import valid_produit_ids
    company = installation.company
    besoins = _bom_quantities(installation)
    valid_ids = valid_produit_ids(company, list(besoins)) if besoins else set()
    for produit_id, qte in besoins.items():
        if produit_id not in valid_ids:
            continue
        resa, created = StockReservation.objects.get_or_create(
            installation=installation, produit_id=produit_id,
            defaults={'company': company, 'quantite': qte})
        if not created and not resa.consomme:
            # Réaligne la quantité réservée sur le BOM (réservation non encore
            # consommée). Une réservation consommée reste figée.
            changed = []
            if resa.quantite != qte:
                resa.quantite = qte
                changed.append('quantite')
            if not resa.active:
                resa.active = True
                changed.append('active')
            if resa.company_id is None:
                resa.company = company
                changed.append('company')
            if changed:
                resa.save(update_fields=changed)
    return list(installation.reservations.filter(active=True))


def consume_reservations(installation, user):
    """N14 — consomme les réservations du chantier au passage à « Installé ».

    Pour chaque réservation ACTIVE non encore consommée, crée UN MouvementStock
    SORTIE (mécanisme de stock existant) et décrémente `Produit.quantite_stock`.
    IDEMPOTENT : le drapeau `consomme` verrouille — repasser par « Installé » ne
    crée aucun mouvement supplémentaire. Renvoie le nombre de SKU consommés."""
    from django.db import transaction
    from django.utils import timezone
    from apps.stock.selectors import lock_produit
    from apps.stock.services import (
        mouvement_type_sortie, record_stock_movement,
    )

    consumed = 0
    with transaction.atomic():
        reservations = (
            StockReservation.objects
            .select_for_update()
            .filter(installation=installation, active=True, consomme=False)
            .select_related('produit')
        )
        for resa in reservations:
            if resa.quantite <= 0:
                # Rien à sortir : on marque consommée pour ne pas la rejouer.
                resa.consomme = True
                resa.date_consommation = timezone.now()
                resa.save(update_fields=['consomme', 'date_consommation'])
                continue
            produit = lock_produit(resa.produit_id)
            qte_avant = produit.quantite_stock
            # ERR80 — garde plancher : ne pilote jamais le stock en négatif. On
            # sort au plus le stock en main (borné à zéro), comme la
            # réconciliation terrain et les pièces SAV.
            qte_sortie = min(resa.quantite, qte_avant) if qte_avant > 0 else 0
            qte_apres = qte_avant - qte_sortie
            record_stock_movement(
                company=installation.company, produit=produit,
                type_mouvement=mouvement_type_sortie(),
                quantite=qte_sortie,
                quantite_avant=qte_avant, quantite_apres=qte_apres,
                reference=installation.reference,
                note=f'Consommation chantier {installation.reference}',
                created_by=user)
            resa.consomme = True
            resa.date_consommation = timezone.now()
            resa.save(update_fields=['consomme', 'date_consommation'])
            consumed += 1
    return consumed


def release_reservations(installation):
    """N14 — libère les réservations NON consommées du chantier (annulation /
    clôture). Une réservation consommée n'est jamais touchée (le stock a déjà
    été sorti). Renvoie le nombre de réservations libérées."""
    return (StockReservation.objects
            .filter(installation=installation, active=True, consomme=False)
            .update(active=False))


# ── YSTCK4 — retour chantier : matériel non posé rapporté au dépôt ─────────
# La consommation (N14/F11) est à SENS UNIQUE : rien ne permettait de faire
# remonter le surplus non installé vers le dépôt. `RetourMateriel`/
# `RetourMaterielLigne` matérialisent le blueprint « retour = mouvement
# ENTRÉE référencé à la sortie d'origine, plafonné à ce qui a RÉELLEMENT été
# sorti pour ce chantier, jamais un ajustement positif libre ».

def _quantite_sortie_chantier(installation, produit_id):
    """Quantité TOTALE réellement sortie pour ce chantier pour ce produit :
    somme des `ConsommationLigne.quantite_utilisee` validées (stock_applique)
    de TOUTES les interventions du chantier (F11 — la seule source qui bouge
    réellement le stock ; la réservation N14 estimée n'en fait pas partie)."""
    from decimal import Decimal
    from django.db.models import Sum
    from .models import ConsommationLigne
    total = (
        ConsommationLigne.objects
        .filter(consommation__intervention__installation=installation,
                produit_id=produit_id, stock_applique=True)
        .aggregate(total=Sum('quantite_utilisee'))['total']
    )
    return total or Decimal('0')


def _quantite_deja_retournee(installation, produit_id):
    """Quantité déjà retournée (retours VALIDÉS uniquement) pour ce produit
    sur ce chantier — un brouillon non validé ne compte pas encore."""
    from decimal import Decimal
    from django.db.models import Sum
    from .models_retour_materiel import RetourMateriel, RetourMaterielLigne
    total = (
        RetourMaterielLigne.objects
        .filter(retour__installation=installation, produit_id=produit_id,
                retour__statut=RetourMateriel.Statut.VALIDE)
        .aggregate(total=Sum('quantite'))['total']
    )
    return total or Decimal('0')


def quantite_retournable(installation, produit_id):
    """Solde encore retournable pour ce produit sur ce chantier = sorti −
    déjà retourné (jamais négatif)."""
    from decimal import Decimal
    sortie = _quantite_sortie_chantier(installation, produit_id)
    retournee = _quantite_deja_retournee(installation, produit_id)
    return max(sortie - retournee, Decimal('0'))


def valider_retour_materiel(retour, user):
    """YSTCK4 — valide un retour BROUILLON : pour chaque ligne {produit,
    quantité}, refuse si la quantité dépasse le solde retournable (sorti −
    déjà retourné), puis poste UN `MouvementStock` ENTREE référencé
    `RETOUR-<reference-chantier>` (idempotent via `stock_applique`).
    Lève ValueError si une ligne dépasse le retournable. Renvoie le nombre de
    lignes appliquées au stock."""
    from decimal import Decimal
    from django.db import transaction
    from apps.stock.selectors import lock_produit
    from apps.stock.services import (
        mouvement_type_entree, record_stock_movement,
    )
    from .models_retour_materiel import RetourMateriel

    if retour.statut == RetourMateriel.Statut.VALIDE:
        raise ValueError('Retour déjà validé.')

    installation = retour.installation
    lignes = list(retour.lignes.select_related('produit').all())
    for ligne in lignes:
        if ligne.produit_id is None:
            continue
        qte = ligne.quantite or Decimal('0')
        retournable = quantite_retournable(installation, ligne.produit_id)
        if qte > retournable:
            raise ValueError(
                f'Quantité retournée ({qte}) supérieure à la quantité '
                f'réellement sortie pour ce chantier ({retournable}) pour '
                f'« {ligne.designation or ligne.produit_id} ».')

    applied = 0
    with transaction.atomic():
        for ligne in lignes:
            if ligne.stock_applique or ligne.produit_id is None:
                continue
            qte = ligne.quantite or Decimal('0')
            if qte <= 0:
                ligne.stock_applique = True
                ligne.save(update_fields=['stock_applique'])
                continue
            produit = lock_produit(ligne.produit_id)
            qte_avant = produit.quantite_stock
            qte_apres = qte_avant + qte
            record_stock_movement(
                company=installation.company, produit=produit,
                type_mouvement=mouvement_type_entree(),
                quantite=qte,
                quantite_avant=qte_avant, quantite_apres=qte_apres,
                reference=f'RETOUR-{installation.reference}',
                note=f'Retour chantier {installation.reference}',
                created_by=user)
            ligne.stock_applique = True
            ligne.save(update_fields=['stock_applique'])
            applied += 1
        retour.statut = RetourMateriel.Statut.VALIDE
        retour.valide_par = user
        from django.utils import timezone as _tz
        retour.valide_le = _tz.now()
        retour.save(update_fields=['statut', 'valide_par', 'valide_le'])
    return applied


def reserver_stock_recu_pour_chantier(*, reception):
    """YPROC10 — à la confirmation d'une réception fournisseur dont le BCF
    porte un ``chantier_origine`` (distinct de la destination de livraison
    XPUR23), crée/complète les ``StockReservation`` actives du chantier pour
    les produits/quantités REÇUS sur cette réception.

    Plafonné à la quantité COMMANDÉE sur la ligne de BCF (posée par
    ``draft_bcf_for_shortfall`` = le manque au moment du brouillon — jamais de
    sur-réservation même si la réception dépasse ce qui était commandé) et à
    la quantité cumulée réellement REÇUE sur cette ligne
    (``ligne_commande.quantite_recue``, déjà tenue à jour par
    ``confirm_reception_fournisseur`` et stable entre deux appels : ne
    dépend PAS du stock live, qu'on ne recalcule donc jamais ici). La
    réservation est donc une fonction PURE de données déjà persistées → un
    rejeu du même événement (ou une confirmation partielle suivie d'une
    autre) retombe toujours sur la même valeur plafond, jamais une addition
    en boucle. No-op silencieux si le BCF n'a aucun ``chantier_origine``
    (comportement historique inchangé). Renvoie le nombre de réservations
    créées/modifiées."""
    bc = reception.bon_commande
    if bc is None or not getattr(bc, 'chantier_origine_id', None):
        return 0
    installation = bc.chantier_origine
    if installation is None:
        return 0

    # Plafond stable par produit = la quantité commandée sur CETTE ligne de
    # BCF (le manque figé au brouillon), et le « réalisé » = la quantité
    # cumulée reçue sur cette même ligne (toutes réceptions confondues).
    plafonds = {}
    recu_cumule_par_produit = {}
    for ligne in reception.lignes.select_related('ligne_commande').all():
        if ligne.produit_id is None:
            continue
        ligne_cmd = ligne.ligne_commande
        ligne_cmd.refresh_from_db()
        plafonds[ligne.produit_id] = max(
            plafonds.get(ligne.produit_id, 0), int(ligne_cmd.quantite or 0))
        recu_cumule_par_produit[ligne.produit_id] = max(
            recu_cumule_par_produit.get(ligne.produit_id, 0),
            int(ligne_cmd.quantite_recue or 0))

    if not plafonds:
        return 0

    count = 0
    for produit_id, plafond in plafonds.items():
        if plafond <= 0:
            continue
        qte_a_reserver = min(recu_cumule_par_produit.get(produit_id, 0), plafond)
        if qte_a_reserver <= 0:
            continue
        resa, created = StockReservation.objects.get_or_create(
            installation=installation, produit_id=produit_id,
            defaults={'company': installation.company,
                      'quantite': qte_a_reserver})
        if created:
            count += 1
            continue
        if resa.consomme:
            # Réservation déjà consommée : ne jamais la rouvrir ici (le
            # stock a déjà été décrémenté pour ce chantier).
            continue
        # Fonction pure du plafond : un rejeu retombe sur la même valeur
        # (jamais d'addition), une réception ultérieure ne fait que monter
        # jusqu'au plafond.
        if qte_a_reserver != resa.quantite:
            resa.quantite = qte_a_reserver
            resa.active = True
            resa.save(update_fields=['quantite', 'active'])
            count += 1
    return count


# ── YDOCF7 — Réservation de stock DEPUIS UN BonCommande (BC) ────────────────
# `bons-commande/{id}/confirmer` ne réservait rien (le stock n'était touché
# qu'à `marquer-livre`, décrément direct) : entre confirmation et livraison,
# deux BC confirmés pouvaient promettre le même stock. Ces fonctions
# réutilisent le mécanisme N14 EXISTANT (`StockReservation` — même modèle,
# mêmes gardes idempotentes) plutôt que d'en inventer un second : un BC
# rattaché à un chantier (via son devis ou directement) réserve sur CE
# chantier ; un BC sans chantier (devis pas encore accepté / BC manuel) est
# un no-op sûr (rien à réserver dessus, comportement identique à avant).
# Toujours derrière le toggle société `reserver_stock_bc` (défaut OFF) —
# l'appelant (views/bon_commande.py) vérifie le toggle avant d'appeler.

def _installation_pour_bc(bon_commande):
    """Chantier associé à ce BC — direct, sinon via son devis d'origine.
    Renvoie None si aucun chantier n'existe (BC sans chantier : no-op sûr)."""
    inst = Installation.objects.filter(bon_commande=bon_commande).first()
    if inst is not None:
        return inst
    if bon_commande.devis_id:
        inst = Installation.objects.filter(
            devis_id=bon_commande.devis_id).first()
    return inst


def _bc_quantities(bon_commande):
    """Quantités entières par produit depuis les lignes du DEVIS d'origine du
    BC (mêmes lignes que celles décrémentées par `marquer-livre`)."""
    from decimal import Decimal, ROUND_HALF_UP
    besoins = {}
    if not bon_commande.devis_id:
        return besoins
    for ligne in bon_commande.devis.lignes.all():
        if not ligne.produit_id:
            continue
        qte = int(Decimal(ligne.quantite).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP))
        if qte <= 0:
            continue
        besoins[ligne.produit_id] = besoins.get(ligne.produit_id, 0) + qte
    return besoins


def reserver_stock_depuis_bc(bon_commande):
    """YDOCF7 — réserve le stock des lignes du BC à sa CONFIRMATION.

    No-op sûr (renvoie []) si le BC n'a aucun chantier associé — un chantier
    n'existe qu'une fois le devis d'origine accepté ; un BC antérieur à cette
    étape (rare) reste un simple document sans effet sur le stock, comme
    avant ce toggle. Réutilise `StockReservation` (mêmes gardes qu'un
    chantier : idempotent, jamais deux réservations pour le même (chantier,
    produit))."""
    installation = _installation_pour_bc(bon_commande)
    if installation is None:
        return []
    besoins = _bc_quantities(bon_commande)
    if not besoins:
        return []
    from apps.stock.selectors import valid_produit_ids
    valid_ids = valid_produit_ids(installation.company, list(besoins))
    reservations = []
    for produit_id, qte in besoins.items():
        if produit_id not in valid_ids:
            continue
        resa, created = StockReservation.objects.get_or_create(
            installation=installation, produit_id=produit_id,
            defaults={'company': installation.company, 'quantite': qte})
        if not created and not resa.consomme:
            changed = []
            if resa.quantite != qte:
                resa.quantite = qte
                changed.append('quantite')
            if not resa.active:
                resa.active = True
                changed.append('active')
            if changed:
                resa.save(update_fields=changed)
        reservations.append(resa)
    return reservations


def liberer_reservation_bc(bon_commande):
    """YDOCF7 — libère les réservations du chantier du BC à son ANNULATION.

    No-op sûr si aucun chantier associé. Ne touche jamais une réservation
    déjà consommée (mécanisme `release_reservations` réutilisé tel quel)."""
    installation = _installation_pour_bc(bon_commande)
    if installation is None:
        return 0
    return release_reservations(installation)


def consommer_reservation_bc(bon_commande, user):
    """YDOCF7 — solde (consomme) les réservations du chantier du BC à sa
    LIVRAISON, au lieu d'un second décrément direct (double décrément évité :
    l'appelant, quand le toggle est ON, appelle CECI au lieu de sortir le
    stock lui-même). No-op sûr si aucun chantier associé."""
    installation = _installation_pour_bc(bon_commande)
    if installation is None:
        return 0
    return consume_reservations(installation, user)


# ── FG296 — Instanciation d'un modèle de projet sur un chantier ───────────────
# Un modèle de projet (« chantier-type ») pré-crée à la demande/signature les
# jalons standard (FG293) et complète la nomenclature gelée du chantier
# (`Installation.bom`) avec ses lignes de BoM type. IDEMPOTENT et ADDITIF :
# on ne recrée jamais un jalon de même libellé déjà présent et on n'écrase
# jamais une ligne de BoM déjà gelée pour le même produit.

def _bom_existing_keys(installation):
    """Clés produit déjà présentes dans la nomenclature gelée du chantier
    (`produit_id` non nul), pour ne jamais dupliquer une ligne."""
    keys = set()
    for ligne in (installation.bom or []):
        if isinstance(ligne, dict) and ligne.get('produit_id'):
            keys.add(ligne['produit_id'])
    return keys


def instantiate_modele_projet(installation, modele, user=None):
    """FG296 — applique un modèle de projet à un chantier.

    Crée les `JalonProjet` du modèle (date cible pré-remplie = date de base
    décalée de `offset_jours` ; base = `date_signature` du chantier, à défaut
    aujourd'hui) sans dupliquer un jalon de même libellé déjà présent, et ajoute
    les lignes de BoM type à `Installation.bom` sans écraser une ligne déjà gelée
    pour le même produit. Renvoie un dict {jalons_crees, bom_lignes_ajoutees}.

    Idempotent : ré-appliquer le même modèle ne crée aucun doublon."""
    from datetime import timedelta
    from django.utils import timezone
    from .models import JalonProjet

    company = installation.company
    base_date = installation.date_signature or timezone.localdate()

    # ── Jalons ───────────────────────────────────────────────────────────────
    existing_libelles = {
        j.libelle for j in installation.jalons.all()
    }
    jalons_crees = 0
    for mj in modele.jalons.all():
        if mj.libelle in existing_libelles:
            continue
        date_cible = None
        try:
            date_cible = base_date + timedelta(days=mj.offset_jours)
        except (TypeError, OverflowError):
            date_cible = None
        JalonProjet.objects.create(
            company=company, installation=installation,
            phase=mj.phase or None, libelle=mj.libelle, ordre=mj.ordre,
            date_cible=date_cible)
        existing_libelles.add(mj.libelle)
        jalons_crees += 1

    # ── BoM type → nomenclature gelée du chantier ───────────────────────────
    bom = list(installation.bom or [])
    existing_keys = _bom_existing_keys(installation)
    bom_ajoutees = 0
    for ml in modele.bom_lignes.all():
        produit_id = ml.produit_id
        # On déduplique sur le produit catalogue ; une ligne sans produit
        # (designation libre) est toujours ajoutée.
        if produit_id and produit_id in existing_keys:
            continue
        try:
            qte = float(ml.quantite)
        except (TypeError, ValueError):
            qte = None
        bom.append({
            'produit_id': produit_id,
            'designation': ml.designation or '',
            'quantite': qte,
            'marque': None,
        })
        if produit_id:
            existing_keys.add(produit_id)
        bom_ajoutees += 1

    if bom_ajoutees:
        installation.bom = bom
        installation.save(update_fields=['bom'])
        # Réaligne les réservations de stock sur la nomenclature enrichie.
        seed_reservations(installation)

    return {'jalons_crees': jalons_crees, 'bom_lignes_ajoutees': bom_ajoutees}


# ── FG71 — Synthèse de coût / marge par chantier (INTERNE, jamais client) ─────
# Assemble la main-d'œuvre (jours estimés/réels), le coût matériel prévu (BoM
# gelé) vs réel (consommation terrain F11), et le total du devis, en une vue de
# marge. STRICTEMENT INTERNE : s'appuie sur `Produit.prix_achat` (interdit de
# bannière sur tout document client). Endpoint réservé admin (cf. la vue).

def _dec(value):
    from decimal import Decimal, InvalidOperation
    if value is None:
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def _bom_material_cost(installation):
    """Coût matériel PRÉVU = somme(quantité BoM gelé × prix_achat catalogue).
    Les lignes sans produit catalogue sont ignorées (pas de prix d'achat)."""
    from decimal import Decimal
    from apps.stock.selectors import get_produit_scoped
    total = Decimal('0')
    detail = []
    for ligne in (installation.bom or []):
        if not isinstance(ligne, dict):
            continue
        produit_id = ligne.get('produit_id')
        if not produit_id:
            continue
        produit = get_produit_scoped(installation.company, produit_id)
        if produit is None:
            continue
        qte = _dec(ligne.get('quantite'))
        prix = _dec(getattr(produit, 'prix_achat', 0))
        cout = qte * prix
        total += cout
        detail.append({
            'produit_id': produit_id,
            'designation': ligne.get('designation') or produit.nom,
            'quantite': float(qte),
            'prix_achat': float(prix),
            'cout': float(cout),
        })
    return total, detail


def _consommation_material_cost(installation):
    """Coût matériel RÉEL = somme(quantité_utilisée × prix_achat) sur les
    réconciliations de consommation VALIDÉES (F11) des interventions du chantier.
    None si aucune réconciliation validée n'existe (→ on retombe sur le prévu)."""
    from decimal import Decimal
    lignes = []
    has_validee = False
    for interv in installation.interventions.all():
        conso = getattr(interv, 'consommation', None)
        if conso is None or not conso.valide:
            continue
        has_validee = True
        lignes.extend(conso.lignes.select_related('produit').all())
    if not has_validee:
        return None, []
    total = Decimal('0')
    detail = []
    for li in lignes:
        produit = li.produit
        prix = _dec(getattr(produit, 'prix_achat', 0)) if produit else Decimal('0')
        qte = _dec(li.quantite_utilisee)
        cout = qte * prix
        total += cout
        detail.append({
            'produit_id': li.produit_id,
            'designation': li.designation,
            'quantite_utilisee': float(qte),
            'prix_achat': float(prix),
            'cout': float(cout),
            'hors_nomenclature': li.hors_nomenclature,
        })
    return total, detail


def compute_chantier_cout(installation, tarif_jour=None):
    """FG71 — synthèse coût / marge d'un chantier (INTERNE, admin-only).

    Renvoie un dict :
      labour: jours estimés/réels + coût (si `tarif_jour` fourni, en MAD/jour) ;
      materiel: coût prévu (BoM gelé) + coût réel (consommation validée, si
        dispo) + écart ; chaque poste détaillé ;
      devis_total_ht / devis_total_ttc : le total du devis source (None sans
        devis) ;
      marge: total_ht − coût matériel (réel si dispo sinon prévu) − coût
        main-d'œuvre, + le taux (% du HT). None si le HT est inconnu.

    `Produit.prix_achat` est INTERNE : ce résultat ne doit jamais alimenter un
    document client (l'endpoint est réservé admin)."""
    from decimal import Decimal
    labour_estime = _dec(installation.labour_jours_estimes)
    labour_reel = _dec(installation.labour_jours_reels)
    tarif = _dec(tarif_jour) if tarif_jour not in (None, '') else None
    labour_cout_estime = (labour_estime * tarif) if tarif is not None else None
    labour_cout_reel = (labour_reel * tarif) if tarif is not None else None

    cout_prevu, detail_prevu = _bom_material_cost(installation)
    cout_reel, detail_reel = _consommation_material_cost(installation)
    materiel_retenu = cout_reel if cout_reel is not None else cout_prevu

    devis = installation.devis
    total_ht = None
    total_ttc = None
    if devis is not None:
        try:
            total_ht = _dec(devis.total_ht)
            total_ttc = _dec(devis.total_ttc)
        except Exception:  # pragma: no cover - défensif
            total_ht = None

    marge = None
    marge_taux = None
    if total_ht is not None:
        cout_mo = labour_cout_reel if labour_cout_reel is not None else Decimal('0')
        marge = total_ht - materiel_retenu - cout_mo
        if total_ht != 0:
            marge_taux = float(round(marge / total_ht * 100, 1))

    return {
        'installation': installation.id,
        'reference': installation.reference,
        'labour': {
            'jours_estimes': float(labour_estime),
            'jours_reels': float(labour_reel),
            'tarif_jour': float(tarif) if tarif is not None else None,
            'cout_estime': float(labour_cout_estime)
            if labour_cout_estime is not None else None,
            'cout_reel': float(labour_cout_reel)
            if labour_cout_reel is not None else None,
        },
        'materiel': {
            'cout_prevu': float(cout_prevu),
            'cout_reel': float(cout_reel) if cout_reel is not None else None,
            'cout_retenu': float(materiel_retenu),
            'source_retenue': 'reel' if cout_reel is not None else 'prevu',
            'ecart': (float(cout_reel - cout_prevu)
                      if cout_reel is not None else None),
            'lignes_prevu': detail_prevu,
            'lignes_reel': detail_reel,
        },
        'devis_total_ht': float(total_ht) if total_ht is not None else None,
        'devis_total_ttc': float(total_ttc) if total_ttc is not None else None,
        'marge': float(marge) if marge is not None else None,
        'marge_taux': marge_taux,
    }


# ── CH1 — Étapes/gates configurables du cycle de vie chantier ─────────────────
# Le cycle de vie PV INTERNATIONAL est amorcé par société (idempotent, additif),
# puis entièrement configurable par le Directeur (ajout/retrait/réordonnancement,
# bloquant/consultatif, éléments requis). L'enum historique à 7 statuts
# (`Installation.statut`) N'EST PAS supprimé : chaque étape porte le statut
# hérité correspondant (`statut_legacy`), si bien que les effets de bord
# existants (consommation du stock à « Installé », remise de garantie/parc à
# « Réceptionné ») continuent de tirer, inchangés, sur les gates mappés.

_S = Installation.Statut

# (cle, libelle, statut_legacy, bloquant, exigences) — cycle de vie PV
# international. Toutes « système » (protégées contre la suppression, mais
# désactivables/réordonnables).
DEFAULT_LIFECYCLE_GATES = [
    ('etude_site', 'Visite technique (étude de site)', _S.SIGNE, False, {}),
    ('conception', 'Conception & ingénierie', _S.SIGNE, False, {}),
    ('autorisations', 'Autorisations & dossier 82-21', _S.SIGNE, True,
     {'exige_dossier': True}),
    ('approvisionnement', 'Approvisionnement matériel', _S.MATERIEL_COMMANDE,
     True, {'exige_materiel': True}),
    ('montage_mecanique', 'Montage mécanique (structure & panneaux)',
     _S.EN_COURS, False, {}),
    ('installation_electrique', 'Installation électrique', _S.EN_COURS,
     False, {}),
    ('mise_en_service', 'Mise en service & essais (IEC 62446-1)', _S.INSTALLE,
     True, {'exige_tests': True}),
    ('inspection_raccordement', 'Inspection & raccordement réseau (PTO)',
     _S.INSTALLE, False, {}),
    ('remise_client', 'Remise au client (handover)', _S.RECEPTIONNE, True,
     {'exige_checklist': True, 'exige_series': True, 'exige_pack': True}),
    ('exploitation_maintenance', 'Exploitation & maintenance (O&M)',
     _S.CLOTURE, False, {}),
]

# Statut hérité CANONIQUE → clé de l'étape amorcée correspondante. Les statuts
# hérités hors entonnoir (a_planifier, pose…) passent d'abord par
# `Installation.canonical_statut`. Chaque statut historique mappe PROPREMENT
# sur une étape — aucun chantier existant n'est orphelin.
LEGACY_STATUT_TO_STAGE = {
    _S.SIGNE: 'etude_site',
    _S.MATERIEL_COMMANDE: 'approvisionnement',
    _S.PLANIFIE: 'montage_mecanique',
    _S.EN_COURS: 'montage_mecanique',
    _S.INSTALLE: 'mise_en_service',
    _S.RECEPTIONNE: 'remise_client',
    _S.CLOTURE: 'exploitation_maintenance',
}


def seed_stages(company):
    """CH1 — amorce le cycle de vie PV international de la société (idempotent,
    additif : ne touche jamais une étape existante — libellés, ordre, drapeaux
    et exigences édités par le Directeur sont préservés)."""
    if company is None:
        return []
    created = []
    for i, (cle, libelle, statut_legacy, bloquant, exiges) in enumerate(
            DEFAULT_LIFECYCLE_GATES):
        stage, was_created = StageModele.objects.get_or_create(
            company=company, cle=cle,
            defaults={
                'libelle': libelle, 'ordre': i, 'bloquant': bloquant,
                'statut_legacy': statut_legacy, 'protege': True,
                'actif': True, **exiges,
            })
        if was_created:
            created.append(stage)
    return created


def stages_actifs(company):
    """Étapes ACTIVES de la société, ordonnées (amorce d'abord si vide)."""
    if company is None:
        return []
    if not StageModele.objects.filter(company=company).exists():
        seed_stages(company)
    return list(StageModele.objects.filter(company=company, actif=True)
                .order_by('ordre', 'id'))


def stages_configures(company):
    """True si la société a AU MOINS une étape définie — c'est l'interrupteur
    de l'application des gates (CH2) : une société qui n'a jamais touché aux
    étapes garde EXACTEMENT le comportement historique (aucun blocage)."""
    if company is None:
        return False
    return StageModele.objects.filter(company=company, actif=True).exists()


def stage_pour_statut(company, statut):
    """Étape mappée pour un statut hérité (canonique ou non) — ou None.

    Résolution : la clé du mapping LEGACY_STATUT_TO_STAGE si l'étape existe et
    est active, sinon la PREMIÈRE étape active portant ce `statut_legacy`
    (couvre les étapes renommées/personnalisées par le Directeur)."""
    if company is None or not statut:
        return None
    canon = Installation.canonical_statut(statut)
    cle = LEGACY_STATUT_TO_STAGE.get(canon)
    if cle:
        stage = StageModele.objects.filter(
            company=company, cle=cle, actif=True).first()
        if stage is not None:
            return stage
    return (StageModele.objects
            .filter(company=company, statut_legacy=canon, actif=True)
            .order_by('ordre', 'id').first())


def etape_courante(installation):
    """Étape courante d'un chantier : son pointeur `etape` s'il est posé (et
    actif, même société), sinon l'étape DÉRIVÉE de son statut hérité — les
    chantiers d'avant CH1 fonctionnent donc sans migration de données."""
    stage = installation.etape
    if (stage is not None and stage.actif
            and stage.company_id == installation.company_id):
        return stage
    return stage_pour_statut(installation.company, installation.statut)


def sync_etape_from_statut(installation):
    """Aligne le pointeur `etape` sur le statut hérité après un changement de
    statut par l'ancien flux (PATCH statut / mise-en-service) : les deux
    couches ne divergent jamais. Sans étape configurée → no-op."""
    stage = stage_pour_statut(installation.company, installation.statut)
    if stage is not None and installation.etape_id != stage.id:
        installation.etape = stage
        installation.save(update_fields=['etape'])
    return stage


# ── FG77 — Contrôle de préparation avant pose (readiness) ─────────────────────
# Avant de lancer la pose (passage à « En cours »), rien ne vérifie la
# disponibilité matériel ni l'état du dossier loi 82-21. Ce sélecteur AVISE
# (advisory) : il agrège le manque matériel (via besoin-materiel), l'état du
# dossier réglementaire et la date de planification en une checklist + un verdict
# « prêt / non prêt » destiné à une bannière. Il ne bloque RIEN par lui-même —
# l'appel reste autorisé ; le frontend peut proposer un override-à-confirmer.

def compute_chantier_readiness(installation):
    """FG77 — état de préparation avant pose d'un chantier (lecture seule).

    Renvoie un dict :
      pret (bool) : aucun bloqueur ;
      checks : [{cle, libelle, statut('ok'|'avertissement'|'bloquant'),
                 detail}] ;
      materiel : {nb_manques, manques:[{designation, manque}]} ;
      dossier : {regime, statut, requis(bool), ok(bool)} ;
      planning : {date_pose_prevue, defini(bool)}.

    Bloqueurs (advisory) : un manque matériel ; un dossier réglementaire requis
    non encore approuvé. Avertissement : pas de date de pose planifiée."""
    from apps.stock.services import compute_besoin_materiel

    checks = []

    # ── Matériel ────────────────────────────────────────────────────────────
    besoins = compute_besoin_materiel(installation)
    manques = [
        {'designation': b['designation'], 'manque': b['manque']}
        for b in besoins if b.get('manque', 0) > 0
    ]
    nb_manques = len(manques)
    if nb_manques:
        checks.append({
            'cle': 'materiel',
            'libelle': 'Disponibilité du matériel',
            'statut': 'bloquant',
            'detail': f'{nb_manques} référence(s) en pénurie.',
        })
    else:
        checks.append({
            'cle': 'materiel',
            'libelle': 'Disponibilité du matériel',
            'statut': 'ok',
            'detail': 'Tout le matériel requis est disponible.',
        })

    # ── Dossier réglementaire loi 82-21 ──────────────────────────────────────
    regime = installation.regime_8221
    dossier_statut = installation.dossier_statut
    NON_CONCERNE = Installation.Regime8221.NON_CONCERNE
    dossier_requis = regime != NON_CONCERNE
    # « Approuvé » ou « Compteur posé » = dossier en règle pour démarrer.
    dossier_ok = (not dossier_requis) or dossier_statut in (
        Installation.DossierStatut.APPROUVE,
        Installation.DossierStatut.COMPTEUR_POSE,
    )
    if not dossier_requis:
        checks.append({
            'cle': 'dossier',
            'libelle': 'Dossier réglementaire (loi 82-21)',
            'statut': 'ok',
            'detail': 'Non concerné.',
        })
    elif dossier_ok:
        checks.append({
            'cle': 'dossier',
            'libelle': 'Dossier réglementaire (loi 82-21)',
            'statut': 'ok',
            'detail': installation.get_dossier_statut_display(),
        })
    else:
        checks.append({
            'cle': 'dossier',
            'libelle': 'Dossier réglementaire (loi 82-21)',
            'statut': 'bloquant',
            'detail': ('Dossier requis non approuvé '
                       f'({installation.get_dossier_statut_display()}).'),
        })

    # ── Planning ──────────────────────────────────────────────────────────────
    planning_defini = installation.date_pose_prevue is not None
    checks.append({
        'cle': 'planning',
        'libelle': 'Date de pose planifiée',
        'statut': 'ok' if planning_defini else 'avertissement',
        'detail': (str(installation.date_pose_prevue) if planning_defini
                   else 'Aucune date de pose prévue.'),
    })

    pret = not any(c['statut'] == 'bloquant' for c in checks)
    return {
        'installation': installation.id,
        'reference': installation.reference,
        'pret': pret,
        'checks': checks,
        'materiel': {'nb_manques': nb_manques, 'manques': manques},
        'dossier': {
            'regime': regime,
            'statut': dossier_statut,
            'requis': dossier_requis,
            'ok': dossier_ok,
        },
        'planning': {
            'date_pose_prevue': (str(installation.date_pose_prevue)
                                 if planning_defini else None),
            'defini': planning_defini,
        },
    }


# ── CH2 — Gates BLOQUANTS : application des exigences d'étape ────────────────
# Le contrôle consultatif FG77 devient APPLIQUÉ : une étape marquée `bloquant`
# ne peut pas être franchie tant que ses éléments requis (`exige_*`) ne sont
# pas réunis ET que les points d'arrêt QHSE du chantier ne sont pas levés
# (lus via `apps.qhse.selectors` — référence lâche par chantier_id, jamais
# d'import de modèle). Les étapes non bloquantes restent PUREMENT
# consultatives. INTERRUPTEUR : une société sans étape configurée
# (`stages_configures` False) garde EXACTEMENT le comportement historique.

def _gate_check_checklist(installation):
    """Toutes les étapes de checklist du chantier sont faites."""
    items = ensure_checklist_items(installation)
    manquants = [it.libelle for it in items if not it.fait]
    if manquants:
        return ("Checklist incomplète : "
                + ", ".join(manquants[:5])
                + (" …" if len(manquants) > 5 else "") + ".")
    return None


def _gate_check_photos(installation):
    """Les étapes de checklist à PHOTO OBLIGATOIRE (FG76) sont faites."""
    items = ensure_checklist_items(installation)
    manquants = [it.libelle for it in items
                 if it.photo_obligatoire and not it.fait]
    if manquants:
        return ("Photos requises manquantes : " + ", ".join(manquants) + ".")
    return None


def _gate_check_series(installation):
    """Au moins un n° de série / équipement relevé quand la checklist du
    chantier comporte une étape de capture de série (N9)."""
    items = ensure_checklist_items(installation)
    if not any(it.capture_serie for it in items):
        return None  # aucun relevé de série attendu sur ce chantier.
    if installation.equipements.exists():
        return None
    from .models import ComponentSerial
    if ComponentSerial.objects.filter(
            intervention__installation=installation).exists():
        return None
    return ("Aucun n° de série relevé (panneaux/onduleur) alors que la "
            "checklist du chantier en attend.")


def _gate_check_tests(installation):
    """CH3 — une fiche de recette IEC 62446-1 PASSÉE (conforme / conforme avec
    réserves) est requise pour franchir le gate « Mise en service ».

    Repli historique : si aucune fiche structurée n'a encore été ouverte mais
    que les champs libres `mes_*` / la date de mise en service portent déjà des
    valeurs (chantiers d'avant CH3), on considère l'essai enregistré — aucun
    chantier existant n'est bloqué rétroactivement."""
    record = getattr(installation, 'commissioning_record', None)
    if record is not None:
        if record.passe:
            return None
        return ("Fiche de recette IEC 62446-1 non conforme "
                f"({record.get_resultat_display()}).")
    # Aucune fiche structurée : repli sur la saisie historique.
    if (installation.date_mise_en_service
            or installation.mes_production_test is not None
            or installation.mes_tension is not None):
        return None
    return "Fiche de recette IEC 62446-1 non enregistrée."


def _gate_check_materiel(installation):
    """Aucune pénurie sur le besoin matériel du chantier (FG77, appliqué)."""
    from apps.stock.services import compute_besoin_materiel
    besoins = compute_besoin_materiel(installation)
    manques = [b['designation'] for b in besoins if b.get('manque', 0) > 0]
    if manques:
        return ("Matériel en pénurie : "
                + ", ".join(manques[:5])
                + (" …" if len(manques) > 5 else "") + ".")
    return None


def _gate_check_dossier(installation):
    """Dossier réglementaire loi 82-21 approuvé quand il est requis."""
    if installation.regime_8221 == Installation.Regime8221.NON_CONCERNE:
        return None
    if installation.dossier_statut in (
            Installation.DossierStatut.APPROUVE,
            Installation.DossierStatut.COMPTEUR_POSE):
        return None
    return ("Dossier loi 82-21 requis non approuvé "
            f"({installation.get_dossier_statut_display()}).")


def _gate_check_pack(installation):
    """CH4 — le pack de remise client doit assembler ses pièces OBLIGATOIRES.

    Assemble (à blanc, sans persister) l'état du pack et rejette tant qu'une
    pièce obligatoire manque. Dégrade proprement : les pièces facultatives
    absentes ne bloquent pas."""
    resume = assemble_handover_pieces(installation)
    manquantes = [p['libelle'] for p in resume['pieces']
                  if p.get('obligatoire') and not p.get('present')]
    if manquantes:
        return ("Pack de remise incomplet : " + ", ".join(manquantes) + ".")
    return None


_GATE_CHECKS = [
    ('exige_checklist', _gate_check_checklist),
    ('exige_photos', _gate_check_photos),
    ('exige_series', _gate_check_series),
    ('exige_tests', _gate_check_tests),
    ('exige_materiel', _gate_check_materiel),
    ('exige_dossier', _gate_check_dossier),
    ('exige_pack', _gate_check_pack),
]


def _gate_check_qhse(installation):
    """Points d'arrêt QHSE du chantier levés (lecture via les selectors QHSE —
    référence lâche par chantier_id, aucun import de modèle cross-app)."""
    from apps.qhse.selectors import hold_points_bloquants_pour_chantier
    points = hold_points_bloquants_pour_chantier(
        installation.company, installation.id)
    if points:
        libelles = [p['intitule'] for p in points]
        return ("Point(s) d'arrêt QHSE non levé(s) : "
                + ", ".join(libelles[:5])
                + (" …" if len(libelles) > 5 else "") + ".")
    return None


# ── QHSE22 — Gate « document unique (DUERP) requis avant la pose » ────────────
# Gate LÉGAL de sécurité : un chantier ne peut ENTRER en pose (montage physique)
# sans document unique d'évaluation des risques validé. L'exigence est appliquée
# via la FRONTIÈRE SERVICES de qhse (`services.exiger_document_unique`,
# référence lâche par chantier_id) — jamais d'import de modèle cross-app. Comme
# la porte QHSE des points d'arrêt, elle est soumise à l'interrupteur historique
# `stages_configures` (une société sans étapes configurées garde EXACTEMENT le
# comportement d'avant).

def _pose_stage_index(stages):
    """Index (dans `stages` ordonné et actif) de l'étape de POSE — le premier
    montage physique, mappé au statut hérité EN_COURS (`montage_mecanique` par
    défaut, ou son équivalent renommé/réordonné par le Directeur).

    Renvoie None si aucune étape active ne porte ce statut (gate DUERP alors
    inopérant — dégradation propre, aucun blocage inattendu)."""
    for k, stage in enumerate(stages):
        if (Installation.canonical_statut(stage.statut_legacy)
                == Installation.Statut.EN_COURS):
            return k
    return None


def _gate_check_duerp(installation):
    """QHSE22 — document unique (DUERP) validé requis AVANT la pose.

    Appel via la frontière services de qhse (`exiger_document_unique`, qui lève
    une ``ValidationError`` au message clair quand le DUERP manque). Renvoie la
    raison FRANÇAISE de blocage, ou None si le document unique lève l'exigence.
    Référence LÂCHE au chantier par son id — aucun import cross-app de modèle."""
    from django.core.exceptions import ValidationError
    from apps.qhse.services import exiger_document_unique
    try:
        exiger_document_unique(installation.company, installation.id)
    except ValidationError as exc:
        messages = getattr(exc, 'messages', None)
        return messages[0] if messages else str(exc)
    return None


def stage_gate_status(installation, stage):
    """État du gate d'une étape pour un chantier : exigences réunies ou non.

    Renvoie {cle, libelle, ordre, bloquant, satisfait, raisons[]} — les
    `raisons` sont des phrases FRANÇAISES prêtes à afficher. Les points
    d'arrêt QHSE ne sont vérifiés que pour une étape BLOQUANTE (une étape
    consultative n'interroge pas la porte QHSE)."""
    raisons = []
    for flag, check in _GATE_CHECKS:
        if not getattr(stage, flag, False):
            continue
        raison = check(installation)
        if raison:
            raisons.append(raison)
    if stage.bloquant:
        raison = _gate_check_qhse(installation)
        if raison:
            raisons.append(raison)
    return {
        'cle': stage.cle,
        'libelle': stage.libelle,
        'ordre': stage.ordre,
        'bloquant': stage.bloquant,
        'satisfait': not raisons,
        'raisons': raisons,
    }


def _gates_non_satisfaits(installation, stages, i, j):
    """Raisons des gates BLOQUANTS non satisfaits parmi stages[i:j+1] — les
    étapes franchies en avançant, DESTINATION COMPRISE : arriver à l'étape
    `j` exige que sa propre porte soit satisfaite (une mise en service n'est
    « atteinte » qu'une fois ses essais IEC 62446-1 passés, une remise client
    qu'une fois son pack assemblé). Les étapes non bloquantes ne bloquent
    jamais (consultatives)."""
    raisons = []
    # QHSE22 — GATE DUERP : franchir VERS la pose (entrer dans l'étape de
    # montage physique) exige un document unique validé. Ne se déclenche qu'au
    # PASSAGE dans l'étape de pose (i < pose ≤ j) : jamais une fois la pose déjà
    # entamée, jamais un recul. Appliqué via la frontière services qhse.
    pose_index = _pose_stage_index(stages)
    if pose_index is not None and i < pose_index <= j:
        raison = _gate_check_duerp(installation)
        if raison:
            raisons.append(raison)
    for stage in stages[i:j + 1]:
        if not stage.bloquant:
            continue
        status = stage_gate_status(installation, stage)
        if not status['satisfait']:
            raisons.extend(
                f"Étape « {stage.libelle} » : {r}"
                for r in status['raisons'])
    return raisons


def verifier_transition_statut(installation, nouveau_statut):
    """CH2 — raisons FRANÇAISES qui bloquent le passage du chantier (dans son
    état actuel) à `nouveau_statut`. Liste vide = transition autorisée.

    Ne s'applique que si la société a configuré ses étapes ; un recul de
    statut n'est jamais bloqué ; un statut non mappé n'est jamais bloqué."""
    company = installation.company
    if not stages_configures(company):
        return []
    canon_old = Installation.canonical_statut(installation.statut)
    canon_new = Installation.canonical_statut(nouveau_statut)
    if canon_old == canon_new:
        return []
    stages = stages_actifs(company)
    index = {s.id: k for k, s in enumerate(stages)}
    depuis = etape_courante(installation)
    cible = stage_pour_statut(company, nouveau_statut)
    if depuis is None or cible is None:
        return []
    i = index.get(depuis.id)
    j = index.get(cible.id)
    if i is None or j is None or j <= i:
        return []
    return _gates_non_satisfaits(installation, stages, i, j)


def verifier_avancement_etape(installation, cible):
    """CH2 — raisons qui bloquent l'avancement du chantier jusqu'à l'étape
    `cible` (StageModele). Liste vide = avancement autorisé. Un déplacement
    vers l'arrière n'est jamais bloqué."""
    stages = stages_actifs(installation.company)
    index = {s.id: k for k, s in enumerate(stages)}
    j = index.get(cible.id)
    if j is None:
        return []
    depuis = etape_courante(installation)
    i = index.get(depuis.id) if depuis is not None else 0
    if i is None:
        i = 0
    if j <= i:
        return []
    return _gates_non_satisfaits(installation, stages, i, j)


def generer_picklist_pour_chantier(installation, company, created_by=None,
                                   reference=None):
    """FG321 - genere un bon de prelevement depuis les reservations actives non
    consommees d'un chantier, une ligne par SKU, ordonnee par casier.

    Le casier de chaque produit est le casier affecte (FG319 BinAffectation) le
    plus rempli ; son `ordre` de parcours est recopie sur la ligne (les SKU sans
    casier passent en dernier). Ne touche jamais aux quantites canoniques.
    """
    from .models import (
        PickList, PickListLigne, StockReservation, BinAffectation,
    )
    pick = PickList.objects.create(
        company=company, installation=installation,
        reference=reference or '', created_by=created_by)
    reservations = StockReservation.objects.filter(
        installation=installation, active=True, consomme=False,
    ).select_related('produit')
    for resa in reservations:
        aff = BinAffectation.objects.filter(
            company=company, produit=resa.produit, bin__archived=False,
        ).select_related('bin').order_by('-quantite').first()
        bin_loc = aff.bin if aff is not None else None
        ordre = bin_loc.ordre if bin_loc is not None else 999999
        PickListLigne.objects.create(
            pick_list=pick, produit=resa.produit,
            designation=getattr(resa.produit, 'nom', None),
            bin=bin_loc, quantite_demandee=resa.quantite, ordre=ordre)
    return pick


def appliquer_landed_cost_au_stock(dossier):
    """DC38 — replie le coût débarqué (FG316) d'un dossier d'import dans le coût
    d'achat stock : pour chaque ligne de coût débarqué, écrit sa quote-part de
    frais dans `LigneBonCommandeFournisseur.frais_annexes` du BON DE COMMANDE
    d'origine, que `stock.average_cost_with_source` intègre déjà (FG67) — aucun
    champ de coût parallèle (l'intention de DC38).

    Sens de dépendance préservé : on LIT le coût débarqué via nos selectors et on
    ÉCRIT via `stock.services` (installations → stock). Nécessite un dossier lié à
    un bon de commande. Renvoie un dict {bon_commande_id, lignes_maj, lignes}.
    """
    from apps.stock.services import definir_frais_annexes_ligne_bcf
    from . import selectors

    bcf_id = dossier.bon_commande_id
    if not bcf_id:
        raise ValueError(
            "Le dossier d'import doit être rattaché à un bon de commande "
            "fournisseur pour reporter le coût débarqué dans le coût d'achat.")

    landed = selectors.landed_cost_dossier(dossier)
    lignes_maj = 0
    detail = []
    for ligne in landed['lignes']:
        produit_id = ligne.get('produit_id')
        if not produit_id:
            continue
        n = definir_frais_annexes_ligne_bcf(
            dossier.company, bcf_id, produit_id,
            ligne.get('quote_part_frais') or 0)
        lignes_maj += n
        detail.append({
            'produit_id': produit_id,
            'quote_part_frais': ligne.get('quote_part_frais'),
            'lignes_bcf_maj': n,
        })
    return {
        'bon_commande_id': bcf_id,
        'lignes_maj': lignes_maj,
        'lignes': detail,
    }


# ── CH3 — Fiche de recette IEC 62446-1 (mise en service structurée) ──────────
# La fiche remplace la saisie libre (mes_*) par un jeu d'essais discret. La
# création est idempotente (un chantier ↔ une fiche). Un relevé I-V calcule
# son écart de puissance mesuré vs attendu et lève un drapeau de défaut.

# Tolérance d'écart de puissance (%) au-delà de laquelle un string est signalé
# défectueux (dégradation/point chaud), valeur usuelle de terrain.
IV_TOLERANCE_PMAX_PCT = 5


def ensure_commissioning_record(installation, user=None):
    """Retourne la fiche de recette du chantier, en la créant si besoin
    (idempotent). La société est celle du chantier, jamais lue du corps."""
    from .models import CommissioningRecord
    record, _ = CommissioningRecord.objects.get_or_create(
        installation=installation,
        defaults={'company': installation.company, 'created_by': user})
    return record


def compute_iv_ecart(reading):
    """Calcule l'écart relatif de Pmax (mesuré vs attendu) d'un relevé I-V et
    positionne `defaut_detecte`. No-op silencieux si une valeur manque."""
    from decimal import Decimal
    mesure = reading.pmax_mesure_w
    attendu = reading.pmax_attendu_w
    if mesure is None or attendu in (None, 0):
        reading.ecart_pmax_pct = None
        reading.defaut_detecte = False
        return reading
    ecart = (Decimal(mesure) - Decimal(attendu)) / Decimal(attendu) * 100
    reading.ecart_pmax_pct = ecart.quantize(Decimal('0.01'))
    # Un écart NÉGATIF au-delà de la tolérance = sous-performance/défaut.
    reading.defaut_detecte = ecart <= Decimal(-IV_TOLERANCE_PMAX_PCT)
    return reading


# ── XFSM13 — re-vérification périodique IEC 62446-2 vs baseline de recette ──
def _pct_ecart(mesure, baseline):
    """Écart relatif (%) mesuré vs baseline, ou None si une valeur manque ou
    que la baseline est nulle (division impossible)."""
    from decimal import Decimal
    if mesure is None or baseline in (None, 0):
        return None
    ecart = (Decimal(mesure) - Decimal(baseline)) / Decimal(baseline) * 100
    return ecart.quantize(Decimal('0.01'))


def enregistrer_reverification(
        intervention, mesures, user=None, seuil_alerte_pct=20):
    """XFSM13 — enregistre une re-vérification IEC 62446-2 pour
    ``intervention`` (de type ``Intervention.Type.REVERIFICATION_62446``),
    compare ses mesures ``{isolement_mohm, continuite_terre_ohm,
    voc_par_string: {label: valeur}}`` à la baseline du chantier (la fiche de
    recette ``CommissioningRecord`` du chantier + ses ``CommissioningIVReading``),
    calcule la dérive, et crée une ``Reserve`` sur l'intervention si la dérive
    dépasse ``seuil_alerte_pct`` (défaut 20 %) sur au moins un point.

    Silencieux (dérive = None) sur tout point sans baseline correspondante —
    ne bloque jamais l'enregistrement. Idempotent au niveau caller : chaque
    appel crée une NOUVELLE re-vérification (l'historique de dérive dans le
    temps est la valeur du contrôle)."""
    from .models import CommissioningIVReading, Reserve, ReverificationMesure

    company = intervention.company
    installation = intervention.installation
    baseline = getattr(installation, 'commissioning_record', None)

    isolement_mesure = mesures.get('isolement_mohm')
    continuite_mesure = mesures.get('continuite_terre_ohm')
    isolement_ecart = _pct_ecart(
        isolement_mesure, getattr(baseline, 'isolement_mohm', None))

    voc_comparaison = []
    depassement = False
    if isolement_ecart is not None and abs(isolement_ecart) > seuil_alerte_pct:
        depassement = True

    if baseline is not None:
        baseline_iv = {
            r.string_label: r.voc_mesure_v
            for r in CommissioningIVReading.objects.filter(record=baseline)}
        for label, voc_mesure in (mesures.get('voc_par_string') or {}).items():
            voc_baseline = baseline_iv.get(label)
            ecart = _pct_ecart(voc_mesure, voc_baseline)
            voc_comparaison.append({
                'string_label': label,
                'voc_baseline_v': str(voc_baseline) if voc_baseline is not None else None,
                'voc_mesure_v': str(voc_mesure) if voc_mesure is not None else None,
                'ecart_pct': str(ecart) if ecart is not None else None,
            })
            if ecart is not None and abs(ecart) > seuil_alerte_pct:
                depassement = True

    reverif = ReverificationMesure.objects.create(
        company=company, intervention_id=intervention.id,
        record_baseline=baseline,
        isolement_mohm=isolement_mesure,
        continuite_terre_ohm=continuite_mesure,
        voc_comparaison=voc_comparaison,
        isolement_ecart_pct=isolement_ecart,
        seuil_alerte_pct=seuil_alerte_pct,
        depassement_detecte=depassement,
        observations=mesures.get('observations') or '',
        created_by=user)

    if depassement:
        reserve = Reserve.objects.create(
            company=company, intervention=intervention,
            description=(
                "Re-vérification IEC 62446-2 : dérive au-delà du seuil "
                f"({seuil_alerte_pct} %) détectée vs la recette initiale."),
            created_by=user)
        reverif.reserve_id = reserve.id
        reverif.save(update_fields=['reserve_id'])

    return reverif


# ── CH4 — Pack de remise client (handover) ───────────────────────────────────
# Le pack assemble les pièces du dossier remis au client + au vendeur en
# RÉFÉRENÇANT l'état réel du chantier (jamais de binaire stocké). Chaque pièce
# porte {type, libelle, reference, present, obligatoire}. Il DÉGRADE proprement
# quand une pièce manque (present=False plutôt qu'un plantage). Les pièces
# OBLIGATOIRES (as-built, certificat de recette, garanties, dossier 82-21 quand
# requis) sont ce que le gate « Remise au client » exige (CH2).

def assemble_handover_pieces(installation):
    """Assemble (SANS persister) la liste des pièces du pack de remise d'un
    chantier depuis son état réel. Renvoie {pieces: [...], complet: bool} —
    `complet` est True quand toutes les pièces OBLIGATOIRES sont présentes."""
    pieces = []

    # ── As-built / schémas (DocumentProjet — même app) ──
    docs = list(installation.inst_documents.all())
    schema = next((d for d in docs
                   if d.type_doc == 'schema_unifilaire'), None)
    pieces.append({
        'type': 'as_built',
        'libelle': 'Dossier as-built / schéma unifilaire',
        'reference': schema.titre if schema is not None else (
            docs[0].titre if docs else None),
        'present': bool(docs),
        'obligatoire': True,
    })

    # ── Fiches techniques (datasheets) des équipements du parc (FG70) ──
    equipements = [eq for eq in installation.equipements.all()
                   if getattr(eq, 'statut', None) != 'remplace']
    datasheets = [eq for eq in equipements
                  if getattr(getattr(eq, 'produit', None), 'description', None)]
    pieces.append({
        'type': 'datasheets',
        'libelle': 'Fiches techniques des équipements',
        'reference': f'{len(datasheets)} fiche(s)' if datasheets else None,
        'present': bool(datasheets),
        'obligatoire': False,
    })

    # ── Garanties (issues du parc SAV — FG70) ──
    garanties = [eq for eq in equipements
                 if getattr(eq, 'date_fin_garantie', None) is not None]
    pieces.append({
        'type': 'garanties',
        'libelle': 'Garanties matériel & production',
        'reference': f'{len(garanties)} équipement(s) couvert(s)'
        if garanties else None,
        'present': bool(garanties),
        'obligatoire': True,
    })

    # ── Certificat de recette IEC 62446-1 (CH3) ──
    record = getattr(installation, 'commissioning_record', None)
    recette_ok = record is not None and record.passe
    pieces.append({
        'type': 'commissioning',
        'libelle': 'Certificat de recette IEC 62446-1',
        'reference': (record.get_resultat_display()
                      if record is not None else None),
        'present': recette_ok,
        'obligatoire': True,
    })

    # ── Dossier réglementaire loi 82-21 (obligatoire seulement si requis) ──
    dossier_requis = (installation.regime_8221
                      != Installation.Regime8221.NON_CONCERNE)
    dossier_present = bool(installation.dossier_reference) or (
        installation.dossier_statut in (
            Installation.DossierStatut.APPROUVE,
            Installation.DossierStatut.COMPTEUR_POSE))
    pieces.append({
        'type': 'dossier_8221',
        'libelle': 'Dossier réglementaire loi 82-21',
        'reference': installation.dossier_reference or (
            installation.get_dossier_statut_display()
            if dossier_requis else 'Non concerné'),
        'present': (not dossier_requis) or dossier_present,
        'obligatoire': dossier_requis,
    })

    # ── Accès monitoring / application ──
    pack = getattr(installation, 'handover_pack', None)
    monitoring = getattr(pack, 'monitoring_acces', None) if pack else None
    pieces.append({
        'type': 'monitoring',
        'libelle': 'Accès monitoring / application',
        'reference': monitoring,
        'present': bool(monitoring),
        'obligatoire': False,
    })

    complet = all(p['present'] for p in pieces if p['obligatoire'])
    return {'pieces': pieces, 'complet': complet}


def generer_handover_pack(installation, user=None):
    """CH4 — assemble ET PERSISTE le pack de remise du chantier (idempotent :
    un chantier ↔ un pack ; le ré-assemblage rafraîchit les pièces). Renvoie le
    HandoverPack. Dégrade proprement : un pack incomplet est produit quand même
    (complet=False), il ne plante jamais."""
    from django.utils import timezone
    from .models import HandoverPack
    resume = assemble_handover_pieces(installation)
    pack, _ = HandoverPack.objects.get_or_create(
        installation=installation,
        defaults={'company': installation.company, 'created_by': user})
    pack.company = installation.company
    pack.pieces = resume['pieces']
    pack.complet = resume['complet']
    pack.date_generation = timezone.now()
    if not pack.titre:
        pack.titre = f'Pack de remise — {installation.reference}'
    pack.save(update_fields=[
        'company', 'pieces', 'complet', 'date_generation', 'titre'])
    return pack


# ── XMFG2 — Réservation & disponibilité des composants d'un ordre ────────────
# Même patron que StockReservation (N14, chantiers) : ENGAGE le stock sans le
# décrémenter. Seed depuis la BOM du kit à la création/confirmation de l'ordre
# (ou les lignes d'ordre XMFG6, repli BOM si absentes). Consommation marquée
# par XMFG1 (verrou d'idempotence côté backflush) ; libération à l'annulation.

def _besoin_avec_perte(quantite, taux_perte_pct):
    """XMFG11 — gonfle une quantité planifiée par le taux de perte attendu (%).
    Arrondi au SUPÉRIEUR (on ne sous-réserve jamais). Défaut 0 = inchangé."""
    from decimal import Decimal, ROUND_CEILING
    if not taux_perte_pct:
        return quantite
    facteur = Decimal('1') + Decimal(str(taux_perte_pct)) / Decimal('100')
    return int((Decimal(str(quantite)) * facteur).to_integral_value(
        rounding=ROUND_CEILING))


def _ordre_besoin_composants(ordre):
    """{produit_id: quantite} pour CET ordre : lignes XMFG6 si présentes
    (repli BOM du kit sinon, multipliées par `ordre.quantite` et gonflées du
    taux de perte attendu — XMFG11)."""
    lignes = list(getattr(ordre, 'lignes', None).all()) if hasattr(
        ordre, 'lignes') else []
    besoins = {}
    if lignes:
        for ligne in lignes:
            if ligne.produit_id is None:
                continue
            besoins[ligne.produit_id] = besoins.get(
                ligne.produit_id, 0) + (ligne.quantite or 0)
        return besoins
    for c in ordre.kit.composants.all():
        if c.produit_id is None:
            continue
        qte = _besoin_avec_perte(
            (c.quantite or 0) * ordre.quantite, c.taux_perte_pct)
        besoins[c.produit_id] = besoins.get(c.produit_id, 0) + qte
    return besoins


def seed_reservations_assemblage(ordre):
    """XMFG2 — réserve les composants du kit pour cet ordre. Idempotent : une
    réservation par (ordre, produit), réalignée à la quantité courante tant
    qu'elle n'est pas consommée. Renvoie la liste des réservations actives."""
    from .models import ReservationAssemblage
    company = ordre.company
    besoins = _ordre_besoin_composants(ordre)
    for produit_id, qte in besoins.items():
        resa, created = ReservationAssemblage.objects.get_or_create(
            ordre=ordre, produit_id=produit_id,
            defaults={'company': company, 'quantite': qte})
        if not created and not resa.consomme:
            changed = []
            if resa.quantite != qte:
                resa.quantite = qte
                changed.append('quantite')
            if not resa.active:
                resa.active = True
                changed.append('active')
            if changed:
                resa.save(update_fields=changed)
    return list(ordre.reservations.filter(active=True))


def release_reservations_assemblage(ordre):
    """XMFG2 — libère les réservations NON consommées de l'ordre (annulation).
    Une réservation déjà consommée n'est jamais touchée. Renvoie le nombre de
    réservations libérées."""
    from .models import ReservationAssemblage
    return (ReservationAssemblage.objects
            .filter(ordre=ordre, active=True, consomme=False)
            .update(active=False))


def disponibilite_par_ligne(ordre):
    """XMFG2 — disponibilité par composant pour l'écran ordre : liste de dicts
    {produit_id, designation, requis, disponible, statut}, `statut` ∈
    {'disponible','partiel','manquant'}. `disponible` = stock total − réservé
    (engagé non consommé, TOUTES réservations confondues, y compris celles de
    CET ordre puisqu'elles sont déjà comptées dans le besoin affiché)."""
    from apps.stock.services import reserved_quantity, available_quantity
    besoins = _ordre_besoin_composants(ordre)
    out = []
    produits = {p.id: p for p in
                _produits_for_ids(ordre.company, list(besoins))}
    for produit_id, requis in besoins.items():
        produit = produits.get(produit_id)
        if produit is None:
            continue
        disponible = available_quantity(produit, reserved_quantity(produit))
        if disponible >= requis:
            statut = 'disponible'
        elif disponible > 0:
            statut = 'partiel'
        else:
            statut = 'manquant'
        out.append({
            'produit_id': produit_id,
            'designation': produit.nom,
            'requis': requis,
            'disponible': disponible,
            'statut': statut,
        })
    out.sort(key=lambda x: x['designation'])
    return out


def _produits_for_ids(company, ids):
    from apps.stock.models import Produit
    if not ids:
        return Produit.objects.none()
    return Produit.objects.filter(company=company, id__in=ids)


def alerter_penurie_assemblage(ordre):
    """XMFG2 — alerte non bloquante (`apps.notifications`, import
    function-local) pour un ordre PLANIFIÉ dont un composant passe sous le
    besoin. Best-effort : ne lève jamais."""
    try:
        from apps.notifications.services import notify_many, resolve_recipients
        from apps.notifications.models import EventType
    except Exception:  # pragma: no cover - défensif
        return
    manquants = [d for d in disponibilite_par_ligne(ordre)
                 if d['statut'] != 'disponible']
    if not manquants:
        return
    try:
        recipients = resolve_recipients(ordre.company, EventType.STOCK_LOW)
        titre = f'Composants manquants — ordre {ordre.reference}'
        corps = ', '.join(
            f"{m['designation']} (besoin {m['requis']}, dispo {m['disponible']})"
            for m in manquants)
        notify_many(recipients, EventType.STOCK_LOW, titre, body=corps,
                    company=ordre.company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── XMFG6 — Composants personnalisables par ordre (kit sur-mesure) ───────────
# Les lignes (`OrdreAssemblageLigne`) sont copiées depuis la BOM du kit à la
# CRÉATION de l'ordre, puis éditables tant que l'ordre est planifié. XMFG1 et
# XMFG2 lisent ces lignes en priorité (repli BOM si absentes — voir
# `_ordre_besoin_composants` ci-dessus, déjà écrit pour ce repli).

def seed_lignes_assemblage(ordre):
    """XMFG6 — copie la BOM du kit en lignes d'ordre éditables, UNE fois (à la
    création), quantités gonflées du taux de perte attendu (XMFG11). Idempotent :
    n'écrase jamais des lignes déjà présentes (même partiellement personnalisées)."""
    from .models import OrdreAssemblageLigne
    if ordre.lignes.exists():
        return list(ordre.lignes.all())
    lignes = [
        OrdreAssemblageLigne(
            ordre=ordre, produit=c.produit, designation=c.designation,
            quantite=_besoin_avec_perte(
                (c.quantite or 0) * ordre.quantite, c.taux_perte_pct),
            origine=OrdreAssemblageLigne.Origine.KIT)
        for c in ordre.kit.composants.all()
    ]
    OrdreAssemblageLigne.objects.bulk_create(lignes)
    return list(ordre.lignes.all())


def cout_prevu_assemblage(ordre):
    """XMFG6 — coût prévu de l'ordre : somme(lignes.quantite × produit.prix_achat)
    si des lignes existent, sinon somme(BOM du kit × ordre.quantite ×
    prix_achat) — repli BOM. Décimal, jamais négatif."""
    from decimal import Decimal
    total = Decimal('0')
    lignes = list(getattr(ordre, 'lignes', None).all()) if hasattr(
        ordre, 'lignes') else []
    if lignes:
        for ligne in lignes:
            if ligne.produit_id is None:
                continue
            prix = getattr(ligne.produit, 'prix_achat', None) or Decimal('0')
            total += Decimal(str(ligne.quantite or 0)) * Decimal(str(prix))
        return total
    for c in ordre.kit.composants.select_related('produit').all():
        if c.produit_id is None:
            continue
        prix = getattr(c.produit, 'prix_achat', None) or Decimal('0')
        qte = (c.quantite or 0) * ordre.quantite
        total += Decimal(str(qte)) * Decimal(str(prix))
    return total


# ── XMFG7 — Capture des numéros de série à l'assemblage + étiquette ──────────
# Comble le trou noir entre la réception (FG61) et la pose (`ComponentSerial`) :
# à la clôture, on relève les séries du composite produit (une par unité) et,
# en option, celles des composants sérialisés consommés (liées au composite).

def enregistrer_series_assemblage(ordre, *, series_composite, series_composants,
                                  user):
    """XMFG7 — enregistre les séries relevées à la clôture. `series_composite` =
    liste de numéros (une entrée par unité produite, dans l'ordre) ;
    `series_composants` = liste optionnelle de dicts
    {produit_id, numero_serie, composite_index} (`composite_index` = index
    dans `series_composite` pour lier le composant à son unité). Renvoie la
    liste des `SerieAssemblage` créées."""
    from .models import SerieAssemblage
    created = []
    composite_objs = []
    for numero in series_composite:
        numero = (numero or '').strip()
        if not numero:
            continue
        obj = SerieAssemblage.objects.create(
            company=ordre.company, ordre=ordre, produit=ordre.kit.produit_compose,
            numero_serie=numero, role=SerieAssemblage.Role.COMPOSITE,
            created_by=user)
        composite_objs.append(obj)
        created.append(obj)
    for entry in (series_composants or []):
        numero = (entry.get('numero_serie') or '').strip()
        if not numero:
            continue
        idx = entry.get('composite_index')
        composite_ref = None
        if isinstance(idx, int) and 0 <= idx < len(composite_objs):
            composite_ref = composite_objs[idx]
        from apps.stock.models import Produit
        produit = None
        produit_id = entry.get('produit_id')
        if produit_id:
            produit = Produit.objects.filter(
                id=produit_id, company=ordre.company).first()
        obj = SerieAssemblage.objects.create(
            company=ordre.company, ordre=ordre, produit=produit,
            numero_serie=numero, role=SerieAssemblage.Role.COMPOSANT,
            composite_ref=composite_ref, created_by=user)
        created.append(obj)
    return created


def etiquette_items_assemblage(ordre):
    """XMFG7 — items d'étiquette (jeton QR + titre + sous-titre, SANS AUCUN
    PRIX) pour chaque unité composite avec série enregistrée sur cet ordre.
    Format attendu par `apps.stock.labels.render_labels_html`."""
    from .models import SerieAssemblage
    series = ordre.series.filter(role=SerieAssemblage.Role.COMPOSITE)
    kit_nom = ordre.kit.nom
    items = []
    for s in series:
        items.append({
            'token': f'ASMSER:{s.id}',
            'titre': kit_nom,
            'sous_titre': s.numero_serie,
        })
    return items


# ── XMFG12 — Ordre de démontage (unbuild) ─────────────────────────────────────

def seed_lignes_demontage(ordre_demontage):
    """XMFG12 — copie la BOM du kit en lignes de démontage éditables (quantité
    ATTENDUE = BOM × ordre.quantite ; RÉCUPÉRÉE par défaut = attendue, éditable
    ligne à ligne avant la clôture). Idempotent."""
    from .models import OrdreDemontageLigne
    if ordre_demontage.lignes.exists():
        return list(ordre_demontage.lignes.all())
    lignes = [
        OrdreDemontageLigne(
            ordre=ordre_demontage, produit=c.produit, designation=c.designation,
            quantite_attendue=(c.quantite or 0) * ordre_demontage.quantite,
            quantite_recuperee=(c.quantite or 0) * ordre_demontage.quantite,
        )
        for c in ordre_demontage.kit.composants.all()
    ]
    OrdreDemontageLigne.objects.bulk_create(lignes)
    return list(ordre_demontage.lignes.all())


# ── XMFG13 — Contrôle qualité de fin d'assemblage (gate avant clôture) ───────

def instancier_controle_qualite(ordre):
    """XMFG13 — instancie la checklist QC du kit sur cet ordre (une fois),
    depuis `ControleQualiteItemModele`. Kit sans modèle (ou modèle inactif) →
    ne crée rien (comportement actuel inchangé). Idempotent."""
    from .models import ControleQualiteOrdre
    modele = getattr(ordre.kit, 'controle_qualite_modele', None)
    if modele is None or not modele.active:
        return []
    existants = set(
        ordre.controles_qualite.values_list('item_modele_id', flat=True))
    items = modele.items.all()
    a_creer = [
        ControleQualiteOrdre(ordre=ordre, item_modele=item)
        for item in items if item.id not in existants
    ]
    if a_creer:
        ControleQualiteOrdre.objects.bulk_create(a_creer)
    return list(ordre.controles_qualite.select_related('item_modele').all())


def controle_qualite_bloque_cloture(ordre):
    """XMFG13 — True si l'ordre a un modèle QC actif et que la checklist n'est
    PAS entièrement passée (tout item doit être `pass` ; un `fail` ou
    `en_attente` bloque). Kit sans modèle → jamais bloquant (False)."""
    modele = getattr(ordre.kit, 'controle_qualite_modele', None)
    if modele is None or not modele.active:
        return False
    from .models import ControleQualiteOrdre
    controles = instancier_controle_qualite(ordre)
    if not controles:
        return False
    return any(
        c.resultat != ControleQualiteOrdre.Resultat.PASS_ for c in controles)


def enregistrer_controle_qualite(ordre, item_modele_id, *, resultat,
                                 valeur_mesuree=None, photo=None, user):
    """XMFG13 — enregistre le résultat d'un item QC pour cet ordre. Si une
    tolérance (valeur_min/max) est définie sur l'item ET qu'une valeur mesurée
    est fournie SANS résultat explicite, le pass/fail est déduit automatiquement.
    Un item en échec ouvre une NCR liée (`qhse.services`, écriture cross-app
    fine) — best-effort, ne bloque jamais l'enregistrement."""
    from decimal import Decimal, InvalidOperation
    from django.utils import timezone
    from .models import ControleQualiteOrdre

    controle = ControleQualiteOrdre.objects.select_related('item_modele').get(
        ordre=ordre, item_modele_id=item_modele_id)
    item = controle.item_modele

    if valeur_mesuree is not None and not isinstance(valeur_mesuree, Decimal):
        try:
            valeur_mesuree = Decimal(str(valeur_mesuree))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError('valeur_mesuree invalide.')

    if resultat is None and valeur_mesuree is not None and (
            item.valeur_min is not None or item.valeur_max is not None):
        ok = True
        if item.valeur_min is not None and valeur_mesuree < item.valeur_min:
            ok = False
        if item.valeur_max is not None and valeur_mesuree > item.valeur_max:
            ok = False
        resultat = (ControleQualiteOrdre.Resultat.PASS_ if ok
                    else ControleQualiteOrdre.Resultat.FAIL)

    controle.resultat = resultat or ControleQualiteOrdre.Resultat.EN_ATTENTE
    controle.valeur_mesuree = valeur_mesuree
    if photo is not None:
        controle.photo = photo
    controle.controle_par = user
    controle.date_controle = timezone.now()
    controle.save(update_fields=[
        'resultat', 'valeur_mesuree', 'photo', 'controle_par', 'date_controle'])

    if controle.resultat == ControleQualiteOrdre.Resultat.FAIL:
        try:
            from apps.qhse.services import creer_ncr_depuis_controle_assemblage
            creer_ncr_depuis_controle_assemblage(
                company=ordre.company, ordre_id=ordre.id,
                titre=f'QC échec — {ordre.reference} · {item.libelle}',
                description=(
                    f'Item « {item.libelle} » en échec sur l\'ordre '
                    f'{ordre.reference} (kit {ordre.kit.nom}).'),
                signale_par=user)
        except Exception:  # pragma: no cover - défensif
            pass
    return controle


# ── XMFG14 — Gamme légère : étapes d'assemblage ──────────────────────────────

def instancier_etapes_ordre(ordre):
    """XMFG14 — instancie la checklist d'exécution du kit sur cet ordre (une
    fois), depuis `EtapeAssemblage`. Kit sans étape → ne crée rien (mode
    opératoire absent = comportement actuel inchangé). Idempotent."""
    from .models import EtapeOrdre
    etapes_modele = ordre.kit.etapes_assemblage.all()
    if not etapes_modele:
        return []
    existants = set(
        ordre.etapes.values_list('etape_modele_id', flat=True))
    a_creer = [
        EtapeOrdre(ordre=ordre, etape_modele=etape)
        for etape in etapes_modele if etape.id not in existants
    ]
    if a_creer:
        EtapeOrdre.objects.bulk_create(a_creer)
    return list(ordre.etapes.select_related('etape_modele').all())


def cocher_etape_ordre(ordre, etape_modele_id, *, fait, duree_reelle_min, user):
    """XMFG14 — coche (ou décoche) une étape d'exécution avec la durée réelle
    saisie. `fait_par`/`fait_le` posés côté serveur quand `fait=True`."""
    from django.utils import timezone
    from .models import EtapeOrdre

    etape_ordre = EtapeOrdre.objects.get(
        ordre=ordre, etape_modele_id=etape_modele_id)
    etape_ordre.fait = bool(fait)
    etape_ordre.duree_reelle_min = duree_reelle_min
    if etape_ordre.fait:
        etape_ordre.fait_par = user
        etape_ordre.fait_le = timezone.now()
    else:
        etape_ordre.fait_par = None
        etape_ordre.fait_le = None
    etape_ordre.save(update_fields=[
        'fait', 'duree_reelle_min', 'fait_par', 'fait_le'])
    return etape_ordre


def totaux_temps_ordre(ordre):
    """XMFG14 — totaux prévu/réel (minutes) sur les étapes de cet ordre.
    Renvoie {'prevu': int|None, 'reel': int, 'complet': bool}. `prevu` est None
    si aucune étape n'a de durée attendue renseignée."""
    etapes = instancier_etapes_ordre(ordre)
    if not etapes:
        return {'prevu': None, 'reel': 0, 'complet': True}
    prevu = 0
    a_une_duree = False
    reel = 0
    for e in etapes:
        if e.etape_modele.duree_attendue_min is not None:
            prevu += e.etape_modele.duree_attendue_min
            a_une_duree = True
        if e.duree_reelle_min is not None:
            reel += e.duree_reelle_min
    return {
        'prevu': prevu if a_une_duree else None,
        'reel': reel,
        'complet': all(e.fait for e in etapes),
    }


# ── XKB1 — boîte d'approbations centralisée (écriture cross-app) ─────────────
class DecisionError(Exception):
    """Décision invalide sur une réquisition d'achat (statut non éligible)."""


def decider_demande_achat(demande_achat, *, approuver, user, motif_refus=''):
    """XKB1 — approuve/refuse une réquisition d'achat (FG310) depuis
    l'agrégateur d'approbations cross-app (``apps/reporting``).

    Réutilise EXACTEMENT les règles de ``DemandeAchatViewSet.approuver`` /
    ``.refuser`` (seule une demande ``SOUMISE`` est décidable ; l'approbateur
    et la date de décision sont posés côté serveur). Lève ``DecisionError`` si
    la demande n'est pas au statut attendu."""
    from django.utils import timezone
    from .models import DemandeAchat

    if demande_achat.statut != DemandeAchat.Statut.SOUMISE:
        raise DecisionError(
            "Seule une demande soumise peut être décidée.")

    demande_achat.approuvee_par = user
    demande_achat.date_decision = timezone.now()
    if approuver:
        demande_achat.statut = DemandeAchat.Statut.APPROUVEE
        demande_achat.motif_refus = None
    else:
        demande_achat.statut = DemandeAchat.Statut.REFUSEE
        demande_achat.motif_refus = (motif_refus or '').strip() or None
    demande_achat.save(update_fields=[
        'statut', 'approuvee_par', 'date_decision', 'motif_refus',
        'date_modification'])
    return demande_achat


# ── XFSM3 — Replanification en masse d'une journée ───────────────────────────
# Construit sur XFSM2 (meilleur créneau) / FG301 (nivellement) : entrée = un
# jour + (optionnellement) un technicien absent ou une liste d'IDs. Sortie =
# propositions de nouveaux créneaux/techniciens (réutilise la même logique
# de scoring que XFSM2, respecte FG300/FG302), puis application en un appel.
# `?simuler=1` (dry-run) ne mute rien — jamais de conflit créé (les créneaux
# proposés excluent déjà les techniciens en conflit/indisponibles ce jour-là,
# héritage direct de XFSM2).

def previsualiser_replanification_masse(company, *, jour, technicien_id=None,
                                        intervention_ids=None):
    """XFSM3 — propositions de re-slot pour un jour donné (dry-run, NE MUTE
    RIEN). Cible soit toutes les interventions du `technicien_id` donné ce
    jour-là, soit une liste explicite `intervention_ids` (les deux
    combinables : filtre supplémentaire). Chaque proposition réutilise
    ``selectors.suggerer_creneau`` (habilitation/conflit/indispo/charge/
    distance) — le créneau proposé ne recrée jamais de conflit FG300. Un même
    couple (technicien, date) n'est JAMAIS proposé deux fois DANS le même lot
    (sinon deux interventions du lot se recréeraient un conflit entre elles
    avant même d'être enregistrées) : chaque proposition déjà retenue plus
    haut dans le lot est exclue des candidats suivants, en repliant sur le
    meilleur candidat restant. Renvoie
    ``{jour, propositions: [{intervention_id, installation_id,
    type_intervention, technicien_actuel_id, proposition}]}``."""
    from .models import Intervention
    from . import selectors

    qs = Intervention.objects.filter(company=company, date_prevue=jour)
    if technicien_id is not None:
        qs = qs.filter(technicien_id=technicien_id)
    if intervention_ids:
        qs = qs.filter(id__in=intervention_ids)

    propositions = []
    reserves_dans_le_lot = set()
    for interv in qs.select_related('installation'):
        suggestions = selectors.suggerer_creneau(
            company, chantier_id=interv.installation_id,
            type_intervention=interv.type_intervention, n=10)
        proposition = None
        for candidat in suggestions['propositions']:
            cle = (candidat['technicien_id'], candidat['date'])
            if cle in reserves_dans_le_lot:
                continue
            proposition = candidat
            break
        if proposition is not None:
            reserves_dans_le_lot.add(
                (proposition['technicien_id'], proposition['date']))
        propositions.append({
            'intervention_id': interv.id,
            'installation_id': interv.installation_id,
            'type_intervention': interv.type_intervention,
            'technicien_actuel_id': interv.technicien_id,
            'proposition': proposition,
        })
    return {'jour': str(jour), 'propositions': propositions}


def appliquer_replanification_masse(company, *, jour, motif, user,
                                    technicien_id=None, intervention_ids=None):
    """XFSM3 — applique en UN appel les propositions de
    ``previsualiser_replanification_masse`` : chaque intervention resolvable
    (une proposition existe) est déplacée vers le technicien + date proposés,
    le compteur `rdv_reschedule_count` (FG78) est incrémenté et un chatter
    (motif) est posé, et le technicien réassigné est notifié (best-effort,
    `apps.notifications`). Les interventions SANS proposition (aucun
    créneau disponible dans la fenêtre XFSM2) sont laissées INTACTES et
    listées à part. Renvoie
    ``{jour, deplacees: [...], non_resolues: [intervention_id...]}``."""
    from django.db import transaction
    from . import intervention_activity
    from .models import Intervention

    motif = (motif or '').strip()
    preview = previsualiser_replanification_masse(
        company, jour=jour, technicien_id=technicien_id,
        intervention_ids=intervention_ids)

    deplacees = []
    non_resolues = []
    with transaction.atomic():
        for entry in preview['propositions']:
            proposition = entry['proposition']
            if proposition is None:
                non_resolues.append(entry['intervention_id'])
                continue
            interv = Intervention.objects.select_for_update().get(
                id=entry['intervention_id'], company=company)
            ancien_tech_id = interv.technicien_id
            nouvelle_date = proposition['date']
            nouveau_tech_id = proposition['technicien_id']
            interv.technicien_id = nouveau_tech_id
            if str(interv.date_prevue) != nouvelle_date:
                interv.rdv_reschedule_count = (
                    interv.rdv_reschedule_count or 0) + 1
            interv.date_prevue = nouvelle_date
            interv.save(update_fields=[
                'technicien_id', 'date_prevue', 'rdv_reschedule_count'])
            intervention_activity.log_note(
                interv, user,
                f"Replanification en masse ({motif or 'sans motif'}) : "
                f"{ancien_tech_id or 'non assigné'} → {nouveau_tech_id}, "
                f"nouvelle date {nouvelle_date}.")
            _notifier_reassignation(interv, user)
            deplacees.append({
                'intervention_id': interv.id,
                'ancien_technicien_id': ancien_tech_id,
                'nouveau_technicien_id': nouveau_tech_id,
                'nouvelle_date': nouvelle_date,
            })
    return {
        'jour': str(jour), 'deplacees': deplacees,
        'non_resolues': non_resolues,
    }


def _notifier_reassignation(interv, user):
    """XFSM3 — notifie (best-effort, ne lève jamais) le technicien réassigné
    d'un changement de créneau."""
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
    except Exception:  # pragma: no cover - défensif
        return
    if not interv.technicien_id:
        return
    try:
        titre = f"Intervention replanifiée — #{interv.id}"
        notify(
            interv.technicien, EventType.CHANTIER_DUE, titre,
            body=f"Nouvelle date : {interv.date_prevue}.",
            company=interv.company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── XMFG16 — Assemblage sous-traité (façon) avec suivi des composants confiés
# Cycle : à la CONFIRMATION d'un ordre lié à un sous-traitant, les composants
# de sa BOM/lignes sont transférés (TransfertStock, `apps.stock.services`)
# vers un emplacement dédié « chez {sous-traitant} » (créé à la volée). À la
# RÉCEPTION du composite, le backflush XMFG1 consomme les composants DEPUIS
# cet emplacement (`emplacement_source` forcé) et le composite est valorisé
# coût composants + montant façon de l'OST (INTERNE — jamais client-facing,
# jamais dans un PDF).

def confier_composants_soustraitance(ordre):
    """XMFG16 — transfère les composants de l'ordre (lignes XMFG6, repli BOM
    du kit) vers l'emplacement dédié du sous-traitant lié, et POSE cet
    emplacement comme `emplacement_source` de l'ordre (le backflush XMFG1 à la
    clôture consommera DEPUIS cet emplacement). No-op si l'ordre n'a pas de
    `sous_traitant`. Idempotent : ne retransfère pas si `emplacement_source`
    pointe déjà vers l'emplacement du sous-traitant."""
    from apps.stock.services import (
        get_or_create_emplacement_soustraitant, transfer_stock,
        ensure_emplacements)

    if ordre.sous_traitant_id is None:
        return ordre

    emplacement = get_or_create_emplacement_soustraitant(
        ordre.company, ordre.sous_traitant.nom)
    if ordre.emplacement_source_id == emplacement.id:
        return ordre  # déjà confié — idempotent.

    depot_principal = ensure_emplacements(ordre.company)
    lignes = list(ordre.lignes.select_related('produit').all())
    composants = (
        [(ligne.produit, ligne.quantite) for ligne in lignes] if lignes
        else [(c.produit, (c.quantite or 0) * ordre.quantite)
              for c in ordre.kit.composants.select_related('produit').all()])
    for produit, quantite in composants:
        if produit is None or not quantite:
            continue
        try:
            transfer_stock(
                company=ordre.company, user=ordre.created_by,
                produit_id=produit.id, source_id=depot_principal.id,
                destination_id=emplacement.id, quantite=quantite,
                note=f'Confié sous-traitant — ordre {ordre.reference}')
        except ValueError:
            # Stock insuffisant au dépôt principal : best-effort, le rapport
            # de reliquat (ci-dessous) restera visible à l'appelant — on ne
            # bloque jamais la confirmation d'ordre pour cette raison.
            continue

    ordre.emplacement_source = emplacement
    ordre.save(update_fields=['emplacement_source'])
    return ordre


def cout_composite_soustraite(ordre):
    """XMFG16 — coût du composite reçu d'un sous-traitant : coût composants
    (``cout_prevu_assemblage``, INTERNE) + montant façon de l'OST lié
    (``montant_realise`` si posé, sinon ``montant`` engagé). None si l'ordre
    n'a pas d'``ordre_sous_traitance``. JAMAIS client-facing ni dans un PDF."""
    from decimal import Decimal
    if ordre.ordre_sous_traitance_id is None:
        return None
    ost = ordre.ordre_sous_traitance
    montant_facon = (
        ost.montant_realise if ost.montant_realise is not None
        else ost.montant) or Decimal('0')
    return cout_prevu_assemblage(ordre) + Decimal(str(montant_facon))


def rapport_composants_chez_soustraitants(company):
    """XMFG16 — reliquat des composants restant CHEZ CHAQUE sous-traitant
    (emplacements « Chez {nom} » avec du stock ventilé non encore consommé —
    un ordre déjà backflushé, ``stock_mouvemente=True``, n'a plus de reliquat).
    Renvoie une liste [{sous_traitant_id, sous_traitant_nom, emplacement_id,
    lignes: [{produit_id, produit_nom, quantite}]}]. Lecture seule."""
    from .models import OrdreAssemblage

    ordres = (OrdreAssemblage.objects
              .filter(company=company, sous_traitant__isnull=False,
                      emplacement_source__isnull=False,
                      stock_mouvemente=False)
              .exclude(statut=OrdreAssemblage.Statut.ANNULE)
              .select_related('sous_traitant', 'emplacement_source'))
    par_emplacement = {}
    for ordre in ordres:
        emp = ordre.emplacement_source
        entry = par_emplacement.setdefault(emp.id, {
            'sous_traitant_id': ordre.sous_traitant_id,
            'sous_traitant_nom': ordre.sous_traitant.nom,
            'emplacement_id': emp.id,
            'lignes': [],
        })
        for se in emp.stocks.select_related('produit').all():
            entry['lignes'].append({
                'produit_id': se.produit_id,
                'produit_nom': se.produit.nom,
                'quantite': se.quantite,
            })
    return list(par_emplacement.values())


def marquer_serie_entrepot_sortie(*, company, produit_id, numero_serie):
    """XPOS9 — si `numero_serie` est déjà enregistré au registre entrepôt
    (`SerieEntrepot`, FG323) pour ce produit/société, le marque SORTI (vente
    comptoir). No-op silencieux si la série n'y est pas enregistrée — un
    produit sérialisé peut très bien être vendu sans être jamais passé par
    l'entrepôt tracé. Renvoie l'objet mis à jour, ou None si non trouvé."""
    from .models_serie_entrepot import SerieEntrepot

    entry = SerieEntrepot.objects.filter(
        company=company, produit_id=produit_id,
        numero_serie=numero_serie).first()
    if entry is None:
        return None
    if entry.statut != SerieEntrepot.Statut.SORTI:
        entry.statut = SerieEntrepot.Statut.SORTI
        entry.save(update_fields=['statut', 'date_modification'])
    return entry


class TicketSansInstallationError(Exception):
    """YSERV2 — levée quand un ticket SAV sans chantier lié demande la
    création d'une intervention (rien à planifier sans Installation)."""


def creer_intervention_depuis_ticket(*, ticket, user, company,
                                     type_intervention=None):
    """YSERV2 — Point d'entrée cross-app (services.py cible) pour créer une
    ``Intervention`` pré-remplie depuis un ticket SAV, appelé EXCLUSIVEMENT
    par ``apps.sav.views`` (jamais un import du modèle ``Intervention``
    depuis ``sav`` — frontière cross-app, CLAUDE.md).

    Le chantier (``installation``), le technicien (``technicien_responsable``
    du ticket) sont repris tels quels ; le type par défaut est DEPANNAGE
    (correctif) sauf ``type_intervention`` explicite. Refuse proprement
    (``TicketSansInstallationError``) si le ticket n'a pas d'installation
    liée — rien à planifier sans chantier. ``ticket`` est passé en instance
    déjà résolue/scopée société par l'appelant ; ``company`` est TOUJOURS
    posée côté serveur (jamais lue du corps de requête).

    Renvoie l'``Intervention`` créée.
    """
    from .models_intervention import Intervention

    if not ticket.installation_id:
        raise TicketSansInstallationError(
            "Ce ticket n'a pas de chantier lié — impossible de planifier "
            'une intervention.')

    interv = Intervention.objects.create(
        company=company,
        installation_id=ticket.installation_id,
        ticket=ticket,
        type_intervention=type_intervention or Intervention.Type.DEPANNAGE,
        technicien=ticket.technicien_responsable,
        date_prevue=ticket.date_tournee,
        created_by=user,
    )
    return interv


# ── YPROC3 — GR/IR automatique (provision à réception, lettrage à facture) ──
# Consommateurs des événements ``core.events.reception_fournisseur_confirmee``
# et ``core.events.facture_fournisseur_creee`` (abonnés dans receivers.py).
# Montants INTERNES (jamais client-facing).

def provisionner_gr_ir_reception(*, reception, company, user):
    """YPROC3 — crée la provision GR/IR (`ReceptionNonFacturee`) pour une
    réception fournisseur venant d'être CONFIRMÉE.

    Montant = Σ (quantité de la ligne de réception × `prix_achat_unitaire` de
    sa ligne de BCF). IDEMPOTENTE : une réception déjà provisionnée (à la main
    ou automatiquement) n'est jamais doublée — renvoie la provision existante.
    Sans BCF lié (réception hors flux normal), no-op (rien à provisionner).
    """
    from decimal import Decimal
    from .models_gr_ir import ReceptionNonFacturee

    if company is None or reception is None:
        return None
    bc = reception.bon_commande
    if bc is None:
        return None

    existante = ReceptionNonFacturee.objects.filter(
        company=company, reception=reception).first()
    if existante is not None:
        return existante

    montant = Decimal('0')
    for ligne in reception.lignes.select_related('ligne_commande').all():
        pu = (ligne.ligne_commande.prix_achat_unitaire
              if ligne.ligne_commande else Decimal('0')) or Decimal('0')
        montant += Decimal(str(ligne.quantite or 0)) * pu

    date_reception = reception.date_reception
    if date_reception is None and reception.date_creation:
        date_reception = reception.date_creation.date()

    return ReceptionNonFacturee.objects.create(
        company=company, reception=reception, bon_commande=bc,
        libelle=f'Réception {reception.reference}',
        montant_provision=montant,
        date_reception=date_reception,
        created_by=user,
    )


def lettrer_gr_ir_facture(*, facture, company, user):
    """YPROC3 — lettre AUTOMATIQUEMENT les provisions GR/IR ouvertes du bon de
    commande d'une facture fournisseur venant d'être CRÉÉE.

    Solde (`lettre=True`, `facture` posée, `date_lettrage`) les provisions non
    encore lettrées de ce BCF, à hauteur du montant facturé (HT) — ne touche
    jamais une provision d'un autre bon de commande. IDEMPOTENTE : une
    provision déjà lettrée est ignorée (jamais re-lettrée / re-décrémentée).
    Sans bon de commande sur la facture, no-op.
    """
    from django.utils import timezone
    from .models_gr_ir import ReceptionNonFacturee

    if company is None or facture is None:
        return []
    bc = getattr(facture, 'bon_commande', None)
    if bc is None:
        return []

    montant_restant = facture.montant_ht or 0
    lettres = []
    provisions = ReceptionNonFacturee.objects.filter(
        company=company, bon_commande=bc, lettre=False).order_by(
        'date_creation')
    for prov in provisions:
        if montant_restant <= 0:
            break
        prov.facture = facture
        prov.lettre = True
        prov.date_lettrage = timezone.now().date()
        prov.save(update_fields=['facture', 'lettre', 'date_lettrage',
                                 'date_modification'])
        lettres.append(prov)
        montant_restant -= (prov.montant_provision or 0)
    return lettres


# ── YSTCK7 — peuplement auto du registre entrepôt (SerieEntrepot) à la
# réception BCF. Consommateur du même événement `reception_fournisseur_
# confirmee` (abonné dans receivers.py) : DC37/FG61 capturent
# `LigneReceptionFournisseur.numeros_serie` mais rien ne créait de
# `SerieEntrepot` (FG323) — le registre devait être peuplé à la main.

def peupler_series_entrepot_reception(*, reception, company, user):
    """YSTCK7 — pour chaque série présente sur une ligne de la réception,
    upsert IDEMPOTENT d'un `SerieEntrepot` (produit, numéro, emplacement
    principal, statut « en stock »). Une série déjà enregistrée pour ce
    produit+société n'est jamais dupliquée (contrainte unique_together —
    `get_or_create`). Sans BCF ni séries, no-op. Renvoie le nombre de séries
    créées."""
    from .models_serie_entrepot import SerieEntrepot
    from apps.stock.services import ensure_emplacements

    if company is None or reception is None:
        return 0
    depot_principal = ensure_emplacements(company)
    created = 0
    for ligne in reception.lignes.select_related('produit').all():
        if ligne.produit_id is None:
            continue
        series = getattr(ligne, 'numeros_serie', None) or []
        for numero in series:
            numero = (numero or '').strip() if isinstance(numero, str) \
                else numero
            if not numero:
                continue
            _, was_created = SerieEntrepot.objects.get_or_create(
                company=company, produit_id=ligne.produit_id,
                numero_serie=numero,
                defaults={
                    'statut': SerieEntrepot.Statut.EN_STOCK,
                    'emplacement': depot_principal,
                    'reference_reception': reception.reference,
                    'created_by': user,
                })
            if was_created:
                created += 1
    return created


# ── YSERV1 — Gate « acompte encaissé » avant planification (opt-in) ────────

def verifier_gate_acompte_planification(installation):
    """YSERV1 — renvoie une raison FRANÇAISE qui bloque le passage du
    chantier à PLANIFIE, ou ``None`` si la transition est autorisée.

    Toggle société `exiger_acompte_avant_planification` (défaut OFF = jamais
    de blocage, comportement historique byte-identique). ON : bloque tant
    qu'aucune Facture de type 'acompte' du devis lié n'est 'payee' — lue via
    `apps.ventes.selectors.acompte_paye_pour_devis` (jamais un import du
    modèle ventes). Un chantier sans devis lié n'est jamais bloqué (rien à
    vérifier)."""
    company = installation.company
    if company is None:
        return None
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company)
    except Exception:  # pragma: no cover - défensif
        return None
    if not getattr(profil, 'exiger_acompte_avant_planification', False):
        return None
    if not installation.devis_id:
        return None
    from apps.ventes.selectors import acompte_paye_pour_devis
    if acompte_paye_pour_devis(installation.devis_id, company):
        return None
    return ("Planification refusée : l'acompte de ce devis n'est pas "
            'encore encaissé (réglage société « acompte avant '
            'planification »).')


# ── YSERV6 — annulation de chantier : solder les interventions ouvertes ────

def annuler_interventions_ouvertes(installation, user):
    """YSERV6 — à l'annulation d'un chantier, marque `annulee=True` (drapeau
    ORTHOGONAL, la state machine F3 `STATUT_ORDER` reste intacte) toutes ses
    interventions NON terminées (statut hors TERMINEE/VALIDEE, pas déjà
    annulée), journalise une note par intervention et notifie les
    techniciens/équipe assignés (best-effort). Renvoie le nombre marquées.
    """
    from .models_intervention import Intervention

    qs = installation.interventions.exclude(
        statut__in=[Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE]
    ).filter(annulee=False)
    count = 0
    for interv in qs:
        interv.annulee = True
        interv.motif_annulation = (
            f'Chantier {installation.reference} annulé')
        interv.save(update_fields=['annulee', 'motif_annulation'])
        from . import intervention_activity
        intervention_activity.log_note(
            interv, user,
            'Intervention annulée automatiquement — chantier annulé.')
        _notifier_intervention_annulee(interv, user)
        count += 1
    return count


def _notifier_intervention_annulee(interv, user):
    """YSERV6 — notifie (best-effort, ne lève jamais) le technicien principal
    et les membres d'équipe d'une intervention annulée."""
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
    except Exception:  # pragma: no cover - défensif
        return
    destinataires = set()
    if interv.technicien_id:
        destinataires.add(interv.technicien)
    try:
        destinataires.update(interv.equipe.all())
    except Exception:  # pragma: no cover - défensif
        pass
    titre = f"Intervention annulée — chantier {interv.installation.reference}"
    for dest in destinataires:
        try:
            notify(
                dest, EventType.CHANTIER_DUE, titre,
                body='Le chantier a été annulé, cette intervention ne '
                     'sera pas réalisée.',
                company=interv.company)
        except Exception:  # pragma: no cover - défensif
            pass


def reactiver_interventions_annulees(installation, user):
    """YSERV6 — à la réactivation d'un chantier, lève UNIQUEMENT le drapeau
    `annulee` des interventions qui l'ont reçu PAR CETTE annulation (motif
    traçant la provenance) — jamais une intervention annulée pour une autre
    raison. Renvoie le nombre réactivé."""
    marker = f'Chantier {installation.reference} annulé'
    qs = installation.interventions.filter(
        annulee=True, motif_annulation=marker)
    count = 0
    for interv in qs:
        interv.annulee = False
        interv.motif_annulation = None
        interv.save(update_fields=['annulee', 'motif_annulation'])
        from . import intervention_activity
        intervention_activity.log_note(
            interv, user,
            'Intervention réactivée — chantier réactivé.')
        count += 1
    return count


# ── YSERV7 — jalons atteints & réception → rappel de facturation d'échéancier
# `JalonProjet.date_reelle`/`atteint` ne déclenchait RIEN côté facturation :
# atteindre le jalon lié à une tranche (acompte/intermediaire/solde) ou
# réceptionner le chantier (tranche SOLDE) ne signale jamais qu'une tranche
# est à facturer. Nudge SEULEMENT — aucune facture créée automatiquement, les
# statuts document restent inchangés. Lecture des factures du devis via
# `apps.ventes.selectors` (jamais les models ventes).

def notifier_jalon_a_facturer(jalon, user=None):
    """YSERV7 — à l'atteinte (`atteint=True`) d'un jalon lié à une tranche
    d'échéancier non encore facturée, notifie (best-effort) le responsable.
    Idempotent : `rappel_facturation_envoye` verrouille — ne notifie jamais
    deux fois pour le même jalon. No-op si le jalon n'est pas atteint, n'a pas
    de tranche liée, ou si le chantier n'a pas de devis source."""
    if not jalon.atteint or not jalon.tranche_echeancier:
        return False
    if jalon.rappel_facturation_envoye:
        return False
    installation = jalon.installation
    devis = getattr(installation, 'devis', None)
    if devis is None:
        return False
    from apps.ventes.selectors import tranche_facturee
    if tranche_facturee(devis, jalon.tranche_echeancier):
        return False
    try:
        from apps.notifications.services import notify_many, resolve_recipients
        from apps.notifications.models import EventType
        libelle_tranche = dict(jalon.TRANCHE_CHOICES).get(
            jalon.tranche_echeancier, jalon.tranche_echeancier)
        recipients = resolve_recipients(jalon.company, EventType.CHANTIER_DUE)
        titre = f'Facture {libelle_tranche} à émettre — jalon {jalon.libelle} atteint'
        notify_many(
            recipients, EventType.CHANTIER_DUE, titre,
            body=f'Chantier {installation.reference} — tranche '
                 f'« {libelle_tranche} » non encore facturée.',
            company=jalon.company)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
    jalon.rappel_facturation_envoye = True
    jalon.save(update_fields=['rappel_facturation_envoye'])
    return True


def notifier_reception_solde_a_facturer(installation, user=None):
    """YSERV7 — à la réception du chantier (RECEPTIONNE), rappelle la tranche
    SOLDE si elle n'est pas encore facturée. Réutilise le même verrou
    d'idempotence que `notifier_jalon_a_facturer` : cherche (ou crée à la
    volée) le jalon RECEPTION du chantier pour y accrocher le drapeau, sans
    dupliquer le mécanisme de garde. No-op sans devis source."""
    devis = getattr(installation, 'devis', None)
    if devis is None:
        return False
    from .models import JalonProjet
    jalon, _ = JalonProjet.objects.get_or_create(
        installation=installation, phase=JalonProjet.Phase.RECEPTION,
        defaults={
            'company': installation.company,
            'libelle': 'Réception',
            'tranche_echeancier': JalonProjet.TRANCHE_SOLDE,
        })
    changed_fields = []
    if not jalon.atteint:
        jalon.atteint = True
        changed_fields.append('atteint')
    if not jalon.tranche_echeancier:
        jalon.tranche_echeancier = JalonProjet.TRANCHE_SOLDE
        changed_fields.append('tranche_echeancier')
    if changed_fields:
        jalon.save(update_fields=changed_fields)
    return notifier_jalon_a_facturer(jalon, user)


def chantiers_a_facturer(company):
    """YSERV7 — sélecteur : chantiers ayant au moins une tranche due (jalon
    atteint ou chantier réceptionné) non encore facturée. Renvoie une liste de
    dicts plats `{installation_id, reference, tranche, jalon_id}` — un par
    tranche due (un chantier peut apparaître plusieurs fois si plusieurs
    tranches sont dues). Lecture seule ; import ventes via selectors seulement."""
    from apps.ventes.selectors import tranche_facturee
    from .models import JalonProjet
    out = []
    jalons = (
        JalonProjet.objects
        .filter(company=company, atteint=True,
                tranche_echeancier__isnull=False)
        .exclude(tranche_echeancier='')
        .select_related('installation', 'installation__devis')
        .order_by('installation_id', 'ordre', 'id')
    )
    for jalon in jalons:
        installation = jalon.installation
        devis = getattr(installation, 'devis', None)
        if devis is None:
            continue
        if tranche_facturee(devis, jalon.tranche_echeancier):
            continue
        out.append({
            'installation_id': installation.id,
            'reference': installation.reference,
            'tranche': jalon.tranche_echeancier,
            'jalon_id': jalon.id,
            'jalon_libelle': jalon.libelle,
        })
    return out


# ── YSTCK5 — expédition/annulation de livraison ventile le grand livre ─────
# `LivraisonViewSet.expedier`/`livrer`/`annuler` ne changeaient QUE le statut :
# les `LivraisonLigne` (produit + quantité) ne réservaient ni ne déplaçaient
# jamais rien — la planification était déconnectée du grand livre. À
# `expedier`, on TRANSFÈRE (jamais un mouvement de sortie : le total ne
# change pas) les lignes du dépôt de la livraison vers l'emplacement
# chantier/van (« Camionnette », créée par `ensure_emplacements`) ; à
# `annuler` d'une livraison déjà expédiée, le contre-transfert. Idempotent via
# `Livraison.stock_mouvemente`. NB : ne double-compte jamais avec
# `consume_reservations` (sortie réelle à « Installé ») — ceci est un
# TRANSFERT interne (dépôt → van/site), pas une consommation.

def _emplacement_van(company):
    """Emplacement « Camionnette » (van/site) de la société — créé à la
    volée par `ensure_emplacements` si la société n'a encore aucun
    emplacement. `ensure_emplacements` ne sème le dépôt+camionnette que
    lorsque la société n'a AUCUN emplacement du tout : si un dépôt a déjà été
    créé par un autre chemin (ex. directement en base, sans passer par ce
    helper), il ne recrée jamais la camionnette manquante. On la garantit
    donc nous-mêmes ici via `get_or_create`, sans toucher au comportement
    (idempotent, additif) d'`ensure_emplacements` pour ses autres appelants."""
    from apps.stock.services import ensure_emplacements
    from apps.stock.models import EmplacementStock
    ensure_emplacements(company)
    van = (
        EmplacementStock.objects
        .filter(company=company, is_principal=False, archived=False)
        .order_by('ordre', 'id')
        .first()
    )
    if van is not None:
        return van
    van, _created = EmplacementStock.objects.get_or_create(
        company=company, nom='Camionnette',
        defaults={'is_principal': False, 'ordre': 10})
    return van


def ventiler_stock_livraison(livraison, user):
    """YSTCK5 — à `expedier` : transfère chaque ligne du dépôt de la
    livraison vers l'emplacement van. No-op sûr (renvoie 0) si la livraison
    n'a pas de dépôt source, si son mode est `direct_site` (jamais passé par
    le dépôt — rien à décrémenter), ou si `stock_mouvemente` est déjà posé
    (idempotent). Une ligne sans produit catalogue ou en stock insuffisant au
    dépôt est ignorée (best-effort, ne bloque jamais l'expédition)."""
    from .models_livraison import Livraison
    if livraison.stock_mouvemente:
        return 0
    if livraison.mode_acheminement == Livraison.ModeAcheminement.DIRECT_SITE:
        return 0
    if livraison.depot_id is None:
        return 0
    van = _emplacement_van(livraison.company)
    if van is None:
        return 0
    from apps.stock.services import transfer_stock
    transferred = 0
    for ligne in livraison.lignes.select_related('produit').all():
        if ligne.produit_id is None or not ligne.quantite:
            continue
        try:
            transfer_stock(
                company=livraison.company, user=user,
                produit_id=ligne.produit_id, source_id=livraison.depot_id,
                destination_id=van.id, quantite=ligne.quantite,
                note=f'Expédition livraison {livraison.reference}')
            transferred += 1
        except ValueError:
            continue  # best-effort : stock insuffisant, on n'échoue pas l'expédition.
    livraison.stock_mouvemente = True
    livraison.save(update_fields=['stock_mouvemente'])
    return transferred


def contre_transferer_stock_livraison(livraison, user):
    """YSTCK5 — à `annuler` une livraison déjà ventilée : contre-transfert
    van → dépôt. No-op si jamais ventilée (`stock_mouvemente=False`)."""
    if not livraison.stock_mouvemente:
        return 0
    if livraison.depot_id is None:
        return 0
    van = _emplacement_van(livraison.company)
    if van is None:
        return 0
    from apps.stock.services import transfer_stock
    reversed_count = 0
    for ligne in livraison.lignes.select_related('produit').all():
        if ligne.produit_id is None or not ligne.quantite:
            continue
        try:
            transfer_stock(
                company=livraison.company, user=user,
                produit_id=ligne.produit_id, source_id=van.id,
                destination_id=livraison.depot_id, quantite=ligne.quantite,
                note=f'Annulation livraison {livraison.reference}')
            reversed_count += 1
        except ValueError:
            continue
    livraison.stock_mouvemente = False
    livraison.save(update_fields=['stock_mouvemente'])
    return reversed_count


# ── ZSTK8 — retour / transfert inverse depuis une Livraison validée ────────
# Odoo génère un « return picking » depuis une livraison validée. Les retours
# FOURNISSEUR existent (stock.RetourFournisseur) mais rien ne permettait de
# générer un retour CLIENT depuis une `Livraison` livrée. Le retour ré-
# incrémente le stock du DÉPÔT SOURCE de la livraison (jamais un ajustement
# libre) — plafonné à la quantité réellement livrée.

def generer_retour_livraison(livraison, user, motif=''):
    """ZSTK8 — crée un `RetourLivraison` BROUILLON pré-rempli depuis les
    lignes livrées de la livraison (quantité_livree = quantité de la ligne
    d'origine, quantite_retournee = 0 par défaut, éditable ensuite ≤ livrée).
    Renvoie le retour créé."""
    from .models_retour_livraison import RetourLivraison, RetourLivraisonLigne

    retour = RetourLivraison.objects.create(
        company=livraison.company, livraison=livraison, motif=motif or '',
        created_by=user)
    for ligne in livraison.lignes.select_related('produit').all():
        RetourLivraisonLigne.objects.create(
            retour=retour, produit_id=ligne.produit_id,
            designation=ligne.designation or (
                ligne.produit.nom if ligne.produit_id else ''),
            quantite_livree=ligne.quantite, quantite_retournee=0)
    return retour


def valider_retour_livraison(retour, user):
    """ZSTK8 — valide le retour : pour chaque ligne dont
    `quantite_retournee > 0`, poste UN `MouvementStock` ENTREE au dépôt
    SOURCE de la livraison (idempotent via `stock_applique`). Refuse (lève
    ValueError) si une ligne dépasse la quantité livrée, ou si la livraison
    source n'a pas de dépôt. Renvoie le nombre de lignes appliquées."""
    from django.db import transaction
    from apps.stock.selectors import lock_produit
    from apps.stock.services import (
        mouvement_type_entree, record_stock_movement,
    )
    from .models_retour_livraison import RetourLivraison

    if retour.statut == RetourLivraison.Statut.VALIDE:
        raise ValueError('Retour déjà validé.')
    livraison = retour.livraison
    if livraison.depot_id is None:
        raise ValueError('Cette livraison n\'a pas de dépôt source.')

    lignes = list(retour.lignes.select_related('produit').all())
    for ligne in lignes:
        if ligne.quantite_retournee > ligne.quantite_livree:
            raise ValueError(
                f'Quantité retournée ({ligne.quantite_retournee}) '
                f'supérieure à la quantité livrée ({ligne.quantite_livree}) '
                f'pour « {ligne.designation or ligne.produit_id} ».')

    applied = 0
    with transaction.atomic():
        for ligne in lignes:
            if (ligne.stock_applique or ligne.produit_id is None
                    or ligne.quantite_retournee <= 0):
                if not ligne.stock_applique:
                    ligne.stock_applique = True
                    ligne.save(update_fields=['stock_applique'])
                continue
            produit = lock_produit(ligne.produit_id)
            qte_avant = produit.quantite_stock
            qte_apres = qte_avant + ligne.quantite_retournee
            record_stock_movement(
                company=livraison.company, produit=produit,
                type_mouvement=mouvement_type_entree(),
                quantite=ligne.quantite_retournee,
                quantite_avant=qte_avant, quantite_apres=qte_apres,
                reference=f'RETOUR-LIV-{livraison.reference}',
                note=f'Retour livraison {livraison.reference}',
                created_by=user)
            ligne.stock_applique = True
            ligne.save(update_fields=['stock_applique'])
            applied += 1
        retour.statut = RetourLivraison.Statut.VALIDE
        retour.valide_par = user
        from django.utils import timezone as _tz
        retour.valide_le = _tz.now()
        retour.save(update_fields=['statut', 'valide_par', 'valide_le'])
    return applied


# ── YHIRE9 — garde d'habilitation à l'affectation d'intervention ───────────
# Mapping type d'intervention → habilitation requise partagé avec XFSM2
# (``selectors._TYPE_VERS_HABILITATION``) : garde le SEUL référentiel, importé
# ici plutôt que dupliqué (les deux modules restent dans la même app).

def verifier_habilitation_affectation(company, technicien, type_intervention):
    """YHIRE9 — vérifie l'habilitation d'un technicien pour le type
    d'intervention qu'on s'apprête à lui affecter (contrôle à l'ÉCRITURE,
    complète XFSM2 qui ne fait QUE suggérer).

    Renvoie ``(bloquant, avertissements)`` :
      * ``bloquant`` — True seulement si le réglage société est 'block' ET
        l'habilitation requise n'est pas valide ;
      * ``avertissements`` — liste de messages FRANÇAIS (vide = rien à
        signaler). Toujours peuplée quand l'habilitation manque/expire,
        indépendamment du mode (le mode ne change que si ça bloque).

    Un type d'intervention sans mapping connu, un technicien sans fiche RH
    liée, ou aucun technicien : jamais bloquant (garde SOFT par défaut,
    cohérent avec FG176/XFSM2 — on ne bloque jamais faute de donnée)."""
    from .selectors import _TYPE_VERS_HABILITATION

    if technicien is None or company is None:
        return False, []
    cle_habilitation = _TYPE_VERS_HABILITATION.get(type_intervention)
    if not cle_habilitation:
        return False, []

    from apps.rh.selectors import (
        dossier_employe_for_user, habilitations_requises_pour_intervention,
        verifier_habilitation_requise,
    )
    # Traduit la clé intermédiaire (ex. 'pose_pv_bt') en codes RÉELS
    # `Habilitation.TypeHabilitation` (ex. ['b1v', 'br']) via
    # `INTERVENTION_HABILITATIONS` — jamais la clé intermédiaire directement
    # (celle-ci ne correspond à aucun titre réel).
    titres_requis = habilitations_requises_pour_intervention(cle_habilitation)
    if not titres_requis:
        return False, []
    dossier = dossier_employe_for_user(company, technicien.id)
    if dossier is None:
        return False, []
    rapport = verifier_habilitation_requise(
        company, dossier, titres_requis)
    if rapport['autorise']:
        return False, []

    avertissements = [rapport['message']] if rapport.get('message') else [
        'Habilitation requise manquante ou expirée : '
        f'{", ".join(titres_requis)}.'
    ]
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company)
        mode = getattr(profil, 'mode_garde_habilitation', 'warn')
    except Exception:  # pragma: no cover - défensif
        mode = 'warn'
    return (mode == 'block'), avertissements


# ── ZSTK10 — regroupement de prélèvements en lot (batch transfer) ─────────
# Les pick-lists (FG321) sont générées par chantier ; Odoo permet de grouper
# plusieurs pickings en un « Batch Transfer » qu'un magasinier traite en une
# seule tournée. `LotPrelevement` regroupe des `PickList` du MÊME dépôt.

def _depot_pick_list(pick_list):
    """Emplacement (dépôt) déduit des lignes d'une pick-list : celui du
    premier casier renseigné, ou None si aucune ligne n'a de casier (une
    pick-list sans casier ne contraint aucun dépôt — jamais bloquant)."""
    ligne = pick_list.lignes.filter(bin__isnull=False).select_related(
        'bin').first()
    return ligne.bin.emplacement_id if ligne is not None else None


def creer_lot_prelevement(company, pick_list_ids, user):
    """ZSTK10 — crée un `LotPrelevement` depuis une sélection de pick-lists du
    MÊME dépôt (scopées société). Lève ValueError si les pick-lists visent des
    dépôts différents, ou si la sélection est vide/inconnue. Référence
    anti-collision via `apps.ventes.utils.references` (jamais count()+1)."""
    from .models import PickList, LotPrelevement

    pick_lists = list(PickList.objects.filter(
        company=company, id__in=pick_list_ids or []))
    if not pick_lists:
        raise ValueError('Aucune pick-list valide sélectionnée.')

    depots = {_depot_pick_list(pl) for pl in pick_lists}
    depots.discard(None)
    if len(depots) > 1:
        raise ValueError(
            'Les pick-lists sélectionnées ne partagent pas le même dépôt.')

    def _save(reference):
        lot = LotPrelevement.objects.create(
            company=company, reference=reference, created_by=user)
        lot.pick_lists.set(pick_lists)
        return lot

    return create_with_reference(LotPrelevement, 'LOTP', company, _save)


def lignes_lot_prelevement(lot):
    """ZSTK10 — lignes CONSOLIDÉES de toutes les pick-lists du lot, triées par
    casier (`BinLocation.ordre`, réutilise l'ordonnancement FG321) pour une
    passe unique de magasinier. Renvoie une liste de dicts plats."""
    lignes = []
    for pl in lot.pick_lists.prefetch_related('lignes__produit', 'lignes__bin'):
        for li in pl.lignes.all():
            lignes.append({
                'ligne_id': li.id,
                'pick_list_id': pl.id,
                'pick_list_reference': pl.reference,
                'produit_id': li.produit_id,
                'designation': li.designation,
                'bin_id': li.bin_id,
                'bin_code': li.bin.code if li.bin_id else None,
                'ordre': li.bin.ordre if li.bin_id else 999999,
                'quantite_demandee': li.quantite_demandee,
                'quantite_prelevee': li.quantite_prelevee,
                'preleve': li.preleve,
            })
    lignes.sort(key=lambda entry: (entry['ordre'], entry['ligne_id']))
    return lignes


def cocher_ligne_lot(lot, ligne_id, quantite_prelevee=None):
    """ZSTK10 — coche une ligne du lot : propage à la `PickListLigne` source
    (même modèle, jamais dupliqué). Lève ValueError si la ligne n'appartient
    à aucune pick-list du lot. Renvoie la ligne mise à jour."""
    from .models import PickListLigne

    ligne = PickListLigne.objects.filter(
        id=ligne_id, pick_list__in=lot.pick_lists.all()).first()
    if ligne is None:
        raise ValueError('Ligne introuvable dans ce lot.')
    ligne.preleve = True
    if quantite_prelevee is not None:
        ligne.quantite_prelevee = quantite_prelevee
    elif not ligne.quantite_prelevee:
        ligne.quantite_prelevee = ligne.quantite_demandee
    ligne.save(update_fields=['preleve', 'quantite_prelevee'])
    return ligne


def cloturer_lot_prelevement(lot):
    """ZSTK10 — clôture le lot (statut TERMINE) UNIQUEMENT si TOUTES ses
    pick-lists sont soldées (statut `PickList.Statut.TERMINE`). Lève
    ValueError sinon (message français). Idempotent."""
    from .models import PickList, LotPrelevement

    non_soldees = lot.pick_lists.exclude(statut=PickList.Statut.TERMINE)
    if non_soldees.exists():
        raise ValueError(
            "Le lot ne peut être clôturé : des pick-lists ne sont pas "
            'encore soldées.')
    lot.statut = LotPrelevement.Statut.TERMINE
    lot.save(update_fields=['statut', 'date_modification'])
    return lot


# ── ZFSM3 — Interventions récurrentes autonomes (sans contrat) ──────────────
def _prochaine_echeance_intervention(echeance, regle, intervalle):
    """ZFSM3 — avance `echeance` d'un pas de la règle. Même patron que
    `apps.gestion_projet.services._prochaine_echeance_suivante` (mensuelle
    clampée en fin de mois), étendu trimestrielle/semestrielle/annuelle en
    multiples de mois."""
    from .models import RecurrenceIntervention
    import calendar
    from datetime import timedelta as _timedelta

    pas_mois = {
        RecurrenceIntervention.Regle.MENSUELLE: 1,
        RecurrenceIntervention.Regle.TRIMESTRIELLE: 3,
        RecurrenceIntervention.Regle.SEMESTRIELLE: 6,
        RecurrenceIntervention.Regle.ANNUELLE: 12,
    }
    mois_pas = pas_mois.get(regle)
    if mois_pas is None:
        # Repli défensif (règle inconnue) : pas hebdomadaire — ne devrait
        # jamais se produire avec les choix fermés du modèle.
        return echeance + _timedelta(weeks=intervalle)
    mois_total = echeance.month - 1 + mois_pas * intervalle
    annee = echeance.year + mois_total // 12
    mois = mois_total % 12 + 1
    dernier_jour = calendar.monthrange(annee, mois)[1]
    jour = min(echeance.day, dernier_jour)
    return echeance.replace(year=annee, month=mois, day=jour)


def generer_interventions_recurrentes(company, *, aujourd_hui=None):
    """ZFSM3 — génère la PROCHAINE `Intervention` de chaque récurrence ACTIVE
    à échéance (prestation périodique SANS contrat : nettoyage trimestriel,
    contrôle semestriel…). IDEMPOTENT : `prochaine_echeance` avance
    immédiatement après chaque création, donc un re-run le même jour ne crée
    JAMAIS deux occurrences pour la même échéance. Respecte `date_fin` et
    `nb_occurrences` (désactive la récurrence une fois atteinte). Renvoie la
    liste des `Intervention` créées.

    Pattern FG1/XPRJ13 (`apps.gestion_projet.services.
    generer_taches_recurrentes`) — même forme, adaptée au domaine chantier."""
    from datetime import date as _date

    from django.db import transaction

    from .models import Intervention, RecurrenceIntervention

    if aujourd_hui is None:
        aujourd_hui = _date.today()

    crees = []
    with transaction.atomic():
        recurrences = RecurrenceIntervention.objects.select_for_update().filter(
            company=company, actif=True, prochaine_echeance__lte=aujourd_hui)
        for rec in recurrences:
            # Rattrape TOUTES les échéances passées (ex. planificateur arrêté
            # un moment) : une intervention par échéance, jamais deux pour la
            # même échéance (avance systématique avant l'itération suivante).
            while rec.actif and rec.prochaine_echeance <= aujourd_hui:
                if rec.date_fin is not None \
                        and rec.prochaine_echeance > rec.date_fin:
                    rec.actif = False
                    rec.save(update_fields=['actif'])
                    break
                if rec.nb_occurrences is not None \
                        and rec.nb_generees >= rec.nb_occurrences:
                    rec.actif = False
                    rec.save(update_fields=['actif'])
                    break
                if rec.installation.annule:
                    # YSERV6 — un chantier annulé n'engendre plus de nouvelle
                    # occurrence (comportement cohérent avec la garde de
                    # création manuelle d'intervention).
                    rec.actif = False
                    rec.save(update_fields=['actif'])
                    break

                interv = Intervention.objects.create(
                    company=rec.company,
                    installation=rec.installation,
                    type_intervention=rec.type_intervention,
                    technicien=rec.technicien_defaut,
                    date_prevue=rec.prochaine_echeance,
                )
                crees.append(interv)

                rec.nb_generees += 1
                rec.prochaine_echeance = _prochaine_echeance_intervention(
                    rec.prochaine_echeance, rec.regle, rec.intervalle)
                if rec.date_fin is not None \
                        and rec.prochaine_echeance > rec.date_fin:
                    rec.actif = False
                if rec.nb_occurrences is not None \
                        and rec.nb_generees >= rec.nb_occurrences:
                    rec.actif = False
                rec.save(update_fields=[
                    'nb_generees', 'prochaine_echeance', 'actif'])
    return crees


# ─────────────────────────────────────────────────────────────────────────────
# XSTK20 — Réappro kanban deux-bacs par scan de carte.
# ─────────────────────────────────────────────────────────────────────────────

def demande_transfert_depuis_kanban(
        *, company, user, produit_id, emplacement_destination_id,
        quantite=None):
    """XSTK20 — Le scan d'une carte kanban (bac vide côté `emplacement_
    destination_id`) crée une DemandeTransfert préremplie depuis le DÉPÔT
    PRINCIPAL avec la quantité de recomplètement configurée sur la carte.

    IDEMPOTENT : si une demande NON TERMINALE (demandé/approuvé) existe déjà
    pour le même couple (produit, destination), elle est renvoyée SANS
    doublon (`created=False`). `quantite` : si non fournie, reprend le
    `StockEmplacement.seuil_max` (FG62) de cet emplacement pour ce produit ;
    à défaut, 1 (repli sûr — mieux qu'une demande à 0).

    Cross-app : `stock.EmplacementStock` / `stock.Produit` /
    `stock.StockEmplacement` lus via `apps.stock.selectors` uniquement —
    jamais leurs models importés ici."""
    from apps.stock.selectors import (
        emplacement_principal_scoped, get_emplacement_scoped,
        get_produit_scoped, seuil_max_emplacement,
    )

    produit = get_produit_scoped(company, produit_id)
    if produit is None:
        raise ValueError('Produit introuvable pour cette société.')
    destination = get_emplacement_scoped(company, emplacement_destination_id)
    if destination is None:
        raise ValueError('Emplacement introuvable pour cette société.')
    if destination.is_principal:
        raise ValueError(
            'Le dépôt principal ne peut pas être la destination d’un '
            'réappro kanban.')
    source = emplacement_principal_scoped(company)
    if source is None:
        raise ValueError(
            'Aucun dépôt principal configuré pour cette société.')

    existante = DemandeTransfert.objects.filter(
        company=company, produit_id=produit.id, source_id=source.id,
        destination_id=destination.id,
        statut__in=[DemandeTransfert.Statut.DEMANDE,
                    DemandeTransfert.Statut.APPROUVE],
    ).order_by('-date_creation').first()
    if existante is not None:
        return existante, False

    if quantite is None:
        quantite = seuil_max_emplacement(company, produit.id, destination.id)
    if not quantite or quantite <= 0:
        quantite = 1

    def _save(reference):
        return DemandeTransfert.objects.create(
            company=company, reference=reference, produit=produit,
            source=source, destination=destination, quantite=quantite,
            motif='Carte kanban scannée (bac vide) — réappro deux-bacs.',
            created_by=user)

    demande = create_with_reference(DemandeTransfert, 'DTR', company, _save)
    return demande, True


# ─────────────────────────────────────────────────────────────────────────────
# XMFG18 — Révisions de nomenclature + duplication (kits de pré-assemblage).
# ─────────────────────────────────────────────────────────────────────────────

def _composition_snapshot_kit(kit):
    """XMFG18 — sérialise la composition courante d'un kit de pré-assemblage
    en liste JSON-compatible. Aucun prix dans le snapshot."""
    out = []
    for c in kit.composants.select_related('produit').order_by('id'):
        out.append({
            'produit_id': c.produit_id,
            'designation': c.designation or (
                c.produit.nom if c.produit_id else ''),
            'quantite': c.quantite,
            'taux_perte_pct': str(c.taux_perte_pct),
        })
    return out


def snapshot_revision_kit(kit, user=None):
    """XMFG18 — crée une révision (snapshot JSON) de la composition COURANTE
    du kit de pré-assemblage si elle diffère de la dernière révision.
    Renvoie (revision, created). Idempotent — pas de doublon si la
    composition n'a pas changé."""
    from .models import RevisionKit
    composition = _composition_snapshot_kit(kit)
    derniere = kit.revisions.order_by('-numero').first()
    if derniere is not None and derniere.composition == composition:
        return derniere, False
    numero = (derniere.numero + 1) if derniere is not None else 1
    revision = RevisionKit.objects.create(
        company=kit.company, kit=kit, numero=numero,
        composition=composition, user=user)
    return revision, True


def composition_kit_au(kit, date_limite):
    """XMFG18 — « composition au JJ/MM/AAAA » : la dernière révision créée à
    la date donnée incluse. None si aucune révision à cette date."""
    return (kit.revisions
            .filter(date_creation__date__lte=date_limite)
            .order_by('-numero')
            .first())


def dupliquer_kit(kit, user=None, facteur_echelle=None):
    """XMFG18 — duplique un kit de pré-assemblage : en-tête copié
    (« <nom> (copie) », référence interne vidée), composants copiés avec
    facteur d'échelle optionnel sur les quantités (entier — arrondi propre
    ROUND_HALF_UP, jamais 0 pour un composant non nul). La copie reçoit sa
    révision n°1."""
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    from .models import Kit, KitComposant

    facteur = None
    if facteur_echelle is not None:
        try:
            facteur = Decimal(str(facteur_echelle))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Facteur d'échelle invalide.")
        if facteur <= 0:
            raise ValueError("Le facteur d'échelle doit être positif.")

    copie = Kit.objects.create(
        company=kit.company,
        nom=f'{kit.nom} (copie)',
        reference_interne=None,
        produit_compose=kit.produit_compose,
        active=kit.active,
        note=kit.note,
        created_by=user)
    for c in kit.composants.all():
        quantite = c.quantite or 0
        if facteur is not None and quantite:
            quantite = int(
                (Decimal(quantite) * facteur).to_integral_value(
                    rounding=ROUND_HALF_UP))
            quantite = max(quantite, 1)
        KitComposant.objects.create(
            kit=copie, produit_id=c.produit_id, designation=c.designation,
            quantite=quantite, taux_perte_pct=c.taux_perte_pct)
    snapshot_revision_kit(copie, user=user)
    return copie


# ─────────────────────────────────────────────────────────────────────────────
# XMFG19 — Remplacement de masse d'un composant (kits de pré-assemblage).
# ─────────────────────────────────────────────────────────────────────────────

def remplacer_composant_kits(company, *, produit_ancien_id, produit_nouveau_id,
                             ratio=None, user=None):
    """XMFG19 — remplace `produit_ancien` par `produit_nouveau` dans TOUTES
    les nomenclatures de kits de pré-assemblage de la société, avec ratio de
    quantité optionnel (arrondi entier ROUND_HALF_UP, jamais 0 pour une ligne
    non nulle). Chaque kit modifié reçoit sa révision XMFG18. Renvoie la
    liste des kits modifiés [{kit_id, kit_nom, quantite_avant,
    quantite_apres}]. L'appelant (stock) enveloppe le tout dans UNE
    transaction atomique — pas de transaction ici."""
    from decimal import Decimal, ROUND_HALF_UP
    from .models import KitComposant

    modifies = []
    kits_touches = {}
    lignes = (KitComposant.objects
              .filter(kit__company=company, produit_id=produit_ancien_id)
              .select_related('kit')
              .order_by('kit__nom', 'id'))
    for c in lignes:
        quantite_avant = c.quantite
        quantite = c.quantite or 0
        if ratio is not None and quantite:
            quantite = int(
                (Decimal(quantite) * Decimal(str(ratio))).to_integral_value(
                    rounding=ROUND_HALF_UP))
            quantite = max(quantite, 1)
        c.produit_id = produit_nouveau_id
        c.quantite = quantite
        c.save(update_fields=['produit', 'quantite'])
        kits_touches[c.kit_id] = c.kit
        modifies.append({
            'kit_id': c.kit_id,
            'kit_nom': c.kit.nom,
            'quantite_avant': quantite_avant,
            'quantite_apres': quantite,
        })
    for kit in kits_touches.values():
        snapshot_revision_kit(kit, user=user)
    return modifies
