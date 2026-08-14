"""Services (écriture/orchestration) du module ``apps.douane``.

Import local des modèles d'autres apps (jamais au niveau module) — toute
lecture d'un document d'une autre app se fait via son ``selectors.py`` ou en
recevant directement l'instance/l'id en paramètre (jamais un import direct de
``apps.<autre_app>.models`` depuis ce fichier)."""
from django.db import transaction

from core.numbering import next_reference


def attribuer_numero_dossier_export(dossier):
    """NTLOG14 — pose ``dossier.numero`` (anti-collision, plus-haut-utilisé+1
    par société) via ``core.numbering`` — jamais un ``count()+1`` (ARC6).
    No-op si déjà posé (idempotent)."""
    if dossier.numero:
        return dossier

    from .models import DossierExport

    # `field='numero'` est OBLIGATOIRE : next_reference cherche par défaut un
    # champ `reference`, absent de ce modèle — l'omettre lève un FieldError à
    # chaque création (« Cannot resolve keyword 'reference' into field »).
    dossier.numero = next_reference(
        DossierExport, 'EXP', dossier.company, padding=4, period='monthly',
        field='numero')
    dossier.save(update_fields=['numero'])
    return dossier


def creer_dossier_export_depuis_facture(
        *, company, facture, pays_destinataire, incoterm='',
        port_embarquement='', port_debarquement='', devise='',
        valeur_marchandise_devise=0, created_by=None):
    """NTLOG14 — crée un ``DossierExport`` à partir d'une
    ``facturation.Facture`` (reçue en paramètre, jamais importée au niveau
    module). Le pays destinataire est capturé EXPLICITEMENT à l'appel : ni
    ``facturation.Facture`` ni ``crm.Client`` ne portent de champ pays
    structuré dans ce dépôt, donc « hérite du pays destinataire » se traduit
    ici par « le dossier créé depuis cette facture porte le pays donné au
    même appel », jamais une déduction magique d'un champ inexistant."""
    from .models import DossierExport

    # Même garde que le viewset : insertion + numérotation dans UNE
    # transaction, sinon un échec de numérotation laisse une ligne
    # `numero=''` committée qui bloque définitivement la société
    # (unique_together (company, numero)).
    with transaction.atomic():
        dossier = DossierExport.objects.create(
            company=company, facture=facture,
            pays_destinataire=pays_destinataire,
            incoterm=incoterm, port_embarquement=port_embarquement,
            port_debarquement=port_debarquement, devise=devise,
            valeur_marchandise_devise=valeur_marchandise_devise,
            created_by=created_by)
        return attribuer_numero_dossier_export(dossier)
