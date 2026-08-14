"""NTWMS35 — Créneaux de rendez-vous ENTRANT proposés au fournisseur.

Étend NTWMS7 (quais + rendez-vous transporteur) et NTWMS8 (check-in kiosque) :
le portail fournisseur existant (``PortailFournisseurToken``, XPUR22) gagne la
prise de rendez-vous. Le fournisseur consulte les créneaux LIBRES d'un quai de
RÉCEPTION sur une fenêtre de dates et réserve lui-même — le magasinier n'a
plus à orchestrer les arrivées à la main.

GARDES (toutes côté serveur, jamais côté client) :
  * seuls les quais ACTIFS de type RECEPTION/MIXTE de la société du jeton sont
    proposés — jamais un quai d'expédition, jamais celui d'une autre société ;
  * un créneau déjà occupé n'est jamais proposé NI réservable : le
    non-chevauchement est déjà appliqué dans ``RendezVousTransporteur.save()``
    (NTWMS7), on s'appuie dessus plutôt que de le ré-implémenter ;
  * le BCF rattaché doit appartenir AU fournisseur porteur du jeton ;
  * la réservation ne crée jamais un quai, un transporteur ou un produit.
"""
import datetime
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# Journée d'ouverture des quais et granularité des créneaux proposés.
HEURE_OUVERTURE = 8
HEURE_FERMETURE = 18
DUREE_CRENEAU_MINUTES = 60
# Fenêtre maximale consultable d'un coup (garde anti-abus sur un endpoint
# PUBLIC : sans plafond, un `periode=3650` ferait balayer dix ans de créneaux).
FENETRE_MAX_JOURS = 30


def _parse_date(valeur):
    if not valeur:
        return None
    if isinstance(valeur, datetime.date):
        return valeur
    try:
        return datetime.date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        raise ValueError('Date invalide (format attendu AAAA-MM-JJ).')


def quais_reception_ouverts(company):
    """Quais ACTIFS pouvant recevoir de la marchandise (RECEPTION ou MIXTE)."""
    from .models_wms import Quai
    return (Quai.objects
            .filter(company=company, actif=True,
                    type_quai__in=[Quai.TypeQuai.RECEPTION,
                                   Quai.TypeQuai.MIXTE])
            .order_by('nom'))


def creneaux_disponibles(company, *, quai_id=None, date_debut=None,
                         periode_jours=7):
    """Créneaux LIBRES des quais de réception, jour par jour.

    ``date_debut`` par défaut = aujourd'hui (fuseau du projet).
    ``periode_jours`` est plafonné à ``FENETRE_MAX_JOURS``. Un créneau déjà
    couvert par un rendez-vous OCCUPANT (tout sauf ANNULÉ) est omis.
    """
    from .models_wms import RendezVousTransporteur

    debut = _parse_date(date_debut) or timezone.localdate()
    try:
        jours = int(periode_jours or 7)
    except (TypeError, ValueError):
        jours = 7
    jours = max(1, min(jours, FENETRE_MAX_JOURS))

    quais = list(quais_reception_ouverts(company))
    if quai_id:
        quais = [q for q in quais if str(q.id) == str(quai_id)]
    if not quais:
        return []

    fin = debut + datetime.timedelta(days=jours)
    occupes = list(RendezVousTransporteur.objects.filter(
        company=company, quai_id__in=[q.id for q in quais],
        statut__in=RendezVousTransporteur.STATUTS_OCCUPANTS,
        date_heure_debut__date__gte=debut,
        date_heure_debut__date__lt=fin,
    ).values_list('quai_id', 'date_heure_debut', 'date_heure_fin'))

    resultat = []
    for quai in quais:
        pris = [(d, f) for (qid, d, f) in occupes if qid == quai.id]
        for offset in range(jours):
            jour = debut + datetime.timedelta(days=offset)
            heure = HEURE_OUVERTURE
            while heure < HEURE_FERMETURE:
                naif_debut = datetime.datetime.combine(
                    jour, datetime.time(hour=heure))
                creneau_debut = timezone.make_aware(naif_debut)
                creneau_fin = creneau_debut + datetime.timedelta(
                    minutes=DUREE_CRENEAU_MINUTES)
                libre = not any(d < creneau_fin and f > creneau_debut
                                for (d, f) in pris)
                if libre:
                    resultat.append({
                        'quai': quai.id,
                        'quai_nom': quai.nom,
                        'date': jour.isoformat(),
                        'debut': creneau_debut.isoformat(),
                        'fin': creneau_fin.isoformat(),
                    })
                heure += max(1, DUREE_CRENEAU_MINUTES // 60)
    return resultat


def reserver_creneau_fournisseur(token_obj, *, quai_id, debut,
                                 bon_commande_id=None, chauffeur_nom='',
                                 immatriculation=''):
    """Le fournisseur porteur du jeton réserve LUI-MÊME un créneau entrant.

    Lève ``ValueError`` (message français, jamais une trace) si : le quai
    n'est pas un quai de réception actif de la société, l'horodatage est
    illisible ou passé, le BCF fourni n'appartient pas à ce fournisseur, ou le
    créneau est déjà pris (garde de non-chevauchement NTWMS7).
    """
    from django.db import transaction

    from .models import BonCommandeFournisseur
    from .models_wms import RendezVousTransporteur

    company = token_obj.company
    fournisseur = token_obj.fournisseur

    quai = next((q for q in quais_reception_ouverts(company)
                 if str(q.id) == str(quai_id)), None)
    if quai is None:
        raise ValueError('Ce quai de réception n\'est pas disponible.')

    if isinstance(debut, datetime.datetime):
        creneau_debut = debut
    else:
        try:
            creneau_debut = datetime.datetime.fromisoformat(str(debut))
        except (TypeError, ValueError):
            raise ValueError('Créneau invalide (horodatage ISO attendu).')
    if timezone.is_naive(creneau_debut):
        creneau_debut = timezone.make_aware(creneau_debut)
    if creneau_debut < timezone.now():
        raise ValueError('Ce créneau est déjà passé.')
    creneau_fin = creneau_debut + datetime.timedelta(
        minutes=DUREE_CRENEAU_MINUTES)

    bcf = None
    if bon_commande_id:
        bcf = (BonCommandeFournisseur.objects
               .filter(id=bon_commande_id, company=company,
                       fournisseur=fournisseur).first())
        if bcf is None:
            # Isolation stricte : on ne dit JAMAIS si le BCF existe ailleurs.
            raise ValueError('Bon de commande introuvable.')

    note = 'NTWMS35 — créneau réservé par le fournisseur via son portail.'
    if bcf is not None:
        note += f' BCF {bcf.reference}.'
    try:
        with transaction.atomic():
            rdv = RendezVousTransporteur(
                company=company, quai=quai,
                date_heure_debut=creneau_debut, date_heure_fin=creneau_fin,
                statut=RendezVousTransporteur.Statut.PLANIFIE,
                chauffeur_nom=(chauffeur_nom or '').strip()[:120],
                immatriculation=(immatriculation or '').strip()[:30],
                note=note)
            rdv.save()
    except ValueError:
        # `save()` refuse le chevauchement (NTWMS7) — message métier propre.
        raise ValueError('Ce créneau vient d\'être réservé, choisissez-en un '
                         'autre.')
    logger.info('NTWMS35 creneau reserve quai=%s fournisseur=%s',
                quai.id, fournisseur.id)
    return rdv
