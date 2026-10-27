import csv
import os

csv_filename = "collection.csv"
if not os.path.exists(csv_filename):
    print(f"[-] Error: {csv_filename} not found in root directory.")
else:
    with open(csv_filename, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        print("[+] CSV Headers:", headers)
        print("\n[+] First 3 Rows:")
        for i in range(3):
            try:
                print(next(reader))
            except StopIteration:
                break
