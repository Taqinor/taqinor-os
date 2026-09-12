"""Sélecteurs (lectures) de la paie.

Lecture seule — jamais d'écriture ici. Certaines fonctions sont exposées aux
autres apps (rh…) qui lisent la paie UNIQUEMENT via ce module (jamais
``apps.paie.models`` directement), symétrique au patron ``apps.rh.selectors``
déjà en place pour le sens inverse. D'autres (``analyse_paie``) sont des
agrégats internes à la paie (rapports), placés ici pour rester lecture-seule
et séparés des écritures de ``services.py``.
"""
from decimal import Decimal

from .models import AvanceSalarie, BulletinPaie, LigneBulletin, ProfilPaie


def _rib_normalise(rib):
    """Normalisation MINIMALE d'un RIB pour comparaison (ARC25).

    Uniquement le retrait des espaces (un RIB saisi « 011 780 … » et
    « 011780… » sont le même compte). Robuste au formatage mais SANS aller
    au-delà : ni casse, ni ponctuation, ni troncature — deux chiffres réellement
    différents doivent rester différents.
    """
    return ''.join((rib or '').split())


def divergences_rib_periode(periode):
    """Divergences RIB paie ↔ RH pour un run de virement (ARC25, lecture seule).

    CONTRÔLE croisé (jamais une fusion) : pour chaque ``ProfilPaie`` de la
    société PAYÉ PAR VIREMENT et rattaché à un dossier RH, compare le
    ``ProfilPaie.rib`` (source de la ligne de virement, PAIE30) au ``rib`` de
    référence de la fiche RH (``rh.DossierEmploye.rib``, lu via
    ``apps.rh.selectors.ribs_par_employe`` — jamais un import de ``rh.models``).

    Les copies figées ``LigneVirement.rib`` sont des snapshots INTENTIONNELS
    (jamais comparés ici). Aucune écriture, aucune unification : ce sélecteur
    ne fait que SIGNALER un écart pour qu'un humain tranche.

    Sémantique des côtés manquants (documentée, pour éviter les faux positifs) :
    un écart n'est retenu QUE si les DEUX RIB sont non vides ET diffèrent après
    retrait des espaces. Un RIB paie vide (déjà couvert par l'avertissement
    bloquant ``rib_manquant_virement`` de ZPAI2) ou un RIB RH vide (référence
    non renseignée) N'est PAS une divergence — on ne compare pas à du vide.

    Toujours scopé société (``periode.company``). Renvoie une liste de dicts
    triée par ``employe_id`` :

    ``{'profil_id', 'employe_id', 'rib_paie', 'rib_rh'}`` (RIB bruts, tels que
    saisis). Liste vide si la période/société manque ou si tout concorde.
    """
    company = getattr(periode, 'company', None)
    if company is None:
        return []

    profils = list(
        ProfilPaie.objects
        .filter(company=company,
                mode_paiement=ProfilPaie.MODE_PAIEMENT_VIREMENT,
                employe__isnull=False)
        .only('id', 'employe_id', 'rib')
    )
    if not profils:
        return []

    from apps.rh import selectors as rh_selectors

    employe_ids = {p.employe_id for p in profils}
    ribs_rh = rh_selectors.ribs_par_employe(company, employe_ids)

    divergences = []
    for profil in profils:
        rib_paie = profil.rib or ''
        rib_rh = ribs_rh.get(profil.employe_id, '') or ''
        # Un côté vide n'est pas une divergence (voir docstring).
        if not rib_paie.strip() or not rib_rh.strip():
            continue
        if _rib_normalise(rib_paie) != _rib_normalise(rib_rh):
            divergences.append({
                'profil_id': profil.id,
                'employe_id': profil.employe_id,
                'rib_paie': rib_paie,
                'rib_rh': rib_rh,
            })
    divergences.sort(key=lambda d: d['employe_id'])
    return divergences


def divergences_cnss_periode(periode):
    """Divergences n° CNSS paie ↔ RH pour une période (WIR89, lecture seule).

    Symétrique de :func:`divergences_rib_periode` (ARC25) : pour chaque
    ``ProfilPaie`` de la société AFFILIÉ CNSS et rattaché à un dossier RH,
    compare le ``ProfilPaie.numero_cnss`` (source du bordereau de déclaration,
    PAIE31) au ``cnss`` de référence de la fiche RH (``rh.DossierEmploye.cnss``,
    lu via ``apps.rh.selectors.cnss_par_employe`` — jamais un import de
    ``rh.models``).

    CONTRÔLE croisé (jamais une fusion) : aucune écriture, aucune unification —
    ce sélecteur ne fait que SIGNALER un écart pour qu'un humain tranche, comme
    son pendant RIB.

    Même sémantique des côtés manquants que ``divergences_rib_periode`` : un
    écart n'est retenu QUE si les DEUX numéros sont non vides ET diffèrent
    après retrait des espaces. Un numéro absent d'un côté N'est PAS une
    divergence — on ne compare pas à du vide.

    Toujours scopé société (``periode.company``). Renvoie une liste de dicts
    triée par ``employe_id`` :

    ``{'profil_id', 'employe_id', 'cnss_paie', 'cnss_rh'}`` (numéros bruts, tels
    que saisis). Liste vide si la période/société manque ou si tout concorde.
    """
    company = getattr(periode, 'company', None)
    if company is None:
        return []

    profils = list(
        ProfilPaie.objects
        .filter(company=company, affilie_cnss=True, employe__isnull=False)
        .only('id', 'employe_id', 'numero_cnss')
    )
    if not profils:
        return []

    from apps.rh import selectors as rh_selectors

    employe_ids = {p.employe_id for p in profils}
    cnss_rh = rh_selectors.cnss_par_employe(company, employe_ids)

    divergences = []
    for profil in profils:
        cnss_paie = profil.numero_cnss or ''
        cnss_reference = cnss_rh.get(profil.employe_id, '') or ''
        # Un côté vide n'est pas une divergence (voir docstring).
        if not cnss_paie.strip() or not cnss_reference.strip():
            continue
        if _rib_normalise(cnss_paie) != _rib_normalise(cnss_reference):
            divergences.append({
                'profil_id': profil.id,
                'employe_id': profil.employe_id,
                'cnss_paie': cnss_paie,
                'cnss_rh': cnss_reference,
            })
    divergences.sort(key=lambda d: d['employe_id'])
    return divergences


def mes_bulletins_valides(user):
    """Bulletins de paie GÉNÉRÉS et VALIDÉS de ``user`` (YHIRE12, cross-app).

    Sélecteur de lecture pour ``rh`` : le portail self-service fusionne cette
    liste avec ses propres dépôts externes (``rh.BulletinPaie``, FG196) en une
    UNE surface ``mes-bulletins`` — jamais deux listes. Rapproché par
    ``profil.employe.user == user`` (jamais par company seule, pour ne jamais
    exposer les bulletins d'un collègue). Renvoie des dicts normalisés
    ``{source, annee, mois, id, date_creation}`` (source='genere').
    """
    qs = (
        BulletinPaie.objects
        .filter(profil__employe__user=user, statut=BulletinPaie.STATUT_VALIDE)
        .select_related('periode')
        .order_by('-periode__annee', '-periode__mois')
    )
    return [
        {
            'source': 'genere',
            'id': b.id,
            'annee': b.periode.annee,
            'mois': b.periode.mois,
            'date_creation': b.date_creation,
        }
        for b in qs
    ]


def taux_charges_patronales(company):
    """NTFPA9 — taux global de charges PATRONALES d'une société (fraction, ex.
    0.18 = 18 %), somme des taux patronaux du ``ParametrePaie`` courant (CNSS +
    AMO + allocations familiales + formation pro).

    Sélecteur de LECTURE pour ``apps.fpa`` (driver masse salariale) : FP&A ne
    lit jamais ``paie.models`` directement. Repli sur les défauts du modèle si
    aucun ``ParametrePaie`` n'existe encore (jamais d'exception).

    AUD710 — ce sélecteur ne RECOPIE plus les taux en dur : il lit le
    ``ParametrePaie`` réel de la société et, à défaut, les DÉFAUTS DES CHAMPS
    du modèle. Un taux (dont l'AMO patronal) n'a donc plus qu'un seul
    propriétaire : le paramètre en base, dont le modèle porte le défaut."""
    from decimal import Decimal

    from .models import ParametrePaie

    champs = ('taux_cnss_patronal', 'taux_amo_patronal',
              'taux_allocations_familiales', 'taux_formation_pro')
    param = ParametrePaie.objects.filter(company=company).order_by('-id').first()
    if param is None:
        pct = sum(
            (Decimal(ParametrePaie._meta.get_field(champ).default)
             for champ in champs), Decimal('0'))
    else:
        pct = sum(
            (Decimal(getattr(param, champ) or 0) for champ in champs),
            Decimal('0'))
    return Decimal(pct) / Decimal('100')


def masse_salariale_base_mensuelle(company):
    """NTFPA9 — somme des ``salaire_base`` des profils de paie ACTIFS d'une
    société (référentiel salaires courant, base mensuelle). Lecture seule pour
    ``apps.fpa`` ; jamais un import de ``paie.models`` côté FP&A."""
    from decimal import Decimal

    from django.db.models import Sum

    total = ProfilPaie.objects.filter(
        company=company, actif=True).aggregate(s=Sum('salaire_base'))['s']
    return Decimal(total or 0)


def solde_avance(avance_id):
    """Solde restant dû d'une ``AvanceSalarie`` par id (YHIRE5, cross-app).

    Sélecteur de lecture pour ``rh`` : le guichet de demande RH
    (``rh.AvanceSalaire``) affiche le solde réel de l'avance MATÉRIALISÉE
    côté paie (le seul moteur câblé au bulletin) sans jamais importer
    ``paie.models``. Renvoie ``None`` si l'id est inconnu.
    """
    avance = AvanceSalarie.objects.filter(pk=avance_id).first()
    if avance is None:
        return None
    return avance.solde_restant


# ── NTPAY16 — Cockpit de conformité paie (échéances + preuves) ─────────────

#: Fenêtre « à venir » du cockpit : une échéance dont la date limite tombe
#: dans les 30 prochains jours est signalée AVANT d'être en retard.
FENETRE_ECHEANCES_A_VENIR_JOURS = 30


def cockpit_conformite_paie(company, *, today=None):
    """État de conformité paie d'une société, en UN seul agrégat (NTPAY16).

    Réunit les cinq signaux qui vivaient chacun dans son coin :

    1. ``EcheanceDeclarative`` (XPAI6) EN RETARD et À VENIR (30 jours) ;
    2. preuves de dépôt MANQUANTES (NTPAY5) — une échéance dont la date limite
       est passée sans le moindre ``DepotDeclaratif`` non rejeté ;
    3. barèmes/paramètres NON VALIDÉS par le fondateur
       (``valide_par_fondateur=False``) — ils calculent de la paie réelle ;
    4. périodes ouvertes EN RETARD de clôture (ZPAI12) ;
    5. avertissements PRÉ-RUN bloquants des périodes ouvertes (ZPAI2).

    ``today`` est injectable (tests déterministes). Lecture seule, strictement
    scopée société. ``conforme`` est VRAI quand les cinq listes sont vides.
    """
    from datetime import timedelta

    from django.utils import timezone as dj_timezone

    from .models import (
        BaremeIR, DepotDeclaratif, EcheanceDeclarative, ParametrePaie,
        PeriodePaie,
    )
    from .services import avertissements_periode, periodes_cloture_en_retard

    if today is None:
        today = dj_timezone.localdate()
    limite_a_venir = today + timedelta(days=FENETRE_ECHEANCES_A_VENIR_JOURS)

    deposees = (EcheanceDeclarative.STATUT_DEPOSEE,
                EcheanceDeclarative.STATUT_PAYEE)
    echeances = list(
        EcheanceDeclarative.objects
        .filter(company=company)
        .select_related('periode')
        .order_by('date_limite', 'type_echeance')
    )

    # Preuves de dépôt réellement enregistrées (un dépôt REJETÉ ne prouve
    # rien : la déclaration reste due).
    avec_preuve = set(
        DepotDeclaratif.objects
        .filter(company=company)
        .exclude(statut=DepotDeclaratif.STATUT_REJETE)
        .values_list('echeance_id', flat=True)
    )

    def _ligne_echeance(echeance):
        return {
            'id': echeance.id,
            'type': echeance.type_echeance,
            'libelle': echeance.get_type_echeance_display(),
            'date_limite': echeance.date_limite,
            'statut': echeance.statut,
            'periode_id': echeance.periode_id,
            'annee': echeance.periode.annee,
            'mois': echeance.periode.mois,
            'jours': (echeance.date_limite - today).days,
        }

    en_retard, a_venir, sans_preuve = [], [], []
    for echeance in echeances:
        if echeance.statut in deposees:
            continue
        if echeance.date_limite < today:
            en_retard.append(_ligne_echeance(echeance))
            if echeance.id not in avec_preuve:
                sans_preuve.append(_ligne_echeance(echeance))
        elif echeance.date_limite <= limite_a_venir:
            a_venir.append(_ligne_echeance(echeance))

    baremes_non_valides = [
        {'id': bareme.id, 'objet': 'bareme_ir',
         'libelle': bareme.libelle or f'Barème IR {bareme.date_effet}',
         'date_effet': bareme.date_effet}
        for bareme in BaremeIR.objects.filter(
            company=company, valide_par_fondateur=False)
        .order_by('date_effet')
    ] + [
        {'id': parametre.id, 'objet': 'parametre_paie',
         'libelle': f'Paramètres sociaux du {parametre.date_effet}',
         'date_effet': parametre.date_effet}
        for parametre in ParametrePaie.objects.filter(
            company=company, valide_par_fondateur=False)
        .order_by('date_effet')
    ]

    periodes_en_retard = [
        {'id': periode.id, 'annee': periode.annee, 'mois': periode.mois,
         'statut': periode.statut, 'type_run': periode.type_run}
        for periode in periodes_cloture_en_retard(company)
    ]

    # ZPAI2 — prérequis manquants des périodes encore OUVERTES seulement :
    # rejouer le panneau sur une période clôturée n'apprendrait rien.
    periodes_ouvertes = PeriodePaie.objects.filter(
        company=company,
        statut__in=[PeriodePaie.STATUT_BROUILLON, PeriodePaie.STATUT_CALCULEE],
    ).order_by('annee', 'mois')
    alertes_pre_run = []
    for periode in periodes_ouvertes:
        signaux = avertissements_periode(periode)
        bloquants = [s for s in signaux if s['gravite'] == 'bloquant']
        if not signaux:
            continue
        alertes_pre_run.append({
            'periode_id': periode.id,
            'annee': periode.annee, 'mois': periode.mois,
            'bloquants': len(bloquants),
            'avertissements': len(signaux) - len(bloquants),
        })

    blocs = (en_retard, sans_preuve, baremes_non_valides, periodes_en_retard,
             alertes_pre_run)
    return {
        'today': today,
        'conforme': not any(blocs),
        'echeances_en_retard': en_retard,
        'echeances_a_venir': a_venir,
        'depots_manquants': sans_preuve,
        'baremes_non_valides': baremes_non_valides,
        'periodes_en_retard': periodes_en_retard,
        'alertes_pre_run': alertes_pre_run,
    }


def _periodes_de_la_fenetre(company, annee_debut, mois_debut, annee_fin,
                            mois_fin):
    """Périodes de paie de la société dans la fenêtre inclusive donnée."""
    from .models import PeriodePaie

    borne_debut = annee_debut * 12 + mois_debut
    borne_fin = annee_fin * 12 + mois_fin
    return [
        p for p in PeriodePaie.objects.filter(company=company)
        if borne_debut <= (p.annee * 12 + p.mois) <= borne_fin
    ]


def analyse_paie(company, annee_debut, mois_debut, annee_fin, mois_fin, *,
                 group_by='rubrique'):
    """Rapport d'analyse de paie multi-périodes (ZPAI1, pivot Odoo « Payroll

    Analysis »). Somme les ``LigneBulletin`` des ``BulletinPaie`` VALIDÉS de
    la société sur la fenêtre ``[annee_debut/mois_debut, annee_fin/mois_fin]``
    (inclusive), groupées soit par ``code`` de rubrique (défaut), soit par
    département (lu via ``apps.rh.selectors.departements_par_employe`` —
    jamais ``rh.models`` directement).

    Renvoie ``{'mois': [...], 'group_by': ..., 'lignes': [{'cle', 'libelle',
    'totaux_par_mois': {mois_iso: montant}, 'total': montant}, ...],
    'total_general': montant}``. ``mois_iso`` est ``'YYYY-MM'``. Lecture
    seule, scopé société.
    """
    if group_by not in ('rubrique', 'departement'):
        raise ValueError("group_by doit être 'rubrique' ou 'departement'.")

    periodes = _periodes_de_la_fenetre(
        company, annee_debut, mois_debut, annee_fin, mois_fin)
    periodes_par_id = {p.id: p for p in periodes}
    mois_iso_ordonnes = sorted({
        f'{p.annee:04d}-{p.mois:02d}' for p in periodes})

    bulletins = list(
        BulletinPaie.objects.filter(
            company=company, periode_id__in=periodes_par_id.keys(),
            statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil'))
    bulletins_par_id = {b.id: b for b in bulletins}

    departement_par_employe = {}
    if group_by == 'departement' and bulletins:
        from apps.rh import selectors as rh_selectors

        employe_ids = {
            b.profil.employe_id for b in bulletins if b.profil_id}
        departement_par_employe = rh_selectors.departements_par_employe(
            company, employe_ids)

    lignes = (
        LigneBulletin.objects
        .filter(company=company, bulletin_id__in=bulletins_par_id.keys())
    )

    # cle -> {'libelle', 'totaux_par_mois': {mois_iso: Decimal}}
    agrege = {}
    for ligne in lignes:
        bulletin = bulletins_par_id.get(ligne.bulletin_id)
        if bulletin is None:
            continue
        periode = periodes_par_id.get(bulletin.periode_id)
        if periode is None:
            continue
        mois_iso = f'{periode.annee:04d}-{periode.mois:02d}'

        if group_by == 'rubrique':
            cle, libelle = ligne.code, ligne.libelle
        else:
            employe_id = bulletin.profil.employe_id if bulletin.profil_id \
                else None
            info = departement_par_employe.get(employe_id, {})
            cle = info.get('departement_id') or 'sans_departement'
            libelle = info.get('departement_nom') or 'Sans département'

        entry = agrege.setdefault(
            cle, {'libelle': libelle, 'totaux_par_mois': {}})
        entry['totaux_par_mois'][mois_iso] = (
            entry['totaux_par_mois'].get(mois_iso, Decimal('0.00'))
            + Decimal(ligne.montant or 0))

    resultat_lignes = []
    total_general = Decimal('0.00')
    for cle, entry in agrege.items():
        total_ligne = sum(
            entry['totaux_par_mois'].values(), Decimal('0.00'))
        total_general += total_ligne
        resultat_lignes.append({
            'cle': cle, 'libelle': entry['libelle'],
            'totaux_par_mois': entry['totaux_par_mois'],
            'total': total_ligne,
        })
    resultat_lignes.sort(key=lambda x: str(x['cle']))

    return {
        'mois': mois_iso_ordonnes,
        'group_by': group_by,
        'lignes': resultat_lignes,
        'total_general': total_general,
    }
