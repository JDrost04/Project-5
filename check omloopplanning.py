import pandas as pd
from datetime import datetime, timedelta

# je gooit dus het omloopschema erin en dan kijk je op het toelaatbaar is
# klopt nog niet heel veel van, sorry :(

# er moet rekening mee gehouden worden dat de omlopen veranderd kunnen worden, dat is nu nog niet het geval
# er moet rekening mee gehouden worden dat in idle er niet opgeladen wordt, maar pas wanneer er van omloop gewisseld wordt

df = pd.read_excel('omloopplanning.xlsx')

max_cap = 300 # maximale capaciteit in kWH
SOH = [85, 95] # State of Health
oplaadtempo_90 = 450 / 60 # kwh per minuut bij opladen tot 90%
oplaadtempo_10 = 60 /60 # kwh per minuut bij oladen tot 10%
DCap_85 = max_cap * 0.85 # (255 kWh)
DCap_95 = max_cap * 0.95 # (285 kWh)
DCap = [DCap_85, DCap_95]
Overdag_90 = [DCap_85*0.9, DCap_95*0.9]
usage = [0.7, 2.5] # kWh per km

# Functie om batterijstatus te berekenen
def simuleer_batterij(df, DCap, vertrektijd, eindtijd):
    battery = DCap * 0.9  # Begin met 90% batterij
    min_battery = DCap * 0.1
    max_battery_dag = DCap * 0.9
    max_battery_nacht = DCap
    oplaadtempo_90 = 1  # kWh per minuut (voorbeeldwaarde)
    opladen_minuten = 15  # Minimaal 15 minuten oplaadtijd
    
    for i, row in df.iterrows():
        # Converteer start en eindtijden naar datetime
        starttijd = datetime.strptime(row['starttijd'], '%H:%M:%S')
        eindtijd = datetime.strptime(row['eindtijd'], '%H:%M:%S')
        
        # Bereken batterijverbruik per rit
        if row['activiteit'] == 'dienst rit' or row['activiteit'] == 'materiaal rit':
            verbruik = row['energieverbruik']
            battery -= verbruik
        
        # Controleer of de batterij opgeladen moet worden tijdens idle periodes
        if row['activiteit'] == 'idle':
            idle_starttijd = datetime.strptime(row['starttijd'], '%H:%M:%S')
            idle_eindtijd = datetime.strptime(row['eindtijd'], '%H:%M:%S')
            
            # Bereken idle tijd in minuten
            idle_tijd = (idle_eindtijd - idle_starttijd).total_seconds() / 60
            
            # Als de idle tijd >= 15 minuten, laad dan op
            if idle_tijd >= opladen_minuten:
                if idle_starttijd < vertrektijd or idle_eindtijd > eindtijd:
                    max_battery = max_battery_nacht
                else:
                    max_battery = max_battery_dag
                
                opgeladen_energie = min(idle_tijd * oplaadtempo_90, max_battery - battery)
                battery += opgeladen_energie
        
        # Check batterijstatus na elke stap
        if battery < min_battery:
            print(f"Waarschuwing: batterij te laag op {row['starttijd datum']}")
        if battery > max_battery_dag and row['activiteit'] != 'idle':
            print(f"Waarschuwing: batterij boven 90% tijdens dienst op {row['starttijd datum']}")
        
    return battery

# Voorbeeld data
DCap = 285  # Capaciteit van de bus
vertrektijd = datetime.strptime('06:00', '%H:%M')
eindtijd = datetime.strptime('00:00', '%H:%M')

# Voer de simulatie uit
final_battery = simuleer_batterij(df, DCap, vertrektijd, eindtijd)
print(f"Finale batterijstatus: {final_battery:.2f} kWh")
