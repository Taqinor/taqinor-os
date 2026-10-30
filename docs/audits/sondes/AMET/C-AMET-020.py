# flake8: noqa  (sonde d'acceptation AMET102, rejouable par scripts/sonde.py — AMET93) (D-ENF22)
"""Acceptation live du groupe AMET (AMET102) : rejeu PA4 « échéancier » sur UN devis de démo accepté,
non facturé, à échéancier : tranche d'acompte brouillon → émission → avoir geste commercial → tranche
suivante → tranches restantes émises → plus rien à facturer (409). Transaction annulée par sonde.py.
"""
SONDE = {
    'constat': 'C-AMET-020',
    'sha': '3bf09bfbf',
    'attendu': "facturer(acompte, brouillon) 201, émission 200, avoir 201, tranche suivante 201, reste à facturer 0 puis generer-facture 409",
}


def sonde(ctx):
    from rest_framework.test import APIClient
    from authentication.models import CustomUser
    from apps.ventes.models import Devis
    u = CustomUser.objects.get(username='demo_admin')
    d = (Devis.objects.filter(company=u.company, statut='accepte', factures__isnull=True,
                              bon_commande__isnull=True).exclude(echeancier=None)
         .exclude(echeancier=[]).order_by('-id').first())
    c = APIClient()
    c.force_authenticate(user=u)
    base = '/api/django/ventes/'
    obs, ok = {'devis': d.pk, 'reference': d.reference, 'echeancier': d.echeancier}, []

    def etat():
        r = c.get(f'{base}devis/{d.pk}/facturer/')
        j = r.json() if r.status_code == 200 else {}
        v = j.get('vente') or {}
        return r.status_code, {k: v.get(k) for k in ('prix_convenu_ttc', 'emis_ttc', 'brouillons_ttc',
                                                     'reste_a_facturer_ttc')}, j.get('prochaine_tranche')

    obs['etat_initial'] = etat()
    r = c.post(f'{base}devis/{d.pk}/facturer/', {'nature': 'acompte', 'emettre': False}, format='json')
    f1 = (r.json() or {}).get('facture', {}) if r.status_code == 201 else {}
    obs['acompte'] = (r.status_code, f1.get('reference'), f1.get('statut'), f1.get('total_ttc'),
                      None if r.status_code == 201 else r.content[:300])
    ok.append(r.status_code == 201 and f1.get('statut') == 'brouillon')
    r = c.post(f'{base}factures/{f1.get("id")}/emettre/', {}, format='json')
    obs['emission_acompte'] = (r.status_code, (r.json() or {}).get('statut') if r.status_code < 300 else r.content[:300])
    ok.append(r.status_code == 200)
    obs['etat_apres_acompte'] = etat()
    from apps.ventes.models import Facture
    fac = Facture.objects.get(pk=f1.get('id'))
    lg = fac.lignes.exclude(produit=None).first()
    r = c.post(f'{base}factures/{fac.pk}/creer-avoir/', {
        'motif': 'Geste commercial (rejeu AMET102)', 'type': 'geste_commercial',
        'lignes': [{'produit': lg.produit_id if lg else None, 'designation': 'Geste commercial',
                    'quantite': '1', 'prix_unitaire': '10.00',
                    'taux_tva': str(getattr(lg, 'taux_tva', None) or fac.taux_tva or '20.00')}]}, format='json')
    obs['avoir'] = (r.status_code, (r.json() or {}).get('reference') if r.status_code < 300 else r.content[:300])
    ok.append(r.status_code == 201)
    # même geste, avoir TOTAL (sans lignes) : seul chemin ouvert sur une facture d'acompte sans produit
    r = c.post(f'{base}factures/{fac.pk}/creer-avoir/', {'motif': 'Geste commercial total (rejeu AMET102)',
                                                        'type': 'geste_commercial'}, format='json')
    obs['avoir_total'] = (r.status_code, (r.json() or {}).get('reference') if r.status_code < 300 else r.content[:300])
    # tranches suivantes jusqu'à épuisement de l'échéancier
    tranches = []
    for _ in range(6):
        r = c.post(f'{base}devis/{d.pk}/generer-facture/', {}, format='json')
        if r.status_code != 201:
            tranches.append((r.status_code, r.content[:300]))
            break
        f = r.json()   # generer-facture ÉMET la tranche (VNT65) : statut attendu « emise »
        tranches.append((201, f.get('reference'), f.get('montant_ttc'), f.get('statut')))
        ok.append(f.get('statut') == 'emise')
    obs['tranches_suivantes'] = tranches
    ok.append(len(tranches) >= 2 and tranches[0][0] == 201)   # au moins une tranche suivante
    ok.append(tranches[-1][0] == 409)                           # plus rien à facturer
    obs['etat_final'] = etat()
    reste = (obs['etat_final'][1] or {}).get('reste_a_facturer_ttc')
    ok.append(reste is not None and float(str(reste).replace(',', '.') or 0) == 0.0)
    obs['controles'] = ok
    obs['repro'] = all(ok)
    return obs
