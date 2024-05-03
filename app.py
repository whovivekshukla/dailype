from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import re, os, datetime, uuid

db_username = os.environ.get('DB_USERNAME')
db_password = os.environ.get('DB_PASSWORD')
db_host = os.environ.get('DB_HOST')
db_port = int(os.environ.get('DB_PORT', '5432'))  # Convert to integer, default port is 5432 if not specified
db_name = os.environ.get('DB_NAME')


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}"
db = SQLAlchemy(app)
migrate = Migrate(app, db)


class Manager(db.Model):
    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    # Add any other necessary fields for the Manager model

class User(db.Model):
    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = db.Column(db.String(120), nullable=False)
    mob_num = db.Column(db.String(15), nullable=False)
    pan_num = db.Column(db.String(10), nullable=False)
    manager_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('manager.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<User {self.full_name}>'

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET'])
def home():
    return jsonify({'message': 'Welcome to DailyPe Assignment!'}), 201

@app.route('/create_user', methods=['POST'])
def create_user():
    data = request.get_json()

    # Validations
    if not data.get('full_name'):
        return jsonify({'message': 'Full name is required'}), 400

    mob_num = data.get('mob_num')
    if not mob_num or not re.match(r'^(\+91|0)?[6-9]\d{9}$', mob_num):
        return jsonify({'message': 'Invalid mobile number'}), 400

    pan_num = data.get('pan_num', '').upper()
    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan_num):
        return jsonify({'message': 'Invalid PAN number'}), 400

    manager_id = data.get('manager_id')
    if manager_id:
        manager = Manager.query.get(manager_id)
        if not manager:
            return jsonify({'message': 'Invalid manager ID'}), 400

    # Check if user with same mob_num or pan_num already exists
    existing_user_by_mob_num = User.query.filter_by(mob_num=re.sub(r'^(\+91|0)', '', mob_num)).first()
    if existing_user_by_mob_num:
        return jsonify({'message': 'User with the same mobile number already exists'}), 400

    existing_user_by_pan_num = User.query.filter_by(pan_num=pan_num).first()
    if existing_user_by_pan_num:
        return jsonify({'message': 'User with the same PAN number already exists'}), 400

    # Create user
    new_user = User(
        full_name=data['full_name'],
        mob_num=re.sub(r'^(\+91|0)', '', mob_num),
        pan_num=pan_num
    )

    if manager_id:
        new_user.manager_id = manager_id

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully'}), 201


@app.route('/get_users', methods=['POST'])
def get_users():
    data = request.get_json()
    user_id = data.get('user_id')
    mob_num = data.get('mob_num')
    manager_id = data.get('manager_id')

    query = User.query.filter_by(is_active=True)

    # Filter by user_id if provided
    if user_id:
        query = query.filter_by(id=user_id)

    # Filter by mob_num if provided
    if mob_num:
        query = query.filter_by(mob_num=mob_num)

    # Filter by manager_id if provided
    if manager_id:
        query = query.filter_by(manager_id=manager_id)

    users = query.all()

    user_list = []
    for user in users:
        user_data = {
            'user_id': str(user.id),
            'manager_id': str(user.manager_id) if user.manager_id else None,
            'full_name': user.full_name,
            'mob_num': user.mob_num,
            'pan_num': user.pan_num,
            'created_at': user.created_at.isoformat(),
            'updated_at': user.updated_at.isoformat() if user.updated_at else None,
            'is_active': user.is_active
        }
        user_list.append(user_data)

    return jsonify(user_list), 200


@app.route('/delete_user', methods=['POST'])
def delete_user():
    data = request.get_json()
    user_id = data.get('user_id')
    mob_num = data.get('mob_num')

    if not user_id and not mob_num:
        return jsonify({'message': 'Either user_id or mob_num is required'}), 400

    if user_id:
        user = User.query.filter_by(id=user_id, is_active=True).first()
    else:
        user = User.query.filter_by(mob_num=mob_num, is_active=True).first()

    if not user:
        return jsonify({'message': 'User not found'}), 404

    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'User deleted successfully'}), 200

@app.route('/update_user', methods=['POST'])
def update_user():
    data = request.get_json()
    user_ids = data.get('user_ids')
    update_data = data.get('update_data')

    if not user_ids or not isinstance(user_ids, list):
        return jsonify({'message': 'user_ids is required and must be a list'}), 400

    if not update_data or not isinstance(update_data, dict):
        return jsonify({'message': 'update_data is required and must be an object'}), 400

    extra_keys = set(update_data.keys()) - {'manager_id'}
    if extra_keys:
        return jsonify({'message': f'Cannot update keys: {", ".join(extra_keys)} in bulk. These keys can be updated individually only.'}), 400

    manager_id_str = update_data.get('manager_id')
    if manager_id_str:
        try:
            manager_id = uuid.UUID(manager_id_str)
        except ValueError:
            return jsonify({'message': 'Invalid manager ID format'}), 400

        manager = Manager.query.filter_by(id=manager_id, is_active=True).first()
        if not manager:
            return jsonify({'message': 'Invalid manager ID'}), 400
    else:
        manager_id = None

    users_to_update = User.query.filter(User.id.in_(user_ids), User.is_active == True).all()
    if len(users_to_update) != len(user_ids):
        return jsonify({'message': 'One or more user IDs not found'}), 404

    for user in users_to_update:
        if manager_id_str:
            if user.manager_id == manager_id:
                return jsonify({'message': f"Manager ID is already '{manager_id_str}' for user {user.id}"}), 400

            if user.manager_id:
                user.is_active = False
                new_user = User(
                    full_name=user.full_name,
                    mob_num=user.mob_num,
                    pan_num=user.pan_num,
                    manager_id=manager_id,
                    created_at=user.created_at
                )
                db.session.add(new_user)
            else:
                user.manager_id = manager_id
                user.updated_at = datetime.datetime.utcnow()

    db.session.commit()
    return jsonify({'message': 'Users updated successfully'}), 200

@app.route('/create_manager', methods=['POST'])
def create_manager():
    data = request.get_json()

    # Validate full_name
    if not data.get('full_name'):
        return jsonify({'message': 'Full name is required'}), 400

    # Validate email
    email = data.get('email')
    if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        return jsonify({'message': 'Invalid email address'}), 400

    # Check if email already exists
    existing_manager = Manager.query.filter_by(email=email).first()
    if existing_manager:
        return jsonify({'message': 'Manager with the same email already exists'}), 400

    # Create new manager
    new_manager = Manager(
        full_name=data['full_name'],
        email=email
    )

    # Add manager to the database
    db.session.add(new_manager)
    db.session.commit()

    return jsonify({
        'manager_id': str(new_manager.id),
        'full_name': new_manager.full_name,
        'email': new_manager.email,
        'is_active': new_manager.is_active
    }), 201


@app.route('/get_managers', methods=['POST'])
def get_managers():
    managers = Manager.query.filter_by(is_active=True).all()

    if not managers:
        return jsonify({'managers': []}), 200

    manager_list = []
    for manager in managers:
        manager_data = {
            'manager_id': str(manager.id),
            'full_name': manager.full_name,
            'email': manager.email,
            'is_active': manager.is_active
        }
        manager_list.append(manager_data)

    return jsonify( manager_list), 200


@app.route('/wipe_database', methods=['POST'])
def wipe_database():
    # Add additional security checks or authentication mechanisms here
    with app.app_context():
        db.drop_all()
        db.create_all()
    return jsonify({'message': 'Database wiped and recreated successfully'}), 200


@app.route('/get_inactive_users', methods=['GET'])
def get_inactive_users():
    inactive_users = User.query.filter_by(is_active=False).all()

    if not inactive_users:
        return jsonify({'users': []}), 200

    user_list = []
    for user in inactive_users:
        user_data = {
            'user_id': str(user.id),
            'manager_id': str(user.manager_id) if user.manager_id else None,
            'full_name': user.full_name,
            'mob_num': user.mob_num,
            'pan_num': user.pan_num,
            'created_at': user.created_at.isoformat(),
            'updated_at': user.updated_at.isoformat() if user.updated_at else None,
            'is_active': user.is_active
        }
        user_list.append(user_data)

    return jsonify({'users': user_list}), 200


if __name__ == '__main__':
    app.run(debug=True)