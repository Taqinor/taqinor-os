import sys
sys.path.insert(0, r"C:\dev\taqinor-os\.claude\worktrees\agricultural-quote-engine-test-bb0ece\backend\django_core")
D=[0,12,24,30,36,39]
OSP=[('Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)','10','7.5',[91,85,70,60,43,34]),
('Pompe immergée OSP 30/11 — 12.5 CV / 9.3 kW (3", 380V)','12.5','9.3',[125,117,97,83,59,46]),
('Pompe immergée OSP 30/13 — 15 CV / 11 kW (3", 380V)','15','11',[148,138,114,98,70,55]),
('Pompe immergée OSP 30/15 — 17.5 CV / 13 kW (3", 380V)','17.5','13',[171,159,132,113,81,63]),
('Pompe immergée OSP 30/16 — 20 CV / 15 kW (3", 380V)','20','15',[182,170,141,120,86,67]),
]
GEN=[('Pompe immergée solaire 1.5 CV Monophasé','1.5'),('Pompe immergée solaire 3 CV Monophasé','3'),
('Pompe immergée solaire 4 CV Triphasé','4'),('Pompe immergée solaire 5.5 CV Triphasé','5.5'),
('Pompe immergée solaire 7.5 CV Triphasé','7.5'),('Pompe immergée solaire 10 CV Triphasé','10'),
('Pompe de surface solaire 1.5 CV Monophasé','1.5'),('Pompe de surface solaire 3 CV Triphasé','3')]
def alim_sel(nom, tension):
    # mirror stock.selectors._alimentation_pompage_pour
    if tension==220: return 'mono'
    if tension==380: return 'tri'
    n=nom.lower()
    if 'monophas' in n: return 'mono'
    if 'triphas' in n: return 'tri'
    import re
    if re.search(r'(?<![\d.,])220\s*v', n): return 'mono'
    if re.search(r'(?<![\d.,])380\s*v', n): return 'tri'
    return ''
def type_sel(nom):
    n=nom.lower()
    if 'surface' in n: return 'surface'
    if 'immerg' in n: return 'immergee'
    return ''
def catalogue(osp_priced=False):
    out=[]; i=1
    for nom,cv,kw,h in OSP:
        out.append({'id':i,'nom':nom,'role_pompage':'pompe','type_pompe':type_sel(nom),'alimentation':alim_sel(nom,380),
                    'pompe_cv':cv,'pompe_kw':kw,'tension_v':380,'courbe_pompe':{'debits_m3h':D,'hmt_m':h},'fiche':{},
                    'prix_connu':osp_priced}); i+=1
    for nom,cv in GEN:
        out.append({'id':i,'nom':nom,'role_pompage':'pompe','type_pompe':type_sel(nom),'alimentation':alim_sel(nom,None),
                    'pompe_cv':cv,'pompe_kw':None,'tension_v':None,'courbe_pompe':None,'fiche':{},'prix_connu':True}); i+=1
    return out
VEI=[('VARIATEUR VEICHI SI22 2.2KW 220V','2.2',220),('VARIATEUR VEICHI SI23 2.2KW 220V','2.2',220),('VARIATEUR VEICHI SI23 2.2KW 380V','2.2',380),
('VARIATEUR VEICHI SI23 4KW 380V','4',380),('VARIATEUR VEICHI SI23 5.5KW 380V','5.5',380),('VARIATEUR VEICHI SI23 7.5KW 380V','7.5',380),
('VARIATEUR VEICHI SI23 11KW 380V','11',380),('VARIATEUR VEICHI SI23 15KW 380V','15',380),('VARIATEUR VEICHI SI23 18KW 380V','18',380)]
def variateurs(fiche=None):
    return [{'id':100+i,'nom':n,'role_pompage':'variateur_pompage','pompe_kw':k,'tension_v':t,'fiche':dict(fiche or {}),'prix_connu':True}
            for i,(n,k,t) in enumerate(VEI)]
import math
# synthetic PVGIS-like profiles: day length & peak per month (Morocco-ish, tilted plane)
DAYLEN=[10.2,11.0,12.0,13.0,13.8,14.3,14.1,13.4,12.4,11.4,10.5,10.0]
PEAK=[900,950,980,990,980,960,950,960,970,940,900,880]
def profils(peak=PEAK, daylen=DAYLEN):
    out=[]
    for m in range(12):
        L=daylen[m]; sr=12.5-L/2; prof=[]
        for h in range(24):
            t=h+0.5
            x=(t-sr)/L
            prof.append(round(peak[m]*math.sin(math.pi*x),1) if 0<x<1 else 0.0)
        out.append(prof)
    return out
PANNEAU={'id':500,'nom':'Panneau 710 Wc','pmax_wc':710,'vmp_v':40.3,'voc_v':48.6,'isc_a':18.6,'imp_a':17.6,'prix_connu':True}
FICHE_VEI={'ond_mppt_v_min':250,'ond_mppt_v_max':750,'ond_v_max_abs':800,'ond_i_max_mppt_a':20,'ond_phases':3}
