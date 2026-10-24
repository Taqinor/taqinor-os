from cat4 import *
from core.pompage.selection import choisir_pompe
from core.pompage.tailles import proposer_tailles
from core.pompage.conception import conception
from core.pompage.volumes import mois_critique as mc_prod
P=profils(); V=variateurs(FICHE_VEI)
base=[20,30,50,80,110,140,160,155,110,60,30,20]
hits=0
for scale in [x/10 for x in range(5,40)]:
  for hmt in (50,60,70,80,90):
    serie=[round(v*scale,1) for v in base]
    b={'m3_jour_mois':serie,'nature':'declare'}
    c=conception(besoin=b,profils_horaires=P,niveau_eau_m=10,debit_exploitation_m3h=200)
    q=c['conception']['debit_conception_m3h']; m=c['conception']['mois_critique']
    ch=choisir_pompe(catalogue(True),hmt_m=hmt,debit_conception_m3h=q,alimentation='tri')
    if ch['etape']!='courbe': continue
    t=proposer_tailles(choix_pompe=ch,besoin_m3_jour_mois=serie,hmt_m=hmt,alimentation='tri',variateurs=V,panneau=PANNEAU,mois_critique=m,profils_horaires=P)
    rec=[x for x in t['tailles'] if x['cle']=='recommandee'][0]
    cp=rec['couverture_pct_mois']; 
    if cp is None: continue
    worst=min((v,i+1) for i,v in enumerate(cp) if v is not None)
    if worst[0]<100:
      hits+=1
      if hits<=6:
        c2=conception(besoin=b,profils_horaires=P,production_m3_jour_mois=rec['m3_jour_mois'],niveau_eau_m=10,debit_exploitation_m3h=200)
        print('scale',scale,'hmt',hmt,'q',q,'mois_crit(heures_pic)',m,'prod-critical',mc_prod(serie,rec['m3_jour_mois']),'rec cov@crit',rec['couverture_mois_critique_pct'],'worst',worst,'pump',rec['pompe_nom'][:24],'nb',rec['nb_panneaux'],'controle',c2['controle_conception']['statut'],c2['controle_conception']['couverture_mois_critique_pct'])
print('hits',hits)
