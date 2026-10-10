"""Aides partagées par plusieurs vues de l'app Paramètres.

``_profile`` et ``_audit_company`` sont utilisés à la fois par les vues du
profil et par les vues d'upload/suppression d'images — regroupés ici pour
éviter une dépendance circulaire entre fichiers de domaine."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

from .models import CompanyProfile, SettingsAuditLog

#: ENF8 — paramètre de requête ``?actif=`` lu par les référentiels
#: (``true``/``1`` ne garde que les lignes actives ; toute autre valeur = tout).
ACTIF_PARAM = OpenApiParameter(
    'actif', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False,
    enum=['true', '1'],
    description='« true » ou « 1 » : ne garder que les lignes actives.')


def _audit_company(request):
    return request.user.company if request.user.company_id else None


def _profile(request):
    """Return the CompanyProfile for the current user's company."""
    return CompanyProfile.get(
        company=request.user.company if request.user.company_id else None
    )


# ── APAR28 — journal d'audit UNIQUE des écritures de réglages ───────────────
#: Champs techniques jamais journalisés (société posée serveur, horodatages).
_CHAMPS_NON_AUDITES = frozenset({
    'id', 'company', 'date_creation', 'date_modification', 'created_at',
    'updated_at',
})


def _instantane(instance):
    """État AUDITABLE d'un réglage : ses champs concrets (valeur brute)."""
    return {
        f.name: getattr(instance, f.attname)
        for f in instance._meta.concrete_fields
        if f.name not in _CHAMPS_NON_AUDITES
    }


def _texte(etat):
    return '; '.join(f'{k}={v}' for k, v in etat.items())


class SettingsAuditedMixin:
    """APAR28 — ``perform_create/update/destroy`` journalisés dans
    ``SettingsAuditLog`` (qui, quand, ancien → nouveau) pour TOUT ViewSet
    d'écriture de réglages. À placer AVANT le ViewSet de base dans la MRO.

    ``audit_section`` nomme la section du journal ; ``audit_libelle`` le
    réglage en clair. Une modification sans changement n'écrit rien ; les
    actions maison (``set_defaut``…) journalisent par :meth:`_journaliser`."""

    audit_section = 'parametres'
    audit_libelle = 'Réglage'

    def _journaliser(self, instance_pk, action, old='', new=''):
        user = self.request.user
        SettingsAuditLog.log_change(
            company=user.company if user.company_id else None, user=user,
            section=self.audit_section,
            field=f'{self.audit_section}:{instance_pk}'[:100],
            field_label=f'{self.audit_libelle} {action}'[:150],
            old=old, new=new)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._journaliser(serializer.instance.pk, 'créé',
                          new=_texte(_instantane(serializer.instance)))

    def perform_update(self, serializer):
        avant = _instantane(serializer.instance)
        super().perform_update(serializer)
        apres = _instantane(serializer.instance)
        changes = [k for k in apres if apres[k] != avant.get(k)]
        if changes:
            self._journaliser(
                serializer.instance.pk, 'modifié',
                old=_texte({k: avant.get(k) for k in changes}),
                new=_texte({k: apres[k] for k in changes}))

    def perform_destroy(self, instance):
        pk, avant = instance.pk, _instantane(instance)  # delete() → pk None
        super().perform_destroy(instance)
        self._journaliser(pk, 'supprimé', old=_texte(avant))
