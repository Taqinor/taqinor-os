"""
XFSM23 — services de géolocalisation temps réel + géofencing technicien.

Trois responsabilités, toutes company-scopées et posées côté serveur :

  * enregistrer/consulter le consentement GPS (déjà obtenu, jamais reposé par
    le client mobile — voir ``models_gps_tracking`` pour la décision fondateur) ;
  * persister une position live et calculer sa distance au chantier de
    l'intervention active liée, en levant une ``GeofenceAlert`` si elle sort du
    rayon attendu ;
  * purger les positions plus vieilles que ``POSITION_RETENTION_JOURS``
    (rétention courte — donnée personnelle sensible, loi 09-08).
"""
from datetime import timedelta

from django.utils import timezone

from .field_services import haversine_km
from .models_gps_tracking import (
    DEFAULT_GEOFENCE_RADIUS_KM,
    POSITION_RETENTION_JOURS,
    GeofenceAlert,
    GpsConsentRecord,
    PositionTechnicien,
)


def record_consent(company, technicien, consent_ref=None, recorded_by=None):
    """Enregistre (ou réactive) le consentement GPS d'un employé — établi UNE
    FOIS, jamais reposé par le client mobile. Idempotent : si un consentement
    ACTIF existe déjà, le renvoie sans doublon (une seule ligne active par
    company+technicien, cf. la contrainte unique conditionnelle)."""
    existing = GpsConsentRecord.objects.filter(
        company=company, technicien=technicien, revoked_at__isnull=True
    ).first()
    if existing:
        return existing
    return GpsConsentRecord.objects.create(
        company=company, technicien=technicien, consent_ref=consent_ref,
        recorded_by=recorded_by)


def has_active_consent(company, technicien):
    """Vrai si le technicien a un consentement GPS actif (non révoqué)."""
    return GpsConsentRecord.objects.filter(
        company=company, technicien=technicien, revoked_at__isnull=True
    ).exists()


def revoke_consent(company, technicien, reason=None):
    """Révoque le consentement actif (action responsable/admin uniquement —
    JAMAIS appelée par le client mobile du technicien). Renvoie le nombre de
    lignes révoquées (0 ou 1)."""
    return GpsConsentRecord.objects.filter(
        company=company, technicien=technicien, revoked_at__isnull=True
    ).update(revoked_at=timezone.now(), revoked_reason=reason)


def _position_precedente(position):
    """Position live précédente du même technicien sur la même intervention,
    parmi celles dont la distance au chantier a pu être calculée.

    Sert à distinguer un FRANCHISSEMENT (NTMOB9) d'un simple ping : sans
    position précédente évaluée, on ne sait pas si le technicien vient
    d'entrer — on ne journalise donc aucune entrée."""
    return (PositionTechnicien.objects
            .filter(company_id=position.company_id,
                    technicien_id=position.technicien_id,
                    intervention_id=position.intervention_id,
                    distance_site_km__isnull=False)
            .exclude(pk=position.pk)
            .order_by('-captured_at', '-id')
            .first())


def enregistrer_position(
        company, technicien, lat, lng, intervention=None,
        accuracy_m=None, captured_at=None,
        radius_km=DEFAULT_GEOFENCE_RADIUS_KM):
    """Persiste une position live et, si une intervention est liée avec un GPS
    de chantier connu, calcule la distance et journalise le franchissement du
    rayon dans ``GeofenceAlert``. Ne bloque JAMAIS l'enregistrement de la
    position elle-même — le géofencing est un signal, pas une garde.

    Deux journaux, un seul modèle :

      * ``sortie`` — la position est hors du rayon (XFSM23, comportement
        d'origine : une ligne par dépassement, sans déduplication) ;
      * ``entree`` — NTMOB9 : la position est DANS le rayon alors que la
        précédente était dehors. Le point de présence est donc posé tout seul
        quand le technicien arrive sur le chantier, sans action de sa part.
        Sans position précédente évaluée, aucune entrée n'est journalisée :
        un ping isolé à l'intérieur n'est pas un franchissement.

    Renvoie ``(position, franchissement_ou_None)``."""
    position = PositionTechnicien.objects.create(
        company=company, technicien=technicien, intervention=intervention,
        lat=lat, lng=lng, accuracy_m=accuracy_m,
        captured_at=captured_at or timezone.now())

    if intervention is None:
        return position, None

    site = getattr(intervention, 'installation', None)
    site_lat = getattr(site, 'gps_lat', None)
    site_lng = getattr(site, 'gps_lng', None)
    distance = haversine_km(lat, lng, site_lat, site_lng)
    if distance is None:
        return position, None

    precedente = _position_precedente(position)

    hors_perimetre = distance > float(radius_km)
    position.distance_site_km = distance
    position.hors_perimetre = hors_perimetre
    position.save(update_fields=['distance_site_km', 'hors_perimetre'])

    type_franchissement = None
    if hors_perimetre:
        type_franchissement = GeofenceAlert.TypeFranchissement.SORTIE
    elif precedente is not None and precedente.hors_perimetre:
        type_franchissement = GeofenceAlert.TypeFranchissement.ENTREE

    alert = None
    if type_franchissement is not None:
        alert = GeofenceAlert.objects.create(
            company=company, intervention=intervention, technicien=technicien,
            position=position, distance_site_km=distance,
            rayon_attendu_km=radius_km,
            type_franchissement=type_franchissement)
    return position, alert


def franchissements_geofence(company, intervention=None, chantier=None,
                             type_franchissement=None):
    """NTMOB9 — historique de présence géofencée, en lecture seule.

    Journal des entrées/sorties du rayon, scopé société, filtrable par
    intervention, par chantier (``Intervention.installation``) et par type.
    Alimente l'écran « Historique de présence » du responsable : les entrées
    sont les arrivées sur site, les sorties les départs/écarts."""
    qs = GeofenceAlert.objects.filter(company=company)
    if intervention is not None:
        qs = qs.filter(intervention=intervention)
    if chantier is not None:
        qs = qs.filter(intervention__installation=chantier)
    if type_franchissement:
        qs = qs.filter(type_franchissement=type_franchissement)
    return qs.select_related(
        'intervention', 'technicien', 'position').order_by('-created_at')


def positions_live(company, technicien=None, intervention=None):
    """Sélecteur-lecture des positions récentes, scopé à la société. Filtre
    optionnel par technicien et/ou intervention (vue superviseur temps réel)."""
    qs = PositionTechnicien.objects.filter(company=company)
    if technicien is not None:
        qs = qs.filter(technicien=technicien)
    if intervention is not None:
        qs = qs.filter(intervention=intervention)
    return qs.order_by('-captured_at')


def dernieres_positions_par_technicien(company, techniciens=None):
    """Dernière position connue par technicien (vue carte superviseur) — une
    ligne par technicien, la plus récente. ``techniciens`` restreint
    optionnellement l'ensemble (ex. l'équipe du responsable)."""
    qs = PositionTechnicien.objects.filter(company=company)
    if techniciens is not None:
        qs = qs.filter(technicien__in=techniciens)
    seen = set()
    resultat = []
    for pos in qs.order_by('technicien_id', '-captured_at'):
        if pos.technicien_id in seen:
            continue
        seen.add(pos.technicien_id)
        resultat.append(pos)
    return resultat


def purge_positions_expirees(
        company=None, retention_jours=POSITION_RETENTION_JOURS):
    """Supprime les positions plus vieilles que la fenêtre de rétention
    (donnée personnelle sensible, loi 09-08 — pas de conservation longue).
    Renvoie le nombre de lignes supprimées. Portée à une société si fournie,
    sinon toutes (usage tâche planifiée/commande manuelle)."""
    seuil = timezone.now() - timedelta(days=retention_jours)
    qs = PositionTechnicien.objects.filter(captured_at__lt=seuil)
    if company is not None:
        qs = qs.filter(company=company)
    nb, _ = qs.delete()
    return nb
