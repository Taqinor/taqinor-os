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
