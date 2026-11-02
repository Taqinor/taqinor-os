SONDE = {"constat": "C-ACAL-VER2-61", "sha": "56d5b623a",
         "attendu": "resynchro d'un document MIXTE (pan sans moduleId listé AVANT un pan à fiche désignée) : "
                    "chaque ligne panneau reste celle de SON modèle — une seule ligne par produit, "
                    "la fiche désignée garde son compte (8), le pan sans fiche passe 4 -> 5 sur SA ligne ; "
                    "jamais la ligne de la fiche désignée « volée » par le modèle sans fiche puis recréée"}


def sonde(ctx):
    # ACAL63 — resynchronisation._reconcilier_panneaux_par_modele : un modèle
    # SANS fiche prend « max(restantes) » (la plus grosse ligne panneau encore
    # libre) ; s'il est itéré AVANT le modèle à fiche désignée (ordre du
    # document), il peut prendre la ligne de la fiche désignée, la porter à son
    # compte, et la fiche désignée crée alors une seconde ligne.
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.ventes.domain.catalogue import _is_panel
    from apps.ventes.domain.lignes import _classe_ligne
    from apps.ventes.domain.geometrie import lire_layout
    from authentication.models import Company
    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACAL VER2-61', slug='sonde-acal-ver2-61')
    u = User.objects.create_user(username='sonde_acal_ver2_61', password='x', role_legacy='responsable', company=co)
    api = APIClient(); api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client sonde')
    P = lambda nom, sku, prix: Produit.objects.create(company=co, nom=nom, sku=sku, prix_vente=Decimal(prix), prix_achat=Decimal('1'), quantite_stock=100)
    p550 = P('Panneau mono 550W', 'V261-550', '2290'); p450 = P('Panneau mono 450W', 'V261-450', '1900')
    P('Onduleur réseau Growatt 10kW', 'V261-OND', '14000')
    pan = lambda ident, n, m: {'id': ident, 'label': ident, 'geometry': dict(
        {'azimuthDeg': 180, 'tiltDeg': 20, 'panels': [{'cx': i, 'cy': 0} for i in range(n)]},
        **({'moduleId': m} if m else {}))}
    mods = [{'id': 'm550', 'libelle': p550.nom, 'source': 'fiche', 'produitId': p550.pk, 'pmaxWc': 550}]
    # Pan B SANS moduleId listé EN PREMIER (wattage annoncé 450), pan A à fiche désignée ensuite.
    doc = lambda nb: {'scenario': 'reseau', 'panelWatt': 450, 'modules': mods,
                      'zones': [pan('B', nb, None), pan('A', 8, 'm550')]}
    print('modeles lus', lire_layout(doc(4)).modeles)
    r = api.post('/api/django/ventes/devis/from-layout/', {'layout': doc(4), 'client': cl.pk}, format='json', HTTP_HOST='localhost')
    if r.status_code != 201:
        print('création', r.status_code, str(r.data)[:300]); return {'repro': False}
    did = r.data['id']

    def lignes():
        return sorted((li.produit_id, int(li.quantite)) for li in Devis.objects.get(pk=did).lignes.all()
                      if _classe_ligne(li, _is_panel))
    avant, ttc_avant = lignes(), Devis.objects.get(pk=did).total_ttc
    s = api.post(f'/api/django/ventes/devis/{did}/sync-layout/', doc(5), format='json', HTTP_HOST='localhost')
    apres, ttc_apres = lignes(), Devis.objects.get(pk=did).total_ttc
    print(f"création {avant} ttc {ttc_avant} ; sync {s.status_code} -> {apres} ttc {ttc_apres} "
          f"avert={str((s.data or {}).get('avertissements') if isinstance(s.data, dict) else s.data)[:300]}")
    non_nulles = [(p, q) for p, q in apres if q]
    produits = [p for p, _ in non_nulles]
    total = sum(q for _, q in non_nulles)
    p550_total = sum(q for p, q in non_nulles if p == p550.pk)
    # Attendu : une ligne non nulle par produit, 13 panneaux, la fiche désignée p550 garde 8
    # (+5 seulement si la création a déjà rangé le pan sans fiche sur p550).
    attendu_p550 = 8 + (5 if all(p == p550.pk for p, q in avant if q) else 0)
    repro = (s.status_code < 400 and
             (len(produits) != len(set(produits)) or total != 13 or p550_total != attendu_p550))
    return {'repro': repro, 'avant': avant, 'apres': apres, 'sync': s.status_code}
