from datetime import datetime
from collections import defaultdict
from typing import Iterable
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
    conditions: list[str]

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
    image_url: str | None
    deals: tuple[Deal]
    description: str
    pub_dates: list[tuple[datetime, datetime]]

    def min_price(self) -> float:
        return min(deal.price_min for deal in self.deals)

    def __str__(self) -> str:
        obj_string =  f"{self.article} | {self.publisher_name} | {self.description} || {'|'.join([d.__str__() for d in self.deals])}"
        return obj_string

    def to_markdown(self):
        obj_string =  f"{self.publisher_name}, {self.article}, {self.description}: \n"
        obj_string +=  f"{self.image_url}\n"
        for deal in self.deals:
            if deal.type in ['RECOMMENDED_RETAIL_PRICE', 'REGULAR_PRICE']:
                continue
            obj_string += f"- {deal.price_range_str()}"
            # obj_string += f"- {deal.type}: {deal.price_range_str()}"
            if deal.conditions:
                obj_string += f" [{', '.join(deal.conditions)}]"
            if deal.price_by_base_unit:
                obj_string += f" ({deal.normalized_price_by_base_unit()})"
            obj_string += "\n"
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
    publisher_name = 'Netto' if publisher_name and publisher_name.lower() == 'netto marken-discount' else publisher_name
    image_url = content_object.get("image", {}).get("url", None)

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
            article_name_from_category_path = "/".join([cp[-1].get('name') for cp in category_paths])
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
                conditions = deal.get('conditions', [])
                condition_strings = []
                for condition in conditions:
                    for key, value in condition.items():
                        if isinstance(value, str):
                            condition_strings.append(value)
                        else:
                            condition_strings.append(f"{key}: {value}")

                if 'EUR' != deal.get("currencyCode", "EUR"):
                    raise ValueError(f"Unexpected currency: {deal.get('currencyCode')}")

                deals_dataobjects.append(Deal(type=deal_type, price_min=price_min, price_max=price_max, price_by_base_unit=price_by_base_unit, conditions=condition_strings))

            # Versuche zuerst SALES_PRICE zu extrahieren, sonst REGULAR_PRICE
            search_result = SearchResult(publisher_name=publisher_name, article=article_name_from_category_path,
                                         image_url=image_url,
                                         deals=tuple(deals_dataobjects), description=description, pub_dates=pub_dates)
            return search_result

        return None



def run(category: str, articles: List[str], publishers: List[str] | None = None):

    print("")
    print(f"# {category}")
    for article in articles:
        #print(f"🔎 {article}")

        try:
            results = search_article(article, publishers)

            if results:
                print(f"## {article}")
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


def extract_price_per_kg(result: SearchResult) -> float | None:
    """
    Extrahiert den niedrigsten €/kg Preis aus allen Deals eines SearchResults.
    Ignoriert 0.0€ Angebote.
    """
    prices = []

    for deal in result.deals:
        if deal.price_min == 0.0:
            continue

        normalized = deal.normalized_price_by_base_unit()
        if not normalized:
            continue

        # erwartet Format wie "15.98€/kg"
        match = re.search(r"([\d\.]+)\s*€/[kg|ml|l]", normalized)
        if match:
            prices.append(float(match.group(1)))

    return min(prices) if prices else None


def detect_badges(result: SearchResult) -> str:
    """
    Erkennt optionale UX-Emojis.
    """
    text = (result.description or "").lower()

    badges = []

    if "tiefgefroren" in text:
        badges.append("❄️")

    if "bio" in text:
        badges.append("🌱")

    return " ".join(badges)


def group_by_article(results: Iterable[SearchResult]) -> dict[str, list[tuple[str, float, str]]]:
    """
    Gruppiert nach Artikelname.
    """
    grouped = defaultdict(list)

    for r in results:
        price_per_kg = extract_price_per_kg(r)
        if price_per_kg is None:
            continue

        badges = detect_badges(r)
        grouped[r.article].append((r.publisher_name, price_per_kg, badges))

    return grouped


def format_ultra_scan(results: Iterable[SearchResult]) -> str:
    grouped = group_by_article(results)
    lines = []

    for article, entries in grouped.items():
        # nach Preis sortieren
        entries = sorted(entries, key=lambda x: x[1])

        top3 = entries[:3]
        if not top3:
            continue

        formatted = []

        for i, (store, price, badges) in enumerate(top3):
            medal = ["🥇", "🥈", "🥉"][i]

            extra = ""
            if i == 0 and len(top3) > 1:
                diff_ratio = (top3[1][1] - price) / top3[1][1]
                if diff_ratio > 0.20:
                    extra = " 🔥"
                elif diff_ratio < 0.05:
                    extra = " ⚖️"

            badge_str = f" {badges}" if badges else ""

            formatted.append(
                f"{medal} {store} {price:.2f}€{extra}{badge_str}"
            )

        line = f"{article} → " + " | ".join(formatted)
        lines.append(line)

    return "\n".join(sorted(lines))


if __name__ == "__main__":
    config = load_config("kaufda.yaml")
    publishers = config.get("publishers")

    for category, items in config.get("articles", {}).items():
        if items:
            run(category, items, publishers)
    exit(0)


    for category, items in config.get("articles", {}).items():
        if items:
            results = []
            for article in items:
                results.extend(search_article(article, publishers))
            if len(results) > 0:
                print(f"\n# {category}")
                print(format_ultra_scan(results))



