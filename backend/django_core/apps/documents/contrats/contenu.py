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
import difflib
import functools
import logging
import re
import string
import types
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
    try:
        suivant = date(annee + (mois_ == 12), mois_ % 12 + 1, 1)
        dernier = (suivant - timedelta(days=1)).day
        return date(annee, mois_, min(d.day, dernier))
    except (OverflowError, ValueError):  # au-delà de l'an 9999
        return None


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

    def date_du_contrat(self):
        """La date du contrat d'installation ÉMIS (ou signé) de ce chantier :
        la date imprimée sur son contenu figé, à défaut celle de son
        émission ; None tant qu'il n'est pas émis."""
        def lire():
            from ..models import ActeContractuel
            acte = (ActeContractuel.objects
                    .filter(company=self.chantier.company_id,
                            chantier=self.chantier.pk, type=T.CONTRAT,
                            statut__in=(T.EMIS, T.SIGNE))
                    .only('contenu', 'emis_le').first())
            if acte is None:
                return None
            return _date((acte.contenu or {}).get('date_document')) or (
                timezone.localtime(acte.emis_le).date()
                if acte.emis_le else None)
        return self._une_fois('date_contrat', lire)

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
        libelles = {t['facture_id']: (t['libelle'], t['key'])
                    for t in plan['tranches'] if t.get('facture_id')}
        paiements = [{
            'date': _iso(p['date_paiement']),
            'libelle': (libelles.get(p['facture_id']) or ('Paiement',))[0],
            'mode': p.get('mode_libelle') or '',
            'montant': _s(p['montant']),
            '_key': (libelles.get(p['facture_id']) or ('', ''))[1],
        } for p in paiements_des_factures([f.pk for f in factures])]
        tranches = [{
            'cle': t['cle'], 'key': t['key'], 'libelle': t['libelle'],
            'montant': _q(t['montant_ttc']),
            'cible': _q(t['cible_cumul_ttc']),
            'pourcentage': t['pourcentage'],
        } for t in plan['tranches']]
        paye = _q(solde['paye'])
        return {
            'prix_ttc': _q(plan['prix_convenu_ttc']),
            'prix_ht': _q(plan['prix_convenu_ht']),
            'tva': _q(plan['prix_convenu_tva']),
            'paye': paye,
            'reste': _q(solde['restant']),
            'avoirs': _q(solde.get('avoirs') or ZERO),
            'tranches': tranches,
            'paiements': paiements,
            'reglements': reglements(paiements, paye),
        }


def reglements(paiements, paye):
    """Les lignes du tableau des paiements : chaque encaissement, puis — si
    le payé canonique (``solde_devis``) en compte davantage (escompte, avance
    ventilée) ou moins (part d'une facture commune) — une ligne NOMMÉE pour
    l'écart. La somme des lignes égale toujours ``paye``, la ligne de total
    du tableau : une seule source."""
    lignes = [dict(p) for p in paiements]
    ecart = _q(paye - sum((_d(p['montant']) or ZERO for p in paiements),
                          ZERO))
    if ecart > 0:
        lignes.append({'date': None, 'libelle': 'Escompte ou avance ventilée',
                       'mode': '', 'montant': _s(ecart),
                       '_key': '_escompte_avance'})
    elif ecart < 0:
        lignes.append({'date': None,
                       'libelle': 'Part imputée à une autre vente',
                       'mode': '', 'montant': _s(ecart),
                       '_key': '_autre_vente'})
    return lignes


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
    """Index de la DERNIÈRE tranche due à la livraison : celle dont la clé
    désigne la commande ou la livraison du matériel (la somme due à la
    livraison est sa cible cumulée) ; sans aucune, la seule première tranche
    (``livraison_sans_etape`` le signale). Jamais « l'avant-dernière » : avec
    50 / 50 ou quatre tranches, ce n'est pas l'étape de la livraison."""
    trouvees = [i for i, t in enumerate(tranches)
                if t['key'] in T.CLES_TRANCHE_LIVRAISON]
    return trouvees[-1] if trouvees else 0


def livraison_sans_etape(tranches):
    """Aucune tranche de l'échéancier ne désigne la commande ni la
    livraison."""
    return bool(tranches) and not any(
        t['key'] in T.CLES_TRANCHE_LIVRAISON for t in tranches)


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
    tranches jusqu'à la livraison supposées réglées).

    Ce qui est dû ne dépasse jamais ce que la vente doit encore
    (``solde_devis['restant']`` : prix − payé − avoirs, retenues, abandons) :
    la part du prix soldée SANS paiement (``deduit``) réduit le reste à
    régler, et la somme exigible à cette étape en est bornée — dans les deux
    langues et les deux variantes de livraison, une seule formule."""
    if not vente:
        return [], None
    tranches = vente['tranches']
    prix = vente['prix_ttc']
    paye = vente['paye']
    restant = vente.get('reste')
    deduit = ZERO if restant is None else max(
        ZERO, prix - paye - max(ZERO, restant))
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
    reste = max(ZERO, prix - effectif - deduit)
    exigible = min(max(ZERO, cible - effectif), reste)
    # Ce qui restera après cette étape : le reste moins l'exigible (encadré
    # « reste à régler » = exigible + restera, toujours).
    restera = max(ZERO, reste - exigible)
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


# Textes courts des tranches : une entrée par clé d'échéancier (résidentiel
# acompte / materiel / solde, jalons C&I), dans les deux langues.
#: « تسلُّم » (réception) écrit d'une seule façon partout, comme dans les
#: textes arabes : damma puis chadda.
TASALLUM = 'تسلُّم'
_EXIGIBILITE = {
    'fr': {'acompte': 'À la signature',
           'materiel': 'À la livraison chez vous',
           'livraison_materiel': 'À la livraison chez vous',
           'solde': 'À la réception des travaux',
           'commande': 'À la commande',
           'mise_en_service': 'À la mise en service',
           'reception_definitive': 'À la réception définitive',
           'reception_financeur': 'À la réception signée (organisme '
                                  'financeur)',
           'liberation_retenue': 'À la libération de la retenue de garantie'},
    'ar': {'acompte': 'عند التوقيع',
           'materiel': 'عند تسليم المعدات',
           'livraison_materiel': 'عند تسليم المعدات',
           'solde': f'عند {TASALLUM} الأشغال',
           'commande': 'عند الطلب',
           'mise_en_service': 'عند التشغيل',
           'reception_definitive': f'عند ال{TASALLUM} النهائي',
           'reception_financeur': f'عند ال{TASALLUM} الموقَّع (الجهة '
                                  f'المموِّلة)',
           'liberation_retenue': 'عند الإفراج عن اقتطاع الضمان'},
}
_MOMENT = {
    'fr': {'acompte': 'à la signature du présent contrat',
           'materiel': 'à la livraison du matériel chez le Client',
           'livraison_materiel': 'à la livraison du matériel chez le Client',
           'solde': 'à la réception des travaux',
           'commande': 'à la commande du matériel',
           'mise_en_service': "à la mise en service de l'installation",
           'reception_definitive': 'à la réception définitive des travaux',
           'reception_financeur': "à la réception signée, par l'organisme "
                                  "financeur",
           'liberation_retenue': 'à la libération de la retenue de garantie'},
    'ar': {'acompte': 'عند توقيع هذا العقد',
           'materiel': 'عند تسليم المعدات إلى الزبون',
           'livraison_materiel': 'عند تسليم المعدات إلى الزبون',
           'solde': f'عند {TASALLUM} الأشغال',
           'commande': 'عند طلب المعدات',
           'mise_en_service': 'عند تشغيل المنظومة',
           'reception_definitive': f'عند ال{TASALLUM} النهائي للأشغال',
           'reception_financeur': f'عند ال{TASALLUM} الموقَّع، من طرف الجهة '
                                  f'المموِّلة',
           'liberation_retenue': 'عند الإفراج عن اقتطاع الضمان'},
}
#: Libellé arabe de chaque tranche ; « solde » = « باقي الثمن » partout.
_LIBELLES_AR = {'acompte': 'التسبيق', 'materiel': 'تسليم المعدات',
                'livraison_materiel': 'تسليم المعدات',
                'solde': 'باقي الثمن', 'commande': 'الطلبية',
                'mise_en_service': 'التشغيل',
                'reception_definitive': f'ال{TASALLUM} النهائي',
                'reception_financeur': 'أداء الجهة المموِّلة',
                'liberation_retenue': 'الإفراج عن اقتطاع الضمان'}
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


def _fusion_garanties_modele(garanties, modele, cles=None):
    """Le modèle de la société s'applique PAR CLÉ (sa garantie d'installation,
    ses textes) : il ne remplace jamais les durées du matériel d'une vente.
    ``cles`` : les champs repris (tous sauf ``cle`` / ``fin`` par défaut)."""
    if not isinstance(modele, list):
        return garanties
    cles = cles or tuple(k for k in T.CLES_GARANTIE if k not in ('cle', 'fin'))
    par_cle = {g.get('cle'): g for g in modele if isinstance(g, dict)}
    return [{**g, **{k: v for k, v in par_cle[g['cle']].items() if k in cles}}
            if g['cle'] in par_cle else g for g in garanties]


def _garanties_ar(defauts_ar, lignes_fr, traductions):
    """Les garanties de la traduction arabe : les LIGNES, durées et dates de
    fin du français (personnalisées ou non) ; pour chaque ligne, la
    désignation, le garant et le détail traduits à la main (même ``cle``),
    sinon la traduction par défaut, sinon le texte français. Une traduction
    dont la ``cle`` n'est pas une ligne française n'ajoute rien."""
    par_cle_defaut = {g.get('cle'): g for g in defauts_ar}
    par_cle_trad = {g.get('cle'): g for g in traductions or []
                    if isinstance(g, dict) and g.get('cle')}
    sortie = []
    for g in (lignes_fr if lignes_fr is not None else defauts_ar):
        ligne = {k: g.get(k) for k in T.CLES_GARANTIE}
        for source in (par_cle_defaut.get(g.get('cle')),
                       par_cle_trad.get(g.get('cle'))):
            for k in T.CLES_GARANTIE_TEXTE:
                if source is not None and isinstance(source.get(k), str):
                    ligne[k] = source[k]
        sortie.append(ligne)
    return sortie


def _dater_garanties(garanties, depart):
    for g in garanties:
        mois = g.get('duree_mois')
        g['fin'] = (_iso(ajouter_mois(depart, mois))
                    if depart and mois else g.get('fin') or None)
    return garanties


# ── Gabarits : un texte personnalisé ne fige jamais une valeur ──────────────
# Un article ou un quitus est une suite de JETONS : texte littéral
# ``('t', texte)`` ou repère ``('r', nom)`` (la valeur vivante ``ctx[nom]``).
# Les textes par défaut sont lus en jetons en les rendant avec des
# SENTINELLES à la place des valeurs. Une correction faite à l'écran est une
# différence sur le texte que l'écran AFFICHAIT : elle est rejouée sur les
# jetons de ce texte (``aligner``), jamais devinée en cherchant une valeur
# dans le texte.
#
# Forme stockée d'un texte : une chaîne où « {nom} » est un repère et
# « {{ » / « }} » des accolades tapées ; le rendu ne substitue que des noms de
# repères connus (``noms_reperes`` et clés du contexte), jamais par
# ``str.format`` : aucun accès « {societe[x]} » n'est évalué. Un paragraphe
# (ou le titre) peut aussi valoir ``{'defaut': j}`` — le paragraphe j de
# l'article de base, entièrement vivant, y compris si le texte par défaut
# change — ou ``{'defaut': j, 'texte': …}`` — la version de l'utilisateur du
# paragraphe j, imprimée tant que ce paragraphe existe (une option qui le
# retire la masque, la recocher la rend). Un article personnalisé est stocké
# ``{cle, v: 2, titre, paragraphes[, base]}`` ; l'ancienne forme (chaînes
# seules, sans ``v``) se lit toujours, rendue telle qu'elle est.

#: Espaces que les montants mis en forme emploient (normale, insécable,
#: fine insécable).
_SEPARATEURS = '   '
_OUVRE, _FERME = '', ''
_SENTINELLE = re.compile(f'{_OUVRE}([^{_FERME}]*){_FERME}')
_NOM_REPERE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_REPERE_STOCKE = re.compile(r'\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}')
#: Forme stockée d'un article personnalisé.
FORME_ARTICLE = 2
#: Séparateur des paragraphes quand plusieurs sont alignés d'un bloc.
_SEP = '\n\n'
#: Un repère VIDE ne s'ancre qu'à un voisin resté dans un bloc d'au moins
#: autant de caractères inchangés — jamais à une lettre isolée qu'un texte
#: réécrit partage par hasard avec l'ancien.
_ANCRE_MIN = 3
_ESPACES = str.maketrans({' ': ' ', ' ': ' '})


def _espaces(texte):
    """Le texte, espaces insécables et fines ramenées à l'espace normale :
    deux textes qui ne diffèrent que par elles sont le même texte (le
    navigateur renvoie souvent des espaces normales)."""
    return texte.translate(_ESPACES)


def _memes(a, b):
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(
            _memes(x, y) for x, y in zip(a, b))
    return isinstance(b, str) and _espaces(a) == _espaces(b)


def _fusionner(jetons):
    """Jetons normalisés : littéraux voisins réunis, littéraux vides ôtés."""
    sortie = []
    for sorte, valeur in jetons:
        if sorte == 't':
            if not valeur:
                continue
            if sortie and sortie[-1][0] == 't':
                sortie[-1] = ('t', sortie[-1][1] + valeur)
                continue
        sortie.append((sorte, valeur))
    return sortie


def lire_gabarit(texte):
    """Les jetons d'un texte stocké (« {nom} » repère, « {{ » / « }} »
    accolades ; toute autre accolade est du texte)."""
    texte = '' if texte is None else str(texte)
    jetons, pos = [], 0
    for m in _REPERE_STOCKE.finditer(texte):
        jetons.append(('t', texte[pos:m.start()]))
        if m.group(1):
            jetons.append(('r', m.group(1)))
        else:
            jetons.append(('t', m.group(0)[0]))
        pos = m.end()
    jetons.append(('t', texte[pos:]))
    return _fusionner(jetons)


def ecrire_gabarit(jetons):
    """La forme stockée de jetons (accolades tapées doublées)."""
    return ''.join(
        valeur.replace('{', '{{').replace('}', '}}') if sorte == 't'
        else '{' + valeur + '}' for sorte, valeur in jetons)


def _chaines_du_module(module):
    """Les chaînes écrites dans un module de textes (constantes et corps des
    fonctions), pour y lire les repères qu'ils citent."""
    pile = [v for k, v in vars(module).items() if not k.startswith('__')]
    vus = set()
    while pile:
        objet = pile.pop()
        if id(objet) in vus:
            continue
        vus.add(id(objet))
        if isinstance(objet, str):
            yield objet
        elif isinstance(objet, (tuple, list, set, frozenset)):
            pile.extend(objet)
        elif isinstance(objet, dict):
            pile.extend(objet.values())
        elif isinstance(objet, types.CodeType):
            pile.extend(objet.co_consts)
        elif isinstance(objet, types.FunctionType) \
                and objet.__module__ == module.__name__:
            pile.append(objet.__code__)


def _champs(chaine):
    try:
        return {nom for _l, nom, _s, _c in string.Formatter().parse(chaine)
                if nom and _NOM_REPERE.fullmatch(nom)}
    except ValueError:
        return set()


@functools.lru_cache(maxsize=1)
def noms_reperes():
    """Tous les repères que les textes par défaut citent (lus dans
    ``textes`` et ``textes_ar``, jamais une liste écrite ici) : un repère
    connu mais absent du contexte s'imprime « à préciser »."""
    from . import textes
    modules, noms = [textes], set()
    try:
        from . import textes_ar
        modules.append(textes_ar)
        noms |= set(getattr(textes_ar, 'FORMES_CTX', {}))
    except ImportError:
        pass
    for module in modules:
        for chaine in _chaines_du_module(module):
            noms |= _champs(chaine)
    return frozenset(noms)


def _valeur(nom, ctx, langue, connus):
    if nom in ctx:
        valeur = ctx[nom]
        return '' if valeur is None else str(valeur)
    if nom in connus:
        return A_PRECISER.get(langue, A_PRECISER['fr'])
    return '{' + nom + '}'


def rendre_jetons(jetons, ctx, langue='fr', connus=None):
    """Le texte de jetons, avec les valeurs vivantes de ``ctx`` (un repère
    connu absent s'imprime « à préciser » ; un nom inconnu reste écrit)."""
    ctx = ctx or {}
    connus = (frozenset(ctx) | noms_reperes()) if connus is None else connus
    return ''.join(valeur if sorte == 't'
                   else _valeur(valeur, ctx, langue, connus)
                   for sorte, valeur in jetons)


def rendre_gabarit(gabarit, ctx, langue='fr'):
    """Le texte d'un gabarit stocké, avec les valeurs vivantes de ``ctx`` —
    substitution stricte des seuls repères connus, jamais d'erreur."""
    return rendre_jetons(lire_gabarit(gabarit), ctx, langue)


def _jetons_sentinelles(texte):
    texte = texte or ''
    jetons, pos = [], 0
    for m in _SENTINELLE.finditer(texte):
        jetons += [('t', texte[pos:m.start()]), ('r', m.group(1))]
        pos = m.end()
    jetons.append(('t', texte[pos:]))
    return _fusionner(jetons)


def _sentinelles(ctx):
    return {nom: f'{_OUVRE}{nom}{_FERME}'
            for nom in set(ctx or {}) | noms_reperes()}


def articles_en_jetons(textes, type_acte, variante, options, ctx):
    """Les articles PAR DÉFAUT d'un acte, en jetons (mêmes clés, mêmes
    paragraphes, mêmes conditions sur ``options`` que ``textes``)."""
    s = _sentinelles(ctx)
    return [{'cle': a['cle'], 'titre': _jetons_sentinelles(a.get('titre')),
             'paragraphes': [_jetons_sentinelles(p)
                             for p in a.get('paragraphes') or []]}
            for a in textes.articles_par_defaut(type_acte, variante, s,
                                                options)]


def quitus_en_jetons(textes, ctx):
    return [_jetons_sentinelles(p)
            for p in textes.quitus_par_defaut(_sentinelles(ctx))]


# ── Résolution : textes stockés → jetons ────────────────────────────────────

def _ref(x):
    """L'indice d'un renvoi ``{'defaut': j}`` (avec ou sans ``texte``)."""
    if isinstance(x, dict):
        j = x.get('defaut')
        if isinstance(j, int) and not isinstance(j, bool):
            return j
    return None


def _jetons_de(x, base):
    """Les jetons d'un texte stocké relatif à ``base`` (liste de jetons), ou
    None quand il ne s'imprime pas (renvoi vers un paragraphe absent)."""
    if isinstance(x, str):
        return lire_gabarit(x)
    j = _ref(x)
    if j is None or not 0 <= j < len(base):
        return None
    if isinstance(x.get('texte'), str):
        return lire_gabarit(x['texte'])
    return base[j]


def resoudre_paragraphes(base, liste, masques=None):
    """``[(jetons, source)]`` : une liste stockée de paragraphes appliquée
    aux paragraphes ``base`` (None : ceux de la base, en renvois)."""
    if not isinstance(liste, list):
        return [(p, {'defaut': j}) for j, p in enumerate(base)]
    sortie = []
    for x in liste:
        jetons = _jetons_de(x, base)
        if jetons is not None:
            sortie.append((jetons, x))
        elif masques is not None and _ref(x) is not None:
            masques.append(x)
    return sortie


def _en_base(articles):
    """Des articles résolus devenus la BASE du niveau suivant : chaque
    paragraphe y est le renvoi ``{'defaut': j}``."""
    return [{'cle': a['cle'], 'titre': a['titre'],
             'paragraphes': list(a['paragraphes']),
             'src_titre': {'defaut': 0},
             'src': [{'defaut': j} for j in range(len(a['paragraphes']))],
             'de_base': True, 'entree': None} for a in articles]


def resoudre_articles(base, liste, masques=None):
    """Applique une liste d'articles stockée à ``base`` (articles en jetons).
    Entrées : ``{cle}`` reprend l'article de base ; ``{cle, retire}`` est un
    article supprimé à l'écran ; ``{cle, titre, paragraphes[, base]}`` est un
    article personnalisé. Une personnalisation d'un article de base
    (``base``) n'est pas imprimée quand une option retire cet article —
    elle reste stockée et revient avec l'option (``masques`` la reçoit) ; un
    article de base jamais cité par la liste (une option recochée, un
    article nouveau) reprend sa place dans l'ordre de base."""
    if not isinstance(liste, list):
        return list(base)
    par_cle = {a['cle']: a for a in base}
    citees = {a.get('cle') for a in liste if isinstance(a, dict)}
    sortie = []
    for e in liste:
        if not isinstance(e, dict) or e.get('retire'):
            continue
        cle = e.get('cle') or ''
        b = par_cle.get(cle)
        if 'paragraphes' not in e and 'titre' not in e:
            if b is not None:
                sortie.append(b)
            continue
        if e.get('base') and b is None:
            if masques is not None:
                masques.append(('article', e))
            continue
        titre = _jetons_de(e.get('titre', ''), [b['titre']] if b else [])
        caches = []
        paragraphes = resoudre_paragraphes(
            b['paragraphes'] if b else [], list(e.get('paragraphes') or []),
            caches)
        if caches and masques is not None:
            masques.append(('paragraphe', e))
        sortie.append({'cle': cle, 'titre': titre or [],
                       'paragraphes': [j for j, _s in paragraphes],
                       'src_titre': e.get('titre', ''),
                       'src': [s for _j, s in paragraphes],
                       'de_base': b is not None, 'entree': e})
    for i, b in enumerate(base):
        if b['cle'] in citees:
            continue
        avant = {x['cle'] for x in base[:i]}
        pos = 0
        for j, s in enumerate(sortie):
            if s['cle'] in avant:
                pos = j + 1
        sortie.insert(pos, b)
    return sortie


def _rendre_article(a, ctx, langue, connus):
    return {'cle': a['cle'],
            'titre': rendre_jetons(a['titre'], ctx, langue, connus),
            'paragraphes': [rendre_jetons(p, ctx, langue, connus)
                            for p in a['paragraphes']]}


# ── Alignement : une correction rejouée sur les jetons affichés ─────────────

def _ancre(a, debuts, image, bloc, longueur):
    """Position, dans le texte saisi, d'un repère VIDE placé en ``a`` du
    texte affiché : juste après son voisin de gauche s'il est resté (un
    fragment vide est collé au texte qui le précède : « {devis_reference}
    {devis_accepte_le} », « {contrat_reference}.{ecart_regle} ») ; en début
    de paragraphe, juste avant son voisin de droite. None : l'utilisateur a
    réécrit cet endroit, le repère disparaît."""
    if a > 0 and a not in debuts:
        g = image[a - 1]
        return g + 1 if g is not None and bloc[a - 1] >= _ANCRE_MIN else None
    if a < longueur and image[a] is not None and bloc[a] >= _ANCRE_MIN:
        return image[a]
    return None


def aligner(affiches, saisis, ctx, langue='fr', connus=None):
    """Rejoue sur des jetons la correction faite à l'écran.

    ``affiches`` : les jetons des paragraphes que l'écran a montrés (rendus
    avec ``ctx``) ; ``saisis`` : les paragraphes renvoyés. Rend une liste de
    jetons par paragraphe saisi. Les caractères laissés tels quels gardent
    leur origine ; un repère dont TOUTE la valeur est restée, d'un seul
    tenant, redevient ``{nom}`` ; un repère dont la valeur a été modifiée
    en son milieu devient du texte (l'utilisateur l'a reprise à son compte —
    le contrôle des montants à l'émission s'y applique) ; un repère vide
    garde sa place tant que son voisin est resté (``_ancre``)."""
    ctx = ctx or {}
    connus = (frozenset(ctx) | noms_reperes()) if connus is None else connus
    morceaux, reperes, debuts, pos = [], [], set(), 0
    for k, jetons in enumerate(affiches):
        if k:
            morceaux.append(_SEP)
            pos += len(_SEP)
        debuts.add(pos)
        for sorte, valeur in jetons:
            texte = (valeur if sorte == 't'
                     else _valeur(valeur, ctx, langue, connus))
            if sorte == 'r':
                reperes.append((valeur, pos, pos + len(texte)))
            morceaux.append(texte)
            pos += len(texte)
    affiche = ''.join(morceaux)
    saisi = _SEP.join(saisis)
    image, bloc = [None] * len(affiche), [0] * len(affiche)
    inverse = [None] * len(saisi)
    # Espaces normale, insécable et fine insécable : égales pour
    # l'alignement (le navigateur rend souvent des espaces normales).
    for tag, i1, i2, j1, _j2 in difflib.SequenceMatcher(
            None, _espaces(affiche), _espaces(saisi),
            autojunk=False).get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                image[i1 + k], bloc[i1 + k] = j1 + k, i2 - i1
                inverse[j1 + k] = i1 + k

    def litteral(a, b):
        # Un caractère resté garde celui du texte affiché (ses espaces).
        return ''.join(saisi[u] if inverse[u] is None
                       else affiche[inverse[u]] for u in range(a, b))
    evenements = []
    for ordre, (nom, a, b) in enumerate(reperes):
        if b > a:
            vues = image[a:b]
            if None not in vues and vues[-1] - vues[0] == b - a - 1:
                evenements.append((vues[0], ordre, vues[-1] + 1, nom))
        else:
            u = _ancre(a, debuts, image, bloc, len(affiche))
            if u is not None:
                evenements.append((u, ordre, u, nom))
    evenements.sort()
    sortie, debut = [], 0
    for texte in saisis:
        fin, jetons, curseur = debut + len(texte), [], debut
        for ud, _ordre, uf, nom in evenements:
            if ud < curseur or ud < debut or uf > fin:
                continue
            jetons += [('t', litteral(curseur, ud)), ('r', nom)]
            curseur = uf
        jetons.append(('t', litteral(curseur, fin)))
        sortie.append(_fusionner(jetons))
        debut = fin + len(_SEP)
    return sortie


def _forme_stockee(jetons, source, base):
    """La forme stockée d'un paragraphe (ou titre) aligné : le renvoi
    ``{'defaut': j}`` s'il redevient le paragraphe j de la base, sinon sa
    chaîne — liée au paragraphe d'origine (``{'defaut': j, 'texte'}``) quand
    il en vient, pour qu'une option qui retire ce paragraphe la masque."""
    j = _ref(source)
    jetons = _fusionner(jetons)
    candidats = ([j] if j is not None and j < len(base) else []) + list(
        range(len(base)))
    for k in candidats:
        if _fusionner(base[k]) == jetons:
            return {'defaut': k}
    texte = ecrire_gabarit(jetons)
    return {'defaut': j, 'texte': texte} if j is not None else texte


def _compacter_paragraphes(affiches, saisis, base, ctx, langue, connus):
    """Forme stockée d'une liste de paragraphes renvoyée par l'écran.
    ``affiches`` : ``[(jetons, source)]`` tels que montrés. Même nombre :
    paragraphe par paragraphe ; sinon les listes sont d'abord alignées
    (paragraphes inchangés, blocs remplacés alignés d'un tenant). Un
    paragraphe inchangé garde sa source (renvoi vivant ou texte stocké) ;
    un paragraphe ajouté est du texte."""
    rendus = [rendre_jetons(j, ctx, langue, connus) for j, _s in affiches]
    if len(rendus) == len(saisis):
        paires = [([i], [i]) for i in range(len(saisis))]
    else:
        paires = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, [_espaces(r) for r in rendus],
                [_espaces(s) for s in saisis], autojunk=False).get_opcodes():
            if tag == 'equal':
                paires += [([i1 + k], [j1 + k]) for k in range(i2 - i1)]
            elif j2 > j1:
                paires.append((list(range(i1, i2)), list(range(j1, j2))))
    sortie = []
    for ia, ju in paires:
        seul = len(ia) == 1 and len(ju) == 1
        if seul and _memes(rendus[ia[0]], saisis[ju[0]]):
            sortie.append(affiches[ia[0]][1])
            continue
        source = affiches[ia[0]][1] if seul else None
        for jetons in aligner([affiches[i][0] for i in ia],
                              [saisis[j] for j in ju], ctx, langue, connus):
            sortie.append(_forme_stockee(jetons, source, base))
    return sortie


def _compacter_article(a, titre, paragraphes, b, ctx, langue, connus):
    """L'entrée stockée d'un article modifié à l'écran (``a`` : tel
    qu'affiché, ``b`` : son article de base ou None)."""
    if _memes(rendre_jetons(a['titre'], ctx, langue, connus), titre):
        src_titre = a['src_titre']
    else:
        src_titre = _forme_stockee(
            aligner([a['titre']], [titre], ctx, langue, connus)[0],
            a['src_titre'] if _ref(a['src_titre']) is not None else None,
            [b['titre']] if b else [])
    paras = _compacter_paragraphes(list(zip(a['paragraphes'], a['src'])),
                                   paragraphes,
                                   b['paragraphes'] if b else [], ctx, langue,
                                   connus)
    if b is not None and src_titre == {'defaut': 0} and paras == [
            {'defaut': j} for j in range(len(b['paragraphes']))]:
        return {'cle': a['cle']}
    entree = {'cle': a['cle'], 'v': FORME_ARTICLE, 'titre': src_titre,
              'paragraphes': paras}
    if b is not None:
        entree['base'] = True
    return entree


def _article_neuf(cle, titre, paragraphes):
    return {'cle': cle, 'v': FORME_ARTICLE,
            'titre': ecrire_gabarit([('t', titre)]),
            'paragraphes': [ecrire_gabarit([('t', p)]) for p in paragraphes]}


def _remettre_non_affichees(sortie, anciennes, affichees):
    """Les entrées déjà stockées pour un article que l'écran ne pouvait pas
    montrer (supprimé, ou personnalisé puis retiré par une option) sont
    gardées telles quelles, à leur place : la liste reçue ne les connaît
    pas, elle ne peut pas les défaire."""
    prises = {e.get('cle') for e in sortie}
    precedente = None
    for e in anciennes or []:
        if not isinstance(e, dict):
            continue
        cle = e.get('cle')
        if cle not in affichees and cle not in prises:
            pos = next((i + 1 for i, s in enumerate(sortie)
                        if s.get('cle') == precedente), 0)
            sortie.insert(pos, e)
            prises.add(cle)
        if cle in prises:
            precedente = cle
    return sortie


def compacter_articles(avant, apres, entrants, langue='fr'):
    """Forme stockée d'une liste d'articles reçue de l'écran.

    ``avant`` : l'état que l'écran AFFICHAIT (``_construire(...,
    interne=True)`` AVANT ce corps : anciennes options, anciennes dates,
    textes stockés) — chaque article reçu est comparé à CET affichage, jamais
    à une base calculée avec les options du même corps (B1). ``apres`` : le
    même acte avec les réglages communs du corps : il dit quels articles de
    base existent désormais. Une liste qui reprend au moins la moitié des
    articles affichés est COMPLÈTE (elle fixe l'ordre ; un article affiché
    et toujours dans la base qui en est absent est marqué ``retire``) ; une
    liste plus courte modifie les articles cités et ajoute les nouveaux à la
    fin. Un article inchangé garde son entrée (ou ``{cle}``) : il suit les
    options et la vente ; un article modifié est aligné (``aligner``)."""
    affiches = avant['articles']
    par_cle = {a['cle']: a for a in affiches}
    cles_aff = [a['cle'] for a in affiches]
    base_avant = {a['cle']: a for a in avant['base']}
    base_apres = {a['cle']: a for a in apres['base']}
    communes = {e['cle'] for e in entrants} & set(cles_aff)
    retires = []
    if not cles_aff or len(communes) * 2 >= len(cles_aff):
        liste = list(entrants)
        retires = [{'cle': c, 'retire': True} for c in cles_aff
                   if c not in communes and c in base_apres]
    else:
        remplaces = {e['cle']: e for e in entrants}
        liste = [remplaces.get(c) or {'cle': c, '_garder': True}
                 for c in cles_aff]
        liste += [e for e in entrants if e['cle'] not in par_cle]
    sortie = []
    for e in liste:
        cle = e['cle']
        a = par_cle.get(cle)
        if e.get('_garder'):
            sortie.append(a['entree'] or {'cle': cle})
            continue
        if 'paragraphes' not in e and 'titre' not in e:
            sortie.append(a['entree'] if a is not None and not a['de_base']
                          and a['entree'] else {'cle': cle})
            continue
        titre, paragraphes = e.get('titre') or '', list(
            e.get('paragraphes') or [])
        etat = avant
        if a is None and cle in base_apres:
            # Un article qu'une option de ce corps fait apparaître : comparé
            # à la nouvelle base, avec le nouveau contexte.
            a, etat = base_apres[cle], apres
        if a is None:
            sortie.append(_article_neuf(cle, titre, paragraphes))
            continue
        ctx, connus = etat['ctx'], etat['connus']
        if _memes(rendre_jetons(a['titre'], ctx, langue, connus), titre) \
                and _memes([rendre_jetons(p, ctx, langue, connus)
                            for p in a['paragraphes']], paragraphes):
            sortie.append(a['entree'] or {'cle': cle})
            continue
        b = (base_avant if etat is avant else base_apres).get(cle)
        sortie.append(_compacter_article(a, titre, paragraphes, b, ctx,
                                         langue, connus))
    sortie = _remettre_non_affichees(sortie, avant['entrees'], set(cles_aff))
    return sortie + [r for r in retires
                     if r['cle'] not in {s.get('cle') for s in sortie}]


def compacter_quitus(avant, saisis, langue='fr'):
    """Forme stockée du quitus renvoyé par l'écran, aligné sur le quitus
    affiché ; None quand il redevient celui de la base."""
    affiches = avant['quitus']
    ctx, connus = avant['ctx'], avant['connus']
    if _memes([rendre_jetons(j, ctx, langue, connus) for j, _s in affiches],
              list(saisis)):
        return avant['quitus_stocke']
    stocke = _compacter_paragraphes(affiches, saisis, avant['quitus_base'],
                                    ctx, langue, connus)
    if stocke == [{'defaut': j} for j in range(len(avant['quitus_base']))]:
        return None
    return stocke


def texte_litteral(sources):
    """Le texte LITTÉRAL de textes stockés (chaînes ou ``{'defaut', 'texte'}``)
    : ce que l'utilisateur a tapé ou repris, sans la valeur d'aucun repère.
    Un renvoi vers la base n'en a pas."""
    morceaux = []
    for x in sources:
        texte = x if isinstance(x, str) else (
            x.get('texte') if isinstance(x, dict) else None)
        if isinstance(texte, str):
            morceaux.append(''.join(v if s == 't' else '\n'
                                    for s, v in lire_gabarit(texte)))
    return '\n'.join(morceaux)


#: Les options booléennes qui retirent un article ou un paragraphe, toutes
#: cochées : sert à nommer un article masqué par une option.
_OPTIONS_TOUT = {'reserve_propriete': True, 'raccorde_reseau': True,
                 'penalite_retard_pct': '1'}


def _titre_masque(entree, textes, type_acte, variante, options, ctx, langue):
    titre = entree.get('titre')
    if isinstance(titre, str) or isinstance((titre or {}).get('texte'), str):
        return rendre_gabarit(titre if isinstance(titre, str)
                              else titre['texte'], ctx, langue)
    for a in textes.articles_par_defaut(type_acte, variante, ctx,
                                        {**options, **_OPTIONS_TOUT}):
        if a['cle'] == entree.get('cle'):
            return a['titre']
    return entree.get('cle') or ''


def message_masques(masques, ctx, textes, contenu, langue='fr'):
    """Les phrases d'avertissement des textes personnalisés qu'une option
    empêche d'imprimer (ils reviennent avec elle)."""
    sortie = []
    for sorte, entree in masques:
        titre = _titre_masque(entree, textes, contenu['type'],
                              contenu['variante'], contenu['options'], ctx,
                              langue)
        if sorte == 'article':
            sortie.append(
                f"L'article « {titre} », que vous avez modifié, n'est pas "
                f"imprimé : l'option qui le porte est décochée. Votre version "
                f"reviendra si vous la cochez de nouveau.")
        else:
            sortie.append(
                f"Un paragraphe que vous avez modifié dans l'article « "
                f"{titre} » n'est pas imprimé : l'option qui le porte est "
                f"décochée. Votre version reviendra si vous la cochez de "
                f"nouveau.")
    return list(dict.fromkeys(sortie))


# ── Montants figés (refus ``montant_fige`` à l'émission) ────────────────────

_MONTANT_DH = re.compile(
    rf'(?<![\w,.])(\d{{1,3}}(?:[{_SEPARATEURS}]\d{{3}})+|\d+)(?:[,.](\d{{1,2}}))?'
    rf'[{_SEPARATEURS}]*(?:DH|MAD|dirhams?|درهم)(?![A-Za-z])', re.IGNORECASE)


def montants_du_texte(texte):
    """Les montants en dirhams écrits dans un texte (Decimal au centime)."""
    sortie = []
    for m in _MONTANT_DH.finditer(str(texte or '')):
        entier = re.sub(f'[{_SEPARATEURS}]', '', m.group(1))
        sortie.append(_q(Decimal(f'{entier}.{m.group(2) or "0"}')))
    return sortie


def montants_figes(acte, lecture=None):
    """Les textes personnalisés de l'acte (articles, quitus ; français et
    arabe) IMPRIMÉS qui écrivent un montant en dirhams dans leur texte
    LITTÉRAL : ``[(nom du texte, [montants])]``, vide sinon.

    Règle du filet (revue 1, S1 ; contre-vérification M2) : avec
    l'alignement, une valeur que l'utilisateur n'a pas touchée redevient son
    repère et suit la vente ; un montant resté LITTÉRAL a donc forcément été
    tapé ou repris à la main (valeur modifiée en son milieu). Il bloque
    l'émission MÊME s'il égale un montant vivant de l'acte : deux tranches de
    même montant, ou un total réglé égal au reste, rendent cette égalité
    trompeuse — rien ne dit que le chiffre désigne la bonne valeur. Un
    montant ne s'écrit jamais à la main dans un acte : il vient de la vente
    par son repère."""
    lecture = lecture or Lecture(acte.chantier)
    sortie = []
    for langue in T.LANGUES:
        surcharges = _surcharges_texte(acte, langue)
        quitus = isinstance(surcharges.get('quitus'), list)
        if not isinstance(surcharges.get('articles'), list) and not quitus:
            continue
        contenu, _ctx, interne = _construire(acte, langue, lecture,
                                             interne=True)
        suffixe = ' (traduction arabe)' if langue == 'ar' else ''
        textes = [(f'L\'article « {rendu["titre"]} »{suffixe}',
                   [a['src_titre']] + list(a['src']))
                  for a, rendu in zip(interne['articles'], contenu['articles'])
                  if a['entree'] is not None]
        if quitus:
            textes.append((f'Le quitus{suffixe}',
                           [s for _j, s in interne.get('quitus') or []]))
        for nom, sources in textes:
            montants = montants_du_texte(texte_litteral(sources))
            if montants:
                sortie.append((nom, list(dict.fromkeys(montants))))
    return sortie


def message_montants_figes(figes):
    """La phrase du refus ``montant_fige`` (et de son avertissement) : chaque
    texte nommé, avec le montant écrit à la main."""
    morceaux = [f'{nom} cite {", ".join(C.montant(m) for m in montants)}'
                for nom, montants in figes]
    return ('; '.join(morceaux) + ', écrit à la main : un montant ne se tape '
            "pas dans un texte, il vient de la vente. Retirez-le de ce texte, "
            "ou remettez le texte par défaut, avant d'émettre.")


# ── Personnalisations ───────────────────────────────────────────────────────

def _vide(valeur):
    return valeur is None or valeur == ''


#: Dates facultatives des sections communes : vidées à l'écran, elles sont
#: effacées (jamais remplacées par la date du chantier).
_DATES_FACULTATIVES = ('date', 'date_mise_en_service')


def _appliquer_communes(contenu, surcharges):
    """Sections communes aux deux langues (dates, options, signataire,
    livraison, réception, service après-vente) — toujours réglées en
    français."""
    s = surcharges or {}
    for cle in ('lieu', 'date_document'):
        if not _vide(s.get(cle)):
            contenu[cle] = s[cle]
    # Champs facultatifs : une chaîne vide EFFACE (le défaut ne revient pas).
    if isinstance(s.get('societe'), dict) and isinstance(
            s['societe'].get('representant'), str):
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
                if k not in cles:
                    continue
                if k in _DATES_FACULTATIVES:
                    # Une date vidée (stockée None) est effacée.
                    contenu[section][k] = v or None
                elif v is not None:
                    contenu[section][k] = v
    if isinstance(s.get('delais'), dict) and not _vide(
            s['delais'].get('date_limite')):
        contenu['_date_limite_fixee'] = s['delais']['date_limite']


def _appliquer_textes(contenu, surcharges, langue, *, modele=False,
                      garanties_fr=None):
    """Sections de texte d'une langue, sauf les articles et le quitus
    (gabarits : ``_articles_et_quitus``). ``modele`` : les garanties du
    modèle s'appliquent par clé (jamais en remplaçant la liste d'une vente).
    ``garanties_fr`` (traduction arabe) : les lignes françaises de l'acte,
    dont l'arabe ne traduit que les textes."""
    s = surcharges or {}
    for cle in ('titre', 'conditions_particulieres', 'conseils_intro'):
        if cle in contenu and isinstance(s.get(cle), str):
            contenu[cle] = s[cle]
    for cle in ('constats', 'reserves', 'conseils', 'entretien'):
        if cle in contenu and isinstance(s.get(cle), list):
            contenu[cle] = copy.deepcopy(s[cle])
    if 'garanties' in contenu and langue == 'ar' and not modele and (
            isinstance(garanties_fr, list)
            or isinstance(s.get('garanties'), list)):
        contenu['garanties'] = _garanties_ar(
            contenu['garanties'],
            garanties_fr if isinstance(garanties_fr, list) else None,
            s.get('garanties'))
    elif 'garanties' in contenu and isinstance(s.get('garanties'), list):
        if modele:
            contenu['garanties'] = _fusion_garanties_modele(
                contenu['garanties'], s['garanties'],
                T.CLES_GARANTIE_TEXTE if langue == 'ar' else None)
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
    if isinstance(s.get('paiement'), dict) \
            and isinstance(contenu.get('paiement'), dict):
        # Les moyens de paiement sont une phrase de la langue : chaque
        # langue règle la sienne.
        for k in T.CLES_PAIEMENT_MODIFIABLES:
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
        except (TypeError, ValueError, OverflowError):
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


#: « ␠du 24 novembre 2026 » / « ␠المؤرَّخ في 24 نونبر 2026 » : la date du
#: contrat collée à sa référence (formes de ``textes_ar.FORMES_CTX``).
_CONTRAT_DU = {'fr': ' du {date}',
               'ar': ' المؤرَّخ '
                     'في {date}'}


def _contexte(contenu, vente, langue, refs, lecture=None):
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
        # L'adresse telle qu'elle est enregistrée, jamais traduite.
        'adresse_societe': societe.get('adresse') or None,
    }
    date_contrat = lecture.date_du_contrat() if lecture is not None else None
    ctx['contrat_du'] = (_CONTRAT_DU[langue].format(
        date=C.date_longue(date_contrat, langue=langue)) if date_contrat
        else '')
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
        ctx['total_regle_lettres'] = _lettres(paiement['total_regle'], langue)
        # Prix − total réglé : la valeur de l'encadré.
        ctx['reste_a_regler'] = _montant(paiement.get('reste_a_regler'),
                                         langue)
        if contenu['type'] == T.CLOTURE:
            ctx['ecart_regle'] = ecart_regle(vente['prix_ttc'], vente['paye'],
                                             vente.get('avoirs'), langue)
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


def _contenu_vivant(acte, langue, lecture, vente, refs):
    """Le squelette vivant d'un acte : identités, système, prix, options."""
    chantier = acte.chantier
    societe = _bloc_societe(lecture)
    client = _bloc_client(chantier)
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
        'type': acte.type, 'variante': acte.variante or '',
        'reference': refs[acte.type],
    }
    if acte.type == T.LIVRAISON:
        contenu['livraison'] = _livraison_defaut(chantier, langue)
    if acte.type == T.RECEPTION:
        contenu['reception'] = {
            'date_mise_en_service': _iso(chantier.date_mise_en_service),
            'prononcee': False, 'delai_levee_reserves': ''}
    if acte.type == T.CLOTURE:
        contenu['sav'] = {'telephone': societe['telephone'], 'whatsapp': '',
                          'email': societe['email'], 'horaires': ''}
    return contenu


def _appliquer_modeles_communs(contenu, acte, modele_contrat, modele):
    """Sections communes : modèle « contrat » (signataire des quatre actes),
    modèle du type, puis l'acte — toujours les surcharges françaises, y
    compris pour la base de comparaison des articles (une option ou une date
    de l'acte n'est jamais prise pour une correction de texte). Rend la date
    limite fixée à la main, s'il y en a une."""
    if modele_contrat is not None:
        rep = ((modele_contrat.surcharges or {}).get('societe') or {})
        if isinstance(rep, dict) and not _vide(rep.get('representant')):
            contenu['societe']['representant'] = rep['representant']
    for objet in (modele, acte):
        if objet is not None:
            _appliquer_communes(contenu, objet.surcharges)
    return contenu.pop('_date_limite_fixee', None)


def _engagement(societe, langue):
    nom = societe.get('nom_court') or societe.get('nom') or ''
    if langue == 'ar':
        return f'يُقرّ الزبون بأنه مدين بهذا المبلغ لـ {nom} برسم باقي الثمن.'
    return (f'Le Client reconnaît devoir cette somme à {nom} au titre du '
            f'solde du prix.')


def _bloc_paiement(contenu, paiement, modalites, langue, chantier):
    """La section ``paiement`` (et ``reception`` de la clôture) selon le type
    d'acte, depuis la situation calculée — aucun montant recalculé ici."""
    type_acte = contenu['type']
    p = paiement or {}
    if type_acte == T.CONTRAT:
        return {'modalites': modalites}
    if type_acte == T.CLOTURE:
        contenu['reception'] = {'date': _iso(chantier.date_reception)}
        return {k: p.get(k) for k in ('total_regle', 'pourcentage_regle',
                                      'exigible_maintenant', 'reste_a_regler')}
    bloc = {
        'total_regle': p.get('total_regle'),
        'pourcentage_regle': p.get('pourcentage_regle'),
        'exigible_maintenant': p.get('exigible_maintenant'),
        'exigible_en_lettres': _lettres(p.get('exigible_maintenant'), langue),
        'restera_ensuite': p.get('restera_ensuite'),
        'reste_a_regler': p.get('reste_a_regler'),
    }
    if type_acte == T.RECEPTION:
        bloc['engagement'] = _engagement(contenu['societe'], langue)
    bloc['modalites'] = modalites
    return bloc


def _sections_derivees(contenu, acte, lecture, vente, langue, date_fixee):
    """Échéancier et état des tranches, délais, paiement, garanties."""
    chantier = acte.chantier
    etats, paiement = situation(acte.type, acte.variante or '', vente)
    contenu['echeancier'] = _echeancier(vente, etats, langue)
    if acte.type == T.CONTRAT:
        contenu['delais'] = _delais(
            contenu['date_document'],
            contenu['options'].get('delai_execution_jours'), date_fixee,
            langue)
    contenu['paiement'] = _bloc_paiement(
        contenu, paiement, _modalites(lecture, langue), langue, chantier)
    if acte.type in (T.CONTRAT, T.CLOTURE):
        garanties = _garanties_vente(lecture, langue)
        garanties.append(_garantie_installation(chantier, contenu['societe'],
                                                langue))
        contenu['garanties'] = garanties


def _finaliser(contenu):
    """Clés stables des garanties, dates de fin (clôture), drapeaux internes
    retirés."""
    if 'garanties' in contenu:
        _completer_cles_garanties(contenu['garanties'])
        depart = ((contenu.get('reception') or {}).get('date')
                  if contenu['type'] == T.CLOTURE else None)
        _dater_garanties(contenu['garanties'], depart)
    if 'delais' in contenu:
        contenu['delais'].pop('_resume', None)
        contenu['delais'].pop('_detail', None)
    return contenu


def _articles_et_quitus(contenu, textes, ctx, langue, s_modele, s_acte):
    """Les articles (et le quitus de la clôture) : textes par défaut en
    jetons → modèle de la société → textes de l'acte, rendus avec ``ctx``.
    Rend l'état interne (jetons, sources, base) que l'alignement compare."""
    connus = frozenset(ctx) | noms_reperes()
    defaut = articles_en_jetons(textes, contenu['type'], contenu['variante'],
                                contenu['options'], ctx)
    base = _en_base(defaut)
    if isinstance(s_modele.get('articles'), list):
        base = _en_base(resoudre_articles(base, s_modele['articles']))
    entrees = s_acte.get('articles')
    entrees = entrees if isinstance(entrees, list) else None
    masques = []
    effectifs = (resoudre_articles(base, entrees, masques)
                 if entrees is not None else base)
    contenu['articles'] = [_rendre_article(a, ctx, langue, connus)
                           for a in effectifs]
    interne = {'defaut': defaut, 'base': base, 'articles': effectifs,
               'entrees': entrees or [], 'masques': masques, 'ctx': ctx,
               'connus': connus}
    if contenu['type'] == T.CLOTURE:
        q_defaut = quitus_en_jetons(textes, ctx)
        q_base = q_defaut
        if isinstance(s_modele.get('quitus'), list):
            q_base = [j for j, _s in resoudre_paragraphes(
                q_defaut, s_modele['quitus'])]
        q_stocke = s_acte.get('quitus')
        q_stocke = q_stocke if isinstance(q_stocke, list) else None
        quitus = resoudre_paragraphes(q_base, q_stocke)
        contenu['quitus'] = [rendre_jetons(j, ctx, langue, connus)
                             for j, _s in quitus]
        interne.update(quitus_defaut=q_defaut, quitus_base=q_base,
                       quitus=quitus, quitus_stocke=q_stocke)
    return interne


def _construire(acte, langue='fr', lecture=None, *, avec_modele=True,
                avec_acte_textes=True, avec_ctx=False, interne=False):
    """Le contenu d'un acte. ``avec_acte_textes=False`` : sans les textes
    personnalisés de l'acte (ses réglages communs restent appliqués) ;
    ``avec_ctx`` : rend ``(contenu, ctx)`` ; ``interne`` : rend ``(contenu,
    ctx, état des articles en jetons)``."""
    if langue not in T.LANGUES:
        raise ValueError(f'Langue inconnue : {langue!r}')
    chantier = acte.chantier
    lecture = lecture or Lecture(chantier)
    vente = lecture.vente()
    refs = {t: reference_acte(t, chantier.reference, chantier.pk)
            for t in T.TYPES}
    contenu = _contenu_vivant(acte, langue, lecture, vente, refs)
    modele_contrat = lecture.modele(T.CONTRAT) if avec_modele else None
    modele = lecture.modele(acte.type) if avec_modele else None
    date_fixee = _appliquer_modeles_communs(contenu, acte, modele_contrat,
                                            modele)
    _sections_derivees(contenu, acte, lecture, vente, langue, date_fixee)
    textes = _textes(langue)
    ctx = _textes_par_defaut(contenu, textes, vente, langue, refs, lecture)
    if modele is not None:
        if langue == 'ar' and 'garanties' in contenu:
            # Les durées du modèle sont communes : réglées en français.
            contenu['garanties'] = _fusion_garanties_modele(
                contenu['garanties'],
                (modele.surcharges or {}).get('garanties'),
                ('duree_mois', 'duree_libelle'))
        _appliquer_textes(contenu, _surcharges_texte(modele, langue), langue,
                          modele=True)
    if avec_acte_textes:
        _appliquer_textes(
            contenu, _surcharges_texte(acte, langue), langue,
            garanties_fr=((acte.surcharges or {}).get('garanties')
                          if langue == 'ar' else None))
    etat = _articles_et_quitus(
        contenu, textes, ctx, langue,
        _surcharges_texte(modele, langue) if modele is not None else {},
        _surcharges_texte(acte, langue) if avec_acte_textes else {})
    contenu = _finaliser(contenu)
    if interne:
        return contenu, ctx, etat
    return (contenu, ctx) if avec_ctx else contenu


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
        # Accord du nom compté (1, 2, 3 à 10, 11 et plus).
        detail = ('المدة المتوقعة: ' + C._compte_ar(
            int(jours), 'يوم عمل واحد', 'يوما عمل', 'أيام عمل', 'يوم عمل')
            + '.') if jours else ''
    else:
        suite = f'Pose le {C.date_longue(pose)}' if pose else 'La pose'
        detail = (f'Durée prévue : {jours} jour{"s" if jours > 1 else ""} '
                  f'ouvré{"s" if jours > 1 else ""}.' if jours else '')
    return {'date': None, 'suite': suite, 'suite_detail': detail,
            'avec_series': False}


#: Noms arabes des lignes d'écart du tableau des paiements.
_ECARTS_AR = {'_escompte_avance': 'خصم أو تسبيق موزَّع',
              '_autre_vente': 'جزء مُحتسب لبيع آخر'}


def _lignes_paiements(vente, langue):
    """Le tableau des paiements du quitus (``reglements`` : sa somme égale le
    total réglé), libellés dans la langue."""
    sortie = []
    for p in (vente or {}).get('reglements') or []:
        libelle = p['libelle']
        if langue == 'ar':
            libelle = (_ECARTS_AR.get(p.get('_key'))
                       or _LIBELLES_AR.get(p.get('_key')) or libelle)
        sortie.append({'date': p['date'], 'libelle': libelle,
                       'mode': p['mode'], 'montant': p['montant']})
    return sortie


def ecart_regle(prix, paye, avoirs, langue):
    """La phrase qui nomme ce qui a soldé le prix sans être un paiement
    (avoir, retenue à la source, abandon de créance) : '' si le payé couvre
    le prix. Repère ``{ecart_regle}`` du quitus, précédé d'une espace."""
    ecart = _q((prix or ZERO) - (paye or ZERO))
    if ecart <= 0:
        return ''
    montant = _montant(ecart, langue)
    par_avoir = (avoirs or ZERO) >= ecart
    if langue == 'ar':
        return (f' أما باقي الثمن، أي {montant}، فقد خُصم بموجب إشعار دائن.'
                if par_avoir else
                f' أما باقي الثمن، أي {montant}، فقد سُوّي بإشعار دائن أو '
                f'باقتطاع من المنبع أو بالتنازل عن الدين.')
    return (f' Le reste du prix, soit {montant}, a été déduit par avoir.'
            if par_avoir else
            f' Le reste du prix, soit {montant}, a été soldé par avoir, '
            f'retenue à la source ou abandon de créance.')


def _textes_par_defaut(contenu, textes, vente, langue, refs, lecture=None):
    """Pose les textes par défaut sans repère (constats, conseils,
    entretien, paiements) ; rend le contexte (repères) qui formate les
    articles et le quitus (``_articles_et_quitus``)."""
    type_acte = contenu['type']
    ctx = _contexte(contenu, vente, langue, refs, lecture)
    if type_acte in (T.LIVRAISON, T.RECEPTION):
        contenu['constats'] = textes.constats_par_defaut(type_acte)
        contenu['reserves'] = []
    if type_acte == T.CLOTURE:
        avec_batterie = contenu['systeme']['avec_batterie']
        contenu['paiements'] = _lignes_paiements(vente, langue)
        intro, conseils = textes.conseils_par_defaut(avec_batterie)
        contenu['conseils_intro'] = intro
        contenu['journee'] = textes.journee_solaire(avec_batterie)
        contenu['conseils'] = conseils
        contenu['entretien'] = textes.entretien_par_defaut()
    return ctx


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


#: Sections stockées en gabarit, alignées sur ce que l'écran affichait.
SECTIONS_GABARIT = ('articles', 'quitus')


def personnaliser(acte, propre, langue='fr', lecture=None):
    """Les personnalisations d'une langue après un enregistrement de
    l'écran (``propre`` : sections validées ; ``None`` remet une section au
    défaut). Lectures seulement : rend le nouveau dictionnaire, l'appelant
    l'écrit.

    Les articles et le quitus reçus sont la liste que l'écran AFFICHAIT,
    corrigée : ils sont alignés sur l'état d'AVANT ce corps (anciennes
    options, anciennes dates, textes stockés), jamais sur une base calculée
    avec les réglages du même corps (B1) ; puis les réglages du corps
    décident quels articles de base existent."""
    lecture = lecture or Lecture(acte.chantier)
    champ = 'surcharges_ar' if langue == 'ar' else 'surcharges'
    cible = dict(getattr(acte, champ) or {})
    textes = {}
    for section, valeur in propre.items():
        if valeur is None:
            cible.pop(section, None)
        elif section in SECTIONS_GABARIT:
            textes[section] = valeur
        else:
            cible[section] = valeur
    if not textes:
        return cible
    avant = _construire(acte, langue, lecture, interne=True)[2]
    suivant = copy.copy(acte)
    setattr(suivant, champ, cible)
    apres = _construire(suivant, langue, lecture, interne=True)[2]
    if 'articles' in textes:
        cible['articles'] = compacter_articles(avant, apres,
                                               textes['articles'], langue)
    if 'quitus' in textes and 'quitus' in avant:
        quitus = compacter_quitus(avant, textes['quitus'], langue)
        if quitus is None:
            cible.pop('quitus', None)
        else:
            cible['quitus'] = quitus
    return cible


def textes_pour_modele(acte, langue='fr', lecture=None):
    """Les articles et le quitus EFFECTIFS de l'acte, en entrées stockées
    relatives aux textes PAR DÉFAUT (sans modèle de la société) — la forme
    d'un modèle : ``{'articles': [...], 'quitus': [...] | None, 'titres':
    {cle: titre imprimé}}``. Les valeurs du chantier restent des repères ;
    seul le texte littéral peut citer le chantier (``texte_litteral``)."""
    contenu, _ctx, etat = _construire(acte, langue, lecture, interne=True)
    defauts = {a['cle']: a for a in etat['defaut']}
    articles = []
    for a in etat['articles']:
        d = defauts.get(a['cle'])
        if d is not None and a['titre'] == d['titre'] \
                and a['paragraphes'] == d['paragraphes']:
            articles.append({'cle': a['cle']})
            continue
        entree = {'cle': a['cle'], 'v': FORME_ARTICLE,
                  'titre': _forme_stockee(a['titre'], None,
                                          [d['titre']] if d else []),
                  'paragraphes': [_forme_stockee(
                      p, None, d['paragraphes'] if d else [])
                      for p in a['paragraphes']]}
        if d is not None:
            entree['base'] = True
        articles.append(entree)
    effectives = {a['cle'] for a in etat['articles']}
    articles += [{'cle': c, 'retire': True} for c in defauts
                 if c not in effectives]
    quitus = None
    if 'quitus' in etat:
        quitus = [_forme_stockee(j, None, etat['quitus_defaut'])
                  for j, _s in etat['quitus']]
        if quitus == [{'defaut': k}
                      for k in range(len(etat['quitus_defaut']))]:
            quitus = None
    return {'articles': articles, 'quitus': quitus,
            'titres': {a['cle']: a['titre'] for a in contenu['articles']}}


def contexte_de(acte, langue='fr', lecture=None):
    """Les repères vivants d'un acte (le ``ctx`` des textes), dans la
    langue."""
    return _construire(acte, langue, lecture, avec_ctx=True)[1]


def sections_modifiables(type_acte, langue='fr'):
    sections = T.SECTIONS_MODIFIABLES[type_acte]
    if langue == 'ar':
        return [s for s in sections if s in T.SECTIONS_TEXTE]
    return list(sections)


def articles_personnalises(acte, langue='fr'):
    """Les ``cle`` des articles dont l'acte stocke un texte propre dans la
    langue (différent du texte par défaut) : ceux que « Rétablir » peut
    remettre par défaut. Un article seulement cité (``{cle}``) ou supprimé
    n'en est pas un."""
    entrees = _surcharges_texte(acte, langue).get('articles')
    if not isinstance(entrees, list):
        return []
    return list(dict.fromkeys(
        e['cle'] for e in entrees if isinstance(e, dict) and e.get('cle')
        and not e.get('retire') and ('paragraphes' in e or 'titre' in e)))


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


def _textes_du_dict(v, cles, section):
    for k in cles:
        if v.get(k) is not None:
            _texte(v[k], section)
    return v


def _booleen(v, cle, section):
    if cle in v and v[cle] is not None:
        _exiger(isinstance(v[cle], bool),
                f'Section « {section} » : vrai ou faux attendu ({cle}).')


def _v_societe(valeur, langue):
    v = _dict_permis(valeur, 'societe', T.CLES_SOCIETE)
    return _textes_du_dict(v, T.CLES_SOCIETE, 'societe')


def _v_delais(valeur, langue):
    v = _dict_permis(valeur, 'delais', T.CLES_DELAIS if langue == 'fr'
                     else T.CLES_DELAIS_AR)
    if 'date_limite' in v:
        v['date_limite'] = _date_texte(v['date_limite'], 'delais')
    return _textes_du_dict(v, ('resume', 'detail'), 'delais')


def _v_livraison(valeur, langue):
    v = _dict_permis(valeur, 'livraison', T.CLES_LIVRAISON)
    if 'date' in v:
        v['date'] = _date_texte(v['date'], 'livraison')
    _booleen(v, 'avec_series', 'livraison')
    return _textes_du_dict(v, ('suite', 'suite_detail'), 'livraison')


def _v_reception(valeur, langue):
    v = _dict_permis(valeur, 'reception', T.CLES_RECEPTION)
    if 'date_mise_en_service' in v:
        v['date_mise_en_service'] = _date_texte(
            v['date_mise_en_service'], 'reception')
    _booleen(v, 'prononcee', 'reception')
    return _textes_du_dict(v, ('delai_levee_reserves',), 'reception')


def _v_sav(valeur, langue):
    v = _dict_permis(valeur, 'sav', T.CLES_SAV)
    return _textes_du_dict(v, T.CLES_SAV, 'sav')


def _v_paiement(valeur, langue):
    _exiger(isinstance(valeur, dict), 'Section « paiement » : objet attendu.')
    montants = [k for k in valeur if k not in T.CLES_PAIEMENT_TEXTE]
    _exiger(not montants,
            "Les montants ne se modifient pas dans un acte : corrigez "
            "l'échéancier de la vente (" + ', '.join(sorted(montants)) + ').')
    autres = [k for k in valeur if k not in T.CLES_PAIEMENT_MODIFIABLES]
    _exiger(not autres,
            'Section « paiement » : seuls les moyens de paiement '
            '(modalites) se modifient.')
    return _textes_du_dict(dict(valeur), T.CLES_PAIEMENT_MODIFIABLES,
                           'paiement')


def _v_options(valeur, langue):
    v = _dict_permis(valeur, 'options', T.CLES_OPTIONS)
    for k in ('consommateur', 'reserve_propriete', 'raccorde_reseau'):
        _booleen(v, k, 'options')
    if 'delai_execution_jours' in v:
        v['delai_execution_jours'] = _entier(v['delai_execution_jours'],
                                             'options')
    if v.get('penalite_retard_pct') is not None:
        d = _d(str(v['penalite_retard_pct']).replace(',', '.'))
        _exiger(d is not None and d.is_finite() and ZERO <= d <= 100,
                'Option « penalite_retard_pct » : pourcentage entre 0 et 100 '
                'attendu.')
        v['penalite_retard_pct'] = f'{d.normalize():f}'
    return v


def _v_echeancier_textes(valeur, langue):
    _exiger(isinstance(valeur, dict),
            'Section « echeancier_textes » : objet attendu.')
    sortie = {}
    for cle, mots in valeur.items():
        _exiger(isinstance(mots, dict),
                'Section « echeancier_textes » : objet attendu par tranche.')
        _exiger(all(k in ('exigibilite', 'note') for k in mots),
                "Les montants ne se modifient pas dans un acte : corrigez "
                "l'échéancier de la vente.")
        sortie[str(cle)] = {k: _texte(v, 'echeancier_textes')
                            for k, v in mots.items() if v is not None}
    return sortie


def _cles_perso(entrees):
    """Une entrée sans clé (ajoutée à l'écran) reçoit ``perso_<n>``."""
    n = 1
    prises = {e['cle'] for e in entrees if e['cle']}
    for e in entrees:
        if not e['cle']:
            while f'perso_{n}' in prises:
                n += 1
            e['cle'] = f'perso_{n}'
            prises.add(e['cle'])
    return entrees


def _v_articles(valeur, langue):
    _exiger(isinstance(valeur, list), 'Section « articles » : liste attendue.')
    sortie = []
    for a in valeur:
        _exiger(isinstance(a, dict),
                'Section « articles » : un objet par article attendu.')
        cle = a.get('cle')
        _exiger(cle is None or isinstance(cle, str),
                'Section « articles » : clé texte attendue.')
        entree = {'cle': cle or ''}
        if 'titre' in a or 'paragraphes' in a:
            entree['titre'] = _texte(a.get('titre') or '', 'articles')
            entree['paragraphes'] = _liste_textes(a.get('paragraphes') or [],
                                                  'articles')
        sortie.append(entree)
    return _cles_perso(sortie)


def _v_constats(valeur, langue):
    _exiger(isinstance(valeur, list), 'Section « constats » : liste attendue.')
    sortie = []
    for k in valeur:
        _exiger(isinstance(k, dict) and isinstance(k.get('texte'), str),
                'Section « constats » : {texte, cochee} attendu.')
        sortie.append({'texte': k['texte'], 'cochee': bool(k.get('cochee'))})
    return sortie


def _v_conseils(valeur, langue):
    _exiger(isinstance(valeur, list), 'Section « conseils » : liste attendue.')
    sortie = []
    for k in valeur:
        _exiger(isinstance(k, dict), 'Section « conseils » : objet attendu.')
        sortie.append({c: _texte(k.get(c) or '', 'conseils')
                       for c in T.CLES_CONSEIL})
    return sortie


def _v_garanties(valeur, langue):
    _exiger(isinstance(valeur, list), 'Section « garanties » : liste attendue.')
    if langue == 'ar':
        # La traduction ne porte que les textes d'une ligne française (même
        # clé) : durées et dates de fin reçues sont ignorées.
        sortie = []
        for g in valeur:
            _exiger(isinstance(g, dict),
                    'Section « garanties » : objet attendu.')
            _exiger(isinstance(g.get('cle'), str) and g['cle'],
                    'Section « garanties » : en arabe, chaque ligne porte la '
                    'clé de sa ligne française.')
            ligne = {'cle': g['cle']}
            for k in T.CLES_GARANTIE_TEXTE:
                if g.get(k) is not None:
                    ligne[k] = _texte(g[k], 'garanties')
            sortie.append(ligne)
        return sortie
    sortie = []
    for g in valeur:
        _exiger(isinstance(g, dict), 'Section « garanties » : objet attendu.')
        sortie.append({
            'cle': g.get('cle') if isinstance(g.get('cle'), str) else '',
            'designation': _texte(g.get('designation') or '', 'garanties'),
            'duree_mois': _entier(g.get('duree_mois'), 'garanties'),
            'duree_libelle': _texte(g.get('duree_libelle') or '', 'garanties'),
            'garant': _texte(g.get('garant') or '', 'garanties'),
            'detail': _texte(g.get('detail') or '', 'garanties'),
            'fin': _date_texte(g.get('fin'), 'garanties'),
        })
    return _cles_perso(sortie)


_VALIDATEURS = {
    'titre': lambda v, langue: _texte(v, 'titre'),
    'conditions_particulieres': lambda v, langue: _texte(
        v, 'conditions_particulieres'),
    'conseils_intro': lambda v, langue: _texte(v, 'conseils_intro'),
    'lieu': lambda v, langue: _texte(v, 'lieu'),
    'date_document': lambda v, langue: _date_texte(v, 'date_document'),
    'reserves': lambda v, langue: _liste_textes(v, 'reserves'),
    'quitus': lambda v, langue: _liste_textes(v, 'quitus'),
    'entretien': lambda v, langue: _liste_textes(v, 'entretien'),
    'societe': _v_societe, 'delais': _v_delais, 'livraison': _v_livraison,
    'reception': _v_reception, 'sav': _v_sav, 'paiement': _v_paiement,
    'options': _v_options, 'echeancier_textes': _v_echeancier_textes,
    'articles': _v_articles, 'constats': _v_constats, 'conseils': _v_conseils,
    'garanties': _v_garanties,
}


def _valider_section(type_acte, section, valeur, langue):
    validateur = _VALIDATEURS.get(section)
    if validateur is None:
        raise ContenuInvalide(f'Section inconnue : {section}.')
    return validateur(valeur, langue)


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
    montant écrit à la main, article personnalisé masqué par une option,
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
        if livraison_sans_etape(tranches):
            sortie.append(
                "Aucune étape de l'échéancier ne correspond à la commande ni "
                "à la livraison : la somme due à la livraison est la seule "
                f"première étape (« {tranches[0]['libelle']} », "
                f"{C.montant(cible)}).")
        if acte.variante == T.RESTE_A_REGLER:
            du = min(max(ZERO, cible - vente['paye']), reste_du(vente))
            if du > 0:
                sortie.append(
                    f'La tranche « {tranches[i]["libelle"]} » n\'est pas '
                    f'encore réglée : {C.montant(du)} restent à encaisser.')
        elif paiement_suppose(acte, vente):
            sortie.append(
                f"L'ERP n'a enregistré que {C.montant(vente['paye'])} de "
                f'paiements : cette version dit {C.montant(cible)} réglés. '
                f'Elle ne pourra être émise qu\'une fois ces paiements '
                f'enregistrés.')
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
    figes = montants_figes(acte, lecture)
    if figes:
        sortie.append(message_montants_figes(figes))
    if isinstance((acte.surcharges or {}).get('articles'), list):
        contenu_fr, ctx, etat = _construire(acte, 'fr', lecture, interne=True)
        sortie += message_masques(etat['masques'], ctx, _textes('fr'),
                                  contenu_fr)
    retard = [T.LIBELLES_SECTIONS[s] for s in T.SECTIONS_MODIFIABLES[acte.type]
              if s in T.SECTIONS_TEXTE and _texte_a_traduire(acte, s, lecture)
              and s not in (acte.surcharges_ar or {})]
    if retard:
        sortie.append('La traduction arabe ne reprend pas vos modifications '
                      'de : ' + ', '.join(retard) + '.')
    return sortie


def _texte_a_traduire(acte, section, lecture=None):
    """La personnalisation française de ``section`` porte-t-elle un TEXTE à
    traduire ? Une date limite (commune) ou une durée de garantie (reprise
    telle quelle en arabe) n'en est pas un."""
    valeur = (acte.surcharges or {}).get(section)
    if valeur is None:
        return False
    if section == 'delais':
        return any(isinstance(valeur, dict) and valeur.get(k)
                   for k in ('resume', 'detail'))
    if section == 'garanties':
        defauts = {g['cle']: g for g in _construire(
            acte, 'fr', lecture, avec_acte_textes=False).get('garanties')
            or []}
        return any(g.get('cle') not in defauts or any(
            (g.get(k) or '') != (defauts[g['cle']].get(k) or '')
            for k in T.CLES_GARANTIE_TEXTE) for g in valeur)
    return True


def paiement_suppose(acte, vente):
    """Variante « tranche réglée » dont les paiements ENREGISTRÉS ne couvrent
    pas la cible cumulée de la livraison : ``{cible, paye}``, sinon None.
    Le brouillon se prévisualise ; il ne s'émet pas (409
    ``paiement_non_enregistre``)."""
    if (acte.type != T.LIVRAISON or acte.variante != T.TRANCHE_REGLEE
            or not vente or not vente['tranches']):
        return None
    cible = vente['tranches'][index_livraison(vente['tranches'])]['cible']
    if vente['paye'] >= cible:
        return None
    return {'cible': cible, 'paye': vente['paye']}


def reste_du(vente):
    """Ce qui reste dû sur la vente (``solde_devis`` : prix − payé − avoirs de
    réduction), jamais négatif ; None sans vente."""
    if not vente:
        return None
    return max(ZERO, vente['reste'])
