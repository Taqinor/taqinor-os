"""ACHT53 (C-ACHT-052/043) — purge des lignes `apps/installations/` des
sections §AANA47 et §ASTK9 de `scripts/fk_scoping_allow.txt` : chaque FK
inscriptible de la liste ci-dessous est BORNÉE à la société de la requête
(`same_company_fields` → champ promu en `CompanyScopedPrimaryKeyRelatedField`)
ou n'est pas inscriptible (lecture seule). Retirer la borne d'un couple fait
échouer son cas, en nommant le couple.

Test SANS base : les sérialiseurs sont instanciés avec un utilisateur en
mémoire et inspectés (aucun appel réseau, aucun mock de la garde).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht53_fk_purge_allowlist"
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from core.serializers import CompanyScopedPrimaryKeyRelatedField

from apps.installations import serializers, serializers_commissioning

User = get_user_model()

#: classe de `serializers.py` → champs FK/M2M inscriptibles bornés.
COUPLES = {
    'EquipeSerializer': ('chef', 'membres'),
    'EtapeApprobationAchatSerializer': ('approbateur', 'demande', 'regle'),
    'GeofenceAlertSerializer': ('acquittee_par',),
    'OrdreAssemblageSerializer': ('responsable', 'kit'),
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
    'PositionTechnicienSerializer': ('intervention',),
    'PreuveLivraisonSerializer': ('livraison',),
    'ProjetChantierSerializer': ('installation', 'projet'),
    'ProjetDevisSerializer': ('projet',),
    'ProjetTicketSerializer': ('projet',),
    'RegleApprobationAchatSerializer': ('chantier', 'programme'),
    'RegleRangementSerializer': ('bin_cible',),
    'RetourLivraisonLigneSerializer': ('retour',),
    'RetourLivraisonSerializer': ('livraison',),
    'RetourMaterielLigneSerializer': ('retour',),
    'RetourMaterielSerializer': ('installation',),
    'SerieAssemblageSerializer': ('ordre',),
    'SerieEntrepotSerializer': ('bin', 'installation'),
}
COUPLES_COMMISSIONING = {
    'CommissioningRecordSerializer': ('installation',),
    'HandoverPackSerializer': ('installation',),
}


def _champ(classe, nom):
    user = User(username='acht53', company_id=1)
    request = Request(APIRequestFactory().get('/'))
    request.user = user
    return classe(context={'request': request}).fields.get(nom)


def _borne(champ):
    """Promu société, ou non inscriptible (lecture seule)."""
    if champ is None or getattr(champ, 'read_only', False):
        return True
    cible = getattr(champ, 'child_relation', champ)
    return type(cible) is CompanyScopedPrimaryKeyRelatedField


class FkPurgeAllowlistTests(SimpleTestCase):
    def test_fk_inscriptibles_bornees_a_la_societe(self):
        non_bornes = []
        for module, couples in ((serializers, COUPLES),
                                (serializers_commissioning,
                                 COUPLES_COMMISSIONING)):
            for nom_classe, champs in couples.items():
                classe = getattr(module, nom_classe)
                for nom in champs:
                    if not _borne(_champ(classe, nom)):
                        non_bornes.append(f'{nom_classe}.{nom}')
        self.assertEqual(
            non_bornes, [],
            f"FK inscriptibles non bornées à la société : {non_bornes}")

    def test_aucune_ligne_installations_dans_les_sections(self):
        """§AANA47 et §ASTK9 ne contiennent plus aucune ligne installations."""
        from pathlib import Path
        racine = Path(__file__).resolve().parents[4]
        allow = (racine / 'scripts' / 'fk_scoping_allow.txt')
        if not allow.is_file():
            self.skipTest('fk_scoping_allow.txt hors du contexte du test')
        lignes = allow.read_text(encoding='utf-8').splitlines()
        debut = next(i for i, ligne in enumerate(lignes)
                     if ligne.startswith('# AANA47'))
        fin = next(i for i, ligne in enumerate(lignes)
                   if ligne.startswith('# ASEC46'))
        restantes = [ligne for ligne in lignes[debut:fin]
                     if 'apps/installations/' in ligne]
        self.assertEqual(restantes, [])
