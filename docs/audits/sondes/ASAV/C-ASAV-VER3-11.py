SONDE = {"constat": "C-ASAV-VER3-11", "sha": "9ad3b8eb3",
         "attendu": "ASAV5 (Given complet, via POST facturer dans l'ordre) : quota 1 chantier -> [contrat 0.00, "
                    "facturable 5000.00] ; quota 2 + annule -> [contrat, contrat] ; contrat sans chantier quota 1 "
                    "-> [contrat, facturable, facturable] ; liste SAV = fiche ; GET contrat = compteur de l'annee "
                    "(2, 2, 3). repro = au moins un ecart."}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import ContratMaintenance, Equipement, PieceConsommee, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    an = timezone.localdate().year
    if timezone.localdate() < date(an, 5, 1):
        return 'STATIQUE — dates fixes fevrier-avril de l annee courante, rejouer apres le 1er mai'
    co = Company.objects.create(nom='Sonde ASAV VER3-11', slug='sonde-asav-ver3-11')
    u = get_user_model().objects.create_user(username='sonde-asav-ver3-11', password='x', company=co,
                                             role_legacy='admin')
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ASAV-311', prix_achat=Decimal('2000'),
                               prix_vente=Decimal('5000'), garantie_mois=12)
    api = APIClient()
    api.force_authenticate(u)
    H = {'HTTP_HOST': 'localhost'}

    def jeu(nom, quota, chantier, mois, annules=()):
        cl = Client.objects.create(company=co, nom='Client', prenom=nom, email=f'sonde-311-{nom}@example.invalid')
        inst = Installation.objects.create(company=co, reference=f'CHT-SONDE-311-{nom}', client=cl)
        eq = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie=f'SN-311-{nom}',
                                       date_pose=date(an - 4, 1, 1))
        eq.recompute_garanties()
        eq.save(update_fields=['date_fin_garantie', 'date_fin_garantie_production'])
        c = ContratMaintenance.objects.create(company=co, client=cl, installation=inst if chantier else None,
                                              actif=True, date_debut=date(an, 1, 1), deplacements_inclus_an=quota)
        tickets = []
        for i, m in enumerate(mois):
            t = Ticket.objects.create(company=co, reference=f'SAV-311-{nom}-{i}', client=cl, installation=inst,
                                      equipement=eq, type=Ticket.Type.CORRECTIF, created_by=u,
                                      date_ouverture=date(an, m, 10), annule=(i in annules))
            PieceConsommee.objects.create(company=co, ticket=t, produit=p, quantite=Decimal('1'), created_by=u)
            tickets.append(t)
        return c, [t for i, t in enumerate(tickets) if i not in annules]

    jeux = {'A': jeu('A', 1, True, [2, 3]), 'B': jeu('B', 2, True, [2, 3, 4], annules=(1,)),
            'C': jeu('C', 1, False, [2, 3, 4])}
    attendu = {'A': (['contrat', 'facturable'], 2), 'B': (['contrat', 'contrat'], 2),
               'C': (['contrat', 'facturable', 'facturable'], 3)}
    # Liste SAV (TicketListSerializer, cache prechargé) vs fiche, AVANT toute facture.
    rl = api.get('/api/django/sav/tickets/', {'page_size': 200}, **H)
    corps = rl.data.get('results', rl.data) if hasattr(rl, 'data') else []
    liste = {row['id']: row.get('couverture_proposee') for row in corps}
    obs, ecarts = {}, []
    for k, (c, tickets) in jeux.items():
        fiche = [api.get(f'/api/django/sav/tickets/{t.pk}/', **H).data.get('couverture_proposee') for t in tickets]
        lst = [liste.get(t.pk) for t in tickets]
        fact = []
        for t in tickets:
            r = api.post(f'/api/django/sav/tickets/{t.pk}/facturer/', {}, format='json', **H)
            t.refresh_from_db()
            prix = ([str(lg.prix_unitaire) for lg in Facture.objects.get(pk=t.facture_id_ext).lignes.all()]
                    if t.facture_id_ext else [])
            fact.append((r.status_code, (r.data or {}).get('couverture'), prix))
        gc = api.get(f'/api/django/sav/contrats-maintenance/{c.pk}/', **H)
        conso = (gc.data.get('droits_restants') or {}).get('deplacements_consommes')
        obs[k] = {'fiche': fiche, 'liste': lst, 'facturer': fact, 'contrat_consommes': conso}
        couv = [f[1] for f in fact]
        prix_ok = all((f[2] == ['0.00']) == (f[1] == 'contrat') for f in fact)
        if couv != attendu[k][0] or not prix_ok or fiche != couv or lst != couv or conso != attendu[k][1]:
            ecarts.append(k)
    print(f'liste status={rl.status_code} ; ' + ' | '.join(f'{k}: {v}' for k, v in obs.items())
          + f' ; ecarts={ecarts}')
    return {'repro': bool(ecarts), 'ecarts': ecarts, 'obs': obs}
