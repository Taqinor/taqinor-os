# flake8: noqa  (sonde de contre-visite vérifie ACHT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ACHT53 (C-ACHT-052 / C-ACHT-043) : le test `tests_acht53_fk_purge_allowlist.py::FkPurgeAllowlistTests`
est un SimpleTestCase STATIQUE (type du champ = CompanyScopedPrimaryKeyRelatedField), sans rejeu en base.
Cette sonde rejoue en base réelle, pour chaque couple (sérialiseur installations, FK inscriptible) de la
liste du test, `to_internal_value` (via `is_valid(partial=True)`) avec l'id d'une ligne EXISTANTE d'une
AUTRE société que celle de la requête, puis (témoin) avec la société de cette ligne.
Source réelle : `core/mixins.SameCompanyFKSerializerMixin`, `core/serializers.scope_related_field`.
Transaction annulée ; aucun objet créé (utilisateur non persisté). Jamais contre la prod."""
SONDE = {"constat": "C-ACHT-052", "sha": "fcbed3760",
         "attendu": "pour chaque couple testable : id d'une autre société refusé sous le champ (400 does_not_exist ou 404), "
                    "même id accepté sur le champ quand la requête porte la société de la ligne ; aucun couple fuyant",
         "modeles": ["authentication.Company", "authentication.CustomUser", "installations.Installation",
                     "installations.Reserve", "installations.Livraison"]}

COUPLES = {
    'EquipeSerializer': ('chef', 'membres'),
    'EtapeApprobationAchatSerializer': ('approbateur', 'demande', 'regle'),
    'GeofenceAlertSerializer': ('acquittee_par',),
    'OrdreAssemblageSerializer': ('responsable', 'kit', 'chantier', 'ordre_sous_traitance'),
    'ProjetTacheSerializer': ('assigne', 'projet'),
    'ReserveSerializer': ('assignee', 'memo'),
    'RevisionKitSerializer': ('user', 'kit'),
    'AppelCommandeSerializer': ('chantier',),
    'BinAffectationSerializer': ('bin',),
    'BinLocationSerializer': ('categorie',),
    'BudgetEngagementSerializer': ('budget',),
    'BudgetProjetSerializer': ('projet',),
    'ChecklistEtapeModeleSerializer': ('template',),
    'ColisLigneSerializer': ('colis',),
    'ColisSerializer': ('installation',),
    'CommandeCadreLigneSerializer': ('commande_cadre',),
    'ConsommationLigneSerializer': ('justification_memo',),
    'ContratPrixLigneSerializer': ('contrat',),
    'ControleQualiteItemModeleSerializer': ('modele',),
    'ControleQualiteModeleSerializer': ('kit',),
    'ControleQualiteOrdreSerializer': ('ordre',),
    'DemandeAchatLigneSerializer': ('demande',),
    'DemandeAchatSerializer': ('chantier', 'programme'),
    'EtapeAssemblageSerializer': ('kit',),
    'EtapeOrdreSerializer': ('ordre',),
    'FicheInterventionChampSerializer': ('template',),
    'FraisImportSerializer': ('dossier',),
    'InstallationSerializer': ('etape',),
    'InterventionSerializer': ('installation',),
    'KitComposantSerializer': ('kit',),
    'LandedCostLigneSerializer': ('dossier',),
    'LivraisonLigneSerializer': ('livraison',),
    'LivraisonSerializer': ('installation', 'transporteur'),
    'OrdreAssemblageLigneSerializer': ('ordre',),
    'OrdreDemontageLigneSerializer': ('ordre',),
    'OrdreDemontageSerializer': ('kit',),
    'PhotoChecklistMetaSerializer': ('checklist_item',),
    'PickListSerializer': ('installation',),
    'PickListLigneSerializer': ('bin',),
    'PositionTechnicienSerializer': ('intervention',),
    'PreuveLivraisonSerializer': ('livraison',),
    'ProjetChantierSerializer': ('installation', 'projet'),
    'ProjetDevisSerializer': ('projet',),
    'ProjetTicketSerializer': ('projet',),
    'ProjetSerializer': ('responsable',),
    'RegleApprobationAchatSerializer': ('chantier', 'programme'),
    'RegleRangementSerializer': ('bin_cible',),
    'RetourLivraisonLigneSerializer': ('retour',),
    'RetourLivraisonSerializer': ('livraison',),
    'RetourMaterielLigneSerializer': ('retour',),
    'RetourMaterielSerializer': ('installation',),
    'SerieAssemblageSerializer': ('ordre',),
    'SerieEntrepotSerializer': ('bin', 'installation'),
    'LotPrelevementSerializer': ('operateur',),
    'GpsConsentRecordSerializer': ('technicien',),
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.exceptions import NotFound
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory
    from rest_framework import serializers as drf
    from apps.installations import serializers as S
    User = get_user_model()

    def req(company_id):
        r = Request(APIRequestFactory().post('/'))
        r.user = User(username='sonde-acht-ver4-001', company_id=company_id)
        return r

    def refuse(cls, nom, valeur, company_id):
        # `to_internal_value` = résolution des FK (champ borné) + filet du mixin ; les validateurs
        # d'unicité / `validate()` métier (hors sujet) ne sont pas joués.
        ser = cls(data={nom: valeur}, partial=True, context={'request': req(company_id)})
        try:
            ser.to_internal_value({nom: valeur})
        except NotFound:
            return True
        except drf.ValidationError as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            return nom in detail
        return False

    fuites, temoins_ko, non_testes, testes = [], [], [], []
    for nom_classe, champs in COUPLES.items():
        cls = getattr(S, nom_classe, None)
        if cls is None:
            non_testes.append(f'{nom_classe}:classe absente')
            continue
        for nom in champs:
            champ = cls(context={'request': req(1)}).fields.get(nom)
            if champ is None or getattr(champ, 'read_only', False):
                non_testes.append(f'{nom_classe}.{nom}:absent/lecture')
                continue
            many = isinstance(champ, drf.ManyRelatedField)
            cible = champ.child_relation if many else champ
            qs = getattr(cible, 'queryset', None)
            if qs is None:
                non_testes.append(f'{nom_classe}.{nom}:sans queryset')
                continue
            model = qs.model
            try:
                ligne = model._default_manager.exclude(company__isnull=True).order_by('pk').first()
            except Exception as exc:  # modèle sans `company` : non borné par construction
                fuites.append(f'{nom_classe}.{nom}:sans company ({type(exc).__name__})')
                continue
            if ligne is None:
                non_testes.append(f'{nom_classe}.{nom}:aucune ligne {model.__name__}')
                continue
            autre = (ligne.company_id or 0) + 987654  # société absente = « une autre société »
            valeur = [ligne.pk] if many else ligne.pk
            testes.append(f'{nom_classe}.{nom}')
            if not refuse(cls, nom, valeur, autre):
                fuites.append(f'{nom_classe}.{nom}')
            if refuse(cls, nom, valeur, ligne.company_id):
                temoins_ko.append(f'{nom_classe}.{nom}')
    print(f'testes={len(testes)} fuites={fuites} temoins_ko={temoins_ko} non_testes={non_testes}')
    return {'repro': not fuites and not temoins_ko, 'testes': len(testes), 'fuites': fuites,
            'temoins_ko': temoins_ko, 'non_testes': non_testes}
