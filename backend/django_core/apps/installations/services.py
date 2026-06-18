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
    ChantierChecklistItem,
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
    return inst, True
