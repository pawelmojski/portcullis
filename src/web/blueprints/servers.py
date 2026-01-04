"""
Servers Blueprint - Server management
"""
from flask import Blueprint, render_template, g, request, redirect, url_for, flash, abort
from flask_login import login_required

from src.core.database import Server, IPAllocation, ServerGroupMember
from src.core.ip_pool import IPPoolManager

servers_bp = Blueprint('servers', __name__)

@servers_bp.route('/')
@login_required
def index():
    """List all servers"""
    db = g.db
    servers = db.query(Server).order_by(Server.name).all()
    return render_template('servers/index.html', servers=servers)

@servers_bp.route('/view/<int:server_id>')
@login_required
def view(server_id):
    """View server details"""
    db = g.db
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        abort(404)
    
    # Get permanent IP allocation for this server
    allocation = db.query(IPAllocation).filter(
        IPAllocation.server_id == server.id,
        IPAllocation.is_active == True,
        IPAllocation.expires_at == None  # Permanent allocation
    ).first()
    
    return render_template('servers/view.html', server=server, allocation=allocation)

@servers_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new server"""
    if request.method == 'POST':
        db = g.db
        try:
            # Get port and determine protocol defaults
            port = int(request.form.get('port', 22))
            ssh_enabled = request.form.get('ssh_enabled') == 'on'
            rdp_enabled = request.form.get('rdp_enabled') == 'on'
            is_active = request.form.get('is_active', 'on') == 'on'
            
            # Set default ports based on enabled protocols
            ssh_port = port if ssh_enabled else 22
            rdp_port = port if rdp_enabled else 3389
            
            server = Server(
                name=request.form['name'],
                ip_address=request.form['address'],  # Template uses 'address', not 'ip_address'
                description=request.form.get('description'),
                os_type=None,  # Can be added to form later
                ssh_port=ssh_port,
                rdp_port=rdp_port,
                is_active=is_active
            )
            db.add(server)
            db.commit()
            db.refresh(server)
            
            # Optionally allocate proxy IP
            if request.form.get('allocate_ip') == 'on':
                pool_manager = IPPoolManager()
                proxy_ip = pool_manager.allocate_permanent_ip(db, server.id)
                if proxy_ip:
                    flash(f'Server {server.name} added with proxy IP {proxy_ip}!', 'success')
                else:
                    flash(f'Server {server.name} added but IP pool exhausted!', 'warning')
            else:
                flash(f'Server {server.name} added successfully!', 'success')
            
            return redirect(url_for('servers.view', server_id=server.id))
        except Exception as e:
            db.rollback()
            flash(f'Error adding server: {str(e)}', 'danger')
    
    return render_template('servers/add.html')

@servers_bp.route('/edit/<int:server_id>', methods=['GET', 'POST'])
@login_required
def edit(server_id):
    """Edit server"""
    db = g.db
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        abort(404)
    
    if request.method == 'POST':
        try:
            # Get port and determine protocol defaults
            port = int(request.form.get('port', 22))
            ssh_enabled = request.form.get('ssh_enabled') == 'on'
            rdp_enabled = request.form.get('rdp_enabled') == 'on'
            is_active = request.form.get('is_active', 'on') == 'on'
            
            # Set default ports based on enabled protocols
            ssh_port = port if ssh_enabled else 22
            rdp_port = port if rdp_enabled else 3389
            
            server.name = request.form['name']
            server.ip_address = request.form['address']  # Template uses 'address'
            server.description = request.form.get('description')
            server.ssh_port = ssh_port
            server.rdp_port = rdp_port
            server.is_active = is_active
            
            db.commit()
            flash(f'Server {server.name} updated successfully!', 'success')
            return redirect(url_for('servers.view', server_id=server.id))
        except Exception as e:
            db.rollback()
            flash(f'Error updating server: {str(e)}', 'danger')
    
    return render_template('servers/edit.html', server=server)

@servers_bp.route('/delete/<int:server_id>', methods=['POST'])
@login_required
def delete(server_id):
    """Delete server"""
    db = g.db
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        abort(404)
    
    try:
        name = server.name
        db.delete(server)
        db.commit()
        flash(f'Server {name} deleted successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting server: {str(e)}', 'danger')
    
    return redirect(url_for('servers.index'))
