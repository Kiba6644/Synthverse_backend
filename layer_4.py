import requests
import pandas as pd
import json
import time
import os
import networkx as nx

# UN M49 Country Codes (Expanded)
COUNTRIES = {
    356: 'India',
    156: 'China',
    842: 'USA',
    784: 'UAE',
    682: 'Saudi Arabia',
    643: 'Russia',
    368: 'Iraq',
    36: 'Australia',
    360: 'Indonesia',
    702: 'Singapore',
    276: 'Germany',
    392: 'Japan',
    410: 'South Korea',
    250: 'France',
    826: 'UK',
    634: 'Qatar',
    414: 'Kuwait',
    710: 'South Africa',
    76:  'Brazil'
}

# HS 2-Digit Commodity Codes (Expanded)
COMMODITIES = {
    '27': 'Mineral fuels and oils (Crude Oil, Coal, LNG)',
    '85': 'Electrical machinery and electronics',
    '84': 'Nuclear reactors, boilers, machinery',
    '71': 'Natural or cultured pearls, precious stones',
    '31': 'Fertilizers',
    '15': 'Animal or vegetable fats and oils',
    '30': 'Pharmaceutical products and medicines',
    '39': 'Plastics and articles thereof',
    '72': 'Iron and steel',
    '29': 'Organic chemicals',
    '90': 'Optical, photographic, medical instruments',
    '10': 'Cereals (Wheat, Rice)'
}

# Chokepoint mappings for trade routes to India
ROUTE_MAPPING = {
    # Middle East
    ('Saudi Arabia', 'India'): {'chokepoints': ['Strait of Hormuz'], 'distance_nm': 1500, 'alt_chokepoints': ['None (Overland/Pipeline not viable)'], 'alt_distance_nm': float('inf')},
    ('Iraq', 'India'): {'chokepoints': ['Strait of Hormuz'], 'distance_nm': 1700, 'alt_distance_nm': float('inf')},
    ('UAE', 'India'): {'chokepoints': ['Strait of Hormuz'], 'distance_nm': 1200, 'alt_distance_nm': float('inf')},
    ('Qatar', 'India'): {'chokepoints': ['Strait of Hormuz'], 'distance_nm': 1300, 'alt_distance_nm': float('inf')},
    ('Kuwait', 'India'): {'chokepoints': ['Strait of Hormuz'], 'distance_nm': 1800, 'alt_distance_nm': float('inf')},
    
    # Europe / Americas
    ('Russia', 'India'): {'chokepoints': ['Suez Canal', 'Bab-el-Mandeb'], 'distance_nm': 4500, 'alt_chokepoints': ['Cape of Good Hope'], 'alt_distance_nm': 11000},
    ('USA', 'India'): {'chokepoints': ['Suez Canal', 'Bab-el-Mandeb'], 'distance_nm': 8500, 'alt_chokepoints': ['Cape of Good Hope'], 'alt_distance_nm': 11500},
    ('Germany', 'India'): {'chokepoints': ['Suez Canal', 'Bab-el-Mandeb'], 'distance_nm': 5000, 'alt_chokepoints': ['Cape of Good Hope'], 'alt_distance_nm': 10500},
    ('France', 'India'): {'chokepoints': ['Suez Canal', 'Bab-el-Mandeb'], 'distance_nm': 4800, 'alt_chokepoints': ['Cape of Good Hope'], 'alt_distance_nm': 10300},
    ('UK', 'India'): {'chokepoints': ['Suez Canal', 'Bab-el-Mandeb'], 'distance_nm': 5500, 'alt_chokepoints': ['Cape of Good Hope'], 'alt_distance_nm': 10800},
    ('Brazil', 'India'): {'chokepoints': ['Cape of Good Hope'], 'distance_nm': 7500, 'alt_chokepoints': ['Direct Sea'], 'alt_distance_nm': 7500},
    ('South Africa', 'India'): {'chokepoints': ['Direct Sea'], 'distance_nm': 4000, 'alt_chokepoints': ['Direct Sea'], 'alt_distance_nm': 4000},

    # Asia Pacific
    ('China', 'India'): {'chokepoints': ['Strait of Malacca'], 'distance_nm': 3500, 'alt_chokepoints': ['Sunda Strait'], 'alt_distance_nm': 4200},
    ('Japan', 'India'): {'chokepoints': ['Strait of Malacca'], 'distance_nm': 4500, 'alt_chokepoints': ['Sunda Strait'], 'alt_distance_nm': 5200},
    ('South Korea', 'India'): {'chokepoints': ['Strait of Malacca'], 'distance_nm': 4300, 'alt_chokepoints': ['Sunda Strait'], 'alt_distance_nm': 5000},
    ('Australia', 'India'): {'chokepoints': ['Sunda Strait'], 'distance_nm': 4500, 'alt_chokepoints': ['Lombok Strait'], 'alt_distance_nm': 4800},
    ('Indonesia', 'India'): {'chokepoints': ['Strait of Malacca'], 'distance_nm': 1500, 'alt_chokepoints': ['Direct Sea'], 'alt_distance_nm': 1600},
    ('Singapore', 'India'): {'chokepoints': ['Strait of Malacca'], 'distance_nm': 1800, 'alt_chokepoints': ['Direct Sea'], 'alt_distance_nm': 1800}
}

def generate_synthetic_fallback():
    """
    Massively expanded historical approximation (using 2023 equivalent ratios).
    Ensures broad topological coverage across 3 major oceans and 5 primary chokepoints.
    """
    print("Generating expanded historical synthetic data...")
    data = []
    
    # Extensive import pairs: (Origin, Commodity, USD Value)
    base_imports = [
        # Asian Electronics & Machinery
        ('China', '85', 30_000_000_000), 
        ('China', '84', 25_000_000_000),
        ('China', '39', 8_000_000_000), # Plastics
        ('Japan', '84', 5_000_000_000),
        ('Japan', '72', 4_000_000_000), # Steel
        ('South Korea', '85', 6_000_000_000),
        ('South Korea', '72', 3_500_000_000),
        ('Singapore', '85', 4_000_000_000),
        
        # Middle East Energy & Chemicals
        ('Saudi Arabia', '27', 28_000_000_000),
        ('Saudi Arabia', '29', 5_000_000_000), # Organics
        ('Iraq', '27', 26_000_000_000),
        ('UAE', '27', 15_000_000_000),
        ('UAE', '71', 8_000_000_000), # Pearls/Stones
        ('Qatar', '27', 12_000_000_000), # LNG
        ('Kuwait', '27', 8_000_000_000),
        
        # European Pharmaceuticals, Tech & Vehicles (Machinery)
        ('Germany', '84', 6_000_000_000),
        ('Germany', '30', 3_000_000_000), # Pharma/Medicines
        ('Germany', '90', 2_500_000_000), # Medical Instruments
        ('France', '30', 1_500_000_000), # Pharma
        ('France', '84', 2_000_000_000), 
        ('UK', '71', 4_000_000_000), 
        ('UK', '30', 1_000_000_000),
        
        # Americas & Russia
        ('USA', '27', 10_000_000_000),
        ('USA', '84', 8_000_000_000),
        ('USA', '90', 4_000_000_000), # Medical Instruments
        ('Russia', '27', 45_000_000_000),
        ('Russia', '31', 3_000_000_000), # Fertilizers
        ('Brazil', '15', 2_000_000_000), # Oils
        
        # Oceanic Minerals & Agriculture
        ('Australia', '27', 12_000_000_000), # Coal
        ('Australia', '10', 1_500_000_000), # Cereals
        ('Indonesia', '27', 10_000_000_000), # Coal
        ('Indonesia', '15', 5_000_000_000), # Palm oil
        ('South Africa', '27', 3_000_000_000),
    ]
    
    for origin, cmd_code, value in base_imports:
        cmd_name = COMMODITIES.get(cmd_code, 'Unknown')
        route_info = ROUTE_MAPPING.get((origin, 'India'), {})
        data.append({
            'year': 2023,
            'origin': origin,
            'destination': 'India',
            'commodity_code': cmd_code,
            'commodity_name': cmd_name,
            'value_usd': value,
            'net_weight_kg': value * 0.5, 
            'chokepoints': route_info.get('chokepoints', []),
            'primary_distance_nm': route_info.get('distance_nm', 0),
            'alt_chokepoints': route_info.get('alt_chokepoints', []),
            'alt_distance_nm': route_info.get('alt_distance_nm', 0)
        })
        
    return pd.DataFrame(data)

def run_layer_4_setup():
    data_path = 'india_imports_dataset.csv'
    
    df = generate_synthetic_fallback()
    df.to_csv(data_path, index=False)
    print(f"Expanded dataset saved to {data_path} with {len(df)} records.")
    
if __name__ == "__main__":
    run_layer_4_setup()
