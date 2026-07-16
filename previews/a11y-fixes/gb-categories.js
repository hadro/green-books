// gb-categories.js — shared category-folding logic for the Green Book explorers.
// Loaded by explorer.html (Green Book only) and all-volumes.html (merged).
//
// ⚠ AUTO-GENERATED from gb-categories.json — DO NOT EDIT BY HAND.
//   Edit gb-categories.json (the single source of truth, also read by the Python
//   dataset build in gb_categories.py), then regenerate:  python3 gen_gb_categories.py
//
// Two-layer normalization (mirrored exactly in gb_categories.py):
//   1. Baseline case fold — trim + uppercase, so "Motel"/"MOTEL" collapse for free.
//   2. Explicit groups — GB_CATEGORY_GROUPS maps a canonical display label to the
//      UPPERCASE raw variants (typos, plurals, synonyms) that fold into it.
// The blank bucket ("" after trim) folds to "Blank or no specific category".
//
// The map is inlined below (not fetched) so it loads synchronously with the page
// and gbCategoryGroup() is available immediately — no async readiness needed.

const GB_CATEGORY_GROUPS = {
  "ATTORNEYS": [
    "ATTY"
  ],
  "ATTRACTIONS": [
    "ATTRACTION"
  ],
  "AUTO REPAIRS": [
    "AUTO REPAIRING"
  ],
  "AUTO SALES & SERVICE": [
    "AUTO SALES AND SERVICE"
  ],
  "AUTO SERVICE - REPAIRS": [
    "AUTO SERVICE & REPAIRS",
    "AUTO SERVICE & REPAIR",
    "AUTO SERVICE & REPAIR SHOP",
    "AUTO REPAIRS & SERVICE"
  ],
  "AUTOMOBILE DEALERS": [
    "AUTOMOBILE DEALER"
  ],
  "AUTOMOBILE SERVICE - REPAIRS, ETC.": [
    "AUTOMOBILE SERVICE-REPAIRS, ETC."
  ],
  "AUTOMOTIVE": [
    "AUTOMOTIVES",
    "AUTOMOBILES"
  ],
  "BANKS": [
    "BANK"
  ],
  "BARBERS - BEAUTY SHOPS": [
    "BARBER - BEAUTY SHOPS",
    "BARBER & BEAUTY SHOPS",
    "BARBER & BEAUTY SHOP",
    "BEAUTY AND BARBER SHOPS"
  ],
  "BEAUTY PARLOR - SUPPLIES": [
    "BEAUTY PARLOR & SUPPLIES"
  ],
  "Blank or no specific category": [
    "HOTELS - MOTELS - TOURIST HOMES - RESTAURANTS",
    "HOTELS AND MOTELS",
    "HOTELS-MOTELS-TOURISTS",
    "MOTELS-HOTELS-TOURISTS",
    "HOTELS, MOTELS, TOURIST HOMES",
    "HOTELS-MOTELS",
    "HOTELS - MOTELS",
    "WHERE TO STAY",
    "LIST OF HOTELS",
    "ACCOMMODATIONS",
    "HOTELS - GUESTS",
    "HOTELS, MOTELS, ETC.",
    "HOTELS-MOTELS-RESORTS",
    "HOTELS - MOTELS - TOURIST HOMES",
    "HOTEL, MOTEL, TOURIST HOMES",
    "HOTELS, MOTELS, TOURISTS HOMES",
    "HOTELS, MOTELS, TOURIST HOMES, RESTAURANTS",
    "HOTELS MOTELS",
    "GUESTS HOTELS MOTELS",
    "GUESTS - HOTELS - MOTELS",
    "HOTEL - GUESTS - MOTELS",
    "HOTEL - GUESTS",
    "GUEST HOUSE - HOTELS - MOTELS",
    "HOTELS - MOTELS - GUEST HOUSES",
    "HOTELS MOTELS GUEST HOUSES",
    "HOTELS, GUEST HOUSES, ETC.",
    "HOTELS - GUEST HOMES - MOTOR COURTS",
    "HOTELS & GUESTS",
    "HOTELS - MOTEL",
    "HOTEL/MOTEL",
    "HOTELS & MOTELS",
    "HOTELS & TOURIST HOMES",
    "HOTELS - TOURIST HOMES",
    "HOTELS & MOTEL",
    "GUESTS",
    "DEALERS - HOTELS - RESTAURANTS",
    "RESTAURANTS/HOTELS/SERVICES",
    "DEALERS AND HOTELS OFFERING DISCOUNTS",
    "GO-BY-AUTO CLUB MEMBERS",
    "GENERAL",
    "MISCELLANEOUS",
    "WHAT TO SEE",
    "NEW YORK CITY",
    "HARLEM",
    "WESTCHESTER",
    "BROOKLYN",
    "YONKERS",
    "VIRGINIA",
    "MARYLAND",
    "FLORIDA",
    "NEW JERSEY",
    "PENNSYLVANIA",
    "SOUTH CAROLINA",
    "NEW JERSEY-PENNSYLVANIA",
    "NEW JERSEY-DELAWARE",
    "MARYLAND-WEST VIRGINIA",
    "NEW YORK-NEW JERSEY",
    "MONTCLAIR",
    "LAWNSIDE",
    "MANASQUAN",
    "NEWARK",
    "NEW BRUNSWICK",
    "MILLINGTON",
    "MOORESTOWN",
    "MORRISTOWN",
    "MT. EPHRAIM",
    "MAGNOLIA",
    "NEPTUNE",
    "AMERICAN LEAGUE",
    "NATIONAL LEAGUE",
    "IMPORTANT FOOTBALL GAMES",
    "CONVENTION CALENDAR",
    "CONVENTION DATES",
    "GENERAL FACTS",
    "ROUTES",
    "POPULAR ROUTES",
    "VACATION TOURS",
    "TOURIST PLACEMENT FOR GROUPS",
    "SUMMER SUPPLEMENT",
    "FACTS ABOUT THE NEW STATE",
    "LOCAL OFFICES",
    "LOCAL COMMITTEES",
    "COOPERATING COMMITTEES",
    "EPISCOPAL DISTRICTS",
    "CONNECTIONAL MEETINGS",
    "NATIONWIDE HOTEL ASSOCIATION, INC. REGIONAL OFFICERS",
    "INDEX TO MAJOR ADVERTISERS",
    "INDEX TO ADVERTISERS",
    "BUSINESS DIRECTORY",
    "CUSTOMS REGULATIONS",
    "RHODE ISLAND FACTS",
    "GENERAL INFORMATION",
    "ROAD MAP",
    "BY CAR TO ALASKA",
    "SEEING SAN FRANCISCO",
    "AUGUST",
    "SEPTEMBER",
    "DECEMBER",
    "OCTOBER - NOVEMBER",
    "TRIP",
    "EVENTS",
    "BIG BEND NATIONAL PARK",
    "ADVERTISEMENT",
    "NOTICE",
    "NOT SPECIFIED",
    "UNSPECIFIED",
    "N/A",
    "NONE",
    "HIGHTOWER'S MOTEL",
    "PAUL'S LUNCH",
    "CUSTER'S LAST STAND",
    "DE COSTA DETECTIVE AGENCY",
    "WOODLAND PARK RESORT",
    "PARADISE PK. RESORT",
    "YELLOW FRONT",
    "DE LUX",
    "DISTRICT ADVERTISING AND CIRCULATION MANAGER",
    "TRAVIS CLARK'S PACKAGE STORES",
    "GOTHARD'S RENTAL AND VACATION SERVICE BUREAU"
  ],
  "BOOKSTORES": [
    "BOOK STORE"
  ],
  "CAFES": [
    "CAFE"
  ],
  "CAFETERIA & CABINS": [
    "CAFETERIA AND CABINS"
  ],
  "CAMPS": [
    "CAMP"
  ],
  "CHINESE RESTAURANTS": [
    "CHINESE RESTAURANT",
    "CHINESE"
  ],
  "CHIROPODIST & PODIATRIST": [
    "CHIROPODIST - PODIATRIST"
  ],
  "CLOTHIERS": [
    "CLOTHIER"
  ],
  "CLUBS": [
    "CLUB"
  ],
  "COCKTAIL LOUNGES": [
    "COCKTAIL LOUNGE"
  ],
  "COTTAGES": [
    "COTTAGE"
  ],
  "COUNTRY CLUBS": [
    "COUNTRY CLUB"
  ],
  "DANCING SCHOOLS": [
    "DANCING SCHOOL"
  ],
  "DENTISTS": [
    "DENTIST",
    "DDS"
  ],
  "DEPARTMENT STORES": [
    "DEPARTMENT STORE"
  ],
  "DRUG STORES": [
    "DRUGGIST",
    "PHARMACY",
    "DRUGS"
  ],
  "EMPLOYMENT AGENCIES": [
    "EMPLOYMENT AGENCY"
  ],
  "FLORISTS": [
    "FLORIST"
  ],
  "FUNERAL HOMES": [
    "FUNERAL HOME"
  ],
  "GARAGES": [
    "GARAGE"
  ],
  "GROCERIES": [
    "GROCERY",
    "GROCER"
  ],
  "GUEST HOUSES": [
    "GUEST HOUSE"
  ],
  "HABERDASHERS": [
    "HABERDASHER",
    "HABERDASHERY"
  ],
  "HOSPITALS": [
    "HOSPITAL"
  ],
  "HOTELS & GUEST HOUSES": [
    "HOTEL & GUEST HOUSE",
    "HOTELS - GUEST HOUSE",
    "HOTELS GUEST HOUSE",
    "HOTEL & GUEST HOUSES",
    "HOTELS-GUEST HOUSES",
    "HOTELS - GUEST HOUSES"
  ],
  "HOTELS AND GUEST HOMES": [
    "GUEST HOMES - HOTELS",
    "HOTELS - GUEST HOMES"
  ],
  "IMPORTANT MEN'S SHOPS": [
    "IMPORTANT MEN'S SHOP"
  ],
  "INNS": [
    "INN"
  ],
  "LAWYERS": [
    "LAWYER"
  ],
  "LODGES": [
    "LODGE"
  ],
  "LODGINGS": [
    "LODGING",
    "LOGDINGS"
  ],
  "MORTICIANS": [
    "MORTICIAN"
  ],
  "MOTOR COURTS": [
    "MOTOR COURT"
  ],
  "NATIONAL PARK FACILITIES": [
    "NATIONAL PARK FACILITY"
  ],
  "NATIONAL PARKS": [
    "NATIONAL PARK"
  ],
  "NEWSPAPERS": [
    "NEWSPAPER"
  ],
  "ORGANIZATIONS": [
    "ORGANIZATION"
  ],
  "PACKAGE STORES": [
    "PACKAGE STORE"
  ],
  "PHOTOGRAPHERS": [
    "PHOTOGRAPHER",
    "PHOTOPRAPHER"
  ],
  "PHYSICIANS": [
    "PHYSICIAN",
    "MD"
  ],
  "PHYSICIANS - SURGEONS": [
    "PHYSICIAN - SURGEON",
    "PHYSICIAN AND SURGEON"
  ],
  "POINTS OF INTEREST": [
    "PLACES OF INTEREST",
    "TOURIST ATTRACTIONS",
    "OF INTEREST"
  ],
  "PRINTERS": [
    "PRINTING"
  ],
  "PRINTERS - BOOK & JOB": [
    "PRINTERS BOOK & JOB"
  ],
  "PROFESSIONALS": [
    "PROFESSIONAL"
  ],
  "PUBLIC RELATIONS COUNSELLORS": [
    "PUBLIC RELATIONS COUNSELLOR"
  ],
  "PUBLISHERS": [
    "PUBLISHING"
  ],
  "RANCHES": [
    "RANCH"
  ],
  "RESTAURANTS - CAFES": [
    "CAFES - RESTAURANTS",
    "CAFE - RESTAURANT"
  ],
  "RETAIL WINES & LIQUORS": [
    "RETAIL WINES & LIQUOR"
  ],
  "SHOE REPAIRS": [
    "SHOE REPAIR"
  ],
  "STATE ANTI-DISCRIMINATION AGENCIES": [
    "NEW YORK STATE COMMISSION AGAINST DISCRIMINATION"
  ],
  "TAILOR SHOPS": [
    "TAILOR"
  ],
  "TAILORS - CLEANING & DYEING": [
    "TAILOR CLEANING & DYEING"
  ],
  "TOURIST HOMES": [
    "LOURIST"
  ],
  "TRAILER PARKS": [
    "TRAILOR PARKS",
    "(TRAILERS PARK)"
  ],
  "TRAVELGUIDE SALUTES": [
    "TRAVELGUIDE SALUTES!"
  ],
  "WINE & LIQUOR STORES": [
    "LQIUOR STORES"
  ]
};

// variant (UPPERCASE) → canonical display label, built once from GB_CATEGORY_GROUPS.
// Canonical labels map to themselves so an already-canonical (or case-variant)
// value resolves without a separate variants entry.
const _GB_CATEGORY_INDEX = (() => {
  const idx = {};
  Object.entries(GB_CATEGORY_GROUPS).forEach(([canonical, variants]) => {
    idx[canonical.toUpperCase()] = canonical;
    variants.forEach(v => { idx[v] = canonical; });
  });
  return idx;
})();

// Fold a raw category value to its display label: baseline case fold, then the
// explicit groups map, falling back to the uppercased raw value when unmatched.
function gbCategoryGroup(raw) {
  const folded = (raw || "").trim().toUpperCase();
  if (!folded) return "Blank or no specific category";
  return _GB_CATEGORY_INDEX[folded] || folded;
}
