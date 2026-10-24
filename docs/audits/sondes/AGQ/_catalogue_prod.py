from django.db import transaction
from django.db.models import Q
import json, sys
with transaction.atomic():
    from apps.stock.models import Produit
    from apps.parametres.models import CompanyProfile
    from authentication.models import Company
    for co in Company.objects.all()[:3]:
        print("== COMPANY", co.id, co.nom)
        prof = CompanyProfile.objects.filter(company=co).first()
        print("  profil agricole:", {k: getattr(prof,k,None) for k in ('agricole_pump_hours','agricole_part_debit_forage_pct','agricole_marge_cable_descente_m','agricole_salissure_supp_pct','pompage','agricole_fda_regle','agricole_charges_solaires')} if prof else None)
        fl=[f.name for f in Produit._meta.fields]
        print("  champs produit pompage:", [f for f in fl if any(s in f for s in ('pomp','courbe','tension','alim','role','type_pompe','actif','archiv'))])
        qs = Produit.objects.filter(company=co)
        print("  produits total:", qs.count())
        for p in qs.filter(Q(role_pompage__isnull=False)&~Q(role_pompage='')).order_by('role_pompage','pompe_kw'):
            c = p.courbe_pompe or {}
            print("   ", p.role_pompage, '|', p.id, p.nom[:55], '| kw=',p.pompe_kw, 'cv=',p.pompe_cv, 'V=',p.tension_v, 'alim=',getattr(p,'alimentation',None), 'type=',getattr(p,'type_pompe',None), '| prix=',p.prix_vente, 'achat>0=', (p.prix_achat or 0)>0, '| courbe=', bool(c.get('debits_m3h')), '| actif=', getattr(p,'is_active',getattr(p,'actif',None)), 'archive=', getattr(p,'archived',getattr(p,'est_archive',None)))
        autres = qs.filter(Q(nom__icontains='pompe')|Q(nom__icontains='variateur')|Q(nom__icontains='afficheur')|Q(nom__icontains='sonde')|Q(nom__icontains='forage')).filter(Q(role_pompage__isnull=True)|Q(role_pompage=''))
        print("  pompage-like sans role:", [(p.id,p.nom[:50],str(p.prix_vente)) for p in autres[:25]])
        pan = qs.filter(nom__icontains='panneau').order_by('-prix_vente')[:5]
        print("  panneaux:", [(p.id,p.nom[:40],str(p.prix_vente)) for p in pan])
    transaction.set_rollback(True)
