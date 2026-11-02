SONDE = {"constat": "C-ACAL-VER2-81", "sha": "56d5b623a",
         "attendu": "ACAL346 CAL_KWC_DEVIS_VS_CALEPINAGE : un devis COHERENT (16 panneaux 550 W chiffres, 16 modules poses au calepinage, "
                    "document de l'atelier portant geometry.kwc calcule au wattage OUTIL 720 W) ne leve AUCUNE violation kWc ; "
                    "aujourd'hui la regle compare 11,52 kWc (outil, pans_du_document -> geometry.kwc) a 8,8 kWc (lignes) et leve un faux ecart ~31 %"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from apps.calepinage.models import Calepinage
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.coherence.registre import REGISTRE, charger_regles
    from apps.ventes.domain.geometrie import layout_hash
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    from apps.ventes.models import Devis
    from authentication.models import Company
    charger_regles()
    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACAL VER2-81', slug='sonde-acal-ver2-81')
    u = User.objects.create_user(username='sonde_acal_ver2_81', password='x', role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Client sonde')
    pan = Produit.objects.create(company=co, nom='Panneau Jinko 550W', sku='VER2-81-PAN',
                                 prix_vente=Decimal('1100'), prix_achat=Decimal('1'), quantite_stock=100)
    # Document tel que l'atelier l'ecrit : compte 16, kWc de l'OUTIL (16 x 720 W).
    layout = {'panelWatt': 720,
              'zones': [{'id': 'z1', 'label': 'Sud',
                         'geometry': {'count': 16, 'kwc': 11.52, 'azimuthDeg': 180, 'tiltDeg': 20}}]}
    devis = Devis.objects.create(company=co, reference='DEV-VER2-81', client=cl, created_by=u,
                                 taux_tva=Decimal('20'), layout_hash=layout_hash(layout))
    devis.lignes.create(produit=pan, designation='Panneau Jinko 550W', quantite=Decimal(16),
                        prix_unitaire=Decimal('1100'))
    Calepinage.objects.create(company=co, client=cl, devis=devis, titre='Villa', roof_layout=layout,
                              layout_hash=layout_hash(layout), version_moteur='2.1.0')
    out = {}
    for rid in ('CAL_MODULES_DEVIS_VS_CALEPINAGE', 'CAL_KWC_DEVIS_VS_CALEPINAGE', 'CAL_EMPREINTE_IMPRIMEE_PERIMEE'):
        r = REGISTRE[rid]
        out[rid] = [getattr(v, 'valeurs', None) for v in r.check(r, devis, None)]
    print('kwc_devis', puissance_kwc_du_devis(devis), 'violations', out)
    # repro = faux positif kWc alors que modules et empreinte concordent
    return {'repro': bool(out['CAL_KWC_DEVIS_VS_CALEPINAGE'])
            and not out['CAL_MODULES_DEVIS_VS_CALEPINAGE']
            and not out['CAL_EMPREINTE_IMPRIMEE_PERIMEE'],
            'violations': out}
