"""NTEXT36 — audit des changements de PLATEFORME par l'admin.

Quand un admin crée/modifie/supprime une brique de la plateforme no-code
(objet personnalisé, règle d'automatisation, définition de rapport, gabarit de
document…), une ligne ``parametres.SettingsAuditLog`` est écrite en
``section='plateforme'`` : QUI, QUOI, QUAND, et l'ancienne → la nouvelle
valeur. C'est la MÊME table (et le même écran « Journal des paramètres ») que
l'audit déjà en place sur ``CustomFieldDefViewSet`` (section='champs') — aucun
second journal n'est créé.

Pourquoi une section DÉDIÉE plutôt que réutiliser 'champs'/'automatisations' :
le journal plateforme répond à une question transverse (« qu'est-ce qui a
changé dans la CONFIGURATION de la plateforme, tous types confondus ? ») que
les sections par domaine ne couvrent pas. Les lignes existantes ne sont ni
déplacées ni modifiées — l'ajout est purement additif.

Écriture DÉFENSIVE : journaliser ne doit jamais faire échouer l'écriture
métier qu'on est en train de tracer (même patron que ``_audit_rule`` dans
``apps.automation.views``).
"""
import logging

logger = logging.getLogger(__name__)

__all__ = ['SECTION_PLATEFORME', 'journaliser_plateforme',
           'AuditPlateformeMixin']

#: Section du ``SettingsAuditLog`` portant les changements de plateforme.
SECTION_PLATEFORME = 'plateforme'


def journaliser_plateforme(company, user, cible, identifiant, libelle,
                           old=None, new=None):
    """Écrit UNE ligne d'audit plateforme (best-effort, jamais bloquante).

    ``cible`` = type de brique ('objet', 'regle', 'rapport', 'gabarit'…),
    ``identifiant`` = clé lisible de l'élément (code ou pk), ``libelle`` =
    l'action en clair (« Objet personnalisé créé »).
    """
    try:
        from apps.parametres.models import SettingsAuditLog

        return SettingsAuditLog.log_change(
            company=company,
            user=user if getattr(user, 'is_authenticated', False) else None,
            section=SECTION_PLATEFORME,
            field=f'{cible}:{identifiant}'[:100],
            field_label=(libelle or '')[:150],
            old=old, new=new,
        )
    except Exception:  # pragma: no cover — défensif
        logger.warning('Audit plateforme non écrit (%s:%s)', cible,
                       identifiant, exc_info=True)
        return None


class AuditPlateformeMixin:
    """Mixin de ViewSet : journalise create/update/destroy en 'plateforme'.

    À poser AVANT le viewset de base dans la MRO. Le viewset renseigne
    ``audit_plateforme_cible`` et, au besoin, surcharge
    ``audit_plateforme_identifiant``/``audit_plateforme_resume``.
    """

    #: Type de brique tracé (segment ``field`` du journal).
    audit_plateforme_cible = 'plateforme'
    #: Nom lisible utilisé dans le libellé (« … créé / modifié / supprimé »).
    audit_plateforme_nom = 'Élément de plateforme'

    def audit_plateforme_identifiant(self, instance):
        return getattr(instance, 'code', None) or getattr(
            instance, 'pk', '') or ''

    def audit_plateforme_resume(self, instance):
        """Valeur lisible mémorisée dans ``old_value``/``new_value``."""
        for attribut in ('libelle', 'nom', 'titre', 'code'):
            valeur = getattr(instance, attribut, None)
            if valeur:
                return str(valeur)
        return str(instance)

    def _journaliser_plateforme(self, instance, libelle, old=None, new=None):
        utilisateur = getattr(self.request, 'user', None)
        journaliser_plateforme(
            company=getattr(utilisateur, 'company', None), user=utilisateur,
            cible=self.audit_plateforme_cible,
            identifiant=self.audit_plateforme_identifiant(instance),
            libelle=libelle, old=old, new=new)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        instance = serializer.instance
        self._journaliser_plateforme(
            instance, f'{self.audit_plateforme_nom} créé',
            old=None, new=self.audit_plateforme_resume(instance))

    def perform_update(self, serializer):
        avant = self.audit_plateforme_resume(serializer.instance)
        super().perform_update(serializer)
        instance = serializer.instance
        self._journaliser_plateforme(
            instance, f'{self.audit_plateforme_nom} modifié',
            old=avant, new=self.audit_plateforme_resume(instance))

    def perform_destroy(self, instance):
        # Journaliser AVANT la suppression : après, l'identifiant et le
        # résumé ne sont plus lisibles de façon fiable.
        avant = self.audit_plateforme_resume(instance)
        libelle = f'{self.audit_plateforme_nom} supprimé'
        identifiant = self.audit_plateforme_identifiant(instance)
        super().perform_destroy(instance)
        utilisateur = getattr(self.request, 'user', None)
        journaliser_plateforme(
            company=getattr(utilisateur, 'company', None), user=utilisateur,
            cible=self.audit_plateforme_cible, identifiant=identifiant,
            libelle=libelle, old=avant, new=None)
