"""Sélecteurs LECTURE SEULE du vertical BTP/EPC (Groupe NTCON).

Les lectures cross-app (chantier ↔ projets, situations, sous-traitance,
retenue de garantie…) passent par ``django.apps.apps.get_model`` — jamais un
import statique de modèle d'une autre app (pattern déjà utilisé par
``installations/selectors.py`` et ``paie/services.py`` pour les lectures
cross-app sans arête d'import ; JAMAIS pour une écriture).
"""
from __future__ import annotations

from django.utils import timezone

from .models import RFI, Lot, ReserveChantier


# ── NTCON1 — Réserves de chantier ───────────────────────────────────────────

#: NTCON27 — valeurs de ``?archivee=`` interprétées comme « oui ».
_VRAI = frozenset({'1', 'true', 'True', 'oui', 'yes', 'on'})
#: …et comme « non » (permet de redemander explicitement les actives).
_FAUX = frozenset({'0', 'false', 'False', 'non', 'no', 'off'})


def reserves_filtrees(qs, *, lot=None, statut=None, gravite=None,
                      chantier_id=None, archivee=None):
    """Applique les filtres optionnels ``?lot=&statut=&gravite=&chantier=``
    (+ ``?archivee=`` — NTCON27).

    ``qs`` est déjà scopé société par l'appelant (``TenantMixin``). Lecture
    seule, ne modifie jamais le queryset d'origine.

    NTCON27 — les réserves ARCHIVÉES sortent des listes par défaut (``archivee``
    absent ⇒ ``archivee=False``). Elles restent atteignables par un filtre
    EXPLICITE ``?archivee=1`` (ou ``?archivee=all`` pour les deux) : rien n'est
    supprimé, tout reste consultable.
    """
    if lot not in (None, ''):
        qs = qs.filter(lot__icontains=lot)
    if statut not in (None, ''):
        qs = qs.filter(statut=statut)
    if gravite not in (None, ''):
        qs = qs.filter(gravite=gravite)
    if chantier_id not in (None, ''):
        qs = qs.filter(chantier_id=chantier_id)
    if archivee in (None, ''):
        qs = qs.filter(archivee=False)
    elif isinstance(archivee, bool):
        qs = qs.filter(archivee=archivee)
    elif str(archivee) in _VRAI:
        qs = qs.filter(archivee=True)
    elif str(archivee) in _FAUX:
        qs = qs.filter(archivee=False)
    # Toute autre valeur (``all``, ``toutes``…) = aucun filtre : les deux.
    return qs


def _q_levee_avant(seuil):
    """``date_levee < seuil`` OU (``date_levee`` absente ET ``updated_at``
    < seuil) — facteur commun de ``reserves_archivables``."""
    from django.db.models import Q
    return (Q(date_levee__lt=seuil)
            | Q(date_levee__isnull=True, updated_at__lt=seuil))


def reserves_archivables(company=None, *, maintenant=None):
    """NTCON27 — réserves LEVÉES dont l'ancienneté dépasse le réglage société.

    Le seuil est lu par société (``ParametresBtpChantier.
    delai_archivage_reserves_levees_mois``, défaut 24 via
    ``services.config_btp``) : la fonction renvoie un dictionnaire
    ``{company_id: queryset}`` plutôt qu'un seul queryset, parce que deux
    sociétés peuvent avoir deux seuils différents et qu'un seuil global serait
    faux pour l'une des deux.

    L'ancienneté est comptée depuis ``date_levee`` quand elle existe (la date
    de la preuve), sinon depuis ``updated_at`` — une réserve marquée levée sans
    passer par le service n'échappe pas au balayage.
    """
    from datetime import timedelta

    from .services import config_btp

    maintenant = maintenant or timezone.now()
    base = ReserveChantier.objects.filter(
        statut=ReserveChantier.Statut.LEVEE, archivee=False)
    if company is not None:
        base = base.filter(company=company)
        companies = [company]
    else:
        Company = ReserveChantier._meta.get_field('company').related_model
        companies = list(
            Company.objects.filter(
                pk__in=base.values_list('company_id', flat=True).distinct()))

    resultat = {}
    for societe in companies:
        mois = config_btp(societe).get(
            'delai_archivage_reserves_levees_mois') or 24
        # 1 mois ≈ 30 jours : la règle est une politique de rétention, pas un
        # calcul comptable — inutile d'introduire une dépendance calendaire.
        seuil = maintenant - timedelta(days=30 * int(mois))
        resultat[societe.pk] = base.filter(company=societe).filter(
            _q_levee_avant(seuil))
    return resultat


# ── NTCON30 — export CSV/XLSX pour reporting externe MOE/client ────────────

#: En-têtes de l'export des réserves. AUCUN coût interne : ni ``prix_achat``,
#: ni déboursé, ni exposition aux pénalités — un MOE/client lit ce fichier.
COLONNES_EXPORT_RESERVES = (
    'Numéro', 'Chantier', 'Lot', 'Description', 'Gravité', 'Statut',
    'Responsable', 'Date limite', 'Date de levée',
)

#: En-têtes de l'export des RFI (« priorité » = impact déclaré du RFI).
COLONNES_EXPORT_RFI = (
    'Numéro', 'Chantier', 'Question', 'Priorité', 'Statut', 'Destinataire',
    'Date limite de réponse', 'Date de réponse',
)


def _nom_utilisateur(user):
    """Nom affichable d'un utilisateur, ou chaîne vide."""
    if user is None:
        return ''
    complet = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    return complet or getattr(user, 'username', '') or ''


def _priorite_rfi(rfi):
    """« Priorité » lisible d'un RFI, DÉRIVÉE de ses impacts déclarés.

    Le modèle NTCON3 ne porte pas de champ ``priorite`` : l'inventer côté
    export serait un chiffre sorti de nulle part. On dérive donc un libellé
    des DEUX impacts que le RFI déclare déjà (coût, délai) — et « Normale »
    quand il n'en déclare aucun.
    """
    marques = []
    if rfi.impact_cout:
        marques.append('coût')
    if rfi.impact_delai_jours:
        marques.append(f'délai {rfi.impact_delai_jours} j')
    return f"Impact {' + '.join(marques)}" if marques else 'Normale'


def export_reserves(qs):
    """NTCON30 — ``(en-têtes, lignes)`` de l'export des réserves.

    ``qs`` est DÉJÀ scopé société + filtré par l'appelant. Lecture seule.
    """
    lignes = []
    for reserve in qs.select_related(
            'chantier', 'responsable_leve').order_by('id'):
        lignes.append([
            reserve.pk,
            str(reserve.chantier) if reserve.chantier_id else '',
            reserve.lot or '',
            reserve.description or '',
            reserve.get_gravite_display(),
            reserve.get_statut_display(),
            _nom_utilisateur(reserve.responsable_leve),
            reserve.date_limite.isoformat() if reserve.date_limite else '',
            (reserve.date_levee.date().isoformat()
             if reserve.date_levee else ''),
        ])
    return list(COLONNES_EXPORT_RESERVES), lignes


def export_rfi(qs):
    """NTCON30 — ``(en-têtes, lignes)`` de l'export des RFI (lecture seule)."""
    lignes = []
    for rfi in qs.select_related(
            'chantier', 'destinataire_user').prefetch_related(
                'reponses').order_by('numero', 'id'):
        premiere = min(
            (r.date_creation for r in rfi.reponses.all()), default=None)
        destinataire = (_nom_utilisateur(rfi.destinataire_user)
                        or rfi.destinataire_texte or '')
        lignes.append([
            rfi.numero,
            str(rfi.chantier) if rfi.chantier_id else '',
            rfi.question or '',
            _priorite_rfi(rfi),
            rfi.get_statut_display(),
            destinataire,
            (rfi.date_limite_reponse.isoformat()
             if rfi.date_limite_reponse else ''),
            premiere.date().isoformat() if premiere else '',
        ])
    return list(COLONNES_EXPORT_RFI), lignes


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

def situations_incluses_hors_societe(situation_ids, company):
    """AUD310 — parmi ``situation_ids`` (IDs de ``gestion_projet.
    SituationTravaux``, tels qu'écrits dans ``DecompteGeneral.
    situations_incluses``), renvoie le sous-ensemble qui N'APPARTIENT PAS à
    ``company`` (ID inconnu OU appartenant à une autre société). Une liste
    vide signifie « tout est valide ». LECTURE cross-app via ``django.apps.
    apps.get_model`` — jamais un import statique, jamais une écriture.
    Utilisé par ``DecompteGeneralSerializer.validate_situations_incluses``
    pour refuser (400) une référence cross-société AVANT écriture.
    """
    from django.apps import apps as django_apps

    situation_ids = list(situation_ids or [])
    if not situation_ids:
        return []
    try:
        SituationTravaux = django_apps.get_model(
            'gestion_projet', 'SituationTravaux')
    except LookupError:  # pragma: no cover - gestion_projet non installé
        return list(situation_ids)
    ids_de_la_societe = set(
        SituationTravaux.objects.filter(
            id__in=situation_ids, company=company,
        ).values_list('id', flat=True))
    return [sid for sid in situation_ids if sid not in ids_de_la_societe]


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
            # AUD310 — défense en profondeur : même si ``situations_incluses``
            # a été écrit sans passer par ``validate_situations_incluses``
            # (données déjà corrompues, écriture directe...), l'agrégat ne
            # doit JAMAIS sommer une ligne d'une autre société sur ce
            # document contractuel de clôture de chantier.
            total_situations = LigneSituation.objects.filter(
                situation_id__in=situation_ids,
                situation__projet__company=dgd.company,
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
    * matériel — ``installations.StockReservation`` CONSOMMÉE × coût unitaire
      DÉBARQUÉ (AUD327 : FOB + quote-part frais d'import — fret/douane/TVA
      import/transit — via ``installations.selectors.landed_cost_dossier``)
      quand le produit réservé trace vers un ``DossierImport`` (dernière
      ``LandedCostLigne`` connue pour ce produit) ; repli sur ``stock.
      Produit.prix_achat`` FOB brut sinon (GENERATOR-ONLY, jamais
      client-facing — CLAUDE.md), via la relation RÉELLE
      ``chantier.reservations``. Câblage DC38 complet (écriture dans le coût
      moyen pondéré stock) reste hors scope — lecture seule, aucune écriture
      ``stock`` (``installations/models_landed_cost.py:14-18``).

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
    # AUD327 — préfère le coût unitaire DÉBARQUÉ (FOB + quote-part frais
    # d'import) quand le produit réservé trace vers un ``DossierImport``
    # (via sa dernière ``LandedCostLigne`` connue), au lieu du ``prix_achat``
    # FOB brut qui sous-évalue silencieusement le comparatif. Lecture cross-
    # app par le SELECTEUR de la cible (``installations.selectors``,
    # jamais son ``models``/``views``) — comme le reste de cette fonction.
    from apps.installations import selectors as installations_selectors

    LandedCostLigne = django_apps.get_model('installations', 'LandedCostLigne')
    landed_par_dossier = {}  # dossier_id -> {ligne_id: cout_debarque_unitaire}

    materiel = Decimal('0')
    for resa in chantier.reservations.filter(
            consomme=True).select_related('produit'):
        cout_unitaire = None
        derniere_ligne = (
            LandedCostLigne.objects
            .filter(company=chantier.company, produit_id=resa.produit_id)
            .select_related('dossier')
            .order_by('-date_creation', '-id')
            .first()
        )
        if derniere_ligne is not None:
            dossier_id = derniere_ligne.dossier_id
            if dossier_id not in landed_par_dossier:
                landed = installations_selectors.landed_cost_dossier(
                    derniere_ligne.dossier)
                landed_par_dossier[dossier_id] = {
                    ln['ligne_id']: Decimal(str(ln['cout_debarque_unitaire']))
                    for ln in landed['lignes']
                }
            cout_unitaire = landed_par_dossier[dossier_id].get(derniere_ligne.id)
        if cout_unitaire is None:
            cout_unitaire = (
                getattr(resa.produit, 'prix_achat', None) or Decimal('0'))
        materiel += Decimal(resa.quantite) * Decimal(cout_unitaire)

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


# ── NTCON14 — Planning TCE multi-lots ───────────────────────────────────────

# Palette de repli du Gantt groupé par lot : utilisée SEULEMENT quand le lot
# n'a pas de ``couleur`` choisie (jamais une couleur inventée écrite en base).
PALETTE_LOTS = [
    '#2563EB', '#16A34A', '#D97706', '#DC2626', '#7C3AED',
    '#0891B2', '#DB2777', '#65A30D',
]


def couleur_lot(lot, rang=0):
    """Couleur d'affichage d'un lot : celle choisie, sinon un repli stable de
    ``PALETTE_LOTS`` indexé par le rang du lot dans son chantier."""
    return lot.couleur or PALETTE_LOTS[rang % len(PALETTE_LOTS)]


def lots_filtres(qs, *, chantier_id=None, statut=None, jalon=None):
    """Filtres optionnels ``?chantier=&statut=&jalon=`` (queryset déjà scopé
    société par ``TenantMixin``). Lecture seule."""
    if chantier_id not in (None, ''):
        qs = qs.filter(chantier_id=chantier_id)
    if statut not in (None, ''):
        qs = qs.filter(statut=statut)
    if jalon not in (None, ''):
        qs = qs.filter(jalon_contractuel=str(jalon).lower() in ('1', 'true', 'vrai'))
    return qs


def planning_par_lot(chantier):
    """NTCON14 — planning Gantt d'un chantier GROUPÉ PAR LOT, avec code
    couleur. Lecture seule, aucune écriture.

    Les tâches proviennent de ``gestion_projet.Tache`` via la table de liaison
    LOCALE ``LotTache`` (relation déclarée par CHAÎNE dans ``models.py`` — aucun
    import de ``gestion_projet.models``). Un lot sans tâche rattachée renvoie
    simplement une liste vide : le Gantt affiche alors la barre du lot seule
    (ses dates prévues).

    Chaque lot porte ``avancement_pct`` (moyenne simple des
    ``Tache.avancement_pct`` rattachées, 0 sans tâche) et ``en_retard``
    (fin prévue dépassée, lot non terminé).
    """
    aujourdhui = timezone.localdate()
    lots = list(
        Lot.objects.filter(chantier=chantier)
        .select_related('sous_traitant')
        .prefetch_related('taches')
        .order_by('ordre', 'id'))
    resultat = []
    for rang, lot in enumerate(lots):
        taches = [{
            'id': t.id,
            'libelle': t.libelle,
            'statut': t.statut,
            'avancement_pct': t.avancement_pct,
            'date_debut_prevue': t.date_debut_prevue,
            'date_fin_prevue': t.date_fin_prevue,
        } for t in lot.taches.all().order_by('ordre', 'id')]
        avancement = (
            round(sum(t['avancement_pct'] for t in taches) / len(taches))
            if taches else 0)
        resultat.append({
            'id': lot.id,
            'nom': lot.nom,
            'ordre': lot.ordre,
            'couleur': couleur_lot(lot, rang),
            'statut': lot.statut,
            'jalon_contractuel': lot.jalon_contractuel,
            'interne': lot.interne,
            'sous_traitant_id': lot.sous_traitant_id,
            'sous_traitant_nom': (
                lot.sous_traitant.nom if lot.sous_traitant_id else ''),
            'date_debut_prevue': lot.date_debut_prevue,
            'date_fin_prevue': lot.date_fin_prevue,
            'date_fin_reelle': lot.date_fin_reelle,
            'avancement_pct': avancement,
            'en_retard': bool(
                lot.statut != Lot.Statut.TERMINE and lot.date_fin_prevue
                and lot.date_fin_prevue < aujourdhui),
            'taches': taches,
        })
    return resultat


# ── NTCON15 — Pénalités de retard PAR LOT ───────────────────────────────────

def penalites_retard_par_lot(chantier, date_reference=None):
    """NTCON15 — exposition aux pénalités de retard, LOT PAR LOT.

    Reprend EXACTEMENT la formule XPRJ27
    (``gestion_projet.selectors.penalites_retard``) ::

        jours_depassement × (taux / 1000) × montant

    plafonnée à ``plafond_penalite_pct`` % du montant quand ce plafond est
    renseigné — mais appliquée au ``Lot`` (NTCON14) et non au projet entier :
    chaque lot est calculé INDÉPENDAMMENT, un lot en retard n'alourdit jamais
    la pénalité d'un autre lot.

    Un lot n'est « applicable » que s'il porte un ``jalon_contractuel``, un
    ``taux_penalite_retard_pmil``, un ``montant_ht`` non nul et une
    ``date_fin_prevue`` — sinon exposition NULLE avec ``applicable=False``
    (jamais d'erreur : le sélecteur reste appelable sur n'importe quel
    chantier). Le retard d'un lot TERMINÉ est FIGÉ à sa ``date_fin_reelle``
    (il ne continue pas de courir) ; un lot en cours court jusqu'à
    ``date_reference`` (défaut : aujourd'hui).

    Donnée INTERNE de pilotage — jamais dans un document client. Lecture
    seule : rien n'est écrit, rien n'est figé (le décompte DÉFINITIF reste à
    établir à la réception du lot).
    """
    from decimal import Decimal

    if date_reference is None:
        date_reference = timezone.localdate()

    lots = Lot.objects.filter(chantier=chantier).order_by('ordre', 'id')
    resultats = []
    total = Decimal('0')
    for lot in lots:
        montant = lot.montant_ht or Decimal('0')
        applicable = bool(
            lot.jalon_contractuel
            and lot.taux_penalite_retard_pmil is not None
            and montant
            and lot.date_fin_prevue is not None
        )
        if not applicable:
            resultats.append({
                'lot_id': lot.id,
                'lot': lot.nom,
                'applicable': False,
                'jours_depassement': 0,
                'taux_penalite_retard_pmil': lot.taux_penalite_retard_pmil,
                'montant_ht': montant,
                'plafond_penalite_pct': lot.plafond_penalite_pct,
                'exposition_brute': Decimal('0'),
                'plafond_montant': None,
                'exposition': Decimal('0'),
                'plafonnee': False,
                'decompte_definitif_a_etablir': False,
            })
            continue

        # Le retard d'un lot TERMINÉ est figé à sa fin réelle.
        fin_constatee = date_reference
        if lot.statut == Lot.Statut.TERMINE and lot.date_fin_reelle:
            fin_constatee = lot.date_fin_reelle
        jours = max((fin_constatee - lot.date_fin_prevue).days, 0)

        taux = lot.taux_penalite_retard_pmil
        brute = (
            Decimal(jours) * (taux / Decimal('1000')) * montant
        ).quantize(Decimal('0.01'))

        plafond_montant = None
        exposition = brute
        plafonnee = False
        if lot.plafond_penalite_pct is not None:
            plafond_montant = (
                montant * lot.plafond_penalite_pct / Decimal('100')
            ).quantize(Decimal('0.01'))
            if brute > plafond_montant:
                exposition = plafond_montant
                plafonnee = True

        total += exposition
        resultats.append({
            'lot_id': lot.id,
            'lot': lot.nom,
            'applicable': True,
            'jours_depassement': jours,
            'taux_penalite_retard_pmil': taux,
            'montant_ht': montant,
            'plafond_penalite_pct': lot.plafond_penalite_pct,
            'exposition_brute': brute,
            'plafond_montant': plafond_montant,
            'exposition': exposition,
            'plafonnee': plafonnee,
            'decompte_definitif_a_etablir': jours > 0,
        })

    return {
        'chantier_id': chantier.pk,
        'date_reference': date_reference,
        'lots': resultats,
        'total_exposition': total,
    }


def kpis_btp(company):
    """NTCON34 — les quatre KPI BTP du reporting transverse, en UN appel.

    Chaque valeur réutilise un sélecteur EXISTANT du module — aucune seconde
    formule :

    * ``btp_reserves_ouvertes``      — réserves actives (ouverte/en cours/
      contestée) non archivées (NTCON1/2/27) ;
    * ``btp_rfi_en_retard``          — ``rfi_en_retard`` (NTCON3/4) ;
    * ``btp_visas_en_attente``       — visas soumis ou en revue (NTCON5) ;
    * ``btp_penalites_cumulees_periode`` — Σ des expositions par lot
      (``penalites_retard_par_lot``, NTCON15) sur les chantiers de la société.

    ``None`` plutôt que ``0`` quand la société n'a AUCUN objet de ce type :
    un 0 affirmerait « rien en retard » là où la vraie réponse est « ce module
    n'est pas utilisé ici » (règle : jamais un chiffre trompeur).
    """
    from decimal import Decimal

    from .models import VisaDocument

    reserves_qs = ReserveChantier.objects.filter(company=company)
    rfi_qs = RFI.objects.filter(company=company)
    visas_qs = VisaDocument.objects.filter(company=company)
    lots_qs = Lot.objects.filter(company=company)

    reserves_ouvertes = (
        reserves_qs.filter(
            archivee=False,
            statut__in=[ReserveChantier.Statut.OUVERTE,
                        ReserveChantier.Statut.EN_COURS,
                        ReserveChantier.Statut.CONTESTEE]).count()
        if reserves_qs.exists() else None)

    rfi_retard = (rfi_en_retard(company).count()
                  if rfi_qs.exists() else None)

    visas_attente = (
        visas_qs.filter(
            statut__in=[VisaDocument.Statut.SOUMIS,
                        VisaDocument.Statut.EN_REVUE]).count()
        if visas_qs.exists() else None)

    penalites = None
    if lots_qs.exists():
        penalites = Decimal('0')
        Chantier = Lot._meta.get_field('chantier').related_model
        ids = lots_qs.values_list('chantier_id', flat=True).distinct()
        for site in Chantier.objects.filter(pk__in=ids):
            penalites += penalites_retard_par_lot(site)['total_exposition']

    return {
        'btp_reserves_ouvertes': reserves_ouvertes,
        'btp_rfi_en_retard': rfi_retard,
        'btp_visas_en_attente': visas_attente,
        'btp_penalites_cumulees_periode': penalites,
    }


def chantiers_avec_lot_en_retard(company=None, *, date_reference=None):
    """NTCON28 — chantiers portant AU MOINS un lot en retard ACTIF.

    « En retard actif » = jalon contractuel, échéance ``date_fin_prevue``
    dépassée, lot NON terminé. C'est le seul périmètre que le balayage
    quotidien a besoin de recalculer : un chantier dont aucun lot n'a glissé
    a une exposition inchangée, la recalculer coûterait une requête pour rien.

    Renvoie un queryset de ``Lot`` (pas de chantiers) : l'appelant regroupe
    lui-même par ``chantier_id``.
    """
    date_reference = date_reference or timezone.localdate()
    qs = Lot.objects.filter(
        jalon_contractuel=True,
        date_fin_prevue__lt=date_reference,
    ).exclude(statut=Lot.Statut.TERMINE)
    if company is not None:
        qs = qs.filter(company=company)
    return qs


def penalites_par_lot_cache_ou_calcul(chantier, *, max_age_heures=36,
                                      maintenant=None):
    """NTCON28 — exposition aux pénalités SERVIE DEPUIS LE CACHE quand il est
    frais, recalculée sinon.

    Le cockpit (NTCON21) relançait le calcul NTCON15 à chaque GET. Le balayage
    quotidien fige le résultat sur ``Lot.penalite_calculee_cache`` ; cette
    fonction le sert tel quel si TOUS les lots du chantier portent un cache de
    moins de ``max_age_heures`` (36 h = une journée + une marge, pour qu'un
    balayage manqué ne serve jamais un chiffre périmé en silence).

    Sinon elle retombe sur ``penalites_retard_par_lot`` — best-effort : un
    balayage qui n'a jamais tourné ne casse aucun écran, il coûte juste le
    calcul. La réponse porte ``source`` (``'cache'`` / ``'calcul'``) et
    ``calcule_le`` pour que l'écran puisse DIRE d'où vient le chiffre plutôt
    que d'afficher une valeur d'âge inconnu.
    """
    from datetime import timedelta

    maintenant = maintenant or timezone.now()
    lots = list(Lot.objects.filter(chantier=chantier).order_by('ordre', 'id'))
    limite = maintenant - timedelta(hours=max_age_heures)

    frais = bool(lots) and all(
        lot.penalite_calculee_cache is not None
        and lot.penalite_calculee_le is not None
        and lot.penalite_calculee_le >= limite
        for lot in lots)

    if not frais:
        paye = penalites_retard_par_lot(chantier)
        paye['source'] = 'calcul'
        paye['calcule_le'] = maintenant
        return paye

    total = sum(
        (_decimal(lot.penalite_calculee_cache.get('exposition'))
         for lot in lots),
        _decimal(0))
    return {
        'chantier_id': chantier.pk,
        'date_reference': lots[0].penalite_calculee_cache.get(
            'date_reference'),
        'lots': [dict(lot.penalite_calculee_cache) for lot in lots],
        'total_exposition': total,
        'source': 'cache',
        'calcule_le': max(lot.penalite_calculee_le for lot in lots),
    }


def _decimal(valeur):
    """``Decimal`` tolérant (le cache JSON stocke des chaînes)."""
    from decimal import Decimal, InvalidOperation
    if valeur in (None, ''):
        return Decimal('0')
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return Decimal('0')


# ── NTCON22 — Rapport d'avancement de chantier sur une période ─────────────

def rapport_avancement(chantier, du, au):
    """NTCON22 — agrégats d'avancement d'un chantier sur ``[du, au]``.

    Document strictement INTERNE/MOE : AUCUN prix d'achat, aucun coût, jamais
    exposé via ``/proposal`` (règle #4 — le moteur premium ne rend QUE les
    devis client). Lecture seule.

    * **lots** (NTCON14) — avancement + retard vs planning ;
    * **réserves** (NTCON1/2) — créées / levées SUR LA PÉRIODE + reste ouvert ;
    * **RFI en cours** (NTCON3) — encore ouverts à la fin de période ;
    * **effectif moyen** — moyenne des effectifs des ``JournalChantier``
      (NTCON6) renseignés sur la période ;
    * **QHSE** — points d'arrêt BLOQUANTS du chantier, lus par le SÉLECTEUR de
      ``qhse`` (jamais ses ``models``/``views``).
    """
    from apps.qhse import selectors as qhse_selectors

    from .models import JournalChantier, ReserveChantier

    aujourdhui = timezone.localdate()
    company = chantier.company

    # ── Lots ────────────────────────────────────────────────────────────
    lots = []
    for bloc in planning_par_lot(chantier):
        fin_prevue = bloc['date_fin_prevue']
        fin_reelle = bloc['date_fin_reelle']
        reference = fin_reelle or min(au, aujourdhui)
        jours_retard = 0
        if fin_prevue and reference and reference > fin_prevue:
            jours_retard = (reference - fin_prevue).days
        lots.append({
            'nom': bloc['nom'],
            'statut': bloc['statut'],
            'avancement_pct': bloc['avancement_pct'],
            'date_fin_prevue': fin_prevue,
            'date_fin_reelle': fin_reelle,
            'en_retard': bloc['en_retard'],
            'jours_retard': jours_retard,
        })

    # ── Réserves de la période ──────────────────────────────────────────
    reserves = ReserveChantier.objects.filter(
        chantier=chantier, company=company)
    creees = reserves.filter(
        created_at__date__gte=du, created_at__date__lte=au).count()
    levees = reserves.filter(
        statut=ReserveChantier.Statut.LEVEE,
        date_levee__date__gte=du, date_levee__date__lte=au).count()
    ouvertes = reserves.filter(statut__in=[
        ReserveChantier.Statut.OUVERTE,
        ReserveChantier.Statut.EN_COURS,
        ReserveChantier.Statut.CONTESTEE,
    ]).count()
    bloquantes = reserves_actives_bloquantes(company, chantier=chantier).count()

    # ── RFI encore ouverts ──────────────────────────────────────────────
    rfis = [{
        'numero': rfi.numero,
        'question': rfi.question,
        'date_limite_reponse': rfi.date_limite_reponse,
        'en_retard': bool(
            rfi.date_limite_reponse and rfi.date_limite_reponse < aujourdhui),
    } for rfi in RFI.objects.filter(
        chantier=chantier, company=company,
        statut=RFI.Statut.OUVERT).order_by('numero')]

    # ── Effectif moyen sur la période (journal NTCON6) ──────────────────
    entrees = JournalChantier.objects.filter(
        chantier=chantier, company=company, date__gte=du, date__lte=au)
    total_interne = total_st = jours = 0
    for entree in entrees:
        jours += 1
        if isinstance(entree.effectif_interne, dict):
            total_interne += sum(entree.effectif_interne.values())
        if isinstance(entree.effectif_sous_traitant, dict):
            total_st += sum(entree.effectif_sous_traitant.values())
    effectif = {
        'jours_renseignes': jours,
        'moyenne_interne': round(total_interne / jours, 1) if jours else 0,
        'moyenne_sous_traitant': round(total_st / jours, 1) if jours else 0,
    }

    return {
        'chantier_id': chantier.pk,
        'du': du,
        'au': au,
        'lots': lots,
        'reserves': {
            'creees_periode': creees,
            'levees_periode': levees,
            'ouvertes': ouvertes,
            'bloquantes_ouvertes': bloquantes,
        },
        'rfi_en_cours': rfis,
        'effectif_moyen': effectif,
        'qhse_points_arret_bloquants': (
            qhse_selectors.hold_points_bloquants_pour_chantier(
                company, chantier.pk)),
    }


# ── NTCON17 — Registre des intervenants (coordination SPS/CISSCT) ──────────

def registre_intervenants(chantier, jour=None):
    """NTCON17 — vue consolidée des intervenants d'un chantier, en UN écran.

    LECTURE SEULE, aucune écriture nulle part. Agrège, chacun par le SÉLECTEUR
    de son app (jamais ses ``models``/``views``) :

    * **sous-traitants actifs** — ``installations.OrdreSousTraitance``
      (FG305) au statut ``emis``/``en_cours`` sur ce chantier, via la relation
      RÉELLE ``chantier.installations_ordres_sous_traitance`` (même app que le
      FK ``chantier``, comme ``debourse_sec_vs_facture``) ;
    * **attestations à jour** (FG307) — ``installations.selectors.
      sous_traitant_attestations_manquantes`` : une pièce obligatoire EXPIRÉE
      est signalée explicitement ;
    * **PPSPS signé** (NTCON16) — ``services.sous_traitant_a_signe_ppsps`` ;
    * **effectifs du jour** — DERNIÈRE entrée du ``JournalChantier`` (NTCON6) ;
    * **personnel interne présent + titres à risque** — ``rh.selectors``
      (``presences_installation`` FG170, ``habilitations_expirantes`` FG173,
      ``certifications_expirantes`` FG174) : tout titre expiré ou expirant
      sous 30 jours est remonté pour la coordination SPS.

    ``alertes`` rassemble, en français, ce qui doit sauter aux yeux du
    coordonnateur : attestation expirée, PPSPS non signé, titre RH échu.
    """
    from apps.installations import selectors as installations_selectors
    from apps.rh import selectors as rh_selectors

    from . import services
    from .models import JournalChantier

    if jour is None:
        jour = timezone.localdate()

    # ── Sous-traitants actifs sur le chantier (FG305) ───────────────────
    sous_traitants = []
    alertes = []
    ordres = (
        chantier.installations_ordres_sous_traitance
        .filter(statut__in=['emis', 'en_cours'])
        .select_related('sous_traitant'))
    for ordre in ordres:
        st = ordre.sous_traitant
        manquantes = installations_selectors.sous_traitant_attestations_manquantes(
            st, jour) if st is not None else []
        ppsps_signe = bool(st is not None and services.sous_traitant_a_signe_ppsps(
            chantier.pk, st.pk))
        sous_traitants.append({
            'ordre_id': ordre.pk,
            'reference': ordre.reference,
            'statut': ordre.statut,
            'prestation': ordre.prestation,
            'sous_traitant_id': getattr(st, 'pk', None),
            'sous_traitant_nom': getattr(st, 'nom', ''),
            'attestations_manquantes': manquantes,
            'attestations_a_jour': not manquantes,
            'ppsps_signe': ppsps_signe,
        })
        if manquantes:
            pieces = ', '.join(m['type_piece'] for m in manquantes)
            alertes.append(
                f'{getattr(st, "nom", "Sous-traitant")} : pièce(s) '
                f'obligatoire(s) expirée(s) — {pieces}.')
        if not ppsps_signe and services.chantier_a_un_ppsps(chantier.pk):
            alertes.append(
                f'{getattr(st, "nom", "Sous-traitant")} : PPSPS du chantier '
                'non signé.')

    # ── Effectifs du jour (dernière entrée de journal, NTCON6) ──────────
    journal = JournalChantier.objects.filter(
        chantier=chantier).order_by('-date', '-id').first()
    effectifs = {
        'date': journal.date if journal else None,
        'effectif_interne': (journal.effectif_interne or {}) if journal else {},
        'effectif_sous_traitant': (
            (journal.effectif_sous_traitant or {}) if journal else {}),
        'total_interne': sum(
            (journal.effectif_interne or {}).values()) if journal and isinstance(
                journal.effectif_interne, dict) else 0,
    }

    # ── Personnel interne présent + titres RH à risque (FG170/173/174) ──
    company = chantier.company
    presences = rh_selectors.presences_installation(
        company, chantier.pk, date_debut=jour, date_fin=jour,
        presents_seulement=True)
    personnel = []
    for presence in presences:
        employe = presence.employe
        titres = []
        for hab in rh_selectors.habilitations_expirantes(
                company, within_days=30, employe_id=employe.pk):
            titres.append({
                'famille': 'habilitation',
                'libelle': hab.get_type_habilitation_display(),
                'date_validite': hab.date_validite,
                'expiree': bool(hab.date_validite and hab.date_validite < jour),
            })
        for cert in rh_selectors.certifications_expirantes(
                company, within_days=30, employe_id=employe.pk):
            titres.append({
                'famille': 'certification',
                'libelle': cert.get_type_certification_display(),
                'date_validite': cert.date_validite,
                'expiree': bool(
                    cert.date_validite and cert.date_validite < jour),
            })
        personnel.append({
            'employe_id': employe.pk,
            'employe': str(employe),
            'titres_a_risque': titres,
        })
        for titre in titres:
            if titre['expiree']:
                alertes.append(
                    f'{employe} : {titre["libelle"]} expiré(e) le '
                    f'{titre["date_validite"]}.')

    return {
        'chantier_id': chantier.pk,
        'date': jour,
        'sous_traitants': sous_traitants,
        'effectifs_du_jour': effectifs,
        'personnel_interne': personnel,
        'alertes': alertes,
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
