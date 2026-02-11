import streamlit as st
import google.generativeai as genai
import requests
import folium
from streamlit_folium import st_folium
from streamlit_searchbox import st_searchbox

# --- CONFIGURATION ---
# Set up your keys in .streamlit/secrets.toml
GEMINI_KEY = st.secrets["GEMINI_KEY"]
GEOAPIFY_KEY = st.secrets["GEOAPIFY_KEY"]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="AI Route Planner", layout="wide")

# --- FUNCTIONS ---

def get_city_suggestions(searchterm: str):
    """Fetches city names from Geoapify for the autocomplete searchbox."""
    if not searchterm:
        return []
    url = f"https://api.geoapify.com/v1/geocode/autocomplete?text={searchterm}&type=city&apiKey={GEOAPIFY_KEY}"
    response = requests.get(url).json()
    return [(r['properties']['formatted'], r['properties']) for r in response.get('features', [])]

def get_route(waypoints):
    """Fetches a route line between multiple coordinates."""
    # Format: "lat,lon|lat,lon"
    point_str = "|".join([f"{p[0]},{p[1]}" for p in waypoints])
    url = f"https://api.geoapify.com/v1/routing?waypoints={point_str}&mode=walk&apiKey={GEOAPIFY_KEY}"
    res = requests.get(url).json()
    # Returns the geometry (coordinates) for the line
    return res['features'][0]['geometry']['coordinates'][0]

# --- UI LAYOUT ---
st.title("🗺️ AI Interactive Travel & Route Planner")

with st.sidebar:
    st.header("Plan Your Trip")
    # 1. City Autocomplete (Avoids typos)
    selected_city_data = st_searchbox(get_city_suggestions, key="city_search", placeholder="Type a city...")
    
    duration = st.slider("Trip Duration (Days)", 1, 7, 3)
    interests = st.text_input("Interests (e.g. Coffee, Museums, Jazz)", "Art and Local Food")
    
    generate_btn = st.button("Generate Smart Itinerary")

if generate_btn and selected_city_data:
    city_name = selected_city_data['formatted']
    lat, lon = selected_city_data['lat'], selected_city_data['lon']
    
    # AI Logic: Ask Gemini to pick 3 best coordinates for the interests
    prompt = f"""
    Suggest 3 specific places for a {duration}-day trip to {city_name} focused on {interests}.
    Return ONLY a Python list of dictionaries with 'name' and approximate 'lat', 'lon'.
    Example: [{'name': 'Eiffel Tower', 'lat': 48.8584, 'lon': 2.2945}]
    """
    
    with st.spinner("AI is scouting locations..."):
        response = model.generate_content(prompt)
        # Convert string response to list (simple eval for prototype)
        places = eval(response.text.strip().replace("```python", "").replace("```", ""))

    # --- MAPPING & ROUTING ---
    st.subheader(f"Your Optimized Route in {city_name}")
    
    # Create Folium Map
    m = folium.Map(location=[lat, lon], zoom_start=13)
    
    # Prepare waypoints for routing (Start at city center -> AI spots)
    route_points = [[lat, lon]] + [[p['lat'], p['lon']] for p in places]
    
    try:
        # Draw Route Line
        route_geom = get_route(route_points)
        # Geoapify returns [lon, lat], Folium needs [lat, lon]
        folium.PolyLine([[p[1], p[0]] for p in route_geom], color="blue", weight=5, opacity=0.7).add_to(m)
    except:
        st.warning("Could not generate a walking route, showing markers only.")

    # Add Markers
    for p in places:
        folium.Marker([p['lat'], p['lon']], popup=p['name'], icon=folium.Icon(color='red', icon='info-sign')).add_to(m)
    
    # Display Map
    st_folium(m, width=1000, height=500)

    # Show Itinerary text
    st.write("### Recommended Stops:")
    for i, p in enumerate(places):
        st.write(f"**Stop {i+1}:** {p['name']}")
