from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = 'empanada-tracker-secret-key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def get_db_connection():
    conn = sqlite3.connect('empanada_tracker.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create the db object BEFORE defining any models
db = SQLAlchemy(app)
# Create the db object BEFORE defining any models

class InventoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(50), nullable=False)  # e.g., 'tapas'
    change_type = db.Column(db.String(20), nullable=False)  # e.g., 'add', 'remove', 'edit'
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200))  # Optional explanation
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    # If user auth exists (e.g., User model), add: user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

def get_wrapped_inventory(conn):
    result = conn.execute('''
        SELECT f.name, MAX(0, COALESCE(SUM(wa.dozens), 0) - COALESCE(SUM(eb.dozens), 0)) as wrapped_unbaked
        FROM flavors f
        LEFT JOIN empanada_wrapped_added wa ON wa.flavor_id = f.id
        LEFT JOIN empanada_baked eb ON eb.flavor_id = f.id
        GROUP BY f.id, f.name
    ''').fetchall()
    return dict((row['name'], row['wrapped_unbaked']) for row in result)

def get_fully_baked_inventory(conn):
    result = conn.execute('''
        SELECT f.name, MAX(0, COALESCE(SUM(eb.dozens), 0) - COALESCE(SUM(mfd.allocated), 0) + COALESCE(SUM(mfd.leftover), 0)) as available
        FROM flavors f
        LEFT JOIN empanada_baked eb ON eb.flavor_id = f.id
        LEFT JOIN market_flavor_data mfd ON mfd.flavor_id = f.id
        GROUP BY f.id, f.name
    ''').fetchall()
    return dict((row['name'], row['available']) for row in result)

@app.route('/')
def dashboard():
    conn = get_db_connection()
    wrapped_inventory = get_wrapped_inventory(conn)
    baked_inventory = get_fully_baked_inventory(conn)
    
    recent_events = conn.execute('''
        SELECT me.id, m.name as market_name, me.event_date, me.cash,
               COALESCE(SUM(mfd.sold), 0) as total_sold, 
               COALESCE(SUM(mfd.leftover), 0) as total_leftover
        FROM market_events me 
        JOIN markets m ON me.market_id = m.id
        LEFT JOIN market_flavor_data mfd ON mfd.market_event_id = me.id
        GROUP BY me.id
        ORDER BY me.event_date DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    return render_template('dashboard.html', 
                         wrapped_inventory=wrapped_inventory, 
                         baked_inventory=baked_inventory,
                         recent_events=recent_events)

@app.route('/inventory')
def inventory():
    conn = get_db_connection()
    wrapped_inventory = get_wrapped_inventory(conn)
    baked_inventory = get_fully_baked_inventory(conn)
    
    # Fetch tapas production totals
    tapas_totals = conn.execute('''
        SELECT COALESCE(SUM(regular_dozens), 0) AS total_regular,
               COALESCE(SUM(ghee_dozens), 0) AS total_ghee,
               COALESCE(SUM(regular_dozens + ghee_dozens), 0) AS grand_total
        FROM tapas_production
    ''').fetchone()
    
    conn.close()
    return render_template('inventory.html', 
                         wrapped_inventory=wrapped_inventory, 
                         baked_inventory=baked_inventory,
                         tapas_totals=tapas_totals)

@app.route('/production', methods=['GET', 'POST'])
def production():
    conn = get_db_connection()
    flavors = conn.execute('SELECT id, name FROM flavors ORDER BY name').fetchall()
    
    if request.method == 'POST':
        action = request.form.get('action')
        date_str = request.form.get('date', date.today().isoformat())
        
        if action == 'tapas':
            try:
                regular = float(request.form.get('regular_dozens', '0'))
                ghee = float(request.form.get('ghee_dozens', '0'))
            except (ValueError, TypeError):
                flash('Please enter valid numeric values for regular and ghee dozens.', 'error')
                conn.close()
                return redirect(url_for('production'))
            notes = request.form.get('notes', '').strip()
            conn.execute('INSERT INTO tapas_production (date, regular_dozens, ghee_dozens, notes) VALUES (?, ?, ?, ?)',
                        (date_str, regular, ghee, notes))
            conn.commit()
            flash(f'Tapas production recorded: {regular} regular, {ghee} ghee dozens')
        
        elif action == 'wrapped':
            flavor_id = int(request.form['flavor_id'])
            dozens = float(request.form['dozens'])
            conn.execute('INSERT INTO empanada_wrapped_added (date, flavor_id, dozens) VALUES (?, ?, ?)',
                        (date_str, flavor_id, dozens))
            conn.commit()
            flash(f'{dozens} dozens of wrapped (unbaked) empanadas added')
        
        elif action == 'bake':
            flavor_id = int(request.form['flavor_id'])
            dozens = float(request.form['dozens'])
            available = conn.execute('''
                SELECT COALESCE(SUM(wa.dozens), 0) - COALESCE(SUM(eb.dozens), 0) as available 
                FROM empanada_wrapped_added wa 
                LEFT JOIN empanada_baked eb ON eb.flavor_id = wa.flavor_id 
                WHERE wa.flavor_id = ?
            ''', (flavor_id,)).fetchone()['available']
            
            if dozens <= available:
                conn.execute('INSERT INTO empanada_baked (date, flavor_id, dozens) VALUES (?, ?, ?)',
                           (date_str, flavor_id, dozens))
                conn.commit()
                flash(f'{dozens} dozens of empanadas successfully baked')
            else:
                flash(f'Error: Only {available} dozens of wrapped empanadas are available to bake for this flavor')
    
    conn.close()
    return render_template('production.html', flavors=flavors)

@app.route('/markets', methods=['GET', 'POST'])
def markets():
    conn = get_db_connection()

    # Load basic lists
    flavors = conn.execute('SELECT id, name FROM flavors ORDER BY name').fetchall()
    markets_list = conn.execute('SELECT id, name FROM markets ORDER BY name').fetchall()

    # === Handle form submissions ===
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_event':
            market_id = request.form['market_id']
            event_date = request.form['event_date']
            conn.execute('INSERT INTO market_events (market_id, event_date) VALUES (?, ?)',
                        (market_id, event_date))
            conn.commit()
            flash('Market event created successfully')

        elif action == 'allocate':
            event_id = int(request.form['event_id'])
            flavor_id = int(request.form['flavor_id'])
            dozens = float(request.form['dozens'])

            # Check available baked inventory
            available = conn.execute('''
                SELECT COALESCE(SUM(eb.dozens), 0) 
                       - COALESCE(SUM(mfd.allocated), 0) 
                       + COALESCE(SUM(mfd.leftover), 0) AS available
                FROM empanada_baked eb
                LEFT JOIN market_flavor_data mfd ON mfd.flavor_id = eb.flavor_id
                WHERE eb.flavor_id = ?
            ''', (flavor_id,)).fetchone()[0]

            if dozens > available:
                flash(f'Only {available:.1f} dozen(s) available to allocate', 'error')
            else:
                conn.execute('''
                    INSERT INTO market_flavor_data (market_event_id, flavor_id, allocated)
                    VALUES (?, ?, ?)
                    ON CONFLICT(market_event_id, flavor_id) DO UPDATE
                    SET allocated = allocated + excluded.allocated
                ''', (event_id, flavor_id, dozens))
                conn.commit()
                flash(f'{dozens:.1f} dozen(s) allocated successfully')
                
        elif action == 'delete_event':
            event_id = int(request.form['event_id'])
            
            # Optional: add a safety check (e.g. only allow if no sales recorded)
            has_sales = conn.execute('''
                SELECT 1 FROM market_flavor_data 
                WHERE market_event_id = ? AND (sold IS NOT NULL OR leftover IS NOT NULL)
                LIMIT 1
            ''', (event_id,)).fetchone()
            
            if has_sales:
                flash('Cannot delete: Sales results have already been recorded for this event.', 'error')
            else:
                # Delete allocations first
                conn.execute('DELETE FROM market_flavor_data WHERE market_event_id = ?', (event_id,))
                # Then delete the event
                conn.execute('DELETE FROM market_events WHERE id = ?', (event_id,))
                conn.commit()
                flash('Market event deleted successfully')
    # === Load market events with total allocated ===
    market_events = conn.execute('''
        SELECT 
            me.id,
            m.name AS market_name,
            me.event_date,
            COALESCE(SUM(mfd.allocated), 0) AS total_allocated
        FROM market_events me
        JOIN markets m ON me.market_id = m.id
        LEFT JOIN market_flavor_data mfd ON mfd.market_event_id = me.id
        GROUP BY me.id, m.name, me.event_date
        ORDER BY me.event_date DESC, me.id DESC
    ''').fetchall()

    # === Load per-flavor allocation details ===
    event_allocations = {}
    details = conn.execute('''
        SELECT 
            me.id AS event_id,
            f.name AS flavor_name,
            mfd.allocated
        FROM market_events me
        LEFT JOIN market_flavor_data mfd ON mfd.market_event_id = me.id
        LEFT JOIN flavors f ON f.id = mfd.flavor_id
        WHERE mfd.allocated IS NOT NULL AND mfd.allocated > 0
        ORDER BY me.event_date DESC, f.name
    ''').fetchall()

    for row in details:
        eid = row['event_id']
        if eid not in event_allocations:
            event_allocations[eid] = []
        event_allocations[eid].append({
            'flavor_name': row['flavor_name'],
            'allocated': row['allocated']
        })

    conn.close()

    return render_template('markets.html',
                           markets=markets_list,
                           market_events=market_events,
                           event_allocations=event_allocations,
                           flavors=flavors,
                           today=date.today().isoformat())


@app.route('/market_results/<int:event_id>', methods=['GET', 'POST'])
def market_results(event_id):
    conn = get_db_connection()
    flavors = conn.execute('SELECT id, name FROM flavors ORDER BY name').fetchall()
    
    if request.method == 'POST':
        flavor_id = int(request.form['flavor_id'])
        brought = float(request.form['brought'])
        sold = float(request.form['sold'])
        leftover = float(request.form['leftover'])
        
        if sold + leftover == brought:
            conn.execute('''
                UPDATE market_flavor_data 
                SET brought = ?, sold = ?, leftover = ? 
                WHERE market_event_id = ? AND flavor_id = ?
            ''', (brought, sold, leftover, event_id, flavor_id))
            if conn.total_changes > 0:
                conn.commit()
                flash(f'Market results recorded successfully')
            else:
                flash('No allocation record found for this flavor in the selected market event')
        else:
            flash('Error: Sold + Leftover must equal Brought')
    
    event = conn.execute('''
        SELECT m.name as market_name, me.event_date, me.cash
        FROM market_events me 
        JOIN markets m ON me.market_id = m.id
        WHERE me.id = ?
    ''', (event_id,)).fetchone()
    
    results = conn.execute('''
        SELECT f.name, mfd.allocated, mfd.brought, mfd.sold, mfd.leftover
        FROM market_flavor_data mfd 
        JOIN flavors f ON f.id = mfd.flavor_id
        WHERE mfd.market_event_id = ?
    ''', (event_id,)).fetchall()
    
    conn.close()
    return render_template('market_results.html', event=event, results=results, flavors=flavors, event_id=event_id)

@app.route('/add_flavor', methods=['GET', 'POST'])
def add_flavor():  # Changed from add_flavor_route to add_flavor
    if request.method == 'POST':
        name = request.form['name'].strip()
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO flavors (name) VALUES (?)', (name,))
            conn.commit()
            conn.close()
            flash(f'Flavor "{name}" added successfully')
            return redirect(url_for('production'))
        except sqlite3.IntegrityError:
            conn.close()
            flash(f'Flavor "{name}" already exists')
    
    return render_template('add_flavor.html')

@app.route('/add_market', methods=['GET', 'POST'])
def add_market():
    if request.method == 'POST':
        name = request.form['name'].strip()
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO markets (name) VALUES (?)', (name,))
            conn.commit()
            conn.close()
            flash(f'Market "{name}" added successfully')
            return redirect(url_for('markets'))
        except sqlite3.IntegrityError:
            conn.close()
            flash(f'Market "{name}" already exists')
    
    return render_template('add_market.html')

@app.route('/tapas_production')
def tapas_production():
    conn = get_db_connection()
    
    # Get all tapas production records
    production_records = conn.execute('''
        SELECT id, date, regular_dozens, ghee_dozens, notes
        FROM tapas_production
        ORDER BY date DESC, id DESC
    ''').fetchall()
    
    # Calculate totals
    totals = conn.execute('''
        SELECT COALESCE(SUM(regular_dozens), 0) AS total_regular,
               COALESCE(SUM(ghee_dozens), 0) AS total_ghee,
               COALESCE(SUM(regular_dozens + ghee_dozens), 0) AS grand_total
        FROM tapas_production
    ''').fetchone()
    
    # Get weekly totals
    weekly_totals = conn.execute('''
        SELECT strftime('%Y-%W', date) AS week,
               SUM(regular_dozens) AS regular,
               SUM(ghee_dozens) AS ghee,
               SUM(regular_dozens + ghee_dozens) AS total
        FROM tapas_production
        GROUP BY week
        ORDER BY week DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('tapas_production.html',
                           records=production_records,
                           totals=totals,
                           weekly_totals=weekly_totals)

@app.route('/edit_tapas_production/<int:id>', methods=['POST'])
def edit_tapas_production(id):
    conn = get_db_connection()
    action = request.form.get('action')
    
    if action == 'delete':
        conn.execute('DELETE FROM tapas_production WHERE id = ?', (id,))
        flash('Tapas production record deleted')
    
    elif action == 'edit':
        try:
            date_str = request.form['date']
            regular = float(request.form['regular_dozens'])
            ghee = float(request.form.get('ghee_dozens', 0))
            notes = request.form.get('notes', '').strip()
            
            conn.execute('''
                UPDATE tapas_production 
                SET date = ?, regular_dozens = ?, ghee_dozens = ?, notes = ?
                WHERE id = ?
            ''', (date_str, regular, ghee, notes, id))
            flash('Tapas production record updated')
        except (ValueError, KeyError):
            flash('Error updating record: Invalid data', 'error')
            
    conn.commit()
    conn.close()
    return redirect(url_for('tapas_production'))

if __name__ == '__main__':
    app.run(debug=True)