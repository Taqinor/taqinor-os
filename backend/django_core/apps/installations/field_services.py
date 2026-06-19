"""
F5–F8 — services du module d'exécution terrain (interventions).

  * F5 — liste de préparation : matériel (nomenclature gelée du chantier) +
    outils (kit d'outillage), cases « chargé », confirmation « Tout est
    chargé », pourcentage de complétion, et drapeau « manquant » qui réutilise
    la réservation de stock existante (apps.stock.services.available_quantity).
  * F6 — distance entre la position GPS d'arrivée et le GPS du chantier.
  * F7 — shot list configurable (créneaux avant/pendant/après) + amorçage par
    défaut au standard de documentation d'un chantier solaire.
  * F8 — créneaux OBLIGATOIRES manquant de photo (garde la transition vers
    « Terminée »).

Tout est company-scopé ; la société est posée côté serveur. Additif.
"""
from math import asin, cos, radians, sin, sqrt

from django.utils import timezone

from .models import (
    Intervention, InterventionPreparation, PreparationMaterielLigne,
    PreparationOutilLigne, ShotListSlot,
)

# ── F7/F8 — shot list par défaut (standard de documentation chantier solaire) ─
# (cle, libellé, phase, obligatoire). Les créneaux « avant/après » de toiture et
# le tableau électrique sont obligatoires : ce sont les preuves d'installation.
DEFAULT_SHOTLIST = [
    ('toiture_avant', 'Toiture avant pose', 'avant', True),
    ('zone_onduleur_avant', 'Emplacement onduleur (avant)', 'avant', False),
    ('tableau_electrique_avant', 'Tableau électrique (avant)', 'avant', True),
    ('structure_posee', 'Structure de fixation posée', 'pendant', False),
    ('panneaux_en_pose', 'Pose des panneaux', 'pendant', False),
    ('cablage', 'Câblage DC/AC', 'pendant', False),
    ('toiture_apres', 'Toiture après pose', 'apres', True),
    ('onduleur_installe', 'Onduleur installé et raccordé', 'apres', True),
    ('tableau_electrique_apres', 'Tableau électrique (après)', 'apres', True),
    ('compteur', 'Compteur / point de comptage', 'apres', False),
    ('vue_ensemble', "Vue d'ensemble de l'installation", 'apres', True),
]

PHASE_ORDER = ['avant', 'pendant', 'apres']


def seed_shotlist_slots(company):
    """Amorce les créneaux de shot list par défaut une seule fois par société
    (idempotent, additif). Ne touche jamais un créneau existant."""
    if company is None or ShotListSlot.objects.filter(company=company).exists():
        return
    for i, (cle, libelle, phase, oblig) in enumerate(DEFAULT_SHOTLIST):
        ShotListSlot.objects.get_or_create(
            company=company, cle=cle,
            defaults={'libelle': libelle, 'phase': phase,
                      'obligatoire': oblig, 'ordre': i, 'protege': True})


def active_shotlist(company):
    """Créneaux actifs de la société, triés (phase puis ordre)."""
    slots = list(ShotListSlot.objects.filter(company=company, actif=True))
    slots.sort(key=lambda s: (PHASE_ORDER.index(s.phase)
                              if s.phase in PHASE_ORDER else 99, s.ordre, s.id))
    return slots


# ── F6 — distance haversine (km) entre arrivée et GPS du chantier ────────────
def haversine_km(lat1, lng1, lat2, lng2):
    """Distance en kilomètres entre deux points GPS (formule de haversine).
    Renvoie None si une coordonnée manque. Aucun service externe."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    try:
        lat1, lng1, lat2, lng2 = (
            float(lat1), float(lng1), float(lat2), float(lng2))
    except (TypeError, ValueError):
        return None
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = (sin(dlat / 2) ** 2
         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2)
    return round(2 * r * asin(sqrt(a)), 3)


def distance_to_site(intervention):
    """F6 — distance (km) entre la position d'arrivée enregistrée et le GPS du
    chantier, ou None si l'une des deux manque."""
    inst = intervention.installation
    return haversine_km(
        intervention.arrivee_gps_lat, intervention.arrivee_gps_lng,
        getattr(inst, 'gps_lat', None), getattr(inst, 'gps_lng', None))


# ── F5 — construction / synchronisation de la liste de préparation ───────────
def _bom_lines(installation):
    """Lignes matériel (produit_id, designation, quantite entier ≥ 1) depuis la
    nomenclature gelée du chantier. Réutilise la même lecture que la réservation
    de stock. Ignore les quantités nulles/illisibles."""
    out = []
    for ligne in (installation.bom or []):
        if not isinstance(ligne, dict):
            continue
        try:
            qte = int(round(float(ligne.get('quantite') or 0)))
        except (TypeError, ValueError):
            continue
        if qte <= 0:
            continue
        out.append({
            'produit_id': ligne.get('produit_id'),
            'designation': ligne.get('designation') or 'Article',
            'quantite': qte,
        })
    return out


def _kit_for_intervention(intervention):
    """Kit d'outillage à pré-sélectionner : celui (actif) dont le
    `type_intervention` correspond au type de l'intervention, sinon None. Le
    type sur l'intervention est une clé texte (Intervention.Type)."""
    from apps.outillage.models import KitOutillage
    company = intervention.company
    if company is None:
        return None
    return (KitOutillage.objects
            .filter(company=company, actif=True,
                    type_intervention=intervention.type_intervention)
            .order_by('ordre', 'id').first())


def _shortfall_for(produit, requis, company, own_reserved):
    """F5 — manque sur un SKU au moment de la préparation : requis − disponible.
    Le disponible tient compte de la réservation de stock existante (engagé non
    consommé), MAIS pas de la réservation propre à CE chantier (sinon le besoin
    serait compté deux fois — le chantier a déjà réservé sa nomenclature à la
    création). 0 si pas de produit catalogue ou pas de pénurie. Réutilise la
    réservation de stock du module stock."""
    if produit is None:
        return 0
    from apps.stock.services import reserved_quantity
    # Réservé par les AUTRES chantiers = total réservé − réservé par celui-ci.
    reserve_autres = max(
        reserved_quantity(produit) - own_reserved.get(produit.id, 0), 0)
    dispo = produit.quantite_stock - reserve_autres
    return max(requis - dispo, 0)


def ensure_preparation(intervention):
    """F5 — garantit la préparation de l'intervention et synchronise ses lignes
    matériel (depuis la nomenclature gelée) + outils (depuis le kit sélectionné
    ou auto-sélectionné). Idempotent : conserve les cases déjà cochées.
    Renvoie l'objet préparation."""
    company = intervention.company
    prep, _ = InterventionPreparation.objects.get_or_create(
        intervention=intervention, defaults={'company': company})
    if prep.company_id is None and company is not None:
        prep.company = company
        prep.save(update_fields=['company'])
    # Kit : auto-sélection au premier passage si rien n'est choisi.
    if prep.kit_id is None:
        kit = _kit_for_intervention(intervention)
        if kit is not None:
            prep.kit = kit
            prep.save(update_fields=['kit'])
    _sync_materiel(prep)
    _sync_outils(prep)
    return prep


def _sync_materiel(prep):
    """Synchronise les lignes matériel sur la nomenclature gelée du chantier,
    sans perdre l'état « chargé » des lignes déjà présentes. Recalcule le
    manque sur le disponible courant."""
    company = prep.company
    installation = prep.intervention.installation
    lignes = _bom_lines(installation)
    existing = {(li.produit_id, li.designation): li
                for li in prep.materiel.all()}
    seen = set()
    from apps.stock.models import Produit
    from apps.stock.services import _own_reservation_map
    own_reserved = _own_reservation_map(installation)
    for i, b in enumerate(lignes):
        produit = None
        if b['produit_id']:
            produit = Produit.objects.filter(
                id=b['produit_id'], company=company).first()
        key = (produit.id if produit else None, b['designation'])
        seen.add(key)
        manque = _shortfall_for(produit, b['quantite'], company, own_reserved)
        li = existing.get(key)
        if li is None:
            PreparationMaterielLigne.objects.create(
                company=company, preparation=prep, produit=produit,
                designation=b['designation'], quantite_requise=b['quantite'],
                manquant=manque > 0, quantite_manquante=manque, ordre=i)
        else:
            li.quantite_requise = b['quantite']
            li.manquant = manque > 0
            li.quantite_manquante = manque
            li.ordre = i
            li.save(update_fields=['quantite_requise', 'manquant',
                                   'quantite_manquante', 'ordre'])
    # Retire les lignes qui ne sont plus dans la nomenclature.
    for key, li in existing.items():
        if key not in seen:
            li.delete()


def _sync_outils(prep):
    """Synchronise les lignes outils sur le kit sélectionné, sans perdre l'état
    « coché ». Sans kit : aucune ligne outil (préparation sans outillage)."""
    company = prep.company
    kit = prep.kit
    existing = {li.outil_id: li for li in prep.outils.all()}
    seen = set()
    if kit is not None:
        items = kit.items.select_related('outil').all()
        for i, item in enumerate(items):
            outil = item.outil
            seen.add(outil.id)
            li = existing.get(outil.id)
            if li is None:
                PreparationOutilLigne.objects.create(
                    company=company, preparation=prep, outil=outil,
                    libelle=outil.nom, ordre=i)
            elif li.ordre != i or li.libelle != outil.nom:
                li.ordre = i
                li.libelle = outil.nom
                li.save(update_fields=['ordre', 'libelle'])
    # Retire les lignes d'un outil qui n'est plus dans le kit (ou kit changé).
    for outil_id, li in existing.items():
        if outil_id not in seen:
            li.delete()


def preparation_completion(prep):
    """F5 — pourcentage de complétion = (lignes matériel chargées + outils
    cochés) / (total lignes). None si la préparation est vide."""
    mats = list(prep.materiel.all())
    outils = list(prep.outils.all())
    total = len(mats) + len(outils)
    if total == 0:
        return None
    done = sum(1 for m in mats if m.charge) + sum(1 for o in outils if o.coche)
    return round(100 * done / total)


def preparation_manques(prep):
    """F5 — lignes matériel en pénurie (manquant=True) recalculées."""
    return [li for li in prep.materiel.all() if li.manquant]


def can_confirm_charge(prep):
    """« Tout est chargé » exige que chaque ligne (matériel + outils) soit
    cochée. Une préparation vide est confirmable (rien à charger)."""
    mats = list(prep.materiel.all())
    outils = list(prep.outils.all())
    return all(m.charge for m in mats) and all(o.coche for o in outils)


# ── F7/F8 — photos de l'intervention par créneau de shot list ────────────────
def intervention_photos(intervention):
    """F7 — pièces jointes (records.Attachment) de l'intervention, réutilisant
    le stockage objet générique. Renvoie le queryset trié (récentes d'abord)."""
    from django.contrib.contenttypes.models import ContentType
    from apps.records.models import Attachment
    ct = ContentType.objects.get_for_model(Intervention)
    return (Attachment.objects
            .filter(content_type=ct, object_id=intervention.id,
                    company=intervention.company)
            .select_related('uploaded_by')
            .order_by('-created_at', 'id'))


def photos_by_slot(intervention):
    """Map {slot_cle: [attachment, ...]} pour l'intervention (le créneau est
    porté par le `filename` préfixé `slot:<cle>|`, voir la vue photos)."""
    out = {}
    for att in intervention_photos(intervention):
        cle = _slot_of_attachment(att)
        out.setdefault(cle, []).append(att)
    return out


_SLOT_PREFIX = 'slot:'
_SLOT_SEP = '|'


def encode_slot_filename(slot_cle, filename):
    """Encode le créneau de shot list dans le nom de fichier stocké, pour
    réutiliser le modèle Attachment générique sans nouveau champ croisé."""
    if not slot_cle:
        return filename
    return f'{_SLOT_PREFIX}{slot_cle}{_SLOT_SEP}{filename}'


def _slot_of_attachment(att):
    name = att.filename or ''
    if name.startswith(_SLOT_PREFIX) and _SLOT_SEP in name:
        return name[len(_SLOT_PREFIX):].split(_SLOT_SEP, 1)[0]
    return ''


def display_filename(att):
    """Nom de fichier sans le préfixe technique de créneau."""
    name = att.filename or ''
    if name.startswith(_SLOT_PREFIX) and _SLOT_SEP in name:
        return name.split(_SLOT_SEP, 1)[1]
    return name


def missing_required_shots(intervention):
    """F8 — créneaux OBLIGATOIRES (actifs) sans aucune photo pour cette
    intervention. Renvoie la liste des ShotListSlot manquants."""
    by_slot = photos_by_slot(intervention)
    missing = []
    for slot in active_shotlist(intervention.company):
        if slot.obligatoire and not by_slot.get(slot.cle):
            missing.append(slot)
    return missing


# ── Garde de transition de statut (F5 départ + F8 arrivée à « Terminée ») ────
def transition_block_reason(intervention, new_statut):
    """Renvoie un message FR si la transition de statut est interdite, sinon
    None. Garde PROPRE à l'intervention — ne lit/écrit JAMAIS le statut chantier
    ni STAGES.py.

    F5 : quitter « À préparer » exige la confirmation « Tout est chargé ».
    F8 : passer à « Terminée » exige une photo par créneau obligatoire."""
    if new_statut == intervention.statut:
        return None
    order = list(Intervention.STATUT_ORDER)

    def rank(s):
        try:
            return order.index(s)
        except ValueError:
            return -1

    # F5 — on ne peut AVANCER au-delà de « À préparer » que si « Tout est
    # chargé » a été confirmé. Un recul (vers À préparer) reste permis.
    if (intervention.statut == Intervention.Statut.A_PREPARER
            and rank(new_statut) > rank(Intervention.Statut.A_PREPARER)):
        prep = getattr(intervention, 'preparation', None)
        if prep is None or not prep.tout_charge:
            return ("Confirmez « Tout est chargé » dans la liste de préparation "
                    "avant de quitter « À préparer ».")

    # F8 — on ne peut atteindre « Terminée » (ou au-delà) que si chaque créneau
    # obligatoire a au moins une photo.
    if (rank(new_statut) >= rank(Intervention.Statut.TERMINEE)
            and rank(intervention.statut) < rank(Intervention.Statut.TERMINEE)):
        missing = missing_required_shots(intervention)
        if missing:
            noms = ', '.join(s.libelle for s in missing)
            return ("Photos obligatoires manquantes avant « Terminée » : "
                    f"{noms}.")
    return None


def confirm_charge(prep, user):
    """F5 — pose la confirmation « Tout est chargé » (acteur + date côté
    serveur). Lève ValueError si toutes les lignes ne sont pas cochées."""
    if not can_confirm_charge(prep):
        raise ValueError(
            "Toutes les lignes (matériel + outils) doivent être cochées.")
    prep.tout_charge = True
    prep.confirme_par = user
    prep.confirme_le = timezone.now()
    prep.save(update_fields=['tout_charge', 'confirme_par', 'confirme_le'])
    return prep
