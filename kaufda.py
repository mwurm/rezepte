from datetime import datetime

import requests
import time
from typing import List, Dict
import yaml
from pathlib import Path
from hashlib import sha256
import re
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from dateutil import parser

PRINT_CATEGORY_PATHS = False
PRINT_DEALS = False

TAGE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

def normalize_price(text: str) -> str | None:
    """
    Vereinheitlicht Preisangaben pro kg oder l.

    Beispiele:
    "1 kg = 46.13"        -> "46.13 EUR/kg"
    "15.98 / kg"          -> "15.98 EUR/kg"
    "1kg = 11,63–6,20"    -> "6.20–11.63 EUR/kg"
    "1 l = 1.80"          -> "1.80 EUR/l"
    """

    if not text:
        return text

    original = text.lower().strip()

    # Einheit erkennen
    unit_match = re.search(r"(kg|ml|l)", original.replace(" ", ""))
    if not unit_match:
        return original

    unit = unit_match.group(1)

    # Kommas in Punkte umwandeln
    text = text.replace(",", ".")

    # Zahlen extrahieren
    numbers = re.findall(r"\d+(?:\.\d+)?", text)

    if not numbers:
        return original

    try:
        values = [Decimal(n) for n in numbers]
    except InvalidOperation:
        return original

    # Falls Form wie "1 kg = 46.13" → die "1" ignorieren
    if len(values) >= 2 and values[0] == 1:
        values = values[1:]

    if not values:
        return original

    # Einzelpreis
    if len(values) == 1:
        return f"{values[0]:.2f}€/{unit}"

    # Preisbereich
    min_val = min(values)
    max_val = max(values)

    return f"{min_val:.2f}–{max_val:.2f} EUR/{unit}"

def load_config(config_path: str = "kaufda.yaml") -> Dict:
    """Lädt die YAML-Konfigurationsdatei."""
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def get_all_articles(config: Dict) -> List[str]:
    """Extrahiert alle Artikel aus den Kategorien."""
    articles = []
    for category, items in config.get("articles", {}).items():
        if items:
            articles.extend(items)
    return articles


OFFER_SEARCH_URL = "https://www.kaufda.de/webapp/api/slots/offerSearch"

# https://www.kaufda.de/webapp/api/slots/offerSearch?searchQuery=h%C3%A4hnchenbrust&lat=47.965625499999994&lng=11.753921799999999&size=25
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}



@dataclass(frozen=True)
class Deal:
    type: str
    price_min: float
    price_max: float
    price_by_base_unit: str

    def price_range_str(self) -> str:
        if self.price_min == self.price_max:
            return f"{self.price_min}€"
        else:
            return f"{self.price_min}€ - {self.price_max}€"

    def normalized_price_by_base_unit(self) -> str | None:
        return normalize_price(self.price_by_base_unit)


@dataclass(frozen=True)
class SearchResult:
    publisher_name: str
    article: str
    deals: tuple[Deal]
    description: str
    pub_dates: list[tuple[datetime, datetime]]

    def min_price(self) -> float:
        return min(deal.price_min for deal in self.deals)

    def __str__(self) -> str:
        obj_string =  f"{self.article} | {self.publisher_name} | {self.description} || {'|'.join([d.__str__() for d in self.deals])}"
        return obj_string

    def to_markdown(self):
        obj_string =  f"{self.publisher_name}, {self.description}: \n"
        for deal in self.deals:
            if deal.type in ['RECOMMENDED_RETAIL_PRICE', 'REGULAR_PRICE']:
                continue
            obj_string += f"- {deal.price_range_str()}"
            # obj_string += f"- {deal.type}: {deal.price_range_str()}"
            if deal.price_by_base_unit:
                obj_string += f" ({deal.normalized_price_by_base_unit()})\n"
        for (start, end) in self.pub_dates:
            obj_string += f"- {TAGE[start.weekday()]} {start.strftime('%d.%m') if start else '?'} - {TAGE[end.weekday()]} {end.strftime('%d.%m') if end else '?'}\n"

        return obj_string

    def to_sha256(self):
        return sha256(self.to_markdown().encode('utf-8')).hexdigest()



def search_article(article: str, preffered_publishers: List[str] | None = None) -> List[SearchResult]:
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
    contents = data.get("_embedded", []).get("contents", [])

    publisher_filtered_contents = list(filter(lambda e: e.get("content", {}).get("publisherName", "").lower() in preffered_publishers, contents)) if preffered_publishers else contents
    found_results = list()
    for result_entry in publisher_filtered_contents:
        try:

            search_result = extract_content(result_entry, article)
            if search_result:
                found_results.append(search_result)


        except Exception as e:
            print(f"Exception: {e}")
            continue

    return list(found_results)


def extract_content(result_entry: dict, searched_article: str) -> SearchResult | None:
    content_object = result_entry.get("content", {})

    publisher_name = content_object.get("publisherName")
    pub_dates = []
    for publicationProfile in content_object.get("publicationProfiles", []):
        start = publicationProfile.get("validity", {}).get("startDate")
        end = publicationProfile.get("validity", {}).get("endDate")

        start_parsed = parser.parse(start) if start else None
        end_parsed = parser.parse(end) if end else None
        pub_dates.append((start_parsed, end_parsed))

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

            deals_dataobjects: list[Deal] = []
            for deal in deals:
                deal_type = deal.get("type")
                price_min = min(deal.get("min"), deal.get("max"))
                price_max = max(deal.get("min"), deal.get("max"))
                price_by_base_unit = deal.get("priceByBaseUnit")

                if 'EUR' != deal.get("currencyCode", "EUR"):
                    raise ValueError(f"Unexpected currency: {deal.get('currencyCode')}")

                deals_dataobjects.append(Deal(type=deal_type, price_min=price_min, price_max=price_max, price_by_base_unit=price_by_base_unit))

            # Versuche zuerst SALES_PRICE zu extrahieren, sonst REGULAR_PRICE
            search_result = SearchResult(publisher_name=publisher_name, article=searched_article,
                                         deals=tuple(deals_dataobjects), description=description, pub_dates=pub_dates)
            return search_result

        return None



def run(category: str, articles: List[str], publishers: List[str] | None = None):

    print("")
    print(f"## {category}")
    for article in articles:
        #print(f"🔎 {article}")

        try:
            results = search_article(article, publishers)

            if results:
                print(article)
                for result in sorted(results, key=lambda r: r.min_price()):
                    print(result.to_markdown())

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
    publishers = config.get("publishers")

    for category, items in config.get("articles", {}).items():
        if items:
            run(category, items, publishers)





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