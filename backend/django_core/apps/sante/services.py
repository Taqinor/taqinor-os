"""Services (écriture/orchestration) du module ``apps.sante``.

Comme ``selectors.py`` (lecture), destiné à être importé PAR D'AUTRES APPS
(import local, jamais au niveau module) — toute référence à un document d'une
autre app passe par une FK par chaîne ou par le sélecteur/service dédié de
cette app cible, jamais par un import direct de ses ``models``.
"""


def attribuer_numero_dossier(patient):
    """NTSAN3 — pose ``patient.numero_dossier`` (anti-collision, plus-haut-
    utilisé+1 par société) via le service de numérotation de fondation
    ``core.numbering`` — jamais un ``count()+1`` (collision documentée si des
    dossiers sont supprimés). No-op si déjà posé (idempotent)."""
    if patient.numero_dossier:
        return patient
    from core.numbering import next_reference

    from .models import Patient

    patient.numero_dossier = next_reference(
        Patient, 'PAT', patient.company, padding=5, period='none',
        field='numero_dossier')
    patient.save(update_fields=['numero_dossier'])
    return patient


def resoudre_client_pour_patient(patient):
    """NTSAN3 — résout/rattache un ``crm.Client`` pour ce patient, SANS jamais
    importer ``apps.crm.models`` (import fonction-local + ``selectors.py``
    de la cible, comme ``apps.crm.services.resolve_client_for_lead``).

    Règle : réutilise le lien existant si déjà posé ; sinon cherche un client
    de la MÊME société par email (si le patient en a un) ; sinon en crée un
    nouveau. Renvoie l'instance ``crm.Client`` (jamais None : un patient a
    toujours un dossier client correspondant une fois résolu).
    """
    if patient.client_id:
        return patient.client

    from apps.crm.selectors import find_client_by_email
    from django.apps import apps as django_apps

    Client = django_apps.get_model('crm', 'Client')

    client = None
    if patient.email:
        client = find_client_by_email(patient.email, company=patient.company)
    if client is None:
        client = Client.objects.create(
            company=patient.company,
            nom=patient.nom,
            prenom=patient.prenom or None,
            email=patient.email or None,
            telephone=patient.telephone or None,
            adresse=patient.adresse or None,
            cin=patient.cin or None,
        )
    patient.client = client
    patient.save(update_fields=['client'])
    return client


def verifier_chevauchement_rdv(
        *, company, praticien, salle, date_heure_debut, duree_min,
        exclude_id=None):
    """NTSAN2/NTSAN4 — garde applicative de non-double-réservation.

    Refuse un `RendezVous` qui chevaucherait un autre RDV actif (statut !=
    annulé) sur le MÊME praticien OU la MÊME salle (si une salle est
    demandée). Renvoie un message FR de blocage, ou ``None`` si le créneau
    est libre. Les durées variant par RDV, le chevauchement est calculé en
    Python (pas une contrainte DB) : ``debut < autre_fin ET fin > autre_debut``.
    """
    from datetime import timedelta

    from .models import RendezVous

    fin = date_heure_debut + timedelta(minutes=duree_min)

    qs = RendezVous.objects.filter(company=company).exclude(
        statut=RendezVous.Statut.ANNULE)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    def _chevauche(autre):
        autre_fin = autre.date_heure_debut + timedelta(minutes=autre.duree_min)
        return date_heure_debut < autre_fin and fin > autre.date_heure_debut

    if praticien is not None:
        for autre in qs.filter(praticien=praticien):
            if _chevauche(autre):
                return (
                    "Ce praticien a déjà un rendez-vous sur ce créneau.")

    if salle is not None:
        for autre in qs.filter(salle=salle):
            if _chevauche(autre):
                return "Cette salle est déjà réservée sur ce créneau."

    return None


def verifier_horaires_praticien(*, praticien, date_heure_debut, duree_min):
    """NTSAN30 — garde applicative : refuse un ``RendezVous`` hors horaire
    d'ouverture configuré ou pendant une indisponibilité du praticien.

    Un praticien SANS ``HoraireOuverturePraticien`` configuré n'est PAS
    restreint par cette garde (additif, jamais de régression pour un
    praticien déjà en service avant paramétrage des horaires — miroir de
    ``selectors._plages_ouverture`` qui retombe sur 08:00-18:00 côté
    calcul de disponibilités NTSAN29). Une ``IndisponibilitePraticien`` qui
    recoupe le créneau bloque TOUJOURS, configurée ou non. Renvoie un
    message FR de blocage, ou ``None`` si le créneau est autorisé."""
    from datetime import timedelta

    from .models import HoraireOuverturePraticien, IndisponibilitePraticien

    if praticien is None:
        return None

    fin = date_heure_debut + timedelta(minutes=duree_min)

    horaires = list(HoraireOuverturePraticien.objects.filter(
        company=praticien.company, praticien=praticien,
        jour_semaine=date_heure_debut.weekday()))
    if horaires:
        dans_horaire = any(
            date_heure_debut.date() == fin.date()
            and date_heure_debut.time() >= h.heure_debut
            and fin.time() <= h.heure_fin
            for h in horaires)
        if not dans_horaire:
            return "Ce créneau est hors des horaires d'ouverture du praticien."

    indisponible = IndisponibilitePraticien.objects.filter(
        company=praticien.company, praticien=praticien,
        date_debut__lt=fin, date_fin__gt=date_heure_debut).exists()
    if indisponible:
        return 'Le praticien est indisponible sur ce créneau.'

    return None


def cloturer_admission(admission, *, date_sortie=None):
    """NTSAN6 — clôture une admission (``en_cours`` → ``cloturee``).

    Garde (critère d'acceptation NTSAN6, complétée par NTSAN10/NTSAN13) :
    une admission ne peut être clôturée que si tous ses actes réalisés
    rattachés sont facturés (``facture_sante_id`` posé) ou explicitement
    marqués non-facturables (``facturable=False``).
    """
    from django.utils import timezone

    from .models import Admission

    if admission.statut == Admission.Statut.CLOTUREE:
        raise ValueError('Cette admission est déjà clôturée.')

    actes_bloquants = admission.actes_realises.filter(
        facturable=True, facture_sante__isnull=True)
    if actes_bloquants.exists():
        raise ValueError(
            "Impossible de clôturer : des actes réalisés ne sont ni "
            "facturés ni marqués non-facturables.")

    admission.statut = Admission.Statut.CLOTUREE
    admission.date_sortie = date_sortie or timezone.now()
    admission.save(update_fields=['statut', 'date_sortie'])
    return admission


def realiser_acte(
        *, admission, patient, praticien, acte, date_realisation,
        quantite=1, facturable=True):
    """NTSAN10 — enregistre un acte réalisé, tarif SNAPSHOTTÉ à la
    réalisation via ``selectors.tarif_applicable`` (convention du patient si
    connue, sinon ``tarif_base_ttc``). Le tarif appliqué ne change JAMAIS
    rétroactivement si ``GrilleTarifaire`` évolue ensuite."""
    from .models import ActeRealise
    from .selectors import tarif_applicable

    tarif = tarif_applicable(acte, getattr(patient, 'convention', None))

    return ActeRealise.objects.create(
        company=admission.company,
        admission=admission,
        patient=patient,
        praticien=praticien,
        acte=acte,
        date_realisation=date_realisation,
        quantite=quantite,
        tarif_applique_ttc=tarif['tarif_ttc'],
        facturable=facturable,
    )


def reste_a_charge_total(acte_realise):
    """NTSAN12 — vrai si cet acte doit basculer en reste-à-charge patient
    total : sa prise en charge (si posée) est refusée, expirée, ou dont la
    ``date_expiration`` est dépassée."""
    from datetime import date as _date

    pec = acte_realise.prise_en_charge
    if pec is None:
        return False
    from .models import PriseEnCharge
    if pec.statut in (PriseEnCharge.Statut.REFUSEE, PriseEnCharge.Statut.EXPIREE):
        return True
    if pec.date_expiration and pec.date_expiration < _date.today():
        return True
    return False


def _dec(value):
    """NTSAN13 — coerce un champ monétaire en ``Decimal``. Django ne convertit
    PAS une valeur assignée en mémoire avant un reload DB : une instance
    fraîchement créée (ou un montant passé en chaîne) peut porter une ``str``.
    Un service de calcul monétaire doit rester robuste à ce cas."""
    from decimal import Decimal
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _split_ligne(acte_realise):
    """NTSAN13 — split tiers payant/patient d'UNE ligne (``ActeRealise``).

    Ordre de résolution :
    1. Reste-à-charge total forcé (prise en charge refusée/expirée) →
       patient 100 %.
    2. ``PriseEnCharge.montant_accorde`` posé → plafonne la part tiers
       payant au montant accordé (restant de la ligne à charge du patient).
    3. ``GrilleTarifaire.taux_prise_charge_pct`` de la convention du
       patient pour cet acte → split proportionnel.
    4. Sinon → patient 100 % (aucune couverture connue).
    """
    from decimal import Decimal

    ligne_ttc = _dec(acte_realise.tarif_applique_ttc) * acte_realise.quantite

    if reste_a_charge_total(acte_realise):
        return Decimal('0'), ligne_ttc

    pec = acte_realise.prise_en_charge
    if pec is not None and pec.montant_accorde is not None:
        tiers = min(_dec(pec.montant_accorde), ligne_ttc)
        return tiers, ligne_ttc - tiers

    from .models import GrilleTarifaire

    convention = getattr(acte_realise.patient, 'convention', None)
    if convention is not None:
        grille = GrilleTarifaire.objects.filter(
            company=acte_realise.company, convention=convention,
            acte_id=acte_realise.acte_id).first()
        if grille is not None and grille.taux_prise_charge_pct:
            tiers = (
                ligne_ttc * _dec(grille.taux_prise_charge_pct)
                / Decimal('100')).quantize(Decimal('0.01'))
            return tiers, ligne_ttc - tiers

    return Decimal('0'), ligne_ttc


def calculer_split_facture_sante(actes_realises):
    """NTSAN13 — somme le split tiers payant/patient sur un ensemble de
    lignes (``ActeRealise``). Renvoie ``(sous_total_ttc, part_tiers_payant,
    part_patient)``. Invariant testé : ``part_tiers_payant + part_patient ==
    sous_total_ttc`` (aucune remise appliquée ici — la remise, si posée,
    s'applique ensuite au niveau facture et réduit la part patient)."""
    from decimal import Decimal

    sous_total = Decimal('0')
    part_tiers_payant = Decimal('0')
    part_patient = Decimal('0')
    for acte_realise in actes_realises:
        tiers, patient_part = _split_ligne(acte_realise)
        sous_total += _dec(acte_realise.tarif_applique_ttc) * acte_realise.quantite
        part_tiers_payant += tiers
        part_patient += patient_part
    return sous_total, part_tiers_payant, part_patient


def creer_facture_sante(
        *, admission, actes_realises, convention=None, remise_ttc=None):
    """NTSAN13 — crée une ``FactureSante`` à partir d'un ensemble d'
    ``ActeRealise`` réalisés pour cette admission, rattache chaque ligne
    (``ActeRealise.facture_sante``). Une remise TTC (optionnelle) réduit la
    part patient (jamais la part tiers payant, déjà contractuelle)."""
    from decimal import Decimal

    from .models import FactureSante

    remise = remise_ttc or Decimal('0')
    sous_total, part_tiers_payant, part_patient = calculer_split_facture_sante(
        actes_realises)
    part_patient -= remise
    total_ttc = sous_total - remise

    facture = FactureSante.objects.create(
        company=admission.company,
        patient=admission.patient,
        admission=admission,
        convention=convention,
        sous_total_ttc=sous_total,
        remise_ttc=remise,
        total_ttc=total_ttc,
        part_tiers_payant_ttc=part_tiers_payant,
        part_patient_ttc=part_patient,
        statut=FactureSante.Statut.EMISE,
    )
    for acte_realise in actes_realises:
        acte_realise.facture_sante = facture
        acte_realise.save(update_fields=['facture_sante'])
    return facture


def montant_du(facture_sante):
    """NTSAN15 — ``montant_du = total_ttc - somme(paiements)``, jamais
    négatif sans un flag d'avoir explicite : un trop-perçu est plafonné à 0
    ici (un avoir est un document distinct, hors périmètre de ce lot)."""
    from decimal import Decimal

    from django.db.models import Sum

    total_paye = facture_sante.paiements.aggregate(
        total=Sum('montant'))['total'] or Decimal('0')
    reste = facture_sante.total_ttc - total_paye
    return max(reste, Decimal('0'))


def enregistrer_paiement(
        *, facture_sante, montant, mode, date_paiement, encaisse_par=None):
    """NTSAN15 — enregistre un paiement partiel ou total sur une facture
    santé, met à jour son statut (payee/payee_partiel) selon le reste dû."""
    from .models import FactureSante, PaiementSante

    paiement = PaiementSante.objects.create(
        company=facture_sante.company,
        facture_sante=facture_sante,
        montant=montant,
        mode=mode,
        date_paiement=date_paiement,
        encaisse_par=encaisse_par,
    )

    reste = montant_du(facture_sante)
    if reste <= 0:
        facture_sante.statut = FactureSante.Statut.PAYEE
    else:
        facture_sante.statut = FactureSante.Statut.PAYEE_PARTIEL
    facture_sante.save(update_fields=['statut'])
    return paiement


def annuler_rendez_vous(rendez_vous, *, annule_par, date_annulation=None):
    """NTSAN37 — annule un ``RendezVous`` (statut → ``annule``), pose
    ``annule_par``/``date_annulation`` et calcule le délai d'annulation
    (``RendezVous.delai_annulation_h``).

    Frais d'annulation tardive : le calcul du délai est TOUJOURS correct,
    mais la facturation d'une pénalité reste DÉSACTIVÉE tant que
    ``ParametragePenaliteAnnulation.actif`` n'est pas explicitement activé
    par la clinique (jamais activé par défaut — DECISION founder). Ce
    service ne crée AUCUNE ``FactureSante`` de pénalité (câblage de la
    facturation réelle hors périmètre de ce lot, décision distincte du
    founder) : il renvoie seulement ``penalite_applicable`` (bool), un
    indicateur que l'écran peut afficher.

    Renvoie ``(rendez_vous, penalite_applicable)``."""
    from django.utils import timezone

    from .models import ParametragePenaliteAnnulation, RendezVous

    date_annulation = date_annulation or timezone.now()
    rendez_vous.statut = RendezVous.Statut.ANNULE
    rendez_vous.annule_par = annule_par
    rendez_vous.date_annulation = date_annulation
    rendez_vous.save(
        update_fields=['statut', 'annule_par', 'date_annulation'])

    penalite_applicable = False
    parametrage = ParametragePenaliteAnnulation.objects.filter(
        company=rendez_vous.company).first()
    if parametrage is not None and parametrage.actif:
        delai_h = rendez_vous.delai_annulation_h
        if delai_h is not None and delai_h < parametrage.delai_min_h:
            penalite_applicable = True

    return rendez_vous, penalite_applicable


def verifier_prise_en_charge(prise_en_charge, *, user=None):
    """NTSAN12 — à appeler quand une `PriseEnCharge` bascule refusee/expiree :
    journalise (chatter + audit, `records.Activity` via `apps.audit.
    recorder.record_field_change`) le basculement en reste-à-charge patient
    total de chaque `ActeRealise` rattaché. Ne modifie AUCUN champ de
    l'acte : le calcul réel du reste-à-charge se fait au moment de la
    facturation (NTSAN13, via `reste_a_charge_total`) — ceci ne fait que
    tracer l'événement, une seule fois par acte concerné."""
    if prise_en_charge.statut not in (
            prise_en_charge.Statut.REFUSEE, prise_en_charge.Statut.EXPIREE):
        return []

    from apps.audit import recorder

    touches = []
    for acte_realise in prise_en_charge.actes_realises.all():
        recorder.record_field_change(
            acte_realise, 'prise_en_charge', 'accordee',
            prise_en_charge.get_statut_display(),
            user=user, field_label='Prise en charge',
            detail=(
                f'Prise en charge {prise_en_charge.get_statut_display().lower()} '
                '— acte basculé en reste-à-charge patient total.'),
        )
        touches.append(acte_realise)
    return touches
