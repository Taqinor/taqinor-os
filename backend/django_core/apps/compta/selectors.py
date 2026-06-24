"""Sélecteurs LECTURE SEULE de la Comptabilité générale (états & restitutions).

Grand livre (FG110), balance générale (FG111), lettrage (FG112), CPC (FG113) et
bilan (FG114) se déduisent tous des ``LigneEcriture`` du grand livre. Aucune
écriture n'est modifiée ici. Toutes les fonctions sont scopées par société.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import (
    BonCommandeFournisseur, Caisse, CompteComptable, CompteTresorerie, Effet,
    FactureFournisseur, LigneEcriture, LignePrevisionnelTresorerie,
    MouvementCaisse, Rapprochement3Voies, ReceptionMarchandise,
)


def _lignes_qs(company, *, date_debut=None, date_fin=None, validees_seulement=False):
    qs = LigneEcriture.objects.filter(company=company).select_related(
        'compte', 'ecriture')
    if date_debut:
        qs = qs.filter(ecriture__date_ecriture__gte=date_debut)
    if date_fin:
        qs = qs.filter(ecriture__date_ecriture__lte=date_fin)
    if validees_seulement:
        qs = qs.filter(ecriture__statut='validee')
    return qs


# ── FG110 / COMPTA19 — Grand livre ─────────────────────────────────────────

def grand_livre(company, *, compte=None, date_debut=None, date_fin=None,
                validees_seulement=False):
    """Détail des mouvements par compte avec solde courant cumulé.

    Renvoie une liste de dicts par compte :
    ``{'compte', 'numero', 'intitule', 'lignes': [...], 'total_debit',
    'total_credit', 'solde'}`` où chaque ligne porte un ``solde_courant`` cumulé.
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement).order_by(
        'compte__numero', 'ecriture__date_ecriture', 'id')
    if compte is not None:
        qs = qs.filter(compte=compte)
    resultat = {}
    soldes = {}
    for ligne in qs:
        num = ligne.compte.numero
        bucket = resultat.setdefault(num, {
            'compte_id': ligne.compte_id,
            'numero': num,
            'intitule': ligne.compte.intitule,
            'lignes': [],
            'total_debit': Decimal('0'),
            'total_credit': Decimal('0'),
        })
        solde = soldes.get(num, Decimal('0')) + ligne.debit - ligne.credit
        soldes[num] = solde
        bucket['total_debit'] += ligne.debit
        bucket['total_credit'] += ligne.credit
        bucket['lignes'].append({
            'date': ligne.ecriture.date_ecriture,
            'journal': ligne.ecriture.journal.code,
            'reference': ligne.ecriture.reference,
            'libelle': ligne.libelle or ligne.ecriture.libelle,
            'debit': ligne.debit,
            'credit': ligne.credit,
            'lettrage': ligne.lettrage,
            'solde_courant': solde,
        })
    for bucket in resultat.values():
        bucket['solde'] = bucket['total_debit'] - bucket['total_credit']
    return sorted(resultat.values(), key=lambda b: b['numero'])


# ── FG111 / COMPTA20 — Balance générale (trial balance) ────────────────────

def balance_generale(company, *, date_debut=None, date_fin=None,
                     validees_seulement=False):
    """Débit/crédit/solde par compte sur une période (≠ balance âgée clients).

    Renvoie une liste de dicts triée par numéro + des totaux globaux. La somme
    des débits doit égaler la somme des crédits (le grand livre est équilibré).
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement)
    agg = qs.values(
        'compte__numero', 'compte__intitule', 'compte__classe',
    ).annotate(
        debit=Sum('debit'), credit=Sum('credit'),
    ).order_by('compte__numero')
    lignes = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for row in agg:
        debit = row['debit'] or Decimal('0')
        credit = row['credit'] or Decimal('0')
        solde = debit - credit
        total_debit += debit
        total_credit += credit
        lignes.append({
            'numero': row['compte__numero'],
            'intitule': row['compte__intitule'],
            'classe': row['compte__classe'],
            'debit': debit,
            'credit': credit,
            'solde_debiteur': solde if solde > 0 else Decimal('0'),
            'solde_crediteur': -solde if solde < 0 else Decimal('0'),
        })
    return {
        'lignes': lignes,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'equilibree': total_debit == total_credit,
    }


# ── FG112 / COMPTA22 — Lettrage / encours par tiers ────────────────────────

def lignes_non_lettrees(company, compte):
    """Lignes non lettrées d'un compte lettrable (factures/règlements ouverts).

    Sert au lettrage manuel et au calcul de l'encours exact d'un tiers.
    """
    return list(
        LigneEcriture.objects.filter(
            company=company, compte=compte, lettrage='',
        ).select_related('ecriture').order_by('ecriture__date_ecriture', 'id'))


def encours_tiers(company, compte):
    """Encours (solde non lettré) d'un compte de tiers lettrable.

    Σ(débit) − Σ(crédit) des seules lignes NON lettrées : ce qui reste dû/à
    régler après appariement.
    """
    agg = LigneEcriture.objects.filter(
        company=company, compte=compte, lettrage='',
    ).aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0')) - (agg['credit'] or Decimal('0'))


def lettrer(company, ligne_ids, code):
    """Pose un code de lettrage sur un lot de lignes SSI elles s'équilibrent.

    Renvoie le nombre de lignes lettrées, ou lève ``ValueError`` si le lot ne
    solde pas (Σ débit ≠ Σ crédit) — on ne lettre jamais un appariement bancal.
    """
    qs = LigneEcriture.objects.filter(company=company, id__in=ligne_ids)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    debit = agg['debit'] or Decimal('0')
    credit = agg['credit'] or Decimal('0')
    if debit != credit:
        raise ValueError(
            f"Lettrage impossible : Σ débit ({debit}) ≠ Σ crédit ({credit}).")
    return qs.update(lettrage=code)


# ── FG113 / COMPTA27 — CPC (Compte de Produits et Charges) ─────────────────

def cpc(company, *, date_debut=None, date_fin=None, validees_seulement=False):
    """État de résultat (CPC) : produits (classe 7) − charges (classe 6).

    Renvoie ``{'produits', 'total_produits', 'charges', 'total_charges',
    'resultat'}``. Le résultat positif = bénéfice, négatif = perte.
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__classe__in=[6, 7])
    agg = qs.values(
        'compte__numero', 'compte__intitule', 'compte__classe',
    ).annotate(debit=Sum('debit'), credit=Sum('credit')).order_by(
        'compte__numero')
    produits, charges = [], []
    total_produits = Decimal('0')
    total_charges = Decimal('0')
    for row in agg:
        debit = row['debit'] or Decimal('0')
        credit = row['credit'] or Decimal('0')
        item = {
            'numero': row['compte__numero'],
            'intitule': row['compte__intitule'],
        }
        if row['compte__classe'] == 7:
            # Produit : solde créditeur.
            montant = credit - debit
            item['montant'] = montant
            total_produits += montant
            produits.append(item)
        else:
            # Charge : solde débiteur.
            montant = debit - credit
            item['montant'] = montant
            total_charges += montant
            charges.append(item)
    return {
        'produits': produits,
        'total_produits': total_produits,
        'charges': charges,
        'total_charges': total_charges,
        'resultat': total_produits - total_charges,
    }


# ── FG114 / COMPTA28 — Bilan (format CGNC) ─────────────────────────────────

def bilan(company, *, date_fin=None, validees_seulement=False):
    """Bilan : actif (classes 2,3,5) / passif (classes 1,4) depuis les soldes.

    Le résultat de l'exercice (CPC) est porté au passif pour équilibrer
    (équation comptable : Actif = Passif + Résultat). Renvoie
    ``{'actif', 'total_actif', 'passif', 'total_passif', 'resultat',
    'equilibre'}``.
    """
    qs = _lignes_qs(company, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__classe__in=[1, 2, 3, 4, 5])
    agg = qs.values(
        'compte__numero', 'compte__intitule', 'compte__classe',
    ).annotate(debit=Sum('debit'), credit=Sum('credit')).order_by(
        'compte__numero')
    actif, passif = [], []
    total_actif = Decimal('0')
    total_passif = Decimal('0')
    for row in agg:
        debit = row['debit'] or Decimal('0')
        credit = row['credit'] or Decimal('0')
        solde = debit - credit
        item = {
            'numero': row['compte__numero'],
            'intitule': row['compte__intitule'],
        }
        if row['compte__classe'] in (2, 3, 5):
            item['montant'] = solde
            total_actif += solde
            actif.append(item)
        else:
            item['montant'] = -solde
            total_passif += -solde
            passif.append(item)
    resultat = cpc(
        company, date_fin=date_fin,
        validees_seulement=validees_seulement)['resultat']
    return {
        'actif': actif,
        'total_actif': total_actif,
        'passif': passif,
        'total_passif': total_passif,
        'resultat': resultat,
        'equilibre': total_actif == (total_passif + resultat),
    }


# ── FG121 — Position de trésorerie depuis le grand livre ───────────────────

def solde_compte(company, compte, *, date_fin=None, validees_seulement=False):
    """Solde (débit − crédit) d'un compte à une date donnée."""
    qs = _lignes_qs(company, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(compte=compte)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0')) - (agg['credit'] or Decimal('0'))


def comptes_par_classe(company, classe):
    """Comptes d'une classe donnée (lecture seule, scopé société)."""
    return list(CompteComptable.objects.filter(
        company=company, classe=classe).order_by('numero'))


# ── FG122 — Position de trésorerie consolidée + projection nette ───────────

# Comptes CGNC dont les soldes alimentent la projection nette. Tout se déduit du
# grand livre de la compta elle-même (AUCUN import cross-app) : la facturation
# client/fournisseur, la paie et les impôts laissent leur trace sur ces comptes.
_COMPTE_CLIENTS = '3421'        # Clients — créances (AR), solde débiteur.
_COMPTE_FOURNISSEURS = '4411'   # Fournisseurs — dettes (AP), solde créditeur.
_COMPTES_TVA_DUE = ('4455', '44552')          # TVA collectée à reverser (passif).
_COMPTES_TVA_RECUP = ('3455', '34552')        # TVA récupérable (actif).
_COMPTES_PAIE = ('4432', '4441', '4443')      # Rémunérations/organismes/État dus.


def _solde_numero(company, numero, *, date_fin=None, validees_seulement=False):
    """Solde (débit − crédit) d'un compte par son numéro, 0 si compte absent."""
    compte = CompteComptable.objects.filter(
        company=company, numero=numero).first()
    if compte is None:
        return Decimal('0')
    return solde_compte(
        company, compte, date_fin=date_fin,
        validees_seulement=validees_seulement)


def _solde_groupe(company, numeros, *, date_fin=None, validees_seulement=False):
    """Solde net (Σ débit − Σ crédit) d'un groupe de comptes (par numéros)."""
    qs = _lignes_qs(company, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__numero__in=numeros)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0')) - (agg['credit'] or Decimal('0'))


def position_tresorerie(company, *, date_fin=None, validees_seulement=False):
    """Position de trésorerie consolidée : solde par compte/caisse + total.

    Pour chaque ``CompteTresorerie`` actif de la société, le solde courant =
    ``solde_initial`` + mouvements du grand livre sur son compte comptable
    (classe 5). Renvoie ``{'comptes': [...], 'total': Decimal}`` où chaque entrée
    porte ``{'id', 'libelle', 'type_compte', 'banque', 'devise', 'solde_initial',
    'mouvements', 'solde'}``. Lecture seule, scopée société.
    """
    comptes = []
    total = Decimal('0')
    treso_qs = CompteTresorerie.objects.filter(
        company=company, actif=True).select_related('compte_comptable').order_by(
        'type_compte', 'libelle')
    for treso in treso_qs:
        mouvements = solde_compte(
            company, treso.compte_comptable, date_fin=date_fin,
            validees_seulement=validees_seulement)
        solde = (treso.solde_initial or Decimal('0')) + mouvements
        total += solde
        comptes.append({
            'id': treso.id,
            'libelle': treso.libelle,
            'type_compte': treso.type_compte,
            'banque': treso.banque,
            'devise': treso.devise,
            'solde_initial': treso.solde_initial or Decimal('0'),
            'mouvements': mouvements,
            'solde': solde,
        })
    return {'comptes': comptes, 'total': total}


def projection_tresorerie(company, *, date_fin=None, validees_seulement=False):
    """Projection nette de trésorerie : position actuelle ± AR/AP/paie/impôts.

    Estimation pragmatique tirée des seuls soldes du grand livre de la compta
    (aucun import cross-app) : la trésorerie consolidée actuelle, augmentée des
    créances clients ouvertes (3421, débit) à encaisser, diminuée des dettes
    fournisseurs (4411, crédit), des dettes de paie & organismes sociaux/fiscaux
    (44xx) et de la TVA nette due (TVA collectée − TVA récupérable). Renvoie
    ``{'tresorerie_actuelle', 'creances_clients', 'dettes_fournisseurs',
    'dettes_paie', 'tva_nette', 'projection_nette'}``. Lecture seule, scopée
    société. C'est une PROJECTION indicative, pas une écriture.
    """
    position = position_tresorerie(
        company, date_fin=date_fin, validees_seulement=validees_seulement)
    tresorerie = position['total']

    # AR : solde débiteur du compte clients (positif = à encaisser).
    solde_clients = _solde_numero(
        company, _COMPTE_CLIENTS, date_fin=date_fin,
        validees_seulement=validees_seulement)
    creances = solde_clients if solde_clients > 0 else Decimal('0')

    # AP : solde créditeur du compte fournisseurs (positif = à payer).
    solde_fournisseurs = _solde_groupe(
        company, [_COMPTE_FOURNISSEURS], date_fin=date_fin,
        validees_seulement=validees_seulement)
    dettes_fourn = -solde_fournisseurs if solde_fournisseurs < 0 else Decimal('0')

    # Paie & organismes : soldes créditeurs (dettes) sur les comptes 44xx.
    solde_paie = _solde_groupe(
        company, _COMPTES_PAIE, date_fin=date_fin,
        validees_seulement=validees_seulement)
    dettes_paie = -solde_paie if solde_paie < 0 else Decimal('0')

    # TVA nette due = TVA collectée (passif) − TVA récupérable (actif).
    tva_due = _solde_groupe(
        company, _COMPTES_TVA_DUE, date_fin=date_fin,
        validees_seulement=validees_seulement)
    tva_recup = _solde_groupe(
        company, _COMPTES_TVA_RECUP, date_fin=date_fin,
        validees_seulement=validees_seulement)
    # TVA due : passif → solde créditeur (négatif) ; on prend sa valeur absolue.
    tva_collectee = -tva_due if tva_due < 0 else Decimal('0')
    # TVA récupérable : actif → solde débiteur (positif).
    tva_recuperable = tva_recup if tva_recup > 0 else Decimal('0')
    tva_nette = tva_collectee - tva_recuperable
    if tva_nette < 0:
        tva_nette = Decimal('0')

    projection = tresorerie + creances - dettes_fourn - dettes_paie - tva_nette
    return {
        'tresorerie_actuelle': tresorerie,
        'creances_clients': creances,
        'dettes_fournisseurs': dettes_fourn,
        'dettes_paie': dettes_paie,
        'tva_nette': tva_nette,
        'projection_nette': projection,
    }


# ── FG123 — Rapprochement bancaire (relevé ↔ écritures) ────────────────────

def solde_gl_compte_tresorerie(rapprochement):
    """Solde GL d'un compte de trésorerie à la fin de la période rapprochée.

    ``solde_initial`` du ``CompteTresorerie`` + mouvements du grand livre sur son
    compte comptable (classe 5) jusqu'à ``date_fin`` du rapprochement. Lecture
    seule, scopée société.
    """
    treso = rapprochement.compte_tresorerie
    mouvements = solde_compte(
        rapprochement.company, treso.compte_comptable,
        date_fin=rapprochement.date_fin)
    return (treso.solde_initial or Decimal('0')) + mouvements


def lignes_gl_pointables(rapprochement):
    """Lignes du grand livre du compte de trésorerie sur la période (FG123).

    Restitue les ``LigneEcriture`` du compte comptable (classe 5) du compte de
    trésorerie dont l'écriture tombe dans ``[date_debut ; date_fin]``, avec un
    drapeau ``pointee`` indiquant si la ligne est déjà appariée dans CE
    rapprochement. Sert à présenter le côté GL face au relevé. Lecture seule.
    """
    from .models import LigneReleve

    treso = rapprochement.compte_tresorerie
    qs = LigneEcriture.objects.filter(
        company=rapprochement.company,
        compte=treso.compte_comptable,
        ecriture__date_ecriture__gte=rapprochement.date_debut,
        ecriture__date_ecriture__lte=rapprochement.date_fin,
    ).select_related('ecriture', 'ecriture__journal').order_by(
        'ecriture__date_ecriture', 'id')
    # IDs des lignes GL déjà pointées dans ce rapprochement.
    pointees = set(
        LigneReleve.objects.filter(rapprochement=rapprochement).values_list(
            'lignes_gl__id', flat=True))
    resultat = []
    for ligne in qs:
        resultat.append({
            'id': ligne.id,
            'date': ligne.ecriture.date_ecriture,
            'journal': ligne.ecriture.journal.code,
            'reference': ligne.ecriture.reference,
            'libelle': ligne.libelle or ligne.ecriture.libelle,
            'debit': ligne.debit,
            'credit': ligne.credit,
            'montant': (ligne.debit or Decimal('0')) - (
                ligne.credit or Decimal('0')),
            'pointee': ligne.id in pointees,
        })
    return resultat


def resume_rapprochement(rapprochement):
    """Synthèse d'un rapprochement : solde relevé vs solde GL vs écart (FG123).

    Renvoie ``{'solde_releve', 'solde_gl', 'ecart', 'lignes_total',
    'lignes_pointees', 'lignes_non_pointees', 'montant_pointe',
    'montant_non_pointe', 'statut', 'rapproche'}``. Le ``solde_gl`` se déduit du
    grand livre, l'``ecart`` global = solde relevé − solde GL ; ``rapproche`` est
    vrai quand chaque ligne de relevé est concordante (écart nul) et que l'écart
    global est nul. Lecture seule, scopée société.
    """
    lignes = list(
        rapprochement.lignes_releve.all().prefetch_related('lignes_gl'))
    solde_gl = solde_gl_compte_tresorerie(rapprochement)
    solde_releve = rapprochement.solde_releve or Decimal('0')
    montant_pointe = Decimal('0')
    montant_non_pointe = Decimal('0')
    lignes_pointees = 0
    lignes_non_pointees = 0
    toutes_concordantes = True
    for ligne in lignes:
        if ligne.est_concordante:
            lignes_pointees += 1
            montant_pointe += ligne.montant or Decimal('0')
        else:
            lignes_non_pointees += 1
            montant_non_pointe += ligne.montant or Decimal('0')
            toutes_concordantes = False
    ecart = solde_releve - solde_gl
    rapproche = (
        bool(lignes) and toutes_concordantes and ecart == Decimal('0'))
    return {
        'solde_releve': solde_releve,
        'solde_gl': solde_gl,
        'ecart': ecart,
        'lignes_total': len(lignes),
        'lignes_pointees': lignes_pointees,
        'lignes_non_pointees': lignes_non_pointees,
        'montant_pointe': montant_pointe,
        'montant_non_pointe': montant_non_pointe,
        'statut': rapprochement.statut,
        'rapproche': rapproche,
    }


# ── FG124 — Caisse / petty cash (journal d'espèces) ────────────────────────

def solde_caisse_a(caisse, *, date_fin=None):
    """Solde théorique d'une caisse (solde initial + entrées − sorties).

    = ``solde_initial`` + Σ(entrées) − Σ(sorties) jusqu'à ``date_fin`` (incluse)
    si fournie. Lecture seule, identique au calcul du service ``solde_caisse``.
    """
    qs = MouvementCaisse.objects.filter(caisse=caisse)
    if date_fin is not None:
        qs = qs.filter(date_mouvement__lte=date_fin)
    entrees = qs.filter(sens=MouvementCaisse.Sens.ENTREE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    sorties = qs.filter(sens=MouvementCaisse.Sens.SORTIE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    return (caisse.solde_initial or Decimal('0')) + entrees - sorties


def journal_caisse(caisse, *, date_debut=None, date_fin=None):
    """Journal d'espèces d'une caisse : mouvements + solde courant cumulé (FG124).

    Renvoie une liste de dicts ordonnée par date puis id, chaque entrée portant
    ``{'id', 'date', 'sens', 'montant', 'montant_signe', 'motif',
    'justificatif', 'piece', 'posted', 'solde_courant'}`` où ``solde_courant``
    est le solde cumulé APRÈS le mouvement (en partant du solde initial). Lecture
    seule, scopée à la caisse.
    """
    qs = MouvementCaisse.objects.filter(caisse=caisse).order_by(
        'date_mouvement', 'id')
    if date_debut is not None:
        qs = qs.filter(date_mouvement__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_mouvement__lte=date_fin)
    solde = caisse.solde_initial or Decimal('0')
    lignes = []
    for mvt in qs:
        solde += mvt.montant_signe
        lignes.append({
            'id': mvt.id,
            'date': mvt.date_mouvement,
            'sens': mvt.sens,
            'montant': mvt.montant,
            'montant_signe': mvt.montant_signe,
            'motif': mvt.motif,
            'justificatif': mvt.justificatif,
            'piece': mvt.piece,
            'posted': mvt.posted,
            'solde_courant': solde,
        })
    return lignes


def resume_caisse(caisse, *, date_fin=None):
    """Synthèse d'une caisse : solde initial, entrées, sorties, solde courant.

    Renvoie ``{'solde_initial', 'total_entrees', 'total_sorties',
    'nb_mouvements', 'solde_courant', 'derniere_cloture'}`` jusqu'à ``date_fin``
    (incluse) si fournie. ``derniere_cloture`` porte la date et l'écart de la
    dernière clôture (ou None). Lecture seule.
    """
    qs = MouvementCaisse.objects.filter(caisse=caisse)
    if date_fin is not None:
        qs = qs.filter(date_mouvement__lte=date_fin)
    total_entrees = qs.filter(sens=MouvementCaisse.Sens.ENTREE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    total_sorties = qs.filter(sens=MouvementCaisse.Sens.SORTIE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    solde_initial = caisse.solde_initial or Decimal('0')
    derniere = caisse.clotures.order_by('-date_cloture', '-id').first()
    return {
        'solde_initial': solde_initial,
        'total_entrees': total_entrees,
        'total_sorties': total_sorties,
        'nb_mouvements': qs.count(),
        'solde_courant': solde_initial + total_entrees - total_sorties,
        'derniere_cloture': (
            {'date_cloture': derniere.date_cloture, 'ecart': derniere.ecart}
            if derniere is not None else None),
    }


def caisses_de(company):
    """Caisses actives d'une société (lecture seule, scopée société)."""
    return list(Caisse.objects.filter(company=company).select_related(
        'compte_tresorerie').order_by('libelle'))


# ── FG126 — Prévisionnel de trésorerie roulant 13 semaines ─────────────────

def previsionnel_tresorerie(company, *, date_debut=None, nb_semaines=13):
    """Prévisionnel de trésorerie roulant sur ``nb_semaines`` semaines (FG126).

    Construit une projection SEMAINE PAR SEMAINE en partant de la position de
    trésorerie consolidée actuelle (selon le grand livre) et en y empilant, pour
    chaque semaine, les ``LignePrevisionnelTresorerie`` prévues qui y tombent
    (montant signé : + encaissement, − décaissement) PLUS les effets ouverts
    (FG127/FG128) dont l'échéance tombe dans la semaine (effets à recevoir → +,
    à payer → −). Renvoie ``{'solde_initial', 'date_debut', 'semaines': [...]}``
    où chaque semaine porte ``{'index', 'date_debut', 'date_fin', 'entrees',
    'sorties', 'flux_net', 'solde_fin', 'lignes': [...]}``. Lecture seule.
    """
    debut = date_debut or timezone.localdate()
    # Cale le début sur le lundi de la semaine de ``debut``.
    debut = debut - timedelta(days=debut.weekday())
    position = position_tresorerie(company)
    solde = position['total']
    solde_initial = solde

    fin_horizon = debut + timedelta(weeks=nb_semaines)
    lignes_prev = list(LignePrevisionnelTresorerie.objects.filter(
        company=company, date_prevue__gte=debut,
        date_prevue__lt=fin_horizon).order_by('date_prevue', 'id'))
    effets = list(Effet.objects.filter(
        company=company, date_echeance__gte=debut,
        date_echeance__lt=fin_horizon,
        statut__in=[Effet.Statut.PORTEFEUILLE, Effet.Statut.REMIS]
    ).order_by('date_echeance', 'id'))

    semaines = []
    for i in range(nb_semaines):
        s_debut = debut + timedelta(weeks=i)
        s_fin = s_debut + timedelta(days=6)
        entrees = Decimal('0')
        sorties = Decimal('0')
        lignes = []
        for lp in lignes_prev:
            if s_debut <= lp.date_prevue <= s_fin:
                montant = lp.montant or Decimal('0')
                if montant >= 0:
                    entrees += montant
                else:
                    sorties += -montant
                lignes.append({
                    'type': 'prevu',
                    'libelle': lp.libelle,
                    'categorie': lp.categorie,
                    'date': lp.date_prevue,
                    'montant': montant,
                })
        for ef in effets:
            if s_debut <= ef.date_echeance <= s_fin:
                montant = ef.montant or Decimal('0')
                if ef.sens == Effet.Sens.RECEVOIR:
                    entrees += montant
                    signe = montant
                else:
                    sorties += montant
                    signe = -montant
                lignes.append({
                    'type': 'effet',
                    'libelle': (ef.numero or ef.tireur
                                or ef.get_type_effet_display()),
                    'categorie': ef.sens,
                    'date': ef.date_echeance,
                    'montant': signe,
                })
        flux_net = entrees - sorties
        solde += flux_net
        semaines.append({
            'index': i + 1,
            'date_debut': s_debut,
            'date_fin': s_fin,
            'entrees': entrees,
            'sorties': sorties,
            'flux_net': flux_net,
            'solde_fin': solde,
            'lignes': lignes,
        })
    return {
        'solde_initial': solde_initial,
        'date_debut': debut,
        'nb_semaines': nb_semaines,
        'semaines': semaines,
    }


# ── FG127 / FG128 — Portefeuille d'effets (échéancier) ─────────────────────

def echeancier_effets(company, *, sens=None, statut=None):
    """Échéancier des effets (chèques/traites) de la société (FG127/FG128).

    Liste les ``Effet`` filtrés par ``sens`` (recevoir/payer) et/ou ``statut``,
    ordonnés par échéance. Renvoie une liste de dicts ; les effets OUVERTS (non
    soldés/rejetés) alimentent la trésorerie prévisionnelle. Lecture seule.
    """
    qs = Effet.objects.filter(company=company)
    if sens:
        qs = qs.filter(sens=sens)
    if statut:
        qs = qs.filter(statut=statut)
    qs = qs.order_by('date_echeance', 'id')
    resultats = []
    for ef in qs:
        resultats.append({
            'id': ef.id,
            'sens': ef.sens,
            'type_effet': ef.type_effet,
            'numero': ef.numero,
            'montant': ef.montant,
            'date_emission': ef.date_emission,
            'date_echeance': ef.date_echeance,
            'banque': ef.banque,
            'tireur': ef.tireur,
            'statut': ef.statut,
            'frais_rejet': ef.frais_rejet,
            'bordereau_id': ef.bordereau_id,
        })
    return resultats


def total_effets_ouverts(company, *, sens):
    """Total des montants des effets OUVERTS d'un sens (portefeuille+remis)."""
    total = Effet.objects.filter(
        company=company, sens=sens,
        statut__in=[Effet.Statut.PORTEFEUILLE, Effet.Statut.REMIS]
    ).aggregate(s=Sum('montant'))['s']
    return total or Decimal('0')


# ── FG131 — Rapprochement 3 voies ──────────────────────────────────────────

def resume_rapprochement_3voies(rap):
    """Résumé d'un ``Rapprochement3Voies`` : montants, écarts, statut paiement.

    Renvoie un dict :
    ``{'montant_commande_ht', 'montant_recu_ht', 'montant_facture_ht',
    'ecart_commande_facture_ht', 'ecart_recu_facture_ht',
    'tolerance_ht', 'ecarts_dans_tolerance', 'paiement_bloque', 'statut'}``.
    """
    return {
        'montant_commande_ht': rap.montant_commande_ht,
        'montant_recu_ht': rap.montant_recu_ht,
        'montant_facture_ht': rap.montant_facture_ht,
        'ecart_commande_facture_ht': rap.ecart_commande_facture_ht,
        'ecart_recu_facture_ht': rap.ecart_recu_facture_ht,
        'tolerance_ht': rap.tolerance_ht,
        'ecarts_dans_tolerance': rap.ecarts_dans_tolerance,
        'paiement_bloque': rap.paiement_bloque,
        'statut': rap.statut,
    }


def factures_fournisseur_a_valider(company):
    """Factures fournisseur dont le paiement est BLOQUÉ (pas de rap. 3V approuvé).

    Renvoie les ``FactureFournisseur`` sans aucun ``Rapprochement3Voies``
    approuvé lié, encore en statut payable (brouillon/a_valider/validee).
    """
    statuts_payables = [
        FactureFournisseur.Statut.BROUILLON,
        FactureFournisseur.Statut.A_VALIDER,
        FactureFournisseur.Statut.VALIDEE,
    ]
    # IDs des factures ayant AU MOINS un rapprochement approuvé.
    ids_approuvees = Rapprochement3Voies.objects.filter(
        company=company,
        statut=Rapprochement3Voies.Statut.APPROUVE,
    ).values_list('facture_id', flat=True)
    return FactureFournisseur.objects.filter(
        company=company,
        statut__in=statuts_payables,
    ).exclude(id__in=ids_approuvees).order_by('date_echeance', 'id')
