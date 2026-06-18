"""Aides partagées par plusieurs vues de l'app Paramètres.

``_profile`` et ``_audit_company`` sont utilisés à la fois par les vues du
profil et par les vues d'upload/suppression d'images — regroupés ici pour
éviter une dépendance circulaire entre fichiers de domaine."""
from .models import CompanyProfile


def _audit_company(request):
    return request.user.company if request.user.company_id else None


def _profile(request):
    """Return the CompanyProfile for the current user's company."""
    return CompanyProfile.get(
        company=request.user.company if request.user.company_id else None
    )
