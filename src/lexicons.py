"""Name patterns and category lists used to classify shops (Italian and English terms)."""

CHAINS = r"carrefour|conad|\bpam\b|tigre|in'?s mercato|todis|\bmd\b|elite|\bsma\b|simply|dec[oò]|pewex|castoro|crai|\bcoop\b|incoop|eurospin|lidl|penny|despar|\bsisa\b|tuod[iì]|\bpim\b|agor[aà]|iper|esselunga|naturas[iì]|\bdem\b|ipercarni|superconti|carrefour|margherita conad|\bemme ?pi[uù]|\bq8\b|eni ?shop|\bnegozio leggero|altromercato|coal\b|\bdok\b|il gigante|todis|famila|\bgs\b|\bmercat[oò] ?pi[uù]"
GENERIC_MARKET = r"mini ?-?market|minimarket|food ?market|super ?market|\bmarket\b|\bh ?24\b|\b24 ?h\b|24/7|24 ?ore|food ?(?:&|and|e) ?drinks?|grocery|food ?store|cash ?(?:&|and) ?carry|drink ?shop"
TOURIST_GOODS = r"souvenir|luggage|gift|\bsim\b|money ?transfer|phone ?center|ricarich|tabacchi|valigi"
TRADITIONAL = r"macelleria|pescheria|enoteca|forno|panific|bottega|salumeria|norcineria|gastronomia|caseificio|azienda agricola|biologic|\bbio\b|gluten|celiac|vineria|pasticceria|latteria"
NON_RETAIL_OV = r"marketing|advertis|b2b|restaurant|\bbar\b|cafe|hotel|massage|salon|repair|plumbing|office|service|wash|agency|gym|fitness|locksmith|school|church|clinic|dentist|doctor|lawyer|real_estate|bed_and_breakfast|accommodation|pub|pizza|night|club|tattoo|barber|bank|atm|pharmacy|parking|taxi|travel|insurance|consult|garden_center|nursery|construction|contractor|manufactur|textile|tailor|sewing|clothing|shoe|jewel|optic|furniture|electron|mobile_phone|computer|hardware|auto|car_|motorcycle|bike|book|florist|flowers|pet|toy|sport|beauty|cosmetic|perfume|tobacco|e_cigarette|vape|cannabis"

OSM_FOOD_SHOPS = {"convenience", "supermarket", "general", "variety_store", "food", "greengrocer", "alcohol", "deli",
                  "kiosk", "gift", "grocery", "frozen_food"}
OV_FOOD_CATS = {"convenience_store", "grocery_store", "liquor_store", "asian_grocery_store", "international_grocery_store",
                "indian_grocery_store", "korean_grocery_store", "greengrocer", "produce_store", "discount_store",
                "souvenir_store", "food_and_beverage_store", "beer_wine_spirits_store", "specialty_foods_store",
                "gift_shop", "shopping", "flea_market"}

# Google Places primary types treated as small food retail
GOOGLE_KEEP_TYPES = {"grocery_store", "supermarket", "convenience_store", "asian_grocery_store", "food_store", "market",
                     "liquor_store", "general_store", "discount_supermarket"}
