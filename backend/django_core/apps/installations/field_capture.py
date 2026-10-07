"""F9–F19 — services de capture/réconciliation terrain d'une intervention.

  * F9  — n° de série par composant (+ OCR swappable no-op) → parc installé.
  * F10 — annotation d'une photo (dessin + légende).
  * F11 — réconciliation du matériel consommé (prévu vs utilisé), justification
          requise sur variance, consommation réelle → mouvements de stock.
  * F12 — surface de revue des dépassements (seuil % éditable en Paramètres).
  * F13 — mémos vocaux (stockage objet) + F14 transcription swappable no-op.
  * F15 — temps d'équipe (durée sur site + temps de trajet).
  * F16 — réserves (punch-list) → suivi intervention / ticket SAV.
  * F17 — réconciliation du retour d'outillage.
  * F18 — sign-off des consignes de sécurité (checklist configurable).

Tout est company-scopé ; la société est posée côté serveur. Additif. La machine
à états de l'intervention n'est JAMAIS touchée par ces services (séparée du
chantier et de STAGES.py).
"""
from decimal import Decimal

from django.utils import timezone

from . import swappable
from .models import (
    ConsommationLigne, Installation, MaterielConsommation, SafetyCheckItem,
    SafetyChecklistSlot, SafetySignoff,
)


# ── F9 — n° de série par composant → parc installé (sav.Equipement) ──────────
def push_serials_to_parc(intervention, user):
    """F9 — pousse les n° de série relevés (avec un produit catalogue) vers le
    parc installé (sav.Equipement), comme la checklist chantier (N9). Idempotent
    via `pousse_parc` : un même relevé ne crée jamais deux équipements. Un n° de
    série VIDE n'empêche PAS la création (l'appareil est tracé sans série).
    Renvoie le nombre d'équipements créés."""
    from apps.sav.services import create_equipement_from_serial
    inst = intervention.installation
    created = 0
    for serial in intervention.serials.filter(
            pousse_parc=False, produit__isnull=False):
        create_equipement_from_serial(
            company=intervention.company, produit=serial.produit,
            installation=inst,
            numero_serie=(serial.numero_serie or '').strip() or None,
            date_pose=inst.date_pose_reelle or timezone.localdate(),
            created_by=user)
        serial.pousse_parc = True
        serial.save(update_fields=['pousse_parc'])
        created += 1
    return created


# ── F11 — construction / synchronisation de la réconciliation matériel ────────
def _bom_quantities(installation):
    """{(produit_id, designation): quantite_prevue Decimal} depuis la
    nomenclature gelée du chantier. Cumule les lignes identiques.

    ASTK127 — plus de copie du lecteur de nomenclature : les lignes viennent
    de ``services.lignes_bom_entieres`` (le survivant unique, arrondi HALF_UP
    de la sortie de la vente) — le terrain lit 13 pour 12,5 m comme la
    réservation N14 et la facture."""
    from .services import lignes_bom_entieres
    out = {}
    for produit_id, designation, qte in lignes_bom_entieres(
            installation.bom):
        key = (produit_id, designation)
        out[key] = out.get(key, Decimal('0')) + Decimal(qte)
    return out


def ensure_consommation(intervention):
    """F11 — garantit la réconciliation matériel de l'intervention et amorce ses
    lignes depuis la nomenclature gelée (prévu). Idempotent : ne touche pas une
    réconciliation validée, conserve les quantités utilisées et lignes hors
    nomenclature déjà saisies. Renvoie l'objet."""
    company = intervention.company
    cons, _ = MaterielConsommation.objects.get_or_create(
        intervention=intervention, defaults={'company': company})
    if cons.company_id is None and company is not None:
        cons.company = company
        cons.save(update_fields=['company'])
    if cons.valide:
        return cons
    besoins = _bom_quantities(intervention.installation)
    existing = {(li.produit_id, li.designation): li
                for li in cons.lignes.filter(hors_nomenclature=False)}
    seen = set()
    for i, ((produit_id, designation), qte) in enumerate(besoins.items()):
        key = (produit_id, designation)
        seen.add(key)
        li = existing.get(key)
        if li is None:
            ligne = ConsommationLigne(
                company=company, consommation=cons, produit_id=produit_id,
                designation=designation, quantite_prevue=qte,
                quantite_utilisee=qte, ordre=i)
            ligne.save()
        elif li.quantite_prevue != qte or li.ordre != i:
            li.quantite_prevue = qte
            li.ordre = i
            li.save(update_fields=['quantite_prevue', 'ordre'])
    # Retire les lignes nomenclature disparues (jamais les hors-nomenclature).
    for key, li in existing.items():
        if key not in seen:
            li.delete()
    return cons


def ligne_needs_justification(ligne):
    """F11 — une ligne exige une justification quand utilisé ≠ prévu et qu'aucune
    justification (texte OU mémo vocal) n'est fournie."""
    if ligne.variance == 0:
        return False
    return not (ligne.justification.strip() or ligne.justification_memo_id)


def consommation_missing_justifications(cons):
    """Lignes en variance sans justification (bloquent la validation)."""
    return [li for li in cons.lignes.all() if ligne_needs_justification(li)]


def validate_consommation(cons, user):
    """F11 — valide la réconciliation : la consommation RÉELLE pilote le stock.

    Pour chaque ligne (sur SKU catalogue) non encore appliquée, crée UN
    MouvementStock SORTIE de la quantité réellement utilisée et décrémente le
    stock — idempotent via `stock_applique`. Lève ValueError si une variance
    n'est pas justifiée. Renvoie le nombre de SKU appliqués au stock.

    La réservation N14 du chantier (estimation devis) est libérée : c'est la
    consommation terrain, pas l'estimation, qui meut le stock."""
    from django.db import transaction
    from apps.stock.selectors import lock_produit
    from apps.stock.services import (
        mouvement_type_sortie, record_stock_movement,
    )

    missing = consommation_missing_justifications(cons)
    if missing:
        raise ValueError(
            "Justification requise sur les lignes en écart : "
            + ', '.join(li.designation for li in missing) + '.')

    applied = 0
    installation = cons.intervention.installation
    with transaction.atomic():
        lignes = (cons.lignes.select_for_update()
                  .filter(stock_applique=False, produit__isnull=False))
        for li in lignes:
            qte = li.quantite_utilisee or Decimal('0')
            if qte <= 0:
                li.stock_applique = True
                li.save(update_fields=['stock_applique'])
                continue
            produit = lock_produit(li.produit_id)
            qte_avant = produit.quantite_stock
            # ERR80 — garde plancher : ne sors jamais plus que le stock en main
            # (on borne à zéro plutôt que de piloter `quantite_stock` négatif).
            qte_sortie = min(qte, qte_avant) if qte_avant > 0 else Decimal('0')
            # ERR41 — sortie sur la quantité DÉCIMALE (jamais int(qte)) : une
            # ligne de 0,5 sort bien 0,5 (et n'est plus tronquée à 0/perdue).
            qte_apres = qte_avant - qte_sortie
            record_stock_movement(
                company=cons.company, produit=produit,
                type_mouvement=mouvement_type_sortie(),
                quantite=qte_sortie, quantite_avant=qte_avant,
                quantite_apres=qte_apres,
                reference=installation.reference,
                note=(f'Consommation réelle intervention '
                      f'{cons.intervention_id} ({installation.reference})'),
                created_by=user,
                # YSTCK3 — consommation DEPUIS la camionnette assignée à
                # l'intervention (si posée) : décrémente CE StockEmplacement
                # plutôt que de laisser le principal absorber la baisse à
                # tort. Sans camionnette assignée : comportement historique
                # inchangé (défaut None).
                emplacement_source=cons.intervention.camionnette)
            li.stock_applique = True
            li.save(update_fields=['stock_applique'])
            applied += 1
        # La réservation devis du chantier ne doit plus mouvoir le stock : on la
        # libère (non consommée) pour éviter une double sortie au passage
        # « Installé ». Idempotent côté service N14.
        from .services import release_reservations
        release_reservations(installation)
        cons.valide = True
        cons.valide_par = user
        cons.valide_le = timezone.now()
        cons.save(update_fields=['valide', 'valide_par', 'valide_le'])
    return applied


# ── F12 — surface de revue des dépassements ──────────────────────────────────
def overage_threshold_pct(company):
    """Seuil (%) de dépassement éditable en Paramètres (défaut 10)."""
    if company is None:
        return Decimal('10')
    try:
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company)
        val = getattr(prof, 'overage_seuil_pct', None)
        return Decimal(str(val)) if val is not None else Decimal('10')
    except Exception:
        return Decimal('10')


def consommation_overage(cons, threshold_pct=None):
    """F12 — lignes dont le dépassement (utilisé/prévu − 1) excède le seuil %.

    Une ligne hors-nomenclature (prévu = 0) avec une quantité utilisée > 0
    compte comme dépassement total. Renvoie une liste de dicts décrivant chaque
    dépassement, avec sa justification — JAMAIS de prix d'achat ni de marge."""
    if threshold_pct is None:
        threshold_pct = overage_threshold_pct(cons.company)
    seuil = Decimal(str(threshold_pct))
    rows = []
    for li in cons.lignes.all():
        prevu = li.quantite_prevue or Decimal('0')
        utilise = li.quantite_utilisee or Decimal('0')
        if utilise <= prevu:
            continue
        if prevu == 0:
            pct = Decimal('100')
        else:
            pct = (utilise - prevu) / prevu * Decimal('100')
        if pct < seuil:
            continue
        rows.append({
            'ligne_id': li.id,
            'designation': li.designation,
            'quantite_prevue': prevu,
            'quantite_utilisee': utilise,
            'depassement_pct': round(pct, 1),
            'justification': li.justification,
            'justification_memo': li.justification_memo_id,
        })
    return rows


def interventions_en_revue(company, threshold_pct=None):
    """F12 — interventions de la société dont la consommation validée dépasse le
    seuil. Renvoie [(intervention, [overage_rows])]."""
    if threshold_pct is None:
        threshold_pct = overage_threshold_pct(company)
    out = []
    qs = (MaterielConsommation.objects
          .filter(company=company, valide=True)
          .select_related('intervention', 'intervention__installation')
          .prefetch_related('lignes'))
    for cons in qs:
        rows = consommation_overage(cons, threshold_pct)
        if rows:
            out.append((cons.intervention, rows))
    return out


# ── F15 — temps d'équipe (durée sur site + temps de trajet) ──────────────────
def _minutes_between(start, end):
    if not (start and end):
        return None
    delta = end - start
    return round(delta.total_seconds() / 60)


def crew_time(intervention):
    """F15 — durée sur site (arrivée → fin) et temps de trajet (départ-dépôt →
    arrivée, + arrivée→retour si renseigné), en minutes. La « fin » est l'heure
    de passage à « Terminée » si connue (date_realisee + check-in), sinon le
    retour-dépôt. Renvoie un dict de minutes (valeurs None si données absentes).

    Alimente le champ chantier des jours-homme réels via labour_days()."""
    # Heure de fin sur site : retour dépôt sinon non borné.
    on_site = _minutes_between(intervention.arrivee_site_le,
                               intervention.retour_depot_le)
    trajet_aller = _minutes_between(intervention.depart_depot_le,
                                    intervention.arrivee_site_le)
    return {
        'depart_depot_le': intervention.depart_depot_le,
        'arrivee_site_le': intervention.arrivee_site_le,
        'retour_depot_le': intervention.retour_depot_le,
        'duree_sur_site_min': on_site,
        'trajet_aller_min': trajet_aller,
    }


def labour_days_for_intervention(intervention, heures_jour=8):
    """F15 — jours-homme estimés de l'intervention : durée sur site × taille
    d'équipe / (heures_jour). None si la durée n'est pas connue."""
    t = crew_time(intervention)
    minutes = t['duree_sur_site_min']
    if minutes is None:
        return None
    equipe = max(intervention.equipe.count(), 1)
    jours = Decimal(minutes) / Decimal(60) / Decimal(heures_jour) * equipe
    return round(jours, 2)


def push_labour_to_chantier(intervention, heures_jour=8):
    """F15 — additionne les jours-homme réels de TOUTES les interventions du
    chantier dans `Installation.labour_jours_reels`. Idempotent (recalcul
    complet, jamais d'accumulation en double). Renvoie la valeur posée."""
    inst = intervention.installation
    total = Decimal('0')
    has_data = False
    for itv in inst.interventions.all():
        jd = labour_days_for_intervention(itv, heures_jour)
        if jd is not None:
            total += Decimal(str(jd))
            has_data = True
    if not has_data:
        return inst.labour_jours_reels
    inst.labour_jours_reels = round(total, 1)
    inst.save(update_fields=['labour_jours_reels'])
    return inst.labour_jours_reels


# ── F18 — consignes de sécurité (checklist configurable + sign-off) ──────────
DEFAULT_SAFETY_SLOTS = [
    ('epi_portes', 'EPI portés (casque, gants, chaussures, harnais si hauteur)'),
    ('consignation_electrique', 'Consignation électrique effectuée (VAT)'),
    ('zone_securisee', 'Zone de travail balisée et sécurisée'),
    ('echelle_stable', 'Échelle / échafaudage stable et vérifié'),
]


def seed_safety_slots(company):
    """Amorce les consignes de sécurité par défaut (idempotent, additif)."""
    if company is None or SafetyChecklistSlot.objects.filter(
            company=company).exists():
        return
    for i, (cle, libelle) in enumerate(DEFAULT_SAFETY_SLOTS):
        SafetyChecklistSlot.objects.get_or_create(
            company=company, cle=cle,
            defaults={'libelle': libelle, 'ordre': i, 'protege': True})


# CIQ624 — consignes C&I (site pro) : aucun chiffre, aucun article. Ajoutées
# UNE fois (clés manquantes) ; une consigne supprimée ou désactivée n'est
# jamais recréée tant qu'une autre consigne C&I existe.
CONSIGNES_CI = [
    ('ci_hauteur', 'Protections collectives ou harnais, et formation au '
                   'travail en hauteur', None),
    ('ci_levage', 'Levage (nacelle, grue) : périmètre balisé', None),
    ('ci_toiture_fragile', 'Toiture fragile (fibrociment, lanterneaux) : '
                           'cheminements protégés', None),
    ('ci_coactivite', "Plan de prévention et coactivité avec l'exploitant",
     None),
    ('ci_habilitation', 'Habilitation électrique du personnel (référentiel à '
                        'confirmer)', None),
    ('ci_consignation_exploitant', "Coupure et consignation coordonnées avec "
                                   "l'exploitant", None),
    ('ci_permis_feu', 'Permis de feu en cas de point chaud', None),
    ('ci_extincteur', 'Extincteur à portée', None),
    ('ci_consignation_poste_mt', 'Consignation au poste par une personne '
                                 'habilitée', 'mt'),
]


def ensure_consignes_ci(company):
    """CIQ624 — ajoute UNE fois les consignes C&I manquantes (idempotent,
    additif). Dès qu'une consigne C&I existe (active ou non), rien n'est
    recréé : une consigne supprimée ou désactivée par la société est
    respectée. Renvoie le nombre de consignes créées."""
    cles = [cle for cle, _l, _n in CONSIGNES_CI]
    if company is None or SafetyChecklistSlot.objects.filter(
            company=company, cle__in=cles).exists():
        return 0
    depart = SafetyChecklistSlot.objects.filter(company=company).count()
    for i, (cle, libelle, niveau) in enumerate(CONSIGNES_CI):
        SafetyChecklistSlot.objects.create(
            company=company, cle=cle, libelle=libelle, ordre=depart + i,
            niveau_tension=niveau, protege=False)
    return len(CONSIGNES_CI)


def ensure_safety_signoff(intervention):
    """F18 — garantit le sign-off de l'intervention et matérialise ses points
    depuis les consignes actives (création paresseuse, idempotente).

    CIQ624 — sur un chantier C&I, les consignes C&I sont ajoutées une fois ;
    une consigne ``mt`` n'est matérialisée que sur un chantier MT."""
    company = intervention.company
    seed_safety_slots(company)
    installation = getattr(intervention, 'installation', None)
    niveau = getattr(installation, 'niveau_tension', None)
    if (getattr(installation, 'type_installation', None)
            == Installation.TypeInstallation.INDUSTRIEL):
        ensure_consignes_ci(company)
    signoff, _ = SafetySignoff.objects.get_or_create(
        intervention=intervention, defaults={'company': company})
    if signoff.company_id is None and company is not None:
        signoff.company = company
        signoff.save(update_fields=['company'])
    existing = {it.cle for it in signoff.items.all()}
    slots = SafetyChecklistSlot.objects.filter(company=company, actif=True)
    for slot in slots:
        if slot.niveau_tension and slot.niveau_tension != niveau:
            continue
        if slot.cle not in existing:
            SafetyCheckItem.objects.create(
                company=company, signoff=signoff, cle=slot.cle,
                libelle=slot.libelle, ordre=slot.ordre)
    return signoff


# ── F14 — transcription d'un mémo vocal (interface swappable, no-op) ─────────
def transcribe_memo(memo):
    """F14 — pose la transcription du mémo via l'interface SWAPPABLE. No-op par
    défaut : étiquette « Non transcrit — service non configuré », `transcrit`
    reste False. L'audio reste la source de vérité. Renvoie le mémo."""
    audio_bytes = None  # le no-op n'a pas besoin de relire l'objet MinIO.
    texte, configure = swappable.transcribe(memo.company, audio_bytes)
    memo.transcript = texte
    memo.transcrit = bool(configure)
    memo.save(update_fields=['transcript', 'transcrit'])
    return memo
