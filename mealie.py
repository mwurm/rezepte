#!/usr/bin/env python
import requests
import json
import argparse
import sys
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
        self.note = note

class RecipeInstruction:
    def __init__(self, text):
        self.text = text




if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url', help='recipe URL', required=True)
    args = parser.parse_args()

    # Read JSON string from file
    recipe_url = args.url

    # Hole Bearer Token
    data = {
        "username": "changeme@email.com",
        "password": "demo"
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

    


    # Decode the JSON string into a Python dictionary
    data = json.loads(json_recipe_response.text)

    # Create an instance of the Person class with the decoded data

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
        recipe_yield=data["recipeYield"],
        ingredients=ingredients,
        instructions=instructions
    )

    recipe.original_recipe_url = recipe_url

    original_stdout = sys.stdout # Save a reference to the original standard output

    out_file_name = rudecode(to_snake_case(recipe.name)) + ".rmd"
    print(f"Write recipe to {out_file_name}")
    with open(out_file_name, 'w') as f:
        sys.stdout = f # Change the standard output to the file we created.
        
        print(recipe.name)
        print(recipe.recipe_yield)
        print(recipe.original_recipe_url)
        print()
        for ingr in recipe.ingredients:
            print(ingr.note)

        print()
        for instr in recipe.instructions:
            print("# " + instr.text)

        sys.stdout = original_stdout # Reset the standard output to its original value


