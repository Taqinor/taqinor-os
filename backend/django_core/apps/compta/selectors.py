"""Sélecteurs LECTURE SEULE de la Comptabilité générale (états & restitutions).

Grand livre (FG110), balance générale (FG111), lettrage (FG112), CPC (FG113) et
bilan (FG114) se déduisent tous des ``LigneEcriture`` du grand livre. Aucune
écriture n'est modifiée ici. Toutes les fonctions sont scopées par société.
"""
from decimal import Decimal

from django.db.models import Sum

from .models import CompteComptable, LigneEcriture


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
