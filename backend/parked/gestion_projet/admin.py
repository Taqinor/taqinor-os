from django.contrib import admin

from .models import (
    ActionProjet,
    BudgetProjet,
    ClotureProjet,
    CommentaireProjet,
    CompteRenduReunion,
    DependanceTache,
    DocumentProjet,
    LotSousTraitance,
    Jalon,
    LigneBudgetProjet,
    ModeleProjet,
    ModeleTache,
    PhaseProjet,
    PortailProjetToken,
    Projet,
    ProjetActivity,
    ProjetChantier,
    ProjetLien,
    Risque,
    SousTraitant,
    Tache,
    Timesheet,
    VersionDocument,
)


class _AdminScopeSociete(admin.ModelAdmin):
    """AUD315 — base ADMIN scopée société pour tout le module.

    Aucun `ModelAdmin` de ce fichier ne surchargeait `get_queryset` : un compte
    `is_staff` d'une société voyait — et pouvait modifier — les lignes de TOUTES
    les sociétés. Or `is_staff` n'est PAS réservé aux comptes internes : le
    seeder de démo et l'inscription posent des comptes admin scopés société qui
    peuvent le porter (`seed_demo_company.py`, `authentication/views.py`).

    Règle : un superutilisateur voit tout (administration plateforme) ; tout
    autre compte ne voit QUE sa société ; un compte sans société ne voit RIEN
    (fail-closed, jamais « tout » par défaut). Les permissions objet
    (voir/modifier/supprimer) refusent en plus toute ligne d'une autre société,
    pour qu'une URL de détail devinée ne contourne pas le filtrage de liste.
    """

    def _societe_utilisateur(self, request):
        return getattr(getattr(request, 'user', None), 'company_id', None)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if getattr(request.user, 'is_superuser', False):
            return qs
        company_id = self._societe_utilisateur(request)
        if company_id is None:
            return qs.none()
        return qs.filter(company_id=company_id)

    def _meme_societe(self, request, obj):
        if obj is None:
            return True
        if getattr(request.user, 'is_superuser', False):
            return True
        company_id = self._societe_utilisateur(request)
        return company_id is not None and obj.company_id == company_id

    def has_view_permission(self, request, obj=None):
        return (super().has_view_permission(request, obj)
                and self._meme_societe(request, obj))

    def has_change_permission(self, request, obj=None):
        return (super().has_change_permission(request, obj)
                and self._meme_societe(request, obj))

    def has_delete_permission(self, request, obj=None):
        return (super().has_delete_permission(request, obj)
                and self._meme_societe(request, obj))


@admin.register(Projet)
class ProjetAdmin(_AdminScopeSociete):
    list_display = ('code', 'nom', 'statut', 'company', 'responsable',
                    'date_debut', 'date_fin_prevue')
    list_filter = ('statut',)
    search_fields = ('code', 'nom', 'description')


@admin.register(ProjetChantier)
class ProjetChantierAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'chantier_id', 'libelle', 'company')
    list_filter = ('company',)
    search_fields = ('libelle',)


@admin.register(ProjetLien)
class ProjetLienAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'type_cible', 'cible_id', 'libelle',
                    'company')
    list_filter = ('type_cible', 'company')
    search_fields = ('libelle',)


@admin.register(PhaseProjet)
class PhaseProjetAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'type_phase', 'ordre', 'statut',
                    'avancement_pct', 'company')
    list_filter = ('type_phase', 'statut', 'company')
    search_fields = ('libelle',)


@admin.register(Tache)
class TacheAdmin(_AdminScopeSociete):
    list_display = ('id', 'code_wbs', 'libelle', 'projet', 'phase', 'parent',
                    'statut', 'avancement_pct', 'company')
    list_filter = ('statut', 'company')
    search_fields = ('libelle', 'code_wbs')


@admin.register(DependanceTache)
class DependanceTacheAdmin(_AdminScopeSociete):
    list_display = ('id', 'predecesseur', 'successeur', 'type_dependance',
                    'lag', 'company')
    list_filter = ('type_dependance', 'company')


@admin.register(Jalon)
class JalonAdmin(_AdminScopeSociete):
    list_display = ('id', 'libelle', 'projet', 'date_prevue', 'date_reelle',
                    'statut', 'facturation_pct', 'company')
    list_filter = ('statut', 'company')
    search_fields = ('libelle', 'description')


@admin.register(ProjetActivity)
class ProjetActivityAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'old_value', 'new_value', 'auteur',
                    'company', 'date_creation')
    list_filter = ('company',)
    search_fields = ('old_value', 'new_value')


@admin.register(BudgetProjet)
class BudgetProjetAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'libelle', 'version', 'statut', 'devise',
                    'company', 'date_creation')
    list_filter = ('statut', 'company')
    search_fields = ('libelle',)


@admin.register(LigneBudgetProjet)
class LigneBudgetProjetAdmin(_AdminScopeSociete):
    list_display = ('id', 'budget', 'categorie', 'libelle', 'quantite', 'pu',
                    'montant_prevu', 'company')
    list_filter = ('categorie', 'company')
    search_fields = ('libelle',)


@admin.register(Timesheet)
class TimesheetAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'ressource', 'tache', 'date', 'heures',
                    'cout', 'company')
    list_filter = ('company',)
    search_fields = ('commentaire',)


@admin.register(Risque)
class RisqueAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'libelle', 'categorie', 'probabilite',
                    'impact', 'criticite', 'statut', 'company')
    list_filter = ('statut', 'categorie', 'company')
    search_fields = ('libelle', 'description', 'mitigation')


@admin.register(ActionProjet)
class ActionProjetAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'libelle', 'statut', 'priorite',
                    'responsable', 'echeance', 'company')
    list_filter = ('statut', 'priorite', 'company')
    search_fields = ('libelle', 'description')


@admin.register(CompteRenduReunion)
class CompteRenduReunionAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'titre', 'date_reunion', 'lieu',
                    'redacteur', 'company')
    list_filter = ('company',)
    search_fields = ('titre', 'decisions', 'ordre_du_jour')


@admin.register(DocumentProjet)
class DocumentProjetAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'nom', 'type_doc', 'derniere_version',
                    'company')
    list_filter = ('type_doc', 'company')
    search_fields = ('nom', 'description')


@admin.register(VersionDocument)
class VersionDocumentAdmin(_AdminScopeSociete):
    list_display = ('id', 'document', 'version', 'auteur', 'company',
                    'date_creation')
    list_filter = ('company',)
    search_fields = ('commentaire',)


@admin.register(CommentaireProjet)
class CommentaireProjetAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'cible_type', 'cible_id', 'auteur',
                    'company', 'date_creation')
    list_filter = ('cible_type', 'company')
    search_fields = ('texte',)


@admin.register(ModeleProjet)
class ModeleProjetAdmin(_AdminScopeSociete):
    list_display = ('id', 'nom', 'type_installation', 'actif', 'company')
    list_filter = ('type_installation', 'actif', 'company')
    search_fields = ('nom', 'description')


@admin.register(ModeleTache)
class ModeleTacheAdmin(_AdminScopeSociete):
    list_display = ('id', 'modele', 'type_phase', 'libelle', 'ordre',
                    'company')
    list_filter = ('type_phase', 'company')
    search_fields = ('libelle',)


@admin.register(PortailProjetToken)
class PortailProjetTokenAdmin(_AdminScopeSociete):
    """AUD315 — le jeton du portail projet n'est plus cherchable NI affichable.

    `search_fields = ('token',)` permettait à n'importe quel compte staff de
    retrouver — et de lire en clair — le jeton du portail public de N'IMPORTE
    QUELLE société, donc d'ouvrir le portail client d'un autre tenant sans
    jamais s'y authentifier. Le jeton EST le secret de ce portail : on cherche
    désormais par projet, et le champ est retiré du formulaire (il reste posé
    côté serveur à la création de l'accès).
    """
    list_display = ('id', 'projet', 'actif', 'company', 'date_creation')
    list_filter = ('actif', 'company')
    search_fields = ('projet__code', 'projet__nom')
    exclude = ('token',)


@admin.register(SousTraitant)
class SousTraitantAdmin(_AdminScopeSociete):
    list_display = ('id', 'nom', 'specialite', 'contact', 'actif', 'company')
    list_filter = ('actif', 'company')
    search_fields = ('nom', 'specialite', 'contact')


@admin.register(LotSousTraitance)
class LotSousTraitanceAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'sous_traitant', 'libelle', 'montant',
                    'statut', 'company')
    list_filter = ('statut', 'company')
    search_fields = ('libelle', 'description')


@admin.register(ClotureProjet)
class ClotureProjetAdmin(_AdminScopeSociete):
    list_display = ('id', 'projet', 'date_cloture', 'date_reception',
                    'cloture_par', 'company')
    list_filter = ('company',)
    search_fields = ('points_positifs', 'recommandations')
