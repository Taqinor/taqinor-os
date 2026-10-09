"""ENF7 — briques de schéma OpenAPI exact de la GED (corps, réponses, paramètres).

Chaque corps / réponse décrit ce que la vue lit / renvoie RÉELLEMENT (voir
``views.py``) ; les statuts d'erreur (400/401/403/404/409/429/500) sont ajoutés
par le crochet plateforme ``core.openapi_erreurs``. Les noms de composants sont
préfixés ``Ged`` (``inline_serializer`` partage un espace de noms unique).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers as s

from apps.records.openapi import CibleModelField

from .models import LIFECYCLE_CHOICES
from .serializers import (
    CreerMultiSignatairesSerializer, DemandeDocumentSerializer,
    DocumentSerializer, ExigenceDossierSerializer,
)


def S(nom, champs, **kw):
    return inline_serializer('Ged' + nom, champs, **kw)


def P(nom, type_=OpenApiTypes.STR, **kw):
    return OpenApiParameter(nom, type_, **kw)


ID = OpenApiTypes.INT
DATE = OpenApiTypes.DATE
FLAG = ['1', 'true', '0', 'false']
FLAG_VRAI = ['1', 'true']
ID_OU_NULL = {'type': 'string', 'pattern': '^(null|[0-9]+)$'}


# ── Paramètres de requête (par vue) ─────────────────────────────────────────
Q_DOCUMENT = P('document', ID, description='Identifiant du document.')
Q_FOLDER = P('folder', ID, description='Identifiant du dossier.')
Q_ACTIF = P('actif', enum=FLAG, description='Filtre sur le drapeau actif.')
Q_STATUT = P('statut', description='Filtre sur le statut.')
Q_Q = P('q', description='Texte recherché.')
Q_FORMAT_CSV = P('format', enum=['csv'],
                 description="``csv`` : export CSV d'audit.")

Q_FOLDERS = [
    P('cabinet', ID, description='Cabinet (armoire) du dossier.'),
    P('parent', ID_OU_NULL, description="Dossier parent, ou ``null`` (racines)."),
]
Q_DOCUMENTS = [
    Q_FOLDER,
    P('coffre', ID_OU_NULL, description="Coffre-fort, ou ``null`` (hors coffre)."),
    P('tag', ID, description='Tag de la taxonomie.'),
    P('statut', enum=[c for c, _ in LIFECYCLE_CHOICES],
      description='Statut du cycle de vie documentaire.'),
    P('proprietaire', ID, description='Propriétaire (utilisateur).'),
    P('contact', ID, description='Contact (client) assigné.'),
]
Q_TAGS = [P('parent', ID_OU_NULL, description="Tag parent, ou ``null`` (racines).")]
Q_TAG_DOCS = [P('descendants', enum=FLAG_VRAI,
                description='``1`` : inclut les sous-tags.')]
Q_APPROBATIONS = [
    Q_DOCUMENT, Q_STATUT,
    P('en_attente', enum=FLAG_VRAI, description='``1`` : en attente seulement.'),
]
Q_JOURNAL = [
    Q_DOCUMENT,
    P('utilisateur', ID, description='Utilisateur.'),
    P('type_acces', description="Type d'accès (aperçu, téléchargement…)."),
]
Q_ACLS = [
    Q_FOLDER, Q_DOCUMENT,
    P('niveau', description='Niveau (lecture / ecriture / gestion).'),
]

# ── Corps ───────────────────────────────────────────────────────────────────
TAG_CORPS = S('TagCorps', {'tag': s.IntegerField()})
ASSIGNER_CORPS = S('AssignerCorps', {
    'proprietaire': s.IntegerField(required=False, allow_null=True),
    'contact': s.IntegerField(required=False, allow_null=True),
})
PARENT_CORPS = S('DeplacerDossierCorps', {
    'parent': s.IntegerField(required=False, allow_null=True)})
DOSSIER_CIBLE_CORPS = S('DeplacerDocumentCorps', {'folder': s.IntegerField()})
FAVORI_REPONSE = S('FavoriReponse', {'favori': s.BooleanField()})
TELEVERSER_CORPS = S('TeleverserCorps', {
    'folder': s.IntegerField(),
    'file': s.FileField(),
    'nom': s.CharField(required=False, allow_blank=True),
    'description': s.CharField(required=False, allow_blank=True),
})
SCAN_LOT_CORPS = S('ScanLotCorps', {
    'folder': s.IntegerField(),
    'files': s.ListField(child=s.FileField(), allow_empty=False),
})
PHOTOS_CORPS = S('AssemblerPhotosCorps', {
    'folder': s.IntegerField(),
    'photos': s.ListField(child=s.FileField(), allow_empty=False),
    'nom': s.CharField(required=False, allow_blank=True),
    'description': s.CharField(required=False, allow_blank=True),
})
LOT_SEPARE_CORPS = S('LotScansSepareCorps', {
    'folder': s.IntegerField(),
    'files': s.ListField(child=s.FileField(), allow_empty=False),
    'nom_base': s.CharField(required=False, allow_blank=True),
})
IMPORT_MASSE_CORPS = S('ImportMasseCorps', {
    'folder': s.IntegerField(),
    'csv': s.FileField(),
    'zip': s.FileField(required=False),
})
APRES_VENTE_CORPS = S('ClasserApresVenteCorps', {
    'nom': s.RegexField(r'\S'),
    'source_type': s.RegexField(r'\S'),
    'source_id': s.IntegerField(),
    'file_key': s.CharField(required=False, allow_blank=True),
    'cabinet': s.CharField(required=False, allow_blank=True),
    'dossier': s.CharField(required=False, allow_blank=True),
    'description': s.CharField(required=False, allow_blank=True),
})
OCR_CORPS = S('OcrPieceCorps', {
    'type_piece': s.CharField(required=False, allow_blank=True)})
VERSION_CORPS = S('VersionRestaurerCorps', {'version': s.IntegerField()})
FICHIER_CORPS = S('FichierCorps', {'file': s.FileField()})
MOTIF_CORPS = S('MotifCorps', {
    'motif': s.CharField(required=False, allow_blank=True)})
COMMENTAIRE_CORPS = S('CommentaireCorps', {
    'commentaire': s.CharField(required=False, allow_blank=True)})
CYCLE_VIE_CORPS = S('CycleVieCorps', {
    'statut': s.ChoiceField(choices=[c for c, _ in LIFECYCLE_CHOICES])})
REVUE_CORPS = S('DemanderRevueCorps', {
    'approbateur': s.IntegerField(required=False, allow_null=True),
    'commentaire': s.CharField(required=False, allow_blank=True),
})
ARCHIVER_CORPS = S('ArchiverLegalementCorps', {
    'motif': s.CharField(required=False, allow_blank=True),
    'retain_until': s.DateField(required=False, allow_null=True),
})
ZONE = S('ZoneCaviardage', {
    'page': s.IntegerField(min_value=0),
    'x0': s.FloatField(), 'y0': s.FloatField(),
    'x1': s.FloatField(), 'y1': s.FloatField(),
}, many=True)
CAVIARDER_CORPS = S('CaviarderCorps', {
    'zones': ZONE,
    'version': s.IntegerField(required=False, allow_null=True),
})
SCINDER_CORPS = S('ScinderCorps', {
    'points_de_coupe': s.ListField(child=s.IntegerField()),
    'version': s.IntegerField(required=False, allow_null=True),
})
FUSIONNER_CORPS = S('FusionnerCorps', {
    'documents': s.ListField(child=s.IntegerField(), min_length=2),
    'cible': s.IntegerField(required=False, allow_null=True),
    'nom': s.CharField(required=False, allow_blank=True),
})
OPERATIONS_LOT_CORPS = S('OperationsLotCorps', {
    'documents': s.ListField(child=s.IntegerField(), allow_empty=False),
    'operation': s.ChoiceField(choices=[
        'tagger', 'detaguer', 'deplacer', 'corbeille', 'telecharger_zip',
        'partager', 'demander_signature', 'demander_revue']),
    'params': s.DictField(required=False),
})
PLANIFIER_CORPS = S('PlanifierCorps', {
    'libelle': s.RegexField(r'\S'),
    'echeance': s.DateField(),
    'assigne_a': s.IntegerField(required=False, allow_null=True),
})
LIEN_CORPS = S('DocumentLienCorps', {
    'document': s.IntegerField(),
    'model': CibleModelField(),
    'id': s.IntegerField(),
})
ARCHIVAGE_CORPS = S('ArchivageLegalCorps', {
    'document': s.IntegerField(),
    'motif': s.CharField(required=False, allow_blank=True),
    'retain_until': s.DateField(required=False, allow_null=True),
})
LEGAL_HOLD_CORPS = S('LegalHoldCorps', {
    'document': s.IntegerField(),
    'motif': s.CharField(required=False, allow_blank=True),
})
VERSION_CREATION_CORPS = S('VersionCreationCorps', {
    'document': s.IntegerField(),
    'file': s.FileField(),
})
SERVICE_INDISPO = S('ServiceIndisponible', {'detail': s.CharField()})
CONTEXTE_CORPS = S('ContexteFusionCorps', {
    'contexte': s.DictField(required=False)})
SIGNATURE_CORPS = S('DemandeSignatureCorps', {
    'document': s.IntegerField(),
    'signataire_nom': s.RegexField(r'\S'),
    'signataire_email': s.RegexField(r'\S'),
})
MARQUER_SIGNE_CORPS = S('MarquerSigneCorps', {
    'provider_ref': s.CharField(required=False, allow_blank=True)})
PROLONGER_CORPS = S('ProlongerCorps', {'expires_at': s.DateTimeField()})
VALIDER_OCR_CORPS = S('ValiderOcrCorps', {
    'champs_corriges': s.DictField(required=False)})
DISPOSITION_CORPS = S('DemandeDispositionCorps', {
    'libelle': s.RegexField(r'\S'),
    'action': s.ChoiceField(choices=['detruire', 'archiver'], required=False),
    'documents': s.ListField(child=s.IntegerField(), allow_empty=False),
})
ENVOI_MASSE_CORPS = S('EnvoiMasseCorps', {
    'modele': s.IntegerField(),
    'libelle': s.CharField(required=False, allow_blank=True),
    'csv': s.FileField(required=False),
    'clients': s.ListField(child=s.IntegerField(), required=False),
})

# ── Réponses ────────────────────────────────────────────────────────────────
LIGNES = S('PermissionsEffectives', {
    'lignes': s.ListField(child=s.DictField())})
SCAN_REPONSE = S('ScanLotReponse', {
    'documents': DocumentSerializer(many=True),
    'erreurs': s.ListField(child=s.DictField()),
})
LOT_SEPARE_REPONSE = S('LotScansSepareReponse', {
    'documents': DocumentSerializer(many=True),
    'barcode_lib_disponible': s.BooleanField(),
})
IMPORT_REPONSE = S('ImportMasseReponse', {
    'crees': s.IntegerField(),
    'documents': DocumentSerializer(many=True),
    'erreurs': s.ListField(child=s.JSONField()),
})
SEMANTIQUE_REPONSE = S('RechercheSemantiqueReponse', {
    'mode': s.CharField(),
    'results': DocumentSerializer(many=True),
})
DOCQA_REPONSE = S('DocQaReponse', {
    'enabled': s.BooleanField(),
    'results': S('DocQaFragment', {
        'source': s.CharField(),
        'document': s.IntegerField(),
        'document_nom': s.CharField(),
        'chunk_index': s.IntegerField(),
        'texte': s.CharField(),
        'distance': s.FloatField(allow_null=True),
    }, many=True),
})
OCR_REPONSE = S('OcrPieceReponse', {
    'document': DocumentSerializer(),
    'metadonnees': s.DictField(),
    'en_validation': s.BooleanField(),
    'ocr_enabled': s.BooleanField(),
})
CLASSER_REPONSE = S('ClasserReponse', {
    'document': DocumentSerializer(),
    'categorie': s.CharField(allow_null=True),
    'ia_enabled': s.BooleanField(),
})
OFFICE_REPONSE = S('OfficeOuvrirReponse', {
    'editor_url': s.CharField(), 'document_id': s.IntegerField()})
LEVES_REPONSE = S('LegalHoldLeveReponse', {'leves': s.IntegerField()})
COMPARER_REPONSE = S('ComparerVersionsReponse', {
    'metadonnees': s.JSONField(),
    'texte_disponible': s.BooleanField(),
    'diff_texte': s.ListField(child=s.JSONField()),
    'message': s.CharField(required=False, allow_blank=True, allow_null=True),
})
OPERATIONS_LOT_REPONSE = S('OperationsLotReponse', {
    'resultats': s.ListField(child=s.JSONField()),
    'erreurs': s.ListField(child=s.JSONField()),
})
TIMELINE_LIGNE = S('TimelineLigne', many=True, champs={
    'type': s.CharField(),
    'evenement': s.CharField(),
    'message': s.CharField(allow_blank=True, allow_null=True),
    'utilisateur': s.CharField(allow_null=True),
    'created_at': s.DateTimeField(),
})
PAGES_REPONSE = S('VersionPagesReponse', {'pages': s.IntegerField()})
ECHU_LIGNE = S('DocumentEchu', many=True, champs={
    'document': s.IntegerField(),
    'document_nom': s.CharField(),
    'politique': s.IntegerField(),
    'politique_nom': s.CharField(),
    'action_echeance': s.CharField(),
    'duree_conservation_jours': s.IntegerField(),
    'jours_depasses': s.IntegerField(),
})
INTEGRITE_REPONSE = S('VerifierIntegriteReponse', {
    'total': s.IntegerField(), 'ok': s.IntegerField(),
    'altere': s.IntegerField(), 'indisponible': s.IntegerField(),
})
QUOTA_ETAT = S('QuotaEtat', {
    'usage_octets': s.IntegerField(),
    'quota_octets': s.IntegerField(),
    'restant_octets': s.IntegerField(),
    'depasse': s.BooleanField(),
    'illimite': s.BooleanField(),
})
GENERER_REPONSE = S('GenererModeleReponse', {
    'document': s.IntegerField(),
    'document_nom': s.CharField(),
    'created': s.BooleanField(),
})
TABLEAU_BORD = S('TableauBordSignatures', {
    'colonnes': s.DictField(child=s.ListField(child=s.JSONField())),
    'total': s.IntegerField(),
})
CHECKLIST_LIGNE = S('ChecklistLigne', many=True, champs={
    'exigence': ExigenceDossierSerializer(),
    'statut': s.CharField(),
    'demande': DemandeDocumentSerializer(allow_null=True),
})
TAMPON = {'type': 'array', 'items': {'type': 'string'}}
RECENTS = S('MesRecents', {
    'consultes': DocumentSerializer(many=True),
    'deposes': DocumentSerializer(many=True),
})
FAVORIS = S('MesFavoris', {
    'dossiers': s.ListField(child=s.DictField()),
    'documents': s.ListField(child=s.DictField()),
})
ANALYTIQUE = S('AnalytiqueGed', {
    'approbations': s.DictField(),
    'signatures': s.DictField(),
})
PUBLIC_DEPOT_INFO = S('DepotPublicInfo', {
    'message': s.CharField(allow_blank=True),
    'quota_fichiers_restant': s.IntegerField(allow_null=True),
})
PUBLIC_DEPOT_CORPS = S('DepotPublicCorps', {
    'file': s.FileField(),
    'nom': s.CharField(required=False, allow_blank=True),
    'email': s.CharField(required=False, allow_blank=True),
})
PUBLIC_DEPOT_OK = S('DepotPublicReponse', {
    'detail': s.CharField(), 'document': s.IntegerField()})
PUBLIC_SIGNATURE = S('SignaturePublique', {
    'document_nom': s.CharField(),
    'document_id': s.IntegerField(),
    'signataire_nom': s.CharField(),
    'statut': s.CharField(),
    'expires_at': s.DateTimeField(allow_null=True),
    'champs': s.ListField(child=s.DictField()),
    'apercu_url': s.CharField(),
    'apercu_mime': s.CharField(allow_blank=True),
})
PUBLIC_SIGNATAIRE = S('SignatairePublic', {
    'document_nom': s.CharField(),
    'document_id': s.IntegerField(),
    'apercu_url': s.CharField(),
    'apercu_mime': s.CharField(allow_blank=True),
    'nom': s.CharField(),
    'role': s.CharField(),
    'ordre': s.IntegerField(),
    'statut': s.CharField(),
    'demande_statut': s.CharField(),
    'auth_extra': s.CharField(allow_null=True),
    'otp_requis': s.BooleanField(),
    'otp_degrade': s.BooleanField(),
    'champs': s.ListField(child=s.DictField()),
})
PUBLIC_SIGNATURE_CORPS = S('SignaturePubliqueCorps', {
    'action': s.ChoiceField(choices=['signer', 'refuser']),
    'consentement': s.BooleanField(required=False),
    'signature_texte': s.CharField(required=False, allow_blank=True),
    'signature_tracee': s.CharField(required=False, allow_blank=True),
    'valeurs_champs': s.DictField(required=False, allow_null=True),
    'motif': s.CharField(required=False, allow_blank=True),
})
PUBLIC_SIGNATAIRE_CORPS = S('SignatairePublicCorps', {
    'action': s.ChoiceField(choices=[
        'signer', 'refuser', 'envoyer-code', 'valider-code']),
    'consentement': s.BooleanField(required=False),
    'signature_texte': s.CharField(required=False, allow_blank=True),
    'signature_tracee': s.CharField(required=False, allow_blank=True),
    'valeurs_champs': s.DictField(required=False, allow_null=True),
    'motif': s.CharField(required=False, allow_blank=True),
    'code': s.CharField(required=False, allow_blank=True),
})
PUBLIC_PARTAGE_CORPS = S('PartagePublicCorps', {
    'password': s.CharField(required=False, allow_blank=True)})
PUBLIC_ERREUR = S('PublicDetail', {
    'detail': s.CharField(), 'code': s.CharField(required=False)})
OTP_REPONSE = S('OtpReponse', {'detail': s.CharField(required=False)})

CREER_MULTI_CORPS = CreerMultiSignatairesSerializer
