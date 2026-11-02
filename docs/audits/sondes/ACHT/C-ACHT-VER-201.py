SONDE = {"constat": "C-ACHT-VER-201", "sha": "c6ab9b58e",
         "attendu": "ACHT46 : une serie relevee AVANT la reception, datee comme le fait "
                    "installations/field_capture.py (date_pose_reelle du chantier, pas le jour du releve), "
                    "est recalee a la date de reception par sweep_bom_to_parc : meme parc (memes dates) "
                    "dans les deux ordres releve/reception"}


def sonde(ctx):
    from datetime import date
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import Equipement
    from apps.sav.services import assurer_equipement_chantier, sweep_bom_to_parc
    from apps.stock.models import Produit

    reception = date(2026, 10, 12)
    pose_reelle = date(2026, 10, 5)  # field_capture : date_reception or date_pose_reelle or ...
    co = Company.objects.create(nom='SONDE-ACHT-VER-201', slug='sonde-acht-ver-201')
    cli = Client.objects.create(company=co, nom='Client', prenom='VER201')
    pan = Produit.objects.create(company=co, nom='Panneau', sku='PAN-VER201', prix_achat=0,
                                 prix_vente=10, garantie_mois=120)

    def chantier(ref):
        return Installation.objects.create(
            company=co, reference=ref, client=cli, date_pose_reelle=pose_reelle,
            bom=[{'produit_id': pan.id, 'designation': 'Panneau', 'quantite': 12}])

    def balayage(inst):
        return sweep_bom_to_parc(installation=inst, company=co, date_pose=reception,
                                 created_by=None, resolve_produit={pan.id: pan}.get)

    def parc(inst):
        return sorted((bool(e.numero_serie), str(e.date_pose), str(e.date_fin_garantie))
                      for e in Equipement.objects.filter(installation=inst, produit=pan))

    # Ordre A : reception puis releve (field_capture passe alors date_reception).
    a = chantier('CH-VER201-A')
    balayage(a)
    assurer_equipement_chantier(company=co, installation=a, produit=pan, numero_serie='SN-VER201-A',
                                quantite_ligne=12, date_pose=reception, created_by=None)
    # Ordre B : releve AVANT reception (field_capture passe date_pose_reelle), puis reception.
    b = chantier('CH-VER201-B')
    assurer_equipement_chantier(company=co, installation=b, produit=pan, numero_serie='SN-VER201-B',
                                quantite_ligne=12, date_pose=pose_reelle, created_by=None)
    balayage(b)
    pa, pb = parc(a), parc(b)
    print('ORDRE A', pa)
    print('ORDRE B', pb)
    dates_b = {d for _, d, _ in pb}
    return {'repro': pa != pb or dates_b != {str(reception)}}
