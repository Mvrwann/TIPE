"""
Ce module implémente les fonctions géométriques nécessaires à la simulation solaire.

Il gère :
- Le calcul de la position du soleil (hauteur, azimut) via la librairie Pysolar.
- Le calcul des angles d'incidence sur les panneaux.
- La modélisation des ombres portées (longueur et facteur de couverture).
"""

import numpy as np
from pysolar.solar import get_altitude, get_azimuth
import datetime


def position_soleil(latitude: float, longitude: float, date_heure: datetime.datetime) -> tuple:
    """
    Retourne la hauteur et l'azimut du soleil pour un lieu et une date donnés.

    Args:
        latitude (float): Latitude du lieu en degrés décimaux.
        longitude (float): Longitude du lieu en degrés décimaux.
        date_heure (datetime.datetime): Date et heure de la simulation.

    Returns:
        tuple: (altitude, azimut) en degrés.
               - altitude : angle par rapport à l'horizon (0° = horizon, 90° = zénith).
               - azimut : orientation par rapport au Nord (180° = Sud).
    """
    # Pysolar attend une timezone aware datetime
    if date_heure.tzinfo is None:
        date_heure = date_heure.replace(tzinfo=datetime.timezone.utc)
    altitude = get_altitude(latitude, longitude, date_heure)
    azimut = get_azimuth(latitude, longitude, date_heure)
    return altitude, azimut


def angle_incidence(hauteur_soleil: float, azimut_soleil: float, 
                    inclinaison_panneau: float, azimut_panneau: float) -> float:
    """
    Calcule l'angle d'incidence des rayons solaires sur la surface du panneau.
    
    L'angle d'incidence est l'angle entre le vecteur solaire et le vecteur normal 
    à la surface du panneau.

    Args:
        hauteur_soleil (float): Hauteur du soleil en degrés.
        azimut_soleil (float): Azimut du soleil en degrés.
        inclinaison_panneau (float): Inclinaison du panneau par rapport à l'horizontale (Tilt).
        azimut_panneau (float): Orientation du panneau (180 = Sud).

    Returns:
        float: Angle d'incidence en degrés.
    """
    h_s_rad = np.radians(hauteur_soleil)
    a_s_rad = np.radians(azimut_soleil)
    i_p_rad = np.radians(inclinaison_panneau)
    a_p_rad = np.radians(azimut_panneau)

    # Vecteur Solaire (S)
    Sx = np.cos(h_s_rad) * np.sin(a_s_rad)
    Sy = np.cos(h_s_rad) * np.cos(a_s_rad)
    Sz = np.sin(h_s_rad)

    # Vecteur Normal du Panneau (P)
    Px = np.sin(i_p_rad) * np.sin(a_p_rad)
    Py = np.sin(i_p_rad) * np.cos(a_p_rad)
    Pz = np.cos(i_p_rad)

    # Produit scalaire
    dot = Sx * Px + Sy * Py + Sz * Pz
    
    # Clip pour éviter les erreurs numériques hors de [-1, 1]
    return np.degrees(np.arccos(np.clip(dot, -1.0, 1.0)))


def longueur_ombre(hauteur_soleil: float, azimut_soleil: float, 
                   inclinaison_panneau: float, hauteur_panneau: float) -> float:
    """
    Calcule la longueur de l'ombre projetée au sol par un panneau.
    
    Utilise une formule simplifiée 2D suffisante pour l'approximation des rangées infinies.
    Formule : L_ombre = L * (cos(beta) + sin(beta)/tan(alpha))

    Args:
        hauteur_soleil (float): Hauteur du soleil en degrés (alpha).
        azimut_soleil (float): Azimut du soleil (non utilisé dans l'approx 2D standard mais gardé pour signature).
        inclinaison_panneau (float): Angle du panneau (beta).
        hauteur_panneau (float): Longueur du côté du panneau (L).

    Returns:
        float: Longueur de l'ombre au sol en mètres.
    """
    if hauteur_soleil <= 0:
        return 1000.0  # Convention : Ombre "infinie" la nuit

    alpha_rad = np.radians(hauteur_soleil)
    beta_rad = np.radians(inclinaison_panneau)

    # Projection horizontale du panneau + Projection de l'ombre portée
    term1 = np.cos(beta_rad)
    term2 = np.sin(beta_rad) / np.tan(alpha_rad)

    return hauteur_panneau * (term1 + term2)


def pourcentage_ombre(longueur_ombre: float, espacement: float, hauteur_panneau: float) -> float:
    """
    Calcule le pourcentage de la surface du panneau voisin qui est ombragé.

    Args:
        longueur_ombre (float): Longueur totale de l'ombre projetée au sol.
        espacement (float): Distance entre le pied du panneau A et le pied du panneau B (Pitch).
        hauteur_panneau (float): Longueur du côté du panneau.

    Returns:
        float: Ratio d'ombre entre 0.0 (pas d'ombre) et 1.0 (totalement ombré).
    """
    if longueur_ombre <= espacement:
        return 0.0

    depassement = longueur_ombre - espacement
    # On suppose que l'ombre monte linéairement sur le panneau suivant
    ratio = depassement / hauteur_panneau
    return min(1.0, ratio)