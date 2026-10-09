# SONDE = {'constat': 'C-AMET-001', 'sha': 'f3716e3f0', 'attendu': "PUT du formulaire facture sur une facture émise → 400 « Montant figé » attendu aujourd'hui, 200 après ATOT35"}
# Sonde de la session audit-méthode du 09/10/2026 (R3), jouée dans le conteneur local en transaction annulée,
# backend mail en mémoire, Celery coupé. Rejouable par scripts/sonde.py (AMET93) ; jamais contre la prod.
exec(open('/tmp/r3v1_safety.py').read())
import json
from rest_framework.test import APIClient
from authentication.models import CustomUser
from apps.ventes.models import Facture
u = CustomUser.objects.get(username='demo_admin')
try:
    with transaction.atomic():
        f = Facture.objects.filter(company=u.company).exclude(statut='brouillon').exclude(statut='annulee').order_by('id').first()
        print("facture", f.id, f.statut, "taux_tva", f.taux_tva, "remise_globale", f.remise_globale, "ttc", f.montant_ttc)
        c = APIClient(); c.force_authenticate(user=u)
        base = '/api/django/ventes/factures/'
        g = c.get(f'{base}?page_size=200')
        lst = g.json()
        items = lst['results'] if isinstance(lst, dict) and 'results' in lst else lst
        item = next(x for x in items if x['id'] == f.id)
        def S(v, d): return str(v if v is not None else d)
        payload = {
            'client': int(item['client']),
            'bon_commande': int(item['bon_commande']) if item.get('bon_commande') else None,
            'statut': item.get('statut') or 'brouillon',
            'date_echeance': item.get('date_echeance') or None,
            'date_livraison': item.get('date_livraison') or None,
            'conditions_paiement': item.get('conditions_paiement') or '',
            'taux_tva': S(item.get('taux_tva'), '20.00'),
            'remise_globale': S(item.get('remise_globale'), '0'),
            'statut_teledeclaration': item.get('statut_teledeclaration') or 'non_soumise',
            'note': (item.get('note') or '') + ' [probe]' or None,
            'reference_commande_client': (item.get('reference_commande_client') or '').strip(),
        }
        print("payload keys", sorted(payload.keys()))
        print("taux_tva sent", payload['taux_tva'], "db", f.taux_tva, "| remise sent", payload['remise_globale'], "db", f.remise_globale)
        r = c.put(f'{base}{f.id}/', payload, format='json')
        print("PUT form-shape status", r.status_code, json.dumps(r.json(), ensure_ascii=False)[:400])
        p2 = {k: v for k, v in payload.items() if k not in ('taux_tva', 'remise_globale')}
        r2 = c.put(f'{base}{f.id}/', p2, format='json')
        print("PUT without taux_tva/remise_globale status", r2.status_code, json.dumps(r2.json(), ensure_ascii=False)[:200])
        r3 = c.patch(f'{base}{f.id}/', {'note': 'probe note only'}, format='json')
        print("PATCH note only status", r3.status_code)
        # line update as the form does for every existing line
        for l in f.lignes.all()[:2]:
            lp = {'facture': f.id, 'produit': l.produit_id, 'designation': l.designation, 'quantite': str(l.quantite),
                  'prix_unitaire': str(l.prix_unitaire), 'remise': str(l.remise), 'taux_tva': str(l.taux_tva) if l.taux_tva is not None else None}
            rl = c.put(f'/api/django/ventes/factures-lignes/{l.id}/', lp, format='json')
            print("PUT unchanged line", l.id, "status", rl.status_code, json.dumps(rl.json(), ensure_ascii=False)[:200])
        print("celery calls intercepted", _CELERY_CALLS, "mails", len(__import__('django.core.mail', fromlist=['outbox']).outbox) if hasattr(__import__('django.core.mail', fromlist=['outbox']),'outbox') else 0)
        raise R()
except R:
    print("ROLLED BACK")
