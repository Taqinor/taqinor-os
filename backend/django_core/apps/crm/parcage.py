"""ACRM65 / ACRM66 — fonctions CRM PARQUÉES derrière un réglage société
(décision fondateur D-ACRM-6 (ii)=(b) et (iii)=(b), 09/10/2026).

Les salles de vente (``CompanyProfile.salles_vente_actif``) et les
apporteurs / deals enregistrés (``CompanyProfile.apporteurs_actif``) n'ont
aucun écran de création dans l'ERP : ÉTEINTS par défaut, ils ne servent plus
rien et ne calculent plus rien en arrière-plan ; allumés, ils se comportent
exactement comme avant. Aucune donnée n'est jamais supprimée.

UN SEUL lecteur des réglages : ce module (patron
``leads_attribution.default_responsable_for`` — profil relu à chaque appel,
jamais mis en cache). Module neutre : n'importe aucune vue.
"""

SALLES_VENTE = 'salles_vente_actif'
APPORTEURS = 'apporteurs_actif'


def reglage_actif(company_id, champ):
    """Vrai si le réglage société ``champ`` est ALLUMÉ pour ``company_id``.

    Société sans profil ou id vide ⇒ ``False`` (le défaut du réglage)."""
    if not company_id:
        return False
    from apps.parametres.models import CompanyProfile
    valeur = (CompanyProfile.objects.filter(company_id=company_id)
              .values_list(champ, flat=True).first())
    return bool(valeur)


def salles_vente_actives(company_id):
    """ACRM65 — les salles de vente sont-elles servies pour cette société ?"""
    return reglage_actif(company_id, SALLES_VENTE)


def apporteurs_actifs(company_id):
    """ACRM66 — apporteurs et deals enregistrés servis (et commission
    calculée au devis accepté) pour cette société ?"""
    return reglage_actif(company_id, APPORTEURS)


class ApporteursParquesMixin:
    """ACRM66 — viewset parqué : réglage éteint ⇒ TOUTE route répond 404
    (après l'authentification et les permissions, donc 401/403 inchangés).
    Rien n'est supprimé ; allumé, le viewset est intact."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # CI #997 api-fuzz : une méthode que la route ne porte pas (``action``
        # nul — TRACE, PUT sur une liste…) reste un 405 : la porte parquée
        # n'y répond pas 404, la réponse ne dépend pas du réglage.
        if hasattr(self, 'action') and self.action is None:
            return
        if not apporteurs_actifs(getattr(request.user, 'company_id', None)):
            from rest_framework.exceptions import NotFound
            raise NotFound()
