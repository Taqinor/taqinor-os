"""AFAC97 (C-AFAC-031 + C-AFAC-049) — ORACLE RÉUTILISABLE du relevé client.

Identité vérifiée sur CHAQUE surface (relevé API, relevé PDF, portail, bloc
« Déjà payé / Reste » du PDF facture), au centime, signes explicites :

    Facturé (TTC émis) + Notes de débit − Payé − Retenues (RAS subies)
    − Avoirs − Abandons = Solde dû        et        0 ≤ Solde dû

et chaque terme lu = la somme, sur les factures visibles du client, du
service unique ``facturation.models.decomposition_du`` (relu en base, jamais
l'objet en mémoire). Agrège par client sans recoder
``oracles_argent.verifier_reste_a_payer`` (la référence par document).
Importé par AFAC99 et par les audits J1b / J3.
"""
import re
from decimal import Decimal

ZERO = Decimal('0')
TERMES = ('facture', 'notes_debit', 'paye', 'retenues', 'avoirs', 'abandons')

#: Libellés du bloc totaux de ``templates/pdf/releve.html`` (AFAC31).
LIBELLES_PDF = {
    'facture': 'Total facturé',
    'notes_debit': 'Notes de débit',
    'paye': 'Total payé',
    'retenues': 'Retenues à la source',
    'avoirs': 'Total avoirs',
    'abandons': 'Abandons de créance',
    'du': 'Solde dû',
}


def _dec(valeur):
    return Decimal(str(valeur if valeur is not None else 0)).quantize(
        Decimal('0.01'))


def termes_attendus(client):
    """Les six termes + le dû attendus, sommés sur les factures visibles du
    client (hors brouillon / annulée — AFAC40), relues en base."""
    from apps.facturation.models import decomposition_du
    from apps.ventes.models import Facture
    attendu = {t: ZERO for t in TERMES}
    attendu['du'] = ZERO
    for f in Facture.objects.filter(client=client).exclude(
            statut__in=('brouillon', 'annulee')):
        dec = decomposition_du(f)
        for t in TERMES:
            attendu[t] += _dec(dec[t])
        attendu['du'] += (ZERO if f.statut == 'payee' else _dec(f.montant_du))
    return attendu


def verifier_identite(totaux, contexte=''):
    """L'identité à six termes et la borne ``0 ≤ dû`` sur des totaux LUS."""
    t = {k: _dec(totaux[k]) for k in (*TERMES, 'du')}
    calcule = (t['facture'] + t['notes_debit'] - t['paye'] - t['retenues']
               - t['avoirs'] - t['abandons'])
    assert calcule == t['du'], (
        f'{contexte} : Facturé {t["facture"]} + ND {t["notes_debit"]} − '
        f'Payé {t["paye"]} − RAS {t["retenues"]} − Avoirs {t["avoirs"]} − '
        f'Abandons {t["abandons"]} = {calcule} ≠ Solde dû {t["du"]}.')
    assert t['du'] >= ZERO, f'{contexte} : solde dû négatif {t["du"]}.'
    return t


def verifier_decomposition_du(totaux, client, contexte=''):
    """Identité + chaque terme = la décomposition du service unique."""
    lus = verifier_identite(totaux, contexte)
    attendu = termes_attendus(client)
    for cle in (*TERMES, 'du'):
        assert lus[cle] == attendu[cle], (
            f'{contexte} : terme « {cle} » lu {lus[cle]} ≠ service '
            f'{attendu[cle]}.')
    return lus


def totaux_releve_pdf(texte):
    """Les sept montants du bloc totaux d'un relevé PDF (texte PyMuPDF
    aplati) : ``{terme: Decimal}``."""
    totaux = {}
    for cle, libelle in LIBELLES_PDF.items():
        m = re.search(re.escape(libelle) + r'\s*[+−-]?\s*([0-9]+\.[0-9]{2})'
                      r'\s*MAD', texte)
        assert m, f'Relevé PDF : libellé « {libelle} » introuvable.'
        totaux[cle] = Decimal(m.group(1))
    return totaux


def verifier_bloc_reste_facture(facture):
    """Bloc « Déjà payé / Reste à payer » du PDF facture (``reglements``) :
    Facturé + ND − Déjà payé − Abandon = Reste à payer = ``montant_du``."""
    from apps.facturation.models import decomposition_du
    from apps.ventes.models import Facture
    from apps.ventes.utils.pdf import reglements_facture_pdf
    f = Facture.objects.get(pk=facture.pk)
    bloc = reglements_facture_pdf(f)
    assert bloc is not None, f'{f.reference} : aucun bloc « Déjà payé ».'
    dec = decomposition_du(f)
    nd = sum((_dec(n['montant']) for n in bloc['notes_debit']), ZERO)
    abandon = _dec(bloc['abandon']['montant']) if bloc['abandon'] else ZERO
    reste = (_dec(dec['facture']) + nd - _dec(bloc['total_deja_paye'])
             - abandon)
    if reste < ZERO:
        reste = ZERO
    assert reste == _dec(bloc['reste_a_payer']) == _dec(f.montant_du), (
        f'{f.reference} : Facturé + ND − Déjà payé − Abandon = {reste}, '
        f'bloc {bloc["reste_a_payer"]}, montant_du {f.montant_du}.')
    return bloc
