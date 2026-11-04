# flake8: noqa  (sonde d'audit — contre-visite AANA du 04/11, rejouable par scripts/sonde.py — AMET93)
"""Le prompt système de l'agent SQL (`backend/fastapi_ia/app/services/sql_agent_service.py`, schéma « Devis → ventes_devis
+ ventes_lignedevis ») prescrit au LLM : « aucun montant stocke : SUM(ventes_lignedevis.quantite *
ventes_lignedevis.prix_unitaire), remises en plus ». Sur un devis à DEUX options (sans/avec batterie) cette somme
additionne les deux paniers, alors que `Devis.total_ht` (domain.argent, option effective D9) n'en compte qu'un.
On exécute la forme EXACTE (curseur brut, filtrée sur l'id du devis) contre `total_ht` / `option_totaux`.
Transaction annulée."""
SONDE = {"constat": "C-AANA-VER4-032", "sha": "d54c88db3",
         "attendu": "devis 2 options accepté « sans » : SUM(quantite × prix_unitaire) = 50 000 ; total_ht = 18 000 (option sans) ; option « avec » = 42 000 ; aucun des deux n'égale la somme",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis", "crm.Client", "stock.Produit"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import connection
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils.options import deux_options_declarees, option_effective, option_totaux
    User = get_user_model()
    co = Company.objects.create(nom='Sonde AANA VER4-032', slug='sonde-aana-ver4-032')
    u = User.objects.create_user(username='sonde-aana-032', password='x', role_legacy='responsable', company=co)
    cli = Client.objects.create(company=co, nom='Client 032')
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AANA-032', client=cli,
                             statut=Devis.Statut.ACCEPTE, date_acceptation=date.today(),
                             option_acceptee='sans_batterie', taux_tva=Decimal('20'), remise_globale=Decimal('0'),
                             created_by=u)
    lignes = [
        ('Panneau solaire 550W', 'PAN', '', Decimal('10'), Decimal('1000')),
        ('Onduleur réseau 8 kW injection', 'OND-R', 'sans', Decimal('1'), Decimal('8000')),
        ('Onduleur hybride 8 kW', 'OND-H', 'avec', Decimal('1'), Decimal('12000')),
        ('Batterie lithium 10 kWh', 'BAT', 'avec', Decimal('1'), Decimal('20000')),
    ]
    for nom, sku, var, q, pu in lignes:
        p = Produit.objects.create(company=co, nom=nom, sku=f'SONDE-AANA032-{sku}', prix_vente=pu, quantite_stock=0)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=q, prix_unitaire=pu,
                                  remise=Decimal('0'), variante=var)
    d = Devis.objects.get(pk=d.pk)
    with connection.cursor() as c:
        c.execute("SELECT SUM(ventes_lignedevis.quantite * ventes_lignedevis.prix_unitaire) "
                  "FROM ventes_lignedevis WHERE ventes_lignedevis.devis_id = %s", [d.pk])
        somme_prompt = c.fetchone()[0]
        c.execute("SELECT SUM(ventes_lignedevis.quantite * ventes_lignedevis.prix_unitaire) "
                  "FROM ventes_devis JOIN ventes_lignedevis ON ventes_lignedevis.devis_id = ventes_devis.id "
                  "WHERE ventes_devis.statut = 'accepte' AND ventes_devis.id = %s", [d.pk])
        somme_prompt_join = c.fetchone()[0]
    obs = {'deux_options': bool(deux_options_declarees(d)), 'option_effective': option_effective(d),
           'sql_prompt_sum': str(somme_prompt), 'sql_prompt_sum_join_accepte': str(somme_prompt_join),
           'total_ht': str(d.total_ht), 'total_ttc': str(d.total_ttc),
           'option_sans_ht': str(option_totaux(d, 'sans_batterie')['ht']),
           'option_avec_ht': str(option_totaux(d, 'avec_batterie')['ht'])}
    print(obs)
    repro = obs['deux_options'] and Decimal(str(somme_prompt)) != Decimal(obs['total_ht']) \
        and Decimal(str(somme_prompt)) != Decimal(obs['option_avec_ht'])
    return {'repro': repro, **obs}
