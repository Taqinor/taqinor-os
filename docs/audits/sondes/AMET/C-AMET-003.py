# flake8: noqa  (sonde de session reprise telle quelle : style libre, logique validee le 09/10)
"""Sonde de la session audit-méthode du 09/10/2026 (R3), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
"""
SONDE = {
    'constat': 'C-AMET-003',
    'sha': 'f3716e3f0',
    'attendu': 'conditions de paiement lues en direct sur un devis signé (60 %/38 280 → 40 %/25 520) ; avoir re-netté 19 830 → 25 830',
}


def sonde(ctx):
    from django.db import transaction
    class R(Exception):
        pass
    _CELERY = _CELERY_CALLS = ctx['celery']


    import json
    from decimal import Decimal
    from django.db.models import Q
    from rest_framework.test import APIClient
    from authentication.models import CustomUser
    from apps.ventes.models import Devis, Facture, Avoir
    from apps.ventes.utils.echeancier import next_tranche, tranches_normalisees, solde_devis
    from apps.ventes.utils.options import option_totaux

    u = CustomUser.objects.get(username='demo_admin')
    co = u.company
    c = APIClient()
    c.force_authenticate(user=u)
    B = '/api/django/ventes'


    def js(r):
        try:
            return json.dumps(r.json(), ensure_ascii=False)[:300]
        except Exception:
            return str(r.content[:200])


    def list_solde(did):
        r = c.get(B + '/devis/', {'page_size': 500})
        data = r.json()
        items = data['results'] if isinstance(data, dict) and 'results' in data else data
        for x in items:
            if x['id'] == did:
                return x.get('statut'), x.get('solde')
        return None, ('NOT IN LIST page', r.status_code, len(items))


    def jsgt(a, b):
        try:
            return float(a) > b
        except Exception:
            return False


    def row_predicate(statut, s):
        if statut != 'accepte':
            return ['Generer facture (disabled)']
        tf, tt = s.get('tranches_facturees'), s.get('tranches_total')
        if isinstance(tf, str) and isinstance(tt, str):
            complet = tf >= tt  # JS string comparison
        else:
            complet = float(tf) >= float(tt)
        if complet:
            return ['Echeancier complet (disabled)']
        btns = []
        if not jsgt(tf, 0):
            btns.append('Facturer (facture complete)')
        btns.append('Generer facture' if jsgt(tf, 0) else 'Facturer par tranches (acompte...)')
        return btns


    def tab_predicate(statut, s):
        if statut != 'accepte':
            return []
        tf = s.get('tranches_facturees')
        btns = []
        if not jsgt(tf, 0):
            btns.append('Facturer (facture complete)')
        btns.append('Generer la facture' if jsgt(tf, 0) else 'Facturer par tranches (acompte...)')
        return btns


    try:
        with transaction.atomic():
            libres = list(Devis.objects.filter(company=co, statut='accepte', factures__isnull=True)
                          .filter(Q(echeancier__isnull=True) | Q(echeancier=[])).distinct().order_by('id')[:6])
            print('accepted devis w/o facture and w/o own echeancier:', [(d.id, d.mode_installation) for d in libres])
            # ===== CLAIM 2 (ATOT2) =====
            d1 = libres[0]
            st, s = list_solde(d1.id)
            print('[C2] before: statut', st, 'solde', s)
            r = c.post(B + '/devis/%d/facturer-complet/' % d1.id,
                       {'paiements': [], 'override_credit': True, 'override_avertissement': True}, format='json')
            print('[C2] facturer-complet', r.status_code, js(r)[:160])
            st, s = list_solde(d1.id)
            print('[C2] after complete invoice: solde', s)
            print('[C2] DevisRow buttons ->', row_predicate(st, s))
            print('[C2] DevisTab buttons ->', tab_predicate(st, s))
            r2 = c.post(B + '/devis/%d/generer-facture/' % d1.id, {}, format='json')
            print('[C2] click tranches -> generer-facture', r2.status_code, js(r2)[:220])
            r3 = c.post(B + '/devis/%d/facturer-complet/' % d1.id, {'paiements': []}, format='json')
            print('[C2] click complete again -> facturer-complet', r3.status_code, js(r3)[:220])
            actives = [f for f in Devis.objects.get(pk=d1.pk).factures.all() if f.statut != 'annulee']
            print('[C2] pre-ATOT2 formula len(actives)=', len(actives), '| type_facture', [f.type_facture for f in actives])
            # ===== CLAIM 4 (payment terms live) =====
            d3 = libres[1]
            print('[C4] devis', d3.id, 'statut', d3.statut, 'mode', d3.mode_installation, 'echeancier', d3.echeancier)
            print('[C4] tranches before:', [(t['key'], str(t['valeur'])) for t in tranches_normalisees(d3)])
            rg = c.post(B + '/devis/%d/generer-facture/' % d3.id, {}, format='json')
            print('[C4] generer-facture (acompte)', rg.status_code, js(rg)[:120])
            nt = next_tranche(Devis.objects.get(pk=d3.pk))
            print('[C4] next tranche BEFORE setting change:', nt and (nt['key'], str(nt['pourcentage']), str(nt['ttc'])))
            mode = d3.mode_installation or 'residentiel'
            if mode == 'residentiel':
                newterms = {mode: {'acompte': 30, 'materiel': 40, 'solde': 30}}
            else:
                newterms = {mode: [{'jalon': 'commande', 'pct': 30}, {'jalon': 'livraison', 'pct': 40},
                                   {'jalon': 'solde', 'pct': 30}]}
            rp = c.patch('/api/django/parametres/update/', {'payment_terms': newterms}, format='json')
            print('[C4] PATCH /parametres/update/ payment_terms', rp.status_code, js(rp)[:160] if rp.status_code >= 400 else '')
            d3 = Devis.objects.get(pk=d3.pk)
            print('[C4] tranches after:', [(t['key'], str(t['valeur'])) for t in tranches_normalisees(d3)])
            nt2 = next_tranche(d3)
            print('[C4] next tranche AFTER setting change:', nt2 and (nt2['key'], str(nt2['pourcentage']), str(nt2['ttc'])))
            print('[C4] solde_devis tranches_total', solde_devis(d3)['tranches_total'])
            # ===== CLAIM 3 (ATOT5) behaviour =====
            d2 = libres[2]
            g1 = c.post(B + '/devis/%d/generer-facture/' % d2.id, {}, format='json')
            g2 = c.post(B + '/devis/%d/generer-facture/' % d2.id, {}, format='json')
            print('[C3] generer x2', g1.status_code, g2.status_code)
            d2 = Devis.objects.get(pk=d2.pk)
            fs = sorted([f for f in d2.factures.all() if f.statut != 'annulee'], key=lambda f: f.id)
            tot = Decimal(str(option_totaux(d2)['ttc']))
            print('[C3] devis', d2.id, 'TTC', tot, 'invoices', [(f.cle_tranche, str(f.total_ttc)) for f in fs])
            nt_before = next_tranche(d2)
            print('[C3] last tranche w/o avoir:', nt_before and (nt_before['key'], str(nt_before['ttc'])))
            mat = fs[-1]
            Avoir.objects.create(company=co, reference='AV-PROBE-R3V1', facture=mat, client=mat.client, statut='emise',
                                 taux_tva=Decimal('20.00'), montant_ht=Decimal('5000.00'), montant_tva=Decimal('1000.00'),
                                 montant_ttc=Decimal('6000.00'), motif='Geste commercial')
            d2 = Devis.objects.get(pk=d2.pk)
            nt_after = next_tranche(d2)
            print('[C3] last tranche after a 6000 TTC goodwill avoir on the materiel invoice:',
                  nt_after and (nt_after['key'], str(nt_after['ttc'])),
                  'delta', nt_after and str(Decimal(str(nt_after['ttc'])) - Decimal(str(nt_before['ttc']))))
            # ===== CLAIM 6 (portail montant_du vs exigible) =====
            f = Facture.objects.filter(company=co).exclude(statut__in=['brouillon', 'annulee', 'payee']).order_by('id').first()
            if f:
                f.retenue_garantie_mad = Decimal('1000.00')
                f.retenue_liberee_le = None
                f.save(update_fields=['retenue_garantie_mad', 'retenue_liberee_le'])
                f = Facture.objects.get(pk=f.pk)
                print('[C6] facture', f.id, f.statut, 'montant_du', f.montant_du, 'retenue_non_liberee',
                      f.retenue_non_liberee, 'montant_exigible', f.montant_exigible,
                      '-> portail payer intention montant =', f.montant_du)
            print('celery intercepted:', _CELERY)
            from django.core import mail
            print('mails in locmem outbox:', len(getattr(mail, 'outbox', [])))
            raise R()
    except R:
        print('ROLLED BACK')
