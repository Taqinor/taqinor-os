"""Le ``contenu`` d'un acte : le dictionnaire que l'écran modifie et que le
PDF imprime, à l'identique (formes : contract_samples/acte_contractuel.json).

Une seule source par valeur (docs/contrats/conception.md § 4). Fusion, dans
cet ordre : valeurs VIVANTES (lues) → textes par défaut (``textes.py``, ou
``textes_ar.py`` pour la traduction arabe) → modèle de la société
(``ModeleActe``) → personnalisations de l'acte.

Règles fermes :
- aucun montant n'est modifiable dans un acte (l'échéancier se corrige sur la
  vente) ; tout montant est une chaîne décimale « 98500.00 » ;
- aucun prix d'achat, aucune marge : seuls les champs publics sont lus ;
- une valeur absente s'imprime « à préciser » et lève un avertissement, jamais
  un chiffre inventé ;
- lectures seulement : rien n'est écrit ici.
"""
import copy
import logging
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.utils import timezone

from . import types as T
from .rendu import composants as C

logger = logging.getLogger(__name__)

ZERO = Decimal('0')
CENTIME = Decimal('0.01')
SCHEMA = 1

A_PRECISER = {'fr': 'à préciser', 'ar': 'يُحدَّد لاحقًا'}


# ── Outils ──────────────────────────────────────────────────────────────────

def _d(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return None


def _q(valeur):
    return Decimal(valeur).quantize(CENTIME, rounding=ROUND_HALF_UP)


def _s(valeur):
    """Montant → chaîne décimale « 98500.00 » (None reste None)."""
    d = _d(valeur)
    return None if d is None else f'{_q(d):f}'


def _pct(valeur):
    """Pourcentage → chaîne courte : 30.00 → « 30 », 33.33 → « 33.33 »."""
    d = _d(valeur)
    if d is None:
        return None
    d = _q(d)
    if d == d.to_integral_value():
        return str(int(d))
    return f'{d.normalize():f}'


def _iso(valeur):
    if valeur is None or valeur == '':
        return None
    if hasattr(valeur, 'isoformat'):
        return valeur.isoformat()[:10]
    return str(valeur)[:10]


def _date(valeur):
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10]) if valeur else None
    except ValueError:
        return None


def ajouter_mois(depart, mois):
    """``depart`` + ``mois`` mois (jour borné à la fin du mois d'arrivée)."""
    d = _date(depart)
    if d is None or mois is None:
        return None
    total = d.month - 1 + int(mois)
    annee, mois_ = d.year + total // 12, total % 12 + 1
    suivant = date(annee + (mois_ == 12), mois_ % 12 + 1, 1)
    dernier = (suivant - timedelta(days=1)).day
    return date(annee, mois_, min(d.day, dernier))


def _slug(texte):
    brut = unicodedata.normalize('NFKD', str(texte or '')).encode(
        'ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '_', brut.lower()).strip('_') or 'garantie'


def _textes(langue):
    """Les textes par défaut de la langue. La traduction arabe vit dans
    ``textes_ar`` (mêmes fonctions, mêmes repères) ; tant qu'elle manque, les
    textes français servent, pour que rien ne casse."""
    from . import textes
    if langue == 'ar':
        try:
            from . import textes_ar
            return textes_ar
        except ImportError:
            logger.warning('contrats : textes_ar absent, textes français servis')
    return textes


def _montant(valeur, langue):
    return C.montant(valeur, langue=langue)


def _lettres(valeur, langue):
    """Montant en lettres : français seulement (aucun convertisseur arabe
    vérifié : vide en arabe, décision du 24/11/2026)."""
    if langue != 'fr' or not _d(valeur):
        return ''
    from core.nombre_lettres import montant_en_lettres
    return montant_en_lettres(_d(valeur))


# ── Lectures vivantes, faites une fois par chantier ─────────────────────────

class Lecture:
    """Les lectures vivantes d'un chantier (société, vente, paiements,
    nomenclature, garanties, modèles) mémoïsées le temps d'un calcul : un
    dossier de cinq actes ne relit pas cinq fois la vente."""

    def __init__(self, chantier):
        self.chantier = chantier
        self._memo = {}

    def _une_fois(self, cle, fabrique):
        if cle not in self._memo:
            self._memo[cle] = fabrique()
        return self._memo[cle]

    @property
    def devis(self):
        return getattr(self.chantier, 'devis', None)

    def profil(self):
        def lire():
            from apps.parametres.models import CompanyProfile
            return CompanyProfile.get(company=self.chantier.company)
        return self._une_fois('profil', lire)

    def logo_uri(self):
        def lire():
            try:
                from apps.ventes.utils.pdf import _company_context
                return _company_context(
                    company=self.chantier.company).get('logo_uri') or ''
            except Exception:  # noqa: BLE001 — logo illisible : le nom suffit
                logger.warning('contrats : logo illisible', exc_info=True)
                return ''
        return self._une_fois('logo', lire)

    def modele(self, type_acte):
        def lire():
            from ..models import ModeleActe
            return ModeleActe.objects.filter(
                company=self.chantier.company, type=type_acte).first()
        return self._une_fois(('modele', type_acte), lire)

    def composants(self):
        def lire():
            from apps.documents.builders import _composants
            return _composants(self.chantier)
        return self._une_fois('composants', lire)

    def garanties_vente(self, langue):
        def lire():
            from apps.ventes.utils.garanties import garanties_de_la_vente
            return garanties_de_la_vente(self.devis, langue)
        return self._une_fois(('garanties', langue), lire)

    def vente(self):
        """Prix, tranches, payé et paiements de la vente du chantier, ou None
        sans devis. Lecteurs : ``plan_facturation`` (prix, tranches figées),
        ``solde_devis`` (payé canonique), ``paiements_des_factures``."""
        return self._une_fois('vente', self._lire_vente)

    def _lire_vente(self):
        devis = self.devis
        if devis is None:
            return None
        from apps.ventes.selectors_facturation import paiements_des_factures
        from apps.ventes.utils.echeancier import solde_devis
        from apps.ventes.vente_facturation import plan_facturation
        plan = plan_facturation(devis)
        solde = solde_devis(devis)
        factures = [f for f, _part in plan.get('factures_parts') or []]
        libelles = {t['facture_id']: t['libelle'] for t in plan['tranches']
                    if t.get('facture_id')}
        paiements = [{
            'date': _iso(p['date_paiement']),
            'libelle': libelles.get(p['facture_id']) or 'Paiement',
            'mode': p.get('mode_libelle') or '',
            'montant': _s(p['montant']),
        } for p in paiements_des_factures([f.pk for f in factures])]
        tranches = [{
            'cle': t['cle'], 'key': t['key'], 'libelle': t['libelle'],
            'montant': _q(t['montant_ttc']),
            'cible': _q(t['cible_cumul_ttc']),
            'pourcentage': t['pourcentage'],
        } for t in plan['tranches']]
        return {
            'prix_ttc': _q(plan['prix_convenu_ttc']),
            'prix_ht': _q(plan['prix_convenu_ht']),
            'tva': _q(plan['prix_convenu_tva']),
            'paye': _q(solde['paye']),
            'reste': _q(solde['restant']),
            'tranches': tranches,
            'paiements': paiements,
        }


# ── Référence, titre ────────────────────────────────────────────────────────

def reference_acte(type_acte, reference_chantier, chantier_id=None):
    """Préfixe de l'acte + référence du chantier sans son préfixe
    (CHT-2026-11-0007 → CTR-2026-11-0007). Aucun compteur."""
    prefixe = T.PREFIXES[type_acte]
    ref = (reference_chantier or '').strip()
    if not ref:
        return f'{prefixe}-{chantier_id}' if chantier_id else prefixe
    _avant, tiret, suite = ref.partition('-')
    return f'{prefixe}-{suite if tiret and suite else ref}'


def index_livraison(tranches):
    """Index de la tranche « livraison du matériel » ; à défaut l'avant-
    dernière tranche (ou la première s'il n'y en a qu'une)."""
    for i, t in enumerate(tranches):
        if t['key'] in T.CLES_TRANCHE_LIVRAISON:
            return i
    return max(0, len(tranches) - 2)


def titre_acte(type_acte, variante, vente):
    if type_acte != T.LIVRAISON:
        return T.TITRES[type_acte]
    if variante == T.RESTE_A_REGLER:
        return T.TITRE_RESTE_A_REGLER
    if not vente or not vente['tranches'] or not vente['prix_ttc']:
        return T.TITRE_TRANCHE_REGLEE_SANS_DEVIS
    i = index_livraison(vente['tranches'])
    part = vente['tranches'][i]['cible'] / vente['prix_ttc'] * 100
    return T.TITRE_TRANCHE_REGLEE.format(pourcentage=C.pourcent(part))


# ── État des tranches et situation de paiement ──────────────────────────────

def _horizon(type_acte, tranches):
    if not tranches:
        return None
    if type_acte == T.CONTRAT:
        return 0
    if type_acte == T.LIVRAISON:
        return index_livraison(tranches)
    return len(tranches) - 1


def situation(type_acte, variante, vente):
    """``(etats, paiement)`` : l'état de chaque tranche (``regle`` /
    ``exigible`` / ``a_venir``, ``regle_le``) et les montants de l'étape,
    calculés depuis les paiements ENREGISTRÉS (variante ``tranche_reglee`` :
    tranches jusqu'à la livraison supposées réglées)."""
    if not vente:
        return [], None
    tranches = vente['tranches']
    prix = vente['prix_ttc']
    paye = vente['paye']
    effectif = paye
    if variante == T.TRANCHE_REGLEE and tranches:
        effectif = max(paye, tranches[index_livraison(tranches)]['cible'])
    horizon = _horizon(type_acte, tranches)
    # Date à laquelle le cumul ENREGISTRÉ a couvert chaque cible.
    cumul, datés = ZERO, []
    for p in sorted(vente['paiements'], key=lambda x: x['date'] or ''):
        cumul += _d(p['montant']) or ZERO
        datés.append((cumul, p['date']))
    etats, exigible_pose = [], False
    for i, t in enumerate(tranches):
        if effectif >= t['cible']:
            regle_le = next((d for c, d in datés if c >= t['cible']), None)
            etats.append({'statut': 'regle', 'regle_le': regle_le})
        elif horizon is not None and i <= horizon and not exigible_pose:
            exigible_pose = True
            etats.append({'statut': 'exigible', 'regle_le': None})
        else:
            etats.append({'statut': 'a_venir', 'regle_le': None})
    cible = tranches[horizon]['cible'] if tranches else prix
    exigible = max(ZERO, cible - effectif)
    restera = max(ZERO, prix - cible)
    reste = max(ZERO, prix - effectif)
    paiement = {
        'total_regle': _s(effectif),
        'pourcentage_regle': _pct(effectif / prix * 100) if prix else None,
        'exigible_maintenant': _s(exigible),
        'restera_ensuite': _s(restera),
        'reste_a_regler': _s(reste),
        'paye_enregistre': paye,
    }
    return etats, paiement


# ── Blocs vivants ───────────────────────────────────────────────────────────

def _bloc_societe(lecture):
    p = lecture.profil()
    return {
        'nom': p.nom or '',
        'nom_court': p.nom or '',
        'forme_juridique': getattr(p, 'forme_juridique', '') or '',
        'capital_social': getattr(p, 'capital_social', '') or '',
        'adresse': p.adresse or '',
        'rc': getattr(p, 'rc', '') or '',
        'ice': getattr(p, 'ice', '') or '',
        'identifiant_fiscal': getattr(p, 'identifiant_fiscal', '') or '',
        'patente': getattr(p, 'patente', '') or '',
        'cnss': getattr(p, 'cnss', '') or '',
        'telephone': p.telephone or '',
        'email': p.email or '',
        'site_web': getattr(p, 'site_web', '') or '',
        'representant': '',
        'logo_uri': lecture.logo_uri(),
    }


def _bloc_client(chantier):
    client = getattr(chantier, 'client', None)
    vide = {'type': 'particulier', 'nom_complet': '', 'cin': '', 'ice': '',
            'rc': '', 'if_fiscal': '', 'representant': '', 'adresse': '',
            'telephone': '', 'email': ''}
    if client is None:
        return vide
    from apps.documents.builders import _client_block
    base = _client_block(client)
    entreprise = getattr(client, 'type_client', '') == 'entreprise'
    nom = ' '.join(x for x in (base.get('prenom'), base.get('nom')) if x)
    adresse = base.get('adresse') or ''
    if entreprise and not adresse:
        adresse = getattr(client, 'adresse_siege', '') or ''
    return {
        'type': 'entreprise' if entreprise else 'particulier',
        'nom_complet': nom.strip(),
        'cin': getattr(client, 'cin', '') or '',
        'ice': getattr(client, 'ice', '') or '',
        'rc': getattr(client, 'rc', '') or '',
        'if_fiscal': getattr(client, 'if_fiscal', '') or '',
        'representant': (getattr(client, 'contact_nom', '') or '')
        if entreprise else '',
        'adresse': adresse,
        'telephone': base.get('telephone') or '',
        'email': base.get('email') or '',
    }


def _type_installation(chantier):
    devis = getattr(chantier, 'devis', None)
    return (chantier.type_installation
            or getattr(devis, 'mode_installation', '') or 'residentiel')


def _bloc_chantier(chantier, client):
    devis = getattr(chantier, 'devis', None)
    return {
        'id': chantier.pk,
        'reference': chantier.reference or '',
        'adresse': chantier.site_adresse or client.get('adresse') or '',
        'ville': chantier.site_ville or '',
        'devis_reference': getattr(devis, 'reference', '') or '',
        'devis_accepte_le': _iso(getattr(devis, 'date_acceptation', None)),
        'type_installation': _type_installation(chantier),
    }


def _bloc_systeme(chantier, lecture):
    lignes = [{
        'designation': c.get('designation') or '',
        'marque': c.get('marque') or '',
        'quantite': str(c.get('quantite') if c.get('quantite') is not None
                        else ''),
        'numeros_serie': '',
    } for c in lecture.composants()]
    resume = ' · '.join(
        f'{lg["quantite"]} × {lg["designation"]}' for lg in lignes[:3])
    batterie = any('batter' in (lg['designation'] or '').lower()
                   for lg in lignes)
    kwc = chantier.puissance_installee_kwc
    return {
        'puissance_kwc': None if kwc is None else f'{_q(kwc):f}',
        'resume': resume,
        'avec_batterie': batterie,
        'lignes': lignes,
    }


def _bloc_prix(vente, langue):
    if not vente:
        return {'total_ttc': None, 'total_ht': None, 'tva': None,
                'total_en_lettres': ''}
    return {
        'total_ttc': _s(vente['prix_ttc']),
        'total_ht': _s(vente['prix_ht']),
        'tva': _s(vente['tva']),
        'total_en_lettres': _lettres(vente['prix_ttc'], langue),
    }


# Textes courts des tranches, par clé.
_EXIGIBILITE = {
    'fr': {'acompte': 'À la signature',
           'materiel': 'À la livraison chez vous',
           'livraison_materiel': 'À la livraison chez vous',
           'solde': 'À la réception des travaux',
           'commande': 'À la commande',
           'mise_en_service': 'À la mise en service',
           'reception_definitive': 'À la réception définitive'},
    'ar': {'acompte': 'عند التوقيع',
           'materiel': 'عند تسليم المعدات',
           'livraison_materiel': 'عند تسليم المعدات',
           'solde': 'عند تسلّم الأشغال',
           'commande': 'عند الطلب',
           'mise_en_service': 'عند التشغيل',
           'reception_definitive': 'عند التسلّم النهائي'},
}
_MOMENT = {
    'fr': {'acompte': 'à la signature du présent contrat',
           'materiel': 'à la livraison du matériel chez le Client',
           'livraison_materiel': 'à la livraison du matériel chez le Client',
           'solde': 'à la réception des travaux'},
    'ar': {'acompte': 'عند توقيع هذا العقد',
           'materiel': 'عند تسليم المعدات إلى الزبون',
           'livraison_materiel': 'عند تسليم المعدات إلى الزبون',
           'solde': 'عند تسلُّم الأشغال'},
}
_LIBELLES_AR = {'acompte': 'التسبيق', 'materiel': 'تسليم المعدات',
                'livraison_materiel': 'تسليم المعدات', 'solde': 'الرصيد'}
_ETAPES_FR = {1: 'une étape', 2: 'deux étapes', 3: 'trois étapes',
              4: 'quatre étapes', 5: 'cinq étapes', 6: 'six étapes'}


def _nombre_etapes(n, langue):
    """« trois étapes » ; en arabe le nombre de paiements qui suit « على »
    (``composants.nombre_de_dfaat``, forme ``textes_ar.FORMES_CTX``)."""
    if langue == 'ar':
        return C.nombre_de_dfaat(n)
    return _ETAPES_FR.get(n, f'{n} étapes')


def _echeancier(vente, etats, langue):
    if not vente:
        return []
    sortie = []
    for t, etat in zip(vente['tranches'], etats):
        libelle = t['libelle']
        if langue == 'ar':
            libelle = _LIBELLES_AR.get(t['key'], libelle)
        sortie.append({
            'cle': t['cle'],
            'libelle': libelle,
            'pourcentage': _pct(t['pourcentage']),
            'montant_ttc': _s(t['montant']),
            'exigibilite': _EXIGIBILITE[langue].get(t['key'], libelle),
            'statut': etat['statut'],
            'regle_le': etat['regle_le'],
            'note': '',
        })
    return sortie


def _liste_tranches(echeancier, vente, langue):
    lignes = []
    for tr, brute in zip(echeancier, vente['tranches'] if vente else []):
        quand = _MOMENT[langue].get(brute['key']) or tr['exigibilite'].lower()
        pct = C.pourcent(tr['pourcentage'])
        montant = _montant(tr['montant_ttc'], langue)
        if langue == 'ar':
            lignes.append(f'- **{pct}**، أي {montant}، {quand}')
        else:
            lignes.append(f'- **{pct}**, soit {montant}, {quand}')
    fin = '؛' if langue == 'ar' else ' ;'
    texte = '\n'.join(lg + (fin if i < len(lignes) - 1 else '.')
                      for i, lg in enumerate(lignes))
    return texte or None


def _modalites(lecture, langue):
    p = lecture.profil()
    instructions = (getattr(p, 'instructions_paiement', '') or '').strip()
    if instructions:
        return instructions
    nom = p.nom or ''
    rib = (getattr(p, 'rib', '') or '').strip()
    banque = (getattr(p, 'banque', '') or '').strip()
    if langue == 'ar':
        texte = f'يتم الأداء بتحويل بنكي أو بشيك لأمر {nom}.'
        if rib:
            texte += f' RIB : {rib}' + (f' — {banque}' if banque else '') + '.'
        return texte
    texte = f"Paiement par virement ou par chèque à l'ordre de {nom}."
    if rib:
        texte += f' RIB : {rib}' + (f' — {banque}' if banque else '') + '.'
    return texte


# ── Garanties ───────────────────────────────────────────────────────────────

_GARANTIES_CONNUES = {
    # libellé du lecteur de la vente → (clé, désignation, détail)
    'Performance': ('panneaux_performance', 'Panneaux — performance',
                    'Puissance garantie dans le temps, selon la courbe du '
                    'fabricant.'),
    'Panneaux': ('panneaux_produit', 'Panneaux — produit',
                 'Défauts de fabrication et de matériaux.'),
    'Batterie': ('batterie', 'Batterie',
                 'Défauts de fabrication, dans les conditions du fabricant.'),
    'Onduleur': ('onduleur', 'Onduleur',
                 'Défauts de fabrication ; réparation ou remplacement.'),
    'Onduleur (option 1)': ('onduleur_option_1', 'Onduleur (option 1)',
                            'Défauts de fabrication ; réparation ou '
                            'remplacement.'),
    'Onduleur (option 2)': ('onduleur_option_2', 'Onduleur (option 2)',
                            'Défauts de fabrication ; réparation ou '
                            'remplacement.'),
}
_DETAILS_AR = {
    'panneaux_performance': 'قدرة مضمونة مع مرور الوقت، وفق منحنى الصانع.',
    'panneaux_produit': 'عيوب التصنيع والمواد.',
    'batterie': 'عيوب التصنيع، وفق شروط الصانع.',
    'onduleur': 'عيوب التصنيع؛ إصلاح أو استبدال.',
    'onduleur_option_1': 'عيوب التصنيع؛ إصلاح أو استبدال.',
    'onduleur_option_2': 'عيوب التصنيع؛ إصلاح أو استبدال.',
    'installation': 'التركيب والأسلاك والربط المنجزة من طرف فرقنا.',
}
_GARANT = {'fr': 'Garantie du fabricant', 'ar': 'ضمان الصانع'}
_DUREE = re.compile(r'^\s*(\d+)\s*(ans?|mois)\s*$', re.IGNORECASE)


def _duree_en_mois(texte):
    """« 25 ans » → 300, « 18 mois » → 18 ; autre texte → None (le libellé
    est alors gardé tel quel, jamais une durée devinée)."""
    m = _DUREE.match(str(texte or ''))
    if not m:
        return None
    n = int(m.group(1))
    return n if m.group(2).lower() == 'mois' else n * 12


def _garanties_vente(lecture, langue):
    """Garanties du matériel vendu (lecteur ``garanties_de_la_vente``), sans
    la ligne « Installation » du devis : la garantie de pose est servie à
    part (champ du chantier, modèle de la société, 24 mois)."""
    fr = lecture.garanties_vente('fr')
    loc = lecture.garanties_vente(langue) if langue != 'fr' else fr
    sortie = []
    for i, g in enumerate(fr):
        designation_fr = g.get('designation') or ''
        if designation_fr == 'Installation':
            continue
        connu = _GARANTIES_CONNUES.get(designation_fr)
        cle = connu[0] if connu else _slug(designation_fr)
        designation = connu[1] if connu else designation_fr
        detail = connu[2] if connu else ''
        if g.get('detail') and connu:
            detail = f'{detail.rstrip(".")} ({g["detail"]}).'
        if langue != 'fr':
            autre = loc[i] if i < len(loc) else {}
            designation = autre.get('designation') or designation
            detail = _DETAILS_AR.get(cle, '')
        mois = _duree_en_mois(g.get('duree'))
        sortie.append({
            'cle': cle, 'designation': designation, 'duree_mois': mois,
            'duree_libelle': '' if mois else (g.get('duree') or ''),
            'garant': _GARANT[langue], 'detail': detail, 'fin': None,
        })
    sortie.sort(key=lambda x: -(x['duree_mois'] or 0))
    return sortie


def _garantie_installation(chantier, societe, langue):
    mois = (getattr(chantier, 'garantie_installation_mois', None)
            or T.GARANTIE_INSTALLATION_DEFAUT_MOIS)
    perimetre = (getattr(chantier, 'garantie_installation_perimetre', '')
                 or '').strip()
    nom = societe.get('nom_court') or societe.get('nom') or ''
    if langue == 'ar':
        return {'cle': 'installation', 'designation': 'التركيب',
                'duree_mois': mois, 'duree_libelle': '',
                'garant': f'ضمان {nom}'.strip(),
                'detail': perimetre or _DETAILS_AR['installation'], 'fin': None}
    return {'cle': 'installation', 'designation': 'Installation',
            'duree_mois': mois, 'duree_libelle': '',
            'garant': f'Garantie {nom}'.strip(),
            'detail': perimetre or 'Pose, câblage et raccordements réalisés '
                                   'par nos équipes.', 'fin': None}


def _fusion_garanties_modele(garanties, modele):
    """Le modèle de la société s'applique PAR CLÉ (sa garantie d'installation,
    ses textes) : il ne remplace jamais les durées du matériel d'une vente."""
    if not isinstance(modele, list):
        return garanties
    par_cle = {g.get('cle'): g for g in modele if isinstance(g, dict)}
    return [{**g, **{k: v for k, v in par_cle[g['cle']].items()
                     if k in T.CLES_GARANTIE and k not in ('cle', 'fin')}}
            if g['cle'] in par_cle else g for g in garanties]


def _dater_garanties(garanties, depart):
    for g in garanties:
        mois = g.get('duree_mois')
        g['fin'] = (_iso(ajouter_mois(depart, mois))
                    if depart and mois else g.get('fin') or None)
    return garanties


# ── Articles ────────────────────────────────────────────────────────────────

def resoudre_articles(base, liste):
    """Applique une liste d'articles personnalisée (forme stockée) à la liste
    ``base`` : une entrée ``{cle}`` seule reprend l'article de base de même
    clé (jamais figé : ses montants restent vivants), une entrée complète le
    remplace ; l'ordre et les suppressions sont ceux de la liste."""
    if not isinstance(liste, list):
        return base
    par_cle = {a['cle']: a for a in base}
    sortie = []
    for a in liste:
        if not isinstance(a, dict):
            continue
        if 'paragraphes' not in a and 'titre' not in a:
            if a.get('cle') in par_cle:
                sortie.append(par_cle[a['cle']])
            continue
        sortie.append({'cle': a.get('cle') or '', 'titre': a.get('titre') or '',
                       'paragraphes': list(a.get('paragraphes') or [])})
    return sortie


def compacter_articles(base, entrants):
    """Forme stockée d'une liste d'articles reçue de l'écran.

    Une liste qui reprend au moins la moitié des articles de ``base`` est une
    liste COMPLÈTE (elle fixe l'ordre et les suppressions) ; une liste plus
    courte modifie les articles cités par leur clé et ajoute les nouveaux à la
    fin. Un article identique à celui de base est stocké par sa seule clé :
    ainsi un texte non modifié ne fige jamais un montant de la vente."""
    par_cle = {a['cle']: a for a in base}
    cles_base = [a['cle'] for a in base]
    communes = {a['cle'] for a in entrants} & set(cles_base)
    if base and len(communes) * 2 < len(cles_base):
        remplaces = {a['cle']: a for a in entrants}
        liste = [remplaces.get(c, {'cle': c}) for c in cles_base]
        liste += [a for a in entrants if a['cle'] not in par_cle]
    else:
        liste = list(entrants)
    sortie = []
    for a in liste:
        defaut = par_cle.get(a['cle'])
        if 'paragraphes' not in a or (
                defaut is not None and a.get('titre') == defaut['titre']
                and list(a.get('paragraphes') or []) == defaut['paragraphes']):
            sortie.append({'cle': a['cle']})
        else:
            sortie.append(a)
    return sortie


# ── Personnalisations ───────────────────────────────────────────────────────

def _vide(valeur):
    return valeur is None or valeur == ''


def _appliquer_communes(contenu, surcharges):
    """Sections communes aux deux langues (dates, options, signataire,
    livraison, réception, service après-vente) — toujours réglées en
    français."""
    s = surcharges or {}
    for cle in ('lieu', 'date_document'):
        if not _vide(s.get(cle)):
            contenu[cle] = s[cle]
    if isinstance(s.get('societe'), dict) and not _vide(
            s['societe'].get('representant')):
        contenu['societe']['representant'] = s['societe']['representant']
    if isinstance(s.get('options'), dict):
        for k, v in s['options'].items():
            if k in T.CLES_OPTIONS and (
                    v is not None or k == 'penalite_retard_pct'):
                contenu['options'][k] = v
    for section, cles in (('livraison', T.CLES_LIVRAISON),
                          ('reception', T.CLES_RECEPTION),
                          ('sav', T.CLES_SAV)):
        if section in contenu and isinstance(s.get(section), dict):
            for k, v in s[section].items():
                if k in cles and v is not None:
                    contenu[section][k] = (None if v == '' and k in (
                        'date', 'date_mise_en_service') else v)
    if isinstance(s.get('delais'), dict) and not _vide(
            s['delais'].get('date_limite')):
        contenu['_date_limite_fixee'] = s['delais']['date_limite']


def _appliquer_textes(contenu, surcharges, langue, *, modele=False):
    """Sections de texte d'une langue. ``modele`` : les garanties du modèle
    s'appliquent par clé (jamais en remplaçant la liste d'une vente)."""
    s = surcharges or {}
    for cle in ('titre', 'conditions_particulieres', 'conseils_intro'):
        if cle in contenu and isinstance(s.get(cle), str):
            contenu[cle] = s[cle]
    for cle in ('constats', 'reserves', 'quitus', 'conseils', 'entretien'):
        if cle in contenu and isinstance(s.get(cle), list):
            contenu[cle] = copy.deepcopy(s[cle])
    if 'articles' in contenu and isinstance(s.get('articles'), list):
        contenu['articles'] = resoudre_articles(contenu['articles'],
                                                s['articles'])
    if 'garanties' in contenu and isinstance(s.get('garanties'), list):
        if modele:
            contenu['garanties'] = _fusion_garanties_modele(
                contenu['garanties'], s['garanties'])
        else:
            contenu['garanties'] = [
                {k: g.get(k) for k in T.CLES_GARANTIE}
                for g in copy.deepcopy(s['garanties'])]
    if 'echeancier' in contenu and isinstance(s.get('echeancier_textes'), dict):
        for tr in contenu['echeancier']:
            mots = s['echeancier_textes'].get(tr['cle'])
            if isinstance(mots, dict):
                for k in ('exigibilite', 'note'):
                    if isinstance(mots.get(k), str):
                        tr[k] = mots[k]
    if 'delais' in contenu and isinstance(s.get('delais'), dict):
        for k in ('resume', 'detail'):
            if isinstance(s['delais'].get(k), str):
                contenu['delais'][k] = s['delais'][k]
                contenu['delais']['_' + k] = True
    if langue == 'fr' and isinstance(s.get('paiement'), dict) \
            and isinstance(contenu.get('paiement'), dict):
        for k in T.CLES_PAIEMENT_TEXTE:
            if isinstance(s['paiement'].get(k), str) \
                    and k in contenu['paiement']:
                contenu['paiement'][k] = s['paiement'][k]


def _surcharges_texte(objet, langue):
    if objet is None:
        return {}
    return (objet.surcharges_ar if langue == 'ar' else objet.surcharges) or {}


# ── Construction ────────────────────────────────────────────────────────────

def _delais(date_document, jours, date_fixee, langue):
    limite = _date(date_fixee)
    if limite is None and jours not in (None, '') and _date(date_document):
        try:
            limite = _date(date_document) + timedelta(days=int(jours))
        except (TypeError, ValueError):
            limite = None
    longue = C.date_longue(limite, langue=langue) if limite else ''
    if langue == 'ar':
        resume = f'في أجل أقصاه {longue}' if longue else A_PRECISER['ar']
        detail = 'يشمل التسليم والتركيب والتشغيل.'
    else:
        resume = f'Au plus tard le {longue}' if longue else 'À préciser'
        detail = 'Livraison, pose et mise en service comprises.'
    return {'resume': resume, 'detail': detail, 'date_limite': _iso(limite)}


def _options_defaut(client, chantier):
    return {
        'consommateur': client.get('type') != 'entreprise',
        'reserve_propriete': True,
        'raccorde_reseau': _type_installation(chantier) != 'agricole',
        'penalite_retard_pct': None,
        'delai_execution_jours': T.DELAI_EXECUTION_DEFAUT_JOURS,
    }


_TEXTES_FIXES = {
    'fr': {'pieces': 'Les pièces détachées nécessaires sont disponibles '
                     'pendant toute la durée des garanties.',
           'demeure': 'huit jours', 'reponse': 'quinze jours'},
    # Formes de ``textes_ar.FORMES_CTX``.
    'ar': {'pieces': 'قطع الغيار اللازمة متوفرة طوال مدة الضمانات.',
           'demeure': '8 أيام', 'reponse': '15 يومًا'},
}


def _contexte(contenu, vente, langue, refs):
    """Les repères des textes par défaut, déjà mis en forme dans la langue.
    Un repère inconnu est laissé absent : le texte imprime « à préciser »."""
    societe = contenu['societe']
    chantier = contenu['chantier']
    prix = contenu['prix']
    fixes = _TEXTES_FIXES[langue]
    garanties = contenu.get('garanties') or []
    pose = next((g for g in garanties if g.get('cle') == 'installation'), None)
    ctx = {
        'societe': societe.get('nom_court') or societe.get('nom') or None,
        'client': contenu['client'].get('nom_complet') or None,
        'devis_reference': chantier.get('devis_reference') or None,
        'contrat_reference': refs[T.CONTRAT],
        'email_societe': societe.get('email') or None,
        'cndp': '',
        'pieces_detachees': fixes['pieces'],
        'delai_mise_en_demeure': fixes['demeure'],
        'delai_reponse': fixes['reponse'],
        'modalites_paiement': _modalites_texte(contenu),
    }
    accepte = C.date_longue(chantier.get('devis_accepte_le'), langue=langue)
    if langue == 'ar':
        ctx['devis_accepte_le'] = (f'، الذي قبله الزبون بتاريخ {accepte}'
                                   if accepte else '')
    else:
        ctx['devis_accepte_le'] = (f', que le Client a accepté le {accepte}'
                                   if accepte else '')
    if prix.get('total_ttc'):
        ctx['total_ttc'] = _montant(prix['total_ttc'], langue)
        ctx['total_lettres'] = prix.get('total_en_lettres') or (
            '' if langue == 'ar' else None)
    limite = (contenu.get('delais') or {}).get('date_limite')
    if limite:
        longue = C.date_longue(limite, langue=langue)
        ctx['date_limite'] = longue if langue == 'ar' else f'le {longue}'
    if pose and pose.get('duree_mois'):
        ctx['garantie_installation'] = C.duree_mois(pose['duree_mois'],
                                                    langue=langue)
    penalite = contenu['options'].get('penalite_retard_pct')
    if penalite not in (None, ''):
        ctx['penalite_retard'] = C.pourcent(penalite)
    echeancier = contenu.get('echeancier') or []
    if echeancier:
        n = len(echeancier)
        ctx['nombre_etapes'] = _nombre_etapes(n, langue)
        ctx['liste_tranches'] = _liste_tranches(echeancier, vente, langue)
    paiement = contenu.get('paiement') or {}
    if paiement.get('total_regle') is not None and vente:
        ctx['total_regle'] = _montant(paiement['total_regle'], langue)
        ctx['pourcentage_regle'] = C.pourcent(paiement.get('pourcentage_regle'))
        ctx['reste_apres_livraison'] = _montant(
            paiement.get('restera_ensuite'), langue)
        ctx['exigible_maintenant'] = _montant(
            paiement.get('exigible_maintenant'), langue)
        ctx['exigible_lettres'] = _lettres(
            paiement.get('exigible_maintenant'), langue)
        i = index_livraison(vente['tranches'])
        if echeancier:
            ctx['libelle_tranche_livraison'] = echeancier[i]['libelle']
    return {k: v for k, v in ctx.items() if v is not None}


def _modalites_texte(contenu):
    return (contenu.get('paiement') or {}).get('modalites') or contenu.get(
        '_modalites') or None


def _construire(acte, langue='fr', lecture=None, *, avec_modele=True,
                avec_acte=True):
    if langue not in T.LANGUES:
        raise ValueError(f'Langue inconnue : {langue!r}')
    chantier = acte.chantier
    lecture = lecture or Lecture(chantier)
    type_acte, variante = acte.type, acte.variante or ''
    textes = _textes(langue)
    vente = lecture.vente()
    societe = _bloc_societe(lecture)
    client = _bloc_client(chantier)
    refs = {t: reference_acte(t, chantier.reference, chantier.pk)
            for t in T.TYPES}

    contenu = {
        'schema': SCHEMA, 'langue': langue, 'version': acte.version,
        'titre': '', 'lieu': chantier.site_ville or '',
        'date_document': _iso(timezone.localdate()),
        'societe': societe, 'client': client,
        'chantier': _bloc_chantier(chantier, client),
        'systeme': _bloc_systeme(chantier, lecture),
        'prix': _bloc_prix(vente, langue),
        'conditions_particulieres': '',
        'signatures': {'client': None, 'societe': None},
        'options': _options_defaut(client, chantier),
        'type': type_acte, 'variante': variante,
        'reference': refs[type_acte],
    }
    if type_acte == T.LIVRAISON:
        contenu['livraison'] = _livraison_defaut(chantier, langue)
    if type_acte == T.RECEPTION:
        contenu['reception'] = {
            'date_mise_en_service': _iso(chantier.date_mise_en_service),
            'prononcee': False, 'delai_levee_reserves': ''}
    if type_acte == T.CLOTURE:
        contenu['sav'] = {'telephone': societe['telephone'], 'whatsapp': '',
                          'email': societe['email'], 'horaires': ''}

    # 1. Sections communes : modèle « contrat » (signataire des quatre actes),
    #    modèle du type, puis l'acte — toujours les surcharges françaises.
    modele_contrat = lecture.modele(T.CONTRAT) if avec_modele else None
    modele = lecture.modele(type_acte) if avec_modele else None
    if modele_contrat is not None:
        rep = ((modele_contrat.surcharges or {}).get('societe') or {})
        if isinstance(rep, dict) and not _vide(rep.get('representant')):
            societe['representant'] = rep['representant']
    for objet in (modele, acte if avec_acte else None):
        if objet is not None:
            _appliquer_communes(contenu, objet.surcharges)
    date_fixee = contenu.pop('_date_limite_fixee', None)

    # 2. Valeurs dérivées (situation de paiement, délais, garanties).
    etats, paiement = situation(type_acte, variante, vente)
    modalites = _modalites(lecture, langue)
    if type_acte in (T.CONTRAT, T.LIVRAISON, T.RECEPTION, T.CLOTURE):
        contenu['echeancier'] = _echeancier(vente, etats, langue)
    if type_acte == T.CONTRAT:
        contenu['delais'] = _delais(
            contenu['date_document'],
            contenu['options'].get('delai_execution_jours'), date_fixee,
            langue)
        contenu['paiement'] = {'modalites': modalites}
    elif type_acte in (T.LIVRAISON, T.RECEPTION):
        p = paiement or {}
        contenu['paiement'] = {
            'total_regle': p.get('total_regle'),
            'pourcentage_regle': p.get('pourcentage_regle'),
            'exigible_maintenant': p.get('exigible_maintenant'),
            'exigible_en_lettres': _lettres(p.get('exigible_maintenant'),
                                            langue),
            'restera_ensuite': p.get('restera_ensuite'),
            'reste_a_regler': p.get('reste_a_regler'),
        }
        if type_acte == T.RECEPTION:
            nom = societe.get('nom_court') or societe.get('nom') or ''
            contenu['paiement']['engagement'] = (
                f'يُقرّ الزبون بأنه مدين بهذا المبلغ لـ {nom} برسم رصيد الثمن.'
                if langue == 'ar' else
                f'Le Client reconnaît devoir cette somme à {nom} au titre du '
                f'solde du prix.')
        contenu['paiement']['modalites'] = modalites
    else:
        p = paiement or {}
        contenu['reception'] = {'date': _iso(chantier.date_reception)}
        contenu['paiement'] = {
            'total_regle': p.get('total_regle'),
            'pourcentage_regle': p.get('pourcentage_regle'),
            'exigible_maintenant': p.get('exigible_maintenant'),
            'reste_a_regler': p.get('reste_a_regler'),
        }
    if type_acte in (T.CONTRAT, T.CLOTURE):
        garanties = _garanties_vente(lecture, langue)
        garanties.append(_garantie_installation(chantier, societe, langue))
        contenu['garanties'] = garanties

    # 3. Textes par défaut de la langue.
    _textes_par_defaut(contenu, textes, vente, langue, refs)

    # 4. Textes personnalisés : modèle de la société puis acte.
    if modele is not None:
        _appliquer_textes(contenu, _surcharges_texte(modele, langue), langue,
                          modele=True)
    if avec_acte:
        _appliquer_textes(contenu, _surcharges_texte(acte, langue), langue)
    if 'garanties' in contenu:
        _completer_cles_garanties(contenu['garanties'])
        depart = (contenu.get('reception') or {}).get('date') \
            if type_acte == T.CLOTURE else None
        _dater_garanties(contenu['garanties'], depart)
    if 'delais' in contenu:
        contenu['delais'].pop('_resume', None)
        contenu['delais'].pop('_detail', None)
    return contenu


def _completer_cles_garanties(garanties):
    """Une ligne ajoutée à l'écran arrive avec une clé vide : le serveur lui
    donne une clé stable (``perso_<n>``)."""
    prises = {g.get('cle') for g in garanties if g.get('cle')}
    n = 1
    for g in garanties:
        if not g.get('cle'):
            while f'perso_{n}' in prises:
                n += 1
            g['cle'] = f'perso_{n}'
            prises.add(g['cle'])


def _livraison_defaut(chantier, langue):
    pose = chantier.date_pose_prevue
    jours = chantier.duree_pose_jours
    if langue == 'ar':
        suite = (f'التركيب يوم {C.date_longue(pose, langue="ar")}'
                 if pose else 'التركيب')
        detail = f'المدة المتوقعة: {jours} أيام عمل.' if jours else ''
    else:
        suite = f'Pose le {C.date_longue(pose)}' if pose else 'La pose'
        detail = (f'Durée prévue : {jours} jour{"s" if jours > 1 else ""} '
                  f'ouvré{"s" if jours > 1 else ""}.' if jours else '')
    return {'date': None, 'suite': suite, 'suite_detail': detail,
            'avec_series': False}


def _textes_par_defaut(contenu, textes, vente, langue, refs):
    type_acte = contenu['type']
    ctx = _contexte(contenu, vente, langue, refs)
    options = contenu['options']
    contenu['articles'] = textes.articles_par_defaut(
        type_acte, contenu['variante'], ctx, options)
    if type_acte in (T.LIVRAISON, T.RECEPTION):
        contenu['constats'] = textes.constats_par_defaut(type_acte)
        contenu['reserves'] = []
    if type_acte == T.CLOTURE:
        avec_batterie = contenu['systeme']['avec_batterie']
        contenu['quitus'] = textes.quitus_par_defaut(ctx)
        vente_paiements = (vente or {}).get('paiements') or []
        contenu['paiements'] = copy.deepcopy(vente_paiements)
        intro, conseils = textes.conseils_par_defaut(avec_batterie)
        contenu['conseils_intro'] = intro
        contenu['journee'] = textes.journee_solaire(avec_batterie)
        contenu['conseils'] = conseils
        contenu['entretien'] = textes.entretien_par_defaut()


# ── API publique du module ──────────────────────────────────────────────────

def construire_contenu(acte, langue='fr', lecture=None):
    """Le contenu VIVANT d'un acte (lectures seulement)."""
    return _construire(acte, langue, lecture)


def contenu_de(acte, langue='fr', lecture=None):
    """Le contenu servi : figé dès l'émission, vivant pour un brouillon."""
    if acte.statut != T.BROUILLON:
        fige = acte.contenu_ar if langue == 'ar' else acte.contenu
        if fige:
            return fige
    return construire_contenu(acte, langue, lecture)


def articles_de_base(acte, langue='fr', lecture=None, *, avec_modele=True):
    """Les articles de l'acte SANS ses propres personnalisations (avec ou sans
    celles du modèle) : la base contre laquelle une liste reçue est
    compactée."""
    return _construire(acte, langue, lecture, avec_modele=avec_modele,
                       avec_acte=False)['articles']


def sections_modifiables(type_acte, langue='fr'):
    sections = T.SECTIONS_MODIFIABLES[type_acte]
    if langue == 'ar':
        return [s for s in sections if s in T.SECTIONS_TEXTE]
    return list(sections)


def sections_personnalisees(acte, langue='fr'):
    surcharges = _surcharges_texte(acte, langue)
    ordre = T.SECTIONS_MODIFIABLES[acte.type]
    return [s for s in ordre if s in surcharges]


# ── Validation des personnalisations reçues ─────────────────────────────────

class ContenuInvalide(ValueError):
    """Personnalisation refusée (400 ``contenu_invalide``), message français."""


def _exiger(condition, message):
    if not condition:
        raise ContenuInvalide(message)


def _texte(valeur, section):
    _exiger(isinstance(valeur, str), f'Section « {section} » : texte attendu.')
    return valeur


def _liste_textes(valeur, section):
    _exiger(isinstance(valeur, list) and all(isinstance(x, str) for x in valeur),
            f'Section « {section} » : liste de textes attendue.')
    return valeur


def _date_texte(valeur, section, vide_permis=True):
    if valeur is None or (vide_permis and valeur == ''):
        return None
    _exiger(isinstance(valeur, str) and _date(valeur) is not None
            and len(valeur) == 10,
            f'Section « {section} » : date AAAA-MM-JJ attendue.')
    return valeur


def _entier(valeur, section, *, positif=True):
    if valeur is None or valeur == '':
        return None
    if isinstance(valeur, bool):
        raise ContenuInvalide(f'Section « {section} » : nombre entier attendu.')
    try:
        d = Decimal(str(valeur).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ContenuInvalide(f'Section « {section} » : nombre entier attendu.')
    _exiger(d.is_finite() and d == d.to_integral_value()
            and (d >= 0 or not positif) and d < 100000,
            f'Section « {section} » : nombre entier attendu.')
    return int(d)


def _dict_permis(valeur, section, cles):
    _exiger(isinstance(valeur, dict), f'Section « {section} » : objet attendu.')
    return {k: v for k, v in valeur.items() if k in cles}


def _valider_section(type_acte, section, valeur, langue):
    if section in ('titre', 'conditions_particulieres', 'conseils_intro',
                   'lieu'):
        return _texte(valeur, section)
    if section == 'date_document':
        return _date_texte(valeur, section)
    if section in ('reserves', 'quitus', 'entretien'):
        return _liste_textes(valeur, section)
    if section == 'societe':
        v = _dict_permis(valeur, section, T.CLES_SOCIETE)
        _exiger(isinstance(v.get('representant', ''), str),
                'Section « societe » : texte attendu pour le représentant.')
        return v
    if section == 'delais':
        v = _dict_permis(valeur, section, T.CLES_DELAIS if langue == 'fr'
                         else T.CLES_DELAIS_AR)
        if 'date_limite' in v:
            v['date_limite'] = _date_texte(v['date_limite'], section)
        for k in ('resume', 'detail'):
            if k in v and v[k] is not None:
                _texte(v[k], section)
        return v
    if section == 'livraison':
        v = _dict_permis(valeur, section, T.CLES_LIVRAISON)
        if 'date' in v:
            v['date'] = _date_texte(v['date'], section)
        for k in ('suite', 'suite_detail'):
            if k in v and v[k] is not None:
                _texte(v[k], section)
        if 'avec_series' in v:
            _exiger(isinstance(v['avec_series'], bool),
                    'Section « livraison » : vrai ou faux attendu.')
        return v
    if section == 'reception':
        v = _dict_permis(valeur, section, T.CLES_RECEPTION)
        if 'date_mise_en_service' in v:
            v['date_mise_en_service'] = _date_texte(
                v['date_mise_en_service'], section)
        if 'prononcee' in v:
            _exiger(isinstance(v['prononcee'], bool),
                    'Section « reception » : vrai ou faux attendu.')
        if v.get('delai_levee_reserves') is not None:
            _texte(v['delai_levee_reserves'], section)
        return v
    if section == 'sav':
        v = _dict_permis(valeur, section, T.CLES_SAV)
        for k, x in v.items():
            if x is not None:
                _texte(x, section)
        return v
    if section == 'paiement':
        _exiger(isinstance(valeur, dict), 'Section « paiement » : objet attendu.')
        montants = [k for k in valeur if k not in T.CLES_PAIEMENT_TEXTE]
        _exiger(not montants,
                "Les montants ne se modifient pas dans un acte : corrigez "
                "l'échéancier de la vente (" + ', '.join(sorted(montants)) + ').')
        for x in valeur.values():
            if x is not None:
                _texte(x, section)
        return dict(valeur)
    if section == 'options':
        v = _dict_permis(valeur, section, T.CLES_OPTIONS)
        for k in ('consommateur', 'reserve_propriete', 'raccorde_reseau'):
            if k in v and v[k] is not None:
                _exiger(isinstance(v[k], bool),
                        f'Option « {k} » : vrai ou faux attendu.')
        if 'delai_execution_jours' in v:
            v['delai_execution_jours'] = _entier(
                v['delai_execution_jours'], 'options')
        if 'penalite_retard_pct' in v and v['penalite_retard_pct'] is not None:
            d = _d(str(v['penalite_retard_pct']).replace(',', '.'))
            _exiger(d is not None and d.is_finite() and ZERO <= d <= 100,
                    'Option « penalite_retard_pct » : pourcentage entre 0 et '
                    '100 attendu.')
            v['penalite_retard_pct'] = f'{d.normalize():f}'
        return v
    if section == 'echeancier_textes':
        _exiger(isinstance(valeur, dict),
                'Section « echeancier_textes » : objet attendu.')
        sortie = {}
        for cle, mots in valeur.items():
            _exiger(isinstance(mots, dict),
                    'Section « echeancier_textes » : objet attendu par tranche.')
            interdits = [k for k in mots if k not in ('exigibilite', 'note')]
            _exiger(not interdits,
                    "Les montants ne se modifient pas dans un acte : corrigez "
                    "l'échéancier de la vente.")
            sortie[str(cle)] = {k: _texte(v, section) for k, v in mots.items()
                                if v is not None}
        return sortie
    if section == 'articles':
        _exiger(isinstance(valeur, list),
                'Section « articles » : liste attendue.')
        sortie = []
        for a in valeur:
            _exiger(isinstance(a, dict),
                    'Section « articles » : un objet par article attendu.')
            cle = a.get('cle')
            _exiger(cle is None or isinstance(cle, str),
                    'Section « articles » : clé texte attendue.')
            entree = {'cle': cle or ''}
            if 'titre' in a or 'paragraphes' in a:
                entree['titre'] = _texte(a.get('titre') or '', section)
                entree['paragraphes'] = _liste_textes(
                    a.get('paragraphes') or [], section)
            sortie.append(entree)
        n = 1
        prises = {a['cle'] for a in sortie if a['cle']}
        for a in sortie:
            if not a['cle']:
                while f'perso_{n}' in prises:
                    n += 1
                a['cle'] = f'perso_{n}'
                prises.add(a['cle'])
        return sortie
    if section == 'constats':
        _exiger(isinstance(valeur, list),
                'Section « constats » : liste attendue.')
        sortie = []
        for k in valeur:
            _exiger(isinstance(k, dict) and isinstance(k.get('texte'), str),
                    'Section « constats » : {texte, cochee} attendu.')
            sortie.append({'texte': k['texte'], 'cochee': bool(k.get('cochee'))})
        return sortie
    if section == 'conseils':
        _exiger(isinstance(valeur, list),
                'Section « conseils » : liste attendue.')
        sortie = []
        for k in valeur:
            _exiger(isinstance(k, dict), 'Section « conseils » : objet attendu.')
            sortie.append({c: _texte(k.get(c) or '', section)
                           for c in T.CLES_CONSEIL})
        return sortie
    if section == 'garanties':
        _exiger(isinstance(valeur, list),
                'Section « garanties » : liste attendue.')
        sortie = []
        for g in valeur:
            _exiger(isinstance(g, dict), 'Section « garanties » : objet attendu.')
            ligne = {
                'cle': g.get('cle') if isinstance(g.get('cle'), str) else '',
                'designation': _texte(g.get('designation') or '', section),
                'duree_mois': _entier(g.get('duree_mois'), 'garanties'),
                'duree_libelle': _texte(g.get('duree_libelle') or '', section),
                'garant': _texte(g.get('garant') or '', section),
                'detail': _texte(g.get('detail') or '', section),
                'fin': _date_texte(g.get('fin'), section),
            }
            sortie.append(ligne)
        _completer_cles_garanties(sortie)
        return sortie
    raise ContenuInvalide(f'Section inconnue : {section}.')


def valider_surcharges(type_acte, surcharges, langue='fr'):
    """Contrôle et nettoie des personnalisations reçues. Une section hors
    ``sections_modifiables`` (de la langue), un montant ou une forme
    inattendue lève ``ContenuInvalide`` (message français). ``None`` = remettre
    la section au défaut (gardé tel quel)."""
    if langue not in T.LANGUES:
        raise ContenuInvalide(f'Langue inconnue : {langue}.')
    _exiger(isinstance(surcharges, dict), 'Personnalisations : objet attendu.')
    permises = set(sections_modifiables(type_acte, langue))
    propre = {}
    for section, valeur in surcharges.items():
        if section not in permises:
            if section in T.SECTIONS_MODIFIABLES[type_acte] and langue == 'ar':
                raise ContenuInvalide(
                    f'Section « {section} » : commune aux deux langues, elle '
                    f'se règle en français.')
            raise ContenuInvalide(f'Section inconnue : {section}.')
        propre[section] = (None if valeur is None else
                           _valider_section(type_acte, section, valeur, langue))
    return propre


# ── Avertissements ──────────────────────────────────────────────────────────

def avertissements(acte, contenu=None, lecture=None):
    """Ce que l'écran doit dire avant l'émission (brouillon seulement) :
    vente absente, paiements non enregistrés, date limite à préciser,
    traduction arabe en retard sur le français."""
    if acte.statut != T.BROUILLON:
        return []
    lecture = lecture or Lecture(acte.chantier)
    vente = lecture.vente()
    if vente is None:
        return ["Ce chantier n'a pas de devis accepté : le prix et "
                "l'échéancier sont à préciser."]
    sortie = []
    tranches = vente['tranches']
    if acte.type == T.LIVRAISON and tranches:
        i = index_livraison(tranches)
        cible = tranches[i]['cible']
        if acte.variante == T.RESTE_A_REGLER:
            du = max(ZERO, cible - vente['paye'])
            if du > 0:
                sortie.append(
                    f'La tranche « {tranches[i]["libelle"]} » n\'est pas '
                    f'encore réglée : {C.montant(du)} restent à encaisser.')
        elif vente['paye'] < cible:
            sortie.append(
                f"L'ERP n'a enregistré que {C.montant(vente['paye'])} de "
                f'paiements : cette version suppose {C.montant(cible)} réglés.')
    if acte.type == T.CLOTURE:
        reste = reste_du(vente)
        if reste > 0:
            sortie.append(
                f'Le prix n\'est pas réglé en totalité : {C.montant(reste)} '
                f'restent dus. Le quitus ne peut pas être émis.')
    if acte.type == T.CONTRAT:
        contenu = contenu if contenu is not None else construire_contenu(
            acte, 'fr', lecture)
        if not (contenu.get('delais') or {}).get('date_limite'):
            sortie.append("La date limite d'exécution est à préciser.")
    if not (acte.chantier.client_id):
        sortie.append("Ce chantier n'a pas de client : l'identité du Client "
                      "est à préciser.")
    retard = [T.LIBELLES_SECTIONS[s] for s in T.SECTIONS_MODIFIABLES[acte.type]
              if s in T.SECTIONS_TEXTE and s in (acte.surcharges or {})
              and s not in (acte.surcharges_ar or {})]
    if retard:
        sortie.append('La traduction arabe ne reprend pas vos modifications '
                      'de : ' + ', '.join(retard) + '.')
    return sortie


def reste_du(vente):
    """Ce qui reste dû sur la vente (``solde_devis`` : prix − payé − avoirs de
    réduction), jamais négatif ; None sans vente."""
    if not vente:
        return None
    return max(ZERO, vente['reste'])
