import folium
import openrouteservice
import numpy as np
from geopy.distance import geodesic

# === Coordonnées de départ et d'arrivée ===
debut = (49.060418927265914, 1.5994303744710572)
fin = (49.06855955197321, 1.6009684049876223)

DISTANCE = 50

def calcul_angle(v1, v2):
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    # Vérification pour éviter la division par zéro
    if norm_v1 == 0 or norm_v2 == 0:
        return 0  # Retourne 0 si l'un des vecteurs est nul

    angle_rad = np.arccos(np.clip(np.dot(v1, v2) / (norm_v1 * norm_v2), -1.0, 1.0))
    return np.degrees(angle_rad)

def distance_geodesique(p1, p2):
    """Calcule la distance en mètres entre deux points (lat, lon)"""
    return geodesic((p1[1], p1[0]), (p2[1], p2[0])).meters

def interpoler_points(coordinates, distance=DISTANCE):
    interpolated_points = []
    for i in range(len(coordinates) - 1):
        p0 = np.array(coordinates[i])
        p1 = np.array(coordinates[i + 1])
        
        # Convertir en (lat, lon) pour calcul géodésique
        lat0, lon0 = p0[1], p0[0]
        lat1, lon1 = p1[1], p1[0]
        
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
    import folium
    import openrouteservice
    import numpy as np

    # === Appel API OpenRouteService ===
    api_key = "5b3ce3597851110001cf6248a792bc3d7c544a5988c36630a5d760a2"
    client = openrouteservice.Client(key=api_key)

    route = client.directions(
        coordinates=[depart_coordonne[::-1], arrive_coordonne[::-1]],
        profile='driving-car',
        format='geojson'
    )

    # === Récupérer et interpoler les coordonnées ===
    coordinates = route['features'][0]['geometry']['coordinates']
    coordinates = interpoler_points(coordinates, distance=DISTANCE)  # Rééchantillonnage tous les 50m

    # === Création de la carte ===
    carte = folium.Map(location=depart_coordonne, zoom_start=15)
    folium.GeoJson(route, name='route').add_to(carte)
    folium.Marker(depart_coordonne, popup="Départ", icon=folium.Icon(color="green")).add_to(carte)
    folium.Marker(arrive_coordonne, popup="Arrivée", icon=folium.Icon(color="red")).add_to(carte)

    # === Initialisation des données à retourner ===
    roadbook = []
    full_point_data = []

    # === Regroupement des virages continus ===
    i = 1
    seuil_angle_min = 10        # ignore les micro-changements
    seuil_angle_total = 20      # angle cumulé minimal pour considérer un virage

    while i < len(coordinates) - 1:
        p0 = np.array(coordinates[i - 1])
        p1 = np.array(coordinates[i])
        p2 = np.array(coordinates[i + 1])

        v1 = p1 - p0
        v2 = p2 - p1

        angle = calcul_angle(v1, v2)
        if np.isnan(angle):
            i += 1
            continue

        cross = np.cross(v1, v2)
        direction = "gauche" if cross > 0 else "droite"

        angle_total = angle
        j = i + 1

        # Regrouper les virages dans la même direction
        while j < len(coordinates) - 1:
            p_prev = np.array(coordinates[j - 1])
            p_curr = np.array(coordinates[j])
            p_next = np.array(coordinates[j + 1])

            v_prev = p_curr - p_prev
            v_next = p_next - p_curr

            a = calcul_angle(v_prev, v_next)
            if np.isnan(a):
                break

            c = np.cross(v_prev, v_next)
            d = "gauche" if c > 0 else "droite"

            if d == direction and a >= seuil_angle_min:
                angle_total += a
                j += 1
            else:
                break

        # Ne rien marquer si pas assez de courbure
        if angle_total < seuil_angle_total:
            i += 1
            continue

        lat, lon = coordinates[i][1], coordinates[i][0]
        angle_final = int(angle_total)

        # Classification copilote selon angle cumulé
        if angle_final < 30:
            note = f"{direction} 6"
            color = "lightgreen"
        elif angle_final < 60:
            note = f"{direction} 5"
            color = "green"
        elif angle_final < 90:
            note = f"{direction} 4"
            color = "orange"
        elif angle_final < 120:
            note = f"{direction} 3"
            color = "darkorange"
        elif angle_final < 150:
            note = f"{direction} 2"
            color = "red"
        else:
            note = f"épingle {direction} | 1"
            color = "darkred"

        roadbook.append((lat, lon, note, angle_final))
        full_point_data.append((lat, lon, note, angle_final))

        # Marqueur
        folium.Marker(
            location=(lat, lon),
            popup=f"{note} ({angle_final}°)",
            icon=folium.Icon(color=color, icon="flag", prefix="fa")
        ).add_to(carte)

        i = j  # sauter les points déjà analysés dans le regroupement

    # === Colorer les segments entre les points selon l’angle ===
    for i in range(1, len(coordinates) - 1):
        p0 = np.array(coordinates[i - 1])
        p1 = np.array(coordinates[i])
        p2 = np.array(coordinates[i + 1])

        v1 = p1 - p0
        v2 = p2 - p1
        angle = calcul_angle(v1, v2)
        if np.isnan(angle):
            continue

        # Choix de couleur selon l’angle
        if angle < 10:
            seg_color = "bleu"
        elif angle < 30:
            seg_color = "lightgreen"
        elif angle < 60:
            seg_color = "green"
        elif angle < 90:
            seg_color = "orange"
        elif angle < 120:
            seg_color = "red"
        elif angle < 150:
            seg_color = "darkred"
        else:
            seg_color = "#800000"  # bordeaux = épingle

        # Tracer le segment p0 → p1
        folium.PolyLine(
            locations=[(p0[1], p0[0]), (p1[1], p1[0])],
            color=seg_color,
            weight=5,
            opacity=0.8
        ).add_to(carte)

    # === Ajouter tous les points GPS bruts (points noirs) ===
    for lon, lat in coordinates:
        folium.CircleMarker(
            location=(lat, lon),
            radius=3,
            color="black",
            fill=True,
            fill_opacity=0.7
        ).add_to(carte)

    # Enregistrement de la carte
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
