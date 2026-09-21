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


# ── NTPAY17 — Comparateur de jeux versionnés (aperçu d'impact) ─────────────

#: Taille MAXIMALE de l'échantillon quand l'appelant n'en fournit pas : un
#: aperçu d'impact se lit, il ne se scrolle pas — et rejouer 400 bulletins en
#: mémoire pour une page d'aperçu serait du gaspillage.
ECHANTILLON_COMPARAISON_DEFAUT = 20


def _jeu_versionne(company, objet):
    """``(parametre, bareme)`` complet à partir d'UN objet versionné (NTPAY17).

    L'appelant publie soit un ``BaremeIR``, soit un ``ParametrePaie`` : la
    moitié manquante est celle RÉELLEMENT en vigueur à la date d'effet de
    l'objet publié (et pour SON pays, NTPAY8) — jamais une valeur inventée.
    """
    from .models import BaremeIR
    from .services import bareme_en_vigueur, parametre_en_vigueur

    if objet is None:
        return None, None
    pays = getattr(objet, 'pays', None)
    if isinstance(objet, BaremeIR):
        return parametre_en_vigueur(
            company, objet.date_effet, pays=pays), objet
    return objet, bareme_en_vigueur(company, objet.date_effet, pays=pays)


def _impact_profil(profil, parametre, bareme):
    """Rejoue EN MÉMOIRE le net/IR/coût employeur d'un profil (NTPAY17).

    Réutilise le cœur pur ``services._net_embauche`` (NTPAY14) — même
    enchaînement que le moteur réel — puis y ajoute les charges patronales.
    Aucune écriture, aucun ``BulletinPaie``.
    """
    from .services import (
        _net_embauche, allocations_familiales_patronale, amo_patronale,
        cnss_patronale, formation_professionnelle_patronale,
    )

    brut = Decimal(profil.salaire_base or 0)
    regime_mutuelle = None
    adhesion = getattr(profil, 'adhesion_mutuelle', None)
    if adhesion is not None and adhesion.actif:
        regime_mutuelle = adhesion.regime

    resultat = _net_embauche(
        brut, parametre=parametre, bareme=bareme,
        affilie_cnss=profil.affilie_cnss, affilie_amo=profil.affilie_amo,
        affilie_cimr=profil.affilie_cimr,
        taux_cimr=profil.taux_cimr_salarial,
        regime_mutuelle=regime_mutuelle,
        montant_exonere_plafond=Decimal(profil.regime_plafond_mensuel or 0)
        if profil.regime_exoneration != ProfilPaie.REGIME_AUCUN
        else Decimal('0'))

    charges = (
        cnss_patronale(parametre, resultat['brut'], profil.affilie_cnss)
        + amo_patronale(parametre, resultat['brut'], profil.affilie_amo)
        + allocations_familiales_patronale(
            parametre, resultat['brut'], profil.affilie_cnss)
        + formation_professionnelle_patronale(
            parametre, resultat['brut'], profil.affilie_cnss)
        + resultat['mutuelle_patronale']
    )
    resultat['charges_patronales'] = charges
    resultat['cout_employeur'] = resultat['brut'] + charges
    return resultat


def comparer_baremes(company, ancien, nouveau, echantillon_profils=None):
    """Aperçu d'IMPACT d'un jeu versionné avant publication (NTPAY17).

    Rejoue EN MÉMOIRE, pour un échantillon de profils ACTIFS, le net, l'IR et
    le coût employeur avec l'ANCIEN puis le NOUVEAU jeu (``BaremeIR`` ou
    ``ParametrePaie`` — la moitié manquante est celle en vigueur à la date
    d'effet de l'objet donné, cf. ``_jeu_versionne``) et restitue l'écart par
    salarié ET en masse.

    ``echantillon_profils`` accepte des ``ProfilPaie`` ou des identifiants ;
    omis, les profils actifs de la société sont pris, dans la limite de
    ``ECHANTILLON_COMPARAISON_DEFAUT``. **Aucune persistance** : c'est un
    aperçu pur, rien n'est écrit ni publié.
    """
    parametre_ancien, bareme_ancien = _jeu_versionne(company, ancien)
    parametre_nouveau, bareme_nouveau = _jeu_versionne(company, nouveau)

    if echantillon_profils is None:
        profils = list(
            ProfilPaie.objects
            .filter(company=company, actif=True)
            .select_related('employe', 'adhesion_mutuelle__regime')
            .order_by('id')[:ECHANTILLON_COMPARAISON_DEFAUT]
        )
    else:
        ids = [getattr(p, 'pk', p) for p in echantillon_profils]
        profils = list(
            ProfilPaie.objects
            .filter(company=company, pk__in=ids)
            .select_related('employe', 'adhesion_mutuelle__regime')
            .order_by('id')
        )

    lignes = []
    totaux = {
        'net_ancien': Decimal('0.00'), 'net_nouveau': Decimal('0.00'),
        'ir_ancien': Decimal('0.00'), 'ir_nouveau': Decimal('0.00'),
        'cout_ancien': Decimal('0.00'), 'cout_nouveau': Decimal('0.00'),
    }
    for profil in profils:
        avant = _impact_profil(profil, parametre_ancien, bareme_ancien)
        apres = _impact_profil(profil, parametre_nouveau, bareme_nouveau)
        employe = getattr(profil, 'employe', None)
        lignes.append({
            'profil_id': profil.id,
            'matricule': getattr(employe, 'matricule', '') if employe else '',
            'nom': f'{employe.nom} {employe.prenom}'.strip()
            if employe else '',
            'brut': avant['brut'],
            'net_ancien': avant['net_a_payer'],
            'net_nouveau': apres['net_a_payer'],
            'ecart_net': apres['net_a_payer'] - avant['net_a_payer'],
            'ir_ancien': avant['ir'],
            'ir_nouveau': apres['ir'],
            'ecart_ir': apres['ir'] - avant['ir'],
            'cout_ancien': avant['cout_employeur'],
            'cout_nouveau': apres['cout_employeur'],
            'ecart_cout': apres['cout_employeur'] - avant['cout_employeur'],
        })
        totaux['net_ancien'] += avant['net_a_payer']
        totaux['net_nouveau'] += apres['net_a_payer']
        totaux['ir_ancien'] += avant['ir']
        totaux['ir_nouveau'] += apres['ir']
        totaux['cout_ancien'] += avant['cout_employeur']
        totaux['cout_nouveau'] += apres['cout_employeur']

    totaux['ecart_net'] = totaux['net_nouveau'] - totaux['net_ancien']
    totaux['ecart_ir'] = totaux['ir_nouveau'] - totaux['ir_ancien']
    totaux['ecart_cout'] = totaux['cout_nouveau'] - totaux['cout_ancien']

    def _decrire(objet, parametre, bareme):
        if objet is None:
            return None
        return {
            'id': objet.id,
            'objet': 'bareme_ir' if bareme is objet else 'parametre_paie',
            'date_effet': objet.date_effet,
            'parametre_id': getattr(parametre, 'id', None),
            'bareme_id': getattr(bareme, 'id', None),
        }

    return {
        'ancien': _decrire(ancien, parametre_ancien, bareme_ancien),
        'nouveau': _decrire(nouveau, parametre_nouveau, bareme_nouveau),
        'nombre_profils': len(lignes),
        'lignes': lignes,
        'totaux': totaux,
    }


# ── NTPAY19 — Rapport « Masse salariale » par période / service / site ─────

GROUPEMENTS_MASSE_SALARIALE = ('departement', 'site')

#: Libellé du groupe « pas d'information » — jamais une affectation inventée.
LIBELLE_SANS_GROUPE = {
    'departement': 'Sans département',
    'site': 'Sans site déclaré',
}


def _bornes_rapport(valeur):
    """``(annee, mois)`` depuis un couple, une ``PeriodePaie`` ou 'YYYY-MM'."""
    if valeur is None:
        return None
    if hasattr(valeur, 'annee') and hasattr(valeur, 'mois'):
        return int(valeur.annee), int(valeur.mois)
    if isinstance(valeur, str):
        annee, _, mois = valeur.partition('-')
        return int(annee), int(mois)
    annee, mois = valeur
    return int(annee), int(mois)


def rapport_masse_salariale(company, periode_debut, periode_fin, *,
                            group_by='departement'):
    """Synthèse de masse salariale sur une fenêtre de périodes (NTPAY19).

    Somme, sur les bulletins VALIDÉS des périodes comprises entre
    ``periode_debut`` et ``periode_fin`` (inclus, chacun un couple
    ``(annee, mois)``, une ``PeriodePaie`` ou ``'YYYY-MM'``), le brut, les
    charges patronales, le coût total et l'EFFECTIF distinct, groupés par
    ``departement`` ou par ``site``.

    Le département et le site sont lus via ``apps.rh.selectors``
    (``departements_par_employe`` / ``equipe_terrain`` — jamais ``rh.models``).
    Un employé sans rattachement tombe dans « Sans département » / « Sans site
    déclaré » : aucune affectation n'est inventée. NOTE — la zone
    d'intervention n'est exposée que pour les employés ACTIFS : un salarié
    sorti en cours de fenêtre apparaît donc « sans site », jamais rattaché au
    hasard.

    Lecture seule, scopée société.
    """
    if group_by not in GROUPEMENTS_MASSE_SALARIALE:
        raise ValueError(
            "group_by doit être 'departement' ou 'site'.")

    from .models import PeriodePaie

    annee_debut, mois_debut = _bornes_rapport(periode_debut)
    annee_fin, mois_fin = _bornes_rapport(periode_fin)
    borne_debut = annee_debut * 12 + mois_debut
    borne_fin = annee_fin * 12 + mois_fin

    periodes = [
        p for p in PeriodePaie.objects.filter(company=company)
        if borne_debut <= (p.annee * 12 + p.mois) <= borne_fin
    ]
    bulletins = list(
        BulletinPaie.objects
        .filter(company=company, periode_id__in=[p.id for p in periodes],
                statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil')
    )

    employe_ids = {
        b.profil.employe_id for b in bulletins
        if b.profil_id and b.profil.employe_id
    }
    groupe_par_employe = {}
    if employe_ids:
        from apps.rh import selectors as rh_selectors

        if group_by == 'departement':
            infos = rh_selectors.departements_par_employe(company, employe_ids)
            groupe_par_employe = {
                employe_id: (info.get('departement_id'),
                             info.get('departement_nom') or '')
                for employe_id, info in infos.items()
            }
        else:
            for ligne in rh_selectors.equipe_terrain(company):
                zone = (ligne.get('zone_intervention') or '').strip()
                if zone:
                    groupe_par_employe[ligne['employe_id']] = (zone, zone)

    agrege = {}
    totaux = {
        'brut': Decimal('0.00'), 'charges_patronales': Decimal('0.00'),
        'cout_total': Decimal('0.00'),
    }
    profils_totaux = set()
    for bulletin in bulletins:
        employe_id = bulletin.profil.employe_id if bulletin.profil_id else None
        cle, libelle = groupe_par_employe.get(employe_id, (None, ''))
        if not cle:
            cle = f'sans_{group_by}'
            libelle = LIBELLE_SANS_GROUPE[group_by]
        entree = agrege.setdefault(cle, {
            'cle': cle, 'libelle': libelle or str(cle),
            'brut': Decimal('0.00'),
            'charges_patronales': Decimal('0.00'),
            'cout_total': Decimal('0.00'),
            'profils': set(),
        })
        brut = Decimal(bulletin.brut or 0)
        charges = Decimal(bulletin.charges_patronales or 0)
        entree['brut'] += brut
        entree['charges_patronales'] += charges
        entree['cout_total'] += brut + charges
        entree['profils'].add(bulletin.profil_id)
        totaux['brut'] += brut
        totaux['charges_patronales'] += charges
        totaux['cout_total'] += brut + charges
        profils_totaux.add(bulletin.profil_id)

    groupes = []
    for entree in agrege.values():
        groupes.append({
            'cle': entree['cle'], 'libelle': entree['libelle'],
            'brut': entree['brut'],
            'charges_patronales': entree['charges_patronales'],
            'cout_total': entree['cout_total'],
            'effectif': len(entree['profils']),
        })
    groupes.sort(key=lambda g: (g['libelle'], str(g['cle'])))
    totaux['effectif'] = len(profils_totaux)

    return {
        'group_by': group_by,
        'periode_debut': {'annee': annee_debut, 'mois': mois_debut},
        'periode_fin': {'annee': annee_fin, 'mois': mois_fin},
        'nombre_periodes': len(periodes),
        'nombre_bulletins': len(bulletins),
        'groupes': groupes,
        'totaux': totaux,
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
