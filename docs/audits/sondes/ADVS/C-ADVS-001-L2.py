# flake8: noqa  (seconde lentille C-ADVS-001, reproduction indépendante — rejouable par scripts/sonde.py)
"""Prix TTC tapés (entiers) → HT à 2 décimales (`solar.js::htFromTtc`, ce que l'écran envoie) : la perte de
centimes est-elle transformée en −100 MAD par le palier ARRONDI-100 (`noyau_totaux._absorber_arrondi`) ?
Autres fixtures que la première lentille : A = mono-taux 10 % (3 × 700 TTC) par POST /atomic ; B = multi-taux
(12 panneaux × 1 100 TTC @10 % + 3 × 1 000 TTC @20 %) par PUT/POST replace-lines sur un brouillon ; témoin
C = 6 × 500 TTC @20 % (le HT arrondi AU-DESSUS : aucun écart attendu). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-001", "sha": "1dfa7986c",
         "attendu": "Devis.total_ttc == palier inférieur de Σ(qté × TTC tapé) pour A, B et C",
         "modeles": ["ventes.Devis", "ventes.LigneDevis"]}


def sonde(ctx):
    import json
    from decimal import Decimal, ROUND_FLOOR
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Devis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 001 L2', slug='sonde-advs-001-l2')
    u = U.objects.create_user(username='sonde-advs-001-l2', password='x', role_legacy='admin', company=c)
    cl = Client.objects.create(company=c, nom='Lentille', prenom='Deux', email='sonde-advs-001-l2@example.invalid')
    api = APIClient()
    api.force_authenticate(u)
    etapes = []

    def appel(nom, meth, url, corps):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        txt = r.content.decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else txt[:300]))
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    def ht(ttc, taux):  # miroir exact de solar.js::htFromTtc (toFixed(2))
        return str((Decimal(ttc) / (1 + Decimal(taux) / 100)).quantize(Decimal('0.01')))

    from apps.stock.models import Produit
    n = [0]

    def ligne(des, q, ttc, taux):
        n[0] += 1
        p = Produit.objects.create(company=c, nom=des, sku=f'ADVS001L2-{n[0]}', prix_vente=Decimal(ht(ttc, taux)),
                                   prix_achat=Decimal('1'), quantite_stock=100, tva=Decimal(taux))
        return {'produit': p.id, 'designation': des, 'quantite': str(q), 'prix_unitaire': ht(ttc, taux),
                'taux_tva': str(taux)}

    def palier(lignes_ttc):
        brut = sum((Decimal(q) * Decimal(p) for q, p in lignes_ttc), Decimal('0'))
        return brut, (brut / 100).to_integral_value(rounding=ROUND_FLOOR) * 100

    cas = {}
    # A — /atomic, mono-taux 10 %
    s, r = appel('A atomic', 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'statut': 'brouillon', 'taux_tva': '10.00',
        'lignes': [ligne('Kit fixation (prix tapé 700 TTC)', 3, '700', 10)]})
    cas['A'] = {'saisie': [(3, '700')], 'id': r.get('id')}
    # C — témoin /atomic 6 × 500 @20 %
    s, r = appel('C atomic', 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'lignes': [ligne('Prestation (prix tapé 500 TTC)', 6, '500', 20)]})
    cas['C'] = {'saisie': [(6, '500')], 'id': r.get('id')}
    # B — brouillon puis replace-lines (chemin d'ÉDITION), multi-taux
    s, r = appel('B atomic', 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'lignes': [ligne('Provisoire', 1, '100', 20)]})
    bid = r.get('id')
    if bid:
        appel('B replace-lines', 'post', f'/api/django/ventes/devis/{bid}/replace-lines/', {
            'lignes': [ligne('Panneau 550 W (prix tapé 1 100 TTC)', 12, '1100', 10),
                       ligne('Coffret AC/DC (prix tapé 1 000 TTC)', 3, '1000', 20)]})
    cas['B'] = {'saisie': [(12, '1100'), (3, '1000')], 'id': bid}

    obs = {'etapes': etapes}
    ecarts = []
    for nom, d in cas.items():
        dv = Devis.objects.filter(company=c, pk=d['id']).first() if d['id'] else None
        if dv is None:
            obs[nom] = 'devis absent'
            continue
        brut, attendu = palier(d['saisie'])
        ttc = Decimal(str(dv.total_ttc))
        lignes = list(dv.lignes.values_list('designation', 'quantite', 'prix_unitaire', 'taux_tva'))
        obs[nom] = {'ttc_tape': str(brut), 'palier_attendu': str(attendu), 'total_ttc': str(ttc),
                    'ecart': str(ttc - attendu), 'lignes': [tuple(str(x) for x in li) for li in lignes]}
        if ttc != attendu:
            ecarts.append(nom)
    obs['cas_en_ecart'] = ecarts
    return {'repro': bool(set(ecarts) & {'A', 'B'}), 'observe': obs}
