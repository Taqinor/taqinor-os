// QJW4 — LA COUCHE LOCALE DU TUNNEL, À EXHAUSTIVITÉ VÉRIFIÉE À LA COMPILATION.
//
// CE QUE CE FICHIER GARANTIT, ET COMMENT. `LIBELLES` est un
// `Record<LocaleTunnel, Record<CleChamp, string>>` : le type est clé sur
// l'UNION LITTÉRALE des clés du registre (`champs.ts`, QJW2). Ajouter un champ
// au registre sans lui donner ses TROIS traductions n'est donc pas une
// omission silencieuse qu'on découvre en production sur la version arabe —
// c'est une erreur `tsc`, à la compilation, avant tout déploiement. C'est la
// moitié de la garantie de parité entre locales, et elle ne coûte RIEN à
// l'exécution : ce sont trois tables de chaînes.
//
// CE QUE CE FICHIER NE FAIT PAS. Il ne partage PAS le balisage. La mise en page
// arabe diffère réellement (RTL, ordre des colonnes, silhouettes miroir) : les
// trois `.astro` gardent chacun le leur. Seules les CHAÎNES et la LOGIQUE sont
// partagées — c'est exactement la frontière que l'audit a montrée tenable.
//
// POURQUOI `ERREURS` N'EST PAS, LUI, UN RECORD COMPLET. Sur les 69 champs du
// registre, six seulement peuvent produire une erreur de champ côté client
// (`validateLead` n'en juge pas d'autres). Forcer une table complète
// obligerait à INVENTER un message d'erreur pour `gpsLat`, `eventId` ou
// `utm_source` — du texte fabriqué que personne n'affichera jamais. La table
// d'erreurs reste donc partielle et honnête ; l'exhaustivité vérifiée par
// `tsc` vit dans `LIBELLES`, qui couvre bien les 69 clés.

import type { CleChamp } from './champs';
import type { LocaleTunnel, MessagesErreurs } from './corps';

/** Un jeu complet de libellés : une entrée par clé du registre, sans trou. */
export type LibellesTunnel = Record<CleChamp, string>;

const FR: LibellesTunnel = {
  // identité + contact
  nomComplet: 'Nom complet',
  telephone: 'Téléphone',
  ville: 'Ville / commune',
  // facture
  trancheFacture: 'Tranche de facture mensuelle',
  typeToiture: 'Type de toiture',
  // consentement + parcours
  consentement: 'Consentement à être recontacté',
  whatsappSeulement: 'Contact par WhatsApp uniquement',
  preferenceContact: 'Préférence de contact',
  email: 'E-mail',
  factureHiver: "Facture d'électricité (hiver)",
  adresse: 'Adresse',
  mode: 'Type de projet',
  languePreferee: 'Langue préférée',
  // session
  clientRef: 'Référence client',
  idempotencyKey: 'Clé de dédoublonnage',
  eventId: "Identifiant d'événement",
  appareilId: "Identifiant d'appareil",
  creneauVisitePartie: 'Créneau de visite (moment)',
  creneauVisiteSemaine: 'Créneau de visite (semaine)',
  // professionnel
  raisonSociale: 'Raison sociale',
  tensionRaccordement: 'Tension de raccordement',
  profilActivite: "Profil d'activité",
  typeSurface: 'Type de surface',
  surfaceM2: 'Surface disponible (m²)',
  proMensuelKwh: 'Consommation mensuelle (kWh)',
  proMensuelMad: 'Facture mensuelle (MAD)',
  categorieCommerciale: "Catégorie d'établissement",
  equipes: "Organisation des équipes",
  surfaceToitureM2: 'Surface de toiture (m²)',
  ombriere: 'Ombrière',
  terrain: 'Terrain',
  // agricole
  sourceEau: "Source d'eau",
  profondeurM: 'Profondeur (m)',
  hmtM: 'Hauteur manométrique totale (m)',
  debitM3h: 'Débit souhaité (m³/h)',
  besoinM3j: "Besoin en eau (m³/jour)",
  heuresPompage: 'Heures de pompage par jour',
  culture: 'Culture',
  regionAgricole: 'Région agronomique',
  surfaceHa: 'Surface irriguée (ha)',
  depenseCarburantMad: 'Dépense carburant (MAD/mois)',
  // estimation
  estimationAffichee: 'Estimation affichée',
  // L-WEBT
  occupationJour: 'Occupation du logement la journée',
  equipChauffeEau: 'Chauffe-eau électrique',
  equipVoitureElectrique: 'Voiture électrique',
  equipVeKmSemaine: 'Kilomètres par semaine',
  equipClim: 'Climatisation',
  equipClimPieces: 'Pièces climatisées',
  equipPiscine: 'Piscine',
  equipPiscinePompeKw: 'Puissance de la pompe (kW)',
  equipChauffeEauKw: 'Puissance du chauffe-eau (kW)',
  equipChauffeEauCreneau: 'Créneau de chauffe',
  equipVeChargeurKw: 'Puissance du chargeur (kW)',
  equipVeCreneau: 'Créneau de recharge',
  equipClimKw: 'Puissance de la climatisation (kW)',
  equipClimCreneau: 'Créneau de climatisation',
  equipPiscineHeuresJour: 'Heures de filtration par jour',
  equipPiscineCreneau: 'Créneau de filtration',
  // anti-spam
  honeypot: 'Champ anti-robot',
  // tracking
  fbclid: 'Identifiant de clic Facebook',
  utm_source: 'Source de campagne',
  utm_medium: 'Support de campagne',
  utm_campaign: 'Campagne',
  utm_content: 'Contenu de campagne',
  utm_term: 'Mot-clé de campagne',
  // carte
  repereToit: 'Repère de toiture',
  gpsLat: 'Latitude',
  gpsLng: 'Longitude',
  contourToit: 'Contour de toiture',
};

const EN: LibellesTunnel = {
  nomComplet: 'Full name',
  telephone: 'Phone',
  ville: 'City / municipality',
  trancheFacture: 'Monthly bill bracket',
  typeToiture: 'Roof type',
  consentement: 'Consent to be contacted',
  whatsappSeulement: 'WhatsApp only',
  preferenceContact: 'Contact preference',
  email: 'Email',
  factureHiver: 'Electricity bill (winter)',
  adresse: 'Address',
  mode: 'Project type',
  languePreferee: 'Preferred language',
  clientRef: 'Client reference',
  idempotencyKey: 'Deduplication key',
  eventId: 'Event id',
  appareilId: 'Device id',
  creneauVisitePartie: 'Site visit slot (time of day)',
  creneauVisiteSemaine: 'Site visit slot (week)',
  raisonSociale: 'Company name',
  tensionRaccordement: 'Grid connection voltage',
  profilActivite: 'Activity profile',
  typeSurface: 'Surface type',
  surfaceM2: 'Available surface (m²)',
  proMensuelKwh: 'Monthly consumption (kWh)',
  proMensuelMad: 'Monthly bill (MAD)',
  categorieCommerciale: 'Business category',
  equipes: 'Shift pattern',
  surfaceToitureM2: 'Roof surface (m²)',
  ombriere: 'Carport canopy',
  terrain: 'Ground-mounted',
  sourceEau: 'Water source',
  profondeurM: 'Depth (m)',
  hmtM: 'Total dynamic head (m)',
  debitM3h: 'Required flow (m³/h)',
  besoinM3j: 'Water need (m³/day)',
  heuresPompage: 'Pumping hours per day',
  culture: 'Crop',
  regionAgricole: 'Agronomic region',
  surfaceHa: 'Irrigated area (ha)',
  depenseCarburantMad: 'Fuel spend (MAD/month)',
  estimationAffichee: 'Estimate shown',
  occupationJour: 'Daytime occupancy',
  equipChauffeEau: 'Electric water heater',
  equipVoitureElectrique: 'Electric car',
  equipVeKmSemaine: 'Kilometres per week',
  equipClim: 'Air conditioning',
  equipClimPieces: 'Air-conditioned rooms',
  equipPiscine: 'Swimming pool',
  equipPiscinePompeKw: 'Pump power (kW)',
  equipChauffeEauKw: 'Water heater power (kW)',
  equipChauffeEauCreneau: 'Heating time slot',
  equipVeChargeurKw: 'Charger power (kW)',
  equipVeCreneau: 'Charging time slot',
  equipClimKw: 'Air conditioning power (kW)',
  equipClimCreneau: 'Air conditioning time slot',
  equipPiscineHeuresJour: 'Filtration hours per day',
  equipPiscineCreneau: 'Filtration time slot',
  honeypot: 'Anti-bot field',
  fbclid: 'Facebook click id',
  utm_source: 'Campaign source',
  utm_medium: 'Campaign medium',
  utm_campaign: 'Campaign',
  utm_content: 'Campaign content',
  utm_term: 'Campaign term',
  repereToit: 'Roof pin',
  gpsLat: 'Latitude',
  gpsLng: 'Longitude',
  contourToit: 'Roof outline',
};

const AR: LibellesTunnel = {
  nomComplet: 'الاسم الكامل',
  telephone: 'الهاتف',
  ville: 'المدينة / الجماعة',
  trancheFacture: 'شريحة الفاتورة الشهرية',
  typeToiture: 'نوع السطح',
  consentement: 'الموافقة على إعادة الاتصال',
  whatsappSeulement: 'واتساب فقط',
  preferenceContact: 'وسيلة الاتصال المفضلة',
  email: 'البريد الإلكتروني',
  factureHiver: 'فاتورة الكهرباء (الشتاء)',
  adresse: 'العنوان',
  mode: 'نوع المشروع',
  languePreferee: 'اللغة المفضلة',
  clientRef: 'مرجع العميل',
  idempotencyKey: 'مفتاح منع التكرار',
  eventId: 'معرّف الحدث',
  appareilId: 'معرّف الجهاز',
  creneauVisitePartie: 'موعد الزيارة (الفترة)',
  creneauVisiteSemaine: 'موعد الزيارة (الأسبوع)',
  raisonSociale: 'اسم الشركة',
  tensionRaccordement: 'جهد الربط بالشبكة',
  profilActivite: 'طبيعة النشاط',
  typeSurface: 'نوع المساحة',
  surfaceM2: 'المساحة المتاحة (م²)',
  proMensuelKwh: 'الاستهلاك الشهري (ك.و.س)',
  proMensuelMad: 'الفاتورة الشهرية (درهم)',
  categorieCommerciale: 'صنف النشاط التجاري',
  equipes: 'نظام الفرق',
  surfaceToitureM2: 'مساحة السطح (م²)',
  ombriere: 'مظلة شمسية',
  terrain: 'تركيب أرضي',
  sourceEau: 'مصدر الماء',
  profondeurM: 'العمق (م)',
  hmtM: 'الارتفاع المانومتري الإجمالي (م)',
  debitM3h: 'الصبيب المطلوب (م³/س)',
  besoinM3j: 'الحاجة من الماء (م³/يوم)',
  heuresPompage: 'ساعات الضخ في اليوم',
  culture: 'الزراعة',
  regionAgricole: 'المنطقة الزراعية',
  surfaceHa: 'المساحة المسقية (هكتار)',
  depenseCarburantMad: 'مصروف الوقود (درهم/شهر)',
  estimationAffichee: 'التقدير المعروض',
  occupationJour: 'شغل المنزل خلال النهار',
  equipChauffeEau: 'سخان ماء كهربائي',
  equipVoitureElectrique: 'سيارة كهربائية',
  equipVeKmSemaine: 'الكيلومترات في الأسبوع',
  equipClim: 'التكييف',
  equipClimPieces: 'الغرف المكيّفة',
  equipPiscine: 'مسبح',
  equipPiscinePompeKw: 'قدرة المضخة (ك.و)',
  equipChauffeEauKw: 'قدرة السخان (ك.و)',
  equipChauffeEauCreneau: 'فترة التسخين',
  equipVeChargeurKw: 'قدرة الشاحن (ك.و)',
  equipVeCreneau: 'فترة الشحن',
  equipClimKw: 'قدرة التكييف (ك.و)',
  equipClimCreneau: 'فترة التكييف',
  equipPiscineHeuresJour: 'ساعات الترشيح في اليوم',
  equipPiscineCreneau: 'فترة الترشيح',
  honeypot: 'حقل مضاد للروبوتات',
  fbclid: 'معرّف نقرة فيسبوك',
  utm_source: 'مصدر الحملة',
  utm_medium: 'وسيط الحملة',
  utm_campaign: 'الحملة',
  utm_content: 'محتوى الحملة',
  utm_term: 'كلمة الحملة',
  repereToit: 'علامة السطح',
  gpsLat: 'خط العرض',
  gpsLng: 'خط الطول',
  contourToit: 'محيط السطح',
};

/**
 * LES LIBELLÉS, par locale. Chaque table est un `Record` COMPLET sur les clés
 * du registre : une clé ajoutée sans ses trois traductions casse `tsc`.
 */
export const LIBELLES: Record<LocaleTunnel, LibellesTunnel> = { fr: FR, en: EN, ar: AR };

/**
 * LES MESSAGES D'ERREUR du pré-contrôle client, par locale.
 *
 * La table FR reprend MOT POUR MOT les messages que `validateLead` produit
 * déjà (`lib/lead.ts`) : la version française est donc inchangée à l'octet,
 * la bascule ne déplace pas un seul caractère sous les yeux d'un visiteur
 * francophone. Les tables EN et AR sont l'amélioration réelle — jusqu'ici un
 * visiteur anglophone ou arabophone recevait ces messages EN FRANÇAIS.
 *
 * `telephone` est DÉLIBÉRÉMENT absent des trois tables : `normalizeMoroccanPhone`
 * rend un message circonstancié (indicatif, longueur, format) qu'aucune chaîne
 * statique ne remplacerait sans perdre de l'information. `construireCorps`
 * laisse alors passer le message d'origine — un message précis en français vaut
 * mieux qu'un message vague traduit.
 */
export const ERREURS: Record<LocaleTunnel, MessagesErreurs> = {
  fr: {
    nomComplet: 'Nom complet requis',
    ville: 'Ville / commune requise',
    typeToiture: 'Type de toiture requis',
    trancheFacture: 'Tranche de facture requise',
    consentement: 'Le consentement est requis pour être recontacté',
  },
  en: {
    nomComplet: 'Full name required',
    ville: 'City / municipality required',
    typeToiture: 'Roof type required',
    trancheFacture: 'Bill bracket required',
    consentement: 'Your consent is required so we can get back to you',
  },
  ar: {
    nomComplet: 'الاسم الكامل مطلوب',
    ville: 'المدينة / الجماعة مطلوبة',
    typeToiture: 'نوع السطح مطلوب',
    trancheFacture: 'شريحة الفاتورة مطلوبة',
    consentement: 'الموافقة ضرورية حتى نتمكن من معاودة الاتصال بكم',
  },
};

/** Le libellé d'un champ dans une locale donnée. */
export function libelle(locale: LocaleTunnel, cle: CleChamp): string {
  return LIBELLES[locale][cle];
}
