from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from datetime import datetime

# Load env variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey_change_in_production'

# Supabase Setup
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("WARNING: Supabase credentials not found in .env")

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    print(f"Error initializing Supabase: {e}")
    supabase = None

# --- Helpers ---
def get_kpis(licenses):
    return {
        'total': len(licenses),
        'active': sum(1 for l in licenses if l.get('status') == 'active'),
        'pending': sum(1 for l in licenses if l.get('status') == 'pending'),
        'expired': sum(1 for l in licenses if l.get('status') == 'expired'),
        'blocked': sum(1 for l in licenses if l.get('status') == 'blocked')
    }

# --- Routes ---

@app.route('/')
def dashboard():
    if not supabase:
        flash("Error de conexión con base de datos", "error")
        return render_template('dashboard.html', licenses=[], kpis={}, current_filters={})

    # Get filters
    status_filter = request.args.get('status', 'all')
    type_filter = request.args.get('type', 'all')
    search_query = request.args.get('q', '').lower()

    # Fetch all licenses (RLS allows select)
    try:
        response = supabase.table('licenses').select('*').order('created_at', desc=True).execute()
        all_licenses = response.data
    except Exception as e:
        flash(f"Error cargando licencias: {str(e)}", "error")
        all_licenses = []

    # Calculate KPIs BEFORE filtering for global stats
    kpis = get_kpis(all_licenses)

    # Apply Filters in Python (simpler for this scale than complex DB queries)
    filtered_licenses = all_licenses

    if status_filter != 'all':
        filtered_licenses = [l for l in filtered_licenses if l.get('status') == status_filter]
    
    if type_filter != 'all':
        filtered_licenses = [l for l in filtered_licenses if l.get('license_type') == type_filter]

    if search_query:
        filtered_licenses = [
            l for l in filtered_licenses 
            if search_query in l.get('license_code', '').lower() or 
               search_query in l.get('client_name', '').lower()
        ]

    return render_template(
        'dashboard.html',
        licenses=filtered_licenses,
        kpis=kpis,
        current_filters={'status': status_filter, 'type': type_filter, 'q': search_query}
    )

@app.route('/licenses/create', methods=['POST'])
def create_license():
    data = {
        'p_license_type': request.form.get('type'),
        'p_client_name': request.form.get('client_name'),
        'p_client_phone': request.form.get('client_phone'),
        'p_days_valid': int(request.form.get('days')),
        'p_extra_notes': request.form.get('notes')
    }
    
    try:
        # Call RPC
        response = supabase.rpc('generate_license_typed', data).execute()
        # response.data is directly the JSON returned by function
        result = response.data
        
        # Check custom success flag from our SQL function
        if result and result.get('success'):
            flash(f"Licencia creada: {result.get('license_code')}", "success")
        else:
            flash("Error al crear licencia", "error")
            
    except Exception as e:
        flash(f"Error del servidor: {str(e)}", "error")

    return redirect(url_for('dashboard'))

@app.route('/licenses/<id>/update', methods=['POST'])
def update_license(id):
    update_data = {
        'client_name': request.form.get('client_name'),
        'client_phone': request.form.get('client_phone'),
        'notes': request.form.get('notes'),
        'max_devices': int(request.form.get('max_devices'))
    }
    
    try:
        supabase.table('licenses').update(update_data).eq('id', id).execute()
        flash("Licencia actualizada correctamente", "success")
    except Exception as e:
        flash(f"Error actualizando: {str(e)}", "error")

    return redirect(url_for('dashboard'))

@app.route('/licenses/<id>/reactivate', methods=['POST'])
def reactivate_license(id):
    days_to_add = int(request.form.get('days', 30))
    
    try:
        response = supabase.rpc('reactivate_license', {'p_license_id': id, 'p_days_to_add': days_to_add}).execute()
        result = response.data
        
        if result and result.get('success'):
             # Formating date for display could be nice but raw string is okay for flash
            flash(f"Licencia reactivada correctamente. Vence: {result.get('new_end_date')}", "success")
        else:
            flash(f"Error al reactivar: {result.get('message')}", "error")
            
    except Exception as e:
        flash(f"Error reactivando: {str(e)}", "error")

    return redirect(url_for('dashboard'))

@app.route('/licenses/<id>/extend', methods=['POST'])
def extend_license(id):
    days_to_add = int(request.form.get('days', 30))
    
    try:
        response = supabase.rpc('extend_license', {'p_license_id': id, 'p_days_to_add': days_to_add}).execute()
        result = response.data
        
        if result and result.get('success'):
            flash(f"Licencia extendida correctamente. Vence: {result.get('new_end_date')}", "success")
        else:
            flash(f"Error al extender: {result.get('message')}", "error")

    except Exception as e:
        flash(f"Error extendiendo: {str(e)}", "error")

    return redirect(url_for('dashboard'))

@app.route('/licenses/<id>/toggle-block', methods=['POST'])
def toggle_block(id):
    try:
        current = supabase.table('licenses').select('status').eq('id', id).single().execute()
        if current.data:
            new_status = 'active' if current.data['status'] == 'blocked' else 'blocked'
            supabase.table('licenses').update({'status': new_status}).eq('id', id).execute()
            flash(f"Estado cambiado a {new_status}", "success")
    except Exception as e:
        flash(f"Error cambiando estado: {str(e)}", "error")
        
    return redirect(url_for('dashboard'))

@app.route('/licenses/<id>/remove-device', methods=['POST'])
def remove_device(id):
    # This comes as JSON fetch
    data = request.get_json()
    device_id = data.get('device_id')
    
    try:
        # Fetch current array
        curr = supabase.table('licenses').select('device_ids').eq('id', id).single().execute()
        devices = curr.data.get('device_ids', [])
        
        if device_id in devices:
            devices.remove(device_id)
            supabase.table('licenses').update({'device_ids': devices}).eq('id', id).execute()
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'message': 'Device not found'}), 404
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/licenses/<id>/delete', methods=['POST'])
def delete_license(id):
    try:
        supabase.table('licenses').delete().eq('id', id).execute()
        flash("Licencia eliminada", "success")
    except Exception as e:
        flash(f"Error eliminando: {str(e)}", "error")

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
