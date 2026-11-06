# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K66 — chantier à plusieurs interventions : valider la consommation terrain (F11) de la PREMIÈRE
intervention libère-t-il les réservations des produits qu'elle n'a pas posés ?
Chantier A (devis accepté : 10 panneaux, 1 onduleur, 1 batterie ; stock 30 / 1 / 1) ; chantier B (devis
accepté : 1 onduleur). Intervention 1 de A (pose panneaux) : F11 amorcée par la vraie route `consommation/`,
onduleur et batterie passés à 0 avec justification « posés à l'intervention 2 » par
`modifier-ligne-consommation`, puis `valider-consommation`. On lit les réservations de A, le besoin matériel de
A et de B (`compute_besoin_materiel`, onglet « Matériel & BC »), puis ce qu'amorce la F11 d'une intervention 2.
Comportement observé à faire trancher (D-ACHT-1 « reliquat libéré ») ; `repro` = la libération a lieu."""
SONDE = {"constat": "C-AAPV-086", "sha": "6ffa876688",
         "attendu": "repro si après F11 de l'intervention 1 : réservations onduleur/batterie de A active=False ; B voit l'onduleur disponible (manque 0) ; A affiche l'onduleur non réservé",
         "modeles": ["stock.MouvementStock", "stock.Produit", "installations.StockReservation",
                     "installations.Installation", "installations.Intervention", "installations.MaterielConsommation",
                     "installations.ConsommationLigne", "ventes.Devis"]}


def sonde(ctx):
    from apps.crm import stages
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.installations.models import Intervention, StockReservation
    from apps.installations.services import create_installation_from_devis
    from apps.stock.models import Produit
    from apps.stock.services import compute_besoin_materiel
    from apps.ventes.models import Devis, LigneDevis
    H = {'HTTP_HOST': 'localhost'}
    I = '/api/django/installations/interventions'
    co = Company.objects.create(nom='Sonde AAPV 086', slug='sonde-aapv-086')
    u = get_user_model().objects.create_user(username='sonde_aapv_086', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    pan = Produit.objects.create(company=co, nom='Panneau AAPV86', sku='AAPV-086-PAN', prix_vente=Decimal('100'),
                                 quantite_stock=30, tva=Decimal('20.00'))
    ond = Produit.objects.create(company=co, nom='Onduleur AAPV86', sku='AAPV-086-OND', prix_vente=Decimal('5000'),
                                 quantite_stock=1, tva=Decimal('20.00'))
    bat = Produit.objects.create(company=co, nom='Batterie AAPV86', sku='AAPV-086-BAT', prix_vente=Decimal('6000'),
                                 quantite_stock=1, tva=Decimal('20.00'))

    def chantier(tag, lignes):
        cl = Client.objects.create(company=co, nom=f'Site {tag}', prenom='Client', email=f'aapv86{tag}@example.invalid')
        lead = Lead.objects.create(company=co, nom=f'Site {tag}', prenom='Client', stage=stages.SIGNED,
                                   type_installation='residentiel')
        d = Devis.objects.create(company=co, reference=f'DEV-AAPV86-{tag}', client=cl, lead=lead,
                                 statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
        for p, q in lignes:
            LigneDevis.objects.create(devis=d, produit=p, designation=p.nom, quantite=Decimal(q),
                                      prix_unitaire=p.prix_vente, taux_tva=Decimal('20.00'))
        inst, _ = create_installation_from_devis(d, u, co)
        return inst

    def resas(inst):
        return {r.produit.sku: (r.quantite, r.active, r.consomme) for r in
                StockReservation.objects.filter(installation=inst).select_related('produit')}

    def besoin(inst, p):
        for e in compute_besoin_materiel(inst):
            if e['produit_id'] == p.id:
                return {k: e.get(k) for k in ('requis', 'disponible', 'reserve_chantier', 'reserve_autres',
                                              'deja_sorti', 'manque_brut', 'manque')}
        return None

    A = chantier('A', [(pan, 10), (ond, 1), (bat, 1)])
    B = chantier('B', [(ond, 1)])
    obs = {'resas_A_avant': resas(A), 'resas_B_avant': resas(B),
           'besoin_B_onduleur_avant': besoin(B, ond)}
    itv1 = Intervention.objects.create(company=co, installation=A, type_intervention=Intervention.Type.POSE)
    g = api.get(f'{I}/{itv1.id}/consommation/', **H)
    lignes = (g.data or {}).get('lignes') or []
    obs['f11_itv1_amorcee'] = [(li.get('designation'), str(li.get('quantite_prevue')), str(li.get('quantite_utilisee')))
                               for li in lignes]
    mods = []
    for li in lignes:
        if li.get('produit') in (ond.id, bat.id):
            m = api.post(f'{I}/{itv1.id}/modifier-ligne-consommation/',
                         {'ligne': li['id'], 'quantite_utilisee': '0',
                          'justification': 'posé à l\'intervention 2 (onduleur / batterie)'}, format='json', **H)
            mods.append(m.status_code)
    v = api.post(f'{I}/{itv1.id}/valider-consommation/', {}, format='json', **H)
    for p in (pan, ond, bat):
        p.refresh_from_db()
    obs.update({'modifier_lignes': mods, 'valider_itv1': v.status_code,
                'valider_detail': None if v.status_code < 400 else str(v.data)[:140],
                'stock_apres': {'PAN': str(pan.quantite_stock), 'OND': str(ond.quantite_stock),
                                'BAT': str(bat.quantite_stock)},
                'resas_A_apres': resas(A),
                'besoin_A_onduleur_apres': besoin(A, ond),
                'besoin_B_onduleur_apres': besoin(B, ond)})
    itv2 = Intervention.objects.create(company=co, installation=A, type_intervention=Intervention.Type.POSE)
    g2 = api.get(f'{I}/{itv2.id}/consommation/', **H)
    obs['f11_itv2_amorcee'] = [(li.get('designation'), str(li.get('quantite_prevue')),
                                str(li.get('quantite_utilisee')))
                               for li in ((g2.data or {}).get('lignes') or [])]
    print(obs)
    ra = obs['resas_A_apres']
    libere = (v.status_code == 200 and ra.get('AAPV-086-OND', (0, True))[1] is False
              and ra.get('AAPV-086-BAT', (0, True))[1] is False)
    obs['repro'] = bool(libere)
    return obs
