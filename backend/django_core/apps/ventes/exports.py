"""T12 — export comptable : journal des ventes + résumé TVA (.xlsx).

Deux feuilles : (1) Journal des ventes = une ligne par ligne de facture émise
sur la période, avec sa TVA par ligne ; (2) Résumé TVA = HT/TVA/TTC répartis
par taux (10 % / 20 %…), réconciliés au centime, + totaux. Lecture seule,
borné à la société. openpyxl (pré-approuvé). Groundwork DGI (per-ligne + ICE).
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.http import HttpResponse

# Statuts « émis » (comptablement sortis) — jamais brouillon ni annulée.
ISSUED_STATUTS = ('emise', 'payee', 'en_retard')


def _q2(d):
    return Decimal(d).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def period_bounds(params):
    """Calcule (debut, fin) depuis ?month=YYYY-MM, ?quarter=YYYY-Q ou
    ?start=&end=. Défaut : mois courant."""
    month = params.get('month')
    quarter = params.get('quarter')
    start = params.get('start')
    end = params.get('end')
    if start and end:
        return date.fromisoformat(start), date.fromisoformat(end)
    if month:
        y, m = (int(x) for x in month.split('-'))
        debut = date(y, m, 1)
        fin = date(y + (m == 12), (m % 12) + 1, 1)
        return debut, fin
    if quarter:
        y, q = (int(x) for x in quarter.upper().replace('Q', '').split('-') if x)
        m0 = (q - 1) * 3 + 1
        debut = date(y, m0, 1)
        fin = date(y + (m0 + 3 > 12), ((m0 + 2) % 12) + 1, 1)
        return debut, fin
    today = date.today()
    return date(today.year, today.month, 1), \
        date(today.year + (today.month == 12), (today.month % 12) + 1, 1)


def export_journal_ventes(company, debut, fin):
    """Construit le classeur .xlsx (journal + résumé TVA) pour [debut, fin[."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from apps.ventes.models import Avoir, Facture

    factures = (Facture.objects
                .filter(company=company, statut__in=ISSUED_STATUTS,
                        date_emission__gte=debut, date_emission__lt=fin)
                .select_related('client').prefetch_related('lignes')
                .order_by('date_emission', 'reference'))

    wb = Workbook()
    ws = wb.active
    ws.title = 'Journal des ventes'
    bold = Font(bold=True)
    headers = ['Facture', 'Date', 'Type', 'Client', 'ICE client',
               'Désignation', 'Qté', 'P.U. HT', 'Total HT', 'TVA %',
               'Montant TVA', 'Total TTC']
    ws.append(headers)
    for c in ws[1]:
        c.font = bold

    par_taux = {}
    tot_ht = tot_tva = tot_ttc = Decimal('0')
    for f in factures:
        type_libelle = f.get_type_facture_display()
        for ligne in f.lignes.all():
            ht = _q2(ligne.total_ht)
            taux = Decimal(ligne.taux_tva_effectif or 0)
            tva = _q2(ht * taux / Decimal('100'))
            ttc = _q2(ht + tva)
            ws.append([
                f.reference,
                f.date_emission.isoformat() if f.date_emission else '',
                type_libelle,
                getattr(f.client, 'nom', '') or '',
                getattr(f.client, 'ice', '') or '',
                ligne.designation, str(ligne.quantite), str(ligne.prix_unitaire),
                float(ht), float(taux), float(tva), float(ttc),
            ])
            bucket = par_taux.setdefault(taux, {'ht': Decimal('0'), 'tva': Decimal('0')})
            bucket['ht'] += ht
            bucket['tva'] += tva
            tot_ht += ht
            tot_tva += tva
            tot_ttc += ttc

    # Avoirs (notes de crédit) émis sur la période : lignes NÉGATIVES pour
    # réconcilier le CA. Ventilés par taux (10/20) comme les factures, et
    # déduits du résumé TVA. Les avoirs annulés sont exclus.
    avoirs = (Avoir.objects
              .filter(company=company, statut=Avoir.Statut.EMISE,
                      date_emission__gte=debut, date_emission__lt=fin)
              .select_related('client', 'facture').prefetch_related('lignes')
              .order_by('date_emission', 'reference'))
    for a in avoirs:
        date_a = a.date_emission.isoformat() if a.date_emission else ''
        nom = getattr(a.client, 'nom', '') or ''
        ice = getattr(a.client, 'ice', '') or ''
        desig = f'Avoir sur {a.facture.reference}' if a.facture_id else 'Avoir'
        for b in a.tva_par_taux:
            taux = Decimal(b['taux'] or 0)
            ht = -_q2(b['base_ht'])
            tva = -_q2(b['montant'])
            ttc = _q2(ht + tva)
            ws.append([
                a.reference, date_a, 'Avoir', nom, ice,
                desig, '', '',
                float(ht), float(taux), float(tva), float(ttc),
            ])
            bucket = par_taux.setdefault(taux, {'ht': Decimal('0'), 'tva': Decimal('0')})
            bucket['ht'] += ht
            bucket['tva'] += tva
            tot_ht += ht
            tot_tva += tva
            tot_ttc += ttc

    # Feuille résumé TVA.
    ws2 = wb.create_sheet('Résumé TVA')
    ws2.append(['Taux TVA', 'Base HT', 'Montant TVA', 'Total TTC'])
    for c in ws2[1]:
        c.font = bold
    for taux in sorted(par_taux):
        b = par_taux[taux]
        ws2.append([f'{taux} %', float(_q2(b['ht'])), float(_q2(b['tva'])),
                    float(_q2(b['ht'] + b['tva']))])
    ws2.append([])
    total_row = ['TOTAL', float(_q2(tot_ht)), float(_q2(tot_tva)), float(_q2(tot_ttc))]
    ws2.append(total_row)
    for c in ws2[ws2.max_row]:
        c.font = bold

    resp = HttpResponse(content_type=(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
    resp['Content-Disposition'] = (
        f'attachment; filename="journal-ventes-{debut.isoformat()}.xlsx"')
    wb.save(resp)
    return resp
