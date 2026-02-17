from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import csv
import io
import secrets
import string
from datetime import datetime, timedelta, timezone

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

def generate_unique_code():
    # Format: XXXX-XXXX-XXXX
    def chunk():
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    
    code = f"{chunk()}-{chunk()}-{chunk()}"
    
    # Check uniqueness (simple check, retry loop handled by caller or just ignored for low probability)
    # For robust implementation, we should check DB.
    # Given the collision space (36^12), it's extremely unlikely.
    return code

@app.route('/')
def dashboard():
    if not supabase:
        flash("Error de conexión con base de datos", "error")
        return render_template('dashboard.html', licenses=[], kpis={}, current_filters={})

    # Get params
    status_filter = request.args.get('status', 'all')
    type_filter = request.args.get('type', 'all')
    search_query = request.args.get('q', '').lower()
    
    # Sorting & Pagination
    sort_by = request.args.get('sort', 'created_at')
    sort_dir = request.args.get('dir', 'desc')
    page = int(request.args.get('page', 1))
    per_page = 20
    
    # Base Query
    query = supabase.table('licenses').select('*', count='exact')
    
    # Current UTC time (timezone aware)
    now_utc = datetime.now(timezone.utc)

    # Apply filters
    if status_filter != 'all':
        if status_filter == 'expiring_soon':
            # Special case for "Por Vencer" filter
             query = query.eq('status', 'active').lte('end_date', (now_utc + timedelta(days=7)).isoformat()).gt('end_date', now_utc.isoformat())
        else:
            query = query.eq('status', status_filter)
            
    if type_filter != 'all':
        query = query.eq('license_type', type_filter)
        
    if search_query:
        # Supabase filtering with OR is tricky in py client, raw ilike is better if supported or simple client side
        # For now, let's try strict match or use textSearch if column is indexed
        # Simplified: Filter by code (exact or like)
        query = query.ilike('license_code', f'%{search_query}%')
    
    # Sorting
    if sort_by == 'days_remaining':
        # approximate sorting by end_date for days_remaining
        query = query.order('end_date', desc=(sort_dir == 'desc'))
    else:
        query = query.order(sort_by, desc=(sort_dir == 'desc'))

    # Pagination
    start = (page - 1) * per_page
    end = start + per_page - 1
    query = query.range(start, end)
    
    try:
        response = query.execute()
        filtered_licenses = response.data
        total_count = response.count
        
        # Calculate Global KPIs (separate cheap query or fetch all active for small DB)
        all_status = supabase.table('licenses').select('status, end_date').execute().data
        
        kpis = {
            'total': len(all_status),
            'active': sum(1 for l in all_status if l.get('status') == 'active'),
            'pending': sum(1 for l in all_status if l.get('status') == 'pending'),
            'expired': sum(1 for l in all_status if l.get('status') == 'expired'),
            'blocked': sum(1 for l in all_status if l.get('status') == 'blocked'),
            'expiring_soon': sum(
                1 for l in all_status 
                if l.get('status') == 'active' 
                and l.get('end_date') 
                and now_utc < datetime.fromisoformat(l['end_date'].replace('Z', '+00:00')) <= now_utc + timedelta(days=7)
            )
        }
    except Exception as e:
        flash(f"Error cargando licencias: {str(e)}", "error")
        filtered_licenses = []
        kpis = {}
        total_count = 0

    # Add calculated 'days_remaining' property for UI
    for l in filtered_licenses:
        l['days_remaining'] = None
        if l.get('end_date'):
            try:
                # Handle 'Z' manually if needed, or use replace
                ed = datetime.fromisoformat(l['end_date'].replace('Z', '+00:00'))
                delta = (ed - now_utc).days
                l['days_remaining'] = delta
            except:
                l['days_remaining'] = None

    return render_template(
        'dashboard.html',
        licenses=filtered_licenses,
        kpis=kpis,
        current_filters={'status': status_filter, 'type': type_filter, 'q': search_query, 'sort': sort_by, 'dir': sort_dir},
        pagination={'page': page, 'per_page': per_page, 'total': total_count, 'pages': (total_count // per_page) + 1}
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

@app.route('/licenses/<id>/reset-devices', methods=['POST'])
def reset_devices(id):
    try:
        # Clear device_ids array
        supabase.table('licenses').update({'device_ids': []}).eq('id', id).execute()
        flash("Dispositivos reseteados correctamente", "success")
    except Exception as e:
        flash(f"Error al resetear dispositivos: {str(e)}", "error")
        
    return redirect(url_for('dashboard'))

@app.route('/licenses/<id>/regenerate-code', methods=['POST'])
def regenerate_code(id):
    try:
        new_code = generate_unique_code()
        # Collision check loop (simple)
        max_retries = 3
        for _ in range(max_retries):
            exists = supabase.table('licenses').select('id').eq('license_code', new_code).execute()
            if not exists.data:
                break
            new_code = generate_unique_code()
            
        supabase.table('licenses').update({'license_code': new_code}).eq('id', id).execute()
        flash(f"Código regenerado: {new_code}", "success")
    except Exception as e:
        flash(f"Error al regenerar código: {str(e)}", "error")
        
    return redirect(url_for('dashboard'))

@app.route('/export')
def export_csv():
    if not supabase:
        return "Error DB", 500

    # Get params (same as dashboard)
    status_filter = request.args.get('status', 'all')
    type_filter = request.args.get('type', 'all')
    search_query = request.args.get('q', '').lower()
    
    # Query (fetching all matching records, no pagination)
    query = supabase.table('licenses').select('*')
    
    # Current UTC time (timezone aware)
    now_utc = datetime.now(timezone.utc)

    if status_filter != 'all':
        if status_filter == 'expiring_soon':
             query = query.eq('status', 'active').lte('end_date', (now_utc + timedelta(days=7)).isoformat()).gt('end_date', now_utc.isoformat())
        else:
            query = query.eq('status', status_filter)
            
    if type_filter != 'all':
        query = query.eq('license_type', type_filter)
        
    if search_query:
        query = query.ilike('license_code', f'%{search_query}%')
        
    # No sorting needed for CSV strictly, but nice to have consistent with default
    query = query.order('created_at', desc=True)
    
    try:
        response = query.execute()
        licenses = response.data
    except Exception as e:
        return f"Error exporting: {str(e)}", 500
        
    # Generate CSV
    si = io.StringIO()
    cw = csv.writer(si)
    # Headers
    cw.writerow(['ID', 'Código', 'Tipo', 'Cliente', 'Teléfono', 'Estado', 'Creado', 'Expira', 'Días Restantes', 'Dispositivos', 'Max Dispositivos', 'Notas'])
    
    for l in licenses:
        # Calculate days remaining
        days_rem = ''
        if l.get('end_date'):
            try:
                ed = datetime.fromisoformat(l['end_date'].replace('Z', '+00:00'))
                days_rem = (ed - now_utc).days
            except:
                pass
                
        cw.writerow([
            l.get('id'),
            l.get('license_code'),
            l.get('license_type'),
            l.get('client_name', ''),
            l.get('client_phone', ''),
            l.get('status'),
            l.get('created_at'),
            l.get('end_date', ''),
            days_rem,
            len(l.get('device_ids') or []),
            l.get('max_devices'),
            l.get('notes', '')
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=licencias_export.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == '__main__':
    app.run(debug=True)
