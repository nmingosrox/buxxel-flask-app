from flask import Flask, render_template, request, jsonify
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)

# --- Supabase Integration ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Supabase URL and Key must be set in the .env file.")

supabase: Client = create_client(url, key)
# --------------------------

@app.route('/')
def home():
    """Renders the home page by fetching listings from Supabase."""
    try:
        # Fetch data from the 'listings' table, ordered by id
        print("Attempting to fetch listings from Supabase...")
        response = supabase.table('listings').select("*").order('id').execute()
        listings = response.data
        print(f"✅ Successfully fetched {len(listings)} listings.")
        return render_template('index.html', listings=listings)
    except Exception as e:
        print(f"❌ Failed to connect to Supabase or fetch listings: {e}")
        print("   Please check your .env file and Supabase table permissions.")
        # Render the page with an empty list so it doesn't crash
        return render_template('index.html', listings=[])

@app.route('/new-listing')
def new_listing_page():
    """Renders the page for creating a new listing."""
    return render_template('create_listing.html')

@app.route('/dashboard')
def dashboard_page():
    """Renders the user's dashboard page."""
    return render_template('dashboard.html')

@app.route('/edit-listing/<int:listing_id>')
def edit_listing_page(listing_id):
    """Renders the page for editing a specific listing."""
    return render_template('edit_listing.html', listing_id=listing_id)

@app.route('/signup', methods=['POST'])
def signup():
    """Handles user signup via Supabase Auth."""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not all([email, password]):
            return jsonify({"error": "Email and password are required."}), 400

        # Simplified Supabase sign up, only using email and password.
        supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        return jsonify({"message": "Signup successful! You can now log in."}), 201
    except Exception as e:
        # Simplified error handling, as the database trigger is no longer a factor.
        error_message = str(e)
        return jsonify({"error": error_message}), 400

@app.route('/login', methods=['POST'])
def login():
    """Handles user login via Supabase Auth."""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({"error": "Email and password are required."}), 400

        # Supabase's sign_in_with_password requires an email.
        session = supabase.auth.sign_in_with_password({"email": email, "password": password})

        return jsonify(session.dict()), 200
    except Exception as e:
        error_message = str(e)
        return jsonify({"error": "Invalid email or password."}), 401

@app.route('/api/listings', methods=['POST'])
def create_listing():
    """Creates a new listing in the database. This is a protected route."""
    try:
        # 1. Get the JWT from the Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization header is missing or invalid."}), 401
        
        jwt = auth_header.split(' ')[1]

        # 2. Verify the JWT and get the user
        user_response = supabase.auth.get_user(jwt)
        user = user_response.user
        if not user:
            return jsonify({"error": "Invalid or expired token."}), 401

        # 3. Get listing data from the request body
        data = request.get_json()
        name = data.get('name')
        price = data.get('price')
        category = data.get('category')
        image = data.get('image')
        description = data.get('description')
        stock = data.get('stock')

        if not all([name, price is not None, category, image, description, stock is not None]):
            return jsonify({"error": "Missing required listing data."}), 400

        # 4. Insert the new listing into the database, including the user's ID
        listing_data = {
            "name": name,
            "price": price,
            "category": category,
            "image": image,
            "description": description,
            "stock": stock,
            "user_id": user.id # Associate the listing with the logged-in user
        }
        
        response = supabase.table('listings').insert(listing_data).execute()

        return jsonify(response.data[0]), 201
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/me/listings', methods=['GET'])
def get_user_listings():
    """Fetches all listings created by the currently authenticated user."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization header is missing or invalid."}), 401
        
        jwt = auth_header.split(' ')[1]
        user_response = supabase.auth.get_user(jwt)
        user = user_response.user
        if not user:
            return jsonify({"error": "Invalid or expired token."}), 401

        response = supabase.table('listings').select("*").eq('user_id', user.id).order('id').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/listings/<int:listing_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_listing(listing_id):
    """Handles fetching, updating, or deleting a single listing for the authenticated user."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization header is missing or invalid."}), 401
        
        jwt = auth_header.split(' ')[1]
        user_response = supabase.auth.get_user(jwt)
        user = user_response.user
        if not user:
            return jsonify({"error": "Invalid or expired token."}), 401

        # The user must own the listing for any operation
        # We can check this once at the beginning for all methods

        if request.method == 'GET':
            # Fetch a single listing, ensuring the user owns it.
            response = supabase.table('listings').select("*").eq('id', listing_id).eq('user_id', user.id).single().execute()
            if not response.data:
                return jsonify({"error": "Listing not found or you do not have permission to view it."}), 404
            return jsonify(response.data), 200

        if request.method == 'PUT':
            # Update a listing. RLS policy will enforce ownership.
            data = request.get_json()
            update_data = {
                "name": data.get('name'),
                "price": data.get('price'),
                "category": data.get('category'),
                "image": data.get('image'),
                "description": data.get('description'),
                "stock": data.get('stock')
            }
            # Remove keys with None values so we don't overwrite with null
            update_data = {k: v for k, v in update_data.items() if v is not None}
            if not update_data:
                return jsonify({"error": "No update data provided."}), 400

            response = supabase.table('listings').update(update_data).eq('id', listing_id).eq('user_id', user.id).execute()
            if not response.data:
                 return jsonify({"error": "Update failed. Listing not found or you do not have permission."}), 404
            return jsonify(response.data[0]), 200

        if request.method == 'DELETE':
            # Delete a listing. RLS policy will enforce ownership.
            response = supabase.table('listings').delete().eq('id', listing_id).eq('user_id', user.id).execute()
            if not response.data:
                return jsonify({"error": "Delete failed. Listing not found or you do not have permission."}), 404
            return jsonify({"message": "Listing deleted successfully."}), 200

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)