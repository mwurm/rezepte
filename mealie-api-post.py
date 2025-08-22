#!/usr/bin/env python3
import os
import pprint
import json
import random
import time

import requests
import dotenv
import os
from rmd_to_asciidoc import Recipe, parse_recipe, Ingredient
import csv
import pandas as pd




def update_food():
    df = pd.read_csv("src/lebensmittel_kategorisiert.csv")
    for index, row in df.iterrows():
        ingredient = Ingredient(100, " Gramm", row['Singular'], preparation_notes=None)
        result = parse_ingredients([ingredient], fail_on_error=False)
        print(f"PARSED {row['Singular']}:")
        print(result)

        if result and ('label' not in result[0]['food'] or not result[0]['food']['label'] or (result[0]['food']['label'] and result[0]['food']['label']['name'] != row['Kategorie'])):

            response = requests.get(f"{MEALIE_API_URL}/foods/{result[0]['food']['id']}", headers=headers)
            json_food = json.loads(response.text)
            json_food["labelId"] = get_label(row['Kategorie'])['id']
            response = requests.put(f"{MEALIE_API_URL}/foods/{result[0]['food']['id']}", json=json_food, headers=headers)
            assert response.status_code == 200, f"Fehler beim Aktualisieren des Lebensmittels: {response.text}"

            if 'label' not in result[0]['food'] or not result[0]['food']['label']:
                print(f"{row['Singular']}: Fehlendes 🏷Label gesetzt zu: {row['Kategorie']}")
            elif result[0]['food']['label'] and result[0]['food']['label']['name'] != row['Kategorie']:
                print(f"{row['Singular']}: 🏷Label geändert von {result[0]['food']['label']['name']} zu: {row['Kategorie']}")


        if not result:
            food_dict = {
              "name": row['Singular'],
            }
            if pd.notna(row['Plural']):
                food_dict["pluralName"] = row['Plural']

            if pd.notna(row['Kategorie']):
                food_dict["labelId"] = get_label(row['Kategorie'])['id']

            response = requests.post(f"{MEALIE_API_URL}/foods", json=food_dict, headers=headers)
            print(response.text)
            print(f"✅ {row['Singular']} hinzugefügt, 🏷Label {row['Kategorie']}")

def post_recipe(recipe: Recipe):
    mealie_dict_recipe = {}
    mealie_dict_recipe["name"] = recipe.name

    response = requests.get(f"{MEALIE_API_URL}/recipes?search={recipe.name}", headers=headers)
    results = json.loads(response.content)
    items = list(filter(lambda x: x['name'] == recipe.name, results['items']))
    if len(items) > 0:
        if len(items) > 1:
            print(f"❌ Mehrere Rezepte mit dem Namen {recipe.name} gefunden, bitte Duplikate löschen: {[x['slug'] for x in items]}")
            exit(1)
        print(f"Rezept {recipe.name} ({recipe.to_id()}) existiert bereits, verwende es zur Aktualisierung...")
        mealie_dict_recipe["slug"] = items[0]['slug']
    else:
        response = requests.post(f"{MEALIE_API_URL}/recipes", json=mealie_dict_recipe, headers=headers)
        if response.status_code == 201:
            print("✅ Rezept erfolgreich angelegt:", response.text)

            #js = json.loads(response.content)
            #pprint.pprint(js, compact=True)
        else:
            print("❌ Fehler:", response.status_code, response.text)
            return None
        mealie_dict_recipe["slug"] = response.text.replace("\"", "")
        print(mealie_dict_recipe["slug"])

    response = requests.get(f"{MEALIE_API_URL}/recipes/{mealie_dict_recipe["slug"]}", headers=headers)
    mealie_dict_recipe = json.loads(response.text)
    mealie_dict_recipe["recipeCategory"] = get_or_create_categories([recipe.category])
    mealie_dict_recipe["tags"] = get_or_create_tags(recipe.tags)

    mealie_dict_recipe["recipeServings"] = float(recipe.yields)
    #mealie_dict_recipe["recipeYieldQuantity"] = float(recipe.yields)
    if recipe.info:
        mealie_dict_recipe["description"] = recipe.info
    if recipe.asciidoc_footer:
        mealie_dict_recipe["notes"] = [{
            "title": "",
            "text": recipe.asciidoc_footer,
        }]

    # "notes": [
    #     {
    #       "title": "<Notiz-Titel>",
    #       "text": "<Notiz-Text>"
    #     }
    #   ],

    mealie_dict_recipe["extras"] = {
       "rmd_file": f"{recipe.to_id()}.rmd"
    }


    #   "extras": {
    #     "rmd_file": "artischockensuppe.rmd"
    #   },




    ingredients_texts = []
    for iwi in recipe.instructions_with_ingredients:
        for ing in iwi.ingredients:
            ingredients_texts.append(ing)

    mealie_dict_recipe["recipeIngredient"] = parse_ingredients(ingredients_texts)


    mealie_dict_recipe["recipeInstructions"] = []
    ingredient_index = 0
    for iwi in recipe.instructions_with_ingredients:
        text = ""
        if len(iwi.ingredients) > 0:
            text = "**"
            text = text + ", ".join([ing.ingredient_name for ing in iwi.ingredients])
            text = text + "**: "
        text = text + "\n".join([i for i in iwi.instructions])
        step_dict = {
            "text": text,
            "ingredientReferences": []
        }
        for _ in iwi.ingredients:
            ref_id = mealie_dict_recipe["recipeIngredient"][ingredient_index]['referenceId']
            step_dict["ingredientReferences"].append({"referenceId": ref_id})
            ingredient_index = ingredient_index + 1

        mealie_dict_recipe["recipeInstructions"].append(step_dict)

    #mealie_dict_recipe["name"] = mealie_dict_recipe["name"] + str(random.randint(1000, 9999))
    #pprint.pprint(mealie_dict_recipe, compact=True)
    response = requests.patch(f"{MEALIE_API_URL}/recipes/{mealie_dict_recipe["slug"]}", json=mealie_dict_recipe, headers=headers)
    if response.status_code == 201 or response.status_code == 200 :
        print("✅ Rezept erfolgreich aktualisiert:", response.text)
        return response.text
        #js = json.loads(response.content)
        #pprint.pprint(js, compact=True)
    else:
        print("❌ Fehler:", response.status_code, response.text)
        return None


def get_or_create_tags(tags: list[str]) -> list[dict]:
    tag_dict_list = []
    for tag in tags:
        response = requests.get(f"{MEALIE_API_URL}/organizers/tags?perPage=1000", headers=headers)
        json_tags = json.loads(response.text)
        tag_found = False
        for t in json_tags['items']:
            if t['name'] == tag:
                tag_dict_list.append({
                    "id": t['id'],
                    "name": t['name'],
                    "slug": t['slug']
                })
                #print(f"Tag '{tag}' gefunden und hinzugefügt.")
                tag_found = True
                break
        if not tag_found:
            tag_dict = {}
            tag_dict["name"] = tag
            response = requests.post(f"{MEALIE_API_URL}/organizers/tags", json=tag_dict, headers=headers)
            assert response.status_code in [200, 201], f"Fehler beim Anlegen des Tags {tag}: {response.text}"
            t = json.loads(response.text)
            tag_dict_list.append(t)
            #print(f"Tag '{tag}' erstellt und hinzugefügt.")
    return tag_dict_list


def parse_ingredients(ingredients: list[Ingredient], fail_on_error=True) -> list | None:
    modified_ingredients = ingredients.copy()
    # Ausführlichere Einheit, damit Parse besser funktioniert
    for i in modified_ingredients:
        if i.unit == "g":
            i.unit = " Gramm"
        if i.unit == "kg":
            i.unit = " Kilogramm"
        if i.unit == "ml":
            i.unit = " Milliliter"
    jdict = {
        "parser": "brute",
        "ingredients": [i.to_string(no_amount_alias=0, no_unit_alias=" Stück", skip_preparation_notes=True) for i in ingredients]
    }
    response = requests.post(f"{MEALIE_API_URL}/parser/ingredients", json=jdict, headers=headers)
    results = json.loads(response.text)
    ingredients_dict = []
    any_error = False
    for (ingredient, result) in zip(ingredients, results):
        if result['confidence']['average'] < .75:
            print(f"❌ Geringe Confidence für '{result}")
            any_error = True
        elif not result['ingredient']['food']['id']:
            print(f"❌ Food {result['input']} hat keine ID: {result['ingredient']['food']}. Bitte anlegen")
            any_error = True
        elif result['ingredient']['unit'] and not result['ingredient']['unit']['id']:
            print(f"❌ Unit {result['input']} hat keine ID: {result['ingredient']['food']}. Bitte anlegen")
            any_error = True
        else:
            result['ingredient']['note'] = ingredient.preparation_notes
            ingredients_dict.append(result['ingredient'])

    if any_error:
        if fail_on_error:
            exit(1)
        else:
            return None
    return ingredients_dict


def get_or_create_categories(categories: list[str]) -> list[dict]:
    cat_dict_list = []
    for cat in categories:
        response = requests.get(f"{MEALIE_API_URL}/organizers/categories", headers=headers)
        json_categories = json.loads(response.text)
        cat_found = False
        for t in json_categories['items']:
            if t['name'] == cat:
                cat_dict_list.append({
                    "id": t['id'],
                    "name": t['name'],
                    "slug": t['slug']
                })
                #print(f"Category '{cat}' gefunden und hinzugefügt.")
                cat_found = True
                break
        if not cat_found:
            cat_dict = {}
            cat_dict["name"] = cat
            response = requests.post(f"{MEALIE_API_URL}/organizers/categories", json=cat_dict, headers=headers)
            t = json.loads(response.text)
            cat_dict_list.append(t)
            #print(f"Category '{cat}' erstellt und hinzugefügt.")
    return cat_dict_list


def get_label(label: str) -> dict:
    response = requests.get(f"{MEALIE_API_URL}/groups/labels", headers=headers)
    json_labels = json.loads(response.text)
    cat_found = False
    for t in json_labels['items']:
        if t['name'] == label:
            return t

    print(f"❌ Label {label} nicht gefunden: Bitte anlegen")
    exit(1)


dotenv.load_dotenv()

# Deine Mealie-Instanz
MEALIE_API_URL = os.environ.get("MEALIE_API_URL")



# Request-Header mit Authentifizierung
headers = {
    "Authorization": f"Bearer {os.environ.get("MEALIE_API_KEY")}",
    "accept": "application/json",
    "Content-Type": "application/json"
}

update_food()

# Rezept senden
for file in os.listdir("src/rmd"):
    if file.endswith(".rmd"):
        with open(f"src/rmd/{file}", 'r', encoding="utf-8") as f:
            #print(f"Reading {f.name}")
            recipe = parse_recipe(f.read())
            if "Mealie" not in recipe.tags and "MealieTodo" not in recipe.tags and "TODO" not in recipe.tags:
                #search = Pfannkuchen
                response = requests.get(f"{MEALIE_API_URL}/recipes?search={recipe.name}", headers=headers)
                results = json.loads(response.content)
                if results['total'] > 0:
                    if 'recipeServings' in results['items'][0] and results['items'][0]['recipeServings'] == float(recipe.yields):
                        print(f"Rezept {recipe.name} ({recipe.to_id()}) existiert bereits, überspringe ...")
                        continue

                print(f"Poste Rezept {recipe.name} ({recipe.to_id()}) ...")
                recipe_id = post_recipe(recipe)
                print(f"✅ Rezept {recipe.name} ({recipe.to_id()}) erfolgreich gepostet: {recipe_id}")



#with open("src/rmd/artischockensuppe.rmd", 'r', encoding="utf-8") as f:
#    print(f"Reading {f.name}")
#    recipe = parse_recipe(f.read())

    #recipe_id = post_recipe(recipe)
    #response = requests.get(f"{MEALIE_API_URL}/foods", headers=headers)
    #jfoods = json.loads(response.text)
    #print(response.text)


#
# response = requests.get(f"{MEALIE_API_URL}/recipes/artischockensuppe-5", headers=headers)
# print(response.text)

# Output aller Zutaten in ausgewählten RMD-Dateien
# ingredient_name_set = set()
# for file in os.listdir("src/rmd"):
#     if file.endswith(".rmd"):
#         with open(f"src/rmd/{file}", 'r', encoding="utf-8") as f:
#             #print(f"Reading {f.name}")
#             recipe = parse_recipe(f.read())
#             if "MealieTodo" in recipe.tags:
#                 ingredient_name_set = ingredient_name_set.union(
#                     set([x.ingredient_name for x in recipe.get_all_ingredients()]))
#
# for x in sorted(list(ingredient_name_set)):
#     print(x)

