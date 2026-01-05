"""
User Groups Blueprint - Hierarchical user group management
"""
from flask import Blueprint, render_template, g, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required

from src.core.database import (
    UserGroup, UserGroupMember, User, 
    validate_no_group_cycle, get_all_user_groups
)

user_groups_bp = Blueprint('user_groups', __name__)

@user_groups_bp.route('/')
@login_required
def index():
    """List all user groups with hierarchy"""
    db = g.db
    groups = db.query(UserGroup).order_by(UserGroup.name).all()
    
    # Build hierarchy tree
    root_groups = [g for g in groups if g.parent_group_id is None]
    
    return render_template('user_groups/index.html', 
                         groups=groups, 
                         root_groups=root_groups)

@user_groups_bp.route('/view/<int:group_id>')
@login_required
def view(group_id):
    """View group details with members"""
    db = g.db
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        abort(404)
    
    # Get all users not in this group
    member_user_ids = [m.user_id for m in group.members]
    available_users = db.query(User).filter(
        User.is_active == True,
        ~User.id.in_(member_user_ids) if member_user_ids else True
    ).order_by(User.username).all()
    
    # Get parent chain
    parent_chain = []
    current = group.parent_group
    while current:
        parent_chain.append(current)
        current = current.parent_group
    parent_chain.reverse()
    
    # Get all child groups (direct)
    child_groups = group.child_groups
    
    return render_template('user_groups/view.html', 
                         group=group, 
                         available_users=available_users,
                         parent_chain=parent_chain,
                         child_groups=child_groups)

@user_groups_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new user group"""
    db = g.db
    
    if request.method == 'POST':
        try:
            parent_id = request.form.get('parent_group_id')
            parent_id = int(parent_id) if parent_id and parent_id != '' else None
            
            group = UserGroup(
                name=request.form['name'],
                description=request.form.get('description'),
                parent_group_id=parent_id
            )
            
            # Validate no cycles (will be None for new group, but check parent chain)
            if parent_id:
                # Check that parent exists and no cycle would occur
                parent = db.query(UserGroup).filter(UserGroup.id == parent_id).first()
                if not parent:
                    flash('Parent group not found', 'danger')
                    return redirect(url_for('user_groups.add'))
            
            db.add(group)
            db.commit()
            flash(f'Group {group.name} created successfully!', 'success')
            return redirect(url_for('user_groups.view', group_id=group.id))
            
        except Exception as e:
            db.rollback()
            flash(f'Error creating group: {str(e)}', 'danger')
    
    # Get all groups for parent selection
    all_groups = db.query(UserGroup).order_by(UserGroup.name).all()
    return render_template('user_groups/add.html', all_groups=all_groups)

@user_groups_bp.route('/edit/<int:group_id>', methods=['GET', 'POST'])
@login_required
def edit(group_id):
    """Edit user group"""
    db = g.db
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        abort(404)
    
    if request.method == 'POST':
        try:
            parent_id = request.form.get('parent_group_id')
            parent_id = int(parent_id) if parent_id and parent_id != '' else None
            
            # Validate no cycles
            if parent_id and parent_id != group.parent_group_id:
                try:
                    validate_no_group_cycle(group.id, parent_id, db, UserGroup)
                except ValueError as e:
                    flash(str(e), 'danger')
                    return redirect(url_for('user_groups.edit', group_id=group_id))
            
            group.name = request.form['name']
            group.description = request.form.get('description')
            group.parent_group_id = parent_id
            
            db.commit()
            flash(f'Group {group.name} updated successfully!', 'success')
            return redirect(url_for('user_groups.view', group_id=group.id))
            
        except Exception as e:
            db.rollback()
            flash(f'Error updating group: {str(e)}', 'danger')
    
    # Get all groups except this one for parent selection
    all_groups = db.query(UserGroup).filter(UserGroup.id != group_id).order_by(UserGroup.name).all()
    return render_template('user_groups/edit.html', group=group, all_groups=all_groups)

@user_groups_bp.route('/delete/<int:group_id>', methods=['POST'])
@login_required
def delete(group_id):
    """Delete user group"""
    db = g.db
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        abort(404)
    
    # Check if group has child groups
    if group.child_groups:
        flash(f'Cannot delete group with child groups. Delete or reassign children first.', 'danger')
        return redirect(url_for('user_groups.view', group_id=group_id))
    
    try:
        name = group.name
        db.delete(group)
        db.commit()
        flash(f'Group {name} deleted successfully!', 'success')
        return redirect(url_for('user_groups.index'))
    except Exception as e:
        db.rollback()
        flash(f'Error deleting group: {str(e)}', 'danger')
        return redirect(url_for('user_groups.view', group_id=group_id))

@user_groups_bp.route('/<int:group_id>/add_member', methods=['POST'])
@login_required
def add_member(group_id):
    """Add user to group"""
    db = g.db
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        abort(404)
    
    user_id = request.form.get('user_id', type=int)
    if not user_id:
        flash('User ID required', 'danger')
        return redirect(url_for('user_groups.view', group_id=group_id))
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('user_groups.view', group_id=group_id))
    
    # Check if already member
    existing = db.query(UserGroupMember).filter(
        UserGroupMember.user_group_id == group_id,
        UserGroupMember.user_id == user_id
    ).first()
    
    if existing:
        flash(f'User {user.username} is already in group {group.name}', 'warning')
    else:
        try:
            member = UserGroupMember(
                user_group_id=group_id,
                user_id=user_id
            )
            db.add(member)
            db.commit()
            flash(f'User {user.username} added to group {group.name}', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Error adding member: {str(e)}', 'danger')
    
    return redirect(url_for('user_groups.view', group_id=group_id))

@user_groups_bp.route('/<int:group_id>/remove_member/<int:user_id>', methods=['POST'])
@login_required
def remove_member(group_id, user_id):
    """Remove user from group"""
    db = g.db
    
    member = db.query(UserGroupMember).filter(
        UserGroupMember.user_group_id == group_id,
        UserGroupMember.user_id == user_id
    ).first()
    
    if not member:
        flash('Member not found', 'danger')
    else:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
            
            db.delete(member)
            db.commit()
            flash(f'User {user.username if user else user_id} removed from group {group.name if group else group_id}', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Error removing member: {str(e)}', 'danger')
    
    return redirect(url_for('user_groups.view', group_id=group_id))

@user_groups_bp.route('/api/hierarchy')
@login_required
def api_hierarchy():
    """Return group hierarchy as JSON for tree visualization"""
    db = g.db
    groups = db.query(UserGroup).all()
    
    def build_node(group):
        return {
            'id': group.id,
            'name': group.name,
            'description': group.description,
            'member_count': len(group.members),
            'children': [build_node(child) for child in group.child_groups]
        }
    
    root_groups = [g for g in groups if g.parent_group_id is None]
    tree = [build_node(g) for g in root_groups]
    
    return jsonify(tree)
