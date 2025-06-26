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
        
        """# Convertir en (lat, lon) pour calcul géodésique
        lat0, lon0 = p0[1], p0[0]
        lat1, lon1 = p1[1], p1[0]"""
        
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

    api_key = "5b3ce3597851110001cf6248a792bc3d7c544a5988c36630a5d760a2"
    client = openrouteservice.Client(key=api_key)

    route = client.directions(
        coordinates=[depart_coordonne[::-1], arrive_coordonne[::-1]],
        profile='driving-car',
        format='geojson'
    )

    coordinates = route['features'][0]['geometry']['coordinates']
    coordinates = interpoler_points(coordinates, distance=DISTANCE)

    carte = folium.Map(location=depart_coordonne, zoom_start=15)
    folium.GeoJson(route, name='route').add_to(carte)
    folium.Marker(depart_coordonne, popup="Départ", icon=folium.Icon(color="green")).add_to(carte)
    folium.Marker(arrive_coordonne, popup="Arrivée", icon=folium.Icon(color="red")).add_to(carte)

    roadbook = []
    full_point_data = []

    i = 1
    seuil_angle_min = 10  # Réduit pour détecter plus de virages
    seuil_angle_total = 20  # Réduit pour détecter plus de virages
    distance_max_virage = 150  # NOUVEAU: Distance maximale pour considérer un virage (en mètres)

    while i < len(coordinates) - 1:
        p0 = np.array(coordinates[i - 1])
        p1 = np.array(coordinates[i])
        p2 = np.array(coordinates[i + 1])

        v1 = p1 - p0
        v2 = p2 - p1

        angle = calcul_angle(v1, v2)
        if np.isnan(angle) or angle < 5:  # Seuil très bas pour le filtrage initial
            i += 1
            continue

        cross = np.cross(v1, v2)
        direction = "gauche" if cross > 0 else "droite"

        angle_total = angle
        j = i + 1
        distance_totale_virage = 0  # NOUVEAU: Suivre la distance du virage

        # Regroupement des points du virage
        while j < len(coordinates) - 1:
            p_prev = np.array(coordinates[j - 1])
            p_curr = np.array(coordinates[j])
            p_next = np.array(coordinates[j + 1])

            # NOUVEAU: Calculer la distance parcourue dans le virage
            distance_segment = distance_geodesique(p_prev, p_curr)
            distance_totale_virage += distance_segment
            
            # NOUVEAU: Arrêter si le virage devient trop long (probablement une ligne droite)
            if distance_totale_virage > distance_max_virage:
                break

            v_prev = p_curr - p_prev
            v_next = p_next - p_curr

            a = calcul_angle(v_prev, v_next)
            if np.isnan(a) or a < 10:  # Seuil très bas pour ne pas rater les petits changements
                break

            c = np.cross(v_prev, v_next)
            d = "gauche" if c > 0 else "droite"

            if d == direction and a >= seuil_angle_min:
                angle_total += a
                j += 1
            else:
                # Vérifier si c'est juste un petit changement de direction
                if abs(a - angle) < 10 and d != direction:
                    # Petite correction, on continue dans la même direction
                    angle_total += a * 0.7  # On compte partiellement
                    j += 1
                else:
                    break

        # NOUVEAU: Vérifier aussi le ratio angle/distance pour éviter les faux virages
        if distance_totale_virage > 0:
            ratio_angle_distance = angle_total / (distance_totale_virage / 10)  # Angle par 10m
            if ratio_angle_distance < 1:  # Réduit de 2 à 1 pour être moins strict
                i += 1
                continue

        if angle_total < seuil_angle_total:
            i += 1
            continue

        # Début et fin du virage
        index_debut = max(i - 1, 0)
        index_fin = min(j, len(coordinates) - 1)
        point_debut = coordinates[index_debut]
        point_fin = coordinates[index_fin]

        angle_final = int(angle_total)

        # Classification copilote MODIFIÉE avec des seuils plus stricts
        if angle_final < 45:  # Augmenté de 30 à 45
            note = f"{direction} 6"
            color = "lightgreen"
            
        elif angle_final < 75:  # Augmenté de 60 à 75
            note = f"{direction} 5"
            color = "green"
        elif angle_final < 105:  # Augmenté de 90 à 105
            note = f"{direction} 4"
            color = "orange"
        elif angle_final < 135:  # Augmenté de 120 à 135
            note = f"{direction} 3"
            color = "darkorange"
        elif angle_final < 165:  # Augmenté de 150 à 165
            note = f"{direction} 2"
            color = "red"
        else:
            note = f"épingle {direction} | 1"
            color = "#800000"

        # Ajouter les 2 marqueurs : début + fin
        folium.Marker(
            location=(point_debut[1], point_debut[0]),
            popup=f"Début {note} (Distance: {distance_totale_virage:.0f}m)",  # NOUVEAU: Afficher la distance
            icon=folium.Icon(color=color, icon="play", prefix="fa")
        ).add_to(carte)

        folium.Marker(
            location=(point_fin[1], point_fin[0]),
            popup=f"Fin {note} (Distance: {distance_totale_virage:.0f}m)",  # NOUVEAU: Afficher la distance
            icon=folium.Icon(color=color, icon="stop", prefix="fa")
        ).add_to(carte)

        # Ajouter au roadbook
        roadbook.append((point_debut[1], point_debut[0], f"Début {note}", angle_final))
        roadbook.append((point_fin[1], point_fin[0], f"Fin {note}", angle_final))

        # Colorier tout le virage
        for k in range(index_debut, index_fin):
            if k + 1 >= len(coordinates):
                break
            lon1, lat1 = coordinates[k]
            lon2, lat2 = coordinates[k + 1]
            folium.PolyLine(
                locations=[(lat1, lon1), (lat2, lon2)],
                color=color,
                weight=5,
                opacity=0.9
            ).add_to(carte)

        i = max(i + 1, j - 2)  # Éviter de rater les virages suivants

    # Affichage de tous les points (points noirs)
    for lon, lat in coordinates:
        folium.CircleMarker(
            location=(lat, lon),
            radius=2,
            color="black",
            fill=True,
            fill_opacity=0.6
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