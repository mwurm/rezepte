#!/usr/bin/env python
import argparse
import re

class Recipe:
    def __init__(self, name, attributes, instructions_with_ingredients):
        self.name = name
        self.attributes = attributes
        self.instructions_with_ingredients = instructions_with_ingredients

class InstructionsWithIngredients:
    def __init__(self, instructions, ingredients):
        self.instructions = instructions
        self.ingredients = ingredients

class Ingredient:
    def __init__(self, amount, unit, ingredient_name, preparation_notes):
        self.amount = amount
        self.unit = unit
        self.ingredient_name = ingredient_name
        self.preparation_notes = preparation_notes

    def __str__(self):
        return f"{int(self.amount) if self.amount.is_integer() else self.amount}{'' if self.unit is None else self.unit} {self.ingredient_name}{'' if self.preparation_notes is None else '; ' + self.preparation_notes}"

class IngredientFactory:
    def get_ingredient(self, ingredient):
        # Define regular expression patterns to match amounts, units, and ingredients
        amount_pattern = r'\d+|\d+\.\d+|\d+\/\d+'  # Matches numeric amounts, fractions, and common non-numeric amounts
        unit_pattern = r'[a-zA-Z]+'  # Matches zero or more letters
        unit_pattern += r'|\s+[mk]?[gl]|\s+TL|\s+EL|\s+Prisen?|\s+Zweige?|\s+Zehen?|\s+Scheiben?|\s+Stücke?|\s+St\.?|\s+Bund|\s+Bd\.?|\s+Pkg\.?|\s+Packung|\s+Dosen?'  # Matches common non-standard units of measurement
        ingredient_pattern = r'[^;]+'  # Matches anything but ; (which is use to separate preparation notes)
        preparation_notes_pattern = r'.+'  # Matches one or more of any character
        # Define a regular expression pattern to match the entire ingredient string
        pattern = r'^({})({})?\s+({})(;({}))?$'.format(amount_pattern, unit_pattern, ingredient_pattern, preparation_notes_pattern)
        
        # Attempt to match the pattern to the ingredient string
        match = re.match(pattern, ingredient)
        
        if match:
            # Extract the amount, unit, and ingredient from the match object
            amount = match.group(1)
            # unit = None if match.group(2) is None else match.group(2).strip()
            unit = match.group(2)
            ingredient = match.group(3)
            preparation_notes = None if match.group(5) is None else match.group(5).strip()
            
            # Convert the amount to a float if it exists
            if amount:
                if '/' in amount:
                    numerator, denominator = amount.split('/')
                    amount = float(numerator) / float(denominator)
                elif amount.lower() == 'eine' or amount.lower() == 'ein':
                    amount = 1.0
                else:
                    amount = float(amount)
            
            # Return a tuple containing the amount, unit, and ingredient
            return Ingredient(amount, unit, ingredient, preparation_notes)
        else:
            # Return None if the ingredient string does not match the pattern
            raise Exception(f"Could not match ingredient string pattern for: {ingredient}")



def parse_recipe(input_str):
    ingredient_factory = IngredientFactory()

    lines = input_str.split("\n")
    name = lines[0]
    attributes = []
    ingredients = []
    instructions_with_ingredients = []
    for line in lines[1:]:
        if line.startswith("#"):
            instructions = line[1:].strip()
            instructions_with_ingredients.append(InstructionsWithIngredients(instructions, ingredients))
            ingredients = []
        elif line.startswith(":"):
            attributes.append(line[1:].strip())
        elif line:
            #parts = line.split(";")
            #quantity, ingredient = parts[0], ";".join(parts[1:])
            #ingredients.append((quantity.strip(), ingredient.strip()))
            ingredients.append(ingredient_factory.get_ingredient(line))
    
    return Recipe(name, attributes, instructions_with_ingredients)




if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='rmd file', required=True)
    args = parser.parse_args()

    input_str = None
    # Read string from file
    with open(args.file) as f:
        input_str = f.read()

    recipe = parse_recipe(input_str)
    print("Rezept: " + recipe.name)
    print(f"Attribute: {recipe.attributes}")
    for ii in recipe.instructions_with_ingredients:
        for ing in ii.ingredients:
            print(ing)
        print(f"# {ii.instructions}")
