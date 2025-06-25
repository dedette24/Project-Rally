import folium
import openrouteservice
import numpy as np
from geopy.distance import geodesic

# === Coordonnées de départ et d'arrivée ===
debut = (49.060418927265914, 1.5994303744710572)
fin = (49.06855955197321, 1.6009684049876223)

DISTANCE = 50  # Distance d'interpolation en mètres

def calcul_angle(v1, v2):
    """Calcule l'angle entre deux vecteurs."""
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    # Vérification pour éviter la division par zéro
    if norm_v1 == 0 or norm_v2 == 0:
        return 0  # Retourne 0 si l'un des vecteurs est nul

    angle_rad = np.arccos(np.clip(np.dot(v1, v2) / (norm_v1 * norm_v2), -1.0, 1.0))
    return np.degrees(angle_rad)

def distance_geodesique(p1, p2):
    """Calcule la distance en mètres entre deux points (lat, lon)."""
    return geodesic((p1[1], p1[0]), (p2[1], p2[0])).meters

def interpoler_points(coordinates, distance=DISTANCE):
    """Interpole des points tous les 'distance' mètres."""
    interpolated_points = []
    for i in range(len(coordinates) - 1):
        p0 = np.array(coordinates[i])
        p1 = np.array(coordinates[i + 1])
        
        segment_length = distance_geodesique(p0, p1)
        
        if segment_length <= distance:
            # Cas des segments très courts - on garde uniquement les extrémités
            interpolated_points.append(p0)
            if i == len(coordinates) - 2:  # Dernier segment
                interpolated_points.append(p1)
        else:
            num_points = max(2, int(np.ceil(segment_length / distance)))
            
            # Interpolation linéaire
            for j in range(num_points):
                ratio = j / (num_points - 1)
                new_point = p0 + ratio * (p1 - p0)
                interpolated_points.append(new_point)
    
    return np.array(interpolated_points)

def recup_itineraire_complet(depart_coordonne, arrive_coordonne):
    """Récupère l'itinéraire complet et génère la carte."""
    # === Appel API OpenRouteService ===
    api_key = "5b3ce3597851110001cf6248a792bc3d7c544a5988c36630a5d760a2"
    client = openrouteservice.Client(key=api_key)

    route = client.directions(
        coordinates=[depart_coordonne[::-1], arrive_coordonne[::-1]],
        profile='driving-car',
        format='geojson'
    )

    coordinates = route['features'][0]['geometry']['coordinates']
    coordinates = interpoler_points(coordinates)  # Interpolation des points
    carte = folium.Map(location=depart_coordonne, zoom_start=15)
    folium.GeoJson(route, name='route').add_to(carte)

    folium.Marker(depart_coordonne, popup="Départ", icon=folium.Icon(color="green")).add_to(carte)
    folium.Marker(arrive_coordonne, popup="Arrivée", icon=folium.Icon(color="red")).add_to(carte)

    roadbook = []
    full_point_data = []
    last_angle = None
    last_note = None

    for i in range(1, len(coordinates)-1):
        p0 = np.array(coordinates[i-1])
        p1 = np.array(coordinates[i])
        p2 = np.array(coordinates[i+1])

        v1 = p1 - p0
        v2 = p2 - p1

        angle = calcul_angle(v1, v2)
        
        # Vérification si l'angle est valide
        if np.isnan(angle):
            continue  # Ignorer ce point si l'angle est NaN

        cross = np.cross(v1, v2)
        direction = "gauche" if cross > 0 else "droite"

        lat, lon = p1[1], p1[0]

        # Classification des virages
        if angle < 10:  # Angle très faible - tout droit
            note = "tout droit"
            color = "gray" 
            icon = "circle"
        elif angle < 30:  # Léger changement de direction
            note = f"{direction} 6"
            color = "lightgreen"
            icon = "flag"
        elif angle < 60:  # Virage large
            note = f"{direction} 5" 
            color = "green"
            icon = "flag"
        elif angle < 90:  # Virage moyen
            note = f"{direction} 4"
            color = "orange"
            icon = "flag"
        elif angle < 120:  # Virage serré
            note = f"{direction} 3"
            color = "darkorange"
            icon = "flag"
        elif angle < 150:  # Virage très serré
            note = f"{direction} 2"
            color = "red"
            icon = "flag"
        else:  # Épingle à cheveux
            note = f"épingle {direction} | 1"
            color = "darkred"
            icon = "flag"

        # Vérification de répétition (on garde le premier point d'une série)
        if last_note == note and abs(last_angle - angle) < 5:  # Seuil de 5°
            continue

        last_angle = angle
        last_note = note

        # Ajouter au roadbook et à la liste complète
        roadbook.append((lat, lon, note, int(angle)))
        full_point_data.append((lat, lon, note, int(angle)))

        # Ajouter le point sur la carte
        folium.Marker(
            location=(lat, lon),
            popup=f"{note} ({int(angle)}°)",
            icon=folium.Icon(color=color, icon=icon, prefix="fa")
        ).add_to(carte)

    carte.save("rendu_html/carte_rally_avec_tous_points.html")
    print("✅ Carte créée : carte_rally_avec_tous_points.html")

    return roadbook, full_point_data

# === Appel principal ===
roadbook, all_points_data = recup_itineraire_complet(debut, fin)

# === Affichage ===
print("\nRoadbook copilote :")
for lat, lon, note, angle in roadbook:
    print(f"{lat:.6f}, {lon:.6f} : {note} ({angle}°)")

print("\nTous les points avec classification :")
for lat, lon, note, angle in all_points_data:
    print(f"{lat:.6f}, {lon:.6f} : {note} ({angle}°)")
