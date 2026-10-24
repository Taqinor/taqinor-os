from cat4 import *
from core.pompage.selection import choisir_pompe
from core.pompage.tailles import proposer_tailles
from core.pompage.conception import conception, besoin_retenu
P=profils(); V=variateurs(FICHE_VEI)
hits=[]
for hmt in range(40,121,5):
  for B in range(60,700,10):
    b=besoin_retenu(volume_declare_m3_jour=B)
    c=conception(besoin=b,profils_horaires=P,niveau_eau_m=10,debit_exploitation_m3h=100)
    q=c['conception']['debit_conception_m3h']; m=c['conception']['mois_critique']
    ch=choisir_pompe(catalogue(True),hmt_m=hmt,debit_conception_m3h=q,alimentation='tri')
    if ch['etape']!='courbe': continue
    t=proposer_tailles(choix_pompe=ch,besoin_m3_jour_mois=b['m3_jour_mois'],hmt_m=hmt,alimentation='tri',variateurs=V,panneau=PANNEAU,mois_critique=m,profils_horaires=P)
    rec=[x for x in t['tailles'] if x['cle']=='recommandee']
    if rec:
      cv=rec[0]['couverture_mois_critique_pct']
      if cv is not None and cv<100:
        hits.append((hmt,B,q,rec[0]['pompe_nom'][:22],cv,rec[0]['nb_panneaux'],[a['code'] for a in t['alertes']],[a['code'] for a in rec[0]['champ']['alertes'] if a['code'].startswith('besoin')]))
for h in hits[:15]: print(h)
print('n hits',len(hits))
