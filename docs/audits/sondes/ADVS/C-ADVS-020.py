# flake8: noqa  (sonde de vérification C-L4-1, rejouable par scripts/sonde.py)
"""C-L4-1 — acceptation C&I au lien public d'un client entreprise « raison sociale à confirmer » : `accept_devis`
scelle `content_hash` avec `client.nom` lu au verrou, PUIS `completer_client_depuis_acceptation` renomme le client
dans la MÊME transaction → `verifier_empreinte_signature` dit « falsifié » et `rendre_pdf_signe` REFUSE l'exemplaire.
Témoin : même parcours avec un client déjà nommé (pas à confirmer). `_store_signed_pdf` bouchonné (le constat porte
sur le sceau, en amont). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-020", "sha": "1dfa7986c",
         "attendu": "après acceptation C&I : sceau intact, exemplaire signé rendu (défaut : intacte=False, état 'refuse')",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.DevisSignature", "crm.Client"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
    from apps.ventes.domain.identite_entreprise import verifier_empreinte_signature
    from apps.ventes.domain.modifiabilite import empreinte_contenu_signable
    from apps.ventes.domain import pdf_signe
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 020', slug='sonde-advs-020')
    u = U.objects.create_user(username='sonde-advs-020', password='x', role_legacy='admin', company=c)
    prods = [Produit.objects.create(company=c, nom=n, sku=f'ADVS020-{i}', prix_vente=Decimal(p), tva=Decimal('20'),
                                    quantite_stock=100)
             for i, (n, p) in enumerate((('Panneau Canadien Solar 710W', '1166.67'),
                                         ('Onduleur réseau Huawei 30kW Triphasé', '42000'),
                                         ('Structure aluminium toiture', '300')))]
    obs = {}

    def cas(etiquette, a_confirmer):
        cl = Client.objects.create(company=c, nom='Karim Exemple', type_client=Client.TypeClient.ENTREPRISE,
                                   raison_sociale_a_confirmer=a_confirmer, contact_nom='Karim Exemple',
                                   email=f'sonde-advs-020-{etiquette}@example.invalid')
        d = Devis.objects.create(company=c, reference=f'DEV-ADVS020-{etiquette}', client=cl, statut='envoye',
                                 taux_tva=Decimal('20'), created_by=u, mode_installation='commercial')
        for i, (p, q) in enumerate(zip(prods, ('40', '1', '40'))):
            LigneDevis.objects.create(devis=d, produit=p, designation=p.nom, quantite=Decimal(q),
                                      prix_unitaire=p.prix_vente, remise=Decimal('0'), ordre=i)
        link = ShareLink.objects.create(company=c, devis=d)
        o = {}
        try:
            emp = empreinte_contenu_signable(Devis.objects.get(pk=d.pk), link=link)
        except Exception as e:
            o['empreinte_err'] = repr(e)[:200]
            emp = None
        corps = {'nom': 'Karim Exemple', 'consent_esign': True, 'empreinte_contenu': emp,
                 'entreprise': {'raison_sociale': 'Boulangerie Exemple SARL', 'signataire_qualite': 'Gérant',
                                'ice': '001234567000089', 'signataire_nom': 'Karim Exemple',
                                'signataire_email': f'karim-{etiquette}@example.invalid', 'pouvoir_engager': True}}
        try:
            with mock.patch('apps.ventes.public_views._notify_open'):
                with transaction.atomic():
                    r = APIClient().post(f'/api/django/public/proposal/{link.token}/accept/', corps, format='json',
                                         HTTP_HOST='localhost')
            o['http'] = r.status_code
            try:
                rj = json.loads(r.content.decode() or '{}')
                o['detail'] = rj.get('detail'), rj.get('code')
            except Exception:
                pass
        except Exception as e:
            o['http'] = repr(e)[:200]
        d2 = Devis.objects.select_related('client').get(pk=d.pk)
        cl.refresh_from_db()
        o['statut'] = d2.statut
        o['client_nom_apres'] = cl.nom
        o['a_confirmer_apres'] = cl.raison_sociale_a_confirmer
        sig = DevisSignature.objects.filter(devis=d2).first()
        o['signature'] = bool(sig)
        if sig is None:
            return o
        v = verifier_empreinte_signature(d2)
        o['verif'] = [v.get('intacte'), v.get('version'), (v.get('message') or '')[:70]]
        # le même sceau recalculé avec l'ancien nom concorde-t-il ? (preuve de la cause)
        try:
            with transaction.atomic():
                Client.objects.filter(pk=cl.pk).update(nom='Karim Exemple')
                d3 = Devis.objects.select_related('client').get(pk=d.pk)
                o['intacte_si_ancien_nom'] = verifier_empreinte_signature(d3).get('intacte')
                transaction.set_rollback(True)
        except Exception as e:
            o['intacte_si_ancien_nom'] = repr(e)[:120]
        appels = []
        with mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf', side_effect=lambda **k: appels.append(1)):
            try:
                with transaction.atomic():
                    o['etat_pdf_signe'] = pdf_signe.rendre_pdf_signe(d.pk)
            except Exception as e:
                o['etat_pdf_signe'] = repr(e)[:160]
        o['store_signed_pdf_appele'] = len(appels)
        return o

    obs['A_a_confirmer'] = cas('A', True)
    obs['T_temoin_nomme'] = cas('T', False)
    a = obs['A_a_confirmer']
    repro = bool(a.get('statut') == 'accepte' and a.get('verif') and a['verif'][0] is False
                 and a.get('etat_pdf_signe') == 'refuse')
    return {'repro': repro, 'observe': obs}
