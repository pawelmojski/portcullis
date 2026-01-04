"""
Server Groups Blueprint - Group management
"""
from flask import Blueprint, render_template, g, request, redirect, url_for, flash, abort
from flask_login import login_required

from src.core.database import ServerGroup, ServerGroupMember, Server

groups_bp = Blueprint('groups', __name__)

@groups_bp.route('/')
@login_required
def index():
    """List all server groups"""
    db = g.db
    groups = db.query(ServerGroup).order_by(ServerGroup.name).all()
    return render_template('groups/index.html', groups=groups)

@groups_bp.route('/view/<int:group_id>')
@login_required
def view(group_id):
    """View group details"""
    db = g.db
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if not group:
        abort(404)
    
    # Get all servers not in this group
    member_server_ids = [m.server_id for m in group.members]
    available_servers = db.query(Server).filter(
        ~Server.id.in_(member_server_ids) if member_server_ids else True
    ).order_by(Server.name).all()
    
    return render_template('groups/view.html', group=group, available_servers=available_servers)

@groups_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new group"""
    if request.method == 'POST':
        db = g.db
        try:
            group = ServerGroup(
                name=request.form['name'],
                description=request.form.get('description')
            )
            db.add(group)
            db.commit()
            flash(f'Group {group.name} added successfully!', 'success')
            return redirect(url_for('groups.view', group_id=group.id))
        except Exception as e:
            db.rollback()
            flash(f'Error adding group: {str(e)}', 'danger')
    
    return render_template('groups/add.html')

@groups_bp.route('/edit/<int:group_id>', methods=['GET', 'POST'])
@login_required
def edit(group_id):
    """Edit group"""
    db = g.db
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if not group:
        abort(404)
    
    if request.method == 'POST':
        try:
            group.name = request.form['name']
            group.description = request.form.get('description')
            db.commit()
            flash(f'Group {group.name} updated successfully!', 'success')
            return redirect(url_for('groups.view', group_id=group.id))
        except Exception as e:
            db.rollback()
            flash(f'Error updating group: {str(e)}', 'danger')
    
    return render_template('groups/edit.html', group=group)

@groups_bp.route('/delete/<int:group_id>', methods=['POST'])
@login_required
def delete(group_id):
    """Delete group"""
    db = g.db
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if not group:
        abort(404)
    
    try:
        name = group.name
        db.delete(group)
        db.commit()
        flash(f'Group {name} deleted successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting group: {str(e)}', 'danger')
    
    return redirect(url_for('groups.index'))

@groups_bp.route('/<int:group_id>/members/add', methods=['POST'])
@login_required
def add_member(group_id):
    """Add server to group"""
    db = g.db
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if not group:
        abort(404)
    
    try:
        server_id = int(request.form['server_id'])
        member = ServerGroupMember(
            server_id=server_id,
            group_id=group.id
        )
        db.add(member)
        db.commit()
        
        server = db.query(Server).filter(Server.id == server_id).first()
        flash(f'Server {server.name} added to group!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error adding server to group: {str(e)}', 'danger')
    
    return redirect(url_for('groups.view', group_id=group_id))

@groups_bp.route('/<int:group_id>/members/<int:member_id>/delete', methods=['POST'])
@login_required
def delete_member(group_id, member_id):
    """Remove server from group"""
    db = g.db
    member = db.query(ServerGroupMember).filter(
        ServerGroupMember.id == member_id,
        ServerGroupMember.group_id == group_id
    ).first()
    if not member:
        abort(404)
    
    try:
        server_name = member.server.name
        db.delete(member)
        db.commit()
        flash(f'Server {server_name} removed from group!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error removing server from group: {str(e)}', 'danger')
    
    return redirect(url_for('groups.view', group_id=group_id))
