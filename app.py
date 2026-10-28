import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from supabase import create_client, Client

# --- CONFIGURACIÓN CON LOGO ---
st.set_page_config(page_title="EuricBank", page_icon="yvaNr.jpg", layout="wide")

# --- CONEXIÓN A SUPABASE ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- LOGO EN EL MENÚ LATERAL ---
st.sidebar.image("yvaNr.jpg", use_container_width=True)

# --- BARRA LATERAL: SELECCIÓN DE PORTAL ---
# --- BARRA LATERAL: SELECCIÓN DE PORTAL ---
tipo_usuario = st.sidebar.radio("Ingresar como:", ["Administrador", "Cliente"])

# ==========================================
# PORTAL DEL CLIENTE (CONSULTA DE DEUDA)
# ==========================================
if tipo_usuario == "Cliente":
    st.header("🔍 Consulta tu Deuda")
    st.write("Ingresa tu número de DNI para ver el estado de tus préstamos.")
    
    dni_buscar = st.text_input("DNI:", key="dni_cliente_buscar")
    
    if st.button("Consultar"):
        if dni_buscar:
            res_cli = supabase.table("clientes").select("*").eq("dni", dni_buscar).execute()
            if len(res_cli.data) == 0:
                st.error("❌ No se encontró ningún cliente con ese DNI.")
            else:
                cliente = res_cli.data[0]
                st.success(f"Bienvenido(a), {cliente['nombres']}")
                
                res_p = supabase.table("prestamos").select("*").eq("cliente_id", cliente['id']).eq("estado", "activo").execute()
                
                if len(res_p.data) == 0:
                    st.info("🎉 ¡Felicidades! No tienes deudas pendientes en este momento.")
                else:
                    for p in res_p.data:
                        st.write("---")
                        if p['frecuencia'] == "Diario Fijo":
                            deuda, dias, _ = calcular_deuda_diaria(p['monto'], p['interes'], p['fecha_inicio'])
                            st.write(f"**Préstamo Diario** (Iniciado: {p['fecha_inicio']})")
                            st.write(f"Capital inicial: S/ {p['monto']:,.2f}")
                            st.write(f"Días transcurridos: {dias}")
                            st.metric("TOTAL A PAGAR HOY", f"S/ {deuda:,.2f}")
                        else:
                            st.write(f"**Préstamo {p['frecuencia']}** (Iniciado: {p['fecha_inicio']})")
                            st.write(f"Monto: S/ {p['monto']:,.2f} | Cuotas: {p['num_cuotas']}")
                            res_c = supabase.table("cuotas").select("*").eq("prestamo_id", p['id']).eq("estado", "pendiente").execute()
                            if len(res_c.data) > 0:
                                df_c = pd.DataFrame(res_c.data)
                                st.write("Cuotas pendientes:")
                                st.dataframe(df_c[['numero', 'monto', 'fecha_vence']], use_container_width=True)
                            else:
                                st.success("Este préstamo ya está pagado.")
        else:
            st.warning("Por favor, ingresa tu DNI.")

# ==========================================
# PORTAL DEL ADMINISTRADOR
# ==========================================
elif tipo_usuario == "Administrador":
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False

    if not st.session_state.admin_logged:
        st.header("🔒 Acceso Administrador")
        pass_admin = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            if pass_admin == "EuricBank2026": 
                st.session_state.admin_logged = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")
        st.stop()

    # --- MENÚ DEL ADMINISTRADOR (¡Asegúrate de que esta línea no se haya borrado!) ---
    menu = st.sidebar.selectbox("Ir a:", ["Clientes", "Nuevo Préstamo", "Cronograma y Pagos", "Cartera Vencida", "Inversionistas"])
# ==========================================
# PORTAL DEL ADMINISTRADOR
# ==========================================
elif tipo_usuario == "Administrador":
    # Contraseña de administrador
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False

    if not st.session_state.admin_logged:
        st.header("🔒 Acceso Administrador")
        pass_admin = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            # CAMBIA "EuricBank2026" por la clave que tú quieras
            if pass_admin == "EuricBank2026": 
                st.session_state.admin_logged = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")
        st.stop() # Detiene la app si no se ha logueado

    # --- MENÚ DEL ADMINISTRADOR ---
    menu = st.sidebar.selectbox("Ir a:", ["Clientes", "Nuevo Préstamo", "Cronograma y Pagos", "Cartera Vencida", "Inversionistas"])
    
    # 1. CLIENTES
       # 1. CLIENTES
    if menu == "Clientes":
        st.header("👥 Clientes")
        
        if "form_key" not in st.session_state:
            st.session_state.form_key = 0

        with st.form(f"nuevo_cliente_{st.session_state.form_key}"):
            col1, col2 = st.columns(2)
            with col1:
                dni = st.text_input("DNI")
                nombres = st.text_input("Nombres")
            with col2:
                telefono = st.text_input("Teléfono")
                direccion = st.text_input("Dirección")
            if st.form_submit_button("Guardar Cliente"):
                try:
                    supabase.table("clientes").insert({"dni": dni, "nombres": nombres, "telefono": telefono, "direccion": direccion}).execute()
                    st.success("✅ Cliente guardado")
                    st.session_state.form_key += 1
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        res = supabase.table("clientes").select("*").execute()
        df_clientes = pd.DataFrame(res.data)
        st.dataframe(df_clientes, use_container_width=True)

        # --- ZONA PARA EDITAR/ELIMINAR CLIENTES ---
        if len(df_clientes) > 0:
            st.write("---")
            with st.expander("⚙️ Editar o Eliminar un Cliente"):
                cliente_sel = st.selectbox("Selecciona el cliente", df_clientes['nombres'])
                row_cli = df_clientes[df_clientes['nombres'] == cliente_sel].iloc[0]
                
                with st.form("editar_cliente_form"):
                    e_dni = st.text_input("DNI", value=row_cli['dni'])
                    e_nombres = st.text_input("Nombres", value=row_cli['nombres'])
                    e_telefono = st.text_input("Teléfono", value=row_cli['telefono'] if row_cli['telefono'] else "")
                    e_direccion = st.text_input("Dirección", value=row_cli['direccion'] if row_cli['direccion'] else "")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Guardar Cambios"):
                            supabase.table("clientes").update({
                                "dni": e_dni, "nombres": e_nombres, "telefono": e_telefono, "direccion": e_direccion
                            }).eq("id", row_cli['id']).execute()
                            st.success("Cliente actualizado")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("🗑️ Eliminar Cliente"):
                            # Al borrar el cliente, se borran sus préstamos por el ON DELETE CASCADE
                            supabase.table("clientes").delete().eq("id", row_cli['id']).execute()
                            st.error("Cliente eliminado.")
                            st.rerun()
    # 2. NUEVO PRÉSTAMO
    elif menu == "Nuevo Préstamo":
        st.header("📝 Nuevo Préstamo")
        res_cli = supabase.table("clientes").select("*").execute()
        clientes = pd.DataFrame(res_cli.data)
        
        if len(clientes) == 0:
            st.warning("⚠️ Registra un cliente primero.")
        else:
            clientes['opcion'] = clientes['nombres'] + " - " + clientes['dni']
            cliente_sel = st.selectbox("Cliente", clientes['opcion'])
            cliente_id = int(clientes[clientes['opcion'] == cliente_sel]['id'].values[0])
            
            fecha_inicio = st.date_input("📅 Fecha", date.today())
            col1, col2 = st.columns(2)
            with col1:
                tipo = st.selectbox("Tipo", ["Diario Fijo", "Simple Mensual", "Francés"])
                monto = st.number_input("Monto (S/)", min_value=10.0, step=100.0)
            with col2:
                if tipo == "Diario Fijo":
                    interes = st.number_input("Interés Diario (S/)", min_value=0.10, value=2.50)
                    num_cuotas = 1
                else:
                    interes = st.number_input("Interés (%)", min_value=0.0)
                    num_cuotas = st.number_input("N° Cuotas", min_value=1)

            if st.button("Generar Préstamo"):
                res_p = supabase.table("prestamos").insert({
                    "cliente_id": cliente_id, "monto": monto, "interes": interes, 
                    "num_cuotas": num_cuotas, "frecuencia": tipo, "fecha_inicio": str(fecha_inicio)
                }).execute()
                prestamo_id = res_p.data[0]['id']
                
                if tipo == "Diario Fijo":
                    supabase.table("cuotas").insert({"prestamo_id": prestamo_id, "numero": 1, "monto": monto, "fecha_vence": str(fecha_inicio)}).execute()
                else:
                    cuotas_calc = calcular_cuotas(monto, tipo, interes, int(num_cuotas), "Mensual")
                    for i in range(1, int(num_cuotas)+1):
                        fv = fecha_inicio + relativedelta(months=i)
                        supabase.table("cuotas").insert({
                            "prestamo_id": prestamo_id, "numero": i, "monto": cuotas_calc[i-1], "fecha_vence": str(fv)
                        }).execute()
                st.success("✅ Préstamo registrado.")

    # 3. CRONOGRAMA Y PAGOS
    elif menu == "Cronograma y Pagos":
        st.header("📅 Estado de Cuentas")
        res_p = supabase.table("prestamos").select("*, clientes(nombres)").eq("estado", "activo").execute()
        prestamos = pd.DataFrame(res_p.data)
        
        if len(prestamos) > 0:
            prestamos['opcion'] = prestamos['clientes'].apply(lambda x: x['nombres']) + " (N° " + prestamos['id'].astype(str) + ")"
            sel = st.selectbox("Seleccionar Préstamo", prestamos['opcion'])
            p_data = prestamos[prestamos['opcion'] == sel].iloc[0]
            id_p = int(p_data['id'])
            
            with st.expander("⚙️ Eliminar Préstamo"):
                if st.button("🗑️ Eliminar este Préstamo"):
                    supabase.table("prestamos").delete().eq("id", id_p).execute()
                    st.success("Eliminado.")
                    st.rerun()
            
            if p_data['frecuencia'] == "Diario Fijo":
                deuda, dias, interes_gen = calcular_deuda_diaria(p_data['monto'], p_data['interes'], p_data['fecha_inicio'])
                col1, col2, col3 = st.columns(3)
                col1.metric("Capital", f"S/ {p_data['monto']:,.2f}")
                col2.metric("Interés", f"S/ {interes_gen:,.2f}")
                col3.metric("TOTAL HOY", f"S/ {deuda:,.2f}")
                
                if st.button("✅ Saldar Deuda Total"):
                    supabase.table("prestamos").update({"estado": "pagado"}).eq("id", id_p).execute()
                    st.success("Saldado.")
                    st.rerun()
            else:
                res_c = supabase.table("cuotas").select("*").eq("prestamo_id", id_p).order("numero").execute()
                for row in res_c.data:
                    col1, col2, col3, col4 = st.columns(4)
                    col1.write(f"**Cuota {row['numero']}**")
                    col2.write(f"S/ {row['monto']}")
                    col3.write(f"Vence: {row['fecha_vence']}")
                    if row['estado'] == 'pagado': col4.success("PAGADO")
                    else:
                        if st.button(f"Cobrar Cuota {row['numero']}", key=f"b_{row['id']}"):
                            supabase.table("cuotas").update({"estado": "pagado"}).eq("id", row['id']).execute()
                            st.rerun()

    # 4. CARTERA VENCIDA
        # 5. INVERSIONISTAS
    elif menu == "Inversionistas":
        st.header("🤝 Inversionistas")
        
        with st.form("nuevo_inv"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nombre")
                dni_i = st.text_input("DNI")
            with col2:
                cap = st.number_input("Capital (S/)", min_value=100.0)
                tasa = st.number_input("Tasa Anual (%)", value=10.0)
            f_aporte = st.date_input("Fecha de Aporte", date.today())
            if st.form_submit_button("Guardar"):
                try:
                    supabase.table("inversionistas").insert({"nombres": nom, "dni": dni_i, "capital": cap, "tasa_anual": tasa, "fecha_aporte": str(f_aporte)}).execute()
                    st.success("✅ Guardado")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        
        res_inv = supabase.table("inversionistas").select("*").eq("estado", "activo").execute()
        df_inv = pd.DataFrame(res_inv.data)

        if len(df_inv) > 0:
            for _, row in df_inv.iterrows():
                hoy = date.today()
                f_ini = datetime.strptime(str(row['fecha_aporte']), '%Y-%m-%d').date()
                dias = (hoy - f_ini).days
                ganancia = row['capital'] * (row['tasa_anual']/100) * (dias/365) if dias > 0 else 0
                
                st.write(f"**{row['nombres']}** | Capital: S/ {row['capital']:,.2f} | Ganancia: S/ {ganancia:,.2f}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Pagar Ganancia", key=f"pay_{row['id']}"):
                        supabase.table("inversionistas").update({"fecha_aporte": str(hoy)}).eq("id", row['id']).execute()
                        st.success("Pagado.")
                        st.rerun()

                # --- ZONA PARA EDITAR/ELIMINAR INVERSIONISTAS ---
                with st.expander("⚙️ Editar / Eliminar"):
                    with st.form(f"edit_inv_{row['id']}"):
                        ei_nom = st.text_input("Nombre", value=row['nombres'])
                        ei_dni = st.text_input("DNI", value=row['dni'])
                        ei_cap = st.number_input("Capital (S/)", value=float(row['capital']))
                        ei_tasa = st.number_input("Tasa (%)", value=float(row['tasa_anual']))
                        
                        cb1, cb2 = st.columns(2)
                        with cb1:
                            if st.form_submit_button("💾 Guardar Cambios"):
                                supabase.table("inversionistas").update({
                                    "nombres": ei_nom, "dni": ei_dni, "capital": ei_cap, "tasa_anual": ei_tasa
                                }).eq("id", row['id']).execute()
                                st.success("Actualizado.")
                                st.rerun()
                        with cb2:
                            if st.form_submit_button("🗑️ Eliminar"):
                                supabase.table("inversionistas").delete().eq("id", row['id']).execute()
                                st.error("Eliminado.")
                                st.rerun()
                st.divider()
