import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import find_peaks
import io

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="Générateur d'Hydrogrammes", layout="wide", page_icon="🌊")

# Force le thème clair
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #000000; }
    .css-1d391kg, .css-12oz5g7 { background-color: #F0F2F6; }
    h1, h2, h3 { color: #005AB5 !important; }
    div[data-testid="stToolbar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("🌊 Générateur d'Hydrogrammes Facile")
st.markdown("Chargez vos données, personnalisez les couleurs et ajustez les étiquettes si besoin.")

# --- BARRE LATÉRALE ---

# 1. IMPORTATION
st.sidebar.header("1. Vos Données")
uploaded_file = st.sidebar.file_uploader("Glissez votre fichier CSV ici", type=["csv"])

# 2. APPARENCE SIMPLE
st.sidebar.header("2. Apparence")
title = st.sidebar.text_input("Titre du graphique", "Hydrogramme de Crue")
c1, c2 = st.sidebar.columns(2)
col_sim_pick = c1.color_picker("Simulé", "#005AB5")
col_obs_pick = c2.color_picker("Observé", "#DC3220")

# 3. RÉGLAGES AVANCÉS (Cachés par défaut)
with st.sidebar.expander("⚙️ Réglages Avancés (Pics & Axes)"):
    st.markdown("**Paramètres des Pics**")
    n_peaks = st.slider("Nombre de pics max", 1, 20, 6)
    peak_sensitivity = st.slider("Sensibilité détection", 1, 200, 10)
    
    st.markdown("**Mise en page**")
    global_x_offset = st.slider("Écartement horizontal global", 0, 100, 25)
    label_size = st.slider("Taille du texte", 8, 20, 11)
    show_hours = st.checkbox("Afficher les heures (Axe X)", value=True)
    
    st.markdown("**Titres des Axes**")
    ylabel = st.text_input("Titre Axe Y", "Débit (m³/s)")
    xlabel = st.text_input("Titre Axe X", "Date et Heure")

# --- FONCTIONS ---
def get_peak_indices(series, n, prominence=10, distance=5):
    series = series.fillna(0)
    peaks, _ = find_peaks(series, prominence=prominence, distance=distance)
    if len(peaks) == 0: return [series.idxmax()]
    peak_df = pd.DataFrame({'index': series.index[peaks], 'val': series.iloc[peaks].values})
    return sorted(peak_df.sort_values(by='val', ascending=False).head(n)['index'].tolist())

# --- LOGIQUE PRINCIPALE ---
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Détection intelligente des colonnes
        cols = df.columns.tolist()
        # On essaie de trouver "date", "sim", "obs" automatiquement
        default_date = next((c for c in cols if "date" in c.lower()), cols[0])
        default_sim = next((c for c in cols if "sim" in c.lower()), cols[1] if len(cols)>1 else cols[0])
        default_obs = next((c for c in cols if "obs" in c.lower()), cols[2] if len(cols)>2 else cols[0])

        # Sélecteurs discrets
        with st.expander("Vérifier les colonnes détectées", expanded=False):
            c1, c2, c3 = st.columns(3)
            date_col = c1.selectbox("Date", cols, index=cols.index(default_date))
            sim_col = c2.selectbox("Simulé", cols, index=cols.index(default_sim))
            obs_col = c3.selectbox("Observé", cols, index=cols.index(default_obs))
        
        # Conversion
        df['Datetime'] = pd.to_datetime(df[date_col])
        df = df.sort_values('Datetime')
        
        # --- DÉTECTION ---
        sim_indices = get_peak_indices(df[sim_col], n_peaks, prominence=peak_sensitivity)
        obs_indices = get_peak_indices(df[obs_col], n_peaks, prominence=peak_sensitivity)
        
        # --- AJUSTEMENT MANUEL ---
        st.sidebar.markdown("---")
        st.sidebar.header("3. Ajustement Manuel")
        st.sidebar.info("Déplacez les étiquettes qui se chevauchent.")
        
        manual_offsets = {} 

        # On utilise des expanders ouverts par défaut uniquement s'il y a peu de pics, sinon fermés
        expand_manual = len(sim_indices) + len(obs_indices) < 10
        
        with st.sidebar.expander("🔵 Position Pics Simulé", expanded=expand_manual):
            for idx in sim_indices:
                t_str = df.loc[idx, 'Datetime'].strftime('%d/%m %Hh')
                v = df.loc[idx, sim_col]
                st.markdown(f"**{t_str}** : {v:.0f}")
                c_x, c_y = st.columns(2)
                dx = c_x.number_input(f"↔ X", value=0, key=f"sx_{idx}", step=5)
                dy = c_y.number_input(f"↕ Y", value=0, key=f"sy_{idx}", step=5)
                manual_offsets[f"sim_{idx}"] = (dx, dy)
                st.markdown("---")

        with st.sidebar.expander("🔴 Position Pics Observé", expanded=expand_manual):
            for idx in obs_indices:
                t_str = df.loc[idx, 'Datetime'].strftime('%d/%m %Hh')
                v = df.loc[idx, obs_col]
                st.markdown(f"**{t_str}** : {v:.0f}")
                c_x, c_y = st.columns(2)
                dx = c_x.number_input(f"↔ X", value=0, key=f"ox_{idx}", step=5)
                dy = c_y.number_input(f"↕ Y", value=0, key=f"oy_{idx}", step=5)
                manual_offsets[f"obs_{idx}"] = (dx, dy)
                st.markdown("---")

        # --- GÉNÉRATION ---
        fig, ax = plt.subplots(figsize=(16, 9), facecolor='white')
        
        ax.plot(df['Datetime'], df[sim_col], color=col_sim_pick, lw=3, label='Débit Simulé', zorder=2)
        ax.plot(df['Datetime'], df[obs_col], color=col_obs_pick, lw=3, ls='--', label='Débit Observé', zorder=2)
        
        def draw_labels(indices, col_name, color, is_sim):
            for idx in indices:
                val = df.loc[idx, col_name]
                time = df.loc[idx, 'Datetime']
                
                # Position par défaut (Simulé à Droite, Observé à Gauche)
                base_x = global_x_offset if is_sim else -global_x_offset
                base_y = 40 
                
                # Ajout manuel
                k = f"sim_{idx}" if is_sim else f"obs_{idx}"
                mdx, mdy = manual_offsets.get(k, (0,0))
                
                ax.scatter(time, val, color=color, s=200, zorder=5, edgecolors='white', lw=2)
                ax.annotate(f"{val:.0f}", xy=(time, val), xytext=(base_x + mdx, base_y + mdy), 
                            textcoords='offset points', ha='center', va='bottom', 
                            fontsize=label_size, fontweight='bold', color=color,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, lw=2, alpha=1.0),
                            arrowprops=dict(arrowstyle="-", color=color, lw=2), zorder=10)

        draw_labels(sim_indices, sim_col, col_sim_pick, is_sim=True)
        draw_labels(obs_indices, obs_col, col_obs_pick, is_sim=False)
        
        # Style
        ax.set_title(title, fontsize=22, fontweight='bold', pad=25, color='#222')
        ax.set_ylabel(ylabel, fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, color='black', ls=':')
        ax.legend(fontsize=12, loc='upper right', frameon=True, framealpha=1.0, facecolor='white', edgecolor='#ccc').set_zorder(10)
        
        # Axe X
        duration = (df['Datetime'].max() - df['Datetime'].min()).days
        if duration < 5:
            locator = mdates.HourLocator(interval=4 if show_hours else 24)
            fmt = '%d/%m %Hh' if show_hours else '%d/%m'
        else:
            locator = mdates.HourLocator(interval=12) if show_hours else mdates.DayLocator(interval=2)
            fmt = '%d/%m %Hh' if show_hours else '%d/%m'
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        plt.setp(ax.get_xticklabels(), rotation=90, ha='center', fontsize=11)
        for spine in ax.spines.values(): spine.set_edgecolor('#333')
            
        st.pyplot(fig)
        
        # Download
        clean_title = title.replace(" ", "_").lower()
        img = io.BytesIO()
        fig.savefig(img, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        st.download_button("💾 Télécharger l'image", data=img, file_name=f"{clean_title}.png", mime="image/png", use_container_width=True)

    except Exception as e:
        st.error(f"Une erreur est survenue : {e}")
        st.info("Vérifiez que votre fichier CSV contient bien des colonnes Date, Simulé et Observé.")

else:
    # Mode Accueil (Vide)
    st.info("👈 Commencez par glisser votre fichier CSV dans le menu de gauche.")
    st.markdown("### Comment ça marche ?")
    st.markdown("1. Importez votre fichier CSV.")
    st.markdown("2. Les colonnes sont détectées automatiquement.")
    st.markdown("3. Ajustez les pics qui se chevauchent avec le menu 'Ajustement Manuel'.")
    st.markdown("4. Téléchargez votre image.")