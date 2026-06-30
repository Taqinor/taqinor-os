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

    IDEMPOTENT : si un chantier existe déjà pour ce devis, on le RETOURNE tel
    quel (created=False) sans en créer un second. C'est ce garde-fou qui rend
    sûre l'auto-création sur l'événement ``devis_accepted`` (cf.
    ``apps/installations/receivers.py``) : ré-accepter un devis ou ré-émettre
    l'événement ne duplique jamais le chantier. Le chantier porte la société du
    devis (``company``), jamais une valeur issue d'une requête.
    """
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
