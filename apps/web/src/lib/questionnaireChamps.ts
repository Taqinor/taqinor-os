/**
 * Registre des libellés et champs du questionnaire client (données seulement).
 * Sorti de pages/questionnaire/[token].astro (CQSTW1) pour que la page ne
 * grossisse plus : libellés FR/EN/AR des listes fermées, champs numériques du
 * bloc pompage et, ci-dessous, les champs ajoutés par CQST3/CQST6.
 */
export type L3 = { fr: string; en: string; ar: string };
export const L = (fr: string, en: string, ar: string): L3 => ({ fr, en, ar });
export const POMPAGE_NUM = {
  niveau_statique_m: { id: 'q-niveau-statique', fr: "À quelle profondeur se trouve l'eau quand la pompe est arrêtée ? (m)", en: 'How deep is the water when the pump is off? (m)', ar: 'على أي عمق يوجد الماء عندما تكون المضخة متوقفة؟ (م)' },
  besoin_eau_m3j: { id: 'q-besoin-eau', fr: "De combien de mètres cubes d'eau avez-vous besoin par jour au plus fort de la saison ? (m³/jour)", en: 'How many cubic metres of water do you need per day at the peak of the season? (m³/day)', ar: 'كم متراً مكعباً من الماء تحتاجون يومياً في ذروة الموسم؟ (م³/اليوم)' },
  surface_irriguee_ha: { id: 'q-surface-irriguee', fr: "Combien d'hectares irriguez-vous ? (ha)", en: 'How many hectares do you irrigate? (ha)', ar: 'كم هكتاراً تسقون؟ (هكتار)' },
  // AGQ34 (D-AGQ-6) — jamais pré-remplie (aucun défaut).
  jours_irrigation_semaine: { id: 'q-jours-irrigation', fr: 'Combien de jours par semaine irriguez-vous en saison ? (1 à 7)', en: 'How many days a week do you irrigate in season? (1 to 7)', ar: 'كم يوماً في الأسبوع تسقون خلال الموسم؟ (من 1 إلى 7)' },
  butane_bouteilles_jour: { id: 'q-butane-bouteilles', fr: 'Combien de bouteilles de butane par jour en saison ? (bouteilles de 12 kg)', en: 'How many butane cylinders per day in season? (12 kg cylinders)', ar: 'كم قنينة بوتان في اليوم خلال الموسم؟ (قنينات 12 كلغ)' },
  carburant_prix_unitaire_mad: { id: 'q-carburant-prix', fr: 'Vous la payez combien, la bouteille (ou le litre de gasoil) ? (MAD)', en: 'How much do you pay for a cylinder (or a litre of diesel)? (MAD)', ar: 'بكم تشترون القنينة (أو لتر الغازوال)؟ (درهم)' },
  depense_carburant_mad_mois: { id: 'q-depense-carburant', fr: 'Combien dépensez-vous en carburant par mois ? (MAD/mois)', en: 'How much do you spend on fuel per month? (MAD/month)', ar: 'كم تنفقون على الوقود شهرياً؟ (درهم/الشهر)' },
} as const;
export const SOURCE_EAU_LABELS: Record<string, L3> = {
  puits: L('Puits', 'Well', 'بئر'), forage: L('Forage', 'Borehole', 'ثقب (فوراج)'),
  bassin: L('Bassin', 'Reservoir', 'حوض'), riviere: L('Rivière', 'River', 'واد'),
};
export const IRRIGATION_LABELS: Record<string, L3> = {
  goutte: L('Goutte-à-goutte', 'Drip', 'التنقيط'), aspersion: L('Aspersion', 'Sprinkler', 'الرش'),
  gravitaire: L('Gravitaire (à la raie)', 'Gravity (furrow)', 'الجاذبية (الأخاديد)'),
};
export const ALIM_LABELS: Record<string, L3> = {
  aucune: L('Pas de pompe actuellement', 'No pump at the moment', 'لا توجد مضخة حالياً'),
  diesel: L('Diesel (gasoil)', 'Diesel', 'ديزل (غازوال)'), butane: L('Butane', 'Butane', 'بوتان'),
  electrique: L('Électricité', 'Electricity', 'كهرباء'),
};
export const TENSION_LABELS: Record<string, L3> = {
  bt: L('Basse tension (BT) — compteur ordinaire', 'Low voltage (LV) — standard meter', 'ضغط منخفض (BT) — عداد عادي'),
  mt: L('Moyenne tension (MT) — poste de transformation', 'Medium voltage (MV) — transformer substation', 'ضغط متوسط (MT) — محطة تحويل'),
  ne_sait_pas: L('Je ne sais pas', "I don't know", 'لا أعرف'),
};
// Fondateur 26/10/2026 — contrat, option de la force motrice et phase : lus sur la facture.
export const CONTRAT_LABELS: Record<string, L3> = {
  bt_domestique: L('Basse tension — domestique', 'Low voltage — domestic', 'ضغط منخفض — منزلي'),
  bt_patente: L('Basse tension — patenté (commerce)', 'Low voltage — business', 'ضغط منخفض — مهني (تجاري)'),
  bt_force_motrice: L('Basse tension — force motrice', 'Low voltage — motive power', 'ضغط منخفض — القوة المحركة'),
  mt_general: L('Moyenne tension', 'Medium voltage', 'ضغط متوسط'),
  ne_sait_pas: L('Je ne sais pas', "I don't know", 'لا أعرف'),
};
export const OPTION_BT_LABELS: Record<string, L3> = {
  normale: L('Option normale', 'Standard option', 'الخيار العادي'),
  bi_horaire: L('Option bi-horaire (heures pleines / heures creuses)', 'Two-rate option (peak / off-peak hours)', 'خيار التوقيتين (ساعات الذروة / الساعات العادية)'),
};
export const PHASE_LABELS: Record<string, L3> = {
  monophase: L('Monophasé', 'Single-phase', 'أحادي الطور'),
  triphase: L('Triphasé', 'Three-phase', 'ثلاثي الأطوار'),
  inconnu: L('Je ne sais pas', "I don't know", 'لا أعرف'),
};
export const ORIENTATION_LABELS: Record<string, L3> = {
  sud: L('Sud', 'South', 'الجنوب'),
  sud_est: L('Sud-Est', 'South-East', 'الجنوب الشرقي'),
  sud_ouest: L('Sud-Ouest', 'South-West', 'الجنوب الغربي'),
  est: L('Est', 'East', 'الشرق'),
  ouest: L('Ouest', 'West', 'الغرب'),
  autre: L('Nord ou autre', 'North or other', 'الشمال أو غيره'),
};
export const SURFACE_LABELS: Record<string, L3> = {
  toiture: L('Sur la toiture', 'On the roof', 'فوق السطح'),
  ombriere: L('Sur une ombrière de parking', 'On a parking canopy', 'فوق مظلة موقف السيارات'),
  terrain: L('Sur un terrain', 'On open ground', 'على أرض مفتوحة'),
};
export const TOITURE_PRO_LABELS: Record<string, L3> = {
  terrasse_beton: L('Terrasse béton', 'Concrete flat roof', 'سطح إسمنتي مسطح'),
  tole_metal: L('Tôle métallique', 'Metal sheet', 'صفائح معدنية'),
  tuiles: L('Tuiles', 'Tiles', 'قرميد'),
  bac_acier: L('Bac acier', 'Steel decking', 'ألواح فولاذية'),
  fibrociment: L('Fibrociment', 'Fibre cement', 'الألياف الإسمنتية'),
  autre: L('Autre', 'Other', 'أخرى'),
};
export const EQUIPES_LABELS: Record<string, L3> = {
  '1x8': L('Une équipe de jour', 'One day shift', 'فريق واحد نهاراً'),
  '2x8': L('Deux équipes', 'Two shifts', 'فريقان'),
  '3x8': L('Trois équipes', 'Three shifts', 'ثلاثة فرق'),
  continu: L('En continu', 'Continuous', 'بشكل متواصل'),
  ne_sait_pas: L('Je ne sais pas', "I don't know", 'لا أعرف'),
};
export const TVA_LABELS: Record<string, L3> = {
  oui: L('Oui', 'Yes', 'نعم'),
  non: L('Non', 'No', 'لا'),
  ne_sait_pas: L('Je ne sais pas', "I don't know", 'لا أعرف'),
};
export const CATEGORIE_LABELS: Record<string, L3> = {
  hotel: L('Hôtel / riad', 'Hotel / riad', 'فندق / رياض'),
  restaurant: L('Restaurant / café', 'Restaurant / café', 'مطعم / مقهى'),
  commerce: L('Commerce / supermarché', 'Shop / supermarket', 'متجر / سوق ممتاز'),
  bureau: L('Bureaux / siège', 'Offices / head office', 'مكاتب / مقر'),
  sante: L('Santé (clinique, cabinet)', 'Health (clinic, practice)', 'صحة (مصحة، عيادة)'),
  ecole: L('École', 'School', 'مدرسة'),
  hammam: L('Hammam / spa / salle de sport', 'Hammam / spa / gym', 'حمام / سبا / قاعة رياضة'),
  boulangerie: L('Boulangerie', 'Bakery', 'مخبزة'),
  froid: L('Froid / entrepôt frigorifique', 'Cold storage', 'تبريد / مستودع مبرد'),
  autre: L('Autre activité', 'Other activity', 'نشاط آخر'),
};
export const JOUR_LABELS: Record<number, L3> = {
  1: L('Lun', 'Mon', 'الاثنين'), 2: L('Mar', 'Tue', 'الثلاثاء'), 3: L('Mer', 'Wed', 'الأربعاء'),
  4: L('Jeu', 'Thu', 'الخميس'), 5: L('Ven', 'Fri', 'الجمعة'), 6: L('Sam', 'Sat', 'السبت'),
  7: L('Dim', 'Sun', 'الأحد'),
};
// Questions propres à la catégorie : libellé par `categorie.cle` puis par `cle`.
export const CAT_Q_LABELS: Record<string, L3> = {
  chambres: L("Combien de chambres avez-vous ?", 'How many rooms do you have?', 'كم عدد الغرف لديكم؟'),
  occupation_pct: L("Quel est votre taux d'occupation moyen sur l'année, à peu près ? (%)", 'What is your average yearly occupancy rate, roughly? (%)', 'ما هي نسبة الإشغال المتوسطة خلال السنة تقريباً؟ (%)'),
  piscine: L("Votre établissement a-t-il une piscine ?", 'Does your establishment have a swimming pool?', 'هل يتوفر مؤسستكم على مسبح؟'),
  heures_piscine: L("La piscine fonctionne combien d'heures par jour ? (h)", 'How many hours a day does the pool run? (h)', 'كم ساعة في اليوم يشتغل المسبح؟ (س)'),
  blanchisserie: L('Lavez-vous le linge sur place ?', 'Do you wash the linen on site?', 'هل تغسلون الأغطية في عين المكان؟'),
  reception_24h: L('La réception est-elle ouverte 24 heures sur 24 ?', 'Is the reception open 24 hours a day?', 'هل الاستقبال مفتوح 24 ساعة على 24؟'),
  chambres_froides: L('Combien de chambres froides avez-vous ?', 'How many cold rooms do you have?', 'كم عدد الغرف الباردة لديكم؟'),
  'commerce.chambres_froides': L('Combien de meubles ou chambres froids avez-vous ?', 'How many refrigerated units or cold rooms do you have?', 'كم عدد واجهات أو غرف التبريد لديكم؟'),
  horaires: L('Quels sont vos horaires de service ?', 'What are your service hours?', 'ما هي ساعات الخدمة لديكم؟'),
  cuisson: L('Cuisinez-vous à l’électricité ou au gaz ?', 'Do you cook with electricity or gas?', 'هل تطبخون بالكهرباء أم بالغاز؟'),
  ouvert_journee_ramadan: L('Pendant le Ramadan, êtes-vous ouverts en journée ?', 'During Ramadan, are you open during the day?', 'خلال رمضان، هل أنتم مفتوحون نهاراً؟'),
  surface_vente_m2: L('Quelle est votre surface de vente ? (m²)', 'What is your sales floor area? (m²)', 'ما هي مساحة البيع لديكم؟ (م²)'),
  effectif: L("Combien de personnes travaillent sur le site ?", 'How many people work on the site?', 'كم عدد الأشخاص الذين يشتغلون في الموقع؟'),
  'ecole.effectif': L("Combien d'élèves accueillez-vous ?", 'How many pupils do you host?', 'كم عدد التلاميذ لديكم؟'),
  clim: L('Avez-vous une climatisation centralisée ?', 'Do you have central air conditioning?', 'هل لديكم تكييف مركزي؟'),
  lits: L('Combien de lits avez-vous ?', 'How many beds do you have?', 'كم عدد الأسرّة لديكم؟'),
  garde_nuit: L('Assurez-vous une garde de nuit ?', 'Do you run a night shift?', 'هل تؤمنون حراسة ليلية؟'),
  internat: L('Avez-vous un internat ?', 'Do you have a boarding house?', 'هل لديكم داخلية؟'),
  fermeture_estivale: L("Fermez-vous l'été ?", 'Do you close in summer?', 'هل تغلقون خلال الصيف؟'),
  surface_m2: L('Quelle est la surface de votre établissement ? (m²)', 'What is the area of your premises? (m²)', 'ما هي مساحة مؤسستكم؟ (م²)'),
  chauffe: L("L'eau est chauffée à l'électricité ou au gaz ?", 'Is the water heated by electricity or gas?', 'هل يُسخَّن الماء بالكهرباء أم بالغاز؟'),
  four: L('Votre four est électrique ou à gaz ?', 'Is your oven electric or gas?', 'هل فرنكم كهربائي أم يشتغل بالغاز؟'),
  cuisson_nocturne: L('Cuisez-vous la nuit ?', 'Do you bake at night?', 'هل تخبزون ليلاً؟'),
  temperature_consigne: L('Quelle est votre température de consigne ? (°C)', 'What is your set-point temperature? (°C)', 'ما هي درجة الحرارة المضبوطة؟ (°م)'),
  volume_m3: L('Quel volume réfrigéré avez-vous ? (m³)', 'What refrigerated volume do you have? (m³)', 'ما هو حجم التبريد لديكم؟ (م³)'),
  saisonnalite_recolte: L('Avez-vous un pic saisonnier lié à la récolte ?', 'Do you have a seasonal peak tied to harvest?', 'هل لديكم ذروة موسمية مرتبطة بالحصاد؟'),
};
export const CAT_OPTION_LABELS: Record<string, L3> = {
  midi: L('Midi', 'Lunch', 'الغداء'),
  soir: L('Soir', 'Evening', 'المساء'),
  continu: L('Continu', 'Continuous', 'متواصل'),
  electrique: L('Électrique', 'Electric', 'كهربائي'),
  gaz: L('Gaz', 'Gas', 'غاز'),
};
export const catLabel = (cat: string, key: string): L3 => CAT_Q_LABELS[`${cat}.${key}`] ?? CAT_Q_LABELS[key];

// ── CQSTW1 — champs pompage ajoutés par CQST3/CQST6 (contrat colonnes_ecrites.pompage) ──
export interface ChampDonnee {
  /** Colonne du contrat (clé de `reponses`). */
  cle: string;
  /** id du contrôle sur la page (lu par collectSectionRaw). */
  id: string;
  type: 'number' | 'select';
  libelle: L3;
  min?: number;
  max?: number;
  options?: ReadonlyArray<{ value: string; libelle: L3 }>;
  /** Plaque de la pompe actuelle : dessinée seulement si mode_pompe = existante. */
  plaque?: boolean;
}


export const CHAMPS_POMPAGE_CQST: readonly ChampDonnee[] = [
  {
    cle: 'profondeur_forage_m', id: 'q-profondeur-forage', type: 'number', min: 0,
    libelle: L('Profondeur totale du forage, en mètres — si vous la connaissez', 'Total depth of the borehole, in metres — if you know it', 'العمق الكلي للبئر بالأمتار — إن كنتم تعرفونه'),
  },
  {
    cle: 'debit_forage_m3h', id: 'q-debit-forage', type: 'number', min: 0,
    libelle: L("Combien d'eau votre forage peut donner par heure (m³/h), d'après un essai ou votre foreur — si vous le savez", 'How much water your borehole can give per hour (m³/h), from a test or your driller — if you know it', 'كم من الماء يعطي بئركم في الساعة (م³/س)، حسب تجربة أو حسب الحفار — إن كنتم تعرفون'),
  },
  {
    cle: 'pompe_hmt_m', id: 'q-pompe-hmt', type: 'number', min: 0,
    libelle: L("Hauteur totale de pompage : profondeur de l'eau + hauteur jusqu'au bassin, en mètres — si vous la connaissez", 'Total pumping height: depth of the water + height up to the reservoir, in metres — if you know it', 'الارتفاع الكلي للضخ: عمق الماء + الارتفاع إلى الحوض بالأمتار — إن كنتم تعرفونه'),
  },
  {
    cle: 'pompe_actuelle_debit_m3h', id: 'q-pompe-debit', type: 'number', min: 0,
    libelle: L("Combien d'eau votre pompe actuelle sort-elle par heure ? (m³/h)", 'How much water does your current pump deliver per hour? (m³/h)', 'كم من الماء تعطي مضختكم الحالية في الساعة؟ (م³/س)'),
  },
  {
    cle: 'pompage_heures_jour', id: 'q-pompage-heures', type: 'number', min: 0, max: 24,
    libelle: L("Combien d'heures par jour votre pompe actuelle tourne-t-elle ? (h)", 'How many hours a day does your current pump run? (h)', 'كم ساعة في اليوم تشتغل مضختكم الحالية؟ (س)'),
  },
  {
    cle: 'mode_pompe', id: 'q-mode-pompe', type: 'select',
    libelle: L('On installe une pompe neuve, ou on garde votre pompe actuelle ?', 'Do we fit a new pump, or keep your current pump?', 'هل نركب مضخة جديدة أم نحتفظ بمضختكم الحالية؟'),
    options: [
      { value: 'neuve', libelle: L('Une pompe neuve', 'A new pump', 'مضخة جديدة') },
      { value: 'existante', libelle: L('Je garde ma pompe actuelle', 'I keep my current pump', 'أحتفظ بمضختي الحالية') },
    ],
  },
  {
    cle: 'pompe_actuelle_kw', id: 'q-pompe-kw', type: 'number', min: 0, plaque: true,
    libelle: L('Puissance écrite sur la plaque de la pompe (kW)', 'Power written on the pump plate (kW)', 'القدرة المكتوبة على لوحة المضخة (كيلوواط)'),
  },
  {
    cle: 'pompe_actuelle_tension_v', id: 'q-pompe-tension', type: 'select', plaque: true,
    libelle: L('Tension écrite sur la plaque : 220 V ou 380 V ?', 'Voltage on the plate: 220 V or 380 V?', 'الجهد المكتوب على اللوحة: 220 أم 380 فولت؟'),
    options: [
      { value: '220', libelle: L('220 V', '220 V', '220 فولت') },
      { value: '380', libelle: L('380 V', '380 V', '380 فولت') },
    ],
  },
  {
    cle: 'pompe_actuelle_phases', id: 'q-pompe-phases', type: 'select', plaque: true,
    libelle: L('Sur la plaque, la pompe est-elle monophasée ou triphasée ?', 'On the plate, is the pump single-phase or three-phase?', 'على اللوحة، هل المضخة أحادية أم ثلاثية الأطوار؟'),
    options: [
      { value: 'mono', libelle: L('Monophasée', 'Single-phase', 'أحادية الطور') },
      { value: 'tri', libelle: L('Triphasée', 'Three-phase', 'ثلاثية الأطوار') },
    ],
  },
];
