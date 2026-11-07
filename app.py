# --- TRUCO DE DISEÑO: MENÚ ARRIBA, LOGO ABAJO GIGANTE (2200px) ---
st.sidebar.markdown(
    """
    <style>
    /* Hacemos que la barra lateral ocupe el 100% de la pantalla */
    [data-testid="stSidebarUserContent"] {
        display: flex;
        flex-direction: column;
        min-height: 85vh; /* Altura para empujar el logo abajo */
    }
    /* Estilos para el contenedor del logo */
    .logo-bottom {
        margin-top: auto; /* Esto empuja el logo al fondo */
        text-align: center;
        padding-bottom: 10px;
    }
    </style>
    <!-- Tu logo con tamaño GIGANTE (4 veces más grande) -->
    <div class="logo-bottom">
        <img src="yvaNr.jpg" width="2200" style="max-width: 100%; height: auto;" alt="EuricBank">
    </div>
    """,
    unsafe_allow_html=True
)
