"""Services du registre des assurances & sinistres d'entreprise (NTASS).

Point d'entrée des ORCHESTRATIONS d'écriture (chatter auto-log, échéancier de
primes, propositions d'écritures comptables via ``compta.services`` — jamais
un import direct de ``compta.models``)."""
import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError

from .models import (
    ActifCouvert, DeclarationSinistre, EcheancePrime, GarantiePolice,
    IndemnisationSinistre, PoliceActivity, PoliceAssurance, SinistreActivity,
)

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


# ── NTASS9 — Renouvellement de police (versioning léger) ───────────────────

def _numero_police_renouvelee(ancienne, nouveau_numero_police=None):
    """Détermine le ``numero_police`` de la police renouvelée : celui fourni
    explicitement (nouveau numéro émis par l'assureur), sinon un suffixe
    ``-R<n>`` sur l'ancien (en évitant toute collision company+numéro)."""
    if nouveau_numero_police:
        return nouveau_numero_police
    base = ancienne.numero_police
    n = 1
    while True:
        candidat = f'{base}-R{n}'
        if not PoliceAssurance.objects.filter(
                company=ancienne.company, numero_police=candidat).exists():
            return candidat
        n += 1


def renouveler_police(police, *, user=None, periodicite=None,
                      nouveau_numero_police=None):
    """NTASS9 — renouvelle une police à ``tacite_reconduction=False`` :

    - crée une NOUVELLE ``PoliceAssurance`` (``date_effet`` = ancienne
      ``date_echeance`` + 1 jour, même durée de couverture que l'ancienne) ;
    - régénère son échéancier de primes (NTASS5) ;
    - copie ses garanties (NTASS4) et ses actifs couverts (NTASS7) ;
    - passe l'ANCIENNE police à ``statut='resiliee'`` (loggé au chatter,
      NTASS3) avec le lien ``police_precedente_id`` posé sur la nouvelle.

    Une police à tacite reconduction ne passe PAS par ce chemin (son
    échéance avance simplement sur la MÊME police) : lève ``ValidationError``.
    """
    if police.tacite_reconduction:
        raise ValidationError(
            'Une police à tacite reconduction ne se renouvelle pas via '
            'cette action — mettez à jour sa date d\'échéance directement.')

    duree = police.date_echeance - police.date_effet
    nouvelle_date_effet = police.date_echeance + datetime.timedelta(days=1)
    nouvelle_date_echeance = nouvelle_date_effet + duree

    nouvelle = PoliceAssurance.objects.create(
        company=police.company, assureur=police.assureur,
        courtier=police.courtier,
        numero_police=_numero_police_renouvelee(police, nouveau_numero_police),
        type_police=police.type_police, libelle=police.libelle,
        date_effet=nouvelle_date_effet, date_echeance=nouvelle_date_echeance,
        tacite_reconduction=police.tacite_reconduction,
        prime_annuelle_ht=police.prime_annuelle_ht,
        statut=PoliceAssurance.Statut.ACTIVE,
        police_precedente=police,
    )
    log_police_creation(nouvelle, user)

    # Échéancier de primes — même périodicité que la dernière échéance
    # connue de l'ancienne police (défaut annuelle si aucune n'existe).
    if periodicite is None:
        derniere = police.echeances_prime.order_by('-date_echeance_paiement').first()
        periodicite = (
            derniere.periodicite if derniere
            else EcheancePrime.Periodicite.ANNUELLE)
    generer_echeancier_prime(nouvelle, periodicite)

    # Copie des garanties (NTASS4).
    for garantie in police.garanties.all():
        GarantiePolice.objects.create(
            company=nouvelle.company, police=nouvelle,
            libelle_garantie=garantie.libelle_garantie,
            plafond_indemnisation=garantie.plafond_indemnisation,
            franchise_montant=garantie.franchise_montant,
            franchise_pourcentage=garantie.franchise_pourcentage,
            notes=garantie.notes)

    # Copie des actifs couverts (NTASS7).
    for actif in police.actifs_couverts.all():
        ActifCouvert.objects.create(
            company=nouvelle.company, police=nouvelle,
            type_actif=actif.type_actif, actif_ref=actif.actif_ref,
            actif_libelle=actif.actif_libelle)

    # Ancienne police → résiliée, loggée au chatter (NTASS3).
    ancien_statut = police.statut
    police.statut = PoliceAssurance.Statut.RESILIEE
    police.save(update_fields=['statut'])
    log_police_transition(
        police, 'statut', 'Statut', ancien_statut,
        PoliceAssurance.Statut.RESILIEE, user)

    return nouvelle


# ── NTASS11 — Chatter DeclarationSinistre ───────────────────────────────────

#: Champs de ``DeclarationSinistre`` dont la transition est auto-loggée.
CHAMPS_SUIVIS_SINISTRE = {
    'statut': 'Statut',
}


def log_sinistre_creation(declaration, user):
    """Journalise la création d'une déclaration de sinistre (NTASS11)."""
    return SinistreActivity.objects.create(
        company=declaration.company, declaration=declaration,
        kind=SinistreActivity.Kind.CREATION, user=user)


def log_sinistre_transition(declaration, champ, champ_label, ancienne_valeur,
                            nouvelle_valeur, user):
    """Journalise un changement de champ suivi (NTASS11)."""
    return SinistreActivity.objects.create(
        company=declaration.company, declaration=declaration,
        kind=SinistreActivity.Kind.MODIFICATION,
        champ=champ, champ_label=champ_label,
        ancienne_valeur='' if ancienne_valeur is None else str(ancienne_valeur),
        nouvelle_valeur='' if nouvelle_valeur is None else str(nouvelle_valeur),
        user=user)


def log_sinistre_transitions_auto(declaration, valeurs_avant, user):
    """Compare l'état AVANT à l'état COURANT de ``declaration`` et loggue une
    entrée par champ suivi (``CHAMPS_SUIVIS_SINISTRE``) modifié (NTASS11)."""
    entrees = []
    for champ, label in CHAMPS_SUIVIS_SINISTRE.items():
        avant = valeurs_avant.get(champ)
        apres = getattr(declaration, champ)
        if avant != apres:
            entrees.append(log_sinistre_transition(
                declaration, champ, label, avant, apres, user))
    return entrees


def log_sinistre_note(declaration, user, body):
    """Ajoute une note manuelle au chatter d'un sinistre (NTASS11)."""
    return SinistreActivity.objects.create(
        company=declaration.company, declaration=declaration,
        kind=SinistreActivity.Kind.NOTE, description=body, user=user)


# ── NTASS12 — Suivi d'indemnisation vs franchise ────────────────────────────

def enregistrer_indemnisation(declaration, *, montant_reclame,
                              montant_indemnise, franchise_appliquee=None,
                              date_versement=None, garantie_id=None, user=None):
    """NTASS12 — pose (ou met à jour) l'indemnisation d'une déclaration de
    sinistre et fait passer son statut à ``indemnise``.

    ``franchise_appliquee`` : si non fournie explicitement, COPIÉE (snapshot)
    depuis la ``GarantiePolice`` désignée par ``garantie_id`` (sinon la
    première garantie de la police, sinon 0) — jamais une FK vivante."""
    if franchise_appliquee is None:
        garantie = None
        if garantie_id is not None:
            garantie = GarantiePolice.objects.filter(
                id=garantie_id, police=declaration.police).first()
        if garantie is None:
            garantie = declaration.police.garanties.first()
        franchise_appliquee = garantie.franchise_montant if garantie else 0

    indemnisation, _ = IndemnisationSinistre.objects.update_or_create(
        declaration=declaration,
        defaults={
            'company': declaration.company,
            'montant_reclame': montant_reclame,
            'franchise_appliquee': franchise_appliquee,
            'montant_indemnise': montant_indemnise,
            'date_versement': date_versement,
        })

    ancien_statut = declaration.statut
    declaration.statut = DeclarationSinistre.Statut.INDEMNISE
    declaration.save(update_fields=['statut'])
    if ancien_statut != declaration.statut:
        log_sinistre_transition(
            declaration, 'statut', 'Statut', ancien_statut,
            declaration.statut, user)
    return indemnisation
