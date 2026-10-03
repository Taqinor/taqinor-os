"""Instantané ANONYMISÉ d'une société — cœur partagé de ``qa_export_anonymise`` /
``qa_import_anonymise`` (QA de nuit sur des données réalistes).

POURQUOI. Le qa-explorer ne testait que ``seed_demo`` (5 devis nus, 3 leads à un
nom) : les branches où vivent les vrais bugs (factures d'électricité,
distributeurs, études, options, pompage, C&I) n'étaient jamais exercées. On
exporte donc un graphe COHÉRENT d'une société réelle — montants, profils
énergétiques, études, lignes, statuts, et les RÉGLAGES DE PRIX de la société
(barème, TVA, tarifs : sans eux la cible tarife aux défauts et les chiffres
dérivent) CONSERVÉS — avec toutes les identités brouillées, puis on le recharge
dans une société locale ``taqinor-anon``.

LA RÈGLE QUI GOUVERNE TOUT : **fail-closed**. Chaque champ passe par
``classify()`` :

* ``KEEP``    — nombres, booléens, dates, énumérations (``choices``) et les
                quelques champs texte NOMMÉS dans ``MODEL_POLICY[...]['keep']``
                (référence de document, désignation de ligne, fiche produit…) ;
* ``SCRAMBLE``— TOUT autre champ texte (Char/Text/Email/URL/Slug), y compris un
                champ ajouté demain que personne n'a classé ;
* ``SCRUB``   — JSON (études, questionnaires) : nombres gardés, chaînes courtes
                « énumération » gardées, chaînes d'identité / e-mail / téléphone
                / texte long brouillées, coordonnées GPS arrondies ;
* ``GPS``     — latitude/longitude arrondies à 0,1° (~11 km, niveau ville) ;
* ``DROP``    — fichiers, photos, signatures, jetons, UUID, IP, chemins PDF…
                et tout type de champ INCONNU (liste blanche de types gardés).

Le brouillage est DÉTERMINISTE PAR VALEUR au sein d'un export (HMAC-SHA256 avec
un sel aléatoire de 32 octets tiré à chaque export et JAMAIS écrit) : le même
nom de client donne le même faux nom partout (le dédoublonnage et les
regroupements survivent), mais rien ne permet de remonter à la valeur source.
Il est aussi INJECTIF par genre (identifiants, e-mails, téléphones, noms,
sociétés…) : deux valeurs réelles différentes ne partagent JAMAIS un faux dans
un même export — sans quoi un index unique de la base rejetterait des lignes à
l'import (``uniq_lead_external_ref`` : 80 leads sur 1 022 perdus le 30/09/2026,
identifiants Odoo de 3 chiffres). Voir ``Scrambler``.

Les modèles de domaine sont atteints par ``django.apps.apps.get_model`` (aucun
import statique d'un modèle de domaine : ``authentication`` reste une app de
fondation, import-linter vert). Aucune valeur réelle n'est JAMAIS imprimée ni
journalisée — seulement des comptes, des noms de classes d'exception et des
noms de contraintes de base (du schéma, pas des données ; ``skip_reason``).
"""
from __future__ import annotations

import datetime as _dt
import decimal
import gzip
import hashlib
import hmac
import io
import json
import re
import secrets
import uuid
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings
from django.db import models

FORMAT = 'taqinor-anon/1'
SUFFIX = '.anon.json.gz'

KEEP = 'keep'
SCRAMBLE = 'scramble'
SCRUB = 'scrub'
GPS = 'gps'
DROP = 'drop'

# ── Graphe exporté (ordre = ordre de création à l'import) ─────────────────
# (label, genre) — 'catalogue' : toute la société ; 'document' : filtrable par
# --since/--limit ; 'child:<champ>' : suit son parent (lignes) ; 'settings' :
# RÉGLAGES de la société (une seule ligne, OneToOne) — la société cible en a
# déjà une à l'import : on y écrit les champs exportés par ``update()``.
EXPORT_ORDER = [
    # Réglages de prix : sans eux, la société cible tarife avec les barèmes PAR
    # DÉFAUT et les chiffres dérivent de la production (factures, couverture).
    ('parametres.CompanyProfile', 'settings'),
    ('parametres.TariffSettings', 'settings'),
    ('stock.Categorie', 'catalogue'),
    ('stock.Fournisseur', 'catalogue'),
    ('stock.Produit', 'catalogue'),
    ('crm.Client', 'document'),
    ('crm.Lead', 'document'),
    ('ventes.Devis', 'document'),
    ('ventes.LigneDevis', 'child:devis'),
    ('ventes.BonCommande', 'document'),
    ('facturation.Facture', 'document'),
    ('facturation.LigneFacture', 'child:facture'),
    ('facturation.Avoir', 'document'),
    ('facturation.LigneAvoir', 'child:avoir'),
    ('facturation.Paiement', 'document'),
    ('installations.Installation', 'document'),
    ('installations.Intervention', 'document'),
]

# Repères de PRIX du profil société que lisent le moteur de devis et les règles
# d'audit (``parametres.selectors.tariff_for`` : tarif ONEE de repli, productible,
# rendement ; ``ventes.utils.company_settings`` : TVA ; validité, échéancier,
# variantes, remises, régime loi 82-21, pompage). LISTE BLANCHE : le reste du
# profil — identité légale, coordonnées, RIB, clés de fichiers, responsables,
# sécurité (mots de passe, sessions), jetons — n'est JAMAIS exporté (jamais
# écrit non plus à l'import : la société cible garde son identité anonyme), et
# un champ ajouté demain au profil n'est pas exporté tant que personne ne l'a
# listé ici (fail-closed). Nombres, booléens et JSON de barème seulement.
PRICING_PROFILE_FIELDS = frozenset({
    'tva_standard', 'tva_panneaux', 'onee_tarif_kwh', 'productible_kwh_kwc',
    'rendement_global', 'prix_cible_kwc_defaut', 'remise_max_pct',
    'discount_approval_threshold', 'agricole_pump_hours',
    'agricole_prix_bonbonne', 'agricole_cout_reel_bonbonne',
    'quote_validity_days', 'payment_terms', 'variante_pct', 'devise_defaut',
    'seuil_regime_declaration_kwc', 'seuil_regime_anre_kwc',
})

# ── Politique EXPLICITE par modèle (le reste suit les règles par défaut) ──
# 'keep' : champs texte SANS donnée personnelle, nécessaires au comportement
#          (référence, désignation de ligne — la séparation d'options du PDF en
#          dépend —, fiche catalogue, ville niveau commune, tranche ONEE…).
#          Un champ JSON nommé ici est exporté TEL QUEL.
# 'drop' : champs à vider même si la règle par défaut les garderait.
# 'gps'  : coordonnées décimales à arrondir.
# 'only' : LISTE BLANCHE — seuls ces champs sont exportés (et écrits à l'import).
MODEL_POLICY = {
    'stock.Categorie': {'keep': {'nom', 'description'}},
    'stock.Fournisseur': {'keep': {'devise_defaut', 'incoterm'}},
    'stock.Produit': {'keep': {
        'nom', 'sku', 'marque', 'description', 'garantie', 'code_barres',
        'unite_stock', 'code_sh', 'pays_origine'}},
    'crm.Client': {'drop': {'code_parrainage'}},
    'crm.Lead': {
        'keep': {'ville', 'ville_reference', 'tranche_onee', 'roof_type',
                 'roi_band', 'external_system', 'utm_source', 'utm_medium'},
        # roof_point/roof_outline = coordonnées précises du toit ;
        # phone/email_normalise recalculés à l'import depuis les faux.
        'drop': {'lien_maps', 'roof_point', 'roof_outline', 'token', 'fbclid',
                 'appareil_id', 'phone_normalise', 'email_normalise'},
        'gps': {'gps_lat', 'gps_lng'},
    },
    'ventes.Devis': {
        'keep': {'reference', 'devise', 'variante_tier'},
        'drop': {'fichier_pdf', 'roof_image', 'layout_hash',
                 'electrical_design_hash', 'pdf_render_meta'},
    },
    'ventes.LigneDevis': {'keep': {'designation', 'groupe_label'}},
    'ventes.BonCommande': {'keep': {'reference'}, 'drop': {'pv_livraison'}},
    'facturation.Facture': {
        'keep': {'reference', 'devise'},
        'drop': {'fichier_pdf', 'fichier_ubl', 'pdf_render_meta'},
    },
    'facturation.LigneFacture': {'keep': {'designation'}},
    'facturation.Avoir': {'keep': {'reference'}, 'drop': {'fichier_pdf'}},
    'facturation.LigneAvoir': {'keep': {'designation'}},
    'facturation.Paiement': {'drop': {'provider_ref', 'idempotency_key'}},
    'installations.Installation': {
        'keep': {'reference', 'site_ville', 'dossier_operateur'},
        'drop': {'signature_client'},
    },
    'installations.Intervention': {
        'drop': {'signature_client', 'lien_client_token', 'lien_rapport_token'},
    },
    # Réglages de prix de la société (voir PRICING_PROFILE_FIELDS).
    'parametres.CompanyProfile': {
        'only': PRICING_PROFILE_FIELDS,
        'keep': {'devise_defaut'},
    },
    # Tarification & ROI : tout le singleton (barème, tolérance, charges fixes,
    # force motrice, surplus, hypothèses ROI/productible, grille horaire,
    # compensation, structure du tarif, taxes, indexation, fiscalité). Nombres,
    # booléens, dates et énumérations sont gardés par type ; les trois champs
    # « source » (texte libre : facture, contrat…) restent BROUILLÉS par défaut
    # — non vides quand ils l'étaient, c'est tout ce que les règles exigent.
    # Les JSON de barème sont gardés TELS QUELS : ce sont des nombres, des prix
    # en CHAÎNES (« 1.622856 ») et des libellés de tranche, et le brouilleur de
    # JSON prendrait un prix à 8 chiffres ou plus (« 118.000000 », tarif hors
    # Maroc) pour un téléphone — il le remplacerait par un faux numéro, et le
    # barème deviendrait illisible (repli silencieux sur les défauts).
    'parametres.TariffSettings': {
        'keep': {'pays_tarif', 'residential_tiers', 'tou_heures', 'tou_tarifs',
                 'taxes',
                 # AGR207 — barème des charges solaires de pompage et règle
                 # FDA datée : montants, libellés de charge et source du
                 # barème, gardés TELS QUELS comme ``taxes`` (une date
                 # « 2026-10-02 » ressemblerait à un téléphone au brouilleur).
                 'charges_pompage_solaire', 'regle_fda_pompage'},
    },
}

# Noms de champ TOUJOURS vidés (quel que soit le modèle) : fichiers, jetons,
# signatures, traces techniques.
DROP_NAME_RE = re.compile(
    r'(fichier|file|photo|image|signature|token|password|passwd|secret|'
    r'attachment|piece_jointe|_ubl|^ip_|_ip$|user_agent|fbclid|appareil_id|'
    r'naissance|lien_)', re.I)
# Noms qui trahissent une identité : un champ NON texte (nombre) portant l'un
# de ces noms est vidé plutôt que gardé.
IDENTITY_NAME_RE = re.compile(
    r'(^|_)(nom|prenom|name|email|mail|tel|telephone|phone|mobile|gsm|'
    r'whatsapp|fax|adresse|address|rue|cin|ice|iban|rib|rc|if|siret|patente|'
    r'cnss|passeport|societe|contact|signataire)($|_)', re.I)
GPS_NAME_RE = re.compile(r'(^|_)(gps|lat|lng|lon|latitude|longitude)($|_)', re.I)

# Types dont la valeur est GARDÉE telle quelle (liste blanche — un type absent
# d'ici et non texte/JSON est VIDÉ : fail-closed).
_KEEP_TYPES = (
    models.IntegerField, models.DecimalField, models.FloatField,
    models.BooleanField, models.DateField, models.TimeField,
    models.DurationField,
)
# NB : DateTimeField hérite de DateField ; PositiveIntegerField, BigIntegerField,
# SmallIntegerField… héritent d'IntegerField.

# ── JSON ──────────────────────────────────────────────────────────────────
JSON_IDENTITY_KEY_RE = re.compile(
    r'(^|_)(nom|prenom|name|firstname|lastname|fullname|email|e_mail|mail|'
    r'tel|telephone|phone|mobile|gsm|whatsapp|fax|adresse|address|rue|cin|'
    r'ice|iban|rib|signature|societe|raison_sociale|contact|note|notes|'
    r'commentaire|comment|comments|message|remarque|remarques|'
    r'signataire)($|_)', re.I)
# Clés d'identité reconnues seulement EN ENTIER (« type_client » est une
# énumération d'étude, « client » un bloc d'identité).
JSON_IDENTITY_EXACT = {'client', 'user', 'username', 'owner', 'auteur',
                       'author', 'beneficiaire', 'proprietaire'}
PHONE_RE = re.compile(r'(\d[\s.\-]?){8,}')
_SHORT_JSON_STR = 60


def model_for(label):
    """Le modèle d'un label ``app.Model`` ou ``None`` (app non installée)."""
    try:
        return django_apps.get_model(label)
    except (LookupError, ValueError):
        return None


def exported_models():
    """[(label, genre, Model)] des modèles disponibles, dans l'ordre d'import."""
    out = []
    for label, kind in EXPORT_ORDER:
        model = model_for(label)
        if model is not None:
            out.append((label, kind, model))
    return out


def _related_label(field):
    rel = getattr(field, 'related_model', None)
    return rel._meta.label if rel is not None else None


def _is_company_fk(field):
    return field.is_relation and _related_label(field) == 'authentication.Company'


def _is_user_fk(field):
    return field.is_relation and _related_label(field) == settings.AUTH_USER_MODEL


def concrete_fields(model):
    """Champs concrets à sérialiser (hors pk, hors M2M, hors inverses)."""
    return [f for f in model._meta.concrete_fields
            if not f.primary_key and not getattr(f, 'generated', False)]


def exported_fields(label, model):
    """Champs que l'export LIT pour ce modèle : tous, sauf quand
    ``MODEL_POLICY[label]['only']`` pose une LISTE BLANCHE (réglages de la
    société : seulement les prix, jamais l'identité ni la sécurité). Un champ
    ajouté demain n'est donc PAS exporté tant que personne ne l'a listé."""
    only = MODEL_POLICY.get(label, {}).get('only')
    fields = concrete_fields(model)
    if only is None:
        return fields
    return [f for f in fields if f.name in only]


def classify(label, field):
    """Politique d'UN champ scalaire : KEEP / SCRAMBLE / SCRUB / GPS / DROP.

    Fail-closed : un champ texte inconnu est brouillé, un type inconnu vidé.
    Les FK sont traitées à part (``serialise_row``)."""
    policy = MODEL_POLICY.get(label, {})
    name = field.name
    if name in policy.get('drop', ()):
        return DROP
    if name in policy.get('gps', ()):
        return GPS
    if name in policy.get('keep', ()):
        return KEEP
    if DROP_NAME_RE.search(name):
        return DROP
    if isinstance(field, (models.FileField, models.UUIDField,
                          models.BinaryField, models.GenericIPAddressField)):
        return DROP
    if isinstance(field, models.JSONField):
        return SCRUB
    if isinstance(field, (models.CharField, models.TextField)):
        # EmailField, URLField, SlugField héritent de CharField.
        if field.choices and not isinstance(field, (models.EmailField,
                                                    models.URLField)):
            return KEEP  # énumération : valeurs du code, jamais une identité
        return SCRAMBLE
    if isinstance(field, _KEEP_TYPES):
        if isinstance(field, (models.DecimalField, models.FloatField)) and \
                GPS_NAME_RE.search(name):
            return GPS
        if IDENTITY_NAME_RE.search(name) and not isinstance(
                field, (models.BooleanField, models.DateField)):
            return DROP
        return KEEP
    return DROP


def scramble_kind(field):
    """Forme du faux (jamais la décision de brouiller — celle-ci est prise)."""
    name = field.name.lower()
    if isinstance(field, models.EmailField) or 'email' in name or 'mail' in name:
        return 'email'
    if isinstance(field, models.URLField) or name.endswith('url'):
        return 'url'
    if re.search(r'(tel|phone|mobile|gsm|whatsapp|fax)', name):
        return 'phone'
    if re.search(r'(^|_)prenom', name):
        return 'prenom'
    if re.search(r'(societe|raison_sociale|entreprise)', name):
        return 'societe'
    if re.search(r'(^|_)(nom|name|signataire|contact_personne|contact)', name):
        return 'nom'
    if re.search(r'(adresse|address|rue)', name):
        return 'adresse'
    if re.search(r'(^|_)(cin|ice|rc|if|if_fiscal|identifiant|rib|iban|siret|'
                 r'patente|cnss|cheque|numero|dgi|external_id|meta_)', name):
        return 'ident'
    if isinstance(field, models.TextField):
        return 'texte'
    return 'generic'


# ── Brouilleur déterministe ───────────────────────────────────────────────
_NOMS = [
    'Amrani', 'Belkadi', 'Cherkaoui', 'Daoudi', 'Essafi', 'Filali', 'Guerrouj',
    'Hajji', 'Iraqi', 'Jamai', 'Kettani', 'Lahlou', 'Mansouri', 'Naciri',
    'Ouazzani', 'Qadiri', 'Rami', 'Sqalli', 'Touimi', 'Wahbi', 'Yacoubi',
    'Zaki', 'Benali', 'Doukkali', 'Fassi', 'Hakimi', 'Kabbaj', 'Lamrani',
    'Mernissi', 'Sebti',
]
_PRENOMS = [
    'Adam', 'Amine', 'Aya', 'Bilal', 'Dounia', 'Driss', 'Fadwa', 'Ghita',
    'Hiba', 'Ilyas', 'Imane', 'Jalil', 'Kenza', 'Lina', 'Mounir', 'Nora',
    'Othmane', 'Rim', 'Samir', 'Souad', 'Tarik', 'Wiam', 'Yassine', 'Zineb',
]
_RUES = [
    'des Orangers', 'des Palmiers', 'du Soleil', 'des Oliviers', 'de la Paix',
    'des Roses', 'du Jasmin', 'des Cèdres', 'de l’Atlas', 'des Figuiers',
]
_SOCIETES = [
    'Atlas', 'Sahara', 'Rif', 'Oasis', 'Argan', 'Safran', 'Cèdre', 'Zellige',
    'Menara', 'Kasbah',
]
_ALNUM = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
_LETTERS = 24  # lettres d'un faux « ident » : _ALNUM[:24] (sans I ni O)

# Genres dont le faux vient d'un RÉSERVOIR FINI par construction (24 prénoms,
# ~2 000 adresses) : deux valeurs différentes y partagent forcément un faux —
# c'est voulu (deux personnes s'appellent « Adam », deux clients habitent « 12
# rue des Roses ») et aucune contrainte d'unicité ne porte sur ces champs.
_POOL_KINDS = frozenset({'prenom', 'adresse'})

# Taille de l'espace des faux d'un genre à largeur 0, et facteur d'agrandissement
# par caractère ajouté. Sert à mesurer le remplissage (élargir passé 50 %).
_SPACE = {
    'email': (16 ** 12, 16),
    'phone': (10 ** 8, 10),
    'nom': (len(_NOMS) * 32 ** 3, 32),
    'societe': (len(_SOCIETES) * 32 ** 3, 32),
    'url': (16 ** 10, 16),
    'texte': (16 ** 8, 16),
    'generic': (16 ** 10, 16),
}


def _mask(text):
    """Forme d'une chaîne : chiffre → « D », lettre → « L », le reste tel quel."""
    return ''.join('D' if c.isdigit() else ('L' if c.isalpha() else c)
                   for c in text)


def _mask_capacity(mask):
    """Nombre de faux « ident » différents que peut produire cette forme."""
    capacity = 1
    for c in mask:
        if c == 'D':
            capacity *= 10
        elif c == 'L':
            capacity *= _LETTERS
    return capacity


class Scrambler:
    """HMAC-SHA256(sel, genre, valeur normalisée) → faux stable par valeur ET
    INJECTIF par genre.

    Le sel (32 octets aléatoires) vit en mémoire le temps d'un export et n'est
    jamais écrit : deux exports donnent des faux différents, et aucun ne se
    ré-identifie par dictionnaire.

    DÉTERMINISME — un mémo ``(genre, valeur, longueur max)`` → faux : la même
    valeur réelle redonne toujours le même faux dans un export, quel que soit
    l'ordre dans lequel on la rencontre.

    INJECTIVITÉ (défaut du 30/09/2026 sur les données réelles) — le faux d'un
    identifiant Odoo de 3 chiffres tenait dans 10³ possibilités : 426 valeurs
    réelles donnaient ~84 collisions, donc 80 leads sur 1 022 rejetés par
    l'index unique ``uniq_lead_external_ref`` à l'import. Chaque genre tient
    donc un registre ``faux → valeur``. Sur collision, le candidat suivant est
    tiré de façon DÉTERMINISTE (HMAC de la valeur + un compteur). Quand
    l'espace d'une forme est rempli à plus de 50 %, on ÉLARGIT d'un caractère
    (le format est gardé tant que c'est possible). Deux valeurs réelles
    différentes ne partagent jamais un faux, et un faux n'est jamais égal à sa
    valeur source. Exceptions assumées : ``prenom`` et ``adresse`` (réservoirs
    finis, voir ``_POOL_KINDS``), et un champ dont ``max_length`` est si court
    que l'espace tronqué est épuisé — le repli (faux du premier tirage) est
    alors COMPTÉ dans ``exhausted`` (jamais une valeur), pour que l'appelant
    le dise.

    Équivalence de deux valeurs = leur forme normalisée : casse et espaces
    ignorés (``nom``, ``email``…), 9 derniers chiffres pour un téléphone
    (+212 6… ≡ 06… ≡ 6…). Un IDENTIFIANT (``ident``) reste sensible à la casse
    et aux espaces, comme l'index unique qui le porte."""

    _PROBES = 64        # tirages par largeur avant d'élargir (garde-fou)
    _MAX_WIDEN = 16     # caractères ajoutables au plus

    def __init__(self, salt=None):
        self._salt = salt or secrets.token_bytes(32)
        self._memo = {}      # (genre, identité, longueur max) -> faux
        self._owner = {}     # genre -> {faux: identité}
        self._used = {}      # (genre, espace) -> nombre de faux attribués
        self._choice = {}    # (genre, identité) -> (largeur, compteur) retenus
        self.widened = {}    # genre -> faux élargis (format non gardé)
        self.exhausted = {}  # genre -> faux NON uniques faute de place

    @staticmethod
    def _identity(kind, value):
        raw = str(value)
        if kind == 'ident':
            return raw
        norm = raw.strip().lower()
        if kind == 'phone':
            digits = re.sub(r'\D', '', norm)
            return digits[-9:] or norm  # sans chiffre : la valeur elle-même
        return norm

    def _digest(self, kind, identity, counter=0):
        tail = '' if counter == 0 else f'\x00{counter}'
        return hmac.new(self._salt, f'{kind}\x00{identity}{tail}'.encode('utf-8'),
                        hashlib.sha256).digest()

    def _code(self, dig, n, offset=0):
        return ''.join(_ALNUM[b % len(_ALNUM)] for b in dig[offset:offset + n])

    @staticmethod
    def _ident(dig, src, width):
        """Format préservé (lettre→lettre, chiffre→chiffre, ponctuation gardée),
        longueur gardée ; ``width`` caractères de PLUS, de la classe du dernier
        caractère alphanumérique, pour agrandir un espace trop rempli."""
        tail = '0'
        for ch in reversed(src):
            if ch.isdigit():
                break
            if ch.isalpha():
                tail = 'A'
                break
        chars = []
        for i in range(len(src) + width):
            b = dig[i % len(dig)] + i
            ch = src[i] if i < len(src) else tail
            if ch.isdigit():
                chars.append(str(b % 10))
            elif ch.isalpha():
                chars.append(_ALNUM[b % _LETTERS])
            else:
                chars.append(ch)
        return ''.join(chars)

    def _build(self, kind, dig, value, width):
        """Le faux d'un tirage, avant troncature à ``max_length``."""
        n = int.from_bytes(dig, 'big')
        if kind == 'email':
            return f'anon-{dig.hex()[:12 + width]}@anon.invalid'
        if kind == 'phone':
            k = 8 + width
            return '+2126' + str(n % 10 ** k).zfill(k)
        if kind == 'nom':
            return f'{_NOMS[n % len(_NOMS)]}-{self._code(dig, 3 + width, 8)}'
        if kind == 'prenom':
            return _PRENOMS[n % len(_PRENOMS)]
        if kind == 'societe':
            return (f'Société {_SOCIETES[n % len(_SOCIETES)]} '
                    f'{self._code(dig, 3 + width, 8)}')
        if kind == 'adresse':
            return f'{(n % 199) + 1} rue {_RUES[(n // 199) % len(_RUES)]}'
        if kind == 'url':
            return f'https://anon.invalid/{dig.hex()[:10 + width]}'
        if kind == 'ident':
            return self._ident(dig, str(value), width)
        if kind == 'texte':
            return f'Texte anonymisé {dig.hex()[:8 + width]}'
        return f'anon-{dig.hex()[:10 + width]}'

    @staticmethod
    def _space(kind, cand, width):
        """(clé, taille) de l'espace de faux où tombe ``cand`` : sert à mesurer
        son remplissage. « ident » : un espace par FORME (chiffres/lettres)."""
        if kind == 'ident':
            mask = _mask(cand)
            return (kind, mask), _mask_capacity(mask)
        base, growth = _SPACE.get(kind, _SPACE['generic'])
        return (kind, width), base * growth ** width

    def _pick(self, kind, identity, value, max_length):
        owners = self._owner.setdefault(kind, {})
        src = str(value)

        def take(cand, space):
            """Le faux ``cand`` (tronqué) s'il est libre ou déjà à cette valeur."""
            final = cand[:max_length] if max_length else cand
            holder = owners.get(final)
            if final == src or (holder is not None and holder != identity):
                return None
            if holder is None:
                owners[final] = identity
                self._used[space] = self._used.get(space, 0) + 1
            return final

        def draw(width, counter):
            return self._build(kind, self._digest(kind, identity, counter),
                               value, width)

        prior = self._choice.get((kind, identity))
        if prior is not None:
            # Déjà tiré pour une AUTRE longueur max : on rejoue LE MÊME tirage
            # (même faux quand il tient dans les deux champs), sans regarder le
            # remplissage d'aujourd'hui — sinon le faux dépendrait du champ.
            width, counter = prior
            space, _ = self._space(kind, draw(width, 0), width)
            final = take(draw(width, counter), space)
            if final is not None:
                return final
        for width in range(self._MAX_WIDEN + 1):
            first = draw(width, 0)
            space, capacity = self._space(kind, first, width)
            if self._used.get(space, 0) * 2 >= capacity and \
                    width < self._MAX_WIDEN:
                continue  # espace rempli à plus de moitié : on élargit
            for counter in range(self._PROBES):
                final = take(first if counter == 0 else draw(width, counter),
                             space)
                if final is None:
                    continue
                self._choice.setdefault((kind, identity), (width, counter))
                if width:
                    self.widened[kind] = self.widened.get(kind, 0) + 1
                return final
        # Espace épuisé (champ trop court pour l'unicité) : repli déterministe,
        # signalé — jamais un plantage de l'export ni une valeur imprimée.
        self.exhausted[kind] = self.exhausted.get(kind, 0) + 1
        out = draw(0, 0)
        return out[:max_length] if max_length else out

    def fake(self, kind, value, max_length=None):
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == '':
            return value
        identity = self._identity(kind, value)
        if kind in _POOL_KINDS:
            out = self._build(kind, self._digest(kind, identity), value, 0)
            return out[:max_length] if max_length else out
        key = (kind, identity, max_length)
        out = self._memo.get(key)
        if out is None:
            out = self._memo[key] = self._pick(kind, identity, value,
                                               max_length)
        return out

    # JSON : nombres gardés, chaînes « énumération » courtes gardées ; tout le
    # reste (clé d'identité, e-mail, téléphone, texte long) brouillé.
    def scrub_json(self, value, key=None, forced=False):
        if isinstance(value, dict):
            return {k: self.scrub_json(
                v, key=str(k),
                forced=forced or _json_identity_key(str(k)))
                for k, v in value.items()}
        if isinstance(value, list):
            return [self.scrub_json(v, key=key, forced=forced) for v in value]
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, (int, float)):
            if key and GPS_NAME_RE.search(key):
                return coarsen_gps(value)
            if forced and key and IDENTITY_NAME_RE.search(key):
                return None
            return value
        if isinstance(value, str):
            if forced:
                kind = 'email' if '@' in value else (
                    'phone' if PHONE_RE.search(value) else 'texte')
                return self.fake(kind, value)
            if '@' in value:
                return self.fake('email', value)
            if PHONE_RE.search(value):
                return self.fake('phone', value)
            if len(value) > _SHORT_JSON_STR or '\n' in value:
                return self.fake('texte', value)
            if key and GPS_NAME_RE.search(key):
                return None
            return value
        return None  # type inattendu : vidé (fail-closed)


def _json_identity_key(key):
    return key.lower() in JSON_IDENTITY_EXACT or bool(
        JSON_IDENTITY_KEY_RE.search(key))


def coarsen_gps(value):
    """Arrondi à 0,1° (~11 km) : la commune reste, la maison disparaît."""
    if value is None:
        return None
    try:
        return float(round(decimal.Decimal(str(value)), 1))
    except (decimal.InvalidOperation, ValueError, TypeError):
        return None


def _jsonable(value):
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, _dt.timedelta):
        return value.total_seconds()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def serialise_value(label, field, raw, scr):
    """Valeur exportée d'un champ NON relationnel selon ``classify``."""
    policy = classify(label, field)
    if policy == DROP or raw is None:
        return None
    if policy == KEEP:
        return _jsonable(raw)
    if policy == GPS:
        coarse = coarsen_gps(raw)
        return None if coarse is None else f'{coarse:.1f}'
    if policy == SCRUB:
        return scr.scrub_json(raw)
    # SCRAMBLE
    return scr.fake(scramble_kind(field), raw,
                    max_length=getattr(field, 'max_length', None))


# ── Chemins de sortie (jamais dans le dépôt sauf var/anon/) ───────────────
def _inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def check_out_path(out):
    """Refuse un chemin qui écrirait l'instantané dans le code source.

    Autorisé : ``-`` (stdout), tout chemin contenant ``var/anon/`` (ignoré par
    git), ou un chemin HORS du projet Django et hors de tout dépôt git. Le nom
    doit finir par ``.anon.json.gz`` (motif ignoré par .gitignore)."""
    if out == '-':
        return None
    path = Path(out).expanduser().resolve()
    if not path.name.endswith(SUFFIX):
        return f"le fichier doit se terminer par « {SUFFIX} »."
    parts = [p.lower() for p in path.parts]
    in_var_anon = any(parts[i] == 'var' and parts[i + 1] == 'anon'
                      for i in range(len(parts) - 1))
    if in_var_anon:
        return None
    base = Path(settings.BASE_DIR).resolve()
    if _inside(path, base):
        return ('refus : chemin dans le code source Django (utilisez var/anon/ '
                'ou un dossier hors du dépôt, ou --out -).')
    for parent in path.parents:
        if (parent / '.git').exists():
            return ('refus : chemin dans un dépôt git hors de var/anon/ '
                    '(le fichier est CONFIDENTIEL).')
    return None


def write_snapshot(payload, out, stdout_buffer):
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'),
                     sort_keys=False).encode('utf-8')
    data = gzip.compress(raw, compresslevel=6, mtime=0)
    if out == '-':
        stdout_buffer.write(data)
        stdout_buffer.flush()
    else:
        path = Path(out).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return len(data)


def read_snapshot(src, stdin_buffer):
    data = stdin_buffer.read() if src == '-' else Path(src).expanduser().read_bytes()
    if data[:2] == b'\x1f\x8b':
        data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
    payload = json.loads(data.decode('utf-8'))
    if not isinstance(payload, dict) or payload.get('format') != FORMAT:
        raise ValueError('format inconnu')
    return payload


# ── EXPORT : sélection d'un graphe cohérent pour UNE société ──────────────
_DATE_FIELDS = ('date_creation', 'created_at', 'date', 'date_emission',
                'date_paiement', 'date_prevue')


def _field_or_none(model, name):
    from django.core.exceptions import FieldDoesNotExist
    try:
        return model._meta.get_field(name)
    except FieldDoesNotExist:
        return None


def _has_company(model):
    f = _field_or_none(model, 'company')
    return f is not None and _is_company_fk(f)


def _date_field(model):
    for name in _DATE_FIELDS:
        f = _field_or_none(model, name)
        if isinstance(f, models.DateField):
            return name
    return None


def select_graph(company, since=None, limit=None):
    """{label: set(pk)} — racines de la société puis FERMETURE par FK.

    Catalogue : toute la société. Documents : ``--since`` (champ date de
    création) puis les ``--limit`` plus récents. Ensuite, jusqu'au point fixe :
    toute cible de FK vers un modèle exporté (de LA MÊME société) est ajoutée,
    et les lignes suivent leurs parents — le graphe importé n'a jamais de FK
    pendante."""
    specs = exported_models()
    labels = {label for label, _, _ in specs}
    by_label = {label: model for label, _, model in specs}
    sel = {label: set() for label in labels}
    for label, kind, model in specs:
        if kind.startswith('child:') or not _has_company(model):
            continue
        qs = model._base_manager.filter(company=company)
        if kind == 'document':
            date_field = _date_field(model)
            if since and date_field:
                qs = qs.filter(**{f'{date_field}__gte': since})
            qs = qs.order_by('-pk')
            if limit:
                qs = qs[:limit]
        sel[label].update(qs.values_list('pk', flat=True))

    for _ in range(25):
        changed = False
        for label, kind, model in specs:
            if kind.startswith('child:'):
                parent = model._meta.get_field(kind.split(':', 1)[1])
                parent_pks = sel.get(_related_label(parent)) or set()
                if parent_pks:
                    pks = set(model._base_manager.filter(
                        **{f'{parent.attname}__in': parent_pks}
                    ).values_list('pk', flat=True))
                    if pks - sel[label]:
                        sel[label] |= pks
                        changed = True
            fks = [f for f in concrete_fields(model)
                   if f.is_relation and _related_label(f) in labels]
            if not fks or not sel[label]:
                continue
            rows = model._base_manager.filter(pk__in=sel[label]).values_list(
                *[f.attname for f in fks])
            for row in rows:
                for f, value in zip(fks, row):
                    target = _related_label(f)
                    if value is None or value in sel[target]:
                        continue
                    tmodel = by_label[target]
                    if _has_company(tmodel) and not tmodel._base_manager.filter(
                            pk=value, company=company).exists():
                        continue  # jamais une ligne d'une autre société
                    sel[target].add(value)
                    changed = True
        if not changed:
            break
    return specs, sel


def build_export(company, since=None, limit=None, scrambler=None):
    """Charge utile JSON (dict) de l'instantané anonymisé de ``company``.

    LECTURE SEULE : l'appelant enveloppe l'appel dans une transaction annulée."""
    from django.utils import timezone

    scr = scrambler or Scrambler()
    specs, sel = select_graph(company, since=since, limit=limit)
    labels = {label for label, _, _ in specs}
    out_models, counts = [], {}
    for label, _kind, model in specs:
        fields = exported_fields(label, model)
        rows = []
        qs = model._base_manager.filter(pk__in=sel[label]).order_by('pk')
        for obj in qs.iterator():
            values = {}
            for f in fields:
                if f.is_relation:
                    if _is_company_fk(f):
                        continue  # réassignée à la société cible à l'import
                    raw = getattr(obj, f.attname)
                    target = _related_label(f)
                    if raw is None:
                        values[f.name] = None
                    elif _is_user_fk(f):
                        values[f.name] = {'$user': 1}  # → anon_admin
                    elif target in labels and raw in sel[target]:
                        values[f.name] = {'$ref': [target, _jsonable(raw)]}
                    else:
                        values[f.name] = None  # cible non exportée : vidée
                    continue
                values[f.name] = serialise_value(
                    label, f, getattr(obj, f.attname), scr)
            rows.append({'pk': _jsonable(obj.pk), 'f': values})
        out_models.append({'label': label, 'rows': rows})
        counts[label] = len(rows)
    return {
        'format': FORMAT,
        'created_at': timezone.now().isoformat(),
        'confidential': ('CONFIDENTIEL — données de production anonymisées. '
                         'Jamais commité, jamais envoyé ailleurs, supprimer '
                         'les anciens instantanés.'),
        'filters': {'since': since.isoformat() if since else None,
                    'limit': limit},
        'counts': counts,
        'models': out_models,
    }


# ── IMPORT : recharge dans la société cible, sans aucun signal ────────────
def _python_value(field, value):
    if value is None:
        if field.null:
            return None
        if field.has_default():
            return field.get_default()
        if isinstance(field, (models.CharField, models.TextField)):
            return ''
        return None
    if isinstance(field, models.JSONField):
        return value
    if isinstance(field, models.DurationField) and \
            isinstance(value, (int, float)):
        return _dt.timedelta(seconds=value)
    return field.to_python(value)


def _fix_unique(model, fields, kwargs):
    """Valeurs uniques GLOBALES : jamais de collision avec une autre société."""
    for f in fields:
        if not f.unique or f.primary_key or f.is_relation:
            continue
        value = kwargs.get(f.attname)
        if value in (None, ''):
            if f.null:
                kwargs[f.attname] = None
            elif isinstance(f, models.CharField):
                kwargs[f.attname] = secrets.token_hex(
                    max(4, min(16, (f.max_length or 32) // 2)))
        elif isinstance(value, str) and model._base_manager.filter(
                **{f.attname: value}).exists():
            kwargs[f.attname] = (
                f'A{secrets.token_hex(3)}-{value}')[:f.max_length or 255]


def skip_reason(exc):
    """Clé de regroupement d'une ligne IGNORÉE à l'import — jamais son contenu.

    PostgreSQL (psycopg2 comme psycopg) nomme la CONTRAINTE violée dans
    ``exc.__cause__.diag.constraint_name`` : un nom de contrainte est du schéma,
    pas une donnée personnelle — alors que le message (« Key (external_id)=(123)
    already exists ») cite, lui, la valeur : il n'est donc JAMAIS lu. Une
    violation NOT NULL n'a pas de contrainte nommée mais nomme sa COLONNE. Sans
    pilote qui les donne (autre base, ``ValidationError``…) : la classe de
    l'exception, comme avant."""
    name = type(exc).__name__
    diag = getattr(getattr(exc, '__cause__', None), 'diag', None)
    constraint = getattr(diag, 'constraint_name', None)
    if constraint:
        return f'{name}[{constraint}]'
    column = getattr(diag, 'column_name', None)
    if column:
        return f'{name}[colonne {column}]'
    return name


def _update_settings_row(model, company_fields, company, kwargs):
    """Réglages de la société (genre ``settings``) : la société cible en a déjà
    UNE ligne (``CompanyProfile`` posé par ``qa_import_anonymise``, contrainte
    OneToOne sur ``company``) — on y écrit les SEULS champs exportés, par
    ``update()`` (aucun signal), sans toucher au reste : la société cible garde
    son identité anonyme. Retourne le pk mis à jour, ou ``None`` s'il n'y a pas
    encore de ligne (l'appelant la crée)."""
    if not company_fields:
        return None
    link = company_fields[0].attname
    pk = model._base_manager.filter(**{link: company.pk}).values_list(
        'pk', flat=True).first()
    if pk is None:
        return None
    changes = {k: v for k, v in kwargs.items() if k != link}
    if changes:
        model._base_manager.filter(pk=pk).update(**changes)
    return pk


def import_payload(payload, company, admin):
    """Recrée le graphe dans ``company``. Retourne (créés, ignorés).

    AUCUN signal : chaque ligne passe par ``bulk_create`` (ni ``save()`` ni
    pre/post_save — donc ni chatter, ni ``notify()``, ni e-mail, ni webhook, ni
    événement de domaine comme ``devis_accepted``, qui ne sont émis que par des
    appels explicites des vues/services), les dates ``auto_now*`` sont
    rétablies par ``QuerySet.update()`` (sans signal non plus). Les RÉGLAGES de
    la société (genre ``settings`` : profil de prix, tarification) mettent à
    jour la ligne que la société cible possède déjà, ``update()`` aussi. Une
    ligne invalide est ignorée DANS un savepoint et comptée par NOM DE
    CONTRAINTE de base (``skip_reason`` ; repli : classe d'exception) — jamais
    son contenu imprimé."""
    from django.core.exceptions import ValidationError
    from django.db import DataError, IntegrityError, transaction

    created, skipped = {}, {}
    idmap = {}
    kinds = dict(EXPORT_ORDER)
    file_pks = {b['label']: {r['pk'] for r in b['rows']}
                for b in payload.get('models', [])}
    deferred = []

    def _skip(label, key):
        bucket = skipped.setdefault(label, {})
        bucket[key] = bucket.get(key, 0) + 1

    for block in payload.get('models', []):
        label = block['label']
        model = model_for(label)
        if model is None:
            skipped[label] = {'app absente': len(block['rows'])}
            continue
        idmap[label] = {}
        fields = {f.name: f for f in concrete_fields(model)}
        company_fields = [f for f in fields.values() if _is_company_fk(f)]
        auto_fields = [f for f in fields.values()
                       if getattr(f, 'auto_now', False)
                       or getattr(f, 'auto_now_add', False)]
        settings_kind = kinds.get(label) == 'settings'
        # Liste blanche aussi À L'IMPORT : un fichier trafiqué ou plus ancien ne
        # peut jamais écrire autre chose que les champs prévus.
        only = MODEL_POLICY.get(label, {}).get('only')
        for row in block['rows']:
            kwargs, defer, ok = {}, [], True
            for name, value in row['f'].items():
                f = fields.get(name)
                if f is None or _is_company_fk(f) or (
                        only is not None and name not in only):
                    continue  # champ disparu du schéma local : ignoré
                if f.is_relation:
                    new = None
                    if isinstance(value, dict) and '$user' in value:
                        new = admin.pk
                    elif isinstance(value, dict) and '$ref' in value:
                        target, src_pk = value['$ref']
                        new = idmap.get(target, {}).get(src_pk)
                        if new is None and f.null and \
                                src_pk in file_pks.get(target, ()):
                            defer.append((f.attname, target, src_pk))
                    if new is None and not f.null:
                        ok = False
                    kwargs[f.attname] = new
                else:
                    try:
                        kwargs[f.attname] = _python_value(f, value)
                    except (ValidationError, ValueError, TypeError):
                        ok = False
            if not ok:
                _skip(label, 'parent absent / valeur invalide')
                continue
            for f in company_fields:
                kwargs[f.attname] = company.pk
            _fix_unique(model, fields.values(), kwargs)
            try:
                with transaction.atomic():
                    new_pk = (_update_settings_row(
                        model, company_fields, company, kwargs)
                        if settings_kind else None)
                    if new_pk is None:
                        obj = model(**kwargs)
                        model._base_manager.bulk_create([obj])
                        autos = {f.attname: kwargs[f.attname]
                                 for f in auto_fields
                                 if kwargs.get(f.attname) is not None}
                        if autos:
                            model._base_manager.filter(
                                pk=obj.pk).update(**autos)
                        new_pk = obj.pk
            except (IntegrityError, DataError, ValidationError, ValueError,
                    TypeError) as exc:
                _skip(label, skip_reason(exc))
                continue
            idmap[label][row['pk']] = new_pk
            created[label] = created.get(label, 0) + 1
            for attname, target, src_pk in defer:
                deferred.append((model, new_pk, attname, target, src_pk))

    for model, pk, attname, target, src_pk in deferred:
        new = idmap.get(target, {}).get(src_pk)
        if new is not None:
            model._base_manager.filter(pk=pk).update(**{attname: new})

    _post_import(idmap)
    return created, skipped


def _post_import(idmap):
    """Colonnes dérivées que ``save()`` aurait posées (bulk_create les saute)."""
    lead_model = model_for('crm.Lead')
    lead_pks = list(idmap.get('crm.Lead', {}).values())
    if lead_model is not None and lead_pks:
        from apps.crm import services as crm_services
        for pk, tel, email in lead_model._base_manager.filter(
                pk__in=lead_pks).values_list('pk', 'telephone', 'email'):
            lead_model._base_manager.filter(pk=pk).update(
                phone_normalise=crm_services.normalize_phone(tel) or '',
                email_normalise=crm_services.normalize_email(email) or '')
    client_model = model_for('crm.Client')
    client_pks = list(idmap.get('crm.Client', {}).values())
    if client_model is not None and client_pks and \
            _field_or_none(client_model, 'code_parrainage') is not None:
        for pk in client_model._base_manager.filter(
                pk__in=client_pks, code_parrainage__isnull=True
        ).values_list('pk', flat=True):
            client_model._base_manager.filter(pk=pk).update(
                code_parrainage=f'TQ-{pk}')
