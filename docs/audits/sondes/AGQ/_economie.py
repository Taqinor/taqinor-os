import json, sys
sys.path.insert(0, '.')
from apps.ventes import economie_pompage as E
# Scenario 3: lead-shaped saisies (butane 2/jour, prix 50, mois 4..10), no jours/semaine
lead = {'energie_actuelle': {'valeur': 'butane', 'provenance': {'origine':'lead','detail':'client','date':'2026-10-01'}},
        'consommation': {'quantite': 2, 'unite':'bouteille_12kg', 'periode':'jour_irrigation', 'saisi_le':'2026-10-01'},
        'depense_unitaire_payee': {'valeur': 50, 'saisi_le':'2026-10-01'},
        'mois_irrigation': {'mois': [4,5,6,7,8,9,10], 'provenance': {'origine':'lead','detail':'client','date':'2026-10-01'}}}
d = E.depense_actuelle(lead)
print('S3 depense:', d['statut'], d['motifs'], d['depense_actuelle'])
lignes = [{'designation':'Pompe','total_ttc_mad':20000,'total_ht_mad':16666.67,'type_equipement':'pompe'},
          {'designation':'Variateur','total_ttc_mad':6000,'total_ht_mad':5000,'role_pompage':'variateur_pompage','garantie_mois':24},
          {'designation':'Panneaux','total_ttc_mad':40000,'total_ht_mad':33333.33}]
b = E.economie_pompage(lead, lignes=lignes, reglages={})
print('S3 bloc statut/publiable:', b['statut'], b['publiable_client'], b['motifs_non_publiable'])
# Scenario 1: complete saisies but NO barème
full = json.loads(json.dumps(lead)); full['consommation']['jours_irrigation_par_semaine'] = 6
sortie = {'besoin': {'nature':'declare','m3_jour_mois':[30]*12}, 'production':{'m3_jour_mois':[40]*12}, 'hmt':{'valeur_m':60}, 'couverture_pct_mois':[100]*12}
b = E.economie_pompage(full, lignes=lignes, reglages={}, sortie_etude=sortie)
print('S1 no bareme: statut', b['statut'], 'publiable', b['publiable_client'], b['motifs_non_publiable'])
print('  charges_solaires', b['charges_solaires'], 'retour', b['economie']['retour_ans'], 'an1', [f for f in b['economie']['flux'] if f['annee']==1])
print('  mad_par_m3', b['mad_par_m3'])
print('  sensib', b['sensibilite_carburant'][:2]); print('  seuil', b['seuil_rentabilite_carburant'])
print('  remplacements', b['remplacements'])
print('  flux', [(f['annee'], f['flux_mad'], f['cumul_mad']) for f in b['economie']['flux']])
print('  depense', b['depense_actuelle'])
print('  coherence', b['coherence'], b['vue_interne']['rendement_global_implicite_pct'])
# with bareme
reg = {'charges_pompage_solaire': [{'libelle':'nettoyage','montant_mad_an':1000,'source':'barème'}]}
b2 = E.economie_pompage(full, lignes=lignes, reglages=reg, sortie_etude=sortie)
print('S1b with bareme: publiable', b2['publiable_client'], 'retour', b2['economie']['retour_ans'], 'm3', b2['mad_par_m3'])
print('keys public:', sorted(E.economie_pompage_publique(b2).keys()))
# VFD no garantie
l2 = [dict(x) for x in lignes]; l2[1]['garantie_mois']=None
b3 = E.economie_pompage(full, lignes=l2, reglages=reg, sortie_etude=sortie)
print('S2 no garantie: publiable', b3['publiable_client'], b3['remplacements'][1])
l3 = [dict(x) for x in lignes]; l3[1]['garantie_mois']=12
b4 = E.economie_pompage(full, lignes=l3, reglages=reg, sortie_etude=sortie)
print('S2 garantie12:', b4['remplacements'][1]['annee'], [f for f in b4['economie']['flux'] if f['annee']==1])
print('PCI butane kwh', E.PCI_CARBURANTS[('butane','bouteille_12kg')]['kwh_par_unite'], 'hyd', E.ENERGIE_HYDRAULIQUE_KWH_PAR_M3_M)
