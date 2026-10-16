import os
import csv

def inspect_local_catalog():
    data_dir = "data"
    print("==========================================")
    print(" INSPECTING LOCAL DATA CATALOG FILES")
    print("==========================================")
    
    if not os.path.exists(data_dir):
        print("[-] Error: 'data' directory not found.")
        return

    csv_files = ["cards.csv", "card_prints.csv", "card_tags.csv", "card_legalities.csv"]
    for filename in csv_files:
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            size_mb = round(os.path.getsize(path) / (1024 * 1024), 2)
            print(f"\n[+] File: {filename} ({size_mb} MB)")
            try:
                with open(path, mode="r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                    print(f"    Headers: {headers[:6]} ... (total {len(headers)} columns)")
                    
                    row_count = sum(1 for row in reader)
                    print(f"    Total Rows: {row_count}")
            except Exception as e:
                print(f"    [-] Error reading {filename}: {e}")
        else:
            print(f"\n[-] Missing File: {filename}")
    print("==========================================")

if __name__ == "__main__":
    inspect_local_catalog()
