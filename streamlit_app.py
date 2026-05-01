"""
Point d'entrée de l'application Streamlit (Dashboard).

Ce fichier gère l'interface utilisateur, la récupération des entrées (sliders, dates),
et l'appel aux fonctions de simulation pour générer les graphiques interactifs via Plotly.
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import datetime
import pandas as pd
import plotly.graph_objects as go
from geometrie import pourcentage_ombre
import pytz

# --- CONFIGURATION GLOBALE ---
st.set_page_config(layout="wide", page_title="SolarTrack : Analyse Industrielle")

# --- STYLE CSS ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
    font-size: 1.1rem;
    font-weight: bold;
    }
    .stInfo, .stWarning {
        padding: 0.8rem;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- IMPORTATION MODULES ---
try:
    from geometrie import position_soleil, angle_incidence, longueur_ombre
    from simulation import angle_backtracking, calculer_puissance
    from constantes import *
except ImportError:
    st.error("ERREUR : Modules manquants. Assurez-vous que geometrie.py, simulation.py et constantes.py sont présents.")
    st.stop()

# --- CONSTANTES ---
LAT, LON = 43.2965, 5.3698  # Marseille
TZ_LOCALE = pytz.timezone("Europe/Paris")

def to_utc(date_obj: datetime.date, hour_float: float) -> datetime.datetime:
    local_dt = TZ_LOCALE.localize(
        datetime.datetime.combine(date_obj, datetime.time(int(hour_float), int((hour_float % 1) * 60)))
    )
    return local_dt.astimezone(datetime.timezone.utc)

# --- ETAT SESSION ---
if 'angle_fixe_opti' not in st.session_state:
    st.session_state.angle_fixe_opti = 30
if 'mode_opti' not in st.session_state:
    st.session_state.mode_opti = "Manuel"


# --- MOTEUR PRIX (SIMULATION MARCHÉ SPOT) ---
def get_market_price(date_obj: datetime.date, hour: float) -> float:
    """
    Simule le prix Spot de l'électricité (€/MWh) basé sur la saisonnalité et l'heure.
    Modèle stochastique simplifié : Saison + Heure + Bruit aléatoire.
    """
    month = date_obj.month
    # Saisonnalité (Prix plus élevés en hiver)
    if month in [11, 12, 1, 2]: base = 120.0
    elif month in [6, 7, 8]: base = 70.0
    else: base = 90.0

    # Horaire (Pointes matin et soir, creux solaire midi)
    if 7 <= hour < 10: coeff = 1.3
    elif 18 <= hour < 21: coeff = 1.4
    elif 11 <= hour < 16: coeff = 0.6
    else: coeff = 1.0

    seed = date_obj.toordinal()
    variation = (seed % 20) - 10 # Petit bruit aléatoire
    return max(0, base * coeff + variation)


# --- CALCUL PHYSIQUE (UNITAIRE) ---
def calcul_physique_complet(h_sol, az_sol, angle_panneau, espacement):
    """Wrapper utilitaire pour calculer toutes les métriques d'un coup."""
    inc = angle_incidence(h_sol, az_sol, angle_panneau, AZIMUT_SUD)
    omb = longueur_ombre(h_sol, az_sol, angle_panneau, PANNEAU_HAUTEUR)
    ombr = pourcentage_ombre(omb, espacement, PANNEAU_HAUTEUR, h_sol, angle_panneau)
    p_out = calculer_puissance(inc, PANNEAU_PUISSANCE_CRETE, ombr)
    return p_out, inc, omb, ombr > 0.05


# --- VISUEL NOTATIONS (POUR ONGLET 4) ---
def generer_schema_notations():
    """Génère un schéma explicatif des notations géométriques avec Matplotlib."""
    fig, ax = plt.subplots(figsize=(10, 5))

    # Paramètres dessin
    x0, y0 = 2, 0
    L = 3
    angle = 30
    angle_rad = np.radians(angle)
    pitch = 6

    # 1. Le Sol
    ax.axhline(0, color='black', linewidth=2)
    ax.text(0.5, -0.3, "SOL (Horizontale)", fontsize=10)

    # 2. Le Panneau (Premier)
    x1 = x0 + L * np.cos(angle_rad)
    y1 = y0 + L * np.sin(angle_rad)
    ax.plot([x0, x1], [y0, y1], color='#3498db', linewidth=6, label='Panneau')

    # 3. Le Panneau Voisin (Fantôme)
    x0_2 = x0 + pitch
    x1_2 = x0_2 + L * np.cos(angle_rad)
    y1_2 = y0 + L * np.sin(angle_rad)
    ax.plot([x0_2, x1_2], [0, y1_2], color='#3498db', linewidth=6, alpha=0.3)

    # 4. Annotations
    # Angle inclinaison (Beta)
    arc = patches.Arc((x0, 0), 2.5, 2.5, angle=0, theta1=0, theta2=angle, color='red', linewidth=2)
    ax.add_patch(arc)
    ax.text(x0 + 1.5, 0.4, r'$\beta$', color='red', fontsize=16, weight='bold')

    # Hauteur panneau (L)
    ax.text(x0 + L/2*np.cos(angle_rad) - 0.5, L/2*np.sin(angle_rad) + 0.5, "L (Longueur)", color='#2980b9', rotation=angle, weight='bold')

    # Espacement (Pitch)
    ax.annotate('', xy=(x0, -0.8), xytext=(x0_2, -0.8), arrowprops=dict(arrowstyle='<->', color='green', lw=2))
    ax.text((x0 + x0_2)/2, -1.2, "d (Espacement / Pitch)", color='green', ha='center', weight='bold', fontsize=12)

    # Soleil (Alpha)
    sun_x, sun_y = x0 - 1, 4.5
    ax.plot(sun_x, sun_y, 'o', color='orange', markersize=25)

    # Rayon incident
    ax.annotate('', xy=(x0+0.5, 0.5), xytext=(sun_x, sun_y), arrowprops=dict(arrowstyle='->', color='orange', linestyle='--', lw=2))
    ax.text(sun_x + 0.6, sun_y - 1.5, r"Rayons ($\alpha$)", color='orange', fontsize=12, weight='bold')

    # Esthétique
    ax.set_xlim(0, 11)
    ax.set_ylim(-2, 6)
    ax.axis('off')

    return fig


# --- VISUEL 3D ---
def generer_visuel_comparatif(angle_f, omb_f, angle_b, omb_b, espacement):
    """Génère la figure Plotly représentant la coupe latérale des panneaux."""
    fig = go.Figure()
    L = PANNEAU_HAUTEUR
    OFFSET_TRACKER = espacement * 2.5 + 4

    def _draw_system(x_start, angle, omb_len, color, name):
        rad = np.radians(angle)
        # Sol
        fig.add_trace(go.Scatter(x=[x_start - 1, x_start + espacement + 2], y=[0, 0], mode='lines',
                                 line=dict(color='gray', width=2), showlegend=False))
        # Ombre
        shadow_color = 'rgba(231, 76, 60, 0.8)' if omb_len > espacement else 'rgba(100, 110, 120, 0.5)'
        fig.add_trace(
            go.Scatter(x=[x_start, x_start + omb_len, x_start + omb_len, x_start], y=[0, 0, 0.05, 0.05], fill='toself',
                       mode='none', fillcolor=shadow_color, showlegend=False))
        # Panneau 1
        fig.add_trace(go.Scatter(x=[x_start, x_start + L * np.cos(rad)], y=[0, L * np.sin(rad)], mode='lines',
                                 line=dict(color=color, width=12), name=name))
        # Panneau 2 (virtuel pour montrer l'espacement)
        bx = x_start + espacement
        fig.add_trace(go.Scatter(x=[bx, bx + L * np.cos(rad)], y=[0, L * np.sin(rad)], mode='lines',
                                 line=dict(color=color, width=12), showlegend=False))

    _draw_system(0, angle_f, omb_f, "#3498db", "Fixe")
    _draw_system(OFFSET_TRACKER, angle_b, omb_b, "#2ecc71", "Tracker")

    # Annotations
    fig.add_annotation(x=espacement / 2, y=1.3, text="FIXE", showarrow=False, font=dict(size=14, color="#3498db"))
    fig.add_annotation(x=OFFSET_TRACKER + espacement / 2, y=1.3, text="TRACKER", showarrow=False,
                       font=dict(size=14, color="#2ecc71"))

    fig.update_layout(xaxis=dict(visible=False, range=[-2, OFFSET_TRACKER + espacement + 3]),
                      yaxis=dict(visible=False, range=[-0.2, 1.5], scaleanchor="x"), height=300,
                      margin=dict(t=30, b=0, l=0, r=0), plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    return fig


# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres Industriels")

    st.subheader("1. Dimensionnement Ferme")
    NB_PANNEAUX = st.number_input("Nombre de Panneaux", min_value=1, max_value=50000, value=1000, step=100)
    PUISSANCE_CRETE_TOTALE = (NB_PANNEAUX * PANNEAU_PUISSANCE_CRETE) / 1000  # kWc
    st.caption(f"Puissance Installée : **{PUISSANCE_CRETE_TOTALE:.0f} kWc**")

    st.markdown("---")
    st.subheader("2. Configuration")
    DATE_SIMU = st.date_input("Date Étudiée", datetime.date(2024, 12, 21))
    ESPACEMENT = st.slider("Espacement (m)", 1.5, 5.0, 2.5, step=0.1)

    st.markdown("---")
    st.subheader("3. Optimisation Fixe")
    opt_mode = st.radio("Cible :", ["Journée", "Annuelle"], horizontal=True)

    if st.button("Calculer Angle Optimal"):
        scores = []
        angles_test = range(0, 91, 1)
        with st.spinner("Optimisation..."):
            if opt_mode == "Journée":
                heures_opt = np.linspace(8, 17, 10)
                for ang in angles_test:
                    e = 0
                    for h in heures_opt:
                        t = to_utc(DATE_SIMU, h)
                        hs, azs = position_soleil(LAT, LON, t)
                        if hs > 0 and longueur_ombre(hs, azs, ang, PANNEAU_HAUTEUR) <= ESPACEMENT:
                            e += np.cos(np.radians(angle_incidence(hs, azs, ang, AZIMUT_SUD)))
                    scores.append(e)
                st.session_state.mode_opti = "Jour"
            else:
                dates_sample = [datetime.date(2024, m, 21) for m in range(1, 13)]
                heures_opt = np.linspace(9, 16, 5)
                for ang in angles_test:
                    e = 0
                    for d in dates_sample:
                        for h in heures_opt:
                            t = to_utc(d, h)
                            hs, azs = position_soleil(LAT, LON, t)
                            if hs > 0 and longueur_ombre(hs, azs, ang, PANNEAU_HAUTEUR) <= ESPACEMENT:
                                e += np.cos(np.radians(angle_incidence(hs, azs, ang, AZIMUT_SUD)))
                    scores.append(e)
                st.session_state.mode_opti = "Annuel"

            best = angles_test[np.argmax(scores)]
            st.session_state.angle_fixe_opti = best
            st.success(f"Optimum : {best}°")

    st.markdown("### Inclinaison Fixe")
    FIXE_ANGLE = st.slider("Angle $\\beta$ (0°=Plat, 90°=Vertical)", 0, 90, st.session_state.angle_fixe_opti)

# --- PAGE PRINCIPALE ---
st.title("Étude Comparative : Fixe vs Backtracking")

tab_dash, tab_eco, tab_map, tab_info = st.tabs(["Tableau de Bord", "Rentabilité & Finance", "Matrice Annuelle", "Notations & Modèles"])

with tab_dash:
    heure_simu = st.slider("Heure Solaire", 6.0, 20.0, 12.0, step=0.1)
    t_utc = to_utc(DATE_SIMU, heure_simu)
    h_sol, az_sol = position_soleil(LAT, LON, t_utc)

    prix_instant = get_market_price(DATE_SIMU, heure_simu)

    if h_sol > 0:
        pf, inc_f, omb_f, crit_f = calcul_physique_complet(h_sol, az_sol, FIXE_ANGLE, ESPACEMENT)
        ang_b = angle_backtracking(h_sol, az_sol, ESPACEMENT, PANNEAU_HAUTEUR, AZIMUT_SUD)
        pb, inc_b, omb_b, crit_b = calcul_physique_complet(h_sol, az_sol, ang_b, ESPACEMENT)

        st.plotly_chart(generer_visuel_comparatif(FIXE_ANGLE, omb_f, ang_b, omb_b, ESPACEMENT),
                        use_container_width=True)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Prod TOTALE (Fixe)", f"{pf * NB_PANNEAUX / 1000:.1f} kW")
        k2.metric("Prod TOTALE (Tracker)", f"{pb * NB_PANNEAUX / 1000:.1f} kW")

        if pf < 1 and pb > 1:
            gain_lbl, d_col = "Sauvetage", "normal"
        elif pf < 1:
            gain_lbl, d_col = "-", "off"
        else:
            g = ((pb - pf) / pf) * 100
            gain_lbl, d_col = f"{g:+.1f} %", "normal" if g > 0 else "inverse"
        k3.metric("Gain Puissance", gain_lbl, delta_color=d_col)
        k4.metric("Prix Marché", f"{prix_instant:.1f} €/MWh")

        st.markdown("---")
        st.subheader(f"Dynamique du {DATE_SIMU}")
        heures = np.linspace(6, 20, 100)
        yf, yb = [], []
        ef, eb = 0, 0
        dt = (heures[1] - heures[0])
        for h in heures:
            t = to_utc(DATE_SIMU, h)
            hs, azs = position_soleil(LAT, LON, t)
            if hs > 0:
                vf, _, _, _ = calcul_physique_complet(hs, azs, FIXE_ANGLE, ESPACEMENT)
                ab = angle_backtracking(hs, azs, ESPACEMENT, PANNEAU_HAUTEUR, AZIMUT_SUD)
                vb, _, _, _ = calcul_physique_complet(hs, azs, ab, ESPACEMENT)
                yf.append(vf * NB_PANNEAUX / 1000)
                yb.append(vb * NB_PANNEAUX / 1000)
                ef += vf * dt
                eb += vb * dt
            else:
                yf.append(0)
                yb.append(0)

        fig, ax = plt.subplots(figsize=(10, 3))
        fig.patch.set_alpha(0)
        ax.set_facecolor((0, 0, 0, 0))
        ax.plot(heures, yf, label=f"Fixe (Total Parc)", color="#3498db", linewidth=2)
        ax.plot(heures, yb, label="Tracker (Total Parc)", color="#2ecc71", linewidth=2.5)
        ax.fill_between(heures, yb, yf, where=np.array(yb) > np.array(yf), color='#2ecc71', alpha=0.15)

        ax.tick_params(colors='gray')
        ax.xaxis.label.set_color('gray')
        ax.yaxis.label.set_color('gray')
        for spine in ax.spines.values(): spine.set_edgecolor('gray')
        ax.axvline(heure_simu, color="gray", linestyle=":")
        ax.set_ylabel("Puissance (kW)")
        ax.legend(frameon=False, labelcolor='gray')
        ax.grid(True, linestyle='--', alpha=0.2)
        st.pyplot(fig)

        c1, c2, c3 = st.columns(3)
        c1.info(f"Énergie Jour Fixe : **{ef * NB_PANNEAUX / 1000:.0f} kWh**")
        c2.success(f"Énergie Jour Tracker : **{eb * NB_PANNEAUX / 1000:.0f} kWh**")
        c3.metric("Gain Volume", f"{((eb - ef) / ef) * 100:+.1f} %" if ef > 0 else "-")

    else:
        st.info("Nuit.")

with tab_eco:
    st.subheader("Rentabilité Financière (Ferme Solaire)")
    st.markdown(f"Simulation pour un parc de **{NB_PANNEAUX} panneaux** ({PUISSANCE_CRETE_TOTALE:.0f} kWc).")

    if st.button("Lancer Simulation Rentabilité Annuelle"):
        with st.spinner("Simulation financière sur 365 jours..."):
            days = range(0, 365, 2)
            hours = np.linspace(6, 21, 20)
            dt = (hours[1] - hours[0])

            rev_f_cumul, rev_b_cumul = 0, 0
            x_ax, y_f, y_b = [], [], []

            start = datetime.date(2024, 1, 1)

            for d in days:
                curr_d = start + datetime.timedelta(days=d)
                day_f, day_b = 0, 0
                for h in hours:
                    t = to_utc(curr_d, h)
                    hs, azs = position_soleil(LAT, LON, t)
                    price = get_market_price(curr_d, h) / 1e6

                    if hs > 0:
                        vf, _, _, _ = calcul_physique_complet(hs, azs, FIXE_ANGLE, ESPACEMENT)
                        ab = angle_backtracking(hs, azs, ESPACEMENT, PANNEAU_HAUTEUR, AZIMUT_SUD)
                        vb, _, _, _ = calcul_physique_complet(hs, azs, ab, ESPACEMENT)

                        day_f += (vf * NB_PANNEAUX) * dt * price
                        day_b += (vb * NB_PANNEAUX) * dt * price

                rev_f_cumul += day_f * 2
                rev_b_cumul += day_b * 2
                x_ax.append(curr_d)
                y_f.append(rev_f_cumul)
                y_b.append(rev_b_cumul)

            gain_euro = rev_b_cumul - rev_f_cumul
            gain_pct = (gain_euro / rev_f_cumul) * 100

            c1, c2, c3 = st.columns(3)
            c1.metric("Chiffre d'Affaires FIXE", f"{rev_f_cumul:,.0f} €".replace(',', ' '))
            c2.metric("Chiffre d'Affaires TRACKER", f"{rev_b_cumul:,.0f} €".replace(',', ' '))
            c3.metric("GAIN FINANCIER NET", f"+{gain_euro:,.0f} €".replace(',', ' '), f"+{gain_pct:.1f} %")

            st.success(f"Sur un an, pour {NB_PANNEAUX} panneaux, le tracking rapporte **{gain_euro:,.0f} €** de plus que le fixe.")

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x_ax, y=y_f, name="Revenus Fixe", line=dict(color="#3498db")))
            fig.add_trace(go.Scatter(x=x_ax, y=y_b, name="Revenus Tracker", line=dict(color="#2ecc71")))
            fig.update_layout(title="Cumul des Revenus (€)", xaxis_title="Date", yaxis_title="Euros", height=400)
            st.plotly_chart(fig, use_container_width=True)

with tab_map:
    st.subheader("Différentiel de Puissance (Tracker - Fixe)")

    st.info(f"""
    **Lecture de la matrice :**
    - Ce graphique montre le **Gain Net** : $P_{{tracker}} - P_{{fixe}}$ (en Watts par panneau).
    - **Rouge Vif** : Le Tracker surclasse le Fixe (souvent quand le Fixe est mal orienté ou ombragé).
    - **Jaune Clair** : Production équivalente (le Fixe est déjà optimal à ce moment-là).
    
    *Référence : Fixe incliné à **{FIXE_ANGLE}°**.*
    """)

    if FIXE_ANGLE > 70:
        st.warning("⚠️ Angle fixe > 70°. Le gain du tracker sera énorme en été (zone rouge) car le fixe vertical capte très peu.")

    if st.button("Générer Matrice"):
        with st.spinner(f"Calcul des gains vs Fixe ({FIXE_ANGLE}°)..."):
            days = range(0, 365, 5)
            # Génération des labels de date pour l'axe X (Jour/Mois)
            start_year = datetime.date(2024, 1, 1)
            date_labels = [(start_year + datetime.timedelta(days=d)).strftime("%d/%m") for d in days]

            hours = range(6, 20)
            z = []

            start = datetime.date(2024, 1, 1)

            for h in hours:
                row = []
                for d in days:
                    t = to_utc(start + datetime.timedelta(days=d), h)
                    hs, azs = position_soleil(LAT, LON, t)

                    if hs > 0:
                        vf, _, _, _ = calcul_physique_complet(hs, azs, FIXE_ANGLE, ESPACEMENT)
                        ab = angle_backtracking(hs, azs, ESPACEMENT, PANNEAU_HAUTEUR, AZIMUT_SUD)
                        vb, _, _, _ = calcul_physique_complet(hs, azs, ab, ESPACEMENT)

                        gain = max(0, vb - vf)
                        row.append(gain)
                    else:
                        row.append(0)
                z.append(row)

            fig = go.Figure(data=go.Heatmap(
                z=z,
                x=date_labels,
                y=list(hours),
                colorscale='YlOrRd',
                colorbar=dict(title="Gain (Watts)")
            ))

            fig.update_layout(
                title=f"Gain Tracker vs Fixe ({FIXE_ANGLE}°)",
                xaxis_title="Date",
                yaxis_title="Heure",
                xaxis=dict(tickmode='auto', nticks=12),
                height=500
            )

            st.plotly_chart(fig, use_container_width=True)

with tab_info:
    st.header("Notations, Modèles et Hypothèses")

    # --- BLOC 1 : NOTATIONS ---
    st.subheader("1. Notations Géométriques")
    st.markdown("Ce schéma définit les angles et longueurs utilisés dans le calcul.")
    st.pyplot(generer_schema_notations())

    col_leg1, col_leg2 = st.columns(2)
    with col_leg1:
        st.markdown(r"""
        **Angles :**
        - $\alpha$ (Alpha) : Hauteur du Soleil (Elevation).
        - $\beta$ (Beta) : Inclinaison du panneau ($0^\circ$ = plat).
        - $\theta_i$ : Angle d'incidence.
        """)
    with col_leg2:
        st.markdown(r"""
        **Dimensions :**
        - $L$ : Longueur du panneau (hypoténuse).
        - $d$ (Pitch) : Espacement inter-rangées.
        """)

    st.markdown("---")

    # --- BLOC 2 : MODELE PHYSIQUE ---
    col_phys, col_limites = st.columns([1.2, 1])

    with col_phys:
        st.subheader("2. Modèle Physique de Production")
        st.info("On utilise un modèle géométrique pur (Loi de Lambert).")
        st.latex(r"""
        P_{out} = P_{crete} \times \eta \times \cos(\theta_i) \times F_{ombre}
        """)
        st.markdown("""
        **Explication des termes :**
        1.  **$P_{crete}$** : Puissance max théorique du panneau (STC).
        2.  **$\cos(\\theta_i)$** : Terme optique. La puissance reçue est proportionnelle à la surface apparente du panneau vue du soleil.
        3.  **$F_{ombre}$** : Facteur binaire (0 ou 1) modélisant l'ombrage.
        """)

    with col_limites:
        st.subheader("3. Hypothèses Simplificatrices (Limites)")
        st.warning("Pour ce TIPE, les phénomènes suivants sont **négligés** :")
        st.markdown(r"""
        - **Rayonnement Diffus :** On suppose que seule la lumière directe du soleil produit de l'énergie ($P_{diffus} = 0$).
        - **Température :** Le rendement $\eta$ est supposé constant (en réalité il chute quand le panneau chauffe).
        - **Géométrie 1 Axe :** On suppose des rangées infinies orientées Est-Ouest (problème 2D).
        - **Prix Spot :** Modélisé comme une variable aléatoire simple (pas de modèle économique complexe).
        """)

    st.markdown("---")

    # --- BLOC 3 : HARD SHADING ---
    st.subheader("4. Modèle d'Ombrage 'Hard Shading'")

    col_hs_txt, col_hs_fig = st.columns([1, 1])

    with col_hs_txt:
        st.markdown("""
        **Pourquoi le Backtracking est-il vital ?**
        
        Les panneaux solaires sont connectés en série (Strings). Si une seule cellule est ombragée, elle bloque le courant de toute la série (effet "tuyau d'arrosage pincé").
        
        Bien que des **diodes by-pass** existent, elles ne sont pas parfaites et provoquent des chutes de tension. Pour simplifier, nous utilisons le modèle du **"Maillon Faible"** :
        """)
        st.error(r"Si l'ombre couvre > 5% du panneau, la production tombe à 0.")

    with col_hs_fig:
        fig_hyp, ax_hyp = plt.subplots(figsize=(5, 2.5))
        x_shade = np.linspace(0, 15, 200)
        y_factor = [1.0 if x <= 5 else 0.0 for x in x_shade]
        ax_hyp.plot(x_shade, y_factor, 'r-', lw=2)
        ax_hyp.fill_between(x_shade, y_factor, color='red', alpha=0.1)
        ax_hyp.set_title("Facteur $F_{ombre}$ (Step Function)")
        ax_hyp.set_xlabel("% Surface Ombragée"); ax_hyp.set_ylabel("Production")
        ax_hyp.axvline(5, color='k', ls='--', label="Seuil critique")
        ax_hyp.legend()
        st.pyplot(fig_hyp)
