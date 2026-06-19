"""N105 — Lecture de l'interrupteur maître DGI (``dgi_export_actif``).

Source unique de vérité pour savoir si la capacité DGI locale est armée pour
une société. Tant qu'il renvoie False (défaut), la capacité reste totalement
invisible et l'endpoint gardé se comporte comme « introuvable ».
"""


def is_dgi_enabled(company):
    """Renvoie True si la capacité DGI locale est armée pour ``company``.

    Robuste par défaut : toute société sans profil (ou ``company`` None) ⇒
    désarmé. Ne crée jamais de profil, ne lève jamais (un échec de lecture =
    OFF), pour rester strictement sans effet de bord quand OFF.
    """
    if company is None:
        return False
    try:
        from apps.parametres.models import CompanyProfile
        profile = (CompanyProfile.objects
                   .filter(company=company)
                   .only('dgi_export_actif')
                   .first())
        return bool(profile and profile.dgi_export_actif)
    except Exception:  # pragma: no cover - lecture best-effort, OFF si échec
        return False
