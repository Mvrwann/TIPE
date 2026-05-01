"""
Ce fichier regroupe toutes les constantes physiques et paramètres de dimensionnement
de la ferme solaire utilisée dans le TIPE.

Ces valeurs peuvent être importées globalement dans les autres modules.
"""

# --- PARAMÈTRES GÉOGRAPHIQUES (Lycée Marseille) ---
LATITUDE = 43.2965
LONGITUDE = 5.3698

# --- GÉOMÉTRIE DU PANNEAU (Unitaire) ---
PANNEAU_HAUTEUR = 1.0       # Mètres (Longueur du côté incliné/Hypoténuse)
PANNEAU_LARGEUR = 1.6       # Mètres (Largeur, donnée indicative)
PANNEAU_PUISSANCE_CRETE = 300 # Watts-crête (Wc) : Puissance max STC
PANNEAU_SURFACE = PANNEAU_HAUTEUR * PANNEAU_LARGEUR
PANNEAU_RENDEMENT = PANNEAU_PUISSANCE_CRETE / (PANNEAU_SURFACE * 1000)

# --- GÉOMÉTRIE DU CHAMP SOLAIRE ---
ESPACEMENT_RANGEES = 2.5    # Mètres (Pitch : Distance pied-à-pied axe Nord-Sud)
AZIMUT_SUD = 180            # 180° = Plein Sud (Standard hémisphère Nord)

# --- PARAMÈTRES DE SIMULATION ---
# INCLINAISON_FIXE : Angle optimal moyen pour le fixe (Marseille approx 30-35°, ici 22° pour test)
INCLINAISON_FIXE = 22       # Degrés
