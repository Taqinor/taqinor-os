"""ASEC59 — garde d'ÉCRITURE ACL des gestes GED restés sans ACL.

Sortie de ``views.py`` (fichier-mur, budget 0 ligne nette — C20) : les gestes
qui modifient un document exigent l'ACL d'écriture
(``selectors.assert_acl_niveau(…, 'ecriture')``, 403 comme ``purger``).
"""
from rest_framework.exceptions import NotFound, PermissionDenied

from . import selectors

#: Actions de ``DocumentViewSet`` soumises à l'ACL d'écriture (ASEC59).
ACTIONS_ECRITURE_ASEC59 = (
    'verrouiller', 'deverrouiller', 'office_ouvrir', 'demander_revue',
    'archiver_legalement', 'placer_legal_hold', 'lever_legal_hold',
    'planifier',
)


def exiger_ecriture(document, user, visible=False):
    """403 si ``user`` n'a pas l'écriture sur ``document`` ; avec
    ``visible``, 404 « Document inconnu. » d'abord s'il ne le voit pas."""
    if document is None:
        return
    if visible and not selectors.documents_visible_to_user(
            user).filter(pk=document.pk).exists():
        raise NotFound('Document inconnu.')
    try:
        selectors.assert_acl_niveau(document, user, 'ecriture')
    except PermissionError as exc:
        raise PermissionDenied(str(exc))


class LienEcritureMixin:
    """Délier modifie le document : écriture ACL exigée."""

    def perform_destroy(self, instance):
        exiger_ecriture(instance.document, self.request.user)
        super().perform_destroy(instance)


class PartageEcritureMixin:
    """Partage public : document visible (404) puis écriture (403).
    company + created_by posés côté serveur (jamais du corps) ; le document
    est validé company-scopé dans le serializer (`validate_document`)."""

    def perform_create(self, serializer):
        exiger_ecriture(serializer.validated_data['document'],
                        self.request.user, visible=True)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        exiger_ecriture(serializer.validated_data.get(
            'document', serializer.instance.document),
            self.request.user, visible=True)
        serializer.save()


class PlanificationEcritureMixin:
    """Planifier un document exige l'écriture ACL sur ce document."""

    def perform_create(self, serializer):
        exiger_ecriture(serializer.validated_data.get('document'),
                        self.request.user)
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)
