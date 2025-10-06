# Buxxel Marketplace

Buxxel is a web application that functions as a simple marketplace. Users can sign up, log in, post items (listings) for sale, and browse items posted by others. It uses [Uploadcare](https://uploadcare.com/) for its file handling and CDN, features a client-side shopping cart, and a user dashboard for managing personal listings.

The application is built with a Python Flask backend and a dynamic frontend using JavaScript (with jQuery) and Bootstrap. It uses [Supabase](https://supabase.com/) as its all-in-one backend-as-a-service for database and authentication.

**For a complete breakdown of the project architecture, API endpoints, and code logic, please see the [Developer Documentation](developer_docs.html).**

---

## Local Setup Guide

### 1. Prerequisites

*   Python 3.8+ and `pip` installed.
*   A Supabase project. You will need the Project URL and the `service_role` key.
*   An Uploadcare account. You will need your Public Key.

### 2. Clone & Install

```bash
# Clone the repository
git clone <your-repo-url>
cd buxxel

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

Create a file named `.env` in the root directory and add your credentials:

```.env
# Supabase Credentials
SUPABASE_URL="https://your-project-ref.supabase.co"
SUPABASE_KEY="your-supabase-service-role-key"

# Uploadcare Credentials
UPLOADCARE_PUBLIC_KEY="your_uploadcare_public_key"
```

### 4. Set up Supabase

*   In your Supabase project, create the `listings` table. You can find the schema in the Developer Documentation.
*   Enable Row Level Security (RLS) on the `listings` table and add policies for `SELECT`, `INSERT`, `UPDATE`, and `DELETE`. Details are in the Developer Documentation.

### 5. Run the Application

```bash
flask run

# Or for development with auto-reloading:
flask --app app --debug run
```
The application will be available at `http://127.0.0.1:5000`.

### 6. Run Tests

From the root directory, run:
```bash
pytest -v
```
