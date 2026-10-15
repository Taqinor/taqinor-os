"""ENF18 — pose du document « schéma unifilaire » d'un chantier sous verrou.

``(installation, type_doc)`` n'a pas de contrainte d'unicité en base (un
chantier porte N révisions d'autres types) : le verrou de la ligne chantier
sérialise deux (re)générations concurrentes du même schéma.
"""
from django.db import transaction

from .models import DocumentProjet


def poser_document_schema_unifilaire(installation, titre, pointeur):
    """Crée ou réaligne l'unique document unifilaire du chantier."""
    type_doc = DocumentProjet.TypeDoc.SCHEMA_UNIFILAIRE
    with transaction.atomic():
        type(installation).objects.select_for_update().filter(
            pk=installation.pk).first()
        doc = DocumentProjet.objects.filter(
            installation=installation, type_doc=type_doc).order_by('id').first()
        if doc is None:
            return DocumentProjet.objects.create(
                installation=installation, type_doc=type_doc,
                company=installation.company, titre=titre, notes=pointeur)
        if doc.titre != titre or doc.notes != pointeur:
            doc.titre = titre
            doc.notes = pointeur
            doc.save(update_fields=['titre', 'notes'])
        return doc
