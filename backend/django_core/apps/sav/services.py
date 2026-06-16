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


def generer_ticket_du(contrat, user=None, today=None):
    """Génère le ticket SAV préventif d'un contrat SI une visite est due.

    IDEMPOTENT : ne crée rien si aucune visite n'est due ou si l'échéance
    courante a déjà été matérialisée (`derniere_echeance_traitee`). Sur succès,
    avance `derniere_visite`/`derniere_echeance_traitee` à l'échéance traitée et
    renvoie le ticket créé ; sinon renvoie None. Aucune dépendance à un
    planificateur — appelé à la demande (lecture de la vue « à venir » ou
    action explicite).
    """
    # Imports locaux pour éviter une boucle d'import models ↔ services.
    from django.utils import timezone
    from .models import Ticket
    from . import activity
    from apps.ventes.utils.references import create_with_reference

    today = today or timezone.localdate()
    if not contrat.est_due(today):
        return None
    echeance = contrat.prochaine_visite
    if (contrat.derniere_echeance_traitee is not None
            and contrat.derniere_echeance_traitee >= echeance):
        return None

    company = contrat.company
    libelle = contrat.libelle or 'Contrat de maintenance'
    description = (
        f"Visite préventive planifiée — {libelle} "
        f"(échéance du {echeance.isoformat()})."
    )

    def _save(ref):
        return Ticket.objects.create(
            reference=ref, company=company, client=contrat.client,
            installation=contrat.installation,
            type=Ticket.Type.PREVENTIF, statut=Ticket.Statut.NOUVEAU,
            description=description, date_ouverture=echeance,
            created_by=user,
        )

    ticket = create_with_reference(Ticket, 'SAV', company, _save)
    if user is not None:
        activity.log_creation(ticket, user)
    contrat.derniere_visite = echeance
    contrat.derniere_echeance_traitee = echeance
    contrat.save(update_fields=[
        'derniere_visite', 'derniere_echeance_traitee', 'date_modification'])
    return ticket


def decrementer_stock_piece(piece, user=None):
    """Décrémente le stock pour une pièce consommée sur un ticket SAV (N46).

    Réutilise EXACTEMENT le patron du reste de l'OS (apps/stock & apps/ventes) :
    un MouvementStock SORTIE avec quantite_avant/quantite_apres puis mise à jour
    de Produit.quantite_stock. Aucune migration stock ajoutée. Idempotent au
    niveau de la pièce via le drapeau `stock_decremente`.

    Le stock peut passer négatif (les autres flux le permettent aussi quand non
    bloquant) — ici on enregistre simplement le mouvement réel.
    """
    from apps.stock.models import MouvementStock

    if piece.stock_decremente:
        return None
    produit = piece.produit
    produit.refresh_from_db()
    qte = int(piece.quantite)
    qte_avant = produit.quantite_stock
    qte_apres = qte_avant - qte
    mouvement = MouvementStock.objects.create(
        company=produit.company,
        produit=produit,
        type_mouvement=MouvementStock.TypeMouvement.SORTIE,
        quantite=qte,
        quantite_avant=qte_avant,
        quantite_apres=qte_apres,
        reference=f'SAV {piece.ticket.reference}',
        note=f'Pièce SAV ticket {piece.ticket.reference}',
        created_by=user,
    )
    produit.quantite_stock = qte_apres
    produit.save(update_fields=['quantite_stock'])
    piece.stock_decremente = True
    piece.save(update_fields=['stock_decremente'])
    return mouvement
