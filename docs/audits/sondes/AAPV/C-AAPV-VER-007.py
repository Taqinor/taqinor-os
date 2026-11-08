# flake8: noqa  (sonde de contre-visite « vérifie AAPV », rejouable par scripts/sonde.py — METHODE §C.4)
"""Contre-visite AAPV17/AAPV71 — la porte INVERSE `rouvrir`. Budget allumé (50 000). DA 20 000 → soumettre →
approuver → generer-bcf (BCF-A, réalisé 20 000) → annuler BCF-A (DA rouverte « approuvée » sans BCF, réalisé 0)
→ rouvrir BCF-A (brouillon) → generer-bcf de la même DA (BCF-B). Attendu sain : `rouvrir` re-commande la DA et
re-consomme l'engagement (generer-bcf alors 409), ou `rouvrir` refuse (409). Défaut : deux BCF vivants pour une
DA de 20 000, réalisé 20 000 au lieu de 40 000 commandés."""
SONDE = {"constat": "C-AAPV-VER-007", "sha": "76344a269d",
         "attendu": "repro si rouvrir 200 puis generer-bcf 200 : BCF-A brouillon + BCF-B vivants pour une DA, realise 20000",
         "modeles": ["installations.DemandeAchat", "installations.DemandeAchatLigne", "achats.BonCommandeFournisseur",
                     "stock.BudgetDepartement", "stock.EngagementBudget", "stock.AchatsParametres"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Fournisseur, AchatsParametres, BudgetDepartement, BonCommandeFournisseur
    from apps.stock.selectors import consommation_budget
    from apps.installations.models import DemandeAchat
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV VER 007', slug='sonde-aapv-ver-007')
    u = get_user_model().objects.create_user(username='sonde_aapv_ver_007', password='x', role_legacy='admin',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-VER7')
    AchatsParametres.objects.update_or_create(company=co, defaults={'budget_departement_actif': True})
    budget = BudgetDepartement.objects.create(company=co, periodicite='annuelle', annee=datetime.date.today().year,
                                              mois=0, montant_alloue=Decimal('50000'))
    base = '/api/django/installations/demandes-achat/'
    r = api.post(base, {'objet': 'DA VER7', 'fournisseur_suggere': f.id}, format='json', **H)
    d1 = r.data['id']
    api.post('/api/django/installations/demandes-achat-lignes/',
             {'demande': d1, 'designation': 'Lot câbles VER7', 'quantite': '1', 'prix_estime': '20000'},
             format='json', **H)

    def budg():
        c = consommation_budget(budget)
        return {k: str(c[k]) for k in ('engage', 'realise', 'restant')}

    obs = {'soumettre': api.post(f'{base}{d1}/soumettre/', {}, format='json', **H).status_code,
           'approuver': api.post(f'{base}{d1}/approuver/', {}, format='json', **H).status_code}
    with TestCase.captureOnCommitCallbacks(execute=True):
        rg = api.post(f'{base}{d1}/generer-bcf/', {'fournisseur': f.id}, format='json', **H)
    obs['generer_bcf_a'] = rg.status_code
    bcf_a = DemandeAchat.objects.get(pk=d1).bon_commande_id
    obs['budget_apres_bcf_a'] = budg()
    bcf_url = '/api/django/stock/bons-commande-fournisseur/'
    with TestCase.captureOnCommitCallbacks(execute=True):
        ra = api.post(f'{bcf_url}{bcf_a}/annuler/', {'motif_annulation': 'erreur'}, format='json', **H)
    obs['annuler_a'] = ra.status_code
    obs['budget_apres_annulation'] = budg()
    with TestCase.captureOnCommitCallbacks(execute=True):
        ro = api.post(f'{bcf_url}{bcf_a}/rouvrir/', {}, format='json', **H)
    obs['rouvrir_a'] = {'http': ro.status_code, 'detail': None if ro.status_code < 400 else str(ro.data)[:160]}
    da1 = DemandeAchat.objects.get(pk=d1)
    obs['da_apres_rouvrir'] = {'statut': da1.statut, 'bon_commande_id': da1.bon_commande_id}
    with TestCase.captureOnCommitCallbacks(execute=True):
        rb = api.post(f'{base}{d1}/generer-bcf/', {'fournisseur': f.id}, format='json', **H)
    obs['generer_bcf_b'] = {'http': rb.status_code, 'detail': None if rb.status_code < 400 else str(rb.data)[:160]}
    vivants = list(BonCommandeFournisseur.objects.filter(company=co).exclude(statut='annule')
                   .values_list('id', 'statut'))
    obs['bcf_vivants'] = [[i, s] for i, s in vivants]
    obs['budget_final'] = budg()
    print(obs)
    temoin_ok = (obs['generer_bcf_a'] == 200 and obs['budget_apres_bcf_a']['realise'] == '20000.00'
                 and ra.status_code == 200 and obs['budget_apres_annulation']['realise'] == '0.00')
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and ro.status_code == 200 and rb.status_code == 200 and len(vivants) == 2)
    return obs
