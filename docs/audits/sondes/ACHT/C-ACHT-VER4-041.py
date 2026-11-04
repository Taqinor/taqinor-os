# flake8: noqa  (sonde de contre-visite vérifie ACHT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ACHT72 (jumeau oublié) : `cocher_outil_ligne` sort l'outil du parc (« En intervention », emplacement
vidé) et seul le DÉCOCHAGE de la ligne ou `confirmer-tool-return` le rendent. Or
`views/intervention.py::choisir_kit` puis `field_services._sync_outils` SUPPRIMENT la ligne d'un outil
qui n'est plus dans le kit (kit retiré ou changé) sans libérer l'outil : `confirmer_tool_return` ne
traite que les outils des lignes COCHÉES (`charges`), l'outil n'y est plus ⇒ jamais rendu. L'outil
reste « En intervention », sans emplacement ; la même intervention ne peut même plus le recharger
(409 « Outil déjà sorti. ») et toute autre intervention le voit en conflit. Témoin : décocher avant
de changer de kit ⇒ Disponible au Dépôt. Chaîne API réelle (responsable). Transaction annulée."""
SONDE = {"constat": "C-ACHT-VER4-041", "sha": "fcbed3760",
         "modeles": ["outillage.Outillage", "outillage.KitOutillage", "outillage.KitOutillageItem",
                     "installations.PreparationOutilLigne", "installations.ToolReturn",
                     "installations.InterventionPreparation", "installations.Intervention",
                     "installations.Installation", "stock.EmplacementStock",
                     "authentication.Company", "authentication.User"],
         "attendu": "cocher C (200) puis choisir-kit null (200) puis confirmer-tool-return (200) : C reste "
                    "en_intervention sans emplacement ; re-choisir le kit puis cocher C : 409 ; "
                    "témoin (décocher d'abord) : disponible au Dépôt"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations import field_services
    from apps.installations.models import Installation, Intervention
    from apps.outillage.models import KitOutillage, KitOutillageItem, Outillage
    from apps.stock.models import EmplacementStock

    co = Company.objects.create(nom='Sonde ACHT VER4-041', slug='sonde-acht-ver4-041')
    u = get_user_model().objects.create_user(username='sonde-acht-v4-041', password='x', company=co,
                                             role_legacy='responsable')
    depot = EmplacementStock.objects.create(company=co, nom='Dépôt sonde 041')
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/installations/interventions'
    inst = Installation.objects.create(company=co, reference='CH-SONDE-V4-041')

    def preparer(nom_outil):
        outil = Outillage.objects.create(company=co, nom=nom_outil, emplacement=depot)
        kit = KitOutillage.objects.create(company=co, nom=f'Kit {nom_outil}', type_intervention='pose')
        KitOutillageItem.objects.create(company=co, kit=kit, outil=outil, ordre=0)
        iv = Intervention.objects.create(company=co, installation=inst, type_intervention='pose',
                                         created_by=u, technicien=u)
        prep = field_services.ensure_preparation(iv)
        prep.kit = kit
        prep.save()
        field_services._sync_outils(prep)
        return outil, kit, iv

    def ligne(iv, outil):
        return iv.preparation.outils.filter(outil=outil).values_list('id', flat=True).first()

    def post(url, corps):
        r = api.post(url, corps, format='json', HTTP_HOST='localhost')
        return r.status_code, (r.data if r.status_code >= 400 else None)

    def etat(outil):
        o = Outillage.objects.get(pk=outil.pk)
        return o.statut, (o.emplacement.nom if o.emplacement_id else None)

    # Scénario : outil chargé, puis kit retiré de la préparation.
    c, kit, iv = preparer('C sonde 041')
    etapes = {'cocher': post(f'{B}/{iv.id}/cocher-outil/', {'ligne': ligne(iv, c), 'coche': True})}
    etapes['apres_cocher'] = etat(c)
    etapes['retirer_kit'] = post(f'{B}/{iv.id}/choisir-kit/', {'kit': None})
    etapes['lignes_outils'] = iv.preparation.outils.count()
    etapes['confirmer_retour'] = post(f'{B}/{iv.id}/confirmer-tool-return/', {})
    etapes['apres_confirmer'] = etat(c)
    etapes['remettre_kit'] = post(f'{B}/{iv.id}/choisir-kit/', {'kit': kit.id})
    etapes['recocher'] = post(f'{B}/{iv.id}/cocher-outil/', {'ligne': ligne(iv, c), 'coche': True})
    obs = etat(c)

    # Témoin : décocher avant de retirer le kit.
    t, _kit2, iv2 = preparer('T sonde 041')
    temoin = {'cocher': post(f'{B}/{iv2.id}/cocher-outil/', {'ligne': ligne(iv2, t), 'coche': True}),
              'decocher': post(f'{B}/{iv2.id}/cocher-outil/', {'ligne': ligne(iv2, t), 'coche': False}),
              'retirer_kit': post(f'{B}/{iv2.id}/choisir-kit/', {'kit': None})}
    temoin['etat'] = etat(t)
    print(f'etapes={etapes} obs={obs} temoin={temoin}')
    repro = (etapes['cocher'][0] == 200 and etapes['retirer_kit'][0] == 200
             and etapes['confirmer_retour'][0] == 200
             and etapes['apres_confirmer'] == (Outillage.Statut.EN_INTERVENTION, None)
             and etapes['recocher'][0] == 409
             and temoin['etat'] == (Outillage.Statut.DISPONIBLE, 'Dépôt sonde 041'))
    return {'repro': repro, 'etapes': etapes, 'observe': obs, 'temoin': temoin}
