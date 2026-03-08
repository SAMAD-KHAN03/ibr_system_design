import requests
missed=0
def get_drug_class(drug_name):
    # Step 1: Get RxCUI for the drug name
    base_url = "https://rxnav.nlm.nih.gov/REST"
    id_url = f"{base_url}/rxcui.json?name={drug_name}"
    
    id_resp = requests.get(id_url).json()
    try:
        rxcui = id_resp['idGroup']['rxnormId'][0]
    except (KeyError, IndexError):
        return False

    # Step 2: Get Classes for that RxCUI
    # relaSource=ATC provides WHO classifications
    # relaSource=DAILYMED provides FDA Established Pharmacologic Classes (EPC)
    class_url = f"{base_url}/rxclass/class/byRxcui.json?rxcui={rxcui}&relaSource=ATC"
    
    class_resp = requests.get(class_url).json()
    
    classes = []
    try:
        class_concepts = class_resp['rxclassDrugInfoList']['rxclassDrugInfo']
        for item in class_concepts:
            class_name = item['rxclassMinConceptItem']['className']
            classes.append(class_name) 
        return list(set(classes)) # Return unique classes
    except KeyError:
        return False

# Example Usage
drugs = [
    # Cardiovascular (ACE Inhibitors, Beta Blockers, Statins, CCBs, Diuretics)
    # "Lisinopril", "Enalapril", "Ramipril", "Benazepril", "Captopril",
    # "Metoprolol", "Atenolol", "Propranolol", "Carvedilol", "Bisoprolol",
    # "Atorvastatin", "Simvastatin", "Rosuvastatin", "Pravastatin", "Lovastatin",
    # "Amlodipine", "Diltiazem", "Verapamil", "Nifedipine", "Felodipine",
    # "Hydrochlorothiazide", "Furosemide", "Spironolactone", "Chlorthalidone", "Torsemide",
    
    # # Central Nervous System (SSRIs, SNRIs, Benzodiazepines, Anticonvulsants)
    # "Sertraline", "Fluoxetine", "Escitalopram", "Paroxetine", "Citalopram",
    # "Duloxetine", "Venlafaxine", "Desvenlafaxine", "Milnacipran", "Levomilnacipran",
    # "Alprazolam", "Diazepam", "Lorazepam", "Clonazepam", "Temazepam",
    # "Gabapentin", "Pregabalin", "Levetiracetam", "Lamotrigine", "Topiramate",
    # "Quetiapine", "Risperidone", "Aripiprazole", "Olanzapine", "Haloperidol",
    
    # # Antimicrobials (Penicillins, Cephalosporins, Fluoroquinolones, Macrolides)
    # "Amoxicillin", "Cephalexin", "Ceftriaxone", "Penicillin V", "Cefdinir",
    # "Ciprofloxacin", "Levofloxacin", "Moxifloxacin", "Ofloxacin", "Gatifloxacin",
    # "Azithromycin", "Clarithromycin", "Erythromycin", "Telithromycin", "Fidaxomicin",
    # "Doxycycline", "Minocycline", "Nitrofurantoin", "Metronidazole", "Clindamycin",
    
    # Endocrine & Metabolic (Antidiabetics, Thyroid, Bone Health)
    # "Metformin", "Glipizide", "Glyburide", "Sitagliptin", "Empagliflozin",
    # "Levothyroxine", "Liothyronine", "Methimazole", "Propylthiouracil", "Teriparatide",
    # "Alendronate", "Ibandronate", "Risedronate", "Zoledronic Acid", "Raloxifene",
    
    # # Respiratory & Gastrointestinal (PPIs, H2 Blockers, Bronchodilators)
    # "Omeprazole", "Pantoprazole", "Esomeprazole", "Lansoprazole", "Dexlansoprazole",
    # "Famotidine", "Cimetidine", "Nizatidine", "Ondansetron", "Promethazine",
    # "Albuterol", "Salmeterol", "Tiotropium", "Montelukast", "Fluticasone",
    
    # # Analgesics & Anti-inflammatories
    # "Ibuprofen", "Naproxen", "Celecoxib", "Diclofenac", "Meloxicam",
    # "Tramadol", "Oxycodone", "Hydrocodone", "Morphine", "Fentanyl"
    # "SERTRALINE HYDROCHLORIDE"
    "losartan"
]
for drug in drugs:
 answer=print(f"Therapeutic Classes for {drug}: {get_drug_class(drug)}")
 if answer==False:
     missed=missed+1
print(f"number of missed is {missed}")
