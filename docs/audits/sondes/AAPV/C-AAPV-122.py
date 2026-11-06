# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""T4 (critique L3) — 2e porte du geste K04 (C-AAPV-063, qui couvrait `annuler`) : SUPPRIMER le BCF brouillon
né d'une DA. Contrôle budgétaire ALLUMÉ (`AchatsParametres.budget_departement_actif`, OFF par défaut) + budget
annuel 50 000. Chaîne par vraies routes : DA 20 000 → soumettre → approuver → generer-bcf →
`DELETE stock/bons-commande-fournisseur/<id>/` (aucun écran n'appelle `deleteBonCommandeFournisseur` : API seule)
→ generer-bcf rejoué → nouvelle DA 35 000 soumise. Mesure : http DELETE, DA (statut, bon_commande_id), budget."""
SONDE = {"constat": "C-AAPV-122", "sha": "acc21a69c0",
         "attendu": "repro si DELETE 204, DA commandee avec bon_commande null, realise 20000 / restant 30000, generer-bcf 409, DA 35000 refusée 400",
         "modeles": ["installations.DemandeAchat", "installations.DemandeAchatLigne", "achats.BonCommandeFournisseur",
                     "stock.BudgetDepartement", "stock.EngagementBudget", "stock.AchatsParametres"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Fournisseur, AchatsParametres, BudgetDepartement, BonCommandeFournisseur, EngagementBudget
    from apps.stock.selectors import consommation_budget
    from apps.installations.models import DemandeAchat
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 122', slug='sonde-aapv-122')
    u = get_user_model().objects.create_user(username='sonde_aapv_122', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV122')
    AchatsParametres.objects.update_or_create(company=co, defaults={'budget_departement_actif': True})
    budget = BudgetDepartement.objects.create(company=co, periodicite='annuelle', annee=datetime.date.today().year,
                                              mois=0, montant_alloue=Decimal('50000'))
    base = '/api/django/installations/demandes-achat/'

    def da(montant, objet):
        r = api.post(base, {'objet': objet, 'fournisseur_suggere': f.id}, format='json', **H)
        assert r.status_code == 201, (r.status_code, r.data)
        did = r.data['id']
        rl = api.post('/api/django/installations/demandes-achat-lignes/',
                      {'demande': did, 'designation': 'Lot câbles ' + objet, 'quantite': '1', 'prix_estime': montant},
                      format='json', **H)
        assert rl.status_code == 201, (rl.status_code, rl.data)
        return did

    def budg():
        c = consommation_budget(budget)
        return {k: str(c[k]) for k in ('engage', 'realise', 'restant')}

    obs = {}
    d1 = da('20000', 'DA1')
    obs['soumettre1'] = api.post(f'{base}{d1}/soumettre/', {}, format='json', **H).status_code
    obs['approuver1'] = api.post(f'{base}{d1}/approuver/', {}, format='json', **H).status_code
    with TestCase.captureOnCommitCallbacks(execute=True):
        rg = api.post(f'{base}{d1}/generer-bcf/', {'fournisseur': f.id}, format='json', **H)
    obs['generer_bcf'] = rg.status_code
    da1 = DemandeAchat.objects.get(pk=d1)
    bcf_id = da1.bon_commande_id
    bc = BonCommandeFournisseur.objects.get(pk=bcf_id)
    obs['bcf'] = {'statut': bc.statut, 'acomptes': bc.acomptes.count()}
    obs['budget_apres_bcf'] = budg()
    with TestCase.captureOnCommitCallbacks(execute=True):
        rd = api.delete(f'/api/django/stock/bons-commande-fournisseur/{bcf_id}/', **H)
    obs['delete_http'] = rd.status_code
    obs['delete_detail'] = None if rd.status_code < 400 else str(getattr(rd, 'data', ''))[:140]
    obs['bcf_existe'] = BonCommandeFournisseur.objects.filter(pk=bcf_id).exists()
    da1.refresh_from_db()
    obs['da_apres_suppression'] = {'statut': da1.statut, 'bon_commande_id': da1.bon_commande_id}
    obs['engagements'] = list(EngagementBudget.objects.filter(demande_achat_id=d1).values_list(
        'statut', 'bon_commande_id', 'montant'))
    obs['engagements'] = [(s, b, str(m)) for s, b, m in obs['engagements']]
    obs['budget_apres_suppression'] = budg()
    rr = api.post(f'{base}{d1}/generer-bcf/', {'fournisseur': f.id}, format='json', **H)
    obs['regenerer_bcf'] = {'http': rr.status_code, 'detail': str(rr.data)[:120]}
    d2 = da('35000', 'DA2')
    r2 = api.post(f'{base}{d2}/soumettre/', {}, format='json', **H)
    obs['soumettre_35000'] = {'http': r2.status_code, 'detail': None if r2.status_code < 400 else str(r2.data)[:180]}
    print(obs)
    temoin_ok = (obs['soumettre1'] == 200 and obs['generer_bcf'] == 200
                 and obs['budget_apres_bcf']['realise'] == '20000.00' and obs['bcf']['statut'] == 'brouillon')
    defaut = (rd.status_code == 204 and not obs['bcf_existe'] and da1.statut == 'commandee'
              and da1.bon_commande_id is None and obs['budget_apres_suppression']['restant'] == '30000.00'
              and rr.status_code >= 400)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
