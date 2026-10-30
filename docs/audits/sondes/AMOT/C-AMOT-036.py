SONDE = {"constat": "C-AMOT-036", "sha": "673ec3f92",
         "attendu": "P3.7 — facture émise de la société démo avec une retenue de garantie de 500 non libérée (posée "
                    "dans la transaction) : GET /factures/<id>/lettre-relance-premium/?niveau=3 -> 200, le PDF réclame "
                    "l'EXIGIBLE (reste dû − 500, au centime) et non le reste dû ; même montant que "
                    "recouvrement.montant_exigible (e-mail / rappel planifié) ; une facture payée -> 409 « Aucune somme "
                    "exigible », sans PDF"}


def sonde(ctx):
    import re
    import fitz
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Facture
    from apps.ventes.recouvrement import montant_exigible
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def centimes(x):
        return f'{Decimal(x):,.2f}'.replace(',', ' ').replace('.', ',')

    out, ok = {}, True
    cands = [f for f in Facture.objects.filter(company=admin.company, statut__in=['emise', 'partiellement_payee'])
             .order_by('-id')[:30] if f.montant_du and f.montant_du > Decimal('1000')]
    if not cands:
        return {'repro': False, 'motif': 'aucune facture émise avec reste dû > 1000 dans la société démo'}
    fac = cands[0]
    Facture.objects.filter(pk=fac.pk).update(retenue_garantie_mad=Decimal('500'))
    fac = Facture.objects.get(pk=fac.pk)
    exig = montant_exigible(fac)
    r = api.get(f'/api/django/ventes/factures/{fac.id}/lettre-relance-premium/?niveau=3', **H)
    txt = ''
    if r.status_code == 200:
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        txt = norm('\n'.join(p.get_text() for p in fitz.open(stream=body, filetype='pdf')))
    out['facture'] = {'reference': fac.reference, 'statut': fac.statut, 'montant_du': str(fac.montant_du),
                      'montant_exigible_propriete': str(fac.montant_exigible), 'montant_exigible_recouvrement': str(exig)}
    out['lettre'] = {'http': r.status_code, 'exigible_imprime': centimes(exig) in txt,
                     'reste_du_imprime': centimes(fac.montant_du) in txt,
                     'lignes_montant': [ln for ln in txt.splitlines() if 'MAD' in ln][:6]}
    ok &= (r.status_code == 200 and centimes(exig) in txt and centimes(fac.montant_du) not in txt
           and exig == fac.montant_du - Decimal('500') and exig == fac.montant_exigible)
    autre = next((f for f in cands[1:]), None) or fac
    Facture.objects.filter(pk=autre.pk).update(statut='payee')
    r2 = api.get(f'/api/django/ventes/factures/{autre.id}/lettre-relance-premium/?niveau=3', **H)
    detail = r2.data.get('detail') if hasattr(r2, 'data') and isinstance(getattr(r2, 'data', None), dict) else None
    out['facture_payee'] = {'reference': autre.reference, 'http': r2.status_code, 'detail': detail,
                            'content_type': r2.get('Content-Type')}
    ok &= r2.status_code == 409 and 'Aucune somme exigible' in (detail or '')
    out['repro'] = bool(ok)
    return out
