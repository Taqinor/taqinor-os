"""Sélecteurs (lectures) du module ``apps.juridique`` (groupe NTJUR).

FRONTIÈRE INTER-APPS — une AUTRE app qui a besoin de LIRE des données
juridiques passe par une fonction de CE fichier (jamais un import de
``apps.juridique.models`` / ``.views``). Imports paresseux (fonction-locaux)
pour ne jamais créer de cycle au chargement des apps.
"""
from __future__ import annotations


def peut_voir_confidentiel(user):
    """Vrai si ``user`` a le droit de voir les dossiers CONFIDENTIELS.

    Palier faisant autorité : ``CustomUser.menu_tier`` (dérivé du Role FK,
    renvoie le palier admin pour un superuser) — jamais ``role_legacy``, peu
    fiable pour un administrateur provisionné via le Role FK. Même patron que
    ``contrats.ContratViewSet.get_queryset`` (CONTRAT6).
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    role_admin = getattr(user, 'ROLE_ADMIN', None)
    if role_admin is None:
        return False
    return getattr(user, 'menu_tier', None) == role_admin


def dossiers_visibles(company, user=None):
    """Dossiers juridiques de ``company``, filtrés par confidentialité.

    Un dossier ``confidentiel`` est EXCLU (invisible, pas 403) pour un
    utilisateur sans le palier requis — y compris son propre responsable
    interne : c'est ce qui protège les dossiers RH/direction.
    """
    from .models import DossierJuridique

    qs = DossierJuridique.objects.filter(company=company)
    if user is not None and not peut_voir_confidentiel(user):
        qs = qs.exclude(
            confidentialite=DossierJuridique.NiveauConfidentialite.CONFIDENTIEL)
    return qs


def dossier_par_id(company, dossier_id, user=None):
    """Un dossier de ``company`` par id (ou ``None``), filtrage confidentialité
    appliqué — lecture cross-app sûre."""
    return dossiers_visibles(company, user=user).filter(pk=dossier_id).first()


# ── NTJUR12 — budget juridique : engagé vs consommé vs alloué ───────────────


def budget_dossier(dossier):
    """Budget d'un dossier : ``engage`` / ``consomme`` / ``budget_alloue``.

    * ``engage``   — Σ des montants engagés par les mandats NON clos (forfait,
      ou taux horaire × heures estimées ; un honoraire de RÉSULTAT n'engage
      rien tant qu'il n'est pas dû — jamais un chiffre inventé) ;
    * ``consomme`` — Σ TTC des notes d'honoraires ``validee``/``payee`` (une
      note simplement ``recue`` n'est pas encore un engagement acté) ;
    * ``pourcentage_consomme`` — ``None`` quand aucune enveloppe n'est fixée
      ou qu'elle vaut 0 (division par zéro GARDÉE, patron
      ``gestion_projet.selectors.couts_engages_vs_reels``) ;
    * ``depassement`` — vrai dès que le consommé dépasse l'enveloppe.
    """
    from decimal import Decimal

    from .models import MandatAvocat, NoteHonoraires

    # Un mandat CLOS n'engage plus rien ; les autres (brouillon, en
    # approbation, actif) comptent : le budget sert justement à voir venir un
    # engagement avant qu'il ne soit activé.
    mandats = MandatAvocat.objects.filter(dossier=dossier).exclude(
        statut=MandatAvocat.Statut.CLOS)
    engage = sum(
        (m.montant_engage for m in mandats), Decimal('0')
    ).quantize(Decimal('0.01'))
    consomme = Decimal('0')
    notes = NoteHonoraires.objects.filter(
        mandat__dossier=dossier,
        statut__in=(NoteHonoraires.Statut.VALIDEE,
                    NoteHonoraires.Statut.PAYEE))
    for note in notes:
        consomme += note.montant_ttc or Decimal('0')
    consomme = consomme.quantize(Decimal('0.01'))
    alloue = dossier.budget_alloue
    pourcentage = None
    if alloue is not None and alloue > 0:
        pourcentage = float(
            (consomme / alloue * Decimal('100')).quantize(Decimal('0.01')))
    return {
        'dossier': dossier.id,
        'reference': dossier.reference,
        'budget_alloue': str(alloue) if alloue is not None else None,
        'engage': str(engage),
        'consomme': str(consomme),
        'pourcentage_consomme': pourcentage,
        'depassement': bool(alloue is not None and alloue > 0
                            and consomme > alloue),
    }


def tableau_bord_juridique(company, user=None):
    """Agrégat juridique de la société (NTJUR12).

    Total engagé/consommé PAR NATURE de dossier + liste des dossiers en
    dépassement (consommé > alloué). Le filtrage de confidentialité s'applique
    à l'AGRÉGAT lui-même : un rôle non autorisé obtient des totaux qui
    EXCLUENT les dossiers confidentiels — jamais de fuite par somme.
    """
    from decimal import Decimal

    dossiers = list(dossiers_visibles(company, user=user))
    par_nature = {}
    depassements = []
    total_engage = Decimal('0')
    total_consomme = Decimal('0')
    for dossier in dossiers:
        budget = budget_dossier(dossier)
        engage = Decimal(budget['engage'])
        consomme = Decimal(budget['consomme'])
        total_engage += engage
        total_consomme += consomme
        seau = par_nature.setdefault(
            dossier.nature, {'nature': dossier.nature, 'nombre': 0,
                             'engage': Decimal('0'),
                             'consomme': Decimal('0')})
        seau['nombre'] += 1
        seau['engage'] += engage
        seau['consomme'] += consomme
        if budget['depassement']:
            depassements.append({
                'dossier': dossier.id,
                'reference': dossier.reference,
                'titre': dossier.titre,
                'budget_alloue': budget['budget_alloue'],
                'consomme': budget['consomme'],
                'pourcentage_consomme': budget['pourcentage_consomme'],
            })
    return {
        'nombre_dossiers': len(dossiers),
        'total_engage': str(total_engage.quantize(Decimal('0.01'))),
        'total_consomme': str(total_consomme.quantize(Decimal('0.01'))),
        'par_nature': [
            {**seau, 'engage': str(seau['engage']),
             'consomme': str(seau['consomme'])}
            for seau in sorted(par_nature.values(),
                               key=lambda s: s['nature'])
        ],
        'depassements': sorted(
            depassements, key=lambda d: d['pourcentage_consomme'] or 0,
            reverse=True),
    }


# ── NTJUR48 — KPI juridiques (consommés en LECTURE par ``reporting``) ───────


def kpis_juridiques(company, user=None, debut=None, fin=None):
    """Les quatre KPI juridiques de la société (NTJUR48).

    * ``juridique_dossiers_ouverts``      — dossiers NON clos ;
    * ``juridique_montant_en_jeu_total``  — Σ des montants en jeu des dossiers
      non clos ;
    * ``juridique_taux_gain``             — dossiers ``clos_gagne`` / total des
      dossiers clos sur la période, en % ; ``None`` si aucun dossier clos (un
      0 % serait un mensonge, pas une absence) ;
    * ``juridique_delai_moyen_resolution`` — moyenne des jours entre
      ``date_ouverture`` et la clôture ; ``None`` si aucun dossier clos.

    ``user`` applique le filtrage de CONFIDENTIALITÉ à l'agrégat : un rôle non
    autorisé obtient des KPI qui EXCLUENT les dossiers confidentiels — jamais
    de fuite par moyenne ni par compteur (cohérent avec NTJUR24).
    ``debut``/``fin`` (dates) bornent la période de CLÔTURE pour le taux de
    gain et le délai moyen.
    """
    from decimal import Decimal

    from .models import DossierJuridique

    qs = dossiers_visibles(company, user=user)
    clos_valeurs = {str(s) for s in DossierJuridique.STATUTS_CLOS}
    ouverts = [d for d in qs if d.statut not in clos_valeurs]
    clos = [d for d in qs if d.statut in clos_valeurs]
    if debut or fin:
        bornes = []
        for dossier in clos:
            jour = dossier.updated_at.date() if dossier.updated_at else None
            if jour is None:
                continue
            if debut and jour < debut:
                continue
            if fin and jour > fin:
                continue
            bornes.append(dossier)
        clos = bornes

    montant_total = sum(
        (d.montant_en_jeu or Decimal('0') for d in ouverts), Decimal('0'))

    taux_gain = None
    if clos:
        gagnes = sum(
            1 for d in clos
            if d.statut == DossierJuridique.Statut.CLOS_GAGNE)
        taux_gain = round(gagnes * 100.0 / len(clos), 2)

    delai_moyen = None
    delais = [
        (d.updated_at.date() - d.date_ouverture).days
        for d in clos
        if d.updated_at and d.date_ouverture
    ]
    if delais:
        delai_moyen = round(sum(delais) / len(delais), 2)

    return {
        'juridique_dossiers_ouverts': len(ouverts),
        'juridique_montant_en_jeu_total': montant_total.quantize(
            Decimal('0.01')),
        'juridique_taux_gain': taux_gain,
        'juridique_delai_moyen_resolution': delai_moyen,
    }


# ── NTJUR20 — timeline unifiée du dossier ───────────────────────────────────


def timeline_dossier(dossier):
    """Frise chronologique UNIQUE du dossier (NTJUR20).

    Fusionne, triées par date décroissante, les quatre sources d'événements du
    dossier :

    * le CHATTER — ``records.Activity`` (ARC8, chatter générique du dépôt ;
      le plan parlait d'un ``DossierJuridiqueActivity`` maison, interdit par
      la garde ``check_platform`` qui gèle les 13 modèles ``*Activity``
      existants — on consomme donc le chatter générique au lieu d'en créer un
      quatorzième) ;
    * les AUDIENCES (NTJUR5) ;
    * les DÉLAIS de prescription (NTJUR4) ;
    * les NOTES D'HONORAIRES (NTJUR11).

    L'écran n'a ainsi qu'UN appel à faire : aucune reconstruction de frise
    côté frontend, donc aucune divergence de tri entre deux écrans.
    """
    from apps.records.services import chatter_qs

    from .models import Audience, DelaiPrescription, NoteHonoraires

    evenements = []
    for activite in chatter_qs(dossier, company=dossier.company):
        evenements.append({
            'type': 'chatter',
            'id': activite.id,
            'date': activite.created_at.date().isoformat(),
            'horodatage': activite.created_at.isoformat(),
            'libelle': (activite.body or '').strip()
            or f'{activite.old_value} → {activite.new_value}',
            'detail': activite.field_label or activite.field or '',
            'auteur': getattr(activite.created_by, 'username', '') or '',
        })
    for audience in Audience.objects.filter(dossier=dossier):
        evenements.append({
            'type': 'audience',
            'id': audience.id,
            'date': audience.date_audience.isoformat(),
            'horodatage': f'{audience.date_audience.isoformat()}T00:00:00',
            'libelle': audience.get_type_audience_display(),
            'detail': audience.get_statut_display(),
            'auteur': '',
        })
    for delai in DelaiPrescription.objects.filter(dossier=dossier):
        evenements.append({
            'type': 'delai',
            'id': delai.id,
            'date': delai.date_limite.isoformat(),
            'horodatage': f'{delai.date_limite.isoformat()}T00:00:00',
            'libelle': delai.get_type_delai_display(),
            'detail': delai.get_statut_display(),
            'auteur': '',
        })
    for note in NoteHonoraires.objects.filter(mandat__dossier=dossier):
        evenements.append({
            'type': 'note_honoraires',
            'id': note.id,
            'date': note.date_facture.isoformat(),
            'horodatage': f'{note.date_facture.isoformat()}T00:00:00',
            'libelle': note.reference or f'Note {note.id}',
            'detail': note.get_statut_display(),
            'auteur': '',
        })
    # Tri chronologique DÉCROISSANT (le plus récent d'abord), départage stable
    # par type puis id pour que deux chargements donnent le même ordre.
    evenements.sort(
        key=lambda e: (e['horodatage'], e['type'], e['id']), reverse=True)
    return evenements


# ── NTJUR19 — résolution de la règle d'approbation d'un engagement ──────────


def regles_approbation_actives(company):
    """Règles d'approbation juridique ACTIVES de la société."""
    from .models import RegleApprobationJuridique

    return RegleApprobationJuridique.objects.filter(
        company=company, actif=True)


def resoudre_regle_approbation_mandat(company, montant, nature_dossier=None):
    """Règle la plus SPÉCIFIQUE couvrant (montant, nature), ou ``None``.

    Spécificité, dans l'ordre (patron ``contrats.selectors``) :
    1. une règle ciblant une nature précise prime sur « toutes natures » ;
    2. à ce niveau égal, l'intervalle de montant BORNÉ le plus étroit prime ;
    3. puis ``priorite`` (plus grande d'abord), puis l'``id`` le plus récent.

    Aucun seuil codé en dur : tout vient des règles en base. ``None`` signifie
    « aucune approbation requise » — l'appelant peut activer directement.
    """
    candidates = [
        r for r in regles_approbation_actives(company)
        if r.couvre(montant, nature_dossier)
    ]
    if not candidates:
        return None

    def _cle(regle):
        nature_specifique = 1 if regle.nature_dossier else 0
        largeur = regle.largeur_intervalle()
        intervalle_borne = 1 if largeur is not None else 0
        largeur_tri = -largeur if largeur is not None else 0
        return (nature_specifique, intervalle_borne, largeur_tri,
                regle.priorite, regle.id)

    candidates.sort(key=_cle, reverse=True)
    return candidates[0]
