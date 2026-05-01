"""
Ce module gère la logique de décision et le calcul énergétique de la ferme solaire.

Il contient :
- Les algorithmes de tracking (Suivi simple vs Backtracking).
- Le modèle de calcul de puissance instantanée (Loi des cosinus + Hard Shading).
- La boucle de simulation temporelle journalière.
"""

import matplotlib.pyplot as plt
import numpy as np
import datetime
from geometrie import position_soleil, angle_incidence, longueur_ombre, pourcentage_ombre
from constantes import *
import pytz

TZ_LOCALE = pytz.timezone("Europe/Paris")


def angle_optimal_tracking(hauteur_soleil: float) -> float:
    """
    Approximation 2D : valide uniquement quand le soleil est proche du méridien Sud.
    Erreur maximale en début/fin de journée (azimut ≠ 180°).
    Hypothèse acceptable dans le cadre d'un tracker 1 axe Est-Ouest.
    """
    # Si le soleil est à 30° de hauteur, le panneau doit être à 60° (90 - 30)
    # pour être face au soleil.
    return max(0, 90 - hauteur_soleil)


def angle_backtracking(hauteur_soleil: float, azimut_soleil: float, 
                       espacement_rangees: float, hauteur_panneau: float, 
                       azimut_panneau: float) -> float:
    """
    Détermine l'angle du tracker en utilisant l'algorithme de Backtracking.
    
    Le but est de s'aplatir (réduire l'angle) si l'ombre portée risque de toucher
    la rangée suivante, sacrifiant l'incidence pour éviter l'ombrage total.

    Args:
        hauteur_soleil (float): Hauteur du soleil.
        azimut_soleil (float): Azimut du soleil.
        espacement_rangees (float): Distance inter-rangées (Pitch).
        hauteur_panneau (float): Taille du panneau.
        azimut_panneau (float): Orientation de la ferme.

    Returns:
        float: Angle optimisé du panneau.
    """
    angle_ideal = angle_optimal_tracking(hauteur_soleil)
    
    # Soleil trop bas (aube/crépuscule) : mise à plat par sécurité
    if hauteur_soleil <= 5: 
        return 0

    L_ombre = longueur_ombre(hauteur_soleil, azimut_soleil, angle_ideal, hauteur_panneau)

    # Si l'ombre dépasse l'espacement, on doit "backtracker" (réduire l'angle)
    if L_ombre > espacement_rangees:
        # Recherche dichotomique de l'angle limite (Shadow Free)
        angle_min, angle_max = 0, angle_ideal
        for _ in range(15): # 15 itérations suffisent pour une précision < 0.1°
            angle_mid = (angle_min + angle_max) / 2
            L_test = longueur_ombre(hauteur_soleil, azimut_soleil, angle_mid, hauteur_panneau)
            if L_test > espacement_rangees:
                angle_max = angle_mid # Encore trop d'ombre, on réduit l'angle
            else:
                angle_min = angle_mid
        return angle_min
    else:
        # Pas d'ombre gênante, on garde l'optimum
        return angle_ideal


def calculer_puissance(angle_incidence: float, puissance_crete: float, 
                       pourcentage_ombre: float) -> float:
    """
    Calcule la puissance électrique produite par un panneau.
    
    Modèle "Hard Shading" : Si plus de 5% du panneau est à l'ombre, 
    la production tombe à 0 (simulation de strings en série sans diodes efficaces).

    Args:
        angle_incidence (float): Angle entre rayon et normale panneau.
        rendement (float): Rendement de conversion du module (ex: 0.20).
        puissance_crete (float): Puissance nominale STC du panneau en Watts.
        pourcentage_ombre (float): Fraction ombragée (0.0 à 1.0).

    Returns:
        float: Puissance de sortie en Watts.
    """
    if angle_incidence > 90: 
        return 0 # Soleil derrière le panneau
        
    facteur_cos = np.cos(np.radians(angle_incidence))

    # Modèle "Maillon Faible" drastique pour le TIPE
    if pourcentage_ombre > 0.05:
        facteur_ombre = 0.0
    else:
        facteur_ombre = 1.0

    return puissance_crete * facteur_cos * facteur_ombre


def simuler_journee(date: datetime.date, afficher_graphe: bool = True):
    """
    Simule la production complète d'une journée pour les 3 stratégies.

    Args:
        date (datetime.date): La journée à simuler.
        afficher_graphe (bool): Si True, affiche un plot Matplotlib (pour debug).

    Returns:
        tuple: (Energie_Fixe, Energie_Track, Energie_Back) en Wh.
    """
    heures_float = []
    res_fixe, res_track, res_back = [], [], []

    # Configuration temporelle (UTC pour éviter problèmes d'été/hiver local)
    temps_debut_local = TZ_LOCALE.localize(datetime.datetime(date.year, date.month, date.day, 6, 0))
    temps_fin_local = TZ_LOCALE.localize(datetime.datetime(date.year, date.month, date.day, 20, 0))
    temps_actuel = temps_debut_local.astimezone(datetime.timezone.utc)
    temps_fin = temps_fin_local.astimezone(datetime.timezone.utc)
    delta = datetime.timedelta(minutes=10)

    while temps_actuel < temps_fin:
        h_sol, az_sol = position_soleil(LATITUDE, LONGITUDE, temps_actuel)

        if h_sol > 0:
            # 1. STRATÉGIE FIXE
            inc_f = angle_incidence(h_sol, az_sol, INCLINAISON_FIXE, AZIMUT_SUD)
            omb_f = longueur_ombre(h_sol, az_sol, INCLINAISON_FIXE, PANNEAU_HAUTEUR)
            ombr_f = pourcentage_ombre(omb_f, ESPACEMENT_RANGEES, PANNEAU_HAUTEUR, h_sol, INCLINAISON_FIXE)
            p_f = calculer_puissance(inc_f, PANNEAU_PUISSANCE_CRETE, ombr_f)


            # 2. STRATÉGIE TRACKING NAÏF
            ang_t = angle_optimal_tracking(h_sol)
            inc_t = angle_incidence(h_sol, az_sol, ang_t, AZIMUT_SUD)
            omb_t = longueur_ombre(h_sol, az_sol, ang_t, PANNEAU_HAUTEUR)
            ombr_t = pourcentage_ombre(omb_t, ESPACEMENT_RANGEES, PANNEAU_HAUTEUR, h_sol, ang_t)
            p_t = calculer_puissance(inc_t, PANNEAU_PUISSANCE_CRETE, ombr_t)

            # 3. STRATÉGIE BACKTRACKING
            ang_b = angle_backtracking(h_sol, az_sol, ESPACEMENT_RANGEES, PANNEAU_HAUTEUR, AZIMUT_SUD)
            inc_b = angle_incidence(h_sol, az_sol, ang_b, AZIMUT_SUD)
            omb_b = longueur_ombre(h_sol, az_sol, ang_b, PANNEAU_HAUTEUR)
            ombr_b = pourcentage_ombre(omb_b, ESPACEMENT_RANGEES, PANNEAU_HAUTEUR, h_sol, ang_b)
            p_b = calculer_puissance(inc_b, PANNEAU_PUISSANCE_CRETE, ombr_b)
            
            heures_float.append(temps_actuel.hour + temps_actuel.minute / 60)
            res_fixe.append(p_f)
            res_track.append(p_t)
            res_back.append(p_b)

        temps_actuel += delta

    # Intégration Riemann (Somme des puissances * pas de temps)
    dt_heures = 10 / 60 # pas de 10 minutes en heures
    e_fixe = sum(res_fixe) * dt_heures
    e_track = sum(res_track) * dt_heures
    e_back = sum(res_back) * dt_heures

    if afficher_graphe:
        print(f"Bilan Journée : Fixe={e_fixe:.1f}Wh, Backtracking={e_back:.1f}Wh")
        plt.figure(figsize=(10, 6))
        plt.plot(heures_float, res_fixe, label=f"Fixe ({INCLINAISON_FIXE}°)")
        plt.plot(heures_float, res_track, label="Tracking Naïf", linestyle="--")
        plt.plot(heures_float, res_back, label="Backtracking", linewidth=2, color="red")
        plt.xlabel("Heure (UTC)")
        plt.ylabel("Puissance Unitaire (W)")
        plt.legend()
        if isinstance(date, datetime.datetime):
            date = date.date()
        plt.title(f"Simulation du {date.isoformat()}")
        plt.show()

    return e_fixe, e_track, e_back


if __name__ == "__main__":
    # Test unitaire rapide
    simuler_journee(datetime.date(2024, 6, 21), afficher_graphe=True)
