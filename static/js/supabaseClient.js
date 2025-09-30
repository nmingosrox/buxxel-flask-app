// This file initializes the Supabase client for use in the browser.
// It should be included in `layout.html` before other scripts that need it.

// IMPORTANT: These are public keys and are safe to be exposed in the browser.
// Supabase security is handled by Row Level Security (RLS) policies.
const SUPABASE_URL = 'https://prijdweukiutqyepplbp.supabase.co'; // ⚠️ Replace with your actual Supabase URL
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InByaWpkd2V1a2l1dHF5ZXBwbGJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTgwOTUyNTAsImV4cCI6MjA3MzY3MTI1MH0.WrHFuFCWdX1gV9X3LRODV7tNE0dvHZRy748rAT40foA'; // ⚠️ Replace with your actual Supabase Anon Key

// We will assign the initialized client to this variable.
window.supabaseClient = null;

try {
    if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
        throw new Error('Supabase URL and Anon Key are required. Please check your script.');
    }
    // Destructure createClient from the global supabase object provided by the CDN script
    const { createClient } = supabase;
    // Initialize the client and assign it to our variable
    window.supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
} catch (error) {
    console.error('Error initializing Supabase client:', error.message);
    // You could display a user-facing error here if Supabase is critical for the page to function.
    alert('Could not connect to the application service. Please try again later.');
}