"""
Création d'un chantier À PARTIR D'UN DEVIS — pré-remplissage + anti-doublon.

Le chantier hérite : client, adresse du SITE (depuis le lead, éditable ensuite),
puissance (depuis l'étude du devis sinon la taille souhaitée du lead),
raccordement GELÉ (depuis le lead), type d'installation (depuis le devis).
Référence sans collision via l'utilitaire commun (jamais count()+1).
"""
from apps.ventes.utils.references import create_with_reference
from .models import ChecklistItem, Installation


def ensure_checklist(installation):
    """Pré-remplit la checklist d'un chantier depuis les défauts de la société.

    Appelé à la création du chantier et PARESSEUSEMENT (si la liste est vide)
    au premier accès. Idempotent : ne crée rien si le chantier a déjà des
    étapes. Retourne le queryset ordonné des étapes.
    """
    # Requête fraîche (jamais le cache de prefetch, qui peut être vide après un
    # get_object() précédent).
    qs = ChecklistItem.objects.filter(installation=installation).order_by(
        'ordre', 'id')
    if qs.exists():
        return qs
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.get(company=installation.company)
    labels = profile.chantier_checklist_effective
    ChecklistItem.objects.bulk_create([
        ChecklistItem(
            company=installation.company, installation=installation,
            label=label, ordre=(i + 1) * 10)
        for i, label in enumerate(labels)
    ])
    return ChecklistItem.objects.filter(installation=installation).order_by(
        'ordre', 'id')


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
            statut=Installation.Statut.A_PLANIFIER,
            created_by=user,
        )

    inst = create_with_reference(Installation, 'CHT', company, _create)
    ensure_checklist(inst)
    return inst, True
