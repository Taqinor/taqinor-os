"""Réglages société lus par le moteur de devis pour le document (sans calcul) :
règle FDA saisie (AGR306) et délai d'intervention (CIQ622, D-AGQ-13).
Sortis de ``builder.py`` (fichier-mur, C20)."""
import logging

logger = logging.getLogger(__name__)


def poser_fda_et_sav(data, devis):
    """AGR306 — la règle FDA SAISIE par la société (``regle_fda_societe``) et,
    D-AGQ-13, le délai d'intervention SAV saisi (``delai_intervention_sav_heures``) :
    posés SEULEMENT quand ils sont saisis ; ne casse jamais un rendu."""
    try:
        from apps.parametres.selectors import regle_fda_pompage_pour
        regle = regle_fda_pompage_pour(getattr(devis, "company", None))
    except Exception:  # noqa: BLE001 — repli daté du module (D-ENF22-BLE001)
        logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
        regle = {}
    if regle:
        data["regle_fda_societe"] = regle
    delai = delai_intervention_societe(devis)
    if delai:
        data["delai_intervention_sav_heures"] = delai


def poser_services_ci(data, om_et_delai, devis):
    """CIQ314 — lignes O&M et délai d'intervention saisis (``om_et_delai`` :
    ``builder.services_ci_du_devis``) ; AMOT100 (D-ACI-19=a) — le facteur
    d'émission du réseau RÉGLÉ par la société (``facteur_co2_reseau``),
    nouveaux rendus seulement. Chaque clé n'est posée que si elle est saisie."""
    om, delai = om_et_delai
    if om:
        data["om_ci_lignes"] = om
    if delai:
        data["delai_intervention_suivi_heures"] = delai
    from apps.ventes.domain.regles_calcul import calcul_corrige
    facteur = facteur_co2_societe(devis) if calcul_corrige(devis) else None
    if facteur:
        data["facteur_co2_reseau"] = facteur


def facteur_co2_societe(devis):
    """AMOT100 — ``{g_kwh, source, date}`` du profil société quand la valeur
    ET sa source sont saisies, sinon None (jamais un facteur par défaut)."""
    company = getattr(devis, "company", None)
    if company is None:
        return None
    try:
        from apps.parametres.models_company import CompanyProfile
        ligne = CompanyProfile.objects.filter(company=company).values_list(
            "facteur_co2_reseau_g_kwh", "facteur_co2_reseau_source",
            "facteur_co2_reseau_date").first()
    except Exception:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
        logger.warning("reglages_societe.facteur_co2_societe : erreur ignorée (mode dégradé)", exc_info=True)
        return None
    if not ligne or not ligne[0] or not str(ligne[1] or "").strip():
        return None
    return {"g_kwh": float(ligne[0]), "source": str(ligne[1]).strip(),
            "date": ligne[2].isoformat() if ligne[2] else None}


def delai_intervention_societe(devis):
    """``CompanyProfile.delai_intervention_suivi_heures`` de la société du
    devis (CIQ622, D-AGQ-13), ``None`` s'il n'est pas saisi — aucun défaut."""
    company = getattr(devis, "company", None)
    if company is None:
        return None
    try:
        from apps.parametres.models_company import CompanyProfile
        return (CompanyProfile.objects.filter(company=company)
                .values_list("delai_intervention_suivi_heures",
                             flat=True).first())
    except Exception:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
        logger.warning("builder.services_ci_du_devis : erreur ignorée (mode dégradé)", exc_info=True)
        return None
