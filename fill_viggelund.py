"""
Fills in Viggelund Steiner's character sheet PDF for the respec:
  Paladin 1 / Storm Sorcerer 6 (Level 7)
"""
import pdfrw

INPUT  = "Viggelund Steiner lv6.pdf"
OUTPUT = "Viggelund Steiner lv7.pdf"

data = {
    # ── Basic info ────────────────────────────────────────────────────────────
    "ClassLevel":   "Paladin lv. 1 / Storm Sorcerer lv. 6",
    "Background":   "Folk Hero",
    "PlayerName":   "Jouke",
    "CharacterName":"Viggelund Steiner",
    "Race ":        "Goliath",
    "Alignment":    "CN",
    "XP":           "",
    "Inspiration":  "1",

    # ── Ability scores ────────────────────────────────────────────────────────
    # STR 14 required: Paladin multiclass needs STR 13+ AND CHA 13+
    # Standard array (15,14,13,12,10,8) + Goliath (+2 STR, +1 CON):
    #   CHA 15→17(ASI), WIS 14, CON 13+1=14, STR 12+2=14, DEX 10, INT 8
    "STR":      "14",
    "STRmod":   "+2",
    "DEX":      "10",
    "DEXmod ":  "+0",   # note trailing space
    "CON":      "14",
    "CONmod":   "+2",
    "INT":      "8",
    "INTmod":   "-1",
    "WIS":      "14",
    "WISmod":   "+2",
    "CHA":      "17",
    "CHamod":   "+3",   # note lowercase 'a'

    # ── Combat ────────────────────────────────────────────────────────────────
    "ProfBonus":  "+3",
    "AC":         "17",   # Splint armor (same as before; add shield for 19 if desired)
    "Initiative": "+0",
    "Speed":      "30ft",

    # ── HP & Hit Dice ─────────────────────────────────────────────────────────
    # Pal1(d10): 12 + Sorc2-6(d6): 5×6=30 → 42
    "HPMax":     "42",
    "HPCurrent": "42",
    "HPTemp":    "",
    "HD":        "1d10 + 6d6",
    "HDTotal":   "1d10 + 6d6",

    # ── Saving throws ─────────────────────────────────────────────────────────
    "ST Strength":    "+2",
    "ST Dexterity":   "+0",
    "ST Constitution":"+2",
    "ST Intelligence":"-1",
    "ST Wisdom":      "+5",   # proficient (Paladin): +2 mod + 3 prof
    "ST Charisma":    "+6",   # proficient (Paladin): +3 mod + 3 prof

    # Saving throw proficiency checkboxes
    "Check Box 11": "/Off",   # STR save – was /Yes as Fighter, clear
    "Check Box 18": "/Off",   # DEX save – stays off
    "Check Box 19": "/Off",   # CON save – was /Yes as Fighter, clear
    "Check Box 20": "/Off",   # INT save – stays off
    "Check Box 21": "/Yes",   # WIS save – new (Paladin)
    "Check Box 22": "/Yes",   # CHA save – new (Paladin)

    # ── Skills ────────────────────────────────────────────────────────────────
    "Acrobatics":       "+0",
    "Animal":           "+5",   # Animal Handling – Folk Hero ✓: WIS +2 + prof +3
    "Arcana":           "+2",   # Sorcerer multiclass ✓: INT -1 + prof +3
    "Athletics":        "+2",   # STR +2, not proficient
    "Deception ":       "+3",   # trailing space
    "History ":         "-1",   # trailing space
    "Insight":          "+2",
    "Intimidation":     "+6",   # Paladin ✓: CHA +3 + prof +3
    "Investigation ":   "-1",   # trailing space
    "Medicine":         "+2",
    "Nature":           "-1",
    "Perception ":      "+2",   # trailing space
    "Performance":      "+3",
    "Persuasion":       "+6",   # Paladin ✓: CHA +3 + prof +3
    "Religion":         "-1",
    "SleightofHand":    "+0",
    "Stealth ":         "+0",   # trailing space (disadvantage in heavy armor)
    "Survival":         "+5",   # Folk Hero ✓: WIS +2 + prof +3
    "Passive":          "12",

    # Skill proficiency checkboxes
    "Check Box 23": "/Off",   # Acrobatics – clear
    "Check Box 24": "/Yes",   # Animal Handling – keep
    "Check Box 25": "/Yes",   # Arcana – new
    "Check Box 26": "/Off",   # Athletics – clear
    "Check Box 27": "/Off",   # Deception
    "Check Box 28": "/Off",   # History
    "Check Box 29": "/Off",   # Insight
    "Check Box 30": "/Yes",   # Intimidation – keep
    "Check Box 31": "/Off",   # Investigation
    "Check Box 32": "/Off",   # Medicine
    "Check Box 33": "/Off",   # Nature
    "Check Box 34": "/Off",   # Perception
    "Check Box 35": "/Off",   # Performance
    "Check Box 36": "/Yes",   # Persuasion – new
    "Check Box 37": "/Off",   # Religion
    "Check Box 38": "/Off",   # Sleight of Hand
    "Check Box 39": "/Off",   # Stealth
    "Check Box 40": "/Yes",   # Survival – keep

    # ── Weapons & attacks ─────────────────────────────────────────────────────
    "Wpn Name":       "Warhammer",
    "Wpn1 AtkBonus":  "+5",   # STR +2 + prof +3
    "Wpn1 Damage":    "1d8/1d10 blu.",
    "Wpn Name 2":     "Dagger",
    "Wpn2 AtkBonus ": "+5",   # STR +2 + prof +3
    "Wpn2 Damage ":   "1d4 piercing",
    "Wpn Name 3":     "Spell Attack",
    "Wpn3 AtkBonus  ":"  +6",
    "Wpn3 Damage ":   "by spell / DC 14",

    "AttacksSpellcasting": (
        "Divine Smite: On melee hit, expend a spell slot for +2d8 radiant damage "
        "(+1d8 per slot level above 1st, max 5d8; +1d8 vs undead/fiends).\r\n\r\n"
        "Tempestuous Magic: After casting a 1st+ level spell, use a bonus action to "
        "fly up to 10 ft without provoking opportunity attacks.\r\n\r\n"
        "Lay on Hands: 5 HP pool/long rest. As an action, restore HP or expend 5 HP "
        "to cure one disease or neutralise one poison."
    ),

    # ── Features and Traits (page 1) ─────────────────────────────────────────
    "Features and Traits": (
        "Stone's Endurance. Reaction: roll d12 + CON mod, reduce damage by that total. "
        "(1× prof/long rest)\r\n\r\n"
        "Powerful Build. Count as one size larger for carrying/pushing/dragging.\r\n\r\n"
        "Mountain Born. Resistance to cold damage; acclimatised to high altitude.\r\n\r\n"
        "Divine Sense. Detect celestials, fiends & undead within 60 ft (not total cover). "
        "4 uses/long rest.\r\n\r\n"
        "Missing a kidney: 1/2 alcohol resistance."
    ),

    # ── Proficiencies ─────────────────────────────────────────────────────────
    "ProficienciesLang": (
        "Languages: Common, Dwarven\n"
        "Armor: All armor, shields\n"
        "Weapons: Simple weapons, martial weapons\n"
        "Vehicles: Land\n"
        "Tools: Carpenter's tools\n"
    ),

    # ── Equipment (unchanged) ─────────────────────────────────────────────────
    "Equipment": (
        "Splint armor, warhammer, dagger, shovel, pot, common clothes, pouch, "
        "small chest, 2 cases for maps/scrolls, fine clothes, bottle of ink, pen, "
        "lamp, 2 flasks of oil, 5 sheets of paper, vial of perfume, sealing wax, soap, "
        r"4 bottles of shitty bourbon, potion of hill giant's strength, dryad arm ×2, "
        r"health potion ×2 \(2d4+2 hp\), dwarven beard oil"
    ),

    # ── Money (unchanged) ─────────────────────────────────────────────────────
    "CP": "",
    "SP": "",
    "EP": "5",
    "GP": "161",
    "PP": "",

    # ── Page 2 – Character details ────────────────────────────────────────────
    "CharacterName 2": "Viggelund Steiner",
    "Age":    "44",
    "Height": "8ft.",
    "Weight": "310lbs",
    "Eyes":   "Steel blue",
    "Skin":   "Tanned",
    "Hair":   "Bald with blonde moustache",

    "PersonalityTraits ": (
        "I'm confident in my own abilities and do what I can to instill confidence in others."
    ),
    "Ideals": "Respect. People deserve to be treated with dignity and respect.",
    "Bonds":  "I protect those who cannot protect themselves.\r\nAlso, someone took my goddamn kidney.",
    "Flaws":  "I have a weakness for the vices of the city, especially hard drink.",

    "Backstory": (
        "Vigge was an entertainer, a strongman making a living as part of a travelling circus. "
        "One particularly rainy day, he was helping to put up the circus tent when he was struck "
        "by lightning. When he woke up, he found that the storm had awakened something ancient and "
        "wild within him - a sorcerous connection to wind and thunder. He also felt a divine calling "
        "stir in his heart, as if the heavens themselves had chosen him.\r\n\r\n"
        "----------==MORE POWERS==-------------\r\n"
        "Heart of the Storm: Resistance to lightning and thunder damage. When casting a 1st+ level "
        "lightning or thunder spell, creatures within 10 ft take 3 lightning or thunder damage.\r\n"
        "Storm Guide: Use your action to stop precipitation in a 20 ft radius around you, or choose "
        "the direction of wind within 100 ft of you."
    ),

    "Feat+Traits": (
        "SORCERER (Storm) FEATURES:\r\n\r\n"
        "Font of Magic: 6 Sorcery Points/long rest. Convert spell slots to points or points to slots:\r\n"
        "  1st=2 pts  |  2nd=3 pts  |  3rd=5 pts\r\n\r\n"
        "Metamagic (2 options):\r\n"
        "  Quickened Spell (2 pts): Cast a 1-action spell as a bonus action.\r\n"
        "  Heightened Spell (3 pts): One target has disadvantage on its first saving throw.\r\n\r\n"
        "Tides of Chaos: Gain advantage on one attack roll, ability check, or saving throw. "
        "Recharges on long rest.\r\n\r\n"
        "Heart of the Storm: Resistance to lightning & thunder. Casting 1st+ level lightning/"
        "thunder spell deals 3 lightning/thunder to creatures of choice within 10 ft.\r\n\r\n"
        "Storm Guide: Action — stop precipitation within 20 ft, or redirect wind within 100 ft."
    ),

    "Allies": (
        "----==THE POWER OF FRIENDSHIP==----\r\n"
        "Rustic Hospitality. You fit in among common folk. You can find a place to hide, rest, or "
        "recuperate among commoners. They will shield you from the law or anyone searching for you "
        "(though they will not risk their lives for you)."
    ),

    "FactionName": "",
    "Treasure": "5 basilisk spikes, basilisk eye, wererat tooth, dwarven beard oil.\r\n\r\nI5v",

    # ── Spellcasting page ─────────────────────────────────────────────────────
    "Spellcasting Class 2":  "Paladin 1 / Storm Sorcerer 6",
    "SpellcastingAbility 2": "Charisma",
    "SpellSaveDC  2":        "14",          # two spaces before '2'
    "SpellAtkBonus 2":       "+6",

    # Spell slot totals / remaining  (slots 19=1st, 20=2nd, 21=3rd …)
    "SlotsTotal 19":     "4",
    "SlotsRemaining 19": "",
    "SlotsTotal 20":     "3",
    "SlotsRemaining 20": "",
    "SlotsTotal 21":     "3",
    "SlotsRemaining 21": "",
    "SlotsTotal 22":     "",  "SlotsRemaining 22": "",
    "SlotsTotal 23":     "",  "SlotsRemaining 23": "",
    "SlotsTotal 24":     "",  "SlotsRemaining 24": "",
    "SlotsTotal 25":     "",  "SlotsRemaining 25": "",
    "SlotsTotal 26":     "",  "SlotsRemaining 26": "",
    "SlotsTotal 27":     "",  "SlotsRemaining 27": "",

    # ── Cantrips ──────────────────────────────────────────────────────────────
    "Spells 1014": "Fire Bolt",
    "Spells 1015": "Shocking Grasp",
    "Spells 1016": "Thunderclap",
    "Spells 1017": "Mage Hand",
    "Spells 1018": "", "Spells 1019": "", "Spells 1020": "",
    "Spells 1021": "", "Spells 1022": "", "Spells 1023": "",

    # ── 1st-level spells ──────────────────────────────────────────────────────
    # Sorcerer known: Thunderwave, Chromatic Orb
    # Paladin prepared (*): Bless, Divine Favor, Shield of Faith, Prot. Evil/Good
    "Spells 1024": "Thunderwave",
    "Spells 1025": "Chromatic Orb",
    "Spells 1026": "Bless *",
    "Spells 1027": "Divine Favor *",
    "Spells 1028": "Shield of Faith *",
    "Spells 1029": "Prot. from Evil/Good *",
    "Spells 1030": "", "Spells 1031": "", "Spells 1032": "", "Spells 1033": "",

    # ── 2nd-level spells ──────────────────────────────────────────────────────
    "Spells 1034": "Misty Step",
    "Spells 1035": "Shatter",
    "Spells 1036": "", "Spells 1037": "", "Spells 1038": "", "Spells 1039": "",
    "Spells 1040": "", "Spells 1041": "", "Spells 1042": "", "Spells 1043": "",
    "Spells 1044": "", "Spells 1045": "", "Spells 1046": "",

    # ── 3rd-level spells ──────────────────────────────────────────────────────
    "Spells 1047": "Call Lightning",
    "Spells 1048": "Lightning Bolt",
    "Spells 1049": "Fly",
    "Spells 1050": "", "Spells 1051": "", "Spells 1052": "", "Spells 1053": "",
    "Spells 1054": "", "Spells 1055": "", "Spells 1056": "", "Spells 1057": "",
    "Spells 1058": "", "Spells 1059": "",

    # ── Clear higher-level slots ──────────────────────────────────────────────
    "Spells 1060": "", "Spells 1061": "", "Spells 1062": "", "Spells 1063": "",
    "Spells 1064": "", "Spells 1065": "", "Spells 1066": "", "Spells 1067": "",
    "Spells 1068": "", "Spells 1069": "", "Spells 1070": "", "Spells 1071": "",
    "Spells 1072": "", "Spells 1073": "", "Spells 1074": "", "Spells 1075": "",
    "Spells 1076": "", "Spells 1077": "", "Spells 1078": "", "Spells 1079": "",
    "Spells 1080": "", "Spells 1081": "", "Spells 1082": "", "Spells 1083": "",
    "Spells 1084": "", "Spells 1085": "", "Spells 1086": "", "Spells 1087": "",
    "Spells 1088": "", "Spells 1089": "", "Spells 1090": "", "Spells 1091": "",
    "Spells 1092": "", "Spells 1093": "", "Spells 1094": "", "Spells 1095": "",
    "Spells 1096": "", "Spells 1097": "", "Spells 1098": "", "Spells 1099": "",
    "Spells 10100": "", "Spells 10101": "", "Spells 10102": "", "Spells 10103": "",
    "Spells 10104": "", "Spells 10105": "", "Spells 10106": "", "Spells 10107": "",
    "Spells 10108": "", "Spells 10109": "", "Spells 101010": "", "Spells 101011": "",
    "Spells 101012": "", "Spells 101013": "",
}


def fill_pdf(input_path: str, output_path: str, fields: dict) -> None:
    template = pdfrw.PdfReader(input_path)

    # Tell PDF viewers to regenerate field appearances
    if template.Root.AcroForm:
        template.Root.AcroForm.update(
            pdfrw.PdfDict(NeedAppearances=pdfrw.PdfObject("true"))
        )

    for page in template.pages:
        if not page.Annots:
            continue
        for annot in page.Annots:
            if annot.Subtype != "/Widget" or not annot.T:
                continue
            key = annot.T[1:-1]   # strip surrounding parentheses
            if key not in fields:
                continue

            val = fields[key]
            ft  = annot.FT        # field type: /Tx, /Btn, /Ch …

            if ft == "/Btn":
                # Checkbox / radio button
                if val in ("", "/Off", "Off"):
                    pval = pdfrw.PdfName("Off")
                else:
                    pval = pdfrw.PdfName("Yes")
                annot.update(pdfrw.PdfDict(V=pval, AS=pval))
            else:
                # Text (and anything else)
                annot.update(pdfrw.PdfDict(V=val, AP=""))

    pdfrw.PdfWriter().write(output_path, template)
    print(f"Written → {output_path}")


if __name__ == "__main__":
    fill_pdf(INPUT, OUTPUT, data)
