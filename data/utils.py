import json

# Path to the file
CROSSBEAM_FILE = "./crossbeam_records_50.json"

def set_all_logo_potential_false():
    with open(CROSSBEAM_FILE, "r") as f:
        records = json.load(f)
    # If the file is a list of records
    if isinstance(records, list):
        for rec in records:
            if (
                isinstance(rec, dict)
                and 'prospect_factors' in rec
                and isinstance(rec['prospect_factors'], dict)
                and 'logo_potential' in rec['prospect_factors']
            ):
                rec['prospect_factors']['logo_potential'] = False
    # If the file is a dict of records
    elif isinstance(records, dict):
        for rec in records.values():
            if (
                isinstance(rec, dict)
                and 'prospect_factors' in rec
                and isinstance(rec['prospect_factors'], dict)
                and 'logo_potential' in rec['prospect_factors']
            ):
                rec['prospect_factors']['logo_potential'] = False
    with open(CROSSBEAM_FILE, "w") as f:
        json.dump(records, f, indent=2)

if __name__ == "__main__":
    set_all_logo_potential_false()
    print("All logo_potential fields set to False.")
