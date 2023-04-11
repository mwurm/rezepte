#!/usr/bin/env python
import argparse
import re
import os
import glob

from rotunicode import rudecode

basic_ingredients = [
    "Ahornsirup",
    "Paprikapulver",
    "Senf",
    "Tomatenmark",
    "Butter",
    "Ei",
    "Eigelb",
    "Eiweiß",
    "Milch",
    "Salz",
    "Pfeffer",
    "Mehl",
    "Cumin",
    "Muskat",
    "Knoblauchzehen?",
    "Knoblauch",
    "Zwiebeln?",
    "Weinessig",
    "Rotweinessig",
    "Weißweinessig",
    "Olivenöl",
    "Öl",
    "Sonnenblumenöl"
    "Aceto balsamico",
    "Toast",
    "Hefe",
    "Trockenhefe",
    "frische Hefe",
    "Hefe (frisch)",
    "Hefe (trocken)",
    "Wasser",
    "Zucker",
    "Stärke",
    "Natron",
    "Zucker, braun",
    "Zucker (braun)",
    "Zucker, weiß",
    "Zucker (weiß)",
    "Vanillezucker",
    "Vanillinzucker",
    "Puderzucker",
    "Staubzucker",
    "Kakaopulver",
    "Speisestärke",
    "Honig",
    "Cumin",
    "Kreuzkümmel",
    "Estragon",
    "Oregano",
    "Lorbeer",
    "Fleischbrühe",
    "Gemüsebrühe",
    "Hühnerbrühe",
    "Brühe"
    

    
    ]

basic_ingredients_regex = "(" + ")|(".join(basic_ingredients) + ")"

def to_snake_case(s):
    # Replace all non-alphanumeric characters with underscores
    s = "".join(c if c.isalnum() else "_" for c in s)
    # Convert to lowercase and join words with underscores
    return "_".join(word.lower() for word in s.split())


class Cookbook:
    def __init__(self, recipes):
        self.recipes = recipes

    def write_to_adoc(self, directory, filename):
        if not os.path.exists(directory):
           os.makedirs(directory)

        f = open(f"{directory}/{filename}", "w")

        f.write(f""":imagesdir: images
:lang: DE
:hyphens:

:docinfo:

= Rezepte
:pdf-page-size: A5
:toc: left
:toclevels: 4
:toc-title:

""")

#        tags = {tuple(tag) for tag in [r.tags for r in self.recipes]}
        tags = sorted(set([item for sublist in [r.tags for r in self.recipes] for item in sublist]), key=lambda t: t.lower())
        f.write(f"Stichwörter: {'; '.join(list(tags))}\n\n")

        cookbook_categories = ["Basis", "Appetithäppchen", "Beilagen", "Salate", "Suppen", "Pasta", "Pizza & Co.", "Eintöpfe", "Aufläufe", "Ofengerichte", "Reisgerichte", "Fleischgerichte", "Geflügel", "Fisch", "Vegetarisches", "Desserts", "Mehlspeisen", "Gebäck", "Kuchen"]
        for recipe in self.recipes:
            if recipe.category not in cookbook_categories:
                raise Exception(f"Recipe {recipe.name} uses unknown category {recipe.category}")                

        for category in cookbook_categories:
            f.write(f"== {category}\n\n")
            for recipe in sorted(filter(lambda rec: rec.category == category and rec.subcategory is None, self.recipes), key=lambda r: r.name):
                f.write(recipe.to_asciidoc_section("==="))

        
            subcategories = set([r.subcategory for r in filter(lambda rec: rec.category == category and rec.subcategory is not None , self.recipes)])
            for subcategory in subcategories:
                f.write(f"=== {subcategory}\n\n")
                for recipe in sorted(filter(lambda rec: rec.category == category and rec.subcategory == subcategory , self.recipes), key=lambda r: r.name):
                    f.write(recipe.to_asciidoc_section("===="))
                

        f.write(f"== Rezepte nach Stichwort\n\n")
        for tag in ["leicht"]:
            f.write(f"=== {tag}\n\n")
            for recipe in sorted(filter(lambda rec: tag in rec.tags, self.recipes), key=lambda r: r.name):
                # * <<sec.curry_mango_garnelen, Curry-Mango-Garnelen>>
                f.write(f"* <<{recipe.sec_id()}, {recipe.name}>>\n")

        f.write("""

ifdef::backend-pdf[]
[%always]

<<<
[index]
== Index
endif::[]""")

        f.close()


class Recipe:
    def __init__(self, name, attributes, instructions_with_ingredients):
        self.name = name
        self.attributes = attributes
        self.yields = attributes['yields']
        self.category = attributes['category']
        self.subcategory = None if 'subcategory' not in attributes else attributes['subcategory'] 
        # ":indexterms: Garnelen, Curry-Mango-Garnelen; Mango-Garnelen"
        self.indexterms = () if 'indexterms' not in attributes else attributes['indexterms'].split(";")
        self.tags = () if 'tags' not in attributes else [t.strip() for t in attributes['tags'].split(";")]
        self.instructions_with_ingredients = instructions_with_ingredients

    def to_id(self):
        return rudecode(to_snake_case(self.name))

    def sec_id(self):
        return f"sec.{self.to_id()}"

    def write_to_adoc(self, directory):
        if not os.path.exists(directory):
           os.makedirs(directory)

        f = open(f"{directory}/{self.to_id()}.adoc", "w")
        f.write("Woops! I have deleted the content!")
        f.close()

    def to_asciidoc_section(self, caption): 
        out_str = "";
        out_str += f"""[%always]
<<<
[id='{self.sec_id()}']

indexterm:[{self.name}]
"""

        for indexterm in self.indexterms:
            out_str += f"indexterm:[{indexterm}]\n"

        out_str += f"""
{caption} {"💥" if "ausprobieren" in self.tags else ""}{self.name}

Portionen: {self.yields}, Stichwörter: {', '.join(self.tags)}

[%noheader, cols="1a,2", grid=rows]
|===
"""
        for instr_with_ingr in self.instructions_with_ingredients:
            out_str += """
|[%noheader, cols=">30%,70%", frame=none, grid=none]
!===
"""
            for ingr in instr_with_ingr.ingredients:
                out_str += f"{ingr.to_asciidoc_nested_table_row()}\n"
            out_str += f"""
!===
.^| {instr_with_ingr.instructions}
"""
        out_str += """|===

"""
        return out_str

class InstructionsWithIngredients:
    def __init__(self, instructions, ingredients):
        self.instructions = instructions
        self.ingredients = ingredients
        # Replace strings like "180°C" by "🌡180℃" using the special UTF-8 symbol ℃
        self.instructions = re.sub(r'(\d+)\s?(°C)', r'🌡\1℃', self.instructions)


class Ingredient:
    def __init__(self, amount, unit, ingredient_name, preparation_notes):
        self.amount = amount
        self.unit = unit
        self.ingredient_name = ingredient_name
        self.preparation_notes = preparation_notes

    def ingredient_name_highlighted(self):
        return self.ingredient_name if re.match(basic_ingredients_regex, self.ingredient_name) else "*" + self.ingredient_name + "*"

    def to_asciidoc_nested_table_row(self):
        amount_str = ""
        if self.amount is not None:
            amount_str = f"{int(self.amount) if self.amount.is_integer() else round(self.amount, 2)}"
        unit_str = ""
        if self.unit is not None:
            unit_str = re.sub(' ', '{nbsp}', self.unit, flags=re.IGNORECASE)
        return f"!{amount_str}{unit_str}!{self.ingredient_name_highlighted()}{'' if self.preparation_notes is None else '; _' + self.preparation_notes + '_'}"

    def __str__(self):
        amount_str = ""
        if self.amount is not None:
            amount_str = f"{int(self.amount) if self.amount.is_integer() else round(self.amount, 2)}"
        return f"{amount_str}{'' if self.unit is None else self.unit} {self.ingredient_name}{'' if self.preparation_notes is None else '; ' + self.preparation_notes}"

class IngredientFactory:
    def get_ingredient(self, ingredient):
        # Define regular expression patterns to match amounts, units, and ingredients
        amount_pattern = r'\d+|\d+\.\d+|\d+\/\d+'  # Matches numeric amounts, fractions, and common non-numeric amounts
        unit_pattern = r'[a-zA-Z]+'  # Matches zero or more letters
        unit_pattern += r'|\s+[cmk]?[glm]|\s+TL|\s+EL|\s+Glas|\s+Prisen?|\s+Pr\.?|\s+Zweige?|\s+Zehen?|\s+Scheiben?|\s+Stücke?|\s+Stk?\.?|\s+Bund|\s+Bd\.?|\s+Bn\.?|\s+Pkg\.?|\s+Packung|\s+Dosen?|\s+Becher|\s+Bch\.?|\s+Be\.?|\s+Beutel|\s+Btl\.?|\s+Stangen?|\s+Stg\.?|\s+Stiele?|\s+Blatt|\s+Blätter|\s+Bl\.?'  # Matches common non-standard units of measurement
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
    attributes = {}
    ingredients = []
    instructions_with_ingredients = []
    for line in lines[1:]:
        if line.startswith("#"):
            instructions = line[1:].strip()
            instructions_with_ingredients.append(InstructionsWithIngredients(instructions, ingredients))
            ingredients = []
        elif line.startswith(":"):
            # attributes :yields: 4
            split_line = line.split(":")
            attributes[split_line[1].strip()] = split_line[2].strip()
        elif line:
            #parts = line.split(";")
            #quantity, ingredient = parts[0], ";".join(parts[1:])
            #ingredients.append((quantity.strip(), ingredient.strip()))
            ingredients.append(ingredient_factory.get_ingredient(line))
    
    return Recipe(name, attributes, instructions_with_ingredients)




if __name__ == '__main__':
    # Parse command line arguments
    # ./rmd_to_asciidoc.py -t src-generated src/rmd/*.rmd
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--target', help='target directory', required=False)
    parser.add_argument('source_files', nargs=argparse.REMAINDER)

    args = parser.parse_args()

    recipes = []
    for filename in args.source_files:
        with open(filename, 'r') as f:
            print(f"Reading {f.name}")
            recipe = parse_recipe(f.read())
            recipes.append(recipe)
            if args.target is not None:
                recipe.write_to_adoc(args.target)

    cookbook = Cookbook(recipes)
    
    cookbook.write_to_adoc(".", "index.adoc")

