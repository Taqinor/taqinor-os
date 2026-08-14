"""Services (écriture/orchestration) du module ``apps.douane``.

Import local des modèles d'autres apps (jamais au niveau module) — toute
lecture d'un document d'une autre app se fait via son ``selectors.py`` ou en
recevant directement l'instance/l'id en paramètre (jamais un import direct de
``apps.<autre_app>.models`` depuis ce fichier).

Revue coordinateur (NTLOG14, post-fold) — deux motifs à ne JAMAIS réintroduire
sur un nouveau modèle numéroté :
  1. ``next_reference`` défaut ``field='reference'`` — un modèle dont le champ
     numéroté ne s'appelle pas littéralement ``reference`` (ici ``numero``)
     DOIT passer ``field=`` explicitement, sinon ``FieldError`` à CHAQUE appel
     (``DossierExport`` n'a pas de champ ``reference``).
  2. Le motif create-puis-numérote (``numero=''`` inséré, puis mis à jour)
     DOIT être enveloppé dans ``transaction.atomic()`` : sans ça, un échec de
     numérotation laisse une ligne ``numero=''`` committée, et
     ``unique_together (company, numero)`` empêche alors TOUTE création
     suivante pour cette société.
"""
from django.db import transaction

from core.numbering import next_reference


def attribuer_numero_dossier_export(dossier):
    """NTLOG14 — pose ``dossier.numero`` (anti-collision, plus-haut-utilisé+1
    par société) via ``core.numbering`` — jamais un ``count()+1`` (ARC6).
    No-op si déjà posé (idempotent). ``field='numero'`` explicite : le défaut
    de ``next_reference`` (``'reference'``) n'existe pas sur ce modèle."""
    if dossier.numero:
        return dossier

    from .models import DossierExport

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
    même appel », jamais une déduction magique d'un champ inexistant.
    Création + numérotation dans UNE SEULE transaction (sinon une ligne
    ``numero=''`` orpheline bloquerait la société — voir docstring module)."""
    from .models import DossierExport

    with transaction.atomic():
        dossier = DossierExport.objects.create(
            company=company, facture=facture, pays_destinataire=pays_destinataire,
            incoterm=incoterm, port_embarquement=port_embarquement,
            port_debarquement=port_debarquement, devise=devise,
            valeur_marchandise_devise=valeur_marchandise_devise,
            created_by=created_by)
        return attribuer_numero_dossier_export(dossier)
