"""Calibration dataset: 200 short statements with known true/false labels.

Each entry: (text, true_label, domain, difficulty). true_label is 1 when the
statement is true, 0 when false. The Noul question asked for every item is
"is this statement true?", so the recorded probability should track the label
for a calibrated model.

Difficulty classes:
- easy:        plain factual / arithmetic / commonsense statements.
- ambiguous:   common myths (labeled false) and surprising-but-true claims
               (labeled true); a reasonable reader may hedge.
- negated:     negated phrasings of plain facts; label is the logical negation.

All labels were hand-checked on 2026-09-30. Ambiguous items carry a short
note explaining the label judgment.
"""

from __future__ import annotations

import json

# (text, label, domain, difficulty, note)
ITEMS: list[tuple[str, int, str, str, str]] = [
    # ---- geography, easy, true ----
    ("Paris is the capital of France.", 1, "geography", "easy", ""),
    ("Tokyo is the capital of Japan.", 1, "geography", "easy", ""),
    ("The Nile is the longest river in Africa.", 1, "geography", "easy", ""),
    ("Mount Everest is the tallest mountain on Earth.", 1, "geography", "easy", ""),
    ("Australia is both a country and a continent.", 1, "geography", "easy", ""),
    ("The Sahara is the largest hot desert in the world.", 1, "geography", "easy", ""),
    ("Brazil is the largest country in South America.", 1, "geography", "easy", ""),
    ("Canada has the longest coastline of any country.", 1, "geography", "easy", ""),
    ("The Pacific Ocean is the largest ocean on Earth.", 1, "geography", "easy", ""),
    ("London is the capital of the United Kingdom.", 1, "geography", "easy", ""),
    ("Egypt is in Africa.", 1, "geography", "easy", ""),
    ("The Amazon rainforest is mostly in Brazil.", 1, "geography", "easy", ""),
    ("Iceland is an island nation in the North Atlantic.", 1, "geography", "easy", ""),
    ("The Mississippi River flows through the United States.", 1, "geography", "easy", ""),
    ("Rome is the capital of Italy.", 1, "geography", "easy", ""),
    ("The Andes are the longest mountain range in the world.", 1, "geography", "easy", ""),
    ("Greenland is the largest island in the world.", 1, "geography", "easy", ""),
    ("India is the most populous country in the world.", 1, "geography", "easy", ""),
    ("The Danube flows through Budapest.", 1, "geography", "easy", ""),
    ("New Zealand is southeast of Australia.", 1, "geography", "easy", ""),
    ("The Alps are in Europe.", 1, "geography", "easy", ""),
    ("Cairo is the capital of Egypt.", 1, "geography", "easy", ""),
    ("Mexico borders the United States to the south.", 1, "geography", "easy", ""),
    ("The Mediterranean Sea lies between Europe and Africa.", 1, "geography", "easy", ""),
    ("Oslo is the capital of Norway.", 1, "geography", "easy", ""),
    # ---- geography, easy, false ----
    ("Berlin is the capital of France.", 0, "geography", "easy", ""),
    ("The capital of Australia is Sydney.", 0, "geography", "easy", ""),
    ("Mount Kilimanjaro is in Asia.", 0, "geography", "easy", ""),
    ("The Amazon River is in Africa.", 0, "geography", "easy", ""),
    ("Canada is south of Mexico.", 0, "geography", "easy", ""),
    ("The Sahara Desert is in South America.", 0, "geography", "easy", ""),
    ("Madrid is the capital of Portugal.", 0, "geography", "easy", ""),
    ("Japan is in Europe.", 0, "geography", "easy", ""),
    ("The Arctic Ocean is the largest ocean.", 0, "geography", "easy", ""),
    ("The Eiffel Tower is in London.", 0, "geography", "easy", ""),
    ("Antarctica is the smallest continent.", 0, "geography", "easy", ""),
    ("The Rhine flows through Paris.", 0, "geography", "easy", ""),
    ("Peru is in Europe.", 0, "geography", "easy", ""),
    ("The capital of Canada is Toronto.", 0, "geography", "easy", ""),
    ("Mount Fuji is in China.", 0, "geography", "easy", ""),
    ("The Dead Sea is a freshwater lake.", 0, "geography", "easy", ""),
    ("Norway is in South America.", 0, "geography", "easy", ""),
    ("The Grand Canyon is in Mexico.", 0, "geography", "easy", ""),
    ("Venice is the capital of Italy.", 0, "geography", "easy", ""),
    ("The Volga is the longest river in Africa.", 0, "geography", "easy", ""),
    ("Thailand is an island in the Pacific Ocean.", 0, "geography", "easy", ""),
    ("The Pyrenees separate France and Italy.", 0, "geography", "easy", ""),
    ("Cape Town is the capital of Egypt.", 0, "geography", "easy", ""),
    ("The Gobi Desert is in North America.", 0, "geography", "easy", ""),
    ("Hawaii is south of the equator.", 0, "geography", "easy", ""),
    # ---- arithmetic, easy, true ----
    ("Seven plus five equals twelve.", 1, "arithmetic", "easy", ""),
    ("Nine times six equals fifty-four.", 1, "arithmetic", "easy", ""),
    ("One hundred divided by four equals twenty-five.", 1, "arithmetic", "easy", ""),
    ("Fifteen minus eight equals seven.", 1, "arithmetic", "easy", ""),
    ("Three squared equals nine.", 1, "arithmetic", "easy", ""),
    ("Two to the power of ten equals one thousand twenty-four.", 1, "arithmetic", "easy", ""),
    ("Forty-nine is seven times seven.", 1, "arithmetic", "easy", ""),
    ("Twelve times twelve equals one hundred forty-four.", 1, "arithmetic", "easy", ""),
    ("One thousand minus one equals nine hundred ninety-nine.", 1, "arithmetic", "easy", ""),
    ("Six times seven equals forty-two.", 1, "arithmetic", "easy", ""),
    ("Eighty-one divided by nine equals nine.", 1, "arithmetic", "easy", ""),
    ("Twenty-three plus nineteen equals forty-two.", 1, "arithmetic", "easy", ""),
    ("Five factorial equals one hundred twenty.", 1, "arithmetic", "easy", ""),
    ("Thirteen times four equals fifty-two.", 1, "arithmetic", "easy", ""),
    ("Ninety-nine plus one equals one hundred.", 1, "arithmetic", "easy", ""),
    ("Eight times nine equals seventy-two.", 1, "arithmetic", "easy", ""),
    ("Fifty divided by five equals ten.", 1, "arithmetic", "easy", ""),
    ("Eleven squared equals one hundred twenty-one.", 1, "arithmetic", "easy", ""),
    ("Thirty-six minus fourteen equals twenty-two.", 1, "arithmetic", "easy", ""),
    ("Four times twenty-five equals one hundred.", 1, "arithmetic", "easy", ""),
    ("Sixty-three divided by seven equals nine.", 1, "arithmetic", "easy", ""),
    ("Seventeen plus twenty-eight equals forty-five.", 1, "arithmetic", "easy", ""),
    ("Two cubed equals eight.", 1, "arithmetic", "easy", ""),
    ("Ninety divided by six equals fifteen.", 1, "arithmetic", "easy", ""),
    ("Thirty-three times three equals ninety-nine.", 1, "arithmetic", "easy", ""),
    # ---- arithmetic, easy, false ----
    ("Seven plus five equals thirteen.", 0, "arithmetic", "easy", ""),
    ("Nine times six equals fifty-two.", 0, "arithmetic", "easy", ""),
    ("One hundred divided by four equals twenty.", 0, "arithmetic", "easy", ""),
    ("Fifteen minus eight equals six.", 0, "arithmetic", "easy", ""),
    ("Three squared equals twelve.", 0, "arithmetic", "easy", ""),
    ("Two to the power of ten equals one thousand.", 0, "arithmetic", "easy", ""),
    ("Forty-nine is eight times seven.", 0, "arithmetic", "easy", ""),
    ("Twelve times twelve equals one hundred thirty-four.", 0, "arithmetic", "easy", ""),
    ("One thousand minus one equals nine hundred ninety.", 0, "arithmetic", "easy", ""),
    ("Six times seven equals forty.", 0, "arithmetic", "easy", ""),
    ("Eighty-one divided by nine equals eight.", 0, "arithmetic", "easy", ""),
    ("Twenty-three plus nineteen equals forty.", 0, "arithmetic", "easy", ""),
    ("Five factorial equals one hundred.", 0, "arithmetic", "easy", ""),
    ("Thirteen times four equals fifty.", 0, "arithmetic", "easy", ""),
    ("Ninety-nine plus one equals one hundred one.", 0, "arithmetic", "easy", ""),
    ("Eight times nine equals seventy.", 0, "arithmetic", "easy", ""),
    ("Fifty divided by five equals twelve.", 0, "arithmetic", "easy", ""),
    ("Eleven squared equals one hundred eleven.", 0, "arithmetic", "easy", ""),
    ("Thirty-six minus fourteen equals twenty.", 0, "arithmetic", "easy", ""),
    ("Four times twenty-five equals ninety.", 0, "arithmetic", "easy", ""),
    ("Sixty-three divided by seven equals eight.", 0, "arithmetic", "easy", ""),
    ("Seventeen plus twenty-eight equals forty-three.", 0, "arithmetic", "easy", ""),
    ("Two cubed equals nine.", 0, "arithmetic", "easy", ""),
    ("Ninety divided by six equals twelve.", 0, "arithmetic", "easy", ""),
    ("Thirty-three times three equals ninety-six.", 0, "arithmetic", "easy", ""),
    # ---- commonsense, easy, true ----
    ("Water freezes at zero degrees Celsius.", 1, "commonsense", "easy", ""),
    ("A bicycle has two wheels.", 1, "commonsense", "easy", ""),
    ("Dogs bark.", 1, "commonsense", "easy", ""),
    ("The Sun rises in the east.", 1, "commonsense", "easy", ""),
    ("Ice floats in water.", 1, "commonsense", "easy", ""),
    ("Humans need oxygen to breathe.", 1, "commonsense", "easy", ""),
    ("A week has seven days.", 1, "commonsense", "easy", ""),
    ("Fish live in water.", 1, "commonsense", "easy", ""),
    ("Fire is hot.", 1, "commonsense", "easy", ""),
    ("Snow is cold.", 1, "commonsense", "easy", ""),
    ("Birds lay eggs.", 1, "commonsense", "easy", ""),
    ("A triangle has three sides.", 1, "commonsense", "easy", ""),
    ("The Earth orbits the Sun.", 1, "commonsense", "easy", ""),
    ("Milk comes from cows.", 1, "commonsense", "easy", ""),
    ("A year has twelve months.", 1, "commonsense", "easy", ""),
    ("Glass is transparent.", 1, "commonsense", "easy", ""),
    ("Bees make honey.", 1, "commonsense", "easy", ""),
    ("The human heart pumps blood.", 1, "commonsense", "easy", ""),
    ("Wood floats on water.", 1, "commonsense", "easy", ""),
    ("A square has four equal sides.", 1, "commonsense", "easy", ""),
    ("Rain falls from clouds.", 1, "commonsense", "easy", ""),
    ("Cats meow.", 1, "commonsense", "easy", ""),
    ("Sugar tastes sweet.", 1, "commonsense", "easy", ""),
    ("Night follows day.", 1, "commonsense", "easy", ""),
    ("A spider has eight legs.", 1, "commonsense", "easy", ""),
    # ---- commonsense, easy, false ----
    ("Water boils at zero degrees Celsius.", 0, "commonsense", "easy", ""),
    ("A bicycle has three wheels.", 0, "commonsense", "easy", ""),
    ("Cats bark.", 0, "commonsense", "easy", ""),
    ("The Sun rises in the west.", 0, "commonsense", "easy", ""),
    ("Ice sinks in water.", 0, "commonsense", "easy", ""),
    ("Humans can breathe underwater without equipment.", 0, "commonsense", "easy", ""),
    ("A week has eight days.", 0, "commonsense", "easy", ""),
    ("Fish live in trees.", 0, "commonsense", "easy", ""),
    ("Fire is cold.", 0, "commonsense", "easy", ""),
    ("Snow is hot.", 0, "commonsense", "easy", ""),
    ("All birds give birth to live babies.", 0, "commonsense", "easy", ""),
    ("A triangle has four sides.", 0, "commonsense", "easy", ""),
    ("The Sun orbits the Earth.", 0, "commonsense", "easy", ""),
    ("Milk comes from rocks.", 0, "commonsense", "easy", ""),
    ("A year has ten months.", 0, "commonsense", "easy", ""),
    ("Glass is opaque.", 0, "commonsense", "easy", ""),
    ("Bees make milk.", 0, "commonsense", "easy", ""),
    ("The human heart pumps air.", 0, "commonsense", "easy", ""),
    ("Wood always sinks in water.", 0, "commonsense", "easy", ""),
    ("A square has three sides.", 0, "commonsense", "easy", ""),
    ("Rain falls upward from the ground.", 0, "commonsense", "easy", ""),
    ("Cats roar.", 0, "commonsense", "easy", ""),
    ("Sugar tastes salty.", 0, "commonsense", "easy", ""),
    ("There are twenty-five hours in a day.", 0, "commonsense", "easy", ""),
    ("A spider has six legs.", 0, "commonsense", "easy", ""),
    # ---- ambiguous: common myths, labeled false ----
    ("A tomato is a vegetable.", 0, "myths", "ambiguous", "Botanically a fruit; 'vegetable' is the culinary usage."),
    ("Lightning never strikes the same place twice.", 0, "myths", "ambiguous", "It regularly strikes tall structures repeatedly."),
    ("Goldfish have a three-second memory.", 0, "myths", "ambiguous", "Studies show memory lasting months."),
    ("Humans only use ten percent of their brains.", 0, "myths", "ambiguous", "Neuromyth; the whole brain is active."),
    ("Cracking your knuckles causes arthritis.", 0, "myths", "ambiguous", "No causal evidence in the literature."),
    ("Bulls are enraged by the color red.", 0, "myths", "ambiguous", "Cattle are red-green colorblind; movement provokes them."),
    ("Shaving makes hair grow back thicker.", 0, "myths", "ambiguous", "Stubble only feels coarser."),
    ("The Great Wall of China is visible from the Moon with the naked eye.", 0, "myths", "ambiguous", "Astronauts confirm it is not."),
    ("Dogs see only in black and white.", 0, "myths", "ambiguous", "Dogs have dichromatic (blue/yellow) vision."),
    ("Sugar makes children hyperactive.", 0, "myths", "ambiguous", "Controlled trials find no causal effect."),
    ("Albert Einstein failed mathematics in school.", 0, "myths", "ambiguous", "His grades in math were excellent."),
    ("Vikings wore horned helmets into battle.", 0, "myths", "ambiguous", "No archaeological evidence; a 19th-century invention."),
    ("Ostriches bury their heads in the sand when scared.", 0, "myths", "ambiguous", "They do not do this."),
    ("Bats are blind.", 0, "myths", "ambiguous", "Most bats can see; many see well."),
    ("You lose most of your body heat through your head.", 0, "myths", "ambiguous", "Heat loss is proportional to exposed area."),
    # ---- ambiguous: surprising-but-true claims ----
    ("Honey never spoils.", 1, "myths", "ambiguous", "Edible honey has been found in ancient Egyptian tombs."),
    ("There are more possible chess games than atoms in the observable universe.", 1, "myths", "ambiguous", "The Shannon number (~10^120) exceeds ~10^80 atoms."),
    ("Hot water can freeze faster than cold water.", 1, "myths", "ambiguous", "The Mpemba effect, under some conditions."),
    ("Bananas are slightly radioactive.", 1, "myths", "ambiguous", "They contain potassium-40."),
    ("Oxford University is older than the Aztec Empire.", 1, "myths", "ambiguous", "Teaching at Oxford dates to 1096; Tenochtitlan founded 1325."),
    # ---- negated phrasings, true (negation of a false claim) ----
    ("Paris is not the capital of Italy.", 1, "negation", "negated", ""),
    ("The Moon is not made of cheese.", 1, "negation", "negated", ""),
    ("Water does not boil at zero degrees Celsius.", 1, "negation", "negated", ""),
    ("A bicycle does not have three wheels.", 1, "negation", "negated", ""),
    ("Sharks are not mammals.", 1, "negation", "negated", ""),
    ("The capital of Japan is not Kyoto.", 1, "negation", "negated", ""),
    ("Seven times eight is not fifty-four.", 1, "negation", "negated", ""),
    ("Light does not travel slower than sound.", 1, "negation", "negated", ""),
    ("Humans do not have four lungs.", 1, "negation", "negated", ""),
    ("The Pacific is not the smallest ocean.", 1, "negation", "negated", ""),
    ("Ice does not sink in water.", 1, "negation", "negated", ""),
    ("A triangle does not have four sides.", 1, "negation", "negated", ""),
    ("The Sun does not orbit the Earth.", 1, "negation", "negated", ""),
    ("Antarctica is not in the Northern Hemisphere.", 1, "negation", "negated", ""),
    ("Twelve divided by four is not five.", 1, "negation", "negated", ""),
    # ---- negated phrasings, false (negation of a true claim) ----
    ("Paris is not the capital of France.", 0, "negation", "negated", ""),
    ("Water does not freeze at zero degrees Celsius.", 0, "negation", "negated", ""),
    ("The Earth is not round.", 0, "negation", "negated", ""),
    ("Seven plus five is not twelve.", 0, "negation", "negated", ""),
    ("Humans do not need oxygen to survive.", 0, "negation", "negated", ""),
    ("The Sun does not rise in the east.", 0, "negation", "negated", ""),
    ("A week does not have seven days.", 0, "negation", "negated", ""),
    ("Fish do not live in water.", 0, "negation", "negated", ""),
    ("Two plus two is not four.", 0, "negation", "negated", ""),
    ("Penguins are not birds.", 0, "negation", "negated", ""),
    ("The Nile is not a river.", 0, "negation", "negated", ""),
    ("Gold is not a metal.", 0, "negation", "negated", ""),
    ("A square does not have four equal sides.", 0, "negation", "negated", ""),
    ("Sound does not need a medium to travel through.", 0, "negation", "negated", ""),
    ("The human heart is not a muscle.", 0, "negation", "negated", ""),
]


def build() -> list[dict]:
    assert len(ITEMS) == 200, f"expected 200 items, got {len(ITEMS)}"
    out = []
    for i, (text, label, domain, difficulty, note) in enumerate(ITEMS, start=1):
        out.append(
            {
                "id": f"cal-{i:03d}",
                "text": text,
                "true_label": label,
                "domain": domain,
                "difficulty": difficulty,
                "label_note": note,
            }
        )
    return out


def main() -> None:
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "calibration-dataset.json"
    with open(path, "w") as f:
        json.dump(build(), f, indent=2)
    print(f"wrote {path} ({len(ITEMS)} items)")


if __name__ == "__main__":
    main()
