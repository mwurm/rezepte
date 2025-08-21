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


def post_recipe(recipe: Recipe):

    mealie_dict_recipe = {}
    mealie_dict_recipe["name"] = recipe.name


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
    mealie_dict_recipe["recipeYieldQuantity"] = float(recipe.yields)
    mealie_dict_recipe["description"] = recipe.info



    ingredients_texts = []
    for iwi in recipe.instructions_with_ingredients:
        for ing in iwi.ingredients:
            ingredients_texts.append(ing)

    mealie_dict_recipe["recipeIngredient"] = parse_ingredients(ingredients_texts)


    mealie_dict_recipe["recipeInstructions"] = []
    ingredient_index = 0
    for iwi in recipe.instructions_with_ingredients:

        for instruction in iwi.instructions:
            text = ""
            if len(iwi.ingredients) > 0:
                text = "**"
                text = text + ", ".join([ing.ingredient_name for ing in iwi.ingredients])
                text = text + "**: "
            text = text + instruction
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
        response = requests.get(f"{MEALIE_API_URL}/organizers/tags", headers=headers)
        json_tags = json.loads(response.text)
        tag_found = False
        for t in json_tags['items']:
            if t['name'] == tag:
                tag_dict_list.append({
                    "id": t['id'],
                    "name": t['name'],
                    "slug": t['slug']
                })
                print(f"Tag '{tag}' gefunden und hinzugefügt.")
                tag_found = True
                break
        if not tag_found:
            tag_dict = {}
            tag_dict["name"] = tag
            response = requests.post(f"{MEALIE_API_URL}/organizers/tags", json=tag_dict, headers=headers)
            t = json.loads(response.text)
            tag_dict_list.append(t)
            print(f"Tag '{tag}' erstellt und hinzugefügt.")
    return tag_dict_list


def parse_ingredients(ingredients: list[Ingredient]) -> dict:
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
        else:
            if result['ingredient']['unit']['name'] == "Stück":
                result['ingredient']['unit'] = ingredient.unit
            result['ingredient']['note'] = ingredient.preparation_notes
            ingredients_dict.append(result['ingredient'])

    if any_error:
        exit(1)
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
                print(f"Category '{cat}' gefunden und hinzugefügt.")
                cat_found = True
                break
        if not cat_found:
            cat_dict = {}
            cat_dict["name"] = cat
            response = requests.post(f"{MEALIE_API_URL}/organizers/categories", json=cat_dict, headers=headers)
            t = json.loads(response.text)
            cat_dict_list.append(t)
            print(f"Category '{cat}' erstellt und hinzugefügt.")
    return cat_dict_list

dotenv.load_dotenv()

# Deine Mealie-Instanz
MEALIE_API_URL = os.environ.get("MEALIE_API_URL")



# Request-Header mit Authentifizierung
headers = {
    "Authorization": f"Bearer {os.environ.get("MEALIE_API_KEY")}",
    "accept": "application/json",
    "Content-Type": "application/json"
}

# Rezept senden

with open("src/rmd/avocado-bulgur-salat.rmd", 'r', encoding="utf-8") as f:
    print(f"Reading {f.name}")
    recipe = parse_recipe(f.read())
    #print(recipe.to_asciidoc_section("Tikka Brathähnchen im Ofen"))



#recipe_id = post_recipe(recipe)
#response = requests.get(f"{MEALIE_API_URL}/foods", headers=headers)
#jfoods = json.loads(response.text)
#print(response.text)

food_dict = {
  "name": "Tomatenmark"
}

response = requests.post(f"{MEALIE_API_URL}/organizers/tags", json=food_dict, headers=headers)
print(response.text)

ingredient_name_set = set()
for file in os.listdir("src/rmd"):
    if file.endswith(".rmd"):
        with open(f"src/rmd/{file}", 'r', encoding="utf-8") as f:
            #print(f"Reading {f.name}")
            recipe = parse_recipe(f.read())
            ingredient_name_set = ingredient_name_set.union(set([x.ingredient_name for x in recipe.get_all_ingredients()]))

for x in sorted(list(ingredient_name_set)):
    print(x)
