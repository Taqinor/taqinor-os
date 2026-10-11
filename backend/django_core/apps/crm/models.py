import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower  # noqa: F401 — façade crm.models (golden SPL70)

from core.models import SoftDeleteModel, TenantModel

from .stages import STAGE_CHOICES, NEW


def valider_mois_irrigation(valeur):
    """AGR400 — ``Lead.mois_irrigation`` : liste d'entiers 1-12 DISTINCTS.

    Vide (None ou liste vide) = question pas encore posée. Toute autre forme
    est refusée avec un message qui nomme les mois.
    """
    from django.core.exceptions import ValidationError
    if valeur in (None, []):
        return
    message = ("« Mois d'irrigation » : une liste de mois distincts, "
               'chacun entre 1 et 12.')
    if not isinstance(valeur, list):
        raise ValidationError(message)
    for mois in valeur:
        if isinstance(mois, bool) or not isinstance(mois, int) \
                or not 1 <= mois <= 12:
            raise ValidationError(message)
    if len(set(valeur)) != len(valeur):
        raise ValidationError(message)


def _valider_entiers_distincts(valeur, borne_max, message):
    from django.core.exceptions import ValidationError
    if valeur in (None, []):
        return
    if not isinstance(valeur, list):
        raise ValidationError(message)
    for x in valeur:
        if isinstance(x, bool) or not isinstance(x, int) \
                or not 1 <= x <= borne_max:
            raise ValidationError(message)
    if len(set(valeur)) != len(valeur):
        raise ValidationError(message)


def valider_jours_ouverture(valeur):
    """CIQ401 — ``Lead.jours_ouverture`` : entiers 1 (lundi) à 7 (dimanche),
    distincts. Vide = question pas encore posée."""
    _valider_entiers_distincts(
        valeur, 7, "« Jours d'ouverture » : une liste de jours distincts, "
        'chacun entre 1 (lundi) et 7 (dimanche).')


def valider_fermeture_mois(valeur):
    """CIQ401 — ``Lead.fermeture_mois`` : entiers 1-12 distincts."""
    _valider_entiers_distincts(
        valeur, 12, '« Mois de fermeture » : une liste de mois distincts, '
        'chacun entre 1 et 12.')


def valider_cos_phi(valeur):
    """CIQ401 — un cos φ est dans ]0 ; 1] (jamais supposé : vide sinon)."""
    from django.core.exceptions import ValidationError
    if valeur is None:
        return
    if not 0 < valeur <= 1:
        raise ValidationError(
            '« Cos φ » : une valeur strictement positive, au plus 1.')


#: CIQ401 (contrat CIQ1 ``lead_pro.json``) — vocabulaire de la provenance
#: d'un relevé mensuel de consommation.
RELEVE_CONSO_SOURCES = ('declare', 'lu_sur_facture', 'ocr_confirme')
#: Clés d'un mois du relevé (toutes facultatives sauf ``mois`` et ``kwh``).
RELEVE_CONSO_CLES_MOIS = (
    'mois', 'kwh', 'kwh_pointe', 'kwh_pleines', 'kwh_creuses',
    'puissance_atteinte_kva', 'cos_phi')


def valider_releve_conso(valeur):
    """CIQ401 — ``Lead.releve_conso`` = {mois: [{mois 'AAAA-MM', kwh ≥ 0,
    registres MT facultatifs ≥ 0, cos_phi facultatif}], source}.

    Au plus 12 mois DISTINCTS (les 12 factures ne sont jamais exigées,
    W5-VB-07 : un seul mois est une réponse valable).
    """
    import re
    from decimal import Decimal, InvalidOperation
    from django.core.exceptions import ValidationError
    if valeur is None:
        return
    message = ('« Relevé de consommation » : au plus 12 mois distincts '
               '(AAAA-MM), chacun avec des kWh positifs ou nuls.')
    if not isinstance(valeur, dict):
        raise ValidationError(message)
    if set(valeur) - {'mois', 'source'}:
        raise ValidationError(message)
    source = valeur.get('source')
    if source is not None and source not in RELEVE_CONSO_SOURCES:
        raise ValidationError(message)
    mois = valeur.get('mois')
    if not isinstance(mois, list) or len(mois) > 12:
        raise ValidationError(message)
    vus = set()
    for ligne in mois:
        if not isinstance(ligne, dict) or set(ligne) - set(
                RELEVE_CONSO_CLES_MOIS):
            raise ValidationError(message)
        cle = ligne.get('mois')
        if not isinstance(cle, str) or not re.fullmatch(
                r'\d{4}-(0[1-9]|1[0-2])', cle) or cle in vus:
            raise ValidationError(message)
        vus.add(cle)
        for champ in RELEVE_CONSO_CLES_MOIS[1:]:
            brut = ligne.get(champ)
            if brut is None:
                if champ == 'kwh':
                    raise ValidationError(message)
                continue
            if isinstance(brut, bool):
                raise ValidationError(message)
            try:
                nombre = Decimal(str(brut))
            except (InvalidOperation, ValueError):
                raise ValidationError(message)
            if not nombre.is_finite() or nombre < 0:
                raise ValidationError(message)
            if champ == 'cos_phi' and not 0 < nombre <= 1:
                raise ValidationError(message)


def normaliser_releve_conso(valeur):
    """Forme servie du relevé : décimaux en texte à 2 décimales (comme un
    ``DecimalField``), ``source`` = ``declare`` si absente. Idempotente : un
    GET renvoyé tel quel donne le même objet."""
    from decimal import Decimal
    if valeur is None:
        return None
    lignes = []
    for ligne in valeur.get('mois') or []:
        propre = {'mois': ligne['mois']}
        for champ in RELEVE_CONSO_CLES_MOIS[1:]:
            brut = ligne.get(champ)
            propre[champ] = (None if brut is None else str(
                Decimal(str(brut)).quantize(Decimal('0.01'))))
        lignes.append(propre)
    lignes.sort(key=lambda ligne: ligne['mois'])
    return {'mois': lignes, 'source': valeur.get('source') or 'declare'}


#: CIQ402 (contrat CIQ8 ``client_entreprise.json``, D-CIQ-11) — ce que chaque
#: étape EXIGE d'une entreprise : rien ne bloque un devis ; l'acceptation en
#: ligne exige la raison sociale et l'ICE ; la facture exige l'ICE.
IDENTITE_ENTREPRISE_REQUIS_POUR = {
    'devis': [],
    'acceptation_en_ligne': ['raison_sociale', 'ice'],
    'facture': ['ice'],
}


def identite_entreprise(*, entreprise, raison_sociale, raison_a_confirmer,
                        ice, rc, if_fiscal, adresse_siege, adresse):
    """CIQ402 — le bloc ``identite_entreprise`` (contrat CIQ8), pur.

    Particulier : forme « complète » sans exigence (règle du contrat). Pour
    une entreprise, ``manquants`` suit l'ordre raison_sociale, ice, rc,
    if_fiscal, adresse_siege — le siège ne manque que si AUCUNE adresse
    n'existe (le document retombe sur l'adresse du site).
    """
    def _vide(valeur):
        return valeur is None or not str(valeur).strip()

    if not entreprise:
        return {
            'type_client': 'particulier', 'complete': True, 'manquants': [],
            'requis_pour': {cle: [] for cle in
                            IDENTITE_ENTREPRISE_REQUIS_POUR},
        }
    manquants = []
    if raison_a_confirmer or _vide(raison_sociale):
        manquants.append('raison_sociale')
    for cle, valeur in (('ice', ice), ('rc', rc), ('if_fiscal', if_fiscal)):
        if _vide(valeur):
            manquants.append(cle)
    if _vide(adresse_siege) and _vide(adresse):
        manquants.append('adresse_siege')
    return {
        'type_client': 'entreprise',
        'complete': not manquants,
        'manquants': manquants,
        'requis_pour': {cle: list(v) for cle, v in
                        IDENTITE_ENTREPRISE_REQUIS_POUR.items()},
    }


def valider_facture_tranche_declaree(valeur):
    """CIQ401 / D-CIQ-19 — {min_mad, max_mad (null = tranche OUVERTE),
    libelle, source}. Une tranche n'est jamais un montant."""
    from decimal import Decimal, InvalidOperation
    from django.core.exceptions import ValidationError
    if valeur is None:
        return
    message = ('« Tranche de facture déclarée » : {min_mad, max_mad (vide '
               'si la tranche est ouverte), libelle, source}.')
    if not isinstance(valeur, dict) or set(valeur) - {
            'min_mad', 'max_mad', 'libelle', 'source'}:
        raise ValidationError(message)
    bornes = []
    for champ in ('min_mad', 'max_mad'):
        brut = valeur.get(champ)
        if brut is None:
            if champ == 'min_mad':
                raise ValidationError(message)
            bornes.append(None)
            continue
        if isinstance(brut, bool):
            raise ValidationError(message)
        try:
            nombre = Decimal(str(brut))
        except (InvalidOperation, ValueError):
            raise ValidationError(message)
        if not nombre.is_finite() or nombre < 0:
            raise ValidationError(message)
        bornes.append(nombre)
    if bornes[1] is not None and bornes[1] < bornes[0]:
        raise ValidationError(message)
    if valeur.get('source') not in (None, 'meta', 'site_web', 'declare'):
        raise ValidationError(message)


# SPL92 — ``Client`` vit dans ``models_clients.py`` (ré-exporté par le bloc du
# bas). Les corps de ``Lead`` et ``SiteProfile`` le désignent au CHARGEMENT
# (``ForeignKey(Client, …)``) : ce nom vaut ici la référence paresseuse
# ``'crm.Client'`` (deconstruct identique : ``to='crm.client'``), puis le
# ré-export le rebinde à la classe — corps de Lead/SiteProfile inchangés.
Client = 'crm.Client'


class Lead(SoftDeleteModel):
    """A sales lead / opportunity — distinct from a Client (customer) record.

    Leads carry a pipeline stage (canonical from STAGES.py) and a source/origin
    so imported test leads are distinguishable from leads created natively in the
    OS. Pipeline stage lives HERE, never on the Client/contact table.

    VX96 — ``Lead`` est le PREMIER adoptant du soft-delete partagé
    (``core.SoftDeleteModel``, FG388). La suppression n'est plus définitive :
    ``LeadViewSet.destroy()`` appelle ``lead.soft_delete(user)``, qui masque le
    lead des querysets par défaut (``Lead.objects`` = vivants) et journalise une
    entrée de corbeille (``DeletionRecord``) restaurable pendant 30 min via le
    ``TrashViewSet`` (``/core/corbeille/``). ``Lead.all_objects`` atteint aussi
    les supprimés. (On ne construit AUCUN écran corbeille ici — NTUX7.)
    """

    class Source(models.TextChoices):
        OS_NATIVE = 'os_native', 'Créé dans TAQINOR'
        # CRX35 — la VALEUR en base reste 'odoo_import_test' (des milliers de
        # lignes la portent, un renommage serait une migration de données pour
        # rien) ; seul le LIBELLÉ est corrigé : la synchronisation Odoo→ERP
        # n'est plus un test depuis le 01/09/2026, elle est le miroir de
        # production. « test » induisait en erreur dans les filtres et exports.
        ODOO_IMPORT_TEST = 'odoo_import_test', 'Import Odoo'
        SITE_WEB = 'site_web', 'Site web'
        # XMKT32 — lead créé depuis un formulaire Meta Lead Ads (Facebook/
        # Instagram), via l'API officielle (jamais de scraping).
        META_LEAD_ADS = 'meta_lead_ads', 'Meta Lead Ads'

    # Tranches de facture du diagnostic du site public — les CLÉS sont
    # strictement identiques aux ids émis par taqinor.ma (billRange.ts).
    class BillRangeBucket(models.TextChoices):
        LT800 = 'lt800', 'Moins de 800 MAD'
        B800_1000 = '800-1000', '800 – 1 000 MAD'
        B1000_1500 = '1000-1500', '1 000 – 1 500 MAD'
        B1500_3000 = '1500-3000', '1 500 – 3 000 MAD'
        B3000_5000 = '3000-5000', '3 000 – 5 000 MAD'
        B5000_10000 = '5000-10000', '5 000 – 10 000 MAD'
        GT10000 = 'gt10000', 'Plus de 10 000 MAD'

    # Canal marketing d'origine (différent de `source`, qui marque la
    # provenance technique de la donnée : natif vs import).
    class Canal(models.TextChoices):
        META_ADS = 'meta_ads', 'Publicité Meta'
        WHATSAPP_CTWA = 'whatsapp_ctwa', 'WhatsApp/CTWA'
        SITE_WEB = 'site_web', 'Site web'
        # Lead du site arrivé par une annonce Google (gclid/gbraid/wbraid ou
        # utm_source google) — classé par le webhook du site, jamais saisi.
        GOOGLE_ADS = 'google_ads', 'Google Ads'
        REFERENCE = 'reference', 'Référence'
        TELEPHONE = 'telephone', 'Téléphone'
        WALK_IN = 'walk_in', 'Visite/Walk-in'
        AUTRE = 'autre', 'Autre'

    class Priorite(models.TextChoices):
        BASSE = 'basse', 'Basse'
        NORMALE = 'normale', 'Normale'
        HAUTE = 'haute', 'Haute'

    class TypeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        COMMERCIAL = 'commercial', 'Commercial'
        INDUSTRIEL = 'industriel', 'Industriel'
        AGRICOLE = 'agricole', 'Agricole'

    class Raccordement(models.TextChoices):
        MONOPHASE = 'monophase', 'Monophasé'
        TRIPHASE = 'triphase', 'Triphasé'
        # Additif (toiture-3D intake) : le prospect ne connaît pas toujours son
        # type de raccordement — choix tolérant qui ne fausse pas l'existant.
        INCONNU = 'inconnu', 'Je ne sais pas'
        # QJR-OFFGRID (fondateur 01/09/2026) — SITE ISOLÉ : il n'y a AUCUN
        # raccordement ONEE à déclarer. Deux conséquences, et deux seulement :
        # le filtre de phase reste INERTE (``compatibilites.normaliser_phase``
        # rend ``None`` sur toute valeur autre que mono/tri — comme
        # « inconnu »), et la composition part en mode HORS RÉSEAU (onduleur
        # autonome + batterie obligatoire) au lieu de coter un onduleur
        # réseau que ce client ne pourra jamais raccorder.
        AUCUN = 'aucun', 'Non raccordé (site isolé)'

    class TypeToiture(models.TextChoices):
        TERRASSE_BETON = 'terrasse_beton', 'Terrasse béton'
        TOLE_METAL = 'tole_metal', 'Tôle/Métal'
        TUILES = 'tuiles', 'Tuiles'
        BAC_ACIER = 'bac_acier', 'Bac acier'
        FIBROCIMENT = 'fibrociment', 'Fibrociment'
        AUTRE = 'autre', 'Autre'

    class Orientation(models.TextChoices):
        SUD = 'sud', 'Sud'
        SUD_EST = 'sud_est', 'Sud-Est'
        SUD_OUEST = 'sud_ouest', 'Sud-Ouest'
        EST = 'est', 'Est'
        OUEST = 'ouest', 'Ouest'
        AUTRE = 'autre', 'Autre'

    class Ombrage(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        PARTIEL = 'partiel', 'Partiel'
        IMPORTANT = 'important', 'Important'

    class StructurePref(models.TextChoices):
        ACIER = 'acier', 'Acier'
        ALUMINIUM = 'aluminium', 'Aluminium'

    class BatterieSouhaitee(models.TextChoices):
        SANS = 'sans', 'Sans batterie'
        AVEC = 'avec', 'Avec batterie'
        LES_DEUX = 'les_deux', 'Les deux options'

    # QW2 — Mode PROFESSIONNEL du site (WJ68) : type de site + nombre de sites.
    # Vocabulaire identique à `apps/web/src/lib/lead.ts` (FACILITY_TYPES /
    # SITE_COUNTS) — additifs, optionnels, jamais redemandés au commercial.
    class FacilityType(models.TextChoices):
        BUREAU = 'bureau', 'Bureau'
        ENTREPOT = 'entrepot', 'Entrepôt'
        USINE = 'usine', 'Usine'
        COMMERCE = 'commerce', 'Commerce'
        AGRICOLE = 'agricole', 'Agricole'
        AUTRE = 'autre', 'Autre'

    class SiteCount(models.TextChoices):
        UN = '1', '1 site'
        DEUX_A_CINQ = '2-5', '2 à 5 sites'
        SIX_PLUS = '6+', '6 sites ou plus'

    # QW2 — Créneau de visite technique préféré (W353), STATIQUE — jamais une
    # réservation confirmée (le RDV réel reste QJ20 Appointment).
    class VisitWindowPart(models.TextChoices):
        MATIN = 'matin', 'Matin'
        APRES_MIDI = 'apres_midi', 'Après-midi'

    class VisitWindowWeek(models.TextChoices):
        CETTE_SEMAINE = 'cette_semaine', 'Cette semaine'
        SEMAINE_PROCHAINE = 'semaine_prochaine', 'Semaine prochaine'

    # QW3 — Préférence de contact EXPLICITE du prospect (lead.ts
    # CONTACT_PREFERENCES), DISTINCTE de `whatsapp_opt_in` (consentement
    # marketing WhatsApp) et de `Canal` (canal marketing d'ORIGINE) : ceci est
    # « comment voulez-vous qu'on vous recontacte », une question posée UNE
    # FOIS au client, jamais déduite ni écrasée par le canal marketing.
    class ContactPreference(models.TextChoices):
        WHATSAPP_ONLY = 'whatsapp_only', 'WhatsApp uniquement'
        PHONE_OK = 'phone_ok', 'Rappel téléphonique OK'

    # Langue préférée du contact pour les messages (ex. WhatsApp). Nullable :
    # tant qu'elle n'est pas renseignée, le message retombe sur le FR. Les clés
    # sont identiques à celles attendues par le constructeur WhatsApp
    # (apps.ventes.utils.whatsapp : langue ∈ {'fr','darija'}).
    class LanguePreferee(models.TextChoices):
        FR = 'fr', 'Français'
        DARIJA = 'darija', 'Darija'

    # CAD65 (audit L3 du 21/09/2026) — la civilité est une DONNÉE du lead,
    # rendue par `{civilite}` dans les textes client (FR « M. »/« Mme »,
    # darija « السي »/« لالة ») : plus aucun « M. » codé en dur.
    class Civilite(models.TextChoices):
        M = 'M.', 'M.'
        MME = 'Mme', 'Mme'

    # ── QK1 — Qualification captée par le site (tous additifs, optionnels) ──
    # Distributeur d'électricité du prospect (détermine la tranche tarifaire).
    # ── CAD-M ── CAD167 — LES SRM RÉGIONALES (décision fondateur du
    # 21/09/2026, Q16 : « il n'y a plus désormais que SRM au Maroc »).
    # Une valeur par région du découpage de 2015, et elle se DÉDUIT de la ville
    # du lead (``apps/crm/srm_regions.py``) plutôt que d'être demandée.
    # ONEE, Lydec, Redal et Amendis restent des libellés HISTORIQUES : une
    # valeur déjà enregistrée ne disparaît JAMAIS d'une fiche existante.
    # La VALEUR ne change AUCUN prix — le barème est national et unique
    # (décision Q7 du 20/08/2026) ; ce champ est un libellé.
    class Distributeur(models.TextChoices):
        SRM_TANGER = 'srm_tanger', 'SRM Tanger-Tétouan-Al Hoceïma'
        SRM_ORIENTAL = 'srm_oriental', 'SRM de l’Oriental'
        SRM_FES = 'srm_fes', 'SRM Fès-Meknès'
        SRM_RABAT = 'srm_rabat', 'SRM Rabat-Salé-Kénitra'
        SRM_BENI_MELLAL = 'srm_beni_mellal', 'SRM Béni Mellal-Khénifra'
        SRM_CASABLANCA = 'srm_casablanca', 'SRM Casablanca-Settat'
        SRM_MARRAKECH = 'srm_marrakech', 'SRM Marrakech-Safi'
        SRM_DRAA = 'srm_draa', 'SRM Drâa-Tafilalet'
        SRM_SOUSS = 'srm_souss', 'SRM Souss-Massa'
        SRM_GUELMIM = 'srm_guelmim', 'SRM Guelmim-Oued Noun'
        SRM_LAAYOUNE = 'srm_laayoune', 'SRM Laâyoune-Sakia El Hamra'
        SRM_DAKHLA = 'srm_dakhla', 'SRM Dakhla-Oued Ed-Dahab'
        # ── Libellés HISTORIQUES, lecture seule (fiches déjà saisies) ──
        ONEE = 'onee', 'ONEE (historique)'
        LYDEC = 'lydec', 'Lydec (historique)'
        REDAL = 'redal', 'Redal (historique)'
        AMENDIS = 'amendis', 'Amendis (historique)'
        AUTRE = 'autre', 'Autre (historique)'

    # Statut d'occupation du bâtiment (un locataire ne décide pas des travaux).
    class Ownership(models.TextChoices):
        PROPRIETAIRE = 'proprietaire', 'Propriétaire'
        LOCATAIRE = 'locataire', 'Locataire'
        AUTRE = 'autre', 'Autre'

    # Horizon du projet déclaré par le prospect.
    class ProjectTimeline(models.TextChoices):
        IMMEDIAT = 'immediat', 'Dès que possible'
        MOINS_3_MOIS = '3_mois', 'Moins de 3 mois'
        MOINS_6_MOIS = '6_mois', '3 à 6 mois'
        PLUS_TARD = 'plus_tard', 'Plus tard / je me renseigne'

    # Intention de financement déclarée.
    class FinancingIntent(models.TextChoices):
        CASH = 'cash', 'Comptant'
        CREDIT = 'credit', 'Crédit / financement'
        INDECIS = 'indecis', 'Pas encore décidé'
        # CIQ401 — valeur INTERNE (D-CIQ-15) : jamais imprimée avant l'avis
        # juridique sur le crédit-bail sous 82-21.
        CREDIT_BAIL = 'credit_bail', 'Crédit-bail (interne)'

    # ── CIQ401 (contrat CIQ1 ``lead_pro.json``) — vocabulaires du lead PRO ──
    class TensionRaccordement(models.TextChoices):
        BT = 'bt', 'Basse tension (BT)'
        MT = 'mt', 'Moyenne tension (MT)'
        NE_SAIT_PAS = 'ne_sait_pas', 'Ne sait pas'

    # CIQ666 (décision fondateur 08/10/2026) — le CONTRAT d'électricité
    # déclaré du site pro : même vocabulaire que ``etude_params.tarif_declare
    # .contrat`` (CIQ222, ``parametres.tarifs_officiels.CONTRATS``) ; « ne sait
    # pas » = aucun contrat transmis au moteur (jamais un contrat supposé).
    class ContratElectricite(models.TextChoices):
        BT_DOMESTIQUE = 'bt_domestique', 'BT domestique'
        BT_PATENTE = 'bt_patente', 'BT patenté'
        BT_FORCE_MOTRICE = 'bt_force_motrice', 'BT force motrice'
        MT_GENERAL = 'mt_general', 'MT (Tarif Général)'
        NE_SAIT_PAS = 'ne_sait_pas', 'Ne sait pas'

    class OptionTarifaireBt(models.TextChoices):
        NORMALE = 'normale', 'Option normale (tranches)'
        BI_HORAIRE = 'bi_horaire', 'Option bi-horaire (HP / HN)'

    class TensionSource(models.TextChoices):
        DECLARE = 'declare', 'Déclarée'
        SITE_WEB = 'site_web', 'Saisie sur le site'
        SITE_DEFAUT_VISIBLE = 'site_defaut_visible', 'Défaut visible du site'
        FACTURE = 'facture', 'Lue sur la facture'
        MESURE_VISITE = 'mesure_visite', 'Mesurée en visite'

    class PuissanceSouscriteSource(models.TextChoices):
        DECLARE = 'declare', 'Déclarée'
        FACTURE = 'facture', 'Lue sur la facture'
        CONTRAT = 'contrat', 'Lue sur le contrat'
        SITE_WEB = 'site_web', 'Saisie sur le site'
        MESURE_VISITE = 'mesure_visite', 'Mesurée en visite'

    class CategorieCommerciale(models.TextChoices):
        HOTEL = 'hotel', 'Hôtel / riad'
        RESTAURANT = 'restaurant', 'Restaurant / café'
        COMMERCE = 'commerce', 'Commerce / supermarché'
        BUREAU = 'bureau', 'Bureaux'
        SANTE = 'sante', 'Santé (clinique, cabinet)'
        ECOLE = 'ecole', 'École'
        HAMMAM = 'hammam', 'Hammam / spa / salle de sport'
        BOULANGERIE = 'boulangerie', 'Boulangerie'
        FROID = 'froid', 'Froid / entrepôt frigorifique'
        AUTRE = 'autre', 'Autre'

    #: Clés FERMÉES de ``reponses_categorie`` par catégorie (contrat CIQ1,
    #: ``reponses_categorie_par_categorie.cles``).
    REPONSES_CATEGORIE_CLES = {
        'hotel': ('chambres', 'occupation_pct', 'piscine', 'heures_piscine',
                  'blanchisserie', 'reception_24h'),
        'restaurant': ('chambres_froides', 'horaires', 'cuisson',
                       'ouvert_journee_ramadan'),
        'commerce': ('surface_vente_m2', 'chambres_froides'),
        'bureau': ('effectif', 'clim'),
        'sante': ('lits', 'garde_nuit'),
        'ecole': ('effectif', 'internat', 'fermeture_estivale'),
        'hammam': ('surface_m2', 'chauffe'),
        'boulangerie': ('four', 'cuisson_nocturne'),
        'froid': ('temperature_consigne', 'volume_m3',
                  'saisonnalite_recolte'),
        'autre': (),
    }

    class OuiNon(models.TextChoices):
        OUI = 'oui', 'Oui'
        NON = 'non', 'Non'

    class RegimeEquipes(models.TextChoices):
        UNE_EQUIPE = '1x8', 'Une équipe (1×8)'
        DEUX_EQUIPES = '2x8', 'Deux équipes (2×8)'
        TROIS_EQUIPES = '3x8', 'Trois équipes (3×8)'
        CONTINU = 'continu', 'En continu'
        NE_SAIT_PAS = 'ne_sait_pas', 'Ne sait pas'

    class TypeSurface(models.TextChoices):
        TOITURE = 'toiture', 'Toiture'
        OMBRIERE = 'ombriere', 'Ombrière de parking'
        TERRAIN = 'terrain', 'Terrain'

    class SurfaceSource(models.TextChoices):
        DECLARE = 'declare', 'Déclarée'
        SITE_WEB = 'site_web', 'Saisie sur le site'
        CALEPINAGE = 'calepinage', 'Calepinage'
        MESURE_VISITE = 'mesure_visite', 'Mesurée en visite'

    class CosPhiSource(models.TextChoices):
        FACTURE = 'facture', 'Lu sur la facture'
        SITE_WEB = 'site_web', 'Saisi sur le site'
        MESURE_VISITE = 'mesure_visite', 'Mesuré en visite'

    class TvaRecuperable(models.TextChoices):
        OUI = 'oui', 'Oui'
        NON = 'non', 'Non'
        NE_SAIT_PAS = 'ne_sait_pas', 'Ne sait pas'

    # Charges futures prévues (clés autorisées de `futures_charges`).
    FUTURES_CHARGES_KEYS = ('clim', 've', 'pompe')

    # L4 (21/08/2026, extension fondateur) — présence au foyer en JOURNÉE,
    # posée au téléphone. Distincte d'``Ownership`` (statut juridique) et
    # d'``occupation_pct`` (taux d'occupation hôtelier) : aucun des deux ne
    # dit qui est là le jour (voir apps/ventes/courbes_journalieres._occupation
    # docstring). Pilote directement la silhouette de consommation servie.
    class OccupationJour(models.TextChoices):
        PRESENT = 'present', 'Présent en journée'
        ABSENT = 'absent', 'Absent en journée'
        PARTIEL = 'partiel', 'Présence partielle (télétravail/mi-temps)'

    # L-BACK (24/08/2026) — créneaux du script d'appel pour chauffe-eau/VE.
    # Voir apps/ventes/courbes_journalieres.py pour les fenêtres horaires
    # exactes servies à chaque créneau (convention interne documentée là-bas,
    # pas une mesure).
    class CreneauChauffeEau(models.TextChoices):
        MATIN = 'matin', 'Matin'
        SOIR = 'soir', 'Soir'
        NUIT = 'nuit', 'Nuit'
        JOURNEE = 'journee', 'Toute la journée'

    class CreneauVe(models.TextChoices):
        NUIT = 'nuit', 'Nuit'
        JOUR = 'jour', 'Jour'
        SOIR = 'soir', 'Soir'

    # L-BACK2 (24/08/2026) — créneaux clim/piscine. Mêmes quatre créneaux
    # pour les deux (script d'appel identique) ; contrairement à
    # CreneauChauffeEau/CreneauVe, ces créneaux ENRICHISSENT une couche déjà
    # active (clim/piscine) au lieu d'en composer une nouvelle — voir
    # apps/ventes/courbes_journalieres.py.
    class CreneauClim(models.TextChoices):
        MATIN = 'matin', 'Matin'
        APRES_MIDI = 'apres_midi', 'Après-midi'
        SOIR = 'soir', 'Soir'
        JOURNEE = 'journee', 'Toute la journée'

    class CreneauPiscine(models.TextChoices):
        MATIN = 'matin', 'Matin'
        APRES_MIDI = 'apres_midi', 'Après-midi'
        SOIR = 'soir', 'Soir'
        JOURNEE = 'journee', 'Toute la journée'

    # ── CAD-L ── CAD149 — vocabulaires de la VAGUE 1 du script d'appel guidé
    # (audit L3 du 21/09/2026). Chaque vocabulaire sert UN champ dont le
    # ``help_text`` porte la question orale : rien n'est réinventé ailleurs.
    class TypeBien(models.TextChoices):
        VILLA = 'villa', 'Villa'
        APPARTEMENT = 'appartement', 'Appartement'
        IMMEUBLE = 'immeuble', 'Immeuble'
        RIAD = 'riad', 'Riad'
        FERME = 'ferme', 'Ferme'
        AUTRE = 'autre', 'Autre'

    # ``secours_coupures`` ABSORBE le besoin « je veux tenir pendant les
    # coupures » : c'est un objectif déclaré, pas un booléen séparé — et il
    # reste un ARGUMENT commercial, sans aucun dimensionnement de secours.
    # CAD163 (décision fondateur du 21/09/2026, Q9) — la loi 82-21 n'est
    # JAMAIS abordée spontanément : le libellé ne la nomme plus, et le choix ne
    # se coche que si le client parle lui-même de revendre son surplus. La
    # VALEUR `injection_8221` ne change pas (données, webhooks, questionnaire).
    class ObjectifProjet(models.TextChoices):
        FACTURE = 'facture', 'Baisser la facture'
        SECOURS_COUPURES = 'secours_coupures', 'Tenir pendant les coupures'
        AUTONOMIE = 'autonomie', 'Gagner en autonomie'
        INJECTION_8221 = ('injection_8221',
                          'Revendre le surplus (si le client en parle)')
        AUTRE = 'autre', 'Autre'

    # Vocabulaire REPRIS de la qualification de visite
    # (``apps/visites/qualification.py``) pour ne pas ouvrir un second
    # vocabulaire du même sujet, + le cas « le propriétaire est un tiers »
    # que la visite ne connaissait pas (locataire, indivision, syndic).
    class Decideur(models.TextChoices):
        SEUL = 'seul', 'Décide seul'
        CONJOINT_FAMILLE = 'conjoint_famille', 'Avec le conjoint / la famille'
        ASSOCIE_DIRECTION = 'associe_direction', 'Avec un associé / la direction'
        PROPRIETAIRE_TIERS = 'proprietaire_tiers', 'Le propriétaire (un tiers) décide'

    # État de la comparaison EN COURS. ``ConcurrentPerte`` reste le
    # post-mortem d'une affaire PERDUE : les deux ne se remplacent pas.
    class DevisConcurrents(models.TextChoices):
        NON = 'non', 'Non, aucun autre devis'
        EN_ATTENTE = 'en_attente', 'En attente d’un autre devis'
        RECU = 'recu', 'A déjà reçu un autre devis'

    class EquipVeStatut(models.TextChoices):
        POSSEDE = 'possede', 'Véhicule déjà là'
        PREVU = 'prevu', 'Véhicule seulement prévu'

    # Vocabulaire IDENTIQUE à celui du site (``pompeActuelle``,
    # apps/crm/webhooks.py) — le butane est GARDÉ : c'est un cas réel du parc
    # marocain qu'un vocabulaire « diesel/réseau/aucune » perdrait.
    class PompeAlimActuelle(models.TextChoices):
        AUCUNE = 'aucune', 'Aucune pompe'
        DIESEL = 'diesel', 'Diesel'
        BUTANE = 'butane', 'Butane'
        ELECTRIQUE = 'electrique', 'Électrique (réseau)'

    # ── AGR400 (Groupe AGR, contrat AGR1 ``lead_pompage.json``) — les
    # vocabulaires des colonnes de pompage. Ceux que le site émet déjà
    # (source d'eau, irrigation, région) gardent MOT POUR MOT les clés du
    # tunnel (``apps/crm/webhooks.py``) : un second vocabulaire du même sujet
    # rendrait le sac et la colonne illisibles ensemble.
    class SourceEau(models.TextChoices):
        PUITS = 'puits', 'Puits'
        FORAGE = 'forage', 'Forage'
        BASSIN = 'bassin', 'Bassin'
        RIVIERE = 'riviere', 'Rivière'

    class NiveauStatiqueSource(models.TextChoices):
        DECLARE = 'declare', 'Déclaré par le client'
        SITE_WEB = 'site_web', 'Saisi sur le site'
        MESURE_VISITE = 'mesure_visite', 'Mesuré en visite'

    class DebitForageSource(models.TextChoices):
        ESSAI = 'essai', 'Essai de pompage'
        FOREUR = 'foreur', 'Donné par le foreur'
        CLIENT = 'client', 'Estimation du client'
        MESURE_VISITE = 'mesure_visite', 'Mesuré en visite'

    class BesoinEauSource(models.TextChoices):
        CLIENT = 'client', 'Déclaré par le client'
        SITE_WEB = 'site_web', 'Saisi sur le site'
        POMPE_ACTUELLE = 'pompe_actuelle', 'Calculé depuis la pompe actuelle'

    class IrrigationMethode(models.TextChoices):
        GOUTTE = 'goutte', 'Goutte-à-goutte'
        ASPERSION = 'aspersion', 'Aspersion'
        GRAVITAIRE = 'gravitaire', 'Gravitaire (à la raie)'

    class RegionAgricole(models.TextChoices):
        SOUSS_MASSA = 'souss-massa', 'Souss-Massa'
        DOUKKALA = 'doukkala', 'Doukkala'
        TADLA = 'tadla', 'Tadla'
        SAISS = 'saiss', 'Saïss'
        ORIENTAL = 'oriental', 'Oriental'
        DRAA_TAFILALET = 'draa-tafilalet', 'Drâa-Tafilalet'
        GHARB_LOUKKOS = 'gharb-loukkos', 'Gharb-Loukkos'
        HAOUZ = 'haouz', 'Haouz'

    class PompeActuelleType(models.TextChoices):
        IMMERGEE = 'immergee', 'Immergée'
        SURFACE = 'surface', 'De surface'
        NE_SAIT_PAS = 'ne_sait_pas', 'Ne sait pas'

    class ElectriciteSurPlace(models.TextChoices):
        AUCUNE = 'aucune', 'Aucune'
        MONOPHASE = 'monophase', 'Monophasé'
        TRIPHASE = 'triphase', 'Triphasé'
        NE_SAIT_PAS = 'ne_sait_pas', 'Ne sait pas'

    class AutorisationPrelevement(models.TextChoices):
        OUI = 'oui', 'Oui'
        NON = 'non', 'Non'
        EN_COURS = 'en_cours', 'En cours'
        NE_SAIT_PAS = 'ne_sait_pas', 'Ne sait pas'

    class ProjetPompage(models.TextChoices):
        EXISTANT = 'existant', 'Remplacer une pompe existante'
        NOUVEAU_FORAGE = 'nouveau_forage', 'Nouveau forage'

    class PompeHmtSource(models.TextChoices):
        DECLAREE = 'declaree', 'Déclarée'
        SITE_WEB = 'site_web', 'Saisie sur le site'

    # AGR522 (contrat AGR501 ``lead_dossier_subvention.json``) — l'état d'un
    # dossier d'aide FDA. INTERNE : jamais dans une charge utile client.
    class DossierSubvention(models.TextChoices):
        NON_CONCERNE = 'non_concerne', 'Non concerné'
        A_DEPOSER = 'a_deposer', 'À déposer'
        DEPOSE = 'depose', 'Déposé'
        ACCORDE = 'accorde', 'Accordé (approbation préalable)'
        REFUSE = 'refuse', 'Refusé'

    # ── CAD-L ── CAD154 — vocabulaires de la VAGUE 2. Les deux REPRENNENT
    # mot pour mot ceux de la qualification de visite
    # (``apps/visites/qualification.py``) : le terrain et le téléphone
    # décrivent le même client, ouvrir un second vocabulaire rendrait les
    # deux illisibles ensemble.
    class FreinPrincipal(models.TextChoices):
        AUCUN = 'aucun', 'Aucun frein'
        PRIX = 'prix', 'Prix'
        COMPARE = 'compare', 'Compare d’autres devis'
        TIMING = 'timing', 'Timing'
        TECHNIQUE = 'technique', 'Technique'
        CONFIANCE = 'confiance', 'Confiance'

    class Declencheur(models.TextChoices):
        ECONOMIES = 'economies', 'Les économies'
        COUPURES = 'coupures', 'Les coupures / l’autonomie'
        ECOLOGIE = 'ecologie', 'L’écologie'
        TECHNOLOGIE = 'technologie', 'La technologie'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='leads',
    )
    # Contact identity (a lead may not yet be a structured client).
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255, blank=True, null=True)
    # CAD65 (audit L3 du 21/09/2026) — « Bonjour M. » partait à une cliente :
    # la civilité était codée en dur dans 17 textes FR et 12 darija, et NI
    # le lead NI le client n'en portaient une. FACULTATIVE, saisie au premier
    # contact : vide ⇒ salutation NEUTRE (le prénom seul), jamais un genre
    # supposé. Nullable comme `langue_preferee` (l'écran envoie null pour
    # « non renseignée »).
    civilite = models.CharField(
        max_length=4, choices=Civilite.choices, blank=True, null=True,
        verbose_name='Civilité',
        help_text="Question au premier appel, seulement en cas de doute : "
                  "« Je vous note Monsieur ou Madame ? » — facultative : "
                  'vide, les messages disent « Bonjour [prénom] », jamais un '
                  'genre supposé.')
    societe = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Question à l'appel : « Quelle est la raison sociale de "
                  'votre entreprise ? » (vide = pas encore posée).')
    email = models.EmailField(blank=True, null=True)
    # CAD146 (21/09/2026) — pas de fuseau horaire par lead : un numéro
    # étranger (diaspora) reçoit ses touches à l'heure de Casablanca. Décision
    # écrite, rien construit tant que CADM7 (comptage) n'a pas de chiffre —
    # voir `apps/crm/horaires.py`, bas de fichier.
    telephone = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    ville = models.CharField(max_length=120, blank=True, null=True)

    # CAD144 (audit L3 du 21/09/2026) — un achat de coopérative ou un comité
    # industriel a PLUSIEURS interlocuteurs (co-associé, technicien d'usine).
    # Un champ libre, visible sur la fiche, et RIEN d'autre : aucune cadence,
    # aucun message, aucune dédup ne lit jamais ces deux colonnes — le
    # protocole vers ce second contact reste MANUEL. Le téléphone est une PII
    # (masqué sans `client_pii_voir`, comme le numéro principal).
    contact_secondaire_nom = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='Contact secondaire (nom)',
        help_text='Co-associé de coopérative, technicien d’usine, membre du '
                  'comité… Aucune relance automatique ne lui est adressée.')
    contact_secondaire_telephone = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='Contact secondaire (téléphone)',
        help_text='Numéro du second interlocuteur — jamais utilisé par la '
                  'cadence : le contacter reste un geste manuel.')

    # Client (fiche structurée) résolu depuis ce lead — rempli au premier devis
    # ou manuellement ; la résolution évite les doublons (voir services.py).
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
    )

    # ── ARC56 — Pont additif vers le répertoire unifié Tiers (stade amont) ──
    # FK nullable (string-FK ``'tiers.Tiers'``) : le lead porte l'identité
    # PRÉ-CONVERSION (avant qu'un Client structuré existe), donc le recoupement
    # « qui est ce tiers ? » (ARC20) doit aussi couvrir ce stade. Rattaché au
    # MÊME Tiers que le Client résolu (via resolve_client_for_lead + le miroir
    # crm.Client → Tiers d'ARC18) ; jamais un 2ᵉ Tiers pour le même acteur.
    # ATTENTION QW7 : ce pont ne touche AUCUN champ de nom du lead.
    tiers = models.ForeignKey(
        'tiers.Tiers',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
        verbose_name='Tiers (répertoire unifié)',
        help_text="Fiche du répertoire unifié reflétant ce prospect "
                  "(stade amont). Renseignée automatiquement (miroir).")

    # Facture électrique du lead (MAD/mois). Si l'été ne diffère pas de
    # l'hiver, facture_hiver vaut pour les deux (ete_differente = False).
    # CAD158 (décision fondateur du 21/09/2026, Q24) — le moteur lit un
    # montant MENSUEL : une facture BIMESTRIELLE est ramenée au mois AU
    # MOMENT DE LA SAISIE (`PERIODICITES_FACTURE`, `services.facture_au_mois`),
    # et AUCUN champ « périodicité » n'est stocké. La question vit ICI, dans le
    # `help_text` (« chaque champ EST le script d'appel »).
    facture_hiver = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Question à l'appel : « Votre facture d'électricité, elle "
                  'est de combien ? Elle couvre un mois ou deux mois ? » — le '
                  'montant ENREGISTRÉ est toujours MENSUEL : une facture de '
                  'deux mois est divisée par deux à la saisie.')
    #: CAD158 — combien de mois couvre la facture déclarée. Un montant
    #: bimestriel est ramené au mois à la saisie ; jamais stocké tel quel.
    PERIODICITES_FACTURE = {'mensuelle': 1, 'bimestrielle': 2}
    facture_ete = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    ete_differente = models.BooleanField(default=False)

    # ── Contact & localisation (extension CRM solaire 2026-06) ──
    whatsapp = models.CharField(max_length=50, blank=True, null=True)
    # Langue préférée du contact (FR/Darija) — pré-sélectionne la langue du
    # message WhatsApp. Nullable : non renseignée → retombe sur le FR.
    langue_preferee = models.CharField(
        max_length=10, choices=LanguePreferee.choices, blank=True, null=True)
    # Bornes géographiques : latitude ∈ [-90, 90], longitude ∈ [-180, 180].
    # Les validateurs s'appliquent à full_clean()/serializers ; le DecimalField
    # max_digits=9/decimal_places=6 autorise déjà ±999.999999, d'où ces gardes.
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])
    # GPS7 (fondateur 07/09/2026) — lien Google Maps envoyé par le client,
    # gardé pour PROVENANCE ; l'écran le convertit en gps_lat/gps_lng via
    # `geolocalisation.coords_depuis_lien_maps` (action resoudre-gps).
    lien_maps = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name='Lien Google Maps')
    # VREF (fondateur 07/09/2026) — ville ERP de RATTACHEMENT quand la ville
    # tapée n'est pas dans le gazetier (douar, petit village) : choisie par
    # Meryem sur l'écran « Vérifier la ville » (carte + villes proches). Le
    # nom tapé par le client est CONSERVÉ dans `ville` ; l'affichage devient
    # « X, près de Y » et les calculs (PVGIS, transport) lisent Y.
    ville_reference = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Ville ERP de rattachement')

    # ── Pipeline / CRM ──
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,  # on_delete: responsable commercial informatif — le lead survit au départ de l'utilisateur
        null=True, blank=True, related_name='leads_assignes')
    canal = models.CharField(
        max_length=20, choices=Canal.choices, blank=True, null=True)
    priorite = models.CharField(
        max_length=10, choices=Priorite.choices, default=Priorite.NORMALE)
    # Tags libres, séparés par des virgules (ex. "Régularisation 82-21, VIP")
    tags = models.CharField(max_length=500, blank=True, null=True)
    # Drapeau « Perdu » — indépendant de l'étape (voir STAGES.py : « Perdu »
    # n'est PAS une étape, c'est un lost-flag qui se pose depuis N'IMPORTE
    # quelle étape, avec sa raison dans motif_perte). Un lead Froid n'est pas
    # forcément perdu ; un lead à « Devis envoyé » peut l'être.
    perdu = models.BooleanField(default=False)
    motif_perte = models.CharField(max_length=255, blank=True, null=True)
    # AMET23 (D-PROVENANCE) — noms des champs saisis par un HUMAIN (liste
    # triée, sans doublon), lus par ``records.provenance.ecrire_si_libre`` :
    # un écrivain automatique ne l'écrase jamais. Posé côté serveur seulement.
    saisies_humaines = models.JSONField(
        default=list, blank=True, verbose_name='Champs saisis par un humain')
    relance_date = models.DateField(null=True, blank=True)
    # MRY5 — « ne plus contacter » : la personne a demandé qu'on la laisse
    # tranquille. DISTINCT de `whatsapp_opt_in` (consentement MARKETING) et de
    # `perdu` (décision commerciale, qui exige un motif). Il n'implique NI
    # l'un NI l'autre : il interdit seulement toute future cadence.
    ne_plus_contacter = models.BooleanField(
        default=False, verbose_name='Ne plus contacter')
    # CAD145 (21/09/2026) — SOURCE UNIQUE lue par le scoring (`scoring.py`),
    # les playbooks (`Playbook.condition`, évalué contre {type_installation,
    # canal} DU LEAD) et les textes de segment (CAD126) : ces trois surfaces
    # ne lisent JAMAIS `SiteProfile.type_installation` (champ CLIENT distinct,
    # voir sa docstring). Les deux existent parce que leurs cycles de vie
    # diffèrent — le lead précède souvent le client — pas par erreur.
    type_installation = models.CharField(
        max_length=20, choices=TypeInstallation.choices, blank=True, null=True)

    # ── XSAL7 — Pipeline pondéré PRÉ-devis (additif, nullable) ──
    # Un lead chaud SANS devis pèse zéro dans le forecast pipeline
    # aujourd'hui ; ces deux champs, saisis librement en amont d'un devis,
    # lui donnent un poids (montant_estime × win_probability, voir
    # apps/reporting/pipeline.py) UNIQUEMENT quand le lead n'a aucun devis
    # actif (jamais de double comptage avec la valeur du devis).
    montant_estime = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant estimé (MAD)',
        help_text="Estimation libre du commercial avant devis — contribue "
                  "au forecast pondéré tant qu'aucun devis actif n'existe.")
    date_cloture_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de clôture prévue')

    # ── Profil énergétique ──
    conso_mensuelle_kwh = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Consommation mensuelle (kWh)',
        help_text="Question à l'appel : « Votre consommation du mois "
                  'dernier, en kWh ? Elle est sur la facture. » (vide = pas '
                  'encore posée).')
    tranche_onee = models.CharField(max_length=100, blank=True, null=True)
    raccordement = models.CharField(
        max_length=12, choices=Raccordement.choices, blank=True, null=True,
        help_text="Question à l'appel : « Votre compteur est-il monophasé ou "
                  'triphasé ? » (vide = pas encore posée).')
    # Installation existante à régulariser ? (Loi 82-21)
    regularisation_8221 = models.BooleanField(default=False)

    # ── L4 (21/08/2026) — Équipements électriques : script d'appel commercial ──
    # Réponses posées AU TÉLÉPHONE, distinctes de `futures_charges` (case à
    # cocher SANS paramètre, posée par le QUESTIONNAIRE WEB — QW2/QK1). Ici :
    # trois états (Oui/Non/Inconnu — `null=True` = pas encore posée, JAMAIS
    # confondu avec « Non ») + une grandeur réelle par équipement quand elle
    # existe. Ces champs composent les couches de `courbes_journalieres`
    # (apps/ventes/courbes_journalieres.py, fonction ``_equipements``) — voir
    # ce module pour la provenance SOURCÉE de chaque défaut/conversion utilisé
    # (mémo estimation-consommation du 21/08/2026, étage 2). Le help_text de
    # chaque champ EST le script d'appel (RÈGLE : « la question exacte à
    # poser » vit ici + dans l'UI CRM, jamais réinventée ailleurs).
    occupation_jour = models.CharField(
        max_length=10, choices=OccupationJour.choices, null=True, blank=True,
        verbose_name='Présence en journée',
        help_text="Question à l'appel : « Y a-t-il quelqu'un à la maison "
                  'en journée ? » (Présent/Absent/Présence partielle — '
                  'vide = pas encore posée). Renseigné : PILOTE la '
                  'silhouette de consommation servie '
                  '(apps/ventes/courbes_journalieres.py _occupation) — '
                  'sinon repli sur le défaut fondateur actuel, inchangé.')
    equip_piscine = models.BooleanField(
        null=True, blank=True, verbose_name='Piscine',
        help_text="Question à l'appel : « Avez-vous une piscine ? » "
                  '(Oui/Non — laisser vide tant que la question n\'a pas '
                  'été posée : vide ≠ Non).')
    equip_piscine_pompe_kw = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Puissance pompe piscine (kW)',
        help_text='Puissance de la pompe de filtration (kW, plaque '
                  'signalétique du moteur). Aucune valeur par défaut : '
                  "le mémo ne cite aucune puissance fiable pour ce parc — "
                  'à relever sur place ou à demander au client, sinon '
                  'laisser vide (aucune couche piscine sans cette valeur).')
    equip_voiture_electrique = models.BooleanField(
        null=True, blank=True, verbose_name='Véhicule électrique',
        help_text="Question à l'appel : « Avez-vous ou prévoyez-vous un "
                  'véhicule électrique ? » (Oui/Non — vide = pas encore '
                  'posée).')
    equip_ve_km_semaine = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='VE — km parcourus/semaine',
        help_text="Question à l'appel : « Combien de km parcourez-vous par "
                  'semaine avec ce véhicule ? » SAISIE OBLIGATOIRE pour '
                  'chiffrer la recharge (aucun défaut : mémo étage 2 — '
                  'conversion ADEME 19,8 kWh/100 km, sans hypothèse de '
                  'kilométrage).')
    equip_clim = models.BooleanField(
        null=True, blank=True, verbose_name='Climatisation',
        help_text="Question à l'appel : « Avez-vous la climatisation ? » "
                  '(Oui/Non — vide = pas encore posée).')
    equip_clim_pieces = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Clim — nombre de pièces/unités',
        help_text="Question à l'appel : « Combien de pièces/unités "
                  'climatisées ? » (chaque unité ≈ 1,4 kWh/h pour un split '
                  '12000 BTU non-inverter — mémo étage 2).')
    equip_chauffe_eau_electrique = models.BooleanField(
        null=True, blank=True, verbose_name='Chauffe-eau électrique',
        help_text="Question à l'appel : « Votre chauffe-eau est-il "
                  'électrique ? » Champ INFORMATIF uniquement : le mémo ne '
                  "donne qu'un ordre de grandeur kWh/personne/an (aucun "
                  "champ « nombre de personnes » collecté) — il n'ajuste "
                  "AUCUNE courbe (omission plutôt qu'un défaut inventé).")

    # ── L-BACK (24/08/2026) — grandeurs réelles complémentaires. Champs
    # INERTES tant que leur paire n'est pas complète (kW + créneau/heures) :
    # une seule moitié renseignée NE produit AUCUNE couche (même règle
    # « zéro chiffre inventé » que le reste du bloc L4 ci-dessus). Voir
    # apps/ventes/courbes_journalieres.py pour la composition.
    equip_chauffe_eau_kw = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Puissance chauffe-eau (kW)',
        help_text='Puissance de la résistance du chauffe-eau électrique '
                  '(kW, plaque signalétique). Avec le créneau ci-dessous : '
                  'compose une couche « impulsion » sur ce créneau. Seule, '
                  'ne produit rien.')
    equip_chauffe_eau_creneau = models.CharField(
        max_length=10, choices=CreneauChauffeEau.choices, null=True,
        blank=True, verbose_name='Créneau de chauffe du chauffe-eau',
        help_text="Question à l'appel : « À quel moment le chauffe-eau "
                  'chauffe-t-il le plus (matin/soir/nuit/toute la '
                  'journée) ? » Avec la puissance ci-dessus : compose une '
                  'couche « impulsion » sur ce créneau. Seul, ne produit '
                  'rien.')
    equip_ve_chargeur_kw = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Puissance chargeur VE (kW)',
        help_text='Puissance du chargeur du véhicule électrique (kW, '
                  'prise renforcée/wallbox). Avec le créneau ci-dessous : '
                  "borne la fenêtre de recharge à l'énergie hebdomadaire "
                  '÷ cette puissance, au lieu de la fenêtre 21h-6h par '
                  'défaut. Seule, ne change rien.')
    equip_ve_creneau = models.CharField(
        max_length=10, choices=CreneauVe.choices, null=True, blank=True,
        verbose_name='Créneau de recharge du VE',
        help_text="Question à l'appel : « À quel moment rechargez-vous "
                  'le véhicule (nuit/jour/soir) ? » Avec la puissance '
                  'ci-dessus : borne la fenêtre de recharge réelle. Seul, '
                  'ne change rien.')
    equip_clim_kw = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Puissance clim déclarée (kW)',
        help_text='Puissance totale RÉELLE de la climatisation (kW, '
                  "relevée sur plaque signalétique), quand elle est "
                  "connue : remplace l'estimation par défaut "
                  '(pièces × 1,4 kWh/h non-inverter). Vide : la couche '
                  'clim reste composée depuis le nombre de pièces.')
    equip_piscine_heures_jour = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        verbose_name='Piscine — heures de filtration/jour',
        help_text='Durée réelle de filtration déclarée (h/jour), quand '
                  "elle est connue : remplace la durée par défaut du "
                  'mémo (8h, bloc 10h-18h). Vide : la couche piscine '
                  'reste composée avec la fenêtre par défaut.')

    # ── L-BACK2 (24/08/2026) — créneaux clim/piscine, même granularité
    # horaire que le bloc L-BACK ci-dessus mais en ENRICHISSEMENT d'une
    # couche déjà active (clim via kW/pièces, piscine via pompe kW), jamais
    # une paire requise pour exister. Voir
    # apps/ventes/courbes_journalieres.py pour la composition.
    equip_clim_creneau = models.CharField(
        max_length=10, choices=CreneauClim.choices, null=True, blank=True,
        verbose_name='Créneau de fonctionnement de la clim',
        help_text="Question à l'appel : « À quel moment la climatisation "
                  'tourne-t-elle le plus (matin/après-midi/soir/toute la '
                  'journée) ? » Avec la puissance déclarée (ou à défaut '
                  "l'estimation par pièces) : place la couche « clim » sur "
                  'ce créneau au lieu du bloc 13h-21h par défaut. Seul, ne '
                  'change rien.')
    equip_piscine_creneau = models.CharField(
        max_length=10, choices=CreneauPiscine.choices, null=True,
        blank=True, verbose_name='Créneau de filtration de la piscine',
        help_text="Question à l'appel : « À quel moment la pompe de "
                  'filtration tourne-t-elle le plus (matin/après-midi/'
                  'soir/toute la journée) ? » Change l\'heure de DÉPART '
                  'de la fenêtre (equip_piscine_heures_jour en contrôle '
                  'toujours la longueur). Seul, ne change rien.')

    # ── Pompage solaire (leads Agricole) ──
    # AGR401 — ancienne colonne CV, renommée : décrit la pompe ACTUELLE (information,
    # éligibilité), JAMAIS la pompe du devis. La puissance retenue est une
    # SORTIE du dimensionnement (clé CV d'``etude_params``), plus
    # stockée sur le Lead.
    pompe_actuelle_cv = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Pompe actuelle (CV)',
        help_text="Question à l'appel : « Votre pompe actuelle fait combien "
                  'de chevaux ? C\'est écrit sur sa plaque. » (vide = pas '
                  'encore posée).')
    pompe_hmt_m = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Question à l'appel : « Connaissez-vous la hauteur totale "
                  'de pompage, en mètres ? » (HMT, vide = pas encore '
                  'posée).')
    pompe_debit_m3h = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Question à l'appel : « Quel débit voulez-vous, en m³ par "
                  'heure ? » (débit SOUHAITÉ, vide = pas encore posée). '
                  'Servi à côté du débit livré, il ne fixe jamais seul le '
                  'besoin.')

    # ── AGR400 — Pompage : les colonnes du contrat AGR1 (``lead_pompage.json``).
    # Toutes ``null=True`` : vide = « la question n'a pas encore été posée »,
    # JAMAIS une réponse ni un défaut. Le ``help_text`` EST la question orale.
    # Les colonnes ``*_source`` et ``carburant_prix_declare_le`` ne se saisissent
    # jamais à la main : le serveur les pose (sérialiseur, webhook, visite).
    source_eau = models.CharField(
        max_length=10, choices=SourceEau.choices, null=True, blank=True,
        verbose_name="Source d'eau",
        help_text="Question à l'appel : « L'eau vient d'où : un puits, un "
                  'forage, un bassin ou une rivière ? » (vide = pas encore '
                  'posée).')
    niveau_statique_m = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="Niveau de l'eau, pompe arrêtée (m)",
        help_text="Question à l'appel : « À quelle profondeur est l'eau "
                  'quand la pompe est arrêtée ? » (mètres, vide = pas encore '
                  'posée).')
    niveau_statique_source = models.CharField(
        max_length=14, choices=NiveauStatiqueSource.choices, null=True,
        blank=True, verbose_name='Provenance du niveau statique')
    profondeur_forage_m = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name='Profondeur du forage (m)',
        help_text="Question à l'appel : « Quelle est la profondeur totale "
                  'du forage ? » (mètres, vide = pas encore posée).')
    debit_forage_m3h = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Débit du forage (m³/h)',
        help_text="Question à l'appel : « Le débit de votre forage est-il "
                  'connu (essai, foreur) ? Combien d\'eau peut-il donner par '
                  'heure ? » (m³/h, vide = pas encore posée).')
    debit_forage_source = models.CharField(
        max_length=14, choices=DebitForageSource.choices, null=True,
        blank=True, verbose_name='Provenance du débit du forage')
    besoin_eau_m3j = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        verbose_name="Besoin en eau (m³/jour)",
        help_text="Question à l'appel : « Combien de m³ d'eau par jour en "
                  'pleine saison ? » (vide = pas encore posée).')
    besoin_eau_source = models.CharField(
        max_length=14, choices=BesoinEauSource.choices, null=True,
        blank=True, verbose_name='Provenance du besoin en eau')
    culture = models.CharField(
        max_length=120, null=True, blank=True, verbose_name='Culture',
        help_text="Question à l'appel : « Qu'est-ce que vous cultivez ? » "
                  '(vide = pas encore posée).')
    surface_irriguee_ha = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        verbose_name='Surface irriguée (ha)',
        help_text="Question à l'appel : « Combien d'hectares irriguez-"
                  'vous ? » (vide = pas encore posée).')
    irrigation_methode = models.CharField(
        max_length=12, choices=IrrigationMethode.choices, null=True,
        blank=True, verbose_name="Méthode d'irrigation",
        help_text="Question à l'appel : « Vous arrosez comment : goutte-à-"
                  'goutte, aspersion ou à la raie ? » (vide = pas encore '
                  'posée).')
    region_agricole = models.CharField(
        max_length=16, choices=RegionAgricole.choices, null=True,
        blank=True, verbose_name='Région agricole',
        help_text="Question à l'appel : « Dans quelle région se trouve "
                  "l'exploitation ? » (vide = pas encore posée).")
    pompe_actuelle_type = models.CharField(
        max_length=12, choices=PompeActuelleType.choices, null=True,
        blank=True, verbose_name='Pompe actuelle — type',
        help_text="Question à l'appel : « Votre pompe actuelle est-elle "
                  'immergée dans le forage, ou en surface ? » (vide = pas '
                  'encore posée).')
    pompe_actuelle_debit_m3h = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Pompe actuelle — débit (m³/h)',
        help_text="Question à l'appel : « Combien d'eau votre pompe "
                  'actuelle sort-elle par heure ? » (m³/h, vide = pas encore '
                  'posée). Avec les heures de la pompe actuelle, donne le '
                  'volume déclaré.')
    butane_bouteilles_jour = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        verbose_name='Butane — bouteilles par jour',
        help_text="Question à l'appel : « Combien de bouteilles de butane "
                  'par jour en saison ? » (bouteilles de 12 kg par jour '
                  "d'irrigation, vide = pas encore posée).")
    carburant_prix_unitaire_mad = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Prix payé (bouteille ou litre, MAD)',
        help_text="Question à l'appel : « Vous la payez combien, la "
                  'bouteille (ou le litre de gasoil) ? » (MAD, vide = pas '
                  'encore posée). Prix PAYÉ déclaré, jamais pré-rempli.')
    carburant_prix_declare_le = models.DateField(
        null=True, blank=True, verbose_name='Prix du carburant déclaré le')
    depense_carburant_mad_mois = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Dépense carburant (MAD/mois)',
        help_text="Question à l'appel : « Combien dépensez-vous en "
                  'carburant par mois ? » (MAD/mois, vide = pas encore '
                  'posée). Information : jamais convertie en consommation.')
    mois_irrigation = models.JSONField(
        null=True, blank=True, validators=[valider_mois_irrigation],
        verbose_name="Mois d'irrigation",
        help_text="Question à l'appel : « Vous irriguez quels mois ? » "
                  '(liste de mois 1 à 12, vide = pas encore posée).')
    distance_forage_champ_m = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Distance forage — panneaux (m)',
        help_text="Question à l'appel : « À quelle distance du forage peut-"
                  'on poser les panneaux ? » (mètres, vide = pas encore '
                  'posée).')
    electricite_sur_place = models.CharField(
        max_length=12, choices=ElectriciteSurPlace.choices, null=True,
        blank=True, verbose_name='Électricité au forage',
        help_text="Question à l'appel : « Y a-t-il l'électricité au "
                  'forage : monophasé, triphasé ou rien ? » (vide = pas '
                  'encore posée).')
    autorisation_prelevement = models.CharField(
        max_length=12, choices=AutorisationPrelevement.choices, null=True,
        blank=True, verbose_name='Autorisation de prélèvement (ABH)',
        help_text="Question à l'appel : « Avez-vous l'autorisation de "
                  "l'Agence de bassin (ABH) pour ce point d'eau ? » (vide = "
                  'pas encore posée).')
    autorisation_numero = models.CharField(
        max_length=60, null=True, blank=True,
        verbose_name="Numéro de l'autorisation",
        help_text="Question à l'appel : « Quel est le numéro de cette "
                  'autorisation ? » (vide = pas encore posée).')
    autorisation_debit_l_s = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Débit autorisé (L/s)',
        help_text="Question à l'appel : « Quel débit l'autorisation vous "
                  'accorde-t-elle, en litres par seconde ? » (vide = pas '
                  'encore posée).')
    autorisation_volume_m3_an = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Volume autorisé (m³/an)',
        help_text="Question à l'appel : « Quel volume par an "
                  "l'autorisation vous accorde-t-elle ? » (vide = pas encore "
                  'posée).')
    compteur_eau = models.BooleanField(
        null=True, blank=True, verbose_name="Compteur d'eau",
        help_text="Question à l'appel : « Avez-vous un compteur d'eau ? » "
                  '(vide = pas encore posée).')
    projet_pompage = models.CharField(
        max_length=16, choices=ProjetPompage.choices, null=True, blank=True,
        verbose_name='Projet de pompage',
        help_text="Question à l'appel : « C'est un puits/forage qui existe, "
                  'ou un forage à creuser ? » (vide = pas encore posée).')
    deja_beneficiaire_fda = models.BooleanField(
        null=True, blank=True, verbose_name='Déjà bénéficiaire FDA',
        help_text="Question à l'appel : « Avez-vous déjà reçu une aide FDA "
                  'pour un pompage solaire sur cette exploitation ? » (vide '
                  '= pas encore posée). Information interne : jamais un '
                  'verdict client.')
    pompe_hmt_source = models.CharField(
        max_length=10, choices=PompeHmtSource.choices, null=True,
        blank=True, verbose_name='Provenance de la HMT')
    # AGR522 — dossier de subvention FDA (INTERNE, D-AGR-6). Vide = pas
    # encore renseigné. La date (dépôt, approbation préalable ou refus) est
    # exigée pour « déposé », « accordé » et « refusé » (sérialiseur). Ce
    # n'est pas un mode de paiement : le préfinancement reste
    # ``financing_intent = credit``.
    dossier_subvention = models.CharField(
        max_length=14, choices=DossierSubvention.choices, null=True,
        blank=True, verbose_name='Dossier de subvention (FDA)')
    dossier_subvention_le = models.DateField(
        null=True, blank=True,
        verbose_name='Date de l’état du dossier de subvention')

    # ── Toiture & site ──
    type_toiture = models.CharField(
        max_length=20, choices=TypeToiture.choices, blank=True, null=True,
        help_text="Question à l'appel : « Comment est faite votre toiture : "
                  'terrasse béton, tôle, tuiles, bac acier, fibrociment ? » '
                  '(vide = pas encore posée).')
    surface_toiture_m2 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Surface disponible pour les panneaux (m²)',
        help_text="Question à l'appel : « Quelle surface est libre pour les "
                  'panneaux, en m² ? » (vide = pas encore posée).')
    orientation = models.CharField(
        max_length=12, choices=Orientation.choices, blank=True, null=True)
    inclinaison_deg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    ombrage = models.CharField(
        max_length=12, choices=Ombrage.choices, blank=True, null=True)
    ombrage_notes = models.TextField(blank=True, null=True)
    nb_etages = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    structure_pref = models.CharField(
        max_length=12, choices=StructurePref.choices, blank=True, null=True)
    # STKCAT9 (fondateur 16/09/2026) — LE PRODUIT de structure choisi pour ce
    # lead. ``structure_pref`` ne sait dire que « acier » ou « aluminium » : il
    # ne peut donc PAS désigner une pergola, un carport ou un bac lesté, alors
    # que le rail « catégorie typée » (STKCAT2) les rend enfin composables.
    # Les deux COHABITENT : le produit, quand il est arrêté, est souverain ; à
    # défaut, la préférence acier/alu décide comme avant (cf.
    # ``ventes.domain.creation._structure_demandee``). Référence de modèle EN
    # CHAÎNE — ``apps.crm`` n'importe jamais les modèles d'``apps.stock``.
    structure_produit = models.ForeignKey(
        'stock.Produit',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Structure choisie (catalogue)',
        help_text='Produit de structure retenu pour ce lead (une fiche du '
                  'catalogue dont la catégorie est typée « Structure »). '
                  'Vide = c\'est « Préférence de structure » (acier / '
                  'aluminium) qui décide, exactement comme avant.',
    )
    taille_souhaitee_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    batterie_souhaitee = models.CharField(
        max_length=12, choices=BatterieSouhaitee.choices, blank=True, null=True)

    # ── Visite technique (légère) ──
    visite_prevue_le = models.DateField(null=True, blank=True)
    visite_effectuee = models.BooleanField(default=False)
    visite_notes = models.TextField(blank=True, null=True)

    # Pipeline stage — canonical keys from STAGES.py (default Nouveau / NEW).
    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default=NEW,
    )
    # Origin marker: native vs imported test data.
    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.OS_NATIVE,
    )
    # Traceability for imported records (e.g. Odoo lead id) — never written back.
    external_system = models.CharField(max_length=50, blank=True, null=True)
    external_id = models.CharField(max_length=100, blank=True, null=True)

    # ── Intake site web (taqinor.ma) — tous additifs et optionnels ──
    # Tranche du diagnostic (clés identiques au site) ; distinct de
    # facture_hiver (montant exact saisi au CRM).
    bill_range_bucket = models.CharField(
        max_length=20, choices=BillRangeBucket.choices, blank=True, null=True)
    # Type de toiture TEL QU'ÉMIS par le site (villa/hangar/toit_plat/autre) —
    # volontairement distinct de type_toiture (taxonomie technique CRM).
    # QJR657 — LEGACY : plus écrit (le « autre » du tunnel était fabriqué) ;
    # `type_toiture` est la seule source. Colonne conservée : sa suppression
    # est une migration destructive séparée.
    roof_type = models.CharField(max_length=30, blank=True, null=True)
    # ── Q2 — Toiture 3D : pin + contour BRUTS du client (additif, optionnels) ──
    # Le client POINTE simplement son bâtiment (il n'est PAS obligé de dessiner) :
    # roof_point = {lat, lng} de l'épingle ; roof_outline = polygone rough
    # OPTIONNEL [[lat,lng], …], le plus souvent vide. Distinct du layout
    # FINALISÉ (panneaux placés) qui vit sur Devis.roof_layout et seul atteint la
    # proposition. bill_kwh = conso mensuelle estimée (kWh) saisie au diagnostic.
    roof_point = models.JSONField(null=True, blank=True)
    roof_outline = models.JSONField(null=True, blank=True)
    bill_kwh = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # Jeton imprévisible par lead pour le lien de hand-off Meriem (conception
    # privée) ET, en aval, la proposition web tokenisée. Toujours posé côté
    # serveur, jamais lu d'un corps de requête.
    token = models.UUIDField(default=uuid.uuid4, editable=False,
                             unique=True, db_index=True)
    # Bande ROI préliminaire affichée au prospect (ex. « 5 à 9 kWc · 4 à 6 ans »)
    roi_band = models.CharField(max_length=200, blank=True, null=True)
    whatsapp_opt_in = models.BooleanField(null=True, blank=True)
    # QW3 — préférence de contact EXPLICITE, distincte de `whatsapp_opt_in`
    # (consentement marketing) et de `canal` (canal marketing d'origine).
    # NULL = non renseignée (comportement historique inchangé).
    contact_preference = models.CharField(
        max_length=16, choices=ContactPreference.choices, blank=True, null=True,
        verbose_name='Préférence de contact')
    # QX15 — horodatage de la POSE de `contact_preference` (distinct de
    # `date_creation` du lead). Le SLA rappel doit mesurer depuis QUAND le
    # rappel a été demandé, pas depuis quand le lead a été créé — un vieux
    # lead dont la préférence est posée MAINTENANT ne doit pas apparaître
    # instantanément « SLA rompu ». NULL = jamais posé (ou posé avant ce
    # champ) ; le sélecteur retombe sur `date_creation` dans ce cas
    # (comportement historique inchangé pour les leads déjà en base).
    contact_preference_set_at = models.DateTimeField(null=True, blank=True)
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    # Attribution publicitaire (capture first-touch du site)
    fbclid = models.CharField(max_length=500, blank=True, null=True)
    # Identifiant de clic Google Ads (first-touch du site, comme fbclid).
    # gbraid/wbraid (iOS) ne sont pas stockés : ils servent seulement à
    # classer le canal `google_ads` dans le webhook du site.
    gclid = models.CharField(max_length=255, blank=True, default='')
    utm_source = models.CharField(max_length=300, blank=True, null=True)
    utm_medium = models.CharField(max_length=300, blank=True, null=True)
    utm_campaign = models.CharField(max_length=300, blank=True, null=True)
    utm_content = models.CharField(max_length=300, blank=True, null=True)
    utm_term = models.CharField(max_length=300, blank=True, null=True)

    # ── ADSENG1 — Identifiants Meta natifs des leads Lead Ads (additifs,
    # nullable). Meta ne pousse JAMAIS campaign_name/adset_name dans le webhook
    # leadgen ; il pousse ad_id/adgroup_id/form_id (+ leadgen_id). On les
    # capture ici comme CLÉS DE JOINTURE STABLES vers les miroirs adsengine
    # (AdMirror.meta_id / AdSetMirror.meta_id / AdCampaignMirror.meta_id), là où
    # les utm_* (chaînes saisies) ne sont bons que pour l'affichage. Vides pour
    # tout lead non-Meta (site/appel/DM). L'attribution PAR VARIANTE (ADSENG6)
    # joint sur meta_ad_id.
    meta_ad_id = models.CharField(max_length=64, blank=True, null=True)
    meta_adset_id = models.CharField(max_length=64, blank=True, null=True)
    meta_campaign_id = models.CharField(max_length=64, blank=True, null=True)
    meta_form_id = models.CharField(max_length=64, blank=True, null=True)

    # ── QK1 — Qualification captée par le site (additifs, nullable) ──
    # Le site collecte ces signaux au moment de la capture. RÈGLE (décision
    # fondateur du 21/09/2026, CAD150/CAD159) : ces champs sont TOUJOURS
    # ÉDITABLES par la commerciale — un lead Meta, un walk-in ou un appel
    # entrant ne les a jamais reçus du site, et l'absence de `distributeur`
    # supprime la courbe de la proposition. La valeur venue du site reste
    # affichée avec sa PROVENANCE (« saisie sur le site le … »,
    # `selectors.provenance_site`), y compris après un écrasement fait en
    # connaissance de cause ; et la QUESTION n'est jamais reposée quand le
    # champ est rempli — elle revient pré-remplie, « à confirmer ».
    # (Remplace l'ancienne règle « jamais re-demandés, jamais édités ».)
    #: CAD150/CAD159 — les champs captés par le site que la fiche rend
    #: éditables avec leur provenance. Source unique (sélecteur, écran).
    CHAMPS_SITE = ('distributeur', 'roof_age', 'ownership', 'project_timeline',
                   'financing_intent', 'facility_type', 'bill_kwh')
    # CAD167 — la colonne passe de 12 à 20 caractères pour porter les codes
    # SRM (`srm_beni_mellal` = 15) ; élargissement pur, aucune valeur
    # existante n'est touchée.
    distributeur = models.CharField(
        max_length=20, choices=Distributeur.choices, blank=True, null=True,
        verbose_name="Distributeur d'électricité",
        help_text="Question à l'appel : AUCUNE — la SRM se DÉDUIT de la "
                  'ville du lead (règle CAD167). Le champ reste saisissable '
                  'pour corriger une déduction, et les libellés historiques '
                  '(ONEE, Lydec, Redal, Amendis) restent lisibles sur les '
                  'fiches déjà remplies. La valeur ne change AUCUN prix : le '
                  'barème est national et unique.')
    # Âge de la toiture en années (numérique simple ; NULL = inconnu).
    roof_age = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Âge de la toiture (ans)')
    ownership = models.CharField(
        max_length=12, choices=Ownership.choices, blank=True, null=True,
        verbose_name="Statut d'occupation")
    project_timeline = models.CharField(
        max_length=12, choices=ProjectTimeline.choices, blank=True, null=True,
        verbose_name='Horizon du projet')
    financing_intent = models.CharField(
        max_length=12, choices=FinancingIntent.choices, blank=True, null=True,
        verbose_name='Financement envisagé',
        help_text="Question à l'appel : « Pensez-vous payer comptant, ou "
                  'passer par un financement ? » (vide = pas encore posée). '
                  '« Crédit-bail » est une valeur INTERNE, jamais imprimée '
                  "avant l'avis juridique (D-CIQ-15).")
    # Charges futures prévues — liste de clés parmi FUTURES_CHARGES_KEYS
    # (clim / véhicule électrique / pompe). NULL = non renseigné.
    futures_charges = models.JSONField(
        null=True, blank=True,
        verbose_name='Charges futures prévues',
        help_text="Liste parmi 'clim', 've', 'pompe'.")

    # ── QW2 — Champs du site sans colonne d'accueil (additifs, nullable) ──
    # NOTE : `raisonSociale` du site RÉUTILISE `societe` (models.py ci-dessus)
    # — pas de colonne dédiée (consigne founder explicite).
    facility_type = models.CharField(
        max_length=12, choices=FacilityType.choices, blank=True, null=True,
        verbose_name='Type de site (pro)')
    site_count = models.CharField(
        max_length=4, choices=SiteCount.choices, blank=True, null=True,
        verbose_name='Nombre de sites (pro)')
    # Créneau de visite technique PRÉFÉRÉ (statique, jamais un RDV confirmé —
    # le rendez-vous réel reste QJ20 Appointment).
    visit_window_part = models.CharField(
        max_length=12, choices=VisitWindowPart.choices, blank=True, null=True,
        verbose_name='Créneau de visite préféré')
    visit_window_week = models.CharField(
        max_length=20, choices=VisitWindowWeek.choices, blank=True, null=True,
        verbose_name='Semaine de visite préférée')
    # Référence courte remise au client. WREF2 (fondateur 21/08/2026) : elle
    # est désormais ATTRIBUÉE PAR LE SERVEUR à la création du lead, au format
    # « NOM-N » (nom de famille tel que tapé + compteur, unique par société et
    # par nom — cf. `apps.crm.webhooks.assign_client_ref`). Le « TQ-XXXX »
    # tiré au hasard par le navigateur n'est plus qu'un code PROVISOIRE
    # d'affichage, conservé dans le payload brut, jamais écrit ici — les
    # fiches d'avant WREF2 le portent encore (le verbose_name ci-dessous date
    # de cette période). Clé de secours HUMAINE : le téléphone reste la clé de
    # rapprochement, il n'y a pas de contrainte d'unicité en base ici.
    client_ref = models.CharField(
        max_length=24, blank=True, null=True,
        verbose_name='Référence client (générée navigateur)')
    # WREF2-PONT (21/08/2026) — le code PROVISOIRE que le site a AFFICHÉ au
    # client (« TQ-XXXX », généré navigateur) quand la référence serveur
    # NOM-N a pris ``client_ref``. L'écran de succès relève la référence
    # serveur après coup (option B — ``public_lead_ref_views``) mais peut
    # échouer silencieusement : c'est alors CE code que le client dicte sur
    # WhatsApp. Indexé par les trois recherches, comme ``client_ref``.
    client_ref_provisoire = models.CharField(
        max_length=24, blank=True, null=True,
        verbose_name='Référence provisoire affichée par le site')
    # Diaspora/MRE : `phoneE164` étranger (indicatif ≠ 212) — une motion
    # commerciale distincte, badge-worthy (jamais utilisé pour qualifiesForCrm).
    phone_is_foreign = models.BooleanField(
        null=True, blank=True, verbose_name='Numéro étranger (diaspora/MRE)')
    # Première page de landing vue (first-touch) — capturée À LA CRÉATION de
    # la fiche : depuis le 18/08/2026 chaque soumission du site crée SA fiche
    # (apps/crm/webhooks.py), donc plus rien à protéger d'un « revenant ».
    page = models.CharField(
        max_length=300, blank=True, null=True,
        verbose_name='Page de landing (first-touch)')

    # ── Questionnaire quote-journey du site (pro/agricole) — additif ──
    # Réponses de dimensionnement SANS colonne d'accueil, clés snake_case
    # alignées sur le vocabulaire etude_params du générateur (water_source,
    # irrigation, besoin_m3j, tension_raccordement, puissance_kva…). Les
    # réponses qui ONT déjà une colonne (HMT/débit/CV pompe → pompe_*,
    # kWh/MAD pro → bill_kwh/facture_hiver) sont mappées sur ces colonnes
    # par le webhook (apps/crm/webhooks.py) et ne sont PAS dupliquées ici.
    web_questionnaire = models.JSONField(
        default=dict, blank=True,
        verbose_name='Questionnaire web (quote-journey)')
    # Chiffres MONTRÉS au visiteur au moment de la capture (kwc, prodKwh,
    # ecoMad*, paybackLabel, pompeCv, champKwc, m3Jour…) — snapshot verbatim
    # re-whitelisté CÔTÉ SERVEUR (webhooks._clean_estimate_shown), jamais
    # recalculé : c'est la promesse vue par le prospect, pas une étude.
    web_estimate = models.JSONField(
        default=dict, blank=True,
        verbose_name='Estimation montrée (web)')

    note = models.TextField(blank=True, null=True)

    # FG28 — Horodatage de la PREMIÈRE prise de contact (set server-side dès
    # que le stage sort de NEW ou qu'une note de contact est enregistrée).
    # Nullable : NULL = jamais contacté. Permet le calcul du délai de réponse
    # et l'alerte SLA « non contacté > Xh » (filtre kanban + badge rouge).
    first_contacted_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Premier contact à',
    )

    # ── Archivage réversible (2026-06-13) — additif ──
    # Un lead archivé disparaît des vues par défaut (kanban/liste/calendrier/
    # graphique) mais reste filtrable (« Archivés ») et restaurable. La
    # suppression définitive reste un geste admin distinct (destroy).
    is_archived = models.BooleanField(default=False)
    # Champs personnalisés (T11) — valeurs indexées par CustomFieldDef.code.
    custom_data = models.JSONField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads_archives',
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    # VX98 — dernier auteur d'une modification (posé server-side dans
    # perform_update, jamais accepté du corps de requête). Alimente la puce de
    # fraîcheur « modifié par X il y a N min » (silencieuse si NULL ou si c'est
    # l'utilisateur courant). Pattern identique à archived_by ; date_modification
    # (auto_now) porte l'horodatage.
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads_modifies',
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    # CAD119 (audit L3 du 21/09/2026) — LA VRAIE DATE DE CRÉATION DU SYSTÈME
    # D'ORIGINE. ``date_creation`` est en ``auto_now_add`` : tous les leads
    # importés portaient la date de la SYNCHRONISATION, et la vraie date
    # finissait dans une note en texte libre (« Créé dans Odoo: … ») que
    # personne ne peut requêter. Le modèle à copier existait à côté : la
    # création Meta repose déjà ``date_creation`` sur la vraie heure d'arrivée.
    # Sans ce champ, tout futur import de rattrapage fausserait de nouveau les
    # KPI de délai (CAD87).
    #
    # NULL = aucune date d'origine connue (lead natif, ou ligne d'avant
    # CAD119) — c'est la vérité ; la lecture retombe alors sur
    # ``date_creation`` via la propriété ``date_origine``.
    date_creation_origine = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Date de création dans le système d'origine",
        help_text="Quand ce dossier est-il né chez le système qui nous l'a "
                  "transmis (Odoo, import) ? Vide si créé ici.",
    )

    # QJ6 — Score de qualité calculé (0–100) et persisté pour un tri
    # pagination-safe. Recalculé à chaque création/mise à jour du lead
    # (services.recompute_lead_score). NULL sur les leads importés avant la
    # migration (backfill optionnel au premier accès).
    score = models.IntegerField(
        null=True, blank=True,
        verbose_name='Score de qualité',
        help_text='Score 0–100 calculé automatiquement (voir scoring.py).',
    )

    # CRX22 — ajustement PERSISTANT du score, additif au calcul.
    # Avant, une automatisation qui écrivait ``score`` directement voyait son
    # delta effacé au premier ``recompute_lead_score`` (édition du lead, job
    # nocturne…). Le delta vit maintenant dans SA propre colonne, appliquée
    # PAR le calcul (``scoring.compute_score``) : il survit à tout recalcul.
    # NULL = aucun ajustement (comportement historique strictement inchangé) ;
    # colonne nullable sans défaut → aucune réécriture des lignes existantes.
    score_ajustement = models.SmallIntegerField(
        null=True, blank=True,
        verbose_name='Ajustement du score',
        help_text="Delta (positif ou négatif) ajouté au score calculé. "
                  "Survit aux recalculs. Vide = aucun ajustement.",
    )

    # XMKT21 — horodatage de l'assignation automatique MQL (franchissement du
    # seuil de score société). NULL tant que le lead n'a jamais franchi le
    # seuil : marqueur d'idempotence (une seule assignation+notification par
    # lead), jamais réinitialisé si le score redescend puis remonte.
    mql_assigned_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Assigné MQL le',
        help_text='Horodatage de la première assignation automatique '
                  'déclenchée par le franchissement du seuil MQL (XMKT21).',
    )

    # ── QW10 — Colonnes de dédup NORMALISÉES + indexées (additif) ──
    # `find_duplicates_by_contact` itérait TOUS les leads d'une société en
    # Python à chaque webhook (O(N), cible d'amplification sur un endpoint à
    # secret statique). Ces colonnes sont maintenues en écriture (voir
    # `save()`) à partir des mêmes normaliseurs (`services.normalize_phone` /
    # `normalize_email`) : la recherche devient une requête indexée, pas un
    # scan. Vide ('') plutôt que NULL pour rester indexable simplement (une
    # valeur vide n'est jamais un doublon — filtrée côté requête).
    phone_normalise = models.CharField(
        max_length=20, blank=True, default='', db_index=True,
        verbose_name='Téléphone normalisé (dédup)')
    email_normalise = models.CharField(
        max_length=254, blank=True, default='', db_index=True,
        verbose_name='Email normalisé (dédup)')
    # ACRM32 — clé normalisée du WHATSAPP (même normaliseur que
    # ``phone_normalise``) : un message WhatsApp d'un numéro connu SEULEMENT
    # en ``whatsapp`` retrouve son lead par une requête indexée.
    whatsapp_normalise = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='WhatsApp normalisé (dédup)')

    # T-TRACE (25/08/2026) — identifiant de l'APPAREIL depuis lequel la
    # demande est arrivée (uuid localStorage posé par le site, transmis par
    # le webhook lead). C'est la clé qui relie une fiche aux visites ANONYMES
    # qui l'ont précédée (``crm.VisiteExterne``) et qui déclenche l'alerte
    # « possible doublon/concurrent » quand DEUX leads de la même société
    # partagent le même appareil. NULL = inconnu (anciens leads, imports,
    # saisie manuelle) — jamais un défaut inventé.
    appareil_id = models.CharField(
        max_length=64, null=True, blank=True,
        verbose_name='Identifiant d’appareil (traçage)')

    # NTADM2 — rattachement OPTIONNEL à une entité intra-tenant (holding /
    # filiale / agence, cf. apps.entites). NULL = « non affecté » : aucun
    # backfill, aucune liste filtrée d'office — comportement STRICTEMENT
    # identique tant que le champ n'est pas renseigné. FK-STRING cross-app :
    # jamais d'import de ``apps.entites.models`` ici.
    entite = models.ForeignKey(
        'entites.Entite',
        # on_delete: supprimer une entité ne doit JAMAIS effacer un lead — la
        # ligne redevient « non affectée » (SET_NULL), jamais une cascade sur
        # du pipeline commercial.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='crm_leads',
        verbose_name='Entité',
    )

    # ── CAD-L ── CAD149 — VAGUE 1 du script d'appel guidé (audit L3 du
    # 21/09/2026, liste arrêtée par le fondateur — CAD160 : huit champs, ni
    # plus ni moins). Tous ``null=True`` : vide = « la question n'a pas encore
    # été posée », JAMAIS une réponse. Le ``help_text`` de chaque champ EST la
    # question orale (règle du bloc L4 ci-dessus) — l'UI CRM la lit d'ici, on
    # ne la recopie nulle part. Les trois derniers PROMEUVENT en colonne des
    # réponses qui vivaient dans le sac ``web_questionnaire``, en gardant le
    # vocabulaire déjà émis par le site.
    type_bien = models.CharField(
        max_length=12, choices=TypeBien.choices, null=True, blank=True,
        verbose_name='Type de bien',
        help_text="Question à l'appel : « De quel type de bien s'agit-il "
                  '— villa, appartement, immeuble, riad, ferme ? » '
                  "(vide = pas encore posée). Remplace l'idée de faire "
                  'saisir le type de toit au téléphone : ce chemin-là est '
                  'fermé depuis la décision du 18/08/2026.')
    objectif_projet = models.CharField(
        max_length=16, choices=ObjectifProjet.choices, null=True, blank=True,
        verbose_name='Objectif du projet',
        help_text="Question à l'appel : « Qu'est-ce qui compte le plus pour "
                  'vous — baisser la facture, tenir pendant les coupures, '
                  "gagner en autonomie ? » (vide = pas encore posée). "
                  '« Revendre le surplus » ne se coche QUE si le client en '
                  'parle lui-même : ce n’est jamais proposé à l’appel. '
                  '« Tenir pendant les coupures » est un ARGUMENT : aucun '
                  'dimensionnement de secours n’en découle.')
    decideur = models.CharField(
        max_length=20, choices=Decideur.choices, null=True, blank=True,
        verbose_name='Qui décide',
        help_text="Question à l'appel : « Qui décide avec vous de ce "
                  'projet ? » (vide = pas encore posée). Renseigné à '
                  '« avec le conjoint / la famille » ou « avec un associé / '
                  'la direction », il pose l’étiquette « Décision à '
                  'plusieurs » qui pilote la touche du dimanche en famille. '
                  'Question ORALE uniquement : jamais dans le questionnaire '
                  'envoyé au client.')
    devis_concurrents = models.CharField(
        max_length=10, choices=DevisConcurrents.choices, null=True,
        blank=True, verbose_name='Autres devis en cours',
        help_text="Question à l'appel : « Avez-vous déjà reçu ou demandé "
                  'un autre devis ? » (vide = pas encore posée). État de la '
                  'comparaison EN COURS — le post-mortem d’une affaire '
                  'perdue reste, lui, dans la fiche « concurrent ». '
                  'Question ORALE uniquement.')
    equip_ve_statut = models.CharField(
        max_length=10, choices=EquipVeStatut.choices, null=True, blank=True,
        verbose_name='Véhicule électrique — déjà là ou prévu ?',
        help_text="Question à l'appel : « Ce véhicule électrique, vous "
                  "l'avez déjà, ou c'est un projet ? » (vide = pas encore "
                  'posée). Précise le « avez-vous OU prévoyez-vous » du '
                  'champ véhicule électrique : une voiture seulement PRÉVUE '
                  'reste comptée, et le devis comme la proposition portent '
                  'alors l’étiquette « avec votre future voiture » — sans '
                  'elle, le chiffre mentirait.')
    pompage_heures_jour = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        verbose_name='Pompage — heures par jour',
        help_text="Question à l'appel : « Combien d'heures par jour la "
                  'pompe ACTUELLE tourne-t-elle ? » (h/jour, vide = pas '
                  'encore posée). Heures de la pompe ACTUELLE : elles '
                  'servent seulement à estimer un volume déclaré (débit '
                  'actuel × heures), jamais des heures de pompage solaire. '
                  'Colonne dédiée de la réponse que le site envoie déjà sous '
                  '« heures de pompage ».')
    pompe_alim_actuelle = models.CharField(
        max_length=12, choices=PompeAlimActuelle.choices, null=True,
        blank=True, verbose_name='Pompe actuelle — alimentation',
        help_text="Question à l'appel : « Votre pompe actuelle marche à "
                  'quoi — diesel, butane, électricité, ou vous n’en avez '
                  'pas ? » (vide = pas encore posée). Colonne dédiée de la '
                  'réponse déjà émise par le site, butane compris.')
    carburant_litres_mois = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        verbose_name='Carburant consommé (litres/mois)',
        help_text="Question à l'appel : « Combien de litres de carburant "
                  'la pompe consomme-t-elle par mois ? » (litres/mois, vide '
                  '= pas encore posée). C’est l’unité qui manquait à côté '
                  'de la dépense en dirhams : l’économie de carburant se '
                  'calcule sur ce que le client DÉCLARE, aucun prix de '
                  'gasoil de référence n’est écrit nulle part.')

    # ── CAD-L ── CAD154 — VAGUE 2 du script d'appel guidé : cinq besoins
    # réels qui ne bloquaient pas l'appel 1 (liste arrêtée par le fondateur —
    # CAD160). Mêmes règles que la vague 1 : ``null=True`` (vide = question
    # pas encore posée), et le ``help_text`` EST la question orale. AUCUN de
    # ces champs ne porte un marqueur de provenance énergie/toiture — il n'y
    # a donc aucune exclusion à motiver dans `selectors.py`.
    nb_personnes_foyer = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Nombre de personnes au foyer',
        help_text="Question à l'appel : « Combien de personnes vivent dans "
                  'ce logement ? » (vide = pas encore posée). Le moteur dit '
                  "lui-même que son absence l'empêche de chiffrer le "
                  "chauffe-eau par ordre de grandeur : sans ce nombre, la "
                  'couche est OMISE plutôt qu’inventée.')
    budget_client_mad = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Budget annoncé par le client (MAD)',
        help_text="Question à l'appel, APRÈS l'envoi du devis seulement "
                  '(décision fondateur du 21/09/2026) : « Quel budget '
                  'aviez-vous en tête ? » (vide = pas encore posée). '
                  "DISTINCT du montant estimé, qui est l'estimation du "
                  'COMMERCIAL et nourrit le forecast pondéré. Question '
                  'ORALE : jamais dans le questionnaire envoyé au client.')
    frein_principal = models.CharField(
        max_length=12, choices=FreinPrincipal.choices, null=True, blank=True,
        verbose_name='Frein principal',
        help_text="Question à l'appel : « Qu'est-ce qui vous retient "
                  'aujourd’hui ? » (vide = pas encore posée). Même '
                  'vocabulaire que la qualification de visite, pour que le '
                  'terrain et le téléphone se relisent. Question ORALE.')
    declencheur = models.CharField(
        max_length=12, choices=Declencheur.choices, null=True, blank=True,
        verbose_name='Ce qui a accroché',
        help_text="Question à l'appel : « Qu'est-ce qui vous a donné envie "
                  'de vous renseigner ? » (vide = pas encore posée). Même '
                  'vocabulaire que la qualification de visite. Question '
                  'ORALE.')
    compteur_puissance_kva = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name='Puissance souscrite du compteur (kVA)',
        help_text="Question à l'appel : « Quelle est votre puissance "
                  'souscrite, en kVA ? Elle est écrite sur votre facture ou '
                  'votre contrat. » (vide = pas encore posée).')
    chauffage_electrique_hiver = models.BooleanField(
        null=True, blank=True, verbose_name='Chauffage électrique en hiver',
        help_text="Question à l'appel : « Vous chauffez-vous à l'électricité "
                  "en hiver ? » (Oui/Non — vide = pas encore posée). Champ "
                  'INFORMATIF : décision fondateur du 21/09/2026 — aucune '
                  "couche de chauffage d'hiver n'est composée, donc il "
                  'n’ajuste AUCUNE courbe.')

    # ── CIQ401 (contrat CIQ1 ``lead_pro.json``) — colonnes du lead PRO ──────
    # Toutes nullables : vide = question pas encore posée, jamais une valeur
    # par défaut enregistrée comme une réponse. Chaque colonne posée au
    # téléphone porte sa question (libellé neutre ; la variante par segment
    # vit dans ``questions_pro``). Les colonnes ``*_source`` sont posées par
    # le SERVEUR selon le chemin d'écriture (fiche/appel → ``declare`` ;
    # webhook → ``site_web``/``site_defaut_visible`` ; visite →
    # ``mesure_visite``), jamais saisies à la main.
    tension_raccordement = models.CharField(
        max_length=12, choices=TensionRaccordement.choices, null=True,
        blank=True, verbose_name='Tension de raccordement',
        help_text="Question à l'appel : « Votre site est-il raccordé en "
                  'basse tension, avec un compteur ordinaire, ou en moyenne '
                  'tension, avec un poste de transformation ? Si vous ne '
                  "savez pas, ce n'est pas grave. » (vide = pas encore "
                  'posée).')
    tension_source = models.CharField(
        max_length=20, choices=TensionSource.choices, null=True, blank=True,
        verbose_name='Provenance de la tension')
    contrat_electricite = models.CharField(
        max_length=20, choices=ContratElectricite.choices, null=True,
        blank=True, verbose_name="Contrat d'électricité",
        help_text="Question à l'appel : « Quel est votre contrat "
                  "d'électricité : basse tension patenté, force motrice, "
                  'domestique, ou moyenne tension ? Il est écrit sur votre '
                  'facture. » (CIQ666 ; vide = pas encore posée, « ne sait '
                  "pas » = aucun contrat transmis au devis automatique).")
    option_tarifaire_bt = models.CharField(
        max_length=12, choices=OptionTarifaireBt.choices, null=True,
        blank=True, verbose_name='Option tarifaire BT',
        help_text="Question à l'appel : « En force motrice, êtes-vous en "
                  'option normale ou en option bi-horaire ? » (CIQ666 ; '
                  'seule la force motrice ouvre le bi-horaire ; vide = pas '
                  'encore posée).')
    puissance_souscrite_source = models.CharField(
        max_length=14, choices=PuissanceSouscriteSource.choices, null=True,
        blank=True, verbose_name='Provenance de la puissance souscrite')
    categorie_commerciale = models.CharField(
        max_length=12, choices=CategorieCommerciale.choices, null=True,
        blank=True, verbose_name='Activité (catégorie commerciale)',
        help_text="Question à l'appel : « Quelle est votre activité : hôtel, "
                  'restaurant ou café, commerce, bureaux, santé, école, '
                  'hammam, boulangerie, froid, ou autre chose ? » (vide = '
                  'pas encore posée).')
    reponses_categorie = models.JSONField(
        null=True, blank=True, verbose_name="Réponses propres à l'activité",
        help_text="Question à l'appel : « Les questions propres à votre "
                  'activité » (chambres, couverts, chambres froides…), '
                  "posées juste après l'activité. Clés FERMÉES par catégorie "
                  '(``REPONSES_CATEGORIE_CLES``).')
    secteur_industriel = models.CharField(
        max_length=120, null=True, blank=True,
        verbose_name='Secteur industriel',
        help_text="Question à l'appel : « Que fabriquez-vous ou que "
                  'transformez-vous sur ce site ? » (vide = pas encore '
                  'posée).')
    export_ue_declare = models.CharField(
        max_length=3, choices=OuiNon.choices, null=True, blank=True,
        verbose_name="Exporte vers l'Union européenne",
        help_text="Question à l'appel : « Exportez-vous une partie de votre "
                  "production vers l'Union européenne ? » (vide = pas encore "
                  'posée).')
    regime_equipes = models.CharField(
        max_length=12, choices=RegimeEquipes.choices, null=True, blank=True,
        verbose_name='Régime des équipes',
        help_text="Question à l'appel : « Travaillez-vous en une équipe de "
                  'jour, en deux équipes, en trois équipes, ou en continu ? » '
                  '(vide = pas encore posée).')
    jours_ouverture = models.JSONField(
        null=True, blank=True, validators=[valider_jours_ouverture],
        verbose_name="Jours d'ouverture",
        help_text="Question à l'appel : « Quels jours de la semaine êtes-vous "
                  'ouverts ou en production ? » (entiers 1 = lundi à 7 = '
                  'dimanche ; vide = pas encore posée).')
    heure_debut = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(24)],
        verbose_name='Heure de début de journée',
        help_text="Question à l'appel : « À quelle heure commence votre "
                  'journée de travail ? » (0-24 ; vide = pas encore posée).')
    heure_fin = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(24)],
        verbose_name='Heure de fin de journée',
        help_text="Question à l'appel : « Et à quelle heure se termine-t-"
                  'elle ? » (0-24 ; vide = pas encore posée).')
    fermeture_mois = models.JSONField(
        null=True, blank=True, validators=[valider_fermeture_mois],
        verbose_name='Mois de fermeture',
        help_text="Question à l'appel : « Fermez-vous certains mois de "
                  "l'année, pour des congés ou une saison creuse ? "
                  'Lesquels ? » (entiers 1-12 ; vide = pas encore posée).')
    type_surface = models.CharField(
        max_length=10, choices=TypeSurface.choices, null=True, blank=True,
        verbose_name='Type de surface',
        help_text="Question à l'appel : « Où pourrait-on poser les panneaux : "
                  'sur la toiture, sur une ombrière de parking, ou sur un '
                  'terrain ? » (vide = pas encore posée).')
    surface_source = models.CharField(
        max_length=14, choices=SurfaceSource.choices, null=True, blank=True,
        verbose_name='Provenance de la surface')
    groupe_electrogene = models.CharField(
        max_length=3, choices=OuiNon.choices, null=True, blank=True,
        verbose_name='Groupe électrogène',
        help_text="Question à l'appel : « Avez-vous un groupe électrogène "
                  'sur le site ? » (vide = pas encore posée).')
    groupe_kva = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Groupe électrogène — puissance (kVA)',
        help_text="Question à l'appel : « Quelle est sa puissance, en "
                  'kVA ? » (vide = pas encore posée).')
    groupe_litres_mois = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        verbose_name='Groupe électrogène — gasoil (L/mois)',
        help_text="Question à l'appel : « Combien de litres de gasoil "
                  'consomme-t-il par mois ? » (vide = pas encore posée).')
    groupe_depense_mad_mois = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Groupe électrogène — dépense (MAD/mois)',
        help_text="Question à l'appel : « Combien dépensez-vous en gasoil "
                  'pour le groupe chaque mois ? » (DÉCLARÉ seulement, jamais '
                  'un prix pré-rempli — Q17 ; vide = pas encore posée).')
    pv_existant_kwc = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        verbose_name='Photovoltaïque existant (kWc)',
        help_text="Question à l'appel : « Avez-vous déjà des panneaux "
                  'solaires installés ? De quelle puissance ? » (vide = pas '
                  'encore posée).')
    cos_phi = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True,
        validators=[valider_cos_phi], verbose_name='Cos φ',
        help_text="Question à l'appel : « Votre facture indique-t-elle un "
                  "cosinus phi ou une pénalité d'énergie réactive ? Quelle "
                  'valeur ? » (jamais supposé ; vide = pas encore posée).')
    cos_phi_source = models.CharField(
        max_length=14, choices=CosPhiSource.choices, null=True, blank=True,
        verbose_name='Provenance du cos φ')
    releve_conso = models.JSONField(
        null=True, blank=True, validators=[valider_releve_conso],
        verbose_name='Relevé mensuel de consommation',
        help_text="Question à l'appel : « Pouvez-vous nous envoyer vos "
                  "dernières factures d'électricité ? Jusqu'à douze mois nous "
                  'aident à être précis. » (au plus 12 mois, jamais exigés '
                  'tous les douze ; vide = pas encore posée).')
    tva_recuperable = models.CharField(
        max_length=12, choices=TvaRecuperable.choices, null=True,
        blank=True, verbose_name='TVA récupérable',
        help_text="Question à l'appel : « Votre entreprise récupère-t-elle "
                  'la TVA sur ses achats ? » (D-CIQ-3 ; vide = pas encore '
                  'posée).')
    ice = models.CharField(
        max_length=30, null=True, blank=True, verbose_name='ICE',
        help_text="Question à l'appel : « Pouvez-vous nous donner l'ICE de "
                  "l'entreprise ? Il figurera sur le devis et la facture. » "
                  '(texte libre ; demandé, jamais bloquant au devis — '
                  'D-CIQ-11).')
    rc = models.CharField(
        max_length=30, null=True, blank=True,
        verbose_name='Registre de commerce (RC)',
        help_text="Question à l'appel : « Et son numéro de registre de "
                  'commerce ? » (vide = pas encore posée).')
    if_fiscal = models.CharField(
        max_length=30, null=True, blank=True,
        verbose_name='Identifiant fiscal (IF)',
        help_text="Question à l'appel : « Et l'identifiant fiscal ? » (vide "
                  '= pas encore posée).')
    adresse_siege = models.TextField(
        null=True, blank=True, verbose_name='Adresse du siège',
        help_text="Question à l'appel : « Quelle est l'adresse du siège, si "
                  'elle diffère de celle du site ? » (vide = pas encore '
                  'posée).')
    fonction_contact = models.CharField(
        max_length=120, null=True, blank=True,
        verbose_name='Fonction du contact',
        help_text="Question à l'appel : « Quelle est votre fonction dans "
                  "l'entreprise ? » (vide = pas encore posée).")
    contact_secondaire_fonction = models.CharField(
        max_length=120, null=True, blank=True,
        verbose_name='Contact secondaire (fonction)',
        help_text="Question à l'appel : « Qui d'autre décide avec vous ? "
                  'Quelle est sa fonction ? » (CAD144 : sans automatisation '
                  '; vide = pas encore posée).')
    contact_secondaire_email = models.EmailField(
        null=True, blank=True, verbose_name='Contact secondaire (e-mail)',
        help_text="Question à l'appel : « Pouvons-nous lui envoyer le devis "
                  'par e-mail ? À quelle adresse ? » (jamais utilisé par la '
                  'cadence ; vide = pas encore posée).')
    facture_tranche_declaree = models.JSONField(
        null=True, blank=True, validators=[valider_facture_tranche_declaree],
        verbose_name='Tranche de facture déclarée',
        help_text="Question à l'appel : « Votre facture mensuelle se situe "
                  'dans quelle tranche ? » — D-CIQ-19 : une tranche OUVERTE '
                  "(« plus de 4 000 DH ») n'est JAMAIS stockée comme un "
                  'montant.')

    def save(self, *args, **kwargs):
        # QW10 — maintient les colonnes de dédup normalisées à chaque save,
        # quelle que soit la voie d'écriture (webhook, admin, API, import) —
        # source unique de vérité : `apps.crm.services` (jamais dupliquée ici).
        from . import leads_doublons as _crm_doublons
        self.phone_normalise = _crm_doublons.normalize_phone(self.telephone) or ''
        self.email_normalise = _crm_doublons.normalize_email(self.email) or ''
        # ACRM32 — idem pour le WhatsApp (tronqué comme la colonne).
        self.whatsapp_normalise = (
            _crm_doublons.normalize_phone(self.whatsapp) or '')[:20]
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'source']),
            models.Index(fields=['company', 'stage']),
            models.Index(fields=['company', 'score'], name='crm_lead_company_score_idx'),
            # QW10 — dédup indexée (téléphone/email normalisés), remplace le
            # scan Python complet de `find_duplicates_by_contact`.
            models.Index(fields=['company', 'phone_normalise'],
                         name='crm_lead_phone_norm_idx'),
            models.Index(fields=['company', 'email_normalise'],
                         name='crm_lead_email_norm_idx'),
            # ACRM32 — dédup indexée sur le WhatsApp normalisé.
            models.Index(fields=['company', 'whatsapp_normalise'],
                         name='crm_lead_wa_norm_idx'),
            # ADSENG1/ADSENG6 — jointure d'attribution PAR VARIANTE : on
            # regroupe les leads d'une société par leur ad Meta (meta_ad_id).
            models.Index(fields=['company', 'meta_ad_id'],
                         name='crm_lead_meta_ad_idx'),
            # T-TRACE — « quels AUTRES leads de cette société partagent cet
            # appareil ? » est posée à CHAQUE création de lead : indexée, donc
            # jamais un scan de la table leads sur le chemin du webhook.
            models.Index(fields=['company', 'appareil_id'],
                         name='crm_lead_appareil_idx'),
        ]
        constraints = [
            # An imported record is unique per (company, system, external id) so
            # a re-run of the import does not create duplicates.
            models.UniqueConstraint(
                fields=['company', 'external_system', 'external_id'],
                name='uniq_lead_external_ref',
                condition=models.Q(external_id__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenom or ''} [{self.stage}]".strip()

    # ── CAD-K ── CAD119 ─────────────────────────────────────────────────
    @property
    def date_origine(self):
        """La date qui DATE ce dossier : celle du système d'origine si on la
        connaît, sinon celle de son insertion ici.

        Tout KPI de délai doit passer par ici : mesurer « joint sous 5 jours »
        depuis la date d'une SYNCHRONISATION répond à une question que
        personne ne pose."""
        return self.date_creation_origine or self.date_creation


class WebsiteLeadPayload(models.Model):
    """Charge utile BRUTE reçue d'une source d'intake — stockée AVANT tout
    mapping.

    Garantie « jamais perdre un lead » : même si le mapping vers Lead échoue
    (payload inattendu, bug, panne du Graph API), la donnée d'origine est
    conservée telle quelle et rejouable. Aucune logique métier ici.

    CRX2 — le modèle sert désormais LES DEUX intakes (le nom historique est
    conservé : renommer la table coûterait plus qu'il ne rapporte). ``source``
    dit lequel, et pilote le chemin de rejeu choisi par l'action ``replay``
    (``webhooks.replay_website_lead_payload`` / ``replay_meta_lead_payload``).
    """

    class Source(models.TextChoices):
        WEBSITE = 'website', 'Site web'
        META_LEAD_ADS = 'meta_lead_ads', 'Meta Lead Ads'

    #: Intake d'origine. Défaut ``website`` : toutes les lignes existantes
    #: viennent du webhook site (seul émetteur avant CRX2).
    source = models.CharField(
        max_length=32, choices=Source.choices, default=Source.WEBSITE,
        db_index=True)
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='website_lead_payloads',
    )
    payload = models.JSONField()
    remote_addr = models.CharField(max_length=64, blank=True, null=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)
    lead = models.ForeignKey(
        Lead, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='website_payloads')

    class Meta:
        verbose_name = 'Payload lead entrant'
        verbose_name_plural = 'Payloads leads entrants'
        ordering = ['-received_at']

    def __str__(self):
        return (f"payload #{self.pk} [{self.source}] "
                f"({'ok' if self.processed else 'brut'})")


class LeadActivity(models.Model):
    """Historique « chatter » d'un lead (style Odoo), modèle maison.

    Deux familles d'entrées :
      - automatiques : création du lead et changements de champs suivis
        (champ, ancienne valeur, nouvelle valeur, utilisateur, horodatage) —
        écrites côté serveur au niveau de l'API, jamais par le navigateur ;
      - manuelles : notes libres (appel passé, commentaire…).
    """

    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'
        # FG30 — Interactions de communication typées
        APPEL = 'appel', 'Appel'
        EMAIL = 'email', 'E-mail'
        # MRY10 — un WhatsApp ENVOYÉ est une prise de contact au même titre
        # qu'un e-mail : sans son propre type il se noyait dans les notes,
        # invisible au compteur de tentatives comme au chatter.
        WHATSAPP = 'whatsapp', 'WhatsApp'

    # FG30 — Résultat optionnel d'un appel ou e-mail (affiché dans le chatter).
    OUTCOMES = [
        ('',        '—'),
        ('joint',   'Joint'),
        ('non_joint', 'Non joint'),
        ('rappel',  'À rappeler'),
        ('refuse',  'Refus'),
        ('interesse', 'Intéressé'),
        # VISITE-CADENCE (fondateur 15/09/2026) — une issue de succès d'un
        # genre nouveau : le client n'a ni signé ni refusé, il a accepté de
        # RECEVOIR le technicien. Elle n'arrête pas la cadence (la proposition
        # reste à relancer si la visite tombe à l'eau) mais elle remplace le
        # geste générique suivant par le seul qui compte : caler la date.
        ('visite_acceptee', 'Visite acceptée'),
    ]
    outcome = models.CharField(
        max_length=20, blank=True, default='',
        choices=OUTCOMES,
        verbose_name="Résultat de l'interaction",
    )

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='lead_activities',
    )
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name='activites')  # on_delete: historique/chatter de Lead — suit son objet
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    # VX111 — pièce jointe optionnelle sur une note manuelle (kind='note'),
    # ex. photo prise depuis mobile pendant une visite. RÉUTILISE le magasin
    # `records.Attachment` existant (déjà whitelisté ('crm','lead')) — jamais
    # un second magasin de fichiers. SET_NULL : la note reste lisible même si
    # la pièce jointe est supprimée indépendamment (ex. depuis AttachmentsPanel).
    attachment = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lead_notes',
        verbose_name='Pièce jointe',
    )
    # Marque une entrée issue d'une action « en masse » (édition groupée de
    # plusieurs leads) — l'Historique l'affiche avec un badge « en masse ».
    bulk = models.BooleanField(default=False)
    # LW28 — note épinglée : mise en avant hors chronologie en tête de
    # l'Historique (`historique/` trie `(-pinned, -created_at)`). Additif,
    # défaut False → comportement historique strictement inchangé.
    pinned = models.BooleanField(default=False, verbose_name='Épinglée')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lead_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité lead'
        verbose_name_plural = 'Activités lead'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['lead', '-created_at'])]

    def __str__(self):
        return f"{self.lead_id} {self.kind} {self.field or ''}".strip()


class LeadTag(models.Model):
    """Étiquette de lead gérée (Paramètres → CRM). Le champ Lead.tags reste un
    texte libre ; cette liste sert de suggestions + couleurs. Additif."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True, related_name='lead_tags')
    nom = models.CharField(max_length=80)
    couleur = models.CharField(max_length=7, blank=True, default='')
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Étiquette de lead'

    def __str__(self):
        return self.nom


class Canal(models.Model):
    """Canal / source de lead géré (Paramètres → CRM). Le champ Lead.canal reste
    une clé texte ; cette liste pilote le sélecteur et les libellés. Additif.

    `cle` = clé stockée sur Lead.canal (ex. 'site_web'). `protege` verrouille un
    canal critique contre le renommage/la suppression : 'site_web' est utilisé
    par le webhook du site web — le supprimer/renommer casserait le pipeline."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True, related_name='canaux')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=80)
    ordre = models.PositiveIntegerField(default=0)
    protege = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = 'Canal de lead'
        verbose_name_plural = 'Canaux de lead'

    def __str__(self):
        return self.libelle


class MotifPerte(models.Model):
    """Motif de perte géré (Paramètres → CRM). Le champ Lead.motif_perte reste
    un texte libre ; cette liste sert de choix proposés. Additif.

    PUB28 — ``est_junk`` distingue un motif de perte JUNK (numéro invalide,
    spam/bot, hors zone, jamais répondu — le lead n'était jamais un prospect
    réel) d'un motif RÉEL (prix, concurrent, reporté — un vrai prospect perdu
    pour une raison commerciale). Sert le signal qualité manquant au veto de
    divergence : le taux de junk PAR AD (``apps.adsengine.attribution``)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True, related_name='motifs_perte')
    nom = models.CharField(max_length=150)
    archived = models.BooleanField(default=False)
    est_junk = models.BooleanField(
        default=False, verbose_name='Motif junk (pas un vrai prospect)',
        help_text='Numéro invalide, spam/bot, hors zone, jamais répondu — '
                  'distinct d\'un motif de perte commercial réel.')

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Motif de perte'

    def __str__(self):
        return self.nom


class MotifPerteStandardPropose(TenantModel):
    """ACRM25 (C-ACRM-018) — la MÉMOIRE des motifs de perte STANDARD déjà
    proposés à une société.

    ``completer_motifs_perte`` ajoutait à CHAQUE lecture de la liste tout
    motif standard absent par son NOM : un motif renommé (« Prix » → « Prix
    trop élevé ») ou supprimé revenait aussitôt. Un motif standard n'est
    désormais proposé qu'UNE fois par société — renommé ou supprimé ensuite,
    il ne ressuscite jamais ; un motif standard AJOUTÉ plus tard au référentiel
    (AGR521, CIQ514…) est, lui, toujours proposé une fois.

    SCA4 — hérite de ``core.models.TenantModel`` (company + created_at/updated_at) ;
    ``company`` redéclaré pour garder ``related_name='+'``."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: mémoire de référentiel 100 % fille du tenant
        related_name='+')
    nom = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'Motif de perte standard proposé'
        verbose_name_plural = 'Motifs de perte standard proposés'
        unique_together = [('company', 'nom')]

    def __str__(self):
        return self.nom


class Appointment(models.Model):
    """QJ20 — Rendez-vous (visite commerciale/technique) planifié sur un lead.

    Modèle additif. Un lead peut avoir plusieurs rendez-vous ; le statut suit
    le cycle de vie (planifié → confirmé → effectué / annulé). Company scopé :
    un rendez-vous appartient à la société du lead. La date planifiée est
    stockée en UTC (convention Django) ; l'UI affiche l'heure locale marocaine
    (Africa/Casablanca).

    RAMADAN-AWARE PACING (``ramadan_pacing``): champ booléen sur la société
    (voir ``Appointment.RAMADAN_AVOID_HOURS``) — quand activé, les rappels
    ne sont PAS envoyés pendant la plage horaire iftar-sensible (défaut :
    18 h – 21 h Casablanca). Le service de rappel consulte ce drapeau avant
    d'envoyer. Aucune dépendance externe : le drapeau est simplement posé par
    l'utilisateur dans les réglages, et la logique est documentée ici.
    """

    # Heures (locales Casablanca) à éviter quand le drapeau Ramadan est actif.
    # Plage iftar-sensible (simplifié : 18h–21h). Documenté ici pour référence.
    RAMADAN_AVOID_START_H = 18
    RAMADAN_AVOID_END_H = 21

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        CONFIRME = 'confirme', 'Confirmé'
        EFFECTUE = 'effectue', 'Effectué'
        ANNULE = 'annule', 'Annulé'
        # PUB37 — additif, DISTINCT d'ANNULE : le prospect ne s'est jamais
        # présenté (vs un RDV annulé À L'AVANCE). Une annonce qui génère des
        # RDV fantômes coûte cher avant que le coût-par-signature ne le
        # montre — signal qualité intermédiaire par variante (adsengine).
        NO_SHOW = 'no_show', 'Absent (no-show)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='appointments',
    )
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,  # on_delete: Appointment est le détail de Lead — n'existe pas sans lui
        related_name='appointments',
        verbose_name='Lead',
    )
    scheduled_at = models.DateTimeField(
        verbose_name='Date et heure planifiées',
        help_text='Heure UTC ; affichée en Africa/Casablanca dans l\'UI.',
    )
    statut = models.CharField(
        max_length=10,
        choices=Statut.choices,
        default=Statut.PLANIFIE,
        verbose_name='Statut',
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='Notes de visite',
    )
    # Whether a reminder has already been dispatched (idempotency guard for
    # the beat job — prevents double-sending if the job fires twice).
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name='Rappel envoyé',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rendez-vous'
        verbose_name_plural = 'Rendez-vous'
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['company', 'scheduled_at'],
                         name='crm_appt_co_sched_idx'),
            models.Index(fields=['lead', 'statut'],
                         name='crm_appt_lead_stat_idx'),
        ]

    def __str__(self):
        return (
            f'RDV #{self.pk} — lead {self.lead_id} '
            f'le {self.scheduled_at:%Y-%m-%d %H:%M} ({self.statut})'
        )


class PointContact(models.Model):
    """FG204 — Tableau d'attribution multi-touch : journal des points de contact.

    Au-delà du first-touch (``Lead.canal``/``Lead.source``), on consigne CHAQUE
    point de contact du parcours d'un lead — publicité Meta → site web →
    WhatsApp → signature — pour une attribution multi-touch (qui a vraiment
    amené, puis converti, le lead).

    Additif et borné société : un enregistrement appartient à la société du lead
    (posée côté serveur, jamais lue du corps de requête — multi-tenant). Le
    ``canal`` réutilise le vocabulaire ``Lead.Canal`` (meta_ads/whatsapp_ctwa/
    site_web/reference/telephone/walk_in/autre), donc aucun nouveau jeu de
    valeurs n'est inventé. ``cout`` est optionnel (canaux payants : Meta Ads…).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='points_contact',
    )
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,  # on_delete: PointContact est le détail de Lead — n'existe pas sans lui
        related_name='points_contact',
        verbose_name='Lead',
    )
    # Canal du point de contact — réutilise STRICTEMENT le vocabulaire
    # Lead.Canal (max_length=20 couvre la plus longue clé, 'whatsapp_ctwa').
    canal = models.CharField(
        max_length=20,
        choices=Lead.Canal.choices,
        verbose_name='Canal',
    )
    # Source/détail libre du canal (ex. nom de la campagne Meta, page web).
    source = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Source',
    )
    # Date/heure du point de contact (défaut : maintenant à la création).
    date_contact = models.DateTimeField(
        verbose_name='Date du contact',
    )
    # Rang explicite dans le parcours (1, 2, 3…) — pose l'ordre du journal
    # même quand deux contacts partagent la même date.
    ordre = models.PositiveIntegerField(
        default=0,
        verbose_name='Ordre / séquence',
    )
    # Note libre sur ce point de contact.
    detail = models.TextField(blank=True, null=True, verbose_name='Détail')
    # Coût du point de contact pour les canaux payants (Meta Ads…). Optionnel.
    cout = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Coût',
        help_text='Coût du point de contact (canaux payants). Vide si gratuit.',
    )
    # Traçabilité : qui a saisi le point de contact (forcé côté serveur) + quand.
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='points_contact_saisis',
        verbose_name='Saisi par',
    )
    saisi_le = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Point de contact'
        verbose_name_plural = 'Points de contact'
        # Journal chronologique : par ordre explicite puis date de contact.
        ordering = ['ordre', 'date_contact', 'id']
        indexes = [
            # Nom d'index ≤ 30 chars (règle CI-enforced).
            models.Index(fields=['company', 'lead'],
                         name='crm_ptcontact_co_lead_idx'),
        ]

    def __str__(self):
        return (
            f'Point de contact {self.get_canal_display()} '
            f'(lead {self.lead_id})'
        )


class SiteProfile(models.Model):
    """DC12 — profil site/énergie RÉUTILISABLE, attaché au client.

    Aujourd'hui le profil énergétique et toiture est re-saisi à chaque devis
    (surtout pour les devis SANS lead, qui n'ont nulle part où puiser ces
    valeurs). Ce modèle est la SOURCE UNIQUE par client : saisi une fois, le
    générateur de devis le pré-remplit ensuite (consommé via
    ``selectors.site_profile_for_client``).

    Les taxonomies (raccordement, type de toiture, orientation, ombrage…) sont
    RÉUTILISÉES depuis ``Lead`` — jamais redéclarées ici — pour éviter une
    seconde liste de choix divergente. Borné société ; un seul profil par
    client (OneToOne). Tous les champs sont optionnels et additifs.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True,
        related_name='site_profiles',
    )
    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,  # on_delete: profil de site du client — n'existe pas sans lui
        related_name='site_profile',
        verbose_name='Client',
    )

    # ── Profil énergétique (mêmes champs que Lead) ──
    facture_hiver = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    facture_ete = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    ete_differente = models.BooleanField(default=False)
    conso_mensuelle_kwh = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    tranche_onee = models.CharField(max_length=100, blank=True, null=True)
    raccordement = models.CharField(
        max_length=12, choices=Lead.Raccordement.choices,
        blank=True, null=True)
    regularisation_8221 = models.BooleanField(default=False)
    # CAD145 (21/09/2026) — dupliqué AVEC INTENTION, pas une divergence : ce
    # champ vit au niveau CLIENT (réutilisable sur un futur devis SANS lead,
    # raison d'être de ce modèle — voir la docstring de la classe), tandis que
    # `Lead.type_installation` est le champ PRÉ-SALE que lisent seuls le
    # scoring, les playbooks et les textes de segment pendant la cadence.
    # Aucun code ne lit CE champ-ci pour ces trois usages (`grep -rn
    # SiteProfile backend/django_core/apps/crm/scoring.py
    # backend/django_core/apps/crm/services.py` = vide) ; il ne sert QUE le
    # pré-remplissage du générateur de devis (`selectors.site_profile_for_client`).
    type_installation = models.CharField(
        max_length=20, choices=Lead.TypeInstallation.choices,
        blank=True, null=True)

    # ── Pompage solaire (clients Agricole) ──
    # AGR401 — ancienne colonne CV, renommée : la pompe ACTUELLE (même copie que
    # ``Lead.pompe_actuelle_cv``).
    pompe_actuelle_cv = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Pompe actuelle (CV)')
    pompe_hmt_m = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    pompe_debit_m3h = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)

    # ── Toiture & site ──
    type_toiture = models.CharField(
        max_length=20, choices=Lead.TypeToiture.choices,
        blank=True, null=True)
    surface_toiture_m2 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    orientation = models.CharField(
        max_length=12, choices=Lead.Orientation.choices,
        blank=True, null=True)
    inclinaison_deg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    ombrage = models.CharField(
        max_length=12, choices=Lead.Ombrage.choices, blank=True, null=True)
    ombrage_notes = models.TextField(blank=True, null=True)

    # ── Localisation du site (pour devis sans lead) ──
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])

    # Traçabilité (forcée côté serveur).
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil site'
        verbose_name_plural = 'Profils site'
        ordering = ['-date_modification']

    def __str__(self):
        return f'Profil site (client {self.client_id})'


def _default_chat_token():
    return uuid.uuid4().hex


class ChatSessionPublique(models.Model):
    """XMKT37 — Session de livechat d'un VISITEUR anonyme du site public.

    Même modèle de confiance que le webhook ``webhooks/website-leads/`` :
    la ``company`` est résolue CÔTÉ SERVEUR (le token identifie la SESSION,
    jamais la société — la société est posée à la création, jamais reçue du
    corps de requête). Le transcript est un JSON horodaté ; aucune donnée
    interne (prix_achat/marges) n'y transite jamais — la réponse IA passe
    par ``core.ai`` dont le prompt XMKT37 exclut ce type de donnée par
    construction (aucun accès aux modèles métier).
    """

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        QUALIFIEE = 'qualifiee', 'Qualifiée'
        FERMEE = 'fermee', 'Fermée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='chat_sessions_publiques')
    token = models.CharField(
        max_length=64, unique=True, default=_default_chat_token,
        editable=False)
    # Transcript horodaté : liste de {auteur: 'visiteur'|'assistant'|'system',
    # texte: str, date: iso8601}. Jamais de champ interne (prix_achat/marge).
    transcript = models.JSONField(default=list, blank=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIVE)
    # Lead créé dès que nom + téléphone/email sont capturés (XMKT37).
    lead = models.ForeignKey(
        Lead, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chat_sessions_publiques')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Session livechat publique'
        verbose_name_plural = 'Sessions livechat publiques'
        ordering = ['-last_message_at']

    def __str__(self):
        return f'Session livechat #{self.pk} ({self.statut})'


# XSAL17 — Lien de réservation de RDV, tokenisé par lead + expirant.
# Même patron que ``ventes.ShareLink`` (jeton long/imprévisible, expiration
# par défaut), gardé DANS crm (pas d'import de ventes.models) : le placeholder
# {lien_rdv} des messages/templates CRM résout vers un lien de CE type,
# jamais vers un ShareLink devis/facture (domaines distincts).
BOOKING_LINK_TTL_DAYS = 14


def _default_booking_token():
    import secrets
    return secrets.token_urlsafe(32)


def _default_booking_expiry():
    from datetime import timedelta

    from django.utils import timezone as _timezone
    return _timezone.now() + timedelta(days=BOOKING_LINK_TTL_DAYS)


class BookingLink(models.Model):
    """XSAL17 — Lien PUBLIC, tokenisé et expirant (14 j), permettant à un
    prospect de réserver un créneau de visite rattaché à SON lead sans
    login. Résolu au moment de l'ENVOI d'un message contenant le placeholder
    ``{lien_rdv}`` (voir ``services.resoudre_lien_rdv``) — jamais généré à
    l'avance/en masse. Une réservation via ce lien crée un ``Appointment``
    via le service ``book_appointment`` existant (même logique métier que la
    création interne)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='booking_links')
    lead = models.ForeignKey(
        'crm.Lead', on_delete=models.CASCADE, related_name='booking_links')  # on_delete: BookingLink est le détail de Lead — n'existe pas sans lui
    token = models.CharField(
        max_length=64, unique=True, default=_default_booking_token,
        editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_booking_expiry)
    # Posé dès qu'un Appointment a été créé via ce lien — un lien déjà
    # utilisé reste résolvable (affiche « déjà réservé ») mais ne recrée
    # jamais un second rendez-vous (idempotence).
    used_at = models.DateTimeField(null=True, blank=True)
    appointment = models.ForeignKey(
        'crm.Appointment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='booking_link_origine')

    class Meta:
        verbose_name = 'Lien de réservation RDV'
        verbose_name_plural = 'Liens de réservation RDV'
        ordering = ['-created_at']

    def __str__(self):
        return f'BookingLink lead#{self.lead_id} ({self.token[:8]}…)'

    @property
    def is_expired(self):
        from django.utils import timezone as _timezone
        return _timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None


# ── FG235 — Suivi des commissions partenaires ──────────────────────────────


# ── FG236 — Gestion des territoires / zones commerciales ───────────────────

class TerritoireCommercial(models.Model):
    """Zone commerciale : découpage géographique + affectation auto (FG236).

    Un territoire regroupe des villes/régions (liste de mots-clés en minuscules)
    et un commercial responsable (par id — ``owner_user_id``, jamais un import
    hors foundation). Le service ``affecter_territoire`` associe un lead à la
    zone qui matche sa ville, en respectant la priorité (plus haute d'abord).
    Scopé société.

    WIR81 — le moteur d'assignation des leads par territoire (module
    ``territoires``, NTCRM1/2, consulté depuis
    ``crm.services.default_responsable_for``) est SORTI (SOLMVP10) : ce
    référentiel ``TerritoireCommercial`` (FG236) est désormais le SEUL,
    conservé (jamais supprimé) car NTDST11 prévoit une FK vers lui ; son
    ViewSet est exposé sous l'UNIQUE préfixe
    ``/api/django/compta/territoires-commerciaux/`` (le double montage ODX13 a
    été retiré ; le retrait complet ODX22 reste futur).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='territoires_commerciaux',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom du territoire')
    villes = models.JSONField(
        default=list, blank=True,
        verbose_name='Villes / régions (liste)')
    owner_user_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Commercial responsable (id)')
    priorite = models.IntegerField(
        default=0, verbose_name='Priorité (haute = prioritaire)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Territoire commercial'
        verbose_name_plural = 'Territoires commerciaux'
        db_table = 'compta_territoirecommercial'
        ordering = ['-priorite', 'nom']

    def __str__(self):
        return self.nom

    def matche_ville(self, ville):
        """True si ``ville`` correspond à l'une des villes/régions du zonage."""
        if not ville:
            return False
        cible = str(ville).strip().lower()
        for v in (self.villes or []):
            mot = str(v).strip().lower()
            if mot and (mot == cible or mot in cible or cible in mot):
                return True
        return False


class LeadActivityArchive(models.Model):
    """YOPSB11 — copie FROIDE d'une ``LeadActivity`` archivée.

    Table append-only à forte croissance (le chatter grossit sans borne) : la
    politique de rétention YOPSB11 déplace les lignes anciennes ici puis les
    supprime de la table vive. Schéma miroir SANS index chaud : les FK sont
    DÉNORMALISÉES en identifiants entiers (``company_id``/``lead_id``/…) — une
    archive ne doit dépendre du cycle de vie d'aucune table vive (pas de
    cascade si le lead/l'utilisateur est supprimé plus tard). Les comptages
    agrégés par société survivent via la colonne ``company_id`` conservée."""

    original_id = models.BigIntegerField(
        help_text="PK de la LeadActivity d'origine (table vive).")
    company_id = models.BigIntegerField(null=True, blank=True)
    lead_id = models.BigIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=15)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    outcome = models.CharField(max_length=20, blank=True, default='')
    attachment_id = models.BigIntegerField(null=True, blank=True)
    bulk = models.BooleanField(default=False)
    user_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField()
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité lead (archive)'
        verbose_name_plural = 'Activités lead (archive)'

    def __str__(self):
        return f'archive:{self.original_id}'


# ── LB48 — Vues enregistrées par compte (filtres + disposition de page) ───────

class SavedView(TenantModel):
    """LB48 — vue enregistrée PERSONNELLE (un utilisateur, une page).

    Mémorise un jeu de filtres + une disposition de vue (ex. Kanban vs liste)
    pour une page donnée (``page`` = clé applicative libre, ex. ``crm.leads``),
    propre à l'utilisateur qui l'a créée — jamais partagée entre utilisateurs
    (contrairement à un futur « vues d'équipe »). Société ET utilisateur sont
    TOUJOURS posés côté serveur (jamais lus du corps de requête, cf.
    ``SavedViewViewSet``). ``rank`` ordonne les vues d'un utilisateur pour une
    page (0 = première/défaut) ; l'action ``reorder`` les réassigne en bloc.
    """
    # SCA4 — `company` + timestamps hérités de core.models.TenantModel
    # (accesseur inverse par défaut : company.crm_savedview_set).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: vue personnelle, sans objet sans son propriétaire
        related_name='crm_vues_enregistrees')
    page = models.CharField(
        max_length=64,
        help_text="Clé applicative de la page (ex. 'crm.leads').")
    name = models.CharField(max_length=80, verbose_name='Nom')
    rank = models.PositiveIntegerField(
        default=0, verbose_name='Rang',
        help_text='0 = première/vue par défaut.')
    payload = models.JSONField(
        default=dict, blank=True,
        help_text="Contenu de la vue : {filters, view}.")

    class Meta:
        verbose_name = 'Vue enregistrée'
        verbose_name_plural = 'Vues enregistrées'
        ordering = ['rank', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'page', 'name'],
                name='crm_sv_uniq_user_page_name',
            ),
        ]

    def __str__(self):
        return f'{self.page} — {self.name} ({self.user_id})'


# ── NTCRM17 — Salle de vente digitale (Digital Sales Room) ─────────────────
# Même modèle de confiance que ``ventes.ShareLink`` + ``ged.PartageGed`` :
# jeton long/imprévisible = SEUL secret d'accès, expiration + mot de passe
# optionnel (haché, jamais en clair). Regroupe plusieurs devis/documents sur
# UNE page consultable sans compte par le client, au lieu de liens dispersés.
SALLE_VENTE_TTL_DAYS = 30


def _default_salle_vente_token():
    import secrets
    return secrets.token_urlsafe(32)


def _default_salle_vente_expiry():
    from datetime import timedelta

    from django.utils import timezone as _timezone
    return _timezone.now() + timedelta(days=SALLE_VENTE_TTL_DAYS)


DEAL_REGISTRATION_PROTECTION_JOURS = 90


def _default_deal_expiry():
    from datetime import timedelta

    from django.utils import timezone as _timezone
    return _timezone.now() + timedelta(days=DEAL_REGISTRATION_PROTECTION_JOURS)


# ── L-QUEST (fondateur 25/08/2026) — « questionnaire envoyable au client » ──
#
# « Un client peut remplir chez lui, à son rythme ; le commercial choisit les
# questions ; DÉFAUT = les informations manquantes ; le GPS est une des
# questions. »
#
# Même patron que ``BookingLink`` (jeton long/imprévisible, lien expirant,
# résolution publique sans login) avec DEUX différences voulues :
#   · le lien se ROUVRE (magic-link) — il n'est jamais « consommé » : le
#     client répond section par section et revient plus tard ;
#   · il porte un SECOND jeton INTERNE, jamais montré au client, qui sert au
#     commercial à visiter la page en APERÇU sans rien déclencher (aucune
#     trace, aucune écriture — voir ``public_questionnaire_views``).
QUESTIONNAIRE_LIEN_TTL_DAYS = 30


def _default_questionnaire_token():
    import secrets
    return secrets.token_urlsafe(32)


def _default_questionnaire_expiry():
    from datetime import timedelta

    from django.utils import timezone as _timezone
    return _timezone.now() + timedelta(days=QUESTIONNAIRE_LIEN_TTL_DAYS)


class QuestionnaireLien(TenantModel):
    """L-QUEST — Lien PUBLIC, tokenisé et expirant (30 j), par lequel le
    CLIENT complète lui-même les informations manquantes de SON lead.

    Le contrat servi/consommé est figé dans
    ``apps/crm/contract_samples/questionnaire_lead.json`` (PACT10) —
    l'écran commercial et la page publique codent contre ce fichier."""

    #: Whitelist UNIQUE des sections (une clé hors de cette liste est refusée
    #: par un 400, jamais silencieusement ignorée). C'est AUSSI l'ordre
    #: d'affichage — source unique, jamais recopiée ailleurs.
    #:
    #: ORDRE (recherche 25/08/2026, ordre fondateur « the right order ») —
    #: engagement CROISSANT, données sensibles en dernier :
    #:   1-2. `occupation` puis `equipements` : une tape, zéro effort, et
    #:        l'occupation en journée est le premier levier du taux
    #:        d'autoconsommation → on commence par le plus facile ;
    #:   3.   `energie` : un chiffre à lire sur la facture ;
    #:   4-5. `toiture` puis `gps` : estimer une surface demande un vrai
    #:        effort, et partager sa position demande une PERMISSION — deux
    #:        marches au-dessus des précédentes ;
    #:   6-8. les trois photos : effort PHYSIQUE (aller au compteur) ;
    #:   9.   `contact` : données personnelles — TOUJOURS en dernier
    #:        (NN/g « Hierarchy of Trust » : ne jamais demander un engagement
    #:        de haut niveau avant d'avoir servi les paliers inférieurs).
    #: L'ancien ordre commençait par `contact` — exactement l'inverse.
    #: AGR411 — `pompage`, `photo_pompe` (plaque) et `photo_forage` (tête de
    #: forage) : sections du lead AGRICOLE seulement (filtre de segment dans
    #: ``crm.questionnaire.sections_du_lead``) — jamais servies à un autre.
    #: CIQ412 (contrat CIQ400) — `reseau`, `activite`, `site`, `societe`,
    #: `photo_factures` (12 factures) et `photo_poste` (compteur / poste de
    #: livraison) : sections du lead PRO (commercial/industriel) seulement.
    #: Même logique d'engagement : réseau et activité (des chiffres connus)
    #: d'abord, le site ensuite, les photos, puis l'identité légale juste
    #: avant les coordonnées.
    SECTIONS_CLES = (
        'occupation', 'equipements', 'energie', 'pompage',
        'reseau', 'activite',
        'toiture', 'site', 'gps',
        'photo_facture', 'photo_compteur', 'photo_tableau',
        'photo_pompe', 'photo_forage',
        'photo_factures', 'photo_poste',
        'societe',
        'contact',
    )

    # Socle multi-tenant ARC1 (``TenantModel`` : company + created_at/
    # updated_at). ``company`` est REdéclarée ici uniquement pour garder un
    # ``related_name`` parlant — le motif documenté dans la docstring de
    # ``core.models.TenantModel``, pas un hand-roll.
    company = models.ForeignKey(  # on_delete: lien interne au tenant — purgé avec sa société.
        'authentication.Company', on_delete=models.CASCADE,
        related_name='questionnaire_liens', verbose_name='Société')
    lead = models.ForeignKey(  # on_delete: lien sans objet si le lead disparaît.
        'crm.Lead', on_delete=models.CASCADE,
        related_name='questionnaire_liens')
    # Jeton CLIENT — c'est celui-là qu'on envoie (WhatsApp/e-mail).
    token = models.CharField(
        max_length=64, unique=True, default=_default_questionnaire_token,
        editable=False)
    # Jeton INTERNE — même page, JAMAIS montré au client : le commercial
    # ouvre l'aperçu sans déclencher la moindre écriture ni la moindre trace.
    token_interne = models.CharField(
        max_length=64, unique=True, default=_default_questionnaire_token,
        editable=False)
    created_by = models.ForeignKey(  # on_delete: on garde le lien si l'auteur quitte l'entreprise.
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='questionnaire_liens_crees')
    # ``created_at``/``updated_at`` viennent de TenantModel (ARC1).
    expires_at = models.DateTimeField(default=_default_questionnaire_expiry)

    # Sections DEMANDÉES — sémantique à TROIS états, identique à
    # ``ventes.ShareLink.sections`` :
    #   · clé ABSENTE → section ACTIVE (défaut) ;
    #   · clé à False → section RETIRÉE (le commercial ne la pose pas) ;
    #   · clé à True  → section posée.
    # Le mint SANS corps `questions` écrit la carte EXPLICITE des informations
    # manquantes (ordre fondateur « DÉFAUT = les informations manquantes »).
    questions = models.JSONField(
        default=dict, blank=True, verbose_name='Sections demandées')

    # Progression du CLIENT sur CE lien (jamais alimentée par l'aperçu
    # interne) : {section: True} — sert à lui réafficher où il s'est arrêté.
    sections_repondues = models.JSONField(
        default=dict, blank=True, verbose_name='Sections déjà répondues')
    derniere_reponse_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière réponse du client')

    class Meta:
        verbose_name = 'Lien questionnaire client'
        verbose_name_plural = 'Liens questionnaire client'
        ordering = ['-created_at']

    def __str__(self):
        return f'QuestionnaireLien lead#{self.lead_id} ({self.token[:8]}…)'

    @property
    def is_expired(self):
        from django.utils import timezone as _timezone
        return _timezone.now() >= self.expires_at

    def question_posee(self, cle):
        """La section ``cle`` est-elle demandée sur ce lien ?

        UNE seule décision, partagée par tous les flux (GET public, POST
        public, écran commercial) : clé absente → True (comportement par
        défaut), clé à False → False. Défensif (``getattr``/type) au cas où
        un test construit un lien à la main."""
        questions = getattr(self, 'questions', None)
        if not isinstance(questions, dict):
            return True
        return questions.get(cle) is not False

    def sections_actives(self):
        """Sections demandées, dans l'ordre de la whitelist."""
        return [cle for cle in self.SECTIONS_CLES if self.question_posee(cle)]


# ── VT1 — VISITE TECHNIQUE TERRAIN ───────────────────────────────────────────
#
# VTA2 — `VisiteTerrain` et `VisiteMedia` ont DÉMÉNAGÉ dans `apps.visites`
# (l'app autonome de la visite terrain, sortie du CRM : le commercial terrain
# n'a pas l'accès CRM). Le move est STATE-ONLY — les tables physiques
# `crm_visiteterrain` / `crm_visitemedia` sont inchangées, aucune donnée n'a
# bougé — et il n'y a DÉLIBÉRÉMENT aucun shim de ré-export ici : un
# `from apps.visites.models import ...` recréerait l'arête
# `apps.crm.models -> apps.visites.models` que le contrat `independence`
# d'import-linter interdit, c'est-à-dire exactement le couplage que ce move
# supprime. Le reste du CRM lit la visite par `apps.visites.selectors`.


# ── Ré-export (SPL91-SPL93) — UN SEUL bloc, TOUT EN BAS : les modèles déplacés vers
# `models_<x>.py` restent enregistrés par Django (qui charge ce module) et
# importables depuis `apps.crm.models`. Rien ne doit être défini après.
from .models_clients import (  # noqa: E402,F401,F811
    _lead_identity_keys, AppareilEquipe, Apporteur, Client,
    CommissionPartenaire, ConcurrentPerte, DealEnregistre, Defi,
    EquipeCommerciale, EtapePlanActivite, ForecastEntry, ForecastSnapshot,
    LeadPlaybookProgress, ObjectifCommercial, Parrainage, Partenaire,
    PlanActivite, PlanCompte, Playbook, PlaybookEtape, PlaybookTache,
    RevueCompte, SalleVente, SalleVenteItem, SalleVenteVue,
    SoumissionLeadPartenaire, SPECIALITES_PARTENAIRE,
    SPECIALITES_PARTENAIRE_CLES, VisiteExterne)
from .models_cadence import (  # noqa: E402,F401
    GesteRelanceAppareil, MessageTemplate, PeriodeAbsence, RelanceEtape)
