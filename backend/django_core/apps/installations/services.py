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
    ChantierChecklistItem, StockReservation,
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

    Si un chantier existe déjà pour ce devis, on le RETOURNE (pas de doublon).
    """
    existing = Installation.objects.filter(devis=devis).first()
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
    # N14 — réserve le stock des SKU de la nomenclature gelée (robuste si le
    # BOM est vide : aucune réservation, aucun plantage).
    seed_reservations(inst)
    return inst, True


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
    from apps.stock.models import Produit
    company = installation.company
    besoins = _bom_quantities(installation)
    valid_ids = set(
        Produit.objects.filter(
            id__in=list(besoins), company=company
        ).values_list('id', flat=True)
    ) if besoins else set()
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
    from apps.stock.models import Produit, MouvementStock

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
            produit = Produit.objects.select_for_update().get(pk=resa.produit_id)
            qte_avant = produit.quantite_stock
            # ERR80 — garde plancher : ne pilote jamais le stock en négatif. On
            # sort au plus le stock en main (borné à zéro), comme la
            # réconciliation terrain et les pièces SAV.
            qte_sortie = min(resa.quantite, qte_avant) if qte_avant > 0 else 0
            qte_apres = qte_avant - qte_sortie
            MouvementStock.objects.create(
                company=installation.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=qte_sortie,
                quantite_avant=qte_avant, quantite_apres=qte_apres,
                reference=installation.reference,
                note=f'Consommation chantier {installation.reference}',
                created_by=user)
            produit.quantite_stock = qte_apres
            produit.save(update_fields=['quantite_stock'])
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
