import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from supabase import create_client, Client

st.set_page_config(page_title="EuricBank", page_icon="💰", layout="wide")

# --- CONEXIÓN A SUPABASE (EuricBank) ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
from supabase import create_client
import httpx
supabase = create_client(url, key)
# --- FUNCIONES DE CÁLCULO ---
def calcular_deuda_diaria(monto_inicial, interes_diario_soles, fecha_inicio):
    hoy = date.today()
    fecha_ini = datetime.strptime(str(fecha_inicio), '%Y-%m-%d').date()
    dias_transcurridos = (hoy - fecha_ini).days
    if dias_transcurridos < 0: return monto_inicial, 0, 0.0
    interes_generado = interes_diario_soles * dias_transcurridos
    monto_actual = monto_inicial + interes_generado
    return round(monto_actual, 2), dias_transcurridos, round(interes_generado, 2)

def calcular_cuotas(monto, tipo, valor_interes, num_cuotas, frecuencia):
    cuotas = []
    if tipo == "Interés Simple Mensual":
        interes_mensual_soles = monto * (valor_interes / 100)
        capital_por_cuota = monto / num_cuotas
        cuota_total = capital_por_cuota + interes_mensual_soles
        cuotas = [round(cuota_total, 2)] * num_cuotas
    elif tipo == "Sistema Bancario (Francés)":
        tasa_mensual = (valor_interes / 100)
        if tasa_mensual == 0: cuotas = [round(monto / num_cuotas, 2)] * num_cuotas
        else:
            cuota = monto * (tasa_mensual * (1 + tasa_mensual)**num_cuotas) / ((1 + tasa_mensual)**num_cuotas - 1)
            cuotas = [round(cuota, 2)] * num_cuotas
    return cuotas

# --- MENÚ ---
st.sidebar.title("🏦 EuricBank")
menu = st.sidebar.radio("Ir a:", ["Clientes", "Nuevo Préstamo", "Cronograma y Pagos", "Cartera Vencida", "Inversionistas"])

# 1. CLIENTES
if menu == "Clientes":
    st.header("👥 Clientes")
    with st.form("nuevo_cliente"):
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
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # Mostrar clientes
    res = supabase.table("clientes").select("*").execute()
    df_clientes = pd.DataFrame(res.data)
    st.dataframe(df_clientes, use_container_width=True)

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
            # Guardar préstamo
            res_p = supabase.table("prestamos").insert({
                "cliente_id": cliente_id, "monto": monto, "interes": interes, 
                "num_cuotas": num_cuotas, "frecuencia": tipo, "fecha_inicio": str(fecha_inicio)
            }).execute()
            prestamo_id = res_p.data[0]['id']
            
            # Generar Cuotas
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
elif menu == "Cartera Vencida":
    st.header("🚨 Cobros en Calle")
    res_p = supabase.table("prestamos").select("*, clientes(nombres, telefono)").eq("estado", "activo").eq("frecuencia", "Diario Fijo").execute()
    activos = pd.DataFrame(res_p.data)
    
    if len(activos) == 0: st.info("No hay préstamos diarios.")
    else:
        total = 0
        for _, row in activos.iterrows():
            deuda, dias, _ = calcular_deuda_diaria(row['monto'], row['interes'], row['fecha_inicio'])
            if dias >= 0:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"👤 **{row['clientes']['nombres']}** | Tel: {row['clientes']['telefono']} | Días: {dias} | **Cobrar: S/ {deuda:,.2f}**")
                with col2:
                    if st.button("🗑️", key=f"del_{row['id']}"):
                        supabase.table("prestamos").delete().eq("id", row['id']).execute()
                        st.rerun()
                total += deuda
        st.metric("TOTAL A COBRAR", f"S/ {total:,.2f}")

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
            except Exception as e:
                st.error(f"Error: {e}")
    
    res_inv = supabase.table("inversionistas").select("*").eq("estado", "activo").execute()
    for row in res_inv.data:
        hoy = date.today()
        f_ini = datetime.strptime(str(row['fecha_aporte']), '%Y-%m-%d').date()
        dias = (hoy - f_ini).days
        ganancia = row['capital'] * (row['tasa_anual']/100) * (dias/365) if dias > 0 else 0
        
        st.write(f"**{row['nombres']}** | Capital: S/ {row['capital']:,.2f} | Ganancia: S/ {ganancia:,.2f}")
        if st.button("Pagar Ganancia", key=f"pay_{row['id']}"):
            supabase.table("inversionistas").update({"fecha_aporte": str(hoy)}).eq("id", row['id']).execute()
            st.success("Pagado.")
            st.rerun()
