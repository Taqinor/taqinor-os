"""
Helpers SAV — arithmétique de garantie (sans dépendance externe).

`add_months` ajoute un nombre de mois à une date en restant dans la stdlib
(calendar), avec recadrage du jour pour les fins de mois (ex. 31 jan + 1 mois
→ 28/29 fév). Sert au calcul des dates de fin de garantie des équipements.
"""
import calendar
from datetime import date


def add_months(d: date, months: int) -> date:
    """Retourne `d` décalée de `months` mois (jour recadré sur la fin de mois)."""
    if d is None or months is None:
        return None
    total = d.month - 1 + int(months)
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# ── Point d'entrée cross-app : ajout au parc installé (sav.Equipement) ───────
# Les autres apps (installations) poussent un équipement dans le parc à travers
# ce service plutôt qu'en important `apps.sav.models` directement (voir CLAUDE.md,
# règle de modularité). Comportement identique à la création inline d'origine.

def create_equipement_from_serial(*, company, produit, installation,
                                  numero_serie, date_pose, created_by):
    """Crée un Equipement au parc, recalcule ses garanties et le sauve. Renvoie
    l'équipement créé. Écriture identique au bloc inline d'origine."""
    from .models import Equipement
    equip = Equipement.objects.create(
        company=company, produit=produit, installation=installation,
        numero_serie=numero_serie, date_pose=date_pose, created_by=created_by)
    equip.recompute_garanties()
    equip.save(update_fields=[
        'date_fin_garantie', 'date_fin_garantie_production'])
    return equip


def create_corrective_ticket(*, company, client, installation, description,
                             created_by):
    """F16 — crée un ticket SAV correctif (référence sans collision via
    l'utilitaire commun). Renvoie le ticket créé. Identique au bloc inline."""
    from apps.ventes.utils.references import create_with_reference
    from .models import Ticket

    def _create(ref):
        return Ticket.objects.create(
            company=company, reference=ref, client=client,
            installation=installation, type=Ticket.Type.CORRECTIF,
            description=description, created_by=created_by)
    return create_with_reference(Ticket, 'SAV', company, _create)
