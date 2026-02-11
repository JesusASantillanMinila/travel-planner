import streamlit as st
import google.generativeai as genai
import requests
import folium
from streamlit_folium import st_folium
from streamlit_searchbox import st_searchbox
import json

# --- 1. CONFIGURATION & KEYS ---
# In production, set these in the Streamlit Cloud Secrets dashboard.
# For local testing, use .streamlit/secrets.toml
try:
    GEMINI_KEY = st.secrets["GEMINI_KEY"]
    GEOAPIFY_KEY = st.secrets["GEOAPIFY_KEY"]
except Exception:
    st.error("Please set your API keys in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

st.set_page_config(page_title="AI Travel & Route Planner", layout="wide")

# --- 2. API HELPER FUNCTIONS ---

def get_city_suggestions(searchterm: str):
    """Fetches city names from Geoapify for the autocomplete searchbox."""
    if not searchterm or len(searchterm) < 3:
        return []
    url = f"https://api.geoapify.com/v1/geocode/autocomplete?text={searchterm}&type=city&apiKey={GEOAPIFY_KEY}"
    try:
        response = requests.get(url).json()
        return [(r['properties']['formatted'], r['properties']) for r in response.get('features', [])]
    except:
        return []

def get_route(waypoints):
    """Fetches a walking route geometry between coordinates."""
    point_str = "|".join([f"{p[0]},{p[1]}" for p in waypoints])
    url = f"https://api.geoapify.com/v1/routing?waypoints={point_str}&mode=walk&apiKey={GEOAPIFY_KEY}"
    res = requests.get(url).json()
    return res['features'][0]['geometry']['coordinates'][0]

# --- 3. SESSION STATE INITIALIZATION ---
# This prevents the app from losing data when Streamlit reruns
if "itinerary" not in st.session_state:
    st.session_state.itinerary = None
if "route" not in st.session_state:
    st.session_state.route = None
if "city_center" not in st.session_state:
    st.session_state.city_center = None

# --- 4. UI SIDEBAR ---
st.title("🗺️ AI Route Planner & Travel Guide")

with st.sidebar:
    st.header("Trip Settings")
    
    # City Searchbox
    selected_city_data = st_searchbox(
        get_city_suggestions, 
        key="city_search", 
        placeholder="Search for a city (e.g. London)..."
    )
    
    duration = st.slider("Duration (Days)", 1, 7, 3)
    interests = st.text_input("Interests", "Historical sites and local food")
    
    generate_btn = st.button("Generate Smart Route", type="primary")

# --- 5. LOGIC: GENERATE ITINERARY ---
if generate_btn and selected_city_data:
    city_name = selected_city_data['formatted']
    lat, lon = selected_city_data['lat'], selected_city_data['lon']
    
    with st.spinner(f"AI is planning your trip to {city_name}..."):
        # Gemini Prompt with specific JSON instructions
        prompt = f"""
        Suggest 3 specific places/attractions for a {duration}-day trip to {city_name} focused on {interests}.
        Return the result as a JSON list of objects.
        Each object must have 'name', 'lat', and 'lon'.
        Example: [{{'name': 'Place A', 'lat': 12.34, 'lon': 56.78}}]
        """
        
        try:
            # Generate content using JSON mode
            response = model.generate_content(
                prompt, 
                generation_config={"response_mime_type": "application/json"}
            )
            places = json.loads(response.text)
            
            # Prepare waypoints: Start at city center -> AI spots
            route_points = [[lat, lon]] + [[p['lat'], p['lon']] for p in places]
            
            # Fetch Route
            route_geom = get_route(route_points)
            
            # Save to Session State
            st.session_state.itinerary = places
            st.session_state.route = route_geom
            st.session_state.city_center = [lat, lon]
            st.session_state.city_name = city_name
            
        except Exception as e:
            st.error(f"Error generating itinerary: {e}")

# --- 6. DISPLAY PERSISTENT CONTENT ---
if st.session_state.itinerary:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"Interactive Route: {st.session_state.city_name}")
        
        # Create Map
        m = folium.Map(location=st.session_state.city_center, zoom_start=13)
        
        # Draw Route
        if st.session_state.route:
            # Geoapify is [lon, lat], Folium is [lat, lon]
            clean_route = [[p[1], p[0]] for p in st.session_state.route]
            folium.PolyLine(clean_route, color="#3388ff", weight=5, opacity=0.8).add_to(m)

        # Add Markers
        for p in st.session_state.itinerary:
            folium.Marker(
                [p['lat'], p['lon']], 
                popup=p['name'],
                icon=folium.Icon(color='red', icon='map-pin', prefix='fa')
            ).add_to(m)
        
        # Display the map (using a key to maintain state)
        st_folium(m, width="100%", height=500, key="main_map")

    with col2:
        st.subheader("Itinerary Details")
        for i, p in enumerate(st.session_state.itinerary):
            with st.expander(f"Stop {i+1}: {p['name']}", expanded=True):
                st.write(f"Located at: {p['lat']}, {p['lon']}")
                st.button(f"View on Google Maps", key=f"btn_{i}", on_click=lambda p=p: st.write(f"https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}"))

else:
    st.info("Select a city and click 'Generate' to see your AI-powered travel route!")
