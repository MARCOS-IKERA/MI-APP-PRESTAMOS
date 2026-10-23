import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import io

st.set_page_config(page_title="Sistema de Préstamos", page_icon="💰", layout="wide")

conn = sqlite3.connect('prestamos.db', check_same_thread=False)
c = conn.cursor()

# --- CREACIÓN DE TABLAS ---
c.execute('''CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, dni TEXT UNIQUE, nombres TEXT, telefono TEXT, direccion TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS prestamos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, monto REAL, interes REAL, num_cuotas INTEGER, frecuencia TEXT, fecha_inicio TEXT, estado TEXT DEFAULT 'activo')''')
c.execute('''CREATE TABLE IF NOT EXISTS cuotas (id INTEGER PRIMARY KEY AUTOINCREMENT, prestamo_id INTEGER, numero INTEGER, monto REAL, fecha_vence TEXT, estado TEXT DEFAULT 'pendiente')''')
c.execute('''CREATE TABLE IF NOT EXISTS pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, cuota_id INTEGER, monto REAL, fecha_pago TEXT, metodo TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS inversionistas (id INTEGER PRIMARY KEY AUTOINCREMENT, nombres TEXT, dni TEXT UNIQUE, capital REAL, tasa_anual REAL, fecha_aporte TEXT, estado TEXT DEFAULT 'activo')''')
c.execute('''CREATE TABLE IF NOT EXISTS pagos_inversionistas (id INTEGER PRIMARY KEY AUTOINCREMENT, inversionista_id INTEGER, monto_pagado REAL, fecha_pago TEXT)''')
conn.commit()

# --- FÓRMULAS MATEMÁTICAS ---
def calcular_deuda_diaria(monto_inicial, interes_diario_soles, fecha_inicio):
    hoy = date.today()
    fecha_ini = datetime.strptime(str(fecha_inicio), '%Y-%m-%d').date()
    dias_transcurridos = (hoy - fecha_ini).days
    
    if dias_transcurridos < 0:
        return monto_inicial, 0, 0.0
        
    # FÓRMULA EXACTA: Monto + (Interés en Soles * Días)
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
        if tasa_mensual == 0:
            cuotas = [round(monto / num_cuotas, 2)] * num_cuotas
        else:
            cuota = monto * (tasa_mensual * (1 + tasa_mensual)**num_cuotas) / ((1 + tasa_mensual)**num_cuotas - 1)
            cuotas = [round(cuota, 2)] * num_cuotas
    return cuotas

def calcular_ganancia_inversionista(capital, tasa_anual, fecha_aporte):
    hoy = date.today()
    fecha_ini = datetime.strptime(str(fecha_aporte), '%Y-%m-%d').date()
    dias_transcurridos = (hoy - fecha_ini).days
    if dias_transcurridos <= 0:
        return 0.0, 0
    ganancia = capital * (tasa_anual / 100) * (dias_transcurridos / 365)
    return round(ganancia, 2), dias_transcurridos

# --- MENÚ LATERAL ---
st.sidebar.title("Menú Principal")
menu = st.sidebar.radio("Ir a:", ["Clientes", "Nuevo Préstamo", "Cronograma y Pagos", "Cartera Vencida", "Inversionistas"])

# 1. CLIENTES
if menu == "Clientes":
    st.header("👥 Registro de Clientes")
    with st.form("nuevo_cliente"):
        col1, col2 = st.columns(2)
        with col1:
            dni = st.text_input("DNI")
            nombres = st.text_input("Nombres Completos")
        with col2:
            telefono = st.text_input("Teléfono")
            direccion = st.text_input("Dirección")
        if st.form_submit_button("Guardar Cliente"):
            try:
                c.execute("INSERT INTO clientes (dni, nombres, telefono, direccion) VALUES (?,?,?,?)", (dni, nombres, telefono, direccion))
                conn.commit()
                st.success("✅ Cliente guardado")
                st.rerun()
            except:
                st.error("❌ Error: El DNI ya existe")
                
    df_clientes = pd.read_sql("SELECT * FROM clientes", conn)
    st.dataframe(df_clientes, use_container_width=True)
    
    if len(df_clientes) > 0:
        st.write("---")
        with st.expander("⚙️ Editar o Eliminar Cliente"):
            cliente_sel = st.selectbox("Selecciona el cliente", df_clientes['nombres'])
            row = df_clientes[df_clientes['nombres'] == cliente_sel].iloc[0]
            
            with st.form("editar_borrar_cliente"):
                e_dni = st.text_input("DNI", value=row['dni'])
                e_nombres = st.text_input("Nombres", value=row['nombres'])
                e_telefono = st.text_input("Teléfono", value=row['telefono'])
                e_direccion = st.text_input("Dirección", value=row['direccion'])
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar Cambios"):
                        c.execute("UPDATE clientes SET dni=?, nombres=?, telefono=?, direccion=? WHERE id=?", 
                                  (e_dni, e_nombres, e_telefono, e_direccion, row['id']))
                        conn.commit()
                        st.success("Cliente actualizado")
                        st.rerun()
                with col2:
                    if st.form_submit_button("🗑️ Eliminar Cliente"):
                        c.execute(f"DELETE FROM pagos WHERE cuota_id IN (SELECT id FROM cuotas WHERE prestamo_id IN (SELECT id FROM prestamos WHERE cliente_id = {row['id']}))")
                        c.execute(f"DELETE FROM cuotas WHERE prestamo_id IN (SELECT id FROM prestamos WHERE cliente_id = {row['id']})")
                        c.execute(f"DELETE FROM prestamos WHERE cliente_id = {row['id']}")
                        c.execute(f"DELETE FROM clientes WHERE id = {row['id']}")
                        conn.commit()
                        st.error("Cliente y sus préstamos eliminados.")
                        st.rerun()

# 2. NUEVO PRÉSTAMO
elif menu == "Nuevo Préstamo":
    st.header("📝 Registrar Préstamo")
    clientes = pd.read_sql("SELECT id, nombres, dni FROM clientes", conn)
    if len(clientes) == 0:
        st.warning("⚠️ Primero registra un cliente.")
    else:
        clientes['opcion'] = clientes['nombres'] + " - " + clientes['dni']
        cliente_sel = st.selectbox("Seleccionar Cliente", clientes['opcion'])
        cliente_id = int(clientes[clientes['opcion'] == cliente_sel]['id'].values[0])
        
        fecha_inicio = st.date_input("📅 Fecha de Préstamo", date.today())
        
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo de Préstamo", ["Diario Compuesto (Se multiplica cada día)", "Interés Simple Mensual", "Sistema Bancario (Francés)"])
            monto = st.number_input("Monto Prestado (S/)", min_value=10.0, step=100.0)
        with col2:
            if tipo == "Diario Compuesto (Se multiplica cada día)":
                interes = st.number_input("Interés Diario FIJO en Soles", min_value=0.10, step=0.10, value=2.50, help="Ejemplo: Si cobras 2.50 soles diarios, escribe 2.50")
                num_cuotas = 1
            else:
                interes = st.number_input("Interés Mensual (%)", min_value=0.0, step=1.0)
                num_cuotas = st.number_input("Número de Cuotas", min_value=1, step=1)

        if st.button("Generar Préstamo"):
            c.execute("INSERT INTO prestamos (cliente_id, monto, interes, num_cuotas, frecuencia, fecha_inicio) VALUES (?,?,?,?,?,?)", 
                      (cliente_id, monto, interes, num_cuotas, tipo, str(fecha_inicio)))
            prestamo_id = c.lastrowid
            
            if tipo == "Diario Compuesto (Se multiplica cada día)":
                c.execute("INSERT INTO cuotas (prestamo_id, numero, monto, fecha_vence) VALUES (?,?,?,?)", 
                          (prestamo_id, 1, monto, str(fecha_inicio)))
            else:
                cuotas_calculadas = calcular_cuotas(monto, tipo, interes, int(num_cuotas), "Mensual")
                for i in range(1, int(num_cuotas)+1):
                    fv = fecha_inicio + relativedelta(months=i)
                    c.execute("INSERT INTO cuotas (prestamo_id, numero, monto, fecha_vence) VALUES (?,?,?,?)", 
                              (prestamo_id, i, cuotas_calculadas[i-1], str(fv)))
            conn.commit()
            st.success("✅ Préstamo registrado.")

# 3. CRONOGRAMA Y PAGOS
elif menu == "Cronograma y Pagos":
    st.header("📅 Estado de Cuentas")
    prestamos = pd.read_sql("SELECT p.id, cl.nombres, p.fecha_inicio, p.monto, p.interes, p.frecuencia FROM prestamos p JOIN clientes cl ON p.cliente_id = cl.id WHERE p.estado = 'activo'", conn)
    
    if len(prestamos) > 0:
        prestamos['opcion'] = prestamos['nombres'] + " (N° " + prestamos['id'].astype(str) + ")"
        sel = st.selectbox("Seleccionar Préstamo", prestamos['opcion'])
        p_data = prestamos[prestamos['opcion'] == sel].iloc[0]
        id_p = int(p_data['id'])
        
        # --- BOTÓN PARA ELIMINAR EL PRÉSTAMO ---
        with st.expander("⚙️ Opciones del Préstamo (Eliminar)"):
            st.warning(f"¿Estás seguro de que deseas eliminar el préstamo de {p_data['nombres']}?")
            if st.button("🗑️ Eliminar este Préstamo Definitivamente"):
                c.execute(f"DELETE FROM pagos WHERE cuota_id IN (SELECT id FROM cuotas WHERE prestamo_id = {id_p})")
                c.execute(f"DELETE FROM cuotas WHERE prestamo_id = {id_p}")
                c.execute(f"DELETE FROM prestamos WHERE id = {id_p}")
                conn.commit()
                st.success("✅ Préstamo eliminado correctamente.")
                st.rerun()
        st.write("---")

        # --- LÓGICA DE CÁLCULO (DIARIO O MENSUAL) ---
        if "Diario" in p_data['frecuencia']:
            deuda, dias, interes_gen = calcular_deuda_diaria(p_data['monto'], p_data['interes'], p_data['fecha_inicio'])
            st.info(f"📅 Inicio: {p_data['fecha_inicio']} | Días transcurridos: {dias}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Capital", f"S/ {p_data['monto']:,.2f}")
            col2.metric("Interés Generado", f"S/ {interes_gen:,.2f}")
            col3.metric("TOTAL HOY", f"S/ {deuda:,.2f}")
            
            if st.button("✅ Cobrar y Saldar Deuda Total"):
                c.execute("UPDATE cuotas SET estado = 'pagado' WHERE prestamo_id = ?", (id_p,))
                c.execute("UPDATE prestamos SET estado = 'pagado' WHERE id = ?", (id_p,))
                conn.commit()
                st.success("Préstamo saldado.")
                st.rerun()
        else:
            cuotas = pd.read_sql(f"SELECT * FROM cuotas WHERE prestamo_id = {id_p} ORDER BY numero", conn)
            for _, row in cuotas.iterrows():
                col1, col2, col3, col4 = st.columns(4)
                col1.write(f"**Cuota {row['numero']}**")
                col2.write(f"S/ {row['monto']}")
                col3.write(f"Vence: {row['fecha_vence']}")
                if row['estado'] == 'pagado':
                    col4.success("PAGADO")
                else:
                    if st.button(f"Cobrar Cuota {row['numero']}", key=f"b_{row['id']}"):
                        c.execute("UPDATE cuotas SET estado = 'pagado' WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.rerun()
    else:
        st.info("No hay préstamos activos en este momento.")

# 4. CARTERA VENCIDA
elif menu == "Cartera Vencida":
    st.header("🚨 Cobros en Calle (Hoy)")
    activos = pd.read_sql("SELECT p.id, cl.nombres, cl.telefono, p.fecha_inicio, p.monto, p.interes, p.frecuencia FROM prestamos p JOIN clientes cl ON p.cliente_id = cl.id WHERE p.estado = 'activo' AND p.frecuencia LIKE '%Diario%'", conn)
    
    if len(activos) == 0:
        st.info("No hay préstamos diarios activos para cobrar.")
    else:
        total = 0
        for _, row in activos.iterrows():
            deuda, dias, _ = calcular_deuda_diaria(row['monto'], row['interes'], row['fecha_inicio'])
            if dias >= 0:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"👤 **{row['nombres']}** | Tel: {row['telefono']} | Días: {dias} | **Cobrar: S/ {deuda:,.2f}**")
                with col2:
                    # Botón para eliminar directamente desde aquí
                    if st.button(f"🗑️ Eliminar", key=f"del_calle_{row['id']}"):
                        c.execute(f"DELETE FROM pagos WHERE cuota_id IN (SELECT id FROM cuotas WHERE prestamo_id = {row['id']})")
                        c.execute(f"DELETE FROM cuotas WHERE prestamo_id = {row['id']}")
                        c.execute(f"DELETE FROM prestamos WHERE id = {row['id']}")
                        conn.commit()
                        st.success(f"Préstamo de {row['nombres']} eliminado.")
                        st.rerun()
                total += deuda
        
        st.write("---")
        st.metric("TOTAL A COBRAR EN CALLE", f"S/ {total:,.2f}")

# 5. INVERSIONISTAS
elif menu == "Inversionistas":
    st.header("🤝 Gestión de Inversionistas")
    
    with st.expander("➕ Registrar Nuevo Inversionista"):
        with st.form("nuevo_inversionista"):
            col1, col2 = st.columns(2)
            with col1:
                nombres_inv = st.text_input("Nombre del Inversionista")
                dni_inv = st.text_input("DNI")
            with col2:
                capital_inv = st.number_input("Capital Aportado (S/)", min_value=100.0, step=500.0)
                tasa_inv = st.number_input("Tasa Anual Pactada (%)", min_value=1.0, value=10.0, step=1.0)
            fecha_aporte = st.date_input("Fecha de Aporte", date.today())
            
            if st.form_submit_button("Guardar Inversionista"):
                try:
                    c.execute("INSERT INTO inversionistas (nombres, dni, capital, tasa_anual, fecha_aporte) VALUES (?,?,?,?,?)", 
                              (nombres_inv, dni_inv, capital_inv, tasa_inv, str(fecha_aporte)))
                    conn.commit()
                    st.success("✅ Inversionista registrado")
                    st.rerun()
                except:
                    st.error("❌ Error: El DNI ya está registrado")

    st.subheader("📊 Estado de Cuentas")
    inversionistas = pd.read_sql("SELECT * FROM inversionistas WHERE estado = 'activo'", conn)
    
    if len(inversionistas) > 0:
        for _, row in inversionistas.iterrows():
            ganancia, dias = calcular_ganancia_inversionista(row['capital'], row['tasa_anual'], row['fecha_aporte'])
            
            st.write(f"**{row['nombres']}** (DNI: {row['dni']})")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Capital Aportado", f"S/ {row['capital']:,.2f}")
            col2.metric("Tasa Anual", f"{row['tasa_anual']}%")
            col3.metric("Ganancia Acumulada", f"S/ {ganancia:,.2f}", help=f"Calculado por {dias} días")
            
            with col4:
                if st.button(f"Pagar Ganancia", key=f"pagar_{row['id']}"):
                    c.execute("INSERT INTO pagos_inversionistas (inversionista_id, monto_pagado, fecha_pago) VALUES (?,?,?)", 
                              (row['id'], ganancia, str(date.today())))
                    c.execute("UPDATE inversionistas SET fecha_aporte = ? WHERE id = ?", (str(date.today()), row['id']))
                    conn.commit()
                    st.success(f"✅ Pago registrado a {row['nombres']}")
                    st.rerun()

            with st.expander("⚙️ Editar / Eliminar Inversionista"):
                with st.form(f"editar_inv_{row['id']}"):
                    e_nombres = st.text_input("Nombre", value=row['nombres'])
                    e_dni = st.text_input("DNI", value=row['dni'])
                    e_capital = st.number_input("Capital (S/)", value=float(row['capital']))
                    e_tasa = st.number_input("Tasa (%)", value=float(row['tasa_anual']))
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.form_submit_button("💾 Guardar Cambios"):
                            c.execute("UPDATE inversionistas SET nombres=?, dni=?, capital=?, tasa_anual=? WHERE id=?", 
                                      (e_nombres, e_dni, e_capital, e_tasa, row['id']))
                            conn.commit()
                            st.success("Datos actualizados.")
                            st.rerun()
                    with col_b2:
                        if st.form_submit_button("🗑️ Eliminar"):
                            c.execute("DELETE FROM pagos_inversionistas WHERE inversionista_id=?", (row['id'],))
                            c.execute("DELETE FROM inversionistas WHERE id=?", (row['id'],))
                            conn.commit()
                            st.error("Inversionista eliminado.")
                            st.rerun()
            st.divider()
    else:
        st.info("Aún no hay inversionistas registrados.")