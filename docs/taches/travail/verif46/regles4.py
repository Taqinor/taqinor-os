"""Recalcul des exemples de spec-4 (stdlib seule). Jours ouvres = lun-ven moins feries donnes."""
import datetime as dt, math
D=dt.date
def ouvres(du,au,feries=()):  # [du,au] inclusif
    s=set();j=du
    while j<=au:
        if j.weekday()<5 and j not in feries: s.add(j)
        j+=dt.timedelta(1)
    return s
def prochain_ouvre(d,feries=()):
    while d.weekday()>=5 or d in feries: d+=dt.timedelta(1)
    return d
print("jours:",{x:D(*x).strftime('%a') for x in [(2026,11,3),(2026,11,17),(2026,11,22),(2026,11,23),(2026,11,6),(2026,11,18)]})
# a_l_arret : ]ref, today]
ref=D(2026,11,3); auj=D(2026,11,17)
n=len(ouvres(ref+dt.timedelta(1),auj)); n2=len(ouvres(ref+dt.timedelta(1),auj,{D(2026,11,6)}))
print("arret: sans ferie",n,"-> arret" if n>=10 else "non","; avec 06/11",n2,"-> arret" if n2>=10 else "non")
# calendrier marocain reel : 06/11 Marche verte, 18/11 Independance
n3=len(ouvres(ref+dt.timedelta(1),auj,{D(2026,11,6)}))
print("arret calendrier MA reel (06/11 ferie):",n3)
# echeance menacee (d)
F28,J28,O,reste=8,20,12,15
besoin=math.ceil(O*J28/F28); print("besoin",besoin,"reste",reste,"menacee",besoin>reste)
# cas simple : projet 2 taches, 1 faite sur 28j -> F28<5 -> silence ; projet neuf F28=0
for F in (0,1,4,5):
    print("F28",F,"signal (d) actif" if F>=5 else "silence")
# echeance aujourd'hui: reste = ouvres(]auj,auj]) = 0
print("reste si echeance=aujourdhui:",len(ouvres(auj+dt.timedelta(1),auj)))
# decaler
for d0,delta in [(D(2026,11,22),7),(D(2026,11,23),-1),(D(2026,11,21),-1)]:
    brut=d0+dt.timedelta(delta); print("decaler",d0,delta,"->",brut,brut.strftime('%a'),"->",prochain_ouvre(brut))
# modele J+5 depuis lun 23/11
b=D(2026,11,23)+dt.timedelta(5); print("modele",b,b.strftime('%a'),"->",prochain_ouvre(b))
# critere 9 : echeance 22/11 + 7
print("crit9", prochain_ouvre(D(2026,11,22)+dt.timedelta(7)))
# critere 10 : jour_prevu = demain (18/11) delta -2 -> 16/11 < 17/11 -> refus
print("crit10", D(2026,11,18)+dt.timedelta(-2) < auj)
# critere 10 variante calendrier MA : demain 18/11 ferie ; delta -2 -> 16/11 refuse ; delta -1 -> 17/11 accepte
# neglige
def neglige(projets):  # projets: nom->(prio,d,actionnables,anciennete_j)
    out=[]
    for p,(pr,d,act,anc) in projets.items():
        if act>=1 and anc>=14 and d==0 and any(q!=p and pq<pr and dq>=1 for q,(pq,dq,_,_) in projets.items()):
            out.append(p)
    return out
print("neglige ex", neglige({'A':(3,0,1,20),'B':(2,4,1,20),'C':(1,1,1,20)}))
print("neglige tous 0", neglige({'A':(3,0,1,20),'B':(2,0,1,20),'C':(1,0,1,20)}))
print("neglige B aussi", neglige({'A':(3,0,1,20),'B':(2,0,1,20),'C':(1,1,1,20)}))
print("neglige Q sans actionnable", neglige({'A':(3,0,1,20),'C':(1,1,0,20)}))
# cycle detection 50 maillons
def accepte(chaine_len_jusqua_T):  # T rencontre a la position k en remontant depuis B
    return not (chaine_len_jusqua_T<=50)
print("cycle T a 51 maillons accepte ?", accepte(51))
# burnup : total(s) = comptees creees <= fin(s) et non annulees <= fin(s)
