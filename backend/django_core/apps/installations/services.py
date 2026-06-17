"""
Création d'un chantier À PARTIR D'UN DEVIS — pré-remplissage + anti-doublon.

Le chantier hérite : client, adresse du SITE (depuis le lead, éditable ensuite),
puissance (depuis l'étude du devis sinon la taille souhaitée du lead),
raccordement GELÉ (depuis le lead), type d'installation (depuis le devis).
Référence sans collision via l'utilitaire commun (jamais count()+1).
"""
from apps.ventes.utils.references import create_with_reference
from .models import (
    Installation, ChecklistEtapeModele, ChantierChecklistItem,
)

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


def seed_checklist_etapes(company):
    """Amorce les étapes de checklist par défaut (idempotent, additif)."""
    if company is None or ChecklistEtapeModele.objects.filter(company=company).exists():
        return
    for i, (cle, libelle, capture) in enumerate(DEFAULT_CHECKLIST_ETAPES):
        ChecklistEtapeModele.objects.get_or_create(
            company=company, cle=cle,
            defaults={'libelle': libelle, 'ordre': i,
                      'capture_serie': capture, 'protege': True})


def ensure_checklist_items(installation):
    """Matérialise les étapes de checklist d'un chantier depuis les modèles
    ACTIFS de sa société (création paresseuse, sans doublon). Renvoie la liste
    ordonnée des items du chantier."""
    company = installation.company
    seed_checklist_etapes(company)
    existing = {it.cle for it in installation.checklist.all()}
    modeles = ChecklistEtapeModele.objects.filter(company=company, actif=True)
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
    libres (sans produit catalogue)."""
    bom = []
    try:
        lignes = devis.lignes.select_related('produit')
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

    # Installateur par défaut : le créateur du chantier (à défaut, None).
    # « Signé » est le 1er jalon de l'entonnoir N1 ; la date de signature
    # reprend la date d'acceptation du devis quand elle existe.
    date_signature = getattr(devis, 'date_acceptation', None) or None

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
            technicien_responsable=user,
            created_by=user,
        )

    inst = create_with_reference(Installation, 'CHT', company, _create)
    return inst, True
