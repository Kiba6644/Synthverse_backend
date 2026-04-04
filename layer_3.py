import requests
import geopy.distance
from flask import Blueprint, request, jsonify

layer_3_bp = Blueprint('layer_3', __name__)

def fetch_amenities(lat, lon, radius=10000, max_results=50, amenity_type="hospital"):
    base_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      node["amenity"="{amenity_type}"](around:{radius},{lat},{lon});
      way["amenity"="{amenity_type}"](around:{radius},{lat},{lon});
      relation["amenity"="{amenity_type}"](around:{radius},{lat},{lon});
    );
    out center;
    """
    
    try:
        response = requests.get(base_url, params={"data": query})
        if response.status_code != 200:
            return {"error": f"Overpass API error: {response.status_code}"}
            
        data = response.json()
        facilities = []
        
        for element in data.get("elements", []):
            name = element.get("tags", {}).get("name", "Unnamed")
            sector_id = element.get("tags", {}).get("addr:suburb", "Unknown")
            
            # For ways and relations, overpass provides a center point
            elem_lat = element.get("lat") or (element.get("center", {}).get("lat"))
            elem_lon = element.get("lon") or (element.get("center", {}).get("lon"))
            
            if elem_lat is None or elem_lon is None:
                continue
            
            distance = geopy.distance.distance((lat, lon), (elem_lat, elem_lon)).km
            facilities.append({
                "name": name,
                "latitude": elem_lat,
                "longitude": elem_lon,
                "distance_km": round(distance, 2),
                "sector_id": sector_id
            })
            
        facilities_sorted = sorted(facilities, key=lambda x: x['distance_km'])
        return facilities_sorted[:max_results]

    except Exception as e:
        return {"error": str(e)}

def calculate_score(lat, lon):
    hospitals = fetch_amenities(lat, lon, amenity_type="hospital")
    police_stations = fetch_amenities(lat, lon, amenity_type="police")
    fire_stations = fetch_amenities(lat, lon, amenity_type="fire_station")
    
    if isinstance(hospitals, dict) and "error" in hospitals:
        return hospitals

    score = 0
    score += len(hospitals) * 3 
    score += len(police_stations) * 2 
    score += len(fire_stations) * 1
    
    all_facilities = hospitals + police_stations + fire_stations

    sector_count = {}
    for facility in all_facilities:
        sector_id = facility.get("sector_id", "Unknown")
        if sector_id == "Unknown":
            continue
        sector_count[sector_id] = sector_count.get(sector_id, 0) + 1

    if not sector_count:
        weakest_sector = {"weakest_sector_name": "No data", "facility_count": 0, "facilities": []}
    else:
        weakest_sector_id = min(sector_count, key=sector_count.get)
        weakest_count = sector_count[weakest_sector_id]
        facilities_in_weakest_sector = [f for f in all_facilities if f.get("sector_id") == weakest_sector_id]
        weakest_sector = {
            "weakest_sector_id": weakest_sector_id,
            "weakest_sector_name": weakest_sector_id,
            "facility_count": weakest_count,
            "facilities": facilities_in_weakest_sector
        }

    return {
        "location": {"latitude": lat, "longitude": lon},
        "total_score": score,
        "facilities": {
            "hospitals": len(hospitals),
            "police_stations": len(police_stations),
            "fire_stations": len(fire_stations),
        },
        "facilities_list": all_facilities[:100],
        "weakest_sector": weakest_sector
    }

@layer_3_bp.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    lat = request.args.get('latitude', type=float)
    lon = request.args.get('longitude', type=float)
    
    if lat is None or lon is None:
        return jsonify({"error": "Please provide latitude and longitude parameters"}), 400
        
    results = fetch_amenities(lat, lon, amenity_type="hospital")
    if isinstance(results, dict) and "error" in results:
        return jsonify(results), 500
        
    return jsonify({"status": "success", "data": results})

@layer_3_bp.route('/api/fire_stations', methods=['GET'])
def get_fire_stations():
    lat = request.args.get('latitude', type=float)
    lon = request.args.get('longitude', type=float)
    
    if lat is None or lon is None:
        return jsonify({"error": "Please provide latitude and longitude parameters"}), 400
        
    results = fetch_amenities(lat, lon, amenity_type="fire_station")
    if isinstance(results, dict) and "error" in results:
        return jsonify(results), 500
        
    return jsonify({"status": "success", "data": results})

@layer_3_bp.route('/api/police_stations', methods=['GET'])
def get_police_stations():
    lat = request.args.get('latitude', type=float)
    lon = request.args.get('longitude', type=float)
    
    if lat is None or lon is None:
        return jsonify({"error": "Please provide latitude and longitude parameters"}), 400
        
    results = fetch_amenities(lat, lon, amenity_type="police")
    if isinstance(results, dict) and "error" in results:
        return jsonify(results), 500
        
    return jsonify({"status": "success", "data": results})

@layer_3_bp.route('/api/score', methods=['GET'])
def get_score():
    lat = request.args.get('latitude', type=float)
    lon = request.args.get('longitude', type=float)
    
    if lat is None or lon is None:
        return jsonify({"error": "Please provide latitude and longitude parameters"}), 400
        
    score_data = calculate_score(lat, lon)
    if isinstance(score_data, dict) and "error" in score_data:
        return jsonify(score_data), 500
        
    return jsonify({"status": "success", "data": score_data})
