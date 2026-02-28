import requests
import time
from typing import List, Dict
import yaml
from pathlib import Path

PRINT_CATEGORY_PATHS = False
PRINT_DEALS = True

def load_config(config_path: str = "kaufda.yaml") -> Dict:
    """Lädt die YAML-Konfigurationsdatei."""
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def get_all_articles(config: Dict) -> List[str]:
    """Extrahiert alle Artikel aus den Kategorien."""
    articles = []
    for category, items in config.get("articles", {}).items():
        articles.extend(items)
    return articles


OFFER_SEARCH_URL = "https://www.kaufda.de/webapp/api/slots/offerSearch"

# https://www.kaufda.de/webapp/api/slots/offerSearch?searchQuery=h%C3%A4hnchenbrust&lat=47.965625499999994&lng=11.753921799999999&size=25
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

def search_article(article: str, preffered_publishers: List[str] | None = None) -> List[Dict]:
    # https://www.kaufda.de/webapp/api/slots/offerSearch?searchQuery=h%C3%A4hnchenbrust&lat=47.965625499999994&lng=11.753921799999999&size=25
    # https://www.kaufda.de/webapp/?query=h%C3%A4hnchenbrust&lat=47.965625499999994&lng=11.753921799999999

    url = "https://www.kaufda.de/webapp/api/slots/offerSearch"

    params = {
        "searchQuery": article,
        "lat": 47.965625499999994,
        "lng": 11.753921799999999,
        "size": 25
    }

    headers = {
        "accept": "application/json",
        "accept-language": "de-DE,de",
        "cache-control": "max-age=3600",
        "content-type": "application/json",
        "delivery_channel": "dest.kaufda",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "user_platform_category": "desktop.web.browser",
        "user_platform_os": "windows"
    }



    response = requests.get(
        url,
        params=params,
        headers=headers
    )

    response.raise_for_status()

    data = response.json()
    results = []

    contents = data.get("_embedded", []).get("contents", [])

    publisher_filtered_contents = list(filter(lambda e: e.get("content", {}).get("publisherName", "").lower() in preffered_publishers, contents)) if preffered_publishers else contents
    for result_entry in publisher_filtered_contents:
        try:

            search_result = extract_content(result_entry, article)
            print(search_result)


        except Exception as e:
            print(f"Exception: {e}")
            continue

    return results

from dataclasses import dataclass

@dataclass
class SearchResult:
    publisher_name: str
    article: str
    price_min: float
    price_max: float
    price_by_base_unit: str
    regular_price_min: float
    regular_price_max: float
    regular_price_by_base_unit: str
    description: str

    def __str__(self) -> str:
        if self.price_min == self.price_max:
            price_range = f"{self.price_min}€"
        else:
            price_range = f"{self.price_min}€ - {self.price_max}€"

        if self.regular_price_min == self.regular_price_max:
            regular_price_range = f"{self.regular_price_min}€"
        else:
            regular_price_range = f"{self.regular_price_min}€ - {self.regular_price_max}€"


        obj_string =  f"{self.article} | {self.publisher_name} | {price_range} | {self.price_by_base_unit} | {self.description}"
        if self.regular_price_min or self.regular_price_max:
            obj_string = obj_string + f" | REGULÄR: {regular_price_range} | {self.regular_price_by_base_unit} |"
        return obj_string


def extract_price_triplet(deals: List[Dict], deal_type: str) -> tuple[float, float, str] | None:
    """
    Extrahiert das Price-Tripel (price_min, price_max, price_by_base_unit) aus einer Liste von Deals.

    Args:
        deals: Liste der Deal-Objekte
        deal_type: Typ des Deals (z.B. 'SALES_PRICE', 'REGULAR_PRICE')

    Returns:
        Tupel von (price_min, price_max, price_by_base_unit) oder None wenn kein passender Deal gefunden

    Raises:
        ValueError: Falls Währung nicht EUR ist
    """

    # 🔎 Chiemseer
    #    {'type': 'SPECIAL_PRICE', 'description': 'Mo, 23.2. – Sa, 28.2.', 'conditions': [{'other': 'Nur mit App'}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 13.99, 'min': 13.99, 'priceByBaseUnit': '1 l = 1.40'}
    #    {'type': 'SALES_PRICE', 'description': ' ', 'conditions': [{}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 14.99, 'min': 14.99, 'priceByBaseUnit': '1 l = 1.50'}
    #    {'type': 'REGULAR_PRICE', 'description': '', 'conditions': [{}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 18.99, 'min': 18.99, 'priceByBaseUnit': ''}
    # Exception: ⚠️ Unerwartete deal types: {'REGULAR_PRICE', 'SALES_PRICE', 'SPECIAL_PRICE'}

    # RECOMMENDED_RETAIL_PRICE
    # 🔎 Schweinefilet
    #    {'type': 'SALES_PRICE', 'description': 'gültig am Samstag, 07.03.26', 'conditions': [{}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 7.77, 'min': 7.77, 'priceByBaseUnit': ''}
    #    {'type': 'RECOMMENDED_RETAIL_PRICE', 'description': '', 'conditions': [{}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 11.99, 'min': 11.99, 'priceByBaseUnit': ''}
    # Exception: ⚠️ Unerwartete deal types: {'RECOMMENDED_RETAIL_PRICE', 'SALES_PRICE'}

    # Hähnchenbrust | METRO | 23.53€ |  | Gewürzt, gebraten, Ofen-gebräunt 2,5-kg-Beutel
    #    {'type': 'SPECIAL_PRICE', 'description': 'Hähnchenbrust-Innenfilets gebräunt', 'conditions': [{'other': 'Ab 4 Beutel'}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 22.46, 'min': 22.46, 'priceByBaseUnit': ''}
    #    {'type': 'SPECIAL_PRICE', 'description': 'Hähnchenbrust-Innenfilets gebräunt', 'conditions': [{'other': 'Ab 2 Beutel'}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 23.53, 'min': 23.53, 'priceByBaseUnit': ''}
    #    {'type': 'SALES_PRICE', 'description': 'Hähnchenbrust-Innenfilets gebräunt', 'conditions': [{'other': 'Ab 1 Beutel'}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 24.6, 'min': 24.6, 'priceByBaseUnit': ''}
    #    {'type': 'SPECIAL_PRICE', 'description': 'Hähnchenbrust gebraten', 'conditions': [{'other': 'Ab 4 Beutel'}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 22.46, 'min': 22.46, 'priceByBaseUnit': ''}
    #    {'type': 'SPECIAL_PRICE', 'description': 'Hähnchenbrust gebraten', 'conditions': [{'other': 'Ab 2 Beutel'}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 23.53, 'min': 23.53, 'priceByBaseUnit': ''}
    #    {'type': 'SALES_PRICE', 'description': 'Hähnchenbrust gebraten', 'conditions': [{'other': 'Ab 1 Beutel'}], 'frequency': 'ONCE', 'currencyCode': 'EUR', 'max': 24.6, 'min': 24.6, 'priceByBaseUnit': ''}
    # Exception: ⚠️ Unerwartete deal types: {'SALES_PRICE', 'SPECIAL_PRICE'}



    for deal in filter(lambda x: x.get('type') == deal_type, deals):
        price_min = min(deal.get("min"), deal.get("max"))
        price_max = max(deal.get("min"), deal.get("max"))
        price_by_base_unit = deal.get("priceByBaseUnit")

        if 'EUR' != deal.get("currencyCode", "EUR"):
            raise ValueError(f"Unexpected currency: {deal.get('currencyCode')}")

        return price_min, price_max, price_by_base_unit

    return (None, None, None)


def extract_content(result_entry: dict, searched_article: str) -> SearchResult | None:
    content_object = result_entry.get("content", {})

    publisher_name = content_object.get("publisherName")


    # finde gesuchten artikel in categoryPaths
    for p in content_object.get("products", []):

        description = ", ".join([desc.get("paragraph") for desc in p.get('description', [])])

        found = False
        category_paths = p.get('categoryPaths', [])
        for category_path in category_paths:
            if PRINT_CATEGORY_PATHS:
                print(f"{category_path}")
            if searched_article in [category.get("name", "") for category in category_path]:
                found = True

        if found:
            deals = content_object.get("deals", [])

            if PRINT_DEALS:
                for d in deals:
                    print(f"   {d}")

            # Sanity-Check: Gibt es andere deal types?
            deal_types = set([deal.get('type') for deal in deals])
            if deal_types - {'SALES_PRICE', 'REGULAR_PRICE'} != set():
                raise ValueError(f"⚠️ Unerwartete deal types: {deal_types}")


            # Versuche zuerst SALES_PRICE zu extrahieren, sonst REGULAR_PRICE
            (price_min, price_max, price_by_base_unit) = extract_price_triplet(deals, 'SALES_PRICE')
            (regular_price_min, regular_price_max, regular_price_by_base_unit) = extract_price_triplet(deals, 'REGULAR_PRICE')

            search_result = SearchResult(publisher_name, searched_article, price_min, price_max, price_by_base_unit,
                                         regular_price_min, regular_price_max, regular_price_by_base_unit,
                                         description)
            return search_result

        return None


def find_best_price(
    article: str,
    preferred_retailers: List[str] | None = None
):
    results = search_article(article, preferred_retailers)

    # Filter nach bevorzugten Händlern
    # filtered = [
    #     r for r in results
    #     if r["retailer"] and r["retailer"].upper() in
    #     [p.upper() for p in preferred_retailers]
    # ]

    # if not filtered:
    #     return None

    # best = min(filtered, key=lambda x: x["price"])
    return results


def run(articles: List[str], publishers: List[str] | None = None):

    for article in articles:
        print(f"🔎 {article}")

        try:
            best = find_best_price(article, publishers)

            # TODO: Ist es moeglich, den "besten" zu finden?
            # if not best:
            #     print("   Keine Angebote bei bevorzugten Händlern gefunden\n")
            #     continue

            # print(f"   💰 {best['price']} € bei {best['retailer']}")
            # print(f"   🏷 Angebot: {'Ja' if best['is_offer'] else 'Nein'}")
            # print(f"   📅 Gültig bis: {best['valid_until']}\n")

            time.sleep(1)  # Rate limiting

        except Exception as e:
            print(f"   Fehler: {e}\n")


if __name__ == "__main__":
    config = load_config("kaufda.yaml")
    articles = get_all_articles(config)
    publishers = config.get("publishers")

    run(articles, publishers)


# if __name__ == "__main__":
#     articles = ["Augustiner"] # Münchner Hell (nicht immer)
#     articles = ["Chiemseer"]
#     articles = ["Oettinger"] #Glorietta / Oettinger    vs "Oettinger Alkoholfrei / Oettinger
#     #articles = ["Ayinger"]  # NA
#
#     #articles = ["Hackfleisch gemischt"]  # DE-103916176
#     #articles = ["Rinderhackfleisch"]  # DE-103755852
#
#     articles = ["Rinderfilet"]  # NA
#     articles = ["Cevapcici"]  # DE-103741278
#     articles = ["Schweinefilet"]  # DE-46548
#     articles = ["Entrecote"]  # DE-46333
#     articles = ["Putenschnitzel"]  # DE-447443
#     articles = ["Hähnchenbrust"]  #   DE-96565476
#     articles = ["Hähnchenbrustfilet"]  # DE-96565507
#     articles = ["Barilla Pesto"]  # Pesto DE-28455   Barilla DE-118573 !!!!!
#     articles = ["Barilla Pasta"]  # Pasta DE-1888207   Barilla DE-118573 !!!!!
#     articles = ["Beinscheibe"]  # DE-114575711   TODO immer Rind?
#     articles = ["Lachsforelle"]  # DE-112824778
#     articles = ["Lachs"]  # DE-189
#
#     articles = ["Fischstäbchen"]  # DE-10502    # Iglo Fischstäbchen DE-304258260
#     articles = ["Iglo Fischstäbchen"]  #  DE-304258260
#
#     articles = ["Lachsfilet"]  # DE-124820091
#     articles = ["Nordsee Backfisch"]  # Nordsee DE-522185456   # Backfisch DE-103720631
#     articles = ["Wiener Würstchen"]  # DE-1475
#     articles = ["Pelmeni"]  # DE-196424573
#     articles = ["Maultaschen"]  # NA
#     articles = ["Roastbeef"]  # DE-46358
#     articles = ["Rinderrouladen"]  # DE-778440418
#     articles = ["Rindergulasch"]  # DE-103750662
#     articles = ["Toffifee"]  # DE-282571   # Storck DE-92457096
#     articles = ["Nutella"]  # DE-9694
#     articles = ["falsches Filet"]  # DE-136402970
#     articles = ["Heidelbeeren"]  # DE-33862705
#     articles = ["Erdbeeren"]  # DE-619032
#     articles = ["Himbeeren"]  # DE-11217
#
#     #articles = ["D'arbo"]  # DE-
#
#     articles = ["Golden Toast"]  # DE-1186081
#     #articles = ["Maracuja"]  # DE-      TODO: _ohne_ Fruchtsaft DE-96565068
#
#     #articles = ["Doppio Passo"]  # DE-
#     #articles = ["Luna Argenta"]  # DE-
#     #articles = ["Rothaus"]  # DE-
#
#
#
#
#     articles = [
#         "Augustiner",
#         "Chiemseer",
#         "Oettinger",
#         "Rinderfilet",
#         "Cevapcici",
#         "Schweinefilet",
#         "Entrecote",
#         "Putenschnitzel",
#         "Hähnchenbrust",
#         "Hähnchenbrustfilet",
#         "Barilla Pesto",
#         "Barilla Pasta",
#         "Beinscheibe",
#         "Lachsforelle",
#         "Lachs",
#         "Fischstäbchen",
#         "Iglo Fischstäbchen",
#         "Lachsfilet",
#         "Nordsee Backfisch",
#         "Wiener Würstchen",
#         "Pelmeni",
#         "Maultaschen",
#         "Roastbeef",
#         "Rinderrouladen",
#         "Rindergulasch",
#         "Toffifee",
#         "Nutella",
#         "falsches Filet",
#         "Heidelbeeren",
#         "Erdbeeren",
#         "Himbeeren",
#         "Golden Toast"
#     ]
#
#     #articles = ["Absolut Vodka"]  # DE-554305 # komisch: bei Netto vermischt mit Quark
#     #articles = ["Mozzarella"]  # DE-246664
#     #articles = ["Parmesan"]  # DE-911771
#     #articles = ["Händlmaier's"]  # DE-197979411   # süßer Senf DE-208821972
#
#
#
#     #articles = ["Hähnchenbrust", "Paprika", "Spaghetti"]
#     # articles = ["Cevapcici"]
#
#     # articles = ["putensteak"]
#     #articles = ["Rinderfilet", "Paprika", "Spaghetti"]
#     publishers = None
#     #publishers = [p.lower() for p in ["rewe", "edeka", "lidl", "Netto", "Netto Marken-Discount", "Penny", "Metro"]]
#     #publishers = [p.lower() for p in ["rewe", "edeka", "Netto Marken-Discount"]]
#
#     run(articles, publishers)