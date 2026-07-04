"""
Helpers SAV — arithmétique de garantie (sans dépendance externe).

`add_months` ajoute un nombre de mois à une date en restant dans la stdlib
(calendar), avec recadrage du jour pour les fins de mois (ex. 31 jan + 1 mois
→ 28/29 fév). Sert au calcul des dates de fin de garantie des équipements.
"""
import calendar
from datetime import date

from django.utils import timezone


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


def ensure_equipement_for_bom_line(*, company, produit, installation,
                                   date_pose, created_by):
    """FG70 — garantit qu'AU MOINS UN Equipement (sans n° de série) existe au
    parc pour la paire (chantier, produit). IDEMPOTENT : si un équipement de ce
    produit existe déjà pour ce chantier (avec ou sans série), ne crée rien et
    renvoie ``(equipement_existant, False)``. Sinon crée un équipement
    serial-less daté de ``date_pose`` (garanties recalculées) et renvoie
    ``(equipement, True)``.

    Sert au balayage de la nomenclature gelée (`Installation.bom`) à la
    réception : la couverture de garantie ne dépend plus d'un technicien qui
    pense à saisir chaque n° de série. Le n° de série reste optionnel et peut
    être renseigné plus tard sur l'équipement créé."""
    from .models import Equipement
    existing = (Equipement.objects
                .filter(company=company, installation=installation,
                        produit=produit)
                .first())
    if existing is not None:
        return existing, False
    equip = create_equipement_from_serial(
        company=company, produit=produit, installation=installation,
        numero_serie=None, date_pose=date_pose, created_by=created_by)
    return equip, True


def sweep_bom_to_parc(*, installation, company, date_pose, created_by,
                      resolve_produit):
    """FG70 — balaye la nomenclature gelée du chantier (`installation.bom`) et
    garantit un Equipement de parc (sans n° de série) par ligne de BoM ayant un
    produit catalogue. IDEMPOTENT et ADDITIF : ne duplique jamais un équipement
    déjà présent pour une paire (chantier, produit) — un re-passage à
    « Réceptionné » ne crée rien de neuf.

    ``resolve_produit(produit_id)`` est fourni par l'appelant (installations)
    pour résoudre le produit catalogue scopé société sans coupler les apps. Les
    lignes sans ``produit_id``, ou dont le produit est introuvable, sont
    ignorées (on ne crée pas d'équipement pour une ligne libre).

    Renvoie un dict-résumé pour la note de remise / la section PDF :
      {'crees': int, 'existants': int, 'lignes': [
          {'designation': str, 'cree': bool}, ...]}.
    """
    bom = getattr(installation, 'bom', None) or []
    crees = 0
    existants = 0
    lignes = []
    seen = set()
    for ligne in bom:
        produit_id = (ligne or {}).get('produit_id')
        if not produit_id:
            continue
        # Plusieurs lignes peuvent référencer le même produit : on ne crée
        # qu'un seul équipement par produit (idempotence intra-balayage).
        if produit_id in seen:
            continue
        produit = resolve_produit(produit_id)
        if produit is None:
            continue
        seen.add(produit_id)
        _equip, created = ensure_equipement_for_bom_line(
            company=company, produit=produit, installation=installation,
            date_pose=date_pose, created_by=created_by)
        designation = (ligne.get('designation')
                       or getattr(produit, 'nom', '') or '')
        lignes.append({'designation': designation, 'cree': created})
        if created:
            crees += 1
        else:
            existants += 1
    return {'crees': crees, 'existants': existants, 'lignes': lignes}


def _technicien_indisponible(company, user, jour):
    """XSAV9 — Vrai si `user` a un dossier RH avec une absence VALIDÉE ce
    jour-là (lu via les selectors rh — jamais un import direct des modèles
    rh). Sans dossier RH rattaché à l'utilisateur, ou si le module rh est
    indisponible/erreur, on considère l'utilisateur DISPONIBLE (repli sûr —
    l'affectation auto ne doit jamais bloquer faute de données RH)."""
    try:
        from apps.rh.selectors import employe_absent_le
        from apps.rh.models import DossierEmploye
        dossier = DossierEmploye.objects.filter(
            company=company, user=user).first()
        if dossier is None:
            return False
        return employe_absent_le(company, dossier.id, jour)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return False


def assign_technicien_auto(*, company, jour=None):
    """XSAV9 — Choisit le technicien actif le MOINS chargé (nb de tickets
    ouverts assignés) pour une affectation automatique, en excluant les
    indisponibilités RH (lues via les selectors rh — jamais un import direct
    des modèles rh) quand elles sont disponibles.

    Renvoie l'utilisateur choisi, ou None si aucun technicien actif éligible
    (repli : le ticket reste sans affectation — comportement OFF inchangé).
    Un technicien = tout utilisateur ACTIF de la société ayant déjà été
    assigné à au moins un ticket (participe au pool de charge) — ce périmètre
    évite d'affecter un compte administratif jamais destiné au terrain.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Count, Q
    from .models import Ticket

    User = get_user_model()
    jour = jour or timezone.localdate()

    candidats = list(
        User.objects.filter(
            company=company, is_active=True,
            tickets_techniques__isnull=False,
        ).distinct()
        .annotate(
            nb_ouverts=Count(
                'tickets_techniques',
                filter=Q(
                    tickets_techniques__statut__in=Ticket.OPEN_STATUTS,
                    tickets_techniques__annule=False),
            ),
        )
        .order_by('nb_ouverts', 'id'))

    for user in candidats:
        if not _technicien_indisponible(company, user, jour):
            return user
    return None


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


# ── XSAV16 — Journal d'immobilisation (downtime) + disponibilité % ──────────

class DowntimeOverlapError(Exception):
    """XSAV16 — Levée quand une nouvelle fenêtre de downtime chevauche une
    fenêtre existante du MÊME équipement (une immobilisation double compterait
    la disponibilité %)."""


def ouvrir_downtime(*, company, equipement, debut, ticket=None, motif='',
                    created_by=None):
    """XSAV16 — Ouvre une immobilisation pour ``equipement`` à partir de
    ``debut``. Refuse tout chevauchement avec une fenêtre existante du même
    équipement : une fenêtre EN COURS (fin=None) chevauche toujours toute
    nouvelle ouverture (on ne peut pas ouvrir une seconde panne pendant que la
    première n'est pas close) ; une fenêtre déjà close chevauche si
    ``debut`` tombe dans son intervalle [debut, fin]. Lève
    ``DowntimeOverlapError`` en cas de chevauchement — jamais une seconde
    fenêtre concurrente créée par erreur."""
    from .models import EquipementDowntime

    en_cours = EquipementDowntime.objects.filter(
        equipement=equipement, fin__isnull=True).exists()
    if en_cours:
        raise DowntimeOverlapError(
            'Une immobilisation est déjà en cours pour cet équipement.')

    chevauche = EquipementDowntime.objects.filter(
        equipement=equipement, debut__lte=debut, fin__gte=debut).exists()
    if chevauche:
        raise DowntimeOverlapError(
            'Cette période chevauche une immobilisation existante.')

    return EquipementDowntime.objects.create(
        company=company, equipement=equipement, debut=debut,
        ticket=ticket, motif=motif or '', created_by=created_by)


def disponibilite_equipement(equipement, *, debut_periode, fin_periode):
    """XSAV16 — Disponibilité % d'un équipement sur ``[debut_periode,
    fin_periode]`` (bornes datetime timezone-aware, inclusives).

    Calcule le temps cumulé d'immobilisation qui INTERSECTE la période
    demandée (une fenêtre en cours utilise ``fin_periode`` comme borne haute
    provisoire), puis renvoie :
      {'duree_periode_heures': float, 'duree_downtime_heures': float,
       'disponibilite_pct': float}
    ``disponibilite_pct`` = 100 si la période est nulle/négative (repli sûr,
    aucune division par zéro)."""
    from django.db.models import Q
    from .models import EquipementDowntime

    duree_periode = (fin_periode - debut_periode).total_seconds() / 3600
    if duree_periode <= 0:
        return {
            'duree_periode_heures': 0.0, 'duree_downtime_heures': 0.0,
            'disponibilite_pct': 100.0,
        }

    qs = EquipementDowntime.objects.filter(
        equipement=equipement, debut__lte=fin_periode,
    ).filter(Q(fin__gte=debut_periode) | Q(fin__isnull=True))

    downtime_heures = 0.0
    for dt in qs:
        fin = dt.fin or fin_periode
        seg_debut = max(dt.debut, debut_periode)
        seg_fin = min(fin, fin_periode)
        if seg_fin > seg_debut:
            downtime_heures += (seg_fin - seg_debut).total_seconds() / 3600

    downtime_heures = min(downtime_heures, duree_periode)
    disponibilite_pct = round(
        (1 - downtime_heures / duree_periode) * 100, 2)
    return {
        'duree_periode_heures': round(duree_periode, 2),
        'duree_downtime_heures': round(downtime_heures, 2),
        'disponibilite_pct': disponibilite_pct,
    }


# ── XSAV17 — Relevés compteur (heures / kWh) + entretien conditionnel ────────

class ReleveDecroissantError(Exception):
    """XSAV17 — Levée quand un relevé est INFÉRIEUR au dernier relevé du même
    équipement (le compteur est cumulatif, jamais décroissant)."""


def enregistrer_releve_compteur(*, company, equipement, type_releve, valeur,
                                date_releve, created_by=None):
    """XSAV17 — Enregistre un relevé de compteur et, si un seuil
    (`Equipement.entretien_toutes_les_heures`) est configuré et franchi
    depuis le dernier entretien généré, matérialise EXACTEMENT UN ticket
    préventif (idempotent : `dernier_entretien_compteur_valeur` avance
    aussitôt qu'un ticket est généré, donc un second relevé au-dessus du
    même seuil — avant le prochain entretien — n'en recrée pas un second).

    Refuse (``ReleveDecroissantError``) un relevé strictement inférieur au
    dernier relevé DU MÊME TYPE pour cet équipement — le compteur est
    cumulatif, jamais décroissant. Renvoie ``(releve, ticket_ou_None)``.
    """
    from decimal import Decimal
    from .models import ReleveCompteurEquipement

    valeur = Decimal(str(valeur))
    dernier = (ReleveCompteurEquipement.objects
               .filter(equipement=equipement, type=type_releve)
               .order_by('-valeur').first())
    if dernier is not None and valeur < dernier.valeur:
        raise ReleveDecroissantError(
            'Ce relevé est inférieur au dernier relevé enregistré '
            f'({dernier.valeur}) — le compteur ne peut pas reculer.')

    releve = ReleveCompteurEquipement.objects.create(
        company=company, equipement=equipement, type=type_releve,
        valeur=valeur, date=date_releve, created_by=created_by)

    seuil = equipement.entretien_toutes_les_heures
    ticket = None
    if seuil:
        reference_base = equipement.dernier_entretien_compteur_valeur or Decimal('0')
        if valeur - reference_base >= seuil:
            ticket = _generer_ticket_preventif_compteur(
                company, equipement, type_releve, valeur, created_by)
            equipement.dernier_entretien_compteur_valeur = valeur
            equipement.save(
                update_fields=['dernier_entretien_compteur_valeur'])
    return releve, ticket


def _generer_ticket_preventif_compteur(company, equipement, type_releve,
                                       valeur, created_by):
    """XSAV17 — Matérialise le ticket préventif de franchissement de seuil."""
    from apps.ventes.utils.references import create_with_reference
    from .models import Ticket

    installation = equipement.installation
    client = getattr(installation, 'client', None)
    label = 'heures' if type_releve == 'heures' else 'kWh'
    description = (
        f'Entretien préventif dû (seuil de {label} franchi — '
        f'compteur à {valeur} {label}).')

    def _create(ref):
        return Ticket.objects.create(
            reference=ref, company=company, client=client,
            installation=installation, equipement=equipement,
            type=Ticket.Type.PREVENTIF, statut=Ticket.Statut.NOUVEAU,
            date_ouverture=timezone.localdate(), description=description,
            created_by=created_by)
    return create_with_reference(Ticket, 'SAV', company, _create)
