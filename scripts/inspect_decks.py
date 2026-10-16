import csv
import os

DATA_DIR = "data"

def inspect_decks():
    decks_path = os.path.join(DATA_DIR, "decks.csv")
    deck_cards_path = os.path.join(DATA_DIR, "deck_cards.csv")

    print("==========================================")
    print(" INSPECTING DECKS & DECK_CARDS CSVs")
    print("==========================================")
    
    if os.path.exists(decks_path):
        print("\n[+] decks.csv preview:")
        with open(decks_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                print(f"    {row}")
                if i >= 4:
                    break
    else:
        print("\n[-] Missing decks.csv")

    if os.path.exists(deck_cards_path):
        print("\n[+] deck_cards.csv preview:")
        with open(deck_cards_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                print(f"    {row}")
                if i >= 4:
                    break
    else:
        print("\n[-] Missing deck_cards.csv")
    print("==========================================")

if __name__ == "__main__":
    inspect_decks()
