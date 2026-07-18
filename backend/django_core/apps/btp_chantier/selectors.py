"""Sélecteurs LECTURE SEULE du vertical BTP/EPC (Groupe NTCON).

Les lectures cross-app (chantier ↔ projets, situations, sous-traitance,
retenue de garantie…) passent par ``django.apps.apps.get_model`` — jamais un
import statique de modèle d'une autre app (pattern déjà utilisé par
``installations/selectors.py`` et ``paie/services.py`` pour les lectures
cross-app sans arête d'import ; JAMAIS pour une écriture).
"""
from __future__ import annotations

from django.utils import timezone

from .models import RFI, ReserveChantier


# ── NTCON1 — Réserves de chantier ───────────────────────────────────────────

def reserves_filtrees(qs, *, lot=None, statut=None, gravite=None, chantier_id=None):
    """Applique les filtres optionnels ``?lot=&statut=&gravite=&chantier=``.

    ``qs`` est déjà scopé société par l'appelant (``TenantMixin``). Lecture
    seule, ne modifie jamais le queryset d'origine.
    """
    if lot not in (None, ''):
        qs = qs.filter(lot__icontains=lot)
    if statut not in (None, ''):
        qs = qs.filter(statut=statut)
    if gravite not in (None, ''):
        qs = qs.filter(gravite=gravite)
    if chantier_id not in (None, ''):
        qs = qs.filter(chantier_id=chantier_id)
    return qs


def reserves_actives_bloquantes(company, chantier=None):
    """``ReserveChantier`` ouvertes/en cours de gravité bloquante (lecture)."""
    qs = ReserveChantier.objects.filter(
        company=company,
        gravite=ReserveChantier.Gravite.BLOQUANTE,
        statut__in=[ReserveChantier.Statut.OUVERTE, ReserveChantier.Statut.EN_COURS],
    )
    if chantier is not None:
        qs = qs.filter(chantier=chantier)
    return qs


# ── NTCON3 — RFI ─────────────────────────────────────────────────────────────

def rfi_filtres(qs, *, chantier_id=None, statut=None):
    """Filtres optionnels ``?chantier=&statut=`` (queryset déjà scopé société).

    L'ordre par défaut (``RFI.Meta.ordering``) trie déjà par
    ``date_limite_reponse`` ascendant — un RFI en retard (échéance passée)
    apparaît donc TOUJOURS avant un RFI encore dans les temps.
    """
    if chantier_id not in (None, ''):
        qs = qs.filter(chantier_id=chantier_id)
    if statut not in (None, ''):
        qs = qs.filter(statut=statut)
    return qs


def rfi_en_retard(company=None, *, chantier=None):
    """``RFI`` ouverts dont l'échéance de réponse est dépassée (lecture).

    ``company=None`` (défaut) balaie TOUTES les sociétés — usage sweep
    Celery beat (``alertes_rfi_retard``, NTCON4) ; un appelant scopé société
    (vue/API) passe explicitement sa société.
    """
    qs = RFI.objects.filter(
        statut=RFI.Statut.OUVERT,
        date_limite_reponse__lt=timezone.localdate())
    if company is not None:
        qs = qs.filter(company=company)
    if chantier is not None:
        qs = qs.filter(chantier=chantier)
    return qs


# ── NTCON9/NTCON10 — DGD (Décompte Général et Définitif) ───────────────────

def calculer_dgd(dgd):
    """NTCON9 — recalcule (LECTURE SEULE, ne sauvegarde RIEN) les totaux d'un
    ``DecompteGeneral`` : ``total_avenants_ht`` (avenants NTCON7 approuvés du
    chantier), ``total_situations_facturees_ht`` (agrégé depuis les
    ``gestion_projet.LigneSituation.montant_periode`` des situations
    ``situations_incluses``, LECTURE cross-app via ``django.apps.apps.
    get_model`` — jamais une écriture), ``retenue_garantie_montant``
    (instantané lu depuis ``compta.RetenueGarantie`` si non déjà figé) et
    ``solde_du_ht``. Renvoie un ``dict`` ; l'appelant décide de persister
    (voir ``services.recalculer_et_enregistrer_dgd``) ou non (aperçu).
    """
    from decimal import Decimal

    from django.apps import apps as django_apps
    from django.db.models import Sum

    from .models import AvenantChantier

    total_avenants = AvenantChantier.objects.filter(
        chantier=dgd.chantier, statut=AvenantChantier.Statut.APPROUVE,
    ).aggregate(total=Sum('montant_ht'))['total'] or Decimal('0')

    total_situations = Decimal('0')
    situation_ids = list(dgd.situations_incluses or [])
    if situation_ids:
        try:
            LigneSituation = django_apps.get_model(
                'gestion_projet', 'LigneSituation')
            total_situations = LigneSituation.objects.filter(
                situation_id__in=situation_ids,
            ).aggregate(total=Sum('montant_periode'))['total'] or Decimal('0')
        except LookupError:  # pragma: no cover - gestion_projet non installé
            total_situations = Decimal('0')

    rg_montant = dgd.retenue_garantie_montant or Decimal('0')
    if dgd.retenue_garantie_id and not dgd.retenue_garantie_montant:
        try:
            RetenueGarantie = django_apps.get_model(
                'compta', 'RetenueGarantie')
            rg = RetenueGarantie.objects.filter(
                pk=dgd.retenue_garantie_id).first()
            if rg is not None:
                rg_montant = rg.montant or Decimal('0')
        except LookupError:  # pragma: no cover - compta non installé
            pass

    solde = (
        (dgd.montant_marche_initial_ht or Decimal('0')) + total_avenants
        - total_situations + rg_montant)
    return {
        'total_avenants_ht': total_avenants,
        'total_situations_facturees_ht': total_situations,
        'retenue_garantie_montant': rg_montant,
        'solde_du_ht': solde,
    }


def recalculer_et_enregistrer_dgd(dgd):
    """NTCON9 — recalcule (``calculer_dgd``) ET persiste les totaux."""
    totaux = calculer_dgd(dgd)
    dgd.total_avenants_ht = totaux['total_avenants_ht']
    dgd.total_situations_facturees_ht = totaux['total_situations_facturees_ht']
    dgd.retenue_garantie_montant = totaux['retenue_garantie_montant']
    dgd.solde_du_ht = totaux['solde_du_ht']
    dgd.save(update_fields=[
        'total_avenants_ht', 'total_situations_facturees_ht',
        'retenue_garantie_montant', 'solde_du_ht'])
    return dgd


# ── NTCON11 — Comparatif déboursé sec vs facturé par chantier ──────────────

def debourse_sec_vs_facture(chantier):
    """NTCON11 — comparatif déboursé sec (coûts RÉELS engagés) vs facturé,
    EN COURS de chantier (pas seulement en fin, contrairement au P&L global
    FG295). Admin/responsable only (gardé côté vue) — JAMAIS un coût dans
    une sortie client.

    Déboursé sec :
    * main-d'œuvre — ``gestion_projet.Timesheet.cout`` (facturable, statut
      approuvée), agrégée sur les projets rattachés au chantier via
      ``gestion_projet.ProjetChantier`` (LECTURE cross-app, ``apps.
      get_model`` — jamais une écriture) ;
    * sous-traitance — ``installations.OrdreSousTraitance.montant_realise``
      (ou ``montant`` si non réceptionné), via la relation RÉELLE déjà
      déclarée sur ``chantier`` (``installations_ordres_sous_traitance`` —
      MÊME app que le FK ``chantier``, aucun import) ;
    * matériel — ``installations.StockReservation`` CONSOMMÉE × ``stock.
      Produit.prix_achat`` (GENERATOR-ONLY, jamais client-facing — CLAUDE.md),
      via la relation RÉELLE ``chantier.reservations``.

    Facturé : situations facturées (XPRJ4, ``gestion_projet.LigneSituation.
    montant_periode`` des situations ``statut=facturee`` du/des projet(s) du
    chantier) + avenants NTCON7 approuvés.
    """
    from decimal import Decimal

    from django.apps import apps as django_apps
    from django.db.models import Sum

    from .models import AvenantChantier

    # ── Main-d'œuvre (lecture cross-app) ────────────────────────────────
    main_oeuvre = Decimal('0')
    projet_ids = []
    try:
        ProjetChantier = django_apps.get_model('gestion_projet', 'ProjetChantier')
        Timesheet = django_apps.get_model('gestion_projet', 'Timesheet')
        projet_ids = list(ProjetChantier.objects.filter(
            chantier_id=chantier.pk).values_list('projet_id', flat=True))
        if projet_ids:
            main_oeuvre = Timesheet.objects.filter(
                projet_id__in=projet_ids, facturable=True,
                statut='approuvee',
            ).aggregate(total=Sum('cout'))['total'] or Decimal('0')
    except LookupError:  # pragma: no cover - gestion_projet non installé
        pass

    # ── Sous-traitance (relation RÉELLE, même app) ──────────────────────
    sous_traitance = Decimal('0')
    for ordre in chantier.installations_ordres_sous_traitance.all():
        sous_traitance += (
            ordre.montant_realise if ordre.montant_realise is not None
            else ordre.montant)

    # ── Matériel (relation RÉELLE, même app) ────────────────────────────
    materiel = Decimal('0')
    for resa in chantier.reservations.filter(
            consomme=True).select_related('produit'):
        prix = getattr(resa.produit, 'prix_achat', None) or Decimal('0')
        materiel += Decimal(resa.quantite) * Decimal(prix)

    debourse_total = main_oeuvre + sous_traitance + materiel

    # ── Facturé ──────────────────────────────────────────────────────────
    total_situations = Decimal('0')
    try:
        SituationTravaux = django_apps.get_model(
            'gestion_projet', 'SituationTravaux')
        LigneSituation = django_apps.get_model(
            'gestion_projet', 'LigneSituation')
        if projet_ids:
            situation_ids = SituationTravaux.objects.filter(
                projet_id__in=projet_ids, statut='facturee',
            ).values_list('id', flat=True)
            total_situations = LigneSituation.objects.filter(
                situation_id__in=list(situation_ids),
            ).aggregate(total=Sum('montant_periode'))['total'] or Decimal('0')
    except LookupError:  # pragma: no cover - gestion_projet non installé
        pass

    total_avenants = AvenantChantier.objects.filter(
        chantier=chantier, statut=AvenantChantier.Statut.APPROUVE,
    ).aggregate(total=Sum('montant_ht'))['total'] or Decimal('0')

    facture_total = total_situations + total_avenants

    return {
        'main_oeuvre': main_oeuvre,
        'sous_traitance': sous_traitance,
        'materiel': materiel,
        'debourse_sec_total': debourse_total,
        'situations_facturees': total_situations,
        'avenants_approuves': total_avenants,
        'facture_total': facture_total,
        'marge': facture_total - debourse_total,
    }


# ── NTCON13 — Alerte plan périmé consulté ───────────────────────────────────

def plans_perimes_sur_chantier(chantier):
    """NTCON13 — détecte, pour ce chantier, tout accusé de réception NTCON12
    marqué « lu » sur une version de plan qui n'est PLUS la DERNIÈRE diffusée
    pour ce même document GED — badge « plan potentiellement obsolète
    consulté » (comparaison best-effort, tracée via ``DiffusionPlan.
    accuse_reception``)."""
    from .models import DiffusionPlan

    diffusions = list(DiffusionPlan.objects.filter(chantier=chantier))
    derniere_version_par_doc = {}
    for d in diffusions:
        courante = derniere_version_par_doc.get(d.document_ged_id, 0)
        if d.version_diffusee > courante:
            derniere_version_par_doc[d.document_ged_id] = d.version_diffusee

    alertes = []
    for d in diffusions:
        derniere = derniere_version_par_doc.get(
            d.document_ged_id, d.version_diffusee)
        if d.version_diffusee >= derniere:
            continue
        for cle, info in (d.accuse_reception or {}).items():
            if info.get('lu'):
                alertes.append({
                    'document_ged_id': d.document_ged_id,
                    'destinataire': cle,
                    'version_consultee': d.version_diffusee,
                    'derniere_version': derniere,
                    'horodatage': info.get('horodatage'),
                })
    return alertes
