"""N105 — Validateur de conformité DGI d'une facture (à la demande).

``validate_dgi_conformity(facture, profile=None) -> list[str]`` renvoie la liste
des problèmes de conformité (messages français) ; une liste VIDE signifie que la
facture porte tous les champs obligatoires DGI. Pur (objets → list[str]),
n'écrit rien, ne change aucun statut.

Champs vérifiés (cadre Article 145 CGI marocain + cohérence comptable) :
  * Identité + identifiants légaux du vendeur (raison sociale, ICE, IF, RC).
  * Identité du client, + ICE OBLIGATOIRE si le client est professionnel (B2B).
  * Numéro de facture (séquentiel) et date d'émission présents.
  * Au moins une ligne, chacune avec désignation, quantité, prix unitaire et
    taux de TVA par ligne renseignés.
  * Cohérence des totaux : HT + TVA = TTC (réconciliés au centime).
"""
from decimal import Decimal, ROUND_HALF_UP


def _q2(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _est_pro(client):
    """B2B : client professionnel (entreprise ou porteur d'un ICE/IF/RC)."""
    if client is None:
        return False
    type_client = (getattr(client, 'type_client', '') or '').lower()
    if type_client == 'entreprise':
        return True
    for attr in ('ice', 'if_fiscal', 'rc'):
        if (getattr(client, attr, '') or '').strip():
            return True
    return False


def _resolve_profile(facture, profile):
    if profile is not None:
        return profile
    from apps.parametres.models import CompanyProfile
    return CompanyProfile.get(company=facture.company)


def validate_dgi_conformity(facture, profile=None):
    """Renvoie la liste des problèmes de conformité DGI (vide = conforme)."""
    profile = _resolve_profile(facture, profile)
    problemes = []

    # ── Identité + identifiants légaux du vendeur ──
    if not (getattr(profile, 'nom', '') or '').strip():
        problemes.append("Identité du vendeur (raison sociale) manquante.")
    if not (getattr(profile, 'ice', '') or '').strip():
        problemes.append("ICE du vendeur manquant.")
    if not (getattr(profile, 'identifiant_fiscal', '') or '').strip():
        problemes.append("Identifiant fiscal (IF) du vendeur manquant.")
    if not (getattr(profile, 'rc', '') or '').strip():
        problemes.append("Registre de commerce (RC) du vendeur manquant.")

    # ── Identité du client (+ ICE obligatoire en B2B) ──
    client = facture.client
    if client is None or not (getattr(client, 'nom', '') or '').strip():
        problemes.append("Identité du client manquante.")
    elif _est_pro(client) and not (getattr(client, 'ice', '') or '').strip():
        problemes.append("ICE du client manquant (client professionnel/B2B).")

    # ── Numéro séquentiel + date d'émission ──
    if not (getattr(facture, 'reference', '') or '').strip():
        problemes.append("Numéro de facture (séquentiel) manquant.")
    if getattr(facture, 'date_emission', None) is None:
        problemes.append("Date d'émission manquante.")

    # ── Lignes : au moins une, chacune complète avec TVA par ligne ──
    lignes = list(facture.lignes.all())
    if not lignes:
        problemes.append("Aucune ligne de facturation.")
    else:
        for idx, ligne in enumerate(lignes, start=1):
            if not (getattr(ligne, 'designation', '') or '').strip():
                problemes.append(
                    f"Ligne {idx} : désignation manquante.")
            if getattr(ligne, 'quantite', None) is None:
                problemes.append(f"Ligne {idx} : quantité manquante.")
            if getattr(ligne, 'prix_unitaire', None) is None:
                problemes.append(
                    f"Ligne {idx} : prix unitaire HT manquant.")
            if getattr(ligne, 'taux_tva_effectif', None) is None:
                problemes.append(f"Ligne {idx} : taux de TVA manquant.")

    # ── Cohérence des totaux HT + TVA = TTC (au centime) ──
    try:
        ht = _q2(facture.total_ht)
        tva = _q2(facture.total_tva)
        ttc = _q2(facture.total_ttc)
        if ht + tva != ttc:
            problemes.append(
                "Incohérence des totaux : HT + TVA ≠ TTC "
                f"({ht} + {tva} ≠ {ttc}).")
    except Exception:
        problemes.append("Totaux HT/TVA/TTC illisibles ou incohérents.")

    return problemes
