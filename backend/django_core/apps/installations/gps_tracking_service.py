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

Revue chantier 26/10/2026 : accusé de réception de la notice par le
technicien (``accepter_consentement``), statut de consentement par technicien
sans N+1 (``statuts_consentement``), rayon propre au chantier, une seule
sortie ouverte par intervention (SUR SITE uniquement) notifiée au(x)
responsable(s), présence calculée (``presence_intervention``) et carte live
en UNE requête.
"""
import logging
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
from .models_intervention import Intervention

logger = logging.getLogger(__name__)

#: Lien de la notification « sortie de périmètre » (écran responsable).
LIEN_SUIVI_GPS = '/planification/suivi-gps'


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


def has_acknowledged_consent(company, technicien):
    """Vrai si le consentement est actif ET que le technicien a accusé
    réception de la notice dans l'application — la seule condition qui
    ouvre le ping (loi 09-08 art. 5 : information préalable)."""
    return GpsConsentRecord.objects.filter(
        company=company, technicien=technicien, revoked_at__isnull=True,
        accepte_le__isnull=False,
    ).exists()


def consentement_de(company, technicien):
    """Le consentement « courant » d'un technicien : l'actif s'il existe,
    sinon le dernier révoqué, sinon ``None``."""
    qs = GpsConsentRecord.objects.filter(company=company, technicien=technicien)
    actif = qs.filter(revoked_at__isnull=True).first()
    if actif is not None:
        return actif
    return qs.order_by('-revoked_at', '-id').first()


def statut_consentement(record):
    """``absent`` | ``a_accepter`` | ``actif`` | ``revoque``."""
    return 'absent' if record is None else record.statut


def statuts_consentement(company):
    """{technicien_id: statut} pour TOUTE la société, en UNE requête (le
    nombre de consentements = le nombre d'employés suivis, petit). Un
    technicien absent du dictionnaire est ``absent``. L'actif l'emporte sur
    un ancien consentement révoqué."""
    statuts = {}
    lignes = (GpsConsentRecord.objects.filter(company=company)
              .values_list('technicien_id', 'revoked_at', 'accepte_le'))
    for technicien_id, revoked_at, accepte_le in lignes:
        if revoked_at is None:
            statuts[technicien_id] = 'actif' if accepte_le else 'a_accepter'
        else:
            statuts.setdefault(technicien_id, 'revoque')
    return statuts


def accepter_consentement(company, technicien, ip=None):
    """Accusé de réception de la notice par le technicien LUI-MÊME. Renvoie
    le consentement mis à jour, ou ``None`` s'il n'existe aucun consentement
    actif pour lui (le responsable doit d'abord l'établir). Idempotent : la
    première date d'accord est conservée."""
    record = GpsConsentRecord.objects.filter(
        company=company, technicien=technicien, revoked_at__isnull=True).first()
    if record is None:
        return None
    if record.accepte_le is None:
        import ipaddress
        try:
            ip = str(ipaddress.ip_address((ip or '').strip()))
        except ValueError:  # adresse absente/illisible : jamais un 500 inet
            ip = None
        record.accepte_le = timezone.now()
        record.accepte_depuis_ip = ip
        record.save(update_fields=['accepte_le', 'accepte_depuis_ip'])
    return record


def rayon_geofence_km(intervention):
    """Rayon (km) du chantier de l'intervention : ``geofence_rayon_m`` s'il
    est renseigné, sinon le défaut 500 m."""
    site = getattr(intervention, 'installation', None)
    rayon_m = getattr(site, 'geofence_rayon_m', None)
    if rayon_m:
        return round(rayon_m / 1000.0, 3)
    return DEFAULT_GEOFENCE_RADIUS_KM


def membre_de_l_intervention(intervention, user):
    """Le technicien principal ou un membre de l'équipe (canonique ou ad hoc)."""
    from .selectors import membres_intervention
    return user.id in membres_intervention(intervention)


def _sortie_deja_ouverte(intervention):
    """Une sortie est « ouverte » tant qu'aucune entrée ne l'a suivie : la
    dernière ligne du journal de l'intervention est une sortie."""
    derniere = (GeofenceAlert.objects.filter(intervention=intervention)
                .order_by('-created_at', '-id')
                .values_list('type_franchissement', flat=True).first())
    return derniere == GeofenceAlert.TypeFranchissement.SORTIE


def _responsables_a_notifier(intervention):
    """Responsable du chantier + créateur de l'intervention, sans le
    technicien suivi lui-même, sans doublon."""
    destinataires = []
    vus = {intervention.technicien_id}
    site = getattr(intervention, 'installation', None)
    for user in (getattr(site, 'technicien_responsable', None),
                 getattr(intervention, 'created_by', None)):
        if user is not None and user.id not in vus and user.is_active:
            vus.add(user.id)
            destinataires.append(user)
    return destinataires


def _notifier_sortie_perimetre(alert):
    """Notifie (best-effort, après commit, ne lève jamais) le(s)
    responsable(s) d'une NOUVELLE sortie de périmètre pendant que
    l'intervention est sur site.

    Clé d'événement : ``INTERVENTION_REPLANIFIEE`` est réemployée faute de
    clé dédiée — ajouter une clé à ``EventType`` exige une migration de
    l'app notifications, hors du périmètre de cette lane (point ouvert)."""
    try:
        from django.db import transaction
        from apps.notifications.services import notify_many
        from apps.notifications.types_evenements import EventType
    except Exception:  # pragma: no cover - défensif
        return
    interv = alert.intervention
    destinataires = _responsables_a_notifier(interv)
    if not destinataires:
        return
    site = getattr(interv, 'installation', None)
    ref = getattr(site, 'reference', None) or f'intervention #{interv.id}'
    qui = getattr(alert.technicien, 'username', '') or 'Le technicien'
    titre = f"Sortie du périmètre — {ref}"
    corps = (f"{qui} est à {alert.distance_site_km} km du chantier "
             f"(rayon {alert.rayon_attendu_km} km) alors que l'intervention "
             "est sur site.")
    company = alert.company

    def _envoyer():
        try:
            notify_many(destinataires, EventType.INTERVENTION_REPLANIFIEE,
                        titre, body=corps, link=LIEN_SUIVI_GPS,
                        company=company)
        except Exception:  # pragma: no cover - défensif
            logger.warning('notifier sortie périmètre : échec ignoré',
                           exc_info=True)

    try:
        transaction.on_commit(_envoyer)
    except Exception:  # pragma: no cover - défensif
        logger.warning('notifier sortie périmètre : échec ignoré',
                       exc_info=True)


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
        accuracy_m=None, captured_at=None, radius_km=None):
    """Persiste une position live et, si une intervention est liée avec un GPS
    de chantier connu, calcule la distance et journalise le franchissement du
    rayon dans ``GeofenceAlert``. Ne bloque JAMAIS l'enregistrement de la
    position elle-même — le géofencing est un signal, pas une garde.

    ``radius_km`` : ``None`` (défaut) = rayon du chantier
    (``rayon_geofence_km``), 500 m si le chantier n'en a pas.

    Deux journaux, un seul modèle :

      * ``sortie`` — la position est hors du rayon ALORS QUE l'intervention
        est SUR SITE (en route, être loin du chantier est normal). Revue
        chantier 26/10/2026 : une seule sortie OUVERTE par intervention —
        aucune nouvelle ligne tant qu'aucune entrée ne l'a suivie — et
        chaque nouvelle sortie notifie le(s) responsable(s) ;
      * ``entree`` — NTMOB9 : la position est DANS le rayon alors que la
        précédente était dehors. Le point de présence est donc posé tout seul
        quand le technicien arrive sur le chantier, sans action de sa part.
        Sans position précédente évaluée, aucune entrée n'est journalisée :
        un ping isolé à l'intérieur n'est pas un franchissement.

    Renvoie ``(position, franchissement_ou_None)``."""
    if radius_km is None:
        radius_km = (rayon_geofence_km(intervention)
                     if intervention is not None else DEFAULT_GEOFENCE_RADIUS_KM)
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
        if (intervention.statut == Intervention.Statut.SUR_SITE
                and not _sortie_deja_ouverte(intervention)):
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
        if type_franchissement == GeofenceAlert.TypeFranchissement.SORTIE:
            _notifier_sortie_perimetre(alert)
    return position, alert


#: Taille maximale d'un lot de rattrapage hors-ligne.
LOT_MAX_POSITIONS = 20


def enregistrer_lot_positions(company, technicien, intervention, points):
    """Rattrapage hors-ligne : enregistre jusqu'à ``LOT_MAX_POSITIONS``
    positions déjà validées (``[{lat, lng, accuracy_m, captured_at}]``) dans
    l'ordre chronologique, en IGNORANT les doublons (même technicien + même
    intervention + même ``captured_at`` — un client qui renvoie un lot après
    une coupure ne double rien). Une seule requête pour repérer les doublons.

    Renvoie ``(positions_creees, alertes, nb_doublons)``."""
    instants = [p['captured_at'] for p in points]
    deja = set(PositionTechnicien.objects.filter(
        company=company, technicien=technicien, intervention=intervention,
        captured_at__in=instants).values_list('captured_at', flat=True))
    creees, alertes, doublons = [], [], 0
    vus = set()
    for p in sorted(points, key=lambda x: x['captured_at']):
        if p['captured_at'] in deja or p['captured_at'] in vus:
            doublons += 1
            continue
        vus.add(p['captured_at'])
        position, alert = enregistrer_position(
            company, technicien, p['lat'], p['lng'],
            intervention=intervention, accuracy_m=p.get('accuracy_m'),
            captured_at=p['captured_at'])
        creees.append(position)
        if alert is not None:
            alertes.append(alert)
    return creees, alertes, doublons


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


def dernieres_positions_par_technicien(company, techniciens=None, depuis=None):
    """Dernière position connue par technicien (vue carte superviseur) — une
    ligne par technicien, la plus récente. ``techniciens`` restreint
    optionnellement l'ensemble (ex. l'équipe du responsable) ; ``depuis``
    écarte les positions plus anciennes (carte « live » : une position de la
    veille n'est pas une position actuelle).

    Revue chantier 26/10/2026 : UNE requête (``DISTINCT ON`` Postgres) au
    lieu de charger toutes les positions de la société puis de les trier en
    Python."""
    qs = PositionTechnicien.objects.filter(company=company)
    if techniciens is not None:
        qs = qs.filter(technicien__in=techniciens)
    if depuis is not None:
        qs = qs.filter(captured_at__gte=depuis)
    return list(
        qs.select_related('technicien', 'intervention')
        .order_by('technicien_id', '-captured_at', '-id')
        .distinct('technicien_id'))


def trajet_du_jour(company, technicien_id, jour, limite=2000):
    """Positions d'un technicien pour un jour (fuseau de la société =
    Africa/Casablanca, ``USE_TZ``), dans l'ordre chronologique — le tracé de
    la journée. Bornée à ``limite`` lignes (≈ 1 ping/min sur 24 h = 1 440)."""
    return list(
        PositionTechnicien.objects.filter(
            company=company, technicien_id=technicien_id,
            captured_at__date=jour)
        .select_related('technicien')
        .order_by('captured_at', 'id')[:limite])


def presence_intervention(intervention):
    """Temps passé sur site d'une intervention, calculé côté serveur.

    * ``premiere_entree`` : première position relevée DANS le rayon ; à
      défaut (positions purgées après 30 j), la première alerte d'entrée ;
      à défaut, le pointage manuel ``arrivee_site_le`` (F6).
    * ``derniere_sortie`` : dernière position relevée dans le rayon (dernier
      instant vu sur site) ; à défaut, la dernière alerte de sortie
      postérieure au début.
    * ``duree_sur_site_min`` : de l'un à l'autre (minutes entières), ``None``
      sans les deux bornes.
    * ``source_debut`` : ``positions`` | ``alertes`` | ``pointage`` | ``None``
      — l'écran dit d'où vient le chiffre, jamais un chiffre sans source.

    Deux requêtes (positions de l'intervention, alertes de l'intervention),
    calcul en Python : ≈ 1 ping/min, quelques centaines de lignes au plus."""
    positions = list(
        PositionTechnicien.objects.filter(intervention=intervention)
        .order_by('captured_at', 'id')
        .values('lat', 'lng', 'captured_at', 'hors_perimetre',
                'distance_site_km'))
    dedans = [p for p in positions
              if p['distance_site_km'] is not None and not p['hors_perimetre']]
    debut = fin = source = None
    if dedans:
        debut, fin, source = dedans[0]['captured_at'], dedans[-1]['captured_at'], 'positions'
    else:
        alertes = list(
            GeofenceAlert.objects.filter(intervention=intervention)
            .order_by('created_at', 'id')
            .values_list('type_franchissement', 'created_at'))
        entrees = [c for t, c in alertes
                   if t == GeofenceAlert.TypeFranchissement.ENTREE]
        if entrees:
            debut, source = entrees[0], 'alertes'
        elif intervention.arrivee_site_le:
            debut, source = intervention.arrivee_site_le, 'pointage'
        if debut is not None:
            sorties = [c for t, c in alertes
                       if t == GeofenceAlert.TypeFranchissement.SORTIE
                       and c >= debut]
            fin = sorties[-1] if sorties else None
    duree = None
    if debut is not None and fin is not None and fin >= debut:
        duree = int((fin - debut).total_seconds() // 60)
    derniere = positions[-1] if positions else None
    return {
        'intervention': intervention.id,
        'premiere_entree': debut,
        'derniere_sortie': fin,
        'duree_sur_site_min': duree,
        'nb_positions': len(positions),
        'source_debut': source,
        'derniere_position': ({
            'lat': derniere['lat'], 'lng': derniere['lng'],
            'captured_at': derniere['captured_at'],
        } if derniere else None),
    }


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
