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
    from django.utils import timezone
    from .models import ControleQualiteOrdre

    controle = ControleQualiteOrdre.objects.select_related('item_modele').get(
        ordre=ordre, item_modele_id=item_modele_id)
    item = controle.item_modele

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
