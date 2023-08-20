#!/usr/bin/env python3
import argparse
import re
import os
import glob
import json

from rotunicode import rudecode

basic_ingredients_regexes = [
    "Ahornsirup",
    "Paprikapulver",
    "Senf",
    "Tomatenmark",
    "Butter",
    "Ei",
    "Eigelb",
    "Eiweiß",
    "Eiklar",
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
    "Hefe",
    "Wasser",
    "Zucker",
    "Stärke",
    "Natron",
    "Zucker",
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
    "Rinderbrühe",
    "Fleischbrühe",
    "Gemüsebrühe",
    "Hühnerbrühe",
    "Brühe"
]

# ergänze Regex am ende mit ((\s*,.*)?(\s*\(.*\))?)*$
# das Deckt folgende Zutatenerweiterungen ab:
# Hefe (frisch)
# Hefe, frisch
# Mehl, Typ 405, Weizen

basic_ingredients_regexes = [f'{r}((\s*,.*)?(\s*\(.*\))?)*$' for r in basic_ingredients_regexes]
basic_ingredients_regex = "(" + ")|(".join(basic_ingredients_regexes) + ")"

def to_snake_case(s):
    # Replace all non-alphanumeric characters with underscores
    s = "".join(c if c.isalnum() else "_" for c in s)
    # Convert to lowercase and join words with underscores
    return "_".join(word.lower() for word in s.split())


class Ingredient:
    def __init__(self, amount: float, unit: str, ingredient_name: str, preparation_notes: str):
        self.amount = amount
        self.unit = unit
        self.ingredient_name = ingredient_name
        self.preparation_notes = preparation_notes

    def ingredient_name_highlighted(self):
        return self.ingredient_name if re.match(basic_ingredients_regex, self.ingredient_name, re.IGNORECASE) else "*" + self.ingredient_name + "*"

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
        amount_pattern = r'\d+|\d+\.\d+|\d+\/\d+|_|etwas'  # Matches numeric amounts, fractions, and common non-numeric amounts
        unit_pattern = r'[a-zA-Z]+'  # Matches zero or more letters
        unit_pattern += r'|\s+[cmk]?[glm]|\s+TL|\s+EL|\s+geh\.?\s+TL|\s+geh\.?\s+EL|\s+Glas|\s+Prisen?|\s+Pr\.?|\s+Zweige?|\s+Zehen?|\s+Scheiben?|\s+Stücke?|\s+Stk?\.?|\s+Bund|\s+Bd\.?|\s+Bn\.?|\s+Pkg\.?|\s+Packung|\s+Msp\.?|\s+Dosen?|\s+Becher|\s+Bch\.?|\s+Be\.?|\s+Beutel|\s+Btl\.?|\s+Stangen?|\s+Stg\.?|\s+Stiele?|\s+Blatt|\s+Blätter|\s+Bl\.?'  # Matches common non-standard units of measurement
        ingredient_pattern = r'[^;]+'  # Matches anything but ; (which is use to separate preparation notes)
        preparation_notes_pattern = r'.+'  # Matches one or more of any character
        # Define a regular expression pattern to match the entire ingredient string
        pattern = r'^({})({})?\s+({})(;({}))?$'.format(amount_pattern, unit_pattern, ingredient_pattern, preparation_notes_pattern)
        
        # Attempt to match the pattern to the ingredient string
        match = re.match(pattern, ingredient, re.IGNORECASE)
        
        if match:
            # Extract the amount, unit, and ingredient from the match object
            amount = match.group(1)
            # unit = None if match.group(2) is None else match.group(2).strip()
            unit = match.group(2)
            ingredient = match.group(3)
            preparation_notes = None if match.group(5) is None else match.group(5).strip()
            # Convert the amount to a float if it exists
            if amount:
                if '_' in amount or 'etwas' in amount:
                    amount = None
                elif '/' in amount:
                    numerator, denominator = amount.split('/')
                    amount = float(numerator) / float(denominator)
                elif amount.lower() == 'eine' or amount.lower() == 'ein':
                    amount = 1.0
                else:
                    amount = float(amount)
            else:
                amount = None

            
            # Return a tuple containing the amount, unit, and ingredient
            return Ingredient(amount, unit, ingredient, preparation_notes)
        else:
            # Return None if the ingredient string does not match the pattern
            raise Exception(f"Could not match ingredient string pattern for: {ingredient}")


class InstructionsWithIngredients:
    def __init__(self, instructions: list[str], ingredients: list[Ingredient]):
        self.instructions = instructions
        self.ingredients = ingredients

    def instructions_to_asciidoc(self) -> str:
        # Replace strings like "180°C" by "🌡180℃" using the special UTF-8 symbol ℃
        adoc_string = "\n\n".join(self.instructions)
        adoc_string = re.sub(r'(\d+)\s?(°C)', r'🌡\1℃', adoc_string)
        return adoc_string



class Recipe:
    def __init__(self, name: str, attributes: dict[str, str], instructions_with_ingredients: list[InstructionsWithIngredients], asciidoc_footer: str):
        self.name = name
        self.yields = attributes['yields']
        self.category = attributes['category']
        self.subcategory = None if 'subcategory' not in attributes else attributes['subcategory'] 
        # ":indexterms: Garnelen, Curry-Mango-Garnelen; Mango-Garnelen"
        self.indexterms = () if 'indexterms' not in attributes else attributes['indexterms'].split(";")
        self.tags = () if 'tags' not in attributes else [t.strip() for t in attributes['tags'].split(";")]
        self.add_autotags_and_sort()
        self.url = None if 'url' not in attributes else attributes['url'] 
        self.source = None if 'source' not in attributes else attributes['source'] 
        self.instructions_with_ingredients = instructions_with_ingredients
        self.asciidoc_footer = asciidoc_footer
        self.info = None if 'info' not in attributes else attributes['info']

    def add_autotags_and_sort(self):
        if ('Mikrowelle' in self.tags or 'Aufwärmen' in self.tags) and self.category != 'Pasta':
            self.tags.append('nur noch aufwärmen')
        if ('Mikrowelle' in self.tags or 'Aufwärmen' in self.tags) and self.category == 'Pasta':
            self.tags.append('nur noch garen')
        self.tags = sorted(self.tags)


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
{caption} {"💥" if "ausprobieren" in self.tags else ""}{"📋" if "TODO" in self.tags else ""}{self.name}

Portionen: {self.yields}{f", Stichwörter: {', '.join(self.tags)}" if self.tags else ""}{f", Quelle: {self.source}" if self.source else ""}{f", URL: {self.url}" if self.url else ""}
"""
        if self.info:
            out_str += f"""
🛈 {self.info}
"""

        out_str += f"""
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
.^| {instr_with_ingr.instructions_to_asciidoc()}
"""
        out_str += f"""|===

{self.asciidoc_footer if self.asciidoc_footer else ''}
"""
        return out_str



class Cookbook:
    def __init__(self, recs : list[Recipe]):
        self.recipes = recs

    def write_json_metadata(self, directory, filename):
        if not os.path.exists(directory):
           os.makedirs(directory)

        recipes_dict = {"recipes": [], "basic_ingredients_regexes" : basic_ingredients_regexes}
        for recipe in self.recipes:
            recipe_dict = {"name": recipe.name, "id": recipe.to_id(), "yields": recipe.yields, "category" : recipe.category, "ingredients": [], "tags": recipe.tags, "url": recipe.url, "source": recipe.source}
            for iwi in recipe.instructions_with_ingredients:
                for ing in iwi.ingredients:
                    recipe_dict["ingredients"].append(ing.__dict__)
            recipes_dict["recipes"].append(recipe_dict)
            
        with open(f"{directory}/{filename}", "w") as f:
            json.dump(recipes_dict, f, indent=4)

    def write_to_adoc(self, directory, filename):
        if not os.path.exists(directory):
           os.makedirs(directory)

        f = open(f"{directory}/{filename}", "w", encoding="utf-8")

        f.write(f""":imagesdir: images
:lang: DE
:hyphens:

:docinfo:

= Rezepte
:pdf-page-size: A4
:toc: left
:toclevels: 4
:toc-title:

""")

#        tags = {tuple(tag) for tag in [r.tags for r in self.recipes]}
        tags = sorted(set([item for sublist in [r.tags for r in self.recipes] for item in sublist]), key=lambda t: t.lower())
        f.write(f"Stichwörter: {'; '.join(list(tags))}\n\n")

        cookbook_categories = ["Appetithäppchen", "Salate", "Suppen", "Pasta", "Pizza & Co.", "Eintöpfe", "Aufläufe", "Ofengerichte", "Reisgerichte", "Fleischgerichte", "Geflügel", "Fisch", "Vegetarisches", "Desserts", "Mehlspeisen", "Gebäck", "Kuchen", "Basis", "Beilagen"]
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

    def write_tagbook_to_adoc(self, directory, filename):
        if not os.path.exists(directory):
           os.makedirs(directory)

        f = open(f"{directory}/{filename}", "w", encoding="utf-8")

        f.write(f""":imagesdir: images
:lang: DE
:hyphens:

:docinfo:

= Rezepte nach Stichwörtern
:pdf-page-size: A4
:toc: left
:toclevels: 4
:toc-title:

""")

        config = [
            ['nur noch aus dem Kühlschrank holen', ['nur noch aus dem Kühlschrank holen'], []],
            ['nur noch aufwärmen', ['nur noch aufwärmen'], []],
            ['nur noch anrichten', ['nur noch anrichten'], []],
            ['nur noch garen', ['nur noch garen'], []],
            ['schnell', ['schnell'], []],
            ['leicht', ['leicht'], []],
            ['schnell+leicht', ['schnell', 'leicht'], []],
            ['!(schnell+leicht)', [], ['schnell', 'leicht']],
            ['vegan', ['vegan'], []],
            ['vegetarisch', ['vegetarisch'], []],
            ['vegetarisch, wenig Käse', ['vegetarisch'], ['Käse']],
            ['Low Meat', ['Low Meat'], []]
        ]

        tags = sorted(set([item for sublist in [r.tags for r in self.recipes] for item in sublist]), key=lambda t: t.lower())
        f.write(f"Stichwörter: {'; '.join(list(tags))}\n\n")

        hauptgerichte = [recipe for recipe in filter(lambda rec: rec.category not in ['Appetithäppchen', 'Suppen', 'Desserts', 'Basis', 'Beilagen'] and rec.subcategory not in ['Dressing'], self.recipes)]

        for c in config:
            gefilterte_rezepte = [recipe for recipe in filter(lambda rec: all(item in rec.tags for item in c[1]) and not set(c[2]).intersection(set(rec. tags)) , hauptgerichte)]

            f.write(f"\n== {c[0]}\n\n")
            for recipe in gefilterte_rezepte:
                # * <<sec.curry_mango_garnelen, Curry-Mango-Garnelen>>
                f.write(f"* https://mwurm.github.io/rezepte/#{recipe.sec_id()}[{recipe.name}] ^{(',{sp}'.join(recipe.tags)).replace(' ', '{sp}')}^\n")

        f.write("""

ifdef::backend-pdf[]
[%always]

<<<
[index]
== Index
endif::[]""")

        f.close()



def parse_recipe(input_str):
    ingredient_factory = IngredientFactory()

    lines = input_str.split("\n")
    name = lines[0]
    attributes = {}
    ingredients = []
    instructions_with_ingredients : list[InstructionsWithIngredients] = []
    asciidoc_footer = None
    read_asciidoc_footer = False
    for line in lines[1:]:
        if not read_asciidoc_footer:
            if line.startswith("#"):
                instructions_with_ingredients.append(InstructionsWithIngredients([line[1:].strip()], ingredients))
                ingredients = []
            elif line.startswith("  ") and len(instructions_with_ingredients) > 0:
                instructions_with_ingredients[-1].instructions.append(line[2:].strip())
                ingredients = []
            elif line.startswith(":"):
                # attributes :yields: 4
                match = re.match(r':(\w+):\s*(.+)', line)
                if match:
                    # If a match was found, extract the key and value
                    key, value = match.groups()
                    attributes[key] = value
            elif line.startswith("---"):
                read_asciidoc_footer = True
                asciidoc_footer = ""
            elif line:
                #parts = line.split(";")
                #quantity, ingredient = parts[0], ";".join(parts[1:])
                #ingredients.append((quantity.strip(), ingredient.strip()))
                ingredients.append(ingredient_factory.get_ingredient(line))
        else:
            asciidoc_footer += f"{line}\n"


    
    return Recipe(name, attributes, instructions_with_ingredients, asciidoc_footer)




if __name__ == '__main__':
    # Parse command line arguments
    # ./rmd_to_asciidoc.py -t src-generated src/rmd/*.rmd
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--target', help='target directory', required=False)
    parser.add_argument('source_files', nargs=argparse.REMAINDER)

    args = parser.parse_args()


    args.source_files = args.source_files if args.source_files else glob.glob('src/rmd/*.rmd')
    recipes = []
    for filename in args.source_files:
        with open(filename, 'r', encoding="utf-8") as f:
            print(f"Reading {f.name}")
            recipe = parse_recipe(f.read())
            recipes.append(recipe)
            if args.target is not None:
                recipe.write_to_adoc(args.target)

    cookbook = Cookbook(recipes)
    
    cookbook.write_to_adoc(".", "index.adoc")
    cookbook.write_tagbook_to_adoc(".", "tagbook.adoc")
    cookbook.write_json_metadata(".", "recipes-metadata.json")

