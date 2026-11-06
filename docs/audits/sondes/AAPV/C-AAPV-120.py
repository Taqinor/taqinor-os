# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""T1 (critique L3) — aucune porte écran ne pose `FactureFournisseur.type_achat` : une PRESTATION chez un
sous-traitant à ARF valide naît « biens » et subit RAS-TVA 0 % au lieu de 75 %. CONDITIONNEL : ne joue que
si `AchatsParametres.ras_tva_actif` est ALLUMÉ (OFF par défaut). Sonde : réglage ON ; fournisseur
`type=service` (DC34) + ARF émise hier. (E) corps EXACT de `FacturesFournisseur.jsx::submit` (sans
`type_achat`) TTC 12 000 / TVA 2 000, puis paiement 12 000 par la route de l'écran
(`POST factures-fournisseur/<id>/paiements/`). (T) témoin : même chaîne, corps API brut avec
`type_achat: 'services'` → 75 % = 1 500. Lit aussi le relevé RAS (`relevé_ras_tva`, export Simpl-TVA)."""
SONDE = {"constat": "C-AAPV-120", "sha": "acc21a69c0",
         "attendu": "repro si E : type_achat=biens, taux 0, RAS 0.00, absente du relevé ; T : taux 75, RAS 1500.00",
         "modeles": ["achats.FactureFournisseur", "achats.PaiementFournisseur", "stock.AchatsParametres",
                     "stock.DocumentConformiteFournisseur", "stock.Fournisseur"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.achats.models import FactureFournisseur
    from apps.stock.models import AchatsParametres, Fournisseur, DocumentConformiteFournisseur
    from apps.stock.services import relevé_ras_tva
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 120', slug='sonde-aapv-120')
    u = get_user_model().objects.create_user(username='sonde_aapv_120', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    ap = AchatsParametres.for_company(co)
    ap.ras_tva_actif = True
    ap.save()
    hier = datetime.date.today() - datetime.timedelta(days=1)

    def st(tag):
        f = Fournisseur.objects.create(company=co, nom='Bureau etudes ' + tag, type=Fournisseur.Type.SERVICE)
        DocumentConformiteFournisseur.objects.create(
            company=co, fournisseur=f, type_document=DocumentConformiteFournisseur.Type.ARF,
            reference='ARF-' + tag, date_emission=hier)
        return f

    def chaine(f, extra, tag):
        corps = {'fournisseur': f.id, 'bon_commande': None, 'ref_fournisseur': 'PREST-' + tag,
                 'date_facture': None, 'date_echeance': None, 'montant_ht': 10000, 'montant_tva': 2000,
                 'montant_ttc': 12000, 'note': None}
        corps.update(extra)
        rc = api.post('/api/django/stock/factures-fournisseur/', corps, format='json', **H)
        assert rc.status_code == 201, (rc.status_code, rc.data)
        fid = rc.data['id']
        rp = api.post(f'/api/django/stock/factures-fournisseur/{fid}/paiements/',
                      {'montant': 12000, 'date_paiement': None, 'mode': 'virement'}, format='json', **H)
        fac = FactureFournisseur.objects.get(pk=fid)
        p = fac.paiements.order_by('-id').first()
        return {'creer_http': rc.status_code, 'type_achat': fac.type_achat, 'payer_http': rp.status_code,
                'detail': None if rp.status_code < 400 else str(rp.data)[:140],
                'taux_ras': str(p.taux_ras) if p else None,
                'montant_ras_tva': str(p.montant_ras_tva) if p else None,
                'net_paye': str(p.montant_net_paye) if p else None, 'statut': fac.statut, 'ref': fac.reference}

    obs = {'ras_tva_actif': AchatsParametres.for_company(co).ras_tva_actif}
    obs['E_ecran'] = chaine(st('E'), {}, 'E')
    obs['T_api_services'] = chaine(st('T'), {'type_achat': 'services'}, 'T')
    releve = relevé_ras_tva(co)
    obs['releve'] = [(r['facture'], r['type_achat'], str(r['taux_ras']), str(r['montant_ras_tva'])) for r in releve]
    obs['E_dans_releve'] = any(r['facture'] == obs['E_ecran']['ref'] for r in releve)
    print(obs)
    temoin_ok = (obs['T_api_services']['type_achat'] == 'services'
                 and Decimal(obs['T_api_services']['montant_ras_tva'] or '0') == Decimal('1500'))
    defaut = (obs['E_ecran']['type_achat'] == 'biens' and obs['E_ecran']['payer_http'] in (200, 201)
              and Decimal(obs['E_ecran']['montant_ras_tva'] or '0') == Decimal('0'))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
