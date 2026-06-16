"""Spécifications d'import réutilisables (leads, clients, produits).

Une SEULE structure décrit, par cible :
  - le modèle Django visé ;
  - les champs importables (clé interne anglais → libellé FR) ;
  - les alias d'en-tête acceptés (FR/EN, accents, casse) pour l'inférence de
    mapping ;
  - les champs requis (une ligne sans eux est signalée, jamais créée) ;
  - la clé de dé-doublonnage (création seulement : un doublon est IGNORÉ, jamais
    écrasé silencieusement) ;
  - des convertisseurs de valeur optionnels (décimal, booléen…).

Le service générique (`service.py`) consomme cette structure ; aucun code
spécifique par cible n'est dupliqué ailleurs.
"""
import unicodedata
from decimal import Decimal, InvalidOperation


def _norm(text):
    """Normalise un en-tête pour l'appariement : minuscules, sans accents, sans
    espaces/ponctuation superflus."""
    s = unicodedata.normalize('NFKD', str(text or ''))
    s = s.encode('ascii', 'ignore').decode('ascii').lower().strip()
    out = []
    for ch in s:
        out.append(ch if ch.isalnum() else ' ')
    return ' '.join(''.join(out).split())


def coerce_text(value):
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def coerce_decimal(value):
    if value in (None, ''):
        return None
    s = str(value).strip().replace(' ', '').replace(',', '.')
    if s == '':
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        raise ValueError('nombre invalide')


def coerce_int(value):
    if value in (None, ''):
        return None
    s = str(value).strip()
    if s == '':
        return None
    try:
        return int(float(s.replace(',', '.')))
    except (ValueError, TypeError):
        raise ValueError('entier invalide')


_TRUE = {'1', 'true', 'vrai', 'oui', 'yes', 'o', 'y', 'x'}
_FALSE = {'0', 'false', 'faux', 'non', 'no', 'n', ''}


def coerce_bool(value):
    if value is None:
        return False
    s = str(value).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    raise ValueError('valeur oui/non invalide')


class FieldSpec:
    """Un champ importable."""

    def __init__(self, key, label, aliases=None, required=False,
                 coerce=coerce_text):
        self.key = key
        self.label = label
        # Le libellé + la clé sont toujours des alias implicites.
        self.aliases = set(aliases or []) | {label, key}
        self.required = required
        self.coerce = coerce

    @property
    def norm_aliases(self):
        return {_norm(a) for a in self.aliases}


class ImportSpec:
    """Spécification complète d'une cible d'import."""

    def __init__(self, target, label, get_model, fields, dedup_keys):
        self.target = target
        self.label = label
        self._get_model = get_model
        self.fields = fields
        # Liste de clés servant à détecter un doublon existant (création seule).
        self.dedup_keys = dedup_keys

    @property
    def model(self):
        return self._get_model()

    def required_keys(self):
        return [f.key for f in self.fields if f.required]

    def match_header(self, header):
        """Retourne la clé de champ correspondant à un en-tête, ou None."""
        nh = _norm(header)
        if not nh:
            return None
        for f in self.fields:
            if nh in f.norm_aliases:
                return f.key
        return None

    def field(self, key):
        for f in self.fields:
            if f.key == key:
                return f
        return None


# ───────────────────────── modèles (chargés à la demande) ───────────────────

def _lead_model():
    from apps.crm.models import Lead
    return Lead


def _client_model():
    from apps.crm.models import Client
    return Client


def _produit_model():
    from apps.stock.models import Produit
    return Produit


# ─────────────────────────────── registre ───────────────────────────────────

LEAD_SPEC = ImportSpec(
    target='lead',
    label='Leads',
    get_model=_lead_model,
    fields=[
        FieldSpec('nom', 'Nom', required=True),
        FieldSpec('prenom', 'Prénom', aliases=['Prenom', 'First name']),
        FieldSpec('societe', 'Société', aliases=['Societe', 'Company']),
        FieldSpec('email', 'Email', aliases=['E-mail', 'Courriel']),
        FieldSpec('telephone', 'Téléphone',
                  aliases=['Telephone', 'Tel', 'Phone', 'GSM']),
        FieldSpec('whatsapp', 'WhatsApp'),
        FieldSpec('adresse', 'Adresse', aliases=['Address']),
        FieldSpec('ville', 'Ville', aliases=['City']),
        FieldSpec('note', 'Note', aliases=['Notes', 'Commentaire']),
    ],
    # Dédup : email (si présent) sinon téléphone — création seule.
    dedup_keys=['email', 'telephone'],
)

CLIENT_SPEC = ImportSpec(
    target='client',
    label='Clients',
    get_model=_client_model,
    fields=[
        FieldSpec('nom', 'Nom', required=True),
        FieldSpec('prenom', 'Prénom', aliases=['Prenom', 'First name']),
        FieldSpec('email', 'Email', aliases=['E-mail', 'Courriel']),
        FieldSpec('telephone', 'Téléphone',
                  aliases=['Telephone', 'Tel', 'Phone', 'GSM']),
        FieldSpec('adresse', 'Adresse', aliases=['Address']),
        FieldSpec('ice', 'ICE'),
        FieldSpec('cin', 'CIN'),
        FieldSpec('if_fiscal', 'IF', aliases=['Identifiant fiscal', 'IF fiscal']),
        FieldSpec('rc', 'RC'),
    ],
    dedup_keys=['email'],
)

PRODUIT_SPEC = ImportSpec(
    target='produit',
    label='Produits',
    get_model=_produit_model,
    fields=[
        FieldSpec('nom', 'Nom', aliases=['Designation', 'Désignation', 'Name'],
                  required=True),
        FieldSpec('sku', 'SKU', aliases=['Reference', 'Référence', 'Code']),
        FieldSpec('description', 'Description'),
        FieldSpec('marque', 'Marque', aliases=['Brand']),
        FieldSpec('prix_vente', 'Prix vente HT',
                  aliases=['Prix vente', 'Prix', 'Prix HT', 'PU HT',
                           'Sale price'],
                  required=True, coerce=coerce_decimal),
        FieldSpec('tva', 'TVA %', aliases=['TVA', 'VAT'], coerce=coerce_decimal),
        FieldSpec('quantite_stock', 'Quantité',
                  aliases=['Quantite', 'Stock', 'Qte', 'Qty'],
                  coerce=coerce_int),
        FieldSpec('seuil_alerte', 'Seuil alerte',
                  aliases=['Seuil', 'Min stock'], coerce=coerce_int),
        FieldSpec('garantie_mois', 'Garantie (mois)',
                  aliases=['Garantie', 'Warranty'], coerce=coerce_int),
        FieldSpec('garantie_production_mois', 'Garantie production (mois)',
                  coerce=coerce_int),
    ],
    # Dédup produits sur le SKU (création seule ; jamais d'écrasement de prix).
    dedup_keys=['sku'],
)

SPECS = {
    'lead': LEAD_SPEC,
    'client': CLIENT_SPEC,
    'produit': PRODUIT_SPEC,
}


def get_spec(target):
    return SPECS.get(target)
