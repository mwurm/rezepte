#!/usr/bin/env python
import requests
import json
import argparse
import sys
import io
import re
from PIL import Image
import os
from rotunicode import rudecode


def to_snake_case(s):
    # Replace all non-alphanumeric characters with underscores
    s = "".join(c if c.isalnum() else "_" for c in s)
    # Convert to lowercase and join words with underscores
    return "_".join(word.lower() for word in s.split())

# Define a class for the deep domain model
class Recipe:
    def __init__(self, name, recipe_yield, ingredients, instructions):
        self.name = name
        self.recipe_yield = recipe_yield
        self.ingredients = ingredients
        self.instructions = instructions


class RecipeIngredient:
    def __init__(self, note):
        note = re.sub('Packung', 'Pkg', note, flags=re.IGNORECASE)
        note = re.sub('Päckchen', 'Pkg', note, flags=re.IGNORECASE)
        note = re.sub('Teelöffel', 'TL', note, flags=re.IGNORECASE)
        note = re.sub('Esslöffel', 'EL', note, flags=re.IGNORECASE)
        note = re.sub('(\d+)bis(\d+)', '\1-\2', note, flags=re.IGNORECASE)

        self.note = note


class RecipeInstruction:
    def __init__(self, text):
        self.text = text




if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('recipe_urls', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    # Hole Bearer Token
    data = {
        "username": "changeme@email.com",
        "password": "MyPassword"
    }
    response = requests.post("https://demo.mealie.io/api/auth/token", data=data)
    json_data = json.loads(response.text)
    token = json_data["access_token"]
    print(f"auth_token: {token}")
    # Generiere Abhol-URL für das JSON-Rezept ("create-url")
    headers = {
        "authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Read JSON string from file
    for recipe_url in args.recipe_urls:
        data = {
            "url": recipe_url,
            "includeTags": False
        }

        response = requests.post("https://demo.mealie.io/api/recipes/create-url", headers=headers, json=data)
        json_url = json.loads(response.text)
        print(f"generated recipe id: {json_url}")

        # Hole JSON-Rezept ab
        headers = {
            "authorization": f"Bearer {token}"
        }

        json_recipe_response = requests.get(f"https://demo.mealie.io/api/recipes/{json_url}", headers=headers)
        print(f"result code: {json_recipe_response.status_code}")

        # print(json_recipe_response.text)

        
        # Decode the JSON string into a Python dictionary
        data = json.loads(json_recipe_response.text)

        # Create an instance of the Recipe class with the decoded data

        ingredients = []
        for i in data["recipeIngredient"]: # lst is the list that contains the data
            ingr = RecipeIngredient(i["note"])
            ingredients.append(ingr)

        instructions = []
        for i in data["recipeInstructions"]: # lst is the list that contains the data
            instr = RecipeInstruction(i["text"])
            instructions.append(instr)

        recipe = Recipe(
            name=data["name"],
            recipe_yield=int(re.sub(r'(\d+).*', r'\1', data["recipeYield"] if data["recipeYield"] else "0")),
            ingredients=ingredients,
            instructions=instructions
        )

        recipe.original_recipe_url = recipe_url

        original_stdout = sys.stdout # Save a reference to the original standard output

        recipe_id = rudecode(to_snake_case(recipe.name))
        out_file_name = "src/rmd/" + recipe_id + ".rmd"
        print(f"Write recipe to {out_file_name}")
        with open(out_file_name, 'w', encoding="UTF-8") as f:
            sys.stdout = f # Change the standard output to the file we created.
            
            print(recipe.name)
            print(f":category: TODO")
            print(f":tags: ausprobieren")
            print(f":yields: {recipe.recipe_yield}")
            print(f":url: {recipe.original_recipe_url}")
            print()
            for ingr in recipe.ingredients:
                print(ingr.note)

            print()
            for instr in recipe.instructions:
                print("# " + instr.text)

            sys.stdout = original_stdout # Reset the standard output to its original value


        mealie_recipe_id = data["id"]
        recipe_image_response = requests.get(f"https://demo.mealie.io/api/media/recipes/{mealie_recipe_id}/images/original.webp", headers=headers)
        if recipe_image_response.status_code == 200:
            with Image.open(io.BytesIO(recipe_image_response.content)) as img:
                # Create a new filename with the same name as the webp file but with a .jpg extension
                webp_image_path = recipe_id + ".webp"
                new_filename = "images/" + recipe_id + ".jpg"
                # Convert the image to JPEG format and save it with the new filename
                img.convert('RGB').save(new_filename, 'JPEG')
                print(f'Successfully converted mealie webp image to {new_filename}')
        else:
            print(f'Error downloading image url: status code {recipe_image_response.status_code}')
