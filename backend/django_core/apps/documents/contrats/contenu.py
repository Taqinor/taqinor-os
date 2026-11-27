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
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from . import types as T
# Les textes personnalisés (gabarits, alignement, validation) vivent dans
# ``gabarits`` : services, sélecteurs et tests les importent de là.
from .gabarits import (
    A_PRECISER, FORME_ARTICLE, ZERO, _SEPARATEURS, _d, _date, _en_base,
    _forme_stockee, _rendre_article, articles_en_jetons, compacter_articles,
    compacter_quitus, message_masques, noms_reperes, quitus_en_jetons,
    rendre_jetons, resoudre_articles, resoudre_paragraphes, texte_litteral,
)
from .rendu import composants as C

logger = logging.getLogger(__name__)

CENTIME = Decimal('0.01')
SCHEMA = 1


# ── Outils ──────────────────────────────────────────────────────────────────

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
            return CompanyProfile.lire(company=self.chantier.company)
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

    def _acte(self, type_acte):
        """L'acte ``type_acte`` (non annulé) du chantier, ou None."""
        def lire():
            from ..models import ActeContractuel
            return (ActeContractuel.objects
                    .filter(company=self.chantier.company_id,
                            chantier=self.chantier.pk, type=type_acte)
                    .exclude(statut=T.ANNULE).order_by('pk').first())
        return self._une_fois(('acte', type_acte), lire)

    def statut_du_contrat(self):
        """Le statut du CONTRAT du chantier (non annulé), ou None sans
        contrat : tant qu'il est un brouillon, une durée de garantie saisie
        sur la clôture lui est portée ; émis ou signé, elle ne change plus."""
        acte = self._acte(T.CONTRAT)
        return acte.statut if acte is not None else None

    def garanties_du_contrat(self, langue):
        """Les garanties du CONTRAT du chantier dans la langue — lignes,
        durées, dates : son contenu figé s'il est émis ou signé, sinon son
        brouillon ; None sans contrat. Une seule garantie par chantier : la
        clôture les reprend telles quelles."""
        def lire():
            acte = self._acte(T.CONTRAT)
            if acte is None:
                return None
            if acte.statut in (T.EMIS, T.SIGNE):
                fige = acte.contenu_ar if langue == 'ar' else acte.contenu
                if fige and isinstance(fige.get('garanties'), list):
                    return fige['garanties']
            return self._contrat_vivant(acte, langue).get('garanties')
        return self._une_fois(('garanties_contrat', langue), lire)

    def _contrat_vivant(self, acte, langue):
        return self._une_fois(('contrat_vivant', langue),
                              lambda: _construire(acte, langue, self))

    def reserve_du_contrat(self):
        """La réserve de propriété du CONTRAT du chantier — son contenu figé
        s'il est émis ou signé, sinon son brouillon ; None sans contrat. Une
        seule par chantier : livraison, réception et clôture la reprennent,
        comme les garanties."""
        def lire():
            acte = self._acte(T.CONTRAT)
            if acte is None:
                return None
            options = ((acte.contenu or {}).get('options')
                       if acte.statut in (T.EMIS, T.SIGNE) else None)
            if not isinstance(options, dict) \
                    or 'reserve_propriete' not in options:
                options = self._contrat_vivant(acte, 'fr')['options']
            return options.get('reserve_propriete') is not False
        return self._une_fois('reserve_contrat', lire)

    def date_reception_signee(self):
        """Le jour où le procès-verbal de réception a été SIGNÉ, ou None."""
        def lire():
            acte = self._acte(T.RECEPTION)
            if acte is None or acte.statut != T.SIGNE:
                return None
            client = ((acte.contenu or {}).get('signatures') or {}).get(
                'client') or {}
            return _date(client.get('signe_le')) or (
                timezone.localtime(acte.signe_le).date()
                if acte.signe_le else None)
        return self._une_fois('reception_signee', lire)

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
        tranches = tranches_convenues(plan['tranches'],
                                      plan['prix_convenu_ttc'])
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


def tranches_convenues(tranches_plan, prix):
    """L'échéancier CONVENU d'une vente, tel qu'un acte l'imprime, calculé
    sur l'échéancier FIGÉ du devis (``unite``/``valeur`` de chaque tranche du
    plan) appliqué au prix convenu : une tranche en % vaut prix × % (au
    centime, demi supérieur), une tranche en MAD vaut son montant, la
    DERNIÈRE prend le reste du prix au centime — la somme égale donc toujours
    le prix. Le pourcentage est montant ÷ prix ; ``cible`` = cumul des
    montants convenus. Jamais ``montant_ttc`` (ce qu'il RESTE à facturer :
    une facture d'acompte de 33 024 DH pour 33 120 DH convenus laissait
    « Acompte 96,00 DH · 0,1 % » dans tous les actes) ni ``cible_cumul_ttc``
    (le TTC déjà facturé s'y substitue au convenu : une facture d'acompte
    d'un autre montant ou un acompte réglé déplaçait toutes les tranches)."""
    from apps.ventes.utils.echeancier import UNITE_MONTANT
    prix = max(ZERO, _q(prix or ZERO))
    sortie, cumul = [], ZERO
    for i, t in enumerate(tranches_plan):
        reste = prix - cumul
        if i == len(tranches_plan) - 1:
            montant = reste
        else:
            valeur = _d(t.get('valeur')) or ZERO
            montant = min(reste, _q(
                valeur if t.get('unite') == UNITE_MONTANT
                else prix * valeur / 100))
            montant = max(ZERO, montant)
        cumul += montant
        sortie.append({
            'cle': t['cle'], 'key': t['key'], 'libelle': t['libelle'],
            'montant': montant, 'cible': cumul,
            'pourcentage': _q(montant / prix * 100) if prix > 0 else ZERO,
        })
    return sortie


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
    if entreprise:
        # Client société (fondateur, 24/11/2026) : « le Client » est la
        # RAISON SOCIALE, jamais une personne. Le gérant ou le responsable
        # (« nom, qualité ») ne sert qu'à signer : ``representant``.
        nom = base.get('nom') or ''
        representant = ', '.join(x.strip() for x in (
            getattr(client, 'contact_nom', '') or '',
            getattr(client, 'contact_fonction', '') or '') if x.strip())
    else:
        nom = ' '.join(x for x in (base.get('prenom'), base.get('nom')) if x)
        representant = ''
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
        'representant': representant,
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
    if 'garanties' in contenu and contenu.get('_garanties_du_contrat'):
        # Lignes, durées et dates venues du CONTRAT (une garantie par
        # chantier) : l'acte n'en reprend que ses textes, par clé.
        if isinstance(s.get('garanties'), list):
            contenu['garanties'] = _fusion_garanties_modele(
                contenu['garanties'], s['garanties'], T.CLES_GARANTIE_TEXTE)
    elif 'garanties' in contenu and langue == 'ar' and not modele and (
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


def _faits_du_francais(contenu, fr, ar):
    """La traduction arabe n'omet aucun fait saisi en français (recette
    C4) : les cases cochées des constats sont communes (lues en français) ;
    un texte libre tapé en français sans équivalent arabe (réserves,
    conditions particulières, constat ajouté) s'imprime TEL QUEL dans le
    document arabe — un fait en français vaut mieux qu'un fait absent ;
    l'avertissement « traduction arabe » demande toujours sa traduction."""
    if 'constats' in contenu and isinstance(fr.get('constats'), list):
        arabes = contenu['constats']
        if isinstance(ar.get('constats'), list):
            # Traduits à la main : les cases du français, ligne à ligne.
            sortie = [dict(k, cochee=bool(f.get('cochee')))
                      for k, f in zip(arabes, fr['constats'])]
            sortie += [{'texte': f.get('texte') or '',
                        'cochee': bool(f.get('cochee'))}
                       for f in fr['constats'][len(arabes):]]
        else:
            from . import textes
            defauts = [k['texte'] for k in
                       textes.constats_par_defaut(contenu['type'])]
            sortie = []
            for f in fr['constats']:
                j = (defauts.index(f.get('texte'))
                     if f.get('texte') in defauts else None)
                texte = (arabes[j]['texte'] if j is not None
                         and j < len(arabes) else f.get('texte') or '')
                sortie.append({'texte': texte,
                               'cochee': bool(f.get('cochee'))})
        contenu['constats'] = sortie
    for cle in ('reserves', 'conditions_particulieres'):
        if cle in contenu and cle not in ar and fr.get(cle):
            contenu[cle] = copy.deepcopy(fr[cle])


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
        'penalite_retard_pct': None,
        'delai_execution_jours': T.DELAI_EXECUTION_DEFAUT_JOURS,
    }


_TEXTES_FIXES = {
    'fr': {'demeure': 'huit jours', 'reponse': 'quinze jours'},
    # Formes de ``textes_ar.FORMES_CTX``.
    'ar': {'demeure': '8 أيام', 'reponse': '15 يومًا'},
}


#: « ␠du 24 novembre 2026 » / « ␠المؤرَّخ في 24 نونبر 2026 » : la date du
#: contrat collée à sa référence (formes de ``textes_ar.FORMES_CTX``).
_CONTRAT_DU = {'fr': ' du {date}',
               'ar': ' المؤرَّخ '
                     'في {date}'}


def _client_nomme(client):
    """Le client tel qu'une phrase le nomme (quitus du dernier acte) : une
    société y porte son ICE — « K and L building (ICE 001234567000089) » —
    pour que les quatre actes l'identifient (fondateur, 24/11/2026)."""
    nom = client.get('nom_complet') or ''
    if nom and client.get('type') == 'entreprise' and client.get('ice'):
        return f"{nom} (ICE {client['ice']})"
    return nom


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
        'client': _client_nomme(contenu['client']) or None,
        'devis_reference': chantier.get('devis_reference') or None,
        'contrat_reference': refs[T.CONTRAT],
        'email_societe': societe.get('email') or None,
        'cndp': '',
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
                                             vente.get('avoirs'), langue,
                                             reste=vente.get('reste'))
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


def _bloc_paiement(contenu, paiement, modalites, langue, chantier,
                   date_reception=None):
    """La section ``paiement`` (et ``reception`` de la clôture) selon le type
    d'acte, depuis la situation calculée — aucun montant recalculé ici."""
    type_acte = contenu['type']
    p = paiement or {}
    if type_acte == T.CONTRAT:
        return {'modalites': modalites}
    if type_acte == T.CLOTURE:
        # Départ des garanties : le jour où le procès-verbal de réception a
        # été SIGNÉ, à défaut la date de réception du chantier.
        contenu['reception'] = {'date': _iso(
            date_reception or chantier.date_reception)}
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
        contenu, paiement, _modalites(lecture, langue), langue, chantier,
        lecture.date_reception_signee() if acte.type == T.CLOTURE else None)
    du_contrat = (lecture.garanties_du_contrat(langue)
                  if acte.type == T.CLOTURE else None)
    if isinstance(du_contrat, list):
        # Une garantie par chantier : celle du CONTRAT (figé s'il est émis
        # ou signé, sinon son brouillon) — jamais une seconde lecture qui
        # dirait « 2 ans » quand le contrat signé dit 36 mois.
        contenu['garanties'] = [{k: g.get(k) for k in T.CLES_GARANTIE}
                                for g in copy.deepcopy(du_contrat)]
        contenu['_garanties_du_contrat'] = True
    elif acte.type in (T.CONTRAT, T.CLOTURE):
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
    contenu.pop('_garanties_du_contrat', None)
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
        q_defaut = quitus_en_jetons(textes, ctx, contenu['options'])
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
    if acte.type != T.CONTRAT:
        # Une réserve de propriété par chantier : celle du CONTRAT (servie
        # ici en lecture ; l'acte ne la règle plus — recette finale, S2).
        contenu['options']['reserve_propriete'] = (
            lecture.reserve_du_contrat() is not False)
    _sections_derivees(contenu, acte, lecture, vente, langue, date_fixee)
    textes = _textes(langue)
    _textes_par_defaut(contenu, textes, vente, langue)
    if modele is not None:
        if langue == 'ar' and 'garanties' in contenu \
                and not contenu.get('_garanties_du_contrat'):
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
    if langue == 'ar' and avec_acte_textes:
        _faits_du_francais(contenu, acte.surcharges or {},
                           acte.surcharges_ar or {})
    # Le contexte APRÈS les personnalisations de l'acte : {modalites_paiement}
    # et {garantie_installation} disent ce que disent l'encadré et le
    # tableau du même document (M4).
    ctx = _contexte(contenu, vente, langue, refs, lecture)
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


def ecart_regle(prix, paye, avoirs, langue, reste=None):
    """La phrase qui nomme ce qui a soldé le prix sans être un paiement
    (avoir, retenue à la source, abandon de créance) : '' si le payé couvre
    le prix. Repère ``{ecart_regle}`` du quitus, précédé d'une espace.
    ``reste`` (``solde_devis['restant']``) : tant que la vente doit encore
    quelque chose, rien n'a « soldé » l'écart — '' (jamais une somme impayée
    présentée comme réglée par avoir ou abandon)."""
    if reste is not None and _q(reste) > 0:
        return ''
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


def _textes_par_defaut(contenu, textes, vente, langue):
    """Pose les textes par défaut sans repère (constats, conseils,
    entretien, paiements), avant les personnalisations qui les
    remplacent."""
    type_acte = contenu['type']
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


# ── API publique du module ──────────────────────────────────────────────────

def construire_contenu(acte, langue='fr', lecture=None):
    """Le contenu VIVANT d'un acte (lectures seulement). ``brouillon`` vaut
    False : c'est ce contenu que l'émission fige."""
    contenu = _construire(acte, langue, lecture)
    contenu['brouillon'] = False
    return contenu


def contenu_de(acte, langue='fr', lecture=None):
    """Le contenu servi : figé dès l'émission, vivant pour un brouillon —
    marqué ``brouillon: True`` (le PDF d'un brouillon porte « PROJET —
    document non émis » sur chaque page ; un acte émis ou signé jamais)."""
    if acte.statut != T.BROUILLON:
        fige = acte.contenu_ar if langue == 'ar' else acte.contenu
        if fige:
            return fige
    contenu = construire_contenu(acte, langue, lecture)
    contenu['brouillon'] = acte.statut not in (T.EMIS, T.SIGNE)
    return contenu


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


def origine_des_garanties(acte, lecture=None):
    """D'où viennent les lignes et les durées de garantie d'un acte (détail
    servi : ``garanties_du_contrat``) : ``''`` — l'acte règle les siennes (le
    contrat, ou une clôture sans contrat) ; sinon le statut du CONTRAT dont la
    clôture les reprend — ``brouillon`` (une durée saisie sur la clôture lui
    est portée), ``emis`` ou ``signe`` (lecture seule : elles ne se règlent
    plus que sur le contrat rouvert, jamais sur un contrat signé)."""
    if acte.type != T.CLOTURE:
        return ''
    lecture = lecture or Lecture(acte.chantier)
    return lecture.statut_du_contrat() or ''


def _faits_de_garanties(garanties):
    return [(g.get('cle'), g.get('duree_mois') or None,
             g.get('duree_libelle') or '') for g in garanties]


def garanties_portees_au_contrat(contrat, lignes, lecture=None):
    """Les garanties ENREGISTRÉES sur la clôture pendant que le contrat est
    encore un brouillon : la liste à stocker sur le CONTRAT (une garantie par
    chantier — sans cela la durée tapée sur la clôture était enregistrée puis
    ignorée, et l'écran réaffichait l'ancienne). None quand lignes et durées
    sont déjà celles du contrat. Les textes du contrat restent les siens (ceux
    de la clôture s'appliquent par clé, sur la clôture) ; une ligne ajoutée
    arrive avec ses textes ; une ligne retirée l'est pour tout le chantier."""
    actuelles = _construire(contrat, 'fr', lecture).get('garanties') or []
    if _faits_de_garanties(actuelles) == _faits_de_garanties(lignes):
        return None
    par_cle = {g.get('cle'): g for g in actuelles}
    sortie = []
    for g in lignes:
        base = par_cle.get(g.get('cle'))
        ligne = {k: (base if base is not None
                     and k in T.CLES_GARANTIE_TEXTE else g).get(k)
                 for k in T.CLES_GARANTIE}
        # La date de fin se calcule sur la clôture (jour de la réception).
        ligne['fin'] = None
        sortie.append(ligne)
    return sortie


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
    return sortie + _avertissements_arabe(acte, lecture)


#: Textes libres qu'un acte arabe imprime TELS QUE TAPÉS en français tant
#: qu'ils ne sont pas traduits (``_faits_du_francais``).
_IMPRIMES_EN_FRANCAIS = {'reserves': 'réserves',
                         'conditions_particulieres': 'conditions particulières',
                         'constats': 'constats ajoutés'}


def _avertissements_arabe(acte, lecture):
    """Ce que l'acte arabe imprime autrement que le français personnalisé :
    les textes libres tapés en français sans version arabe (imprimés en
    français), puis les sections dont l'arabe reste au texte par défaut.
    Une case cochée n'est jamais signalée : elle est commune aux deux."""
    fr, ar = acte.surcharges or {}, acte.surcharges_ar or {}
    en_francais, par_defaut = [], []
    for s in T.SECTIONS_MODIFIABLES[acte.type]:
        if s not in T.SECTIONS_TEXTE or s in ar:
            continue
        if s in _IMPRIMES_EN_FRANCAIS:
            if _texte_libre_francais(acte, s, fr.get(s)):
                en_francais.append(_IMPRIMES_EN_FRANCAIS[s])
        elif _texte_a_traduire(acte, s, lecture):
            par_defaut.append(T.LIBELLES_SECTIONS[s])
    sortie = []
    if en_francais:
        sortie.append("Dans l'acte arabe, ces textes s'impriment en "
                      'français : ' + ', '.join(en_francais) + '. '
                      "Traduisez-les si le client lit l'arabe.")
    if par_defaut:
        sortie.append('La traduction arabe ne reprend pas vos modifications '
                      'de : ' + ', '.join(par_defaut) + '.')
    return sortie


def _texte_libre_francais(acte, section, valeur):
    """La section porte-t-elle un texte tapé en français (une réserve, des
    conditions, un constat ajouté ou réécrit) ? Les constats par défaut,
    cochés ou non, ont leur traduction."""
    if section == 'constats':
        from . import textes
        defauts = {k['texte'] for k in textes.constats_par_defaut(acte.type)}
        return any((k.get('texte') or '').strip()
                   and k.get('texte') not in defauts
                   for k in valeur or [] if isinstance(k, dict))
    if isinstance(valeur, list):
        return any(isinstance(x, str) and x.strip() for x in valeur)
    return isinstance(valeur, str) and bool(valeur.strip())


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
