"""Services du registre des assurances & sinistres d'entreprise (NTASS).

Point d'entrée des ORCHESTRATIONS d'écriture (chatter auto-log, échéancier de
primes, propositions d'écritures comptables via ``compta.services`` — jamais
un import direct de ``compta.models``)."""
import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal

from .models import EcheancePrime, PoliceActivity

# ── NTASS3 — Chatter PoliceAssurance ────────────────────────────────────────

#: Champs de ``PoliceAssurance`` dont la transition est auto-loggée (NTASS3).
CHAMPS_SUIVIS_POLICE = {
    'statut': 'Statut',
    'date_echeance': "Date d'échéance",
    'prime_annuelle_ht': 'Prime annuelle HT',
}


def log_police_creation(police, user):
    """Journalise la création d'une police (entrée ``creation``)."""
    return PoliceActivity.objects.create(
        company=police.company, police=police,
        kind=PoliceActivity.Kind.CREATION, user=user)


def log_police_transition(police, champ, champ_label, ancienne_valeur,
                          nouvelle_valeur, user):
    """Journalise un changement de champ suivi (NTASS3)."""
    return PoliceActivity.objects.create(
        company=police.company, police=police,
        kind=PoliceActivity.Kind.MODIFICATION,
        champ=champ, champ_label=champ_label,
        ancienne_valeur='' if ancienne_valeur is None else str(ancienne_valeur),
        nouvelle_valeur='' if nouvelle_valeur is None else str(nouvelle_valeur),
        user=user)


def log_police_transitions_auto(police, valeurs_avant, user):
    """Compare l'état AVANT (``valeurs_avant``, dict champ→valeur capturé avant
    la sauvegarde) à l'état COURANT de ``police`` et loggue une entrée par
    champ suivi (``CHAMPS_SUIVIS_POLICE``) dont la valeur a changé."""
    entrees = []
    for champ, label in CHAMPS_SUIVIS_POLICE.items():
        avant = valeurs_avant.get(champ)
        apres = getattr(police, champ)
        if avant != apres:
            entrees.append(log_police_transition(
                police, champ, label, avant, apres, user))
    return entrees


def log_police_note(police, user, body):
    """Ajoute une note manuelle au chatter d'une police (NTASS3)."""
    return PoliceActivity.objects.create(
        company=police.company, police=police,
        kind=PoliceActivity.Kind.NOTE, description=body, user=user)


# ── NTASS5 — Échéancier de primes ───────────────────────────────────────────

#: Nombre d'échéances par an pour chaque périodicité (NTASS5).
_ECHEANCES_PAR_AN = {
    EcheancePrime.Periodicite.ANNUELLE: 1,
    EcheancePrime.Periodicite.SEMESTRIELLE: 2,
    EcheancePrime.Periodicite.TRIMESTRIELLE: 4,
    EcheancePrime.Periodicite.MENSUELLE: 12,
}


def _ajouter_mois(date, n):
    """Ajoute ``n`` mois à ``date`` (calendaire pur, sans dépendance externe) ;
    borne le jour au dernier jour du mois cible si dépassement (ex. 31 jan +1
    mois → 28/29 fév)."""
    mois_total = date.month - 1 + n
    annee = date.year + mois_total // 12
    mois = mois_total % 12 + 1
    jour = min(date.day, calendar.monthrange(annee, mois)[1])
    return datetime.date(annee, mois, jour)


def generer_echeancier_prime(police, periodicite):
    """Découpe ``police.prime_annuelle_ht`` en échéances datées (NTASS5).

    Le nombre d'échéances est dérivé de ``periodicite`` (1/2/4/12 par an) ; la
    première échéance tombe à ``police.date_effet``, les suivantes espacées de
    12/N mois. Chaque échéance porte ``montant = prime_annuelle_ht / N``
    (arrondi 2 décimales, le dernier montant absorbe le reliquat d'arrondi pour
    que la somme reste EXACTEMENT ``prime_annuelle_ht``). Idempotent au sens
    « appel explicite » : n'efface PAS un échéancier existant — l'appelant
    (création/renouvellement de police, NTASS9) décide quand régénérer."""
    n = _ECHEANCES_PAR_AN[periodicite]
    interval_mois = 12 // n
    montant_unitaire = (police.prime_annuelle_ht / n).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    echeances = []
    total_pose = Decimal('0.00')
    for i in range(n):
        date_echeance = _ajouter_mois(police.date_effet, i * interval_mois)
        if i == n - 1:
            montant = police.prime_annuelle_ht - total_pose
        else:
            montant = montant_unitaire
            total_pose += montant
        echeances.append(EcheancePrime.objects.create(
            company=police.company, police=police,
            date_echeance_paiement=date_echeance, montant=montant,
            periodicite=periodicite))
    return echeances


# ── NTASS6 — Proposition d'écriture comptable sur échéance de prime ────────

#: Compte CGNC charge assurances (ajouté à ``compta.services._COMPTES_CGNC``).
_COMPTE_CHARGE_ASSURANCE = '6134'
#: Compte CGNC fournisseurs (contrepartie — la prime n'est pas encore payée).
_COMPTE_FOURNISSEUR_ASSURANCE = '4411'


def proposer_ecriture_prime(echeance, *, user=None):
    """NTASS6 — PROPOSE (brouillon) l'écriture comptable d'une échéance de
    prime : débite le compte charge « Assurances » (6134), crédite le compte
    fournisseurs (4411, contrepartie — la prime n'est pas encore réglée).

    Écrit UNIQUEMENT via ``compta.services`` (jamais ``compta.models``
    directement, CLAUDE.md règle de modularité cross-app) : le verrouillage de
    période est délégué à ``creer_ecriture_od`` (refuse une date dans une
    période clôturée, FG115) — l'écriture est TOUJOURS créée en ``brouillon``,
    jamais auto-postée (override explicite du défaut ``VALIDEE`` de
    ``creer_ecriture_od``). Lie ``echeance.ecriture_ref`` et passe son statut
    à ``proposee_compta``."""
    from apps.compta import services as compta_services  # cross-app WRITE
    from apps.compta.models import EcritureComptable

    company = echeance.company
    requis = [_COMPTE_CHARGE_ASSURANCE, _COMPTE_FOURNISSEUR_ASSURANCE]
    if any(compta_services.get_compte(company, num) is None for num in requis):
        compta_services.seed_plan_comptable(company)
    compte_charge = compta_services.get_compte(company, _COMPTE_CHARGE_ASSURANCE)
    compte_fournisseur = compta_services.get_compte(
        company, _COMPTE_FOURNISSEUR_ASSURANCE)

    police = echeance.police
    libelle = (
        f'Prime assurance {police.numero_police} — échéance '
        f'{echeance.date_echeance_paiement}')
    ecriture = compta_services.creer_ecriture_od(
        company, echeance.date_echeance_paiement, libelle,
        [
            {'compte': compte_charge, 'libelle': libelle,
             'debit': echeance.montant, 'credit': 0},
            {'compte': compte_fournisseur, 'libelle': libelle,
             'debit': 0, 'credit': echeance.montant},
        ],
        reference=f'PRIME-{police.numero_police}',
        created_by=user,
        # NTASS6 — jamais auto-postée : override du défaut VALIDEE de
        # creer_ecriture_od.
        statut=EcritureComptable.Statut.BROUILLON,
    )
    echeance.ecriture_ref = ecriture.id
    echeance.statut = EcheancePrime.Statut.PROPOSEE_COMPTA
    echeance.save(update_fields=['ecriture_ref', 'statut'])
    return ecriture
