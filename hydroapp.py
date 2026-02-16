import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import find_peaks
import io

# --- CONFIGURATION PAGE ---
st.set_page_config(
    page_title="Générateur d'Hydrogrammes", 
    layout="wide", 
    page_icon="🌊",
    initial_sidebar_state="expanded"
)

# --- CSS RÉPARATEUR & DESIGN ---
st.markdown("""
<style>
    /* 1. PALETTE DE COULEURS */
    :root {
        --primary-color: #0277BD;      /* Bleu Pro */
        --bg-color: #FAFAFA;           /* Blanc Cassé */
        --sidebar-bg: #F5F7F9;         /* Gris perle pour la sidebar */
        --text-main: #2C3E50;          /* Gris foncé pour le texte principal */
        --text-sidebar: #1F2937;       /* Noir doux pour la sidebar (LISIBILITÉ MAX) */
    }

    /* 2. STYLE GLOBAL */
    .stApp {
        background-color: var(--bg-color);
        color: var(--text-main);
    }
    
    /* 3. BARRE LATÉRALE - CONTRASTE FORCÉ */
    section[data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
        border-right: 1px solid #E5E7EB;
    }
    
    /* Force la couleur des textes dans la sidebar (labels, headers, markdown) */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] p {
        color: var(--text-sidebar) !important;
    }
    
    /* 4. BOUTON DE MENU (FLÈCHE) */
    button[kind="header"] {
        background-color: transparent !important;
        color: var(--primary-color) !important;
    }
    [data-testid="stSidebarCollapsedControl"] {
        color: var(--primary-color) !important;
        background-color: white !important;
        border: 1px solid #ddd;
    }

    /* 5. TITRES PRINCIPAUX */
    h1 { color: var(--primary-color) !important; }
    
    /* 6. INPUTS & SLIDERS */
    /* Fond blanc pour les inputs pour contraster avec le gris de la sidebar */
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }
    /* Sliders en bleu */
    .stSlider > div > div > div > div { background-color: var(--primary-color); }

    div[data-testid="stToolbar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("🌊 Générateur d'Hydrogrammes")
st.markdown("---")

# --- BARRE LATÉRALE ---

# 1. IMPORTATION
st.sidebar.header("1. Vos Données")
uploaded_file = st.sidebar.file_uploader("Glissez votre fichier CSV ici", type=["csv"])

# 2. APPARENCE
st.sidebar.header("2. Apparence")
title = st.sidebar.text_input("Titre du graphique", "Hydrogramme de Crue")

c1, c2 = st.sidebar.columns(2)
col_sim_pick = c1.color_picker("Simulé", "#0288D1") 
col_obs_pick = c2.color_picker("Observé", "#D32F2F")

# 3. RÉGLAGES AVANCÉS
with st.sidebar.expander("⚙️ Réglages Avancés"):
    st.markdown("**Paramètres des Pics**")
    n_peaks = st.slider("Nombre de pics max", 1, 20, 6)
    peak_sensitivity = st.slider("Sensibilité détection", 1, 200, 10)
    
    st.markdown("**Mise en page**")
    global_x_offset = st.slider("Écartement horizontal", 0, 100, 25)
    label_size = st.slider("Taille du texte", 8, 20, 11)
    show_hours = st.checkbox("Afficher les heures", value=True)
    
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
        
        # Détection auto
        cols = df.columns.tolist()
        default_date = next((c for c in cols if "date" in c.lower()), cols[0])
        default_sim = next((c for c in cols if "sim" in c.lower()), cols[1] if len(cols)>1 else cols[0])
        default_obs = next((c for c in cols if "obs" in c.lower()), cols[2] if len(cols)>2 else cols[0])

        with st.expander("Vérifier les colonnes détectées", expanded=False):
            c1, c2, c3 = st.columns(3)
            date_col = c1.selectbox("Date", cols, index=cols.index(default_date))
            sim_col = c2.selectbox("Simulé", cols, index=cols.index(default_sim))
            obs_col = c3.selectbox("Observé", cols, index=cols.index(default_obs))
        
        df['Datetime'] = pd.to_datetime(df[date_col])
        df = df.sort_values('Datetime')
        
        # DÉTECTION
        sim_indices = get_peak_indices(df[sim_col], n_peaks, prominence=peak_sensitivity)
        obs_indices = get_peak_indices(df[obs_col], n_peaks, prominence=peak_sensitivity)
        
        # AJUSTEMENT MANUEL
        st.sidebar.markdown("---")
        st.sidebar.header("3. Ajustement Manuel")
        st.sidebar.caption("Déplacez les étiquettes si elles se chevauchent.")
        
        manual_offsets = {} 
        expand_manual = len(sim_indices) + len(obs_indices) < 10
        
        with st.sidebar.expander("🔵 Pics Simulé", expanded=expand_manual):
            for idx in sim_indices:
                t_str = df.loc[idx, 'Datetime'].strftime('%d/%m %Hh')
                v = df.loc[idx, sim_col]
                st.markdown(f"**{t_str}** : {v:.0f}")
                c_x, c_y = st.columns(2)
                dx = c_x.number_input(f"↔ X", value=0, key=f"sx_{idx}", step=5)
                dy = c_y.number_input(f"↕ Y", value=0, key=f"sy_{idx}", step=5)
                manual_offsets[f"sim_{idx}"] = (dx, dy)
                st.markdown("---")

        with st.sidebar.expander("🔴 Pics Observé", expanded=expand_manual):
            for idx in obs_indices:
                t_str = df.loc[idx, 'Datetime'].strftime('%d/%m %Hh')
                v = df.loc[idx, obs_col]
                st.markdown(f"**{t_str}** : {v:.0f}")
                c_x, c_y = st.columns(2)
                dx = c_x.number_input(f"↔ X", value=0, key=f"ox_{idx}", step=5)
                dy = c_y.number_input(f"↕ Y", value=0, key=f"oy_{idx}", step=5)
                manual_offsets[f"obs_{idx}"] = (dx, dy)
                st.markdown("---")

        # GÉNÉRATION GRAPHIQUE
        fig, ax = plt.subplots(figsize=(16, 9), facecolor='white')
        
        ax.plot(df['Datetime'], df[sim_col], color=col_sim_pick, lw=2.5, label='Débit Simulé', zorder=2)
        ax.plot(df['Datetime'], df[obs_col], color=col_obs_pick, lw=2.5, ls='--', label='Débit Observé', zorder=2)
        
        def draw_labels(indices, col_name, color, is_sim):
            for idx in indices:
                val = df.loc[idx, col_name]
                time = df.loc[idx, 'Datetime']
                
                base_x = global_x_offset if is_sim else -global_x_offset
                base_y = 40 
                
                k = f"sim_{idx}" if is_sim else f"obs_{idx}"
                mdx, mdy = manual_offsets.get(k, (0,0))
                
                ax.scatter(time, val, color=color, s=180, zorder=5, edgecolors='white', lw=2)
                
                ax.annotate(f"{val:.0f}", xy=(time, val), xytext=(base_x + mdx, base_y + mdy), 
                            textcoords='offset points', ha='center', va='bottom', 
                            fontsize=label_size, fontweight='bold', color=color,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, lw=1.5, alpha=0.95),
                            arrowprops=dict(arrowstyle="-", color=color, lw=1.5), zorder=10)

        draw_labels(sim_indices, sim_col, col_sim_pick, is_sim=True)
        draw_labels(obs_indices, obs_col, col_obs_pick, is_sim=False)
        
        ax.set_title(title, fontsize=20, fontweight='600', pad=20, color='#2C3E50')
        ax.set_ylabel(ylabel, fontsize=12, fontweight='bold', color='#2C3E50')
        ax.set_xlabel(xlabel, fontsize=12, fontweight='bold', color='#2C3E50')
        
        ax.grid(True, alpha=0.2, color='#2C3E50', ls='-')
        ax.legend(fontsize=11, loc='upper right', frameon=True, framealpha=1.0, facecolor='white', edgecolor='#E1E4E8').set_zorder(10)
        
        duration = (df['Datetime'].max() - df['Datetime'].min()).days
        if duration < 5:
            locator = mdates.HourLocator(interval=4 if show_hours else 24)
            fmt = '%d/%m %Hh' if show_hours else '%d/%m'
        else:
            locator = mdates.HourLocator(interval=12) if show_hours else mdates.DayLocator(interval=2)
            fmt = '%d/%m %Hh' if show_hours else '%d/%m'
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        plt.setp(ax.get_xticklabels(), rotation=90, ha='center', fontsize=10)
        
        for spine in ax.spines.values(): spine.set_edgecolor('#BDC3C7')
            
        st.pyplot(fig)
        
        clean_title = title.replace(" ", "_").lower()
        img = io.BytesIO()
        fig.savefig(img, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        st.download_button("💾 Télécharger l'image", data=img, file_name=f"{clean_title}.png", mime="image/png", use_container_width=True)

    except Exception as e:
        st.error(f"Une erreur est survenue : {e}")
        st.info("Vérifiez que votre fichier CSV est correct.")

else:
    st.info("👈 Commencez par glisser votre fichier CSV dans le menu de gauche.")
