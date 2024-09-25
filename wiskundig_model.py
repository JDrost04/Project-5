# ons wiskundige model 
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

Afstandsmatrix = pd.read_excel("Connexxion data - 2024-2025.xlsx", sheet_name = "Afstandsmatrix" )
all_sheets = pd.read_excel("Connexxion data - 2024-2025.xlsx", sheet_name = None)
print("Beschikbare sheets in het bestand:", list(all_sheets.keys()))

# we hebben 2 tabellen dus die kunnen we zo laten zien:
Dienstregeling = all_sheets['Dienstregeling']
Afstandsmatrix = all_sheets['Afstandsmatrix']

# Parameters
max_cap = 300 # maximale capaciteit in kWH
SOH = [85, 95] # State of Health
oplaadtempo_90 = 450 / 60 # kwh per minuut bij opladen tot 90%
oplaadtempo_10 = 60 /60 # kwh per minuut bij opladen van 90% tot 100%
DCap_85 = max_cap * 0.85 # (255 kWh)
DCap_95 = max_cap * 0.95 # (285 kWh)
DCap = [DCap_85, DCap_95]
Overdag_90 = [DCap_85*0.9, DCap_95*0.9]
usage = [0.7, 2.5] # kWh per km

Afstandsmatrix["afstand in meters"] = Afstandsmatrix["afstand in meters"]/1000 # Ik bereken hier de afstand in km
Afstandsmatrix = Afstandsmatrix.rename(columns={'afstand in meters': 'afstand in km'}) # Hier hernoem ik de kolom.
Afstandsmatrix["buslijn"] = Afstandsmatrix["buslijn"].fillna("materiaalrit") # Ik wil laten zien dat alle waarde die NaN zijn materiaalritten zijn.

# Reistijden naar uren omrekenen
Afstandsmatrix["min reistijd in min"] = Afstandsmatrix["min reistijd in min"]/60 #max reistijd per uur.
Afstandsmatrix["max reistijd in min"] = Afstandsmatrix["max reistijd in min"]/60 #min reistijd per uur.
Afstandsmatrix = Afstandsmatrix.rename(columns={'min reistijd in min': 'min reistijd in uur'})
Afstandsmatrix = Afstandsmatrix.rename(columns={'max reistijd in min': 'max reistijd in uur'})

# we willen weten hoeveel km per uur een bus gemiddeld gaat.
Afstandsmatrix["max_speed"] = Afstandsmatrix["afstand in km"]/ Afstandsmatrix['min reistijd in uur'] 
Afstandsmatrix["min_speed"] = Afstandsmatrix["afstand in km"]/ Afstandsmatrix['max reistijd in uur'] 

# we willen weten hoeveel kwh je nodig hebt per rit: Verbruik per km =  0.7-2.5 kWh 
Afstandsmatrix["max_energy"] = Afstandsmatrix["afstand in km"]* 2.5
Afstandsmatrix["min_energy"] = Afstandsmatrix["afstand in km"]* 0.7

from datetime import datetime

Dienstregeling['vertrektijd_dt'] = Dienstregeling['vertrektijd'].apply(lambda x: datetime.strptime(x, '%H:%M')) # vertrijd omzetten naar datetime
def bereken_eindtijd(row):
    """ telt de maximale reistijd op bij de vertrektijd, zodat er een kolom komt met eindtijd
    Parameters: row
    Output: eindtijd in HH:MM
    """
    reistijd = Afstandsmatrix[(Afstandsmatrix['startlocatie'] == row['startlocatie']) & 
                              (Afstandsmatrix['eindlocatie'] == row['eindlocatie'])]['min reistijd in uur'].values
    if len(reistijd) > 0:
        reistijd_in_min = reistijd[0] # Converteer reistijd naar minuten
        eindtijd = row['vertrektijd_dt'] + timedelta(minutes=reistijd_in_min)
        return eindtijd
    else:
        return None 
Dienstregeling['eindtijd'] = Dienstregeling.apply(bereken_eindtijd, axis=1)

def oplaad(battery, DCap, huidige_tijd, vertrektijd, eindtijd):
    """
    Beheren batterijstatus met verschillende regels voor opladen.
    Parameters: 
        - battery: huidige batterijpercentage in kWh
        - Dcap: batterijcapaciteit
        - huidige_tijd: het moment waarop de bus moet opladen
        - vertrektijd: tijd van de eerste busrit
        - eindtijd: tijd van de laatste busrit
    Output: Nieuwe batterij percentage in kWh
    """
    # Minimale batterijpercentage
    min_battery = 0.10 * DCap  # De batterij mag niet onder dit percentage komen
    max_battery_dag = 0.90 * DCap  # Maximaal 90% overdag
    max_battery_nacht = DCap  # Maximaal 100% na dienstregeling
    oplaadtijd_minuten = 15  # Minimaal 15 minuten opladen
    opladen_per_min = oplaadtempo_90  # Oplaadsnelheid tot 90%

    # Oplaadlimiet afhankelijk van het moment van de dag
    if huidige_tijd < vertrektijd or huidige_tijd > eindtijd:
        max_battery = max_battery_nacht
    else:
        max_battery = max_battery_dag

    # Opladen gedurende de idle tijd (minimaal 15 minuten)
    opgeladen_energie = oplaadtijd_minuten * opladen_per_min  # Energie in kWh

    if battery <= min_battery: 
        new_battery = battery + opgeladen_energie
        if new_battery > max_battery:  # Zorgen dat het niet boven max uitkomt
            new_battery = max_battery
    else:
        new_battery = battery

    return new_battery

def battery_usage(distance, huidige_tijd, vertrektijd, eindtijd, bus_type='high'):
    """
    Bereken het energieverbruik per rit op basis van afstand en snelheid.
    Houdt rekening met opladen voor en na de dienstregeling.
    Parameters: 
        - distance: afstand van de rit in km
        - huidige_tijd: huidige tijd van de busrit
        - vertrektijd: tijd van de eerste rit.
        - eindtijd: tijd van de laatste rit
        - bus_type: SOH van de bus (85% of 95%)
    Output: Nieuwe batterijpercentage na de rit en eventuele oplaadbeurt.
    """
    # Selecteer de juiste batterijcapaciteit
    if bus_type == 'high': 
        battery_cap = DCap_85 * 0.9  # 85% SOH
    else: 
        battery_cap = DCap_95 * 0.9  # 95% SOH

    # Verbruik van de bus tijdens de rit (per km)
    batterij_verbruik = distance * np.mean(usage)  # Verbruik in kWh
    remaining_battery = battery_cap - batterij_verbruik

    # Checken of de bus moet opladen na de rit
    remaining_battery = oplaad(remaining_battery, battery_cap, huidige_tijd, vertrektijd, eindtijd)
    
    return remaining_battery
 
""""   
Overdag niet meer dan 90% opladen = 229,5 - 256,5 kWh -> staat in functie opladen 
Altijd tenminste 15 min achtereen worden opgeladen. -> staat ook in opladen
Veiligheidsmarge van ongeveer 10% van de SOH -> bus minimaal SOC (state of charge) waarde van 10% 
Veiligheidsmarge van ongeveer 10% van de SOH -> bus minimaal SOC (state of charge) waarde van 10%. 
Minimale hoeveelheid in accu = 25,5 -28,5 kWh -> staat ook in opladen
Verbruik per km =  0.7-2.5 kWh 
Idling verbruikt het 0.01 kWh (verbruik van bus in stilstand) 
Lijn 401 eerste rit vertrekt om 6:04 vanuit de airport (Apt) naar Eindhoven Centraal (bst). 
401 laatste rit van Apt naar bst is om 00:31. Deze lijn zou klaar moeten zijn tussen de 00:53 en 00:56
Lijn 401 eerste rit vertrekt om 5:07 vanuit Eindhoven Centraal (bst) naar airport (Apt). 
401 laatste rit van bst naar apt is om 00:09. Deze lijn zou klaar moeten zijn tussen de 00:31 en 00:33. 
Lijn 400 eerste rit vertrekt om 7:19 vanuit de airport (Apt) naar Eindhoven Centraal (bst). 
400 laatste rit van Apt naar bst is om 20:46. Deze lijn zou klaar moeten zijn tussen de 21:07 en 21:09 
Lijn 400 eerste rit vertrekt om 06:52 vanuit Eindhoven Centraal (bst) naar airport (Apt). 
401 laatste rit van bst naar apt is om 19:37. Deze lijn zou klaar moeten zijn tussen de 19:58 en 20:00.  
"""